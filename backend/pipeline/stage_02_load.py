"""
Stage 02 — Load

Load every file listed in 01_discover_manifest.json into one DataFrame.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pdfplumber

from backend.utils.config import DATA_PROCESSED, DATA_RAW
from backend.utils.logger import get_logger
from backend.utils import pipeline_state

logger = get_logger("efl_indexdb.pipeline.load")

STAGE_NAME = "Load"
MANIFEST_PATH = DATA_PROCESSED / "01_discover_manifest.json"
PARQUET_PATH = DATA_PROCESSED / "02_loaded.parquet"
REPORT_PATH = DATA_PROCESSED / "02_load_report.json"


def _load_manifest(path: Path = MANIFEST_PATH) -> list[dict]:
    if not path.exists():
        raise RuntimeError(
            f"Discover manifest not found at {path}. "
            "Run stage Discover first: python -m backend.pipeline.stage_01_discover"
        )
    with path.open("r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    files = manifest.get("files") or []
    if not files:
        raise RuntimeError(
            "Discover manifest contains no files. "
            "Place datasets in data/raw/ and re-run Discover."
        )
    return files


def _discovery_failed(entry: dict) -> bool:
    """Skip entries that did not discover cleanly."""
    if entry.get("error") or entry.get("failed") is True:
        return True
    if not entry.get("path") or not entry.get("ext"):
        return True
    if entry.get("size_bytes") is None:
        return True
    return False


def _resolve_encoding(encoding: str | None) -> str:
    if not encoding or encoding.lower() in {"unknown", "none", "ascii"}:
        # chardet often reports "ascii" for mostly-ASCII UTF-8 files; utf-8 is safer
        return "utf-8"
    return encoding


def _load_csv(path: Path, encoding: str) -> pd.DataFrame:
    candidates = [encoding]
    for fallback in ("utf-8", "utf-8-sig", "latin-1"):
        if fallback not in candidates:
            candidates.append(fallback)
    last_err: Exception | None = None
    for enc in candidates:
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False)
        except UnicodeDecodeError as exc:
            last_err = exc
            logger.info("CSV decode with %s failed for %s; trying next encoding", enc, path.name)
    raise last_err or UnicodeDecodeError("utf-8", b"", 0, 1, f"Could not decode {path}")


def _json_dict_of_lists_to_frame(data: dict) -> pd.DataFrame:
    """Flatten {category: [items...]} vocabulary/metadata JSON into rows."""
    rows: list[dict] = []
    for key, value in data.items():
        if isinstance(value, list):
            for item in value:
                rows.append(
                    {
                        "topic_domain": str(key),
                        "raw_text": str(item),
                        "title": str(item),
                    }
                )
        else:
            rows.append(
                {
                    "topic_domain": str(key),
                    "raw_text": str(value),
                    "title": str(key),
                }
            )
    if not rows:
        raise ValueError("JSON object produced zero rows")
    return pd.DataFrame(rows)


def _load_json(path: Path, encoding: str) -> pd.DataFrame:
    try:
        return pd.read_json(path, orient="records", encoding=encoding)
    except (ValueError, TypeError) as first_err:
        logger.info(
            "read_json(orient=records) failed for %s (%s); trying lines=True",
            path.name,
            first_err,
        )
        try:
            return pd.read_json(path, lines=True, encoding=encoding)
        except (ValueError, TypeError) as second_err:
            logger.info(
                "read_json(lines=True) failed for %s (%s); trying dict-of-lists flatten",
                path.name,
                second_err,
            )
            with path.open("r", encoding=encoding, errors="replace") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return _json_dict_of_lists_to_frame(data)
            if isinstance(data, list):
                return pd.json_normalize(data)
            raise ValueError(f"Unsupported JSON structure in {path.name}: {type(data)}") from second_err


def _load_jsonl(path: Path, encoding: str) -> pd.DataFrame:
    return pd.read_json(path, lines=True, encoding=encoding)


def _load_txt(path: Path, encoding: str) -> pd.DataFrame:
    with path.open("r", encoding=encoding, errors="replace") as fh:
        lines = [line.rstrip("\n\r") for line in fh]
    return pd.DataFrame({"raw_text": lines})


def _load_pdf(path: Path) -> pd.DataFrame:
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text)
    return pd.DataFrame({"raw_text": pages})


def _load_one(entry: dict) -> tuple[pd.DataFrame, dict]:
    rel = entry["path"]
    ext = str(entry["ext"]).lower()
    encoding = _resolve_encoding(entry.get("encoding"))
    abs_path = DATA_RAW / rel

    if not abs_path.exists():
        raise FileNotFoundError(f"Listed in manifest but missing on disk: {abs_path}")

    if ext == ".csv":
        df = _load_csv(abs_path, encoding)
    elif ext == ".json":
        df = _load_json(abs_path, encoding)
    elif ext == ".jsonl":
        df = _load_jsonl(abs_path, encoding)
    elif ext == ".txt":
        df = _load_txt(abs_path, encoding)
    elif ext == ".pdf":
        df = _load_pdf(abs_path)
    else:
        raise ValueError(f"Unsupported extension for Load stage: {ext}")

    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)

    df = df.copy()
    df["source_file"] = rel
    df["source_ext"] = ext

    report = {
        "path": rel,
        "ext": ext,
        "rows": int(len(df)),
        "status": "ok",
    }
    return df, report


def run() -> dict:
    pipeline_state.mark_running(STAGE_NAME)
    try:
        entries = _load_manifest()
        frames: list[pd.DataFrame] = []
        file_reports: list[dict] = []

        for entry in entries:
            rel = entry.get("path", "<unknown>")
            if _discovery_failed(entry):
                logger.warning("skipping failed discovery entry: %s", entry)
                file_reports.append(
                    {
                        "path": rel,
                        "ext": entry.get("ext"),
                        "rows": 0,
                        "status": "skipped_discovery_failed",
                    }
                )
                continue

            try:
                df, report = _load_one(entry)
                frames.append(df)
                file_reports.append(report)
                logger.info("loaded %s → %s rows", rel, report["rows"])
            except Exception as exc:  # noqa: BLE001 — record per-file failure
                logger.exception("failed to load %s", rel)
                file_reports.append(
                    {
                        "path": rel,
                        "ext": entry.get("ext"),
                        "rows": 0,
                        "status": "failed",
                        "error": str(exc),
                    }
                )

        if not frames:
            raise RuntimeError(
                "Load produced zero DataFrames. Check discover manifest and raw files."
            )

        combined = pd.concat(frames, axis=0, ignore_index=True, sort=False)
        DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
        combined.to_parquet(PARQUET_PATH, engine="pyarrow", index=False)
        logger.info("wrote %s (%s rows)", PARQUET_PATH, len(combined))

        report = {
            "stage": STAGE_NAME,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "files": file_reports,
            "total_rows": int(len(combined)),
            "output": str(PARQUET_PATH.as_posix()),
        }
        with REPORT_PATH.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
            fh.write("\n")
        logger.info("wrote load report → %s (total_rows=%s)", REPORT_PATH, report["total_rows"])

        pipeline_state.mark_complete(STAGE_NAME)
        return report
    except Exception:
        pipeline_state.mark_failed(STAGE_NAME)
        raise


if __name__ == "__main__":
    run()

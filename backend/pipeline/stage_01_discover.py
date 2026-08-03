"""
Stage 01 — Discover

Scan data/raw/ and write a discovery manifest for EFL IndexDB.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import chardet
from tabulate import tabulate

from backend.utils.config import (
    DATA_PROCESSED,
    DATA_RAW,
    RAW_IGNORE_NAMES,
    SUPPORTED_RAW_EXTENSIONS,
)
from backend.utils.logger import get_logger
from backend.utils import pipeline_state

logger = get_logger("efl_indexdb.pipeline.discover")

STAGE_NAME = "Discover"
MANIFEST_PATH = DATA_PROCESSED / "01_discover_manifest.json"
SAMPLE_BYTES = 65_536


def _is_raw_empty(raw_dir: Path) -> bool:
    if not raw_dir.exists():
        return True
    for path in raw_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.name in RAW_IGNORE_NAMES:
            continue
        return False
    return True


def _detect_encoding(path: Path) -> str:
    try:
        with path.open("rb") as fh:
            raw = fh.read(SAMPLE_BYTES)
        if not raw:
            return "unknown"
        result = chardet.detect(raw) or {}
        encoding = result.get("encoding") or "unknown"
        return str(encoding).lower()
    except OSError:
        return "unknown"


def _estimate_rows(path: Path, ext: str) -> int | None:
    if ext == ".pdf":
        return None
    encoding = _detect_encoding(path)
    enc = "utf-8" if encoding in {"unknown", "ascii"} else encoding
    try:
        with path.open("r", encoding=enc, errors="replace") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return None


def discover_files(raw_dir: Path | None = None) -> list[dict]:
    root = raw_dir or DATA_RAW
    if _is_raw_empty(root):
        raise RuntimeError(
            "data/raw/ is empty (no datasets found). "
            "Place EFL dataset files in data/raw/ before running the Discover stage. "
            "See data/raw/README_PLACE_DATASETS_HERE.txt for supported formats."
        )

    files: list[dict] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name in RAW_IGNORE_NAMES:
            continue

        ext = path.suffix.lower()
        if ext not in SUPPORTED_RAW_EXTENSIONS:
            logger.warning("unsupported file type skipped: %s (ext=%s)", path, ext or "<none>")
            continue

        rel = path.relative_to(root).as_posix()
        size_bytes = path.stat().st_size
        encoding = _detect_encoding(path)
        rows_estimate = _estimate_rows(path, ext)

        record = {
            "path": rel,
            "ext": ext,
            "size_bytes": size_bytes,
            "rows_estimate": rows_estimate,
            "encoding": encoding,
        }
        files.append(record)
        logger.info(
            "discovered %s | %s | %s bytes | rows=%s | enc=%s",
            rel,
            ext,
            size_bytes,
            rows_estimate,
            encoding,
        )

    if not files:
        raise RuntimeError(
            "data/raw/ contains files, but none with supported extensions "
            "(.csv, .json, .jsonl, .txt, .pdf). Place supported EFL datasets in data/raw/."
        )
    return files


def print_summary(files: list[dict]) -> None:
    table = [
        [
            f["path"],
            f["ext"],
            f["size_bytes"],
            f["rows_estimate"] if f["rows_estimate"] is not None else "n/a (pdf)",
            f["encoding"],
        ]
        for f in files
    ]
    print(
        tabulate(
            table,
            headers=["path", "ext", "size_bytes", "rows_estimate", "encoding"],
            tablefmt="github",
        )
    )
    print(f"\nTotal files discovered: {len(files)}")


def run() -> dict:
    pipeline_state.mark_running(STAGE_NAME)
    try:
        files = discover_files()
        manifest = {
            "stage": STAGE_NAME,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "files": files,
        }
        DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
        with MANIFEST_PATH.open("w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
            fh.write("\n")
        logger.info("wrote manifest → %s", MANIFEST_PATH)
        print_summary(files)
        pipeline_state.mark_complete(STAGE_NAME)
        return manifest
    except Exception:
        pipeline_state.mark_failed(STAGE_NAME)
        raise


if __name__ == "__main__":
    run()

"""
Stage 03 — Integrate

Normalise columns to the canonical EFL schema and upsert into MetadataStore.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from backend.db.metadata_store import MetadataStore
from backend.utils.config import DATA_PROCESSED
from backend.utils.logger import get_logger
from backend.utils import pipeline_state

logger = get_logger("efl_indexdb.pipeline.integrate")

STAGE_NAME = "Integrate"
INPUT_PATH = DATA_PROCESSED / "02_loaded.parquet"
OUTPUT_PATH = DATA_PROCESSED / "03_integrated.parquet"
REPORT_PATH = DATA_PROCESSED / "03_integration_report.json"

CANONICAL_COLUMNS = [
    "resource_id",
    "title",
    "raw_text",
    "cefr_level",
    "skill_type",
    "topic_domain",
    "source_name",
    "source_url",
]

CEFR_ALLOWED = {"A1", "A2", "B1", "B2", "C1", "C2"}
SKILL_ALLOWED = {
    "Reading",
    "Writing",
    "Listening",
    "Speaking",
    "Grammar",
    "Vocabulary",
}
TOPIC_ALLOWED = {
    "Business",
    "Science",
    "Culture",
    "Technology",
    "Daily Life",
    "Academic",
    "Travel",
    "Health",
}

COLUMN_ALIASES: dict[str, str] = {
    "level": "cefr_level",
    "label": "cefr_level",
    "cefr": "cefr_level",
    "cefr_level": "cefr_level",
    "skill": "skill_type",
    "skill_type": "skill_type",
    "topic": "topic_domain",
    "topic_domain": "topic_domain",
    "text": "raw_text",
    "content": "raw_text",
    "body": "raw_text",
    "essay": "raw_text",
    "full_text": "raw_text",
    "excerpt": "raw_text",
    "raw_text": "raw_text",
    "name": "title",
    "heading": "title",
    "title": "title",
    "question": "title",
    "prompt": "title",
    "url": "source_url",
    "source_url": "source_url",
    "source": "source_name",
    "source_name": "source_name",
    "id": "resource_id",
    "text_id": "resource_id",
    "resource_id": "resource_id",
}

def _norm_col(name: str) -> str:
    cleaned = str(name).strip().lower()
    cleaned = re.sub(r"[\s\-]+", "_", cleaned)
    cleaned = re.sub(r"[^a-z0-9_]", "", cleaned)
    return cleaned

def _apply_column_aliases(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    mapping: dict[str, str] = {}
    rename: dict[str, str] = {}
    for col in df.columns:
        norm = _norm_col(col)
        target = COLUMN_ALIASES.get(norm)
        if target:
            mapping[col] = target

            if target in df.columns and col != target:

                continue
            if target not in rename.values():
                rename[col] = target
            else:

                mapping[col] = target

    out = df.rename(columns=rename)

    for original, target in mapping.items():
        if original in out.columns and original != target:
            if target not in out.columns:
                out[target] = out[original]
            else:
                out[target] = out[target].where(out[target].notna() & (out[target].astype(str).str.len() > 0), out[original])
            if original != target and original in out.columns and original not in CANONICAL_COLUMNS:

                pass
    return out, mapping

def _series_str(series: pd.Series | None, index: pd.Index) -> pd.Series:
    if series is None:
        return pd.Series([None] * len(index), index=index, dtype="object")
    return series

def _null_if_blank(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    return text

def _normalise_cefr(value: object) -> str | None:
    text = _null_if_blank(value)
    if text is None:
        return None
    token = text.strip().upper().replace(" ", "")

    match = re.search(r"\b(A1|A2|B1|B2|C1|C2)\b", token)
    if match:
        token = match.group(1)
    return token if token in CEFR_ALLOWED else None

def _normalise_skill(value: object) -> str | None:
    text = _null_if_blank(value)
    if text is None:
        return None
    titled = text.strip().title()

    synonyms = {
        "Read": "Reading",
        "Write": "Writing",
        "Listen": "Listening",
        "Speak": "Speaking",
        "Vocab": "Vocabulary",
    }
    titled = synonyms.get(titled, titled)
    return titled if titled in SKILL_ALLOWED else None

def _normalise_topic(value: object) -> str | None:
    text = _null_if_blank(value)
    if text is None:
        return None

    cleaned = re.sub(r"\s+", " ", text.strip())
    titled = cleaned.title()
    if titled.lower() == "daily life":
        titled = "Daily Life"
    return titled if titled in TOPIC_ALLOWED else None

def _source_name_from_path(source_file: object) -> str | None:
    text = _null_if_blank(source_file)
    if text is None:
        return None
    parts = Path(text.replace("\\", "/")).parts
    if len(parts) >= 2:
        return parts[0]
    return Path(parts[-1]).stem if parts else None

def _title_from_text(raw_text: object) -> str | None:
    text = _null_if_blank(raw_text)
    if text is None:
        return None
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:80] if compact else None

def integrate(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    working, column_mapping = _apply_column_aliases(df)

    for col in list(working.columns):
        norm = _norm_col(col)
        target = COLUMN_ALIASES.get(norm)
        if not target or col == target:
            continue
        if target not in working.columns:
            working[target] = working[col]
        else:
            primary = working[target]
            secondary = working[col]
            working[target] = primary.where(primary.notna() & (primary.astype(str).str.strip() != ""), secondary)

    n = len(working)
    idx = working.index

    resource_id = _series_str(working.get("resource_id"), idx).map(
        lambda v: _null_if_blank(v) or str(uuid.uuid4())
    )
    raw_text = _series_str(working.get("raw_text"), idx).map(_null_if_blank)
    title = _series_str(working.get("title"), idx).map(_null_if_blank)
    title = [
        t if t is not None else _title_from_text(rt)
        for t, rt in zip(title.tolist(), raw_text.tolist(), strict=True)
    ]

    cefr_level = _series_str(working.get("cefr_level"), idx).map(_normalise_cefr)
    skill_type = _series_str(working.get("skill_type"), idx).map(_normalise_skill)
    topic_domain = _series_str(working.get("topic_domain"), idx).map(_normalise_topic)

    source_name_col = _series_str(working.get("source_name"), idx).map(_null_if_blank)
    source_file_col = _series_str(working.get("source_file"), idx)
    source_name = [
        sn if sn is not None else _source_name_from_path(sf)
        for sn, sf in zip(source_name_col.tolist(), source_file_col.tolist(), strict=True)
    ]
    source_url = _series_str(working.get("source_url"), idx).map(_null_if_blank)

    out = pd.DataFrame(
        {
            "resource_id": resource_id.astype(str),
            "title": title,
            "raw_text": raw_text,
            "cefr_level": cefr_level,
            "skill_type": skill_type,
            "topic_domain": topic_domain,
            "source_name": source_name,
            "source_url": source_url,
        }
    )

    before = len(out)
    out = out.drop_duplicates(subset=["resource_id"], keep="first").reset_index(drop=True)
    dropped_dupes = before - len(out)
    if dropped_dupes:
        logger.info("dropped %s duplicate resource_id rows", dropped_dupes)

    null_counts = {col: int(out[col].isna().sum()) for col in CANONICAL_COLUMNS}
    report_meta = {
        "column_mapping_applied": column_mapping,
        "duplicate_resource_ids_dropped": dropped_dupes,
        "input_rows": n,
    }
    return out, {"null_counts_per_column": null_counts, **report_meta}

def run() -> dict:
    pipeline_state.mark_running(STAGE_NAME)
    try:
        if not INPUT_PATH.exists():
            raise RuntimeError(
                f"Missing {INPUT_PATH}. Run Load first: python -m backend.pipeline.stage_02_load"
            )

        loaded = pd.read_parquet(INPUT_PATH)
        logger.info("loaded %s rows from %s", len(loaded), INPUT_PATH)

        integrated, meta = integrate(loaded)
        DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
        integrated.to_parquet(OUTPUT_PATH, engine="pyarrow", index=False)
        logger.info("wrote %s (%s rows)", OUTPUT_PATH, len(integrated))

        store = MetadataStore()
        upserted = store.upsert_many(integrated)
        logger.info("metadata store now has %s rows (upserted %s)", store.count(), upserted)

        report = {
            "stage": STAGE_NAME,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "total_rows": int(len(integrated)),
            "null_counts_per_column": meta["null_counts_per_column"],
            "column_mapping_applied": meta["column_mapping_applied"],
            "duplicate_resource_ids_dropped": meta["duplicate_resource_ids_dropped"],
            "metadata_upserted": upserted,
            "output": str(OUTPUT_PATH.as_posix()),
        }
        with REPORT_PATH.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
            fh.write("\n")
        logger.info("wrote integration report → %s", REPORT_PATH)

        pipeline_state.mark_complete(STAGE_NAME)
        return report
    except Exception:
        pipeline_state.mark_failed(STAGE_NAME)
        raise

if __name__ == "__main__":
    run()

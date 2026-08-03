"""
Stage 05 — Clean

Remove noise and standardise text for embedding (EFL IndexDB).
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from backend.utils.config import DATA_PROCESSED
from backend.utils.logger import get_logger
from backend.utils import pipeline_state

logger = get_logger("efl_indexdb.pipeline.clean")

STAGE_NAME = "Clean"
INPUT_PATH = DATA_PROCESSED / "03_integrated.parquet"
OUTPUT_PATH = DATA_PROCESSED / "05_cleaned.parquet"
REPORT_PATH = DATA_PROCESSED / "05_clean_report.json"

MAX_TOKENS = 512
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_html(text: str) -> str:
    soup = BeautifulSoup(text, "lxml")
    return soup.get_text(separator=" ")


def _normalise_unicode(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def _collapse_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _truncate_tokens(text: str, max_tokens: int = MAX_TOKENS) -> str:
    tokens = text.split(" ")
    if len(tokens) <= max_tokens:
        return text
    return " ".join(tokens[:max_tokens])


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict], int, int]:
    steps_log: list[dict] = []
    working = df.copy()
    rows_before = len(working)

    # 1. Drop null / too-short raw_text
    text = working["raw_text"].fillna("").astype(str)
    keep_mask = text.map(lambda t: len(t.strip()) >= 20)
    dropped = int((~keep_mask).sum())
    working = working.loc[keep_mask].copy()
    steps_log.append(
        {
            "step": 1,
            "name": "drop_null_or_short_raw_text",
            "rows_removed": dropped,
            "rows_remaining": int(len(working)),
        }
    )
    logger.info("step 1 drop short/null raw_text: removed %s → %s left", dropped, len(working))

    # 2–5 operate on remaining rows
    raw_series = working["raw_text"].fillna("").astype(str)

    stripped = raw_series.map(_strip_html)
    steps_log.append(
        {
            "step": 2,
            "name": "strip_html",
            "rows_removed": 0,
            "rows_remaining": int(len(working)),
            "note": "BeautifulSoup lxml get_text applied to all remaining rows",
        }
    )
    logger.info("step 2 strip HTML: processed %s rows", len(working))

    normalised = stripped.map(_normalise_unicode)
    steps_log.append(
        {
            "step": 3,
            "name": "normalise_unicode_nfkc",
            "rows_removed": 0,
            "rows_remaining": int(len(working)),
        }
    )
    logger.info("step 3 unicode NFKC: processed %s rows", len(working))

    collapsed = normalised.map(_collapse_whitespace)
    # Re-check length after whitespace collapse (empty-ish after HTML strip)
    keep_after_collapse = collapsed.map(lambda t: len(t.strip()) >= 20)
    dropped_after = int((~keep_after_collapse).sum())
    working = working.loc[keep_after_collapse].copy()
    collapsed = collapsed.loc[keep_after_collapse]
    steps_log.append(
        {
            "step": 4,
            "name": "collapse_whitespace",
            "rows_removed": dropped_after,
            "rows_remaining": int(len(working)),
        }
    )
    logger.info(
        "step 4 collapse whitespace: removed %s empty-after-clean → %s left",
        dropped_after,
        len(working),
    )

    raw_text_full = collapsed.copy()
    truncated = collapsed.map(_truncate_tokens)
    truncated_count = int((raw_text_full.str.split().map(len) > MAX_TOKENS).sum())
    working["raw_text_full"] = raw_text_full.to_numpy()
    working["raw_text"] = truncated.to_numpy()
    steps_log.append(
        {
            "step": 5,
            "name": "truncate_to_512_tokens",
            "rows_removed": 0,
            "rows_remaining": int(len(working)),
            "rows_truncated": truncated_count,
            "max_tokens": MAX_TOKENS,
        }
    )
    logger.info(
        "step 5 truncate to %s tokens: truncated %s rows; full text in raw_text_full",
        MAX_TOKENS,
        truncated_count,
    )

    working = working.reset_index(drop=True)
    rows_after = len(working)
    return working, steps_log, rows_before, rows_after


def run() -> dict:
    pipeline_state.mark_running(STAGE_NAME)
    try:
        if not INPUT_PATH.exists():
            raise RuntimeError(
                f"Missing {INPUT_PATH}. Run Integrate first: "
                "python -m backend.pipeline.stage_03_integrate"
            )

        df = pd.read_parquet(INPUT_PATH)
        logger.info("loaded %s rows from %s", len(df), INPUT_PATH)

        cleaned, steps_log, rows_before, rows_after = clean_dataframe(df)
        DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
        cleaned.to_parquet(OUTPUT_PATH, engine="pyarrow", index=False)
        logger.info("wrote %s (%s rows)", OUTPUT_PATH, rows_after)

        report = {
            "stage": STAGE_NAME,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "rows_before": rows_before,
            "rows_after": rows_after,
            "rows_dropped": rows_before - rows_after,
            "steps_log": steps_log,
            "output": str(OUTPUT_PATH.as_posix()),
        }
        with REPORT_PATH.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
            fh.write("\n")
        logger.info(
            "clean report: before=%s after=%s dropped=%s → %s",
            rows_before,
            rows_after,
            report["rows_dropped"],
            REPORT_PATH,
        )

        pipeline_state.mark_complete(STAGE_NAME)
        return report
    except Exception:
        pipeline_state.mark_failed(STAGE_NAME)
        raise


if __name__ == "__main__":
    run()

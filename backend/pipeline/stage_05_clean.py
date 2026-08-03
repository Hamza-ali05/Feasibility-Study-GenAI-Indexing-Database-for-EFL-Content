"""
Stage 05 — Clean

Remove noise and standardise text for embedding (EFL IndexDB).
Cleaning rules live in ``backend.utils.text_cleaning`` (shared with Analyzer).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from backend.utils.config import DATA_PROCESSED
from backend.utils.logger import get_logger
from backend.utils import pipeline_state
from backend.utils.text_cleaning import clean_dataframe

logger = get_logger("efl_indexdb.pipeline.clean")

STAGE_NAME = "Clean"
INPUT_PATH = DATA_PROCESSED / "03_integrated.parquet"
OUTPUT_PATH = DATA_PROCESSED / "05_cleaned.parquet"
REPORT_PATH = DATA_PROCESSED / "05_clean_report.json"

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

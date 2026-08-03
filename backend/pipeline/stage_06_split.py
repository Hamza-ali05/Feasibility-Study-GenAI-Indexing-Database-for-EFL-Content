"""
Stage 06 — Split

Stratified train / validation / test split for EFL IndexDB.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
from sklearn.model_selection import train_test_split

from backend.utils.config import DATA_PROCESSED, DATA_SPLITS
from backend.utils.logger import get_logger
from backend.utils import pipeline_state

logger = get_logger("efl_indexdb.pipeline.split")

STAGE_NAME = "Split"
INPUT_PATH = DATA_PROCESSED / "05_cleaned.parquet"
TRAIN_PATH = DATA_SPLITS / "train" / "train.parquet"
VAL_PATH = DATA_SPLITS / "val" / "val.parquet"
TEST_PATH = DATA_SPLITS / "test" / "test.parquet"
REPORT_PATH = DATA_PROCESSED / "06_split_report.json"

RANDOM_STATE = 42
TRAIN_SIZE = 0.70
VAL_SIZE = 0.15
TEST_SIZE = 0.15
CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
MISSING_LABEL = "_MISSING_"


def _cefr_null_rate(df: pd.DataFrame) -> float:
    if "cefr_level" not in df.columns or len(df) == 0:
        return 1.0
    return float(df["cefr_level"].isna().mean())


def _choose_stratify_column(df: pd.DataFrame) -> str:
    null_rate = _cefr_null_rate(df)
    if null_rate > 0.40:
        logger.info(
            "cefr_level null rate=%.4f > 0.40 → stratifying by skill_type",
            null_rate,
        )
        return "skill_type"
    logger.info(
        "cefr_level null rate=%.4f ≤ 0.40 → stratifying by cefr_level",
        null_rate,
    )
    return "cefr_level"


def _stratify_labels(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([MISSING_LABEL] * len(df), index=df.index, dtype="object")
    return df[column].fillna(MISSING_LABEL).astype(str)


def _cefr_distribution(df: pd.DataFrame) -> dict[str, int]:
    if "cefr_level" not in df.columns:
        return {k: 0 for k in CEFR_ORDER}
    counts = df["cefr_level"].dropna().astype(str).value_counts()
    return {k: int(counts.get(k, 0)) for k in CEFR_ORDER}


def _split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    strat_col = _choose_stratify_column(df)
    labels = _stratify_labels(df, strat_col)

    # Relative split of the 30% holdout into equal val/test → 15% / 15% overall
    val_share_of_holdout = VAL_SIZE / (VAL_SIZE + TEST_SIZE)

    try:
        train_df, holdout_df = train_test_split(
            df,
            test_size=(1.0 - TRAIN_SIZE),
            random_state=RANDOM_STATE,
            stratify=labels,
        )
        holdout_labels = _stratify_labels(holdout_df, strat_col)
        val_df, test_df = train_test_split(
            holdout_df,
            test_size=(1.0 - val_share_of_holdout),
            random_state=RANDOM_STATE,
            stratify=holdout_labels,
        )
        logger.info("stratified split succeeded using column=%s", strat_col)
    except ValueError as exc:
        logger.warning(
            "stratified split failed (%s); falling back to random split "
            "with random_state=%s",
            exc,
            RANDOM_STATE,
        )
        train_df, holdout_df = train_test_split(
            df,
            test_size=(1.0 - TRAIN_SIZE),
            random_state=RANDOM_STATE,
            stratify=None,
        )
        val_df, test_df = train_test_split(
            holdout_df,
            test_size=(1.0 - val_share_of_holdout),
            random_state=RANDOM_STATE,
            stratify=None,
        )
        strat_col = f"{strat_col}_FAILED_RANDOM_FALLBACK"

    return (
        train_df.reset_index(drop=True),
        val_df.reset_index(drop=True),
        test_df.reset_index(drop=True),
        strat_col,
    )


def run() -> dict:
    pipeline_state.mark_running(STAGE_NAME)
    try:
        if not INPUT_PATH.exists():
            raise RuntimeError(
                f"Missing {INPUT_PATH}. Run Clean first: "
                "python -m backend.pipeline.stage_05_clean"
            )

        df = pd.read_parquet(INPUT_PATH)
        logger.info("loaded %s rows from %s", len(df), INPUT_PATH)

        train_df, val_df, test_df, strat_col = _split(df)

        for path in (TRAIN_PATH, VAL_PATH, TEST_PATH):
            path.parent.mkdir(parents=True, exist_ok=True)

        train_df.to_parquet(TRAIN_PATH, engine="pyarrow", index=False)
        val_df.to_parquet(VAL_PATH, engine="pyarrow", index=False)
        test_df.to_parquet(TEST_PATH, engine="pyarrow", index=False)
        logger.info(
            "wrote splits train=%s val=%s test=%s",
            len(train_df),
            len(val_df),
            len(test_df),
        )

        report = {
            "stage": STAGE_NAME,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "total": int(len(df)),
            "train_n": int(len(train_df)),
            "val_n": int(len(val_df)),
            "test_n": int(len(test_df)),
            "ratio": {"train": TRAIN_SIZE, "val": VAL_SIZE, "test": TEST_SIZE},
            "random_state": RANDOM_STATE,
            "stratify_column": strat_col,
            "cefr_null_rate": round(_cefr_null_rate(df), 4),
            "cefr_distribution_per_split": {
                "train": _cefr_distribution(train_df),
                "val": _cefr_distribution(val_df),
                "test": _cefr_distribution(test_df),
            },
            "outputs": {
                "train": str(TRAIN_PATH.as_posix()),
                "val": str(VAL_PATH.as_posix()),
                "test": str(TEST_PATH.as_posix()),
            },
        }
        with REPORT_PATH.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
            fh.write("\n")
        logger.info("wrote split report → %s", REPORT_PATH)

        pipeline_state.mark_complete(STAGE_NAME)
        return report
    except Exception:
        pipeline_state.mark_failed(STAGE_NAME)
        raise


if __name__ == "__main__":
    run()

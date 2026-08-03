"""
Stage 08 — Balance

Address CEFR class imbalance in the training set (embedding space).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from imblearn.over_sampling import RandomOverSampler, SMOTE

from backend.utils.config import DATA_EMBEDDINGS, DATA_PROCESSED, DATA_SPLITS
from backend.utils.logger import get_logger
from backend.utils import pipeline_state

logger = get_logger("efl_indexdb.pipeline.balance")

STAGE_NAME = "Balance"
TRAIN_PARQUET = DATA_SPLITS / "train" / "train.parquet"
TRAIN_EMBEDDINGS = DATA_EMBEDDINGS / "train_embeddings.npy"
TRAIN_IDS = DATA_EMBEDDINGS / "train_ids.json"

BALANCED_PARQUET = DATA_SPLITS / "train" / "balanced_train.parquet"
BALANCED_EMBEDDINGS = DATA_SPLITS / "train" / "balanced_embeddings.npy"
REPORT_PATH = DATA_PROCESSED / "08_balance_report.json"

IMBALANCE_RATIO_THRESHOLD = 3.0
SMOTE_MIN_SAMPLES = 6  # SMOTE default k_neighbors=5
RANDOM_STATE = 42
CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


def _class_counts(labels: pd.Series) -> dict[str, int]:
    counts = labels.astype(str).value_counts()
    # Prefer CEFR order first, then any extras
    ordered: dict[str, int] = {}
    for level in CEFR_ORDER:
        if level in counts.index:
            ordered[level] = int(counts[level])
    for label, count in counts.items():
        if label not in ordered:
            ordered[str(label)] = int(count)
    return ordered


def _imbalance_ratio(counts: dict[str, int]) -> float:
    if not counts:
        return 0.0
    values = list(counts.values())
    return float(max(values) / max(min(values), 1))


def _align_train_and_embeddings(
    train_df: pd.DataFrame,
    embeddings: np.ndarray,
    ids: list[str],
) -> tuple[pd.DataFrame, np.ndarray]:
    if len(embeddings) != len(ids):
        raise RuntimeError(
            f"Embedding/id length mismatch: embeddings={len(embeddings)} ids={len(ids)}"
        )
    id_to_pos = {rid: i for i, rid in enumerate(ids)}
    ordered_idx: list[int] = []
    keep_rows: list[int] = []
    for row_i, rid in enumerate(train_df["resource_id"].astype(str).tolist()):
        pos = id_to_pos.get(rid)
        if pos is None:
            logger.warning("resource_id %s missing from train_ids.json; dropping", rid)
            continue
        keep_rows.append(row_i)
        ordered_idx.append(pos)

    aligned_df = train_df.iloc[keep_rows].reset_index(drop=True)
    aligned_emb = embeddings[np.asarray(ordered_idx, dtype=np.int64)]
    if len(aligned_df) != len(aligned_emb):
        raise RuntimeError("Failed to align train parquet with embeddings")
    return aligned_df, aligned_emb


def _select_strategy(counts: dict[str, int]) -> str:
    if len(counts) < 2:
        return "skip_insufficient_classes"
    ratio = _imbalance_ratio(counts)
    if ratio <= IMBALANCE_RATIO_THRESHOLD:
        return "skip_acceptable"
    if any(n < SMOTE_MIN_SAMPLES for n in counts.values()):
        return "random_oversampler"
    return "smote"


def _balance_labeled(
    X: np.ndarray,
    y: pd.Series,
    strategy: str,
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """Return balanced embeddings, integer indices into original labeled rows, and labels."""
    y_arr = y.astype(str).to_numpy()
    if strategy == "smote":
        sampler = SMOTE(random_state=RANDOM_STATE)
    elif strategy == "random_oversampler":
        sampler = RandomOverSampler(random_state=RANDOM_STATE)
    else:
        raise ValueError(f"Unknown balancing strategy: {strategy}")

    # imblearn returns resampled X and y; track provenance via index feature
    index_col = np.arange(len(X), dtype=np.float32).reshape(-1, 1)
    X_aug = np.hstack([X, index_col])
    X_res, y_res = sampler.fit_resample(X_aug, y_arr)
    source_idx = np.clip(np.rint(X_res[:, -1]).astype(np.int64), 0, len(X) - 1)
    X_balanced = X_res[:, :-1].astype(np.float32, copy=False)
    return X_balanced, source_idx, pd.Series(y_res, name="cefr_level")


def run() -> dict:
    pipeline_state.mark_running(STAGE_NAME)
    try:
        for path in (TRAIN_PARQUET, TRAIN_EMBEDDINGS, TRAIN_IDS):
            if not path.exists():
                raise RuntimeError(
                    f"Missing {path}. Run Split and Preprocess before Balance."
                )

        train_df = pd.read_parquet(TRAIN_PARQUET)
        embeddings = np.load(TRAIN_EMBEDDINGS).astype(np.float32, copy=False)
        with TRAIN_IDS.open("r", encoding="utf-8") as fh:
            train_ids = json.load(fh)

        train_df, embeddings = _align_train_and_embeddings(train_df, embeddings, train_ids)
        logger.info("aligned train rows=%s emb_shape=%s", len(train_df), embeddings.shape)

        labeled_mask = train_df["cefr_level"].notna()
        labeled_df = train_df.loc[labeled_mask].reset_index(drop=True)
        labeled_emb = embeddings[labeled_mask.to_numpy()]
        unlabeled_df = train_df.loc[~labeled_mask].reset_index(drop=True)
        unlabeled_emb = embeddings[(~labeled_mask).to_numpy()]

        counts_before = _class_counts(labeled_df["cefr_level"]) if len(labeled_df) else {}
        strategy = _select_strategy(counts_before)
        ratio = _imbalance_ratio(counts_before) if counts_before else 0.0
        logger.info(
            "labeled=%s unlabeled=%s class_counts_before=%s ratio=%.3f strategy=%s",
            len(labeled_df),
            len(unlabeled_df),
            counts_before,
            ratio,
            strategy,
        )

        if strategy == "skip_acceptable":
            logger.info("Balancing not needed; distribution is acceptable.")
            balanced_labeled_df = labeled_df
            balanced_labeled_emb = labeled_emb
            strategy_applied = "none"
        elif strategy == "skip_insufficient_classes":
            logger.info(
                "Balancing not needed; fewer than 2 CEFR classes with labels "
                "(distribution is acceptable for skip)."
            )
            balanced_labeled_df = labeled_df
            balanced_labeled_emb = labeled_emb
            strategy_applied = "none"
        else:
            balanced_emb, source_idx, y_res = _balance_labeled(
                labeled_emb, labeled_df["cefr_level"], strategy
            )
            balanced_labeled_df = labeled_df.iloc[source_idx].reset_index(drop=True)
            balanced_labeled_df = balanced_labeled_df.copy()
            balanced_labeled_df["cefr_level"] = y_res.to_numpy()
            # Resampled rows reuse source metadata; flag repeated source indices
            original_n = len(labeled_df)
            seen: set[int] = set()
            synthetic_flags: list[bool] = []
            for idx in source_idx.tolist():
                if idx in seen:
                    synthetic_flags.append(True)
                else:
                    seen.add(idx)
                    synthetic_flags.append(False)
            balanced_labeled_df["is_balanced_synthetic"] = synthetic_flags
            balanced_labeled_emb = balanced_emb
            strategy_applied = strategy
            logger.info(
                "applied %s: labeled %s → %s",
                strategy_applied,
                original_n,
                len(balanced_labeled_df),
            )

        # Keep unlabeled rows unchanged; append after balanced labeled set
        if "is_balanced_synthetic" not in balanced_labeled_df.columns:
            balanced_labeled_df = balanced_labeled_df.copy()
            balanced_labeled_df["is_balanced_synthetic"] = False
        unlabeled_out = unlabeled_df.copy()
        unlabeled_out["is_balanced_synthetic"] = False

        balanced_df = pd.concat([balanced_labeled_df, unlabeled_out], ignore_index=True)
        balanced_embeddings = (
            np.vstack([balanced_labeled_emb, unlabeled_emb]).astype(np.float32)
            if len(unlabeled_emb) and len(balanced_labeled_emb)
            else (
                balanced_labeled_emb.astype(np.float32)
                if len(balanced_labeled_emb)
                else unlabeled_emb.astype(np.float32)
            )
        )

        counts_after = _class_counts(
            balanced_df.loc[balanced_df["cefr_level"].notna(), "cefr_level"]
        )

        BALANCED_PARQUET.parent.mkdir(parents=True, exist_ok=True)
        balanced_df.to_parquet(BALANCED_PARQUET, engine="pyarrow", index=False)
        np.save(BALANCED_EMBEDDINGS, balanced_embeddings)
        logger.info(
            "wrote %s (%s rows) and %s %s",
            BALANCED_PARQUET,
            len(balanced_df),
            BALANCED_EMBEDDINGS,
            balanced_embeddings.shape,
        )

        report = {
            "stage": STAGE_NAME,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "strategy_applied": strategy_applied,
            "imbalance_ratio_before": round(ratio, 4),
            "threshold": IMBALANCE_RATIO_THRESHOLD,
            "labeled_n_before": int(len(labeled_df)),
            "unlabeled_n": int(len(unlabeled_df)),
            "class_counts_before": counts_before,
            "class_counts_after": counts_after,
            "rows_after": int(len(balanced_df)),
            "outputs": {
                "balanced_train": str(BALANCED_PARQUET.as_posix()),
                "balanced_embeddings": str(BALANCED_EMBEDDINGS.as_posix()),
            },
        }
        with REPORT_PATH.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
            fh.write("\n")
        logger.info("wrote balance report → %s", REPORT_PATH)

        pipeline_state.mark_complete(STAGE_NAME)
        return report
    except Exception:
        pipeline_state.mark_failed(STAGE_NAME)
        raise


if __name__ == "__main__":
    run()

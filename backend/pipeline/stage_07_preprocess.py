"""
Stage 07 — Preprocess

Generate SBERT sentence embeddings for train, val, and test sets.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

from backend.api.websocket_manager import broadcast_pipeline_status
from backend.models.embedder import DEFAULT_MODEL_NAME, Embedder
from backend.utils.config import DATA_EMBEDDINGS, DATA_PROCESSED, DATA_SPLITS
from backend.utils.logger import get_logger
from backend.utils import pipeline_state

logger = get_logger("efl_indexdb.pipeline.preprocess")

STAGE_NAME = "Preprocess"
BATCH_SIZE = 64
PROGRESS_EVERY_N_BATCHES = 10

TRAIN_PARQUET = DATA_SPLITS / "train" / "train.parquet"
VAL_PARQUET = DATA_SPLITS / "val" / "val.parquet"
TEST_PARQUET = DATA_SPLITS / "test" / "test.parquet"
REPORT_PATH = DATA_PROCESSED / "07_preprocess_report.json"

def _embed_split(
    df: pd.DataFrame,
    *,
    embedder: Embedder,
    split_name: str,
    batches_done_global: list[int],
    batches_total: int,
) -> tuple[np.ndarray, list[str]]:
    texts = df["raw_text"].fillna("").astype(str).tolist()
    ids = df["resource_id"].astype(str).tolist()
    n = len(texts)
    if n == 0:
        return np.zeros((0, embedder.embedding_dim), dtype=np.float32), []

    chunks: list[np.ndarray] = []
    n_batches = (n + BATCH_SIZE - 1) // BATCH_SIZE
    progress = tqdm(range(n_batches), desc=f"embed:{split_name}", unit="batch")

    for batch_idx in progress:
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, n)
        batch_texts = texts[start:end]
        batch_emb = embedder.encode(
            batch_texts,
            batch_size=BATCH_SIZE,
            show_progress_bar=False,
        )
        chunks.append(np.asarray(batch_emb, dtype=np.float32))

        batches_done_global[0] += 1
        if batches_done_global[0] % PROGRESS_EVERY_N_BATCHES == 0 or batches_done_global[0] == batches_total:
            pct = 100.0 * batches_done_global[0] / max(batches_total, 1)
            broadcast_pipeline_status(
                STAGE_NAME,
                "RUNNING",
                progress_pct=round(pct, 2),
            )
            progress.set_postfix(progress_pct=f"{pct:.1f}%")

    embeddings = np.vstack(chunks).astype(np.float32, copy=False)
    return embeddings, ids

def _count_batches(n_rows: int) -> int:
    if n_rows <= 0:
        return 0
    return (n_rows + BATCH_SIZE - 1) // BATCH_SIZE

def run() -> dict:
    pipeline_state.mark_running(STAGE_NAME)
    started = time.perf_counter()
    try:
        for path in (TRAIN_PARQUET, VAL_PARQUET, TEST_PARQUET):
            if not path.exists():
                raise RuntimeError(
                    f"Missing {path}. Run Split first: "
                    "python -m backend.pipeline.stage_06_split"
                )

        train_df = pd.read_parquet(TRAIN_PARQUET)
        val_df = pd.read_parquet(VAL_PARQUET)
        test_df = pd.read_parquet(TEST_PARQUET)
        logger.info(
            "loaded splits train=%s val=%s test=%s",
            len(train_df),
            len(val_df),
            len(test_df),
        )

        logger.info("loading SBERT model %s (uses local HF cache if available)", DEFAULT_MODEL_NAME)
        embedder = Embedder(DEFAULT_MODEL_NAME)
        logger.info("model ready; embedding_dim=%s", embedder.embedding_dim)

        batches_total = (
            _count_batches(len(train_df))
            + _count_batches(len(val_df))
            + _count_batches(len(test_df))
        )
        batches_done_global = [0]
        broadcast_pipeline_status(STAGE_NAME, "RUNNING", progress_pct=0.0)

        train_emb, train_ids = _embed_split(
            train_df,
            embedder=embedder,
            split_name="train",
            batches_done_global=batches_done_global,
            batches_total=batches_total,
        )
        val_emb, val_ids = _embed_split(
            val_df,
            embedder=embedder,
            split_name="val",
            batches_done_global=batches_done_global,
            batches_total=batches_total,
        )
        test_emb, test_ids = _embed_split(
            test_df,
            embedder=embedder,
            split_name="test",
            batches_done_global=batches_done_global,
            batches_total=batches_total,
        )

        DATA_EMBEDDINGS.mkdir(parents=True, exist_ok=True)
        np.save(DATA_EMBEDDINGS / "train_embeddings.npy", train_emb)
        np.save(DATA_EMBEDDINGS / "val_embeddings.npy", val_emb)
        np.save(DATA_EMBEDDINGS / "test_embeddings.npy", test_emb)

        def _write_ids(path: Path, ids: list[str]) -> None:
            with path.open("w", encoding="utf-8") as fh:
                json.dump(ids, fh)
                fh.write("\n")

        _write_ids(DATA_EMBEDDINGS / "train_ids.json", train_ids)
        _write_ids(DATA_EMBEDDINGS / "val_ids.json", val_ids)
        _write_ids(DATA_EMBEDDINGS / "test_ids.json", test_ids)

        duration = time.perf_counter() - started
        report = {
            "stage": STAGE_NAME,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "model_name": DEFAULT_MODEL_NAME,
            "embedding_dim": int(embedder.embedding_dim),
            "train_n": int(len(train_ids)),
            "val_n": int(len(val_ids)),
            "test_n": int(len(test_ids)),
            "duration_seconds": round(duration, 3),
            "batch_size": BATCH_SIZE,
            "outputs": {
                "train_embeddings": str((DATA_EMBEDDINGS / "train_embeddings.npy").as_posix()),
                "val_embeddings": str((DATA_EMBEDDINGS / "val_embeddings.npy").as_posix()),
                "test_embeddings": str((DATA_EMBEDDINGS / "test_embeddings.npy").as_posix()),
                "train_ids": str((DATA_EMBEDDINGS / "train_ids.json").as_posix()),
                "val_ids": str((DATA_EMBEDDINGS / "val_ids.json").as_posix()),
                "test_ids": str((DATA_EMBEDDINGS / "test_ids.json").as_posix()),
            },
        }
        with REPORT_PATH.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
            fh.write("\n")
        logger.info(
            "preprocess done dim=%s train=%s val=%s test=%s duration=%.1fs → %s",
            report["embedding_dim"],
            report["train_n"],
            report["val_n"],
            report["test_n"],
            duration,
            REPORT_PATH,
        )

        broadcast_pipeline_status(STAGE_NAME, "RUNNING", progress_pct=100.0)
        pipeline_state.mark_complete(STAGE_NAME)
        return report
    except Exception:
        pipeline_state.mark_failed(STAGE_NAME)
        raise

if __name__ == "__main__":
    run()

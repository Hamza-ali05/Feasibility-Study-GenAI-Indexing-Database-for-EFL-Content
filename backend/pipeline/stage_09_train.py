"""
Stage 09 — Train

Train CEFR classifiers, build FAISS index, pre-scan duplicate candidates.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import faiss
import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from backend.db.metadata_store import MetadataStore
from backend.utils.config import DATA_EMBEDDINGS, DATA_PROCESSED, DATA_SPLITS
from backend.utils.logger import get_logger
from backend.utils import pipeline_state

logger = get_logger("efl_indexdb.pipeline.train")

STAGE_NAME = "Train"
BALANCED_PARQUET = DATA_SPLITS / "train" / "balanced_train.parquet"
BALANCED_EMBEDDINGS = DATA_SPLITS / "train" / "balanced_embeddings.npy"
MODELS_DIR = DATA_PROCESSED / "models"
FAISS_INDEX_PATH = DATA_EMBEDDINGS / "faiss_index.bin"
FAISS_ID_MAP_PATH = DATA_EMBEDDINGS / "faiss_id_map.json"
DUP_CANDIDATES_PATH = DATA_PROCESSED / "duplicate_candidates.json"
REPORT_PATH = DATA_PROCESSED / "09_train_report.json"

RANDOM_STATE = 42
DUP_SIM_THRESHOLD = 0.97
DUP_TOP_N = 200
DUP_SEARCH_K = 32

def _load_balanced() -> tuple[pd.DataFrame, np.ndarray]:
    if not BALANCED_PARQUET.exists() or not BALANCED_EMBEDDINGS.exists():
        raise RuntimeError(
            "Missing balanced train artefacts. Run Balance first: "
            "python -m backend.pipeline.stage_08_balance"
        )
    df = pd.read_parquet(BALANCED_PARQUET)
    emb = np.load(BALANCED_EMBEDDINGS).astype(np.float32, copy=False)
    if len(df) != len(emb):
        raise RuntimeError(
            f"balanced_train rows ({len(df)}) != embeddings ({len(emb)})"
        )
    return df, emb

def _train_classifiers(
    df: pd.DataFrame, embeddings: np.ndarray
) -> tuple[float, float, object, object, object]:
    labeled_mask = df["cefr_level"].notna()
    labeled_df = df.loc[labeled_mask].reset_index(drop=True)
    X = embeddings[labeled_mask.to_numpy()]
    y = labeled_df["cefr_level"].astype(str)

    if len(labeled_df) < 2 or y.nunique() < 2:
        raise RuntimeError(
            "Need at least 2 CEFR-labeled classes to train classifiers. "
            f"Found labeled={len(labeled_df)} unique={y.nunique()}"
        )

    sbert_clf = LogisticRegression(max_iter=1000, C=1.0, random_state=RANDOM_STATE)
    sbert_clf.fit(X, y)
    sbert_acc = float(sbert_clf.score(X, y))
    logger.info("SBERT+LR train accuracy=%.4f (n=%s)", sbert_acc, len(y))

    tfidf_pipe = Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    max_features=20000,
                    ngram_range=(1, 2),
                    min_df=2,
                    sublinear_tf=True,
                ),
            ),
            (
                "clf",
                LogisticRegression(max_iter=1000, C=1.0, random_state=RANDOM_STATE),
            ),
        ]
    )
    texts = labeled_df["raw_text"].fillna("").astype(str)
    tfidf_pipe.fit(texts, y)
    tfidf_acc = float(tfidf_pipe.score(texts, y))
    logger.info("TF-IDF+LR train accuracy=%.4f (n=%s)", tfidf_acc, len(y))

    vectorizer = tfidf_pipe.named_steps["tfidf"]
    tfidf_clf = tfidf_pipe.named_steps["clf"]
    return sbert_acc, tfidf_acc, sbert_clf, tfidf_clf, vectorizer

def _l2_normalize(embeddings: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return (embeddings / norms).astype(np.float32)

def _build_faiss(embeddings: np.ndarray, resource_ids: list[str]) -> tuple[faiss.Index, dict]:
    vectors = _l2_normalize(embeddings)
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)
    id_map = {
        str(i): {
            "resource_id": rid,
            "faiss_index": i,
        }
        for i, rid in enumerate(resource_ids)
    }

    id_map["by_resource_id"] = {rid: i for i, rid in enumerate(resource_ids)}
    logger.info("FAISS IndexFlatIP built ntotal=%s dim=%s", index.ntotal, dim)
    return index, id_map

def _find_duplicate_candidates(
    index: faiss.Index,
    embeddings: np.ndarray,
    resource_ids: list[str],
) -> list[dict]:
    vectors = _l2_normalize(embeddings)
    n = len(resource_ids)
    k = min(DUP_SEARCH_K, n)
    scores, indices = index.search(vectors, k)

    pair_scores: dict[tuple[str, str], float] = {}
    for i in range(n):
        id_a = resource_ids[i]
        for sim, j in zip(scores[i].tolist(), indices[i].tolist()):
            if j < 0 or j == i:
                continue
            if float(sim) < DUP_SIM_THRESHOLD:
                continue
            id_b = resource_ids[j]
            key = tuple(sorted((id_a, id_b)))
            prev = pair_scores.get(key)
            if prev is None or float(sim) > prev:
                pair_scores[key] = float(sim)

    ranked = sorted(pair_scores.items(), key=lambda item: item[1], reverse=True)[:DUP_TOP_N]
    candidates = [
        {
            "resource_id_a": a,
            "resource_id_b": b,
            "similarity": round(sim, 6),
        }
        for (a, b), sim in ranked
    ]
    logger.info(
        "duplicate candidates ≥%.2f: found=%s kept_top=%s",
        DUP_SIM_THRESHOLD,
        len(pair_scores),
        len(candidates),
    )
    return candidates

def run() -> dict:
    pipeline_state.mark_running(STAGE_NAME)
    try:
        df, embeddings = _load_balanced()
        resource_ids = df["resource_id"].astype(str).tolist()
        logger.info("loaded balanced train n=%s dim=%s", len(df), embeddings.shape[1])

        sbert_acc, tfidf_acc, sbert_clf, tfidf_clf, vectorizer = _train_classifiers(
            df, embeddings
        )
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(sbert_clf, MODELS_DIR / "sbert_lr_classifier.joblib")
        joblib.dump(tfidf_clf, MODELS_DIR / "tfidf_lr_baseline.joblib")
        joblib.dump(vectorizer, MODELS_DIR / "tfidf_vectorizer.joblib")
        logger.info("saved classifiers → %s", MODELS_DIR)

        index, id_map = _build_faiss(embeddings, resource_ids)
        DATA_EMBEDDINGS.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(FAISS_INDEX_PATH))
        with FAISS_ID_MAP_PATH.open("w", encoding="utf-8") as fh:
            json.dump(id_map, fh)
            fh.write("\n")
        logger.info("wrote FAISS index → %s", FAISS_INDEX_PATH)

        store = MetadataStore()
        linked = store.set_faiss_indices(id_map["by_resource_id"])
        logger.info("metadata FAISS links updated: %s", linked)

        candidates = _find_duplicate_candidates(index, embeddings, resource_ids)
        with DUP_CANDIDATES_PATH.open("w", encoding="utf-8") as fh:
            json.dump(
                {
                    "threshold": DUP_SIM_THRESHOLD,
                    "capped_at": DUP_TOP_N,
                    "candidates": candidates,
                },
                fh,
                indent=2,
            )
            fh.write("\n")

        report = {
            "stage": STAGE_NAME,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "classifier_train_accuracy": round(sbert_acc, 6),
            "tfidf_train_accuracy": round(tfidf_acc, 6),
            "faiss_ntotal": int(index.ntotal),
            "index_type": "IndexFlatIP",
            "duplicate_candidates_found": int(len(candidates)),
            "metadata_faiss_links": int(linked),
            "outputs": {
                "sbert_lr_classifier": str((MODELS_DIR / "sbert_lr_classifier.joblib").as_posix()),
                "tfidf_lr_baseline": str((MODELS_DIR / "tfidf_lr_baseline.joblib").as_posix()),
                "tfidf_vectorizer": str((MODELS_DIR / "tfidf_vectorizer.joblib").as_posix()),
                "faiss_index": str(FAISS_INDEX_PATH.as_posix()),
                "faiss_id_map": str(FAISS_ID_MAP_PATH.as_posix()),
                "duplicate_candidates": str(DUP_CANDIDATES_PATH.as_posix()),
            },
        }
        with REPORT_PATH.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
            fh.write("\n")
        logger.info("train report → %s", REPORT_PATH)

        pipeline_state.mark_complete(STAGE_NAME)
        return report
    except Exception:
        pipeline_state.mark_failed(STAGE_NAME)
        raise

if __name__ == "__main__":
    run()

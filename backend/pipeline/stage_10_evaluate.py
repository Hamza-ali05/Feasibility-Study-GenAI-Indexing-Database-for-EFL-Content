"""
Stage 10 — Evaluate

Retrieval + CEFR classification metrics on the test set (EFL IndexDB).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import faiss
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.metrics.pairwise import cosine_similarity

from backend.utils.config import DATA_EMBEDDINGS, DATA_PROCESSED, DATA_SPLITS
from backend.utils.logger import get_logger
from backend.utils import pipeline_state

logger = get_logger("efl_indexdb.pipeline.evaluate")

STAGE_NAME = "Evaluate"
K = 10
CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]

TEST_PARQUET = DATA_SPLITS / "test" / "test.parquet"
TEST_EMBEDDINGS = DATA_EMBEDDINGS / "test_embeddings.npy"
TEST_IDS = DATA_EMBEDDINGS / "test_ids.json"
TRAIN_BALANCED = DATA_SPLITS / "train" / "balanced_train.parquet"
FAISS_INDEX_PATH = DATA_EMBEDDINGS / "faiss_index.bin"
FAISS_ID_MAP_PATH = DATA_EMBEDDINGS / "faiss_id_map.json"
SBERT_MODEL_PATH = DATA_PROCESSED / "models" / "sbert_lr_classifier.joblib"
TFIDF_CLF_PATH = DATA_PROCESSED / "models" / "tfidf_lr_baseline.joblib"
TFIDF_VEC_PATH = DATA_PROCESSED / "models" / "tfidf_vectorizer.joblib"
REPORT_PATH = DATA_PROCESSED / "10_evaluation_report.json"

def _require(path) -> None:
    if not path.exists():
        raise RuntimeError(f"Missing required artefact: {path}")

def _l2_normalize(x: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return (x / norms).astype(np.float32)

def _align_test(df: pd.DataFrame, embeddings: np.ndarray, ids: list[str]) -> tuple[pd.DataFrame, np.ndarray]:
    id_to_pos = {rid: i for i, rid in enumerate(ids)}
    keep_rows: list[int] = []
    ordered: list[int] = []
    for row_i, rid in enumerate(df["resource_id"].astype(str).tolist()):
        pos = id_to_pos.get(rid)
        if pos is None:
            continue
        keep_rows.append(row_i)
        ordered.append(pos)
    aligned = df.iloc[keep_rows].reset_index(drop=True)
    emb = embeddings[np.asarray(ordered, dtype=np.int64)]
    return aligned, emb

def _relevant_ids_for_query(query_row: pd.Series, corpus_df: pd.DataFrame) -> set[str]:
    """Relevance: same CEFR if labeled; else same source_name."""
    qid = str(query_row["resource_id"])
    cefr = query_row.get("cefr_level")
    if pd.notna(cefr):
        mask = corpus_df["cefr_level"].astype(str) == str(cefr)
        ids = set(corpus_df.loc[mask, "resource_id"].astype(str)) - {qid}
        if ids:
            return ids
    source = query_row.get("source_name")
    if pd.notna(source) and str(source).strip():
        mask = corpus_df["source_name"].astype(str) == str(source)
        ids = set(corpus_df.loc[mask, "resource_id"].astype(str)) - {qid}
        return ids
    return set()

def _precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top = retrieved[:k]
    hits = sum(1 for rid in top if rid in relevant)
    return hits / k

def _recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    top = retrieved[:k]
    hits = sum(1 for rid in top if rid in relevant)
    return hits / len(relevant)

def _f1_at_k(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)

def _average_precision(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    hits = 0
    sum_prec = 0.0
    for i, rid in enumerate(retrieved[:k], start=1):
        if rid in relevant:
            hits += 1
            sum_prec += hits / i
    if hits == 0:
        return 0.0
    return sum_prec / min(len(relevant), k)

def _aggregate_retrieval(
    retrieved_lists: list[list[str]],
    relevant_sets: list[set[str]],
    k: int,
) -> dict[str, float]:
    precs, recalls, maps, f1s = [], [], [], []
    evaluated = 0
    for retrieved, relevant in zip(retrieved_lists, relevant_sets):
        if not relevant:
            continue
        evaluated += 1
        p = _precision_at_k(retrieved, relevant, k)
        r = _recall_at_k(retrieved, relevant, k)
        ap = _average_precision(retrieved, relevant, k)
        precs.append(p)
        recalls.append(r)
        maps.append(ap)
        f1s.append(_f1_at_k(p, r))

    if evaluated == 0:
        logger.warning("No queries with non-empty relevance sets; retrieval metrics are 0")
        return {
            "precision_at_10": 0.0,
            "recall_at_10": 0.0,
            "map": 0.0,
            "f1_at_10": 0.0,
            "queries_evaluated": 0,
        }

    return {
        "precision_at_10": float(np.mean(precs)),
        "recall_at_10": float(np.mean(recalls)),
        "map": float(np.mean(maps)),
        "f1_at_10": float(np.mean(f1s)),
        "queries_evaluated": evaluated,
    }

def _faiss_retrieve(
    index: faiss.Index,
    query_embeddings: np.ndarray,
    faiss_row_to_id: list[str],
    k: int,
) -> list[list[str]]:
    q = _l2_normalize(query_embeddings)
    k_eff = min(k, index.ntotal)
    scores, indices = index.search(q, k_eff)
    results: list[list[str]] = []
    for row in indices:
        ids = []
        for j in row.tolist():
            if j < 0:
                continue
            ids.append(faiss_row_to_id[j])
        results.append(ids)
    return results

def _tfidf_retrieve(
    vectorizer,
    corpus_texts: list[str],
    corpus_ids: list[str],
    query_texts: list[str],
    k: int,
) -> list[list[str]]:
    corpus_matrix = vectorizer.transform(corpus_texts)
    query_matrix = vectorizer.transform(query_texts)

    results: list[list[str]] = []
    batch = 256
    k_eff = min(k, len(corpus_ids))
    for start in range(0, len(query_texts), batch):
        end = min(start + batch, len(query_texts))
        sims = cosine_similarity(query_matrix[start:end], corpus_matrix)
        for row in sims:
            top_idx = np.argpartition(-row, kth=min(k_eff, len(row) - 1))[:k_eff]
            top_sorted = top_idx[np.argsort(-row[top_idx])]
            results.append([corpus_ids[i] for i in top_sorted.tolist()])
    return results

def _classification_metrics(y_true: list[str], y_pred: list[str]) -> tuple[dict, list]:
    labels = [c for c in CEFR_ORDER if c in set(y_true) | set(y_pred)]
    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_macro": float(
            precision_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
        ),
        "recall_macro": float(
            recall_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
        ),
        "f1_macro": float(
            f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
        ),
        "labels": labels,
        "n": len(y_true),
    }
    cm = confusion_matrix(y_true, y_pred, labels=labels).tolist()
    return metrics, cm

def run() -> dict:
    pipeline_state.mark_running(STAGE_NAME)
    try:
        for path in (
            TEST_PARQUET,
            TEST_EMBEDDINGS,
            TEST_IDS,
            TRAIN_BALANCED,
            FAISS_INDEX_PATH,
            FAISS_ID_MAP_PATH,
            SBERT_MODEL_PATH,
            TFIDF_CLF_PATH,
            TFIDF_VEC_PATH,
        ):
            _require(path)

        test_df = pd.read_parquet(TEST_PARQUET)
        test_emb = np.load(TEST_EMBEDDINGS).astype(np.float32, copy=False)
        with TEST_IDS.open("r", encoding="utf-8") as fh:
            test_ids = json.load(fh)
        test_df, test_emb = _align_test(test_df, test_emb, test_ids)

        train_df = pd.read_parquet(TRAIN_BALANCED)
        corpus_ids = train_df["resource_id"].astype(str).tolist()
        corpus_texts = train_df["raw_text"].fillna("").astype(str).tolist()

        with FAISS_ID_MAP_PATH.open("r", encoding="utf-8") as fh:
            id_map = json.load(fh)

        faiss_row_to_id = [id_map[str(i)]["resource_id"] for i in range(len(corpus_ids))]
        index = faiss.read_index(str(FAISS_INDEX_PATH))

        sbert_clf = joblib.load(SBERT_MODEL_PATH)
        tfidf_clf = joblib.load(TFIDF_CLF_PATH)
        vectorizer = joblib.load(TFIDF_VEC_PATH)

        logger.info(
            "evaluate setup: test=%s train_corpus=%s faiss_ntotal=%s",
            len(test_df),
            len(train_df),
            index.ntotal,
        )

        relevant_sets = [
            _relevant_ids_for_query(row, train_df) for _, row in test_df.iterrows()
        ]

        sbert_retrieved = _faiss_retrieve(index, test_emb, faiss_row_to_id, K)
        sbert_retrieval = _aggregate_retrieval(sbert_retrieved, relevant_sets, K)
        logger.info("SBERT retrieval@%s: %s", K, sbert_retrieval)

        query_texts = test_df["raw_text"].fillna("").astype(str).tolist()
        tfidf_retrieved = _tfidf_retrieve(
            vectorizer, corpus_texts, corpus_ids, query_texts, K
        )
        tfidf_retrieval = _aggregate_retrieval(tfidf_retrieved, relevant_sets, K)
        logger.info("TF-IDF retrieval@%s: %s", K, tfidf_retrieval)

        delta = {
            key: round(sbert_retrieval[key] - tfidf_retrieval[key], 6)
            for key in ("precision_at_10", "recall_at_10", "map", "f1_at_10")
        }
        for key, value in delta.items():
            logger.info("delta %s (SBERT - TFIDF) = %s", key, value)

        labeled_mask = test_df["cefr_level"].notna()
        labeled = test_df.loc[labeled_mask].reset_index(drop=True)
        labeled_emb = test_emb[labeled_mask.to_numpy()]
        y_true = labeled["cefr_level"].astype(str).tolist()

        if not y_true:
            raise RuntimeError("No CEFR-labeled rows in test split for classification metrics")

        y_pred_sbert = sbert_clf.predict(labeled_emb).tolist()
        y_pred_tfidf = tfidf_clf.predict(
            vectorizer.transform(labeled["raw_text"].fillna("").astype(str))
        ).tolist()

        sbert_clf_metrics, cm_sbert = _classification_metrics(y_true, y_pred_sbert)
        tfidf_clf_metrics, cm_tfidf = _classification_metrics(y_true, y_pred_tfidf)
        logger.info("SBERT classification: %s", sbert_clf_metrics)
        logger.info("TF-IDF classification: %s", tfidf_clf_metrics)

        report = {
            "stage": STAGE_NAME,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "retrieval": {
                "sbert": {
                    "precision_at_10": round(sbert_retrieval["precision_at_10"], 6),
                    "recall_at_10": round(sbert_retrieval["recall_at_10"], 6),
                    "map": round(sbert_retrieval["map"], 6),
                    "f1_at_10": round(sbert_retrieval["f1_at_10"], 6),
                },
                "tfidf": {
                    "precision_at_10": round(tfidf_retrieval["precision_at_10"], 6),
                    "recall_at_10": round(tfidf_retrieval["recall_at_10"], 6),
                    "map": round(tfidf_retrieval["map"], 6),
                    "f1_at_10": round(tfidf_retrieval["f1_at_10"], 6),
                },
                "delta": delta,
                "queries_evaluated": int(sbert_retrieval.get("queries_evaluated", 0)),
                "relevance_rule": "same cefr_level if labeled else same source_name",
                "k": K,
            },
            "classification": {
                "sbert": {
                    "accuracy": round(sbert_clf_metrics["accuracy"], 6),
                    "precision_macro": round(sbert_clf_metrics["precision_macro"], 6),
                    "recall_macro": round(sbert_clf_metrics["recall_macro"], 6),
                    "f1_macro": round(sbert_clf_metrics["f1_macro"], 6),
                },
                "tfidf": {
                    "accuracy": round(tfidf_clf_metrics["accuracy"], 6),
                    "precision_macro": round(tfidf_clf_metrics["precision_macro"], 6),
                    "recall_macro": round(tfidf_clf_metrics["recall_macro"], 6),
                    "f1_macro": round(tfidf_clf_metrics["f1_macro"], 6),
                },
                "n_labeled_test": int(len(y_true)),
            },
            "confusion_matrix_sbert": cm_sbert,
            "confusion_matrix_tfidf": cm_tfidf,
            "confusion_matrix_labels": sbert_clf_metrics["labels"],
        }

        with REPORT_PATH.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
            fh.write("\n")
        logger.info("wrote evaluation report → %s", REPORT_PATH)

        pipeline_state.mark_complete(STAGE_NAME)
        return report
    except Exception:
        pipeline_state.mark_failed(STAGE_NAME)
        raise

if __name__ == "__main__":
    run()

"""
Stage 10 — Evaluate

Retrieval + CEFR classification metrics on the test set (EFL IndexDB).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

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
PER_QUERY_PATH = DATA_PROCESSED / "10_per_query_metrics.json"

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


def _mrr(retrieved: list[str], relevant: set[str], k: int) -> float:
    for i, rid in enumerate(retrieved[:k], start=1):
        if rid in relevant:
            return 1.0 / i
    return 0.0


def _aggregate_retrieval(
    retrieved_lists: list[list[str]],
    relevant_sets: list[set[str]],
    k: int = 10,
) -> dict[str, float]:
    """Aggregate retrieval metrics at k=5 and k (default 10)."""
    ks = sorted({5, int(k)})
    buckets: dict[int, dict[str, list[float]]] = {
        kk: {"p": [], "r": [], "ap": [], "f1": [], "mrr": []} for kk in ks
    }
    evaluated = 0
    for retrieved, relevant in zip(retrieved_lists, relevant_sets):
        if not relevant:
            continue
        evaluated += 1
        for kk in ks:
            p = _precision_at_k(retrieved, relevant, kk)
            r = _recall_at_k(retrieved, relevant, kk)
            ap = _average_precision(retrieved, relevant, kk)
            buckets[kk]["p"].append(p)
            buckets[kk]["r"].append(r)
            buckets[kk]["ap"].append(ap)
            buckets[kk]["f1"].append(_f1_at_k(p, r))
            buckets[kk]["mrr"].append(_mrr(retrieved, relevant, kk))

    if evaluated == 0:
        logger.warning("No queries with non-empty relevance sets; retrieval metrics are 0")
        out: dict[str, float] = {"queries_evaluated": 0, "map": 0.0, "mrr": 0.0}
        for kk in ks:
            out[f"precision_at_{kk}"] = 0.0
            out[f"recall_at_{kk}"] = 0.0
            out[f"f1_at_{kk}"] = 0.0
        return out

    primary_k = max(ks)
    out = {
        "queries_evaluated": evaluated,
        "map": float(np.mean(buckets[primary_k]["ap"])),
        "mrr": float(np.mean(buckets[primary_k]["mrr"])),
    }
    for kk in ks:
        out[f"precision_at_{kk}"] = float(np.mean(buckets[kk]["p"]))
        out[f"recall_at_{kk}"] = float(np.mean(buckets[kk]["r"]))
        out[f"f1_at_{kk}"] = float(np.mean(buckets[kk]["f1"]))
    return out


def _per_query_metrics(
    retrieved_lists: list[list[str]],
    relevant_sets: list[set[str]],
    query_ids: list[str],
    k: int = 10,
) -> list[dict]:
    """Per-query precision/recall (and related) for paired significance tests."""
    ks = sorted({5, int(k)})
    rows: list[dict] = []
    for qid, retrieved, relevant in zip(query_ids, retrieved_lists, relevant_sets):
        if not relevant:
            continue
        row: dict = {
            "query_id": str(qid),
            "n_relevant": len(relevant),
        }
        for kk in ks:
            p = _precision_at_k(retrieved, relevant, kk)
            r = _recall_at_k(retrieved, relevant, kk)
            row[f"precision_at_{kk}"] = float(p)
            row[f"recall_at_{kk}"] = float(r)
            row[f"f1_at_{kk}"] = float(_f1_at_k(p, r))
            row[f"ap_at_{kk}"] = float(_average_precision(retrieved, relevant, kk))
            row[f"mrr_at_{kk}"] = float(_mrr(retrieved, relevant, kk))
        rows.append(row)
    return rows


def _per_class_f1_from_cm(cm: list[list[int]], labels: list[str]) -> dict[str, float]:
    mat = np.asarray(cm, dtype=float)
    out: dict[str, float] = {}
    for i, label in enumerate(labels):
        if i >= mat.shape[0]:
            break
        tp = mat[i, i]
        fp = mat[:, i].sum() - tp
        fn = mat[i, :].sum() - tp
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )
        out[str(label)] = float(f1)
    return out


def _apply_metadata_filters(
    retrieved_lists: list[list[str]],
    query_df: pd.DataFrame,
    corpus_df: pd.DataFrame,
    k: int,
) -> list[list[str]]:
    """Post-filter FAISS hits by CEFR / skill / topic match with the query."""
    meta = corpus_df.set_index(corpus_df["resource_id"].astype(str), drop=False)
    filtered: list[list[str]] = []
    for (_, qrow), hits in zip(query_df.iterrows(), retrieved_lists):
        kept: list[str] = []
        q_cefr = qrow.get("cefr_level")
        q_skill = qrow.get("skill_type")
        q_topic = qrow.get("topic_domain")
        for rid in hits:
            if rid not in meta.index:
                continue
            crow = meta.loc[rid]
            if isinstance(crow, pd.DataFrame):
                crow = crow.iloc[0]
            if pd.notna(q_cefr) and str(crow.get("cefr_level")) != str(q_cefr):
                continue
            if pd.notna(q_skill) and str(crow.get("skill_type")) != str(q_skill):
                continue
            if pd.notna(q_topic) and str(crow.get("topic_domain")) != str(q_topic):
                continue
            kept.append(str(rid))
            if len(kept) >= k:
                break
        # If filters removed everything, fall back to unfiltered top-k
        filtered.append(kept if kept else list(hits[:k]))
    return filtered


def _try_experiment_tracker():
    """Return (ExperimentTracker, ExperimentConfig) or (None, None)."""
    try:
        from research.experiment_tracker import ExperimentConfig, ExperimentTracker

        return ExperimentTracker(), ExperimentConfig
    except Exception as exc:  # noqa: BLE001 — pipeline must not fail
        logger.warning("ExperimentTracker unavailable; skipping experiment log: %s", exc)
        return None, None


def _get_or_create_named_experiment(et, ExperimentConfig, name: str, description: str, config: dict):
    for exp in et.list_experiments():
        if exp.name == name:
            return exp
    return et.create_experiment(
        name=name,
        description=description,
        config=ExperimentConfig(**config),
    )


def _results_payload(
    retrieval: dict,
    classification: dict,
    confusion_matrix: list[list[int]] | None,
    labels: list[str] | None,
) -> dict:
    return {
        "retrieval": {
            "precision_at_k": retrieval.get("precision_at_10"),
            "recall_at_k": retrieval.get("recall_at_10"),
            "map": retrieval.get("map"),
            "f1_at_k": retrieval.get("f1_at_10"),
            "mrr": retrieval.get("mrr"),
        },
        "classification": {
            "accuracy": classification.get("accuracy"),
            "precision_macro": classification.get("precision_macro"),
            "recall_macro": classification.get("recall_macro"),
            "f1_macro": classification.get("f1_macro"),
        },
        "confusion_matrix": confusion_matrix,
        "per_class_f1": (
            _per_class_f1_from_cm(confusion_matrix, labels)
            if confusion_matrix and labels
            else None
        ),
    }


def _record_baseline_experiments(
    sbert_retrieval: dict,
    tfidf_retrieval: dict,
    sbert_clf_metrics: dict,
    tfidf_clf_metrics: dict,
    cm_sbert: list,
    cm_tfidf: list,
) -> None:
    """Auto-register SBERT / TF-IDF experiments and export comparison table."""
    et, ExperimentConfig = _try_experiment_tracker()
    if et is None:
        return

    from backend.utils.config import Config

    sbert_exp = _get_or_create_named_experiment(
        et,
        ExperimentConfig,
        name="SBERT Semantic Retrieval",
        description="Pipeline Stage 10 SBERT + FAISS semantic retrieval baseline",
        config={
            "retrieval_method": "sbert",
            "embedding_model": getattr(Config, "SBERT_MODEL", None)
            or "sentence-transformers/all-MiniLM-L6-v2",
            "classifier": "logistic_regression",
            "faiss_index_type": "IndexFlatIP",
            "metadata_filters_enabled": False,
            "rag_enabled": False,
            "top_k": K,
            "random_seed": 42,
        },
    )
    tfidf_exp = _get_or_create_named_experiment(
        et,
        ExperimentConfig,
        name="TF-IDF Baseline Retrieval",
        description="Pipeline Stage 10 classical TF-IDF cosine retrieval baseline",
        config={
            "retrieval_method": "tfidf",
            "embedding_model": None,
            "classifier": "logistic_regression",
            "faiss_index_type": None,
            "metadata_filters_enabled": False,
            "rag_enabled": False,
            "top_k": K,
            "random_seed": 42,
        },
    )

    et.start_experiment(sbert_exp.experiment_id)
    et.record_results(
        sbert_exp.experiment_id,
        _results_payload(
            sbert_retrieval,
            sbert_clf_metrics,
            cm_sbert,
            sbert_clf_metrics.get("labels"),
        ),
    )

    et.start_experiment(tfidf_exp.experiment_id)
    et.record_results(
        tfidf_exp.experiment_id,
        _results_payload(
            tfidf_retrieval,
            tfidf_clf_metrics,
            cm_tfidf,
            tfidf_clf_metrics.get("labels"),
        ),
    )

    out_dir = Path(__file__).resolve().parents[2] / "research" / "reports" / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)
    et.export_comparison_table(
        [sbert_exp.experiment_id, tfidf_exp.experiment_id],
        out_dir,
    )
    msg = (
        "Experiment results recorded. Comparison table exported to "
        "research/reports/experiments/"
    )
    print(msg)
    logger.info(msg)

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
            if j < 0 or j >= len(faiss_row_to_id):
                continue
            rid = faiss_row_to_id[j]
            if rid:
                ids.append(rid)
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

        index = faiss.read_index(str(FAISS_INDEX_PATH))
        ntotal = int(index.ntotal)
        faiss_row_to_id = []
        for i in range(ntotal):
            entry = id_map.get(str(i)) or id_map.get(i)
            if entry is None:
                faiss_row_to_id.append("")
            elif isinstance(entry, dict):
                faiss_row_to_id.append(str(entry.get("resource_id") or ""))
            else:
                faiss_row_to_id.append(str(entry))

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

        delta_keys = (
            "precision_at_5",
            "recall_at_5",
            "precision_at_10",
            "recall_at_10",
            "map",
            "f1_at_10",
            "mrr",
        )
        delta = {
            key: round(sbert_retrieval.get(key, 0.0) - tfidf_retrieval.get(key, 0.0), 6)
            for key in delta_keys
            if key in sbert_retrieval and key in tfidf_retrieval
        }
        for key, value in delta.items():
            logger.info("delta %s (SBERT - TFIDF) = %s", key, value)

        query_ids = test_df["resource_id"].astype(str).tolist()
        per_query_payload = {
            "stage": STAGE_NAME,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "k_values": [5, K],
            "relevance_rule": "same cefr_level if labeled else same source_name",
            "methods": {
                "sbert": _per_query_metrics(
                    sbert_retrieved, relevant_sets, query_ids, K
                ),
                "tfidf": _per_query_metrics(
                    tfidf_retrieved, relevant_sets, query_ids, K
                ),
            },
        }
        with PER_QUERY_PATH.open("w", encoding="utf-8") as fh:
            json.dump(per_query_payload, fh, indent=2)
            fh.write("\n")
        logger.info("wrote per-query metrics → %s", PER_QUERY_PATH)

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

        def _round_retrieval(metrics: dict) -> dict:
            keys = (
                "precision_at_5",
                "recall_at_5",
                "f1_at_5",
                "precision_at_10",
                "recall_at_10",
                "map",
                "f1_at_10",
                "mrr",
            )
            return {k: round(float(metrics[k]), 6) for k in keys if k in metrics}

        report = {
            "stage": STAGE_NAME,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "retrieval": {
                "sbert": _round_retrieval(sbert_retrieval),
                "tfidf": _round_retrieval(tfidf_retrieval),
                "delta": delta,
                "queries_evaluated": int(sbert_retrieval.get("queries_evaluated", 0)),
                "relevance_rule": "same cefr_level if labeled else same source_name",
                "k": K,
                "per_query_metrics_path": str(PER_QUERY_PATH),
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

        try:
            _record_baseline_experiments(
                sbert_retrieval,
                tfidf_retrieval,
                sbert_clf_metrics,
                tfidf_clf_metrics,
                cm_sbert,
                cm_tfidf,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Experiment tracking failed (non-fatal): %s", exc)

        pipeline_state.mark_complete(STAGE_NAME)
        return report
    except Exception:
        pipeline_state.mark_failed(STAGE_NAME)
        raise

if __name__ == "__main__":
    run()

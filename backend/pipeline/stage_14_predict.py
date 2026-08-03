"""
Stage 14 — Predict

Free-text query → ranked EFL resources (FAISS + TF-IDF comparison).
Unlocks live Search / Recommendations / RAG once COMPLETE.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import faiss
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from tabulate import tabulate

from backend.api.websocket_manager import broadcast_pipeline_status
from backend.models.embedder import Embedder
from backend.utils.config import DATA_EMBEDDINGS, DATA_PROCESSED, DATA_SPLITS
from backend.utils.logger import get_logger
from backend.utils import pipeline_state

logger = get_logger("efl_indexdb.pipeline.predict")

STAGE_NAME = "Predict"
FAISS_INDEX_PATH = DATA_EMBEDDINGS / "faiss_index.bin"
FAISS_ID_MAP_PATH = DATA_EMBEDDINGS / "faiss_id_map.json"
BALANCED_PARQUET = DATA_SPLITS / "train" / "balanced_train.parquet"
SBERT_CLF_PATH = DATA_PROCESSED / "models" / "sbert_lr_classifier.joblib"
TFIDF_VEC_PATH = DATA_PROCESSED / "models" / "tfidf_vectorizer.joblib"
OUTPUT_PATH = DATA_PROCESSED / "14_last_predict.json"

RESULT_FIELDS = [
    "rank",
    "resource_id",
    "title",
    "cefr_level",
    "skill_type",
    "topic_domain",
    "source_name",
    "similarity_score",
]

def _l2_normalize(x: np.ndarray) -> np.ndarray:
    if x.ndim == 1:
        x = x.reshape(1, -1)
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return (x / norms).astype(np.float32)

def _load_corpus() -> tuple[pd.DataFrame, dict[str, int], list[str]]:
    if not BALANCED_PARQUET.exists():
        raise RuntimeError(f"Missing corpus parquet: {BALANCED_PARQUET}")
    if not FAISS_ID_MAP_PATH.exists():
        raise RuntimeError(f"Missing FAISS id map: {FAISS_ID_MAP_PATH}")

    df = pd.read_parquet(BALANCED_PARQUET)
    with FAISS_ID_MAP_PATH.open("r", encoding="utf-8") as fh:
        id_map = json.load(fh)

    by_resource = id_map.get("by_resource_id") or {}
    if not by_resource:

        by_resource = {
            id_map[str(i)]["resource_id"]: i
            for i in range(len(df))
            if str(i) in id_map
        }

    ntotal = len(by_resource)
    row_to_id = [""] * ntotal
    for rid, idx in by_resource.items():
        if 0 <= int(idx) < ntotal:
            row_to_id[int(idx)] = str(rid)

    meta = df.drop_duplicates(subset=["resource_id"], keep="first").copy()
    meta["resource_id"] = meta["resource_id"].astype(str)
    meta = meta.set_index("resource_id", drop=False)
    return meta, {str(k): int(v) for k, v in by_resource.items()}, row_to_id

def _row_payload(rank: int, resource_id: str, score: float, meta: pd.DataFrame) -> dict:
    if resource_id in meta.index:
        row = meta.loc[resource_id]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]

        def _val(col: str):
            if col not in row.index:
                return None
            v = row[col]
            if v is None or (isinstance(v, float) and np.isnan(v)):
                return None
            return None if pd.isna(v) else (str(v) if col != "similarity_score" else v)

        return {
            "rank": rank,
            "resource_id": resource_id,
            "title": _val("title"),
            "cefr_level": _val("cefr_level"),
            "skill_type": _val("skill_type"),
            "topic_domain": _val("topic_domain"),
            "source_name": _val("source_name"),
            "similarity_score": float(score),
        }

    return {
        "rank": rank,
        "resource_id": resource_id,
        "title": None,
        "cefr_level": None,
        "skill_type": None,
        "topic_domain": None,
        "source_name": None,
        "similarity_score": float(score),
    }

def _faiss_search(
    query_vec: np.ndarray,
    index: faiss.Index,
    row_to_id: list[str],
    meta: pd.DataFrame,
    top_k: int,
) -> list[dict]:
    q = _l2_normalize(query_vec)
    k = min(top_k, index.ntotal)
    scores, indices = index.search(q, k)
    results: list[dict] = []
    for rank, (score, idx) in enumerate(zip(scores[0].tolist(), indices[0].tolist()), start=1):
        if idx < 0 or idx >= len(row_to_id):
            continue
        rid = row_to_id[idx]
        if not rid:
            continue
        results.append(_row_payload(rank, rid, score, meta))
    return results

def _tfidf_search(
    query: str,
    vectorizer,
    corpus_texts: list[str],
    corpus_ids: list[str],
    meta: pd.DataFrame,
    top_k: int,
) -> list[dict]:
    q = vectorizer.transform([query])
    corpus = vectorizer.transform(corpus_texts)
    sims = cosine_similarity(q, corpus)[0]
    k = min(top_k, len(corpus_ids))
    top_idx = np.argpartition(-sims, kth=min(k, len(sims) - 1))[:k]
    top_sorted = top_idx[np.argsort(-sims[top_idx])]
    results: list[dict] = []
    for rank, i in enumerate(top_sorted.tolist(), start=1):
        results.append(_row_payload(rank, str(corpus_ids[i]), float(sims[i]), meta))
    return results

def _print_side_by_side(faiss_hits: list[dict], tfidf_hits: list[dict]) -> None:
    def _short(row: dict | None) -> str:
        if not row:
            return "—"
        title = (row.get("title") or "")[:40]
        return (
            f"#{row['rank']} {row.get('cefr_level') or '?'} "
            f"sim={row['similarity_score']:.3f} {title}"
        )

    n = max(len(faiss_hits), len(tfidf_hits))
    table = []
    for i in range(n):
        f = faiss_hits[i] if i < len(faiss_hits) else None
        t = tfidf_hits[i] if i < len(tfidf_hits) else None
        table.append([i + 1, _short(f), _short(t)])
    print("\n=== Predict results (FAISS semantic vs TF-IDF) ===")
    print(tabulate(table, headers=["k", "FAISS / SBERT", "TF-IDF"], tablefmt="github"))
    print()

def predict(query: str, top_k: int = 10) -> dict:
    for path in (
        FAISS_INDEX_PATH,
        FAISS_ID_MAP_PATH,
        BALANCED_PARQUET,
        SBERT_CLF_PATH,
        TFIDF_VEC_PATH,
    ):
        if not path.exists():
            raise RuntimeError(
                f"Missing {path}. Complete Train (and prior stages) before Predict."
            )

    meta, _by_resource, row_to_id = _load_corpus()
    corpus_df = pd.read_parquet(BALANCED_PARQUET)
    corpus_ids = corpus_df["resource_id"].astype(str).tolist()
    corpus_texts = corpus_df["raw_text"].fillna("").astype(str).tolist()

    embedder = Embedder()
    query_vec = embedder.encode([query], batch_size=1, show_progress_bar=False)[0]

    clf = joblib.load(SBERT_CLF_PATH)
    predicted_cefr = str(clf.predict(query_vec.reshape(1, -1))[0])
    proba = clf.predict_proba(query_vec.reshape(1, -1))[0]
    cefr_confidence = {
        str(cls): float(p) for cls, p in zip(clf.classes_, proba)
    }

    index = faiss.read_index(str(FAISS_INDEX_PATH))
    faiss_hits = _faiss_search(query_vec, index, row_to_id, meta, top_k)

    vectorizer = joblib.load(TFIDF_VEC_PATH)
    tfidf_hits = _tfidf_search(query, vectorizer, corpus_texts, corpus_ids, meta, top_k)

    payload = {
        "stage": STAGE_NAME,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "top_k": top_k,
        "predicted_query_cefr": predicted_cefr,
        "predicted_query_cefr_confidence": cefr_confidence,
        "faiss_results": faiss_hits,
        "tfidf_results": tfidf_hits,
        "pipeline_ready": True,
    }
    return payload

def run(query: str, top_k: int = 10) -> dict:
    pipeline_state.mark_running(STAGE_NAME)
    try:
        payload = predict(query=query, top_k=top_k)
        DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
        with OUTPUT_PATH.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
        logger.info("wrote last prediction → %s", OUTPUT_PATH)

        print(f"Query: {query!r}")
        print(f"Predicted query CEFR: {payload['predicted_query_cefr']}")
        _print_side_by_side(payload["faiss_results"], payload["tfidf_results"])

        faiss_table = [
            [
                r["rank"],
                (r.get("title") or "")[:50],
                r.get("cefr_level"),
                r.get("skill_type"),
                r.get("topic_domain"),
                r.get("source_name"),
                f"{r['similarity_score']:.4f}",
                r["resource_id"][:8] + "…",
            ]
            for r in payload["faiss_results"]
        ]
        print(tabulate(
            faiss_table,
            headers=[
                "rank",
                "title",
                "cefr",
                "skill",
                "topic",
                "source",
                "sim",
                "id",
            ],
            tablefmt="github",
        ))
        print()

        pipeline_state.mark_complete(STAGE_NAME)
        broadcast_pipeline_status(STAGE_NAME, "COMPLETE", pipeline_ready=True)
        return payload
    except Exception:
        pipeline_state.mark_failed(STAGE_NAME)
        raise

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="EFL IndexDB Predict — semantic resource search")
    parser.add_argument("--query", required=True, help="Free-text search query")
    parser.add_argument("--top_k", type=int, default=10, help="Number of results (default 10)")
    args = parser.parse_args(argv)
    if args.top_k < 1:
        raise SystemExit("--top_k must be >= 1")
    run(query=args.query, top_k=args.top_k)

if __name__ == "__main__":
    main()



from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path.cwd()
if not (ROOT / "data" / "splits" / "test" / "test.parquet").exists():
    ROOT = Path.cwd().parent

TEST_PARQUET = ROOT / "data" / "splits" / "test" / "test.parquet"
TRAIN_BALANCED = ROOT / "data" / "splits" / "train" / "balanced_train.parquet"
TFIDF_VEC_PATH = ROOT / "data" / "processed" / "models" / "tfidf_vectorizer.joblib"

K = 10

MAX_QUERIES = 200

test_df = pd.read_parquet(TEST_PARQUET)
corpus_df = pd.read_parquet(TRAIN_BALANCED)
vectorizer = joblib.load(TFIDF_VEC_PATH)

print(f"test rows={len(test_df):,}  corpus rows={len(corpus_df):,}")
print(f"vectorizer loaded from {TFIDF_VEC_PATH}")

def relevant_ids(query_row: pd.Series, corpus: pd.DataFrame) -> set[str]:
    qid = str(query_row["resource_id"])
    cefr = query_row.get("cefr_level")
    if pd.notna(cefr):
        mask = corpus["cefr_level"].astype(str) == str(cefr)
        ids = set(corpus.loc[mask, "resource_id"].astype(str)) - {qid}
        if ids:
            return ids
    source = query_row.get("source_name")
    if pd.notna(source) and str(source).strip():
        mask = corpus["source_name"].astype(str) == str(source)
        return set(corpus.loc[mask, "resource_id"].astype(str)) - {qid}
    return set()

def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    return sum(1 for rid in retrieved[:k] if rid in relevant) / k

def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return sum(1 for rid in retrieved[:k] if rid in relevant) / len(relevant)

def f1_at_k(p: float, r: float) -> float:
    if p + r == 0:
        return 0.0
    return 2 * p * r / (p + r)

def average_precision(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    hits = 0
    sum_prec = 0.0
    for i, rid in enumerate(retrieved[:k], start=1):
        if rid in relevant:
            hits += 1
            sum_prec += hits / i
    return sum_prec / min(len(relevant), k)

corpus_ids = corpus_df["resource_id"].astype(str).tolist()
corpus_matrix = vectorizer.transform(corpus_df["raw_text"].fillna("").astype(str))

labelled = test_df[test_df["cefr_level"].notna()].copy()
if labelled.empty:
    labelled = test_df.copy()
queries = labelled.head(MAX_QUERIES).reset_index(drop=True)
query_matrix = vectorizer.transform(queries["raw_text"].fillna("").astype(str))

print(f"Evaluating TF-IDF retrieval on {len(queries)} queries (k={K})…")
sims = cosine_similarity(query_matrix, corpus_matrix)

p_list, r_list, ap_list, f1_list = [], [], [], []
for i, row in queries.iterrows():
    scores = sims[i]

    qid = str(row["resource_id"])
    top_idx = np.argsort(-scores)[: K + 5]
    retrieved: list[str] = []
    for j in top_idx:
        rid = corpus_ids[int(j)]
        if rid == qid:
            continue
        retrieved.append(rid)
        if len(retrieved) >= K:
            break
    rel = relevant_ids(row, corpus_df)
    p = precision_at_k(retrieved, rel, K)
    r = recall_at_k(retrieved, rel, K)
    p_list.append(p)
    r_list.append(r)
    ap_list.append(average_precision(retrieved, rel, K))
    f1_list.append(f1_at_k(p, r))

metrics = {
    "precision_at_10": float(np.mean(p_list)),
    "recall_at_10": float(np.mean(r_list)),
    "map": float(np.mean(ap_list)),
    "f1_at_10": float(np.mean(f1_list)),
    "queries_evaluated": len(queries),
    "k": K,
}

print("\n=== TF-IDF retrieval metrics ===")
for key, value in metrics.items():
    if isinstance(value, float):
        print(f"  {key:18s} {value:.6f}")
    else:
        print(f"  {key:18s} {value}")

report_path = ROOT / "data" / "processed" / "10_evaluation_report.json"
if report_path.exists():
    report = json.loads(report_path.read_text(encoding="utf-8"))
    tfidf_full = report.get("retrieval", {}).get("tfidf", {})
    print("Stage-10 full-test TF-IDF retrieval:")
    for key in ("precision_at_10", "recall_at_10", "map", "f1_at_10"):
        print(f"  {key:18s} {float(tfidf_full.get(key, float('nan'))):.6f}")
else:
    print("No 10_evaluation_report.json yet — run Stage Evaluate first.")

"""CLI helper to register and run named feasibility experiments.

Usage:
  python -m research.run_experiment \\
    --name "Experiment 3: SBERT + Metadata Filters" \\
    --method sbert_metadata \\
    --description "SBERT retrieval with post-retrieval CEFR/skill/topic filtering"
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import faiss
import joblib
import numpy as np
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
_BACKEND = _PROJECT_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from backend.pipeline import stage_10_evaluate as evaluate  # noqa: E402
from backend.utils.config import Config  # noqa: E402
from research.experiment_tracker import ExperimentConfig, ExperimentTracker  # noqa: E402

CANDIDATE_POOL = 50
RAG_SAMPLE_N = 10


def _keyword_overlap(answer: str, reference: str) -> float:
    """Simple token-overlap relevance of RAG answer vs resource text."""
    tok = re.compile(r"[a-z0-9']+", re.I)
    a = set(tok.findall((answer or "").lower()))
    b = set(tok.findall((reference or "").lower()))
    # Drop very short tokens
    a = {t for t in a if len(t) > 2}
    b = {t for t in b if len(t) > 2}
    if not a or not b:
        return 0.0
    return len(a & b) / len(a)


def _load_eval_artefacts():
    for path in (
        evaluate.TEST_PARQUET,
        evaluate.TEST_EMBEDDINGS,
        evaluate.TEST_IDS,
        evaluate.TRAIN_BALANCED,
        evaluate.FAISS_INDEX_PATH,
        evaluate.FAISS_ID_MAP_PATH,
        evaluate.SBERT_MODEL_PATH,
        evaluate.TFIDF_CLF_PATH,
        evaluate.TFIDF_VEC_PATH,
    ):
        evaluate._require(path)

    test_df = pd.read_parquet(evaluate.TEST_PARQUET)
    test_emb = np.load(evaluate.TEST_EMBEDDINGS).astype(np.float32, copy=False)
    with evaluate.TEST_IDS.open("r", encoding="utf-8") as fh:
        import json

        test_ids = json.load(fh)
    test_df, test_emb = evaluate._align_test(test_df, test_emb, test_ids)

    train_df = pd.read_parquet(evaluate.TRAIN_BALANCED)
    corpus_ids = train_df["resource_id"].astype(str).tolist()
    corpus_texts = train_df["raw_text"].fillna("").astype(str).tolist()

    with evaluate.FAISS_ID_MAP_PATH.open("r", encoding="utf-8") as fh:
        import json

        id_map = json.load(fh)
    index = faiss.read_index(str(evaluate.FAISS_INDEX_PATH))
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
    sbert_clf = joblib.load(evaluate.SBERT_MODEL_PATH)
    tfidf_clf = joblib.load(evaluate.TFIDF_CLF_PATH)
    vectorizer = joblib.load(evaluate.TFIDF_VEC_PATH)
    return {
        "test_df": test_df,
        "test_emb": test_emb,
        "train_df": train_df,
        "corpus_ids": corpus_ids,
        "corpus_texts": corpus_texts,
        "faiss_row_to_id": faiss_row_to_id,
        "index": index,
        "sbert_clf": sbert_clf,
        "tfidf_clf": tfidf_clf,
        "vectorizer": vectorizer,
    }


def _classification_bundle(test_df, test_emb, sbert_clf, tfidf_clf, vectorizer, method: str):
    labeled_mask = test_df["cefr_level"].notna()
    labeled = test_df.loc[labeled_mask].reset_index(drop=True)
    labeled_emb = test_emb[labeled_mask.to_numpy()]
    y_true = labeled["cefr_level"].astype(str).tolist()
    if not y_true:
        raise RuntimeError("No CEFR-labeled rows in test split")

    if method == "tfidf":
        y_pred = tfidf_clf.predict(
            vectorizer.transform(labeled["raw_text"].fillna("").astype(str))
        ).tolist()
    else:
        y_pred = sbert_clf.predict(labeled_emb).tolist()

    metrics, cm = evaluate._classification_metrics(y_true, y_pred)
    return metrics, cm


def _run_rag_keyword_probe(test_df: pd.DataFrame, train_df: pd.DataFrame) -> dict:
    """If ANTHROPIC_API_KEY is set, score 10 RAG answers with keyword overlap."""
    key = getattr(Config, "ANTHROPIC_API_KEY", None)
    if not key or not str(key).strip():
        return {
            "rag_enabled": False,
            "rag_samples": 0,
            "rag_keyword_overlap_mean": None,
            "note": "ANTHROPIC_API_KEY not set; RAG probe skipped",
        }

    from backend.services import rag_service

    sample = test_df.head(RAG_SAMPLE_N)
    scores: list[float] = []
    corpus = train_df.set_index(train_df["resource_id"].astype(str), drop=False)

    for _, row in sample.iterrows():
        # Prefer a short natural query from title / first words of text
        title = str(row.get("title") or "").strip()
        text = str(row.get("raw_text") or "").strip()
        question = title if title else " ".join(text.split()[:12])
        if not question:
            continue
        try:
            result = rag_service.ask(question=question, top_k=5)
            answer = str(result.get("answer") or "")
            contexts = result.get("sources") or result.get("contexts") or []
            ref_bits: list[str] = []
            for ctx in contexts:
                if isinstance(ctx, dict):
                    rid = str(ctx.get("resource_id") or "")
                    if rid and rid in corpus.index:
                        crow = corpus.loc[rid]
                        if isinstance(crow, pd.DataFrame):
                            crow = crow.iloc[0]
                        ref_bits.append(str(crow.get("raw_text") or ""))
                    else:
                        ref_bits.append(
                            str(ctx.get("text_snippet") or ctx.get("text") or ctx.get("snippet") or "")
                        )
                else:
                    ref_bits.append(str(ctx))
            reference = " ".join(ref_bits) if ref_bits else text
            scores.append(_keyword_overlap(answer, reference))
        except Exception as exc:  # noqa: BLE001
            print(f"  RAG sample failed: {exc}")

    mean_score = float(np.mean(scores)) if scores else None
    return {
        "rag_enabled": True,
        "rag_samples": len(scores),
        "rag_keyword_overlap_mean": mean_score,
        "note": "keyword-overlap relevance vs retrieved resource text",
    }


def run_named_experiment(name: str, method: str, description: str) -> None:
    et = ExperimentTracker()
    artefacts = _load_eval_artefacts()
    test_df = artefacts["test_df"]
    test_emb = artefacts["test_emb"]
    train_df = artefacts["train_df"]
    k = evaluate.K

    metadata_on = method in ("sbert_metadata", "sbert_metadata_rag")
    rag_on = method == "sbert_metadata_rag"

    config = ExperimentConfig(
        retrieval_method=method,  # type: ignore[arg-type]
        embedding_model=(
            None
            if method == "tfidf"
            else getattr(Config, "SBERT_MODEL", None)
            or "sentence-transformers/all-MiniLM-L6-v2"
        ),
        classifier="logistic_regression",
        faiss_index_type=None if method == "tfidf" else "IndexFlatIP",
        metadata_filters_enabled=metadata_on,
        rag_enabled=rag_on,
        top_k=k,
        random_seed=42,
        custom_params={"candidate_pool": CANDIDATE_POOL} if metadata_on else {},
    )

    exp = et.create_experiment(name=name, description=description, config=config)
    et.start_experiment(exp.experiment_id)
    print(f"Started experiment {exp.experiment_id} ({name}) method={method}")

    try:
        relevant_sets = [
            evaluate._relevant_ids_for_query(row, train_df)
            for _, row in test_df.iterrows()
        ]

        if method == "tfidf":
            retrieved = evaluate._tfidf_retrieve(
                artefacts["vectorizer"],
                artefacts["corpus_texts"],
                artefacts["corpus_ids"],
                test_df["raw_text"].fillna("").astype(str).tolist(),
                k,
            )
        else:
            pool = CANDIDATE_POOL if metadata_on else k
            retrieved = evaluate._faiss_retrieve(
                artefacts["index"],
                test_emb,
                artefacts["faiss_row_to_id"],
                pool,
            )
            if metadata_on:
                retrieved = evaluate._apply_metadata_filters(
                    retrieved, test_df, train_df, k
                )

        retrieval = evaluate._aggregate_retrieval(retrieved, relevant_sets, k)
        clf_metrics, cm = _classification_bundle(
            test_df,
            test_emb,
            artefacts["sbert_clf"],
            artefacts["tfidf_clf"],
            artefacts["vectorizer"],
            method,
        )

        rag_info = None
        if rag_on:
            print("Running RAG keyword-overlap probe (up to 10 samples)…")
            rag_info = _run_rag_keyword_probe(test_df, train_df)
            print(f"  RAG probe: {rag_info}")

        payload = evaluate._results_payload(retrieval, clf_metrics, cm, clf_metrics.get("labels"))
        recorded = et.record_results(exp.experiment_id, payload)

        if rag_info is not None:
            # Persist RAG probe details on the experiment notes / custom_params
            note = (
                f"RAG probe: samples={rag_info.get('rag_samples')}, "
                f"keyword_overlap_mean={rag_info.get('rag_keyword_overlap_mean')}, "
                f"{rag_info.get('note')}"
            )
            updated = recorded.model_copy(
                update={
                    "notes": ((recorded.notes + "\n") if recorded.notes else "") + note,
                    "config": recorded.config.model_copy(
                        update={
                            "custom_params": {
                                **recorded.config.custom_params,
                                **rag_info,
                            }
                        }
                    ),
                }
            )
            et._experiments[exp.experiment_id] = updated
            et._save()

        out_dir = _PROJECT_ROOT / "research" / "reports" / "experiments"
        out_dir.mkdir(parents=True, exist_ok=True)
        card = et.export_experiment_card(exp.experiment_id, out_dir)
        print(f"Recorded results. Experiment card -> {card}")
        print(
            f"Retrieval: P@10={retrieval['precision_at_10']:.4f} "
            f"R@10={retrieval['recall_at_10']:.4f} "
            f"MAP={retrieval['map']:.4f} "
            f"F1@10={retrieval['f1_at_10']:.4f} "
            f"MRR={retrieval.get('mrr', 0):.4f}"
        )
    except Exception as exc:
        et.fail_experiment(exp.experiment_id, str(exc))
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a named EFL IndexDB feasibility experiment"
    )
    parser.add_argument("--name", required=True, help="Experiment display name")
    parser.add_argument(
        "--method",
        required=True,
        choices=["tfidf", "sbert", "sbert_metadata", "sbert_metadata_rag"],
        help="Retrieval / evaluation configuration",
    )
    parser.add_argument(
        "--description",
        default="",
        help="Short description for the experiment log",
    )
    args = parser.parse_args(argv)
    run_named_experiment(args.name, args.method, args.description)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

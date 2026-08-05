"""
Stage 12 — Explain Local

Per-prediction LIME explanations for sampled test resources.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from lime.lime_tabular import LimeTabularExplainer
from sentence_transformers import SentenceTransformer

from backend.models.embedder import DEFAULT_MODEL_NAME, get_embedder
from backend.utils.config import DATA_EMBEDDINGS, DATA_PROCESSED, DATA_SPLITS
from backend.utils.logger import get_logger
from backend.utils import pipeline_state

logger = get_logger("efl_indexdb.pipeline.explain_local")

STAGE_NAME = "Explain Local"
TEST_PARQUET = DATA_SPLITS / "test" / "test.parquet"
TEST_EMBEDDINGS = DATA_EMBEDDINGS / "test_embeddings.npy"
TEST_IDS = DATA_EMBEDDINGS / "test_ids.json"
TRAIN_BALANCED = DATA_SPLITS / "train" / "balanced_train.parquet"
TRAIN_BALANCED_EMB = DATA_SPLITS / "train" / "balanced_embeddings.npy"
SBERT_MODEL_PATH = DATA_PROCESSED / "models" / "sbert_lr_classifier.joblib"
REPORT_PATH = DATA_PROCESSED / "12_explain_local_report.json"

CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
N_SAMPLES = 10
TOP_FEATURES = 5
RANDOM_STATE = 42
LIME_TRAIN_CAP = 1500

def _align(df: pd.DataFrame, embeddings: np.ndarray, ids: list[str]) -> tuple[pd.DataFrame, np.ndarray]:
    id_to_pos = {rid: i for i, rid in enumerate(ids)}
    keep: list[int] = []
    ordered: list[int] = []
    for row_i, rid in enumerate(df["resource_id"].astype(str).tolist()):
        pos = id_to_pos.get(rid)
        if pos is None:
            continue
        keep.append(row_i)
        ordered.append(pos)
    return df.iloc[keep].reset_index(drop=True), embeddings[np.asarray(ordered, dtype=np.int64)]

def _stratified_sample(df: pd.DataFrame, n: int = N_SAMPLES, seed: int = RANDOM_STATE) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    labeled = df[df["cefr_level"].notna()].copy()
    selected_idx: list[int] = []

    if len(labeled):

        levels = [c for c in CEFR_ORDER if (labeled["cefr_level"].astype(str) == c).any()]
        if levels:
            base = max(1, n // len(levels))
            extras = n - base * len(levels)
            for i, level in enumerate(levels):
                pool = labeled.index[labeled["cefr_level"].astype(str) == level].to_numpy()
                take = min(len(pool), base + (1 if i < extras else 0))
                if take <= 0:
                    continue
                chosen = rng.choice(pool, size=take, replace=False)
                selected_idx.extend(chosen.tolist())

    if len(selected_idx) < n:
        remaining = df.index.difference(selected_idx).to_numpy()
        need = n - len(selected_idx)
        if len(remaining) and need > 0:
            chosen = rng.choice(remaining, size=min(need, len(remaining)), replace=False)
            selected_idx.extend(chosen.tolist())

    selected_idx = selected_idx[:n]
    if not selected_idx:
        raise RuntimeError("Could not sample any test rows for Explain Local")
    return df.loc[selected_idx].reset_index(drop=True)

def _load_sentence_transformer(model_name: str) -> SentenceTransformer:
    """Prefer process embedder / local HF cache — avoid Hub when offline."""
    try:
        return get_embedder(model_name).model
    except Exception as exc:
        logger.warning("get_embedder failed (%s); trying local_files_only", exc)
    try:
        return SentenceTransformer(model_name, local_files_only=True)
    except Exception as cache_exc:
        logger.warning(
            "Local cache miss for %s (%s); attempting download",
            model_name,
            cache_exc,
        )
        return SentenceTransformer(model_name, local_files_only=False)

def _fallback_dim_map(n_dims: int) -> dict[int, str]:
    return {d: f"dim_{d}" for d in range(n_dims)}

def _build_dim_token_map(
    model_name: str = DEFAULT_MODEL_NAME,
    *,
    n_dims: int | None = None,
    top_per_dim: int = 1,
) -> dict[int, str]:
    """
    Approximate mapping: for each embedding dimension, pick the tokenizer
    vocabulary token whose input-embedding component on that dim has the
    largest absolute value (excluding special tokens).

    If the model cannot be loaded offline (DNS / Hub down), fall back to
    ``dim_N`` labels so LIME explanations still complete.
    """
    del top_per_dim
    logger.info("building approx dim→token map from %s input embeddings", model_name)
    try:
        st = _load_sentence_transformer(model_name)
        tokenizer = st.tokenizer
        emb_layer = st[0].auto_model.get_input_embeddings()
        weight = emb_layer.weight.detach().cpu().numpy()

        special = set(int(i) for i in tokenizer.all_special_ids)
        abs_w = np.abs(weight)
        for sid in special:
            if 0 <= sid < abs_w.shape[0]:
                abs_w[sid, :] = -1.0
        top_ids = np.argmax(abs_w, axis=0)
        mapping: dict[int, str] = {}
        for d, vocab_id in enumerate(top_ids.tolist()):
            piece = tokenizer.convert_ids_to_tokens(int(vocab_id))
            mapping[d] = piece if piece else f"dim_{d}"
        return mapping
    except Exception as exc:
        dims = int(n_dims) if n_dims is not None else 384
        logger.warning(
            "dim→token map unavailable (%s); using dim_N labels for %s dims",
            exc,
            dims,
        )
        return _fallback_dim_map(dims)

def _lime_top_features(
    explainer: LimeTabularExplainer,
    predict_proba,
    x: np.ndarray,
    predicted_label: str,
    class_names: list[str],
    dim_token_map: dict[int, str],
) -> list[dict]:
    label_idx = class_names.index(predicted_label) if predicted_label in class_names else 0
    explanation = explainer.explain_instance(
        x.astype(np.float64),
        predict_proba,
        num_features=TOP_FEATURES,
        labels=(label_idx,),
    )
    pairs = explanation.as_list(label=label_idx)
    features: list[dict] = []
    for name, weight in pairs[:TOP_FEATURES]:

        dim = None
        text = str(name)
        for part in text.replace(">", " ").replace("<", " ").replace("=", " ").split():
            if part.startswith("dim_"):
                try:
                    dim = int(part.split("_", 1)[1])
                except ValueError:
                    dim = None
                break
        if dim is None:

            digits = "".join(ch if ch.isdigit() else " " for ch in text).split()
            dim = int(digits[0]) if digits else -1
        features.append(
            {
                "dim": int(dim),
                "weight": float(weight),
                "approx_token": dim_token_map.get(int(dim), f"dim_{dim}"),
                "lime_feature": text,
            }
        )
    return features

def run() -> dict:
    pipeline_state.mark_running(STAGE_NAME)
    try:
        for path in (
            TEST_PARQUET,
            TEST_EMBEDDINGS,
            TEST_IDS,
            TRAIN_BALANCED,
            TRAIN_BALANCED_EMB,
            SBERT_MODEL_PATH,
        ):
            if not path.exists():
                raise RuntimeError(f"Missing required artefact: {path}")

        test_df = pd.read_parquet(TEST_PARQUET)
        test_emb = np.load(TEST_EMBEDDINGS).astype(np.float32, copy=False)
        with TEST_IDS.open("r", encoding="utf-8") as fh:
            test_ids = json.load(fh)
        test_df, test_emb = _align(test_df, test_emb, test_ids)

        test_df = test_df.copy()
        test_df["_emb_row"] = np.arange(len(test_df))

        sample_df = _stratified_sample(test_df, n=N_SAMPLES, seed=RANDOM_STATE)
        sample_emb = test_emb[sample_df["_emb_row"].to_numpy()]
        logger.info(
            "sampled %s test rows; cefr counts=%s",
            len(sample_df),
            sample_df["cefr_level"].fillna("(null)").astype(str).value_counts().to_dict(),
        )

        clf = joblib.load(SBERT_MODEL_PATH)
        class_names = [str(c) for c in clf.classes_]

        train_df = pd.read_parquet(TRAIN_BALANCED)
        train_emb = np.load(TRAIN_BALANCED_EMB).astype(np.float32, copy=False)
        labeled_mask = train_df["cefr_level"].notna().to_numpy()
        train_X = train_emb[labeled_mask]
        if len(train_X) > LIME_TRAIN_CAP:
            rng = np.random.default_rng(RANDOM_STATE)
            train_X = train_X[rng.choice(len(train_X), size=LIME_TRAIN_CAP, replace=False)]

        feature_names = [f"dim_{i}" for i in range(train_X.shape[1])]
        explainer = LimeTabularExplainer(
            train_X.astype(np.float64),
            feature_names=feature_names,
            class_names=class_names,
            discretize_continuous=True,
            mode="classification",
            random_state=RANDOM_STATE,
        )

        dim_token_map = _build_dim_token_map(
            DEFAULT_MODEL_NAME,
            n_dims=int(train_X.shape[1]),
        )

        def predict_proba(batch: np.ndarray) -> np.ndarray:
            return clf.predict_proba(batch)

        records: list[dict] = []
        for i, row in sample_df.iterrows():
            x = sample_emb[i]
            pred = str(clf.predict(x.reshape(1, -1))[0])
            true_cefr = None if pd.isna(row.get("cefr_level")) else str(row["cefr_level"])
            title = None if pd.isna(row.get("title")) else str(row["title"])
            top_features = _lime_top_features(
                explainer,
                predict_proba,
                x,
                pred,
                class_names,
                dim_token_map,
            )

            bits = [
                f"{f['approx_token']}(dim {f['dim']}:{f['weight']:+.3f})"
                for f in top_features
            ]
            readable = (
                f"Predicted {pred}"
                + (f" (true {true_cefr})" if true_cefr else "")
                + "; influential approx tokens: "
                + ", ".join(bits)
            )
            record = {
                "resource_id": str(row["resource_id"]),
                "title": title,
                "predicted_cefr": pred,
                "true_cefr": true_cefr,
                "top_features": top_features,
                "human_readable": readable,
            }
            records.append(record)
            logger.info("explained %s → %s", record["resource_id"], pred)

        report = {
            "stage": STAGE_NAME,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "n_samples": len(records),
            "seed": RANDOM_STATE,
            "explanations": records,
        }

        with REPORT_PATH.open("w", encoding="utf-8") as fh:
            json.dump(records, fh, indent=2)
            fh.write("\n")

        meta_path = DATA_PROCESSED / "12_explain_local_meta.json"
        with meta_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
            fh.write("\n")
        logger.info("wrote local explanations → %s (%s items)", REPORT_PATH, len(records))

        pipeline_state.mark_complete(STAGE_NAME)
        return report
    except Exception:
        pipeline_state.mark_failed(STAGE_NAME)
        raise

if __name__ == "__main__":
    run()

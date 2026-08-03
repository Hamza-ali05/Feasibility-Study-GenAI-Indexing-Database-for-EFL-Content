"""
Stage 13 — Explain Quality

Faithfulness, LIME stability, and CEFR/skill bias audit.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from lime.lime_tabular import LimeTabularExplainer
from sklearn.metrics import f1_score
from sklearn.metrics.pairwise import cosine_similarity
from tabulate import tabulate

from backend.utils.config import DATA_EMBEDDINGS, DATA_PROCESSED, DATA_SPLITS
from backend.utils.logger import get_logger
from backend.utils import pipeline_state

logger = get_logger("efl_indexdb.pipeline.explain_quality")

STAGE_NAME = "Explain Quality"
EVAL_REPORT = DATA_PROCESSED / "10_evaluation_report.json"
GLOBAL_REPORT = DATA_PROCESSED / "11_explain_global_report.json"
LOCAL_REPORT = DATA_PROCESSED / "12_explain_local_report.json"
REPORT_PATH = DATA_PROCESSED / "13_explain_quality_report.json"

TEST_PARQUET = DATA_SPLITS / "test" / "test.parquet"
TEST_EMBEDDINGS = DATA_EMBEDDINGS / "test_embeddings.npy"
TEST_IDS = DATA_EMBEDDINGS / "test_ids.json"
TRAIN_BALANCED = DATA_SPLITS / "train" / "balanced_train.parquet"
TRAIN_BALANCED_EMB = DATA_SPLITS / "train" / "balanced_embeddings.npy"
SBERT_MODEL_PATH = DATA_PROCESSED / "models" / "sbert_lr_classifier.joblib"

BIAS_F1_THRESHOLD = 0.60
LIME_TRAIN_CAP = 800
TOP_N_WEIGHTS = 5
STABILITY_SEEDS = (7, 99)


def _require(path) -> None:
    if not path.exists():
        raise RuntimeError(f"Missing required artefact: {path}. Run prior stages first.")


def _f1_from_confusion(cm: list[list[int]], labels: list[str]) -> dict[str, float]:
    matrix = np.asarray(cm, dtype=float)
    scores: dict[str, float] = {}
    for i, label in enumerate(labels):
        tp = matrix[i, i]
        fp = matrix[:, i].sum() - tp
        fn = matrix[i, :].sum() - tp
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )
        scores[str(label)] = float(f1)
    return scores


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


def _weight_vector(pairs: list[tuple[int, float]], dim: int) -> np.ndarray:
    vec = np.zeros(dim, dtype=np.float64)
    for feature_dim, weight in pairs:
        if 0 <= feature_dim < dim:
            vec[feature_dim] = float(weight)
    return vec


def _lime_feature_pairs(
    explainer: LimeTabularExplainer,
    predict_proba,
    x: np.ndarray,
    predicted_label: str,
    class_names: list[str],
) -> list[tuple[int, float]]:
    label_idx = class_names.index(predicted_label) if predicted_label in class_names else 0
    explanation = explainer.explain_instance(
        x.astype(np.float64),
        predict_proba,
        num_features=TOP_N_WEIGHTS,
        labels=(label_idx,),
    )
    pairs: list[tuple[int, float]] = []
    for name, weight in explanation.as_list(label=label_idx)[:TOP_N_WEIGHTS]:
        text = str(name)
        dim = -1
        for part in text.replace(">", " ").replace("<", " ").replace("=", " ").split():
            if part.startswith("dim_"):
                try:
                    dim = int(part.split("_", 1)[1])
                except ValueError:
                    dim = -1
                break
        if dim < 0:
            digits = "".join(ch if ch.isdigit() else " " for ch in text).split()
            dim = int(digits[0]) if digits else -1
        pairs.append((dim, float(weight)))
    return pairs


def _faithfulness(
    clf,
    embeddings_by_id: dict[str, np.ndarray],
    local_explanations: list[dict],
) -> float:
    flips = 0
    n = 0
    for item in local_explanations:
        rid = str(item["resource_id"])
        x = embeddings_by_id.get(rid)
        if x is None or not item.get("top_features"):
            continue
        top = max(item["top_features"], key=lambda f: abs(float(f.get("weight", 0.0))))
        dim = int(top["dim"])
        if dim < 0 or dim >= x.shape[0]:
            continue
        original = str(clf.predict(x.reshape(1, -1))[0])
        x_flip = x.copy()
        # Flip: negate the top influential dimension
        x_flip[dim] = -x_flip[dim]
        new_pred = str(clf.predict(x_flip.reshape(1, -1))[0])
        n += 1
        if new_pred != original:
            flips += 1
    if n == 0:
        return 0.0
    return float(flips / n)


def _stability(
    clf,
    train_X: np.ndarray,
    sample_embeddings: list[np.ndarray],
    sample_preds: list[str],
) -> float:
    class_names = [str(c) for c in clf.classes_]
    feature_names = [f"dim_{i}" for i in range(train_X.shape[1])]
    dim = train_X.shape[1]

    def predict_proba(batch: np.ndarray) -> np.ndarray:
        return clf.predict_proba(batch)

    sims: list[float] = []
    for x, pred in zip(sample_embeddings, sample_preds):
        vectors = []
        for seed in STABILITY_SEEDS:
            explainer = LimeTabularExplainer(
                train_X.astype(np.float64),
                feature_names=feature_names,
                class_names=class_names,
                discretize_continuous=True,
                mode="classification",
                random_state=seed,
            )
            pairs = _lime_feature_pairs(explainer, predict_proba, x, pred, class_names)
            vectors.append(_weight_vector(pairs, dim))
        sim = float(cosine_similarity(vectors[0].reshape(1, -1), vectors[1].reshape(1, -1))[0, 0])
        if np.isnan(sim):
            sim = 0.0
        sims.append(sim)
    return float(np.mean(sims)) if sims else 0.0


def _per_skill_f1(clf, test_df: pd.DataFrame, test_emb: np.ndarray) -> dict[str, float]:
    if "skill_type" not in test_df.columns:
        return {}
    mask = test_df["skill_type"].notna() & test_df["cefr_level"].notna()
    if not mask.any():
        logger.info("No rows with both skill_type and cefr_level; per_skill_f1 empty")
        return {}

    subset = test_df.loc[mask].reset_index(drop=True)
    X = test_emb[mask.to_numpy()]
    y_true = subset["cefr_level"].astype(str)
    y_pred = pd.Series(clf.predict(X), dtype=str)
    scores: dict[str, float] = {}
    for skill, group in subset.groupby(subset["skill_type"].astype(str)):
        idx = group.index.to_numpy()
        if len(idx) == 0:
            continue
        scores[str(skill)] = float(
            f1_score(y_true.iloc[idx], y_pred.iloc[idx], average="macro", zero_division=0)
        )
    return scores


def run() -> dict:
    pipeline_state.mark_running(STAGE_NAME)
    try:
        for path in (EVAL_REPORT, GLOBAL_REPORT, LOCAL_REPORT, SBERT_MODEL_PATH):
            _require(path)

        with EVAL_REPORT.open("r", encoding="utf-8") as fh:
            eval_report = json.load(fh)
        with GLOBAL_REPORT.open("r", encoding="utf-8") as fh:
            global_report = json.load(fh)
        with LOCAL_REPORT.open("r", encoding="utf-8") as fh:
            local_explanations = json.load(fh)

        if not isinstance(local_explanations, list):
            local_explanations = local_explanations.get("explanations", [])

        clf = joblib.load(SBERT_MODEL_PATH)

        # --- Bias from evaluation confusion matrix (CEFR) ---
        labels = eval_report.get("confusion_matrix_labels") or [
            str(c) for c in getattr(clf, "classes_", [])
        ]
        cm = eval_report.get("confusion_matrix_sbert") or []
        per_cefr_f1 = _f1_from_confusion(cm, labels) if cm else {}

        # --- Load embeddings for faithfulness / stability / skill F1 ---
        for path in (TEST_PARQUET, TEST_EMBEDDINGS, TEST_IDS, TRAIN_BALANCED, TRAIN_BALANCED_EMB):
            _require(path)

        test_df = pd.read_parquet(TEST_PARQUET)
        test_emb = np.load(TEST_EMBEDDINGS).astype(np.float32, copy=False)
        with TEST_IDS.open("r", encoding="utf-8") as fh:
            test_ids = json.load(fh)
        test_df, test_emb = _align(test_df, test_emb, test_ids)
        emb_by_id = {
            str(rid): test_emb[i]
            for i, rid in enumerate(test_df["resource_id"].astype(str).tolist())
        }

        faithfulness_score = _faithfulness(clf, emb_by_id, local_explanations)
        logger.info("faithfulness flip_rate=%.4f", faithfulness_score)

        train_df = pd.read_parquet(TRAIN_BALANCED)
        train_emb = np.load(TRAIN_BALANCED_EMB).astype(np.float32, copy=False)
        labeled_mask = train_df["cefr_level"].notna().to_numpy()
        train_X = train_emb[labeled_mask]
        if len(train_X) > LIME_TRAIN_CAP:
            rng = np.random.default_rng(42)
            train_X = train_X[rng.choice(len(train_X), size=LIME_TRAIN_CAP, replace=False)]

        sample_embeddings: list[np.ndarray] = []
        sample_preds: list[str] = []
        for item in local_explanations:
            rid = str(item["resource_id"])
            x = emb_by_id.get(rid)
            if x is None:
                continue
            sample_embeddings.append(x)
            sample_preds.append(str(item.get("predicted_cefr") or clf.predict(x.reshape(1, -1))[0]))

        logger.info("computing LIME stability on %s samples (seeds=%s)", len(sample_embeddings), STABILITY_SEEDS)
        stability_score = _stability(clf, train_X, sample_embeddings, sample_preds)
        logger.info("stability_score=%.4f", stability_score)

        per_skill_f1 = _per_skill_f1(clf, test_df, test_emb)

        bias_flags: list[str] = []
        for level, score in per_cefr_f1.items():
            if score < BIAS_F1_THRESHOLD:
                bias_flags.append(f"CEFR {level} F1={score:.3f} < {BIAS_F1_THRESHOLD:.2f} (at risk)")
        for skill, score in per_skill_f1.items():
            if score < BIAS_F1_THRESHOLD:
                bias_flags.append(f"skill {skill} F1={score:.3f} < {BIAS_F1_THRESHOLD:.2f} (at risk)")
        if not per_skill_f1:
            bias_flags.append(
                "skill_type unavailable or fully null — per_skill_f1 not computed"
            )

        # Stdout bias audit table
        rows = [["CEFR", level, f"{score:.3f}", "at risk" if score < BIAS_F1_THRESHOLD else "ok"]
                for level, score in per_cefr_f1.items()]
        rows += [["skill", skill, f"{score:.3f}", "at risk" if score < BIAS_F1_THRESHOLD else "ok"]
                 for skill, score in per_skill_f1.items()]
        if not rows:
            rows = [["—", "—", "—", "no group metrics"]]
        print("\n=== Bias audit summary (EFL IndexDB) ===")
        print(tabulate(rows, headers=["group_type", "group", "f1", "status"], tablefmt="github"))
        print(f"faithfulness_score (flip_rate): {faithfulness_score:.4f}")
        print(f"stability_score: {stability_score:.4f}")
        print(f"bias_flags ({len(bias_flags)}):")
        for flag in bias_flags:
            print(f"  - {flag}")
        print("========================================\n")

        report = {
            "stage": STAGE_NAME,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "faithfulness_score": round(faithfulness_score, 6),
            "stability_score": round(stability_score, 6),
            "per_cefr_f1": {k: round(v, 6) for k, v in per_cefr_f1.items()},
            "per_skill_f1": {k: round(v, 6) for k, v in per_skill_f1.items()},
            "bias_flags": bias_flags,
            "inputs": {
                "evaluation_report": str(EVAL_REPORT.as_posix()),
                "explain_global_report": str(GLOBAL_REPORT.as_posix()),
                "explain_local_report": str(LOCAL_REPORT.as_posix()),
                "global_top_features_available": bool(
                    global_report.get("top_20_shap_features")
                ),
            },
            "bias_threshold": BIAS_F1_THRESHOLD,
        }
        with REPORT_PATH.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
            fh.write("\n")
        logger.info("wrote explain-quality report → %s", REPORT_PATH)

        pipeline_state.mark_complete(STAGE_NAME)
        return report
    except Exception:
        pipeline_state.mark_failed(STAGE_NAME)
        raise


if __name__ == "__main__":
    run()

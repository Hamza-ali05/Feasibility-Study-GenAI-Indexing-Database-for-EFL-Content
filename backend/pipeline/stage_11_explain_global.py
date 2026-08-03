"""
Stage 11 — Explain Global

Global SHAP explainability for the SBERT CEFR logistic regression classifier.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np
import pandas as pd
import shap

from backend.utils.config import DATA_PROCESSED, DATA_SPLITS
from backend.utils.logger import get_logger
from backend.utils import pipeline_state

logger = get_logger("efl_indexdb.pipeline.explain_global")

STAGE_NAME = "Explain Global"
BALANCED_PARQUET = DATA_SPLITS / "train" / "balanced_train.parquet"
BALANCED_EMBEDDINGS = DATA_SPLITS / "train" / "balanced_embeddings.npy"
SBERT_MODEL_PATH = DATA_PROCESSED / "models" / "sbert_lr_classifier.joblib"
EXPLAIN_DIR = DATA_PROCESSED / "explain"
REPORT_PATH = DATA_PROCESSED / "11_explain_global_report.json"

BG_PAGE = "#F9F8F5"
BORDER = "#D3D1C7"
ACCENT = "#3C3489"
TEXT_MUTED = "#888780"
TEXT_PRIMARY = "#2C2C2A"

TOP_N = 20
# Cap rows for SHAP / beeswarm speed while remaining representative
MAX_EXPLAIN_ROWS = 2000
RANDOM_STATE = 42


def _style_axes(ax: plt.Axes) -> None:
    ax.set_facecolor(BG_PAGE)
    ax.tick_params(colors=TEXT_MUTED)
    ax.xaxis.label.set_color(TEXT_PRIMARY)
    ax.yaxis.label.set_color(TEXT_PRIMARY)
    ax.title.set_color(TEXT_PRIMARY)
    for spine in ax.spines.values():
        spine.set_color(BORDER)


def _load_labeled_matrix() -> tuple[np.ndarray, np.ndarray, list[str]]:
    if not BALANCED_PARQUET.exists() or not BALANCED_EMBEDDINGS.exists():
        raise RuntimeError(
            "Missing balanced train artefacts. Run Balance/Train before Explain Global."
        )
    if not SBERT_MODEL_PATH.exists():
        raise RuntimeError(f"Missing classifier: {SBERT_MODEL_PATH}")

    df = pd.read_parquet(BALANCED_PARQUET)
    emb = np.load(BALANCED_EMBEDDINGS).astype(np.float32, copy=False)
    if len(df) != len(emb):
        raise RuntimeError("balanced_train / embeddings length mismatch")

    mask = df["cefr_level"].notna().to_numpy()
    X = emb[mask]
    y = df.loc[mask, "cefr_level"].astype(str).to_numpy()
    if len(X) == 0:
        raise RuntimeError("No CEFR-labeled training rows for SHAP")

    if len(X) > MAX_EXPLAIN_ROWS:
        rng = np.random.default_rng(RANDOM_STATE)
        idx = rng.choice(len(X), size=MAX_EXPLAIN_ROWS, replace=False)
        X = X[idx]
        y = y[idx]
        logger.info("subsampled labeled rows for SHAP: %s", MAX_EXPLAIN_ROWS)

    return X, y, sorted(set(y.tolist()))


def _mean_abs_shap_per_class(
    shap_values: list[np.ndarray] | np.ndarray,
    class_names: list[str],
    feature_names: list[str],
) -> list[dict]:
    """
    shap_values for multi-class LinearExplainer is typically a list of
    (n_samples, n_features) arrays, one per class.
    """
    if isinstance(shap_values, list):
        per_class = shap_values
    elif isinstance(shap_values, np.ndarray) and shap_values.ndim == 3:
        # (n_samples, n_features, n_classes) or (n_classes, n_samples, n_features)
        if shap_values.shape[0] == len(class_names):
            per_class = [shap_values[i] for i in range(len(class_names))]
        else:
            per_class = [shap_values[:, :, i] for i in range(shap_values.shape[-1])]
    else:
        per_class = [np.asarray(shap_values)]
        class_names = class_names[:1] or ["model"]

    # Global ranking by mean |SHAP| across classes
    stacked = np.stack([np.abs(arr).mean(axis=0) for arr in per_class], axis=0)
    global_mean = stacked.mean(axis=0)
    top_idx = np.argsort(-global_mean)[:TOP_N]

    results: list[dict] = []
    for rank, dim in enumerate(top_idx.tolist(), start=1):
        entry = {
            "rank": rank,
            "dimension_index": int(dim),
            "feature": feature_names[dim],
            "mean_abs_shap_global": float(global_mean[dim]),
            "mean_abs_shap_per_class": {
                class_names[c]: float(stacked[c, dim]) for c in range(len(per_class))
            },
        }
        results.append(entry)
    return results


def _plot_summary_bar(mean_abs: np.ndarray, feature_names: list[str], path) -> None:
    top_idx = np.argsort(-mean_abs)[:TOP_N]
    labels = [feature_names[i] for i in top_idx][::-1]
    values = mean_abs[top_idx][::-1]

    fig, ax = plt.subplots(figsize=(8, 6), facecolor=BG_PAGE)
    ax.barh(labels, values, color=ACCENT, edgecolor=BORDER, linewidth=0.6)
    ax.set_xlabel("mean(|SHAP value|)")
    ax.set_title("Global SHAP — top 20 embedding dimensions")
    _style_axes(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=120, facecolor=BG_PAGE)
    plt.close(fig)


def _plot_beeswarm(shap_values, X: np.ndarray, feature_names: list[str], path) -> None:
    """
    Beeswarm for the class with highest mean |SHAP| mass (or first class).
    Uses shap.summary_plot then restyles figure colours.
    """
    if isinstance(shap_values, list):
        # Pick class with largest overall |SHAP|
        masses = [float(np.abs(v).mean()) for v in shap_values]
        class_i = int(np.argmax(masses))
        values = shap_values[class_i]
    elif isinstance(shap_values, np.ndarray) and shap_values.ndim == 3:
        if shap_values.shape[0] < shap_values.shape[-1]:
            masses = [float(np.abs(shap_values[i]).mean()) for i in range(shap_values.shape[0])]
            class_i = int(np.argmax(masses))
            values = shap_values[class_i]
        else:
            masses = [float(np.abs(shap_values[:, :, i]).mean()) for i in range(shap_values.shape[-1])]
            class_i = int(np.argmax(masses))
            values = shap_values[:, :, class_i]
    else:
        values = np.asarray(shap_values)
        class_i = 0

    plt.figure(facecolor=BG_PAGE)
    shap.summary_plot(
        values,
        X,
        feature_names=feature_names,
        max_display=TOP_N,
        show=False,
        plot_type="dot",
        color=ACCENT,
    )
    fig = plt.gcf()
    fig.patch.set_facecolor(BG_PAGE)
    for ax in fig.axes:
        ax.set_facecolor(BG_PAGE)
        ax.tick_params(colors=TEXT_MUTED)
        for spine in ax.spines.values():
            spine.set_color(BORDER)
        ax.title.set_color(TEXT_PRIMARY)
    fig.tight_layout()
    fig.savefig(path, dpi=120, facecolor=BG_PAGE, bbox_inches="tight")
    plt.close(fig)
    logger.info("beeswarm used SHAP values for class_index=%s", class_i)


def run() -> dict:
    pipeline_state.mark_running(STAGE_NAME)
    try:
        X, y, present_labels = _load_labeled_matrix()
        model = joblib.load(SBERT_MODEL_PATH)
        class_names = [str(c) for c in getattr(model, "classes_", present_labels)]
        feature_names = [f"dim_{i}" for i in range(X.shape[1])]
        logger.info(
            "SHAP LinearExplainer on X=%s classes=%s",
            X.shape,
            class_names,
        )

        explainer = shap.LinearExplainer(model, X)
        shap_values = explainer.shap_values(X)

        # Global mean |SHAP| across classes for bar plot
        top_features = _mean_abs_shap_per_class(shap_values, class_names, feature_names)
        if isinstance(shap_values, list):
            global_mean_abs = np.mean([np.abs(v).mean(axis=0) for v in shap_values], axis=0)
        elif isinstance(shap_values, np.ndarray) and shap_values.ndim == 3:
            if shap_values.shape[0] == len(class_names):
                global_mean_abs = np.mean([np.abs(shap_values[i]).mean(axis=0) for i in range(len(class_names))], axis=0)
            else:
                global_mean_abs = np.mean(
                    [np.abs(shap_values[:, :, i]).mean(axis=0) for i in range(shap_values.shape[-1])],
                    axis=0,
                )
        else:
            global_mean_abs = np.abs(np.asarray(shap_values)).mean(axis=0)

        EXPLAIN_DIR.mkdir(parents=True, exist_ok=True)
        bar_path = EXPLAIN_DIR / "global_shap_bar.png"
        bee_path = EXPLAIN_DIR / "global_shap_beeswarm.png"
        _plot_summary_bar(global_mean_abs, feature_names, bar_path)
        _plot_beeswarm(shap_values, X, feature_names, bee_path)
        logger.info("wrote plots → %s , %s", bar_path, bee_path)

        report = {
            "stage": STAGE_NAME,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "model": str(SBERT_MODEL_PATH.as_posix()),
            "n_samples_explained": int(len(X)),
            "embedding_dim": int(X.shape[1]),
            "classes": class_names,
            "top_20_shap_features": top_features,
            "plots": {
                "global_shap_bar": str(bar_path.as_posix()),
                "global_shap_beeswarm": str(bee_path.as_posix()),
            },
        }
        with REPORT_PATH.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
            fh.write("\n")
        logger.info("wrote explain-global report → %s", REPORT_PATH)

        pipeline_state.mark_complete(STAGE_NAME)
        return report
    except Exception:
        pipeline_state.mark_failed(STAGE_NAME)
        raise


if __name__ == "__main__":
    run()

"""Publication-ready research metrics export for the EFL IndexDB dissertation.

Reads Stages 10–13 evaluation / explainability JSON reports and writes
CSV, LaTeX booktabs, and PNG artefacts under research/reports/metrics/.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

# Project palette (aligned with backend/pipeline/stage_04_eda.py)
BG_PAGE = "#F9F8F5"
BORDER = "#D3D1C7"
TEXT_MUTED = "#888780"
ACCENT_PURPLE = "#3C3489"
ACCENT_PURPLE_BG = "#EEEDFE"
TEXT_PRIMARY = "#2C2C2A"
GREY_MID = "#B4B2A9"
GREY_LIGHT = "#D3D1C7"
GREYISH_CMAP = LinearSegmentedColormap.from_list(
    "efl_greyish",
    ["#F9F8F5", "#D3D1C7", "#B4B2A9", "#888780", "#5F5E5A", ACCENT_PURPLE],
)

CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DATA_PROCESSED = _PROJECT_ROOT / "data" / "processed"
_DATA_EMBEDDINGS = _PROJECT_ROOT / "data" / "embeddings"
_DATA_SPLITS = _PROJECT_ROOT / "data" / "splits"
_DEFAULT_OUT = _PROJECT_ROOT / "research" / "reports" / "metrics"

_STAGE_FILES = {
    "Evaluate": _DATA_PROCESSED / "10_evaluation_report.json",
    "Explain Global": _DATA_PROCESSED / "11_explain_global_report.json",
    "Explain Local": _DATA_PROCESSED / "12_explain_local_report.json",
    "Explain Quality": _DATA_PROCESSED / "13_explain_quality_report.json",
}

_SBERT_MODEL = _DATA_PROCESSED / "models" / "sbert_lr_classifier.joblib"
_TEST_EMBEDDINGS = _DATA_EMBEDDINGS / "test_embeddings.npy"
_TEST_IDS = _DATA_EMBEDDINGS / "test_ids.json"
_TEST_PARQUET = _DATA_SPLITS / "test" / "test.parquet"


def _latex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    out = str(text)
    for src, dst in replacements.items():
        out = out.replace(src, dst)
    return out


def _fmt_metric(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def _delta_cell(delta: float | None, digits: int = 4) -> str:
    if delta is None:
        return "—"
    arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.{digits}f} {arrow}"


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        writer.writerows(rows)


def _write_latex_booktabs(
    path: Path,
    headers: list[str],
    rows: list[list[str]],
    caption: str,
    label: str,
) -> None:
    col_spec = "l" + "r" * (len(headers) - 1)
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        rf"\caption{{{_latex_escape(caption)}}}",
        rf"\label{{{label}}}",
        rf"\begin{{tabular}}{{{col_spec}}}",
        r"\toprule",
        " & ".join(_latex_escape(h) for h in headers) + r" \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(" & ".join(_latex_escape(c) for c in row) + r" \\")
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _render_table_png(
    path: Path,
    headers: list[str],
    rows: list[list[str]],
    title: str,
) -> None:
    n_rows = max(len(rows), 1)
    fig, ax = plt.subplots(
        figsize=(max(7, 1.5 * len(headers)), max(2.8, 0.42 * (n_rows + 2)))
    )
    fig.patch.set_facecolor(BG_PAGE)
    ax.set_facecolor(BG_PAGE)
    ax.axis("off")
    ax.set_title(title, color=TEXT_PRIMARY, fontsize=12, pad=12)

    cell_text = rows if rows else [["—"] * len(headers)]
    table = ax.table(
        cellText=cell_text,
        colLabels=headers,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.15, 1.45)
    for (row_i, _col_i), cell in table.get_celld().items():
        cell.set_edgecolor(BORDER)
        if row_i == 0:
            cell.set_facecolor(ACCENT_PURPLE_BG)
            cell.set_text_props(color=ACCENT_PURPLE, weight="bold")
        else:
            cell.set_facecolor(BG_PAGE)
            cell.set_text_props(color=TEXT_PRIMARY)

    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def _metrics_from_confusion(
    cm: list[list[int]], labels: list[str]
) -> list[dict]:
    """Per-class precision / recall / F1 / support from a confusion matrix."""
    mat = np.asarray(cm, dtype=float)
    if mat.size == 0:
        return []
    rows: list[dict] = []
    for i, label in enumerate(labels):
        if i >= mat.shape[0]:
            break
        tp = mat[i, i]
        fp = mat[:, i].sum() - tp
        fn = mat[i, :].sum() - tp
        support = int(mat[i, :].sum())
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )
        rows.append(
            {
                "label": label,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "support": support,
            }
        )
    return rows


def _pad_confusion_to_cefr(
    cm: list[list[int]], labels: list[str]
) -> tuple[np.ndarray, list[str]]:
    """Expand / reorder confusion matrix onto full A1–C2 axes."""
    label_to_idx = {lab: i for i, lab in enumerate(labels)}
    out = np.zeros((6, 6), dtype=float)
    for i, src in enumerate(CEFR_ORDER):
        if src not in label_to_idx:
            continue
        si = label_to_idx[src]
        for j, dst in enumerate(CEFR_ORDER):
            if dst not in label_to_idx:
                continue
            dj = label_to_idx[dst]
            if si < len(cm) and dj < len(cm[si]):
                out[i, j] = cm[si][dj]
    return out, CEFR_ORDER


class ResearchMetricsExporter:
    """Export Stages 10–13 artefacts as dissertation-ready tables and figures."""

    def __init__(self) -> None:
        missing: list[str] = []
        for stage, path in _STAGE_FILES.items():
            if not path.exists():
                missing.append(f"{stage} ({path.name})")
        if missing:
            raise FileNotFoundError(
                "Missing evaluation artefact(s) for stage(s): "
                + ", ".join(missing)
                + ". Run pipeline Stages 10–13 before exporting research metrics."
            )

        self.eval_report = json.loads(
            _STAGE_FILES["Evaluate"].read_text(encoding="utf-8-sig")
        )
        self.global_report = json.loads(
            _STAGE_FILES["Explain Global"].read_text(encoding="utf-8-sig")
        )
        self.local_report = json.loads(
            _STAGE_FILES["Explain Local"].read_text(encoding="utf-8-sig")
        )
        self.quality_report = json.loads(
            _STAGE_FILES["Explain Quality"].read_text(encoding="utf-8-sig")
        )
        self._generated: list[str] = []

    def _track(self, path: Path) -> Path:
        self._generated.append(str(path.as_posix()))
        return path

    def export_retrieval_metrics_table(self, output_dir: str | Path) -> None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        retrieval = self.eval_report.get("retrieval") or {}
        sbert = retrieval.get("sbert") or {}
        tfidf = retrieval.get("tfidf") or {}
        delta = retrieval.get("delta") or {}

        metric_keys = [
            ("Precision@10", "precision_at_10"),
            ("Recall@10", "recall_at_10"),
            ("MAP", "map"),
            ("F1@10", "f1_at_10"),
        ]
        headers = ["Metric", "SBERT", "TF-IDF", "Delta (↑/↓)"]
        rows: list[list[str]] = []
        for label, key in metric_keys:
            s_val = sbert.get(key)
            t_val = tfidf.get(key)
            d_val = delta.get(key)
            if d_val is None and s_val is not None and t_val is not None:
                d_val = float(s_val) - float(t_val)
            rows.append(
                [
                    label,
                    _fmt_metric(s_val),
                    _fmt_metric(t_val),
                    _delta_cell(float(d_val) if d_val is not None else None),
                ]
            )

        _write_csv(self._track(output_dir / "retrieval_metrics.csv"), headers, rows)
        _write_latex_booktabs(
            self._track(output_dir / "retrieval_metrics.tex"),
            headers,
            rows,
            caption="Retrieval metrics: SBERT vs TF-IDF (test set)",
            label="tab:retrieval_metrics",
        )
        _render_table_png(
            self._track(output_dir / "retrieval_metrics.png"),
            headers,
            rows,
            title="Retrieval Metrics (SBERT vs TF-IDF)",
        )

    def export_classification_metrics_table(self, output_dir: str | Path) -> None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        clf = self.eval_report.get("classification") or {}
        sbert = clf.get("sbert") or {}
        tfidf = clf.get("tfidf") or {}

        metric_keys = [
            ("Accuracy", "accuracy"),
            ("Precision (macro)", "precision_macro"),
            ("Recall (macro)", "recall_macro"),
            ("F1 (macro)", "f1_macro"),
        ]
        headers = ["Metric", "SBERT", "TF-IDF", "Delta"]
        rows: list[list[str]] = []
        for label, key in metric_keys:
            s_val = sbert.get(key)
            t_val = tfidf.get(key)
            d_val = None
            if s_val is not None and t_val is not None:
                d_val = float(s_val) - float(t_val)
            rows.append(
                [
                    label,
                    _fmt_metric(s_val),
                    _fmt_metric(t_val),
                    _delta_cell(d_val),
                ]
            )

        _write_csv(
            self._track(output_dir / "classification_metrics.csv"), headers, rows
        )
        _write_latex_booktabs(
            self._track(output_dir / "classification_metrics.tex"),
            headers,
            rows,
            caption="CEFR classification metrics: SBERT vs TF-IDF",
            label="tab:classification_metrics",
        )
        _render_table_png(
            self._track(output_dir / "classification_metrics.png"),
            headers,
            rows,
            title="Classification Metrics (SBERT vs TF-IDF)",
        )

    def _plot_confusion(
        self, cm: list[list[int]], labels: list[str], path: Path, title: str
    ) -> None:
        mat, axis_labels = _pad_confusion_to_cefr(cm, labels)
        fig, ax = plt.subplots(figsize=(7, 6))
        fig.patch.set_facecolor(BG_PAGE)
        ax.set_facecolor(BG_PAGE)
        im = ax.imshow(mat, cmap=GREYISH_CMAP)
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.ax.yaxis.set_tick_params(color=TEXT_MUTED)
        plt.setp(cbar.ax.yaxis.get_ticklabels(), color=TEXT_MUTED)

        ax.set_xticks(range(6))
        ax.set_yticks(range(6))
        ax.set_xticklabels(axis_labels, color=TEXT_PRIMARY)
        ax.set_yticklabels(axis_labels, color=TEXT_PRIMARY)
        ax.set_xlabel("Predicted CEFR", color=TEXT_PRIMARY)
        ax.set_ylabel("True CEFR", color=TEXT_PRIMARY)
        ax.set_title(title, color=TEXT_PRIMARY)

        thresh = mat.max() / 2.0 if mat.max() > 0 else 0.5
        for i in range(6):
            for j in range(6):
                val = int(mat[i, j])
                ax.text(
                    j,
                    i,
                    str(val),
                    ha="center",
                    va="center",
                    color="white" if mat[i, j] > thresh else TEXT_PRIMARY,
                    fontsize=9,
                )

        for spine in ax.spines.values():
            spine.set_color(BORDER)
        fig.tight_layout()
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=150, facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close(fig)

    def export_confusion_matrix(self, output_dir: str | Path) -> None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        labels = self.eval_report.get("confusion_matrix_labels") or CEFR_ORDER
        cm_sbert = self.eval_report.get("confusion_matrix_sbert") or []
        cm_tfidf = self.eval_report.get("confusion_matrix_tfidf") or []

        self._plot_confusion(
            cm_sbert,
            labels,
            self._track(output_dir / "confusion_matrix_sbert.png"),
            "Confusion Matrix — SBERT",
        )
        self._plot_confusion(
            cm_tfidf,
            labels,
            self._track(output_dir / "confusion_matrix_tfidf.png"),
            "Confusion Matrix — TF-IDF",
        )

    def _export_one_classification_report(
        self,
        output_dir: Path,
        prefix: str,
        cm: list[list[int]],
        labels: list[str],
        title: str,
        caption: str,
        label: str,
    ) -> None:
        per_class = _metrics_from_confusion(cm, labels)
        headers = ["CEFR Level", "Precision", "Recall", "F1-Score", "Support"]
        rows: list[list[str]] = []
        for item in per_class:
            rows.append(
                [
                    item["label"],
                    _fmt_metric(item["precision"]),
                    _fmt_metric(item["recall"]),
                    _fmt_metric(item["f1"]),
                    str(item["support"]),
                ]
            )

        supports = [r["support"] for r in per_class]
        total_support = sum(supports) or 1
        if per_class:
            macro_p = float(np.mean([r["precision"] for r in per_class]))
            macro_r = float(np.mean([r["recall"] for r in per_class]))
            macro_f = float(np.mean([r["f1"] for r in per_class]))
            weighted_p = (
                sum(r["precision"] * r["support"] for r in per_class) / total_support
            )
            weighted_r = (
                sum(r["recall"] * r["support"] for r in per_class) / total_support
            )
            weighted_f = sum(r["f1"] * r["support"] for r in per_class) / total_support
            rows.append(
                [
                    "macro avg",
                    _fmt_metric(macro_p),
                    _fmt_metric(macro_r),
                    _fmt_metric(macro_f),
                    str(sum(supports)),
                ]
            )
            rows.append(
                [
                    "weighted avg",
                    _fmt_metric(weighted_p),
                    _fmt_metric(weighted_r),
                    _fmt_metric(weighted_f),
                    str(sum(supports)),
                ]
            )

        _write_csv(self._track(output_dir / f"{prefix}.csv"), headers, rows)
        _write_latex_booktabs(
            self._track(output_dir / f"{prefix}.tex"),
            headers,
            rows,
            caption=caption,
            label=label,
        )
        _render_table_png(
            self._track(output_dir / f"{prefix}.png"),
            headers,
            rows,
            title=title,
        )

    def export_classification_report(self, output_dir: str | Path) -> None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        labels = self.eval_report.get("confusion_matrix_labels") or CEFR_ORDER
        self._export_one_classification_report(
            output_dir,
            "classification_report_sbert",
            self.eval_report.get("confusion_matrix_sbert") or [],
            labels,
            title="Classification Report — SBERT",
            caption="Per-CEFR classification report (SBERT)",
            label="tab:classification_report_sbert",
        )
        self._export_one_classification_report(
            output_dir,
            "classification_report_tfidf",
            self.eval_report.get("confusion_matrix_tfidf") or [],
            labels,
            title="Classification Report — TF-IDF",
            caption="Per-CEFR classification report (TF-IDF)",
            label="tab:classification_report_tfidf",
        )

    def _load_sbert_probabilities(
        self,
    ) -> tuple[np.ndarray, np.ndarray, list[str]] | None:
        """Load classifier + test set and return (y_true_bin, y_score, class_names).

        y_true_bin is one-hot / indicator matrix (n_samples × n_classes).
        y_score is predict_proba (n_samples × n_classes).
        """
        missing = [
            p
            for p in (_SBERT_MODEL, _TEST_EMBEDDINGS, _TEST_PARQUET)
            if not p.exists()
        ]
        if missing:
            return None

        import joblib
        import pandas as pd

        clf = joblib.load(_SBERT_MODEL)
        emb = np.load(_TEST_EMBEDDINGS).astype(np.float32, copy=False)
        test_df = pd.read_parquet(_TEST_PARQUET)

        if _TEST_IDS.exists():
            with _TEST_IDS.open(encoding="utf-8") as fh:
                test_ids = json.load(fh)
            id_to_pos = {str(rid): i for i, rid in enumerate(test_ids)}
            order = [
                id_to_pos[str(rid)]
                for rid in test_df["resource_id"].astype(str)
                if str(rid) in id_to_pos
            ]
            if order and len(order) == len(test_df):
                emb = emb[np.asarray(order, dtype=int)]
            elif len(emb) != len(test_df):
                n = min(len(emb), len(test_df))
                emb = emb[:n]
                test_df = test_df.iloc[:n].reset_index(drop=True)

        labeled_mask = test_df["cefr_level"].notna()
        labeled = test_df.loc[labeled_mask].reset_index(drop=True)
        labeled_emb = emb[labeled_mask.to_numpy()]
        if labeled.empty:
            return None

        y_true = labeled["cefr_level"].astype(str).to_numpy()
        if hasattr(clf, "predict_proba"):
            y_score = clf.predict_proba(labeled_emb)
            class_names = [str(c) for c in clf.classes_]
        else:
            # Decision function fallback → sigmoid-ish ranking not ideal; skip
            return None

        # Align class order to CEFR where possible
        from sklearn.preprocessing import label_binarize

        y_bin = label_binarize(y_true, classes=class_names)
        if y_bin.ndim == 1:
            y_bin = np.column_stack([1 - y_bin, y_bin])
        return y_bin, y_score, class_names

    def _placeholder_curve(self, path: Path, title: str, reason: str) -> None:
        fig, ax = plt.subplots(figsize=(8, 5))
        fig.patch.set_facecolor(BG_PAGE)
        ax.set_facecolor(BG_PAGE)
        ax.text(
            0.5,
            0.5,
            f"{title}\n\n{reason}",
            ha="center",
            va="center",
            color=TEXT_MUTED,
            transform=ax.transAxes,
            fontsize=11,
        )
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color(BORDER)
        fig.tight_layout()
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=150, facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close(fig)

    def export_roc_curves(self, output_dir: str | Path) -> None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "roc_curves_sbert.png"

        loaded = self._load_sbert_probabilities()
        if loaded is None:
            self._placeholder_curve(
                self._track(path),
                "ROC Curves — SBERT",
                "Classifier / test embeddings unavailable.\n"
                "Run Stage 9 (Train) and Stage 10 (Evaluate),\n"
                f"ensuring {_SBERT_MODEL.name} and test_embeddings.npy exist.",
            )
            return

        from sklearn.metrics import auc, roc_curve

        y_bin, y_score, class_names = loaded
        fig, ax = plt.subplots(figsize=(8, 6))
        fig.patch.set_facecolor(BG_PAGE)
        ax.set_facecolor(BG_PAGE)

        colours = [
            "#1F5F3F",
            "#1F4A6E",
            "#7A5A00",
            "#8A4B12",
            "#7A1F35",
            ACCENT_PURPLE,
        ]
        for i, name in enumerate(class_names):
            if y_bin.shape[1] <= i or y_score.shape[1] <= i:
                continue
            # Skip classes with no positive labels
            if y_bin[:, i].sum() == 0:
                continue
            fpr, tpr, _ = roc_curve(y_bin[:, i], y_score[:, i])
            roc_auc = auc(fpr, tpr)
            ax.plot(
                fpr,
                tpr,
                color=colours[i % len(colours)],
                lw=1.8,
                label=f"{name} (AUC = {roc_auc:.3f})",
            )

        ax.plot([0, 1], [0, 1], linestyle="--", color=GREY_MID, lw=1)
        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(0.0, 1.05)
        ax.set_xlabel("False Positive Rate", color=TEXT_PRIMARY)
        ax.set_ylabel("True Positive Rate", color=TEXT_PRIMARY)
        ax.set_title("ROC Curves (one-vs-rest) — SBERT", color=TEXT_PRIMARY)
        ax.legend(loc="lower right", frameon=False, labelcolor=TEXT_MUTED, fontsize=8)
        ax.tick_params(colors=TEXT_MUTED)
        for spine in ax.spines.values():
            spine.set_color(BORDER)

        fig.tight_layout()
        fig.savefig(
            self._track(path), dpi=150, facecolor=fig.get_facecolor(), bbox_inches="tight"
        )
        plt.close(fig)

    def export_precision_recall_curves(self, output_dir: str | Path) -> None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "pr_curves_sbert.png"

        loaded = self._load_sbert_probabilities()
        if loaded is None:
            self._placeholder_curve(
                self._track(path),
                "Precision–Recall Curves — SBERT",
                "Classifier / test embeddings unavailable.\n"
                "Run Stage 9 (Train) and Stage 10 (Evaluate) first.",
            )
            return

        from sklearn.metrics import average_precision_score, precision_recall_curve

        y_bin, y_score, class_names = loaded
        fig, ax = plt.subplots(figsize=(8, 6))
        fig.patch.set_facecolor(BG_PAGE)
        ax.set_facecolor(BG_PAGE)

        colours = [
            "#1F5F3F",
            "#1F4A6E",
            "#7A5A00",
            "#8A4B12",
            "#7A1F35",
            ACCENT_PURPLE,
        ]
        for i, name in enumerate(class_names):
            if y_bin.shape[1] <= i or y_score.shape[1] <= i:
                continue
            if y_bin[:, i].sum() == 0:
                continue
            precision, recall, _ = precision_recall_curve(y_bin[:, i], y_score[:, i])
            ap = average_precision_score(y_bin[:, i], y_score[:, i])
            ax.plot(
                recall,
                precision,
                color=colours[i % len(colours)],
                lw=1.8,
                label=f"{name} (AP = {ap:.3f})",
            )

        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(0.0, 1.05)
        ax.set_xlabel("Recall", color=TEXT_PRIMARY)
        ax.set_ylabel("Precision", color=TEXT_PRIMARY)
        ax.set_title("Precision–Recall Curves — SBERT", color=TEXT_PRIMARY)
        ax.legend(loc="lower left", frameon=False, labelcolor=TEXT_MUTED, fontsize=8)
        ax.tick_params(colors=TEXT_MUTED)
        for spine in ax.spines.values():
            spine.set_color(BORDER)

        fig.tight_layout()
        fig.savefig(
            self._track(path), dpi=150, facecolor=fig.get_facecolor(), bbox_inches="tight"
        )
        plt.close(fig)

    def export_explainability_summary(self, output_dir: str | Path) -> None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        q = self.quality_report
        bias_flags = q.get("bias_flags") or []
        bias_text = "; ".join(bias_flags) if bias_flags else "None"

        headers = ["Metric", "Value"]
        rows = [
            ["Faithfulness Score", _fmt_metric(q.get("faithfulness_score"))],
            ["Stability Score", _fmt_metric(q.get("stability_score"))],
            ["Bias Flags", bias_text],
        ]
        per_cefr = q.get("per_cefr_f1") or {}
        for level in CEFR_ORDER:
            if level in per_cefr:
                rows.append([f"CEFR {level} F1", _fmt_metric(per_cefr[level])])
        for skill, score in sorted((q.get("per_skill_f1") or {}).items()):
            rows.append([f"Skill {skill} F1", _fmt_metric(score)])

        # Also emit dedicated per-CEFR / per-skill companion tables
        cefr_headers = ["CEFR Level", "F1"]
        cefr_rows = [
            [level, _fmt_metric(per_cefr[level])]
            for level in CEFR_ORDER
            if level in per_cefr
        ]
        skill_headers = ["Skill", "F1"]
        skill_rows = [
            [skill, _fmt_metric(score)]
            for skill, score in sorted((q.get("per_skill_f1") or {}).items())
        ]

        _write_csv(
            self._track(output_dir / "explainability_summary.csv"), headers, rows
        )
        _write_latex_booktabs(
            self._track(output_dir / "explainability_summary.tex"),
            headers,
            rows,
            caption="Explainability quality summary (Stage 13)",
            label="tab:explainability_summary",
        )
        _render_table_png(
            self._track(output_dir / "explainability_summary.png"),
            headers,
            rows,
            title="Explainability Summary",
        )

        if cefr_rows:
            _write_csv(
                self._track(output_dir / "explainability_per_cefr_f1.csv"),
                cefr_headers,
                cefr_rows,
            )
        if skill_rows:
            _write_csv(
                self._track(output_dir / "explainability_per_skill_f1.csv"),
                skill_headers,
                skill_rows,
            )

    def export_all(
        self, output_dir: str | Path = "research/reports/metrics"
    ) -> list[str]:
        """Run every export helper; return generated file paths."""
        out = Path(output_dir)
        if not out.is_absolute():
            out = _PROJECT_ROOT / out
        out.mkdir(parents=True, exist_ok=True)
        self._generated = []

        self.export_retrieval_metrics_table(out)
        self.export_classification_metrics_table(out)
        self.export_confusion_matrix(out)
        self.export_classification_report(out)
        self.export_roc_curves(out)
        self.export_precision_recall_curves(out)
        self.export_explainability_summary(out)

        return list(self._generated)

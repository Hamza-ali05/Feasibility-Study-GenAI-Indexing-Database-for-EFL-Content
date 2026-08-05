"""Benchmark comparison report generator for the EFL IndexDB feasibility study.

Compares TF-IDF vs SBERT (+ metadata / RAG variants) using Stage 10 evaluation
artefacts and the research experiment log. Produces markdown, CSV, LaTeX, and PNG.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from research.utils.latex_tables import dataframe_to_all

# Project palette
BG_PAGE = "#F9F8F5"
BORDER = "#D3D1C7"
TEXT_MUTED = "#888780"
ACCENT = "#3C3489"
ACCENT_BG = "#EEEDFE"
TEXT_PRIMARY = "#2C2C2A"
GREYISH_CMAP = LinearSegmentedColormap.from_list(
    "efl_greyish",
    ["#F9F8F5", "#D3D1C7", "#B4B2A9", "#888780", "#5F5E5A", ACCENT],
)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DATA_PROCESSED = _PROJECT_ROOT / "data" / "processed"
_EVAL_PATH = _DATA_PROCESSED / "10_evaluation_report.json"
_PER_QUERY_PATH = _DATA_PROCESSED / "10_per_query_metrics.json"
_EDA_PATH = _DATA_PROCESSED / "04_eda_report.json"
_EXPERIMENT_LOG = _PROJECT_ROOT / "research" / "experiments" / "experiment_log.json"
_DEFAULT_OUT = _PROJECT_ROOT / "research" / "reports" / "benchmark"

METHOD_ROWS = [
    ("tfidf", "TF-IDF Baseline"),
    ("sbert", "SBERT (all-MiniLM-L6-v2)"),
    ("sbert_metadata", "SBERT + Metadata Filters"),
    ("sbert_metadata_rag", "SBERT + Metadata + RAG"),
]

RETRIEVAL_COLS = ["Method", "P@5", "P@10", "R@5", "R@10", "MAP", "MRR", "F1@10"]
CLASS_COLS = ["Method", "Accuracy", "Precision", "Recall", "F1 (macro)"]

_MISSING = "—"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None


def _pct_improve(new: float | None, baseline: float | None) -> float | None:
    if new is None or baseline is None:
        return None
    if baseline == 0:
        return None if new == 0 else float("inf")
    return round(100.0 * (float(new) - float(baseline)) / abs(float(baseline)), 2)


def _cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    diff = a - b
    n = len(diff)
    if n < 2:
        return 0.0
    sd = float(np.std(diff, ddof=1))
    if sd == 0:
        return 0.0
    return float(np.mean(diff) / sd)


def _fmt_cell(value: Any) -> Any:
    if value is None:
        return _MISSING
    if isinstance(value, float):
        if np.isnan(value):
            return _MISSING
        return round(value, 4)
    return value


class BenchmarkReportGenerator:
    """Auto-generate structured GenAI vs TF-IDF benchmark comparison artefacts."""

    def __init__(self) -> None:
        self.eval_report = _load_json(_EVAL_PATH) or {}
        self.eda_report = _load_json(_EDA_PATH) or {}
        self.per_query = _load_json(_PER_QUERY_PATH) or {}
        self.experiment_log = _load_json(_EXPERIMENT_LOG) or {"experiments": []}
        self.notes: list[str] = []
        self._method_metrics = self._collect_method_metrics()

    # ── data collection ─────────────────────────────────────────────────

    def _latest_completed_by_method(self) -> dict[str, dict[str, Any]]:
        """Map retrieval_method → latest completed experiment with results."""
        out: dict[str, dict[str, Any]] = {}
        experiments = self.experiment_log.get("experiments") or []
        for exp in experiments:
            if exp.get("status") != "completed" or not exp.get("results"):
                continue
            cfg = exp.get("config") or {}
            method = cfg.get("retrieval_method")
            if not method:
                continue
            prev = out.get(method)
            if prev is None or str(exp.get("completed_at") or "") >= str(
                prev.get("completed_at") or ""
            ):
                out[method] = exp
        return out

    def _metrics_from_eval(self, key: str) -> dict[str, Any]:
        retrieval = (self.eval_report.get("retrieval") or {}).get(key) or {}
        classification = (self.eval_report.get("classification") or {}).get(key) or {}
        return {
            "precision_at_5": retrieval.get("precision_at_5"),
            "precision_at_10": retrieval.get("precision_at_10"),
            "recall_at_5": retrieval.get("recall_at_5"),
            "recall_at_10": retrieval.get("recall_at_10"),
            "map": retrieval.get("map"),
            "mrr": retrieval.get("mrr"),
            "f1_at_10": retrieval.get("f1_at_10"),
            "accuracy": classification.get("accuracy"),
            "precision_macro": classification.get("precision_macro"),
            "recall_macro": classification.get("recall_macro"),
            "f1_macro": classification.get("f1_macro"),
            "source": "stage_10",
        }

    def _metrics_from_experiment(self, exp: dict[str, Any]) -> dict[str, Any]:
        results = exp.get("results") or {}
        retrieval = results.get("retrieval") or {}
        classification = results.get("classification") or {}
        # Experiment tracker stores precision_at_k (typically @10)
        return {
            "precision_at_5": retrieval.get("precision_at_5"),
            "precision_at_10": retrieval.get("precision_at_k")
            or retrieval.get("precision_at_10"),
            "recall_at_5": retrieval.get("recall_at_5"),
            "recall_at_10": retrieval.get("recall_at_k")
            or retrieval.get("recall_at_10"),
            "map": retrieval.get("map"),
            "mrr": retrieval.get("mrr"),
            "f1_at_10": retrieval.get("f1_at_k") or retrieval.get("f1_at_10"),
            "accuracy": classification.get("accuracy"),
            "precision_macro": classification.get("precision_macro"),
            "recall_macro": classification.get("recall_macro"),
            "f1_macro": classification.get("f1_macro"),
            "source": f"experiment:{exp.get('experiment_id', '')[:8]}",
            "confusion_matrix": results.get("confusion_matrix"),
        }

    def _collect_method_metrics(self) -> dict[str, dict[str, Any]]:
        metrics: dict[str, dict[str, Any]] = {}

        # Prefer Stage 10 for tfidf / sbert when present
        for key in ("tfidf", "sbert"):
            m = self._metrics_from_eval(key)
            if any(m.get(k) is not None for k in ("precision_at_10", "map", "accuracy")):
                metrics[key] = m

        # Overlay / fill from experiments
        for method, exp in self._latest_completed_by_method().items():
            exp_m = self._metrics_from_experiment(exp)
            if method not in metrics:
                metrics[method] = exp_m
            else:
                # Fill missing fields from experiment without overwriting stage-10
                for k, v in exp_m.items():
                    if k == "source":
                        continue
                    if metrics[method].get(k) is None and v is not None:
                        metrics[method][k] = v

        missing = [label for key, label in METHOD_ROWS if key not in metrics]
        if missing:
            self.notes.append(
                "Methods without completed results (run corresponding experiments): "
                + ", ".join(missing)
            )
        return metrics

    # ── public API ──────────────────────────────────────────────────────

    def generate_comparison_table(self) -> pd.DataFrame:
        rows = []
        for key, label in METHOD_ROWS:
            m = self._method_metrics.get(key)
            if not m:
                rows.append(
                    {
                        "Method": label,
                        "P@5": _MISSING,
                        "P@10": _MISSING,
                        "R@5": _MISSING,
                        "R@10": _MISSING,
                        "MAP": _MISSING,
                        "MRR": _MISSING,
                        "F1@10": _MISSING,
                    }
                )
                continue
            rows.append(
                {
                    "Method": label,
                    "P@5": _fmt_cell(m.get("precision_at_5")),
                    "P@10": _fmt_cell(m.get("precision_at_10")),
                    "R@5": _fmt_cell(m.get("recall_at_5")),
                    "R@10": _fmt_cell(m.get("recall_at_10")),
                    "MAP": _fmt_cell(m.get("map")),
                    "MRR": _fmt_cell(m.get("mrr")),
                    "F1@10": _fmt_cell(m.get("f1_at_10")),
                }
            )
        return pd.DataFrame(rows, columns=RETRIEVAL_COLS)

    def generate_classification_comparison(self) -> pd.DataFrame:
        rows = []
        for key, label in METHOD_ROWS:
            m = self._method_metrics.get(key)
            if not m or all(
                m.get(k) is None
                for k in ("accuracy", "precision_macro", "recall_macro", "f1_macro")
            ):
                rows.append(
                    {
                        "Method": label,
                        "Accuracy": _MISSING,
                        "Precision": _MISSING,
                        "Recall": _MISSING,
                        "F1 (macro)": _MISSING,
                    }
                )
                continue
            rows.append(
                {
                    "Method": label,
                    "Accuracy": _fmt_cell(m.get("accuracy")),
                    "Precision": _fmt_cell(m.get("precision_macro")),
                    "Recall": _fmt_cell(m.get("recall_macro")),
                    "F1 (macro)": _fmt_cell(m.get("f1_macro")),
                }
            )
        return pd.DataFrame(rows, columns=CLASS_COLS)

    def generate_statistical_significance(
        self,
        method_a_results: list[float] | np.ndarray | None = None,
        method_b_results: list[float] | np.ndarray | None = None,
        *,
        method_a: str = "sbert",
        method_b: str = "tfidf",
        metric: str = "precision_at_10",
    ) -> dict[str, Any]:
        """Paired t-test, Wilcoxon, and Cohen's d on per-query metrics.

        If ``method_a_results`` / ``method_b_results`` are omitted, load paired
        values from ``data/processed/10_per_query_metrics.json``.
        """
        a = method_a_results
        b = method_b_results

        if a is None or b is None:
            methods = (self.per_query.get("methods") or {})
            rows_a = methods.get(method_a) or []
            rows_b = methods.get(method_b) or []
            by_a = {r["query_id"]: r.get(metric) for r in rows_a if "query_id" in r}
            by_b = {r["query_id"]: r.get(metric) for r in rows_b if "query_id" in r}
            common = sorted(set(by_a) & set(by_b))
            a = [by_a[q] for q in common if by_a[q] is not None and by_b[q] is not None]
            b = [by_b[q] for q in common if by_a[q] is not None and by_b[q] is not None]

        result: dict[str, Any] = {
            "t_test_p": None,
            "wilcoxon_p": None,
            "cohens_d": None,
            "significant_at_05": False,
            "n_paired": 0,
            "metric": metric,
            "method_a": method_a,
            "method_b": method_b,
            "note": None,
        }

        if a is None or b is None or len(a) == 0 or len(b) == 0:
            result["note"] = (
                "Per-query metrics unavailable. Re-run Stage 10 Evaluate to write "
                f"{_PER_QUERY_PATH.name}."
            )
            return result

        arr_a = np.asarray(a, dtype=float)
        arr_b = np.asarray(b, dtype=float)
        n = min(len(arr_a), len(arr_b))
        arr_a, arr_b = arr_a[:n], arr_b[:n]
        result["n_paired"] = int(n)

        if n < 2:
            result["note"] = "Fewer than 2 paired observations; tests not computed."
            return result

        try:
            from scipy import stats

            t_res = stats.ttest_rel(arr_a, arr_b, nan_policy="omit")
            result["t_test_p"] = float(t_res.pvalue)
            try:
                w_res = stats.wilcoxon(arr_a - arr_b, zero_method="wilcox", alternative="two-sided")
                result["wilcoxon_p"] = float(w_res.pvalue)
            except ValueError as exc:
                result["note"] = f"Wilcoxon skipped: {exc}"
            result["cohens_d"] = round(_cohens_d(arr_a, arr_b), 4)
            p = result["t_test_p"]
            result["significant_at_05"] = bool(p is not None and p < 0.05)
        except ImportError:
            # Fallback without scipy: manual paired t approx + skip wilcoxon
            diff = arr_a - arr_b
            mean_d = float(np.mean(diff))
            sd_d = float(np.std(diff, ddof=1))
            if sd_d > 0:
                t_stat = mean_d / (sd_d / np.sqrt(n))
                # two-sided p via normal approximation for large n
                from math import erfc, sqrt

                result["t_test_p"] = float(erfc(abs(t_stat) / sqrt(2)))
            result["cohens_d"] = round(_cohens_d(arr_a, arr_b), 4)
            result["wilcoxon_p"] = None
            result["note"] = "scipy unavailable; Wilcoxon not computed; t p-value via normal approx."
            p = result["t_test_p"]
            result["significant_at_05"] = bool(p is not None and p < 0.05)

        return result

    def generate_improvement_summary(self) -> dict[str, Any]:
        tfidf = self._method_metrics.get("tfidf") or {}
        genai_keys = ("sbert", "sbert_metadata", "sbert_metadata_rag")

        def _score(m: dict[str, Any]) -> float:
            vals = [m.get(k) for k in ("map", "f1_at_10", "precision_at_10") if m.get(k) is not None]
            return float(np.mean(vals)) if vals else -1.0

        best_key = None
        best_m: dict[str, Any] = {}
        best_score = -1.0
        for key in genai_keys:
            m = self._method_metrics.get(key)
            if not m:
                continue
            sc = _score(m)
            if sc > best_score:
                best_score = sc
                best_key = key
                best_m = m

        label = dict(METHOD_ROWS).get(best_key or "", best_key or "—")
        summary = {
            "best_genai_method": label,
            "best_genai_key": best_key,
            "precision_improvement_pct": _pct_improve(
                best_m.get("precision_at_10"), tfidf.get("precision_at_10")
            ),
            "recall_improvement_pct": _pct_improve(
                best_m.get("recall_at_10"), tfidf.get("recall_at_10")
            ),
            "map_improvement_pct": _pct_improve(best_m.get("map"), tfidf.get("map")),
            "f1_improvement_pct": _pct_improve(
                best_m.get("f1_at_10"), tfidf.get("f1_at_10")
            ),
            "mrr_improvement_pct": _pct_improve(best_m.get("mrr"), tfidf.get("mrr")),
            "accuracy_improvement_pct": _pct_improve(
                best_m.get("accuracy"), tfidf.get("accuracy")
            ),
        }
        return summary

    # ── charts / exports ────────────────────────────────────────────────

    def _plot_retrieval_bars(self, df: pd.DataFrame, output_path: Path) -> None:
        metric_cols = [c for c in ["P@5", "P@10", "R@5", "R@10", "MAP", "MRR", "F1@10"] if c in df.columns]
        numeric = df.copy()
        for c in metric_cols:
            numeric[c] = pd.to_numeric(numeric[c], errors="coerce")

        methods = numeric["Method"].tolist()
        x = np.arange(len(methods))
        width = 0.11
        fig, ax = plt.subplots(figsize=(12, 5.5), facecolor=BG_PAGE)
        ax.set_facecolor(BG_PAGE)
        colors = [GREYISH_CMAP(i / max(len(metric_cols) - 1, 1)) for i in range(len(metric_cols))]

        for i, col in enumerate(metric_cols):
            vals = numeric[col].fillna(0).to_numpy()
            offset = (i - (len(metric_cols) - 1) / 2) * width
            bars = ax.bar(x + offset, vals, width, label=col, color=colors[i], edgecolor=BORDER)
            # Hide bars that were missing (NaN → 0 with hatch)
            for j, raw in enumerate(numeric[col].tolist()):
                if pd.isna(raw):
                    bars[j].set_alpha(0.15)

        ax.set_xticks(x)
        ax.set_xticklabels([m.replace(" ", "\n") for m in methods], fontsize=8)
        ax.set_ylabel("Score", color=TEXT_PRIMARY)
        ax.set_ylim(0, 1.05)
        ax.set_title("Retrieval Performance Comparison", color=TEXT_PRIMARY, fontweight="bold")
        ax.legend(frameon=False, fontsize=8, ncol=min(4, len(metric_cols)))
        ax.tick_params(colors=TEXT_MUTED)
        for spine in ax.spines.values():
            spine.set_color(BORDER)
        fig.tight_layout()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches="tight", facecolor=BG_PAGE)
        plt.close(fig)

    def _plot_confusion_side_by_side(self, output_path: Path) -> None:
        labels = self.eval_report.get("confusion_matrix_labels") or [
            "A1",
            "A2",
            "B1",
            "B2",
            "C1",
            "C2",
        ]
        cm_s = self.eval_report.get("confusion_matrix_sbert")
        cm_t = self.eval_report.get("confusion_matrix_tfidf")
        if not cm_s or not cm_t:
            return

        fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), facecolor=BG_PAGE)
        for ax, cm, title in (
            (axes[0], cm_s, "SBERT"),
            (axes[1], cm_t, "TF-IDF"),
        ):
            mat = np.asarray(cm, dtype=float)
            im = ax.imshow(mat, cmap=GREYISH_CMAP)
            ax.set_title(title, color=TEXT_PRIMARY, fontweight="bold")
            ax.set_xticks(range(len(labels)))
            ax.set_yticks(range(len(labels)))
            ax.set_xticklabels(labels, fontsize=8)
            ax.set_yticklabels(labels, fontsize=8)
            ax.set_xlabel("Predicted", color=TEXT_MUTED)
            ax.set_ylabel("True", color=TEXT_MUTED)
            for i in range(mat.shape[0]):
                for j in range(mat.shape[1]):
                    ax.text(
                        j,
                        i,
                        int(mat[i, j]),
                        ha="center",
                        va="center",
                        color=TEXT_PRIMARY,
                        fontsize=7,
                    )
            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

        fig.suptitle("CEFR Confusion Matrices", color=TEXT_PRIMARY, fontweight="bold")
        fig.tight_layout()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches="tight", facecolor=BG_PAGE)
        plt.close(fig)

    def export_all_tables(self, output_dir: str | Path) -> list[str]:
        out = Path(output_dir)
        if not out.is_absolute():
            out = _PROJECT_ROOT / out
        out.mkdir(parents=True, exist_ok=True)

        files: list[str] = []
        retrieval = self.generate_comparison_table()
        classification = self.generate_classification_comparison()
        improvement = self.generate_improvement_summary()

        files.extend(
            dataframe_to_all(
                retrieval,
                base_name="retrieval_comparison",
                output_dir=str(out),
                caption="Retrieval performance comparison across methods.",
                label="tab:retrieval_comparison",
                highlight_best_col="MAP",
            )
        )
        files.extend(
            dataframe_to_all(
                classification,
                base_name="classification_comparison",
                output_dir=str(out),
                caption="CEFR classification performance comparison.",
                label="tab:classification_comparison",
                highlight_best_col="F1 (macro)",
            )
        )

        improv_rows = [
            {"Metric": "Precision@10", "Improvement %": improvement.get("precision_improvement_pct")},
            {"Metric": "Recall@10", "Improvement %": improvement.get("recall_improvement_pct")},
            {"Metric": "MAP", "Improvement %": improvement.get("map_improvement_pct")},
            {"Metric": "F1@10", "Improvement %": improvement.get("f1_improvement_pct")},
            {"Metric": "MRR", "Improvement %": improvement.get("mrr_improvement_pct")},
            {"Metric": "Accuracy", "Improvement %": improvement.get("accuracy_improvement_pct")},
        ]
        improv_df = pd.DataFrame(improv_rows)
        improv_df["Improvement %"] = improv_df["Improvement %"].map(
            lambda v: _MISSING if v is None else (round(v, 2) if isinstance(v, float) else v)
        )
        files.extend(
            dataframe_to_all(
                improv_df,
                base_name="improvement_summary",
                output_dir=str(out),
                caption=(
                    f"Percentage improvement of {improvement.get('best_genai_method')} "
                    "over TF-IDF baseline."
                ),
                label="tab:improvement_summary",
            )
        )
        return files

    def _key_findings(self, improvement: dict[str, Any], sig: dict[str, Any]) -> list[str]:
        findings: list[str] = []
        best = improvement.get("best_genai_method") or "the best GenAI method"
        map_imp = improvement.get("map_improvement_pct")
        f1_imp = improvement.get("f1_improvement_pct")
        p_imp = improvement.get("precision_improvement_pct")

        if map_imp is not None:
            findings.append(
                f"{best} improves MAP by {map_imp:+.1f}% relative to the TF-IDF baseline."
            )
        if p_imp is not None:
            findings.append(
                f"Precision@10 improvement vs TF-IDF: {p_imp:+.1f}%."
            )
        if f1_imp is not None:
            findings.append(f"F1@10 improvement vs TF-IDF: {f1_imp:+.1f}%.")

        if sig.get("t_test_p") is not None:
            sig_txt = "significant" if sig.get("significant_at_05") else "not significant"
            findings.append(
                f"Paired t-test on per-query {sig.get('metric')} "
                f"({sig.get('method_a')} vs {sig.get('method_b')}, n={sig.get('n_paired')}): "
                f"p={sig['t_test_p']:.4g} ({sig_txt} at α=0.05); "
                f"Cohen's d={sig.get('cohens_d')}."
            )
        elif sig.get("note"):
            findings.append(str(sig["note"]))

        for note in self.notes:
            findings.append(note)

        if not findings:
            findings.append(
                "Insufficient completed experiment results to summarise improvements."
            )
        return findings

    def generate_full_report(
        self, output_dir: str | Path = "research/reports/benchmark"
    ) -> str:
        out = Path(output_dir)
        if not out.is_absolute():
            out = _PROJECT_ROOT / out
        out.mkdir(parents=True, exist_ok=True)

        retrieval_df = self.generate_comparison_table()
        class_df = self.generate_classification_comparison()
        improvement = self.generate_improvement_summary()
        sig = self.generate_statistical_significance()
        table_files = self.export_all_tables(out)

        bars_path = out / "retrieval_comparison_bars.png"
        self._plot_retrieval_bars(retrieval_df, bars_path)
        cm_path = out / "confusion_matrices.png"
        self._plot_confusion_side_by_side(cm_path)

        # Dataset summary
        total = self.eda_report.get("total_resources")
        cefr = self.eda_report.get("cefr_distribution") or {}
        sources = self.eda_report.get("top_sources") or {}
        if isinstance(sources, list):
            source_lines = []
            for s in sources[:10]:
                if isinstance(s, dict):
                    name = s.get("source_name") or s.get("name") or s.get("source") or "?"
                    count = s.get("count", s.get("n", ""))
                    source_lines.append(f"- {name}: {count}")
                else:
                    source_lines.append(f"- {s}")
        elif isinstance(sources, dict):
            source_lines = [f"- {k}: {v}" for k, v in list(sources.items())[:10]]
        else:
            source_lines = ["- (source breakdown unavailable)"]

        cefr_lines = (
            [f"- {k}: {v}" for k, v in cefr.items()]
            if isinstance(cefr, dict)
            else ["- (CEFR distribution unavailable)"]
        )

        findings = self._key_findings(improvement, sig)

        def _df_md(df: pd.DataFrame) -> str:
            try:
                return df.to_markdown(index=False)
            except Exception:
                return "```\n" + df.to_string(index=False) + "\n```"

        sig_lines = [
            f"- Metric: `{sig.get('metric')}` ({sig.get('method_a')} vs {sig.get('method_b')})",
            f"- Paired n: {sig.get('n_paired')}",
            f"- Paired t-test p: {sig.get('t_test_p')}",
            f"- Wilcoxon p: {sig.get('wilcoxon_p')}",
            f"- Cohen's d: {sig.get('cohens_d')}",
            f"- Significant at α=0.05: {sig.get('significant_at_05')}",
        ]
        if sig.get("note"):
            sig_lines.append(f"- Note: {sig['note']}")

        improv_rows = [
            ("Precision@10", improvement.get("precision_improvement_pct")),
            ("Recall@10", improvement.get("recall_improvement_pct")),
            ("MAP", improvement.get("map_improvement_pct")),
            ("F1@10", improvement.get("f1_improvement_pct")),
            ("MRR", improvement.get("mrr_improvement_pct")),
        ]
        improv_md = "| Metric | Improvement % |\n|--------|---------------|\n" + "\n".join(
            f"| {name} | {(_MISSING if v is None else f'{v:+.2f}')} |"
            for name, v in improv_rows
        )

        md = f"""# Benchmark Comparison Report

Auto-generated comparison of retrieval and CEFR classification methods for the
EFL IndexDB GenAI feasibility study.

## Dataset Summary

- **Total resources:** {total if total is not None else _MISSING}
- **Queries evaluated (Stage 10):** {(self.eval_report.get('retrieval') or {}).get('queries_evaluated', _MISSING)}
- **Labeled test rows (classification):** {(self.eval_report.get('classification') or {}).get('n_labeled_test', _MISSING)}

### CEFR distribution

{chr(10).join(cefr_lines)}

### Source breakdown

{chr(10).join(source_lines)}

## Retrieval Performance Comparison

{_df_md(retrieval_df)}

Artefacts: `retrieval_comparison.csv` / `.tex` / `.png`

![Retrieval bar chart]({bars_path.name})

### Statistical significance

{chr(10).join(sig_lines)}

## Classification Performance Comparison

{_df_md(class_df)}

Artefacts: `classification_comparison.csv` / `.tex` / `.png`

{"![Confusion matrices](" + cm_path.name + ")" if cm_path.exists() else "_Confusion matrices unavailable (missing Stage 10 matrices)._"}

## Performance Improvement Summary

Best GenAI method vs TF-IDF: **{improvement.get('best_genai_method') or _MISSING}**

{improv_md}

### Key findings

{chr(10).join(f"- {f}" for f in findings)}

## Methodology Notes

- **Embedding model:** sentence-transformers/all-MiniLM-L6-v2 (384-d)
- **Index type:** FAISS IndexFlatIP (inner product on L2-normalised vectors ≈ cosine)
- **Baseline retrieval:** TF-IDF + cosine similarity
- **Classifier:** Logistic Regression (SBERT embeddings vs TF-IDF features)
- **Evaluation protocol:** leave-query-out style test-set retrieval; relevance =
  same `cefr_level` when labeled, else same `source_name`
- **Cut-offs:** P/R/F1 @5 and @10; MAP / MRR @10
- **Random seed:** 42
- **Per-query metrics file:** `{_PER_QUERY_PATH.as_posix()}`

### Data sources

- `{_EVAL_PATH.as_posix()}`
- `{_EXPERIMENT_LOG.as_posix()}`
- `{_EDA_PATH.as_posix()}`

### Exported tables

{chr(10).join(f"- `{Path(p).name}`" for p in table_files)}
"""

        report_path = out / "benchmark_comparison_report.md"
        report_path.write_text(md, encoding="utf-8")
        return str(report_path)


if __name__ == "__main__":
    gen = BenchmarkReportGenerator()
    path = gen.generate_full_report()
    print(f"Report generated: {path}")

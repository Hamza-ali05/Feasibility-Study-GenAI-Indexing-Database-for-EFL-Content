"""Structured experiment tracking for the EFL IndexDB feasibility study.

Compares retrieval / classification configurations (TF-IDF, SBERT,
SBERT+Metadata, SBERT+Metadata+RAG) with persisted results under
``research/experiments/experiment_log.json``.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, Field

from research.utils.latex_tables import dataframe_to_all

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_EXPERIMENTS_DIR = _PROJECT_ROOT / "research" / "experiments"
_DEFAULT_LOG = _EXPERIMENTS_DIR / "experiment_log.json"
_SPLIT_REPORT = _PROJECT_ROOT / "data" / "processed" / "06_split_report.json"

RetrievalMethod = Literal[
    "tfidf",
    "sbert",
    "sbert_metadata",
    "sbert_metadata_rag",
]
ExperimentStatus = Literal["configured", "running", "completed", "failed"]


class ExperimentConfig(BaseModel):
    retrieval_method: RetrievalMethod
    embedding_model: str | None = None
    classifier: str = "logistic_regression"
    faiss_index_type: str | None = None
    metadata_filters_enabled: bool = False
    rag_enabled: bool = False
    top_k: int = 10
    random_seed: int = 42
    custom_params: dict[str, Any] = Field(default_factory=dict)


class DatasetInfo(BaseModel):
    total_resources: int = 0
    train_size: int = 0
    val_size: int = 0
    test_size: int = 0
    dataset_hash: str = ""


class RetrievalResults(BaseModel):
    precision_at_k: float | None = None
    recall_at_k: float | None = None
    map: float | None = None
    f1_at_k: float | None = None
    mrr: float | None = None


class ClassificationResults(BaseModel):
    accuracy: float | None = None
    precision_macro: float | None = None
    recall_macro: float | None = None
    f1_macro: float | None = None


class ExperimentResults(BaseModel):
    retrieval: RetrievalResults = Field(default_factory=RetrievalResults)
    classification: ClassificationResults = Field(
        default_factory=ClassificationResults
    )
    confusion_matrix: list[list[int]] | None = None
    per_class_f1: dict[str, float] | None = None


class Experiment(BaseModel):
    experiment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    config: ExperimentConfig
    dataset_info: DatasetInfo = Field(default_factory=DatasetInfo)
    results: ExperimentResults | None = None
    environment: dict[str, Any] = Field(default_factory=dict)
    started_at: str | None = None
    completed_at: str | None = None
    status: ExperimentStatus = "configured"
    notes: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _capture_dataset_info() -> DatasetInfo:
    """Read Stage 06 split report when present; otherwise return empty info."""
    if not _SPLIT_REPORT.exists():
        return DatasetInfo()
    try:
        raw = json.loads(_SPLIT_REPORT.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return DatasetInfo()

    payload = json.dumps(raw, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return DatasetInfo(
        total_resources=int(raw.get("total") or 0),
        train_size=int(raw.get("train_n") or 0),
        val_size=int(raw.get("val_n") or 0),
        test_size=int(raw.get("test_n") or 0),
        dataset_hash=digest,
    )


def _capture_environment() -> dict[str, Any]:
    """Snapshot from Phase 12 reproducibility module when available."""
    try:
        from research.reproducibility import capture_environment  # type: ignore

        snap = capture_environment()
        return snap if isinstance(snap, dict) else {"snapshot": snap}
    except Exception:
        return {
            "note": (
                "reproducibility module (Phase 12) not available; "
                "environment snapshot deferred"
            ),
            "captured_at": _now_iso(),
        }


def _coerce_results(results: dict[str, Any]) -> ExperimentResults:
    """Accept nested or flat result dicts from pipeline reports."""
    retrieval_raw = results.get("retrieval") or {}
    classification_raw = results.get("classification") or {}

    # Flatten SBERT-style nested reports if a method key is present
    if "sbert" in retrieval_raw and isinstance(retrieval_raw["sbert"], dict):
        method = results.get("method") or "sbert"
        branch = retrieval_raw.get(method) or retrieval_raw.get("sbert") or {}
        retrieval = {
            "precision_at_k": branch.get("precision_at_k", branch.get("precision_at_10")),
            "recall_at_k": branch.get("recall_at_k", branch.get("recall_at_10")),
            "map": branch.get("map"),
            "f1_at_k": branch.get("f1_at_k", branch.get("f1_at_10")),
            "mrr": branch.get("mrr"),
        }
    else:
        retrieval = {
            "precision_at_k": retrieval_raw.get(
                "precision_at_k", retrieval_raw.get("precision_at_10")
            ),
            "recall_at_k": retrieval_raw.get(
                "recall_at_k", retrieval_raw.get("recall_at_10")
            ),
            "map": retrieval_raw.get("map"),
            "f1_at_k": retrieval_raw.get("f1_at_k", retrieval_raw.get("f1_at_10")),
            "mrr": retrieval_raw.get("mrr"),
        }

    if "sbert" in classification_raw and isinstance(
        classification_raw["sbert"], dict
    ):
        method = results.get("method") or "sbert"
        branch = (
            classification_raw.get(method)
            or classification_raw.get("sbert")
            or {}
        )
        classification = branch
    else:
        classification = classification_raw

    return ExperimentResults(
        retrieval=RetrievalResults.model_validate(retrieval),
        classification=ClassificationResults.model_validate(classification),
        confusion_matrix=results.get("confusion_matrix"),
        per_class_f1=results.get("per_class_f1"),
    )


class ExperimentTracker:
    """Persist and compare feasibility-study experiment configurations."""

    def __init__(self, log_path: Path | str | None = None) -> None:
        self.log_path = Path(log_path) if log_path else _DEFAULT_LOG
        self._experiments: dict[str, Experiment] = {}
        self._load()

    def _load(self) -> None:
        self._experiments.clear()
        if not self.log_path.exists():
            return
        raw = json.loads(self.log_path.read_text(encoding="utf-8-sig"))
        items = raw if isinstance(raw, list) else raw.get("experiments", [])
        for item in items:
            exp = Experiment.model_validate(item)
            self._experiments[exp.experiment_id] = exp

    def _save(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "experiments": [
                e.model_dump() for e in self._experiments.values()
            ]
        }
        self.log_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _get_or_raise(self, experiment_id: str) -> Experiment:
        if experiment_id not in self._experiments:
            raise KeyError(f"Experiment not found: {experiment_id}")
        return self._experiments[experiment_id]

    def create_experiment(
        self,
        name: str,
        description: str,
        config: ExperimentConfig | dict[str, Any],
    ) -> Experiment:
        """Register a new experiment; auto-capture dataset_info from split report."""
        cfg = (
            config
            if isinstance(config, ExperimentConfig)
            else ExperimentConfig.model_validate(config)
        )
        exp = Experiment(
            name=name,
            description=description,
            config=cfg,
            dataset_info=_capture_dataset_info(),
            status="configured",
        )
        self._experiments[exp.experiment_id] = exp
        self._save()
        return exp

    def start_experiment(self, experiment_id: str) -> None:
        exp = self._get_or_raise(experiment_id)
        updated = exp.model_copy(
            update={"status": "running", "started_at": _now_iso()}
        )
        self._experiments[experiment_id] = updated
        self._save()

    def record_results(
        self, experiment_id: str, results: dict[str, Any]
    ) -> Experiment:
        exp = self._get_or_raise(experiment_id)
        parsed = _coerce_results(results)
        updated = exp.model_copy(
            update={
                "results": parsed,
                "status": "completed",
                "completed_at": _now_iso(),
                "environment": _capture_environment(),
            }
        )
        self._experiments[experiment_id] = updated
        self._save()
        return updated

    def fail_experiment(self, experiment_id: str, error_message: str) -> None:
        exp = self._get_or_raise(experiment_id)
        note = (exp.notes + "\n" if exp.notes else "") + f"[FAILED] {error_message}"
        updated = exp.model_copy(
            update={
                "status": "failed",
                "completed_at": _now_iso(),
                "notes": note.strip(),
            }
        )
        self._experiments[experiment_id] = updated
        self._save()

    def get_experiment(self, experiment_id: str) -> Experiment:
        return self._get_or_raise(experiment_id)

    def list_experiments(self) -> list[Experiment]:
        """All experiments sorted by started_at descending (unset last)."""
        with_ts = [e for e in self._experiments.values() if e.started_at]
        without_ts = [e for e in self._experiments.values() if not e.started_at]
        with_ts.sort(key=lambda e: e.started_at or "", reverse=True)
        return with_ts + without_ts

    def compare_experiments(self, experiment_ids: list[str]) -> pd.DataFrame:
        """Comparison table with best-per-column markers in a parallel view.

        Numeric columns hold floats; a ``_best`` attribute on the returned
        frame (``df.attrs['best']``) maps column → winning experiment name.
        """
        rows: list[dict[str, Any]] = []
        for eid in experiment_ids:
            exp = self._get_or_raise(eid)
            ret = (exp.results.retrieval if exp.results else None) or RetrievalResults()
            clf = (
                exp.results.classification if exp.results else None
            ) or ClassificationResults()
            rows.append(
                {
                    "Experiment": exp.name,
                    "Method": exp.config.retrieval_method,
                    "P@10": ret.precision_at_k,
                    "R@10": ret.recall_at_k,
                    "MAP": ret.map,
                    "F1": ret.f1_at_k,
                    "MRR": ret.mrr,
                    "Accuracy": clf.accuracy,
                }
            )

        df = pd.DataFrame(rows)
        metric_cols = ["P@10", "R@10", "MAP", "F1", "MRR", "Accuracy"]
        best: dict[str, str] = {}
        for col in metric_cols:
            series = pd.to_numeric(df[col], errors="coerce")
            if series.notna().any():
                idx = int(series.idxmax())
                best[col] = str(df.loc[idx, "Experiment"])
                # Mark best cell for display helpers (suffix ★ in a display copy)
        df.attrs["best"] = best

        # Display-oriented copy with ★ on best values (keeps originals numeric via attrs)
        display = df.copy()
        for col, winner in best.items():
            mask = display["Experiment"] == winner
            display.loc[mask, col] = display.loc[mask, col].apply(
                lambda v: v  # keep numeric; export layer bolds via highlight
            )
        display.attrs["best"] = best
        return display

    def export_comparison_table(
        self, experiment_ids: list[str], output_dir: str | Path
    ) -> list[str]:
        """Export comparison as CSV / LaTeX / PNG via latex_tables helpers."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        df = self.compare_experiments(experiment_ids)
        best = df.attrs.get("best") or {}

        # LaTeX with per-column best bolding
        tex_path = output_dir / "experiment_comparison.tex"
        self._write_comparison_booktabs(df, best, tex_path)

        paths = dataframe_to_all(
            df,
            base_name="experiment_comparison",
            output_dir=str(output_dir),
            caption="Experiment comparison (feasibility study configurations)",
            label="tab:experiment_comparison",
            highlight_best_col="MAP" if "MAP" in df.columns else None,
            float_format="%.4f",
        )
        # Overwrite tex with multi-column bold version
        self._write_comparison_booktabs(df, best, tex_path)
        return paths

    @staticmethod
    def _write_comparison_booktabs(
        df: pd.DataFrame, best: dict[str, str], path: Path
    ) -> None:
        headers = [str(c) for c in df.columns]
        lines = [
            r"\begin{table}[htbp]",
            r"\centering",
            r"\caption{Experiment comparison (feasibility study configurations)}",
            r"\label{tab:experiment_comparison}",
            r"\begin{tabular}{" + ("l" * 2 + "r" * (len(headers) - 2)) + "}",
            r"\toprule",
            " & ".join(headers) + r" \\",
            r"\midrule",
        ]
        metric_cols = {"P@10", "R@10", "MAP", "F1", "MRR", "Accuracy"}
        for _, row in df.iterrows():
            cells: list[str] = []
            for col in headers:
                val = row[col]
                if col in metric_cols:
                    if val is None or (isinstance(val, float) and pd.isna(val)):
                        text = "—"
                    else:
                        text = f"{float(val):.4f}"
                    if best.get(col) == row["Experiment"] and text != "—":
                        text = rf"\textbf{{{text}}}"
                else:
                    text = str(val).replace("_", r"\_")
                cells.append(text)
            lines.append(" & ".join(cells) + r" \\")
        lines.extend(
            [
                r"\bottomrule",
                r"\end{tabular}",
                r"\end{table}",
                "",
            ]
        )
        path.write_text("\n".join(lines), encoding="utf-8")

    def export_experiment_card(
        self, experiment_id: str, output_dir: str | Path
    ) -> str:
        """One-page markdown summary of a single experiment."""
        exp = self._get_or_raise(experiment_id)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        safe = "".join(
            c if c.isalnum() or c in "-_" else "_" for c in exp.name
        )[:60]
        path = output_dir / f"experiment_card_{safe or exp.experiment_id[:8]}.md"

        cfg = exp.config
        ds = exp.dataset_info
        lines = [
            f"# Experiment Card: {exp.name}",
            "",
            f"**ID:** `{exp.experiment_id}`  ",
            f"**Status:** {exp.status}  ",
            f"**Started:** {exp.started_at or '—'}  ",
            f"**Completed:** {exp.completed_at or '—'}  ",
            "",
            exp.description or "_No description._",
            "",
            "## Configuration",
            "",
            "| Parameter | Value |",
            "| --- | --- |",
            f"| Retrieval method | `{cfg.retrieval_method}` |",
            f"| Embedding model | {cfg.embedding_model or '—'} |",
            f"| Classifier | {cfg.classifier} |",
            f"| FAISS index | {cfg.faiss_index_type or '—'} |",
            f"| Metadata filters | {cfg.metadata_filters_enabled} |",
            f"| RAG enabled | {cfg.rag_enabled} |",
            f"| top_k | {cfg.top_k} |",
            f"| random_seed | {cfg.random_seed} |",
            "",
            "## Dataset",
            "",
            "| Split | Size |",
            "| --- | ---: |",
            f"| Total | {ds.total_resources} |",
            f"| Train | {ds.train_size} |",
            f"| Val | {ds.val_size} |",
            f"| Test | {ds.test_size} |",
            f"| Dataset hash | `{ds.dataset_hash or '—'}` |",
            "",
            "## Results",
            "",
        ]

        if exp.results is None:
            lines.append("_No results recorded yet._")
            lines.append("")
        else:
            ret = exp.results.retrieval
            clf = exp.results.classification
            lines.extend(
                [
                    "### Retrieval",
                    "",
                    "| Metric | Value |",
                    "| --- | ---: |",
                    f"| P@k | {ret.precision_at_k if ret.precision_at_k is not None else '—'} |",
                    f"| R@k | {ret.recall_at_k if ret.recall_at_k is not None else '—'} |",
                    f"| MAP | {ret.map if ret.map is not None else '—'} |",
                    f"| F1@k | {ret.f1_at_k if ret.f1_at_k is not None else '—'} |",
                    f"| MRR | {ret.mrr if ret.mrr is not None else '—'} |",
                    "",
                    "### Classification",
                    "",
                    "| Metric | Value |",
                    "| --- | ---: |",
                    f"| Accuracy | {clf.accuracy if clf.accuracy is not None else '—'} |",
                    f"| Precision (macro) | {clf.precision_macro if clf.precision_macro is not None else '—'} |",
                    f"| Recall (macro) | {clf.recall_macro if clf.recall_macro is not None else '—'} |",
                    f"| F1 (macro) | {clf.f1_macro if clf.f1_macro is not None else '—'} |",
                    "",
                ]
            )
            if exp.results.confusion_matrix:
                lines.append("### Confusion matrix")
                lines.append("")
                lines.append("```")
                for row in exp.results.confusion_matrix:
                    lines.append("  ".join(f"{v:4d}" for v in row))
                lines.append("```")
                lines.append("")
            if exp.results.per_class_f1:
                lines.append("### Per-class F1")
                lines.append("")
                lines.append("| Class | F1 |")
                lines.append("| --- | ---: |")
                for cls, score in sorted(exp.results.per_class_f1.items()):
                    lines.append(f"| {cls} | {score:.4f} |")
                lines.append("")

        lines.extend(["## Environment", ""])
        if exp.environment:
            lines.append("```json")
            lines.append(json.dumps(exp.environment, indent=2, ensure_ascii=False))
            lines.append("```")
            lines.append("")
        else:
            lines.append("_No environment snapshot._")
            lines.append("")

        lines.extend(["## Notes", "", exp.notes or "_None._", ""])
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path.as_posix())

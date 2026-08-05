"""Auto-generate draft dissertation chapter sections from pipeline artefacts.

Pulls real numbers from Stage reports, experiments, practitioner evaluation,
benchmark comparison, and reproducibility snapshots. Never fabricates metrics —
missing sources become explicit ``[PLACEHOLDER: ...]`` / ``[DATA NOT AVAILABLE]``
markers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DATA_PROCESSED = _PROJECT_ROOT / "data" / "processed"
_DEFAULT_OUT = _PROJECT_ROOT / "research" / "reports" / "draft_chapters"

_STAGE_FILES: dict[str, Path] = {
    "01": _DATA_PROCESSED / "01_discover_manifest.json",
    "02": _DATA_PROCESSED / "02_load_report.json",
    "03": _DATA_PROCESSED / "03_integration_report.json",
    "04": _DATA_PROCESSED / "04_eda_report.json",
    "05": _DATA_PROCESSED / "05_clean_report.json",
    "06": _DATA_PROCESSED / "06_split_report.json",
    "07": _DATA_PROCESSED / "07_preprocess_report.json",
    "08": _DATA_PROCESSED / "08_balance_report.json",
    "09": _DATA_PROCESSED / "09_train_report.json",
    "10": _DATA_PROCESSED / "10_evaluation_report.json",
    "11": _DATA_PROCESSED / "11_explain_global_report.json",
    "12": _DATA_PROCESSED / "12_explain_local_report.json",
    "12_meta": _DATA_PROCESSED / "12_explain_local_meta.json",
    "13": _DATA_PROCESSED / "13_explain_quality_report.json",
    "14": _DATA_PROCESSED / "14_last_predict.json",
}

_PIPELINE_STATE = _DATA_PROCESSED / "pipeline_state.json"
_PER_QUERY = _DATA_PROCESSED / "10_per_query_metrics.json"
_EXPERIMENT_LOG = _PROJECT_ROOT / "research" / "experiments" / "experiment_log.json"
_BENCHMARK_MD = (
    _PROJECT_ROOT / "research" / "reports" / "benchmark" / "benchmark_comparison_report.md"
)
_BENCHMARK_CSV = (
    _PROJECT_ROOT / "research" / "reports" / "benchmark" / "retrieval_comparison.csv"
)
_CLASS_CSV = (
    _PROJECT_ROOT / "research" / "reports" / "benchmark" / "classification_comparison.csv"
)
_IMPROV_CSV = (
    _PROJECT_ROOT / "research" / "reports" / "benchmark" / "improvement_summary.csv"
)
_SNAPSHOT = _PROJECT_ROOT / "research" / "reproducibility" / "latest_snapshot.json"
_SECURITY_REPORT = _PROJECT_ROOT / "research" / "reports" / "security" / "security_evaluation.md"
_DUPLICATES = _DATA_PROCESSED / "duplicate_candidates.json"
_ARCHITECTURE_FIGS = _PROJECT_ROOT / "research" / "reports" / "figures"


def _load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None


def _placeholder(stage_or_msg: str) -> str:
    if stage_or_msg.startswith("run ") or " " in stage_or_msg.lower():
        return f"[PLACEHOLDER: {stage_or_msg}]"
    return f"[DATA NOT AVAILABLE — run stage {stage_or_msg}]"


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _md_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "_No rows available._"
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


def _df_to_md(df: pd.DataFrame | None) -> str:
    if df is None or df.empty:
        return "_No data._"
    try:
        return df.to_markdown(index=False)
    except Exception:
        return "```\n" + df.to_string(index=False) + "\n```"


def _dist_table(mapping: Any, name_header: str = "Category") -> str:
    if not isinstance(mapping, dict) or not mapping:
        return _placeholder("run stage 04 (EDA)")
    rows = [[str(k), v] for k, v in mapping.items()]
    return _md_table([name_header, "Count"], rows)


def _sources_table(top_sources: Any) -> str:
    if isinstance(top_sources, list) and top_sources:
        rows = []
        for s in top_sources[:15]:
            if isinstance(s, dict):
                name = s.get("source_name") or s.get("name") or s.get("source") or "?"
                count = s.get("count", s.get("n", "—"))
                rows.append([name, count])
            else:
                rows.append([str(s), "—"])
        return _md_table(["Source", "Count"], rows)
    if isinstance(top_sources, dict) and top_sources:
        return _md_table(
            ["Source", "Count"],
            [[k, v] for k, v in list(top_sources.items())[:15]],
        )
    return _placeholder("run stage 04 (EDA)")


class ResearchReportGenerator:
    """Draft dissertation chapters from real pipeline / evaluation artefacts."""

    def __init__(self) -> None:
        self.stages: dict[str, Any] = {}
        for key, path in _STAGE_FILES.items():
            self.stages[key] = _load_json(path)

        self.pipeline_state = _load_json(_PIPELINE_STATE) or {}
        self.per_query = _load_json(_PER_QUERY)
        self.experiment_log = _load_json(_EXPERIMENT_LOG) or {"experiments": []}
        self.snapshot = _load_json(_SNAPSHOT)
        self.duplicates = _load_json(_DUPLICATES)
        self.security_report = (
            _SECURITY_REPORT.read_text(encoding="utf-8")
            if _SECURITY_REPORT.exists()
            else None
        )
        self.benchmark_md = (
            _BENCHMARK_MD.read_text(encoding="utf-8") if _BENCHMARK_MD.exists() else None
        )

        self.retrieval_comparison = self._read_csv(_BENCHMARK_CSV)
        self.classification_comparison = self._read_csv(_CLASS_CSV)
        self.improvement_summary = self._read_csv(_IMPROV_CSV)

        self.practitioner = self._load_practitioner()
        self.significance = self._load_significance()

    @staticmethod
    def _read_csv(path: Path) -> pd.DataFrame | None:
        if not path.exists():
            return None
        try:
            return pd.read_csv(path)
        except Exception:
            return None

    def _load_practitioner(self) -> dict[str, Any] | None:
        try:
            from research.practitioner_eval.feedback_analyzer import FeedbackAnalyzer

            return FeedbackAnalyzer().full_analysis()
        except Exception as exc:  # noqa: BLE001
            return {"_error": str(exc)}

    def _load_significance(self) -> dict[str, Any] | None:
        try:
            from research.benchmark_report import BenchmarkReportGenerator

            return BenchmarkReportGenerator().generate_statistical_significance()
        except Exception:
            return None

    # ── helpers ─────────────────────────────────────────────────────────

    def _stage_statuses(self) -> dict[str, dict[str, Any]]:
        doc = self.pipeline_state
        if isinstance(doc.get("stages"), dict):
            return doc["stages"]
        # Legacy flat layout
        if all(isinstance(v, dict) and "status" in v for v in doc.values() if isinstance(v, dict)):
            return {k: v for k, v in doc.items() if isinstance(v, dict) and "status" in v}
        return {}

    def _eda(self) -> dict[str, Any]:
        return self.stages.get("04") or {}

    def _eval(self) -> dict[str, Any]:
        return self.stages.get("10") or {}

    def _explain_global(self) -> dict[str, Any]:
        return self.stages.get("11") or {}

    def _explain_local_list(self) -> list[dict[str, Any]]:
        raw = self.stages.get("12")
        if isinstance(raw, list):
            return [x for x in raw if isinstance(x, dict)]
        if isinstance(raw, dict):
            expl = raw.get("explanations")
            if isinstance(expl, list):
                return [x for x in expl if isinstance(x, dict)]
        meta = self.stages.get("12_meta")
        if isinstance(meta, dict) and isinstance(meta.get("explanations"), list):
            return [x for x in meta["explanations"] if isinstance(x, dict)]
        return []

    def _explain_quality(self) -> dict[str, Any]:
        return self.stages.get("13") or {}

    def _write(self, path: Path, content: str) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        return str(path)

    # ── Chapter 4: Results ──────────────────────────────────────────────

    def generate_results_chapter(
        self, output_path: str | Path | None = None
    ) -> str:
        out = Path(output_path) if output_path else _DEFAULT_OUT / "chapter_4_results.md"
        eda = self._eda()
        ev = self._eval()
        statuses = self._stage_statuses()
        quality = self._explain_quality()
        global_rep = self._explain_global()
        local = self._explain_local_list()

        # 4.1 Dataset
        total = eda.get("total_resources")
        sec_41 = [
            "## 4.1 Dataset Overview",
            "",
            f"- **Number of EFL resources collected:** {_fmt(total, 0) if total is not None else _placeholder('04')}",
            "",
            "### Source breakdown",
            "",
            _sources_table(eda.get("top_sources")),
            "",
            "### CEFR distribution",
            "",
            _dist_table(eda.get("cefr_distribution"), "CEFR Level"),
            "",
            f"*Figure reference:* CEFR distribution chart from Stage 04 EDA "
            f"(`{(eda.get('plots') or {}).get('cefr', 'data/processed/plots/…') if isinstance(eda.get('plots'), dict) else 'data/processed/plots/…'}`).",
            "",
            "### Skill type distribution",
            "",
            _dist_table(eda.get("skill_distribution"), "Skill"),
            "",
            "### Topic domain distribution",
            "",
            _dist_table(eda.get("topic_distribution"), "Topic"),
        ]

        # 4.2 Pipeline execution
        duration_rows = []
        total_runtime = 0.0
        has_duration = False
        rerun_notes = []
        for name, entry in statuses.items():
            dur = entry.get("duration_seconds")
            status = entry.get("status", "—")
            err = entry.get("error")
            if dur is not None:
                has_duration = True
                total_runtime += float(dur)
            duration_rows.append(
                [name, status, _fmt(dur, 2) if dur is not None else "—", err or ""]
            )
            if status == "FAILED" and err:
                rerun_notes.append(f"- **{name}** failed: {err}")

        snap_runtime = (self.snapshot or {}).get("runtime") or {}
        if snap_runtime.get("pipeline_total_seconds") is not None:
            total_runtime = float(snap_runtime["pipeline_total_seconds"])
            has_duration = True

        sec_42 = [
            "## 4.2 Pipeline Execution Summary",
            "",
            f"- **Total runtime:** "
            + (
                f"{total_runtime:.1f} seconds"
                if has_duration
                else _placeholder("re-run pipeline stages to record timings")
            ),
            "",
            "### Per-stage durations",
            "",
            _md_table(
                ["Stage", "Status", "Duration (s)", "Error"],
                duration_rows,
            )
            if duration_rows
            else _placeholder("pipeline_state.json missing"),
            "",
            "### Re-runs / failures",
            "",
            "\n".join(rerun_notes) if rerun_notes else "- No failed stages recorded in the current pipeline state.",
        ]

        # 4.3 Retrieval
        retrieval = ev.get("retrieval") or {}
        sbert_r = retrieval.get("sbert") or {}
        tfidf_r = retrieval.get("tfidf") or {}
        delta = retrieval.get("delta") or {}
        sig = self.significance or {}

        if self.retrieval_comparison is not None:
            ret_table = _df_to_md(self.retrieval_comparison)
        elif sbert_r or tfidf_r:
            ret_table = _md_table(
                ["Method", "P@10", "R@10", "MAP", "F1@10", "MRR"],
                [
                    [
                        "TF-IDF",
                        _fmt(tfidf_r.get("precision_at_10")),
                        _fmt(tfidf_r.get("recall_at_10")),
                        _fmt(tfidf_r.get("map")),
                        _fmt(tfidf_r.get("f1_at_10")),
                        _fmt(tfidf_r.get("mrr")),
                    ],
                    [
                        "SBERT",
                        _fmt(sbert_r.get("precision_at_10")),
                        _fmt(sbert_r.get("recall_at_10")),
                        _fmt(sbert_r.get("map")),
                        _fmt(sbert_r.get("f1_at_10")),
                        _fmt(sbert_r.get("mrr")),
                    ],
                ],
            )
        else:
            ret_table = _placeholder("10")

        delta_bits = []
        for key, label in (
            ("precision_at_10", "Precision@10"),
            ("recall_at_10", "Recall@10"),
            ("map", "MAP"),
            ("f1_at_10", "F1@10"),
        ):
            if key in delta:
                delta_bits.append(f"- **Δ {label} (SBERT − TF-IDF):** {_fmt(delta[key])}")
        if not delta_bits:
            delta_bits.append(_placeholder("10 (delta metrics)"))

        if sig.get("t_test_p") is not None:
            sig_block = (
                f"- Paired t-test p = {_fmt(sig.get('t_test_p'))} "
                f"(n={sig.get('n_paired')}; significant@0.05={sig.get('significant_at_05')})\n"
                f"- Wilcoxon p = {_fmt(sig.get('wilcoxon_p'))}\n"
                f"- Cohen's d = {_fmt(sig.get('cohens_d'))}"
            )
        else:
            sig_block = sig.get("note") or _placeholder(
                "run stage 10 to produce 10_per_query_metrics.json"
            )

        sec_43 = [
            "## 4.3 Retrieval Performance",
            "",
            "### SBERT vs TF-IDF comparison",
            "",
            ret_table,
            "",
            "### Metric deltas",
            "",
            "\n".join(delta_bits),
            "",
            "### Statistical significance",
            "",
            sig_block,
            "",
            "*Figure X: Retrieval metrics comparison* — see "
            "`research/reports/benchmark/retrieval_comparison_bars.png` "
            "(regenerate via `BenchmarkReportGenerator.generate_full_report()`).",
        ]

        # 4.4 Classification
        clf = ev.get("classification") or {}
        sbert_c = clf.get("sbert") or {}
        tfidf_c = clf.get("tfidf") or {}
        labels = ev.get("confusion_matrix_labels") or []
        cm_s = ev.get("confusion_matrix_sbert")
        cm_t = ev.get("confusion_matrix_tfidf")

        per_class = quality.get("per_cefr_f1") or {}
        if per_class:
            per_class_md = _md_table(
                ["CEFR", "F1"],
                [[k, _fmt(v)] for k, v in per_class.items()],
            )
        else:
            per_class_md = _placeholder("13 (per-class F1) or re-derive from confusion matrices")

        bias_flags = quality.get("bias_flags") or []
        bias_md = (
            "\n".join(f"- {b}" for b in bias_flags)
            if bias_flags
            else "- No bias flags recorded in the explainability quality report."
        )

        if self.classification_comparison is not None:
            clf_table = _df_to_md(self.classification_comparison)
        elif sbert_c or tfidf_c:
            clf_table = _md_table(
                ["Method", "Accuracy", "Precision (macro)", "Recall (macro)", "F1 (macro)"],
                [
                    [
                        "TF-IDF",
                        _fmt(tfidf_c.get("accuracy")),
                        _fmt(tfidf_c.get("precision_macro")),
                        _fmt(tfidf_c.get("recall_macro")),
                        _fmt(tfidf_c.get("f1_macro")),
                    ],
                    [
                        "SBERT",
                        _fmt(sbert_c.get("accuracy")),
                        _fmt(sbert_c.get("precision_macro")),
                        _fmt(sbert_c.get("recall_macro")),
                        _fmt(sbert_c.get("f1_macro")),
                    ],
                ],
            )
        else:
            clf_table = _placeholder("10")

        cm_note = (
            f"Confusion matrices are available for labels {labels}. "
            "See `research/reports/benchmark/confusion_matrices.png` and Appendix."
            if cm_s and cm_t
            else _placeholder("10 (confusion matrices)")
        )

        sec_44 = [
            "## 4.4 Classification Performance",
            "",
            clf_table,
            "",
            "### Per-class F1 scores",
            "",
            per_class_md,
            "",
            "### Confusion matrix analysis",
            "",
            cm_note,
            "",
            "### Bias flags (explainability quality)",
            "",
            bias_md,
        ]

        # 4.5 Explainability
        shap = global_rep.get("top_20_shap_features") or []
        if shap:
            shap_rows = []
            for item in shap[:20]:
                if isinstance(item, dict):
                    shap_rows.append(
                        [
                            item.get("feature") or item.get("name") or item.get("dim") or "?",
                            _fmt(item.get("importance") or item.get("mean_abs_shap") or item.get("value")),
                        ]
                    )
                else:
                    shap_rows.append([str(item), "—"])
            shap_md = _md_table(["Feature", "Importance"], shap_rows)
        else:
            shap_md = _placeholder("11 (SHAP global features empty — re-run Explain Global)")

        lime_blocks = []
        for i, item in enumerate(local[:3], start=1):
            rid = item.get("resource_id", "?")
            pred = item.get("predicted_cefr", item.get("prediction", "—"))
            true = item.get("true_cefr", item.get("label", "—"))
            human = item.get("human_readable") or item.get("summary") or ""
            feats = item.get("top_features") or item.get("features") or []
            feat_txt = ", ".join(
                (
                    f"{f.get('feature', f.get('token', '?'))} ({_fmt(f.get('weight', f.get('score')))})"
                    if isinstance(f, dict)
                    else str(f)
                )
                for f in feats[:5]
            )
            lime_blocks.append(
                f"**Example {i}** (`{rid}`): predicted={pred}, true={true}. "
                f"Top features: {feat_txt or '—'}. {human}"
            )
        if not lime_blocks:
            lime_blocks.append(_placeholder("12 (LIME local explanations)"))

        sec_45 = [
            "## 4.5 Explainability Analysis",
            "",
            "### SHAP global feature importance summary",
            "",
            shap_md,
            "",
            f"- Samples explained: {_fmt(global_rep.get('n_samples_explained'), 0) if global_rep else _placeholder('11')}",
            f"- Embedding dim: {_fmt(global_rep.get('embedding_dim'), 0) if global_rep else _placeholder('11')}",
            "",
            "### LIME local explanation examples",
            "",
            "\n\n".join(lime_blocks),
            "",
            "### Faithfulness and stability",
            "",
            f"- **Faithfulness score:** {_fmt(quality.get('faithfulness_score')) if quality else _placeholder('13')}",
            f"- **Stability score:** {_fmt(quality.get('stability_score')) if quality else _placeholder('13')}",
            f"- **Bias threshold:** {_fmt(quality.get('bias_threshold')) if quality else _placeholder('13')}",
            "",
            "### Bias audit findings",
            "",
            bias_md,
        ]

        # 4.6 Live features
        predict = self.stages.get("14") or {}
        dup_stats = ""
        if isinstance(self.duplicates, dict):
            n = self.duplicates.get("n_candidates") or len(
                self.duplicates.get("candidates") or self.duplicates.get("pairs") or []
            )
            dup_stats = f"- Duplicate candidates recorded: {n}"
        elif isinstance(self.duplicates, list):
            dup_stats = f"- Duplicate candidates recorded: {len(self.duplicates)}"
        else:
            dup_stats = f"- Duplicate detection: {_placeholder('run duplicate detection / live features')}"

        prac = self.practitioner or {}
        sus = prac.get("sus") if isinstance(prac, dict) else None
        rec_line = (
            f"- Practitioner SUS mean (proxy for perceived recommendation/tool usability): "
            f"{_fmt(sus.get('mean_sus'), 2)} (n={sus.get('n_respondents')})"
            if isinstance(sus, dict) and sus.get("mean_sus") is not None
            else f"- Recommendation relevance (practitioner): {_placeholder('complete practitioner SUS / interviews')}"
        )

        sec_46 = [
            "## 4.6 Live Feature Evaluation",
            "",
            "### RAG answer quality",
            "",
            (
                f"- Last Predict artefact present (`14_last_predict.json`): "
                f"query={_fmt(predict.get('query') or predict.get('q'))}; "
                f"top_k={_fmt(predict.get('top_k') or predict.get('k'), 0)}."
                if predict
                else f"- {_placeholder('14')}"
            ),
            "- Qualitative RAG answer grading: "
            + (
                "see practitioner interview themes / experiment notes."
                if isinstance(prac, dict) and not prac.get("_error")
                else _placeholder("run RAG experiments + practitioner interviews")
            ),
            "",
            "### Recommendation relevance",
            "",
            rec_line,
            "",
            "### Resource Analyzer",
            "",
            "- Classification accuracy on new uploads: "
            + (
                f"Stage 10 SBERT accuracy on held-out test = {_fmt(sbert_c.get('accuracy'))} "
                "(proxy; live Analyzer uses the same CEFR model)."
                if sbert_c.get("accuracy") is not None
                else _placeholder("10 / live Analyzer evaluation log")
            ),
            "",
            "### Duplicate detection",
            "",
            dup_stats,
        ]

        body = "\n".join(
            [
                "# Chapter 4: Results",
                "",
                "*Auto-generated draft. All figures and tables cite pipeline artefacts; "
                "replace placeholders after re-running missing stages.*",
                "",
                *sec_41,
                "",
                *sec_42,
                "",
                *sec_43,
                "",
                *sec_44,
                "",
                *sec_45,
                "",
                *sec_46,
                "",
            ]
        )
        return self._write(out, body)

    # ── Chapter 5: Evaluation ───────────────────────────────────────────

    def generate_evaluation_chapter(
        self, output_path: str | Path | None = None
    ) -> str:
        out = (
            Path(output_path)
            if output_path
            else _DEFAULT_OUT / "chapter_5_evaluation.md"
        )
        statuses = self._stage_statuses()
        all_complete = bool(statuses) and all(
            (statuses.get(s) or {}).get("status") == "COMPLETE"
            for s in statuses
        )
        # Prefer ordered check for the 14 known stage names when available
        try:
            from backend.utils.pipeline_state import STAGES_IN_ORDER

            order = list(STAGES_IN_ORDER)
            all_complete = all(
                (statuses.get(s) or {}).get("status") == "COMPLETE" for s in order
            )
            incomplete = [
                s for s in order if (statuses.get(s) or {}).get("status") != "COMPLETE"
            ]
        except Exception:
            incomplete = [
                s for s, e in statuses.items() if e.get("status") != "COMPLETE"
            ]

        live_checks = {
            "Search API": self._eval().get("retrieval") is not None,
            "CEFR classifier artefacts": bool(
                (_DATA_PROCESSED / "models" / "sbert_lr_classifier.joblib").exists()
            ),
            "FAISS index": (_PROJECT_ROOT / "data" / "embeddings" / "faiss_index.bin").exists(),
            "Predict artefact": self.stages.get("14") is not None,
            "RAG (Anthropic)": bool(
                any(
                    (e.get("config") or {}).get("rag_enabled")
                    and e.get("status") == "completed"
                    for e in (self.experiment_log.get("experiments") or [])
                )
            ),
        }
        failed_live = [k for k, ok in live_checks.items() if not ok]

        ev = self._eval()
        sbert_r = (ev.get("retrieval") or {}).get("sbert") or {}
        map_v = sbert_r.get("map")
        threshold_note = (
            f"SBERT MAP={_fmt(map_v)}. "
            + (
                "This exceeds a conventional 0.5 MAP feasibility threshold used in the study protocol."
                if map_v is not None and float(map_v) >= 0.5
                else "Compare against the feasibility threshold defined in the proposal/methodology."
            )
            if map_v is not None
            else _placeholder("10")
        )

        # Practitioner
        prac = self.practitioner if isinstance(self.practitioner, dict) else {}
        recruitment = prac.get("recruitment") or {}
        sus = prac.get("sus") or {}
        demo = prac.get("demographics") or {}
        thematic = prac.get("thematic_analysis") or {}

        if prac.get("_error") and not recruitment and not sus:
            err = prac.get("_error")
            prac_block = [
                f"- {_placeholder(f'practitioner evaluation module ({err})')}",
            ]
        else:
            demo_rows = []
            contexts = demo.get("teaching_contexts") or {}
            if isinstance(contexts, dict):
                for k, v in contexts.items():
                    demo_rows.append([k, v])
            demo_table = (
                _md_table(["Teaching context", "n"], demo_rows)
                if demo_rows
                else _placeholder("collect demographics questionnaire responses")
            )
            themes = thematic.get("themes") or []
            if isinstance(themes, list) and themes:
                theme_lines = []
                for t in themes[:12]:
                    if isinstance(t, dict):
                        theme_lines.append(
                            f"- **{t.get('theme', t.get('name', '?'))}** "
                            f"(freq={t.get('frequency', t.get('count', '—'))}): "
                            f"{t.get('description', '')}"
                        )
                    else:
                        theme_lines.append(f"- {t}")
                theme_md = "\n".join(theme_lines)
            else:
                theme_md = _placeholder("code interviews / generate thematic map")

            prac_block = [
                "### Participant demographics",
                "",
                demo_table,
                "",
                f"- Mean years experience: {_fmt(demo.get('mean_years_experience') or recruitment.get('mean_experience_years'), 1)}",
                f"- Recruited / interviewed / coded: "
                f"{recruitment.get('total_recruited', '—')} / "
                f"{recruitment.get('total_interviewed', '—')} / "
                f"{recruitment.get('total_coded', '—')}",
                "",
                "### SUS score summary",
                "",
                f"- Mean SUS: {_fmt(sus.get('mean_sus'), 2)}",
                f"- SD: {_fmt(sus.get('std_sus'), 2)}",
                f"- Range: {_fmt(sus.get('min_sus'), 2)} – {_fmt(sus.get('max_sus'), 2)}",
                f"- n respondents: {_fmt(sus.get('n_respondents'), 0)}",
                f"- Adjective rating: {_fmt(sus.get('adjective_rating'))}",
                "",
                "### Thematic analysis findings",
                "",
                theme_md,
                "",
                "### Usability assessment summary",
                "",
                (
                    f"Mean SUS of {_fmt(sus.get('mean_sus'), 2)} indicates "
                    f"{_fmt(sus.get('adjective_rating'))} usability on the Bangor scale."
                    if sus.get("mean_sus") is not None
                    else _placeholder("SUS responses")
                ),
            ]

        # Improvements
        improv_md = (
            _df_to_md(self.improvement_summary)
            if self.improvement_summary is not None
            else _placeholder("run BenchmarkReportGenerator.generate_full_report()")
        )

        quality = self._explain_quality()
        bias = quality.get("bias_flags") or []

        security_block = (
            self.security_report
            if self.security_report
            else _placeholder("Phase 16 security evaluation (not yet available)")
        )

        body = "\n".join(
            [
                "# Chapter 5: Evaluation and Discussion",
                "",
                "*Auto-generated draft from evaluation artefacts and practitioner module.*",
                "",
                "## 5.1 Technical Feasibility Assessment",
                "",
                f"- **System completed all 14 stages:** {'YES' if all_complete else 'NO'}",
                (
                    f"  - Incomplete / non-COMPLETE: {', '.join(incomplete)}"
                    if incomplete
                    else "  - All recorded stages are COMPLETE."
                ),
                f"- **All live features operational:** {'YES' if not failed_live else 'NO'}",
                (
                    "  - Gaps: " + ", ".join(failed_live)
                    if failed_live
                    else "  - Search artefacts, classifier, FAISS, and Predict present."
                ),
                f"- **Retrieval performance meets threshold:** {threshold_note}",
                "",
                "## 5.2 Practitioner Evaluation",
                "",
                *prac_block,
                "",
                "## 5.3 Comparison with Existing Approaches",
                "",
                "### Performance improvement over TF-IDF baseline",
                "",
                improv_md,
                "",
                "### Positioning against the literature",
                "",
                "- Dense retrieval with SBERT is expected to outperform sparse TF-IDF on semantic EFL queries; "
                "confirm against the literature review gaps (domain-specific CEFR resources, practitioner UX).",
                "- Metadata-filtered retrieval and RAG remain partially evaluated — "
                + (
                    "see experiment log for completed variants."
                    if self.experiment_log.get("experiments")
                    else _placeholder("run metadata / RAG experiments")
                ),
                "",
                "## 5.4 Limitations",
                "",
                "- **Dataset size / coverage:** EDA reports "
                f"{_fmt(self._eda().get('total_resources'), 0) if self._eda() else '—'} resources; "
                "proposal noted a smaller curated subset for early feasibility — discuss generalisability carefully.",
                "- **Single embedding model tested:** all-MiniLM-L6-v2 (384-d); larger multilingual models not compared.",
                "- **Practitioner sample size:** target n=6–8; actual interviewed = "
                f"{_fmt((prac.get('recruitment') or {}).get('total_interviewed'), 0)}.",
                "- **Prototype scope vs production:** offline pipeline + FastAPI prototype; "
                "not a hardened multi-tenant production deployment.",
                "",
                "## 5.5 Ethical and Security Considerations",
                "",
                "### GDPR compliance summary",
                "",
                "- Practitioner data uses pseudonyms; withdrawal purges transcripts/codes "
                "(see `research/practitioner_eval`).",
                "- Admin JWT protects mutation endpoints; search is read-oriented.",
                "- See `docs/architecture.md` §11 for the controls table.",
                "",
                "### Algorithmic bias findings",
                "",
                (
                    "\n".join(f"- {b}" for b in bias)
                    if bias
                    else f"- {_placeholder('13 (bias flags)')}"
                ),
                "",
                "### Security evaluation results",
                "",
                security_block
                if isinstance(security_block, str) and security_block.startswith("#")
                else f"- {security_block}",
                "",
            ]
        )
        return self._write(out, body)

    # ── Chapter 3: Methodology ──────────────────────────────────────────

    def generate_methodology_section(
        self, output_path: str | Path | None = None
    ) -> str:
        out = (
            Path(output_path)
            if output_path
            else _DEFAULT_OUT / "chapter_3_methodology.md"
        )
        snap = self.snapshot or {}
        platform = snap.get("platform") or {}
        gpu = snap.get("gpu") or {}
        key_pkgs = snap.get("key_packages") or {}
        seeds = snap.get("random_seeds") or {}
        cfg = snap.get("config") or {}
        dataset = snap.get("dataset") or {}
        eda = self._eda()

        if key_pkgs:
            pkg_md = _md_table(
                ["Package", "Version"],
                [[k, v] for k, v in key_pkgs.items()],
            )
        else:
            pkg_md = _placeholder("capture reproducibility snapshot (Phase 12)")

        env_rows = [
            ["Python", (snap.get("python_version") or "—").split(" ")[0] if snap else "—"],
            ["OS", platform.get("os", "—")],
            ["Machine", platform.get("machine", "—")],
            ["CPU count", platform.get("cpu_count", "—")],
            ["GPU available", gpu.get("available", "—")],
            ["GPU device", gpu.get("device_name", "—")],
            ["Snapshot timestamp", snap.get("timestamp", "—")],
        ]
        env_md = (
            _md_table(["Item", "Value"], env_rows)
            if snap
            else _placeholder("capture reproducibility snapshot")
        )

        stack_md = _md_table(
            ["Layer", "Technology"],
            [
                ["Embeddings", cfg.get("embedding_model", "all-MiniLM-L6-v2")],
                ["Vector index", cfg.get("faiss_index_type", "IndexFlatIP")],
                ["Classifier", cfg.get("classifier", "LogisticRegression")],
                ["API", "FastAPI (REST + WebSocket)"],
                ["Frontend", "Material Dashboard React"],
                ["LLM (RAG / Analyzer)", "Anthropic API"],
                ["Metadata / Analytics", "SQLite"],
            ],
        )

        arch_ref = (
            f"- Architecture diagram: `research/reports/figures/system_architecture.png` "
            f"({'present' if (_ARCHITECTURE_FIGS / 'system_architecture.png').exists() else 'missing — run DissertationFigureGenerator'})"
        )

        body = "\n".join(
            [
                "# Chapter 3: Methodology (Technical Implementation Section)",
                "",
                "*Auto-generated draft. Section numbers (3.X) should be aligned with the final thesis outline.*",
                "",
                "## 3.X Implementation Environment",
                "",
                env_md,
                "",
                "### Key package versions",
                "",
                pkg_md,
                "",
                "### Hardware specifications",
                "",
                f"- Processor: {platform.get('processor') or _placeholder('reproducibility snapshot')}",
                f"- GPU memory (GB): {_fmt(gpu.get('memory_gb'))}",
                f"- Random seeds: {json.dumps(seeds) if seeds else _placeholder('reproducibility snapshot')}",
                "",
                "## 3.X+1 Dataset Preparation",
                "",
                "### Data sources and licensing",
                "",
                "- Curated open EFL / graded-reader / public-domain text sources under `data/raw/` "
                "(see Discover manifest and dataset README for licensing notes).",
                f"- Dataset hash (raw dir): `{dataset.get('raw_dir_hash') or '—'}`",
                "",
                "### Data collection procedure",
                "",
                "- Offline 14-stage pipeline: Discover → Load → Integrate → EDA → Clean → Split → "
                "Preprocess → Balance → Train → Evaluate → Explain* → Predict.",
                "- Integration produces a unified resource table with CEFR, skill, topic, and text fields.",
                "",
                "### Dataset statistics (EDA)",
                "",
                f"- Total resources: {_fmt(eda.get('total_resources'), 0) if eda else _placeholder('04')}",
                f"- Integrated rows (snapshot): {_fmt(dataset.get('integrated_rows'), 0)}",
                f"- Train / val / test rows: "
                f"{_fmt(dataset.get('train_rows'), 0)} / "
                f"{_fmt(dataset.get('val_rows'), 0)} / "
                f"{_fmt(dataset.get('test_rows'), 0)}",
                "",
                _sources_table(eda.get("top_sources")) if eda else _placeholder("04"),
                "",
                "## 3.X+2 System Architecture",
                "",
                arch_ref,
                "- Also: `data_flow_diagram.png`, `component_diagram.png`, `pipeline_flowchart.png`.",
                "",
                "### Component descriptions",
                "",
                "- **Pipeline package:** offline ETL, training, evaluation, explainability.",
                "- **Services:** search, RAG, recommend, analyzer, duplicates, analytics.",
                "- **Stores:** FAISS vectors, SQLite metadata, SQLite analytics.",
                "- **Frontend:** Pipeline Monitor, Search, Insights, Admin, Practitioner Evaluation.",
                "",
                "### Technology stack",
                "",
                stack_md,
                "",
            ]
        )
        return self._write(out, body)

    # ── Appendix ────────────────────────────────────────────────────────

    def generate_model_statistics_appendix(
        self, output_path: str | Path | None = None
    ) -> str:
        out = (
            Path(output_path)
            if output_path
            else _DEFAULT_OUT / "appendix_model_stats.md"
        )
        ev = self._eval()
        clf = ev.get("classification") or {}
        labels = ev.get("confusion_matrix_labels") or []
        cm_s = ev.get("confusion_matrix_sbert")
        cm_t = ev.get("confusion_matrix_tfidf")
        global_rep = self._explain_global()
        local = self._explain_local_list()
        quality = self._explain_quality()

        def _cm_md(cm: Any, title: str) -> str:
            if not cm or not labels:
                return f"### {title}\n\n{_placeholder('10')}\n"
            header = ["True \\ Pred"] + [str(l) for l in labels]
            rows = []
            for i, lab in enumerate(labels):
                row = [lab] + [
                    cm[i][j] if i < len(cm) and j < len(cm[i]) else "—"
                    for j in range(len(labels))
                ]
                rows.append(row)
            return f"### {title}\n\n{_md_table(header, rows)}\n"

        # Classification reports
        clf_sections = []
        for name, block in (("SBERT", clf.get("sbert")), ("TF-IDF", clf.get("tfidf"))):
            if not block:
                clf_sections.append(f"### {name}\n\n{_placeholder('10')}\n")
                continue
            clf_sections.append(
                f"### {name}\n\n"
                + _md_table(
                    ["Metric", "Value"],
                    [
                        ["Accuracy", _fmt(block.get("accuracy"))],
                        ["Precision (macro)", _fmt(block.get("precision_macro"))],
                        ["Recall (macro)", _fmt(block.get("recall_macro"))],
                        ["F1 (macro)", _fmt(block.get("f1_macro"))],
                    ],
                )
                + "\n"
            )

        # Per-query distributions
        per_query_md = _placeholder("10 (10_per_query_metrics.json)")
        if isinstance(self.per_query, dict) and self.per_query.get("methods"):
            lines = []
            for method, rows in (self.per_query.get("methods") or {}).items():
                if not rows:
                    continue
                df = pd.DataFrame(rows)
                numeric_cols = [
                    c
                    for c in df.columns
                    if c.startswith(("precision_", "recall_", "f1_", "ap_", "mrr_"))
                ]
                if not numeric_cols:
                    continue
                desc = df[numeric_cols].describe().T.reset_index()
                desc.columns = ["metric"] + list(desc.columns[1:])
                lines.append(f"#### Method: `{method}` (n={len(rows)})\n")
                lines.append(_df_to_md(desc.round(4)))
                lines.append("")
            if lines:
                per_query_md = "\n".join(lines)

        # SHAP full table
        shap = global_rep.get("top_20_shap_features") or []
        if shap:
            shap_rows = []
            for item in shap:
                if isinstance(item, dict):
                    shap_rows.append(
                        [
                            item.get("feature") or item.get("name") or item.get("dim") or "?",
                            _fmt(
                                item.get("importance")
                                or item.get("mean_abs_shap")
                                or item.get("value")
                            ),
                        ]
                    )
                else:
                    shap_rows.append([str(item), "—"])
            shap_md = _md_table(["Feature", "Importance"], shap_rows)
        else:
            shap_md = _placeholder("11")

        # LIME all samples
        lime_parts = []
        for i, item in enumerate(local, start=1):
            lime_parts.append(
                f"#### Sample {i}: `{item.get('resource_id', '?')}`\n\n"
                f"- Predicted: {item.get('predicted_cefr', item.get('prediction', '—'))}\n"
                f"- True: {item.get('true_cefr', item.get('label', '—'))}\n"
                f"- Title: {item.get('title', '—')}\n"
                f"- Human-readable: {item.get('human_readable') or item.get('summary') or '—'}\n"
                f"- Top features: `{json.dumps(item.get('top_features') or item.get('features') or [], ensure_ascii=False)[:500]}`\n"
            )
        lime_md = "\n".join(lime_parts) if lime_parts else _placeholder("12")

        # Experiment log
        experiments = self.experiment_log.get("experiments") or []
        if experiments:
            exp_rows = []
            for e in experiments:
                cfg = e.get("config") or {}
                res = (e.get("results") or {}).get("retrieval") or {}
                exp_rows.append(
                    [
                        e.get("experiment_id", "")[:8],
                        e.get("name", "—"),
                        cfg.get("retrieval_method", "—"),
                        e.get("status", "—"),
                        _fmt(res.get("map") or res.get("precision_at_k")),
                        (e.get("completed_at") or "—")[:19],
                    ]
                )
            exp_md = _md_table(
                ["ID", "Name", "Method", "Status", "MAP/P@k", "Completed"],
                exp_rows,
            )
        else:
            exp_md = _placeholder("run experiments via ExperimentTracker")

        # ROC / AUC — typically not stored; placeholder
        roc_md = (
            "- ROC / AUC artefacts: "
            + (
                "see `research/reports/metrics/` if exported by ResearchMetricsExporter."
                if (_PROJECT_ROOT / "research" / "reports" / "metrics").exists()
                else _placeholder("export metrics / train ROC artefacts (not present in Stage 10 JSON)")
            )
        )

        body = "\n".join(
            [
                "# Appendix: Model Statistics",
                "",
                "*Auto-generated appendix compiling evaluation and explainability artefacts.*",
                "",
                "## Full classification reports",
                "",
                *clf_sections,
                "",
                "## Confusion matrices",
                "",
                _cm_md(cm_s, "SBERT"),
                _cm_md(cm_t, "TF-IDF"),
                "",
                "## ROC curves and AUC values",
                "",
                roc_md,
                "",
                "## Per-query metric distributions",
                "",
                per_query_md,
                "",
                "## SHAP feature importance (full table from Stage 11)",
                "",
                shap_md,
                "",
                f"- Faithfulness: {_fmt(quality.get('faithfulness_score'))}",
                f"- Stability: {_fmt(quality.get('stability_score'))}",
                "",
                "## LIME explanation details",
                "",
                lime_md,
                "",
                "## Complete experiment log (summary)",
                "",
                exp_md,
                "",
                f"- Full JSON: `{_EXPERIMENT_LOG.as_posix()}`",
                "",
            ]
        )
        return self._write(out, body)

    # ── Orchestrator ────────────────────────────────────────────────────

    def generate_all(
        self, output_dir: str | Path = "research/reports/draft_chapters"
    ) -> list[str]:
        out = Path(output_dir)
        if not out.is_absolute():
            out = _PROJECT_ROOT / out
        out.mkdir(parents=True, exist_ok=True)

        return [
            self.generate_methodology_section(out / "chapter_3_methodology.md"),
            self.generate_results_chapter(out / "chapter_4_results.md"),
            self.generate_evaluation_chapter(out / "chapter_5_evaluation.md"),
            self.generate_model_statistics_appendix(out / "appendix_model_stats.md"),
        ]


if __name__ == "__main__":
    gen = ResearchReportGenerator()
    files = gen.generate_all()
    print(f"Generated {len(files)} draft sections")
    for path in files:
        print(path)

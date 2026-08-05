"""Qualitative feedback analysis for practitioner evaluation.

Aggregates InterviewManager, QuestionnaireStore, and QualitativeCoder into
dissertation-ready summaries and a Practitioner Evaluation chapter draft.
"""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from pathlib import Path
from statistics import mean

from research.practitioner_eval.interview_manager import InterviewManager
from research.practitioner_eval.qualitative_coder import QualitativeCoder
from research.practitioner_eval.questionnaire_store import QuestionnaireStore

_RESEARCH_ROOT = Path(__file__).resolve().parents[1]
_THEMATIC_MAP_PATH = _RESEARCH_ROOT / "coding" / "thematic_map.json"

_Q_DIGITAL_FREQ = "q4"
_Q_SATISFACTION = "q5"


class FeedbackAnalyzer:
    """Combine recruitment, SUS, demographics, and thematic coding outputs."""

    def __init__(
        self,
        interview_manager: InterviewManager | None = None,
        questionnaire_store: QuestionnaireStore | None = None,
        qualitative_coder: QualitativeCoder | None = None,
    ) -> None:
        self.interviews = interview_manager or InterviewManager()
        self.questionnaires = questionnaire_store or QuestionnaireStore()
        self.coder = qualitative_coder or QualitativeCoder(
            interview_manager=self.interviews
        )

    def _pseudonym_map(self) -> dict[str, str]:
        return {p.participant_id: p.pseudonym for p in self.interviews.get_all()}

    def _demographics_summary(self) -> dict:
        active = [
            p for p in self.interviews.get_all() if p.status != "Withdrawn"
        ]
        contexts = Counter(p.teaching_context for p in active)
        mean_years = (
            float(mean(p.years_experience for p in active)) if active else 0.0
        )

        digital_freq: Counter[str] = Counter()
        satisfaction: Counter[str] = Counter()
        for resp in self.questionnaires.get_responses("demographics"):
            answers = resp.responses
            if _Q_DIGITAL_FREQ in answers:
                digital_freq[str(answers[_Q_DIGITAL_FREQ])] += 1
            if _Q_SATISFACTION in answers:
                satisfaction[str(answers[_Q_SATISFACTION])] += 1

        return {
            "teaching_contexts": dict(sorted(contexts.items())),
            "mean_years_experience": round(mean_years, 2),
            "digital_tool_frequency": dict(sorted(digital_freq.items())),
            "current_satisfaction": dict(sorted(satisfaction.items())),
        }

    def _thematic_map_dict(self) -> dict:
        """Build thematic map via QualitativeCoder and return the JSON payload."""
        self.coder.export_thematic_map_json(_THEMATIC_MAP_PATH)
        if not _THEMATIC_MAP_PATH.exists():
            return {"themes": []}
        return json.loads(_THEMATIC_MAP_PATH.read_text(encoding="utf-8"))

    def full_analysis(self) -> dict:
        """Combined qualitative evaluation payload for the dissertation."""
        theme_freq = self.coder.theme_frequency_table()
        return {
            "recruitment": self.interviews.recruitment_summary(),
            "sus": self.questionnaires.sus_summary(),
            "demographics": self._demographics_summary(),
            "thematic_analysis": {
                "total_segments": len(self.coder._segments),
                "total_codes": len(self.coder.list_all_codes()),
                "total_themes": len(self.coder.list_all_themes()),
                "themes": theme_freq,
                "thematic_map": self._thematic_map_dict(),
            },
        }

    def _individual_sus_rows(self) -> list[tuple[str, float]]:
        """(pseudonym, sus_score) for participants with a complete SUS response."""
        id_to_pseudo = self._pseudonym_map()
        by_id: dict[str, float] = {}
        for pid in {
            r.participant_id for r in self.questionnaires.get_responses("sus")
        }:
            score = self.questionnaires.compute_sus_score(pid)
            if score is not None:
                by_id[pid] = score
        rows = [
            (id_to_pseudo.get(pid, pid[:8]), score)
            for pid, score in by_id.items()
        ]
        rows.sort(key=lambda t: t[0])
        return rows

    def generate_practitioner_chapter_draft(self, output_path: str | Path) -> None:
        """Draft 'Practitioner Evaluation' dissertation section from real data only."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "participants.csv"
            self.interviews.export_participant_table_csv(csv_path)
            demo_csv = csv_path.read_text(encoding="utf-8").strip()

        sus = self.questionnaires.sus_summary()
        sus_rows = self._individual_sus_rows()
        id_to_pseudo = self._pseudonym_map()
        themes = self.coder.list_all_themes()
        recruitment = self.interviews.recruitment_summary()
        demographics = self._demographics_summary()

        lines: list[str] = [
            "# 4.X Practitioner Evaluation",
            "",
            "This section reports findings from the qualitative practitioner "
            "evaluation arm of the feasibility study. All figures and quotes "
            "are drawn from stored participant, questionnaire, and coding data.",
            "",
            "## 4.X.1 Participant Demographics",
            "",
        ]

        if not demo_csv or demo_csv.count("\n") < 1:
            lines.append(
                "_No active (non-withdrawn) participants recorded yet._"
            )
            lines.append("")
        else:
            header, *body = demo_csv.splitlines()
            cols = header.split(",")
            lines.append("| " + " | ".join(cols) + " |")
            lines.append("| " + " | ".join("---" for _ in cols) + " |")
            for row in body:
                lines.append("| " + " | ".join(row.split(",")) + " |")
            lines.append("")
            contexts = recruitment.get("contexts_represented") or []
            lines.append(
                f"Contexts represented: {', '.join(contexts) or 'none'}; "
                f"mean years of EFL experience: "
                f"{demographics['mean_years_experience']}."
            )
            lines.append("")

        lines.extend(["## 4.X.2 System Usability Scale Results", ""])
        if sus.get("n_respondents", 0) == 0:
            lines.append("_No SUS responses recorded yet._")
            lines.append("")
        else:
            lines.append(
                f"Mean SUS = **{sus['mean_sus']}** "
                f"(SD = {sus['std_sus']}, range {sus['min_sus']}–{sus['max_sus']}, "
                f"n = {sus['n_respondents']}). "
                f"Bangor et al. (2009) adjective rating: "
                f"**{sus['adjective_rating']}**."
            )
            lines.append("")
            lines.append("| Pseudonym | SUS Score |")
            lines.append("| --- | ---: |")
            for pseudo, score in sus_rows:
                lines.append(f"| {pseudo} | {score:.1f} |")
            lines.append("")

        lines.extend(
            [
                "## 4.X.3 Thematic Analysis Findings",
                "",
                "Themes were developed following Braun and Clarke (2006).",
                "",
            ]
        )
        if not themes:
            lines.append("_No themes assigned to coded segments yet._")
            lines.append("")
        else:
            for theme in themes:
                segs = self.coder.get_codes_by_theme(theme)
                subs = sorted({s.sub_theme for s in segs if s.sub_theme})
                codes = sorted({s.code for s in segs})
                lines.append(f"### Theme: {theme}")
                lines.append("")
                lines.append(
                    f"**Description:** This theme groups {len(segs)} coded "
                    f"segment(s) spanning code(s): {', '.join(codes) or 'n/a'}."
                )
                lines.append("")
                if subs:
                    lines.append("**Sub-themes:** " + ", ".join(subs))
                    lines.append("")
                lines.append("**Illustrative quotes:**")
                lines.append("")
                for code in codes:
                    for s in [x for x in segs if x.code == code][:2]:
                        pseudo = id_to_pseudo.get(
                            s.participant_id, s.participant_id[:8]
                        )
                        excerpt = s.text_excerpt.replace("\n", " ").strip()
                        lines.append(f"> {excerpt}")
                        lines.append(">")
                        lines.append(f"> — {pseudo} (`{code}`)")
                        lines.append("")

        lines.extend(["## 4.X.4 Summary of Practitioner Feedback", ""])
        summary_bits: list[str] = [
            f"{recruitment.get('total_recruited', 0)} practitioner(s) were "
            f"recruited; {recruitment.get('total_interviewed', 0)} interviewed; "
            f"{recruitment.get('total_coded', 0)} coded."
        ]
        if sus.get("n_respondents", 0):
            summary_bits.append(
                f"Mean SUS was {sus['mean_sus']} "
                f"({sus['adjective_rating']} on the Bangor et al. adjective scale)."
            )
        else:
            summary_bits.append("SUS data are not yet available.")
        if themes:
            summary_bits.append(
                f"Thematic analysis currently comprises "
                f"{len(self.coder._segments)} segments, "
                f"{len(self.coder.list_all_codes())} codes, and "
                f"{len(themes)} theme(s): {', '.join(themes)}."
            )
        else:
            summary_bits.append(
                "Thematic coding has not yet produced defined themes."
            )
        lines.append(" ".join(summary_bits))
        lines.append("")

        output_path.write_text("\n".join(lines), encoding="utf-8")

"""Seed a complete practitioner-evaluation walkthrough (8 pseudonyms).

IMPORTANT: rows are tagged ``data_provenance=protocol_walkthrough``.
They exercise consent, SUS, bias ratings, transcripts, and Braun & Clarke
coding so the dissertation toolchain works. They are not a substitute for
REC-approved field interviews with real teachers.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from research.practitioner_eval.interview_manager import InterviewManager
from research.practitioner_eval.models import (
    CodedSegment,
    InterviewRecord,
    Participant,
    QuestionnaireResponse,
)
from research.practitioner_eval.qualitative_coder import QualitativeCoder
from research.practitioner_eval.questionnaire_store import QuestionnaireStore

_ROOT = Path(__file__).resolve().parents[1]
_INTERVIEWS = _ROOT / "interviews"
_ETHICS = _ROOT / "ethics"
_PROVENANCE = "protocol_walkthrough"

_CONTEXTS = [
    ("Primary", 6, "Public School", "LinkedIn"),
    ("Secondary", 11, "Public School", "Professional Network"),
    ("Adult", 8, "Private Language School", "LinkedIn"),
    ("Academic English", 14, "University/College", "Professional Network"),
    ("Secondary", 4, "Private Language School", "Email"),
    ("Adult", 19, "Freelance/Private Tutor", "LinkedIn"),
    ("Primary", 9, "Public School", "Professional Network"),
    ("Academic English", 7, "University/College", "Conference"),
]

_THEMES = [
    ("pedagogical_fit", "Usefulness", "CEFR match"),
    ("trust_filters", "Trust", "Metadata filters"),
    ("usability_search", "Usability", "Search speed"),
    ("skill_gap", "Coverage", "Listening/speaking gap"),
    ("rag_grounding", "Trust", "Ask AI grounding"),
    ("bias_cefr", "Fairness", "Level imbalance"),
    ("time_saving", "Usefulness", "Lesson planning"),
    ("need_labels", "Coverage", "Skill/topic labels"),
]


def _transcript(i: int, context: str) -> str:
    lines = [
        f"[PROTOCOL WALKTHROUGH — not a field interview. Pseudonym P{i}. Context: {context}.]",
        "I usually hunt for graded readers on several websites, so a single index would save time.",
        "CEFR filters are the first thing I would use; if B1 results include C1 texts I would not trust it.",
        "Skill filters for listening and speaking matter as much as reading passages.",
        "The search felt fast compared with keyword Google queries for 'A2 travel dialogue'.",
        "I worry that most items look like reading texts rather than classroom audio.",
        "Ask AI is useful only if it cites the worksheet, not if it invents grammar rules.",
        "I would still want to skim the extract before I set it as homework.",
        "Topic tags such as Health or Travel help me build a weekly scheme of work.",
        "If Inner-Circle culture dominates, I would add local materials myself.",
        "Overall the prototype is promising for feasibility, not yet a replacement for my folders.",
    ]
    return "\n".join(lines) + "\n"


def _sus_scores(i: int) -> dict[str, int]:
    base = [4, 2, 4, 2, 4, 2, 4, 2, 4, 2]
    jitter = (i % 3) - 1
    out: dict[str, int] = {}
    for n, v in enumerate(base, start=1):
        out[f"sus_{n:02d}"] = min(5, max(1, v + jitter))
    return out


def run_seed() -> dict:
    mgr = InterviewManager()
    store = QuestionnaireStore()
    coder = QualitativeCoder(interview_manager=mgr)
    _INTERVIEWS.mkdir(parents=True, exist_ok=True)
    _ETHICS.mkdir(parents=True, exist_ok=True)

    consent_log: list[dict] = []
    created: list[str] = []
    existing = {p.pseudonym: p for p in mgr.get_all()}

    for i, (ctx, years, inst, via) in enumerate(_CONTEXTS, start=1):
        pseudo = f"P{i}"
        if pseudo in existing:
            participant = existing[pseudo]
        else:
            participant = mgr.add_participant(
                Participant(
                    pseudonym=pseudo,
                    teaching_context=ctx,  # type: ignore[arg-type]
                    years_experience=years,
                    institution_type=inst,
                    recruited_via=via,
                    consent_given=True,
                    consent_date=date.today().isoformat(),
                    interview_date=date.today().isoformat(),
                    interview_duration_minutes=35,
                    status="Consented",
                )
            )
        pid = participant.participant_id
        created.append(pid)
        consent_log.append(
            {
                "pseudonym": pseudo,
                "participant_id": pid,
                "pis_issued": True,
                "consent_recorded": True,
                "consent_date": date.today().isoformat(),
                "withdrawal_window_days": 14,
                "data_provenance": _PROVENANCE,
            }
        )

        t_path = _INTERVIEWS / f"{pseudo}_transcript.txt"
        t_path.write_text(_transcript(i, ctx), encoding="utf-8")
        rel = str(t_path.relative_to(_ROOT)).replace("\\", "/")
        mgr.link_interview(
            pid,
            InterviewRecord(
                participant_id=pid,
                audio_file=None,
                transcript_file=rel,
                duration_minutes=35,
                interview_date=date.today().isoformat(),
                interviewer_notes=f"data_provenance={_PROVENANCE}",
            ),
        )
        mgr.update_status(pid, "Transcribed")

        now = datetime.now(timezone.utc).isoformat()
        store.store_response(
            QuestionnaireResponse(
                participant_id=pid,
                questionnaire_id="sus",
                responses=_sus_scores(i),
                completed_at=now,
            )
        )
        store.store_response(
            QuestionnaireResponse(
                participant_id=pid,
                questionnaire_id="demographics",
                responses={"q1": ctx, "q2": years, "q3": inst, "q4": 4, "q5": 3},
                completed_at=now,
            )
        )
        store.store_response(
            QuestionnaireResponse(
                participant_id=pid,
                questionnaire_id="bias",
                responses={
                    "bias_01": 4,
                    "bias_02": 4 if i % 2 else 3,
                    "bias_03": 3,
                    "bias_04": 3,
                    "bias_05": 4,
                },
                completed_at=now,
            )
        )

        theme, parent, sub = _THEMES[i - 1]
        lines = t_path.read_text(encoding="utf-8").splitlines()
        excerpt = lines[min(2, len(lines) - 1)]
        coder.code_segment(
            CodedSegment(
                participant_id=pid,
                transcript_line_start=2,
                transcript_line_end=3,
                text_excerpt=excerpt,
                code=theme,
                theme=parent,
                sub_theme=sub,
                coder_notes=_PROVENANCE,
            )
        )
        mgr.update_status(pid, "Coded")

    consent_path = _ETHICS / "consent_log.json"
    consent_path.write_text(
        json.dumps(
            {
                "data_provenance": _PROVENANCE,
                "note": "Process log only. No real names. Fieldwork still requires REC approval.",
                "entries": consent_log,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    map_path = _ROOT / "coding" / "thematic_map.json"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        coder.export_thematic_map_json(map_path)
    except Exception:
        map_path.write_text(
            json.dumps(
                {"themes": [t[1] for t in _THEMES], "data_provenance": _PROVENANCE},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    report_path = _ROOT / "reports" / "thematic_coding_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        coder.generate_coding_report(report_path)
    except Exception:
        report_path.write_text(
            "# Thematic coding report\n\nProtocol walkthrough (8 coded segments).\n",
            encoding="utf-8",
        )

    return {
        "participants": len(created),
        "sus": store.sus_summary(),
        "consent_log": str(consent_path),
        "data_provenance": _PROVENANCE,
    }


if __name__ == "__main__":
    print(json.dumps(run_seed(), indent=2, default=str))

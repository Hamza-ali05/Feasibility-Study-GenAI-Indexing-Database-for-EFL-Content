"""
Practitioner Evaluation API — admin-only qualitative research workflow.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.auth.admin_auth import get_current_admin
from research.practitioner_eval.export import export_all
from research.practitioner_eval.feedback_analyzer import FeedbackAnalyzer
from research.practitioner_eval.interview_manager import InterviewManager
from research.practitioner_eval.models import (
    Participant,
    ParticipantStatus,
    QuestionnaireResponse,
)
from research.practitioner_eval.qualitative_coder import QualitativeCoder
from research.practitioner_eval.questionnaire_store import QuestionnaireStore

router = APIRouter(tags=["practitioner"])

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_REPORTS_DIR = _PROJECT_ROOT / "research" / "reports"

_VALID_STATUSES = {
    "Recruited",
    "Consented",
    "Interviewed",
    "Transcribed",
    "Coded",
    "Withdrawn",
}


class ParticipantCreate(BaseModel):
    """Participant payload without auto id (generated server-side)."""

    pseudonym: str
    teaching_context: str
    years_experience: int = Field(..., ge=0)
    institution_type: str
    recruited_via: str
    consent_given: bool = False
    consent_date: str | None = None
    interview_date: str | None = None
    interview_duration_minutes: int | None = None
    status: ParticipantStatus = "Recruited"


class StatusUpdate(BaseModel):
    status: str


def _managers() -> tuple[InterviewManager, QuestionnaireStore, QualitativeCoder, FeedbackAnalyzer]:
    interviews = InterviewManager()
    questionnaires = QuestionnaireStore()
    coder = QualitativeCoder(interview_manager=interviews)
    analyzer = FeedbackAnalyzer(
        interview_manager=interviews,
        questionnaire_store=questionnaires,
        qualitative_coder=coder,
    )
    return interviews, questionnaires, coder, analyzer


@router.get("/participants")
def list_participants(
    _admin: str = Depends(get_current_admin),
) -> list[dict[str, Any]]:
    """All participants with linked interview + questionnaire responses."""
    interviews, questionnaires, _, _ = _managers()
    out: list[dict[str, Any]] = []
    for p in interviews.get_all():
        interview = interviews.get_interview(p.participant_id)
        responses = [
            r.model_dump()
            for r in questionnaires._responses
            if r.participant_id == p.participant_id
        ]
        out.append(
            {
                **p.model_dump(),
                "interview": interview.model_dump() if interview else None,
                "questionnaire_responses": responses,
            }
        )
    out.sort(key=lambda row: row.get("pseudonym") or "")
    return out


@router.post("/participants", status_code=status.HTTP_201_CREATED)
def create_participant(
    body: ParticipantCreate,
    _admin: str = Depends(get_current_admin),
) -> dict[str, Any]:
    interviews, _, _, _ = _managers()
    try:
        participant = Participant(**body.model_dump())
        created = interviews.add_participant(participant)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return created.model_dump()


@router.patch("/participants/{participant_id}/status")
def update_participant_status(
    participant_id: str,
    body: StatusUpdate,
    _admin: str = Depends(get_current_admin),
) -> dict[str, Any]:
    if body.status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status. Expected one of: {sorted(_VALID_STATUSES)}",
        )
    interviews, _, _, _ = _managers()
    try:
        updated = interviews.update_status(participant_id, body.status)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return updated.model_dump()


@router.post("/participants/{participant_id}/withdraw")
def withdraw_participant(
    participant_id: str,
    _admin: str = Depends(get_current_admin),
) -> dict[str, str]:
    interviews, _, _, _ = _managers()
    try:
        interviews.withdraw_participant(participant_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return {
        "status": "Withdrawn",
        "participant_id": participant_id,
        "detail": "Transcript and coded segments purged; withdrawal logged.",
    }


@router.get("/questionnaires")
def list_questionnaires(
    _admin: str = Depends(get_current_admin),
) -> list[dict[str, str]]:
    _, store, _, _ = _managers()
    items: list[dict[str, str]] = []
    for qid, definition in store._definitions.items():
        items.append(
            {
                "questionnaire_id": qid,
                "title": str(definition.get("title") or qid),
            }
        )
    items.sort(key=lambda x: x["questionnaire_id"])
    return items


@router.get("/questionnaires/{questionnaire_id}")
def get_questionnaire(
    questionnaire_id: str,
    _admin: str = Depends(get_current_admin),
) -> dict[str, Any]:
    _, store, _, _ = _managers()
    try:
        return store.load_questionnaire(questionnaire_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/responses", status_code=status.HTTP_201_CREATED)
def store_response(
    body: QuestionnaireResponse,
    _admin: str = Depends(get_current_admin),
) -> dict[str, Any]:
    _, store, _, _ = _managers()
    store.store_response(body)
    return body.model_dump()


@router.get("/sus-summary")
def sus_summary(_admin: str = Depends(get_current_admin)) -> dict[str, Any]:
    _, store, _, _ = _managers()
    return store.sus_summary()


@router.get("/recruitment-summary")
def recruitment_summary(
    _admin: str = Depends(get_current_admin),
) -> dict[str, Any]:
    interviews, _, _, _ = _managers()
    return interviews.recruitment_summary()


@router.get("/thematic-summary")
def thematic_summary(
    _admin: str = Depends(get_current_admin),
) -> dict[str, Any]:
    _, _, coder, _ = _managers()
    return {
        "code_frequency": coder.code_frequency_table(),
        "theme_frequency": coder.theme_frequency_table(),
        "total_segments": len(coder._segments),
        "total_codes": len(coder.list_all_codes()),
        "total_themes": len(coder.list_all_themes()),
    }


@router.get("/report")
def full_report(_admin: str = Depends(get_current_admin)) -> dict[str, Any]:
    _, _, _, analyzer = _managers()
    return analyzer.full_analysis()


@router.post("/export")
def export_reports(
    _admin: str = Depends(get_current_admin),
) -> dict[str, Any]:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    export_all(_REPORTS_DIR)
    generated = sorted(
        str(p.relative_to(_PROJECT_ROOT)).replace("\\", "/")
        for p in _REPORTS_DIR.iterdir()
        if p.is_file() and p.name != ".gitkeep"
    )
    return {"output_dir": "research/reports", "files": generated}

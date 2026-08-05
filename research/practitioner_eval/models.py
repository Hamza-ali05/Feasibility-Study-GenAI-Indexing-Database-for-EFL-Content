"""Pydantic v2 data models for the Practitioner Evaluation Module.

All participant identifiers use pseudonyms (P1, P2, …) — never real names —
in line with GDPR and CCCU research ethics requirements.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


TeachingContext = Literal["Primary", "Secondary", "Adult", "Academic English"]
ParticipantStatus = Literal[
    "Recruited",
    "Consented",
    "Interviewed",
    "Transcribed",
    "Coded",
    "Withdrawn",
]


class Participant(BaseModel):
    """Anonymised EFL practitioner recruited for the feasibility study."""

    participant_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pseudonym: str = Field(
        ...,
        description='Pseudonym only (e.g. "P1", "P2") — never real names',
        examples=["P1", "P2"],
    )
    teaching_context: TeachingContext
    years_experience: int = Field(..., ge=0)
    institution_type: str
    recruited_via: str = Field(
        ...,
        description='Recruitment channel (e.g. "LinkedIn", "Professional Network")',
    )
    consent_given: bool = False
    consent_date: str | None = Field(
        default=None,
        description="ISO date when informed consent was obtained",
    )
    interview_date: str | None = Field(
        default=None,
        description="ISO date of the semi-structured interview",
    )
    interview_duration_minutes: int | None = Field(default=None, ge=0)
    status: ParticipantStatus = "Recruited"


class InterviewRecord(BaseModel):
    """Metadata for one semi-structured interview session."""

    participant_id: str
    audio_file: str | None = Field(
        default=None,
        description=(
            "Path to audio on CCCU secure server — never stored in this repo"
        ),
    )
    transcript_file: str | None = Field(
        default=None,
        description="Path to anonymised .txt transcript under research/interviews/",
    )
    duration_minutes: int = Field(..., ge=0)
    interview_date: str = Field(..., description="ISO date")
    interviewer_notes: str = ""


class QuestionnaireResponse(BaseModel):
    """One completed questionnaire instance for a participant."""

    participant_id: str
    questionnaire_id: str
    responses: dict[str, Any]
    completed_at: str = Field(..., description="ISO datetime")


class CodedSegment(BaseModel):
    """A thematically coded excerpt from an anonymised transcript.

    Coding follows Braun and Clarke (2006) thematic analysis.
    """

    segment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    participant_id: str
    transcript_line_start: int = Field(..., ge=1)
    transcript_line_end: int = Field(..., ge=1)
    text_excerpt: str
    code: str
    theme: str | None = None
    sub_theme: str | None = None
    coder_notes: str | None = None

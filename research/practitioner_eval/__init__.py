"""Practitioner Evaluation Module for the EFL IndexDB feasibility study.

Supports recruitment tracking, questionnaire storage, thematic coding
(Braun & Clarke, 2006), and qualitative feedback analysis for 6–8 EFL
practitioners.
"""

from research.practitioner_eval.models import (
    CodedSegment,
    InterviewRecord,
    Participant,
    QuestionnaireResponse,
)

__all__ = [
    "Participant",
    "InterviewRecord",
    "QuestionnaireResponse",
    "CodedSegment",
]

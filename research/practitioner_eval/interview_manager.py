"""Interview lifecycle management for practitioner evaluation.

Tracks participants from recruitment through coding. Persistence is a
JSON file at research/practitioner_eval/participants.json. Transcripts
and coded segments live under research/interviews/ and research/coding/.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from statistics import mean

from research.practitioner_eval.models import (
    InterviewRecord,
    Participant,
    ParticipantStatus,
)

logger = logging.getLogger(__name__)

_RESEARCH_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_STORE = Path(__file__).resolve().parent / "participants.json"
_INTERVIEWS_DIR = _RESEARCH_ROOT / "interviews"
_CODING_DIR = _RESEARCH_ROOT / "coding"
_WITHDRAWAL_LOG = Path(__file__).resolve().parent / "withdrawal_log.jsonl"

_STATUS_KEYS = {
    "Recruited": "total_recruited",
    "Consented": "total_consented",
    "Interviewed": "total_interviewed",
    "Transcribed": "total_transcribed",
    "Coded": "total_coded",
    "Withdrawn": "total_withdrawn",
}


class InterviewManager:
    """CRUD and lifecycle operations for anonymised practitioner participants."""

    def __init__(self, store_path: Path | str | None = None) -> None:
        self.store_path = Path(store_path) if store_path else _DEFAULT_STORE
        self._participants: dict[str, Participant] = {}
        self._interviews: dict[str, InterviewRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        raw = json.loads(self.store_path.read_text(encoding="utf-8"))
        for item in raw.get("participants", []):
            p = Participant.model_validate(item)
            self._participants[p.participant_id] = p
        for item in raw.get("interviews", []):
            rec = InterviewRecord.model_validate(item)
            self._interviews[rec.participant_id] = rec

    def _save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "participants": [p.model_dump() for p in self._participants.values()],
            "interviews": [i.model_dump() for i in self._interviews.values()],
        }
        self.store_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _get_or_raise(self, participant_id: str) -> Participant:
        if participant_id not in self._participants:
            raise KeyError(f"Participant not found: {participant_id}")
        return self._participants[participant_id]

    def add_participant(self, participant: Participant) -> Participant:
        """Register a new anonymised participant and persist."""
        if participant.participant_id in self._participants:
            raise ValueError(
                f"Participant already exists: {participant.participant_id}"
            )
        for existing in self._participants.values():
            if existing.pseudonym == participant.pseudonym:
                raise ValueError(
                    f"Pseudonym already in use: {participant.pseudonym}"
                )
        self._participants[participant.participant_id] = participant
        self._save()
        return participant

    def update_status(
        self, participant_id: str, new_status: ParticipantStatus | str
    ) -> Participant:
        """Update lifecycle status (Recruited → … → Coded / Withdrawn)."""
        participant = self._get_or_raise(participant_id)
        updated = participant.model_copy(update={"status": new_status})
        self._participants[participant_id] = updated
        self._save()
        return updated

    def withdraw_participant(self, participant_id: str) -> None:
        """Set status to Withdrawn and purge associated research artefacts.

        Deletes the linked anonymised transcript and any coded segments for
        this participant (CCCU data retention / right to withdraw). Audio on
        the CCCU secure server is not touched from this repo — only logged.
        """
        participant = self._get_or_raise(participant_id)
        interview = self._interviews.get(participant_id)

        deleted_transcript: str | None = None
        deleted_coding_files: list[str] = []

        if interview and interview.transcript_file:
            transcript_path = Path(interview.transcript_file)
            if not transcript_path.is_absolute():
                transcript_path = _RESEARCH_ROOT / transcript_path
            if transcript_path.exists():
                transcript_path.unlink()
                deleted_transcript = str(transcript_path)

        # Remove coded-segment files that name this participant
        if _CODING_DIR.exists():
            for path in _CODING_DIR.glob("*.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                segments = data if isinstance(data, list) else data.get("segments", [])
                if not isinstance(segments, list):
                    continue
                remaining = [
                    s
                    for s in segments
                    if s.get("participant_id") != participant_id
                ]
                if len(remaining) != len(segments):
                    if remaining:
                        path.write_text(
                            json.dumps(
                                remaining
                                if isinstance(data, list)
                                else {**data, "segments": remaining},
                                indent=2,
                                ensure_ascii=False,
                            )
                            + "\n",
                            encoding="utf-8",
                        )
                    else:
                        path.unlink()
                    deleted_coding_files.append(str(path))

            # Also remove a dedicated per-participant coding file if present
            dedicated = _CODING_DIR / f"{participant.pseudonym}_codes.json"
            if dedicated.exists():
                dedicated.unlink()
                deleted_coding_files.append(str(dedicated))

        self._participants[participant_id] = participant.model_copy(
            update={"status": "Withdrawn"}
        )
        self._interviews.pop(participant_id, None)
        self._save()

        log_entry = {
            "event": "withdrawal",
            "participant_id": participant_id,
            "pseudonym": participant.pseudonym,
            "deleted_transcript": deleted_transcript,
            "deleted_coding_files": deleted_coding_files,
            "audio_file_note": (
                interview.audio_file
                if interview and interview.audio_file
                else None
            ),
            "message": (
                "Participant withdrawn; transcript and coded segments deleted "
                "from repo. Confirm CCCU secure-server audio purge separately."
            ),
        }
        _WITHDRAWAL_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _WITHDRAWAL_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        logger.info(
            "Withdrawal recorded for %s (%s)",
            participant.pseudonym,
            participant_id,
        )

    def get_all(self) -> list[Participant]:
        return list(self._participants.values())

    get_all = get_all

    def get_by_status(self, status: ParticipantStatus | str) -> list[Participant]:
        return [p for p in self._participants.values() if p.status == status]

    def link_interview(
        self, participant_id: str, interview: InterviewRecord
    ) -> None:
        """Attach an InterviewRecord and sync participant interview fields."""
        participant = self._get_or_raise(participant_id)
        if interview.participant_id != participant_id:
            interview = interview.model_copy(
                update={"participant_id": participant_id}
            )
        self._interviews[participant_id] = interview
        self._participants[participant_id] = participant.model_copy(
            update={
                "interview_date": interview.interview_date,
                "interview_duration_minutes": interview.duration_minutes,
                "status": (
                    participant.status
                    if participant.status
                    in ("Interviewed", "Transcribed", "Coded", "Withdrawn")
                    else "Interviewed"
                ),
            }
        )
        self._save()

    def get_interview(self, participant_id: str) -> InterviewRecord | None:
        return self._interviews.get(participant_id)

    def recruitment_summary(self) -> dict:
        """Aggregate counts and demographics for the methodology chapter."""
        participants = list(self._participants.values())
        counts = {v: 0 for v in _STATUS_KEYS.values()}
        for p in participants:
            key = _STATUS_KEYS.get(p.status)
            if key:
                counts[key] += 1

        active = [p for p in participants if p.status != "Withdrawn"]
        contexts = sorted({p.teaching_context for p in active})
        mean_exp = (
            float(mean(p.years_experience for p in active)) if active else 0.0
        )

        return {
            **counts,
            "contexts_represented": contexts,
            "mean_experience_years": round(mean_exp, 2),
        }

    def export_participant_table_csv(self, output_path: str | Path) -> None:
        """Anonymised methodology table (no real names or contact data)."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            p
            for p in self._participants.values()
            if p.status != "Withdrawn"
        ]
        rows.sort(key=lambda p: p.pseudonym)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                [
                    "Pseudonym",
                    "Teaching Context",
                    "Years Experience",
                    "Institution Type",
                ]
            )
            for p in rows:
                writer.writerow(
                    [
                        p.pseudonym,
                        p.teaching_context,
                        p.years_experience,
                        p.institution_type,
                    ]
                )

    # API / coder aliases
    get_all = get_all
    add_participant = add_participant
    update_status = update_status
    withdraw_participant = withdraw_participant
    recruitment_summary = recruitment_summary
    get_interview = get_interview
    link_interview = link_interview

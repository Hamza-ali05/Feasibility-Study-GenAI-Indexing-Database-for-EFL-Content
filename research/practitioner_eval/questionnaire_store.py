"""Questionnaire definition loading and response persistence.

Loads instruments from research/questionnaires/ and stores completed
responses in research/practitioner_eval/responses.json.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean, pstdev

from research.practitioner_eval.models import QuestionnaireResponse

_QUESTIONNAIRES_DIR = Path(__file__).resolve().parents[1] / "questionnaires"
_DEFAULT_RESPONSES = Path(__file__).resolve().parent / "responses.json"

# Bangor, Kortum & Miller (2009) adjective ratings for mean SUS
_SUS_ADJECTIVE_THRESHOLDS: list[tuple[float, str]] = [
    (85.5, "Excellent"),
    (72.75, "Good"),
    (52.01, "OK"),
    (38.01, "Poor"),
    (0.0, "Awful"),
]

_SUS_ITEM_ORDER = [f"sus_{i:02d}" for i in range(1, 11)]


def _bangor_adjective(mean_sus: float) -> str:
    for threshold, label in _SUS_ADJECTIVE_THRESHOLDS:
        if mean_sus >= threshold:
            return label
    return "Awful"


class QuestionnaireStore:
    """Load questionnaire templates and persist / score responses."""

    def __init__(
        self,
        questionnaires_dir: Path | str | None = None,
        responses_path: Path | str | None = None,
    ) -> None:
        self.questionnaires_dir = (
            Path(questionnaires_dir) if questionnaires_dir else _QUESTIONNAIRES_DIR
        )
        self.responses_path = (
            Path(responses_path) if responses_path else _DEFAULT_RESPONSES
        )
        self._definitions: dict[str, dict] = {}
        self._responses: list[QuestionnaireResponse] = []
        self._load_definitions()
        self._load_responses()

    def _load_definitions(self) -> None:
        self._definitions.clear()
        if not self.questionnaires_dir.exists():
            return
        for path in sorted(self.questionnaires_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            qid = data.get("questionnaire_id")
            if not qid:
                raise ValueError(f"Missing questionnaire_id in {path}")
            self._definitions[qid] = data

    def _load_responses(self) -> None:
        self._responses.clear()
        if not self.responses_path.exists():
            return
        raw = json.loads(self.responses_path.read_text(encoding="utf-8"))
        items = raw if isinstance(raw, list) else raw.get("responses", [])
        self._responses = [
            QuestionnaireResponse.model_validate(item) for item in items
        ]

    def _save_responses(self) -> None:
        self.responses_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [r.model_dump() for r in self._responses]
        self.responses_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def load_questionnaire(self, questionnaire_id: str) -> dict:
        """Return question list, scale descriptions, and section structure."""
        if questionnaire_id not in self._definitions:
            raise KeyError(f"Unknown questionnaire_id: {questionnaire_id}")
        return self._definitions[questionnaire_id]

    def store_response(self, response: QuestionnaireResponse) -> None:
        """Append a completed response to responses.json."""
        self._responses.append(response)
        self._save_responses()

    def get_responses(self, questionnaire_id: str) -> list[QuestionnaireResponse]:
        return [
            r for r in self._responses if r.questionnaire_id == questionnaire_id
        ]

    @staticmethod
    def _extract_sus_scores(responses: dict) -> list[float] | None:
        """Pull 10 SUS item scores (1–5) in order from a response dict."""
        scores: list[float] = []
        # Prefer explicit sus_01 … sus_10 keys
        if all(k in responses for k in _SUS_ITEM_ORDER):
            for key in _SUS_ITEM_ORDER:
                scores.append(float(responses[key]))
            return scores
        # Fallback: numbered keys q1–q10 or 1–10
        for i in range(1, 11):
            for key in (f"q{i}", str(i), f"item_{i}"):
                if key in responses:
                    scores.append(float(responses[key]))
                    break
            else:
                return None
        return scores if len(scores) == 10 else None

    @classmethod
    def _brooke_sus(cls, item_scores: list[float]) -> float:
        """Brooke (1996): odd −1, even 5−score; sum × 2.5 → 0–100."""
        if len(item_scores) != 10:
            raise ValueError("SUS requires exactly 10 item scores")
        total = 0.0
        for idx, raw in enumerate(item_scores, start=1):
            score = float(raw)
            if score < 1 or score > 5:
                raise ValueError(f"SUS item {idx} out of range 1–5: {score}")
            if idx % 2 == 1:
                total += score - 1
            else:
                total += 5 - score
        return total * 2.5

    def compute_sus_score(self, participant_id: str) -> float | None:
        """SUS score for one participant, or None if no complete SUS response."""
        sus_responses = [
            r
            for r in self._responses
            if r.questionnaire_id == "sus" and r.participant_id == participant_id
        ]
        if not sus_responses:
            return None
        # Use the most recent completion
        latest = max(sus_responses, key=lambda r: r.completed_at)
        items = self._extract_sus_scores(latest.responses)
        if items is None:
            return None
        return self._brooke_sus(items)

    def sus_summary(self) -> dict:
        """Aggregate SUS statistics with Bangor et al. (2009) adjective rating."""
        # Latest complete SUS response wins per participant
        by_participant: dict[str, float] = {}
        for r in sorted(self.get_responses("sus"), key=lambda x: x.completed_at):
            items = self._extract_sus_scores(r.responses)
            if items is None:
                continue
            by_participant[r.participant_id] = self._brooke_sus(items)

        scores = list(by_participant.values())
        n = len(scores)
        if n == 0:
            return {
                "mean_sus": None,
                "std_sus": None,
                "min_sus": None,
                "max_sus": None,
                "n_respondents": 0,
                "adjective_rating": None,
            }

        mean_sus = float(mean(scores))
        std_sus = float(pstdev(scores)) if n > 1 else 0.0
        if math.isnan(std_sus):
            std_sus = 0.0

        return {
            "mean_sus": round(mean_sus, 2),
            "std_sus": round(std_sus, 2),
            "min_sus": round(min(scores), 2),
            "max_sus": round(max(scores), 2),
            "n_respondents": n,
            "adjective_rating": _bangor_adjective(mean_sus),
        }

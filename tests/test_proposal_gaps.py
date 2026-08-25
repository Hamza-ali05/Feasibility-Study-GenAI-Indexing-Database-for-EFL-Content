"""Tests for proposal-gap closures (taxonomy, extractive RAG, media captions)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from backend.models.taxonomy_classifier import (
    SKILL_LABELS,
    TOPIC_LABELS,
    _argmax_labels,
    keyword_seed_labels,
)
from backend.services.media_ingest import parse_captions
from backend.services.rag_service import extractive_answer


def test_prototype_argmax_picks_nearest_label():
    proto = np.eye(len(SKILL_LABELS), dtype=np.float32)
    query = proto[SKILL_LABELS.index("Listening")].reshape(1, -1)
    labels, conf = _argmax_labels(query, proto, SKILL_LABELS)
    assert labels == ["Listening"]
    assert float(conf[0]) > 0.9


def test_keyword_seed_requires_strong_evidence():
    skill, topic, s, t = keyword_seed_labels("hello world this is a short note")
    assert skill is None
    assert topic is None
    skill, topic, s, t = keyword_seed_labels(
        "This grammar exercise practises verb forms, tenses, articles and syntax."
    )
    assert skill == "Grammar"
    assert s >= 3


def test_extractive_rag_uses_retrieved_sentences():
    answer = extractive_answer(
        "airport boarding pass",
        [
            {
                "title": "Airport A2",
                "text_snippet": (
                    "Please have your passport and boarding pass ready. "
                    "The flight to Manchester is now boarding at gate fourteen."
                ),
            }
        ],
    )
    assert "boarding" in answer.lower()
    assert "Airport A2" in answer


def test_extractive_rag_empty_context():
    answer = extractive_answer("anything", [])
    assert "enough information" in answer.lower()


def test_parse_vtt_captions(tmp_path: Path):
    vtt = tmp_path / "clip.vtt"
    vtt.write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHello learners.\n",
        encoding="utf-8",
    )
    text = parse_captions(vtt)
    assert "Hello learners" in text
    assert "WEBVTT" not in text

"""Transformer skill / topic classifiers (SBERT prototypes + logistic regression).

Replaces hash-based taxonomy fallback. Labels are pedagogical hypotheses
produced by the same MiniLM encoder used for retrieval, not random IDs.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from backend.utils.config import DATA_PROCESSED
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.taxonomy_classifier")

SKILL_LABELS = ["Reading", "Writing", "Listening", "Speaking", "Grammar", "Vocabulary"]
TOPIC_LABELS = [
    "Business",
    "Science",
    "Culture",
    "Technology",
    "Daily Life",
    "Academic",
    "Travel",
    "Health",
]

SKILL_PROTOTYPES: dict[str, str] = {
    "Reading": (
        "A reading comprehension passage, article, story or graded reader "
        "for English learners to read silently."
    ),
    "Writing": (
        "A writing task, essay prompt, composition, letter or paragraph "
        "practice for English learners."
    ),
    "Listening": (
        "A listening activity, audio transcript, podcast, dictation or "
        "recording for English learners to hear."
    ),
    "Speaking": (
        "A speaking activity, oral practice, conversation, dialogue, "
        "pronunciation or presentation for English learners."
    ),
    "Grammar": (
        "A grammar exercise covering tenses, verb forms, articles, syntax "
        "or sentence structure."
    ),
    "Vocabulary": (
        "A vocabulary list, synonyms, collocations, word families or "
        "glossary for English learners."
    ),
}

TOPIC_PROTOTYPES: dict[str, str] = {
    "Business": "Business, companies, markets, finance, offices and work.",
    "Science": "Science, experiments, biology, physics, chemistry and research.",
    "Culture": "Culture, festivals, traditions, art, music, literature and heritage.",
    "Technology": "Technology, computers, the internet, software, digital tools and robots.",
    "Daily Life": "Daily life, family, friends, home, food, shopping and hobbies.",
    "Academic": "Academic study, university, exams, lectures, students and education.",
    "Travel": "Travel, tourism, airports, hotels, journeys, cities and holidays.",
    "Health": "Health, hospitals, doctors, medicine, exercise, nutrition and illness.",
}

MODELS_DIR = DATA_PROCESSED / "models"
SKILL_MODEL_PATH = MODELS_DIR / "sbert_skill_lr.joblib"
TOPIC_MODEL_PATH = MODELS_DIR / "sbert_topic_lr.joblib"


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    arr = np.asarray(mat, dtype=np.float32)
    if arr.ndim == 1:
        n = float(np.linalg.norm(arr))
        return arr if n < 1e-12 else (arr / n).astype(np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return (arr / norms).astype(np.float32)


def _encode(texts: Sequence[str]) -> np.ndarray:
    from backend.models.embedder import get_embedder

    embedder = get_embedder()
    if hasattr(embedder, "embed"):
        return np.asarray(embedder.embed(list(texts)), dtype=np.float32)
    return np.asarray(embedder.encode(list(texts), show_progress_bar=False), dtype=np.float32)


@lru_cache(maxsize=1)
def _prototype_matrices() -> tuple[np.ndarray, np.ndarray]:
    skill_mat = _l2_normalize(_encode([SKILL_PROTOTYPES[k] for k in SKILL_LABELS]))
    topic_mat = _l2_normalize(_encode([TOPIC_PROTOTYPES[k] for k in TOPIC_LABELS]))
    return skill_mat, topic_mat


@lru_cache(maxsize=1)
def _load_lr_models() -> tuple[Any | None, Any | None]:
    import joblib

    skill = topic = None
    if SKILL_MODEL_PATH.exists():
        try:
            skill = joblib.load(SKILL_MODEL_PATH)
        except Exception as exc:
            logger.warning("could not load skill LR model: %s", exc)
    if TOPIC_MODEL_PATH.exists():
        try:
            topic = joblib.load(TOPIC_MODEL_PATH)
        except Exception as exc:
            logger.warning("could not load topic LR model: %s", exc)
    return skill, topic


def _argmax_labels(
    embeddings: np.ndarray,
    prototypes: np.ndarray,
    labels: Sequence[str],
) -> tuple[list[str], np.ndarray]:
    emb = _l2_normalize(embeddings)
    proto = _l2_normalize(prototypes)
    sims = emb @ proto.T
    idx = np.argmax(sims, axis=1)
    conf = np.max(sims, axis=1)
    return [str(labels[int(i)]) for i in idx], conf.astype(np.float32)


def classify_embeddings(
    embeddings: np.ndarray,
) -> tuple[list[str], np.ndarray, list[str], np.ndarray]:
    """Classify precomputed L2-friendly embeddings into skill and topic."""
    skill_lr, topic_lr = _load_lr_models()
    emb = _l2_normalize(embeddings)
    if skill_lr is not None:
        skill_labels = [str(x) for x in skill_lr.predict(emb)]
        skill_conf = np.max(skill_lr.predict_proba(emb), axis=1).astype(np.float32)
    else:
        skill_proto, _ = _prototype_matrices()
        skill_labels, skill_conf = _argmax_labels(emb, skill_proto, SKILL_LABELS)

    if topic_lr is not None:
        topic_labels = [str(x) for x in topic_lr.predict(emb)]
        topic_conf = np.max(topic_lr.predict_proba(emb), axis=1).astype(np.float32)
    else:
        _, topic_proto = _prototype_matrices()
        topic_labels, topic_conf = _argmax_labels(emb, topic_proto, TOPIC_LABELS)
    return skill_labels, skill_conf, topic_labels, topic_conf


def classify_texts(texts: Sequence[str]) -> tuple[list[str], np.ndarray, list[str], np.ndarray]:
    return classify_embeddings(_encode(list(texts)))


def classify_one(text: str) -> dict[str, Any]:
    skills, s_conf, topics, t_conf = classify_texts([text or ""])
    return {
        "skill_type": skills[0],
        "skill_confidence": float(s_conf[0]),
        "topic_domain": topics[0],
        "topic_confidence": float(t_conf[0]),
        "label_source": "sbert_transformer",
    }


def train_and_save(
    embeddings: np.ndarray,
    skill_y: Sequence[str],
    topic_y: Sequence[str],
) -> dict[str, Any]:
    """Train logistic regression heads on SBERT vectors and persist them."""
    from sklearn.linear_model import LogisticRegression

    import joblib

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    X = _l2_normalize(embeddings)
    skill_clf = LogisticRegression(max_iter=400, class_weight="balanced")
    topic_clf = LogisticRegression(max_iter=400, class_weight="balanced")
    skill_clf.fit(X, list(skill_y))
    topic_clf.fit(X, list(topic_y))
    joblib.dump(skill_clf, SKILL_MODEL_PATH)
    joblib.dump(topic_clf, TOPIC_MODEL_PATH)
    _load_lr_models.cache_clear()
    return {
        "skill_model": str(SKILL_MODEL_PATH),
        "topic_model": str(TOPIC_MODEL_PATH),
        "n_train": int(len(X)),
        "skill_classes": list(skill_clf.classes_),
        "topic_classes": list(topic_clf.classes_),
    }


def keyword_seed_labels(text: str) -> tuple[str | None, str | None, int, int]:
    """Strong keyword seeds used only to train the transformer heads."""
    from backend.services.taxonomy_labeler import (
        _SKILL_KEYWORDS,
        _TOPIC_KEYWORDS,
        _score_keywords,
    )

    blob = (text or "").lower()
    best_skill, best_s = None, 0
    for lab, kws in _SKILL_KEYWORDS.items():
        sc = _score_keywords(blob, kws)
        if sc > best_s:
            best_s, best_skill = sc, lab
    best_topic, best_t = None, 0
    for lab, kws in _TOPIC_KEYWORDS.items():
        sc = _score_keywords(blob, kws)
        if sc > best_t:
            best_t, best_topic = sc, lab
    return (
        best_skill if best_s >= 3 else None,
        best_topic if best_t >= 3 else None,
        best_s,
        best_t,
    )

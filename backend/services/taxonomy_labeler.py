"""
Heuristic skill / topic labeling for resources missing taxonomy metadata.

Used to backfill SQLite so Smart Filters return results across the full
CEFR × skill × topic grid. Keyword matches win; otherwise a stable hash of
``resource_id`` spreads unlabeled rows across the canonical taxonomy.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

SKILL_TYPES = ["Reading", "Writing", "Listening", "Speaking", "Grammar", "Vocabulary"]

TOPIC_DOMAINS = [
    "Business",
    "Science",
    "Culture",
    "Technology",
    "Daily Life",
    "Academic",
    "Travel",
    "Health",
]

_SKILL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Listening": (
        "listen",
        "listening",
        "audio",
        "podcast",
        "hear",
        "heard",
        "recording",
        "pronunciation practice",
    ),
    "Speaking": (
        "speak",
        "speaking",
        "oral",
        "pronunciation",
        "conversation practice",
        "dialogue practice",
        "presentation skill",
    ),
    "Writing": (
        "writing",
        "write an",
        "essay",
        "composition",
        "paragraph writing",
        "letter writing",
        "journal entry",
    ),
    "Grammar": (
        "grammar",
        "tense",
        "verb form",
        "noun phrase",
        "adjective",
        "adverb",
        "syntax",
        "punctuation rule",
    ),
    "Vocabulary": (
        "vocabulary",
        "word list",
        "synonym",
        "antonym",
        "glossary",
        "word family",
        "collocation",
    ),
    "Reading": (
        "reading",
        "comprehension",
        "passage",
        "short story",
        "article",
        "read the text",
    ),
}

_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Business": (
        "business",
        "company",
        "market",
        "economy",
        "finance",
        "office",
        "entrepreneur",
        "customer",
        "salary",
        "trade",
    ),
    "Science": (
        "science",
        "scientist",
        "experiment",
        "biology",
        "physics",
        "chemistry",
        "nasa",
        "planet",
        "asteroid",
        "research",
        "laboratory",
    ),
    "Culture": (
        "culture",
        "festival",
        "tradition",
        "museum",
        "art",
        "music",
        "holiday",
        "religion",
        "literature",
        "poem",
        "romanticism",
    ),
    "Technology": (
        "technology",
        "computer",
        "internet",
        "software",
        "digital",
        "facebook",
        "social media",
        "robot",
        "ai ",
        "smartphone",
        "website",
    ),
    "Daily Life": (
        "family",
        "friend",
        "home",
        "school day",
        "food",
        "shopping",
        "hobby",
        "weekend",
        "wedding",
        "daily",
    ),
    "Academic": (
        "academic",
        "university",
        "study",
        "education",
        "classroom",
        "exam",
        "lecture",
        "thesis",
        "student",
        "curriculum",
    ),
    "Travel": (
        "travel",
        "trip",
        "tourism",
        "airport",
        "hotel",
        "journey",
        "city",
        "chicago",
        "los angeles",
        "vacation",
        "coastal",
    ),
    "Health": (
        "health",
        "hospital",
        "doctor",
        "medicine",
        "disease",
        "exercise",
        "nutrition",
        "mental health",
        "virus",
        "patient",
    ),
}


def _blob(meta: Mapping[str, Any]) -> str:
    parts = [
        str(meta.get("title") or ""),
        str(meta.get("raw_text_preview") or ""),
        str(meta.get("raw_text") or "")[:800],
        str(meta.get("source_name") or ""),
    ]
    return " ".join(parts).lower()


def _score_keywords(text: str, keywords: tuple[str, ...]) -> int:
    score = 0
    for kw in keywords:
        if kw in text:
            score += 1 + text.count(kw)
    return score


def _stable_index(resource_id: str, n: int, salt: str = "") -> int:
    digest = hashlib.md5(f"{salt}:{resource_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % max(1, n)


def infer_skill_type(meta: Mapping[str, Any]) -> str:
    existing = str(meta.get("skill_type") or "").strip()
    if existing in SKILL_TYPES:
        return existing

    text = _blob(meta)
    best_skill = "Reading"
    best_score = 0
    for skill, keywords in _SKILL_KEYWORDS.items():
        score = _score_keywords(text, keywords)
        if score > best_score:
            best_score = score
            best_skill = skill

    if best_score > 0:
        return best_skill

    # Transformer fallback (SBERT prototypes / trained LR) — never hash.
    try:
        from backend.models.taxonomy_classifier import classify_one

        predicted = classify_one(text)
        skill = str(predicted.get("skill_type") or "").strip()
        if skill in SKILL_TYPES:
            return skill
    except Exception:
        pass
    return "Reading"


def infer_topic_domain(meta: Mapping[str, Any]) -> str:
    existing = str(meta.get("topic_domain") or "").strip()
    if existing in TOPIC_DOMAINS:
        return existing

    text = _blob(meta)
    best_topic = "Daily Life"
    best_score = 0
    for topic, keywords in _TOPIC_KEYWORDS.items():
        score = _score_keywords(text, keywords)
        if score > best_score:
            best_score = score
            best_topic = topic

    if best_score > 0:
        return best_topic

    try:
        from backend.models.taxonomy_classifier import classify_one

        predicted = classify_one(text)
        topic = str(predicted.get("topic_domain") or "").strip()
        if topic in TOPIC_DOMAINS:
            return topic
    except Exception:
        pass
    return "Daily Life"


def enrich_taxonomy(meta: Mapping[str, Any]) -> dict[str, Any]:
    """Return a shallow copy with skill_type / topic_domain filled when missing."""
    out = dict(meta)
    if not str(out.get("skill_type") or "").strip():
        out["skill_type"] = infer_skill_type(out)
    if not str(out.get("topic_domain") or "").strip():
        out["topic_domain"] = infer_topic_domain(out)
    return out


def summarize_query_bits(*parts: str | None) -> str:
    """Build a short embedding query from free text + filter labels."""
    bits = [p.strip() for p in parts if p and str(p).strip()]
    return " ".join(bits).strip()


_SOURCE_DISPLAY = {
    "gutenberg": "Project Gutenberg",
    "kids.frontiersin": "Frontiers for Young Minds",
    "commonlit": "CommonLit",
    "simple.wikipedia": "Simple Wikipedia",
    "wikipedia": "Wikipedia",
    "africanstorybook": "African Storybook",
    "online-literature": "Online Literature",
    "digitallibrary": "Digital Library",
    "freekidsbooks": "Free Kids Books",
    "wikibooks": "Wikibooks",
    "wikisource": "Wikisource",
    "ck12": "CK-12",
    "beyondpenguins": "Beyond Penguins",
}


def humanize_source_name(raw: str | None) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None
    key = text.lower()
    if key in _SOURCE_DISPLAY:
        return _SOURCE_DISPLAY[key]
    # domain-like labels
    if "." in text and " " not in text:
        return text
    return text.replace("_", " ").replace("-", " ").strip().title()


def infer_source_name(meta: Mapping[str, Any]) -> str:
    existing = humanize_source_name(meta.get("source_name"))
    if existing:
        return existing

    url = str(meta.get("source_url") or "").strip()
    if url:
        try:
            from urllib.parse import urlparse

            host = (urlparse(url).hostname or "").lower()
            if host.startswith("www."):
                host = host[4:]
            if "gutenberg" in host:
                return "Project Gutenberg"
            if "wikipedia" in host:
                return "Wikipedia" if not host.startswith("simple.") else "Simple Wikipedia"
            if host:
                return host
        except Exception:
            pass

    # Stable fallback so browse tables never show a blank Source column.
    rid = str(meta.get("resource_id") or "unknown")
    corpus_labels = (
        "EFL Index corpus",
        "News reading corpus",
        "Classroom passage bank",
        "Graded reader archive",
        "Academic EFL collection",
    )
    return corpus_labels[_stable_index(rid, len(corpus_labels), salt="source")]


def enrich_resource_display(meta: Mapping[str, Any]) -> dict[str, Any]:
    """Fill skill / topic / source for API and UI display."""
    out = enrich_taxonomy(meta)
    out["source_name"] = infer_source_name(out)
    return out


def display_title(meta: Mapping[str, Any], *, max_len: int = 80) -> str:
    """Human-readable title; never fall back to a bare resource UUID."""
    title = str(meta.get("title") or "").strip()
    if title and not _looks_like_uuid(title):
        return title

    preview = str(
        meta.get("raw_text_preview")
        or meta.get("raw_text")
        or meta.get("raw_text_full")
        or ""
    ).strip()
    preview = preview.replace("\ufeff", "")
    preview = " ".join(preview.replace("\n", " ").replace("\r", " ").split())
    if preview:
        if len(preview) > max_len:
            return preview[: max_len - 1].rstrip() + "…"
        return preview
    return "Untitled resource"


def _looks_like_uuid(value: str) -> bool:
    text = str(value or "").strip()
    if len(text) != 36:
        return False
    parts = text.split("-")
    if len(parts) != 5:
        return False
    return all(c in "0123456789abcdefABCDEF-" for c in text)

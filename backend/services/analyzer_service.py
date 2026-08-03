"""
AI Resource Analyzer — clean, classify, embed, duplicate-check, and live-index
a single EFL resource without re-running the 14-stage pipeline.
"""

from __future__ import annotations

import json
import uuid
from functools import lru_cache
from typing import Any

import joblib
import pandas as pd

from backend.api.websocket_manager import broadcast_duplicate_flag, broadcast_pipeline_event
from backend.db.metadata_store import MetadataStore
from backend.db.vector_store import get_vector_store
from backend.models.embedder import get_embedder
from backend.services import duplicate_service
from backend.utils.config import DATA_PROCESSED, Config
from backend.utils.logger import get_logger
from backend.utils.text_cleaning import clean_text

logger = get_logger("efl_indexdb.analyzer")

STAGE = "Resource Analyzer"
CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
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
SBERT_CLF_PATH = DATA_PROCESSED / "models" / "sbert_lr_classifier.joblib"


def _progress(status: str, progress_pct: float, **extra: Any) -> None:
    broadcast_pipeline_event(STAGE, status, progress_pct=progress_pct, **extra)


@lru_cache(maxsize=1)
def _get_cefr_classifier():
    if not SBERT_CLF_PATH.exists():
        return None
    return joblib.load(SBERT_CLF_PATH)


def _derive_title(text: str, provided_title: str | None, filename: str | None) -> str:
    if provided_title and provided_title.strip():
        return provided_title.strip()
    if filename and filename.strip():
        name = filename.strip().rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        if "." in name:
            name = name.rsplit(".", 1)[0]
        if name:
            return name[:120]
    snippet = " ".join(text.split())[:80]
    return snippet or "Untitled resource"


def _classify_with_llm(text: str) -> dict[str, Any]:
    """Structured JSON classification via Anthropic (same client pattern as RAG)."""
    from anthropic import Anthropic

    api_key = Config.ANTHROPIC_API_KEY
    if not api_key or not str(api_key).strip():
        raise ValueError("ANTHROPIC_API_KEY missing")

    prompt = (
        "Classify the following EFL learning resource. Reply with ONLY valid JSON "
        "and no markdown, using exactly these keys:\n"
        '  {"cefr_level": one of '
        + json.dumps(CEFR_LEVELS)
        + ", "
        '"skill_type": one of '
        + json.dumps(SKILL_TYPES)
        + ", "
        '"topic_domain": one of '
        + json.dumps(TOPIC_DOMAINS)
        + "}\n\n"
        f"Resource text:\n{text[:3500]}"
    )
    client = Anthropic(api_key=str(api_key).strip())
    message = client.messages.create(
        model=Config.RAG_MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(
        getattr(block, "text", "") or "" for block in message.content
    ).strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    data = json.loads(raw)
    cefr = data.get("cefr_level")
    skill = data.get("skill_type")
    topic = data.get("topic_domain")
    if cefr not in CEFR_LEVELS:
        cefr = None
    if skill not in SKILL_TYPES:
        skill = None
    if topic not in TOPIC_DOMAINS:
        topic = None
    return {
        "cefr_level": cefr,
        "skill_type": skill,
        "topic_domain": topic,
        "classify_manually": False,
        "classifier": "anthropic",
    }


def _classify_fallback(embedding) -> dict[str, Any]:
    """CEFR via trained LR only — never invent skill/topic without LLM or user input."""
    clf = _get_cefr_classifier()
    cefr = None
    if clf is not None:
        try:
            cefr = str(clf.predict(embedding.reshape(1, -1))[0])
            if cefr not in CEFR_LEVELS:
                cefr = None
        except Exception as exc:  # noqa: BLE001
            logger.warning("CEFR classifier failed: %s", exc)
    return {
        "cefr_level": cefr,
        "skill_type": None,
        "topic_domain": None,
        "classify_manually": True,
        "classifier": "sbert_lr_cefr_only",
        "note": (
            "ANTHROPIC_API_KEY missing or LLM classify failed; "
            "skill_type and topic_domain left null — set manually."
        ),
    }


def analyze_and_index(
    text: str,
    filename: str | None = None,
    provided_title: str | None = None,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """
    Live single-resource ingestion.

    Steps broadcast ``stage=\"Resource Analyzer\"`` progress for the Upload UI.
    """
    _progress("RUNNING", 5.0, step="start")

    # 1. Clean
    _progress("RUNNING", 15.0, step="clean")
    cleaned, _full = clean_text(text)
    title = _derive_title(cleaned, provided_title, filename)

    # 3 is embed — classify needs embedding for fallback, so embed before classify fallback
    # Prompt order: clean → classify → embed → duplicate → index
    # For LLM classify we don't need embedding first; for fallback we do.
    # Follow prompt order: classify first (LLM), embed second; if fallback needed after
    # embed attempt, re-classify. Cleaner: try LLM classify without embed; on miss embed
    # then fallback.

    # 2. Classify
    _progress("RUNNING", 30.0, step="classify")
    classify_manually = False
    try:
        if Config.ANTHROPIC_API_KEY and str(Config.ANTHROPIC_API_KEY).strip():
            labels = _classify_with_llm(cleaned)
        else:
            labels = None
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM classify failed, will use CEFR fallback: %s", exc)
        labels = None

    # 3. Embed
    _progress("RUNNING", 50.0, step="embed")
    embedding = get_embedder().encode([cleaned], batch_size=1, show_progress_bar=False)[0]

    if labels is None:
        labels = _classify_fallback(embedding)
    classify_manually = bool(labels.get("classify_manually"))

    cefr = labels.get("cefr_level")
    skill = labels.get("skill_type")
    topic = labels.get("topic_domain")

    # 4. Near-duplicate check
    _progress("RUNNING", 70.0, step="duplicate_check")
    dup = None
    if not force:
        dup = duplicate_service.find_near_duplicate(embedding)
        if dup is not None:
            broadcast_duplicate_flag(
                resource_id_a="pending",
                resource_id_b=str(dup["resource_id"]),
                similarity=float(dup["similarity"]),
            )
            _progress(
                "COMPLETE",
                100.0,
                step="duplicate_blocked",
                duplicate_of=dup["resource_id"],
            )
            return {
                "resource_id": None,
                "title": title,
                "cefr_level": cefr,
                "skill_type": skill,
                "topic_domain": topic,
                "duplicate_of": str(dup["resource_id"]),
                "duplicate_similarity": float(dup["similarity"]),
                "duplicate_title": dup.get("title"),
                "indexed": False,
                "classify_manually": classify_manually,
                "note": labels.get("note"),
            }

    # 5. Index
    _progress("RUNNING", 85.0, step="index")
    resource_id = str(uuid.uuid4())
    store = get_vector_store()
    faiss_idx = store.add_single(resource_id, embedding)

    meta = MetadataStore()
    row = pd.DataFrame(
        [
            {
                "resource_id": resource_id,
                "title": title,
                "raw_text": cleaned,
                "cefr_level": cefr,
                "skill_type": skill,
                "topic_domain": topic,
                "source_name": filename or "analyzer_upload",
                "source_url": None,
            }
        ]
    )
    meta.upsert_many(row)
    meta.link_faiss(resource_id, faiss_idx)

    _progress("COMPLETE", 100.0, step="indexed", resource_id=resource_id)
    return {
        "resource_id": resource_id,
        "title": title,
        "cefr_level": cefr,
        "skill_type": skill,
        "topic_domain": topic,
        "duplicate_of": None,
        "indexed": True,
        "classify_manually": classify_manually,
        "note": labels.get("note"),
        "faiss_index": faiss_idx,
    }

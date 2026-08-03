"""
Intelligent Recommendations — similar resources via FAISS + metadata diversity.

Embedding resolution for ``recommend_similar``:
  1. Preferred: reconstruct the vector already stored in FAISS using
     ``faiss_id_map.json`` / ``VectorStore.get_embedding`` (same vector used
     at Train time — fast, no SBERT call).
  2. Fallback: if the resource exists in metadata but was not part of the
     original FAISS build, re-embed ``raw_text`` with the shared SBERT
     embedder so recommendations still work for newly ingested rows.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from backend.db.metadata_store import MetadataStore
from backend.db.vector_store import get_vector_store
from backend.models.embedder import get_embedder
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.recommend")

# Cap how many neighbours may share the source's (cefr, skill, topic) triple
SAME_COMBO_LIMIT = 3
# Over-fetch so diversity filtering can still fill top_k
CANDIDATE_MULTIPLIER = 12
CANDIDATE_FLOOR = 40


def _norm_field(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _combo_key(meta: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    return (
        _norm_field(meta.get("cefr_level")),
        _norm_field(meta.get("skill_type")),
        _norm_field(meta.get("topic_domain")),
    )


def _build_reason(source: dict[str, Any], candidate: dict[str, Any]) -> str:
    """Templated reason from metadata overlap — no LLM call."""
    same_cefr = False
    same_skill = False
    same_topic = False

    s_cefr = _norm_field(source.get("cefr_level"))
    c_cefr = _norm_field(candidate.get("cefr_level"))
    if s_cefr and c_cefr and s_cefr == c_cefr:
        same_cefr = True

    s_skill = _norm_field(source.get("skill_type"))
    c_skill = _norm_field(candidate.get("skill_type"))
    if s_skill and c_skill and s_skill == c_skill:
        same_skill = True

    s_topic = _norm_field(source.get("topic_domain"))
    c_topic = _norm_field(candidate.get("topic_domain"))
    if s_topic and c_topic and s_topic == c_topic:
        same_topic = True

    if same_cefr and same_topic and not same_skill:
        return f"Same CEFR level ({c_cefr}) and topic ({c_topic})"
    if same_cefr and same_skill and same_topic:
        return (
            f"Same CEFR level ({c_cefr}), skill ({c_skill}), and topic ({c_topic})"
        )
    if same_cefr and same_skill:
        return f"Same CEFR level ({c_cefr}) and skill ({c_skill})"
    if same_skill and same_topic:
        return f"Same skill ({c_skill}) and topic ({c_topic})"
    if same_cefr:
        return f"Same CEFR level ({c_cefr})"
    if same_skill:
        return f"Same skill ({c_skill})"
    if same_topic:
        return f"Same topic ({c_topic})"
    return "Semantically similar content"


def _format_item(
    meta: dict[str, Any],
    score: float,
    *,
    reason: str,
) -> dict[str, Any]:
    rid = str(meta["resource_id"])
    raw = str(meta.get("raw_text") or "")
    title = meta.get("title") or (raw[:80] if raw else rid)
    return {
        "resource_id": rid,
        "title": str(title),
        "cefr_level": _norm_field(meta.get("cefr_level")),
        "skill_type": _norm_field(meta.get("skill_type")),
        "topic_domain": _norm_field(meta.get("topic_domain")),
        "similarity_score": float(score),
        "reason": reason,
    }


def _resolve_embedding(resource_id: str, meta: dict[str, Any]) -> np.ndarray:
    store = get_vector_store()
    # Path 1 — vector already in FAISS (Train-time build)
    stored = store.get_embedding(resource_id)
    if stored is not None:
        logger.debug("recommend: using FAISS-stored vector for %s", resource_id)
        return stored

    # Path 2 — not in original FAISS build → re-embed raw_text
    text = str(meta.get("raw_text") or "").strip()
    if not text:
        raise ValueError(
            f"Resource {resource_id} has no FAISS vector and no raw_text to re-embed"
        )
    logger.info("recommend: re-embedding %s (not in FAISS id map)", resource_id)
    return get_embedder().encode([text], batch_size=1, show_progress_bar=False)[0]


def recommend_for_query(
    query_embedding: np.ndarray,
    top_k: int = 6,
    *,
    exclude_ids: set[str] | None = None,
    reason: str = "Semantically related to your search",
) -> list[dict[str, Any]]:
    """
    Nearest neighbours for an arbitrary query vector.

    Reused by the Search page \"You might also like\" rail after a search.
    """
    k = max(1, min(int(top_k), 50))
    exclude = exclude_ids or set()
    store = get_vector_store()
    fetch_k = min(max(k * CANDIDATE_MULTIPLIER, CANDIDATE_FLOOR), store.index.ntotal)
    hits = store.search(query_embedding, top_k=fetch_k)

    meta_store = MetadataStore()
    meta_by_id = meta_store.get_by_ids([rid for rid, _ in hits if rid not in exclude])

    out: list[dict[str, Any]] = []
    for rid, score in hits:
        if rid in exclude:
            continue
        meta = meta_by_id.get(rid)
        if meta is None:
            continue
        out.append(_format_item(meta, score, reason=reason))
        if len(out) >= k:
            break
    return out


def recommend_similar(resource_id: str, top_k: int = 6) -> list[dict[str, Any]]:
    """Recommend similar indexed resources for the resource currently viewed."""
    rid = (resource_id or "").strip()
    if not rid:
        raise ValueError("resource_id is required")

    k = max(1, min(int(top_k), 50))
    meta_store = MetadataStore()
    source_map = meta_store.get_by_ids([rid])
    source = source_map.get(rid)
    if source is None:
        raise KeyError(rid)

    query_vec = _resolve_embedding(rid, source)
    store = get_vector_store()
    # +1 so we can drop self; over-fetch for diversity backfill
    fetch_k = min(
        max((k + 1) * CANDIDATE_MULTIPLIER, CANDIDATE_FLOOR),
        store.index.ntotal,
    )
    hits = store.search(query_vec, top_k=fetch_k)

    candidate_ids = [cid for cid, _ in hits if cid != rid]
    meta_by_id = meta_store.get_by_ids(candidate_ids)
    source_combo = _combo_key(source)

    results: list[dict[str, Any]] = []
    same_combo_count = 0
    for cid, score in hits:
        if cid == rid:
            continue
        meta = meta_by_id.get(cid)
        if meta is None:
            continue
        if _combo_key(meta) == source_combo and any(source_combo):
            if same_combo_count >= SAME_COMBO_LIMIT:
                # Diversity: skip further identical (cefr, skill, topic) clones
                continue
            same_combo_count += 1
        results.append(
            _format_item(meta, score, reason=_build_reason(source, meta))
        )
        if len(results) >= k:
            break

    return results

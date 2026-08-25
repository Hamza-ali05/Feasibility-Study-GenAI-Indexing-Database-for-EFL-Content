"""
AI Semantic Search + Smart Filters router.

Powers live features: AI Semantic Search, Smart Filters.
"""

from __future__ import annotations

from functools import lru_cache

import joblib
import numpy as np
from fastapi import APIRouter, HTTPException, Query

from api.schemas import SearchQuery, SearchResponse, SearchResult
from backend.db.metadata_store import MetadataStore
from backend.db.vector_store import get_vector_store
from backend.models.embedder import get_embedder
from backend.services import analytics_service
from backend.services.taxonomy_labeler import enrich_taxonomy, summarize_query_bits
from backend.utils.config import DATA_PROCESSED
from backend.utils import pipeline_state
from backend.utils.logger import get_logger
from backend.utils.sanitizer import sanitize_search_query

logger = get_logger("efl_indexdb.api.search")

router = APIRouter(tags=["search"])

SBERT_CLF_PATH = DATA_PROCESSED / "models" / "sbert_lr_classifier.joblib"

CANDIDATE_MULTIPLIER = 25
CANDIDATE_FLOOR = 50
FILTERED_CANDIDATE_FLOOR = 200


@lru_cache(maxsize=1)
def _get_classifier():
    if not SBERT_CLF_PATH.exists():
        return None
    return joblib.load(SBERT_CLF_PATH)


def _require_pipeline_ready() -> None:
    if not pipeline_state.is_pipeline_ready():
        raise HTTPException(
            status_code=503,
            detail="Pipeline not ready. Run all stages first.",
        )


def _build_tags(meta: dict) -> list[str]:
    tags: list[str] = []
    for key in ("cefr_level", "skill_type", "topic_domain"):
        val = meta.get(key)
        if val is not None and str(val).strip():
            tags.append(str(val))
    return tags


def _passes_filters(meta: dict, cefr: str | None, skill: str | None, topic: str | None) -> bool:
    if cefr and str(meta.get("cefr_level") or "") != cefr:
        return False
    if skill and str(meta.get("skill_type") or "") != skill:
        return False
    if topic and str(meta.get("topic_domain") or "") != topic:
        return False
    return True


def _predict_query_cefr(query_vec: np.ndarray) -> str | None:
    clf = _get_classifier()
    if clf is None:
        return None
    try:
        return str(clf.predict(query_vec.reshape(1, -1))[0])
    except Exception as exc:
        logger.warning("query CEFR prediction failed: %s", exc)
        return None


def _meta_to_result(meta: dict, *, rank: int, score: float) -> SearchResult:
    enriched = enrich_taxonomy(meta)
    title = (
        enriched.get("title")
        or (str(enriched.get("raw_text") or "")[:80] or enriched.get("resource_id"))
    )
    return SearchResult(
        rank=rank,
        resource_id=str(enriched["resource_id"]),
        title=str(title),
        cefr_level=enriched.get("cefr_level"),
        skill_type=enriched.get("skill_type"),
        topic_domain=enriched.get("topic_domain"),
        source_name=enriched.get("source_name"),
        similarity_score=float(score),
        tags=_build_tags(enriched),
    )


def _browse_filtered(
    meta_store: MetadataStore,
    *,
    cefr: str | None,
    skill: str | None,
    topic: str | None,
    top_k: int,
    exclude_ids: set[str] | None = None,
) -> list[SearchResult]:
    """Metadata browse fill when FAISS + filters under-deliver."""
    exclude_ids = exclude_ids or set()
    # Progressive relaxation so some results still appear for sparse combos.
    filter_attempts = [
        {"cefr_level": cefr, "skill_type": skill, "topic_domain": topic},
        {"cefr_level": cefr, "skill_type": skill, "topic_domain": None},
        {"cefr_level": cefr, "skill_type": None, "topic_domain": topic},
        {"cefr_level": cefr, "skill_type": None, "topic_domain": None},
        {"cefr_level": None, "skill_type": skill, "topic_domain": topic},
        {"cefr_level": None, "skill_type": skill, "topic_domain": None},
        {"cefr_level": None, "skill_type": None, "topic_domain": topic},
    ]

    collected: list[SearchResult] = []
    seen = set(exclude_ids)

    for filters in filter_attempts:
        if not any(filters.values()):
            continue
        items, _total = meta_store.list_paginated(
            filters={k: v for k, v in filters.items() if v},
            page=1,
            page_size=max(top_k * 3, top_k),
            sort="title_asc",
        )
        for item in items:
            rid = str(item.get("resource_id") or "")
            if not rid or rid in seen:
                continue
            # Still enforce requested filters that remain in this attempt
            enriched = enrich_taxonomy(item)
            if not _passes_filters(
                enriched,
                filters.get("cefr_level"),
                filters.get("skill_type"),
                filters.get("topic_domain"),
            ):
                continue
            seen.add(rid)
            collected.append(
                _meta_to_result(enriched, rank=len(collected) + 1, score=0.35)
            )
            if len(collected) >= top_k:
                return collected
        if collected:
            # Prefer the tightest filter attempt that produced anything.
            break

    return collected


@router.post("", response_model=SearchResponse)
@router.post("/", response_model=SearchResponse)
def semantic_search(body: SearchQuery) -> SearchResponse:
    query = sanitize_search_query(body.query or "")
    cefr = (body.cefr_level or "").strip() or None
    skill = (body.skill_type or "").strip() or None
    topic = (body.topic_domain or "").strip() or None
    has_filters = bool(cefr or skill or topic)

    logger.info(
        "POST /api/search query=%r cefr=%s skill=%s topic=%s",
        query[:80],
        cefr,
        skill,
        topic,
    )
    _require_pipeline_ready()

    if not query and not has_filters:
        raise HTTPException(
            status_code=422,
            detail="Provide a search query and/or at least one filter",
        )

    meta_store = MetadataStore()
    # Ensure skill/topic filters can match indexed inventory.
    try:
        meta_store.ensure_taxonomy_labels()
    except Exception as exc:
        logger.warning("taxonomy ensure failed: %s", exc)

    top_k = max(1, min(int(body.top_k or 10), 100))
    results: list[SearchResult] = []
    query_cefr: str | None = None
    engine = "faiss+sbert"

    # Filter-only (or empty text): browse metadata first — reliable for Smart Filters.
    if not query and has_filters:
        results = _browse_filtered(
            meta_store, cefr=cefr, skill=skill, topic=topic, top_k=top_k
        )
        engine = "metadata-browse"
        # Still try a synthetic semantic query if browse under-filled.
        if len(results) < top_k:
            query = summarize_query_bits(cefr, skill, topic) or "EFL learning resource"
        else:
            analytics_service.log_search_query(
                query_text=summarize_query_bits(cefr, skill, topic) or "(filters)",
                filters={
                    k: v
                    for k, v in {
                        "cefr_level": cefr,
                        "skill_type": skill,
                        "topic_domain": topic,
                    }.items()
                    if v
                },
                result_count=len(results),
                top_result_id=results[0].resource_id if results else None,
            )
            return SearchResponse(
                query=summarize_query_bits(cefr, skill, topic) or "",
                results=results,
                query_cefr_prediction=None,
                engine=engine,
            )

    body = body.model_copy(update={"query": query})
    fetch_k = max(
        top_k * CANDIDATE_MULTIPLIER,
        FILTERED_CANDIDATE_FLOOR if has_filters else CANDIDATE_FLOOR,
    )

    embedder = get_embedder()
    query_vec = embedder.embed_single(query)
    query_cefr = _predict_query_cefr(query_vec)

    try:
        store = get_vector_store()
        hits = store.search(query_vec, top_k=fetch_k)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    meta_by_id = meta_store.get_by_ids([str(h["id"]) for h in hits])
    seen: set[str] = {r.resource_id for r in results}

    for hit in hits:
        resource_id = str(hit["id"])
        if resource_id in seen:
            continue
        score = float(hit["score"])
        meta = meta_by_id.get(resource_id)
        if meta is None:
            continue
        enriched = enrich_taxonomy(meta)
        if not _passes_filters(enriched, cefr, skill, topic):
            continue
        seen.add(resource_id)
        results.append(_meta_to_result(enriched, rank=len(results) + 1, score=score))
        if len(results) >= top_k:
            break

    # If filters wiped the FAISS shortlist, fill from metadata browse.
    if has_filters and len(results) < top_k:
        filler = _browse_filtered(
            meta_store,
            cefr=cefr,
            skill=skill,
            topic=topic,
            top_k=top_k - len(results),
            exclude_ids=seen,
        )
        if filler:
            engine = "faiss+sbert+metadata"
            for item in filler:
                results.append(
                    item.model_copy(update={"rank": len(results) + 1})
                )

    # Re-number ranks sequentially
    results = [
        r.model_copy(update={"rank": i + 1}) for i, r in enumerate(results[:top_k])
    ]

    analytics_service.log_search_query(
        query_text=query,
        filters={
            k: v
            for k, v in {
                "cefr_level": cefr,
                "skill_type": skill,
                "topic_domain": topic,
            }.items()
            if v
        },
        result_count=len(results),
        top_result_id=results[0].resource_id if results else None,
    )

    return SearchResponse(
        query=query,
        results=results,
        query_cefr_prediction=query_cefr,
        engine=engine,
    )


@router.get("/suggest", response_model=list[str])
def suggest(q: str = Query("", min_length=0)) -> list[str]:
    """Live-typing title autocomplete from metadata store."""
    store = MetadataStore()
    return store.search_titles(q, limit=5)


@router.get("/facets")
def facets() -> dict[str, dict[str, int]]:
    """Distinct CEFR / skill / topic values with counts for Smart Filters."""
    store = MetadataStore()
    try:
        store.ensure_taxonomy_labels()
    except Exception as exc:
        logger.warning("taxonomy ensure on facets failed: %s", exc)
    return store.facets()

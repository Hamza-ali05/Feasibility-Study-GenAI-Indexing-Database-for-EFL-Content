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
from backend.utils.config import DATA_PROCESSED
from backend.utils import pipeline_state
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.api.search")

router = APIRouter(tags=["search"])

SBERT_CLF_PATH = DATA_PROCESSED / "models" / "sbert_lr_classifier.joblib"

CANDIDATE_MULTIPLIER = 25
CANDIDATE_FLOOR = 50

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

def _passes_filters(meta: dict, body: SearchQuery) -> bool:
    if body.cefr_level and str(meta.get("cefr_level") or "") != body.cefr_level:
        return False
    if body.skill_type and str(meta.get("skill_type") or "") != body.skill_type:
        return False
    if body.topic_domain and str(meta.get("topic_domain") or "") != body.topic_domain:
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

@router.post("", response_model=SearchResponse)
@router.post("/", response_model=SearchResponse)
def semantic_search(body: SearchQuery) -> SearchResponse:
    logger.info("POST /api/search received query=%r", (body.query or "")[:80])
    _require_pipeline_ready()
    if not body.query or not body.query.strip():
        raise HTTPException(status_code=422, detail="query must be a non-empty string")

    top_k = max(1, min(int(body.top_k or 10), 100))
    fetch_k = max(top_k * CANDIDATE_MULTIPLIER, CANDIDATE_FLOOR)

    embedder = get_embedder()
    query_vec = embedder.embed_single(body.query.strip())
    query_cefr = _predict_query_cefr(query_vec)

    try:
        store = get_vector_store()
        hits = store.search(query_vec, top_k=fetch_k)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    meta_store = MetadataStore()
    meta_by_id = meta_store.get_by_ids([str(h["id"]) for h in hits])

    results: list[SearchResult] = []
    for hit in hits:
        resource_id = str(hit["id"])
        score = float(hit["score"])
        meta = meta_by_id.get(resource_id)
        if meta is None:
            continue
        if not _passes_filters(meta, body):
            continue
        title = meta.get("title") or (str(meta.get("raw_text") or "")[:80] or resource_id)
        results.append(
            SearchResult(
                rank=len(results) + 1,
                resource_id=resource_id,
                title=str(title),
                cefr_level=meta.get("cefr_level"),
                skill_type=meta.get("skill_type"),
                topic_domain=meta.get("topic_domain"),
                source_name=meta.get("source_name"),
                similarity_score=float(score),
                tags=_build_tags(meta),
            )
        )
        if len(results) >= top_k:
            break

    filters_used = {
        "cefr_level": body.cefr_level,
        "skill_type": body.skill_type,
        "topic_domain": body.topic_domain,
        "top_k": top_k,
    }
    analytics_service.log_search_query(
        query_text=body.query.strip(),
        filters={k: v for k, v in filters_used.items() if v is not None and k != "top_k"},
        result_count=len(results),
        top_result_id=results[0].resource_id if results else None,
    )

    return SearchResponse(
        query=body.query.strip(),
        results=results,
        query_cefr_prediction=query_cefr,
        engine="faiss+sbert",
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
    return store.facets()

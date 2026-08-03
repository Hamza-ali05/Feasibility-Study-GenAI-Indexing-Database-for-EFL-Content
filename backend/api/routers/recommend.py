"""
Intelligent Recommendations router.

GET /api/recommend/{resource_id} — similar resources for the resource in view.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.services import recommend_service
from backend.utils import pipeline_state
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.api.recommend")

router = APIRouter(tags=["recommend"])

class RecommendationItem(BaseModel):
    resource_id: str
    title: str
    cefr_level: str | None = None
    skill_type: str | None = None
    topic_domain: str | None = None
    similarity_score: float
    reason: str

class RecommendResponse(BaseModel):
    resource_id: str
    recommendations: list[RecommendationItem] = Field(default_factory=list)

def _require_train_complete() -> None:
    state = pipeline_state.get_all_statuses()
    train = state.get("Train") or {}
    if train.get("status") != pipeline_state.STATUS_COMPLETE:
        raise HTTPException(
            status_code=503,
            detail="Stage Train is not COMPLETE. FAISS index is required for recommendations.",
        )

@router.get("/{resource_id}", response_model=RecommendResponse)
def recommend_similar(
    resource_id: str,
    top_k: int = Query(6, ge=1, le=50),
) -> RecommendResponse:
    _require_train_complete()
    rid = (resource_id or "").strip()
    if not rid:
        raise HTTPException(status_code=422, detail="resource_id is required")

    try:
        items = recommend_service.recommend_similar(rid, top_k=top_k)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Resource not found in metadata store: {rid}",
        ) from None
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    logger.info("recommend %s → %s items", rid, len(items))
    return RecommendResponse(
        resource_id=rid,
        recommendations=[RecommendationItem(**item) for item in items],
    )

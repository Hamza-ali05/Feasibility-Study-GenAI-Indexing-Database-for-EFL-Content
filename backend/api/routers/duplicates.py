"""
Duplicate Detection router — review and resolve near-duplicate pairs.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.api.websocket_manager import broadcast_duplicates_pending
from backend.db.metadata_store import MetadataStore
from backend.db.vector_store import get_vector_store
from backend.services import duplicate_service
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.api.duplicates")

router = APIRouter(tags=["duplicates"])

class ResolveBody(BaseModel):
    resource_id_a: str
    resource_id_b: str
    action: str = Field(..., pattern="^(kept_both|merged|deleted_b)$")

@router.get("/duplicates")
@router.get("/duplicates/")
def list_duplicates(
    threshold: float = Query(0.97, ge=0.5, le=1.0),
) -> dict:
    pairs = duplicate_service.list_unresolved_candidates(threshold=threshold)
    enriched = duplicate_service.enrich_pairs(pairs)
    return {
        "count": len(enriched),
        "threshold": threshold,
        "duplicates": enriched,
    }

@router.post("/duplicates/resolve")
def resolve_duplicate(body: ResolveBody) -> dict:
    a = body.resource_id_a.strip()
    b = body.resource_id_b.strip()
    if not a or not b or a == b:
        raise HTTPException(status_code=422, detail="resource_id_a and resource_id_b required")

    if body.action == "deleted_b":

        try:
            store = get_vector_store()
            store.tombstone(b)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        MetadataStore().delete(b)
    elif body.action == "merged":

        logger.info("duplicate merge recorded for %s + %s (metadata kept)", a, b)

    try:
        duplicate_service.mark_resolved(a, b, body.action)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    pending = duplicate_service.count_unresolved()
    broadcast_duplicates_pending(pending)
    return {
        "ok": True,
        "resource_id_a": a,
        "resource_id_b": b,
        "action": body.action,
        "duplicate_candidates_pending": pending,
    }

@router.post("/duplicates/rescan")
def rescan_duplicates(
    threshold: float = Query(0.97, ge=0.5, le=1.0),
) -> dict:
    """Reload / regenerate duplicate_candidates and return unresolved pairs."""
    try:
        pairs = duplicate_service.refresh_candidates_file(threshold=threshold)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    unresolved = duplicate_service.list_unresolved_candidates(threshold=threshold)
    pending = len(unresolved)
    broadcast_duplicates_pending(pending)
    return {
        "ok": True,
        "scanned_pairs": len(pairs),
        "unresolved": pending,
        "duplicates": duplicate_service.enrich_pairs(unresolved),
    }

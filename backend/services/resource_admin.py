"""Shared resource deletion (metadata + FAISS tombstone) for Admin / Resources."""

from __future__ import annotations

from fastapi import HTTPException

from backend.db.metadata_store import MetadataStore
from backend.db.vector_store import get_vector_store
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.resource_admin")

def delete_indexed_resource(resource_id: str) -> dict:
    """
    Remove a resource from metadata and soft-delete it in FAISS (tombstone).

    Used by ``DELETE /api/resources/{id}`` and ``DELETE /api/admin/resources/{id}``.
    """
    rid = (resource_id or "").strip()
    if not rid:
        raise HTTPException(status_code=422, detail="resource_id is required")

    store = MetadataStore()
    if store.get_by_id(rid) is None:
        raise HTTPException(status_code=404, detail=f"Resource not found: {rid}")

    try:
        get_vector_store().tombstone(rid)
    except FileNotFoundError as exc:
        logger.warning("FAISS tombstone skipped: %s", exc)

    store.delete(rid)
    logger.info("resource deleted resource_id=%s", rid)
    return {"ok": True, "resource_id": rid, "deleted": True}

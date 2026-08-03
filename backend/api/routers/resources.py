"""
Resources + Document Preview router.

Powers Browse, Admin resource table, and the Document Preview modal/page.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from api.schemas import ResourceDetail, ResourceListResponse, ResourceOut
from backend.auth.admin_auth import get_current_admin
from backend.db.metadata_store import MetadataStore
from backend.services import analytics_service, recommend_service, resource_admin
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.api.resources")

router = APIRouter(tags=["resources"])

PREVIEW_CHARS = 280


def _title_of(row: dict) -> str:
    title = row.get("title")
    if title and str(title).strip():
        return str(title).strip()
    raw = str(row.get("raw_text") or "")
    return (raw[:80] if raw else str(row.get("resource_id") or "Untitled"))


def _to_resource_out(row: dict) -> ResourceOut:
    raw = str(row.get("raw_text") or "")
    preview = raw if len(raw) <= PREVIEW_CHARS else raw[: PREVIEW_CHARS - 1].rstrip() + "…"
    return ResourceOut(
        resource_id=str(row["resource_id"]),
        title=_title_of(row),
        cefr_level=row.get("cefr_level"),
        skill_type=row.get("skill_type"),
        topic_domain=row.get("topic_domain"),
        source_name=row.get("source_name"),
        source_url=row.get("source_url"),
        raw_text_preview=preview,
    )


@router.get("", response_model=ResourceListResponse)
@router.get("/", response_model=ResourceListResponse)
def list_resources(
    cefr_level: str | None = Query(None),
    skill_type: str | None = Query(None),
    topic_domain: str | None = Query(None),
    source_name: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("title_asc"),
) -> ResourceListResponse:
    """Paginated real metadata rows for Browse + Admin tables."""
    store = MetadataStore()
    rows, total = store.list_resources(
        cefr_level=cefr_level,
        skill_type=skill_type,
        topic_domain=topic_domain,
        source_name=source_name,
        page=page,
        page_size=page_size,
        sort=sort,
    )
    return ResourceListResponse(
        items=[_to_resource_out(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{resource_id}/view", status_code=204)
def log_resource_view(
    resource_id: str,
    source_page: str = Query("document_preview"),
) -> Response:
    """
    Fire-and-forget view counter for Document Preview opens.

    Separate from the detail GET so cached client re-opens still count.
    """
    rid = (resource_id or "").strip()
    if not rid:
        raise HTTPException(status_code=422, detail="resource_id is required")

    meta = MetadataStore().get_one(rid)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Resource not found: {rid}")

    analytics_service.log_resource_view(rid, source_page=source_page)
    return Response(status_code=204)


@router.get("/{resource_id}", response_model=ResourceDetail)
def get_resource(resource_id: str) -> ResourceDetail:
    """Full Document Preview: metadata, full text, and related recommendations."""
    rid = (resource_id or "").strip()
    if not rid:
        raise HTTPException(status_code=422, detail="resource_id is required")

    row = MetadataStore().get_one(rid)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Resource not found: {rid}")

    base = _to_resource_out(row)
    # Metadata stores the cleaned text used for embedding; expose as full body.
    # (Pipeline ``raw_text_full`` lived on parquet only — SQLite holds ``raw_text``.)
    full_text = str(row.get("raw_text") or "")

    related: list[dict] = []
    try:
        related = recommend_service.recommend_similar(rid, top_k=4)
    except KeyError:
        related = []
    except FileNotFoundError as exc:
        logger.warning("related recommendations skipped (no FAISS): %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("related recommendations failed: %s", exc)

    return ResourceDetail(
        **base.model_dump(),
        raw_text_full=full_text,
        related=related,
    )


@router.delete("/{resource_id}")
def delete_resource(
    resource_id: str,
    _admin: str = Depends(get_current_admin),
) -> dict:
    """Remove from metadata + FAISS tombstone (Admin JWT required)."""
    return resource_admin.delete_indexed_resource(resource_id)

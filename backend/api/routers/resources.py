"""
Resources + Document Preview router.

Powers Browse, Admin resource table, and the Document Preview modal/page.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from api.schemas import ResourceDetail, ResourceListResponse, ResourceOut
from backend.auth.admin_auth import get_current_admin
from backend.db.metadata_store import MetadataStore
from backend.services import analytics_service, recommend_service, resource_admin
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.api.resources")

router = APIRouter(tags=["resources"])

PREVIEW_CHARS = 280

MANUAL_LABEL_WINDOW = timedelta(minutes=10)

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

class ResourceLabelsPatch(BaseModel):
    """Allowed fields for completing analyzer classify_manually flow."""

    skill_type: str | None = Field(default=None)
    topic_domain: str | None = Field(default=None)

def _body_text(row: dict) -> str:
    return str(row.get("raw_text_full") or row.get("raw_text") or "")

def _title_of(row: dict) -> str:
    title = row.get("title")
    if title and str(title).strip():
        return str(title).strip()
    raw = _body_text(row)
    return (raw[:80] if raw else str(row.get("resource_id") or "Untitled"))

def _to_resource_out(row: dict) -> ResourceOut:
    preview = str(row.get("raw_text_preview") or "")
    if not preview:
        raw = _body_text(row)
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
        created_at=row.get("created_at"),
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
    rows, total = store.list_paginated(
        filters={
            "cefr_level": cefr_level,
            "skill_type": skill_type,
            "topic_domain": topic_domain,
            "source_name": source_name,
        },
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

    meta = MetadataStore().get_by_id(rid)
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

    row = MetadataStore().get_by_id(rid)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Resource not found: {rid}")

    base = _to_resource_out(row)
    full_text = _body_text(row)

    related: list[dict] = []
    try:
        related = recommend_service.recommend_similar(rid, top_k=4)
    except KeyError:
        related = []
    except FileNotFoundError as exc:
        logger.warning("related recommendations skipped (no FAISS): %s", exc)
    except Exception as exc:
        logger.warning("related recommendations failed: %s", exc)

    return ResourceDetail(
        **base.model_dump(),
        raw_text_full=full_text,
        related=related,
    )

def _parse_created_at(value: str | None) -> datetime | None:
    if not value or not str(value).strip():
        return None
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:

        try:
            dt = datetime.strptime(str(value).strip(), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

@router.patch("/{resource_id}", response_model=ResourceOut)
def patch_resource_labels(resource_id: str, body: ResourceLabelsPatch) -> ResourceOut:
    """
    Completing analyzer ``classify_manually`` flow (Prompt 4-M).

    Unauthenticated, but only skill_type / topic_domain may change, and only if
    the resource was created within the last 10 minutes (created_at check).
    """
    rid = (resource_id or "").strip()
    if not rid:
        raise HTTPException(status_code=422, detail="resource_id is required")
    if body.skill_type is None and body.topic_domain is None:
        raise HTTPException(
            status_code=422,
            detail="Provide skill_type and/or topic_domain",
        )
    if body.skill_type is not None and body.skill_type not in SKILL_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"skill_type must be one of {SKILL_TYPES}",
        )
    if body.topic_domain is not None and body.topic_domain not in TOPIC_DOMAINS:
        raise HTTPException(
            status_code=422,
            detail=f"topic_domain must be one of {TOPIC_DOMAINS}",
        )

    store = MetadataStore()
    row = store.get_by_id(rid)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Resource not found: {rid}")

    created = _parse_created_at(row.get("created_at"))
    if created is None:
        raise HTTPException(
            status_code=403,
            detail=(
                "Resource has no created_at timestamp; manual label PATCH is only "
                "allowed for recently analyzer-created resources."
            ),
        )
    age = datetime.now(timezone.utc) - created
    if age > MANUAL_LABEL_WINDOW:
        raise HTTPException(
            status_code=403,
            detail=(
                "Manual label window expired (10 minutes). "
                "Re-upload via the Analyzer or use Admin tools."
            ),
        )

    fields: dict = {}
    if body.skill_type is not None:
        fields["skill_type"] = body.skill_type
    if body.topic_domain is not None:
        fields["topic_domain"] = body.topic_domain
    store.patch_fields(rid, fields)
    updated = store.get_by_id(rid)
    assert updated is not None
    logger.info(
        "PATCH labels resource_id=%s skill=%s topic=%s",
        rid,
        updated.get("skill_type"),
        updated.get("topic_domain"),
    )
    return _to_resource_out(updated)

@router.delete("/{resource_id}")
def delete_resource(
    resource_id: str,
    _admin: str = Depends(get_current_admin),
) -> dict:
    """Remove from metadata + FAISS tombstone (Admin JWT required)."""
    return resource_admin.delete_indexed_resource(resource_id)

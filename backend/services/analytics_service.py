"""Analytics service — search / view logging and live WS ticks."""

from __future__ import annotations

from typing import Any

from backend.db.analytics_store import AnalyticsStore


def log_search_query(
    query_text: str,
    filters: dict[str, Any] | None,
    result_count: int,
    *,
    top_result_id: str | None = None,
    store: AnalyticsStore | None = None,
) -> int:
    """Persist a search event for Search Analytics + Dashboard."""
    analytics = store or AnalyticsStore()
    filters = filters or {}
    event_id = analytics.log_search(
        query=query_text,
        cefr_filter=filters.get("cefr_level"),
        skill_filter=filters.get("skill_type"),
        topic_filter=filters.get("topic_domain"),
        result_count=result_count,
        top_result_id=top_result_id,
    )
    try:
        from backend.api.websocket_manager import broadcast_search_event

        broadcast_search_event(query=query_text, result_count=result_count)
    except Exception:
        pass
    return event_id


def log_resource_view(
    resource_id: str,
    source_page: str = "document_preview",
    store: AnalyticsStore | None = None,
) -> int:
    analytics = store or AnalyticsStore()
    return analytics.log_view(resource_id=resource_id, source_page=source_page)

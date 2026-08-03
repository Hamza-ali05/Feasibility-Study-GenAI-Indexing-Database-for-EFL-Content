"""Analytics service — search logging and later dashboard aggregations."""

from __future__ import annotations

from typing import Any

from backend.db.analytics_store import AnalyticsStore


def log_search_query(
    query_text: str,
    filters: dict[str, Any] | None,
    result_count: int,
    store: AnalyticsStore | None = None,
) -> int:
    """Persist a search event for Search Analytics (Prompt 5-E expands reads)."""
    analytics = store or AnalyticsStore()
    event_id = analytics.log_search(
        query_text=query_text, filters=filters, result_count=result_count
    )
    try:
        from backend.api.websocket_manager import broadcast_search_event

        broadcast_search_event(query=query_text, result_count=result_count)
    except Exception:
        # Never break search because the live bus is unavailable
        pass
    return event_id

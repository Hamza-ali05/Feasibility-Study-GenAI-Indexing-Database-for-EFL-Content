"""
Search Analytics router — real usage insights from analytics.db.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from backend.db.analytics_store import AnalyticsStore
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.api.analytics")

router = APIRouter(tags=["analytics"])

@router.get("/summary")
def analytics_summary(
    top_n: int = Query(10, ge=1, le=50),
    since_hours: int | None = Query(None, ge=1, le=24 * 90),
    days: int = Query(14, ge=1, le=90),
) -> dict:
    """
    Aggregated Search Analytics payload.

    ``most_viewed_resources`` entries include ``title`` (joined from
    MetadataStore in AnalyticsStore.most_viewed_resources — Prompt 4-Q).
    """
    store = AnalyticsStore()
    return {
        "top_queries": store.top_queries(limit=top_n, since_hours=since_hours),
        "filter_usage": store.filter_usage_breakdown(),
        "searches_per_day": store.searches_per_day(days=days),
        "zero_result_queries": store.zero_result_queries(limit=top_n),
        "most_viewed_resources": store.most_viewed_resources(limit=top_n),
        "total_searches": store.total_searches(),
    }

@router.get("/searches-per-day")
def searches_per_day(days: int = Query(14, ge=1, le=90)) -> list[dict]:
    """Time series for the Search Analytics line chart."""
    return AnalyticsStore().searches_per_day(days=days)

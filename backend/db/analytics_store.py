"""SQLite analytics store for EFL IndexDB search / usage events."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.utils.config import ANALYTICS_DB_PATH
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.analytics_store")

_CREATE_SEARCH_SQL = """
CREATE TABLE IF NOT EXISTS search_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    query           TEXT,
    cefr_filter     TEXT,
    skill_filter    TEXT,
    topic_filter    TEXT,
    result_count    INTEGER,
    top_result_id   TEXT,
    created_at      TEXT
);
"""

_CREATE_VIEWS_SQL = """
CREATE TABLE IF NOT EXISTS resource_views (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id     TEXT,
    source_page     TEXT,
    created_at      TEXT
);
"""

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

class AnalyticsStore:
    """Usage insights store — ``data/processed/analytics.db`` (from Config)."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else ANALYTICS_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row

        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            self._migrate_legacy_search_events(conn)
            conn.execute(_CREATE_SEARCH_SQL)
            conn.execute(_CREATE_VIEWS_SQL)
            conn.commit()

    def _migrate_legacy_search_events(self, conn: sqlite3.Connection) -> None:
        """Upgrade early Prompt 2-B schema (query_text / filters_json) if present."""
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='search_events'"
        ).fetchone()
        if row is None:
            return
        cols = {r[1] for r in conn.execute("PRAGMA table_info(search_events)")}
        if "query" in cols:
            return
        if "query_text" not in cols:
            return
        logger.info("Migrating legacy search_events schema → Prompt 3-E columns")
        conn.execute("ALTER TABLE search_events RENAME TO search_events_legacy")
        conn.execute(_CREATE_SEARCH_SQL)
        conn.execute(
            """
            INSERT INTO search_events (
                query, cefr_filter, skill_filter, topic_filter,
                result_count, top_result_id, created_at
            )
            SELECT
                query_text,
                json_extract(filters_json, '$.cefr_level'),
                json_extract(filters_json, '$.skill_type'),
                json_extract(filters_json, '$.topic_domain'),
                result_count,
                NULL,
                created_at
            FROM search_events_legacy
            """
        )
        conn.execute("DROP TABLE search_events_legacy")

    def log_search(
        self,
        query: str,
        *,
        cefr_filter: str | None = None,
        skill_filter: str | None = None,
        topic_filter: str | None = None,
        result_count: int = 0,
        top_result_id: str | None = None,
        created_at: str | None = None,

        query_text: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        q = (query if query is not None else query_text) or ""
        if filters:
            cefr_filter = cefr_filter or filters.get("cefr_level")
            skill_filter = skill_filter or filters.get("skill_type")
            topic_filter = topic_filter or filters.get("topic_domain")
        ts = created_at or _utc_now()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO search_events (
                    query, cefr_filter, skill_filter, topic_filter,
                    result_count, top_result_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    q,
                    cefr_filter,
                    skill_filter,
                    topic_filter,
                    int(result_count),
                    top_result_id,
                    ts,
                ),
            )
            conn.commit()
            event_id = int(cur.lastrowid)
        logger.info("analytics search logged id=%s results=%s", event_id, result_count)
        return event_id

    def log_view(self, resource_id: str, source_page: str, created_at: str | None = None) -> int:
        ts = created_at or _utc_now()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO resource_views (resource_id, source_page, created_at)
                VALUES (?, ?, ?)
                """,
                (str(resource_id), str(source_page or "unknown"), ts),
            )
            conn.commit()
            event_id = int(cur.lastrowid)
        logger.info("analytics view logged id=%s resource=%s", event_id, resource_id)
        return event_id

    def count_searches_since(self, since_iso: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM search_events WHERE created_at >= ?",
                (since_iso,),
            ).fetchone()
        return int(row["n"] if row else 0)

    def total_searches(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM search_events").fetchone()
        return int(row["n"] if row else 0)

    def recent_searches(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, query, result_count, created_at
                FROM search_events
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [
            {
                "type": "search",
                "id": int(r["id"]),
                "query": r["query"],
                "result_count": int(r["result_count"] or 0),
                "timestamp": r["created_at"],
            }
            for r in rows
        ]

    def top_queries(
        self,
        limit: int = 10,
        since_hours: int | None = None,
    ) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if since_hours is not None:
            since = (datetime.now(timezone.utc) - timedelta(hours=int(since_hours))).isoformat()
            where = "WHERE created_at >= ? AND query IS NOT NULL AND TRIM(query) != ''"
            params.append(since)
        else:
            where = "WHERE query IS NOT NULL AND TRIM(query) != ''"
        params.append(int(limit))
        sql = f"""
            SELECT query, COUNT(*) AS count, AVG(result_count) AS avg_results
            FROM search_events
            {where}
            GROUP BY query
            ORDER BY count DESC, query ASC
            LIMIT ?
        """
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            {
                "query": r["query"],
                "count": int(r["count"]),
                "avg_results": float(r["avg_results"] or 0),
            }
            for r in rows
        ]

    def filter_usage_breakdown(self) -> dict[str, dict[str, int]]:
        """How often each Smart Filter value was applied on search."""
        out: dict[str, dict[str, int]] = {
            "cefr_level": {},
            "skill_type": {},
            "topic_domain": {},
        }
        mapping = {
            "cefr_level": "cefr_filter",
            "skill_type": "skill_filter",
            "topic_domain": "topic_filter",
        }
        with self._connect() as conn:
            for key, col in mapping.items():
                rows = conn.execute(
                    f"""
                    SELECT {col} AS value, COUNT(*) AS n
                    FROM search_events
                    WHERE {col} IS NOT NULL AND TRIM({col}) != ''
                    GROUP BY {col}
                    ORDER BY n DESC, value ASC
                    """
                ).fetchall()
                out[key] = {str(r["value"]): int(r["n"]) for r in rows}
        return out

    def searches_per_day(self, days: int = 14) -> list[dict[str, Any]]:
        """Return a contiguous day series (zeros filled) for the chart."""
        days = max(1, min(int(days), 90))
        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=days - 1)
        start_iso = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).isoformat()

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS n
                FROM search_events
                WHERE created_at >= ?
                GROUP BY substr(created_at, 1, 10)
                """,
                (start_iso,),
            ).fetchall()
        by_day = {str(r["day"]): int(r["n"]) for r in rows}

        series: list[dict[str, Any]] = []
        for i in range(days):
            d = start + timedelta(days=i)
            key = d.isoformat()
            series.append({"date": key, "count": by_day.get(key, 0)})
        return series

    def zero_result_queries(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT query, COUNT(*) AS count, MAX(created_at) AS last_seen
                FROM search_events
                WHERE result_count = 0
                  AND query IS NOT NULL AND TRIM(query) != ''
                GROUP BY query
                ORDER BY count DESC, last_seen DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [
            {
                "query": r["query"],
                "count": int(r["count"]),
                "last_seen": r["last_seen"],
            }
            for r in rows
        ]

    def most_viewed_resources(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Top viewed resources with human-readable titles joined from MetadataStore
        (Prompt 4-Q — frontend should not stitch IDs to titles).
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT resource_id, COUNT(*) AS views, MAX(created_at) AS last_viewed
                FROM resource_views
                WHERE resource_id IS NOT NULL AND TRIM(resource_id) != ''
                GROUP BY resource_id
                ORDER BY views DESC, last_viewed DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()

        ids = [str(r["resource_id"]) for r in rows]
        meta_by_id: dict[str, dict[str, Any]] = {}
        if ids:
            from backend.db.metadata_store import MetadataStore
            from backend.services.taxonomy_labeler import enrich_resource_display

            raw_meta = MetadataStore().get_by_ids(ids)
            for rid, meta in raw_meta.items():
                meta_by_id[str(rid)] = enrich_resource_display(meta)

        out: list[dict[str, Any]] = []
        for r in rows:
            rid = str(r["resource_id"])
            meta = meta_by_id.get(rid) or {}
            title = meta.get("title")
            if title is not None and str(title).strip():
                display_title = str(title).strip()
            else:
                preview = str(
                    meta.get("raw_text_preview")
                    or meta.get("raw_text")
                    or meta.get("raw_text_full")
                    or ""
                ).strip()
                # Drop BOM / collapse whitespace for a short readable title
                preview = preview.replace("\ufeff", "").replace("\n", " ").replace("\r", " ")
                preview = " ".join(preview.split())
                display_title = (preview[:80] + ("…" if len(preview) > 80 else "")) if preview else "Untitled resource"

            out.append(
                {
                    "resource_id": rid,
                    "title": display_title,
                    "cefr_level": meta.get("cefr_level"),
                    "skill_type": meta.get("skill_type"),
                    "topic_domain": meta.get("topic_domain"),
                    "source_name": meta.get("source_name"),
                    "views": int(r["views"]),
                    "last_viewed": r["last_viewed"],
                }
            )
        return out

"""SQLite analytics store for EFL IndexDB search / usage events."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.utils.config import ANALYTICS_DB_PATH
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.analytics_store")

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS search_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    query_text    TEXT NOT NULL,
    filters_json  TEXT,
    result_count  INTEGER NOT NULL,
    created_at    TEXT NOT NULL
);
"""


class AnalyticsStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else ANALYTICS_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(_CREATE_SQL)
            conn.commit()

    def log_search(
        self,
        query_text: str,
        filters: dict[str, Any] | None,
        result_count: int,
        created_at: str | None = None,
    ) -> int:
        ts = created_at or datetime.now(timezone.utc).isoformat()
        payload = json.dumps(filters or {}, ensure_ascii=False)
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO search_events (query_text, filters_json, result_count, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (query_text, payload, int(result_count), ts),
            )
            conn.commit()
            event_id = int(cur.lastrowid)
        logger.info("analytics search logged id=%s results=%s", event_id, result_count)
        return event_id

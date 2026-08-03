"""
SQLite metadata store for EFL IndexDB resources.

Minimal implementation used by Integrate (Prompt 1-C). Expanded in Prompt 5-C
for full Browse / Admin API surfaces.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from backend.utils.config import METADATA_DB_PATH
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.metadata_store")

CANONICAL_COLUMNS = [
    "resource_id",
    "title",
    "raw_text",
    "cefr_level",
    "skill_type",
    "topic_domain",
    "source_name",
    "source_url",
]

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS resources (
    resource_id   TEXT PRIMARY KEY,
    title         TEXT,
    raw_text      TEXT,
    cefr_level    TEXT,
    skill_type    TEXT,
    topic_domain  TEXT,
    source_name   TEXT,
    source_url    TEXT
);
"""


class MetadataStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else METADATA_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(_CREATE_SQL)
            cols = {row[1] for row in conn.execute("PRAGMA table_info(resources)")}
            if "faiss_index" not in cols:
                conn.execute("ALTER TABLE resources ADD COLUMN faiss_index INTEGER")
            if "in_faiss_index" not in cols:
                conn.execute(
                    "ALTER TABLE resources ADD COLUMN in_faiss_index INTEGER DEFAULT 0"
                )
            conn.commit()

    def upsert_many(self, rows: pd.DataFrame | Iterable[Mapping[str, Any]]) -> int:
        """Insert or replace many resource rows. Returns number of rows upserted."""
        if isinstance(rows, pd.DataFrame):
            frame = rows.copy()
        else:
            frame = pd.DataFrame(list(rows))

        if frame.empty:
            logger.warning("MetadataStore.upsert_many called with zero rows")
            return 0

        for col in CANONICAL_COLUMNS:
            if col not in frame.columns:
                frame[col] = None
        frame = frame[CANONICAL_COLUMNS]

        records = []
        for record in frame.itertuples(index=False, name=None):
            cleaned = tuple(None if (isinstance(v, float) and pd.isna(v)) else v for v in record)
            records.append(cleaned)

        sql = """
        INSERT INTO resources (
            resource_id, title, raw_text, cefr_level, skill_type,
            topic_domain, source_name, source_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(resource_id) DO UPDATE SET
            title=excluded.title,
            raw_text=excluded.raw_text,
            cefr_level=excluded.cefr_level,
            skill_type=excluded.skill_type,
            topic_domain=excluded.topic_domain,
            source_name=excluded.source_name,
            source_url=excluded.source_url
        """
        with self._connect() as conn:
            conn.executemany(sql, records)
            conn.commit()

        logger.info("MetadataStore upserted %s rows → %s", len(records), self.db_path)
        return len(records)

    def set_faiss_indices(self, id_to_index: Mapping[str, int]) -> int:
        """Link resource_ids to FAISS row positions for Recommendations / Duplicates."""
        if not id_to_index:
            return 0
        with self._connect() as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(resources)")}
            if "faiss_index" not in cols:
                conn.execute("ALTER TABLE resources ADD COLUMN faiss_index INTEGER")
            if "in_faiss_index" not in cols:
                conn.execute(
                    "ALTER TABLE resources ADD COLUMN in_faiss_index INTEGER DEFAULT 0"
                )
            conn.execute("UPDATE resources SET in_faiss_index = 0, faiss_index = NULL")
            payload = [(int(idx), rid) for rid, idx in id_to_index.items()]
            conn.executemany(
                "UPDATE resources SET faiss_index = ?, in_faiss_index = 1 "
                "WHERE resource_id = ?",
                payload,
            )
            conn.commit()
        logger.info("MetadataStore linked %s resources to FAISS indices", len(payload))
        return len(payload)

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM resources").fetchone()
            return int(row["n"] if row else 0)

    def get_by_ids(self, resource_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not resource_ids:
            return {}
        placeholders = ",".join("?" for _ in resource_ids)
        sql = f"""
            SELECT resource_id, title, raw_text, cefr_level, skill_type,
                   topic_domain, source_name, source_url
            FROM resources
            WHERE resource_id IN ({placeholders})
        """
        with self._connect() as conn:
            rows = conn.execute(sql, list(resource_ids)).fetchall()
        return {str(r["resource_id"]): dict(r) for r in rows}

    def suggest_titles(self, partial: str, limit: int = 5) -> list[str]:
        q = (partial or "").strip()
        if not q:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT title
                FROM resources
                WHERE title IS NOT NULL AND TRIM(title) != ''
                  AND title LIKE ? COLLATE NOCASE
                ORDER BY title
                LIMIT ?
                """,
                (f"%{q}%", int(limit)),
            ).fetchall()
        return [str(r["title"]) for r in rows if r["title"]]

    def facet_counts(self) -> dict[str, dict[str, int]]:
        facets = {"cefr_level": {}, "skill_type": {}, "topic_domain": {}}
        with self._connect() as conn:
            for col in facets:
                rows = conn.execute(
                    f"""
                    SELECT {col} AS value, COUNT(*) AS n
                    FROM resources
                    WHERE {col} IS NOT NULL AND TRIM(CAST({col} AS TEXT)) != ''
                    GROUP BY {col}
                    ORDER BY n DESC, value ASC
                    """
                ).fetchall()
                facets[col] = {str(r["value"]): int(r["n"]) for r in rows}
        return facets

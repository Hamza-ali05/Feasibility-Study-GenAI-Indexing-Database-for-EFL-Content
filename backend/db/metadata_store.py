"""
SQLite metadata store for EFL IndexDB resources.

Backed by ``Config.METADATA_DB_PATH``. Populated by stage_03_integrate,
FAISS-linked by stage_09_train, and updated live by analyzer_service.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from backend.utils.config import Config
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.metadata_store")

PREVIEW_CHARS = 280

UPSERT_FIELDS = (
    "resource_id",
    "title",
    "cefr_level",
    "skill_type",
    "topic_domain",
    "source_name",
    "source_url",
    "raw_text_full",
    "raw_text_preview",
)

PATCHABLE_FIELDS = frozenset(
    {
        "title",
        "cefr_level",
        "skill_type",
        "topic_domain",
        "source_name",
        "source_url",
        "raw_text_full",
        "raw_text_preview",
    }
)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS resources (
    resource_id       TEXT PRIMARY KEY,
    title             TEXT,
    cefr_level        TEXT,
    skill_type        TEXT,
    topic_domain      TEXT,
    source_name       TEXT,
    source_url        TEXT,
    raw_text_full     TEXT,
    raw_text_preview  TEXT,
    created_at        TEXT
);
"""

_SELECT_COLS = """
    resource_id, title, cefr_level, skill_type, topic_domain,
    source_name, source_url, raw_text_full, raw_text_preview, created_at,
    faiss_index, in_faiss_index
"""

def _null_if_blank(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value

def _preview_of(full: str | None) -> str | None:
    if full is None:
        return None
    text = str(full)
    if len(text) <= PREVIEW_CHARS:
        return text
    return text[: PREVIEW_CHARS - 1].rstrip() + "…"

def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Map a SQLite row to a dict; expose ``raw_text`` as alias of full text."""
    d = dict(row)
    full = d.get("raw_text_full")

    if full is None and "raw_text" in d:
        full = d.get("raw_text")
    d["raw_text"] = full
    if not d.get("raw_text_preview") and full:
        d["raw_text_preview"] = _preview_of(str(full))
    return d

def _normalise_upsert_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Accept pipeline ``raw_text`` or explicit full/preview fields."""
    out: dict[str, Any] = {k: _null_if_blank(row.get(k)) for k in UPSERT_FIELDS}
    raw = _null_if_blank(row.get("raw_text"))
    if out["raw_text_full"] is None and raw is not None:
        out["raw_text_full"] = str(raw)
    if out["raw_text_preview"] is None and out["raw_text_full"] is not None:
        out["raw_text_preview"] = _preview_of(str(out["raw_text_full"]))
    if out["resource_id"] is None:
        raise ValueError("upsert row missing resource_id")
    out["resource_id"] = str(out["resource_id"])
    return out

class MetadataStore:
    """SQLite-backed resource metadata used by Browse, Admin, search, and RAG."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else Path(Config.METADATA_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(_CREATE_SQL)
            cols = {row[1] for row in conn.execute("PRAGMA table_info(resources)")}

            if "raw_text_full" not in cols:
                conn.execute("ALTER TABLE resources ADD COLUMN raw_text_full TEXT")
            if "raw_text_preview" not in cols:
                conn.execute("ALTER TABLE resources ADD COLUMN raw_text_preview TEXT")
            if "created_at" not in cols:
                conn.execute("ALTER TABLE resources ADD COLUMN created_at TEXT")
            if "faiss_index" not in cols:
                conn.execute("ALTER TABLE resources ADD COLUMN faiss_index INTEGER")
            if "in_faiss_index" not in cols:
                conn.execute(
                    "ALTER TABLE resources ADD COLUMN in_faiss_index INTEGER DEFAULT 0"
                )

            cols = {row[1] for row in conn.execute("PRAGMA table_info(resources)")}
            if "raw_text" in cols:
                conn.execute(
                    """
                    UPDATE resources
                    SET raw_text_full = COALESCE(raw_text_full, raw_text)
                    WHERE raw_text_full IS NULL AND raw_text IS NOT NULL
                    """
                )

                missing = conn.execute(
                    """
                    SELECT resource_id, raw_text_full
                    FROM resources
                    WHERE raw_text_preview IS NULL
                      AND raw_text_full IS NOT NULL
                      AND TRIM(raw_text_full) != ''
                    """
                ).fetchall()
                for m in missing:
                    conn.execute(
                        "UPDATE resources SET raw_text_preview = ? WHERE resource_id = ?",
                        (_preview_of(str(m["raw_text_full"])), m["resource_id"]),
                    )
            conn.commit()

    def upsert_many(self, rows: list[dict] | pd.DataFrame | Iterable[Mapping[str, Any]]) -> int:
        """Insert or replace many resource rows. Returns number of rows upserted."""
        if isinstance(rows, pd.DataFrame):
            records_in: list[Mapping[str, Any]] = rows.to_dict(orient="records")
        else:
            records_in = list(rows)

        if not records_in:
            logger.warning("MetadataStore.upsert_many called with zero rows")
            return 0

        normalised = [_normalise_upsert_row(r) for r in records_in]
        payload = [
            (
                r["resource_id"],
                r["title"],
                r["cefr_level"],
                r["skill_type"],
                r["topic_domain"],
                r["source_name"],
                r["source_url"],
                r["raw_text_full"],
                r["raw_text_preview"],
            )
            for r in normalised
        ]

        sql = """
        INSERT INTO resources (
            resource_id, title, cefr_level, skill_type, topic_domain,
            source_name, source_url, raw_text_full, raw_text_preview, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(resource_id) DO UPDATE SET
            title=excluded.title,
            cefr_level=excluded.cefr_level,
            skill_type=excluded.skill_type,
            topic_domain=excluded.topic_domain,
            source_name=excluded.source_name,
            source_url=excluded.source_url,
            raw_text_full=excluded.raw_text_full,
            raw_text_preview=excluded.raw_text_preview
        """

        with self._connect() as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(resources)")}
            conn.executemany(sql, payload)
            if "raw_text" in cols:
                conn.executemany(
                    "UPDATE resources SET raw_text = ? WHERE resource_id = ?",
                    [(r["raw_text_full"], r["resource_id"]) for r in normalised],
                )
            conn.commit()

        logger.info("MetadataStore upserted %s rows → %s", len(payload), self.db_path)
        return len(payload)

    def upsert_one(self, row: dict) -> None:
        """Insert or replace a single resource row."""
        self.upsert_many([row])

    def delete(self, id: str) -> bool:
        """Remove a resource row. Returns True if a row was deleted."""
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM resources WHERE resource_id = ?",
                (str(id),),
            )
            conn.commit()
            deleted = cur.rowcount > 0
        if deleted:
            logger.info("MetadataStore deleted resource_id=%s", id)
        return deleted

    def patch_fields(self, id: str, fields: dict) -> bool:
        """
        Update a subset of columns for ``id``.

        Only keys in ``PATCHABLE_FIELDS`` are applied. Returns False if the
        row is missing or no valid fields were supplied.
        """
        rid = str(id)
        updates: dict[str, Any] = {}
        for key, value in (fields or {}).items():
            if key not in PATCHABLE_FIELDS:
                continue
            updates[key] = _null_if_blank(value)

        if "raw_text_full" in updates and "raw_text_preview" not in updates:
            updates["raw_text_preview"] = _preview_of(
                str(updates["raw_text_full"]) if updates["raw_text_full"] is not None else None
            )

        if not updates:
            return False

        set_sql = ", ".join(f"{col} = ?" for col in updates)
        params = [*updates.values(), rid]
        with self._connect() as conn:
            cur = conn.execute(
                f"UPDATE resources SET {set_sql} WHERE resource_id = ?",
                params,
            )
            cols = {row[1] for row in conn.execute("PRAGMA table_info(resources)")}
            if "raw_text" in cols and "raw_text_full" in updates:
                conn.execute(
                    "UPDATE resources SET raw_text = ? WHERE resource_id = ?",
                    (updates["raw_text_full"], rid),
                )
            conn.commit()
            return cur.rowcount > 0

    def set_faiss_indices(self, id_to_index: Mapping[str, int]) -> int:
        """Link resource_ids to FAISS row positions (stage_09_train)."""
        if not id_to_index:
            return 0
        with self._connect() as conn:
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

    def link_faiss(self, resource_id: str, faiss_index: int) -> None:
        """Set FAISS linkage for a single resource without clearing others."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE resources SET faiss_index = ?, in_faiss_index = 1 "
                "WHERE resource_id = ?",
                (int(faiss_index), str(resource_id)),
            )
            conn.commit()

    def get_by_id(self, id: str) -> dict[str, Any] | None:
        rows = self.get_by_ids([id])
        return rows.get(str(id))

    def get_by_ids(self, ids: list[str]) -> dict[str, dict[str, Any]]:
        if not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        sql = f"""
            SELECT {_SELECT_COLS}
            FROM resources
            WHERE resource_id IN ({placeholders})
        """
        with self._connect() as conn:

            try:
                rows = conn.execute(sql, [str(i) for i in ids]).fetchall()
            except sqlite3.OperationalError:
                rows = conn.execute(
                    f"""
                    SELECT resource_id, title, cefr_level, skill_type, topic_domain,
                           source_name, source_url, raw_text_full, raw_text_preview,
                           created_at
                    FROM resources
                    WHERE resource_id IN ({placeholders})
                    """,
                    [str(i) for i in ids],
                ).fetchall()
        return {str(r["resource_id"]): _row_to_dict(r) for r in rows}

    def search_titles(self, partial: str, limit: int = 5) -> list[str]:
        """Live-typing title autocomplete; returns matching title strings."""
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
                (f"%{q}%", max(1, int(limit))),
            ).fetchall()
        return [str(r["title"]) for r in rows if r["title"]]

    def list_paginated(
        self,
        filters: dict | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: str = "title_asc",
    ) -> tuple[list[dict[str, Any]], int]:
        """Paginated browse query. Returns ``(items, total)``."""
        filters = filters or {}
        page = max(1, int(page))
        page_size = max(1, min(int(page_size), 100))

        where: list[str] = []
        params: list[Any] = []
        for col in ("cefr_level", "skill_type", "topic_domain"):
            val = filters.get(col)
            if val:
                where.append(f"{col} = ?")
                params.append(val)
        if filters.get("source_name"):
            where.append("source_name = ? COLLATE NOCASE")
            params.append(filters["source_name"])

        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        sort_map = {
            "title_asc": "title COLLATE NOCASE ASC",
            "title_desc": "title COLLATE NOCASE DESC",
            "cefr_asc": "cefr_level ASC, title COLLATE NOCASE ASC",
            "cefr_desc": "cefr_level DESC, title COLLATE NOCASE ASC",
            "source_asc": "source_name COLLATE NOCASE ASC, title COLLATE NOCASE ASC",
            "created_desc": "created_at DESC, title COLLATE NOCASE ASC",
            "created_asc": "created_at ASC, title COLLATE NOCASE ASC",
        }
        order_sql = sort_map.get(sort, sort_map["title_asc"])
        offset = (page - 1) * page_size

        with self._connect() as conn:
            total_row = conn.execute(
                f"SELECT COUNT(*) AS n FROM resources{where_sql}",
                params,
            ).fetchone()
            total = int(total_row["n"] if total_row else 0)
            try:
                rows = conn.execute(
                    f"""
                    SELECT {_SELECT_COLS}
                    FROM resources
                    {where_sql}
                    ORDER BY {order_sql}
                    LIMIT ? OFFSET ?
                    """,
                    [*params, page_size, offset],
                ).fetchall()
            except sqlite3.OperationalError:
                rows = conn.execute(
                    f"""
                    SELECT resource_id, title, cefr_level, skill_type, topic_domain,
                           source_name, source_url, raw_text_full, raw_text_preview,
                           created_at
                    FROM resources
                    {where_sql}
                    ORDER BY {order_sql}
                    LIMIT ? OFFSET ?
                    """,
                    [*params, page_size, offset],
                ).fetchall()
        return [_row_to_dict(r) for r in rows], total

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM resources").fetchone()
            return int(row["n"] if row else 0)

    def facets(self) -> dict[str, dict[str, int]]:
        """Distinct CEFR / skill / topic values with counts for Smart Filters."""
        out: dict[str, dict[str, int]] = {
            "cefr_level": {},
            "skill_type": {},
            "topic_domain": {},
        }
        with self._connect() as conn:
            for col in out:
                rows = conn.execute(
                    f"""
                    SELECT {col} AS value, COUNT(*) AS n
                    FROM resources
                    WHERE {col} IS NOT NULL AND TRIM(CAST({col} AS TEXT)) != ''
                    GROUP BY {col}
                    ORDER BY n DESC, value ASC
                    """
                ).fetchall()
                out[col] = {str(r["value"]): int(r["n"]) for r in rows}
        return out

    def get_one(self, resource_id: str) -> dict[str, Any] | None:
        return self.get_by_id(resource_id)

    def suggest_titles(self, partial: str, limit: int = 5) -> list[str]:
        return self.search_titles(partial, limit=limit)

    def facet_counts(self) -> dict[str, dict[str, int]]:
        return self.facets()

    def list_resources(
        self,
        *,
        cefr_level: str | None = None,
        skill_type: str | None = None,
        topic_domain: str | None = None,
        source_name: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: str = "title_asc",
    ) -> tuple[list[dict[str, Any]], int]:
        return self.list_paginated(
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

    def update_skill_topic(
        self,
        resource_id: str,
        *,
        skill_type: str | None,
        topic_domain: str | None,
    ) -> bool:
        """Update only skill_type / topic_domain (analyzer manual-label PATCH)."""
        fields: dict[str, Any] = {}
        if skill_type is not None:
            fields["skill_type"] = skill_type
        if topic_domain is not None:
            fields["topic_domain"] = topic_domain
        if not fields:
            return False

        if self.get_by_id(resource_id) is None:
            return False
        return self.patch_fields(resource_id, fields)

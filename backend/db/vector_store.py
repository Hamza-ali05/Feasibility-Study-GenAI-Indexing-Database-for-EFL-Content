"""FAISS vector index helper for live search."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import faiss
import numpy as np

from backend.utils.config import DATA_EMBEDDINGS
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.vector_store")

FAISS_INDEX_PATH = DATA_EMBEDDINGS / "faiss_index.bin"
FAISS_ID_MAP_PATH = DATA_EMBEDDINGS / "faiss_id_map.json"
FAISS_TOMBSTONES_PATH = DATA_EMBEDDINGS / "faiss_tombstones.json"


def _l2_normalize(x: np.ndarray) -> np.ndarray:
    if x.ndim == 1:
        x = x.reshape(1, -1)
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return (x / norms).astype(np.float32)


class VectorStore:
    def __init__(
        self,
        index_path: Path | None = None,
        id_map_path: Path | None = None,
        tombstones_path: Path | None = None,
    ) -> None:
        self.index_path = index_path or FAISS_INDEX_PATH
        self.id_map_path = id_map_path or FAISS_ID_MAP_PATH
        self.tombstones_path = tombstones_path or FAISS_TOMBSTONES_PATH
        if not self.index_path.exists():
            raise FileNotFoundError(f"FAISS index missing: {self.index_path}")
        if not self.id_map_path.exists():
            raise FileNotFoundError(f"FAISS id map missing: {self.id_map_path}")
        self.index = faiss.read_index(str(self.index_path))
        with self.id_map_path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        by_resource = raw.get("by_resource_id") or {}
        if by_resource:
            n = self.index.ntotal
            self.row_to_id = [""] * n
            self.id_to_row: dict[str, int] = {}
            for rid, idx in by_resource.items():
                i = int(idx)
                if 0 <= i < n:
                    self.row_to_id[i] = str(rid)
                    self.id_to_row[str(rid)] = i
        else:
            self.row_to_id = [
                raw[str(i)]["resource_id"] for i in range(self.index.ntotal) if str(i) in raw
            ]
            self.id_to_row = {rid: i for i, rid in enumerate(self.row_to_id) if rid}

        # FAISS IndexFlatIP has no true delete — tombstoned ids are filtered in search().
        self.tombstones: set[str] = self._load_tombstones()
        logger.info(
            "VectorStore ready ntotal=%s tombstones=%s",
            self.index.ntotal,
            len(self.tombstones),
        )

    def _load_tombstones(self) -> set[str]:
        if not self.tombstones_path.exists():
            return set()
        try:
            with self.tombstones_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                return {str(x) for x in data}
            return {str(x) for x in (data.get("tombstoned_ids") or [])}
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to load FAISS tombstones: %s", exc)
            return set()

    def _persist_tombstones(self) -> None:
        self.tombstones_path.parent.mkdir(parents=True, exist_ok=True)
        with self.tombstones_path.open("w", encoding="utf-8") as fh:
            json.dump(
                {
                    "tombstoned_ids": sorted(self.tombstones),
                    "note": (
                        "IndexFlatIP cannot remove vectors in-place; these ids are "
                        "filtered out of VectorStore.search() results."
                    ),
                },
                fh,
                indent=2,
            )
            fh.write("\n")

    def tombstone(self, resource_id: str) -> None:
        """
        Soft-delete a resource from retrieval.

        FAISS ``IndexFlatIP`` does **not** support true vector deletion. We keep
        the row in the on-disk index (ids stay stable) and add ``resource_id`` to
        a persisted tombstone set that ``search()`` filters post-retrieval.
        Rebuilding the index in stage Train removes tombstones permanently.
        """
        rid = str(resource_id)
        self.tombstones.add(rid)
        self._persist_tombstones()
        logger.info("FAISS tombstoned resource_id=%s (ntombstones=%s)", rid, len(self.tombstones))

    def get_embedding(self, resource_id: str) -> np.ndarray | None:
        """Return the stored FAISS vector for ``resource_id``, or None if absent."""
        idx = self.id_to_row.get(str(resource_id))
        if idx is None:
            return None
        if str(resource_id) in self.tombstones:
            return None
        vec = self.index.reconstruct(int(idx))
        return np.asarray(vec, dtype=np.float32)

    def search(self, query_embedding: np.ndarray, top_k: int = 10) -> list[tuple[str, float]]:
        q = _l2_normalize(np.asarray(query_embedding, dtype=np.float32))
        if self.index.ntotal <= 0:
            return []
        # Over-fetch so tombstoned hits can be skipped while still filling top_k
        fetch = min(
            max(int(top_k) + len(self.tombstones) + 5, int(top_k) * 3),
            self.index.ntotal,
        )
        scores, indices = self.index.search(q, fetch)
        hits: list[tuple[str, float]] = []
        for score, idx in zip(scores[0].tolist(), indices[0].tolist()):
            if idx < 0 or idx >= len(self.row_to_id):
                continue
            rid = self.row_to_id[idx]
            if not rid:
                continue
            # Soft-delete filter — IndexFlatIP cannot remove rows in-place.
            if rid in self.tombstones:
                continue
            hits.append((rid, float(score)))
            if len(hits) >= top_k:
                break
        return hits

    def _persist_id_map(self) -> None:
        payload: dict = {
            str(i): {"resource_id": rid} for i, rid in enumerate(self.row_to_id) if rid
        }
        payload["by_resource_id"] = dict(self.id_to_row)
        with self.id_map_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    def add_single(self, resource_id: str, embedding: np.ndarray) -> int:
        """
        Append one L2-normalised vector to the live FAISS index and persist.

        Returns the new FAISS row index. Updates in-memory maps so subsequent
        searches see the resource immediately (no process restart required).
        """
        rid = str(resource_id)
        if rid in self.tombstones:
            # Re-activating a previously deleted id
            self.tombstones.discard(rid)
            self._persist_tombstones()
        if rid in self.id_to_row:
            raise ValueError(f"resource_id already in FAISS index: {rid}")
        vec = _l2_normalize(np.asarray(embedding, dtype=np.float32))
        self.index.add(vec)
        new_idx = int(self.index.ntotal - 1)
        while len(self.row_to_id) <= new_idx:
            self.row_to_id.append("")
        self.row_to_id[new_idx] = rid
        self.id_to_row[rid] = new_idx
        faiss.write_index(self.index, str(self.index_path))
        self._persist_id_map()
        logger.info("FAISS add_single %s → row %s (ntotal=%s)", rid, new_idx, self.index.ntotal)
        return new_idx


# Prompt-facing alias
FAISSVectorStore = VectorStore


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    return VectorStore()

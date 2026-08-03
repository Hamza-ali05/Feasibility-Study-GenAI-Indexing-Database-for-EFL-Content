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
    ) -> None:
        self.index_path = index_path or FAISS_INDEX_PATH
        self.id_map_path = id_map_path or FAISS_ID_MAP_PATH
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
        logger.info("VectorStore ready ntotal=%s", self.index.ntotal)

    def get_embedding(self, resource_id: str) -> np.ndarray | None:
        """Return the stored FAISS vector for ``resource_id``, or None if absent."""
        idx = self.id_to_row.get(str(resource_id))
        if idx is None:
            return None
        vec = self.index.reconstruct(int(idx))
        return np.asarray(vec, dtype=np.float32)

    def search(self, query_embedding: np.ndarray, top_k: int = 10) -> list[tuple[str, float]]:
        q = _l2_normalize(np.asarray(query_embedding, dtype=np.float32))
        k = min(max(top_k, 1), self.index.ntotal)
        scores, indices = self.index.search(q, k)
        hits: list[tuple[str, float]] = []
        for score, idx in zip(scores[0].tolist(), indices[0].tolist()):
            if idx < 0 or idx >= len(self.row_to_id):
                continue
            rid = self.row_to_id[idx]
            if not rid:
                continue
            hits.append((rid, float(score)))
        return hits


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    return VectorStore()

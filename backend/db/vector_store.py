"""FAISS vector index with tombstone soft-deletes for live search / RAG."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import faiss
import numpy as np

from backend.utils.config import DATA_EMBEDDINGS, DATA_PROCESSED, FAISS_INDEX_PATH
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.vector_store")

FAISS_ID_MAP_PATH = DATA_EMBEDDINGS / "faiss_id_map.json"

TOMBSTONED_IDS_PATH = DATA_PROCESSED / "tombstoned_ids.json"

_LEGACY_TOMBSTONES_PATH = DATA_EMBEDDINGS / "faiss_tombstones.json"

def _l2_normalize(x: np.ndarray) -> np.ndarray:
    """L2-normalise so IndexFlatIP approximates cosine similarity."""
    arr = np.asarray(x, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return (arr / norms).astype(np.float32)

class FAISSVectorStore:
    """
    Live FAISS ``IndexFlatIP`` store.

    Soft-deletes use an in-memory ``tombstoned`` set persisted to
    ``data/processed/tombstoned_ids.json`` so Admin / Duplicate Detection
    removals take effect without a full index rebuild.
    """

    def __init__(
        self,
        index_path: Path | None = None,
        id_map_path: Path | None = None,
        tombstones_path: Path | None = None,
        *,
        autoload: bool = True,
    ) -> None:
        self.index_path = Path(index_path) if index_path else Path(FAISS_INDEX_PATH)
        self.id_map_path = Path(id_map_path) if id_map_path else FAISS_ID_MAP_PATH
        self.tombstones_path = (
            Path(tombstones_path) if tombstones_path else TOMBSTONED_IDS_PATH
        )
        self.index: faiss.Index | None = None
        self.row_to_id: list[str] = []
        self.id_to_row: dict[str, int] = {}

        self.tombstoned: set[str] = self._load_tombstones()
        if autoload and self.index_path.exists() and self.id_map_path.exists():
            self.load_index(self.index_path)
        logger.info(
            "FAISSVectorStore ready ntotal=%s tombstoned=%s",
            self.index.ntotal if self.index is not None else 0,
            len(self.tombstoned),
        )

    @property
    def tombstones(self) -> set[str]:
        return self.tombstoned

    def _load_tombstones(self) -> set[str]:
        ids: set[str] = set()
        for path in (self.tombstones_path, _LEGACY_TOMBSTONES_PATH):
            if not path.exists():
                continue
            try:
                with path.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, list):
                    ids.update(str(x) for x in data)
                else:
                    ids.update(str(x) for x in (data.get("tombstoned_ids") or []))
            except Exception as exc:
                logger.warning("failed to load tombstones from %s: %s", path, exc)
        return ids

    def _persist_tombstones(self) -> None:
        self.tombstones_path.parent.mkdir(parents=True, exist_ok=True)
        with self.tombstones_path.open("w", encoding="utf-8") as fh:
            json.dump(
                {
                    "tombstoned_ids": sorted(self.tombstoned),
                    "note": (
                        "IndexFlatIP cannot remove vectors in-place; these ids are "
                        "filtered out of FAISSVectorStore.search() results."
                    ),
                },
                fh,
                indent=2,
            )
            fh.write("\n")

    def load_index(self, path: Path | str | None = None) -> None:
        """Load FAISS index + id map from disk into memory."""
        index_path = Path(path) if path is not None else self.index_path
        if not index_path.exists():
            raise FileNotFoundError(f"FAISS index missing: {index_path}")
        if not self.id_map_path.exists():
            raise FileNotFoundError(f"FAISS id map missing: {self.id_map_path}")

        self.index = faiss.read_index(str(index_path))
        self.index_path = index_path
        with self.id_map_path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)

        by_resource = raw.get("by_resource_id") or {}
        if by_resource:
            n = self.index.ntotal
            self.row_to_id = [""] * n
            self.id_to_row = {}
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

        logger.info("Loaded FAISS index ntotal=%s from %s", self.index.ntotal, index_path)

    def build_index(self, embeddings: np.ndarray, ids: list[str]) -> None:
        """Build a fresh ``IndexFlatIP`` from L2-normalised embeddings + resource ids."""
        if len(ids) == 0:
            raise ValueError("build_index requires at least one id")
        vecs = _l2_normalize(np.asarray(embeddings, dtype=np.float32))
        if vecs.ndim != 2:
            raise ValueError(f"embeddings must be 2-D, got shape {vecs.shape}")
        if vecs.shape[0] != len(ids):
            raise ValueError(
                f"embeddings rows ({vecs.shape[0]}) != len(ids) ({len(ids)})"
            )
        dim = int(vecs.shape[1])
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(vecs)
        self.row_to_id = [str(rid) for rid in ids]
        self.id_to_row = {str(rid): i for i, rid in enumerate(self.row_to_id)}
        logger.info("Built FAISS IndexFlatIP ntotal=%s dim=%s", self.index.ntotal, dim)

    def save_index(self, path: Path | str | None = None) -> None:
        """Persist the live index and id map to disk."""
        if self.index is None:
            raise RuntimeError("No FAISS index to save — call build_index or load_index first")
        index_path = Path(path) if path is not None else self.index_path
        index_path.parent.mkdir(parents=True, exist_ok=True)
        self.id_map_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(index_path))
        self.index_path = index_path
        self._persist_id_map()
        logger.info("Saved FAISS index ntotal=%s → %s", self.index.ntotal, index_path)

    def _persist_id_map(self) -> None:
        payload: dict = {
            str(i): {"resource_id": rid} for i, rid in enumerate(self.row_to_id) if rid
        }
        payload["by_resource_id"] = dict(self.id_to_row)
        with self.id_map_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    def search(self, query_vec: np.ndarray, top_k: int = 10) -> list[dict[str, float | str]]:
        """
        Nearest-neighbour search.

        Tombstoned ids are filtered out before returning so soft-deletes
        disappear from search / recommend / RAG without a rebuild.
        """
        if self.index is None or self.index.ntotal <= 0:
            return []
        q = _l2_normalize(np.asarray(query_vec, dtype=np.float32))
        fetch = min(
            max(int(top_k) + len(self.tombstoned) + 5, int(top_k) * 3),
            self.index.ntotal,
        )
        scores, indices = self.index.search(q, fetch)
        hits: list[dict[str, float | str]] = []
        for score, idx in zip(scores[0].tolist(), indices[0].tolist()):
            if idx < 0 or idx >= len(self.row_to_id):
                continue
            rid = self.row_to_id[idx]
            if not rid:
                continue
            if rid in self.tombstoned:
                continue
            hits.append({"id": str(rid), "score": float(score)})
            if len(hits) >= int(top_k):
                break
        return hits

    def add_single(self, embedding: np.ndarray, id: str) -> None:
        """
        Append one L2-normalised vector to the live index and persist via ``save_index``.

        Used by the AI Resource Analyzer for live ingestion between full pipeline runs.
        """
        if self.index is None:
            raise RuntimeError("No FAISS index loaded — cannot add_single")
        rid = str(id)
        if rid in self.tombstoned:

            self.tombstoned.discard(rid)
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
        self.save_index()
        logger.info("FAISS add_single %s → row %s (ntotal=%s)", rid, new_idx, self.index.ntotal)

    def tombstone(self, id: str) -> None:
        """
        Soft-delete a resource from retrieval.

        FAISS ``IndexFlatIP`` does not support true vector deletion. The row
        stays in the on-disk index; ``id`` is added to the persisted tombstone
        set that ``search()`` filters post-retrieval.
        """
        rid = str(id)
        self.tombstoned.add(rid)
        self._persist_tombstones()
        logger.info("FAISS tombstoned id=%s (n=%s)", rid, len(self.tombstoned))

    def get_embedding(self, resource_id: str) -> np.ndarray | None:
        """Return the stored FAISS vector for ``resource_id``, or None if absent/tombstoned."""
        if self.index is None:
            return None
        rid = str(resource_id)
        idx = self.id_to_row.get(rid)
        if idx is None or rid in self.tombstoned:
            return None
        vec = self.index.reconstruct(int(idx))
        return np.asarray(vec, dtype=np.float32)

VectorStore = FAISSVectorStore

@lru_cache(maxsize=1)
def get_vector_store() -> FAISSVectorStore:
    return FAISSVectorStore()

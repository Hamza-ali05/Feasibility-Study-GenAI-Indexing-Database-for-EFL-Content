"""SBERT embedder helper for EFL IndexDB."""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

import numpy as np
from sentence_transformers import SentenceTransformer

from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.embedder")

DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


class Embedder:
    """Thin wrapper around sentence-transformers with local-cache loading."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self.model_name = model_name
        logger.info("Loading SentenceTransformer %s …", model_name)
        # Prefer HuggingFace cache so live API requests do not block on download.
        try:
            self.model = SentenceTransformer(model_name, local_files_only=True)
            logger.info("Loaded %s from local cache", model_name)
        except Exception as cache_exc:  # noqa: BLE001
            logger.warning(
                "Local cache miss for %s (%s); downloading — this can take several minutes",
                model_name,
                cache_exc,
            )
            self.model = SentenceTransformer(model_name, local_files_only=False)
            logger.info("Downloaded and loaded %s", model_name)
        # Prefer the current ST API; fall back for older package versions.
        dim_fn = getattr(self.model, "get_embedding_dimension", None) or getattr(
            self.model, "get_sentence_embedding_dimension", None
        )
        self.embedding_dim = int(dim_fn()) if dim_fn else 384
        logger.info("SentenceTransformer ready dim=%s", self.embedding_dim)

    def encode(
        self,
        texts: Sequence[str],
        *,
        batch_size: int = 64,
        show_progress_bar: bool = True,
        convert_to_numpy: bool = True,
    ) -> np.ndarray:
        embeddings = self.model.encode(
            list(texts),
            batch_size=batch_size,
            show_progress_bar=show_progress_bar,
            convert_to_numpy=convert_to_numpy,
            normalize_embeddings=False,
        )
        array = np.asarray(embeddings, dtype=np.float32)
        return array


@lru_cache(maxsize=1)
def get_embedder(model_name: str = DEFAULT_MODEL_NAME) -> Embedder:
    """Process-wide singleton used by search, RAG, and startup warm-up."""
    return Embedder(model_name=model_name)

"""SBERT embedder — singleton SentenceTransformer wrapper for EFL IndexDB."""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

import numpy as np
from sentence_transformers import SentenceTransformer

from backend.utils.config import Config
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.embedder")

DEFAULT_MODEL_NAME = Config.SBERT_MODEL

def _l2_normalize(x: np.ndarray) -> np.ndarray:
    """L2-normalise rows (or a single vector) to unit length."""
    arr = np.asarray(x, dtype=np.float32)
    if arr.ndim == 1:
        norm = float(np.linalg.norm(arr))
        if norm < 1e-12:
            return arr
        return (arr / norm).astype(np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return (arr / norms).astype(np.float32)

class SBERTEmbedder:
    """
    Process-wide singleton around ``sentence-transformers``.

    Loads ``Config.SBERT_MODEL`` once; ``embed`` / ``embed_single`` return
    float32 L2-normalised vectors suitable for FAISS ``IndexFlatIP`` (cosine).
    """

    _instance: SBERTEmbedder | None = None

    def __new__(cls, model_name: str | None = None) -> SBERTEmbedder:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str | None = None) -> None:
        if getattr(self, "_initialized", False):
            return
        model_name = model_name or Config.SBERT_MODEL
        self.model_name = model_name
        logger.info("Loading SentenceTransformer %s …", model_name)

        try:
            self.model = SentenceTransformer(model_name, local_files_only=True)
            logger.info("Loaded %s from local cache", model_name)
        except Exception as cache_exc:
            logger.warning(
                "Local cache miss for %s (%s); downloading — this can take several minutes",
                model_name,
                cache_exc,
            )
            self.model = SentenceTransformer(model_name, local_files_only=False)
            logger.info("Downloaded and loaded %s", model_name)
        dim_fn = getattr(self.model, "get_embedding_dimension", None) or getattr(
            self.model, "get_sentence_embedding_dimension", None
        )
        self.embedding_dim = int(dim_fn()) if dim_fn else 384
        self._initialized = True
        logger.info("SBERTEmbedder ready dim=%s", self.embedding_dim)

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed a batch of texts → float32 L2-normalised ndarray of shape (N, D)."""
        if not texts:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)
        embeddings = self.model.encode(
            list(texts),
            batch_size=64,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=False,
        )
        return _l2_normalize(np.asarray(embeddings, dtype=np.float32))

    def embed_single(self, text: str) -> np.ndarray:
        """Embed one text → float32 L2-normalised 1-D vector."""
        return self.embed([text])[0]

    def encode(
        self,
        texts: Sequence[str],
        *,
        batch_size: int = 64,
        show_progress_bar: bool = True,
        convert_to_numpy: bool = True,
    ) -> np.ndarray:
        """Pipeline-compatible alias; same L2-normalised float32 output as ``embed``."""
        del convert_to_numpy
        if not texts:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)
        embeddings = self.model.encode(
            list(texts),
            batch_size=batch_size,
            show_progress_bar=show_progress_bar,
            convert_to_numpy=True,
            normalize_embeddings=False,
        )
        return _l2_normalize(np.asarray(embeddings, dtype=np.float32))

Embedder = SBERTEmbedder

@lru_cache(maxsize=1)
def get_embedder(model_name: str | None = None) -> SBERTEmbedder:
    """Process-wide singleton used by search, RAG, analyzer, and startup warm-up."""
    return SBERTEmbedder(model_name=model_name or Config.SBERT_MODEL)

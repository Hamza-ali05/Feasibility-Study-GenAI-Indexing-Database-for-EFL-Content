"""
EFL IndexDB — path and runtime configuration (Prompt 5-A).

Loads ``.env`` via python-dotenv and exposes a ``Config`` singleton plus
stable path aliases used across the pipeline and API.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

load_dotenv(PROJECT_ROOT / "backend" / ".env", override=False)

def _env_str(key: str, default: str | None = None) -> str | None:
    raw = os.getenv(key)
    if raw is None:
        return default
    stripped = raw.strip()
    return stripped if stripped else default


def _env_bool(key: str, default: bool = False) -> bool:
    raw = _env_str(key)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_path(key: str, default: Path) -> Path:
    raw = _env_str(key)
    if not raw:
        return default
    p = Path(raw)
    return p if p.is_absolute() else (PROJECT_ROOT / p)

class Config:
    """
    Runtime settings for live AI features (RAG, analyzer, admin auth, CORS, etc.).

    Every field listed in ``backend/.env.example`` is mirrored here.
    Path fields accept absolute paths or paths relative to PROJECT_ROOT.
    """

    SBERT_MODEL: str = (
        _env_str("SBERT_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        or "sentence-transformers/all-MiniLM-L6-v2"
    )
    FAISS_INDEX_PATH: Path = _env_path(
        "FAISS_INDEX_PATH",
        PROJECT_ROOT / "data" / "embeddings" / "faiss_index.bin",
    )
    METADATA_DB_PATH: Path = _env_path(
        "METADATA_DB_PATH",
        PROJECT_ROOT / "data" / "processed" / "metadata.db",
    )
    ANALYTICS_DB_PATH: Path = _env_path(
        "ANALYTICS_DB_PATH",
        PROJECT_ROOT / "data" / "processed" / "analytics.db",
    )
    DATA_RAW_DIR: Path = _env_path("DATA_RAW_DIR", PROJECT_ROOT / "data" / "raw")

    LOG_LEVEL: str = (_env_str("LOG_LEVEL", "INFO") or "INFO").upper()

    # When True, unhandled exceptions may include detail in API responses.
    # Keep False for demos / shared deployments.
    DEBUG: bool = _env_bool("DEBUG", False)

    ANTHROPIC_API_KEY: str | None = _env_str("ANTHROPIC_API_KEY")
    RAG_MODEL: str = _env_str("RAG_MODEL", "claude-sonnet-4-6") or "claude-sonnet-4-6"

    ADMIN_USERNAME: str | None = _env_str("ADMIN_USERNAME")
    ADMIN_PASSWORD_HASH: str | None = _env_str("ADMIN_PASSWORD_HASH")
    JWT_SECRET: str | None = _env_str("JWT_SECRET")

    CORS_ORIGIN: str = _env_str("CORS_ORIGIN", "http://localhost:3000") or "http://localhost:3000"

    @classmethod
    def get(cls, field_name: str) -> Any:
        """Return a Config attribute by name (raises AttributeError if unknown)."""
        if not hasattr(cls, field_name) or field_name.startswith("_"):
            raise AttributeError(f"Config has no field '{field_name}'")
        return getattr(cls, field_name)

    @classmethod
    def require(cls, field_name: str) -> Any:
        """
        Return a non-empty Config field, or raise ``RuntimeError`` with a clear
        message. Used by ``rag_service`` / ``admin_auth`` instead of ad-hoc checks.
        """
        try:
            value = cls.get(field_name)
        except AttributeError as exc:
            raise RuntimeError(str(exc)) from exc

        missing = value is None or (isinstance(value, str) and not value.strip())
        if missing:
            raise RuntimeError(
                f"{field_name} is not set. Add it to the project-root .env "
                f"(see backend/.env.example). Required for this feature."
            )
        if isinstance(value, str):
            return value.strip()
        return value

DATA_RAW = Config.DATA_RAW_DIR
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_EMBEDDINGS = Config.FAISS_INDEX_PATH.parent
DATA_SPLITS = PROJECT_ROOT / "data" / "splits"

PIPELINE_STATE_PATH = DATA_PROCESSED / "pipeline_state.json"
METADATA_DB_PATH = Config.METADATA_DB_PATH
ANALYTICS_DB_PATH = Config.ANALYTICS_DB_PATH
FAISS_INDEX_PATH = Config.FAISS_INDEX_PATH

PIPELINE_STAGES = [
    "Discover",
    "Load",
    "Integrate",
    "EDA",
    "Clean",
    "Split",
    "Preprocess",
    "Balance",
    "Train",
    "Evaluate",
    "Explain Global",
    "Explain Local",
    "Explain Quality",
    "Predict",
]

SUPPORTED_RAW_EXTENSIONS = {".csv", ".json", ".jsonl", ".txt", ".pdf"}

RAW_IGNORE_NAMES = {".gitkeep", "README_PLACE_DATASETS_HERE.txt"}

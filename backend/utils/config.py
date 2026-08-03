"""EFL IndexDB — path and runtime configuration."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# backend/utils/config.py → project root is parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load project-root .env if present (never invent keys — missing stays empty).
load_dotenv(PROJECT_ROOT / ".env")
# Also allow backend/.env (Prompt 3-H documents ADMIN_* there).
load_dotenv(PROJECT_ROOT / "backend" / ".env", override=False)


class Config:
    """Runtime settings for live AI features (RAG, analyzer, admin auth, etc.)."""

    ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY") or None
    # Student-project default; override with RAG_MODEL in .env if needed.
    RAG_MODEL: str = os.getenv("RAG_MODEL", "claude-sonnet-4-6")

    # Single-admin Auth (Admin Panel) — set via .env; never commit real secrets.
    ADMIN_USERNAME: str | None = os.getenv("ADMIN_USERNAME") or None
    ADMIN_PASSWORD_HASH: str | None = os.getenv("ADMIN_PASSWORD_HASH") or None
    JWT_SECRET: str | None = os.getenv("JWT_SECRET") or None

DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_EMBEDDINGS = PROJECT_ROOT / "data" / "embeddings"
DATA_SPLITS = PROJECT_ROOT / "data" / "splits"

PIPELINE_STATE_PATH = DATA_PROCESSED / "pipeline_state.json"
METADATA_DB_PATH = DATA_PROCESSED / "metadata.db"
ANALYTICS_DB_PATH = DATA_PROCESSED / "analytics.db"

# Exact stage names (sidebar, API, state, tests) — keep in sync with pipeline_state.STAGES_IN_ORDER
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

# Placeholder files that do not count as datasets
RAW_IGNORE_NAMES = {".gitkeep", "README_PLACE_DATASETS_HERE.txt"}

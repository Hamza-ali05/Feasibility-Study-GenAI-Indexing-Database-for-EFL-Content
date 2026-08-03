"""Shared pytest fixtures for EFL IndexDB tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _ROOT / "backend"
for _p in (_ROOT, _BACKEND):
    s = str(_p)
    if s not in sys.path:
        sys.path.insert(0, s)

@pytest.fixture
def client():
    """FastAPI TestClient without SBERT/FAISS warm-up on startup."""
    from fastapi.testclient import TestClient

    from backend.api.main import app

    if hasattr(app.router, "on_startup"):
        app.router.on_startup.clear()

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()

"""Core API tests (Prompt 6-A)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from backend.auth.admin_auth import get_current_admin
from backend.db.metadata_store import MetadataStore
from backend.utils import pipeline_state

def test_health(client) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "pipeline_ready" in body

def test_search_503_when_pipeline_not_ready(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline_state, "is_pipeline_ready", lambda: False)

    monkeypatch.setattr(
        "api.routers.search.pipeline_state.is_pipeline_ready",
        lambda: False,
        raising=False,
    )
    monkeypatch.setattr(
        "backend.api.routers.search.pipeline_state.is_pipeline_ready",
        lambda: False,
        raising=False,
    )

    resp = client.post("/api/search", json={"query": "grammar practice", "top_k": 5})
    assert resp.status_code == 503
    assert "Pipeline not ready" in resp.json()["detail"]

def test_pipeline_status_returns_14_stages(client) -> None:
    resp = client.get("/api/pipeline/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "stages" in body
    assert len(body["stages"]) == 14
    names = [s["name"] for s in body["stages"]]
    assert names == pipeline_state.STAGES_IN_ORDER

def test_reset_stage(client, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.api.main import app

    state_path = tmp_path / "pipeline_state.json"

    monkeypatch.setattr(pipeline_state, "PIPELINE_STATE_PATH", state_path)
    monkeypatch.setattr(
        "backend.utils.pipeline_state.PIPELINE_STATE_PATH",
        state_path,
    )

    state = pipeline_state.load_state(state_path)
    pipeline_state.set_stage_status(
        "Discover",
        pipeline_state.STATUS_COMPLETE,
        path=state_path,
    )
    assert (
        pipeline_state.load_state(state_path)["Discover"]["status"]
        == pipeline_state.STATUS_COMPLETE
    )

    app.dependency_overrides[get_current_admin] = lambda: "admin"
    try:

        with patch.object(pipeline_state, "PIPELINE_STATE_PATH", state_path):
            resp = client.post("/api/pipeline/reset/Discover")
        assert resp.status_code == 200
        assert resp.json()["stage"] == "Discover"

        statuses = pipeline_state.get_all_statuses(path=state_path)
        assert statuses["Discover"]["status"] == pipeline_state.STATUS_PENDING
    finally:
        app.dependency_overrides.pop(get_current_admin, None)

def test_search_facets_reflects_metadata(
    client, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "meta_test.db"
    store = MetadataStore(db_path=db_path)
    store.upsert_many(
        [
            {
                "resource_id": "r1",
                "title": "A1 Reading One",
                "raw_text": "This is long enough sample text for resource one.",
                "cefr_level": "A1",
                "skill_type": "Reading",
                "topic_domain": "Travel",
                "source_name": "test",
            },
            {
                "resource_id": "r2",
                "title": "A1 Reading Two",
                "raw_text": "This is long enough sample text for resource two.",
                "cefr_level": "A1",
                "skill_type": "Reading",
                "topic_domain": "Travel",
                "source_name": "test",
            },
            {
                "resource_id": "r3",
                "title": "B1 Writing One",
                "raw_text": "This is long enough sample text for resource three.",
                "cefr_level": "B1",
                "skill_type": "Writing",
                "topic_domain": "Business",
                "source_name": "test",
            },
        ]
    )

    def _factory() -> MetadataStore:
        return MetadataStore(db_path=db_path)

    monkeypatch.setattr("api.routers.search.MetadataStore", _factory, raising=False)
    monkeypatch.setattr("backend.api.routers.search.MetadataStore", _factory, raising=False)

    resp = client.get("/api/search/facets")
    assert resp.status_code == 200
    facets = resp.json()
    assert facets["cefr_level"]["A1"] == 2
    assert facets["cefr_level"]["B1"] == 1
    assert facets["skill_type"]["Reading"] == 2
    assert facets["skill_type"]["Writing"] == 1

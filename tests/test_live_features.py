"""Live-feature tests (Prompt 6-B) — no real Anthropic / SBERT network calls."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from backend.auth.admin_auth import hash_password
from backend.db.metadata_store import MetadataStore
from backend.db.vector_store import FAISSVectorStore
from backend.services import recommend_service
from backend.utils import pipeline_state
from backend.utils.config import Config

SAMPLE_TEXT = (
    "Travelling by train is often more relaxing than flying. Learners can "
    "describe journeys, buy tickets, and ask for directions at the station."
)

def _fake_contexts() -> list[dict]:
    return [
        {
            "resource_id": "src-1",
            "title": "Train travel A2",
            "text_snippet": "Buy a ticket at the station…",
            "similarity_score": 0.91,
            "cefr_level": "A2",
        },
        {
            "resource_id": "src-2",
            "title": "Airport vocabulary",
            "text_snippet": "Check-in desks and boarding passes…",
            "similarity_score": 0.87,
            "cefr_level": "B1",
        },
    ]

def _patch_train_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    def _statuses(*_a, **_k):
        return {
            name: {
                "status": (
                    pipeline_state.STATUS_COMPLETE
                    if name == "Train"
                    else pipeline_state.STATUS_PENDING
                ),
                "run_at": None,
                "error": None,
                "progress_pct": None,
            }
            for name in pipeline_state.STAGES_IN_ORDER
        }

    monkeypatch.setattr(pipeline_state, "get_all_statuses", _statuses)
    monkeypatch.setattr(
        "api.routers.analyzer.pipeline_state.get_all_statuses",
        _statuses,
        raising=False,
    )
    monkeypatch.setattr(
        "backend.api.routers.analyzer.pipeline_state.get_all_statuses",
        _statuses,
        raising=False,
    )

def test_qa_ask_raises_clear_error_without_api_key(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pipeline_state, "is_pipeline_ready", lambda: True)
    monkeypatch.setattr(
        "api.routers.qa.pipeline_state.is_pipeline_ready",
        lambda: True,
        raising=False,
    )
    monkeypatch.setattr(Config, "ANTHROPIC_API_KEY", None)
    monkeypatch.setattr(
        "backend.services.rag_service.Config.ANTHROPIC_API_KEY",
        None,
        raising=False,
    )

    resp = client.post("/api/qa/ask", json={"question": "What is CEFR A1?", "top_k": 3})
    assert 400 <= resp.status_code < 500
    assert "ANTHROPIC_API_KEY" in resp.json()["detail"]

def test_qa_ask_returns_sources(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline_state, "is_pipeline_ready", lambda: True)
    monkeypatch.setattr(
        "api.routers.qa.pipeline_state.is_pipeline_ready",
        lambda: True,
        raising=False,
    )
    monkeypatch.setattr(Config, "ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setattr(Config, "RAG_MODEL", "claude-test-mock")

    contexts = _fake_contexts()
    monkeypatch.setattr(
        "backend.services.rag_service.retrieve_context",
        lambda question, top_k=5: contexts,
    )

    mock_block = SimpleNamespace(text="Grounded answer from indexed resources.")
    mock_message = SimpleNamespace(content=[mock_block])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message

    with patch("anthropic.Anthropic", return_value=mock_client):
        resp = client.post(
            "/api/qa/ask",
            json={"question": "How do I buy a train ticket?", "top_k": 2},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["sources"]) == 2
    assert body["sources"][0]["resource_id"] == "src-1"
    assert "Grounded answer" in body["answer"]
    mock_client.messages.create.assert_called_once()

def _seed_recommend_world(
    tmp_path: Path,
    rows: list[dict],
    *,
    query_id: str,
) -> tuple[FAISSVectorStore, MetadataStore]:
    """Build a tiny FAISS index + metadata DB for recommend_similar tests."""
    meta = MetadataStore(db_path=tmp_path / "meta.db")
    meta.upsert_many(rows)

    dim = 8
    ids = [str(r["resource_id"]) for r in rows]

    emb = np.eye(len(ids), dim, dtype=np.float32)

    q_idx = ids.index(query_id)
    for i in range(len(ids)):
        if i == q_idx:
            continue
        emb[i] = emb[q_idx] * 0.9 + np.eye(1, dim, k=(i % dim), dtype=np.float32)[0] * 0.1

    store = FAISSVectorStore(
        index_path=tmp_path / "faiss.bin",
        id_map_path=tmp_path / "id_map.json",
        tombstones_path=tmp_path / "tombstoned_ids.json",
        autoload=False,
    )
    store.build_index(emb, ids)
    return store, meta

def test_recommend_excludes_self(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    query_id = "self-res"
    rows = [
        {
            "resource_id": query_id,
            "title": "Self",
            "raw_text": SAMPLE_TEXT,
            "cefr_level": "B1",
            "skill_type": "Reading",
            "topic_domain": "Travel",
        },
        {
            "resource_id": "n1",
            "title": "Neigh 1",
            "raw_text": SAMPLE_TEXT + " one",
            "cefr_level": "B1",
            "skill_type": "Reading",
            "topic_domain": "Travel",
        },
        {
            "resource_id": "n2",
            "title": "Neigh 2",
            "raw_text": SAMPLE_TEXT + " two",
            "cefr_level": "B1",
            "skill_type": "Reading",
            "topic_domain": "Travel",
        },
    ]
    store, meta = _seed_recommend_world(tmp_path, rows, query_id=query_id)

    monkeypatch.setattr(recommend_service, "MetadataStore", lambda: meta)
    monkeypatch.setattr(recommend_service, "get_vector_store", lambda: store)

    results = recommend_service.recommend_similar(query_id, top_k=5)
    assert all(r["resource_id"] != query_id for r in results)
    assert len(results) >= 1

def test_recommend_diversity_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    query_id = "src"
    same = {
        "cefr_level": "B1",
        "skill_type": "Reading",
        "topic_domain": "Travel",
    }
    rows = [
        {
            "resource_id": query_id,
            "title": "Source",
            "raw_text": SAMPLE_TEXT,
            **same,
        }
    ]

    for i in range(5):
        rows.append(
            {
                "resource_id": f"same-{i}",
                "title": f"Same {i}",
                "raw_text": SAMPLE_TEXT + f" same {i}",
                **same,
            }
        )

    for i in range(2):
        rows.append(
            {
                "resource_id": f"diff-{i}",
                "title": f"Diff {i}",
                "raw_text": SAMPLE_TEXT + f" diff {i}",
                "cefr_level": "B1",
                "skill_type": "Reading",
                "topic_domain": "Business",
            }
        )

    store, meta = _seed_recommend_world(tmp_path, rows, query_id=query_id)
    monkeypatch.setattr(recommend_service, "MetadataStore", lambda: meta)
    monkeypatch.setattr(recommend_service, "get_vector_store", lambda: store)

    results = recommend_service.recommend_similar(query_id, top_k=10)
    same_combo = [
        r
        for r in results
        if r.get("cefr_level") == "B1"
        and r.get("skill_type") == "Reading"
        and r.get("topic_domain") == "Travel"
    ]
    assert len(same_combo) <= recommend_service.SAME_COMBO_LIMIT

    assert len(results) >= recommend_service.SAME_COMBO_LIMIT

def test_analyzer_blocks_on_duplicate(client, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_train_complete(monkeypatch)
    monkeypatch.setattr(Config, "ANTHROPIC_API_KEY", None)

    fake_emb = np.ones(8, dtype=np.float32)
    fake_embedder = MagicMock()
    fake_embedder.embed_single.return_value = fake_emb
    monkeypatch.setattr(
        "backend.services.analyzer_service.get_embedder",
        lambda: fake_embedder,
    )
    monkeypatch.setattr(
        "backend.services.analyzer_service._classify_fallback",
        lambda _emb: {
            "cefr_level": "B1",
            "skill_type": "Reading",
            "topic_domain": "Travel",
            "classify_manually": False,
            "note": None,
        },
    )
    monkeypatch.setattr(
        "backend.services.analyzer_service.duplicate_service.find_near_duplicate",
        lambda _emb, **_k: {
            "resource_id": "existing-dup",
            "title": "Existing near duplicate",
            "similarity": 0.99,
        },
    )
    monkeypatch.setattr(
        "backend.services.analyzer_service.broadcast_duplicate_flag",
        lambda **_k: None,
    )
    monkeypatch.setattr(
        "backend.services.analyzer_service._progress",
        lambda *_a, **_k: None,
    )

    resp = client.post(
        "/api/analyzer/upload",
        json={"text": SAMPLE_TEXT, "title": "Upload candidate"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["indexed"] is False
    assert body["duplicate_of"] == "existing-dup"

def test_analyzer_confirm_duplicate_forces_insert(
    client, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_train_complete(monkeypatch)
    monkeypatch.setattr(Config, "ANTHROPIC_API_KEY", None)

    fake_emb = np.ones(8, dtype=np.float32)
    fake_embedder = MagicMock()
    fake_embedder.embed_single.return_value = fake_emb
    monkeypatch.setattr(
        "backend.services.analyzer_service.get_embedder",
        lambda: fake_embedder,
    )
    monkeypatch.setattr(
        "backend.services.analyzer_service._classify_fallback",
        lambda _emb: {
            "cefr_level": "B1",
            "skill_type": "Reading",
            "topic_domain": "Travel",
            "classify_manually": False,
            "note": None,
        },
    )

    monkeypatch.setattr(
        "backend.services.analyzer_service.duplicate_service.find_near_duplicate",
        lambda _emb, **_k: {
            "resource_id": "existing-dup",
            "title": "Existing",
            "similarity": 0.99,
        },
    )
    monkeypatch.setattr(
        "backend.services.analyzer_service._progress",
        lambda *_a, **_k: None,
    )

    store = FAISSVectorStore(
        index_path=tmp_path / "faiss.bin",
        id_map_path=tmp_path / "id_map.json",
        tombstones_path=tmp_path / "tombstoned_ids.json",
        autoload=False,
    )

    store.build_index(np.eye(1, 8, dtype=np.float32), ["seed"])
    meta = MetadataStore(db_path=tmp_path / "meta.db")

    monkeypatch.setattr(
        "backend.services.analyzer_service.get_vector_store",
        lambda: store,
    )
    monkeypatch.setattr(
        "backend.services.analyzer_service.MetadataStore",
        lambda: meta,
    )

    resp = client.post(
        "/api/analyzer/confirm-duplicate",
        json={"text": SAMPLE_TEXT, "title": "Forced insert", "force": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["indexed"] is True
    assert body["resource_id"]
    assert body["duplicate_of"] is None

def test_duplicates_resolve_tombstones(
    client, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tombstone_path = tmp_path / "tombstoned_ids.json"
    store = FAISSVectorStore(
        index_path=tmp_path / "faiss.bin",
        id_map_path=tmp_path / "id_map.json",
        tombstones_path=tombstone_path,
        autoload=False,
    )
    store.build_index(
        np.eye(2, 4, dtype=np.float32),
        ["keep-a", "drop-b"],
    )
    meta = MetadataStore(db_path=tmp_path / "meta.db")
    meta.upsert_many(
        [
            {
                "resource_id": "keep-a",
                "title": "Keep",
                "raw_text": SAMPLE_TEXT,
                "cefr_level": "A2",
            },
            {
                "resource_id": "drop-b",
                "title": "Drop",
                "raw_text": SAMPLE_TEXT + " b",
                "cefr_level": "A2",
            },
        ]
    )

    monkeypatch.setattr(
        "api.routers.duplicates.get_vector_store",
        lambda: store,
        raising=False,
    )
    monkeypatch.setattr(
        "backend.api.routers.duplicates.get_vector_store",
        lambda: store,
        raising=False,
    )
    monkeypatch.setattr(
        "api.routers.duplicates.MetadataStore",
        lambda: meta,
        raising=False,
    )
    monkeypatch.setattr(
        "backend.api.routers.duplicates.MetadataStore",
        lambda: meta,
        raising=False,
    )
    monkeypatch.setattr(
        "backend.services.duplicate_service.mark_resolved",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "backend.services.duplicate_service.count_unresolved",
        lambda *_a, **_k: 0,
    )
    monkeypatch.setattr(
        "api.routers.duplicates.broadcast_duplicates_pending",
        lambda *_a, **_k: None,
        raising=False,
    )
    monkeypatch.setattr(
        "backend.api.routers.duplicates.broadcast_duplicates_pending",
        lambda *_a, **_k: None,
        raising=False,
    )

    resp = client.post(
        "/api/duplicates/resolve",
        json={
            "resource_id_a": "keep-a",
            "resource_id_b": "drop-b",
            "action": "deleted_b",
        },
    )
    assert resp.status_code == 200

    assert tombstone_path.exists()
    payload = json.loads(tombstone_path.read_text(encoding="utf-8"))
    assert "drop-b" in payload.get("tombstoned_ids", [])
    assert meta.get_by_id("drop-b") is None

def test_admin_endpoints_require_auth(client, monkeypatch: pytest.MonkeyPatch) -> None:
    password = "test-admin-pass"
    monkeypatch.setattr(Config, "ADMIN_USERNAME", "admin")
    monkeypatch.setattr(Config, "ADMIN_PASSWORD_HASH", hash_password(password))
    monkeypatch.setattr(Config, "JWT_SECRET", "unit-test-jwt-secret-32chars-min!!")

    monkeypatch.setattr(
        "api.routers.admin.dashboard_service.build_dashboard_summary",
        lambda: {"pipeline_ready": False, "total_resources": 0},
        raising=False,
    )
    monkeypatch.setattr(
        "backend.api.routers.admin.dashboard_service.build_dashboard_summary",
        lambda: {"pipeline_ready": False, "total_resources": 0},
        raising=False,
    )
    monkeypatch.setattr(
        "api.routers.admin.AnalyticsStore.total_searches",
        lambda self: 0,
        raising=False,
    )
    monkeypatch.setattr(
        "backend.api.routers.admin.AnalyticsStore.total_searches",
        lambda self: 0,
        raising=False,
    )
    monkeypatch.setattr(
        "api.routers.admin.duplicate_service.count_unresolved",
        lambda: 0,
        raising=False,
    )
    monkeypatch.setattr(
        "backend.api.routers.admin.duplicate_service.count_unresolved",
        lambda: 0,
        raising=False,
    )

    unauth = client.get("/api/admin/overview")
    assert unauth.status_code == 401

    login = client.post(
        "/api/admin/login",
        json={"username": "admin", "password": password},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    auth = client.get(
        "/api/admin/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert auth.status_code == 200
    assert auth.json().get("admin_user") == "admin"

def test_analytics_logs_search(
    client, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    analytics_db = tmp_path / "analytics_test.db"
    monkeypatch.setattr(
        "backend.db.analytics_store.ANALYTICS_DB_PATH",
        analytics_db,
    )
    monkeypatch.setattr(
        "backend.services.analytics_service.AnalyticsStore",
        lambda: __import__(
            "backend.db.analytics_store", fromlist=["AnalyticsStore"]
        ).AnalyticsStore(db_path=analytics_db),
    )
    monkeypatch.setattr(
        "api.routers.analytics.AnalyticsStore",
        lambda: __import__(
            "backend.db.analytics_store", fromlist=["AnalyticsStore"]
        ).AnalyticsStore(db_path=analytics_db),
        raising=False,
    )
    monkeypatch.setattr(
        "backend.api.routers.analytics.AnalyticsStore",
        lambda: __import__(
            "backend.db.analytics_store", fromlist=["AnalyticsStore"]
        ).AnalyticsStore(db_path=analytics_db),
        raising=False,
    )

    before = client.get("/api/analytics/summary").json()["total_searches"]

    monkeypatch.setattr(pipeline_state, "is_pipeline_ready", lambda: True)
    monkeypatch.setattr(
        "api.routers.search.pipeline_state.is_pipeline_ready",
        lambda: True,
        raising=False,
    )
    monkeypatch.setattr(
        "backend.api.routers.search.pipeline_state.is_pipeline_ready",
        lambda: True,
        raising=False,
    )

    fake_emb = np.ones(8, dtype=np.float32)
    fake_embedder = MagicMock()
    fake_embedder.embed_single.return_value = fake_emb
    monkeypatch.setattr(
        "api.routers.search.get_embedder",
        lambda: fake_embedder,
        raising=False,
    )
    monkeypatch.setattr(
        "backend.api.routers.search.get_embedder",
        lambda: fake_embedder,
        raising=False,
    )
    monkeypatch.setattr(
        "api.routers.search._predict_query_cefr",
        lambda _v: "B1",
        raising=False,
    )
    monkeypatch.setattr(
        "backend.api.routers.search._predict_query_cefr",
        lambda _v: "B1",
        raising=False,
    )

    fake_store = MagicMock()
    fake_store.search.return_value = [{"id": "hit-1", "score": 0.88}]
    monkeypatch.setattr(
        "api.routers.search.get_vector_store",
        lambda: fake_store,
        raising=False,
    )
    monkeypatch.setattr(
        "backend.api.routers.search.get_vector_store",
        lambda: fake_store,
        raising=False,
    )

    meta = MetadataStore(db_path=tmp_path / "search_meta.db")
    meta.upsert_one(
        {
            "resource_id": "hit-1",
            "title": "Hit One",
            "raw_text": SAMPLE_TEXT,
            "cefr_level": "B1",
            "skill_type": "Reading",
            "topic_domain": "Travel",
        }
    )
    monkeypatch.setattr(
        "api.routers.search.MetadataStore",
        lambda: meta,
        raising=False,
    )
    monkeypatch.setattr(
        "backend.api.routers.search.MetadataStore",
        lambda: meta,
        raising=False,
    )
    monkeypatch.setattr(
        "backend.services.analytics_service.broadcast_search_event",
        lambda **_k: None,
        raising=False,
    )

    search_resp = client.post(
        "/api/search",
        json={"query": "train tickets vocabulary", "top_k": 5},
    )
    assert search_resp.status_code == 200

    after = client.get("/api/analytics/summary").json()["total_searches"]
    assert after == before + 1

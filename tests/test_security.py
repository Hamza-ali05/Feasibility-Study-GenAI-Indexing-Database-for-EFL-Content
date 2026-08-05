"""Security hardening & evaluation tests (Prompt 16-C)."""

from __future__ import annotations

import pytest

from api.middleware_security import reset_rate_limit_buckets
from backend.utils import pipeline_state
from backend.utils.config import Config


ADMIN_PATHS = [
    "/api/admin/me",
    "/api/admin/overview",
    "/api/report/sections",
    "/api/security/report",
    "/api/security/owasp",
    "/api/practitioner/participants",
    "/api/metrics/export",
]


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    reset_rate_limit_buckets()
    yield
    reset_rate_limit_buckets()


def test_unauthenticated_admin_endpoints(client) -> None:
    for path in ADMIN_PATHS:
        method = "post" if path.endswith("/export") else "get"
        resp = getattr(client, method)(path)
        assert resp.status_code in {401, 403}, f"{path} → {resp.status_code}"


def test_rate_limiter_login(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "ADMIN_USERNAME", "admin")
    monkeypatch.setattr(
        Config,
        "ADMIN_PASSWORD_HASH",
        "$2b$12$invalidhashplaceholderxxxxxxxxxxxx",  # verify will fail
    )
    monkeypatch.setattr(Config, "JWT_SECRET", "unit-test-jwt-secret-32chars-min!!")

    # Even with a bogus hash, failed attempts still hit the rate limiter
    statuses = []
    for i in range(6):
        r = client.post(
            "/api/admin/login",
            json={"username": "admin", "password": f"wrong-{i}"},
        )
        statuses.append(r.status_code)

    assert 429 in statuses, f"expected rate limit among {statuses}"
    assert statuses[-1] == 429


def test_search_query_sanitization(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline_state, "is_pipeline_ready", lambda *a, **k: True)

    # Avoid SBERT/FAISS — return empty hits
    class _FakeEmbedder:
        def embed_single(self, _text):
            import numpy as np

            return np.zeros(384, dtype=np.float32)

    class _FakeStore:
        def search(self, *_a, **_k):
            return []

    monkeypatch.setattr("api.routers.search.get_embedder", lambda: _FakeEmbedder())
    monkeypatch.setattr("api.routers.search.get_vector_store", lambda: _FakeStore())
    monkeypatch.setattr(
        "api.routers.search.MetadataStore",
        lambda: type("M", (), {"get_by_ids": lambda self, ids: {}})(),
    )
    monkeypatch.setattr(
        "api.routers.search.analytics_service.log_search_query",
        lambda **kwargs: None,
    )
    monkeypatch.setattr("api.routers.search._predict_query_cefr", lambda *_a, **_k: None)

    dirty = '<script>alert(1)</script> beginner reading'
    r = client.post("/api/search/", json={"query": dirty, "top_k": 3})
    assert r.status_code == 200, r.text
    body = r.json()
    echoed = body.get("query") or ""
    raw = r.text or ""
    assert "<script>" not in echoed.lower()
    assert "</script>" not in echoed.lower()
    assert "<script>" not in raw.lower()
    assert "beginner reading" in echoed


def test_file_upload_extension_block(client, monkeypatch: pytest.MonkeyPatch) -> None:
    def _statuses(*_a, **_k):
        return {
            name: {
                "status": pipeline_state.STATUS_COMPLETE
                if name == "Train"
                else pipeline_state.STATUS_PENDING,
                "run_at": None,
                "error": None,
                "progress_pct": None,
            }
            for name in pipeline_state.STAGES_IN_ORDER
        }

    monkeypatch.setattr(pipeline_state, "get_all_statuses", _statuses)

    files = {
        "file": ("malware.exe", b"MZ\x00\x00fake", "application/octet-stream"),
    }
    r = client.post("/api/analyzer/upload", files=files)
    assert r.status_code == 400, r.text
    assert "extension" in (r.json().get("detail") or "").lower() or "unsupported" in (
        r.json().get("detail") or ""
    ).lower()


def test_file_upload_size_limit(client, monkeypatch: pytest.MonkeyPatch) -> None:
    def _statuses(*_a, **_k):
        return {
            name: {
                "status": pipeline_state.STATUS_COMPLETE
                if name == "Train"
                else pipeline_state.STATUS_PENDING,
                "run_at": None,
                "error": None,
                "progress_pct": None,
            }
            for name in pipeline_state.STAGES_IN_ORDER
        }

    monkeypatch.setattr(pipeline_state, "get_all_statuses", _statuses)

    big = b"A" * (5 * 1024 * 1024 + 10)
    files = {"file": ("huge.txt", big, "text/plain")}
    r = client.post("/api/analyzer/upload", files=files)
    assert r.status_code == 400, r.text
    detail = (r.json().get("detail") or "").lower()
    assert "size" in detail or "maximum" in detail or "5" in detail


def test_error_no_stack_trace(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "DEBUG", False)
    r = client.post(
        "/api/search/",
        content="{not-valid-json",
        headers={"Content-Type": "application/json"},
    )
    # FastAPI/Starlette typically returns 422 for bad JSON
    assert r.status_code in {400, 422, 500}
    text = r.text or ""
    assert "Traceback" not in text
    assert "File \"" not in text
    assert ".py\", line" not in text


def test_security_headers(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"


def test_cors_rejects_unauthorized_origin(client) -> None:
    r = client.options(
        "/api/search/",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    allow = r.headers.get("access-control-allow-origin")
    assert allow not in {"*", "http://evil.com"}, f"unexpected ACAO={allow!r}"

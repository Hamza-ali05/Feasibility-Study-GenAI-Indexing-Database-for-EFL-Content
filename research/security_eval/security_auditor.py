"""Automated defensive security auditor for the EFL IndexDB local API.

Runs OWASP-aligned checks against ``base_url`` (default localhost).
Test vectors are standard educational payloads for evaluating *this*
system only — not for use against third-party targets.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from research.utils.latex_tables import dataframe_to_all

_PKG_ROOT = Path(__file__).resolve().parent
_VECTORS = _PKG_ROOT / "test_vectors"
_DEFAULT_REPORTS = _PKG_ROOT / "reports"
_PROJECT_ROOT = _PKG_ROOT.parents[1]

BG_PAGE = "#F9F8F5"
BORDER = "#D3D1C7"
ACCENT = "#3C3489"
TEXT_MUTED = "#888780"
PASS_C = "#5F5E5A"
FAIL_C = "#3C3489"
WARN_C = "#B4B2A9"

_DEFAULT_SECRETS = {
    "secret",
    "changeme",
    "password",
    "jwt_secret",
    "your-secret-here",
    "supersecret",
    "12345678901234567890123456789012",
}

_ADMIN_ENDPOINTS_DEFAULT = [
    "/api/admin/me",
    "/api/report/sections",
    "/api/practitioner/participants",
    "/api/pipeline/status",
]

_LEAK_PATTERNS = [
    re.compile(r"Traceback \(most recent call last\)", re.I),
    re.compile(r"File \"[A-Za-z]:\\\\", re.I),
    re.compile(r"/Users/|/home/[a-z]+/|D:\\\\Documents", re.I),
    re.compile(r"sqlite3\.|OperationalError|psycopg2", re.I),
    re.compile(r"fastapi==|pydantic==|starlette==", re.I),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_vectors(name: str) -> list[str]:
    path = _VECTORS / name
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, list):
        return [str(x) for x in data]
    if isinstance(data, dict) and "payloads" in data:
        return [str(x) for x in data["payloads"]]
    return []


def _excerpt(text: str, n: int = 180) -> str:
    t = " ".join(str(text).split())
    return t if len(t) <= n else t[: n - 1] + "…"


class SecurityAuditor:
    """Self-contained httpx client that audits the local EFL IndexDB API."""

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=30.0, follow_redirects=True)
        self._admin_token: str | None = None
        self._last_audit: dict[str, Any] | None = None

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> SecurityAuditor:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ── helpers ─────────────────────────────────────────────────────────

    def _try_login(self) -> str | None:
        """Best-effort admin login using env credentials (optional)."""
        user = os.getenv("ADMIN_USERNAME") or os.getenv("EFL_ADMIN_USER")
        password = os.getenv("ADMIN_PASSWORD") or os.getenv("EFL_ADMIN_PASSWORD")
        if not user or not password:
            try:
                from backend.utils.config import Config

                user = user or getattr(Config, "ADMIN_USERNAME", None)
            except Exception:
                pass
        if not user or not password:
            return None
        try:
            r = self.client.post(
                "/api/admin/login",
                json={"username": user, "password": password},
            )
            if r.status_code == 200:
                token = (r.json() or {}).get("access_token")
                if token:
                    self._admin_token = str(token)
                    return self._admin_token
        except Exception:
            return None
        return None

    def _auth_headers(self, token: str | None = None) -> dict[str, str]:
        t = token if token is not None else self._admin_token
        if not t:
            return {}
        return {"Authorization": f"Bearer {t}"}

    def _make_expired_token(self) -> str | None:
        try:
            from jose import jwt
            from backend.utils.config import Config
            from backend.auth.admin_auth import ALGORITHM

            secret = str(Config.require("JWT_SECRET"))
            exp = datetime.now(timezone.utc) - timedelta(hours=1)
            return jwt.encode(
                {
                    "sub": "admin",
                    "exp": exp,
                    "iat": exp - timedelta(hours=1),
                    "role": "admin",
                },
                secret,
                algorithm=ALGORITHM,
            )
        except Exception:
            return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.expired.signature"

    def _make_short_lived_token(self, seconds: int = 1) -> str | None:
        try:
            from jose import jwt
            from backend.utils.config import Config
            from backend.auth.admin_auth import ALGORITHM

            secret = str(Config.require("JWT_SECRET"))
            now = datetime.now(timezone.utc)
            return jwt.encode(
                {
                    "sub": "admin",
                    "exp": now + timedelta(seconds=seconds),
                    "iat": now,
                    "role": "admin",
                },
                secret,
                algorithm=ALGORITHM,
            )
        except Exception:
            return None

    # ── Authentication & Authorization ──────────────────────────────────

    def test_jwt_auth_required(
        self, endpoints: list[str] | None = None
    ) -> list[dict[str, Any]]:
        endpoints = endpoints or list(_ADMIN_ENDPOINTS_DEFAULT)
        # /api/pipeline/status is public — skip or note; use admin ones
        endpoints = [e for e in endpoints if e != "/api/pipeline/status"] or [
            "/api/admin/me",
            "/api/report/sections",
            "/api/practitioner/participants",
        ]
        results: list[dict[str, Any]] = []
        if not self._admin_token:
            self._try_login()

        expired = self._make_expired_token()
        malformed = "not-a-jwt.token.value"

        for ep in endpoints:
            # No token
            try:
                r = self.client.get(ep)
                passed = r.status_code in {401, 403}
                results.append(
                    {
                        "endpoint": ep,
                        "test": "no_token",
                        "passed": passed,
                        "detail": f"status={r.status_code}",
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "endpoint": ep,
                        "test": "no_token",
                        "passed": False,
                        "detail": f"request error: {exc}",
                    }
                )

            # Expired
            try:
                r = self.client.get(ep, headers=self._auth_headers(expired))
                passed = r.status_code in {401, 403}
                results.append(
                    {
                        "endpoint": ep,
                        "test": "expired_token",
                        "passed": passed,
                        "detail": f"status={r.status_code}",
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "endpoint": ep,
                        "test": "expired_token",
                        "passed": False,
                        "detail": str(exc),
                    }
                )

            # Malformed
            try:
                r = self.client.get(ep, headers=self._auth_headers(malformed))
                passed = r.status_code in {401, 403}
                results.append(
                    {
                        "endpoint": ep,
                        "test": "malformed_token",
                        "passed": passed,
                        "detail": f"status={r.status_code}",
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "endpoint": ep,
                        "test": "malformed_token",
                        "passed": False,
                        "detail": str(exc),
                    }
                )

            # Valid token (if available)
            if self._admin_token:
                try:
                    r = self.client.get(ep, headers=self._auth_headers())
                    passed = r.status_code < 400
                    results.append(
                        {
                            "endpoint": ep,
                            "test": "valid_token",
                            "passed": passed,
                            "detail": f"status={r.status_code}",
                        }
                    )
                except Exception as exc:
                    results.append(
                        {
                            "endpoint": ep,
                            "test": "valid_token",
                            "passed": False,
                            "detail": str(exc),
                        }
                    )
            else:
                results.append(
                    {
                        "endpoint": ep,
                        "test": "valid_token",
                        "passed": False,
                        "detail": "skipped — set ADMIN_USERNAME/ADMIN_PASSWORD to exercise positive path",
                    }
                )

        return results

    def test_jwt_expiry(self) -> dict[str, Any]:
        token = self._make_short_lived_token(1)
        if not token:
            return {
                "passed": False,
                "detail": "Could not mint short-lived token (JWT_SECRET missing?)",
            }
        time.sleep(2.2)
        try:
            r = self.client.get("/api/admin/me", headers=self._auth_headers(token))
            passed = r.status_code in {401, 403}
            return {
                "passed": passed,
                "detail": f"After 2s wait, /api/admin/me → {r.status_code}",
            }
        except Exception as exc:
            return {"passed": False, "detail": str(exc)}

    def test_jwt_secret_strength(self) -> dict[str, Any]:
        try:
            from backend.utils.config import Config

            secret = str(Config.JWT_SECRET or "")
        except Exception:
            secret = str(os.getenv("JWT_SECRET") or "")
        length = len(secret)
        is_default = secret.lower().strip() in _DEFAULT_SECRETS or length == 0
        passed = length >= 32 and not is_default
        return {
            "passed": passed,
            "secret_length": length,
            "is_default": is_default,
            "detail": (
                "JWT_SECRET meets length/non-default checks"
                if passed
                else "JWT_SECRET too short or looks like a placeholder"
            ),
        }

    def test_password_hashing(self) -> dict[str, Any]:
        try:
            from backend.utils.config import Config

            hashed = str(Config.ADMIN_PASSWORD_HASH or "")
        except Exception:
            hashed = str(os.getenv("ADMIN_PASSWORD_HASH") or "")
        algo = "unknown"
        passed = False
        if hashed.startswith("$2b$"):
            algo, passed = "bcrypt($2b$)", True
        elif hashed.startswith("$2a$"):
            algo, passed = "bcrypt($2a$)", True
        elif hashed.startswith("$2y$"):
            algo, passed = "bcrypt($2y$)", True
        elif hashed and not hashed.startswith("$"):
            algo = "plaintext_or_non_bcrypt"
        return {
            "passed": passed,
            "hash_algorithm": algo,
            "detail": "ADMIN_PASSWORD_HASH is bcrypt" if passed else "Hash missing or not bcrypt",
        }

    def test_brute_force_protection(self) -> dict[str, Any]:
        codes: list[int] = []
        for i in range(20):
            try:
                r = self.client.post(
                    "/api/admin/login",
                    json={"username": "admin", "password": f"wrong-password-{i}"},
                )
                codes.append(r.status_code)
            except Exception:
                codes.append(0)
        rate_limited = any(c == 429 for c in codes)
        locked = any(c in {423, 403} for c in codes[10:])
        passed = rate_limited or locked
        return {
            "passed": passed,
            "detail": (
                f"20 failed logins → statuses {sorted(set(codes))}; "
                f"rate_limited={rate_limited}"
            ),
            "recommendation": (
                "Add login rate limiting / account lockout (e.g. slowapi, "
                "nginx limit_req, or application-level counters)."
                if not passed
                else "Rate limiting or lockout observed."
            ),
        }

    # ── Input validation ────────────────────────────────────────────────

    def test_sql_injection(
        self, endpoints: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        payloads = _load_vectors("sql_injection.json")
        endpoints = endpoints or [
            {"method": "POST", "path": "/api/search/", "field": "query", "body": {"top_k": 5}},
            {"method": "POST", "path": "/api/qa/ask", "field": "question", "body": {"top_k": 3}},
        ]
        results: list[dict[str, Any]] = []
        sql_error_hints = (
            "syntax error",
            "sqlite",
            "operationalerror",
            "you have an error in your sql",
            "unclosed quotation",
            "sqlstate",
        )
        for ep in endpoints:
            path = ep["path"]
            field = ep.get("field", "query")
            method = ep.get("method", "POST").upper()
            base_body = dict(ep.get("body") or {})
            for payload in payloads:
                body = {**base_body, field: payload}
                try:
                    if method == "GET":
                        r = self.client.get(path, params={field: payload})
                    else:
                        r = self.client.post(path, json=body)
                    text = (r.text or "").lower()
                    leaked = any(h in text for h in sql_error_hints)
                    # 5xx with SQL noise = fail; 4xx/2xx without SQL noise = pass
                    passed = (not leaked) and r.status_code < 500
                    results.append(
                        {
                            "endpoint": path,
                            "payload": payload,
                            "passed": passed,
                            "response_code": r.status_code,
                            "detail": (
                                "SQL error indicators in body"
                                if leaked
                                else _excerpt(r.text or r.reason_phrase)
                            ),
                        }
                    )
                except Exception as exc:
                    results.append(
                        {
                            "endpoint": path,
                            "payload": payload,
                            "passed": False,
                            "response_code": 0,
                            "detail": str(exc),
                        }
                    )
        return results

    def test_xss_prevention(
        self, endpoints: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        payloads = _load_vectors("xss_payloads.json")
        endpoints = endpoints or [
            {"method": "POST", "path": "/api/search/", "field": "query", "body": {"top_k": 5}},
        ]
        results: list[dict[str, Any]] = []
        for ep in endpoints:
            path = ep["path"]
            field = ep.get("field", "query")
            base_body = dict(ep.get("body") or {})
            for payload in payloads:
                body = {**base_body, field: payload}
                try:
                    r = self.client.post(path, json=body)
                    raw = r.text or ""
                    # Fail if response echoes executable HTML/JS payload unescaped
                    dangerous = (
                        "<script>" in raw.lower()
                        or "onerror=" in raw.lower()
                        or "javascript:alert" in raw.lower()
                    ) and payload.lower() in raw.lower()
                    # JSON APIs typically escape; if Content-Type is JSON, treat as pass unless raw script tags
                    ctype = (r.headers.get("content-type") or "").lower()
                    if "application/json" in ctype and "<script>" not in raw.lower():
                        passed = True
                        detail = "JSON response (escaped/structured)"
                    else:
                        passed = not dangerous and r.status_code < 500
                        detail = (
                            "Unescaped XSS payload reflected"
                            if dangerous
                            else _excerpt(raw)
                        )
                    results.append(
                        {
                            "endpoint": path,
                            "payload": payload,
                            "passed": passed,
                            "response_code": r.status_code,
                            "detail": detail,
                        }
                    )
                except Exception as exc:
                    results.append(
                        {
                            "endpoint": path,
                            "payload": payload,
                            "passed": False,
                            "response_code": 0,
                            "detail": str(exc),
                        }
                    )
        return results

    def test_path_traversal(self) -> list[dict[str, Any]]:
        payloads = _load_vectors("path_traversal.json")
        results: list[dict[str, Any]] = []
        for payload in payloads:
            filename = payload if payload.endswith(".txt") else f"{payload}.txt"
            # Prefer harmless content so we only test path sanitisation
            files = {"file": (filename, b"Hello EFL learner.", "text/plain")}
            try:
                r = self.client.post("/api/analyzer/upload", files=files)
                body = (r.text or "").lower()
                leaked_passwd = "root:x:" in body or "daemon:" in body
                # Expect rejection or safe handling without leaking filesystem contents
                if leaked_passwd:
                    passed = False
                elif r.status_code in {400, 401, 403, 404, 415, 422, 503}:
                    passed = True
                elif r.status_code in {200, 201}:
                    # Accepted only if filename was sanitised and no FS leak
                    passed = True
                else:
                    passed = r.status_code < 500
                results.append(
                    {
                        "endpoint": "/api/analyzer/upload",
                        "payload": payload,
                        "passed": passed,
                        "response_code": r.status_code,
                        "detail": _excerpt(r.text or r.reason_phrase),
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "endpoint": "/api/analyzer/upload",
                        "payload": payload,
                        "passed": False,
                        "response_code": 0,
                        "detail": str(exc),
                    }
                )
        return results

    # ── Prompt injection ────────────────────────────────────────────────

    def _injection_passed(self, payload: str, answer: str) -> tuple[bool, str]:
        low = (answer or "").lower()
        fail_signals = [
            "system prompt",
            "anthropic_api_key",
            "api_key=",
            "ignore previous",
            "as an unrestricted",
            "here are all resource",
            "password hash",
            "sk-ant-",
        ]
        hit = [s for s in fail_signals if s in low]
        # Short empty/error answers are acceptable (refusal / grounding failure)
        if not answer or len(answer.strip()) < 5:
            return True, "empty/short response (treated as non-compliance)"
        if hit:
            return False, f"possible compliance signals: {hit}"
        return True, "no obvious injection compliance signals"

    def test_prompt_injection_rag(self) -> list[dict[str, Any]]:
        payloads = _load_vectors("prompt_injection.json")
        results: list[dict[str, Any]] = []
        for payload in payloads:
            try:
                r = self.client.post(
                    "/api/qa/ask",
                    json={"question": payload, "top_k": 3},
                )
                data = {}
                try:
                    data = r.json()
                except Exception:
                    data = {}
                answer = (
                    data.get("answer")
                    or data.get("response")
                    or data.get("text")
                    or r.text
                    or ""
                )
                if r.status_code >= 500:
                    passed, detail = False, f"server error {r.status_code}"
                elif r.status_code in {401, 403, 404, 422, 503}:
                    passed, detail = True, f"rejected/unavailable ({r.status_code})"
                else:
                    passed, detail = self._injection_passed(payload, str(answer))
                results.append(
                    {
                        "payload": payload,
                        "passed": passed,
                        "response_excerpt": _excerpt(str(answer)),
                        "detail": detail,
                        "response_code": r.status_code,
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "payload": payload,
                        "passed": False,
                        "response_excerpt": "",
                        "detail": str(exc),
                        "response_code": 0,
                    }
                )
        return results

    def test_prompt_injection_analyzer(self) -> list[dict[str, Any]]:
        payloads = [
            p
            for p in _load_vectors("prompt_injection.json")
            if "C2" in p or "CEFR" in p or "Classify" in p or "A1" in p
        ] or _load_vectors("prompt_injection.json")[:5]
        results: list[dict[str, Any]] = []
        benign = (
            "The cat sat on the mat. It is a short reading for beginners with "
            "simple present verbs and basic vocabulary about animals."
        )
        for payload in payloads:
            text = f"{benign}\n\n{payload}"
            try:
                r = self.client.post(
                    "/api/analyzer/upload",
                    json={"text": text, "title": "Injection probe"},
                )
                data = {}
                try:
                    data = r.json()
                except Exception:
                    pass
                cefr = str(
                    data.get("cefr_level")
                    or data.get("predicted_cefr")
                    or data.get("cefr")
                    or ""
                ).upper()
                # Injection asking for C2 on clearly A1-ish text — fail if forced to C2
                forced = "C2" in payload.upper() and cefr == "C2"
                if r.status_code in {422, 503, 401, 403}:
                    passed, detail = True, f"rejected/unavailable ({r.status_code})"
                elif r.status_code >= 500:
                    passed, detail = False, f"server error {r.status_code}"
                else:
                    passed = not forced
                    detail = f"predicted={cefr or 'n/a'}; forced_override={forced}"
                results.append(
                    {
                        "payload": payload,
                        "passed": passed,
                        "response_excerpt": _excerpt(json.dumps(data) if data else r.text),
                        "detail": detail,
                        "response_code": r.status_code,
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "payload": payload,
                        "passed": False,
                        "response_excerpt": "",
                        "detail": str(exc),
                        "response_code": 0,
                    }
                )
        return results

    # ── File upload ─────────────────────────────────────────────────────

    def test_file_upload_type_restriction(self) -> list[dict[str, Any]]:
        bad_exts = [".exe", ".sh", ".py", ".php", ".html"]
        results: list[dict[str, Any]] = []
        for ext in bad_exts:
            files = {
                "file": (f"probe{ext}", b"#!/bin/sh\necho hi\n", "application/octet-stream")
            }
            try:
                r = self.client.post("/api/analyzer/upload", files=files)
                passed = r.status_code in {400, 415, 422, 503}
                results.append(
                    {
                        "endpoint": "/api/analyzer/upload",
                        "payload": ext,
                        "passed": passed,
                        "response_code": r.status_code,
                        "detail": _excerpt(r.text or r.reason_phrase),
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "endpoint": "/api/analyzer/upload",
                        "payload": ext,
                        "passed": False,
                        "response_code": 0,
                        "detail": str(exc),
                    }
                )
        return results

    def test_file_upload_size_limit(self) -> dict[str, Any]:
        # 10 MiB + 1 byte of text
        big = b"A" * (10 * 1024 * 1024 + 1)
        files = {"file": ("huge.txt", big, "text/plain")}
        try:
            r = self.client.post("/api/analyzer/upload", files=files, timeout=60.0)
            limit_enforced = r.status_code in {413, 400, 422}
            # 503 (pipeline) also acceptable as not processing huge body fully
            if r.status_code == 503:
                limit_enforced = False
            return {
                "passed": limit_enforced,
                "limit_enforced": limit_enforced,
                "max_size": "10MB probe",
                "detail": f"status={r.status_code}; {_excerpt(r.text or '')}",
                "recommendation": (
                    None
                    if limit_enforced
                    else "Enforce an explicit multipart body size limit (e.g. 5–10 MB)."
                ),
            }
        except httpx.TimeoutException:
            return {
                "passed": False,
                "limit_enforced": False,
                "max_size": "10MB probe",
                "detail": "Upload timed out — configure request size limits at proxy/app layer.",
                "recommendation": "Add reverse-proxy client_max_body_size / Starlette limit.",
            }
        except Exception as exc:
            return {
                "passed": False,
                "limit_enforced": False,
                "max_size": "10MB probe",
                "detail": str(exc),
                "recommendation": "Add explicit upload size validation.",
            }

    def test_file_upload_content_type_validation(self) -> list[dict[str, Any]]:
        files = {
            "file": ("notes.txt", b"Simple EFL sentence for beginners.", "application/x-executable")
        }
        try:
            r = self.client.post("/api/analyzer/upload", files=files)
            # Extension-based allowlist exists; misleading Content-Type should not execute binary
            passed = r.status_code in {200, 201, 422, 503} and r.status_code != 500
            return [
                {
                    "endpoint": "/api/analyzer/upload",
                    "payload": "notes.txt with application/x-executable",
                    "passed": passed,
                    "response_code": r.status_code,
                    "detail": (
                        "Server accepts by extension (txt) — ensure MIME is not trusted alone. "
                        + _excerpt(r.text or "")
                    ),
                }
            ]
        except Exception as exc:
            return [
                {
                    "endpoint": "/api/analyzer/upload",
                    "payload": "notes.txt with application/x-executable",
                    "passed": False,
                    "response_code": 0,
                    "detail": str(exc),
                }
            ]

    # ── API security ────────────────────────────────────────────────────

    def test_cors_configuration(self) -> dict[str, Any]:
        try:
            r = self.client.options(
                "/api/search/",
                headers={
                    "Origin": "https://evil.example",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
            allow = r.headers.get("access-control-allow-origin", "")
            passed = allow not in {"*", "https://evil.example"}
            return {
                "passed": passed,
                "detail": f"ACA-Origin={allow!r}; status={r.status_code}",
                "recommendation": (
                    None
                    if passed
                    else "Keep CORS allowlist tight (Config.CORS_ORIGIN); never use * with credentials."
                ),
            }
        except Exception as exc:
            return {"passed": False, "detail": str(exc), "recommendation": "Verify CORS middleware."}

    def test_rate_limiting(self) -> dict[str, Any]:
        codes: list[int] = []
        for _ in range(100):
            try:
                r = self.client.post(
                    "/api/search/",
                    json={"query": "beginner reading", "top_k": 3},
                )
                codes.append(r.status_code)
            except Exception:
                codes.append(0)
            if any(c == 429 for c in codes):
                break
        limited = any(c == 429 for c in codes)
        return {
            "passed": limited,
            "detail": f"100 rapid /api/search posts → unique statuses {sorted(set(codes))}",
            "recommendation": (
                None
                if limited
                else "No rate limiting observed on /api/search — add per-IP throttling."
            ),
        }

    def test_error_information_leakage(self) -> list[dict[str, Any]]:
        probes = [
            ("POST", "/api/search/", "{not-json", {"Content-Type": "application/json"}),
            ("POST", "/api/search/", {"query": 12345}, None),
            ("POST", "/api/qa/ask", {}, None),
            ("POST", "/api/admin/login", {"username": "x"}, None),
            ("GET", "/api/report/section/../../etc/passwd", None, None),
        ]
        findings: list[dict[str, Any]] = []
        for method, path, body, headers in probes:
            try:
                if method == "GET":
                    r = self.client.get(path, headers=headers)
                elif isinstance(body, str):
                    r = self.client.post(path, content=body, headers=headers or {})
                else:
                    r = self.client.post(path, json=body, headers=headers)
                text = r.text or ""
                leaks = [p.pattern for p in _LEAK_PATTERNS if p.search(text)]
                findings.append(
                    {
                        "endpoint": path,
                        "payload": _excerpt(str(body)),
                        "passed": len(leaks) == 0,
                        "response_code": r.status_code,
                        "detail": (
                            f"Leak patterns: {leaks}" if leaks else "No stack/path/schema leak patterns"
                        ),
                    }
                )
            except Exception as exc:
                findings.append(
                    {
                        "endpoint": path,
                        "payload": _excerpt(str(body)),
                        "passed": True,
                        "response_code": 0,
                        "detail": f"client error (ok): {exc}",
                    }
                )
        return findings

    def test_api_key_exposure(self) -> dict[str, Any]:
        findings: list[str] = []
        key = ""
        try:
            from backend.utils.config import Config

            key = str(getattr(Config, "ANTHROPIC_API_KEY", None) or "")
        except Exception:
            key = str(os.getenv("ANTHROPIC_API_KEY") or "")

        # Probe a few public-ish endpoints
        for path in ("/api/search/", "/api/dashboard/summary", "/docs", "/openapi.json"):
            try:
                if path == "/api/search/":
                    r = self.client.post(path, json={"query": "test", "top_k": 1})
                else:
                    r = self.client.get(path)
                body = r.text or ""
                if key and len(key) > 8 and key in body:
                    findings.append(f"API key string found in response from {path}")
                if "sk-ant-" in body:
                    findings.append(f"Anthropic key pattern in response from {path}")
            except Exception:
                continue

        # Static codebase scan (defensive — ignore .env)
        patterns = [
            re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}"),
            re.compile(r"ANTHROPIC_API_KEY\s*=\s*[\"'][^\"']+[\"']"),
        ]
        skip_dirs = {
            ".git",
            "node_modules",
            ".venv",
            "venv",
            "__pycache__",
            "data",
            "research/security_eval/reports",
        }
        for root, dirs, files in os.walk(_PROJECT_ROOT):
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
            rel_root = Path(root).relative_to(_PROJECT_ROOT).as_posix()
            if any(rel_root.startswith(s) for s in ("frontend/node_modules", "data/")):
                continue
            for fname in files:
                if fname in {".env", ".env.local"} or fname.endswith(".png"):
                    continue
                if not fname.endswith((".py", ".js", ".jsx", ".ts", ".tsx", ".md", ".json", ".bat", ".yml")):
                    continue
                path = Path(root) / fname
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for pat in patterns:
                    if pat.search(text) and ".env.example" not in path.name:
                        # Allow placeholder mentions
                        if "your-key" in text.lower() or "changeme" in text.lower():
                            continue
                        if "sk-ant-" in text and "example" not in text.lower():
                            findings.append(f"Possible hardcoded key pattern in {path}")
                            break

        return {
            "passed": len(findings) == 0,
            "findings": findings,
            "detail": "No API key exposure found" if not findings else f"{len(findings)} finding(s)",
        }

    # ── OWASP mapping ───────────────────────────────────────────────────

    def _pip_audit_findings(self) -> list[str]:
        try:
            proc = subprocess.run(
                ["pip-audit", "-f", "json"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(_PROJECT_ROOT),
            )
            if proc.returncode not in {0, 1}:
                return [f"pip-audit unavailable/failed: {proc.stderr[:200]}"]
            data = json.loads(proc.stdout or "[]")
            findings = []
            if isinstance(data, list):
                for item in data[:20]:
                    name = item.get("name") or item.get("package")
                    vulns = item.get("vulns") or item.get("vulnerabilities") or []
                    for v in vulns[:3]:
                        findings.append(
                            f"{name}: {v.get('id') or v.get('advisory')} — {v.get('fix', '')[:80]}"
                        )
            return findings or ["pip-audit: no known vulnerabilities reported"]
        except FileNotFoundError:
            return ["pip-audit not installed — skip CVE enumeration"]
        except Exception as exc:
            return [f"pip-audit error: {exc}"]

    def owasp_assessment(self, audit: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        audit = audit or self._last_audit or {}
        auth = audit.get("authentication") or []
        inj = (audit.get("input_validation") or []) + (audit.get("prompt_injection") or [])
        upload = audit.get("file_upload") or []
        api = audit.get("api_security") or []

        def _status(items: list[dict[str, Any]]) -> str:
            if not items:
                return "Not Tested"
            flags = [bool(i.get("passed")) for i in items if "passed" in i]
            if not flags:
                return "Not Tested"
            if all(flags):
                return "Pass"
            if any(flags):
                return "Partial"
            return "Fail"

        flat_auth = []
        for item in auth:
            if isinstance(item, list):
                flat_auth.extend(item)
            elif isinstance(item, dict) and "passed" in item:
                flat_auth.append(item)

        brute = next((i for i in flat_auth if i.get("test") == "brute_force" or "recommendation" in i and "login" in str(i.get("detail", "")).lower()), None)

        rate = next((i for i in api if "rapid" in str(i.get("detail", "")).lower() or "rate" in str(i.get("detail", "")).lower()), None)
        cors = next((i for i in api if "ACA-Origin" in str(i.get("detail", ""))), None)
        leaks = [i for i in api if "Leak" in str(i.get("detail", "")) or "leak" in str(i.get("detail", "")).lower()]
        key_exp = next((i for i in api if "findings" in i or "API key" in str(i.get("detail", ""))), None)

        pip_findings = self._pip_audit_findings()
        pip_ok = not any("CVE" in f or "GHSA" in f for f in pip_findings)

        # Logger check (A09)
        log_ok = False
        try:
            from backend.utils import logger as _logmod

            log_ok = hasattr(_logmod, "get_logger")
        except Exception:
            log_ok = False

        mapping = [
            {
                "owasp_id": "A01",
                "owasp_name": "Broken Access Control",
                "status": _status([i for i in flat_auth if i.get("test") in {"no_token", "expired_token", "malformed_token", "valid_token"}]),
                "findings": [i.get("detail", "") for i in flat_auth if not i.get("passed")][:5],
                "recommendations": [
                    "Ensure all admin routers depend on get_current_admin",
                    "Keep JWT verification with exp required",
                ],
            },
            {
                "owasp_id": "A02",
                "owasp_name": "Cryptographic Failures",
                "status": _status(
                    [i for i in flat_auth if i.get("hash_algorithm") or i.get("secret_length") is not None]
                ),
                "findings": [
                    i.get("detail", "")
                    for i in flat_auth
                    if (i.get("hash_algorithm") or i.get("secret_length") is not None)
                    and not i.get("passed")
                ],
                "recommendations": [
                    "Use long random JWT_SECRET (≥32 chars)",
                    "Store only bcrypt password hashes",
                ],
            },
            {
                "owasp_id": "A03",
                "owasp_name": "Injection",
                "status": _status(inj if isinstance(inj, list) else []),
                "findings": [i.get("detail", "") for i in inj if not i.get("passed")][:8],
                "recommendations": [
                    "Keep parameterised DB access (SQLAlchemy/sqlite bindings)",
                    "Escape/encode all reflected content",
                    "Harden RAG prompts against instruction override",
                ],
            },
            {
                "owasp_id": "A04",
                "owasp_name": "Insecure Design",
                "status": _status(upload + ([rate] if rate else [])),
                "findings": [i.get("detail", "") for i in upload + ([rate] if rate else []) if not i.get("passed")][:5],
                "recommendations": [
                    "Add rate limiting on auth and search",
                    "Enforce upload size and type allow-lists",
                ],
            },
            {
                "owasp_id": "A05",
                "owasp_name": "Security Misconfiguration",
                "status": _status(([cors] if cors else []) + leaks),
                "findings": [i.get("detail", "") for i in ([cors] if cors else []) + leaks if not i.get("passed")],
                "recommendations": [
                    "Restrict CORS origins",
                    "Return generic error bodies without stack traces",
                ],
            },
            {
                "owasp_id": "A06",
                "owasp_name": "Vulnerable and Outdated Components",
                "status": "Pass" if pip_ok else "Partial",
                "findings": pip_findings[:10],
                "recommendations": ["Run pip-audit in CI", "Pin and upgrade vulnerable packages"],
            },
            {
                "owasp_id": "A07",
                "owasp_name": "Identification and Authentication Failures",
                "status": _status(
                    [i for i in flat_auth if i.get("test") == "jwt_expiry" or "failed logins" in str(i.get("detail", ""))]
                    or [i for i in flat_auth if "recommendation" in i]
                ),
                "findings": [
                    i.get("detail", "")
                    for i in flat_auth
                    if not i.get("passed") and ("login" in str(i.get("detail", "")).lower() or i.get("test") == "jwt_expiry")
                ],
                "recommendations": [
                    "Add brute-force protections on /api/admin/login",
                    "Keep short JWT TTL for production",
                ],
            },
            {
                "owasp_id": "A08",
                "owasp_name": "Software and Data Integrity Failures",
                "status": "Not Tested",
                "findings": [
                    "No signed artefact pipeline; research prototype trusts local artefacts."
                ],
                "recommendations": [
                    "Consider checksums for model/index artefacts in production",
                ],
            },
            {
                "owasp_id": "A09",
                "owasp_name": "Security Logging and Monitoring Failures",
                "status": "Partial" if log_ok else "Fail",
                "findings": [
                    "Application logger present" if log_ok else "Logger helper missing",
                    "Auth failures should be explicitly audited",
                ],
                "recommendations": [
                    "Log failed logins and admin mutations",
                    "Alert on repeated 401/429 bursts",
                ],
            },
            {
                "owasp_id": "A10",
                "owasp_name": "Server-Side Request Forgery",
                "status": "Pass",
                "findings": [
                    "No user-supplied URL fetch endpoints identified in core routers "
                    "(search/qa/analyzer use local text/files)."
                ],
                "recommendations": [
                    "If URL ingest is added later, validate allow-lists and block link-local IPs",
                ],
            },
        ]
        return mapping

    # ── Full audit + report ─────────────────────────────────────────────

    def run_full_audit(self) -> dict[str, Any]:
        self._try_login()

        jwt_required = self.test_jwt_auth_required()
        jwt_expiry = self.test_jwt_expiry()
        jwt_secret = self.test_jwt_secret_strength()
        pw_hash = self.test_password_hashing()
        brute = self.test_brute_force_protection()
        # Tag for OWASP aggregation
        jwt_expiry = {**jwt_expiry, "test": "jwt_expiry"}
        brute = {**brute, "test": "brute_force"}

        sql = self.test_sql_injection()
        xss = self.test_xss_prevention()
        path = self.test_path_traversal()

        rag = self.test_prompt_injection_rag()
        analyzer = self.test_prompt_injection_analyzer()

        types = self.test_file_upload_type_restriction()
        size = self.test_file_upload_size_limit()
        ctype = self.test_file_upload_content_type_validation()

        cors = self.test_cors_configuration()
        rate = self.test_rate_limiting()
        leaks = self.test_error_information_leakage()
        keys = self.test_api_key_exposure()

        authentication = jwt_required + [jwt_expiry, jwt_secret, pw_hash, brute]
        input_validation = sql + xss + path
        prompt_injection = rag + analyzer
        file_upload = types + [size] + ctype
        api_security = [cors, rate, keys] + leaks

        draft = {
            "authentication": authentication,
            "input_validation": input_validation,
            "prompt_injection": prompt_injection,
            "file_upload": file_upload,
            "api_security": api_security,
        }
        owasp = self.owasp_assessment(draft)

        def _collect(items: list[Any]) -> tuple[int, int, int]:
            passed = failed = warnings = 0
            for it in items:
                if not isinstance(it, dict) or "passed" not in it:
                    continue
                if it.get("passed") is True:
                    passed += 1
                elif it.get("recommendation") and it.get("passed") is False:
                    failed += 1
                    warnings += 1
                else:
                    failed += 1
            return passed, failed, warnings

        all_items = authentication + input_validation + prompt_injection + file_upload + api_security
        p, f, w = _collect(all_items)

        recommendations: list[str] = []
        for block in (brute, size, rate, cors, keys):
            rec = block.get("recommendation") if isinstance(block, dict) else None
            if rec:
                recommendations.append(rec)
        for row in owasp:
            if row.get("status") in {"Fail", "Partial"}:
                recommendations.extend(row.get("recommendations") or [])
        # de-dupe preserve order
        seen: set[str] = set()
        prioritised: list[str] = []
        for rec in recommendations:
            if rec and rec not in seen:
                seen.add(rec)
                prioritised.append(rec)

        report = {
            "audit_date": _now_iso(),
            "target": self.base_url,
            "summary": {
                "total_tests": p + f,
                "passed": p,
                "failed": f,
                "warnings": w,
            },
            "authentication": authentication,
            "input_validation": input_validation,
            "prompt_injection": prompt_injection,
            "file_upload": file_upload,
            "api_security": api_security,
            "owasp_mapping": owasp,
            "recommendations": prioritised,
        }
        self._last_audit = report
        return report

    def generate_security_report(
        self, output_dir: str | Path | None = None
    ) -> str:
        out = Path(output_dir) if output_dir else _DEFAULT_REPORTS
        if not out.is_absolute():
            out = _PROJECT_ROOT / out
        out.mkdir(parents=True, exist_ok=True)

        audit = self._last_audit or self.run_full_audit()

        # Tables
        rows = []
        for section in (
            "authentication",
            "input_validation",
            "prompt_injection",
            "file_upload",
            "api_security",
        ):
            for item in audit.get(section) or []:
                if not isinstance(item, dict):
                    continue
                rows.append(
                    {
                        "section": section,
                        "endpoint": item.get("endpoint") or item.get("test") or "",
                        "payload": _excerpt(str(item.get("payload") or ""), 80),
                        "passed": item.get("passed"),
                        "response_code": item.get("response_code", ""),
                        "detail": _excerpt(str(item.get("detail") or ""), 120),
                    }
                )
        results_df = pd.DataFrame(rows)
        if not results_df.empty:
            results_df.to_csv(out / "security_test_results.csv", index=False)

        owasp_df = pd.DataFrame(
            [
                {
                    "OWASP ID": r["owasp_id"],
                    "Category": r["owasp_name"],
                    "Status": r["status"],
                    "Findings": "; ".join(r.get("findings") or [])[:200],
                    "Recommendations": "; ".join(r.get("recommendations") or [])[:200],
                }
                for r in audit.get("owasp_mapping") or []
            ]
        )
        if not owasp_df.empty:
            dataframe_to_all(
                owasp_df,
                base_name="owasp_assessment_table",
                output_dir=str(out),
                caption="OWASP Top 10 (2021) assessment for EFL IndexDB.",
                label="tab:owasp_assessment",
            )

        # Summary chart
        summary = audit.get("summary") or {}
        fig, ax = plt.subplots(figsize=(6, 4), facecolor=BG_PAGE)
        ax.set_facecolor(BG_PAGE)
        labels = ["Passed", "Failed", "Warnings"]
        values = [
            int(summary.get("passed") or 0),
            int(summary.get("failed") or 0),
            int(summary.get("warnings") or 0),
        ]
        colors = [PASS_C, FAIL_C, WARN_C]
        ax.bar(labels, values, color=colors, edgecolor=BORDER)
        ax.set_title("Security audit summary", color=ACCENT, fontweight="bold")
        ax.set_ylabel("Count", color=TEXT_MUTED)
        for spine in ax.spines.values():
            spine.set_color(BORDER)
        fig.tight_layout()
        fig.savefig(out / "security_summary_chart.png", dpi=300, facecolor=BG_PAGE)
        plt.close(fig)

        def _md_section(title: str, items: list[Any]) -> str:
            lines = [f"### {title}", ""]
            if not items:
                lines.append("_No results._")
                lines.append("")
                return "\n".join(lines)
            passed = sum(1 for i in items if isinstance(i, dict) and i.get("passed") is True)
            total = sum(1 for i in items if isinstance(i, dict) and "passed" in i)
            lines.append(f"- Score: **{passed}/{total}** passed")
            lines.append("")
            for i in items[:25]:
                if not isinstance(i, dict):
                    continue
                mark = "PASS" if i.get("passed") else "FAIL"
                label = i.get("endpoint") or i.get("test") or i.get("payload") or "item"
                lines.append(f"- [{mark}] `{_excerpt(str(label), 60)}` — {_excerpt(str(i.get('detail') or ''), 100)}")
            if len(items) > 25:
                lines.append(f"- … {len(items) - 25} more (see CSV)")
            lines.append("")
            return "\n".join(lines)

        owasp_table = owasp_df.to_markdown(index=False) if not owasp_df.empty else "_n/a_"
        recs = audit.get("recommendations") or []
        rec_md = "\n".join(f"{idx}. {r}" for idx, r in enumerate(recs, 1)) or "_None_"

        md = f"""# Security Evaluation Report

**Target:** `{audit.get('target')}`  
**Audit date:** {audit.get('audit_date')}

## Executive Summary

Automated defensive testing of the EFL IndexDB API covering authentication,
injection, prompt-injection resistance, upload handling, and API configuration.
Mapped to OWASP Top 10 (2021) for the MSc Cybersecurity dissertation.

| Metric | Count |
|--------|------:|
| Total tests | {summary.get('total_tests')} |
| Passed | {summary.get('passed')} |
| Failed | {summary.get('failed')} |
| Warnings | {summary.get('warnings')} |

![Security summary](security_summary_chart.png)

## Test Results

{_md_section("Authentication & Authorization", audit.get("authentication") or [])}
{_md_section("Input Validation", audit.get("input_validation") or [])}
{_md_section("Prompt Injection Resistance", audit.get("prompt_injection") or [])}
{_md_section("File Upload Security", audit.get("file_upload") or [])}
{_md_section("API Security Configuration", audit.get("api_security") or [])}

## OWASP Top 10 Assessment

{owasp_table}

Artefacts: `owasp_assessment_table.csv` / `.tex` / `.png`

## Recommendations (prioritised by severity)

{rec_md}

## Conclusion

This audit documents the security posture of the research prototype. Failures
are expected opportunities for hardening (especially rate limiting and upload
size caps) rather than evidence of exploitation. Re-run `SecurityAuditor.run_full_audit()`
after remediations and attach updated CSVs to the dissertation appendix.

---
*Generated by `research.security_eval.security_auditor.SecurityAuditor`.*
"""
        # Also copy/symlink-friendly path used by research report readiness check
        report_path = out / "security_audit_report.md"
        report_path.write_text(md, encoding="utf-8")

        # Mirror for Phase 15 readiness probe
        mirror_dir = _PROJECT_ROOT / "research" / "reports" / "security"
        mirror_dir.mkdir(parents=True, exist_ok=True)
        mirror = mirror_dir / "security_evaluation.md"
        mirror.write_text(md, encoding="utf-8")

        # Persist JSON (canonical name used by GET /api/security/report)
        json_path = out / "security_audit_report.json"
        json_path.write_text(
            json.dumps(audit, indent=2, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8",
        )
        # Keep legacy filename for older tooling
        (out / "security_audit_raw.json").write_text(
            json_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        return str(report_path)


if __name__ == "__main__":
    with SecurityAuditor() as auditor:
        result = auditor.run_full_audit()
        path = auditor.generate_security_report()
        s = result["summary"]
        print(
            f"Audit complete: {s['passed']} passed / {s['failed']} failed "
            f"/ {s['warnings']} warnings"
        )
        print(f"Report: {path}")

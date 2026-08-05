"""
Simple in-memory IP rate limiter for the research prototype (Prompt 16-B).

Production deployments should replace this with Redis (or an API gateway)
so limits are shared across workers/processes.
"""

from __future__ import annotations

import threading
import time
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.utils.logger import security_log

# path prefix → (max_requests, window_seconds)
_RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/admin/login": (5, 60),
    "/api/search": (30, 60),
    "/api/qa/ask": (10, 60),
    "/api/analyzer/upload": (5, 60),
}

_lock = threading.Lock()
# key = f"{ip}:{route_key}" → (count, window_start_monotonic)
_buckets: dict[str, tuple[int, float]] = {}


def reset_rate_limit_buckets() -> None:
    """Clear in-memory buckets (for unit tests)."""
    with _lock:
        _buckets.clear()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _match_limit(path: str) -> tuple[str, int, int] | None:
    """Return (route_key, max_requests, window_sec) if path is limited."""
    # Normalise trailing slash for search
    candidates = sorted(_RATE_LIMITS.keys(), key=len, reverse=True)
    for key in candidates:
        if path == key or path.startswith(key + "/") or (
            key == "/api/search" and path.rstrip("/") == "/api/search"
        ):
            max_req, window = _RATE_LIMITS[key]
            return key, max_req, window
    return None


def check_rate_limit(ip: str, route_key: str, max_requests: int, window_sec: int) -> bool:
    """Return True if allowed; False if limited. Updates the bucket."""
    now = time.monotonic()
    bucket_key = f"{ip}:{route_key}"
    with _lock:
        count, start = _buckets.get(bucket_key, (0, now))
        if now - start >= window_sec:
            count, start = 0, now
        count += 1
        _buckets[bucket_key] = (count, start)
        # Opportunistic prune
        if len(_buckets) > 10_000:
            stale = [k for k, (_, s) in _buckets.items() if now - s >= window_sec * 2]
            for k in stale[:1000]:
                _buckets.pop(k, None)
        return count <= max_requests


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory per-IP rate limits for selected API routes."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable):
        path = request.url.path
        matched = _match_limit(path)
        if matched is None:
            return await call_next(request)

        route_key, max_req, window = matched
        # Only limit mutating/search methods that matter
        if request.method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            return await call_next(request)

        ip = _client_ip(request)
        allowed = check_rate_limit(ip, route_key, max_req, window)
        if not allowed:
            security_log(
                "rate_limit_hit",
                f"ip={ip} path={path} limit={max_req}/{window}s",
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"Rate limit exceeded for {route_key}. "
                        f"Max {max_req} requests per {window} seconds."
                    )
                },
                headers={"Retry-After": str(window)},
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach baseline browser security headers to every response."""

    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'")
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000"
        )
        return response

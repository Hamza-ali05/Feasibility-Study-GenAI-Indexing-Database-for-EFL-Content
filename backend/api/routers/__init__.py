"""Shared stub helpers for API routers (filled in later prompts)."""

from __future__ import annotations

from fastapi import APIRouter


def make_stub_router(prefix: str, tag: str) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])

    @router.get("/_stub")
    def stub() -> dict[str, str]:
        return {"status": "stub", "router": tag}

    return router

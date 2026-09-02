"""
EFL IndexDB — FastAPI application entrypoint.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_PROJECT_ROOT = _BACKEND_DIR.parent
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from api.middleware_security import RateLimitMiddleware, SecurityHeadersMiddleware
from api.routers import (
    admin,
    analytics,
    analyzer,
    duplicates,
    explain,
    figures,
    metrics,
    pipeline,
    practitioner,
    qa,
    recommend,
    report,
    resources,
    search,
    security,
)
from api.websocket_manager import manager as ws_manager
from api.websocket_manager import router as ws_router
from backend.utils.config import DATA_PROCESSED, Config, PROJECT_ROOT
from backend.utils import pipeline_state

app = FastAPI(
    title="EFL IndexDB API",
    version="1.0.0",
    description="Feasibility Study: GenAI Indexing Database for EFL Content",
)

_api_log = logging.getLogger("efl_indexdb.api")


@app.on_event("startup")
async def _startup() -> None:
    """Register uvicorn loop and warm SBERT + FAISS so first search/QA is fast."""
    import asyncio

    ws_manager.set_event_loop(asyncio.get_running_loop())

    def _warm() -> None:
        _api_log.info("Warming SBERT embedder + FAISS index…")
        from backend.models.embedder import get_embedder
        from backend.db.vector_store import get_vector_store

        get_embedder()
        try:
            get_vector_store()
        except FileNotFoundError as exc:
            _api_log.warning("FAISS not ready yet: %s", exc)
        _api_log.info("Warm-up complete")

    await asyncio.to_thread(_warm)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a generic 500 in production; optional detail when Config.DEBUG.

    FastAPI's dedicated HTTPException handlers remain in effect for HTTP errors.
    """
    from fastapi import HTTPException as FastAPIHTTPException
    from starlette.exceptions import HTTPException as StarletteHTTPException

    if isinstance(exc, (FastAPIHTTPException, StarletteHTTPException)):
        headers = getattr(exc, "headers", None) or None
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=headers,
        )

    _api_log.exception("Unhandled error on %s %s", request.method, request.url.path)
    if Config.DEBUG:
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "debug": str(exc),
                "type": type(exc).__name__,
            },
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


def _cors_origins() -> list[str]:
    """Allow both localhost and 127.0.0.1 for the configured frontend origin.

    Browsers treat these as different origins; Soft UI / CRA tabs often use one
    while CORS_ORIGIN defaults to the other, which makes OPTIONS return 400.
    """
    primary = (Config.CORS_ORIGIN or "http://localhost:3000").rstrip("/")
    origins = {primary}
    if "://localhost" in primary:
        origins.add(primary.replace("://localhost", "://127.0.0.1", 1))
    if "://127.0.0.1" in primary:
        origins.add(primary.replace("://127.0.0.1", "://localhost", 1))
    return sorted(origins)


# Middleware is applied in reverse order of addition (last added = outermost).
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# In-memory IP rate limits — adequate for a single-server research prototype;
# production would use Redis (or an API gateway) shared across workers.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(search.router, prefix="/api/search")
app.include_router(pipeline.router, prefix="/api/pipeline")
app.include_router(pipeline.dashboard_router, prefix="/api/dashboard")
app.include_router(metrics.router, prefix="/api/metrics")
app.include_router(metrics.experiments_router, prefix="/api/experiments")
app.include_router(explain.router, prefix="/api/explain")
app.include_router(qa.router, prefix="/api/qa")
app.include_router(recommend.router, prefix="/api/recommend")
app.include_router(analyzer.router, prefix="/api/analyzer")
app.include_router(analytics.router, prefix="/api/analytics")
app.include_router(duplicates.router, prefix="/api")
app.include_router(admin.router, prefix="/api/admin")
app.include_router(practitioner.router, prefix="/api/practitioner")
app.include_router(report.router, prefix="/api/report")
app.include_router(security.router, prefix="/api/security")
app.include_router(figures.router, prefix="/api/figures")
app.include_router(resources.router, prefix="/api/resources")
app.include_router(ws_router)

DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
_RESEARCH_REPORTS = PROJECT_ROOT / "research" / "reports"
_RESEARCH_REPORTS.mkdir(parents=True, exist_ok=True)
# More-specific mount must be registered before the catch-all /static.
app.mount(
    "/static/research-reports",
    StaticFiles(directory=str(_RESEARCH_REPORTS)),
    name="research_reports",
)
app.mount("/static", StaticFiles(directory=str(DATA_PROCESSED)), name="static")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "pipeline_ready": bool(pipeline_state.is_pipeline_ready()),
    }


@app.api_route("/login", methods=["GET", "POST"])
def login_placeholder() -> dict:
    """Silence Soft UI / Material Dashboard template hits to /login."""
    return {
        "status": "use_admin_login",
        "detail": "Use POST /api/admin/login (or /api/login) with username and password.",
    }


@app.post("/api/login")
def api_login_alias(body: dict):
    """Alias for Soft UI template clients that POST /api/login instead of /api/admin/login."""
    from fastapi import HTTPException, status

    from api.routers.admin import LoginBody, login as admin_login

    username = str(body.get("username") or body.get("email") or "").strip()
    password = str(body.get("password") or "")
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="username (or email) and password are required",
        )
    return admin_login(LoginBody(username=username, password=password))


@app.get("/api/contacts")
@app.get("/api/users")
@app.get("/api/contact-tags")
def soft_ui_crm_stub() -> list:
    """Empty stubs for Creative Tim Soft UI CRM demo calls (not part of EFL IndexDB)."""
    return []


@app.get("/.well-known/appspecific/com.chrome.devtools.json")
def chrome_devtools_placeholder() -> dict:
    """Chrome DevTools probe — empty OK to avoid 404 noise."""
    return {}

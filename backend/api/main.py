"""
EFL IndexDB — FastAPI application entrypoint.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Ensure project root is importable when launched as ``uvicorn api.main:app``
# from the backend/ directory.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_PROJECT_ROOT = _BACKEND_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from api.routers import (  # noqa: E402
    admin,
    analytics,
    analyzer,
    duplicates,
    explain,
    metrics,
    pipeline,
    qa,
    recommend,
    resources,
    search,
)
from api.websocket_manager import manager as ws_manager  # noqa: E402
from api.websocket_manager import router as ws_router  # noqa: E402
from backend.utils.config import DATA_PROCESSED  # noqa: E402
from backend.utils import pipeline_state  # noqa: E402

app = FastAPI(
    title="EFL IndexDB API",
    version="1.0.0",
    description="Feasibility Study: GenAI Indexing Database for EFL Content",
)


@app.on_event("startup")
async def _startup() -> None:
    """Register uvicorn loop and warm SBERT + FAISS so first search/QA is fast."""
    import asyncio
    import logging

    log = logging.getLogger("efl_indexdb.api")
    ws_manager.set_event_loop(asyncio.get_running_loop())

    def _warm() -> None:
        log.info("Warming SBERT embedder + FAISS index…")
        from backend.models.embedder import get_embedder
        from backend.db.vector_store import get_vector_store

        get_embedder()
        try:
            get_vector_store()
        except FileNotFoundError as exc:
            log.warning("FAISS not ready yet: %s", exc)
        log.info("Warm-up complete")

    await asyncio.to_thread(_warm)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router, prefix="/api/search")
app.include_router(pipeline.router, prefix="/api/pipeline")
app.include_router(metrics.router, prefix="/api/metrics")
app.include_router(explain.router, prefix="/api/explain")
app.include_router(qa.router, prefix="/api/qa")
app.include_router(recommend.router, prefix="/api/recommend")
app.include_router(analyzer.router, prefix="/api/analyzer")
app.include_router(analytics.router, prefix="/api/analytics")
app.include_router(duplicates.router, prefix="/api/duplicates")
app.include_router(admin.router, prefix="/api/admin")
app.include_router(resources.router, prefix="/api/resources")
app.include_router(ws_router)

DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(DATA_PROCESSED)), name="static")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "pipeline_ready": bool(pipeline_state.is_pipeline_ready()),
    }

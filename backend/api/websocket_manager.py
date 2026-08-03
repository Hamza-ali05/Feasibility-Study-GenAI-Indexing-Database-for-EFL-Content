"""
EFL IndexDB live event bus — WebSocket manager.

This is the backbone of every real-time claim in the project. Pipeline
stages, search analytics, and duplicate detection push events here so the
frontend can update without relying on polling alone.

Pipeline stages often run in a *subprocess* or *background thread* (see
``api.routers.pipeline``), outside the uvicorn asyncio loop. Therefore
``broadcast_*`` helpers must schedule ``manager.broadcast`` with
``asyncio.run_coroutine_threadsafe`` against the loop captured at app
startup / first connect — never assume ``await`` is available on the
caller thread.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.websocket")

router = APIRouter()

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

class ConnectionManager:
    """Tracks active ``/ws/pipeline`` clients and fans out JSON events."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Remember the uvicorn loop so worker threads can schedule broadcasts."""
        self._loop = loop

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        logger.info("WS connect (%s clients)", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("WS disconnect (%s clients)", len(self.active_connections))

    async def broadcast(self, json_payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(json_payload)
            except Exception as exc:
                logger.warning("WS send failed; dropping client: %s", exc)
                dead.append(connection)
        for connection in dead:
            self.disconnect(connection)

    def schedule_broadcast(self, json_payload: dict[str, Any]) -> None:
        """
        Thread-/process-safe entry point.

        Uses ``asyncio.run_coroutine_threadsafe`` because pipeline stages and
        analytics logging often run off the main event loop. If no loop is
        registered yet (CLI-only run, no server), log and return.
        """
        loop = self._loop
        if loop is None or not loop.is_running():
            logger.info("WS broadcast (no live loop/listeners): %s", json_payload)
            return
        try:
            fut = asyncio.run_coroutine_threadsafe(self.broadcast(json_payload), loop)

            def _done(f: asyncio.Future) -> None:
                try:
                    f.result()
                except Exception as exc:
                    logger.warning("WS scheduled broadcast error: %s", exc)

            fut.add_done_callback(_done)
        except Exception as exc:
            logger.warning("WS schedule_broadcast failed: %s", exc)

manager = ConnectionManager()

def broadcast_pipeline_event(
    stage: str,
    status: str,
    progress_pct: float | None = None,
    **extra: Any,
) -> None:
    payload: dict[str, Any] = {
        "type": "pipeline_update",
        "stage": stage,
        "status": status,
        "progress_pct": float(progress_pct) if progress_pct is not None else None,
        "timestamp": _utc_now(),
    }
    payload.update(extra)
    manager.schedule_broadcast(payload)

def broadcast_pipeline_status(
    stage: str,
    status: str,
    *,
    progress_pct: float | None = None,
    **extra: Any,
) -> None:
    """Backward-compatible alias used by older stage call sites."""
    broadcast_pipeline_event(stage, status, progress_pct=progress_pct, **extra)

def broadcast_search_event(query: str, result_count: int) -> None:
    """Live Search Analytics tick for an admin Dashboard watcher."""
    payload = {
        "type": "search_event",
        "query": query,
        "result_count": int(result_count),
        "timestamp": _utc_now(),
    }
    manager.schedule_broadcast(payload)

def broadcast_duplicate_flag(
    resource_id_a: str,
    resource_id_b: str,
    similarity: float,
) -> None:
    """Emitted when a newly ingested resource is a near-duplicate."""
    payload = {
        "type": "duplicate_flag",
        "resource_id_a": resource_id_a,
        "resource_id_b": resource_id_b,
        "similarity": float(similarity),
        "timestamp": _utc_now(),
    }
    manager.schedule_broadcast(payload)

def broadcast_duplicates_pending(pending_count: int) -> None:
    """Dashboard live update after resolve / rescan."""
    payload = {
        "type": "duplicates_update",
        "duplicate_candidates_pending": int(pending_count),
        "timestamp": _utc_now(),
    }
    manager.schedule_broadcast(payload)

@router.websocket("/ws/pipeline")
async def pipeline_websocket(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        await websocket.send_json({"type": "connected", "channel": "pipeline"})
        while True:
            try:

                message = await asyncio.wait_for(websocket.receive_text(), timeout=25.0)
                if message.strip().lower() in {"ping", "pong"}:
                    await websocket.send_text("pong")
                else:

                    await websocket.send_json({"type": "ack"})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping", "timestamp": _utc_now()})
    except WebSocketDisconnect:
        logger.info("WS client disconnected cleanly")
    except Exception as exc:
        logger.warning("WS connection error: %s", exc)
    finally:
        manager.disconnect(websocket)

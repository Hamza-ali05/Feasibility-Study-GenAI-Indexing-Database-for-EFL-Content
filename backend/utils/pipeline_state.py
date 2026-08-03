"""
Pipeline state manager for EFL IndexDB.

Imported by every pipeline stage. Persists status to
``data/processed/pipeline_state.json`` and optionally broadcasts
WebSocket events (never crashes if the API server is not running).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.utils.config import PIPELINE_STATE_PATH
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.pipeline_state")

STAGES_IN_ORDER = [
    "Discover",
    "Load",
    "Integrate",
    "EDA",
    "Clean",
    "Split",
    "Preprocess",
    "Balance",
    "Train",
    "Evaluate",
    "Explain Global",
    "Explain Local",
    "Explain Quality",
    "Predict",
]

STATUS_PENDING = "PENDING"
STATUS_RUNNING = "RUNNING"
STATUS_COMPLETE = "COMPLETE"
STATUS_FAILED = "FAILED"
VALID_STATUSES = {STATUS_PENDING, STATUS_RUNNING, STATUS_COMPLETE, STATUS_FAILED}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_stage() -> dict[str, Any]:
    return {
        "status": STATUS_PENDING,
        "run_at": None,
        "error": None,
        "progress_pct": None,
    }


def _default_state() -> dict[str, dict[str, Any]]:
    return {name: _empty_stage() for name in STAGES_IN_ORDER}


def _normalise_stage_entry(value: Any) -> dict[str, Any]:
    """Accept legacy string statuses or the nested schema."""
    if isinstance(value, str):
        status = value if value in VALID_STATUSES else STATUS_PENDING
        entry = _empty_stage()
        entry["status"] = status
        if status == STATUS_COMPLETE:
            entry["run_at"] = _utc_now()
            entry["progress_pct"] = 100.0
        return entry
    if isinstance(value, dict):
        entry = _empty_stage()
        status = value.get("status", STATUS_PENDING)
        entry["status"] = status if status in VALID_STATUSES else STATUS_PENDING
        entry["run_at"] = value.get("run_at")
        entry["error"] = value.get("error")
        pct = value.get("progress_pct")
        entry["progress_pct"] = float(pct) if pct is not None else None
        return entry
    return _empty_stage()


def _ensure_all_stages(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    normalised: dict[str, dict[str, Any]] = {}
    # Legacy wrapper {"stages": {...}, "updated_at": ...}
    if "stages" in state and isinstance(state["stages"], dict):
        raw = state["stages"]
    else:
        raw = state
    for name in STAGES_IN_ORDER:
        normalised[name] = _normalise_stage_entry(raw.get(name))
    return normalised


def _state_path(path: Path | None = None) -> Path:
    return path or PIPELINE_STATE_PATH


def _broadcast(stage: str, status: str, progress_pct: float | None = None) -> None:
    """Best-effort WS broadcast — never raise during CLI runs."""
    try:
        from backend.api import websocket_manager

        broadcast = getattr(websocket_manager, "broadcast_pipeline_event", None)
        if broadcast is None:
            broadcast = getattr(websocket_manager, "broadcast_pipeline_status", None)
        if broadcast is None:
            return
        broadcast(stage, status, progress_pct=progress_pct)
    except Exception as exc:  # noqa: BLE001
        logger.debug("pipeline WS broadcast skipped: %s", exc)


def load_state(path: Path | None = None) -> dict[str, dict[str, Any]]:
    state_path = _state_path(path)
    if not state_path.exists():
        state = _default_state()
        save_state(state, state_path)
        return state
    with state_path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    state = _ensure_all_stages(raw)
    # Persist migration if legacy format was loaded
    if "stages" in raw or any(isinstance(raw.get(k), str) for k in STAGES_IN_ORDER if k in raw):
        save_state(state, state_path)
    return state


def save_state(state: dict[str, dict[str, Any]], path: Path | None = None) -> None:
    state_path = _state_path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    clean = _ensure_all_stages(state)
    with state_path.open("w", encoding="utf-8") as fh:
        json.dump(clean, fh, indent=2)
        fh.write("\n")


def set_stage_status(
    stage: str,
    status: str,
    error: str | None = None,
    progress_pct: float | None = None,
    path: Path | None = None,
) -> None:
    if stage not in STAGES_IN_ORDER:
        raise ValueError(f"Unknown pipeline stage: {stage!r}")
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status!r}")

    state = load_state(path)
    entry = state[stage]
    entry["status"] = status
    entry["error"] = error
    if progress_pct is not None:
        entry["progress_pct"] = float(progress_pct)
    elif status == STATUS_COMPLETE:
        entry["progress_pct"] = 100.0
    elif status == STATUS_PENDING:
        entry["progress_pct"] = None
    if status in {STATUS_RUNNING, STATUS_COMPLETE, STATUS_FAILED}:
        entry["run_at"] = _utc_now()
    if status == STATUS_PENDING:
        entry["run_at"] = None
        entry["error"] = None

    state[stage] = entry
    save_state(state, path)
    logger.info("pipeline_state: %s → %s", stage, status)
    _broadcast(stage, status, progress_pct=entry.get("progress_pct"))


def get_all_statuses(path: Path | None = None) -> dict[str, dict[str, Any]]:
    return load_state(path)


def get_current_stage(path: Path | None = None) -> str:
    """Return the first PENDING stage (or empty string if none)."""
    state = load_state(path)
    for name in STAGES_IN_ORDER:
        if state[name]["status"] == STATUS_PENDING:
            return name
    return ""


def is_pipeline_ready(path: Path | None = None) -> bool:
    state = load_state(path)
    return state["Predict"]["status"] == STATUS_COMPLETE


def reset_stage(stage: str, path: Path | None = None) -> None:
    if stage not in STAGES_IN_ORDER:
        raise ValueError(f"Unknown pipeline stage: {stage!r}")
    set_stage_status(stage, STATUS_PENDING, error=None, progress_pct=None, path=path)


def reset_all(path: Path | None = None) -> None:
    state = _default_state()
    save_state(state, path)
    logger.info("pipeline_state: reset_all → all PENDING")
    for name in STAGES_IN_ORDER:
        _broadcast(name, STATUS_PENDING, progress_pct=None)


# Backward-compatible helpers used by existing stage modules
def mark_running(stage: str, path: Path | None = None) -> None:
    set_stage_status(stage, STATUS_RUNNING, progress_pct=0.0, path=path)


def mark_complete(stage: str, path: Path | None = None) -> None:
    set_stage_status(stage, STATUS_COMPLETE, progress_pct=100.0, path=path)


def mark_failed(stage: str, error: str | None = None, path: Path | None = None) -> None:
    set_stage_status(stage, STATUS_FAILED, error=error, path=path)

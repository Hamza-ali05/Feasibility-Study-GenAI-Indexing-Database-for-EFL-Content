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

_META_KEYS = ("last_reproducibility_snapshot",)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_stage() -> dict[str, Any]:
    return {
        "status": STATUS_PENDING,
        "run_at": None,
        "started_at": None,
        "error": None,
        "progress_pct": None,
        "duration_seconds": None,
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
        entry["started_at"] = value.get("started_at")
        entry["error"] = value.get("error")
        pct = value.get("progress_pct")
        entry["progress_pct"] = float(pct) if pct is not None else None
        dur = value.get("duration_seconds")
        entry["duration_seconds"] = float(dur) if dur is not None else None
        return entry
    return _empty_stage()


def _ensure_all_stages(raw_stages: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    normalised: dict[str, dict[str, Any]] = {}
    raw = raw_stages or {}
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
    except Exception as exc:
        logger.debug("pipeline WS broadcast skipped: %s", exc)


def _load_document(path: Path | None = None) -> dict[str, Any]:
    """Load full pipeline_state.json document (stages + metadata)."""
    state_path = _state_path(path)
    if not state_path.exists():
        return {"stages": _default_state()}
    with state_path.open("r", encoding="utf-8-sig") as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict):
        return {"stages": _default_state()}

    if "stages" in raw and isinstance(raw["stages"], dict):
        stages_raw = raw["stages"]
        meta = {k: raw[k] for k in _META_KEYS if k in raw}
    else:
        # Legacy flat file: stage names at top level
        stages_raw = {k: v for k, v in raw.items() if k in STAGES_IN_ORDER}
        meta = {k: raw[k] for k in _META_KEYS if k in raw}

    doc = {"stages": _ensure_all_stages(stages_raw), **meta}
    return doc


def _save_document(doc: dict[str, Any], path: Path | None = None) -> None:
    state_path = _state_path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    stages = _ensure_all_stages(doc.get("stages") if isinstance(doc.get("stages"), dict) else doc)
    payload: dict[str, Any] = {"stages": stages}
    for key in _META_KEYS:
        if key in doc and doc[key] is not None:
            payload[key] = doc[key]
    with state_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")


def load_state(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return stage map only (backward-compatible for callers)."""
    doc = _load_document(path)
    # Migrate legacy flat files to wrapped schema on read
    state_path = _state_path(path)
    if state_path.exists():
        with state_path.open("r", encoding="utf-8-sig") as fh:
            raw = json.load(fh)
        if isinstance(raw, dict) and "stages" not in raw:
            _save_document(doc, path)
    return doc["stages"]


def save_state(state: dict[str, dict[str, Any]], path: Path | None = None) -> None:
    """Persist stages while preserving top-level metadata keys."""
    doc = _load_document(path)
    doc["stages"] = _ensure_all_stages(state)
    _save_document(doc, path)


def get_meta(key: str, path: Path | None = None) -> Any:
    doc = _load_document(path)
    return doc.get(key)


def set_meta(key: str, value: Any, path: Path | None = None) -> None:
    doc = _load_document(path)
    doc[key] = value
    _save_document(doc, path)


def capture_run_metadata(path: Path | None = None) -> str | None:
    """Capture a ReproducibilitySnapshot and record its path in pipeline state.

    Safe to call when the research module is unavailable — logs and returns None.
    """
    try:
        from research.reproducibility import ReproducibilitySnapshot

        snapshot = ReproducibilitySnapshot.capture()
        snap_path = ReproducibilitySnapshot.save_snapshot(snapshot)
        set_meta("last_reproducibility_snapshot", snap_path, path=path)
        logger.info("reproducibility snapshot saved → %s", snap_path)
        return snap_path
    except Exception as exc:  # noqa: BLE001 — never break the pipeline
        logger.warning("capture_run_metadata failed (non-fatal): %s", exc)
        return None


def sync_snapshot_runtime(path: Path | None = None) -> None:
    """Write per-stage duration_seconds from pipeline state into the latest snapshot."""
    snap_path = get_meta("last_reproducibility_snapshot", path=path)
    if not snap_path:
        return
    snap_file = Path(str(snap_path))
    if not snap_file.is_absolute():
        from backend.utils.config import PROJECT_ROOT

        snap_file = PROJECT_ROOT / snap_file
    if not snap_file.exists():
        # Fall back to latest_snapshot.json
        from backend.utils.config import PROJECT_ROOT

        snap_file = PROJECT_ROOT / "research" / "reproducibility" / "latest_snapshot.json"
    if not snap_file.exists():
        return

    try:
        data = json.loads(snap_file.read_text(encoding="utf-8-sig"))
        stages = load_state(path)
        per_stage: dict[str, float] = {}
        total = 0.0
        for name, entry in stages.items():
            dur = entry.get("duration_seconds")
            if dur is not None:
                per_stage[name] = float(dur)
                total += float(dur)
        data["runtime"] = {
            "pipeline_total_seconds": round(total, 3) if per_stage else None,
            "per_stage_seconds": per_stage or None,
        }
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        snap_file.write_text(text, encoding="utf-8")
        # Keep latest in sync
        from backend.utils.config import PROJECT_ROOT

        latest = PROJECT_ROOT / "research" / "reproducibility" / "latest_snapshot.json"
        latest.parent.mkdir(parents=True, exist_ok=True)
        latest.write_text(text, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("sync_snapshot_runtime failed (non-fatal): %s", exc)


def _compute_duration_seconds(started_at: str | None) -> float | None:
    if not started_at:
        return None
    try:
        start = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        end = datetime.now(timezone.utc)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        return round(max(0.0, (end - start).total_seconds()), 3)
    except Exception:
        return None


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

    now = _utc_now()
    if status == STATUS_RUNNING:
        entry["started_at"] = now
        entry["run_at"] = now
        entry["duration_seconds"] = None
    elif status in {STATUS_COMPLETE, STATUS_FAILED}:
        entry["run_at"] = now
        entry["duration_seconds"] = _compute_duration_seconds(entry.get("started_at"))
    elif status == STATUS_PENDING:
        entry["run_at"] = None
        entry["started_at"] = None
        entry["error"] = None
        entry["duration_seconds"] = None

    state[stage] = entry
    save_state(state, path)
    logger.info(
        "pipeline_state: %s → %s (duration=%s)",
        stage,
        status,
        entry.get("duration_seconds"),
    )
    _broadcast(stage, status, progress_pct=entry.get("progress_pct"))

    if status in {STATUS_COMPLETE, STATUS_FAILED}:
        sync_snapshot_runtime(path)


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
    doc = _load_document(path)
    doc["stages"] = _default_state()
    # Keep last_reproducibility_snapshot pointer if present
    _save_document(doc, path)
    logger.info("pipeline_state: reset_all → all PENDING")
    for name in STAGES_IN_ORDER:
        _broadcast(name, STATUS_PENDING, progress_pct=None)


def mark_running(stage: str, path: Path | None = None) -> None:
    set_stage_status(stage, STATUS_RUNNING, progress_pct=0.0, path=path)


def mark_complete(stage: str, path: Path | None = None) -> None:
    set_stage_status(stage, STATUS_COMPLETE, progress_pct=100.0, path=path)


def mark_failed(stage: str, error: str | None = None, path: Path | None = None) -> None:
    set_stage_status(stage, STATUS_FAILED, error=error, path=path)


def get_latest_reproducibility_snapshot() -> dict[str, Any] | None:
    """Load the JSON snapshot referenced by pipeline state (or latest file)."""
    from backend.utils.config import PROJECT_ROOT

    snap_path = get_meta("last_reproducibility_snapshot")
    candidates: list[Path] = []
    if snap_path:
        p = Path(str(snap_path))
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        candidates.append(p)
    candidates.append(
        PROJECT_ROOT / "research" / "reproducibility" / "latest_snapshot.json"
    )
    for path in candidates:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                continue
    return None

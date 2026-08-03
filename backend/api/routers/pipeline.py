"""
Pipeline Monitor API router.

Powers Pipeline Monitor: status, single-stage run, reset, run-all.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time

from fastapi import APIRouter, BackgroundTasks, HTTPException

from api.schemas import PipelineStatus, StageStatusItem
from backend.utils.config import PROJECT_ROOT
from backend.utils import pipeline_state
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.api.pipeline")

router = APIRouter(tags=["pipeline"])

STAGE_MODULES: dict[str, str] = {
    "Discover": "backend.pipeline.stage_01_discover",
    "Load": "backend.pipeline.stage_02_load",
    "Integrate": "backend.pipeline.stage_03_integrate",
    "EDA": "backend.pipeline.stage_04_eda",
    "Clean": "backend.pipeline.stage_05_clean",
    "Split": "backend.pipeline.stage_06_split",
    "Preprocess": "backend.pipeline.stage_07_preprocess",
    "Balance": "backend.pipeline.stage_08_balance",
    "Train": "backend.pipeline.stage_09_train",
    "Evaluate": "backend.pipeline.stage_10_evaluate",
    "Explain Global": "backend.pipeline.stage_11_explain_global",
    "Explain Local": "backend.pipeline.stage_12_explain_local",
    "Explain Quality": "backend.pipeline.stage_13_explain_quality",
    "Predict": "backend.pipeline.stage_14_predict",
}

# Predict needs a default query when launched via pipeline run
PREDICT_DEFAULT_ARGS = [
    "--query",
    "EFL reading comprehension practice",
    "--top_k",
    "10",
]

POLL_INTERVAL_SEC = 1.0
STAGE_TIMEOUT_SEC = 20 * 60

_run_all_lock = threading.Lock()
_run_all_active = False


def _normalize_stage_name(stage_name: str) -> str:
    """Accept URL path segments with spaces or hyphens."""
    raw = stage_name.replace("-", " ").replace("_", " ").strip()
    # Exact match first
    if raw in STAGE_MODULES:
        return raw
    # Case-insensitive match
    lower_map = {k.lower(): k for k in STAGE_MODULES}
    if raw.lower() in lower_map:
        return lower_map[raw.lower()]
    raise HTTPException(
        status_code=404,
        detail=(
            f"Unknown stage {stage_name!r}. "
            f"Valid stages: {list(pipeline_state.STAGES_IN_ORDER)}"
        ),
    )


def _spawn_stage(stage: str) -> subprocess.Popen:
    module = STAGE_MODULES[stage]
    cmd = [sys.executable, "-m", module]
    if stage == "Predict":
        cmd.extend(PREDICT_DEFAULT_ARGS)
    logger.info("starting stage subprocess: %s", " ".join(cmd))
    # Mark RUNNING immediately so UI updates before the child process does
    pipeline_state.set_stage_status(stage, pipeline_state.STATUS_RUNNING, progress_pct=0.0)
    return subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _wait_for_terminal(stage: str, timeout: float = STAGE_TIMEOUT_SEC) -> str:
    """Poll until COMPLETE or FAILED (or timeout → FAILED)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = pipeline_state.get_all_statuses()[stage]["status"]
        if status in {
            pipeline_state.STATUS_COMPLETE,
            pipeline_state.STATUS_FAILED,
        }:
            return status
        time.sleep(POLL_INTERVAL_SEC)
    pipeline_state.set_stage_status(
        stage,
        pipeline_state.STATUS_FAILED,
        error=f"Timed out after {int(timeout)}s waiting for stage to finish",
    )
    return pipeline_state.STATUS_FAILED


def _run_all_worker() -> None:
    global _run_all_active
    try:
        for stage in pipeline_state.STAGES_IN_ORDER:
            statuses = pipeline_state.get_all_statuses()
            if statuses[stage]["status"] == pipeline_state.STATUS_COMPLETE:
                logger.info("run-all: skipping already COMPLETE stage %s", stage)
                continue
            logger.info("run-all: starting %s", stage)
            _spawn_stage(stage)
            final = _wait_for_terminal(stage)
            if final != pipeline_state.STATUS_COMPLETE:
                logger.error("run-all: stopping — %s ended as %s", stage, final)
                return
            logger.info("run-all: %s COMPLETE", stage)
        logger.info("run-all: all stages finished")
    finally:
        with _run_all_lock:
            _run_all_active = False


@router.get("/status", response_model=PipelineStatus)
def get_status() -> PipelineStatus:
    statuses = pipeline_state.get_all_statuses()
    stages = [
        StageStatusItem(
            name=name,
            status=statuses[name]["status"],
            run_at=statuses[name].get("run_at"),
            progress_pct=statuses[name].get("progress_pct"),
        )
        for name in pipeline_state.STAGES_IN_ORDER
    ]
    return PipelineStatus(
        stages=stages,
        current_stage=pipeline_state.get_current_stage() or "",
        pipeline_ready=pipeline_state.is_pipeline_ready(),
    )


@router.post("/run/{stage_name}")
def run_stage(stage_name: str) -> dict:
    stage = _normalize_stage_name(stage_name)
    statuses = pipeline_state.get_all_statuses()
    if statuses[stage]["status"] == pipeline_state.STATUS_COMPLETE:
        raise HTTPException(
            status_code=409,
            detail="Stage already complete. Use /reset to re-run.",
        )
    if statuses[stage]["status"] == pipeline_state.STATUS_RUNNING:
        raise HTTPException(
            status_code=409,
            detail=f"Stage '{stage}' is already RUNNING.",
        )
    _spawn_stage(stage)
    return {"message": f"Stage '{stage}' started", "stage": stage}


@router.post("/reset/{stage_name}")
def reset_stage(stage_name: str) -> dict:
    stage = _normalize_stage_name(stage_name)
    pipeline_state.reset_stage(stage)
    return {"message": f"Stage '{stage}' reset to PENDING", "stage": stage}


@router.post("/reset-all")
def reset_all() -> dict:
    pipeline_state.reset_all()
    return {"message": "All stages reset to PENDING"}


@router.post("/run-all")
def run_all(background_tasks: BackgroundTasks) -> dict:
    global _run_all_active
    with _run_all_lock:
        if _run_all_active:
            raise HTTPException(
                status_code=409,
                detail="A full pipeline run is already in progress.",
            )
        _run_all_active = True
    background_tasks.add_task(_run_all_worker)
    return {
        "message": "Full pipeline run started",
        "stages": list(pipeline_state.STAGES_IN_ORDER),
    }

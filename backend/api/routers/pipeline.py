"""
Pipeline Monitor API router.

Powers Pipeline Monitor: status, single-stage run, reset, run-all.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from api.schemas import PipelineStatus, StageStatusItem
from backend.auth.admin_auth import get_current_admin
from backend.services import dashboard_service
from backend.utils.config import DATA_PROCESSED, PROJECT_ROOT
from backend.utils import pipeline_state
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.api.pipeline")

router = APIRouter(tags=["pipeline"])

dashboard_router = APIRouter(tags=["dashboard"])

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

ARTIFACT_FILES: dict[str, Path] = {
    "discover": DATA_PROCESSED / "01_discover_manifest.json",
    "load": DATA_PROCESSED / "02_load_report.json",
    "integrate": DATA_PROCESSED / "03_integration_report.json",
    "eda": DATA_PROCESSED / "04_eda_report.json",
    "clean": DATA_PROCESSED / "05_clean_report.json",
    "split": DATA_PROCESSED / "06_split_report.json",
    "preprocess": DATA_PROCESSED / "07_preprocess_report.json",
    "balance": DATA_PROCESSED / "08_balance_report.json",
    "train": DATA_PROCESSED / "09_train_report.json",
}

EDA_PLOT_URLS = {
    "cefr_bar": "/static/eda_plots/cefr_bar.png",
    "skill_pie": "/static/eda_plots/skill_pie.png",
    "topic_bar": "/static/eda_plots/topic_bar.png",
    "text_length_hist": "/static/eda_plots/text_length_hist.png",
}

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

    if raw in STAGE_MODULES:
        return raw

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
            error=statuses[name].get("error"),
        )
        for name in pipeline_state.STAGES_IN_ORDER
    ]
    return PipelineStatus(
        stages=stages,
        current_stage=pipeline_state.get_current_stage() or "",
        pipeline_ready=pipeline_state.is_pipeline_ready(),
    )

def _read_artifact_json(slug: str) -> dict[str, Any]:
    path = ARTIFACT_FILES.get(slug)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Unknown artifact '{slug}'")
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Artifact {path.name} not found. "
                f"Run the corresponding pipeline stage first."
            ),
        )
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read {path.name}: {exc}",
        ) from exc
    if not isinstance(data, dict):
        return {"data": data}
    return data

@router.get("/artifact/{slug}")
def get_pipeline_artifact(slug: str) -> dict[str, Any]:
    """
    Prompt 4-N — thin JSON readers for Pipeline Monitor stage pages.

    Supported slugs: discover, load, integrate, eda, clean, split,
    preprocess, balance, train.

    Evaluate → use GET /api/metrics; Explain* → GET /api/explain/*.
    """
    raw = (slug or "").strip().lower().replace("_", "-")
    if raw not in ARTIFACT_FILES:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown artifact '{slug}'. "
                f"Valid: {sorted(ARTIFACT_FILES.keys())}"
            ),
        )
    payload = _read_artifact_json(raw)
    if raw == "eda":
        payload = {
            **payload,
            "plot_urls": EDA_PLOT_URLS,
        }
    return payload

@router.post("/run/{stage_name}")
def run_stage(
    stage_name: str,
    _admin: str = Depends(get_current_admin),
) -> dict:
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
def reset_stage(
    stage_name: str,
    _admin: str = Depends(get_current_admin),
) -> dict:
    stage = _normalize_stage_name(stage_name)
    pipeline_state.reset_stage(stage)
    return {"message": f"Stage '{stage}' reset to PENDING", "stage": stage}

@router.post("/reset-all")
def reset_all(_admin: str = Depends(get_current_admin)) -> dict:
    pipeline_state.reset_all()
    return {"message": "All stages reset to PENDING"}

@router.post("/run-all")
def run_all(
    background_tasks: BackgroundTasks,
    _admin: str = Depends(get_current_admin),
) -> dict:
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

@dashboard_router.get("/summary")
def dashboard_summary() -> dict:
    """
    Single Dashboard payload (poll every ~5s + websocket refresh).

    Aggregates pipeline state, metadata counts, EDA/train/eval JSON, analytics.
    """
    return dashboard_service.build_dashboard_summary()

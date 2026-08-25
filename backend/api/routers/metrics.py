"""
Metrics / evaluation API router (+ experiment tracking endpoints).
"""

from __future__ import annotations

import io
import json
import threading
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.schemas import MetricsResponse
from backend.auth.admin_auth import get_current_admin
from backend.utils.config import DATA_PROCESSED, PROJECT_ROOT
from backend.utils.logger import get_logger
from research.experiment_tracker import ExperimentTracker
from research.metrics_export import ResearchMetricsExporter

logger = get_logger("efl_indexdb.api.metrics")

router = APIRouter(tags=["metrics"])
experiments_router = APIRouter(tags=["experiments"])

EVAL_REPORT_PATH = DATA_PROCESSED / "10_evaluation_report.json"
METRICS_EXPORT_DIR = PROJECT_ROOT / "research" / "reports" / "metrics"
EXPERIMENT_EXPORT_DIR = PROJECT_ROOT / "research" / "reports" / "experiments"

_VALID_METHODS = {"tfidf", "sbert", "sbert_metadata", "sbert_metadata_rag"}
_experiment_run_lock = threading.Lock()
_experiment_run_active = False


@router.get("", response_model=MetricsResponse)
@router.get("/", response_model=MetricsResponse)
def get_metrics() -> MetricsResponse:
    if not EVAL_REPORT_PATH.exists():
        raise HTTPException(status_code=404, detail="Run stage Evaluate first.")

    with EVAL_REPORT_PATH.open("r", encoding="utf-8-sig") as fh:
        report = json.load(fh)

    retrieval = report.get("retrieval") or {}
    classification = report.get("classification") or {}
    return MetricsResponse(
        retrieval=retrieval,
        classification=classification,
        evaluation_run_at=report.get("run_at"),
        confusion_matrix_sbert=report.get("confusion_matrix_sbert"),
        confusion_matrix_tfidf=report.get("confusion_matrix_tfidf"),
        confusion_matrix_labels=report.get("confusion_matrix_labels"),
    )


def _rel_export_path(path: Path | str) -> str:
    """Return posix path relative to project root when possible."""
    p = Path(path)
    try:
        return p.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def _download_url(filename: str) -> str:
    return f"/static/research-reports/metrics/{filename}"


@router.post("/export")
def export_publication_metrics(
    _admin: str = Depends(get_current_admin),
) -> dict:
    """Admin-only: run ResearchMetricsExporter.export_all()."""
    try:
        exporter = ResearchMetricsExporter()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        files = exporter.export_all(METRICS_EXPORT_DIR)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Metrics export failed: {exc}",
        ) from exc

    rel_files = [_rel_export_path(f) for f in files]
    return {
        "files_generated": len(rel_files),
        "output_dir": "research/reports/metrics",
        "files": rel_files,
    }


@router.get("/export/files")
def list_export_files(
    _admin: str = Depends(get_current_admin),
) -> dict:
    """List publication tables already written under research/reports/metrics/."""
    if not METRICS_EXPORT_DIR.exists():
        return {"output_dir": "research/reports/metrics", "files": []}

    items: list[dict] = []
    for path in sorted(METRICS_EXPORT_DIR.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        stat = path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        items.append(
            {
                "filename": path.name,
                "size": stat.st_size,
                "last_modified": mtime,
                "download_url": _download_url(path.name),
                "path": _rel_export_path(path),
            }
        )
    return {"output_dir": "research/reports/metrics", "files": items}


# ── Experiment tracking (mounted at /api/experiments) ───────────────────


class ExperimentRunBody(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    method: Literal["tfidf", "sbert", "sbert_metadata", "sbert_metadata_rag"]


class ExperimentCompareBody(BaseModel):
    experiment_ids: list[str] = Field(..., min_length=1)


def _experiment_summary(exp) -> dict[str, Any]:
    ret = exp.results.retrieval if exp.results else None
    clf = exp.results.classification if exp.results else None
    return {
        "experiment_id": exp.experiment_id,
        "name": exp.name,
        "description": exp.description,
        "method": exp.config.retrieval_method,
        "status": exp.status,
        "started_at": exp.started_at,
        "completed_at": exp.completed_at,
        "precision_at_10": ret.precision_at_k if ret else None,
        "map": ret.map if ret else None,
        "f1_at_10": ret.f1_at_k if ret else None,
        "mrr": ret.mrr if ret else None,
        "accuracy": clf.accuracy if clf else None,
    }


def _run_experiment_job(name: str, description: str, method: str) -> None:
    global _experiment_run_active
    try:
        from research.run_experiment import run_named_experiment

        logger.info("Background experiment start name=%s method=%s", name, method)
        run_named_experiment(name=name, method=method, description=description)
        logger.info("Background experiment finished name=%s", name)
    except Exception:
        logger.exception("Background experiment failed name=%s method=%s", name, method)
    finally:
        with _experiment_run_lock:
            _experiment_run_active = False


@experiments_router.get("")
@experiments_router.get("/")
def list_experiments() -> list[dict[str, Any]]:
    """Return all tracked experiments (summary rows for the dashboard)."""
    et = ExperimentTracker()
    return [_experiment_summary(exp) for exp in et.list_experiments()]


@experiments_router.post("/run")
def run_experiment(
    body: ExperimentRunBody,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Queue research.run_experiment as a background task."""
    global _experiment_run_active
    if body.method not in _VALID_METHODS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid method. Expected one of: {sorted(_VALID_METHODS)}",
        )
    with _experiment_run_lock:
        if _experiment_run_active:
            raise HTTPException(
                status_code=409,
                detail="An experiment is already running. Wait for it to finish.",
            )
        _experiment_run_active = True

    background_tasks.add_task(
        _run_experiment_job,
        body.name.strip(),
        body.description or "",
        body.method,
    )
    return {
        "status": "started",
        "name": body.name.strip(),
        "method": body.method,
        "detail": "Experiment queued in the background. Refresh the list shortly.",
    }


@experiments_router.post("/export-comparison")
def export_experiment_comparison(body: ExperimentCompareBody) -> StreamingResponse:
    """Export selected experiments as CSV / LaTeX / PNG and download as a ZIP."""
    et = ExperimentTracker()
    ids = [i.strip() for i in body.experiment_ids if i and str(i).strip()]
    if len(ids) < 1:
        raise HTTPException(status_code=422, detail="Select at least one experiment.")

    for eid in ids:
        try:
            et.get_experiment(eid)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    EXPERIMENT_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        files = et.export_comparison_table(ids, EXPERIMENT_EXPORT_DIR)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Comparison export failed: {exc}",
        ) from exc

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            path = Path(file_path)
            if not path.is_file():
                continue
            zf.write(path, arcname=path.name)
    if buf.tell() == 0:
        raise HTTPException(status_code=500, detail="Export produced no downloadable files.")
    buf.seek(0)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"experiment_comparison_{stamp}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@experiments_router.get("/{experiment_id}")
def get_experiment(experiment_id: str) -> dict[str, Any]:
    et = ExperimentTracker()
    try:
        exp = et.get_experiment(experiment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return exp.model_dump()

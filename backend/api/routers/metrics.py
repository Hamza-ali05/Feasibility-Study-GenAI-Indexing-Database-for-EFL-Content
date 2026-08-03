"""
Metrics / evaluation API router.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from api.schemas import MetricsResponse
from backend.utils.config import DATA_PROCESSED

router = APIRouter(tags=["metrics"])

EVAL_REPORT_PATH = DATA_PROCESSED / "10_evaluation_report.json"


@router.get("", response_model=MetricsResponse)
@router.get("/", response_model=MetricsResponse)
def get_metrics() -> MetricsResponse:
    if not EVAL_REPORT_PATH.exists():
        raise HTTPException(status_code=404, detail="Run stage Evaluate first.")

    with EVAL_REPORT_PATH.open("r", encoding="utf-8") as fh:
        report = json.load(fh)

    retrieval = report.get("retrieval") or {}
    classification = report.get("classification") or {}
    return MetricsResponse(
        retrieval=retrieval,
        classification=classification,
        evaluation_run_at=report.get("run_at"),
    )

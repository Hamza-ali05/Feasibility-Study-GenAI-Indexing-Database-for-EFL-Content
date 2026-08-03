"""
Explainability API router (Global / Local / Quality).
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException

from api.schemas import ExplainGlobalResponse, ExplainLocalResponse, QualityResponse
from backend.utils.config import DATA_PROCESSED

router = APIRouter(tags=["explain"])

GLOBAL_REPORT = DATA_PROCESSED / "11_explain_global_report.json"
LOCAL_REPORT = DATA_PROCESSED / "12_explain_local_report.json"
QUALITY_REPORT = DATA_PROCESSED / "13_explain_quality_report.json"

GLOBAL_PLOT_URL = "/static/explain/global_shap_bar.png"

def _load_json(path) -> Any:
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Missing report {path.name}. Run the corresponding Explain stage first.",
        )
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)

@router.get("/global", response_model=ExplainGlobalResponse)
def explain_global() -> ExplainGlobalResponse:
    report = _load_json(GLOBAL_REPORT)
    top_features = report.get("top_20_shap_features") or report.get("top_features") or []
    plot_url = GLOBAL_PLOT_URL
    plots = report.get("plots") or {}
    if plots.get("global_shap_bar"):

        plot_url = GLOBAL_PLOT_URL
    return ExplainGlobalResponse(top_features=list(top_features), plot_url=plot_url)

@router.get("/local", response_model=ExplainLocalResponse)
def explain_local() -> ExplainLocalResponse:
    report = _load_json(LOCAL_REPORT)
    if isinstance(report, list):
        samples = report
    else:
        samples = report.get("explanations") or report.get("samples") or []
    return ExplainLocalResponse(samples=list(samples))

@router.get("/quality", response_model=QualityResponse)
def explain_quality() -> QualityResponse:
    report = _load_json(QUALITY_REPORT)
    return QualityResponse(
        faithfulness_score=float(report.get("faithfulness_score") or 0.0),
        stability_score=float(report.get("stability_score") or 0.0),
        bias_flags=list(report.get("bias_flags") or []),
        per_cefr_f1={str(k): float(v) for k, v in (report.get("per_cefr_f1") or {}).items()},
    )

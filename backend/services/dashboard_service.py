"""Dashboard summary aggregation — cheap JSON + SQL reads for the live Dashboard."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.db.analytics_store import AnalyticsStore
from backend.db.metadata_store import MetadataStore
from backend.utils.config import DATA_PROCESSED
from backend.utils import pipeline_state
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.dashboard")

EDA_REPORT = DATA_PROCESSED / "04_eda_report.json"
TRAIN_REPORT = DATA_PROCESSED / "09_train_report.json"
EVAL_REPORT = DATA_PROCESSED / "10_evaluation_report.json"
DUP_CANDIDATES = DATA_PROCESSED / "duplicate_candidates.json"
LAST_PREDICT = DATA_PROCESSED / "14_last_predict.json"

def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.warning("dashboard failed to read %s: %s", path, exc)
        return None

def _topline_evaluation(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    retrieval = report.get("retrieval") or {}
    classification = report.get("classification") or {}
    sbert_r = retrieval.get("sbert") or {}
    sbert_c = classification.get("sbert") or {}
    return {
        "run_at": report.get("run_at"),
        "sbert_precision_at_10": sbert_r.get("precision_at_10"),
        "sbert_recall_at_10": sbert_r.get("recall_at_10"),
        "sbert_map": sbert_r.get("map"),
        "sbert_f1_macro": sbert_c.get("f1_macro"),
        "sbert_accuracy": sbert_c.get("accuracy"),
        "queries_evaluated": retrieval.get("queries_evaluated"),
        "n_labeled_test": classification.get("n_labeled_test"),
    }

def _pipeline_activity(limit: int = 10) -> list[dict[str, Any]]:
    """Derive recent pipeline stage events from pipeline_state run_at stamps."""
    state = pipeline_state.get_all_statuses()
    events: list[dict[str, Any]] = []
    for name in pipeline_state.STAGES_IN_ORDER:
        entry = state.get(name) or {}
        run_at = entry.get("run_at")
        status = entry.get("status")
        if not run_at:
            continue
        events.append(
            {
                "type": "pipeline",
                "stage": name,
                "status": status,
                "timestamp": run_at,
            }
        )

    events.sort(key=lambda e: str(e.get("timestamp") or ""), reverse=True)
    return events[:limit]

def _upload_activity() -> list[dict[str, Any]]:
    """Surface last Predict artefact as a recent activity signal when present."""
    predict = _read_json(LAST_PREDICT)
    if not predict:
        return []
    return [
        {
            "type": "predict",
            "timestamp": predict.get("run_at") or predict.get("timestamp"),
            "query": predict.get("query"),
            "result_count": len(predict.get("results") or []),
        }
    ]

def build_dashboard_summary() -> dict[str, Any]:
    """One-pass summary for GET /api/dashboard/summary (polled every ~5s)."""
    statuses = pipeline_state.get_all_statuses()
    stages_complete = sum(
        1
        for name in pipeline_state.STAGES_IN_ORDER
        if (statuses.get(name) or {}).get("status") == pipeline_state.STATUS_COMPLETE
    )

    eda = _read_json(EDA_REPORT)
    train = _read_json(TRAIN_REPORT)
    evaluation = _read_json(EVAL_REPORT)
    dups = _read_json(DUP_CANDIDATES)

    total_resources = 0
    try:
        total_resources = MetadataStore().count()
    except Exception as exc:
        logger.warning("metadata count failed: %s", exc)

    faiss_ntotal = None
    if train and train.get("faiss_ntotal") is not None:
        try:
            faiss_ntotal = int(train["faiss_ntotal"])
        except (TypeError, ValueError):
            faiss_ntotal = None

    try:
        from backend.db.vector_store import get_vector_store

        idx = get_vector_store().index
        faiss_ntotal = int(idx.ntotal) if idx is not None else 0
    except Exception:
        pass

    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    analytics = AnalyticsStore()
    last_search_count_24h = analytics.count_searches_since(since)

    dup_pending = 0
    try:
        from backend.services import duplicate_service

        dup_pending = duplicate_service.count_unresolved()
    except Exception as exc:
        logger.warning("unresolved duplicate count failed: %s", exc)
        if dups:
            candidates = dups.get("candidates")
            if isinstance(candidates, list):
                dup_pending = len(candidates)

    activity = (
        analytics.recent_searches(limit=10)
        + _pipeline_activity(limit=14)
        + _upload_activity()
    )
    activity = [a for a in activity if a.get("timestamp")]
    activity.sort(key=lambda e: str(e.get("timestamp") or ""), reverse=True)
    recent_activity = activity[:10]

    cefr_distribution = {}
    if eda and isinstance(eda.get("cefr_distribution"), dict):
        cefr_distribution = eda["cefr_distribution"]

    return {
        "pipeline_ready": bool(pipeline_state.is_pipeline_ready()),
        "current_stage": pipeline_state.get_current_stage(),
        "stages_complete": stages_complete,
        "total_resources": total_resources,
        "cefr_distribution": cefr_distribution,
        "faiss_ntotal": faiss_ntotal,
        "last_search_count_24h": last_search_count_24h,
        "last_evaluation": _topline_evaluation(evaluation),
        "duplicate_candidates_pending": dup_pending,
        "recent_activity": recent_activity,
    }

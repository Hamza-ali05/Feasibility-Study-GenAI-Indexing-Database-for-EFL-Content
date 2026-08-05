"""Dissertation figures API — generate and list Phase 13 diagrams (admin-only)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.auth.admin_auth import get_current_admin
from backend.utils.config import PROJECT_ROOT
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.api.figures")

router = APIRouter(tags=["figures"])

FIGURES_DIR = PROJECT_ROOT / "research" / "reports" / "figures"

_EXPECTED_STEMS = [
    "system_architecture",
    "data_flow_diagram",
    "pipeline_flowchart",
    "embedding_pipeline",
    "search_sequence",
    "rag_sequence",
    "component_diagram",
    "cefr_classification_flow",
]


def _file_meta(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "filename": path.name,
        "stem": path.stem,
        "format": path.suffix.lstrip(".").lower(),
        "size": int(stat.st_size),
        "last_modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "download_url": f"/static/research-reports/figures/{path.name}",
    }


@router.get("/list")
def list_figures(_admin: str = Depends(get_current_admin)) -> dict[str, Any]:
    """List generated dissertation figures (PNG + SVG)."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(
        [_file_meta(p) for p in FIGURES_DIR.iterdir() if p.suffix.lower() in {".png", ".svg"}],
        key=lambda x: x["filename"],
    )
    return {
        "output_dir": str(FIGURES_DIR),
        "expected": _EXPECTED_STEMS,
        "files": files,
        "count": len(files),
    }


@router.post("/export")
def export_figures(_admin: str = Depends(get_current_admin)) -> dict[str, Any]:
    """Admin-only: regenerate all dissertation figures (PNG 300 DPI + SVG)."""
    try:
        from research.dissertation_figures import DissertationFigureGenerator
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"DissertationFigureGenerator unavailable: {exc}",
        ) from exc

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    try:
        gen = DissertationFigureGenerator()
        files = gen.export_all(FIGURES_DIR)
    except Exception as exc:
        logger.exception("Figure export failed")
        raise HTTPException(status_code=500, detail=f"Figure export failed: {exc}") from exc

    return {
        "status": "ok",
        "output_dir": str(FIGURES_DIR),
        "files": files,
        "count": len(files),
    }

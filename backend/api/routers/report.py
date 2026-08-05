"""Research report draft generation API (admin-only)."""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.auth.admin_auth import get_current_admin
from backend.utils.config import DATA_PROCESSED, PROJECT_ROOT
from backend.utils import pipeline_state
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.api.report")

router = APIRouter(tags=["report"])

DRAFT_DIR = PROJECT_ROOT / "research" / "reports" / "draft_chapters"
EXPERIMENT_LOG = PROJECT_ROOT / "research" / "experiments" / "experiment_log.json"
EVAL_REPORT = DATA_PROCESSED / "10_evaluation_report.json"
SECURITY_REPORT = PROJECT_ROOT / "research" / "reports" / "security" / "security_evaluation.md"
PARTICIPANTS = PROJECT_ROOT / "research" / "practitioner_eval" / "participants.json"

SectionKey = Literal[
    "results",
    "evaluation",
    "methodology",
    "model_statistics",
    "all",
]

_SECTION_FILES: dict[str, str] = {
    "results": "chapter_4_results.md",
    "evaluation": "chapter_5_evaluation.md",
    "methodology": "chapter_3_methodology.md",
    "model_statistics": "appendix_model_stats.md",
}

_SECTION_METHODS: dict[str, str] = {
    "results": "generate_results_chapter",
    "evaluation": "generate_evaluation_chapter",
    "methodology": "generate_methodology_section",
    "model_statistics": "generate_model_statistics_appendix",
}


class GenerateRequest(BaseModel):
    sections: list[SectionKey] = Field(
        default_factory=lambda: ["all"],
        description="Draft sections to generate",
    )


def _resolve_keys(sections: list[str]) -> list[str]:
    keys: list[str] = []
    for raw in sections:
        key = str(raw).strip().lower()
        if key == "all":
            return list(_SECTION_FILES.keys())
        if key not in _SECTION_FILES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unknown section {raw!r}. "
                    f"Valid: {list(_SECTION_FILES)} or 'all'"
                ),
            )
        if key not in keys:
            keys.append(key)
    if not keys:
        raise HTTPException(status_code=400, detail="No sections selected.")
    return keys


def _word_count(text: str) -> int:
    return len([w for w in text.split() if w.strip()])


def _safe_draft_path(filename: str) -> Path:
    name = Path(str(filename)).name
    if not name.endswith(".md") or ".." in name:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    path = (DRAFT_DIR / name).resolve()
    try:
        path.relative_to(DRAFT_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid filename.") from exc
    return path


def _section_meta(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    title = path.stem.replace("_", " ").title()
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    stat = path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    return {
        "filename": path.name,
        "title": title,
        "size": int(stat.st_size),
        "word_count": _word_count(text),
        "last_modified": mtime,
        "download_url": f"/static/research-reports/draft_chapters/{path.name}",
    }


def _practitioner_has_data() -> bool:
    if PARTICIPANTS.exists():
        try:
            import json

            data = json.loads(PARTICIPANTS.read_text(encoding="utf-8-sig"))
            if isinstance(data, list) and len(data) > 0:
                return True
            if isinstance(data, dict) and data.get("participants"):
                return True
        except Exception:
            pass
    try:
        from research.practitioner_eval.interview_manager import InterviewManager

        summary = InterviewManager().recruitment_summary()
        return int(summary.get("total_recruited") or 0) > 0
    except Exception:
        return False


def _experiments_tracked() -> bool:
    if not EXPERIMENT_LOG.exists():
        return False
    try:
        import json

        data = json.loads(EXPERIMENT_LOG.read_text(encoding="utf-8-sig"))
        experiments = data.get("experiments") if isinstance(data, dict) else data
        return bool(experiments)
    except Exception:
        return False


def _pipeline_complete() -> bool:
    try:
        return bool(pipeline_state.is_pipeline_ready())
    except Exception:
        statuses = pipeline_state.get_all_statuses()
        return all(
            (statuses.get(s) or {}).get("status") == pipeline_state.STATUS_COMPLETE
            for s in pipeline_state.STAGES_IN_ORDER
        )


def _readiness() -> list[dict[str, Any]]:
    return [
        {
            "id": "pipeline",
            "label": "Pipeline complete?",
            "ready": _pipeline_complete(),
            "link": "/pipeline/discover",
        },
        {
            "id": "evaluation",
            "label": "Evaluation run?",
            "ready": EVAL_REPORT.exists(),
            "link": "/pipeline/evaluate",
        },
        {
            "id": "experiments",
            "label": "Experiments tracked?",
            "ready": _experiments_tracked(),
            "link": "/experiments",
        },
        {
            "id": "practitioner",
            "label": "Practitioner data entered?",
            "ready": _practitioner_has_data(),
            "link": "/practitioner/manage",
        },
        {
            "id": "security",
            "label": "Security audit run?",
            "ready": SECURITY_REPORT.exists(),
            "link": "/about",
        },
    ]


@router.post("/generate")
def generate_report(
    body: GenerateRequest,
    _admin: str = Depends(get_current_admin),
) -> dict[str, Any]:
    """Admin-only: generate selected dissertation draft sections."""
    keys = _resolve_keys(list(body.sections or ["all"]))
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from research.research_report import ResearchReportGenerator
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"ResearchReportGenerator unavailable: {exc}",
        ) from exc

    generator = ResearchReportGenerator()
    files: list[str] = []
    generated: list[str] = []

    for key in keys:
        method_name = _SECTION_METHODS[key]
        filename = _SECTION_FILES[key]
        target = DRAFT_DIR / filename
        try:
            method = getattr(generator, method_name)
            path = method(target)
            files.append(str(path))
            generated.append(key)
        except Exception as exc:
            logger.exception("Failed generating section %s", key)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate {key}: {exc}",
            ) from exc

    return {
        "sections_generated": generated,
        "output_dir": str(DRAFT_DIR),
        "files": files,
    }


@router.get("/sections")
def list_sections(_admin: str = Depends(get_current_admin)) -> dict[str, Any]:
    """List generated draft sections plus data-readiness checklist."""
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    sections: list[dict[str, Any]] = []
    for path in sorted(DRAFT_DIR.glob("*.md")):
        try:
            sections.append(_section_meta(path))
        except Exception as exc:
            logger.warning("Skipping draft %s: %s", path.name, exc)
    return {"sections": sections, "readiness": _readiness()}


@router.get("/section/{filename}")
def get_section(
    filename: str,
    _admin: str = Depends(get_current_admin),
) -> dict[str, Any]:
    """Return markdown content of a draft section for preview."""
    path = _safe_draft_path(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Section '{filename}' not found.")
    meta = _section_meta(path)
    meta["content"] = path.read_text(encoding="utf-8-sig")
    return meta


@router.get("/download-all")
def download_all_zip(_admin: str = Depends(get_current_admin)) -> StreamingResponse:
    """Zip all generated draft `.md` files for download."""
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    paths = sorted(DRAFT_DIR.glob("*.md"))
    if not paths:
        raise HTTPException(
            status_code=404,
            detail="No draft sections found. Generate sections first.",
        )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in paths:
            zf.writestr(path.name, path.read_text(encoding="utf-8-sig"))
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="draft_chapters.zip"',
        },
    )

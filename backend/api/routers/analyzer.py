"""
AI Resource Analyzer router — live single-resource upload / paste ingestion.
"""

from __future__ import annotations

import io
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.services import analyzer_service
from backend.utils import pipeline_state
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.api.analyzer")

router = APIRouter(tags=["analyzer"])

ALLOWED_EXTENSIONS = {".txt", ".csv", ".pdf"}


class ConfirmDuplicateBody(BaseModel):
    text: str
    title: str | None = None
    force: bool = Field(default=True)


class AnalyzerResult(BaseModel):
    resource_id: str | None = None
    title: str
    cefr_level: str | None = None
    skill_type: str | None = None
    topic_domain: str | None = None
    duplicate_of: str | None = None
    duplicate_similarity: float | None = None
    duplicate_title: str | None = None
    indexed: bool
    classify_manually: bool = False
    note: str | None = None
    faiss_index: int | None = None


def _require_train_complete() -> None:
    state = pipeline_state.get_all_statuses()
    train = state.get("Train") or {}
    if train.get("status") != pipeline_state.STATUS_COMPLETE:
        raise HTTPException(
            status_code=503,
            detail=(
                "Stage Train is not COMPLETE. Run the pipeline at least once so a "
                "FAISS index exists before using the AI Resource Analyzer."
            ),
        )


def _extract_text_from_upload(filename: str, raw: bytes) -> str:
    lower = (filename or "").lower()
    if lower.endswith(".txt"):
        return raw.decode("utf-8", errors="replace")
    if lower.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(raw))
        if df.empty:
            raise ValueError("CSV file has no rows")
        row = df.iloc[0]
        for col in ("raw_text", "text", "content", "body", "essay", "full_text"):
            if col in df.columns and pd.notna(row[col]):
                return str(row[col])
        parts = [str(v) for v in row.tolist() if isinstance(v, str) and v.strip()]
        if not parts:
            parts = [str(v) for v in row.tolist() if pd.notna(v)]
        return " ".join(parts)
    if lower.endswith(".pdf"):
        import pdfplumber

        pages: list[str] = []
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        return "\n".join(pages)
    raise ValueError(
        f"Unsupported file type for '{filename}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}"
    )


def _run_analyze(
    text: str,
    *,
    title: str | None,
    filename: str | None,
    force: bool,
) -> dict[str, Any]:
    try:
        return analyzer_service.analyze_and_index(
            text=text,
            filename=filename,
            provided_title=title,
            force=force,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("analyzer failed")
        raise HTTPException(status_code=500, detail=f"Analyzer failed: {exc}") from exc


def _to_result(result: dict[str, Any]) -> AnalyzerResult:
    return AnalyzerResult(**{k: result.get(k) for k in AnalyzerResult.model_fields})


@router.post("/upload", response_model=AnalyzerResult)
async def upload(request: Request) -> AnalyzerResult:
    """
    Multipart file upload (.txt / .csv / .pdf) **or** JSON
    ``{\"text\": str, \"title\": str|null}``.
    """
    _require_train_complete()

    content_type = (request.headers.get("content-type") or "").lower()
    filename: str | None = None
    body_text: str | None = None
    body_title: str | None = None

    if "application/json" in content_type:
        payload = await request.json()
        body_text = str(payload.get("text") or "")
        body_title = payload.get("title")
    elif "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("file")
        body_title = form.get("title")  # type: ignore[assignment]
        if isinstance(body_title, bytes):
            body_title = body_title.decode("utf-8", errors="replace")
        form_text = form.get("text")
        if upload is not None and hasattr(upload, "filename") and upload.filename:
            filename = str(upload.filename)
            suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if suffix not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Unsupported extension '{suffix}'. "
                        f"Allowed: {sorted(ALLOWED_EXTENSIONS)}"
                    ),
                )
            raw = await upload.read()
            try:
                body_text = _extract_text_from_upload(filename, raw)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        elif form_text is not None:
            body_text = str(form_text)
        else:
            raise HTTPException(
                status_code=422,
                detail="multipart must include file or text field",
            )
    else:
        raise HTTPException(
            status_code=422,
            detail="Use multipart/form-data (file) or application/json {text, title}.",
        )

    if not body_text or not str(body_text).strip():
        raise HTTPException(status_code=422, detail="text is empty")

    result = _run_analyze(
        str(body_text),
        title=str(body_title) if body_title else None,
        filename=filename,
        force=False,
    )
    return _to_result(result)


@router.post("/confirm-duplicate", response_model=AnalyzerResult)
def confirm_duplicate(body: ConfirmDuplicateBody) -> AnalyzerResult:
    """Force-insert after the frontend duplicate-confirmation dialog."""
    _require_train_complete()
    if not body.force:
        raise HTTPException(
            status_code=422,
            detail="confirm-duplicate requires force=true",
        )
    if not body.text or not body.text.strip():
        raise HTTPException(status_code=422, detail="text is empty")

    result = _run_analyze(
        body.text,
        title=body.title,
        filename=None,
        force=True,
    )
    return _to_result(result)

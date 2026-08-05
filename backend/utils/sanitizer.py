"""Input sanitization helpers for the EFL IndexDB API (Prompt 16-B)."""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException

from backend.utils.logger import security_log

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_NULL_BYTE = "\x00"

# Heuristic signatures for security logging (defensive — not a WAF)
_SQL_HINTS = (
    "' or ",
    " or 1=1",
    "union select",
    "drop table",
    "sqlite_master",
    ";--",
    "'--",
)
_XSS_HINTS = (
    "<script",
    "javascript:",
    "onerror=",
    "onload=",
    "<img ",
    "<svg",
)

ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".csv", ".pdf"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

_EXT_CONTENT_TYPES: dict[str, set[str]] = {
    ".txt": {"text/plain", "application/octet-stream", ""},
    ".csv": {
        "text/csv",
        "application/csv",
        "text/plain",
        "application/vnd.ms-excel",
        "application/octet-stream",
        "",
    },
    ".pdf": {"application/pdf", "application/octet-stream", ""},
}


def _strip_nulls(text: str) -> str:
    return text.replace(_NULL_BYTE, "")


def _detect_and_log(kind: str, text: str) -> None:
    low = text.lower()
    if any(h in low for h in _SQL_HINTS):
        security_log(
            "suspicious_sql_payload",
            f"{kind}: possible SQL injection pattern in input",
        )
    if any(h in low for h in _XSS_HINTS):
        security_log(
            "suspicious_xss_payload",
            f"{kind}: possible XSS pattern in input",
        )


def sanitize_search_query(query: str) -> str:
    """Strip HTML tags, null bytes; cap length at 500 characters."""
    if query is None:
        return ""
    text = _strip_nulls(str(query))
    _detect_and_log("search_query", text)
    text = _HTML_TAG_RE.sub("", text)
    text = text.strip()
    if len(text) > 500:
        text = text[:500]
    return text


def sanitize_text_input(text: str) -> str:
    """Sanitize longer free-text (resource uploads / paste); cap at 10_000 chars."""
    if text is None:
        return ""
    cleaned = _strip_nulls(str(text))
    _detect_and_log("text_input", cleaned)
    cleaned = _HTML_TAG_RE.sub("", cleaned)
    if len(cleaned) > 10_000:
        cleaned = cleaned[:10_000]
    return cleaned


def validate_file_upload(file: Any) -> None:
    """Validate upload filename, size, and content-type vs extension.

    ``file`` may be a Starlette ``UploadFile``, or any object/dict with
    ``filename``, ``size`` / ``spool_max_size``, and ``content_type`` /
    ``headers``.
    Raises ``HTTPException(400)`` on failure.
    """
    if file is None:
        raise HTTPException(status_code=400, detail="No file provided.")

    if isinstance(file, dict):
        filename = str(file.get("filename") or "")
        size = file.get("size")
        content_type = str(file.get("content_type") or file.get("content-type") or "")
    else:
        filename = str(getattr(file, "filename", None) or "")
        size = getattr(file, "size", None)
        content_type = str(getattr(file, "content_type", None) or "")
        if not content_type and hasattr(file, "headers"):
            try:
                content_type = str(file.headers.get("content-type") or "")
            except Exception:
                content_type = ""

    if not filename or "." not in filename:
        security_log("rejected_upload", f"missing/invalid filename: {filename!r}")
        raise HTTPException(
            status_code=400,
            detail="Filename must include an extension (.txt, .csv, or .pdf).",
        )

    # Use basename only (path traversal defence)
    name = filename.replace("\\", "/").split("/")[-1]
    ext = "." + name.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        security_log("rejected_upload", f"disallowed extension {ext} ({name})")
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file extension '{ext}'. "
                f"Allowed: {sorted(ALLOWED_UPLOAD_EXTENSIONS)}"
            ),
        )

    if size is not None:
        try:
            size_i = int(size)
        except (TypeError, ValueError):
            size_i = None
        if size_i is not None and size_i > MAX_UPLOAD_BYTES:
            security_log(
                "rejected_upload",
                f"file too large: {size_i} bytes (limit {MAX_UPLOAD_BYTES})",
            )
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds maximum size of {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
            )

    ctype = (content_type or "").split(";")[0].strip().lower()
    allowed_types = _EXT_CONTENT_TYPES.get(ext, set())
    # Empty / missing content-type is tolerated; explicit mismatch is rejected
    if ctype and ctype not in allowed_types and "octet-stream" not in ctype:
        # Still allow common browser quirks for txt/csv
        if not (ext in {".txt", ".csv"} and ctype.startswith("text/")):
            security_log(
                "rejected_upload",
                f"content-type mismatch: {ctype!r} for {ext}",
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Content-Type '{ctype}' does not match extension '{ext}'. "
                    f"Expected one of: {sorted(t for t in allowed_types if t)}"
                ),
            )

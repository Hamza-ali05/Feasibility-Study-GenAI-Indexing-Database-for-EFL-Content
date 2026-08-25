"""Security evaluation API — run audits and fetch OWASP results (admin-only)."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.auth.admin_auth import get_current_admin
from backend.utils.config import PROJECT_ROOT
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.api.security")

router = APIRouter(tags=["security"])

REPORTS_DIR = PROJECT_ROOT / "research" / "security_eval" / "reports"
AUDIT_JSON = REPORTS_DIR / "security_audit_report.json"
AUDIT_MD = REPORTS_DIR / "security_audit_report.md"

_state_lock = threading.Lock()
_audit_state: dict[str, Any] = {
    "running": False,
    "current_category": None,
    "started_at": None,
    "finished_at": None,
    "error": None,
    "last_summary": None,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_state(**kwargs: Any) -> None:
    with _state_lock:
        _audit_state.update(kwargs)


def _get_state() -> dict[str, Any]:
    with _state_lock:
        return dict(_audit_state)


def _empty_report() -> dict[str, Any]:
    """Placeholder payload when no audit has been run yet."""
    return {
        "available": False,
        "audit_date": None,
        "target": None,
        "summary": {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0,
        },
        "authentication": [],
        "input_validation": [],
        "prompt_injection": [],
        "file_upload": [],
        "api_security": [],
        "owasp_mapping": [],
        "recommendations": [],
        "message": "No security audit report yet. Run a security audit to generate results.",
    }


def _load_audit_json() -> dict[str, Any]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    # Prefer canonical name; fall back to legacy raw file
    for path in (AUDIT_JSON, REPORTS_DIR / "security_audit_raw.json"):
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                if isinstance(data, dict):
                    data = dict(data)
                    data.setdefault("available", True)
                    return data
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Failed reading %s: %s", path, exc)
    return _empty_report()


def _run_audit_job() -> None:
    """Execute SecurityAuditor category-by-category with progress updates."""
    _set_state(
        running=True,
        current_category="initialising",
        started_at=_utc_now(),
        finished_at=None,
        error=None,
    )
    try:
        from research.security_eval.security_auditor import SecurityAuditor

        with SecurityAuditor() as auditor:
            auditor._try_login()

            _set_state(current_category="authentication")
            jwt_required = auditor.test_jwt_auth_required()
            jwt_expiry = {**auditor.test_jwt_expiry(), "test": "jwt_expiry"}
            jwt_secret = auditor.test_jwt_secret_strength()
            pw_hash = auditor.test_password_hashing()
            brute = {**auditor.test_brute_force_protection(), "test": "brute_force"}
            authentication = jwt_required + [jwt_expiry, jwt_secret, pw_hash, brute]

            _set_state(current_category="input_validation")
            input_validation = (
                auditor.test_sql_injection()
                + auditor.test_xss_prevention()
                + auditor.test_path_traversal()
            )

            _set_state(current_category="prompt_injection")
            prompt_injection = (
                auditor.test_prompt_injection_rag()
                + auditor.test_prompt_injection_analyzer()
            )

            _set_state(current_category="file_upload")
            file_upload = (
                auditor.test_file_upload_type_restriction()
                + [auditor.test_file_upload_size_limit()]
                + auditor.test_file_upload_content_type_validation()
            )

            _set_state(current_category="api_security")
            api_security = [
                auditor.test_cors_configuration(),
                auditor.test_rate_limiting(),
                auditor.test_api_key_exposure(),
            ] + auditor.test_error_information_leakage()

            draft = {
                "authentication": authentication,
                "input_validation": input_validation,
                "prompt_injection": prompt_injection,
                "file_upload": file_upload,
                "api_security": api_security,
            }

            _set_state(current_category="owasp_mapping")
            owasp = auditor.owasp_assessment(draft)

            def _collect(items: list[Any]) -> tuple[int, int, int]:
                passed = failed = warnings = 0
                for it in items:
                    if not isinstance(it, dict) or "passed" not in it:
                        continue
                    if it.get("passed") is True:
                        passed += 1
                    elif it.get("recommendation") and it.get("passed") is False:
                        failed += 1
                        warnings += 1
                    else:
                        failed += 1
                return passed, failed, warnings

            all_items = (
                authentication
                + input_validation
                + prompt_injection
                + file_upload
                + api_security
            )
            p, f, w = _collect(all_items)

            recommendations: list[str] = []
            for block in (brute, file_upload[1] if len(file_upload) > 1 else {}, api_security[1] if len(api_security) > 1 else {}):
                if isinstance(block, dict) and block.get("recommendation"):
                    recommendations.append(str(block["recommendation"]))
            for row in owasp:
                if row.get("status") in {"Fail", "Partial"}:
                    recommendations.extend(row.get("recommendations") or [])
            seen: set[str] = set()
            prioritised = []
            for rec in recommendations:
                if rec and rec not in seen:
                    seen.add(rec)
                    prioritised.append(rec)

            report = {
                "audit_date": _utc_now(),
                "target": auditor.base_url,
                "summary": {
                    "total_tests": p + f,
                    "passed": p,
                    "failed": f,
                    "warnings": w,
                },
                "authentication": authentication,
                "input_validation": input_validation,
                "prompt_injection": prompt_injection,
                "file_upload": file_upload,
                "api_security": api_security,
                "owasp_mapping": owasp,
                "recommendations": prioritised,
            }
            auditor._last_audit = report

            _set_state(current_category="generating_report")
            auditor.generate_security_report(REPORTS_DIR)
            _set_state(
                running=False,
                current_category=None,
                finished_at=_utc_now(),
                last_summary=report.get("summary"),
                error=None,
            )
            logger.info("Security audit finished: %s", report.get("summary"))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Security audit failed")
        _set_state(
            running=False,
            current_category=None,
            finished_at=_utc_now(),
            error=str(exc),
        )


@router.post("/run-audit")
def run_audit(
    background_tasks: BackgroundTasks,
    _admin: str = Depends(get_current_admin),
) -> dict[str, str]:
    """Admin-only: start a full security audit in the background."""
    state = _get_state()
    if state.get("running"):
        raise HTTPException(
            status_code=409,
            detail="A security audit is already running.",
        )
    background_tasks.add_task(_run_audit_job)
    return {
        "status": "started",
        "message": "Security audit running...",
    }


@router.get("/status")
def audit_status(_admin: str = Depends(get_current_admin)) -> dict[str, Any]:
    """Progress for the Security Evaluation UI."""
    return _get_state()


@router.get("/report")
def get_report(_admin: str = Depends(get_current_admin)) -> dict[str, Any]:
    """Latest audit JSON results."""
    return _load_audit_json()


@router.get("/owasp")
def get_owasp(_admin: str = Depends(get_current_admin)) -> dict[str, Any]:
    """OWASP Top 10 assessment rows only."""
    data = _load_audit_json()
    return {
        "audit_date": data.get("audit_date"),
        "owasp_mapping": data.get("owasp_mapping") or [],
    }


@router.get("/report.md")
def download_markdown(_admin: str = Depends(get_current_admin)) -> FileResponse:
    """Download the markdown security audit report."""
    if not AUDIT_MD.exists():
        raise HTTPException(
            status_code=404,
            detail="Markdown report not found. Run an audit first.",
        )
    return FileResponse(
        path=str(AUDIT_MD),
        media_type="text/markdown",
        filename="security_audit_report.md",
    )

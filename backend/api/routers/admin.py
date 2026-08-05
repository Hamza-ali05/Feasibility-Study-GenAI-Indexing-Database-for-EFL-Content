"""
Admin Panel router — auth + management (pipeline, resources, logs, overview).
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.routers import pipeline as pipeline_mod
from backend.auth.admin_auth import create_access_token, get_current_admin, verify_password
from backend.db.analytics_store import AnalyticsStore
from backend.services import dashboard_service, duplicate_service, resource_admin
from backend.utils.config import Config
from backend.utils.logger import get_logger, security_log, tail_log_lines

logger = get_logger("efl_indexdb.api.admin")

router = APIRouter(tags=["admin"])

class LoginBody(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class MeResponse(BaseModel):
    username: str

@router.post("/login", response_model=TokenResponse)
def login(body: LoginBody) -> TokenResponse:
    expected_user = Config.ADMIN_USERNAME
    if not expected_user or not Config.ADMIN_PASSWORD_HASH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Admin auth is not configured. Set ADMIN_USERNAME and "
                "ADMIN_PASSWORD_HASH in .env (see backend/.env.example)."
            ),
        )
    if body.username != expected_user or not verify_password(body.password):
        security_log(
            "failed_login",
            f"username={body.username!r}",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        token = create_access_token(body.username)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    logger.info("admin login ok user=%s", body.username)
    return TokenResponse(access_token=token, token_type="bearer")

@router.get("/me", response_model=MeResponse)
def me(username: str = Depends(get_current_admin)) -> MeResponse:
    """Frontend session check — returns username when Bearer JWT is valid."""
    return MeResponse(username=username)

@router.get("/overview")
def overview(_admin: str = Depends(get_current_admin)) -> dict:
    """Dashboard summary + analytics totals for the Admin Panel home."""
    summary = dashboard_service.build_dashboard_summary()
    total_searches = AnalyticsStore().total_searches()
    try:
        dup_pending = duplicate_service.count_unresolved()
    except Exception:
        dup_pending = summary.get("duplicate_candidates_pending", 0)
    return {
        **summary,
        "duplicate_candidates_pending": dup_pending,
        "total_searches": total_searches,
        "admin_user": _admin,
    }

@router.post("/pipeline/run/{stage_name}")
def admin_run_stage(
    stage_name: str,
    _admin: str = Depends(get_current_admin),
) -> dict:
    """Protected wrapper — same logic as ``POST /api/pipeline/run/{stage}``."""
    return pipeline_mod.run_stage(stage_name, _admin=_admin)

@router.post("/pipeline/run-all")
def admin_run_all(
    background_tasks: BackgroundTasks,
    _admin: str = Depends(get_current_admin),
) -> dict:
    return pipeline_mod.run_all(background_tasks, _admin=_admin)

@router.post("/pipeline/reset/{stage_name}")
def admin_reset_stage(
    stage_name: str,
    _admin: str = Depends(get_current_admin),
) -> dict:
    return pipeline_mod.reset_stage(stage_name, _admin=_admin)

@router.delete("/resources/{resource_id}")
def admin_delete_resource(
    resource_id: str,
    _admin: str = Depends(get_current_admin),
) -> dict:
    """Same deletion path as ``DELETE /api/resources/{id}``."""
    return resource_admin.delete_indexed_resource(resource_id)

@router.get("/logs")
def admin_logs(
    lines: int = Query(200, ge=1, le=5000),
    _admin: str = Depends(get_current_admin),
) -> dict:
    """Tail ``logs/efl_indexdb.log`` for the Admin Panel live log viewer."""
    return {"lines": tail_log_lines(lines), "path": "logs/efl_indexdb.log"}

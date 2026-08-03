"""
Single-admin authentication for the EFL IndexDB Admin Panel.

Research prototype — one username/password from Config, JWT bearer tokens.
Uses the ``bcrypt`` package directly (passlib is incompatible with bcrypt≥4.1).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from backend.utils.config import Config

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/login", auto_error=True)

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 12

def _password_bytes(plain: str) -> bytes:
    return plain.encode("utf-8")[:72]

def verify_password(plain: str) -> bool:
    """Check plaintext password against ``Config.ADMIN_PASSWORD_HASH``."""
    hashed = Config.ADMIN_PASSWORD_HASH
    if not hashed or not str(hashed).strip():
        return False
    try:
        return bcrypt.checkpw(
            _password_bytes(plain),
            str(hashed).strip().encode("utf-8"),
        )
    except Exception:
        return False

def hash_password(plain: str) -> str:
    """Hash helper (same algorithm as generate_password_hash.py)."""
    return bcrypt.hashpw(_password_bytes(plain), bcrypt.gensalt()).decode("utf-8")

def create_access_token(username: str) -> str:
    """Issue an HS256 JWT (12-hour expiry) signed with ``Config.JWT_SECRET``."""
    secret = str(Config.require("JWT_SECRET"))
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": username,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "role": "admin",
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)

def get_current_admin(token: str = Depends(oauth2_scheme)) -> str:
    """FastAPI dependency — returns admin username or raises 401."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate admin credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        secret = str(Config.require("JWT_SECRET"))
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    try:

        data = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            options={"verify_exp": True, "require_exp": True},
        )
        username = data.get("sub")
        if not username or not isinstance(username, str):
            raise credentials_exception
        expected = Config.ADMIN_USERNAME
        if not expected or username != expected:
            raise credentials_exception
        return username
    except JWTError as exc:
        raise credentials_exception from exc

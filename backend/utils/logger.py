"""
EFL IndexDB — shared logging helper (Prompt 5-A).

Standard library logging: level from ``Config.LOG_LEVEL``, console + file.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from backend.utils.config import PROJECT_ROOT, Config

LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "efl_indexdb.log"
SECURITY_LOG_FILE = LOG_DIR / "security.log"

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
_CONFIGURED = False
_SECURITY_LOGGER: logging.Logger | None = None

def _resolve_level() -> int:
    name = (Config.LOG_LEVEL or "INFO").upper()
    return getattr(logging, name, logging.INFO)

def _ensure_root_handlers() -> None:
    """Attach shared handlers once to the package root logger."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = _resolve_level()
    root = logging.getLogger("efl_indexdb")
    root.setLevel(level)
    root.propagate = False

    formatter = logging.Formatter(_FORMAT)

    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in root.handlers):
        stream = logging.StreamHandler(sys.stdout)
        stream.setLevel(level)
        stream.setFormatter(formatter)
        root.addHandler(stream)

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        if not any(
            isinstance(h, logging.FileHandler) and Path(getattr(h, "baseFilename", "")) == LOG_FILE
            for h in root.handlers
        ):
            file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
    except OSError:

        pass

    _CONFIGURED = True

def get_logger(name: str = "efl_indexdb") -> logging.Logger:
    """
    Factory used by every module.

    Child loggers (``efl_indexdb.*``) inherit handlers from the package root.
    """
    _ensure_root_handlers()
    level = _resolve_level()

    if name == "efl_indexdb" or name.startswith("efl_indexdb."):
        logger = logging.getLogger(name)
    else:

        logger = logging.getLogger(f"efl_indexdb.{name}" if name else "efl_indexdb")

    logger.setLevel(level)

    if logger is not logging.getLogger("efl_indexdb"):
        logger.propagate = True

        logger.handlers.clear()
    return logger

def tail_log_lines(lines: int = 200) -> list[str]:
    """Return the last ``lines`` of ``logs/efl_indexdb.log`` (empty if missing)."""
    n = max(1, min(int(lines), 5000))
    if not LOG_FILE.exists():
        return []
    try:
        text = LOG_FILE.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    parts = text.splitlines()
    return parts[-n:]


def security_log(event: str, detail: str = "") -> None:
    """Append a security event to ``logs/security.log`` (separate from app log)."""
    global _SECURITY_LOGGER
    _ensure_root_handlers()
    if _SECURITY_LOGGER is None:
        sec = logging.getLogger("efl_indexdb.security")
        sec.setLevel(logging.INFO)
        sec.propagate = False
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            if not any(
                isinstance(h, logging.FileHandler)
                and Path(getattr(h, "baseFilename", "")) == SECURITY_LOG_FILE
                for h in sec.handlers
            ):
                fh = logging.FileHandler(SECURITY_LOG_FILE, encoding="utf-8")
                fh.setLevel(logging.INFO)
                fh.setFormatter(logging.Formatter(_FORMAT))
                sec.addHandler(fh)
        except OSError:
            # Fall back to root app logger if security file cannot be created
            get_logger("efl_indexdb.security").warning(
                "security_log file unavailable; event=%s detail=%s", event, detail
            )
            return
        _SECURITY_LOGGER = sec
    msg = f"event={event}"
    if detail:
        msg = f"{msg} | {detail}"
    _SECURITY_LOGGER.info(msg)

"""EFL IndexDB — shared logging helper (stdout + logs/efl_indexdb.log)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from backend.utils.config import PROJECT_ROOT

LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "efl_indexdb.log"


def get_logger(name: str = "efl_indexdb") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    stream = logging.StreamHandler(sys.stdout)
    stream.setLevel(logging.INFO)
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        # Still usable with stdout-only if logs/ cannot be created
        pass

    logger.propagate = False
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

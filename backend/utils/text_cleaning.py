"""
Shared text-cleaning rules (pipeline Clean stage + live Resource Analyzer).

Keep a single implementation so Stage 05 and live ingestion never drift.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup

MAX_TOKENS = 512
MIN_TEXT_LEN = 20
_WHITESPACE_RE = re.compile(r"\s+")


def strip_html(text: str) -> str:
    soup = BeautifulSoup(text, "lxml")
    return soup.get_text(separator=" ")


def normalise_unicode(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def collapse_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def truncate_tokens(text: str, max_tokens: int = MAX_TOKENS) -> str:
    tokens = text.split(" ")
    if len(tokens) <= max_tokens:
        return text
    return " ".join(tokens[:max_tokens])


def clean_text(text: str, *, max_tokens: int = MAX_TOKENS) -> tuple[str, str]:
    """
    Clean a single resource string.

    Returns ``(raw_text_truncated, raw_text_full)`` after HTML strip, NFKC,
    whitespace collapse, and optional token truncate. Raises ``ValueError``
    if the text is empty/too short after cleaning.
    """
    raw = "" if text is None else str(text)
    cleaned = collapse_whitespace(normalise_unicode(strip_html(raw)))
    if len(cleaned) < MIN_TEXT_LEN:
        raise ValueError(
            f"Text too short after cleaning ({len(cleaned)} chars; need ≥ {MIN_TEXT_LEN})"
        )
    full = cleaned
    truncated = truncate_tokens(full, max_tokens=max_tokens)
    return truncated, full


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]], int, int]:
    """Vectorised Clean-stage path used by ``stage_05_clean``."""
    steps_log: list[dict[str, Any]] = []
    working = df.copy()
    rows_before = len(working)

    text = working["raw_text"].fillna("").astype(str)
    keep_mask = text.map(lambda t: len(t.strip()) >= MIN_TEXT_LEN)
    dropped = int((~keep_mask).sum())
    working = working.loc[keep_mask].copy()
    steps_log.append(
        {
            "step": 1,
            "name": "drop_null_or_short_raw_text",
            "rows_removed": dropped,
            "rows_remaining": int(len(working)),
        }
    )

    raw_series = working["raw_text"].fillna("").astype(str)
    stripped = raw_series.map(strip_html)
    steps_log.append(
        {
            "step": 2,
            "name": "strip_html",
            "rows_removed": 0,
            "rows_remaining": int(len(working)),
            "note": "BeautifulSoup lxml get_text applied to all remaining rows",
        }
    )

    normalised = stripped.map(normalise_unicode)
    steps_log.append(
        {
            "step": 3,
            "name": "normalise_unicode_nfkc",
            "rows_removed": 0,
            "rows_remaining": int(len(working)),
        }
    )

    collapsed = normalised.map(collapse_whitespace)
    keep_after_collapse = collapsed.map(lambda t: len(t.strip()) >= MIN_TEXT_LEN)
    dropped_after = int((~keep_after_collapse).sum())
    working = working.loc[keep_after_collapse].copy()
    collapsed = collapsed.loc[keep_after_collapse]
    steps_log.append(
        {
            "step": 4,
            "name": "collapse_whitespace",
            "rows_removed": dropped_after,
            "rows_remaining": int(len(working)),
        }
    )

    raw_text_full = collapsed.copy()
    truncated = collapsed.map(lambda t: truncate_tokens(t, max_tokens=MAX_TOKENS))
    truncated_count = int((raw_text_full.str.split().map(len) > MAX_TOKENS).sum())
    working["raw_text_full"] = raw_text_full.to_numpy()
    working["raw_text"] = truncated.to_numpy()
    steps_log.append(
        {
            "step": 5,
            "name": "truncate_to_512_tokens",
            "rows_removed": 0,
            "rows_remaining": int(len(working)),
            "rows_truncated": truncated_count,
            "max_tokens": MAX_TOKENS,
        }
    )

    working = working.reset_index(drop=True)
    rows_after = len(working)
    return working, steps_log, rows_before, rows_after

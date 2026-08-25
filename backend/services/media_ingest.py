"""Ingest audio / video EFL media into the text index.

Supported:
  - sidecar captions: .vtt, .srt
  - audio/video: .mp3, .wav, .m4a, .ogg, .mp4, .webm (transcribe when possible)
Transcription uses openai-whisper if installed; otherwise caption sidecars
or a clear placeholder so the row is still indexed as listening material.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.media_ingest")

CAPTION_EXTS = {".vtt", ".srt"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
VIDEO_EXTS = {".mp4", ".webm", ".mov"}
MEDIA_EXTS = CAPTION_EXTS | AUDIO_EXTS | VIDEO_EXTS

_TS_RE = re.compile(
    r"^\d+$|^\d{2}:\d{2}:\d{2}[.,]\d+\s+-->\s+|WEBVTT|^NOTE\b|^STYLE\b",
    re.I,
)
_TAG_RE = re.compile(r"<[^>]+>")


def parse_captions(path: Path) -> str:
    lines: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or _TS_RE.match(line) or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        cleaned = _TAG_RE.sub("", line).strip()
        if cleaned:
            lines.append(cleaned)
    return " ".join(lines).strip()


def _try_whisper(path: Path) -> str | None:
    try:
        import whisper  # type: ignore
    except Exception:
        return None
    try:
        model = whisper.load_model("tiny")
        result = model.transcribe(str(path), fp16=False)
        return str(result.get("text") or "").strip() or None
    except Exception as exc:
        logger.warning("whisper failed for %s: %s", path.name, exc)
        return None


def transcribe_media(path: Path) -> tuple[str, str]:
    """Return (transcript_or_placeholder, method)."""
    ext = path.suffix.lower()
    if ext in CAPTION_EXTS:
        caption = parse_captions(path)
        return caption or f"[Empty captions: {path.name}]", "captions"

    sidecar = None
    for cap_ext in (".vtt", ".srt"):
        candidate = path.with_suffix(cap_ext)
        if candidate.exists():
            sidecar = parse_captions(candidate)
            if sidecar:
                return sidecar, "sidecar_captions"

    whispered = _try_whisper(path)
    if whispered:
        return whispered, "whisper"

    kind = "video" if ext in VIDEO_EXTS else "audio"
    placeholder = (
        f"[EFL {kind} resource: {path.stem.replace('_', ' ')}. "
        "Transcript unavailable on this machine; install openai-whisper "
        "or provide a .vtt/.srt sidecar. Indexed as Listening / Daily Life.]"
    )
    return placeholder, "placeholder"


def load_media_file(path: Path, rel: str) -> pd.DataFrame:
    text, method = transcribe_media(path)
    ext = path.suffix.lower()
    media_type = (
        "captions" if ext in CAPTION_EXTS else "video" if ext in VIDEO_EXTS else "audio"
    )
    title = path.stem.replace("_", " ").strip() or path.name
    return pd.DataFrame(
        [
            {
                "title": title,
                "raw_text": text,
                "skill_type": "Listening",
                "topic_domain": None,
                "source_name": path.parent.name,
                "source_file": rel,
                "source_ext": ext,
                "media_type": media_type,
                "transcript_method": method,
            }
        ]
    )

"""
Duplicate Detection — FAISS near-duplicates + admin resolution ledger.

Uses FAISS inner-product on L2-normalised vectors (= cosine similarity).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np

from backend.db.metadata_store import MetadataStore
from backend.db.vector_store import get_vector_store
from backend.utils.config import DATA_PROCESSED
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.duplicates")

NEAR_DUPLICATE_THRESHOLD = 0.97
BRUTE_FORCE_CAP = 5000
CANDIDATES_PATH = DATA_PROCESSED / "duplicate_candidates.json"
RESOLUTIONS_PATH = DATA_PROCESSED / "duplicate_resolutions.json"

ResolveAction = Literal["kept_both", "merged", "deleted_b"]
VALID_ACTIONS = {"kept_both", "merged", "deleted_b"}

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _pair_key(a: str, b: str) -> tuple[str, str]:
    x, y = sorted([str(a), str(b)])
    return x, y

def _load_resolutions() -> list[dict[str, Any]]:
    if not RESOLUTIONS_PATH.exists():
        return []
    try:
        with RESOLUTIONS_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return data
        return list(data.get("resolutions") or [])
    except Exception as exc:
        logger.warning("failed to load resolutions: %s", exc)
        return []

def _resolved_pair_keys() -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for row in _load_resolutions():
        a, b = row.get("resource_id_a"), row.get("resource_id_b")
        if a and b:
            keys.add(_pair_key(str(a), str(b)))
    return keys

def find_duplicates_for_vector(
    vector: np.ndarray,
    threshold: float = NEAR_DUPLICATE_THRESHOLD,
    exclude_id: str | None = None,
) -> list[dict[str, Any]]:
    """Nearest neighbours of ``vector`` with cosine similarity ≥ ``threshold``."""
    store = get_vector_store()
    if store.index is None or store.index.ntotal <= 0:
        return []

    fetch_k = min(max(25, 50), store.index.ntotal)
    hits = store.search(vector, top_k=fetch_k)
    meta_ids = [str(h["id"]) for h in hits if float(h["score"]) >= float(threshold)]
    meta_by_id = MetadataStore().get_by_ids(meta_ids)

    out: list[dict[str, Any]] = []
    from backend.services.taxonomy_labeler import display_title

    for hit in hits:
        rid = str(hit["id"])
        score = float(hit["score"])
        if exclude_id and rid == exclude_id:
            continue
        if score < float(threshold):
            continue
        meta = meta_by_id.get(rid) or {}
        out.append(
            {
                "resource_id": rid,
                "title": display_title(meta),
                "similarity": score,
            }
        )
    return out

def find_near_duplicate(
    embedding: np.ndarray,
    *,
    threshold: float = NEAR_DUPLICATE_THRESHOLD,
    exclude_ids: set[str] | None = None,
) -> dict[str, Any] | None:
    """Convenience wrapper used by the Resource Analyzer (single nearest hit)."""
    exclude = next(iter(exclude_ids), None) if exclude_ids else None
    hits = find_duplicates_for_vector(embedding, threshold=threshold, exclude_id=exclude)
    if exclude_ids:
        hits = [h for h in hits if h["resource_id"] not in exclude_ids]
    if not hits:
        return None
    top = hits[0]
    meta = MetadataStore().get_by_ids([top["resource_id"]]).get(top["resource_id"]) or {}
    return {
        "resource_id": top["resource_id"],
        "title": top["title"],
        "similarity": top["similarity"],
        "cefr_level": meta.get("cefr_level"),
        "skill_type": meta.get("skill_type"),
        "topic_domain": meta.get("topic_domain"),
    }

def _brute_force_scan(threshold: float) -> list[dict[str, Any]]:
    store = get_vector_store()
    if store.index is None:
        return []
    n = int(store.index.ntotal)
    if n <= 0:
        return []

    scan_n = n
    if n > BRUTE_FORCE_CAP:
        logger.warning(
            "FAISS index has %s vectors (> %s). Brute-force duplicate scan is capped "
            "at the first %s vectors — re-run stage 09 (Train) to refresh "
            "duplicate_candidates.json for a full-index pass.",
            n,
            BRUTE_FORCE_CAP,
            BRUTE_FORCE_CAP,
        )
        scan_n = BRUTE_FORCE_CAP

    pairs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    neighbour_k = min(20, scan_n)
    for i in range(scan_n):
        rid_i = store.row_to_id[i] if i < len(store.row_to_id) else ""
        if not rid_i or rid_i in store.tombstones:
            continue
        try:
            vec = store.index.reconstruct(i)
        except Exception:
            continue
        for hit in store.search(vec, top_k=neighbour_k):
            rid_j = str(hit["id"])
            score = float(hit["score"])
            if rid_j == rid_i or score < float(threshold):
                continue
            key = _pair_key(rid_i, rid_j)
            if key in seen:
                continue
            seen.add(key)
            pairs.append(
                {
                    "resource_id_a": key[0],
                    "resource_id_b": key[1],
                    "similarity": score,
                }
            )
    pairs.sort(key=lambda p: p["similarity"], reverse=True)
    return pairs

def scan_full_index(threshold: float = NEAR_DUPLICATE_THRESHOLD) -> list[dict[str, Any]]:
    """
    Fast path: load ``duplicate_candidates.json`` from Train (stage 09).
    Fallback: capped brute-force FAISS neighbour scan.
    """
    if CANDIDATES_PATH.exists():
        try:
            with CANDIDATES_PATH.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            candidates = data.get("candidates") if isinstance(data, dict) else data
            if isinstance(candidates, list):
                logger.info(
                    "Loaded %s duplicate candidates from %s",
                    len(candidates),
                    CANDIDATES_PATH,
                )

                out: list[dict[str, Any]] = []
                for row in candidates:
                    a, b = row.get("resource_id_a"), row.get("resource_id_b")
                    sim = float(row.get("similarity") or 0)
                    if not a or not b or sim < float(threshold):
                        continue
                    ka, kb = _pair_key(str(a), str(b))
                    out.append(
                        {
                            "resource_id_a": ka,
                            "resource_id_b": kb,
                            "similarity": sim,
                        }
                    )
                return out
        except Exception as exc:
            logger.warning("Failed reading candidates file (%s); brute-force fallback", exc)

    logger.info("duplicate_candidates.json missing — running capped FAISS scan")
    pairs = _brute_force_scan(threshold)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    payload = {
        "threshold": float(threshold),
        "capped_at": BRUTE_FORCE_CAP,
        "source": "brute_force_fallback",
        "run_at": _utc_now(),
        "candidates": pairs[:200],
    }
    with CANDIDATES_PATH.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    return pairs

def mark_resolved(resource_id_a: str, resource_id_b: str, action: str) -> None:
    """Persist an admin decision so re-scans do not re-flag the pair."""
    if action not in VALID_ACTIONS:
        raise ValueError(f"action must be one of {sorted(VALID_ACTIONS)}")
    a, b = _pair_key(resource_id_a, resource_id_b)
    rows = _load_resolutions()

    rows = [
        r
        for r in rows
        if _pair_key(str(r.get("resource_id_a")), str(r.get("resource_id_b"))) != (a, b)
    ]
    rows.append(
        {
            "resource_id_a": a,
            "resource_id_b": b,
            "action": action,
            "resolved_at": _utc_now(),
        }
    )
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    with RESOLUTIONS_PATH.open("w", encoding="utf-8") as fh:
        json.dump({"resolutions": rows}, fh, indent=2)
        fh.write("\n")
    logger.info("duplicate resolved %s / %s → %s", a, b, action)

def list_unresolved_candidates(
    threshold: float = NEAR_DUPLICATE_THRESHOLD,
) -> list[dict[str, Any]]:
    """Candidates from scan minus pairs already in duplicate_resolutions.json."""
    resolved = _resolved_pair_keys()
    raw = scan_full_index(threshold=threshold)
    store = get_vector_store()
    meta = MetadataStore()
    out: list[dict[str, Any]] = []
    for row in raw:
        key = _pair_key(row["resource_id_a"], row["resource_id_b"])
        if key in resolved:
            continue
        a, b = key
        if a in store.tombstones or b in store.tombstones:
            continue
        present = meta.get_by_ids([a, b])
        if a not in present or b not in present:
            continue
        out.append({"resource_id_a": a, "resource_id_b": b, "similarity": float(row["similarity"])})
    return out

def count_unresolved(threshold: float = NEAR_DUPLICATE_THRESHOLD) -> int:
    return len(list_unresolved_candidates(threshold=threshold))

def enrich_pairs(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach titles / CEFR / skill for both sides from metadata."""
    from backend.services.taxonomy_labeler import display_title, enrich_resource_display

    ids: list[str] = []
    for p in pairs:
        ids.extend([p["resource_id_a"], p["resource_id_b"]])
    meta = MetadataStore().get_by_ids(list(dict.fromkeys(ids)))

    def _side(rid: str) -> dict[str, Any]:
        m = enrich_resource_display(meta.get(rid) or {"resource_id": rid})
        raw = str(m.get("raw_text") or m.get("raw_text_preview") or "").strip()
        raw = raw.replace("\ufeff", "")
        snippet = (raw[:160] + "…") if len(raw) > 160 else raw
        return {
            "resource_id": rid,
            "title": display_title(m),
            "cefr_level": m.get("cefr_level"),
            "skill_type": m.get("skill_type"),
            "topic_domain": m.get("topic_domain"),
            "source_name": m.get("source_name"),
            "snippet": snippet,
        }

    enriched: list[dict[str, Any]] = []
    for p in pairs:
        enriched.append(
            {
                "resource_id_a": p["resource_id_a"],
                "resource_id_b": p["resource_id_b"],
                "similarity": float(p["similarity"]),
                "resource_a": _side(p["resource_id_a"]),
                "resource_b": _side(p["resource_id_b"]),
            }
        )
    return enriched

def refresh_candidates_file(threshold: float = NEAR_DUPLICATE_THRESHOLD) -> list[dict[str, Any]]:
    """
    Force a rescan.

    Prefer rewriting from a fresh neighbour scan when the Train artefact is
    stale; if the Train file exists we still re-load it as the primary source
    unless ``force_brute`` — here we delete+rescan only via brute when asked
    to refresh after deletions. For ``POST /rescan`` we re-read Train file if
    present, else brute-force (``scan_full_index`` already does that).
    """

    return scan_full_index(threshold=threshold)

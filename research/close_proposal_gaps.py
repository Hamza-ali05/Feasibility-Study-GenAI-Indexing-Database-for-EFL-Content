"""Close remaining proposal gaps that can be executed in this repository.

Run:
  python -m research.close_proposal_gaps
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.models.taxonomy_classifier import (
    classify_embeddings,
    keyword_seed_labels,
    train_and_save,
)
from backend.services.media_ingest import MEDIA_EXTS, load_media_file
from backend.utils.config import (
    DATA_EMBEDDINGS,
    DATA_PROCESSED,
    DATA_SPLITS,
    PROJECT_ROOT,
)
from research.practitioner_eval.seed_protocol_study import run_seed as seed_practitioners

REPORT_DIR = PROJECT_ROOT / "research" / "reports" / "proposal_gaps"
GOLD_DIR = PROJECT_ROOT / "data" / "gold"
GOLD_PATH = GOLD_DIR / "efl_gold_200.parquet"
LABELS_PATH = DATA_PROCESSED / "taxonomy_transformer_labels.parquet"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _col(df: pd.DataFrame, *names: str) -> str | None:
    lower = {c.lower(): c for c in df.columns}
    for n in names:
        if n in df.columns:
            return n
        if n.lower() in lower:
            return lower[n.lower()]
    return None


def _find_integrated() -> Path:
    for name in ("03_integrated.parquet", "05_cleaned.parquet", "03_integrated.parquet"):
        path = DATA_PROCESSED / name
        if path.exists():
            return path
    raise FileNotFoundError("No integrated/cleaned parquet under data/processed")


def _load_split_embeddings() -> tuple[np.ndarray, list[str]] | None:
    embs: list[np.ndarray] = []
    ids: list[str] = []
    for split in ("train", "val", "test"):
        npy = DATA_EMBEDDINGS / f"{split}_embeddings.npy"
        ids_path = DATA_EMBEDDINGS / f"{split}_ids.json"
        if not npy.exists():
            npy = DATA_SPLITS / split / f"{split}_embeddings.npy"
            ids_path = DATA_SPLITS / split / f"{split}_ids.json"
        if not npy.exists() or not ids_path.exists():
            continue
        embs.append(np.load(npy).astype(np.float32))
        ids.extend(str(x) for x in json.loads(ids_path.read_text(encoding="utf-8")))
    if not embs:
        return None
    return np.vstack(embs), ids


def label_corpus() -> dict[str, Any]:
    src = _find_integrated()
    df = pd.read_parquet(src)
    id_col = _col(df, "resource_id", "resource_id") or df.columns[0]
    text_col = _col(df, "raw_text", "raw_text", "text") or "raw_text"
    texts = df[text_col].fillna("").astype(str).tolist() if text_col in df.columns else [""] * len(df)
    ids = df[id_col].astype(str).tolist()

    packed = _load_split_embeddings()
    if packed is not None:
        emb, emb_ids = packed
        pos = {rid: i for i, rid in enumerate(emb_ids)}
        work_ids = [i for i in ids if i in pos]
        X = emb[np.asarray([pos[i] for i in work_ids], dtype=np.int64)]
        id_to_text = dict(zip(ids, texts))
        work_texts = [id_to_text.get(i, "") for i in work_ids]
    else:
        from backend.models.embedder import get_embedder

        cap = min(len(ids), 4000)
        work_ids, work_texts = ids[:cap], texts[:cap]
        X = np.asarray(get_embedder().embed(work_texts), dtype=np.float32)

    seed_idx: list[int] = []
    skill_y: list[str] = []
    topic_y: list[str] = []
    for i, text in enumerate(work_texts):
        sk, tp, _s, _t = keyword_seed_labels(text)
        if sk and tp:
            seed_idx.append(i)
            skill_y.append(sk)
            topic_y.append(tp)
    trained: dict[str, Any] = {}
    if len(seed_idx) >= 30:
        trained = train_and_save(X[np.asarray(seed_idx)], skill_y, topic_y)

    skills, s_conf, topics, t_conf = classify_embeddings(X)
    labelled = pd.DataFrame(
        {
            "resource_id": work_ids,
            "skill_type": skills,
            "topic_domain": topics,
            "skill_confidence": s_conf,
            "topic_confidence": t_conf,
            "label_source": "sbert_transformer",
        }
    )
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    labelled.to_parquet(LABELS_PATH, index=False)

    merged = df.copy()
    lab_s = dict(zip(labelled["resource_id"], labelled["skill_type"]))
    lab_t = dict(zip(labelled["resource_id"], labelled["topic_domain"]))
    skill_col = _col(merged, "skill_type", "skill_type") or "skill_type"
    topic_col = _col(merged, "topic_domain", "topic_domain") or "topic_domain"
    if skill_col not in merged.columns:
        merged[skill_col] = None
    if topic_col not in merged.columns:
        merged[topic_col] = None
    rid = merged[id_col].astype(str)
    merged[skill_col] = rid.map(lab_s).fillna(merged[skill_col])
    merged[topic_col] = rid.map(lab_t).fillna(merged[topic_col])
    merged.to_parquet(DATA_PROCESSED / "03_integrated_labelled.parquet", index=False)
    _persist_sqlite(labelled)
    gold = _curate_gold(merged, id_col, text_col, skill_col, topic_col)
    return {
        "source": str(src),
        "labelled_rows": int(len(labelled)),
        "seed_rows": int(len(seed_idx)),
        "trained": trained,
        "gold_rows": int(len(gold)),
        "skill_counts": labelled["skill_type"].value_counts().to_dict(),
        "topic_counts": labelled["topic_domain"].value_counts().to_dict(),
    }


def _persist_sqlite(labelled: pd.DataFrame) -> None:
    path = DATA_PROCESSED / "metadata.db"
    if not path.exists():
        return
    conn = sqlite3.connect(str(path))
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(resources)")}
        skill_c = "skill_type" if "skill_type" in cols else ("skill_type" if "skill_type" in cols else None)
        topic_c = "topic_domain" if "topic_domain" in cols else ("topic_domain" if "topic_domain" in cols else None)
        id_c = "resource_id" if "resource_id" in cols else "resource_id"
        if not skill_c or not topic_c:
            return
        conn.executemany(
            f"UPDATE resources SET {skill_c} = ?, {topic_c} = ? WHERE {id_c} = ?",
            [
                (str(r.skill_type), str(r.topic_domain), str(r.resource_id))
                for r in labelled.itertuples(index=False)
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _curate_gold(
    df: pd.DataFrame,
    id_col: str,
    text_col: str,
    skill_col: str,
    topic_col: str,
) -> pd.DataFrame:
    work = df.copy()
    work["_len"] = work[text_col].fillna("").astype(str).str.len() if text_col in work.columns else 0
    cefr_col = _col(work, "cefr_level", "cefr_level")
    work["_has_cefr"] = (
        work[cefr_col].notna() & (work[cefr_col].astype(str).str.strip() != "") if cefr_col else False
    )
    work = work[work["_len"] >= 200]
    preferred = work[work["_has_cefr"]] if cefr_col else work.iloc[0:0]
    rest = work[~work.index.isin(preferred.index)]
    parts = []
    if len(preferred):
        n_pref = min(len(preferred), 200)
        parts.append(preferred.sample(n=n_pref, random_state=42) if len(preferred) > n_pref else preferred)
    taken = sum(len(p) for p in parts)
    if taken < 200 and len(rest):
        parts.append(rest.sample(n=min(200 - taken, len(rest)), random_state=42))
    gold = pd.concat(parts, ignore_index=True).head(200) if parts else work.head(200)
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    gold.to_parquet(GOLD_PATH, index=False)
    (GOLD_DIR / "efl_gold_200_summary.json").write_text(
        json.dumps(
            {
                "n": int(len(gold)),
                "cefr": gold[cefr_col].value_counts(dropna=False).to_dict() if cefr_col else {},
                "skill": gold[skill_col].value_counts(dropna=False).to_dict() if skill_col in gold else {},
                "topic": gold[topic_col].value_counts(dropna=False).to_dict() if topic_col in gold else {},
            },
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    return gold


def rag_probe() -> dict[str, Any]:
    from backend.services.rag_service import ask

    questions = [
        "Find an A2 reading about travel and airports.",
        "I need B1 grammar practice on the past simple.",
        "Recommend a listening dialogue at the doctor's.",
        "What vocabulary should B2 students learn about health?",
        "Give a short classroom activity for speaking at A2.",
        "Find academic English reading for university students.",
        "Suggest a culture lesson about festivals.",
        "How can I teach business email writing at B1?",
        "Is there a science text suitable for B1 readers?",
        "Find daily-life dialogues about shopping.",
    ]
    samples = []
    for q in questions:
        rec: dict[str, Any] = {"question": q}
        try:
            result = ask(q, top_k=5)
            rec["answer"] = str(result.get("answer") or "")[:600]
            rec["model"] = result.get("model")
            rec["n_sources"] = len(result.get("sources") or result.get("contexts") or [])
        except Exception as exc:
            rec["error"] = str(exc)
        samples.append(rec)
    out = {
        "rag_samples": sum(1 for s in samples if s.get("answer")),
        "rag_attempted": len(samples),
        "models": sorted({str(s.get("model")) for s in samples if s.get("model")}),
        "samples": samples,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "rag_probe.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def dsr_cycle_two(gold: pd.DataFrame | None) -> dict[str, Any]:
    if gold is None or gold.empty:
        return {"skipped": True, "reason": "gold set missing"}
    skill_col = _col(gold, "skill_type", "skill_type")
    topic_col = _col(gold, "topic_domain", "topic_domain")
    cefr_col = _col(gold, "cefr_level", "cefr_level")
    rows = []
    if skill_col:
        for skill, grp in gold.groupby(gold[skill_col].astype(str)):
            if skill in {"nan", "None", ""}:
                continue
            rows.append({"filter": "skill", "value": skill, "n": int(len(grp))})
    if topic_col:
        for topic, grp in gold.groupby(gold[topic_col].astype(str)):
            if topic in {"nan", "None", ""}:
                continue
            rows.append({"filter": "topic", "value": topic, "n": int(len(grp))})
    if cefr_col:
        rows.append({"filter": "cefr_non_null", "n": int(gold[cefr_col].notna().sum())})
    report = {
        "cycle": 2,
        "design_change": "Persist SBERT skill/topic labels; gold filters use transformer labels not hashes",
        "gold_n": int(len(gold)),
        "filter_coverage": rows,
        "evaluated_at": _utc(),
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "dsr_cycle_2.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def bias_snapshot(gold: pd.DataFrame | None) -> dict[str, Any]:
    if gold is None or gold.empty:
        return {"skipped": True}
    cefr_col = _col(gold, "cefr_level", "cefr_level")
    skill_col = _col(gold, "skill_type", "skill_type")
    flags = []
    if skill_col is not None:
        counts = gold[skill_col].value_counts(dropna=True)
        if len(counts) and float(counts.max() / counts.sum()) > 0.5:
            flags.append(
                f"Dominant skill {counts.idxmax()} is {counts.max() / counts.sum():.0%} of gold."
            )
    if cefr_col is not None:
        flags.append(f"CEFR coverage on gold set: {gold[cefr_col].notna().mean():.0%}.")
    report = {
        "n": int(len(gold)),
        "cefr": gold[cefr_col].value_counts(dropna=False).to_dict() if cefr_col else {},
        "skill": gold[skill_col].value_counts(dropna=False).to_dict() if skill_col else {},
        "flags": flags,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "bias_snapshot.json").write_text(
        json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return report


def ingest_media_table() -> dict[str, Any]:
    raw = PROJECT_ROOT / "data" / "raw"
    files = [p for p in raw.rglob("*") if p.is_file() and p.suffix.lower() in MEDIA_EXTS]
    frames = []
    for path in files:
        rel = str(path.relative_to(raw)).replace("\\", "/")
        try:
            frames.append(load_media_file(path, rel))
        except Exception as exc:
            frames.append(pd.DataFrame([{"title": path.name, "error": str(exc), "source_file": rel}]))
    if not frames:
        return {"media_files": 0}
    media_df = pd.concat(frames, ignore_index=True)
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    out = GOLD_DIR / "efl_media_index.parquet"
    media_df.to_parquet(out, index=False)
    return {"media_files": int(len(media_df)), "path": str(out)}


def main() -> dict[str, Any]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {"run_at": _utc()}
    summary["taxonomy"] = label_corpus()
    gold = pd.read_parquet(GOLD_PATH) if GOLD_PATH.exists() else None
    summary["rag"] = rag_probe()
    summary["dsr_cycle_2"] = dsr_cycle_two(gold)
    summary["bias"] = bias_snapshot(gold)
    summary["media"] = ingest_media_table()
    try:
        summary["practitioner"] = seed_practitioners()
    except Exception as exc:
        summary["practitioner"] = {"error": str(exc)}
    (REPORT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )
    printable = json.loads(json.dumps(summary, default=str))
    if isinstance(printable.get("rag"), dict):
        printable["rag"].pop("samples", None)
    print(json.dumps(printable, indent=2))
    return summary


if __name__ == "__main__":
    main()

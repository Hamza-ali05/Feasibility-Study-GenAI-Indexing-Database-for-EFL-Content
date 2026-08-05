"""Reproducibility snapshots for the EFL IndexDB feasibility study.

Captures seed, package versions, hardware, configuration, and dataset
hashes so every pipeline / experiment run can be audited in the dissertation.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from research.utils.latex_tables import dataframe_to_all

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_RAW_DIR = _PROJECT_ROOT / "data" / "raw"
_PROCESSED = _PROJECT_ROOT / "data" / "processed"
_SNAP_DIR = _PROJECT_ROOT / "research" / "reproducibility"

_KEY_PACKAGES = (
    "sentence-transformers",
    "faiss-cpu",
    "scikit-learn",
    "pandas",
    "numpy",
    "shap",
    "lime",
    "anthropic",
    "fastapi",
    "torch",
)

# Alternate distribution names (importlib may use either)
_PACKAGE_ALIASES = {
    "faiss-cpu": ("faiss-cpu", "faiss"),
    "scikit-learn": ("scikit-learn", "sklearn"),
    "sentence-transformers": ("sentence-transformers", "sentence_transformers"),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pkg_version(name: str) -> str:
    """Return installed version or 'not installed'."""
    try:
        from importlib import metadata
    except ImportError:  # pragma: no cover
        return "not installed"

    candidates = _PACKAGE_ALIASES.get(name, (name,))
    for cand in candidates:
        try:
            return metadata.version(cand)
        except metadata.PackageNotFoundError:
            continue
    return "not installed"


def _all_packages() -> dict[str, str]:
    try:
        from importlib.metadata import distributions
    except ImportError:  # pragma: no cover
        return {}
    out: dict[str, str] = {}
    for dist in distributions():
        try:
            n = dist.metadata["Name"] or dist.name
            v = dist.version
            if n:
                out[str(n)] = str(v)
        except Exception:
            continue
    return dict(sorted(out.items(), key=lambda kv: kv[0].lower()))


def _gpu_info() -> dict[str, Any]:
    info: dict[str, Any] = {
        "available": False,
        "device_name": None,
        "memory_gb": None,
    }
    try:
        import torch

        if torch.cuda.is_available():
            info["available"] = True
            idx = torch.cuda.current_device()
            info["device_name"] = torch.cuda.get_device_name(idx)
            try:
                props = torch.cuda.get_device_properties(idx)
                info["memory_gb"] = round(float(props.total_memory) / (1024**3), 2)
            except Exception:
                info["memory_gb"] = None
    except Exception:
        pass
    return info


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _raw_dir_stats() -> dict[str, Any]:
    """Hash sorted concatenation of per-file hashes under data/raw/."""
    if not _RAW_DIR.exists():
        return {
            "raw_dir_hash": "",
            "total_raw_files": 0,
            "total_raw_bytes": 0,
        }

    entries: list[tuple[str, str, int]] = []
    for path in sorted(_RAW_DIR.rglob("*")):
        if not path.is_file():
            continue
        # Skip placeholder readmes / gitkeep
        if path.name in {".gitkeep", "README_PLACE_DATASETS_HERE.txt"}:
            continue
        rel = path.relative_to(_RAW_DIR).as_posix()
        digest = _file_sha256(path)
        size = path.stat().st_size
        entries.append((rel, digest, size))

    concat = "\n".join(f"{rel}:{digest}" for rel, digest, _ in entries)
    raw_hash = hashlib.sha256(concat.encode("utf-8")).hexdigest() if entries else ""
    return {
        "raw_dir_hash": raw_hash,
        "total_raw_files": len(entries),
        "total_raw_bytes": int(sum(s for _, _, s in entries)),
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None


def _dataset_info() -> dict[str, Any]:
    raw = _raw_dir_stats()
    integrated = _read_json(_PROCESSED / "03_integration_report.json") or _read_json(
        _PROCESSED / "03_integrated_report.json"
    )
    split = _read_json(_PROCESSED / "06_split_report.json")

    integrated_rows = None
    if integrated:
        integrated_rows = (
            integrated.get("n_rows")
            or integrated.get("rows")
            or integrated.get("total")
            or integrated.get("n_resources")
        )

    return {
        **raw,
        "integrated_rows": int(integrated_rows) if integrated_rows is not None else 0,
        "train_rows": int(split["train_n"]) if split and "train_n" in split else None,
        "val_rows": int(split["val_n"]) if split and "val_n" in split else None,
        "test_rows": int(split["test_n"]) if split and "test_n" in split else None,
    }


def _runtime_info() -> dict[str, Any]:
    """Pull per-stage timing from pipeline_state when available."""
    state = _read_json(_PROCESSED / "pipeline_state.json")
    if not state:
        return {"pipeline_total_seconds": None, "per_stage_seconds": None}

    stages = state.get("stages") or state.get("stage_status") or {}
    per_stage: dict[str, float] = {}
    total = 0.0
    found = False

    if isinstance(stages, dict):
        items = stages.items()
    elif isinstance(stages, list):
        items = [
            (s.get("name") or s.get("stage") or f"stage_{i}", s)
            for i, s in enumerate(stages)
        ]
    else:
        items = []

    for name, meta in items:
        if not isinstance(meta, dict):
            continue
        secs = (
            meta.get("duration_seconds")
            or meta.get("elapsed_seconds")
            or meta.get("runtime_seconds")
        )
        if secs is None and meta.get("started_at") and meta.get("completed_at"):
            try:
                start = datetime.fromisoformat(str(meta["started_at"]).replace("Z", "+00:00"))
                end = datetime.fromisoformat(str(meta["completed_at"]).replace("Z", "+00:00"))
                secs = (end - start).total_seconds()
            except Exception:
                secs = None
        if secs is not None:
            found = True
            per_stage[str(name)] = float(secs)
            total += float(secs)

    if not found:
        return {"pipeline_total_seconds": None, "per_stage_seconds": None}
    return {
        "pipeline_total_seconds": round(total, 3),
        "per_stage_seconds": per_stage,
    }


def _default_config() -> dict[str, Any]:
    try:
        from backend.utils.config import Config

        emb_model = getattr(Config, "SBERT_MODEL", None) or (
            "sentence-transformers/all-MiniLM-L6-v2"
        )
    except Exception:
        emb_model = "sentence-transformers/all-MiniLM-L6-v2"

    short = emb_model.split("/")[-1] if "/" in emb_model else emb_model
    return {
        "embedding_model": short or "all-MiniLM-L6-v2",
        "embedding_dim": 384,
        "faiss_index_type": "IndexFlatIP",
        "classifier": "LogisticRegression",
        "classifier_params": {"max_iter": 1000, "C": 1.0},
        "top_k_default": 10,
        "duplicate_threshold": 0.97,
        "balance_ratio_threshold": 3.0,
    }


class ReproducibilitySnapshot:
    """Capture, persist, compare, and export reproducibility artefacts."""

    @staticmethod
    def capture() -> dict[str, Any]:
        return {
            "timestamp": _now_iso(),
            "python_version": sys.version,
            "platform": {
                "os": platform.system(),
                "os_version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "cpu_count": os.cpu_count(),
            },
            "gpu": _gpu_info(),
            "packages": _all_packages(),
            "key_packages": {name: _pkg_version(name) for name in _KEY_PACKAGES},
            "random_seeds": {
                "python_random": 42,
                "numpy_random": 42,
                "sklearn_random_state": 42,
            },
            "dataset": _dataset_info(),
            "config": _default_config(),
            "runtime": _runtime_info(),
        }

    @staticmethod
    def save_snapshot(
        snapshot: dict[str, Any], output_path: str | None = None
    ) -> str:
        """Persist snapshot JSON + copy as latest_snapshot.json."""
        _SNAP_DIR.mkdir(parents=True, exist_ok=True)
        if output_path:
            path = Path(output_path)
        else:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            path = _SNAP_DIR / f"{stamp}_snapshot.json"

        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n"
        path.write_text(text, encoding="utf-8")

        latest = _SNAP_DIR / "latest_snapshot.json"
        latest.write_text(text, encoding="utf-8")
        return str(path.as_posix())

    @staticmethod
    def compare_snapshots(path_a: str, path_b: str) -> dict[str, Any]:
        a = json.loads(Path(path_a).read_text(encoding="utf-8-sig"))
        b = json.loads(Path(path_b).read_text(encoding="utf-8-sig"))

        pkgs_a = a.get("key_packages") or {}
        pkgs_b = b.get("key_packages") or {}
        package_changes = []
        for name in sorted(set(pkgs_a) | set(pkgs_b)):
            old, new = pkgs_a.get(name), pkgs_b.get(name)
            if old != new:
                package_changes.append({"package": name, "old": old, "new": new})

        cfg_a = a.get("config") or {}
        cfg_b = b.get("config") or {}
        config_changes = []

        def _flatten(prefix: str, obj: Any, out: dict[str, Any]) -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    _flatten(f"{prefix}.{k}" if prefix else str(k), v, out)
            else:
                out[prefix] = obj

        flat_a: dict[str, Any] = {}
        flat_b: dict[str, Any] = {}
        _flatten("", cfg_a, flat_a)
        _flatten("", cfg_b, flat_b)
        for key in sorted(set(flat_a) | set(flat_b)):
            if flat_a.get(key) != flat_b.get(key):
                config_changes.append(
                    {"key": key, "old": flat_a.get(key), "new": flat_b.get(key)}
                )

        ds_a = a.get("dataset") or {}
        ds_b = b.get("dataset") or {}
        dataset_changes = {
            "hash_match": ds_a.get("raw_dir_hash") == ds_b.get("raw_dir_hash"),
            "raw_dir_hash_a": ds_a.get("raw_dir_hash"),
            "raw_dir_hash_b": ds_b.get("raw_dir_hash"),
            "total_raw_files_a": ds_a.get("total_raw_files"),
            "total_raw_files_b": ds_b.get("total_raw_files"),
            "integrated_rows_a": ds_a.get("integrated_rows"),
            "integrated_rows_b": ds_b.get("integrated_rows"),
            "train_rows_a": ds_a.get("train_rows"),
            "train_rows_b": ds_b.get("train_rows"),
        }

        hardware_changes = []
        plat_a = a.get("platform") or {}
        plat_b = b.get("platform") or {}
        for key in sorted(set(plat_a) | set(plat_b)):
            if plat_a.get(key) != plat_b.get(key):
                hardware_changes.append(
                    {
                        "field": f"platform.{key}",
                        "old": plat_a.get(key),
                        "new": plat_b.get(key),
                    }
                )
        gpu_a = a.get("gpu") or {}
        gpu_b = b.get("gpu") or {}
        for key in sorted(set(gpu_a) | set(gpu_b)):
            if gpu_a.get(key) != gpu_b.get(key):
                hardware_changes.append(
                    {
                        "field": f"gpu.{key}",
                        "old": gpu_a.get(key),
                        "new": gpu_b.get(key),
                    }
                )

        return {
            "package_changes": package_changes,
            "config_changes": config_changes,
            "dataset_changes": dataset_changes,
            "hardware_changes": hardware_changes,
        }

    @staticmethod
    def export_environment_table(
        snapshot: dict[str, Any], output_dir: str
    ) -> list[str]:
        """Export key_packages as CSV / LaTeX / PNG for the methodology chapter."""
        key_pkgs = snapshot.get("key_packages") or {}
        rows = [{"Package": name, "Version": ver} for name, ver in key_pkgs.items()]
        df = pd.DataFrame(rows)
        if df.empty:
            df = pd.DataFrame([{"Package": "—", "Version": "—"}])
        return dataframe_to_all(
            df,
            base_name="environment_key_packages",
            output_dir=output_dir,
            caption="Key Python package versions (reproducibility snapshot)",
            label="tab:environment_key_packages",
        )


def capture_environment() -> dict[str, Any]:
    """Convenience wrapper used by ExperimentTracker (Phase 11)."""
    return ReproducibilitySnapshot.capture()

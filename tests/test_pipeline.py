"""Pipeline unit tests (Prompt 6-A)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.db.vector_store import FAISSVectorStore
from backend.utils import pipeline_state
from backend.utils.text_cleaning import MIN_TEXT_LEN, clean_dataframe

def test_pipeline_state_init(tmp_path: Path) -> None:
    """All 14 stages initialise as PENDING on a fresh state file."""
    state_path = tmp_path / "pipeline_state.json"
    state = pipeline_state.load_state(state_path)

    assert len(state) == 14
    assert list(state.keys()) == pipeline_state.STAGES_IN_ORDER
    for name, entry in state.items():
        assert entry["status"] == pipeline_state.STATUS_PENDING, name

def test_discover_raises_on_empty_dir(tmp_path: Path) -> None:
    from backend.pipeline.stage_01_discover import discover_files

    empty = tmp_path / "raw"
    empty.mkdir()
    (empty / ".gitkeep").write_text("", encoding="utf-8")

    with pytest.raises(RuntimeError, match="data/raw/ is empty"):
        discover_files(empty)

def test_discover_manifest_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.pipeline import stage_01_discover as discover

    raw = tmp_path / "raw"
    raw.mkdir()
    csv_path = raw / "sample.csv"
    csv_path.write_text("title,raw_text\nHello,This is a long enough sample row\n", encoding="utf-8")

    processed = tmp_path / "processed"
    processed.mkdir()
    state_path = tmp_path / "pipeline_state.json"

    monkeypatch.setattr(discover, "DATA_RAW", raw)
    monkeypatch.setattr(discover, "DATA_PROCESSED", processed)
    monkeypatch.setattr(discover, "MANIFEST_PATH", processed / "01_discover_manifest.json")
    monkeypatch.setattr(pipeline_state, "PIPELINE_STATE_PATH", state_path)
    monkeypatch.setattr(
        "backend.utils.pipeline_state.PIPELINE_STATE_PATH",
        state_path,
    )

    monkeypatch.setattr(discover.pipeline_state, "mark_running", lambda *_a, **_k: None)
    monkeypatch.setattr(discover.pipeline_state, "mark_complete", lambda *_a, **_k: None)
    monkeypatch.setattr(discover.pipeline_state, "mark_failed", lambda *_a, **_k: None)

    manifest = discover.run()

    assert set(manifest.keys()) >= {"stage", "run_at", "files"}
    assert manifest["stage"] == "Discover"
    assert len(manifest["files"]) == 1
    file_entry = manifest["files"][0]
    assert set(file_entry.keys()) >= {
        "path",
        "ext",
        "size_bytes",
        "rows_estimate",
        "encoding",
    }
    assert file_entry["path"] == "sample.csv"
    assert file_entry["ext"] == ".csv"

    on_disk = json.loads((processed / "01_discover_manifest.json").read_text(encoding="utf-8"))
    assert on_disk["files"][0]["path"] == "sample.csv"

def test_load_unified_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.pipeline import stage_02_load as load

    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "demo.csv").write_text(
        "title,raw_text\nOne,Alpha text long enough here\nTwo,Beta text long enough here\n",
        encoding="utf-8",
    )

    processed = tmp_path / "processed"
    processed.mkdir()
    manifest = {
        "stage": "Discover",
        "run_at": "2026-01-01T00:00:00+00:00",
        "files": [
            {
                "path": "demo.csv",
                "ext": ".csv",
                "size_bytes": 100,
                "rows_estimate": 3,
                "encoding": "utf-8",
            }
        ],
    }
    manifest_path = processed / "01_discover_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    parquet_path = processed / "02_loaded.parquet"

    monkeypatch.setattr(load, "DATA_RAW", raw)
    monkeypatch.setattr(load, "DATA_PROCESSED", processed)
    monkeypatch.setattr(load, "MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(load, "PARQUET_PATH", parquet_path)
    monkeypatch.setattr(load, "REPORT_PATH", processed / "02_load_report.json")

    monkeypatch.setattr(load, "_load_manifest", lambda path=None: list(manifest["files"]))
    monkeypatch.setattr(load.pipeline_state, "mark_running", lambda *_a, **_k: None)
    monkeypatch.setattr(load.pipeline_state, "mark_complete", lambda *_a, **_k: None)
    monkeypatch.setattr(load.pipeline_state, "mark_failed", lambda *_a, **_k: None)

    load.run()

    df = pd.read_parquet(parquet_path)
    assert "source_file" in df.columns
    assert set(df["source_file"].unique()) == {"demo.csv"}
    assert len(df) == 2

def test_clean_drops_short_rows() -> None:
    df = pd.DataFrame(
        {
            "resource_id": ["a", "b", "c"],
            "title": ["t1", "t2", "t3"],
            "raw_text": [
                "short",
                "x" * (MIN_TEXT_LEN - 1),
                "This sentence is definitely longer than twenty characters.",
            ],
            "cefr_level": ["A1", "A2", "B1"],
            "skill_type": ["Reading"] * 3,
            "topic_domain": ["Travel"] * 3,
            "source_name": ["test"] * 3,
            "source_url": [None] * 3,
        }
    )
    cleaned, _steps, before, after = clean_dataframe(df)
    assert before == 3
    assert after == 1
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["resource_id"] == "c"

def test_split_ratios(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.pipeline import stage_06_split as split

    n = 200
    levels = (["A1", "A2", "B1", "B2"] * (n // 4))[:n]
    df = pd.DataFrame(
        {
            "resource_id": [f"r{i}" for i in range(n)],
            "title": [f"Title {i}" for i in range(n)],
            "raw_text": [f"Sample text content number {i} " + ("word " * 10) for i in range(n)],
            "cefr_level": levels,
            "skill_type": ["Reading"] * n,
            "topic_domain": ["Travel"] * n,
            "source_name": ["synth"] * n,
            "source_url": [None] * n,
        }
    )

    processed = tmp_path / "processed"
    splits = tmp_path / "splits"
    processed.mkdir()
    for part in ("train", "val", "test"):
        (splits / part).mkdir(parents=True)

    cleaned_path = processed / "05_cleaned.parquet"
    df.to_parquet(cleaned_path, index=False)

    monkeypatch.setattr(split, "DATA_PROCESSED", processed)
    monkeypatch.setattr(split, "DATA_SPLITS", splits)
    monkeypatch.setattr(split, "INPUT_PATH", cleaned_path)
    monkeypatch.setattr(split, "TRAIN_PATH", splits / "train" / "train.parquet")
    monkeypatch.setattr(split, "VAL_PATH", splits / "val" / "val.parquet")
    monkeypatch.setattr(split, "TEST_PATH", splits / "test" / "test.parquet")
    monkeypatch.setattr(split, "REPORT_PATH", processed / "06_split_report.json")
    monkeypatch.setattr(split.pipeline_state, "mark_running", lambda *_a, **_k: None)
    monkeypatch.setattr(split.pipeline_state, "mark_complete", lambda *_a, **_k: None)
    monkeypatch.setattr(split.pipeline_state, "mark_failed", lambda *_a, **_k: None)

    split.run()

    train_n = len(pd.read_parquet(splits / "train" / "train.parquet"))
    val_n = len(pd.read_parquet(splits / "val" / "val.parquet"))
    test_n = len(pd.read_parquet(splits / "test" / "test.parquet"))
    total = train_n + val_n + test_n
    assert total == n

    assert abs(train_n / total - 0.70) <= 0.02
    assert abs(val_n / total - 0.15) <= 0.02
    assert abs(test_n / total - 0.15) <= 0.02

def test_preprocess_embedding_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.pipeline import stage_07_preprocess as preprocess

    splits = tmp_path / "splits"
    embeddings_dir = tmp_path / "embeddings"
    processed = tmp_path / "processed"
    embeddings_dir.mkdir()
    processed.mkdir()

    def _write_split(name: str, n: int) -> Path:
        part = splits / name
        part.mkdir(parents=True)
        path = part / f"{name}.parquet"
        pd.DataFrame(
            {
                "resource_id": [f"{name}-{i}" for i in range(n)],
                "raw_text": [f"Text for {name} row {i} " + ("x " * 15) for i in range(n)],
            }
        ).to_parquet(path, index=False)
        return path

    train_path = _write_split("train", 5)
    val_path = _write_split("val", 3)
    test_path = _write_split("test", 2)

    dim = 8

    class FakeEmbedder:
        embedding_dim = dim

        def __init__(self, *_a, **_k) -> None:
            pass

        def encode(self, texts, **_kwargs):
            return np.ones((len(list(texts)), dim), dtype=np.float32)

    monkeypatch.setattr(preprocess, "Embedder", FakeEmbedder)
    monkeypatch.setattr(preprocess, "DATA_EMBEDDINGS", embeddings_dir)
    monkeypatch.setattr(preprocess, "DATA_PROCESSED", processed)
    monkeypatch.setattr(preprocess, "DATA_SPLITS", splits)
    monkeypatch.setattr(preprocess, "TRAIN_PARQUET", train_path)
    monkeypatch.setattr(preprocess, "VAL_PARQUET", val_path)
    monkeypatch.setattr(preprocess, "TEST_PARQUET", test_path)
    monkeypatch.setattr(preprocess, "REPORT_PATH", processed / "07_preprocess_report.json")
    monkeypatch.setattr(preprocess.pipeline_state, "mark_running", lambda *_a, **_k: None)
    monkeypatch.setattr(preprocess.pipeline_state, "mark_complete", lambda *_a, **_k: None)
    monkeypatch.setattr(preprocess.pipeline_state, "mark_failed", lambda *_a, **_k: None)
    monkeypatch.setattr(
        preprocess,
        "broadcast_pipeline_status",
        lambda *_a, **_k: None,
    )

    preprocess.run()

    train_emb = np.load(embeddings_dir / "train_embeddings.npy")
    val_emb = np.load(embeddings_dir / "val_embeddings.npy")
    test_emb = np.load(embeddings_dir / "test_embeddings.npy")

    assert train_emb.shape == (5, dim)
    assert val_emb.shape == (3, dim)
    assert test_emb.shape == (2, dim)

def test_tombstone_filters_search_results(tmp_path: Path) -> None:
    dim = 4
    ids = ["keep-a", "drop-me", "keep-b"]

    embeddings = np.eye(3, dim, dtype=np.float32)
    embeddings[1] = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)

    store = FAISSVectorStore(
        index_path=tmp_path / "faiss_index.bin",
        id_map_path=tmp_path / "faiss_id_map.json",
        tombstones_path=tmp_path / "tombstoned_ids.json",
        autoload=False,
    )
    store.build_index(embeddings, ids)
    store.tombstone("drop-me")

    hits = store.search(embeddings[1], top_k=3)
    returned_ids = [h["id"] for h in hits]
    assert "drop-me" not in returned_ids
    assert len(returned_ids) <= 2

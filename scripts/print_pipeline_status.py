"""Print existing pipeline stage status and key artefact presence (no re-run)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "processed" / "pipeline_state.json"
PROCESSED = ROOT / "data" / "processed"
EMBEDDINGS = ROOT / "data" / "embeddings"

ORDER = [
    "Discover",
    "Load",
    "Integrate",
    "EDA",
    "Clean",
    "Split",
    "Preprocess",
    "Balance",
    "Train",
    "Evaluate",
    "Explain Global",
    "Explain Local",
    "Explain Quality",
    "Predict",
]

KEY_FILES = [
    "01_discover_manifest.json",
    "02_load_report.json",
    "03_integration_report.json",
    "04_eda_report.json",
    "05_clean_report.json",
    "06_split_report.json",
    "07_preprocess_report.json",
    "08_balance_report.json",
    "09_train_report.json",
    "10_evaluation_report.json",
    "11_explain_global_report.json",
    "12_explain_local_report.json",
    "13_explain_quality_report.json",
    "14_last_predict.json",
    "metadata.db",
    "pipeline_state.json",
]


def stage_status(stages: dict, name: str) -> str:
    value = stages.get(name)
    if isinstance(value, dict):
        return str(value.get("status", "?"))
    if isinstance(value, str):
        return value
    return "?"


def main() -> int:
    if not STATE.exists():
        print("  [WARN] pipeline_state.json missing")
        return 1

    raw = json.loads(STATE.read_text(encoding="utf-8"))
    stages = raw.get("stages", raw) if isinstance(raw, dict) else {}

    print("  Stage                 Status")
    print("  --------------------- ----------")
    complete = 0
    for name in ORDER:
        status = stage_status(stages, name)
        if status == "COMPLETE":
            complete += 1
        print(f"  {name:<21} {status}")

    print()
    print(f"  Complete: {complete}/{len(ORDER)}")
    print("  Key artefacts under data/processed/:")
    for name in KEY_FILES:
        mark = "[OK]" if (PROCESSED / name).exists() else "[--]"
        print(f"   {mark} {name}")

    faiss = EMBEDDINGS / "faiss_index.bin"
    mark = "[OK]" if faiss.exists() else "[MISSING]"
    print(f"  FAISS index: {mark} {faiss.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

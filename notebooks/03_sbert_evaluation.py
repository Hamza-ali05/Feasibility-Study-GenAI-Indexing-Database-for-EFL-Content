

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path.cwd()
REPORT_PATH = ROOT / "data" / "processed" / "10_evaluation_report.json"
if not REPORT_PATH.exists():
    ROOT = Path.cwd().parent
    REPORT_PATH = ROOT / "data" / "processed" / "10_evaluation_report.json"

OUT_DIR = ROOT / "data" / "processed" / "eda_plots"
OUT_DIR.mkdir(parents=True, exist_ok=True)
DELTA_PNG = OUT_DIR / "sbert_vs_tfidf_delta.png"

BG_PAGE = "#F9F8F5"
BORDER = "#D3D1C7"
TEXT_MUTED = "#888780"
ACCENT = "#3C3489"
POSITIVE = "#1F5F3F"
NEGATIVE = "#7A1F35"

assert REPORT_PATH.exists(), (
    f"Missing {REPORT_PATH}. Run: python -m backend.pipeline.stage_10_evaluate"
)

report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
print("Loaded", REPORT_PATH)
print("stage=", report.get("stage"), " run_at=", report.get("run_at"))
print(
    "queries_evaluated=",
    report.get("retrieval", {}).get("queries_evaluated"),
    " k=",
    report.get("retrieval", {}).get("k"),
)
print("relevance_rule=", report.get("retrieval", {}).get("relevance_rule"))

retrieval = report["retrieval"]
ret_rows = []
for metric in ("precision_at_10", "recall_at_10", "map", "f1_at_10"):
    sbert_v = float(retrieval["sbert"][metric])
    tfidf_v = float(retrieval["tfidf"][metric])
    delta_v = float(retrieval["delta"][metric])
    ret_rows.append(
        {
            "metric": metric,
            "sbert": sbert_v,
            "tfidf": tfidf_v,
            "delta_sbert_minus_tfidf": delta_v,
        }
    )
retrieval_table = pd.DataFrame(ret_rows).set_index("metric")
print("=== Retrieval (test set) ===")
display_df = retrieval_table.copy()
print(display_df.to_string(float_format=lambda x: f"{x:.6f}"))

classification = report.get("classification", {})
clf_rows = []
for metric in ("accuracy", "precision_macro", "recall_macro", "f1_macro"):
    clf_rows.append(
        {
            "metric": metric,
            "sbert": float(classification.get("sbert", {}).get(metric, float("nan"))),
            "tfidf": float(classification.get("tfidf", {}).get(metric, float("nan"))),
        }
    )
clf_table = pd.DataFrame(clf_rows).set_index("metric")
clf_table["delta_sbert_minus_tfidf"] = clf_table["sbert"] - clf_table["tfidf"]
print("=== CEFR classification ===")
print(f"n_labeled_test={classification.get('n_labeled_test')}")
print(clf_table.to_string(float_format=lambda x: f"{x:.6f}"))

summary = pd.concat(
    [
        retrieval_table.assign(task="retrieval"),
        clf_table.assign(task="classification"),
    ]
)
summary = summary.reset_index().set_index(["task", "metric"])
print(summary.to_string(float_format=lambda x: f"{x:.6f}"))

plot_metrics = [
    ("retrieval / P@10", float(retrieval["delta"]["precision_at_10"])),
    ("retrieval / R@10", float(retrieval["delta"]["recall_at_10"])),
    ("retrieval / MAP", float(retrieval["delta"]["map"])),
    ("retrieval / F1@10", float(retrieval["delta"]["f1_at_10"])),
    ("clf / accuracy", float(clf_table.loc["accuracy", "delta_sbert_minus_tfidf"])),
    ("clf / F1-macro", float(clf_table.loc["f1_macro", "delta_sbert_minus_tfidf"])),
]

labels = [m[0] for m in plot_metrics]
values = [m[1] for m in plot_metrics]
colors = [POSITIVE if v >= 0 else NEGATIVE for v in values]

fig, ax = plt.subplots(figsize=(10, 5), facecolor=BG_PAGE)
ax.set_facecolor(BG_PAGE)
bars = ax.barh(labels, values, color=colors, edgecolor=BORDER)
ax.axvline(0.0, color=TEXT_MUTED, linewidth=1)
ax.set_xlabel("Δ metric (SBERT − TF-IDF)")
ax.set_title("SBERT vs TF-IDF — evaluation deltas")
ax.tick_params(colors=TEXT_MUTED)
for spine in ax.spines.values():
    spine.set_color(BORDER)
for bar, val in zip(bars, values):
    ax.text(
        val,
        bar.get_y() + bar.get_height() / 2,
        f" {val:+.4f}",
        va="center",
        ha="left" if val >= 0 else "right",
        color=TEXT_MUTED,
        fontsize=9,
    )
fig.tight_layout()
fig.savefig(DELTA_PNG, dpi=140, facecolor=BG_PAGE)
print("saved", DELTA_PNG)
plt.show()

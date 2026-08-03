

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path.cwd()
if not (ROOT / "data" / "processed" / "03_integrated.parquet").exists():
    ROOT = Path.cwd().parent

INTEGRATED = ROOT / "data" / "processed" / "03_integrated.parquet"
PLOTS_DIR = ROOT / "data" / "processed" / "eda_plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

BG_PAGE = "#F9F8F5"
BORDER = "#D3D1C7"
TEXT_MUTED = "#888780"
TEXT_PRIMARY = "#2C2C2A"
CEFR_COLORS = {
    "A1": "#1F5F3F",
    "A2": "#1F4A6E",
    "B1": "#7A5A00",
    "B2": "#8A4B12",
    "C1": "#7A1F35",
    "C2": "#3C3489",
}
CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
SKILL_ORDER = ["Reading", "Writing", "Listening", "Speaking", "Grammar", "Vocabulary"]
TOPIC_ORDER = [
    "Business",
    "Science",
    "Culture",
    "Technology",
    "Daily Life",
    "Academic",
    "Travel",
    "Health",
]

print("Loading", INTEGRATED)
df = pd.read_parquet(INTEGRATED)
print(f"rows={len(df):,}  cols={list(df.columns)}")
df.head(3)

df = df.copy()
df["text_len"] = df["raw_text"].fillna("").astype(str).str.len()

print("=== raw_text character length describe() ===")
print(df["text_len"].describe())

print("\n=== CEFR value counts ===")
print(df["cefr_level"].value_counts(dropna=False).reindex(CEFR_ORDER + [None], fill_value=0))

print("\n=== skill_type value counts ===")
print(df["skill_type"].value_counts(dropna=False))

print("\n=== topic_domain value counts ===")
print(df["topic_domain"].value_counts(dropna=False))

null_cols = [
    "resource_id",
    "title",
    "raw_text",
    "cefr_level",
    "skill_type",
    "topic_domain",
    "source_name",
    "source_url",
]
null_rates = {c: float(df[c].isna().mean()) for c in null_cols if c in df.columns}
print("\n=== null rates ===")
for k, v in null_rates.items():
    print(f"  {k:16s} {v:6.2%}")

def _style(ax: plt.Axes) -> None:
    ax.set_facecolor(BG_PAGE)
    ax.tick_params(colors=TEXT_MUTED)
    for spine in ax.spines.values():
        spine.set_color(BORDER)

cefr_counts = (
    df["cefr_level"].dropna().astype(str).value_counts().reindex(CEFR_ORDER, fill_value=0)
)
fig, ax = plt.subplots(figsize=(8, 4), facecolor=BG_PAGE)
ax.bar(
    CEFR_ORDER,
    [int(cefr_counts.get(k, 0)) for k in CEFR_ORDER],
    color=[CEFR_COLORS[k] for k in CEFR_ORDER],
)
ax.set_title("CEFR level distribution")
ax.set_xlabel("CEFR level")
ax.set_ylabel("Count")
_style(ax)
fig.tight_layout()
out = PLOTS_DIR / "cefr_bar.png"
fig.savefig(out, dpi=120, facecolor=BG_PAGE)
print("saved", out)
plt.show()

skill_counts = df["skill_type"].dropna().astype(str).value_counts()
labels = [k for k in SKILL_ORDER if k in skill_counts.index]
if not labels:
    labels = list(skill_counts.index)
sizes = [int(skill_counts[k]) for k in labels]

fig, ax = plt.subplots(figsize=(7, 7), facecolor=BG_PAGE)
ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90)
ax.set_title("Skill-type distribution")
fig.tight_layout()
out = PLOTS_DIR / "skill_pie.png"
fig.savefig(out, dpi=120, facecolor=BG_PAGE)
print("saved", out)
plt.show()

topic_counts = (
    df["topic_domain"].dropna().astype(str).value_counts().reindex(TOPIC_ORDER, fill_value=0)
)
ordered = [k for k in TOPIC_ORDER if int(topic_counts.get(k, 0)) > 0]
fig, ax = plt.subplots(figsize=(9, 4), facecolor=BG_PAGE)
ax.barh(ordered, [int(topic_counts[k]) for k in ordered], color="#3C3489")
ax.set_title("Topic domain distribution")
ax.set_xlabel("Count")
_style(ax)
fig.tight_layout()
out = PLOTS_DIR / "topic_bar.png"
fig.savefig(out, dpi=120, facecolor=BG_PAGE)
print("saved", out)
plt.show()

lengths = df["text_len"]
clip = float(lengths.quantile(0.99)) if len(lengths) else 0.0
clipped = lengths.clip(upper=clip)

fig, ax = plt.subplots(figsize=(8, 4), facecolor=BG_PAGE)
ax.hist(clipped, bins=40, color="#1F4A6E", edgecolor=BORDER)
ax.set_title("raw_text character length (clipped at 99th pct)")
ax.set_xlabel("Characters")
ax.set_ylabel("Frequency")
_style(ax)
fig.tight_layout()
out = PLOTS_DIR / "text_length_hist.png"
fig.savefig(out, dpi=120, facecolor=BG_PAGE)
print("saved", out)
plt.show()

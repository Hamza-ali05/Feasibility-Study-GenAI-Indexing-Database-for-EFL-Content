"""
Stage 04 — EDA

Exploratory statistics and plots for Metrics / Dashboard artefacts.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from backend.utils.config import DATA_PROCESSED
from backend.utils.logger import get_logger
from backend.utils import pipeline_state

logger = get_logger("efl_indexdb.pipeline.eda")

STAGE_NAME = "EDA"
INPUT_PATH = DATA_PROCESSED / "03_integrated.parquet"
REPORT_PATH = DATA_PROCESSED / "04_eda_report.json"
PLOTS_DIR = DATA_PROCESSED / "eda_plots"

BG_PAGE = "#F9F8F5"
BORDER = "#D3D1C7"
TEXT_MUTED = "#888780"
ACCENT_PURPLE = "#3C3489"
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

def _style_axes(ax: plt.Axes) -> None:
    ax.set_facecolor(BG_PAGE)
    ax.tick_params(colors=TEXT_MUTED)
    ax.xaxis.label.set_color(TEXT_PRIMARY)
    ax.yaxis.label.set_color(TEXT_PRIMARY)
    ax.title.set_color(TEXT_PRIMARY)
    for spine in ax.spines.values():
        spine.set_color(BORDER)

def _distribution(series: pd.Series, ordered: list[str]) -> dict[str, int]:
    counts = series.dropna().astype(str).value_counts()
    return {key: int(counts.get(key, 0)) for key in ordered}

def _text_length_stats(series: pd.Series) -> dict[str, float]:
    lengths = series.fillna("").astype(str).str.len()
    return {
        "mean": float(lengths.mean()) if len(lengths) else 0.0,
        "median": float(lengths.median()) if len(lengths) else 0.0,
        "std": float(lengths.std(ddof=0)) if len(lengths) else 0.0,
        "min": int(lengths.min()) if len(lengths) else 0,
        "max": int(lengths.max()) if len(lengths) else 0,
    }

def _null_rates(df: pd.DataFrame, columns: list[str]) -> dict[str, float]:
    n = len(df) or 1
    return {col: float(df[col].isna().sum() / n) for col in columns}

def _top_sources(series: pd.Series, n: int = 10) -> list[dict]:
    counts = series.fillna("(unknown)").astype(str).value_counts().head(n)
    return [{"source_name": str(name), "count": int(count)} for name, count in counts.items()]

def _plot_cefr_bar(dist: dict[str, int], path: Path) -> None:
    labels = CEFR_ORDER
    values = [dist.get(k, 0) for k in labels]
    colors = [CEFR_COLORS[k] for k in labels]

    fig, ax = plt.subplots(figsize=(8, 4.5), facecolor=BG_PAGE)
    ax.bar(labels, values, color=colors, edgecolor=BORDER, linewidth=0.8)
    ax.set_title("CEFR level distribution")
    ax.set_xlabel("CEFR level")
    ax.set_ylabel("Count")
    _style_axes(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=120, facecolor=BG_PAGE)
    plt.close(fig)

def _plot_skill_pie(dist: dict[str, int], path: Path) -> None:
    labels = [k for k in SKILL_ORDER if dist.get(k, 0) > 0]
    values = [dist[k] for k in labels]

    palette = [BORDER, TEXT_MUTED, ACCENT_PURPLE, "#B4B2A9", "#5F5E5A", "#D3D1C7"]
    colors = [palette[i % len(palette)] for i in range(len(labels))]

    fig, ax = plt.subplots(figsize=(7, 5), facecolor=BG_PAGE)
    if sum(values) == 0:
        ax.text(0.5, 0.5, "No skill_type values", ha="center", va="center", color=TEXT_MUTED)
        ax.set_axis_off()
    else:
        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            colors=colors,
            autopct="%1.1f%%",
            startangle=90,
            wedgeprops={"edgecolor": BG_PAGE, "linewidth": 1},
            textprops={"color": TEXT_PRIMARY},
        )
        for t in autotexts:
            t.set_color(TEXT_PRIMARY)
            t.set_fontsize(8)
        ax.set_title("Skill type distribution")
    fig.tight_layout()
    fig.savefig(path, dpi=120, facecolor=BG_PAGE)
    plt.close(fig)

def _plot_topic_bar(dist: dict[str, int], path: Path) -> None:
    labels = TOPIC_ORDER
    values = [dist.get(k, 0) for k in labels]

    fig, ax = plt.subplots(figsize=(9, 4.5), facecolor=BG_PAGE)
    ax.bar(labels, values, color=ACCENT_PURPLE, edgecolor=BORDER, linewidth=0.8)
    ax.set_title("Topic domain distribution")
    ax.set_xlabel("Topic")
    ax.set_ylabel("Count")
    ax.tick_params(axis="x", rotation=30)
    _style_axes(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=120, facecolor=BG_PAGE)
    plt.close(fig)

def _plot_text_length_hist(lengths: pd.Series, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5), facecolor=BG_PAGE)
    data = lengths.clip(upper=lengths.quantile(0.99)) if len(lengths) else lengths
    ax.hist(data, bins=40, color=TEXT_MUTED, edgecolor=BORDER)
    ax.set_title("Text length (characters)")
    ax.set_xlabel("Character count")
    ax.set_ylabel("Frequency")
    _style_axes(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=120, facecolor=BG_PAGE)
    plt.close(fig)

def build_report(df: pd.DataFrame) -> dict:
    cefr_distribution = _distribution(df["cefr_level"], CEFR_ORDER)
    skill_distribution = _distribution(df["skill_type"], SKILL_ORDER)
    topic_distribution = _distribution(df["topic_domain"], TOPIC_ORDER)
    text_length_stats = _text_length_stats(df["raw_text"])
    null_rates = _null_rates(
        df,
        ["resource_id", "title", "raw_text", "cefr_level", "skill_type", "topic_domain", "source_name", "source_url"],
    )
    top_sources = _top_sources(df["source_name"], n=10)

    return {
        "stage": STAGE_NAME,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "total_resources": int(len(df)),
        "cefr_distribution": cefr_distribution,
        "skill_distribution": skill_distribution,
        "topic_distribution": topic_distribution,
        "text_length_stats": text_length_stats,
        "null_rates": {k: round(v, 4) for k, v in null_rates.items()},
        "top_sources": top_sources,
    }

def print_summary(report: dict) -> None:
    print("\n=== EDA summary (EFL IndexDB) ===")
    print(f"total_resources: {report['total_resources']}")
    print(f"cefr_distribution: {report['cefr_distribution']}")
    print(f"skill_distribution: {report['skill_distribution']}")
    print(f"topic_distribution: {report['topic_distribution']}")
    print(f"text_length_stats: {report['text_length_stats']}")
    print(f"null_rates: {report['null_rates']}")
    print("top_sources:")
    for item in report["top_sources"]:
        print(f"  - {item['source_name']}: {item['count']}")
    print(f"plots → {PLOTS_DIR}")
    print("=================================\n")

def run() -> dict:
    pipeline_state.mark_running(STAGE_NAME)
    try:
        if not INPUT_PATH.exists():
            raise RuntimeError(
                f"Missing {INPUT_PATH}. Run Integrate first: "
                "python -m backend.pipeline.stage_03_integrate"
            )

        df = pd.read_parquet(INPUT_PATH)
        logger.info("loaded %s rows from %s", len(df), INPUT_PATH)

        report = build_report(df)
        PLOTS_DIR.mkdir(parents=True, exist_ok=True)

        lengths = df["raw_text"].fillna("").astype(str).str.len()
        _plot_cefr_bar(report["cefr_distribution"], PLOTS_DIR / "cefr_bar.png")
        _plot_skill_pie(report["skill_distribution"], PLOTS_DIR / "skill_pie.png")
        _plot_topic_bar(report["topic_distribution"], PLOTS_DIR / "topic_bar.png")
        _plot_text_length_hist(lengths, PLOTS_DIR / "text_length_hist.png")
        logger.info("wrote plots to %s", PLOTS_DIR)

        report["plots"] = {
            "cefr_bar": str((PLOTS_DIR / "cefr_bar.png").as_posix()),
            "skill_pie": str((PLOTS_DIR / "skill_pie.png").as_posix()),
            "topic_bar": str((PLOTS_DIR / "topic_bar.png").as_posix()),
            "text_length_hist": str((PLOTS_DIR / "text_length_hist.png").as_posix()),
        }

        with REPORT_PATH.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
            fh.write("\n")
        logger.info("wrote EDA report → %s", REPORT_PATH)

        print_summary(report)
        pipeline_state.mark_complete(STAGE_NAME)
        return report
    except Exception:
        pipeline_state.mark_failed(STAGE_NAME)
        raise

if __name__ == "__main__":
    run()

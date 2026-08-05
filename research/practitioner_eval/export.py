"""Publication-ready exports for practitioner evaluation artefacts.

Produces CSV, LaTeX tabular, and PNG figures using the project greyish
palette shared with the pipeline EDA / explainability charts.
"""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from research.practitioner_eval.feedback_analyzer import FeedbackAnalyzer
from research.practitioner_eval.interview_manager import InterviewManager
from research.practitioner_eval.qualitative_coder import QualitativeCoder
from research.practitioner_eval.questionnaire_store import QuestionnaireStore

# Project palette (aligned with backend/pipeline/stage_04_eda.py)
BG_PAGE = "#F9F8F5"
BORDER = "#D3D1C7"
TEXT_MUTED = "#888780"
ACCENT = "#3C3489"
TEXT_PRIMARY = "#2C2C2A"
GREY_MID = "#B4B2A9"
GREY_DARK = "#5F5E5A"
GREYISH = [BORDER, TEXT_MUTED, GREY_MID, GREY_DARK, ACCENT, "#A8A69E"]

_RESEARCH_ROOT = Path(__file__).resolve().parents[1]


def _latex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    out = str(text)
    for src, dst in replacements.items():
        out = out.replace(src, dst)
    return out


def _write_latex_tabular(
    path: Path,
    headers: list[str],
    rows: list[list[str]],
    caption: str,
    label: str,
) -> None:
    cols = "l" * len(headers)
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        rf"\caption{{{_latex_escape(caption)}}}",
        rf"\label{{{label}}}",
        rf"\begin{{tabular}}{{{cols}}}",
        r"\toprule",
        " & ".join(_latex_escape(h) for h in headers) + r" \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(
            " & ".join(_latex_escape(c) for c in row) + r" \\"
        )
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _render_table_png(
    path: Path,
    headers: list[str],
    rows: list[list[str]],
    title: str,
) -> None:
    fig, ax = plt.subplots(
        figsize=(max(6, 1.6 * len(headers)), max(2.5, 0.45 * (len(rows) + 2)))
    )
    fig.patch.set_facecolor(BG_PAGE)
    ax.set_facecolor(BG_PAGE)
    ax.axis("off")
    ax.set_title(title, color=TEXT_PRIMARY, fontsize=12, pad=12)

    cell_text = rows if rows else [["—"] * len(headers)]
    table = ax.table(
        cellText=cell_text,
        colLabels=headers,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.2, 1.4)
    for (row_i, col_i), cell in table.get_celld().items():
        cell.set_edgecolor(BORDER)
        if row_i == 0:
            cell.set_facecolor(GREY_MID)
            cell.set_text_props(color=TEXT_PRIMARY, weight="bold")
        else:
            cell.set_facecolor(BG_PAGE)
            cell.set_text_props(color=TEXT_PRIMARY)

    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def export_participant_demographics_table(
    output_dir: str | Path,
    interview_manager: InterviewManager | None = None,
) -> None:
    """Save participant_demographics.csv / .tex / .png (anonymised)."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    mgr = interview_manager or InterviewManager()

    csv_path = output_dir / "participant_demographics.csv"
    mgr.export_participant_table_csv(csv_path)

    headers = [
        "Pseudonym",
        "Teaching Context",
        "Years Experience",
        "Institution Type",
    ]
    rows: list[list[str]] = []
    with csv_path.open(encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        for row in reader:
            rows.append(row)

    _write_latex_tabular(
        output_dir / "participant_demographics.tex",
        headers,
        rows,
        caption="Anonymised practitioner participant demographics",
        label="tab:participant_demographics",
    )
    _render_table_png(
        output_dir / "participant_demographics.png",
        headers,
        rows,
        title="Participant Demographics",
    )


def export_sus_results(
    output_dir: str | Path,
    questionnaire_store: QuestionnaireStore | None = None,
    interview_manager: InterviewManager | None = None,
) -> None:
    """Save sus_scores.csv / .tex / sus_bar_chart.png."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    store = questionnaire_store or QuestionnaireStore()
    mgr = interview_manager or InterviewManager()
    id_to_pseudo = {p.participant_id: p.pseudonym for p in mgr.get_all()}

    by_id: dict[str, float] = {}
    for pid in {r.participant_id for r in store.get_responses("sus")}:
        score = store.compute_sus_score(pid)
        if score is not None:
            by_id[pid] = score

    pairs = sorted(
        (
            (id_to_pseudo.get(pid, pid[:8]), score)
            for pid, score in by_id.items()
        ),
        key=lambda t: t[0],
    )

    csv_path = output_dir / "sus_scores.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Pseudonym", "SUS_Score"])
        for pseudo, score in pairs:
            writer.writerow([pseudo, f"{score:.1f}"])

    _write_latex_tabular(
        output_dir / "sus_scores.tex",
        ["Pseudonym", "SUS Score"],
        [[p, f"{s:.1f}"] for p, s in pairs],
        caption="Individual System Usability Scale (SUS) scores",
        label="tab:sus_scores",
    )

    # Bar chart with mean line
    fig, ax = plt.subplots(figsize=(8, 4.5))
    fig.patch.set_facecolor(BG_PAGE)
    ax.set_facecolor(BG_PAGE)

    if pairs:
        labels = [p for p, _ in pairs]
        values = [s for _, s in pairs]
        colors = [GREYISH[i % len(GREYISH)] for i in range(len(values))]
        ax.bar(labels, values, color=colors, edgecolor=BORDER)
        mean_sus = sum(values) / len(values)
        ax.axhline(
            mean_sus,
            color=ACCENT,
            linestyle="--",
            linewidth=1.5,
            label=f"Mean = {mean_sus:.1f}",
        )
        ax.legend(frameon=False, labelcolor=TEXT_MUTED)
    else:
        ax.text(
            0.5,
            0.5,
            "No SUS responses",
            ha="center",
            va="center",
            color=TEXT_MUTED,
            transform=ax.transAxes,
        )

    ax.set_ylim(0, 100)
    ax.set_ylabel("SUS Score", color=TEXT_PRIMARY)
    ax.set_xlabel("Participant", color=TEXT_PRIMARY)
    ax.set_title("SUS Scores by Participant", color=TEXT_PRIMARY)
    ax.tick_params(colors=TEXT_MUTED)
    for spine in ax.spines.values():
        spine.set_color(BORDER)

    fig.tight_layout()
    fig.savefig(
        output_dir / "sus_bar_chart.png",
        dpi=150,
        facecolor=fig.get_facecolor(),
        bbox_inches="tight",
    )
    plt.close(fig)


def export_thematic_map_figure(
    output_dir: str | Path,
    qualitative_coder: QualitativeCoder | None = None,
) -> None:
    """Render hierarchical thematic map as thematic_map.png (greyish palette)."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    coder = qualitative_coder or QualitativeCoder()

    with tempfile.TemporaryDirectory() as tmp:
        map_path = Path(tmp) / "thematic_map.json"
        coder.export_thematic_map_json(map_path)
        data = json.loads(map_path.read_text(encoding="utf-8"))

    themes = data.get("themes", [])

    fig, ax = plt.subplots(figsize=(12, max(6, 1.2 * max(len(themes), 1) + 2)))
    fig.patch.set_facecolor(BG_PAGE)
    ax.set_facecolor(BG_PAGE)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("Thematic Map", color=TEXT_PRIMARY, fontsize=13, pad=10)

    if not themes:
        ax.text(
            0.5,
            0.5,
            "No themes coded",
            ha="center",
            va="center",
            color=TEXT_MUTED,
        )
        fig.tight_layout()
        fig.savefig(
            output_dir / "thematic_map.png",
            dpi=150,
            facecolor=fig.get_facecolor(),
            bbox_inches="tight",
        )
        plt.close(fig)
        return

    # Flatten layout: columns = theme | sub-theme | code
    # Collect vertical slots per column
    theme_nodes: list[tuple[str, int]] = []
    sub_nodes: list[tuple[str, str, int]] = []  # theme, sub, count
    code_nodes: list[tuple[str, str, str, int]] = []  # theme, sub, code, count

    for t in themes:
        theme_name = t["theme"]
        theme_count = 0
        for st in t.get("sub_themes", []):
            sub_name = st["sub_theme"]
            sub_count = 0
            for c in st.get("codes", []):
                cnt = int(c.get("count", 0))
                code_nodes.append((theme_name, sub_name, c["code"], cnt))
                sub_count += cnt
            sub_nodes.append((theme_name, sub_name, sub_count))
            theme_count += sub_count
        theme_nodes.append((theme_name, theme_count))

    def _ys(n: int) -> list[float]:
        if n <= 0:
            return []
        if n == 1:
            return [0.5]
        return [0.9 - i * (0.8 / (n - 1)) for i in range(n)]

    max_count = max(
        [c for _, c in theme_nodes]
        + [c for *_, c in sub_nodes]
        + [c for *_, c in code_nodes]
        + [1]
    )

    def _box(x: float, y: float, label: str, count: int, color: str, width: float = 0.22):
        size = 0.035 + 0.04 * (count / max_count)
        height = max(0.04, size)
        rect = FancyBboxPatch(
            (x - width / 2, y - height / 2),
            width,
            height,
            boxstyle="round,pad=0.01,rounding_size=0.01",
            linewidth=1.0,
            edgecolor=BORDER,
            facecolor=color,
        )
        ax.add_patch(rect)
        ax.text(
            x,
            y,
            f"{label}\n(n={count})",
            ha="center",
            va="center",
            fontsize=7,
            color=TEXT_PRIMARY,
            wrap=True,
        )

    theme_ys = _ys(len(theme_nodes))
    sub_ys = _ys(len(sub_nodes))
    code_ys = _ys(len(code_nodes))

    theme_pos = {
        name: (0.15, y) for (name, _), y in zip(theme_nodes, theme_ys)
    }
    sub_pos = {
        (th, sub): (0.5, y)
        for (th, sub, _), y in zip(sub_nodes, sub_ys)
    }
    code_pos = {
        (th, sub, code): (0.85, y)
        for (th, sub, code, _), y in zip(code_nodes, code_ys)
    }

    # Edges
    for th, sub, code, _ in code_nodes:
        x0, y0 = sub_pos[(th, sub)]
        x1, y1 = code_pos[(th, sub, code)]
        ax.plot([x0 + 0.11, x1 - 0.11], [y0, y1], color=BORDER, linewidth=0.8)
    for th, sub, _ in sub_nodes:
        x0, y0 = theme_pos[th]
        x1, y1 = sub_pos[(th, sub)]
        ax.plot([x0 + 0.11, x1 - 0.11], [y0, y1], color=BORDER, linewidth=1.0)

    for i, (name, count) in enumerate(theme_nodes):
        x, y = theme_pos[name]
        _box(x, y, name, count, GREYISH[i % len(GREYISH)])
    for i, (th, sub, count) in enumerate(sub_nodes):
        x, y = sub_pos[(th, sub)]
        _box(x, y, sub, count, GREYISH[(i + 2) % len(GREYISH)], width=0.2)
    for i, (th, sub, code, count) in enumerate(code_nodes):
        x, y = code_pos[(th, sub, code)]
        _box(x, y, code, count, GREYISH[(i + 4) % len(GREYISH)], width=0.2)

    ax.text(0.15, 0.97, "Themes", ha="center", color=TEXT_MUTED, fontsize=9)
    ax.text(0.5, 0.97, "Sub-themes", ha="center", color=TEXT_MUTED, fontsize=9)
    ax.text(0.85, 0.97, "Codes", ha="center", color=TEXT_MUTED, fontsize=9)

    fig.tight_layout()
    fig.savefig(
        output_dir / "thematic_map.png",
        dpi=150,
        facecolor=fig.get_facecolor(),
        bbox_inches="tight",
    )
    plt.close(fig)


def export_code_frequency_chart(
    output_dir: str | Path,
    qualitative_coder: QualitativeCoder | None = None,
) -> None:
    """Horizontal bar chart of code frequencies → code_frequency.png."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    coder = qualitative_coder or QualitativeCoder()
    freq = coder.code_frequency_table()

    fig, ax = plt.subplots(figsize=(8, max(3.5, 0.35 * max(len(freq), 1) + 1)))
    fig.patch.set_facecolor(BG_PAGE)
    ax.set_facecolor(BG_PAGE)

    if freq:
        labels = list(freq.keys())[::-1]
        values = list(freq.values())[::-1]
        colors = [GREYISH[i % len(GREYISH)] for i in range(len(values))]
        ax.barh(labels, values, color=colors, edgecolor=BORDER)
    else:
        ax.text(
            0.5,
            0.5,
            "No codes recorded",
            ha="center",
            va="center",
            color=TEXT_MUTED,
            transform=ax.transAxes,
        )

    ax.set_xlabel("Frequency", color=TEXT_PRIMARY)
    ax.set_title("Code Frequency", color=TEXT_PRIMARY)
    ax.tick_params(colors=TEXT_MUTED)
    for spine in ax.spines.values():
        spine.set_color(BORDER)

    fig.tight_layout()
    fig.savefig(
        output_dir / "code_frequency.png",
        dpi=150,
        facecolor=fig.get_facecolor(),
        bbox_inches="tight",
    )
    plt.close(fig)


def export_all(output_dir: str | Path) -> None:
    """Run all practitioner-evaluation export helpers into ``output_dir``."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    analyzer = FeedbackAnalyzer()
    export_participant_demographics_table(output_dir, analyzer.interviews)
    export_sus_results(output_dir, analyzer.questionnaires, analyzer.interviews)
    export_thematic_map_figure(output_dir, analyzer.coder)
    export_code_frequency_chart(output_dir, analyzer.coder)

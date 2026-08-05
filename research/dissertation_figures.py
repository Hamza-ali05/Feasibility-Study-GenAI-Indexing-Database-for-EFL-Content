"""Dissertation figure generator for the EFL IndexDB feasibility study.

Produces architecture, DFD, flowchart, sequence, and component diagrams
as PNG (300 DPI) and SVG using matplotlib only — no external diagram tools.
Uses the project greyish palette shared with EDA / metrics exports.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle
from matplotlib.lines import Line2D

# ── Project palette ─────────────────────────────────────────────────────
BG_PAGE = "#F9F8F5"
BORDER = "#D3D1C7"
GREY_MID = "#B4B2A9"
TEXT_MUTED = "#888780"
TEXT_DARK = "#5F5E5A"
TEXT_PRIMARY = "#2C2C2A"
ACCENT = "#3C3489"
ACCENT_BG = "#EEEDFE"
WHITE = "#FFFFFF"

_LAYER_BANDS = ("#EEEDFE", "#F9F8F5", "#E8E6DE", "#EEEDFE", "#F0EFEA")
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_OUT = _PROJECT_ROOT / "research" / "reports" / "figures"


# ── Drawing helpers ─────────────────────────────────────────────────────


def _setup_ax(figsize: tuple[float, float]) -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=figsize, facecolor=BG_PAGE)
    ax.set_facecolor(BG_PAGE)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def _save(fig: plt.Figure, output_dir: Path, stem: str) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    png = output_dir / f"{stem}.png"
    svg = output_dir / f"{stem}.svg"
    fig.savefig(png, dpi=300, bbox_inches="tight", facecolor=BG_PAGE, edgecolor="none")
    fig.savefig(svg, bbox_inches="tight", facecolor=BG_PAGE, edgecolor="none")
    plt.close(fig)
    return [str(png), str(svg)]


def _rounded(
    ax: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    facecolor: str = WHITE,
    edgecolor: str = BORDER,
    linewidth: float = 1.2,
    radius: float = 0.02,
    zorder: int = 3,
) -> FancyBboxPatch:
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.004,rounding_size={radius}",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=linewidth,
        zorder=zorder,
    )
    ax.add_patch(patch)
    return patch


def _text(
    ax: plt.Axes,
    x: float,
    y: float,
    s: str,
    *,
    size: float = 8,
    weight: str = "normal",
    color: str = TEXT_PRIMARY,
    ha: str = "center",
    va: str = "center",
    wrap: bool = False,
    zorder: int = 5,
) -> None:
    ax.text(
        x,
        y,
        s,
        fontsize=size,
        fontweight=weight,
        color=color,
        ha=ha,
        va=va,
        zorder=zorder,
        wrap=wrap,
        family="sans-serif",
    )


def _arrow(
    ax: plt.Axes,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    color: str = ACCENT,
    style: str = "-|>",
    lw: float = 1.4,
    connectionstyle: str = "arc3,rad=0",
    label: str | None = None,
    label_offset: tuple[float, float] = (0.0, 0.02),
    label_size: float = 6.5,
) -> None:
    arr = FancyArrowPatch(
        (x1, y1),
        (x2, y2),
        arrowstyle=style,
        mutation_scale=12,
        linewidth=lw,
        color=color,
        connectionstyle=connectionstyle,
        zorder=4,
    )
    ax.add_patch(arr)
    if label:
        mx = (x1 + x2) / 2 + label_offset[0]
        my = (y1 + y2) / 2 + label_offset[1]
        _text(ax, mx, my, label, size=label_size, color=TEXT_MUTED)


def _diamond(
    ax: plt.Axes,
    cx: float,
    cy: float,
    w: float,
    h: float,
    *,
    facecolor: str = ACCENT_BG,
    edgecolor: str = ACCENT,
) -> None:
    pts = [
        (cx, cy + h / 2),
        (cx + w / 2, cy),
        (cx, cy - h / 2),
        (cx - w / 2, cy),
    ]
    ax.add_patch(
        Polygon(pts, closed=True, facecolor=facecolor, edgecolor=edgecolor, linewidth=1.2, zorder=3)
    )


def _dfd_process(ax: plt.Axes, cx: float, cy: float, r: float, label: str) -> None:
    ax.add_patch(
        Circle(
            (cx, cy),
            r,
            facecolor=ACCENT_BG,
            edgecolor=ACCENT,
            linewidth=1.4,
            zorder=3,
        )
    )
    # Multi-line label inside circle
    lines = label.split("\n")
    step = 0.028
    start = cy + step * (len(lines) - 1) / 2
    for i, line in enumerate(lines):
        _text(ax, cx, start - i * step, line, size=6.5, weight="normal", color=ACCENT)


def _dfd_store(ax: plt.Axes, x: float, y: float, w: float, h: float, label: str) -> None:
    # Parallel lines (open sides) for DFD data store
    ax.add_line(Line2D([x, x + w], [y + h, y + h], color=ACCENT, lw=1.6, zorder=3))
    ax.add_line(Line2D([x, x + w], [y, y], color=ACCENT, lw=1.6, zorder=3))
    ax.add_patch(
        Rectangle((x, y), w, h, facecolor=WHITE, edgecolor="none", zorder=2)
    )
    _text(ax, x + w / 2, y + h / 2, label, size=7, weight="normal", color=TEXT_PRIMARY)


def _dfd_entity(ax: plt.Axes, x: float, y: float, w: float, h: float, label: str) -> None:
    ax.add_patch(
        Rectangle(
            (x, y),
            w,
            h,
            facecolor=WHITE,
            edgecolor=TEXT_DARK,
            linewidth=1.4,
            zorder=3,
        )
    )
    _text(ax, x + w / 2, y + h / 2, label, size=7, weight="bold", color=TEXT_PRIMARY)


def _title(ax: plt.Axes, text: str, y: float = 0.97) -> None:
    _text(ax, 0.5, y, text, size=12, weight="bold", color=TEXT_PRIMARY)


class DissertationFigureGenerator:
    """Generate high-quality dissertation diagrams (PNG + SVG)."""

    def export_system_architecture_diagram(self, output_dir: str | Path) -> str:
        out = Path(output_dir)
        fig, ax = _setup_ax((11, 9))
        _title(ax, "System Architecture — EFL IndexDB")

        layers = [
            {
                "name": "Presentation Layer",
                "y": 0.78,
                "h": 0.14,
                "color": _LAYER_BANDS[0],
                "comps": [("Material Dashboard\nReact Frontend", 0.35, 0.42)],
            },
            {
                "name": "API Layer",
                "y": 0.60,
                "h": 0.14,
                "color": _LAYER_BANDS[1],
                "comps": [("FastAPI\n(REST + WebSocket)", 0.35, 0.42)],
            },
            {
                "name": "Storage Layer",
                "y": 0.40,
                "h": 0.16,
                "color": _LAYER_BANDS[2],
                "comps": [
                    ("FAISS\nVector Index", 0.12, 0.22),
                    ("SQLite\nMetadata", 0.39, 0.22),
                    ("SQLite\nAnalytics", 0.66, 0.22),
                ],
            },
            {
                "name": "Data Layer",
                "y": 0.20,
                "h": 0.16,
                "color": _LAYER_BANDS[3],
                "comps": [
                    ("Raw EFL\nDatasets", 0.18, 0.28),
                    ("14-Stage\nPipeline", 0.54, 0.28),
                ],
            },
        ]

        for layer in layers:
            band = Rectangle(
                (0.04, layer["y"]),
                0.92,
                layer["h"],
                facecolor=layer["color"],
                edgecolor=BORDER,
                linewidth=1.0,
                zorder=1,
            )
            ax.add_patch(band)
            _text(
                ax,
                0.06,
                layer["y"] + layer["h"] - 0.025,
                layer["name"],
                size=8,
                weight="bold",
                color=ACCENT,
                ha="left",
                va="top",
            )
            for label, cx, cw in layer["comps"]:
                cy = layer["y"] + 0.025
                ch = layer["h"] - 0.045
                _rounded(
                    ax,
                    cx,
                    cy,
                    cw,
                    ch,
                    facecolor=WHITE,
                    edgecolor=ACCENT,
                    linewidth=1.3,
                )
                _text(ax, cx + cw / 2, cy + ch / 2, label, size=7.5, weight="normal")

        # External Anthropic
        _rounded(
            ax,
            0.72,
            0.62,
            0.22,
            0.10,
            facecolor=ACCENT_BG,
            edgecolor=ACCENT,
            linewidth=1.3,
        )
        _text(ax, 0.83, 0.67, "Anthropic API\n(RAG + Analyzer)", size=7, weight="normal", color=ACCENT)

        # Vertical flow arrows between layers
        _arrow(ax, 0.50, 0.78, 0.50, 0.74, color=ACCENT)
        _arrow(ax, 0.50, 0.60, 0.50, 0.56, color=ACCENT)
        _arrow(ax, 0.50, 0.40, 0.50, 0.36, color=ACCENT)
        _arrow(ax, 0.32, 0.28, 0.54, 0.28, color=ACCENT, label="ingest")
        _arrow(ax, 0.68, 0.67, 0.77, 0.67, color=ACCENT, style="<->", label="LLM")

        # Footer note
        _text(
            ax,
            0.5,
            0.08,
            "Data flows upward through Storage → API → Presentation; Anthropic is an external dependency.",
            size=7,
            color=TEXT_MUTED,
        )

        paths = _save(fig, out, "system_architecture")
        return paths[0]

    def export_data_flow_diagram(self, output_dir: str | Path) -> str:
        out = Path(output_dir)
        fig, ax = _setup_ax((12, 9))
        _title(ax, "Data Flow Diagram (Level 0) — EFL IndexDB")

        # External entities
        _dfd_entity(ax, 0.02, 0.78, 0.16, 0.10, "EFL\nPractitioner")
        _dfd_entity(ax, 0.02, 0.42, 0.16, 0.10, "Admin")
        _dfd_entity(ax, 0.02, 0.10, 0.16, 0.10, "EFL\nDatasets")

        # Processes (circles)
        processes = [
            (0.38, 0.82, "Content\nIngestion"),
            (0.62, 0.82, "Semantic\nIndexing"),
            (0.38, 0.52, "Search &\nRetrieval"),
            (0.62, 0.52, "CEFR\nClassification"),
            (0.50, 0.22, "RAG Question\nAnswering"),
        ]
        for cx, cy, lab in processes:
            _dfd_process(ax, cx, cy, 0.075, lab)

        # Data stores
        _dfd_store(ax, 0.80, 0.78, 0.16, 0.08, "D1 Vector DB")
        _dfd_store(ax, 0.80, 0.58, 0.16, 0.08, "D2 Metadata DB")
        _dfd_store(ax, 0.80, 0.38, 0.16, 0.08, "D3 Analytics DB")

        # Flows
        _arrow(ax, 0.18, 0.15, 0.32, 0.76, label="raw files", label_offset=(0.02, 0.0))
        _arrow(ax, 0.455, 0.82, 0.545, 0.82, label="cleaned records")
        _arrow(ax, 0.695, 0.82, 0.80, 0.82, label="embeddings")
        _arrow(ax, 0.695, 0.80, 0.80, 0.62, label="metadata", connectionstyle="arc3,rad=-0.2")
        _arrow(ax, 0.18, 0.83, 0.305, 0.83, label="queries")
        _arrow(ax, 0.38, 0.745, 0.38, 0.595, label="")
        _arrow(ax, 0.455, 0.52, 0.545, 0.52, label="")
        _arrow(ax, 0.80, 0.62, 0.455, 0.55, label="filter meta", connectionstyle="arc3,rad=0.25")
        _arrow(ax, 0.80, 0.78, 0.455, 0.56, label="vectors", connectionstyle="arc3,rad=0.35")
        _arrow(ax, 0.18, 0.47, 0.305, 0.52, label="manage")
        _arrow(ax, 0.38, 0.445, 0.45, 0.29, label="context")
        _arrow(ax, 0.50, 0.145, 0.18, 0.78, label="answers", connectionstyle="arc3,rad=0.35")
        _arrow(ax, 0.575, 0.22, 0.80, 0.42, label="events", connectionstyle="arc3,rad=-0.15")
        _arrow(ax, 0.695, 0.52, 0.80, 0.58, label="labels")

        _text(
            ax,
            0.5,
            0.03,
            "DFD notation: rectangles = external entities · circles = processes · parallel lines = data stores",
            size=6.5,
            color=TEXT_MUTED,
        )

        paths = _save(fig, out, "data_flow_diagram")
        return paths[0]

    def export_pipeline_flowchart(self, output_dir: str | Path) -> str:
        out = Path(output_dir)
        fig, ax = _setup_ax((10, 16))
        _title(ax, "14-Stage Pipeline Flowchart", y=0.985)

        stages = [
            (1, "Discover", "data/raw/", "01_discover_manifest.json"),
            (2, "Load", "manifest", "02_loaded_tables.json"),
            (3, "Integrate", "tables", "03_integrated.parquet"),
            (4, "EDA", "integrated", "04_eda_report.json"),
            (5, "Clean", "EDA flags", "05_cleaned.parquet"),
            (6, "Split", "cleaned", "06_split_report.json"),
            (7, "Preprocess", "splits", "07_preprocessed/"),
            (8, "Balance", "train split", "08_balanced/"),
            (9, "Train", "balanced", "09_models/"),
            (10, "Evaluate", "models", "10_eval_report.json"),
            (11, "Explain Global", "model", "11_global_shap/"),
            (12, "Explain Local", "samples", "12_local_lime/"),
            (13, "Explain Quality", "explanations", "13_quality.json"),
            (14, "Predict", "query", "14_predictions.json"),
        ]

        # Layout: two columns for readability, but sequential flow via arrows
        # Actually single vertical column is clearer for flowcharts
        top = 0.94
        box_h = 0.048
        gap = 0.012
        box_w = 0.42
        box_x = 0.29

        centers: list[tuple[float, float]] = []
        for i, (num, name, inp, outp) in enumerate(stages):
            y = top - i * (box_h + gap) - box_h
            cy = y + box_h / 2
            centers.append((box_x + box_w / 2, cy))

            _rounded(
                ax,
                box_x,
                y,
                box_w,
                box_h,
                facecolor=WHITE if num != 8 else ACCENT_BG,
                edgecolor=ACCENT,
                linewidth=1.3,
                radius=0.015,
            )
            _text(
                ax,
                box_x + box_w / 2,
                cy,
                f"{num:02d}  {name}",
                size=8,
                weight="bold",
                color=TEXT_PRIMARY,
            )

            # Side annotations
            _text(ax, box_x - 0.02, cy, inp, size=5.5, color=TEXT_MUTED, ha="right")
            _text(ax, box_x + box_w + 0.02, cy, outp, size=5.5, color=TEXT_MUTED, ha="left")

            if i > 0:
                prev = centers[i - 1]
                _arrow(ax, prev[0], prev[1] - box_h / 2 - 0.002, centers[i][0], cy + box_h / 2 + 0.002)

        # Decision diamond after Balance (stage 8) — annotate beside stage 8
        bal_i = 7  # 0-based index for Balance
        bx, by = centers[bal_i]
        _diamond(ax, 0.12, by, 0.14, 0.055)
        _text(ax, 0.12, by, "Imbalance\nratio > 3.0?", size=5.5, color=ACCENT)
        _arrow(ax, 0.19, by, box_x - 0.01, by, color=ACCENT, label="yes→resample", label_offset=(0, 0.018))
        _text(ax, 0.12, by - 0.04, "no → pass-through", size=5, color=TEXT_MUTED)

        _text(
            ax,
            0.5,
            0.015,
            "Left: key inputs · Center: stages · Right: primary artefacts · Diamond: Balance gate",
            size=6.5,
            color=TEXT_MUTED,
        )

        paths = _save(fig, out, "pipeline_flowchart")
        return paths[0]

    def export_embedding_pipeline_diagram(self, output_dir: str | Path) -> str:
        out = Path(output_dir)
        fig, ax = _setup_ax((14, 4.5))
        _title(ax, "Embedding Pipeline — Text → FAISS Vector", y=0.92)

        steps = [
            ("Raw Text", "variable\nlength", WHITE),
            ("SBERT\nTokenizer", "token ids", ACCENT_BG),
            ("Transformer\nEncoder", "hidden\nstates", ACCENT_BG),
            ("Mean\nPooling", "384-d", WHITE),
            ("L2\nNormalization", "unit\nvector", WHITE),
            ("384-dim\nVector", "ℝ³⁸⁴", ACCENT_BG),
            ("FAISS\nIndexFlatIP", "inner\nproduct", ACCENT_BG),
        ]

        n = len(steps)
        total_w = 0.92
        gap = 0.018
        box_w = (total_w - gap * (n - 1)) / n
        x0 = 0.04
        y = 0.32
        h = 0.38

        for i, (title, dim, fc) in enumerate(steps):
            x = x0 + i * (box_w + gap)
            _rounded(ax, x, y, box_w, h, facecolor=fc, edgecolor=ACCENT, linewidth=1.4)
            _text(ax, x + box_w / 2, y + h * 0.62, title, size=8, weight="bold")
            _text(ax, x + box_w / 2, y + h * 0.28, dim, size=6.5, color=TEXT_MUTED)
            if i < n - 1:
                _arrow(
                    ax,
                    x + box_w + 0.002,
                    y + h / 2,
                    x + box_w + gap - 0.002,
                    y + h / 2,
                    color=ACCENT,
                )

        _text(
            ax,
            0.5,
            0.12,
            "Model: sentence-transformers/all-MiniLM-L6-v2 · Similarity: cosine via L2-normalised IP",
            size=7,
            color=TEXT_MUTED,
        )

        paths = _save(fig, out, "embedding_pipeline")
        return paths[0]

    def _sequence_diagram(
        self,
        output_dir: Path,
        stem: str,
        title: str,
        participants: Sequence[str],
        messages: Sequence[tuple[int, int, str, str]],
    ) -> str:
        """Render a UML-style sequence diagram.

        messages: (from_idx, to_idx, label, kind) where kind in {"sync","return","async"}.
        """
        n = len(participants)
        width = max(10.0, 1.6 * n + 2)
        # Height scales with message count
        height = max(6.0, 0.55 * len(messages) + 2.5)
        fig, ax = _setup_ax((width, height))
        _title(ax, title, y=0.97)

        # Participant boxes along top
        margin_x = 0.06
        usable = 0.88
        slot = usable / n
        box_w = min(0.14, slot * 0.85)
        centers_x = [margin_x + slot * i + slot / 2 for i in range(n)]
        head_y = 0.88
        head_h = 0.06

        for i, name in enumerate(participants):
            cx = centers_x[i]
            _rounded(
                ax,
                cx - box_w / 2,
                head_y,
                box_w,
                head_h,
                facecolor=ACCENT_BG,
                edgecolor=ACCENT,
                linewidth=1.2,
            )
            _text(ax, cx, head_y + head_h / 2, name, size=6.5, weight="bold", color=ACCENT)
            # Lifeline
            ax.add_line(
                Line2D(
                    [cx, cx],
                    [head_y, 0.08],
                    color=BORDER,
                    lw=1.0,
                    linestyle="--",
                    zorder=1,
                )
            )

        # Messages
        top_msg = 0.82
        bottom_msg = 0.12
        span = top_msg - bottom_msg
        step = span / max(len(messages), 1)

        for mi, (src, dst, label, kind) in enumerate(messages):
            y = top_msg - mi * step - step * 0.35
            x1, x2 = centers_x[src], centers_x[dst]
            style = "-|>" if kind != "return" else "->"
            color = ACCENT if kind != "return" else TEXT_MUTED
            ls_style = "solid" if kind != "return" else "dashed"
            arr = FancyArrowPatch(
                (x1, y),
                (x2, y),
                arrowstyle=style,
                mutation_scale=11,
                linewidth=1.3,
                color=color,
                linestyle=ls_style,
                zorder=4,
            )
            ax.add_patch(arr)
            # Activation box hint on destination
            act_h = step * 0.45
            ax.add_patch(
                Rectangle(
                    (x2 - 0.008, y - act_h * 0.3),
                    0.016,
                    act_h,
                    facecolor=ACCENT_BG,
                    edgecolor=ACCENT,
                    linewidth=0.6,
                    zorder=2,
                )
            )
            mid = (x1 + x2) / 2
            _text(ax, mid, y + 0.018, label, size=6, color=TEXT_PRIMARY)

        paths = _save(fig, output_dir, stem)
        return paths[0]

    def export_search_sequence_diagram(self, output_dir: str | Path) -> str:
        participants = [
            "User",
            "Frontend",
            "FastAPI",
            "SBERT\nEmbedder",
            "FAISS\nIndex",
            "Metadata\nStore",
        ]
        messages = [
            (0, 1, "Enter query", "sync"),
            (1, 2, "POST /api/search", "sync"),
            (2, 3, "Embed query", "sync"),
            (3, 2, "query vector (384-d)", "return"),
            (2, 4, "kNN search", "sync"),
            (4, 2, "top-k ids + scores", "return"),
            (2, 5, "Filter by CEFR/skill/topic", "sync"),
            (5, 2, "enriched metadata", "return"),
            (2, 1, "Return ranked results", "return"),
            (1, 0, "Display results", "return"),
        ]
        return self._sequence_diagram(
            Path(output_dir),
            "search_sequence",
            "Sequence Diagram — Semantic Search",
            participants,
            messages,
        )

    def export_rag_sequence_diagram(self, output_dir: str | Path) -> str:
        participants = [
            "User",
            "Frontend",
            "FastAPI",
            "SBERT",
            "FAISS",
            "Metadata\nStore",
            "Prompt\nBuilder",
            "Anthropic\nAPI",
        ]
        messages = [
            (0, 1, "Ask question", "sync"),
            (1, 2, "POST /api/rag (stream)", "async"),
            (2, 3, "Embed question", "sync"),
            (3, 2, "vector", "return"),
            (2, 4, "Retrieve context chunks", "sync"),
            (4, 2, "top-k passages", "return"),
            (2, 5, "Load passage metadata", "sync"),
            (5, 2, "titles / CEFR / urls", "return"),
            (2, 6, "Build grounded prompt", "sync"),
            (6, 2, "messages[]", "return"),
            (2, 7, "chat.completions (stream)", "async"),
            (7, 2, "token chunks", "return"),
            (2, 1, "SSE / WebSocket tokens", "async"),
            (1, 0, "Render streaming answer", "return"),
        ]
        return self._sequence_diagram(
            Path(output_dir),
            "rag_sequence",
            "Sequence Diagram — RAG Question Answering",
            participants,
            messages,
        )

    def export_component_diagram(self, output_dir: str | Path) -> str:
        out = Path(output_dir)
        fig, ax = _setup_ax((12, 9))
        _title(ax, "Component Diagram — Software Packages")

        components = [
            # name, x, y, w, h
            ("Frontend Package\n(Material Dashboard)", 0.35, 0.82, 0.30, 0.10),
            ("API Package\n(routers, schemas)", 0.35, 0.66, 0.30, 0.10),
            ("Auth Package", 0.72, 0.66, 0.22, 0.10),
            ("Services Package\nRAG · Recommend · Analyzer\nAnalytics · Duplicate", 0.28, 0.44, 0.36, 0.14),
            ("Models Package\n(SBERT Embedder)", 0.70, 0.46, 0.24, 0.10),
            ("DB Package\nVector · Metadata · Analytics", 0.28, 0.24, 0.36, 0.12),
            ("Pipeline Package\n(14 stage modules)", 0.04, 0.44, 0.20, 0.14),
            ("Utils Package\nconfig · state · logger", 0.70, 0.24, 0.24, 0.12),
        ]

        for name, x, y, w, h in components:
            _rounded(
                ax,
                x,
                y,
                w,
                h,
                facecolor=WHITE,
                edgecolor=ACCENT,
                linewidth=1.4,
            )
            # UML component stereotype bar
            ax.add_patch(
                Rectangle(
                    (x + w - 0.035, y + h - 0.028),
                    0.022,
                    0.016,
                    facecolor=ACCENT_BG,
                    edgecolor=ACCENT,
                    linewidth=0.8,
                    zorder=4,
                )
            )
            _text(ax, x + w / 2, y + h / 2, name, size=7, weight="normal")

        # Dependencies
        deps = [
            (0.50, 0.82, 0.50, 0.76, "HTTP / WS"),
            (0.50, 0.66, 0.50, 0.58, "calls"),
            (0.65, 0.71, 0.72, 0.71, "JWT"),
            (0.46, 0.44, 0.46, 0.36, "persist"),
            (0.64, 0.51, 0.70, 0.51, "embed"),
            (0.24, 0.51, 0.28, 0.51, "writes artefacts"),
            (0.64, 0.30, 0.70, 0.30, "config"),
            (0.50, 0.66, 0.14, 0.58, "triggers", "arc3,rad=0.35"),
        ]
        for dep in deps:
            if len(dep) == 6:
                x1, y1, x2, y2, lab, cs = dep
                _arrow(ax, x1, y1, x2, y2, label=lab, connectionstyle=cs, color=TEXT_DARK)
            else:
                x1, y1, x2, y2, lab = dep
                _arrow(ax, x1, y1, x2, y2, label=lab, color=TEXT_DARK)

        _text(
            ax,
            0.5,
            0.08,
            "Arrows denote compile/runtime dependencies between packages (UML component view).",
            size=7,
            color=TEXT_MUTED,
        )

        paths = _save(fig, out, "component_diagram")
        return paths[0]

    def export_cefr_classification_flow(self, output_dir: str | Path) -> str:
        out = Path(output_dir)
        fig, ax = _setup_ax((12, 6.5))
        _title(ax, "CEFR Classification Flow — SBERT vs TF-IDF Baseline", y=0.95)

        def _row(y: float, label: str, steps: list[tuple[str, str]], accent_row: bool) -> None:
            _text(ax, 0.04, y + 0.08, label, size=8, weight="bold", color=ACCENT, ha="left")
            n = len(steps)
            x0 = 0.08
            box_w = 0.14
            gap = 0.04
            h = 0.16
            for i, (title, sub) in enumerate(steps):
                x = x0 + i * (box_w + gap)
                fc = ACCENT_BG if accent_row and i in {1, 2} else WHITE
                _rounded(ax, x, y, box_w, h, facecolor=fc, edgecolor=ACCENT, linewidth=1.2)
                _text(ax, x + box_w / 2, y + h * 0.62, title, size=7, weight="bold")
                _text(ax, x + box_w / 2, y + h * 0.28, sub, size=6, color=TEXT_MUTED)
                if i < n - 1:
                    _arrow(
                        ax,
                        x + box_w + 0.004,
                        y + h / 2,
                        x + box_w + gap - 0.004,
                        y + h / 2,
                    )

        primary = [
            ("Input Text", "resource body"),
            ("SBERT\nEmbedding", "384-d vector"),
            ("Logistic\nRegression", "softmax / OvR"),
            ("Predicted\nCEFR Level", "A1…C2"),
        ]
        baseline = [
            ("Input Text", "resource body"),
            ("TF-IDF\nVectorizer", "sparse bag"),
            ("Logistic\nRegression", "baseline"),
            ("Predicted\nCEFR Level", "A1…C2"),
        ]

        _row(0.58, "Primary (SBERT)", primary, True)
        _row(0.22, "Baseline (TF-IDF)", baseline, False)

        # Shared CEFR legend
        levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
        for i, lv in enumerate(levels):
            x = 0.20 + i * 0.10
            _rounded(ax, x, 0.06, 0.08, 0.06, facecolor=WHITE, edgecolor=BORDER)
            _text(ax, x + 0.04, 0.09, lv, size=7, weight="bold", color=TEXT_DARK)

        _text(ax, 0.12, 0.09, "Levels:", size=7, color=TEXT_MUTED, ha="right")

        paths = _save(fig, out, "cefr_classification_flow")
        return paths[0]

    def export_all(self, output_dir: str | Path = "research/reports/figures") -> list[str]:
        out = Path(output_dir)
        if not out.is_absolute():
            out = _PROJECT_ROOT / out

        exporters = [
            self.export_system_architecture_diagram,
            self.export_data_flow_diagram,
            self.export_pipeline_flowchart,
            self.export_embedding_pipeline_diagram,
            self.export_search_sequence_diagram,
            self.export_rag_sequence_diagram,
            self.export_component_diagram,
            self.export_cefr_classification_flow,
        ]

        files: list[str] = []
        for fn in exporters:
            png = fn(out)
            svg = str(Path(png).with_suffix(".svg"))
            files.extend([png, svg])
        return files


if __name__ == "__main__":
    gen = DissertationFigureGenerator()
    generated = gen.export_all()
    print(f"Generated {len(generated)} figures")
    for path in generated:
        print(path)

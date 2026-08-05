"""Shared LaTeX / PNG / CSV table helpers for dissertation exports.

Used by ``metrics_export`` (Phase 10), ``benchmark_report`` (Phase 14),
and ``research_report`` (Phase 15).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

# Default project palette (aligned with pipeline EDA / metrics export)
DEFAULT_HEADER_BG = "#EEEDFE"
DEFAULT_HEADER_TEXT = "#3C3489"
DEFAULT_CELL_BG = "#FFFFFF"
DEFAULT_BORDER = "#D3D1C7"
DEFAULT_TEXT = "#2C2C2A"
DEFAULT_PAGE_BG = "#F9F8F5"


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


def _format_cell(value, float_format: str = "%.4f") -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        try:
            return float_format % float(value)
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def dataframe_to_booktabs(
    df: pd.DataFrame,
    caption: str,
    label: str,
    output_path: str,
    highlight_best_col: str | None = None,
    float_format: str = "%.4f",
) -> None:
    """Write ``df`` as a booktabs LaTeX tabular to ``output_path``.

    When ``highlight_best_col`` is set, the highest numeric value in that
    column is wrapped in ``\\textbf{...}``.
    """
    if df is None or df.empty:
        raise ValueError("dataframe_to_booktabs requires a non-empty DataFrame")

    working = df.copy()
    headers = [str(c) for c in working.columns.tolist()]

    best_row_idx: int | None = None
    if highlight_best_col is not None:
        if highlight_best_col not in working.columns:
            raise KeyError(
                f"highlight_best_col {highlight_best_col!r} not in columns: {headers}"
            )
        series = pd.to_numeric(working[highlight_best_col], errors="coerce")
        if series.notna().any():
            best_row_idx = int(series.idxmax())

    # Column alignment: first left, rest right (numeric-friendly)
    col_spec = "l" + "r" * (len(headers) - 1) if headers else "l"

    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        rf"\caption{{{_latex_escape(caption)}}}",
        rf"\label{{{label}}}",
        rf"\begin{{tabular}}{{{col_spec}}}",
        r"\toprule",
        " & ".join(_latex_escape(h) for h in headers) + r" \\",
        r"\midrule",
    ]

    for idx, row in working.iterrows():
        cells: list[str] = []
        for col in working.columns:
            raw = row[col]
            text = _format_cell(raw, float_format)
            escaped = _latex_escape(text)
            if (
                highlight_best_col is not None
                and col == highlight_best_col
                and best_row_idx is not None
                and idx == best_row_idx
            ):
                escaped = rf"\textbf{{{escaped}}}"
            cells.append(escaped)
        lines.append(" & ".join(cells) + r" \\")

    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
            "",
        ]
    )

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def dataframe_to_png(
    df: pd.DataFrame,
    title: str,
    output_path: str,
    header_bg: str = DEFAULT_HEADER_BG,
    header_text: str = DEFAULT_HEADER_TEXT,
    cell_bg: str = DEFAULT_CELL_BG,
    border: str = DEFAULT_BORDER,
    text_color: str = DEFAULT_TEXT,
    figsize: tuple | None = None,
) -> None:
    """Render ``df`` as a PNG table image via matplotlib ``table()``."""
    if df is None or df.empty:
        raise ValueError("dataframe_to_png requires a non-empty DataFrame")

    working = df.copy()
    headers = [str(c) for c in working.columns.tolist()]
    cell_text = [
        [_format_cell(v) for v in row]
        for row in working.itertuples(index=False, name=None)
    ]

    n_rows = len(cell_text)
    n_cols = len(headers)
    if figsize is None:
        figsize = (max(6.0, 1.55 * n_cols), max(2.5, 0.42 * (n_rows + 2)))

    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor(DEFAULT_PAGE_BG)
    ax.set_facecolor(DEFAULT_PAGE_BG)
    ax.axis("off")
    ax.set_title(title, color=text_color, fontsize=12, pad=12)

    table = ax.table(
        cellText=cell_text,
        colLabels=headers,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.15, 1.45)

    for (row_i, _col_i), cell in table.get_celld().items():
        cell.set_edgecolor(border)
        if row_i == 0:
            cell.set_facecolor(header_bg)
            cell.set_text_props(color=header_text, weight="bold")
        else:
            cell.set_facecolor(cell_bg)
            cell.set_text_props(color=text_color)

    fig.tight_layout()
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def dataframe_to_all(
    df: pd.DataFrame,
    base_name: str,
    output_dir: str,
    caption: str = "",
    label: str = "",
    **kwargs,
) -> list[str]:
    """Save CSV, LaTeX (.tex), and PNG (.png) versions of ``df``.

    Extra ``kwargs`` are forwarded to ``dataframe_to_booktabs`` /
    ``dataframe_to_png`` where relevant (e.g. ``highlight_best_col``,
    ``float_format``, ``header_bg``, ``figsize``).
    """
    if df is None or df.empty:
        raise ValueError("dataframe_to_all requires a non-empty DataFrame")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / f"{base_name}.csv"
    tex_path = out_dir / f"{base_name}.tex"
    png_path = out_dir / f"{base_name}.png"

    df.to_csv(csv_path, index=False)

    booktabs_keys = {"highlight_best_col", "float_format"}
    booktabs_kwargs = {k: v for k, v in kwargs.items() if k in booktabs_keys}
    png_keys = {
        "header_bg",
        "header_text",
        "cell_bg",
        "border",
        "text_color",
        "figsize",
    }
    png_kwargs = {k: v for k, v in kwargs.items() if k in png_keys}

    tex_caption = caption or base_name.replace("_", " ").title()
    tex_label = label or f"tab:{base_name}"
    dataframe_to_booktabs(
        df,
        caption=tex_caption,
        label=tex_label,
        output_path=str(tex_path),
        **booktabs_kwargs,
    )
    dataframe_to_png(
        df,
        title=tex_caption,
        output_path=str(png_path),
        **png_kwargs,
    )

    return [
        str(csv_path.as_posix()),
        str(tex_path.as_posix()),
        str(png_path.as_posix()),
    ]

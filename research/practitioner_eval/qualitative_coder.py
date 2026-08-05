"""Thematic coding support (Braun & Clarke, 2006).

Supports the six-phase thematic analysis workflow:
  1. Familiarisation (load_transcript)
  2. Generating / refining codes (code_segment, bulk_code, merge_codes)
  3. Searching for themes (assign_theme)
  4–5. Reviewing / defining themes (theme tables, thematic map)
  6. Producing the report (generate_coding_report)
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from research.practitioner_eval.interview_manager import InterviewManager
from research.practitioner_eval.models import CodedSegment

_RESEARCH_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_STORE = _RESEARCH_ROOT / "coding" / "coded_segments.json"
_INTERVIEWS_DIR = _RESEARCH_ROOT / "interviews"
_SECOND_CODER_CANDIDATES = (
    _RESEARCH_ROOT / "coding" / "coder_b_segments.json",
    _RESEARCH_ROOT / "coding" / "coded_segments_coder_b.json",
)


def _ranges_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start <= b_end and b_start <= a_end


def _load_segment_list(path: Path) -> list[CodedSegment]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else raw.get("segments", [])
    return [CodedSegment.model_validate(item) for item in items]


def _cohen_kappa(labels_a: list[str], labels_b: list[str]) -> float:
    """Cohen's kappa for two parallel categorical label lists."""
    if len(labels_a) != len(labels_b):
        raise ValueError("Label lists must be the same length")
    n = len(labels_a)
    if n == 0:
        return 0.0

    categories = sorted(set(labels_a) | set(labels_b))
    # Confusion / co-occurrence matrix
    matrix: dict[tuple[str, str], int] = defaultdict(int)
    for a, b in zip(labels_a, labels_b):
        matrix[(a, b)] += 1

    po = sum(1 for a, b in zip(labels_a, labels_b) if a == b) / n

    # Marginal probabilities
    pa = Counter(labels_a)
    pb = Counter(labels_b)
    pe = sum((pa[c] / n) * (pb[c] / n) for c in categories)

    if pe >= 1.0:
        return 1.0 if po >= 1.0 else 0.0
    return (po - pe) / (1.0 - pe)


class QualitativeCoder:
    """Persist and analyse coded transcript segments for thematic analysis."""

    def __init__(
        self,
        store_path: Path | str | None = None,
        interview_manager: InterviewManager | None = None,
    ) -> None:
        self.store_path = Path(store_path) if store_path else _DEFAULT_STORE
        self.interview_manager = interview_manager or InterviewManager()
        self._segments: list[CodedSegment] = []
        self._load()

    def _load(self) -> None:
        self._segments.clear()
        if not self.store_path.exists():
            return
        self._segments = _load_segment_list(self.store_path)

    def _save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "segments": [s.model_dump() for s in self._segments],
        }
        self.store_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _participant_exists(self, participant_id: str) -> bool:
        return any(
            p.participant_id == participant_id
            for p in self.interview_manager.get_all()
        )

    def _transcript_path(self, participant_id: str) -> Path:
        return _INTERVIEWS_DIR / f"{participant_id}_transcript.txt"

    def load_transcript(self, participant_id: str) -> list[str]:
        """Read anonymised transcript; return lines prefixed with line numbers."""
        path = self._transcript_path(participant_id)
        if not path.exists():
            raise FileNotFoundError(
                f"Transcript not found for {participant_id}: {path}"
            )
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        return [f"{i}|{line}" for i, line in enumerate(lines, start=1)]

    def _validate_segment(self, segment: CodedSegment) -> None:
        if not self._participant_exists(segment.participant_id):
            raise KeyError(
                f"Participant not found in InterviewManager: "
                f"{segment.participant_id}"
            )
        if segment.transcript_line_start > segment.transcript_line_end:
            raise ValueError(
                "transcript_line_start must be <= transcript_line_end"
            )
        path = self._transcript_path(segment.participant_id)
        if path.exists():
            n_lines = len(path.read_text(encoding="utf-8").splitlines())
            if segment.transcript_line_start < 1 or segment.transcript_line_end > n_lines:
                raise ValueError(
                    f"Line range {segment.transcript_line_start}-"
                    f"{segment.transcript_line_end} outside transcript "
                    f"(1–{n_lines}) for {segment.participant_id}"
                )
        elif segment.transcript_line_start < 1:
            raise ValueError("transcript_line_start must be >= 1")

    def code_segment(self, segment: CodedSegment) -> CodedSegment:
        """Add one coded segment after validating participant and line range."""
        self._validate_segment(segment)
        self._segments.append(segment)
        self._save()
        return segment

    def bulk_code(self, segments: list[CodedSegment]) -> int:
        """Add multiple coded segments. Returns count added."""
        for segment in segments:
            self._validate_segment(segment)
        self._segments.extend(segments)
        self._save()
        return len(segments)

    def get_codes_by_participant(self, participant_id: str) -> list[CodedSegment]:
        return [s for s in self._segments if s.participant_id == participant_id]

    def get_codes_by_code(self, code: str) -> list[CodedSegment]:
        return [s for s in self._segments if s.code == code]

    def get_codes_by_theme(self, theme: str) -> list[CodedSegment]:
        return [s for s in self._segments if s.theme == theme]

    def list_all_codes(self) -> list[str]:
        return sorted({s.code for s in self._segments})

    def list_all_themes(self) -> list[str]:
        return sorted({s.theme for s in self._segments if s.theme})

    def assign_theme(
        self, code: str, theme: str, sub_theme: str | None = None
    ) -> int:
        """Phase 3: attach theme / sub-theme to every segment with ``code``."""
        updated = 0
        new_segments: list[CodedSegment] = []
        for s in self._segments:
            if s.code == code:
                new_segments.append(
                    s.model_copy(update={"theme": theme, "sub_theme": sub_theme})
                )
                updated += 1
            else:
                new_segments.append(s)
        self._segments = new_segments
        if updated:
            self._save()
        return updated

    def merge_codes(self, old_code: str, new_code: str) -> int:
        """Phase 2 refinement: rename ``old_code`` → ``new_code``."""
        if old_code == new_code:
            return 0
        updated = 0
        new_segments: list[CodedSegment] = []
        for s in self._segments:
            if s.code == old_code:
                new_segments.append(s.model_copy(update={"code": new_code}))
                updated += 1
            else:
                new_segments.append(s)
        self._segments = new_segments
        if updated:
            self._save()
        return updated

    def code_frequency_table(self) -> dict[str, int]:
        """Return {code: count} sorted descending by count."""
        counts = Counter(s.code for s in self._segments)
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    def theme_frequency_table(self) -> dict[str, dict[str, int]]:
        """Return {theme: {sub_theme|_total: count}}."""
        table: dict[str, dict[str, int]] = {}
        for s in self._segments:
            if not s.theme:
                continue
            bucket = table.setdefault(s.theme, {"_total": 0})
            bucket["_total"] += 1
            sub = s.sub_theme if s.sub_theme else "_none"
            bucket[sub] = bucket.get(sub, 0) + 1
        # Stable key order: theme alpha; within theme _total first then subs
        ordered: dict[str, dict[str, int]] = {}
        for theme in sorted(table):
            inner = table[theme]
            ordered_inner: dict[str, int] = {"_total": inner["_total"]}
            for key in sorted(k for k in inner if k != "_total"):
                ordered_inner[key] = inner[key]
            ordered[theme] = ordered_inner
        return ordered

    def inter_rater_check(self, coder_a_file: str, coder_b_file: str) -> dict:
        """Cohen's kappa and % agreement on overlapping coded segments."""
        segs_a = _load_segment_list(Path(coder_a_file))
        segs_b = _load_segment_list(Path(coder_b_file))

        labels_a: list[str] = []
        labels_b: list[str] = []
        used_b: set[int] = set()

        for a in segs_a:
            best_j: int | None = None
            best_overlap = 0
            for j, b in enumerate(segs_b):
                if j in used_b:
                    continue
                if a.participant_id != b.participant_id:
                    continue
                if not _ranges_overlap(
                    a.transcript_line_start,
                    a.transcript_line_end,
                    b.transcript_line_start,
                    b.transcript_line_end,
                ):
                    continue
                overlap = min(a.transcript_line_end, b.transcript_line_end) - max(
                    a.transcript_line_start, b.transcript_line_start
                ) + 1
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_j = j
            if best_j is not None:
                used_b.add(best_j)
                labels_a.append(a.code)
                labels_b.append(segs_b[best_j].code)

        n = len(labels_a)
        if n == 0:
            return {"kappa": 0.0, "pct_agreement": 0.0, "n_compared": 0}

        agreements = sum(1 for x, y in zip(labels_a, labels_b) if x == y)
        pct = (agreements / n) * 100.0
        kappa = _cohen_kappa(labels_a, labels_b)
        return {
            "kappa": round(kappa, 4),
            "pct_agreement": round(pct, 2),
            "n_compared": n,
        }

    def export_thematic_map_json(self, output_path: str | Path) -> None:
        """Hierarchical theme → sub-theme → code map for dissertation figures."""
        # theme -> sub_theme -> code -> excerpts
        hierarchy: dict[str, dict[str, dict[str, list[str]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )
        for s in self._segments:
            theme = s.theme or "Unassigned"
            sub = s.sub_theme or "Unassigned"
            hierarchy[theme][sub][s.code].append(s.text_excerpt)

        themes_out = []
        for theme in sorted(hierarchy):
            sub_themes_out = []
            for sub in sorted(hierarchy[theme]):
                codes_out = []
                for code in sorted(hierarchy[theme][sub]):
                    excerpts = hierarchy[theme][sub][code]
                    codes_out.append(
                        {
                            "code": code,
                            "count": len(excerpts),
                            "example_excerpts": excerpts[:3],
                        }
                    )
                sub_themes_out.append({"sub_theme": sub, "codes": codes_out})
            themes_out.append({"theme": theme, "sub_themes": sub_themes_out})

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"themes": themes_out}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def generate_coding_report(self, output_path: str | Path) -> None:
        """Markdown coding report for dissertation appendices / analysis chapter."""
        code_freq = self.code_frequency_table()
        theme_freq = self.theme_frequency_table()
        themes = self.list_all_themes()
        codes = self.list_all_codes()
        sub_themes = sorted(
            {s.sub_theme for s in self._segments if s.sub_theme}
        )

        lines: list[str] = [
            "# Thematic Coding Report",
            "",
            "Generated by `QualitativeCoder` following Braun and Clarke (2006).",
            "",
            "## Summary",
            "",
            f"- **Total segments coded:** {len(self._segments)}",
            f"- **Distinct codes:** {len(codes)}",
            f"- **Themes:** {len(themes)}",
            f"- **Sub-themes:** {len(sub_themes)}",
            "",
            "## Code Frequency Table",
            "",
            "| Code | Count |",
            "| --- | ---: |",
        ]
        for code, count in code_freq.items():
            lines.append(f"| {code} | {count} |")

        lines.extend(
            [
                "",
                "## Theme Frequency Table",
                "",
                "| Theme | Sub-theme | Count |",
                "| --- | --- | ---: |",
            ]
        )
        for theme, bucket in theme_freq.items():
            lines.append(f"| {theme} | _total | {bucket.get('_total', 0)} |")
            for sub, count in bucket.items():
                if sub == "_total":
                    continue
                label = "(none)" if sub == "_none" else sub
                lines.append(f"| {theme} | {label} | {count} |")

        lines.extend(["", "## Themes, Definitions, and Representative Quotes", ""])
        for theme in themes:
            theme_segs = self.get_codes_by_theme(theme)
            theme_codes = sorted({s.code for s in theme_segs})
            theme_subs = sorted({s.sub_theme for s in theme_segs if s.sub_theme})
            definition = (
                f"Theme encompassing codes: {', '.join(theme_codes)}."
                if theme_codes
                else "No codes assigned."
            )
            lines.append(f"### {theme}")
            lines.append("")
            lines.append(f"**Definition:** {definition}")
            lines.append("")
            if theme_subs:
                lines.append(
                    "**Sub-themes:** " + ", ".join(theme_subs)
                )
                lines.append("")
            for code in theme_codes:
                excerpts = [
                    s.text_excerpt
                    for s in theme_segs
                    if s.code == code
                ][:2]
                lines.append(f"#### Code: `{code}`")
                lines.append("")
                if excerpts:
                    for i, ex in enumerate(excerpts, start=1):
                        clean = ex.replace("\n", " ").strip()
                        lines.append(f"> ({i}) {clean}")
                        lines.append("")
                else:
                    lines.append("_No excerpts._")
                    lines.append("")

        # Inter-rater reliability if a second coder file is present
        second = next((p for p in _SECOND_CODER_CANDIDATES if p.exists()), None)
        lines.extend(["## Inter-Rater Reliability", ""])
        if second and self.store_path.exists():
            stats = self.inter_rater_check(str(self.store_path), str(second))
            lines.append(
                f"Compared primary store (`{self.store_path.name}`) with "
                f"`{second.name}`."
            )
            lines.append("")
            lines.append(f"- **n compared:** {stats['n_compared']}")
            lines.append(f"- **Percentage agreement:** {stats['pct_agreement']}%")
            lines.append(f"- **Cohen's κ:** {stats['kappa']}")
            lines.append("")
        else:
            lines.append(
                "No second-coder file found "
                "(expected `research/coding/coder_b_segments.json` or "
                "`coded_segments_coder_b.json`). Skipped for single-researcher MSc "
                "workflow; place a file there and re-run if the supervisor "
                "requests IRR."
            )
            lines.append("")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")

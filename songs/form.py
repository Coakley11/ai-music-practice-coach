"""Ordered section / form helpers for backing tracks and analysis."""

from __future__ import annotations

from typing import Any


def section_order(sections: dict[str, list[str]]) -> list[tuple[str, list[str]]]:
    """Iterate sections in definition order (insertion-ordered dicts, Py 3.7+)."""
    return list(sections.items())


def chord_blocks_for_backing(
    sections: dict[str, list[str]],
    *,
    only_section: str | None = None,
) -> list[str]:
    """Flatten chords in section order for the synthesizer (one block = one bar)."""
    pairs = section_order(sections)
    if only_section:
        pairs = [(n, ch) for n, ch in pairs if n == only_section]
    out: list[str] = []
    for _, chs in pairs:
        out.extend(chs)
    return out


def form_timeline_rows(sections: dict[str, list[str]]) -> list[dict[str, Any]]:
    """Measure index table for UI (1-based bar numbers, one chord = one bar)."""
    rows: list[dict[str, Any]] = []
    m0 = 1
    for name, chs in section_order(sections):
        if not chs:
            continue
        m1 = m0 + len(chs) - 1
        rows.append(
            {
                "section": name,
                "start_bar": m0,
                "end_bar": m1,
                "bars": len(chs),
            }
        )
        m0 = m1 + 1
    return rows


def section_name_for_bar(sections: dict[str, list[str]], bar_1based: int) -> str | None:
    """Which section contains this bar (1-based), if any."""
    if bar_1based < 1:
        return None
    for name, chs in section_order(sections):
        n = len(chs)
        if n == 0:
            continue
        if bar_1based <= n:
            return name
        bar_1based -= n
    return None

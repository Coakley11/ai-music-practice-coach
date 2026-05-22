"""Reusable lead-sheet formatting helpers (verified core reference songs)."""

from __future__ import annotations

import html
import re
from typing import Any

try:
    from song_catalog.verified_core_refs import (
        VERIFIED_CORE_REFERENCE_KEYS,
        is_verified_core_reference,
        lyric_cues_for_reference,
        reference_for,
    )
except ImportError:
    VERIFIED_CORE_REFERENCE_KEYS = frozenset()

    def is_verified_core_reference(title: str, artist: str) -> bool:
        return False

    def lyric_cues_for_reference(title: str, artist: str) -> dict[str, list[str]]:
        return {}

    def reference_for(title: str, artist: str) -> dict[str, Any] | None:
        return None

DEFAULT_BARS_PER_ROW = 4
MOBILE_BARS_PER_ROW = 2
VERIFIED_BARS_PER_ROW = 4
VERIFIED_MOBILE_BARS_PER_ROW = 2


def section_header_html(title: str, *, subtitle: str = "") -> str:
    sub = f'<p class="sheet-section-sub">{html.escape(subtitle)}</p>' if subtitle else ""
    return (
        f'<div class="sheet-section-head">'
        f'<h3 class="sheet-section-title">{html.escape(title)}</h3>{sub}</div>'
    )


def chord_tag_html(chord: str, *, bar_num: int | None = None, is_current: bool = False) -> str:
    cls = "chord-tag current" if is_current else "chord-tag"
    bar = f'<span class="chord-bar-num">Bar {bar_num}</span>' if bar_num else ""
    return (
        f'<span class="{cls}">{bar}'
        f'<span class="chord-tag-symbol">{html.escape(str(chord))}</span></span>'
    )


def bars_per_row_for_song(
    song_data: dict[str, Any] | None,
    *,
    mobile: bool = False,
) -> int:
    if song_data and is_verified_core_reference(
        song_data.get("title", ""),
        song_data.get("artist", ""),
    ):
        return VERIFIED_MOBILE_BARS_PER_ROW if mobile else VERIFIED_BARS_PER_ROW
    return MOBILE_BARS_PER_ROW if mobile else DEFAULT_BARS_PER_ROW


def merge_lyric_cues_for_song(
    song_data: dict[str, Any],
    catalog_cues: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    """Prefer verified reference lyric lines when this song is a core reference."""
    title = song_data.get("title", "")
    artist = song_data.get("artist", "")
    ref_cues = lyric_cues_for_reference(title, artist)
    merged: dict[str, list[str]] = dict(catalog_cues or song_data.get("lyric_cues") or {})
    for section, lines in ref_cues.items():
        if lines:
            merged[section] = lines
    return merged


def lead_sheet_body_class(song_data: dict[str, Any] | None) -> str:
    if song_data and is_verified_core_reference(
        song_data.get("title", ""),
        song_data.get("artist", ""),
    ):
        return "lead-sheet verified-core-sheet"
    return "lead-sheet"


def section_lyric_lines_for_grid(
    section_name: str,
    chord_count: int,
    *,
    lyric_cues: dict[str, list[str]] | None = None,
    section_lyrics: dict[str, str] | None = None,
    bars_per_row: int = 4,
) -> list[str]:
    """Lyric phrases aligned to chord rows (verified refs supply multi-line cues)."""
    user_text = (section_lyrics or {}).get(section_name, "")
    lines = [ln.strip() for ln in str(user_text).splitlines() if ln.strip()]
    if not lines:
        raw = (lyric_cues or {}).get(section_name, [])
        if isinstance(raw, list):
            lines = [str(x).strip() for x in raw if str(x).strip()]
        elif raw:
            lines = [str(raw).strip()]
    if not lines:
        return []
    rows_needed = max(1, int((max(1, chord_count) + bars_per_row - 1) / bars_per_row))
    if len(lines) >= rows_needed:
        return lines[:rows_needed]
    out: list[str] = []
    for i in range(rows_needed):
        out.append(lines[min(i, len(lines) - 1)])
    return out


def chord_display_cell(chord: str, previous: str | None) -> str:
    """Repeat symbol for unchanged harmony."""
    return "%" if previous and chord == previous else str(chord)


def wrap_width_for_chord(chord: str) -> int:
    """Min cell width hint from chord symbol length (slash chords need room)."""
    base = len(str(chord))
    if "/" in str(chord):
        base += 2
    return max(4, min(10, base + 2))


def has_lyric_chord_sheet(song_data: dict[str, Any] | None) -> bool:
    if not song_data:
        return False
    ext = song_data.get("extensions") or {}
    if ext.get("lyric_chord_chart"):
        return True
    try:
        from song_catalog.lyric_chord_charts import has_lyric_chord_chart

        return has_lyric_chord_chart(
            song_data.get("title", ""),
            song_data.get("artist", ""),
        )
    except ImportError:
        return False


def lyric_chord_chart_sections(song_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolved lyric/chord sections for rendering (catalog or extensions)."""
    ext = song_data.get("extensions") or {}
    custom = ext.get("lyric_chord_chart")
    if custom:
        return list(custom)
    try:
        from song_catalog.lyric_chord_charts import lyric_chord_chart_for_song

        row = lyric_chord_chart_for_song(
            song_data.get("title", ""),
            song_data.get("artist", ""),
        )
        if row:
            return list(row.get("chart") or [])
    except ImportError:
        pass
    return []

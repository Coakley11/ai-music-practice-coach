"""Per-song lyric/cue section layout (dynamic from chart structure, user-customizable)."""

from __future__ import annotations

from typing import Any

STANDARD_SECTION_NAMES: tuple[str, ...] = (
    "Intro",
    "Verse",
    "Verse 2",
    "Pre-Chorus",
    "Chorus",
    "Bridge",
    "Interlude",
    "Solo",
    "Outro",
)


def lyrics_section_layout_key(song_slug: str) -> str:
    return f"lyrics_section_layout::{song_slug}"


def _section_sort_rank(name: str) -> tuple[int, str]:
    low = name.lower()
    if "intro" in low:
        return (0, name)
    if "verse" in low:
        return (1, name)
    if "pre" in low and "chorus" in low:
        return (2, name)
    if "chorus" in low:
        return (3, name)
    if "bridge" in low:
        return (4, name)
    if "interlude" in low:
        return (5, name)
    if "solo" in low:
        return (6, name)
    if "outro" in low:
        return (7, name)
    return (8, name)


def sort_section_names(section_names: list[str]) -> list[str]:
    names = [str(n).strip() for n in section_names if str(n).strip()]
    return sorted(names, key=_section_sort_rank)


def chart_section_names(
    song_data: dict[str, Any],
    sections: dict[str, list[str]],
) -> list[str]:
    """Section names from the active chart (respects ``section_order`` when set)."""
    if not sections:
        return []
    explicit = song_data.get("section_order")
    if isinstance(explicit, list) and explicit:
        ordered = [str(s) for s in explicit if str(s) in sections]
        for name in sections:
            if name not in ordered:
                ordered.append(name)
        return ordered
    return sort_section_names(list(sections.keys()))


def default_lyrics_section_layout(
    song_data: dict[str, Any],
    sections: dict[str, list[str]],
) -> list[str]:
    """Only sections that exist on this song's chart — no empty Bridge/Outro template."""
    return chart_section_names(song_data, sections)


def resolve_lyrics_editor_sections(
    session_state: dict,
    song_slug: str,
    song_data: dict[str, Any],
    sections: dict[str, list[str]],
) -> list[str]:
    """Editable section list for Lyrics & Cues (persisted per song in session)."""
    layout_key = lyrics_section_layout_key(song_slug)
    default = default_lyrics_section_layout(song_data, sections)
    layout = session_state.get(layout_key)
    if not isinstance(layout, list) or not layout:
        session_state[layout_key] = list(default)
        return list(default)
    cleaned = [str(s).strip() for s in layout if str(s).strip()]
    if not cleaned:
        session_state[layout_key] = list(default)
        return list(default)
    return cleaned


def reset_lyrics_section_layout(
    session_state: dict,
    song_slug: str,
    song_data: dict[str, Any],
    sections: dict[str, list[str]],
) -> list[str]:
    layout = default_lyrics_section_layout(song_data, sections)
    session_state[lyrics_section_layout_key(song_slug)] = list(layout)
    return layout


def add_lyrics_section(
    session_state: dict,
    song_slug: str,
    section_name: str,
) -> list[str]:
    layout_key = lyrics_section_layout_key(song_slug)
    layout = list(session_state.get(layout_key) or [])
    name = str(section_name).strip()
    if name and name not in layout:
        layout.append(name)
    session_state[layout_key] = layout
    return layout


def remove_lyrics_section(
    session_state: dict,
    song_slug: str,
    section_name: str,
) -> list[str]:
    layout_key = lyrics_section_layout_key(song_slug)
    layout = [s for s in (session_state.get(layout_key) or []) if s != section_name]
    session_state[layout_key] = layout
    return layout


def move_lyrics_section(
    session_state: dict,
    song_slug: str,
    section_name: str,
    direction: int,
) -> list[str]:
    layout_key = lyrics_section_layout_key(song_slug)
    layout = list(session_state.get(layout_key) or [])
    if section_name not in layout:
        return layout
    idx = layout.index(section_name)
    new_idx = idx + direction
    if new_idx < 0 or new_idx >= len(layout):
        return layout
    layout[idx], layout[new_idx] = layout[new_idx], layout[idx]
    session_state[layout_key] = layout
    return layout


def rename_lyrics_section(
    session_state: dict,
    song_slug: str,
    old_name: str,
    new_name: str,
    section_lyrics: dict[str, str],
) -> tuple[list[str], dict[str, str]]:
    new_name = str(new_name).strip()
    if not new_name or old_name == new_name:
        layout = list(session_state.get(lyrics_section_layout_key(song_slug)) or [])
        return layout, section_lyrics
    layout_key = lyrics_section_layout_key(song_slug)
    layout = list(session_state.get(layout_key) or [])
    if old_name in layout:
        layout[layout.index(old_name)] = new_name
    session_state[layout_key] = layout
    if old_name in section_lyrics:
        section_lyrics[new_name] = section_lyrics.pop(old_name)
    return layout, section_lyrics


def optional_sections_to_add(layout: list[str]) -> list[str]:
    return [s for s in STANDARD_SECTION_NAMES if s not in layout]

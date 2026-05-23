"""Per-song lyric/cue section layout (dynamic from chart structure, user-customizable)."""

from __future__ import annotations

import re
from typing import Any

_BRACKET_HEADER_RE = re.compile(r"^\[(.+?)\]\s*(.*)$")

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


def _section_sort_rank(name: str) -> tuple[int, int, str]:
    low = name.lower()
    num = _section_number(name) or 0
    if "intro" in low:
        return (0, num, name)
    if "verse" in low:
        return (1, num, name)
    if "pre" in low and "chorus" in low:
        return (2, num, name)
    if "chorus" in low:
        return (3, num, name)
    if "bridge" in low:
        return (4, num, name)
    if "interlude" in low:
        return (5, num, name)
    if "solo" in low:
        return (6, num, name)
    if "outro" in low:
        return (7, num, name)
    return (8, num, name)


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
    chart_keys = set(sections.keys())
    layout = session_state.get(layout_key)
    if not isinstance(layout, list) or not layout:
        session_state[layout_key] = list(default)
        return list(default)
    cleaned = [str(s).strip() for s in layout if str(s).strip()]
    if not cleaned:
        session_state[layout_key] = list(default)
        return list(default)
    cleaned_set = set(cleaned)
    if cleaned_set != set(default) and (
        cleaned_set - chart_keys or set(default) - cleaned_set
    ):
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


def lyrics_paste_placeholder(section_names: list[str]) -> str:
    """Example paste format using [Section] headers for the active song."""
    names = [str(n).strip() for n in section_names if str(n).strip()]
    if not names:
        return "[Verse]\nyour lyrics or cues"
    blocks: list[str] = []
    for name in names:
        low = name.lower()
        if "intro" in low:
            hint = "your intro lyrics or cues"
        elif "outro" in low:
            hint = "your outro lyrics or cues"
        elif "chorus" in low:
            hint = f"your {name.lower()} lyrics or cues"
        elif "verse" in low:
            hint = f"your {name.lower()} lyrics or cues"
        elif "bridge" in low:
            hint = f"your {name.lower()} lyrics or cues"
        else:
            hint = f"your {name.lower()} lyrics or cues"
        blocks.append(f"[{name}]\n{hint}")
    return "\n\n".join(blocks)


def _section_base_name(section_name: str) -> str:
    return section_name.split("(", 1)[0].split("/", 1)[0].strip().lower()


def _section_number(name: str) -> int | None:
    match = re.search(r"\d+", str(name))
    return int(match.group()) if match else None


def _section_match_score(label: str, section_name: str) -> int | None:
    label_norm = " ".join(label.lower().replace("-", " ").replace("/", " ").split())
    section_norm = " ".join(section_name.lower().replace("-", " ").replace("/", " ").split())
    section_base = _section_base_name(section_name).replace("-", " ")
    if not label_norm or not section_norm:
        return None
    if label_norm == section_norm:
        return 0
    label_num = _section_number(label_norm)
    section_num = _section_number(section_norm)
    if label_num is not None and section_num is not None and label_num != section_num:
        return None
    if label_norm == section_base:
        return 1
    section_tokens = set(section_norm.split())
    label_tokens = set(label_norm.split())
    if label_tokens and label_tokens.issubset(section_tokens):
        if label_norm == "chorus" and "pre" in section_tokens:
            return 8
        return 2
    if label_norm in section_norm:
        if label_norm == "chorus" and "pre chorus" in section_norm:
            return 8
        return 4
    return None


def match_lyric_section_label(label: str, section_names: list[str]) -> str | None:
    scored: list[tuple[int, int, int, str]] = []
    for idx, section_name in enumerate(section_names):
        score = _section_match_score(label, section_name)
        if score is not None:
            scored.append((score, len(section_name), idx, section_name))
    if not scored:
        return None
    return sorted(scored)[0][3]


def _try_header_line(line: str, section_names: list[str]) -> str | None:
    """Bracket [Verse 1], bracket+text, or Section: header."""
    bracket = _BRACKET_HEADER_RE.match(line)
    if bracket:
        header = bracket.group(1).strip()
        match = match_lyric_section_label(header, section_names)
        if match:
            return match
    if ":" in line:
        maybe_section, _cue = line.split(":", 1)
        match = match_lyric_section_label(maybe_section.strip(), section_names)
        if match:
            return match
    return None


def parse_user_lyric_cues(
    raw_text: str, section_names: list[str]
) -> tuple[dict[str, list[str]], bool]:
    """Parse [Section] headers or ``Section:`` lines. Returns (cues, saw_header)."""
    if not raw_text or not section_names:
        return {}, False

    cues: dict[str, list[str]] = {name: [] for name in section_names}
    current: str | None = None
    saw_header = False

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        header_match = _try_header_line(line, section_names)
        if header_match:
            saw_header = True
            current = header_match
            bracket = _BRACKET_HEADER_RE.match(line)
            if bracket and bracket.group(2).strip():
                cues[current].append(bracket.group(2).strip())
            elif ":" in line:
                _, cue = line.split(":", 1)
                if cue.strip():
                    cues[current].append(cue.strip())
            continue

        if not saw_header:
            continue

        if current is None:
            current = section_names[0]

        cues[current].append(line)

    filtered = {name: lines for name, lines in cues.items() if lines}
    return filtered, saw_header


def split_lyrics_by_paragraphs(raw_text: str, section_names: list[str]) -> dict[str, str]:
    """Assign blank-line-separated paragraphs to sections in chart order."""
    if not raw_text.strip() or not section_names:
        return {}
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", raw_text.strip()) if b.strip()]
    if not blocks:
        return {}
    out: dict[str, str] = {}
    for idx, section_name in enumerate(section_names):
        if idx < len(blocks):
            out[section_name] = blocks[idx]
    return out


def split_lyrics_by_sections(raw_text: str, section_names: list[str]) -> dict[str, str]:
    """
    Assign pasted lyrics/cues to the song's section list.

    1. [Section] or ``Section:`` headers
    2. Blank-line-separated paragraphs in section_order
    3. Even line split fallback
    """
    if not raw_text or not section_names:
        return {}

    parsed, saw_header = parse_user_lyric_cues(raw_text, section_names)
    if saw_header and parsed:
        return {
            name: "\n".join(parsed.get(name, []))
            for name in section_names
            if parsed.get(name)
        }

    by_para = split_lyrics_by_paragraphs(raw_text, section_names)
    if by_para:
        return by_para

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return {}

    import math

    out: dict[str, str] = {}
    chunk_size = max(1, math.ceil(len(lines) / len(section_names)))
    for idx, section_name in enumerate(section_names):
        chunk = lines[idx * chunk_size : (idx + 1) * chunk_size]
        if chunk:
            out[section_name] = "\n".join(chunk)
    return out

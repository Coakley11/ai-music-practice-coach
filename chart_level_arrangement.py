"""Practice-level chart views: harmonic complexity and song form per level.

Beginner — simpler chords, short practice-friendly form.
Intermediate — approachable harmony, most sections (no instrumentals / excess repeats).
Advanced — full catalog harmony and complete song form.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from beginner_arrangement import (
    BEGINNER_LEVEL,
    ROLE_BRIDGE,
    ROLE_CHORUS,
    ROLE_INTRO,
    ROLE_INTERLUDE,
    ROLE_OTHER,
    ROLE_OUTRO,
    ROLE_PRECHORUS,
    ROLE_SOLO,
    ROLE_VERSE,
    build_beginner_display_labels,
    classify_section_role,
    is_beginner_level,
    select_beginner_section_names,
)
from music_theory import split_chord

INTERMEDIATE_LEVEL = "Intermediate"
ADVANCED_LEVEL = "Advanced"

LEVEL_ARRANGEMENT_FLAG = "_level_arrangement_active"
LEVEL_ARRANGEMENT_TIER = "_level_arrangement_tier"


def is_intermediate_level(level: Any) -> bool:
    return str(level or "").strip().lower() == INTERMEDIATE_LEVEL.lower()


def is_advanced_level(level: Any) -> bool:
    return str(level or "").strip().lower() == ADVANCED_LEVEL.lower()


def _map_subdivided(token: str, mapper) -> str:
    if "|" not in token:
        return mapper(token)
    parts = [p.strip() for p in token.split("|") if p.strip()]
    return "|".join(mapper(p) for p in parts)


def simplify_chord_for_beginner(chord: str, *, genre: str = "") -> str:
    """Strip slash chords, extensions, and reharm moves for beginner charts."""
    token = str(chord or "").strip()
    if not token:
        return token

    def _one(part: str) -> str:
        head = part
        if "/" in part:
            head = part.split("/", 1)[0].strip()
        root, suffix = split_chord(head)
        s = suffix.lower()
        if any(tok in s for tok in ("m7b5", "dim", "aug", "alt")):
            return root + ("m" if "m" in s and "maj" not in s else "")
        if s.startswith("m") and "maj" not in s:
            return root + "m"
        if "maj7" in s or "maj9" in s:
            return root
        if any(tok in s for tok in ("9", "11", "13", "sus", "add")):
            return root + ("m" if s.startswith("m") and "maj" not in s else "")
        if "7" in s:
            return root + ("7" if "blues" in genre.lower() else root)
        return root + ("m" if s.startswith("m") and "maj" not in s else "")

    return _map_subdivided(token, _one)


def normalize_chord_for_intermediate(chord: str) -> str:
    """Mostly original harmony; trim only dense jazz extensions."""
    token = str(chord or "").strip()
    if not token:
        return token
    out = token.replace("maj9", "maj7").replace("M9", "M7")
    out = out.replace("m9", "m7").replace("min9", "m7")
    out = out.replace("13", "7").replace("11", "7")
    return out.replace("7#9", "7").replace("7b9", "7").replace("alt", "7")


def chords_for_level(chords: list[str], level: str, *, genre: str = "") -> list[str]:
    if is_beginner_level(level):
        return [simplify_chord_for_beginner(c, genre=genre) for c in chords]
    if is_intermediate_level(level):
        return [normalize_chord_for_intermediate(c) for c in chords]
    return list(chords)


def sections_for_level(song_data: Mapping[str, Any] | None, level: str) -> dict[str, list[str]]:
    """Chord content per section for a practice level (full section dict keys)."""
    if not song_data:
        return {}
    explicit = (song_data.get("chart_versions") or {}) if isinstance(song_data, Mapping) else {}
    if level in explicit and explicit[level]:
        return {name: list(chords) for name, chords in explicit[level].items()}

    raw = song_data.get("sections") or {}
    genre = str(song_data.get("genre") or "")
    if is_advanced_level(level):
        return {name: list(chords) for name, chords in raw.items()}
    return {
        name: chords_for_level(list(chords), level, genre=genre)
        for name, chords in raw.items()
    }


def select_intermediate_section_names(section_names: list[str] | None) -> list[str]:
    """Most of the real form without instrumentals or excessive chorus tails."""
    if not section_names:
        return []

    outros = [n for n in section_names if classify_section_role(n) == ROLE_OUTRO]
    final_outro = next((n for n in reversed(outros) if "final" in n.lower()), None)
    if not final_outro and outros:
        final_outro = outros[-1]

    intro_kept = False
    bridge_kept = False
    prechorus_kept = False
    chorus_count = 0
    verse_count = 0
    out: list[str] = []

    for name in section_names:
        role = classify_section_role(name)
        if role in (ROLE_SOLO, ROLE_INTERLUDE):
            continue
        if role == ROLE_INTRO:
            if not intro_kept:
                out.append(name)
                intro_kept = True
            continue
        if role == ROLE_BRIDGE:
            if not bridge_kept:
                out.append(name)
                bridge_kept = True
            continue
        if role == ROLE_PRECHORUS:
            if not prechorus_kept:
                out.append(name)
                prechorus_kept = True
            continue
        if role == ROLE_CHORUS:
            low = name.lower()
            if "final" in low:
                if name not in out:
                    out.append(name)
                continue
            if chorus_count < 2:
                out.append(name)
                chorus_count += 1
            continue
        if role == ROLE_VERSE:
            if verse_count < 4:
                out.append(name)
                verse_count += 1
            continue
        if role == ROLE_OUTRO:
            continue
        if role == ROLE_OTHER and name not in out:
            out.append(name)

    if final_outro and final_outro not in out:
        out.append(final_outro)

    if not out:
        return list(section_names[:6])
    return out


def select_section_names_for_level(section_names: list[str] | None, level: str) -> list[str]:
    if is_advanced_level(level):
        return list(section_names or [])
    if is_beginner_level(level):
        return select_beginner_section_names(section_names, max_verses=2, max_choruses=2)
    if is_intermediate_level(level):
        return select_intermediate_section_names(section_names)
    return list(section_names or [])


def _section_order_from_song(song_data: Mapping[str, Any]) -> list[str]:
    order = list(song_data.get("section_order") or [])
    if order:
        return order
    sections = song_data.get("sections")
    if isinstance(sections, Mapping):
        return list(sections.keys())
    return []


def level_view_of_song_data(
    song_data: Mapping[str, Any] | None,
    *,
    level: str,
) -> dict[str, Any] | None:
    """Shallow copy with level-appropriate ``section_order`` (never mutates catalog)."""
    if song_data is None:
        return None
    base = dict(song_data)
    if is_advanced_level(level):
        return base

    order = _section_order_from_song(base)
    if not order:
        return base

    trimmed = select_section_names_for_level(order, level)
    if trimmed == order:
        return base

    base["section_order"] = trimmed
    base[LEVEL_ARRANGEMENT_FLAG] = True
    base[LEVEL_ARRANGEMENT_TIER] = str(level)
    base["_beginner_arrangement_original_order"] = list(order)
    if is_beginner_level(level):
        base["_beginner_arrangement_active"] = True
        base["_beginner_display_labels"] = build_beginner_display_labels(trimmed)
    return base


def level_view_of_sections(
    sections: Mapping[str, Any] | None,
    *,
    section_order_for_level: list[str] | None,
) -> dict[str, Any]:
    if not sections:
        return {}
    if not section_order_for_level:
        return dict(sections)
    return {name: sections[name] for name in section_order_for_level if name in sections}


def is_level_arrangement_active(song_data: Mapping[str, Any] | None, *, level: str = "") -> bool:
    if not song_data:
        return False
    if is_beginner_level(level):
        return bool(song_data.get("_beginner_arrangement_active"))
    if is_intermediate_level(level):
        return bool(song_data.get(LEVEL_ARRANGEMENT_FLAG)) and str(
            song_data.get(LEVEL_ARRANGEMENT_TIER) or ""
        ).strip() == INTERMEDIATE_LEVEL
    return False


def resolve_level_chart(
    song_data: Mapping[str, Any] | None,
    level: str,
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """Return ``(song_data_view, sections)`` for charts, backing, and practice UI."""
    base = dict(song_data) if isinstance(song_data, Mapping) else {}
    sections = sections_for_level(base, level)
    view = level_view_of_song_data(base, level=level) or base
    order = list(view.get("section_order") or [])
    if order:
        sections = level_view_of_sections(sections, section_order_for_level=order)
    return view, sections

"""Section chord pattern repeats for Composition Studio.

Authoritative harmony for a section is always ``section["chords"]`` — the full
expanded event list (including every repeated pass and any occurrence-level edit).

When the progression is still a clean tile of a base pattern, ``harmony`` also
tracks:
- ``chord_pattern`` — base suggestion entries
- ``chord_repeats`` — how many times that pattern is tiled into ``chords``
- ``chords_tiled`` — True while slider re-expansion is safe
- ``chord_source_id`` — suggestion id used for card highlighting

Once the user accepts a refinement or manual edit that is not a pure re-tile,
``chords_tiled`` becomes False and the full ``chords`` list is the only truth.
"""

from __future__ import annotations

import copy
from typing import Any

from custom_progression_lab import format_entries_bar_line, normalize_chord_symbol

from composition_document import apply_section_chords, harmony_edit_target

CHORD_REPEAT_MIN = 1
CHORD_REPEAT_MAX = 4

COMPLETION_COPY = (
    "Your chords are ready. Build or hum a melody over them — or keep refining harmony."
)


def clamp_chord_repeats(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = 1
    return max(CHORD_REPEAT_MIN, min(CHORD_REPEAT_MAX, n))


def _clone_entries(entries: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in list(entries or []):
        if isinstance(raw, dict):
            out.append(copy.deepcopy(raw))
        else:
            sym = normalize_chord_symbol(str(raw or "")) or str(raw or "").strip()
            if sym:
                out.append({"chord": sym, "bars": 1})
    return out


def expand_chord_entries_by_repeats(
    entries: list[dict[str, Any]] | None,
    repeats: int,
) -> list[dict[str, Any]]:
    """Tile ``entries`` ``repeats`` times into one flat progression."""
    pattern = _clone_entries(entries)
    n = clamp_chord_repeats(repeats)
    if not pattern:
        return []
    if n == 1:
        return pattern
    out: list[dict[str, Any]] = []
    for r in range(n):
        for row in pattern:
            item = copy.deepcopy(row)
            item["pass_index"] = r
            out.append(item)
    return out


def entry_symbols(entries: list[dict[str, Any]] | None) -> list[str]:
    symbols: list[str] = []
    for raw in list(entries or []):
        if not isinstance(raw, dict):
            continue
        sym = normalize_chord_symbol(str(raw.get("chord") or "")) or str(raw.get("chord") or "").strip()
        if not sym:
            continue
        bars = max(1, int(raw.get("bars") or 1))
        symbols.extend([sym] * bars)
    return symbols


def format_full_progression_display(
    entries: list[dict[str, Any]] | None,
    *,
    pattern_len: int | None = None,
) -> str:
    """Human-readable full progression; groups repeated passes when possible."""
    symbols = entry_symbols(entries)
    if not symbols:
        return "(empty)"
    plen = int(pattern_len or 0)
    if plen > 0 and len(symbols) > plen and len(symbols) % plen == 0:
        lines: list[str] = []
        for i in range(0, len(symbols), plen):
            chunk = symbols[i : i + plen]
            lines.append(" | ".join(chunk))
        return "\n".join(lines)
    # Fallback: continuous bar line (allow long expanded progressions).
    return format_entries_bar_line(entries, max_chords=max(24, len(symbols) + 4))


def ensure_harmony_chord_meta(section: dict[str, Any] | None) -> dict[str, Any]:
    """Ensure section harmony carries chord pattern / repeat metadata."""
    if not isinstance(section, dict):
        return {}
    harmony = section.get("harmony")
    if not isinstance(harmony, dict):
        harmony = {}
        section["harmony"] = harmony
    chords = list(section.get("chords") or [])
    if "chord_pattern" not in harmony:
        harmony["chord_pattern"] = _clone_entries(chords) if chords else []
    if "chord_repeats" not in harmony:
        harmony["chord_repeats"] = 1
    if "chords_tiled" not in harmony:
        pattern = list(harmony.get("chord_pattern") or [])
        if pattern and chords:
            psyms = entry_symbols(pattern)
            csyms = entry_symbols(chords)
            if psyms and csyms and len(csyms) % len(psyms) == 0:
                n = len(csyms) // len(psyms)
                harmony["chords_tiled"] = csyms == (psyms * n)
                if harmony["chords_tiled"]:
                    harmony["chord_repeats"] = clamp_chord_repeats(n)
            else:
                harmony["chords_tiled"] = False
        else:
            harmony["chords_tiled"] = bool(chords)
    harmony.setdefault("chord_source_id", "")
    harmony["chord_repeats"] = clamp_chord_repeats(harmony.get("chord_repeats"))
    return harmony


def get_chord_pattern(section: dict[str, Any] | None) -> list[dict[str, Any]]:
    harmony = ensure_harmony_chord_meta(section)
    pattern = harmony.get("chord_pattern")
    if isinstance(pattern, list) and pattern:
        return _clone_entries(pattern)
    return _clone_entries((section or {}).get("chords") or [])


def get_chord_repeats(section: dict[str, Any] | None) -> int:
    harmony = ensure_harmony_chord_meta(section)
    return clamp_chord_repeats(harmony.get("chord_repeats"))


def get_chord_source_id(section: dict[str, Any] | None) -> str:
    harmony = ensure_harmony_chord_meta(section)
    return str(harmony.get("chord_source_id") or "")


def chords_are_tiled(section: dict[str, Any] | None) -> bool:
    harmony = ensure_harmony_chord_meta(section)
    return bool(harmony.get("chords_tiled"))


def pattern_length_for_display(section: dict[str, Any] | None) -> int | None:
    """Pass width for multi-line display when the section is still tiled."""
    if not chords_are_tiled(section):
        # Still try to group by stored pattern length if chords are an exact multiple.
        pattern = get_chord_pattern(section)
        plen = len(entry_symbols(pattern))
        symbols = entry_symbols((section or {}).get("chords") or [])
        if plen > 0 and len(symbols) > plen and len(symbols) % plen == 0:
            return plen
        return None
    pattern = get_chord_pattern(section)
    plen = len(entry_symbols(pattern))
    return plen if plen > 0 else None


def accept_chord_pattern(
    doc: dict[str, Any],
    section_id: str,
    pattern_entries: list[dict[str, Any]],
    *,
    source_id: str = "",
    repeats: int | None = None,
) -> bool:
    """Accept a base suggestion as the active tiled progression."""
    edit_id, sec = harmony_edit_target(doc, section_id)
    if not sec:
        return False
    harmony = ensure_harmony_chord_meta(sec)
    pattern = _clone_entries(pattern_entries)
    if not pattern:
        return False
    n = clamp_chord_repeats(repeats if repeats is not None else harmony.get("chord_repeats") or 1)
    harmony["chord_pattern"] = pattern
    harmony["chord_repeats"] = n
    harmony["chords_tiled"] = True
    harmony["chord_source_id"] = str(source_id or "")
    expanded = expand_chord_entries_by_repeats(pattern, n)
    return apply_section_chords(doc, edit_id or section_id, expanded)


def set_section_chord_repeats(doc: dict[str, Any], section_id: str, repeats: int) -> bool:
    """Re-tile the stored base pattern when still in tiled mode."""
    edit_id, sec = harmony_edit_target(doc, section_id)
    if not sec or not chords_are_tiled(sec):
        return False
    harmony = ensure_harmony_chord_meta(sec)
    pattern = get_chord_pattern(sec)
    if not pattern:
        return False
    n = clamp_chord_repeats(repeats)
    harmony["chord_repeats"] = n
    harmony["chords_tiled"] = True
    expanded = expand_chord_entries_by_repeats(pattern, n)
    return apply_section_chords(doc, edit_id or section_id, expanded)


def accept_full_progression(
    doc: dict[str, Any],
    section_id: str,
    entries: list[dict[str, Any]],
    *,
    source_id: str = "",
    tiled: bool = False,
    pattern_entries: list[dict[str, Any]] | None = None,
    repeats: int | None = None,
) -> bool:
    """Install a full progression as authoritative section harmony."""
    edit_id, sec = harmony_edit_target(doc, section_id)
    if not sec:
        return False
    full = _clone_entries(entries)
    if not full:
        return False
    harmony = ensure_harmony_chord_meta(sec)
    if tiled and pattern_entries:
        pattern = _clone_entries(pattern_entries)
        n = clamp_chord_repeats(repeats if repeats is not None else 1)
        harmony["chord_pattern"] = pattern
        harmony["chord_repeats"] = n
        harmony["chords_tiled"] = True
        harmony["chord_source_id"] = str(source_id or "")
        full = expand_chord_entries_by_repeats(pattern, n)
    else:
        harmony["chord_pattern"] = _clone_entries(full)
        harmony["chord_repeats"] = 1
        harmony["chords_tiled"] = False
        harmony["chord_source_id"] = str(source_id or "")
    return apply_section_chords(doc, edit_id or section_id, full)


def mark_progression_customized(section: dict[str, Any] | None) -> None:
    """After occurrence-level edits, freeze tiling so repeats cannot wipe changes."""
    if not isinstance(section, dict):
        return
    harmony = ensure_harmony_chord_meta(section)
    harmony["chords_tiled"] = False
    harmony["chord_pattern"] = _clone_entries(section.get("chords") or [])
    harmony["chord_repeats"] = 1
    harmony["chord_source_id"] = ""

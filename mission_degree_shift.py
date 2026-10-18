"""Move Mission Up / Down: shift a Mission phrase by exactly one degree of its own tonal framework.

The framework is the Mission's real collection, never the rendered note names and never a semitone grid:

* pentatonic / blues Missions use the ordered collection the generator resolved
  (``resolve_pentatonic_choice`` / ``resolve_blues_choice``, selected by the motif's ``pentatonic_relationship``);
* "chord tones only" / "guide tones" Missions step through the chord's tones / guide tones;
* every other Mission steps through the diatonic scale of the motif's ``spelling_reference`` (the key the
  generator spelled it in), falling back to the Practice Key.

Everything here runs in concert (canonical) pitch; the caller projects to the Written Key afterwards.
A note is described as (collection degree, semitone offset above that degree), so rhythm, contour and
inflection survive and Up then Down (or Down then Up) restores the phrase exactly.
"""

from __future__ import annotations

from bisect import bisect_right
from typing import Any


class MoveRefused(Exception):
    """The move cannot be made without breaking the Mission or the framework."""


def _pc(name: str) -> int:
    from improvisation_motif import _midi_from_note

    return _midi_from_note(str(name), 4) % 12


def resolve_framework(
    mission: str, motif: dict[str, Any], *, chord: str, key_center: str
) -> tuple[str, dict[int, str]]:
    """(label, {pitch class: spelled name}) for the collection this Mission moves through."""
    from improvisation_mission_rules import (
        BLUES_RELATIONSHIPS,
        PENTATONIC_RELATIONSHIPS,
        _guide_third_seventh,
        resolve_blues_choice,
        resolve_pentatonic_choice,
    )
    from improvisation_motif import _note_from_midi, _parse_key_scale, chord_tone_names

    key = str(motif.get("spelling_reference") or key_center or "C").strip() or "C"
    rel = str(motif.get("pentatonic_relationship") or "").strip()
    low = str(mission or "").lower()
    if rel in BLUES_RELATIONSHIPS and chord:
        _r, _k, notes, label, _b = resolve_blues_choice(chord, key, rel)
        return label, {_pc(n): n for n in notes}
    if rel in PENTATONIC_RELATIONSHIPS and chord:
        _r, _k, notes, label = resolve_pentatonic_choice(chord, key, rel)
        return label, {_pc(n): n for n in notes}
    if "guide tone" in low and chord:
        notes = [g for g in _guide_third_seventh(chord, key_center=key) if g]
        if notes:
            return f"{chord} guide tones", {_pc(n): n for n in notes}
    if "chord tones" in low and chord:
        notes = chord_tone_names(chord, reference_key=key)
        if notes:
            return f"{chord} chord tones", {_pc(n): n for n in notes}
    _mode, pcs = _parse_key_scale(key)
    return f"{key} scale", {pc: _note_from_midi(pc, key) for pc in pcs}


def shift_midis_by_degree(midis: list[int], collection_pcs: set[int], direction: int) -> list[int]:
    """Move every pitch one collection degree in ``direction`` (+1 / -1), keeping any inflection."""
    ladder = [m for m in range(0, 128) if m % 12 in collection_pcs]
    if len(ladder) < 2:
        raise MoveRefused("the scale has too few notes to move through")
    out: list[int] = []
    for m in midis:
        i = bisect_right(ladder, int(m)) - 1
        if i < 0:
            raise MoveRefused("a note is below the movable range")
        offset = int(m) - ladder[i]
        j = i + (1 if direction > 0 else -1)
        if j < 0 or j + 1 >= len(ladder):
            raise MoveRefused("that would move a note past the end of the playable range")
        if offset and offset >= ladder[j + 1] - ladder[j]:
            raise MoveRefused("this phrase has a chromatic note with no matching position one scale degree away")
        out.append(ladder[j] + offset)
    return out


def move_concert_motif(
    motif: dict[str, Any],
    concert_midis: list[int],
    *,
    mission: str,
    chord: str,
    key_center: str,
    direction: int,
) -> tuple[list[str], list[int], str]:
    """Return (spelled concert notes, concert midis, framework label) one degree up/down."""
    from improvisation_motif import _note_from_midi

    label, names = resolve_framework(mission, motif, chord=chord, key_center=key_center)
    moved = shift_midis_by_degree(list(concert_midis), set(names), direction)
    spell_key = str(motif.get("spelling_reference") or key_center or "C").strip() or "C"
    notes = [names.get(m % 12) or _note_from_midi(m, spell_key) for m in moved]
    return notes, moved, label

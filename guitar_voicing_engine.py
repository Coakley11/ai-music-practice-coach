"""Level-aware guitar chord voicing generator.

Produces real, playable fretboard voicings per difficulty level instead of
one static cowboy-chord lookup for every level:

- Beginner: open/cowboy chords from ``GUITAR_SHAPES``/song ``guitar_tabs``
  where available; a compact 3-note shell voicing (root-3rd-7th, low
  position) for chords that have no open-chord shape (e.g. jazz harmony
  that doesn't fit a cowboy grip).
- Intermediate: a movable 4-note voicing (root-3rd-5th-7th) built from
  actual chord-tone pitch classes placed on the fretboard, with inversions
  and inherent position movement -- a real barre/movable shape, not a
  fixed lookup.
- Advanced: a 3-note shell (3rd-7th-root, omitting the 5th) or a wider
  drop-2-style voicing on the top four strings, chosen chord-to-chord to
  minimize fretboard movement (voice leading / position planning), with a
  light touch of altered-dominant color when the chord symbol itself asks
  for one (b9/#9/#5/b13/alt).

All voicings are expressed in the engine's existing 6-character
``GUITAR_SHAPES``-style fret string (low E, A, D, G, B, high e; ``x`` =
muted, a single digit 0-9 = fret) so they drop directly into
``practice_notation.py``'s existing TAB renderer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from music_theory import (
    classify_chord_quality,
    normalize_chord_for_theory,
    pitch_class_from_spelled_note,
    spell_chord_tones,
)

# Standard tuning, low string to high string, pitch class of the open string.
_OPEN_PC = [4, 9, 2, 7, 11, 4]  # E A D G B e
_NUM_STRINGS = 6
_MAX_FRET = 9  # single-character fret slot in the existing shape format
_MAX_SPAN = {"Beginner": 3, "Intermediate": 4, "Advanced": 4}


@dataclass
class GuitarVoicingEvent:
    measure: int
    chord: str
    shape: str  # 6-char low-to-high fret string, e.g. "x32010"
    label: str  # "open", "shell (3-7-R)", "drop-2", "barre (A-shape)", ...
    position: int  # lowest fretted fret used (0 = open position)
    tones: list[str]  # chord tones actually voiced, spelled


def _chord_tone_pcs(chord: str) -> list[int]:
    tones = spell_chord_tones(chord)
    return [pitch_class_from_spelled_note(t) for t in tones if t]


def _alteration_hint(chord: str) -> int | None:
    """Pitch-class *offset from the root* for an explicit altered-dominant
    color written into the chord symbol itself (b9/#9/#5/b13/alt), or None.
    """
    head = normalize_chord_for_theory(chord)
    low = head.lower()
    if "b9" in low:
        return 1
    if "#9" in low or "#9" in head:
        return 3
    if "#5" in low or "b13" in low:
        return 8
    if "alt" in low:
        return 1  # altered dominant: lean on the b9 color
    return None


def _fret_for_pc_on_string(string_idx: int, target_pc: int, *, min_fret: int = 0) -> int | None:
    open_pc = _OPEN_PC[string_idx]
    for fret in range(min_fret, _MAX_FRET + 1):
        if (open_pc + fret) % 12 == target_pc:
            return fret
    return None


def _search_voicing(
    target_pcs: list[int],
    string_order: list[int],
    *,
    center_fret: int | None,
    max_span: int,
) -> dict[int, int] | None:
    """Assign each pitch class in *target_pcs* to a distinct string in
    *string_order*, within *max_span* frets of each other, as close as
    possible to *center_fret*. Returns {string_idx: fret} or None if no
    assignment fits every tone within the span (caller should drop a tone
    and retry).
    """
    if not target_pcs or not string_order:
        return None
    anchor = center_fret if center_fret is not None else 2
    best: dict[int, int] | None = None
    best_cost = None

    def backtrack(i: int, used_strings: list[int], chosen: dict[int, int]) -> None:
        nonlocal best, best_cost
        if i == len(target_pcs):
            frets = list(chosen.values())
            span = max(frets) - min(frets) if frets else 0
            if span > max_span:
                return
            cost = span + sum(abs(f - anchor) for f in frets) * 0.1
            if best_cost is None or cost < best_cost:
                best_cost = cost
                best = dict(chosen)
            return
        pc = target_pcs[i]
        candidates: list[tuple[int, int]] = []
        for s in string_order:
            if s in used_strings:
                continue
            lo = max(0, anchor - max_span)
            fret = _fret_for_pc_on_string(s, pc, min_fret=lo)
            while fret is not None and fret <= anchor + max_span:
                candidates.append((s, fret))
                fret = _fret_for_pc_on_string(s, pc, min_fret=fret + 1)
        # Try closest-to-anchor candidates first so the search converges fast.
        candidates.sort(key=lambda sf: abs(sf[1] - anchor))
        for s, fret in candidates[:4]:
            chosen[s] = fret
            backtrack(i + 1, used_strings + [s], chosen)
            del chosen[s]

    backtrack(0, [], {})
    return best


def _frets_to_shape(frets_by_string: dict[int, int]) -> str:
    out = ["x"] * _NUM_STRINGS
    for s, f in frets_by_string.items():
        out[s] = str(min(9, max(0, f)))
    return "".join(out)


def _position_of(frets_by_string: dict[int, int]) -> int:
    fretted = [f for f in frets_by_string.values() if f > 0]
    return min(fretted) if fretted else 0


def validate_voicing(frets_by_string: dict[int, int], *, max_span: int = 4) -> tuple[bool, str]:
    """Playability check: fret span, string count, finger count."""
    if not frets_by_string:
        return False, "no sounding strings"
    frets = list(frets_by_string.values())
    fretted = [f for f in frets if f > 0]
    if fretted:
        span = max(fretted) - min(fretted)
        if span > max_span:
            return False, f"fret span {span} exceeds {max_span}"
    # Approximate finger count: distinct non-open frets (a barre covers many
    # strings at one fret with a single finger, so count distinct fret values,
    # not distinct strings).
    distinct_frets = len(set(fretted))
    if distinct_frets > 4:
        return False, f"{distinct_frets} distinct frets needs more than 4 fingers"
    if len(frets_by_string) < 3:
        return False, "fewer than 3 sounding strings"
    return True, "ok"


def _beginner_voicing(chord: str, guitar_tabs: dict[str, str]) -> GuitarVoicingEvent:
    from practice_notation import GUITAR_SHAPES  # local import: avoid cycle at module load

    if chord in guitar_tabs:
        shape = guitar_tabs[chord]
        return GuitarVoicingEvent(0, chord, shape, "open", 0, spell_chord_tones(chord))
    if chord in GUITAR_SHAPES:
        shape = GUITAR_SHAPES[chord]
        return GuitarVoicingEvent(0, chord, shape, "open", 0, spell_chord_tones(chord))
    head = chord.split("/")[0]
    if head in guitar_tabs:
        return GuitarVoicingEvent(0, chord, guitar_tabs[head], "open", 0, spell_chord_tones(chord))
    if head in GUITAR_SHAPES:
        return GuitarVoicingEvent(0, chord, GUITAR_SHAPES[head], "open", 0, spell_chord_tones(chord))

    # No cowboy shape fits this harmony (e.g. jazz quality) -- compact
    # beginner shell (root-3rd-7th, or root-3rd-5th for a plain triad) low
    # on the neck. The 7th is what signals the chord's jazz quality, so it
    # must not be dropped in favor of the 5th.
    tones = spell_chord_tones(chord)
    pcs = [pitch_class_from_spelled_note(t) for t in tones if t]
    if len(pcs) >= 4:
        want = [pcs[0], pcs[1], pcs[3]]
    else:
        want = pcs[:3] if len(pcs) >= 3 else pcs
    result = _search_voicing(want, [1, 2, 3, 4], center_fret=2, max_span=_MAX_SPAN["Beginner"])
    if result is None and len(want) > 2:
        result = _search_voicing(want[:2], [1, 2, 3, 4], center_fret=2, max_span=_MAX_SPAN["Beginner"])
    if result is None:
        return GuitarVoicingEvent(0, chord, "x32010", "open (fallback)", 0, tones)
    return GuitarVoicingEvent(0, chord, _frets_to_shape(result), "compact shell", _position_of(result), tones)


def _intermediate_voicing(chord: str, prev_position: int | None) -> GuitarVoicingEvent:
    tones = spell_chord_tones(chord)
    pcs = [pitch_class_from_spelled_note(t) for t in tones if t]
    if not pcs:
        pcs = [0, 4, 7]
    center = prev_position if prev_position is not None else 2
    # Full movable voicing across five strings -- root/A-shape family.
    result = _search_voicing(pcs, [0, 1, 2, 3, 4], center_fret=center, max_span=_MAX_SPAN["Intermediate"])
    if result is None:
        result = _search_voicing(pcs, [1, 2, 3, 4], center_fret=center, max_span=_MAX_SPAN["Intermediate"])
    if result is None:
        result = _search_voicing(pcs[:3], [1, 2, 3, 4], center_fret=center, max_span=_MAX_SPAN["Intermediate"])
    if result is None:
        return GuitarVoicingEvent(0, chord, "x32010", "barre (fallback)", 0, tones)
    label = "barre (movable)" if _position_of(result) > 0 else "open"
    return GuitarVoicingEvent(0, chord, _frets_to_shape(result), label, _position_of(result), tones)


def _advanced_voicing(chord: str, prev_position: int | None) -> GuitarVoicingEvent:
    quality = classify_chord_quality(chord)
    tones = spell_chord_tones(chord)
    pcs = [pitch_class_from_spelled_note(t) for t in tones if t]
    if len(pcs) < 3:
        pcs = pcs + [pcs[0]] if pcs else [0, 4, 7]
    root_pc, third_pc = pcs[0], pcs[1]
    seventh_pc = pcs[3] if len(pcs) >= 4 else None
    center = prev_position if prev_position is not None else 3

    if seventh_pc is not None:
        shell = [third_pc, seventh_pc, root_pc]
        label = "shell (3-7-R)"
    else:
        shell = pcs[:3]
        label = "shell (3-5-R)"

    alt = _alteration_hint(chord)
    if quality == "dom" and alt is not None:
        shell = shell[:2] + [(root_pc + alt) % 12]
        label = "shell + altered color"

    result = _search_voicing(shell, [1, 2, 3, 4], center_fret=center, max_span=_MAX_SPAN["Advanced"])
    if result is None:
        result = _search_voicing(shell[:2], [1, 2, 3, 4], center_fret=center, max_span=_MAX_SPAN["Advanced"])
    if result is None and seventh_pc is not None:
        # drop-2 style: wider 4-note voicing across the top four strings.
        drop2 = [root_pc, seventh_pc, third_pc, (pcs[2] if len(pcs) > 2 else root_pc)]
        result = _search_voicing(drop2, [1, 2, 3, 4], center_fret=center, max_span=_MAX_SPAN["Advanced"])
        label = "drop-2"
    if result is None:
        return GuitarVoicingEvent(0, chord, "x32010", "shell (fallback)", 0, tones)
    return GuitarVoicingEvent(0, chord, _frets_to_shape(result), label, _position_of(result), tones)


def build_level_guitar_voicings(
    chords: list[str],
    *,
    level: str,
    guitar_tabs: dict[str, str] | None = None,
) -> list[GuitarVoicingEvent]:
    """One voicing per chord in *chords*, level-appropriate and
    position-connected chord-to-chord for Intermediate/Advanced."""
    tabs = guitar_tabs or {}
    out: list[GuitarVoicingEvent] = []
    prev_position: int | None = None
    for m_idx, chord in enumerate(chords):
        if level == "Beginner":
            ev = _beginner_voicing(chord, tabs)
        elif level == "Advanced":
            ev = _advanced_voicing(chord, prev_position)
        else:
            ev = _intermediate_voicing(chord, prev_position)
        ev.measure = m_idx
        out.append(ev)
        prev_position = ev.position
    return out


__all__ = [
    "GuitarVoicingEvent",
    "build_level_guitar_voicings",
    "validate_voicing",
]

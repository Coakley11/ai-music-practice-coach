"""Level-aware Guitar Pentatonics fretboard exercise generator.

Practice Focus = Pentatonics on Guitar must produce a **moving single-note
pentatonic line** -- ascending/descending fragments, sequenced patterns,
and (Advanced) position-connected phrases across the selected section's
actual harmony -- not a held chord shape with a relabeled caption.

Reuses, rather than reinvents, existing infrastructure:
- ``chord_navigation_notation._pentatonic_pool`` for the harmony-aware
  pentatonic pitch-class pool (chord-quality-aware minor/major/dominant
  pentatonic selection) -- the same policy already used for wind/bass/
  piano Pentatonics, so Guitar picks the identical pentatonic collection
  per chord as every other instrument, instead of a Guitar-only harmonic
  theory system.
- ``guitar_voicing_engine``'s standard-tuning fretboard pitch-class math
  (``_OPEN_PC``) and fret-bounds convention (``_MAX_FRET``).
- The canonical resolved groove (passed in by the caller, exactly like
  ``guitar_voicing_engine``/``practice_notation.py``'s existing comping
  path) -- this module never re-infers groove independently.
"""

from __future__ import annotations

from dataclasses import dataclass

from chord_navigation_notation import _pentatonic_pool
from music_theory import pitch_class_from_spelled_note

_NUM_STRINGS = 6
_OPEN_PC = [4, 9, 2, 7, 11, 4]  # E A D G B e -- same standard-tuning math as guitar_voicing_engine
_MAX_FRET = 9

# Eighth-note slot indices (of the existing 8-slot-per-bar TAB grid) that
# carry a note at each level -- increasing rhythmic density/activity level
# to level, matching the wind/Practice-Melody Beginner->Advanced curve.
_BEGINNER_SLOTS: tuple[int, ...] = (0, 2, 4, 6)
_INTERMEDIATE_SLOTS: tuple[int, ...] = (0, 1, 2, 4, 5, 6)
_ADVANCED_SLOTS_STRAIGHT: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6, 7)
_ADVANCED_SLOTS_DISPLACED: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7)  # off-the-downbeat entry

# Fret-window width (inclusive span) searched per level -- Beginner stays in
# one compact box; Intermediate/Advanced allow a wider search so the phrase
# can connect neighboring positions.
_WINDOW_SPAN = {"Beginner": 3, "Intermediate": 5, "Advanced": 7}
_PREFERRED_LO = {"Beginner": 2, "Intermediate": 2, "Advanced": 1}
_MAX_SAME_STRING_JUMP = 5  # frets -- consecutive notes on the same string
_MAX_CONSECUTIVE_JUMP = 7  # frets -- any two consecutive notes, any strings


@dataclass
class PentatonicNoteEvent:
    measure: int
    slot: int  # 0-7 within the bar's 8 eighth-note grid
    string_idx: int  # 0 = low E ... 5 = high e
    fret: int
    pitch_class: int
    chord: str
    note_name: str = ""
    is_chromatic_approach: bool = False
    position_shift: bool = False  # True if this note starts a new box relative to the previous note


def _pc_pool_for_chord(chord: str, level: str) -> list[tuple[int, str]]:
    """Harmony-aware pentatonic pool for *chord* -- reuses the same
    chord-quality-aware selection every other instrument's Pentatonics
    focus already uses, so Guitar never diverges onto its own scale
    choice for the same chord/level."""
    spelled = _pentatonic_pool(chord, level)
    out: list[tuple[int, str]] = []
    seen: set[int] = set()
    for note in spelled:
        pc = pitch_class_from_spelled_note(note)
        if pc is None or pc in seen:
            continue
        seen.add(pc)
        out.append((pc, note))
    return out


def _positions_in_window(target_pcs: list[int], lo: int, hi: int) -> list[tuple[int, int, int]]:
    """All (string_idx, fret, pc) with fret in [lo, hi] and pc in target_pcs."""
    out = []
    for s in range(_NUM_STRINGS):
        for fret in range(max(0, lo), min(_MAX_FRET, hi) + 1):
            pc = (_OPEN_PC[s] + fret) % 12
            if pc in target_pcs:
                out.append((s, fret, pc))
    return out


def _best_window(target_pcs: list[int], *, span: int, preferred_lo: int) -> tuple[int, int]:
    """Choose the fret window [lo, lo+span] covering the most distinct
    target pitch classes, closest to ``preferred_lo`` (position continuity
    with the previous chord's box)."""
    best = (0, span)
    best_score: tuple[int, int] | None = None
    max_lo = max(0, _MAX_FRET - span)
    for lo in range(0, max_lo + 1):
        hi = lo + span
        covered = {pc for (_, _, pc) in _positions_in_window(target_pcs, lo, hi)}
        score = (-len(covered), abs(lo - preferred_lo))
        if best_score is None or score < best_score:
            best_score = score
            best = (lo, hi)
    return best


def _nearest_candidate(
    candidates: list[tuple[int, int, int]],
    pc: int,
    prev: tuple[int, int] | None,
) -> tuple[int, int] | None:
    """Pick the (string, fret) for *pc* closest to *prev* -- same/adjacent
    string and small fret distance preferred -- among *candidates*, so
    consecutive notes form a physically sensible fretboard path instead of
    an arbitrary jump created solely by pitch selection."""
    options = [(s, f) for (s, f, p) in candidates if p == pc]
    if not options:
        return None
    if prev is None:
        options.sort(key=lambda sf: (abs(sf[0] - 3), sf[1]))
        return options[0]
    ps, pf = prev

    def cost(sf: tuple[int, int]) -> tuple[int, int, int]:
        s, f = sf
        return (abs(s - ps) * 2, abs(f - pf), f)

    options.sort(key=cost)
    # Prefer an option that keeps the move physically playable (bounded
    # same-string stretch, bounded overall jump); only fall back to the
    # closest-by-cost option regardless of bound when nothing else exists
    # (e.g. the very first note of a two-window Advanced search), so a
    # musically-driven position shift never silently becomes an
    # unplayable same-string leap.
    playable = [
        sf
        for sf in options
        if not (sf[0] == ps and abs(sf[1] - pf) > _MAX_SAME_STRING_JUMP)
        and abs(sf[1] - pf) <= _MAX_CONSECUTIVE_JUMP
    ]
    return playable[0] if playable else options[0]


def _degree_sequence(pcs: list[int], *, n: int, level: str, ascending_first: bool) -> list[int]:
    """Order of pentatonic pitch classes to walk through for one measure.

    Beginner: one clean ascending run then back down -- a single
    recognizable shape, comfortable string crossing.
    Intermediate: grouped-by-3 sequencing (a standard pentatonic-sequencing
    exercise) with a direction change -- clearly goes beyond one static run.
    Advanced: skip-wise/intervallic traversal across the wider window, with
    a direction reversal partway -- broader, less predictable movement.
    """
    if not pcs:
        return []
    pool = list(pcs)
    if level == "Beginner":
        up = (pool * ((n // len(pool)) + 2))[: max(1, n // 2)]
        down = list(reversed(up))
        seq = (up + down)[:n]
        return seq if seq else pool[:n]
    if level == "Intermediate":
        groups: list[int] = []
        for start in range(len(pool) * 2):
            groups.append(pool[start % len(pool)])
            groups.append(pool[(start + 1) % len(pool)])
            groups.append(pool[(start + 2) % len(pool)])
        seq = groups[:n]
        return list(reversed(seq)) if not ascending_first else seq
    # Advanced: intervallic (skip-wise) traversal, direction reverses partway.
    skip = pool[0::2] + pool[1::2]
    extended = skip * ((n // max(1, len(skip))) + 2)
    up = extended[:n]
    if not ascending_first:
        mid = n // 2
        up = up[:mid] + list(reversed(up[:mid]))[: n - mid]
    return up[:n]


def _level_slots(level: str, *, displaced: bool) -> tuple[int, ...]:
    if level == "Beginner":
        return _BEGINNER_SLOTS
    if level == "Intermediate":
        return _INTERMEDIATE_SLOTS
    return _ADVANCED_SLOTS_DISPLACED if displaced else _ADVANCED_SLOTS_STRAIGHT


def build_guitar_pentatonic_measures(
    chords: list[str],
    *,
    level: str,
    is_jazz_groove: bool,
    is_sparse_groove: bool = False,
    prev_window_lo: int | None = None,
) -> list[list[PentatonicNoteEvent]]:
    """One list of :class:`PentatonicNoteEvent` per chord/measure, in
    order, position-connected measure-to-measure the way
    ``guitar_voicing_engine.build_level_guitar_voicings`` connects chord
    voicings. *is_jazz_groove* gates the Advanced chromatic-approach-note
    embellishment (Pop/Rock stays stylistically plain); *is_sparse_groove*
    (Ballad) thins the rhythm for "more space / less density"."""
    span = _WINDOW_SPAN.get(level, 4)
    preferred_lo = _PREFERRED_LO.get(level, 2) if prev_window_lo is None else prev_window_lo
    out: list[list[PentatonicNoteEvent]] = []
    ascending_first = True

    for m_idx, chord in enumerate(chords):
        pool = _pc_pool_for_chord(chord, level)
        pcs = [pc for pc, _ in pool]
        names_by_pc = dict(pool)
        if not pcs:
            out.append([])
            continue

        lo, hi = _best_window(pcs, span=span, preferred_lo=preferred_lo)
        candidates = _positions_in_window(pcs, lo, hi)
        if level == "Advanced" and len(chords) > 1:
            # Connect a second, neighboring window so Advanced genuinely
            # traverses more than one box across the phrase.
            lo2, hi2 = _best_window(pcs, span=span, preferred_lo=lo + span)
            candidates = candidates + _positions_in_window(pcs, lo2, hi2)

        displaced = is_jazz_groove and level == "Advanced"
        slots = _level_slots(level, displaced=displaced)
        if is_sparse_groove and len(slots) > 4:
            slots = slots[::2]

        degrees = _degree_sequence(pcs, n=len(slots), level=level, ascending_first=ascending_first)
        ascending_first = not ascending_first  # alternate shape measure-to-measure

        events: list[PentatonicNoteEvent] = []
        prev_sf: tuple[int, int] | None = None
        prev_window = (lo, hi)
        for slot, pc in zip(slots, degrees):
            sf = _nearest_candidate(candidates, pc, prev_sf)
            if sf is None:
                continue
            s, f = sf
            shift = prev_sf is not None and not (prev_window[0] <= f <= prev_window[1])
            events.append(
                PentatonicNoteEvent(
                    measure=m_idx,
                    slot=slot,
                    string_idx=s,
                    fret=f,
                    pitch_class=pc,
                    chord=chord,
                    note_name=names_by_pc.get(pc, ""),
                    position_shift=shift,
                )
            )
            prev_sf = sf

        # Advanced + Jazz: one controlled chromatic lower-neighbor approach
        # note into the next chord's pentatonic target, on the last slot of
        # the measure -- the same "approach tone into a strong-beat target"
        # idea practice_melody_generator already uses for Jazz-Advanced,
        # applied here deterministically (one per chord change) rather than
        # via that module's RNG, since this is a fixed fretboard exercise,
        # not a generated melody.
        if is_jazz_groove and level == "Advanced" and m_idx + 1 < len(chords) and events:
            next_pool = _pc_pool_for_chord(chords[m_idx + 1], level)
            if next_pool:
                target_pc = next_pool[0][0]
                approach_pc = (target_pc - 1) % 12
                approach_candidates = _positions_in_window(
                    [approach_pc], max(0, prev_window[0] - 1), prev_window[1] + 2
                )
                last = events[-1]
                sf = _nearest_candidate(approach_candidates, approach_pc, (last.string_idx, last.fret))
                if sf is not None:
                    s, f = sf
                    events[-1] = PentatonicNoteEvent(
                        measure=m_idx,
                        slot=last.slot,
                        string_idx=s,
                        fret=f,
                        pitch_class=approach_pc,
                        chord=chord,
                        note_name="",
                        is_chromatic_approach=True,
                        position_shift=last.position_shift,
                    )

        out.append(events)
        preferred_lo = lo

    return out


def validate_pentatonic_line(measures: list[list[PentatonicNoteEvent]]) -> tuple[bool, str]:
    """Melodic-line playability check -- deliberately NOT the chord-voicing
    finger-count/span rules (those assume several simultaneous fretted
    notes; a monophonic pentatonic line is one finger at a time). Checks:
    fret bounds, no same-string jump wider than a comfortable stretch, and
    no consecutive-note jump so wide it could only be a pitch-selection
    artifact rather than a real, playable phrase."""
    for measure in measures:
        prev: tuple[int, int] | None = None
        for ev in measure:
            if not (0 <= ev.fret <= _MAX_FRET):
                return False, f"fret {ev.fret} out of range"
            if not (0 <= ev.string_idx < _NUM_STRINGS):
                return False, f"string {ev.string_idx} out of range"
            if prev is not None:
                ps, pf = prev
                if ps == ev.string_idx and abs(pf - ev.fret) > _MAX_SAME_STRING_JUMP:
                    return False, f"same-string jump {abs(pf - ev.fret)} frets exceeds {_MAX_SAME_STRING_JUMP}"
                if abs(pf - ev.fret) > _MAX_CONSECUTIVE_JUMP:
                    return False, f"consecutive-note jump {abs(pf - ev.fret)} frets exceeds {_MAX_CONSECUTIVE_JUMP}"
            prev = (ev.string_idx, ev.fret)
    return True, "ok"


__all__ = [
    "PentatonicNoteEvent",
    "build_guitar_pentatonic_measures",
    "validate_pentatonic_line",
]

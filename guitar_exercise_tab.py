"""Guitar TAB for the Practice page's scale and arpeggio exercises.

The guitar already had a single-note TAB path - ``guitar_pentatonic_engine`` - and the
renderer to draw it. What it did not have was a way to put a *given line of pitches* on the
fretboard: the pentatonic engine chooses its own notes from pitch classes, so it can pick
whichever octave is convenient. A scale or arpeggio study arrives from the shared
``notation_exercise_patterns`` engine as absolute MIDI, and an octave is not negotiable - C4
and C5 are different exercises. Mapping pitch classes would quietly discard that.

So this module maps **absolute pitches** onto strings and frets, and nothing else. It makes
no harmonic choices: the notes, the pattern, the level curve and the Practice Focus are all
decided upstream by ``build_exercise_midis``, exactly as they are for the wind instruments
and the piano. The playability rules and the rhythmic slot grid are imported from
``guitar_pentatonic_engine`` rather than restated, so one fretboard policy governs every
melodic guitar line in the app.

Capo
----
Nothing here offsets for a capo, deliberately. When capo mode is on, the Practice page
transposes the chart into the *shape* key upstream (``_capo_ctx.shape_sections``) and the
whole notation layer works in written/shape terms, where fret 0 is the capo. Adding a capo
offset to the fret arithmetic as well would transpose the exercise twice.

Position choice
---------------
Each pitch has two or three playable positions, so the fingering is chosen by a short
Viterbi pass over the whole bar rather than note by note. A greedy nearest-position walk
takes the cheapest next step and can strand the hand, paying for it later in the bar; the
exhaustive pass is small enough to be exact (at most a handful of options per note) and
actually minimises hand movement across the line, which is what "minimal position shifts"
has to mean.

Pure Python: no Streamlit and no HTML, so the fingering is unit-testable on its own.
"""

from __future__ import annotations

from typing import Sequence

from guitar_pentatonic_engine import (
    LEVEL_SLOTS,
    MAX_CONSECUTIVE_JUMP,
    MAX_SAME_STRING_JUMP,
    NUM_STRINGS,
    WINDOW_SPAN,
    PentatonicNoteEvent,
)

# Standard tuning as absolute MIDI, low to high: E2 A2 D3 G3 B3 E4. The same six values
# ``backing_rock_guitar.OPEN_STRINGS`` plays, imported rather than retyped so a retuning
# never has to be remembered in two places.
try:  # pragma: no cover - the fallback only matters if that module moves
    from backing_rock_guitar import OPEN_STRINGS as OPEN_STRING_MIDI
except Exception:  # pragma: no cover
    OPEN_STRING_MIDI = (40, 45, 50, 55, 59, 64)

# How far up the neck an exercise is allowed to go. The pentatonic engine stops at 9 because
# a blues box lives down there; a two-octave scale study needs a little more room, and 12
# keeps every position within one hand-shift of the nut.
EXERCISE_MAX_FRET = 12

# What movement costs, used only to rank fingerings against each other.
# Crossing a string inside the hand's current box is nearly free - that is what playing in
# position *is*. Moving the box is what costs, which is why the shift penalty dwarfs it.
_STRING_CHANGE_COST = 1
_SHIFT_PENALTY = 12

__all__ = [
    "EXERCISE_MAX_FRET",
    "OPEN_STRING_MIDI",
    "build_guitar_exercise_measures",
    "fret_for_midi_on_string",
    "map_line_to_frets",
    "playable_in_tab_range",
    "positions_for_midi",
    "validate_exercise_tab",
]


def fret_for_midi_on_string(
    midi: int,
    string_idx: int,
    *,
    max_fret: int = EXERCISE_MAX_FRET,
) -> int | None:
    """The fret that sounds *midi* on *string_idx*, or ``None`` if it is not on that string.

    ``string_idx`` is 0 = low E ... 5 = high e, matching ``PentatonicNoteEvent``.
    """
    if not 0 <= int(string_idx) < NUM_STRINGS:
        return None
    fret = int(midi) - OPEN_STRING_MIDI[int(string_idx)]
    return fret if 0 <= fret <= int(max_fret) else None


def positions_for_midi(
    midi: int,
    *,
    max_fret: int = EXERCISE_MAX_FRET,
) -> list[tuple[int, int]]:
    """Every ``(string_idx, fret)`` that sounds exactly *midi*, low string first."""
    out: list[tuple[int, int]] = []
    for s in range(NUM_STRINGS):
        fret = fret_for_midi_on_string(midi, s, max_fret=max_fret)
        if fret is not None:
            out.append((s, fret))
    return out


def playable_in_tab_range(midi: int, *, max_fret: int = EXERCISE_MAX_FRET) -> bool:
    return bool(positions_for_midi(midi, max_fret=max_fret))


def _reach_cost(prev: tuple[int, int], nxt: tuple[int, int]) -> int | None:
    """What crossing from one position to the next costs the hand, or ``None`` if it cannot.

    The two bounds are the pentatonic engine's, imported rather than reinvented: no
    same-string stretch wider than a hand, and no leap so wide it could only be an artifact
    of pitch selection rather than a phrase anyone would play.
    """
    ps, pf = prev
    ns, nf = nxt
    fret_move = abs(nf - pf)
    if ps == ns and fret_move > MAX_SAME_STRING_JUMP:
        return None
    if fret_move > MAX_CONSECUTIVE_JUMP:
        return None
    return fret_move + _STRING_CHANGE_COST * abs(ns - ps)


def _box_for_level(level: str) -> int:
    """How many frets the hand covers without moving, by level."""
    return int(WINDOW_SPAN.get(str(level or "Intermediate").strip().title(), 5))


def map_line_to_frets(
    midis: Sequence[int],
    *,
    max_fret: int = EXERCISE_MAX_FRET,
    start_near_fret: int = 2,
    box_span: int = 5,
) -> list[tuple[int, int] | None]:
    """Fingerings for a line of absolute pitches, keeping the hand in position where it can.

    Returns one ``(string_idx, fret)`` per input pitch - or ``None`` where a pitch is simply
    not on the fretboard in this range, which is reported rather than silently octave-shifted
    into something the exercise did not ask for.

    The cost being minimised is *hand movement*, not note-to-note distance, and the two are
    not the same thing. Minimising distance per note walks a scale straight up one string,
    because each step is only a fret or two; that is the shortest path and nobody fingers a
    scale that way. What a guitarist actually does is hold the hand still and cross strings,
    so the state carried through the pass is the hand's fret window: crossing strings inside
    it is nearly free, and leaving it is what gets charged for.

    The pass is exhaustive over positions rather than greedy. A greedy walk takes the
    cheapest next step and can strand the hand where the rest of the bar is expensive;
    with at most three positions per pitch the exact answer is cheap enough to just compute.
    """
    line = [int(m) for m in midis if m is not None]
    if not line:
        return []
    span = max(2, int(box_span))

    # state -> (cost, path). The state is where the hand is *and* the box it is holding.
    states: dict[tuple[int, int, int, int], tuple[int, list[tuple[int, int] | None]]] = {}
    unreachable_prefix: list[None] = []

    for midi in line:
        options = positions_for_midi(midi, max_fret=max_fret)
        if not options:
            # Keep the line's length honest and carry the hand position across the gap.
            if not states:
                unreachable_prefix.append(None)
            else:
                states = {k: (c, path + [None]) for k, (c, path) in states.items()}
            continue

        if not states:
            for (st, fr) in options:
                lo, hi = (fr, fr) if fr else (0, span)
                states[(st, fr, lo, hi)] = (
                    abs(fr - int(start_near_fret)) + abs(st - 3),
                    [(st, fr)],
                )
            continue

        nxt: dict[tuple[int, int, int, int], tuple[int, list[tuple[int, int] | None]]] = {}
        for (st, fr) in options:
            for (ps, pf, lo, hi), (cost, path) in states.items():
                anchor = next((p for p in reversed(path) if p is not None), (ps, pf))
                reach = _reach_cost(anchor, (st, fr))
                if reach is None:
                    continue
                # Fret 0 is the nut (or the capo) and is available from any position, so an
                # open string never counts as leaving the box.
                if fr == 0 or lo <= fr <= hi:
                    new_lo, new_hi, extra = lo, hi, 0
                elif max(hi, fr) - min(lo, fr) <= span:
                    new_lo, new_hi, extra = min(lo, fr), max(hi, fr), 0
                else:
                    new_lo, new_hi = fr, fr
                    extra = _SHIFT_PENALTY
                total = cost + reach + extra
                key = (st, fr, new_lo, new_hi)
                best = nxt.get(key)
                if best is None or total < best[0]:
                    nxt[key] = (total, path + [(st, fr)])
        if not nxt:
            # No bounded route reaches this pitch; take the cheapest state and pay for the
            # leap rather than dropping a note the harmony asked for.
            cheap_key, (cheap_cost, cheap_path) = min(states.items(), key=lambda kv: kv[1][0])
            st, fr = options[0]
            nxt[(st, fr, fr, fr)] = (
                cheap_cost + MAX_CONSECUTIVE_JUMP * 4,
                cheap_path + [(st, fr)],
            )
        states = nxt

    if not states:
        return list(unreachable_prefix)
    best_path = min(states.values(), key=lambda cp: cp[0])[1]
    return unreachable_prefix + best_path


def _is_shift(prev: tuple[int, int] | None, nxt: tuple[int, int]) -> bool:
    """Whether this note moves the hand to a new position rather than reaching a finger."""
    if prev is None:
        return False
    return abs(nxt[1] - prev[1]) > 2


def build_guitar_exercise_measures(
    chords: Sequence[str],
    *,
    level: str = "Intermediate",
    mode: str = "scales",
    focus: str = "",
    key_center: str = "C",
    max_fret: int = EXERCISE_MAX_FRET,
) -> list[list[PentatonicNoteEvent]]:
    """One bar of TAB events per chord, for the existing single-note TAB renderer.

    The notes come from ``build_exercise_midis`` - the same engine the wind instruments and
    the piano use - so a scale over Am6 is the same A Dorian here as it is there. This adds
    only the fingering and the rhythmic placement.
    """
    from notation_exercise_patterns import build_exercise_midis

    chord_list = [str(c or "").strip() or "C" for c in (chords or [])]
    if not chord_list:
        return []

    lvl = str(level or "Intermediate").strip().title()
    if lvl not in LEVEL_SLOTS:
        lvl = "Intermediate"
    slots = LEVEL_SLOTS[lvl]

    bars, _patterns = build_exercise_midis(
        chord_list,
        level=lvl,
        instrument="Guitar",
        key_center=key_center,
        focus=focus,
        mode=mode,
    )

    measures: list[list[PentatonicNoteEvent]] = []
    prev_pos: tuple[int, int] | None = None
    for bar_idx, bar_midis in enumerate(bars, start=1):
        fingering = map_line_to_frets(
            bar_midis,
            max_fret=max_fret,
            start_near_fret=prev_pos[1] if prev_pos else 2,
            box_span=_box_for_level(lvl),
        )
        events: list[PentatonicNoteEvent] = []
        chord = chord_list[bar_idx - 1] if bar_idx - 1 < len(chord_list) else chord_list[-1]
        for n, (midi, pos) in enumerate(zip(bar_midis, fingering)):
            if pos is None:
                continue
            s, f = pos
            events.append(
                PentatonicNoteEvent(
                    measure=bar_idx,
                    slot=slots[n % len(slots)],
                    string_idx=s,
                    fret=f,
                    pitch_class=int(midi) % 12,
                    chord=chord,
                    position_shift=_is_shift(prev_pos, pos),
                )
            )
            prev_pos = pos
        measures.append(events)
    return measures


def validate_exercise_tab(
    measures: Sequence[Sequence[PentatonicNoteEvent]],
    *,
    max_fret: int = EXERCISE_MAX_FRET,
) -> tuple[bool, str]:
    """Playability check for a generated exercise line.

    Same two rules ``validate_pentatonic_line`` applies, with this module's higher fret
    ceiling. It is checked here rather than by calling that function because that one pins
    the pentatonic engine's 9-fret limit, which a two-octave study legitimately exceeds.
    """
    for measure in measures:
        prev: tuple[int, int] | None = None
        for ev in measure:
            if not 0 <= int(ev.fret) <= int(max_fret):
                return False, f"fret {ev.fret} out of range"
            if not 0 <= int(ev.string_idx) < NUM_STRINGS:
                return False, f"string {ev.string_idx} out of range"
            if prev is not None:
                ps, pf = prev
                if ps == int(ev.string_idx) and abs(pf - int(ev.fret)) > MAX_SAME_STRING_JUMP:
                    return (
                        False,
                        f"same-string jump {abs(pf - int(ev.fret))} frets exceeds "
                        f"{MAX_SAME_STRING_JUMP}",
                    )
            prev = (int(ev.string_idx), int(ev.fret))
    return True, "ok"

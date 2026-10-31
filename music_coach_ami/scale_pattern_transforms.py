"""AMI M1c: the musical transforms behind a scale-pattern recipe — chromatic approaches, syncopation, displacement, anticipation.

All of them work on the *concert-pitch* line the engines produced (``MusicalEvent`` tuples) and return a new line; none of them writes
notation. They are applied in a fixed order, so that each layer touches only its own dimension:

1. ``add_approaches``  - pitch only. Replaces the weak note just before a chord tone (or key tone) with its half-step neighbour; the
                         rhythm grid is untouched.
2. ``retime``          - rhythm only. Re-times the same pitches in the same order (syncopation, displacement) and never removes,
                         adds or reorders a pitch. Where a rhythm cannot hold every note (sixteenth notes have no shorter value to
                         borrow from) it refuses with the reason (``TransformUnavailable``) instead of dropping notes.
3. ``anticipate``      - only on explicit request. Plays the first note of the next chord an eighth note early.

Every transform tags the notes it adds (``tone_role`` = ``approach_below`` / ``approach_above`` / ``anticipation``), and ``verify``
re-checks the finished line from those tags alone: bar durations, that each approach note is a half step from the chord tone it
resolves to, and that each anticipation is a tone of the chord that follows.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from typing import Any, Callable, Sequence

from music_coach_ami import scale_pattern_harmony as sph
from music_coach_ami.musical_idea_engine import MusicalEvent

F = Fraction
NAMES: dict[Fraction, str] = {F(4): "whole", F(2): "half", F(1): "quarter", F(1, 2): "eighth", F(1, 4): "sixteenth"}
BEATS: dict[str, Fraction] = {v: k for k, v in NAMES.items()}
APPROACH_BELOW, APPROACH_ABOVE, ANTICIPATION = "approach_below", "approach_above", "anticipation"
SHARPS = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
FLATS = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")
# the 2-beat syncopated tile: durations in beats. Four eighths become four notes (e q s s) — same count, same span. Sixteenths have no such
# tile: eight notes in two beats can only be eight sixteenths, so a sixteenth-note pattern cannot be syncopated without losing notes.
TILES: dict[str, tuple[Fraction, ...]] = {"eighth": (F(1, 2), F(1), F(1, 4), F(1, 4))}
TILE_BEATS = F(2)


class TransformUnavailable(ValueError):
    """The transform cannot be applied to this line; the message is shown to the player."""


# ---------------------------------------------------------------- timed events


def is_rest(ev: MusicalEvent) -> bool:
    return str(ev.duration or "").lower().startswith("rest") or not str(ev.spelled or "").strip()


def dur_of(ev: MusicalEvent) -> Fraction:
    name = str(ev.duration or "").lower()
    name = name[5:] if name.startswith("rest_") else name
    if name not in BEATS:
        raise TransformUnavailable(f"a {name or 'note'} value can't be re-timed")
    return BEATS[name]


def per_bar_of(meter: str) -> Fraction:
    return F(3) if (meter or "4/4") == "3/4" else F(4)


def onset_of(ev: MusicalEvent, per_bar: Fraction) -> Fraction:
    return per_bar * int(ev.bar_index) + F(str(ev.beat)).limit_denominator(8)


def _midi(ev: MusicalEvent) -> int:
    return sph.midi_of(ev.spelled, int(ev.octave))


def _place(ev: MusicalEvent, onset: Fraction, dur: Fraction, per_bar: Fraction, **changes: Any) -> MusicalEvent:
    if dur not in NAMES:
        raise TransformUnavailable(f"a duration of {dur} beats can't be notated")
    bar = int(onset // per_bar)
    beat = onset - per_bar * bar
    if beat + dur > per_bar:
        raise TransformUnavailable("a note would cross the bar line")
    name = NAMES[dur]
    rest = is_rest(ev) or str(changes.get("duration", "")).startswith("rest")
    return replace(ev, bar_index=bar, beat=float(beat), duration=f"rest_{name}" if rest else name, **{k: v for k, v in changes.items() if k != "duration"})


# ---------------------------------------------------------------- 1. chromatic approaches


def _neighbour(target_midi: int, below: bool) -> tuple[str, int, int]:
    """(spelling, octave, midi) of the half-step neighbour: sharps rising to the target, flats falling to it, naturals where the neighbour is one."""
    midi = target_midi - 1 if below else target_midi + 1
    name = (SHARPS if below else FLATS)[midi % 12]
    return name, sph.octave_for(name, midi), midi


def add_approaches(
    events: Sequence[MusicalEvent], *, per_bar: Fraction, mode: str, density: int, is_target: Callable[[MusicalEvent], bool],
    segment_starts: set[Fraction], bounds: tuple[int, int],
) -> tuple[list[MusicalEvent], list[dict[str, Any]]]:
    """Replace the note before each eligible target with a half-step approach to it.

    A target is a chord tone (chord-following) or a tonic-triad tone of the key (key-based) that falls on a strong beat — beats 1 and 3 and
    every chord change at density 1, every beat at density 2. The approach comes from the side the line was already moving from
    (``mode`` "both") or from the side the player named. Nothing is added where no such target exists.
    """
    out = list(events)
    applied: list[dict[str, Any]] = []
    used: set[int] = set()
    for i in range(1, len(out)):
        tgt, prev = out[i], out[i - 1]
        if i in used or (i - 1) in used or is_rest(tgt) or is_rest(prev) or not is_target(tgt):
            continue
        at = onset_of(tgt, per_bar)
        in_bar = at - per_bar * int(tgt.bar_index)
        strong = in_bar.denominator == 1 and (density >= 2 or in_bar % 2 == 0 or at in segment_starts)
        if not strong:
            continue
        tm, pm = _midi(tgt), _midi(prev)
        below = mode == "below" or (mode == "both" and pm <= tm)
        if mode == "above":
            below = False
        name, octave, midi = _neighbour(tm, below)
        if not (bounds[0] <= midi <= bounds[1]) or midi == pm:
            continue
        out[i - 1] = replace(prev, spelled=name, octave=octave, scale_degree=None, pitch_class=sph.pc_of(name),
                             tone_role=APPROACH_BELOW if below else APPROACH_ABOVE)
        applied.append({"index": i - 1, "target_index": i, "direction": "below" if below else "above"})
        used.update((i - 1, i))
    return out, applied


def respell_approaches(events: Sequence[MusicalEvent]) -> list[MusicalEvent]:
    """Re-spell approach notes in the staff the player reads (written pitch): a transposed approach keeps its exact pitch but is written the way
    an approach is written — sharps rising to the target, flats falling to it — instead of whatever the transposition happens to give."""
    out = list(events)
    for i, e in enumerate(out):
        if e.tone_role in (APPROACH_BELOW, APPROACH_ABOVE) and not is_rest(e):
            midi = _midi(e)
            name = (SHARPS if e.tone_role == APPROACH_BELOW else FLATS)[midi % 12]
            out[i] = replace(e, spelled=name, octave=sph.octave_for(name, midi), pitch_class=sph.pc_of(name))
    return out


# ---------------------------------------------------------------- 2. rhythm: syncopation and displacement


def retime(
    events: Sequence[MusicalEvent], *, per_bar: Fraction, pieces: Sequence[tuple[Fraction, Fraction]], level: int, displaced: bool,
) -> tuple[list[MusicalEvent], int]:
    """Re-time the same pitches, in the same order, inside each ``(start, length)`` piece (a chord segment cut at the bar lines).

    ``level`` 1 syncopates every other two-beat tile, 2 syncopates all of them; ``displaced`` starts each piece one subdivision late with
    a rest, and makes the room by halving the last note(s) of the piece (a pick-up into what follows). Every pitch survives: the second value
    returned is always 0 (kept for callers), and a rhythm that cannot hold every note raises ``TransformUnavailable`` with the reason.
    """
    timed = sorted(((onset_of(e, per_bar), e) for e in events), key=lambda t: t[0])
    out: list[MusicalEvent] = []
    groups = [[e for at, e in timed if start <= at < start + length] for start, length in pieces]
    arrived: set[int] = set()          # pieces that begin with the approach note into them (displacement)
    if displaced:
        # a rest must never sit between an approach note and the note it resolves to: the approach travels with its target, taking the
        # late-start slot of the next piece
        for gi in range(len(groups) - 1):
            g, nxt = groups[gi], groups[gi + 1]
            if g and nxt and g[-1].tone_role in (APPROACH_BELOW, APPROACH_ABOVE):
                groups[gi + 1].insert(0, replace(g.pop(), chord=nxt[0].chord))
                arrived.add(gi + 1)
    for gi, ((start, length), group) in enumerate(zip(pieces, groups)):
        if not group:
            continue
        unit = dur_of(group[0])
        if any(dur_of(e) != unit or is_rest(e) for e in group):
            out.extend(group)                                # an already re-timed piece: leave it exactly as it is
            continue
        unit_name = NAMES[unit]
        if level and unit_name not in TILES:
            if unit_name == "sixteenth":
                raise TransformUnavailable(
                    "this pattern is already in sixteenth notes, the shortest value I write, so every note fills its beat exactly and there is no room to shift "
                    "one without taking another out. Your notes stay as they are; make it one step easier (eighth notes) and I can syncopate it")
            raise TransformUnavailable("syncopation needs eighth notes or faster — make the pattern harder first, then ask for syncopation")
        layout: list[tuple[Fraction, bool]] = []          # (duration, is_rest)
        pos = F(0)
        tile_no = 0
        while pos < length:
            remaining = length - pos
            if unit_name in TILES and remaining >= TILE_BEATS and unit == F(1, 2):
                if level >= 2 or (level == 1 and tile_no % 2 == 0):
                    layout.extend((d, False) for d in TILES[unit_name])
                else:
                    layout.extend((unit, False) for _ in range(int(TILE_BEATS / unit)))
                pos += TILE_BEATS
                tile_no += 1
            elif remaining >= unit:
                layout.append((unit, False))
                pos += unit
            else:
                layout.append((remaining, False))          # a remainder shorter than the subdivision keeps its own value
                pos += remaining
        delta = len(group) - len(layout)          # a carried-in approach note adds one, a carried-out one removes one
        if delta == 0 and displaced and gi not in arrived:
            layout = _displace(layout, unit, lead_is_rest=True)
        elif delta == -1 and displaced:
            layout = [(layout[0][0], True)] + layout[1:]          # the first slot becomes the late-start rest; everything else keeps its place
        elif delta == 1 and gi in arrived:
            layout = _displace(layout, unit, lead_is_rest=False)  # the carried-in approach takes the first slot
        elif delta != 0:
            raise TransformUnavailable("this chord segment can't carry the same notes in that rhythm")
        cursor = start
        template = group[0]
        pool = list(group)
        for d, rest in layout:
            if rest:
                out.append(_place(replace(template, spelled="", octave=0, scale_degree=None, pitch_class=None, tone_role="", articulation=""),
                                  cursor, d, per_bar, duration=f"rest_{NAMES[d]}"))
            else:
                out.append(_place(pool.pop(0), cursor, d, per_bar))
            cursor += d
        if pool:
            raise TransformUnavailable("this rhythm would leave out some of your notes")
    return out, 0


def _displace(layout: list[tuple[Fraction, bool]], unit: Fraction, *, lead_is_rest: bool) -> list[tuple[Fraction, bool]]:
    """Add one ``unit`` slot at the front (a late-start rest, or the approach note carried in) and keep all the notes by halving the last ones
    (a pick-up into what follows) until the piece is the same length again. Raises when no note can be halved to a written value."""
    out = list(layout)
    need = unit
    saved = F(0)
    for i in range(len(out) - 1, -1, -1):
        d, is_rest_ = out[i]
        half = d / 2
        if not is_rest_ and half in NAMES and half <= need - saved:
            out[i] = (half, False)
            saved += half
        if saved == need:
            break
    if saved != need:
        raise TransformUnavailable(
            "starting this rhythm late would need a note shorter than a sixteenth to keep all of your notes. "
            "Your notes stay as they are; an eighth-note pattern can be displaced")
    out.insert(0, (unit, lead_is_rest))
    return out


def anticipate(
    events: Sequence[MusicalEvent], *, per_bar: Fraction, boundaries: Sequence[tuple[Fraction, str, str]],
) -> tuple[list[MusicalEvent], list[dict[str, Any]]]:
    """Play the first note of each new chord an eighth note early.

    ``boundaries`` are (onset of the chord change, chord before, chord after) for real changes only. The note is a copy of the next chord's
    first pitch, written in the old chord's time (its ``chord`` stays the old chord, so the chord symbol still changes where the chart
    changes). Whatever was sounding in that eighth is replaced; a longer note that straddles it is shortened to end where the anticipation
    starts. A boundary where that can't be notated is skipped and reported.
    """
    items = sorted(((onset_of(e, per_bar), e) for e in events), key=lambda t: t[0])
    records: list[dict[str, Any]] = []
    protect_until = F(-1)              # the arrival note of the previous anticipation must survive the next one
    for b, prev_chord, next_chord in boundaries:
        s = b - F(1, 2)
        nxt = next(((at, e) for at, e in items if at >= b and not is_rest(e) and e.tone_role not in (APPROACH_BELOW, APPROACH_ABOVE)), None)
        if nxt is None or s < 0:
            records.append({"onset": b, "skipped": "there is no following note to anticipate"})
            continue
        if s < protect_until:
            records.append({"onset": b, "skipped": "the chord before it is too short to anticipate without losing the note the previous anticipation leads to"})
            continue
        cut = [(at, e) for at, e in items if s <= at < b]
        order = [e for _at, e in items]
        lost_target = any(e.tone_role not in (APPROACH_BELOW, APPROACH_ABOVE) and i > 0 and order[i - 1].tone_role in (APPROACH_BELOW, APPROACH_ABOVE)
                          and order[i - 1] not in [c for _a, c in cut] for i, e in enumerate(order) if any(e is c for _a, c in cut))
        if lost_target:
            records.append({"onset": b, "skipped": "the last note before it is the target of a chromatic approach"})
            continue
        straddle = [(at, e) for at, e in items if at < s < at + dur_of(e)]
        keep = [(at, e) for at, e in items if not (s <= at < b)]
        if straddle:
            at0, e0 = straddle[-1]
            if (s - at0) not in NAMES:
                records.append({"onset": b, "skipped": "the note before it can't be shortened to a notatable value"})
                continue
            keep = [(at, e if e is not e0 else _place(e, at0, s - at0, per_bar)) for at, e in keep]
        base = nxt[1]
        ant = _place(replace(base, chord=prev_chord, scale_degree=None, tone_role=ANTICIPATION, cell_index=None, articulation=""), s, F(1, 2), per_bar)
        items = sorted(keep + [(s, ant)], key=lambda t: t[0])
        protect_until = nxt[0] + dur_of(nxt[1])
        records.append({"onset": b, "from_chord": prev_chord, "to_chord": next_chord, "replaced": len(cut), "note": f"{base.spelled}"})
    return [e for _at, e in items], records


# ---------------------------------------------------------------- verification


def verify(
    events: Sequence[MusicalEvent], *, per_bar: Fraction, bars: int, is_target: Callable[[MusicalEvent], bool],
    chord_pcs: Callable[[str], set[int]] | None,
) -> list[str]:
    """Re-check a finished line from the notes and their tags alone. Returns the problems found (empty when the line is sound)."""
    errors: list[str] = []
    ordered = sorted(events, key=lambda e: onset_of(e, per_bar))
    cursor = F(0)
    for e in ordered:
        try:
            at, d = onset_of(e, per_bar), dur_of(e)
        except TransformUnavailable as exc:
            errors.append(str(exc))
            continue
        if at != cursor:
            errors.append(f"gap_or_overlap_at_{at}")
            cursor = at
        bar_end = per_bar * (int(e.bar_index) + 1)
        if at + d > bar_end:
            errors.append(f"note_crosses_bar_{e.bar_index + 1}")
        cursor = at + d
    if cursor != per_bar * int(bars):
        errors.append(f"line_is_{cursor}_beats_not_{per_bar * int(bars)}")
    for i, e in enumerate(ordered):
        role = e.tone_role
        if role in (APPROACH_BELOW, APPROACH_ABOVE):
            nxt = ordered[i + 1] if i + 1 < len(ordered) else None
            if nxt is None or is_rest(nxt):
                errors.append(f"approach_{e.spelled}_has_no_target")
                continue
            diff = _midi(nxt) - _midi(e)
            if diff != (1 if role == APPROACH_BELOW else -1):
                errors.append(f"approach_{e.spelled}_is_not_a_half_step_{'below' if role == APPROACH_BELOW else 'above'}_{nxt.spelled}")
            if not is_target(nxt):
                errors.append(f"approach_{e.spelled}_resolves_to_a_non_target_{nxt.spelled}")
        elif role == ANTICIPATION:
            nxt = next((x for x in ordered[i + 1:] if not is_rest(x) and x.tone_role not in (APPROACH_BELOW, APPROACH_ABOVE)), None)
            if dur_of(e) != F(1, 2):
                errors.append("anticipation_is_not_an_eighth")
            if nxt is None or _midi(nxt) != _midi(e):
                errors.append(f"anticipation_{e.spelled}_is_not_the_note_that_follows")
            elif chord_pcs is not None:
                if nxt.chord == e.chord:
                    errors.append("anticipation_without_a_chord_change")
                elif sph.pc_of(e.spelled) not in chord_pcs(nxt.chord):
                    errors.append(f"anticipation_{e.spelled}_is_not_in_{nxt.chord}")
    return errors[:6]


def facts(events: Sequence[MusicalEvent], *, per_bar: Fraction) -> dict[str, Any]:
    """What the transforms did, read back from the tags: for the explanation the player sees."""
    ordered = sorted(events, key=lambda e: onset_of(e, per_bar))
    approaches: list[dict[str, Any]] = []
    anticipations: list[dict[str, Any]] = []
    for i, e in enumerate(ordered):
        nxt = next((x for x in ordered[i + 1:] if not is_rest(x)), None)
        where = {"bar": int(e.bar_index) + 1, "beat": f"{float(e.beat) + 1:g}"}
        if e.tone_role in (APPROACH_BELOW, APPROACH_ABOVE) and nxt is not None:
            approaches.append({**where, "note": e.spelled, "target": nxt.spelled, "chord": nxt.chord, "direction": "below" if e.tone_role == APPROACH_BELOW else "above"})
        elif e.tone_role == ANTICIPATION and nxt is not None:
            anticipations.append({**where, "note": e.spelled, "from_chord": e.chord, "to_chord": nxt.chord})
    rests = sum(1 for e in ordered if is_rest(e))
    offbeat_long = sum(1 for e in ordered if not is_rest(e) and dur_of(e) >= 1 and (onset_of(e, per_bar) % 1) != 0)
    return {"approaches": approaches, "anticipations": anticipations, "rests": rests, "offbeat_long_notes": offbeat_long,
            "notes": sum(1 for e in ordered if not is_rest(e))}

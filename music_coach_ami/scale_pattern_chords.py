"""A scale pattern that follows the chord changes.

The harmony is the chart's own timeline (``scale_pattern_harmony.timeline_segments``): each chord segment gets the scale that chord
calls for, and the pattern cell (1-2-3-4 by default) is run through that scale from the chord's root, so the line changes scale where
the chord changes — mid-bar for a split bar. The line is built in concert pitch inside the instrument's sounding window and written
for the instrument by an exact transposition (octave included), so concert and written pitch always differ by one constant.

Chord tones are marked as such; every other note is a note of the chord's own scale. No chromatic approach or passing note outside
the scale is added, so none is claimed.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from music_coach_ami import scale_pattern_harmony as sph
from music_coach_ami.musical_idea_engine import MusicalEvent, MusicalIdeaComposition, _degree_cycle, _unit_duration, generation_window
from music_coach_ami.notation_profile import apply_register_override, notation_profile_for_instrument

SUPPORTED_METERS = ("4/4", "3/4")
_DUR_BEATS = {"whole": Fraction(4), "half": Fraction(2), "quarter": Fraction(1), "eighth": Fraction(1, 2), "sixteenth": Fraction(1, 4),
              "triplet_eighth": Fraction(1, 3)}
_TOLERANCE = 2          # semitones either side of the window, the same tolerance the engine's own range check allows
_FILL = (("half", Fraction(2)), ("quarter", Fraction(1)), ("eighth", Fraction(1, 2)), ("sixteenth", Fraction(1, 4)))


class ChordFollowingUnavailable(ValueError):
    """The request cannot be answered with a chord-following pattern; the message says why (and is shown to the player)."""


@dataclass
class ChordFollowing:
    composition: MusicalIdeaComposition          # concert pitch
    segments: list[sph.Segment]
    scales: dict[str, sph.ChordScale]            # concert chord symbol -> its scale
    key: sph.KeyScale
    window: tuple[int, int]                      # concert midi window the line was built in


def _fill(beats: Fraction, unit: str) -> list[str]:
    unit_beats = _DUR_BEATS[unit]
    n = int(beats // unit_beats)
    out = [unit] * n
    rest = beats - unit_beats * n
    if rest and unit == "triplet_eighth":
        raise ChordFollowingUnavailable("a chord change that does not fall on a beat can't be filled with triplets")
    for name, value in _FILL:
        while rest >= value:
            out.append(name)
            rest -= value
    if rest:
        raise ChordFollowingUnavailable("a chord change falls between the note values I can write for this rhythm")
    return out


def _nearest(spelled: str, target: int, low: int, high: int) -> tuple[int, int]:
    """(octave, midi) of ``spelled`` inside [low, high] nearest ``target``; the higher one on a tie."""
    best: tuple[int, int] | None = None
    for octave in range(0, 9):
        midi = sph.midi_of(spelled, octave)
        if low <= midi <= high and (best is None or (abs(midi - target), -midi) < (abs(best[1] - target), -best[1])):
            best = (octave, midi)
    if best is None:
        raise ChordFollowingUnavailable(f"{spelled} has no place inside this instrument's comfortable range")
    return best


def _place_cell(spelled: list[str], target: int, low: int, high: int, hard: tuple[int, int]) -> list[tuple[int, int]]:
    """Octaves for one cell so that the whole cell sits inside [low, high] with no octave leap inside it: the anchor is the candidate
    nearest ``target`` whose cell fits, and each later note is the one nearest the note before it."""
    lo, hi = max(low - _TOLERANCE, hard[0]), min(high + _TOLERANCE, hard[1])
    anchors = [(o, sph.midi_of(spelled[0], o)) for o in range(0, 9) if lo <= sph.midi_of(spelled[0], o) <= hi]
    anchors.sort(key=lambda om: (abs(om[1] - target), -om[1]))
    for octave, midi in anchors:
        path = [(octave, midi)]
        for note in spelled[1:]:
            prev = path[-1][1]
            options = [(o, sph.midi_of(note, o)) for o in range(0, 9)]
            path.append(min(options, key=lambda om: (abs(om[1] - prev), -om[1])))
        if all(lo <= m <= hi for _o, m in path):
            return path
    raise ChordFollowingUnavailable(f"a {len(spelled)}-note cell on {spelled[0]} does not fit this instrument's comfortable range")


def generate(idea: Any, section_chords: list[str], key: sph.KeyScale, *, notation_instrument: str, offset: int, bars: int) -> ChordFollowing:
    meter = str(idea.meter or "4/4")
    if meter not in SUPPORTED_METERS:
        raise ChordFollowingUnavailable(f"chord-following patterns are available in 4/4 and 3/4, not {meter}")
    try:
        segments = sph.timeline_segments(section_chords, bars, meter)
    except ValueError as exc:
        raise ChordFollowingUnavailable(str(exc)) from exc
    scales: dict[str, sph.ChordScale] = {}
    for seg in segments:
        if seg.chord not in scales:
            try:
                scales[seg.chord] = sph.chord_scale_for(seg.chord, key)
            except ValueError as exc:
                raise ChordFollowingUnavailable(str(exc)) from exc
    profile = apply_register_override(notation_profile_for_instrument(notation_instrument), idea.register)
    low_w, high_w, _prefer = generation_window(profile, instrument=notation_instrument, register=idea.register, object_type="pattern",
                                               difficulty=idea.difficulty or idea.level)
    low_w, high_w = sph.written_window(notation_instrument, low_w, high_w)
    low, high = low_w - offset, high_w - offset          # the sounding window that writes inside the written window
    playable = sph.playable_written_range(notation_instrument)
    hard = (playable[0] - offset, playable[1] - offset) if playable else (-1000, 1000)   # what the horn can actually sound
    unit = _unit_duration(idea)
    cell = _degree_cycle(idea.interval_pattern or "1-2-3-4")
    descending = (idea.direction or "").strip().lower() == "descending"
    events: list[MusicalEvent] = []
    prev_midi: int | None = None
    cell_no = 0
    for seg in segments:
        scale = scales[seg.chord]
        roles = sph.chord_tone_roles(seg.chord)
        names = _fill(seg.beats, unit)
        cursor = seg.beat
        degrees: list[int] = []
        k = 0
        while len(degrees) < len(names):
            root_idx = -k if descending else k                       # the cell's anchor walks the scale from the chord's root
            for d in cell:
                step = root_idx - (d - 1) if descending else root_idx + (d - 1)
                degrees.append((step % 7) + 1)
            k += 1
        picked = degrees[: len(names)]
        for start in range(0, len(names), len(cell)):
            group = [(names[k], picked[k]) for k in range(start, min(start + len(cell), len(names)))]
            spelled_group = [scale.notes[deg - 1] for _d, deg in group]
            target = (low + 4) if prev_midi is None else prev_midi + (-2 if descending else 2)
            path = _place_cell(spelled_group, target, low, high, hard)
            for (dur, degree), spelled, (octave, midi) in zip(group, spelled_group, path):
                events.append(MusicalEvent(
                    spelled=spelled, octave=octave, duration=dur, bar_index=seg.bar, beat=float(cursor), articulation=idea.articulation,
                    scale_degree=degree, pitch_class=sph.pc_of(spelled), chord=seg.chord, role="pattern", cell_index=cell_no,
                    domain="concert", tone_role="chord_tone" if sph.pc_of(spelled) in roles else "scale",
                ))
                prev_midi = midi
                cursor += _DUR_BEATS[dur]
            cell_no += 1
    errors = _check(events, segments, scales, low, high, meter, hard)
    comp = MusicalIdeaComposition(
        events=tuple(events), reference_key=key.token, meter=meter, bars=int(bars), object_type="pattern",
        style=f"chord-following {key.tonality}", notation_profile=profile, strategy=f"chord_following:{unit}:{idea.interval_pattern or 'scalar'}",
        tonic=key.tonic, tonality=key.tonality, scale_spelling=(), validation_errors=tuple(errors), validation_ok=not errors,
    )
    return ChordFollowing(composition=comp, segments=segments, scales=scales, key=key, window=(low, high))


def _check(events: list[MusicalEvent], segments: list[sph.Segment], scales: dict[str, sph.ChordScale], low: int, high: int, meter: str,
           hard: tuple[int, int]) -> list[str]:
    errors: list[str] = []
    per_bar = sph._beats_per_bar(meter)
    by_bar: dict[int, Fraction] = {}
    for ev in events:
        in_scale = {sph.pc_of(n) for n in scales[ev.chord].notes}
        if sph.pc_of(ev.spelled) not in in_scale:
            errors.append(f"out_of_scale:{ev.spelled}@{ev.chord}")
        midi = sph.midi_of(ev.spelled, int(ev.octave))
        if not (max(low - _TOLERANCE, hard[0]) <= midi <= min(high + _TOLERANCE, hard[1])):
            errors.append(f"out_of_window:{ev.spelled}{ev.octave}")
        by_bar[ev.bar_index] = by_bar.get(ev.bar_index, Fraction(0)) + _DUR_BEATS[ev.duration]
    for seg in segments:
        if seg.bar not in by_bar:
            errors.append(f"missing_bar_{seg.bar}")
    for bar, total in by_bar.items():
        if total != per_bar:
            errors.append(f"bar_{bar}_has_{total}_beats")
    return errors[:6]


def written_composition(cf: ChordFollowing, offset: int, *, written_key: str, semitones_mod12: int) -> MusicalIdeaComposition:
    """The line written for the instrument: every note ``offset`` semitones above its sounding pitch, chord symbols transposed to match."""
    from dataclasses import replace

    from music_theory import transpose_chord

    def chord_fn(chord: str) -> str:
        return transpose_chord(chord, int(semitones_mod12), reference_key=written_key or cf.key.token) if semitones_mod12 else chord

    comp = cf.composition
    events = sph.exact_written_events(comp.events, offset, chord_fn) if offset else [replace(e, domain="written") for e in comp.events]
    wk = sph._token_parts(written_key) if written_key else None
    tonic, tonality = wk if wk else (comp.tonic, comp.tonality)
    return replace(comp, events=tuple(events), tonic=tonic, tonality=tonality, reference_key=written_key or comp.reference_key)


def key_based_written(concert: MusicalIdeaComposition, offset: int, *, written_key: str) -> MusicalIdeaComposition:
    """A key-based pattern written for the instrument by exact transposition: each note keeps its scale degree (so it is spelled in the
    written key's scale, as the legacy writer does) and sits exactly ``offset`` semitones above its sounding pitch, octave included."""
    from dataclasses import replace

    from music_coach_ami.musical_idea_engine import authoritative_scale_degrees

    wk = sph._token_parts(written_key) if written_key else None
    tonic = wk[0] if wk else concert.tonic
    tonality = concert.tonality
    scale = authoritative_scale_degrees(tonic, tonality)
    events = []
    for ev in concert.events:
        if not str(ev.spelled or "").strip() or str(ev.duration or "").lower().startswith("rest"):
            events.append(replace(ev, domain="written"))
            continue
        target = sph.midi_of(ev.spelled, int(ev.octave)) + offset
        if ev.scale_degree and len(scale) >= 7:
            spelled = scale[(int(ev.scale_degree) - 1) % len(scale)]
        else:
            spelled = sph.transpose_spelled(ev.spelled, offset)
        events.append(replace(ev, spelled=spelled, octave=sph.octave_for(spelled, target), pitch_class=sph.pc_of(spelled), domain="written"))
    return replace(concert, events=tuple(events), tonic=tonic, reference_key=written_key or concert.reference_key,
                   scale_spelling=tuple(scale))

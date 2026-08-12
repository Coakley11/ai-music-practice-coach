"""Structured musical-idea generators (patterns, licks, phrases) → events → ABC."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from music_coach_ami.musical_idea_request import MusicalIdeaRequest
from music_coach_ami.notation_profile import (
    NotationProfile,
    apply_register_override,
    notation_profile_for_instrument,
)


@dataclass(frozen=True)
class MusicalEvent:
    spelled: str
    octave: int
    duration: str  # whole|half|quarter|eighth|triplet_eighth|sixteenth
    bar_index: int
    beat: float
    articulation: str = ""
    scale_degree: int | None = None
    chord: str = ""
    role: str = ""


@dataclass(frozen=True)
class MusicalIdeaComposition:
    events: tuple[MusicalEvent, ...]
    reference_key: str
    meter: str
    bars: int
    object_type: str
    style: str
    notation_profile: NotationProfile
    strategy: str = ""


def _clean(text: object) -> str:
    return str(text or "").strip()


def _level(idea: MusicalIdeaRequest) -> str:
    low = _clean(idea.difficulty or idea.level).lower()
    if "advanced" in low or "hard" in low:
        return "advanced"
    if "begin" in low or "easy" in low or "simple" in low:
        return "beginner"
    return "intermediate"


def _beats_per_bar(meter: str) -> float:
    m = _clean(meter) or "4/4"
    if m == "3/4":
        return 3.0
    if m == "6/8":
        return 3.0  # compound: treat as 3 dotted-quarter feel in packing units of eighth*2
    return 4.0


def _dur_beats(duration: str, meter: str = "4/4") -> float:
    if duration == "whole":
        return _beats_per_bar(meter)
    if duration == "half":
        return 2.0
    if duration == "quarter":
        return 1.0
    if duration == "eighth":
        return 0.5
    if duration == "triplet_eighth":
        return 1.0 / 3.0
    if duration == "sixteenth":
        return 0.25
    return 1.0


def _unit_duration(idea: MusicalIdeaRequest) -> str:
    r = _clean(idea.rhythm).lower()
    if r == "triplet":
        return "triplet_eighth"
    if r == "sixteenth":
        return "sixteenth"
    if r == "eighth":
        return "eighth"
    if r == "half":
        return "half"
    if r == "whole":
        return "whole"
    if r == "sparse":
        return "half"
    if r == "busy":
        return "sixteenth"
    lvl = _level(idea)
    if idea.tempo_bpm and idea.tempo_bpm >= 140 and lvl == "beginner":
        return "quarter"
    if lvl == "advanced":
        return "eighth" if r != "quarter" else "quarter"
    if lvl == "beginner":
        return "quarter"
    return "eighth"


def _spell_scale(tonic: str, tonality: str) -> list[str]:
    from music_coach_ami.scale_engine import spell_scale_degrees_for_direction

    scale_type = _clean(tonality) or "major"
    notes = spell_scale_degrees_for_direction(tonic, scale_type, "ascending")
    return [n for n in notes if n]


def _degree_cycle(pattern: str) -> list[int]:
    p = _clean(pattern).lower()
    if p == "1-3-2-4":
        return [1, 3, 2, 4]
    if p == "1-3-4-2":
        return [1, 3, 4, 2]
    if p in {"1-2-3-4", "fourths"}:  # four-note cell default
        if p == "fourths":
            return [1, 4]
        return [1, 2, 3, 4]
    if p == "1-2-3":
        return [1, 2, 3]
    if p in {"thirds", "broken_thirds"}:
        return [1, 3]
    if p == "fifths":
        return [1, 5]
    return [1, 2, 3, 4]


def _place_degree(
    scale: Sequence[str],
    degree: int,
    *,
    prefer_midi: int,
    profile: NotationProfile,
    reference_key: str,
) -> tuple[str, int, int]:
    from music_theory import midi_from_spelled_note, pitch_class_from_spelled_note, spell_note_in_key

    idx = (int(degree) - 1) % max(1, len(scale) - 1) if len(scale) > 1 else 0
    # Include octave wrap using tonic repeats at end when present.
    note = scale[idx] if idx < len(scale) else scale[0]
    pc = pitch_class_from_spelled_note(note)
    spelled = spell_note_in_key(pc, reference_key)
    low, high = profile.midi_low, profile.midi_high
    best_oct = profile.written_octave
    best_midi = midi_from_spelled_note(spelled, octave=best_oct)
    best_dist = abs(best_midi - prefer_midi)
    for octv in range(1, 8):
        midi = midi_from_spelled_note(spelled, octave=octv)
        if midi < low - 2 or midi > high + 2:
            continue
        dist = abs(midi - prefer_midi)
        if dist < best_dist or (low <= midi <= high and not (low <= best_midi <= high)):
            best_dist = dist
            best_oct = octv
            best_midi = midi
    return spelled, best_oct, int(best_midi)


def _pack_events(
    notes: list[tuple[str, int, int | None, str]],
    *,
    bars: int,
    meter: str,
    unit: str,
    articulation: str,
) -> list[MusicalEvent]:
    events: list[MusicalEvent] = []
    beats_bar = _beats_per_bar(meter)
    unit_beats = _dur_beats(unit, meter)
    cursor = 0.0
    i = 0
    while cursor < bars * beats_bar and i < len(notes) * 8:
        bar = int(cursor // beats_bar)
        beat = cursor % beats_bar
        spelled, octv, deg, role = notes[i % len(notes)]
        # Don't overflow the bar — shorten last unit if needed.
        remain = beats_bar - beat
        dur = unit
        if unit_beats > remain + 1e-6:
            if remain >= 2.0 - 1e-6:
                dur = "half"
            elif remain >= 1.0 - 1e-6:
                dur = "quarter"
            elif remain >= 0.5 - 1e-6:
                dur = "eighth"
            else:
                cursor = (bar + 1) * beats_bar
                continue
        events.append(
            MusicalEvent(
                spelled=spelled,
                octave=octv,
                duration=dur,
                bar_index=bar,
                beat=float(beat),
                articulation=articulation,
                scale_degree=deg,
                role=role,
            )
        )
        cursor += _dur_beats(dur, meter)
        i += 1
        if len(events) > bars * 32:
            break
    # Ensure we filled requested bars with at least a rest-free skeleton.
    if events and events[-1].bar_index < bars - 1:
        # Pad with last pitch as quarters.
        last = events[-1]
        cursor = (events[-1].bar_index + 1) * beats_bar
        while cursor < bars * beats_bar:
            bar = int(cursor // beats_bar)
            events.append(
                MusicalEvent(
                    spelled=last.spelled,
                    octave=last.octave,
                    duration="quarter",
                    bar_index=bar,
                    beat=float(cursor % beats_bar),
                    articulation=articulation,
                    scale_degree=last.scale_degree,
                    role="pad",
                )
            )
            cursor += 1.0
    return events


def generate_scale_pattern(
    idea: MusicalIdeaRequest,
    *,
    notation_instrument: str,
) -> MusicalIdeaComposition:
    tonic = _clean(idea.explicit_key) or "C"
    tonality = _clean(idea.tonality) or "major"
    scale = _spell_scale(tonic, tonality)
    if len(scale) < 2:
        scale = [tonic, tonic]
    profile = apply_register_override(
        notation_profile_for_instrument(notation_instrument),
        idea.register,
    )
    bars = int(idea.bars or 4)
    unit = _unit_duration(idea)
    direction = _clean(idea.direction) or "ascending"
    cell = _degree_cycle(idea.interval_pattern or "1-2-3-4")
    prefer = (profile.midi_low + profile.midi_high) // 2
    notes: list[tuple[str, int, int | None, str]] = []

    def emit_degrees(degrees: list[int], *, role: str) -> None:
        nonlocal prefer
        for deg in degrees:
            spelled, octv, midi = _place_degree(
                scale, deg, prefer_midi=prefer, profile=profile, reference_key=tonic
            )
            notes.append((spelled, octv, deg, role))
            prefer = midi + (2 if direction != "descending" else -4)

    if direction == "descending":
        # Walk cells down the scale.
        start = len(scale) - 1
        for root_deg in range(start, 0, -1):
            shifted = [((d - 1 + root_deg - 1) % (len(scale) - 1)) + 1 for d in cell]
            emit_degrees(shifted, role="pattern")
    elif direction == "both":
        for root_deg in range(1, len(scale)):
            shifted = [((d - 1 + root_deg - 1) % (len(scale) - 1)) + 1 for d in cell]
            emit_degrees(shifted, role="asc")
        for root_deg in range(len(scale) - 1, 0, -1):
            shifted = [((d - 1 + root_deg - 1) % (len(scale) - 1)) + 1 for d in cell]
            emit_degrees(shifted, role="desc")
    else:
        for root_deg in range(1, len(scale)):
            shifted = [((d - 1 + root_deg - 1) % (len(scale) - 1)) + 1 for d in cell]
            emit_degrees(shifted, role="pattern")

    events = _pack_events(
        notes,
        bars=bars,
        meter=idea.meter or "4/4",
        unit=unit,
        articulation=idea.articulation,
    )
    return MusicalIdeaComposition(
        events=tuple(events),
        reference_key=tonic,
        meter=idea.meter or "4/4",
        bars=bars,
        object_type="pattern",
        style=idea.style or tonality,
        notation_profile=profile,
        strategy=f"scale_pattern:{direction}:{idea.interval_pattern or 'scalar'}",
    )


def generate_lick(
    idea: MusicalIdeaRequest,
    *,
    notation_instrument: str,
) -> MusicalIdeaComposition:
    """Idiomatic short line — not a mechanical scale dump."""
    tonic = _clean(idea.explicit_key) or "C"
    tonality = _clean(idea.tonality) or ("blues" if idea.style == "blues" else "natural minor")
    if idea.style == "blues" and not idea.tonality:
        tonality = "blues"
    scale = _spell_scale(tonic, tonality)
    profile = apply_register_override(
        notation_profile_for_instrument(notation_instrument),
        idea.register,
    )
    bars = int(idea.bars or 4)
    lvl = _level(idea)
    direction = _clean(idea.direction) or "arch"
    prefer = (profile.midi_low + profile.midi_high) // 2

    # Contour templates as scale degrees (1-based, may exceed octave).
    if idea.style == "blues" or tonality == "blues":
        templates = {
            "beginner": [1, 1, 3, 1, 5, 3, 1, 1],
            "intermediate": [1, 3, 5, 6, 5, 3, 1, 5, 3, 1],
            "advanced": [1, 2, 3, 5, 6, 5, 3, 2, 1, 3, 5, 1],
        }
    elif idea.style in {"jazz", "bebop"}:
        templates = {
            "beginner": [1, 2, 3, 5, 3, 2, 1, 1],
            "intermediate": [1, 2, 3, 5, 6, 5, 3, 2, 1, 7, 1],
            "advanced": [1, 7, 1, 2, 3, 5, 4, 3, 2, 1, 3, 5],
        }
    else:
        templates = {
            "beginner": [1, 2, 3, 2, 1, 1, 5, 3],
            "intermediate": [1, 3, 5, 4, 3, 2, 1, 5, 3, 1],
            "advanced": [1, 2, 3, 5, 6, 7, 5, 3, 2, 1, 3, 1],
        }
    degrees = list(templates.get(lvl, templates["intermediate"]))
    if direction == "descending":
        degrees = list(reversed(degrees))
    elif direction == "ascending":
        degrees = sorted(degrees) if lvl == "beginner" else degrees
        # Ensure overall rise: start low degrees.
        degrees = [d if d >= 1 else 1 for d in degrees]
        degrees[0] = 1
        degrees[-1] = max(degrees)

    unit = _unit_duration(idea)
    if lvl == "beginner" and not idea.rhythm:
        unit = "quarter"
    notes: list[tuple[str, int, int | None, str]] = []
    for deg in degrees:
        spelled, octv, midi = _place_degree(
            scale, deg, prefer_midi=prefer, profile=profile, reference_key=tonic
        )
        notes.append((spelled, octv, deg, "lick"))
        step = 3 if direction == "ascending" else (-3 if direction == "descending" else 1)
        prefer = midi + step

    # Space: insert held notes on bar ends for phrase shape.
    events = _pack_events(
        notes,
        bars=bars,
        meter=idea.meter or "4/4",
        unit=unit,
        articulation=idea.articulation,
    )
    return MusicalIdeaComposition(
        events=tuple(events),
        reference_key=tonic,
        meter=idea.meter or "4/4",
        bars=bars,
        object_type="lick",
        style=idea.style or tonality,
        notation_profile=profile,
        strategy=f"lick:{lvl}:{direction}",
    )


def generate_phrase_over_chords(
    idea: MusicalIdeaRequest,
    chords: Sequence[str],
    *,
    notation_instrument: str,
    reference_key: str,
) -> MusicalIdeaComposition:
    """Song-relative phrase targeting chord tones."""
    from improvisation_motif import chord_tone_names
    from music_theory import chord_root_for_theory, normalize_chord_for_theory

    profile = apply_register_override(
        notation_profile_for_instrument(notation_instrument),
        idea.register,
    )
    usable = [_clean(c) for c in chords if _clean(c)]
    bars = int(idea.bars or min(4, max(2, len(usable))))
    usable = usable[:bars] or ["C"]
    lvl = _level(idea)
    unit = "half" if lvl == "beginner" else "quarter"
    if idea.rhythm:
        unit = _unit_duration(idea)
    prefer = (profile.midi_low + profile.midi_high) // 2
    notes: list[tuple[str, int, int | None, str]] = []
    ref = _clean(reference_key) or _clean(idea.explicit_key) or "C"
    for chord in usable:
        tones = chord_tone_names(chord, reference_key=ref) or [
            chord_root_for_theory(normalize_chord_for_theory(chord)) or "C"
        ]
        pick = [tones[0]]
        if lvl != "beginner" and len(tones) > 2:
            pick.append(tones[2])  # fifth
        if lvl == "advanced" and len(tones) > 1:
            pick.append(tones[1])
        for t in pick:
            from music_theory import midi_from_spelled_note, pitch_class_from_spelled_note, spell_note_in_key

            spelled = spell_note_in_key(pitch_class_from_spelled_note(t), ref)
            # reuse place via synthetic 1-note scale
            spelled2, octv, midi = _place_degree(
                [spelled, spelled],
                1,
                prefer_midi=prefer,
                profile=profile,
                reference_key=ref,
            )
            notes.append((spelled2, octv, None, "chord_tone"))
            prefer = midi + 2
        if lvl == "beginner":
            # one target per bar already via half notes packing
            pass

    events = _pack_events(
        notes,
        bars=bars,
        meter=idea.meter or "4/4",
        unit=unit,
        articulation=idea.articulation,
    )
    # Attach chord labels per bar
    labeled: list[MusicalEvent] = []
    for ev in events:
        chord = usable[min(ev.bar_index, len(usable) - 1)]
        labeled.append(
            MusicalEvent(
                spelled=ev.spelled,
                octave=ev.octave,
                duration=ev.duration,
                bar_index=ev.bar_index,
                beat=ev.beat,
                articulation=ev.articulation,
                scale_degree=ev.scale_degree,
                chord=chord,
                role=ev.role,
            )
        )
    return MusicalIdeaComposition(
        events=tuple(labeled),
        reference_key=ref,
        meter=idea.meter or "4/4",
        bars=bars,
        object_type="phrase",
        style=idea.style or "song_phrase",
        notation_profile=profile,
        strategy=f"phrase_over_chords:{lvl}",
    )


def generate_sequence(
    idea: MusicalIdeaRequest,
    *,
    notation_instrument: str,
) -> MusicalIdeaComposition:
    from dataclasses import replace

    idea2 = replace(
        idea,
        object_type="sequence",
        interval_pattern=idea.interval_pattern or "1-2-3",
    )
    comp = generate_scale_pattern(idea2, notation_instrument=notation_instrument)
    return MusicalIdeaComposition(
        events=comp.events,
        reference_key=comp.reference_key,
        meter=comp.meter,
        bars=comp.bars,
        object_type="sequence",
        style=comp.style,
        notation_profile=comp.notation_profile,
        strategy=f"sequence:{idea.interval_pattern or '1-2-3'}",
    )


def composition_to_abc(
    composition: MusicalIdeaComposition,
    *,
    title: str,
    bpm: int | None = None,
) -> str:
    from music_theory import abc_key_signature_for_reference

    from music_coach_ami.notation_validate import validate_notation_structure
    from music_coach_ami.scale_engine import (
        _abc_beam_within_measure,
        _abc_default_length,
        _abc_layout_systems_from_lines,
        _abc_tune_block,
        _note_to_abc,
    )

    meter = composition.meter or "4/4"
    key = composition.reference_key or "C"
    clef = composition.notation_profile.clef or "treble"
    q = int(bpm or 96)
    key_field = abc_key_signature_for_reference(key, scale_type="major")
    by_bar: dict[int, list[MusicalEvent]] = {}
    for ev in composition.events:
        by_bar.setdefault(ev.bar_index, []).append(ev)

    measure_lines: list[str] = []
    for bar_i in range(composition.bars):
        evs = by_bar.get(bar_i) or []
        parts: list[str] = []
        for idx, ev in enumerate(evs):
            tok = _note_to_abc(ev.spelled, ev.octave, key_field=key_field)
            dur_l = str(ev.duration).lower()
            if dur_l in ("half", "minim"):
                suffix = "2"
            elif dur_l in ("eighth", "quaver", "triplet_eighth"):
                suffix = "/2"
            elif dur_l in ("whole", "semibreve"):
                suffix = "4"
            elif dur_l in ("sixteenth",):
                suffix = "/4"
            else:
                suffix = ""
            if ev.articulation == "staccato":
                tok = tok + "."
            if idx == 0 and ev.chord:
                chord_label = str(ev.chord).replace('"', "'")
                parts.append(f'"{chord_label}"{tok}{suffix}')
            else:
                parts.append(f"{tok}{suffix}")
        if not parts:
            parts = ["z4"]
        measure_lines.append(_abc_beam_within_measure(parts, meter, _abc_default_length("quarter")) + " |")

    music = _abc_layout_systems_from_lines(measure_lines, lines_per_system=4)
    abc = _abc_tune_block(
        tune_number=1,
        title=title,
        key_field=key_field,
        bpm=q,
        meter=meter,
        note_value="quarter",
        music=music,
        clef=clef,
    )
    try:
        validate_notation_structure(abc, meter=meter, clef=clef, profile=composition.notation_profile)
    except Exception:
        pass
    return abc


def play_summary(composition: MusicalIdeaComposition) -> list[str]:
    lines: list[str] = []
    by_bar: dict[int, list[MusicalEvent]] = {}
    for ev in composition.events:
        by_bar.setdefault(ev.bar_index, []).append(ev)
    for bar_i in range(composition.bars):
        evs = by_bar.get(bar_i) or []
        names = " ".join(f"{e.spelled}{e.octave}" for e in evs[:8])
        chord = f" ({evs[0].chord})" if evs and evs[0].chord else ""
        lines.append(f"Bar {bar_i + 1}{chord}: {names}")
    return lines


def composition_diagnostics(composition: MusicalIdeaComposition) -> dict[str, Any]:
    midis: list[int] = []
    try:
        from music_theory import midi_from_spelled_note

        for ev in composition.events:
            midis.append(int(midi_from_spelled_note(ev.spelled, octave=ev.octave)))
    except ImportError:
        pass
    return {
        "bars_generated": composition.bars,
        "event_count": len(composition.events),
        "strategy": composition.strategy,
        "notation_clef": composition.notation_profile.clef,
        "written_midi_range_used": [min(midis), max(midis)] if midis else None,
        "contour_first_last_midi": [midis[0], midis[-1]] if len(midis) >= 2 else midis,
    }

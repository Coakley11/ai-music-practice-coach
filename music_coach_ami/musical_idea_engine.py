"""Structured musical-idea generators (patterns, licks, phrases) → events → ABC."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any, Sequence

from music_coach_ami.musical_idea_request import MusicalIdeaRequest
from music_coach_ami.notation_profile import (
    NotationProfile,
    apply_register_override,
    notation_profile_for_instrument,
    notation_profile_for_piano_role,
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
    pitch_class: int | None = None
    chord: str = ""
    role: str = ""
    cell_index: int | None = None
    domain: str = "concert"  # concert | written
    tone_role: str = ""  # chord_tone | passing | neighbor | approach | extension


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
    tonic: str = ""
    tonality: str = ""
    scale_spelling: tuple[str, ...] = ()
    validation_errors: tuple[str, ...] = ()
    validation_ok: bool = True


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
        return 3.0
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


def authoritative_scale_degrees(tonic: str, tonality: str) -> list[str]:
    """Seven unique scale-degree spellings (no repeated octave tonic)."""
    from music_coach_ami.scale_engine import spell_scale_degrees_for_direction

    scale_type = _clean(tonality) or "major"
    notes = spell_scale_degrees_for_direction(tonic, scale_type, "ascending")
    unique: list[str] = []
    for n in notes:
        if not n:
            continue
        if unique and n == unique[0]:
            break
        unique.append(n)
    return unique


def _pc(note: str) -> int:
    from music_theory import pitch_class_from_spelled_note

    return int(pitch_class_from_spelled_note(note))


def _midi(note: str, octave: int) -> int:
    from music_theory import midi_from_spelled_note

    return int(midi_from_spelled_note(note, octave=octave))


def generation_window(
    profile: NotationProfile,
    *,
    instrument: str,
    register: str = "",
    object_type: str = "",
    difficulty: str = "",
) -> tuple[int, int, int]:
    """Return (low, high, start_prefer) MIDI for generation — comfort ≠ playable envelope."""
    reg = _clean(register).lower()
    playable = apply_register_override(profile, reg if reg in {"high", "low"} else "")
    low, high = playable.midi_low, playable.midi_high
    inst = _clean(instrument).lower()
    obj = _clean(object_type).lower()
    lvl = _clean(difficulty).lower()

    if "flute" in inst and reg not in {"high", "low"}:
        # Comfortable middle practice window (~G4–D6); playable envelope stays wider.
        comfort_low, comfort_high = 67, 86
        low = max(low, comfort_low)
        high = min(high, comfort_high)
        if obj == "bass_line":
            high = min(high, 79)  # bias lower for supportive lines
        if "begin" in lvl or "easy" in lvl:
            high = min(high, 81)
            prefer = low + 5
        else:
            prefer = low + 8
        return low, high, prefer

    if reg == "high":
        prefer = high - 4
    elif reg == "low":
        prefer = low + 4
    else:
        prefer = (low + high) // 2
        if "begin" in lvl or "easy" in lvl:
            # Narrower central band for very easy material.
            span = max(8, (high - low) // 2)
            mid = prefer
            low = max(low, mid - span // 2)
            high = min(high, mid + span // 2)
            prefer = (low + high) // 2
    return low, high, prefer


def _place_spelled_note(
    spelled: str,
    *,
    prefer_midi: int,
    low: int,
    high: int,
    direction: str = "",
    previous_midi: int | None = None,
) -> tuple[str, int, int]:
    """Choose octave for an authoritative spelling — never re-spell the note.

    Direction continuity uses ``previous_midi`` (last placed event), not the
    generation-window center. Using the center as a direction reference caused
    ascending lines to jump to the top of the staff on the first note.
    """
    candidates: list[tuple[int, int]] = []
    for octv in range(0, 9):
        midi = _midi(spelled, octv)
        if midi < low - 2 or midi > high + 2:
            continue
        candidates.append((octv, midi))
    if not candidates:
        # Absolute fallback — still keep the spelling.
        octv = max(0, min(8, prefer_midi // 12 - 1))
        return spelled, octv, _midi(spelled, octv)

    def _in_window(midi: int) -> bool:
        return low <= midi <= high

    if previous_midi is not None and direction == "ascending":
        up = [c for c in candidates if c[1] >= previous_midi]
        if up:
            # Nearest pitch at or above previous (true ascending continuity).
            octv, midi = min(up, key=lambda c: (c[1] - previous_midi, 0 if _in_window(c[1]) else 1))
            return spelled, octv, midi
        # Ceiling: explicit wrap to lowest in-window occurrence.
        in_win = [c for c in candidates if _in_window(c[1])] or candidates
        octv, midi = min(in_win, key=lambda c: c[1])
        return spelled, octv, midi

    if previous_midi is not None and direction == "descending":
        down = [c for c in candidates if c[1] <= previous_midi]
        if down:
            octv, midi = min(down, key=lambda c: (previous_midi - c[1], 0 if _in_window(c[1]) else 1))
            return spelled, octv, midi
        in_win = [c for c in candidates if _in_window(c[1])] or candidates
        octv, midi = max(in_win, key=lambda c: c[1])
        return spelled, octv, midi

    if previous_midi is not None and direction in {"", "nearest", "continue"}:
        scored = sorted(
            candidates,
            key=lambda c: (
                0 if _in_window(c[1]) else 1,
                abs(c[1] - previous_midi),
                abs(c[1] - prefer_midi),
            ),
        )
        octv, midi = scored[0]
        return spelled, octv, midi

    # No prior event / free placement: closest to prefer inside the window.
    scored = sorted(
        candidates,
        key=lambda c: (
            0 if _in_window(c[1]) else 1,
            abs(c[1] - prefer_midi),
            abs(c[1] - ((low + high) // 2)),
        ),
    )
    octv, midi = scored[0]
    return spelled, octv, midi


def _degree_cycle(pattern: str) -> list[int]:
    p = _clean(pattern).lower()
    if p == "1-3-2-4":
        return [1, 3, 2, 4]
    if p == "1-3-4-2":
        return [1, 3, 4, 2]
    if p == "1-2-3-4":
        return [1, 2, 3, 4]
    if p == "1-2-3":
        return [1, 2, 3]
    if p in {"thirds", "broken_thirds"}:
        return [1, 3]
    if p == "fourths":
        return [1, 4]
    if p == "fifths":
        return [1, 5]
    return [1, 2, 3, 4]


def _degree_spelling(scale: Sequence[str], degree: int) -> tuple[str, int]:
    """Map 1-based degree to spelling. Degrees wrap by octave of the 7-note scale."""
    n = len(scale)
    if n < 1:
        return "C", 1
    idx = (int(degree) - 1) % n
    return scale[idx], idx + 1


def _events_needed(bars: int, meter: str, unit: str) -> int:
    beats = bars * _beats_per_bar(meter)
    ub = _dur_beats(unit, meter)
    if ub <= 0:
        return bars * 4
    return max(1, int(round(beats / ub)))


def _pack_events_exact(
    pitched: list[tuple[str, int, int | None, str, int | None]],
    *,
    bars: int,
    meter: str,
    unit: str,
    articulation: str,
) -> list[MusicalEvent]:
    """Place pre-generated notes into bars. Does not cycle/repeat the source list."""
    events: list[MusicalEvent] = []
    beats_bar = _beats_per_bar(meter)
    cursor = 0.0
    for spelled, octv, deg, role, cell in pitched:
        if cursor >= bars * beats_bar - 1e-9:
            break
        bar = int(cursor // beats_bar)
        if bar >= bars:
            break
        beat = cursor % beats_bar
        remain = beats_bar - beat
        dur = unit
        ub = _dur_beats(unit, meter)
        if ub > remain + 1e-6:
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
                pitch_class=_pc(spelled),
                role=role,
                cell_index=cell,
            )
        )
        cursor += _dur_beats(dur, meter)
    return events


def generate_scale_pattern(
    idea: MusicalIdeaRequest,
    *,
    notation_instrument: str,
) -> MusicalIdeaComposition:
    tonic = _clean(idea.explicit_key) or "C"
    tonality = _clean(idea.tonality) or "major"
    scale = authoritative_scale_degrees(tonic, tonality)
    if len(scale) < 5:
        scale = [tonic, tonic]
    profile = notation_profile_for_instrument(notation_instrument)
    low, high, prefer = generation_window(
        profile,
        instrument=notation_instrument,
        register=idea.register,
        object_type="pattern",
        difficulty=idea.difficulty or idea.level,
    )
    bars = int(idea.bars or 4)
    unit = _unit_duration(idea)
    direction = _clean(idea.direction) or "ascending"
    cell = _degree_cycle(idea.interval_pattern or "1-2-3-4")
    need = _events_needed(bars, idea.meter or "4/4", unit)

    pitched: list[tuple[str, int, int | None, str, int | None]] = []
    n = len(scale)
    # Root degrees advance through the scale in the global direction.
    if direction == "descending":
        root_degrees = list(range(n, 0, -1))
        prefer = high - 4
    elif direction == "both":
        root_degrees = list(range(1, n + 1))
        prefer = (low + high) // 2
    else:
        root_degrees = list(range(1, n + 1))
        prefer = low + 4

    cell_i = 0
    guard = 0
    prev_anchor: int | None = None
    pass_dir = "ascending" if direction != "descending" else "descending"
    while len(pitched) < need and guard < need * 4:
        guard += 1
        roots = root_degrees if pass_dir == "ascending" else list(range(n, 0, -1))
        for root in roots:
            if len(pitched) >= need:
                break
            degrees = [((d - 1 + root - 1) % n) + 1 for d in cell]
            if pass_dir == "descending":
                # Keep root as cell anchor; walk downward through the cell shape.
                degrees = [((root - 1 - (d - 1)) % n) + 1 for d in cell]
            cell_notes: list[tuple[str, int, int | None, str, int | None]] = []
            local_prev: int | None = None
            for j, deg in enumerate(degrees):
                if len(pitched) + len(cell_notes) >= need:
                    break
                spelled, _ = _degree_spelling(scale, deg)
                if j == 0:
                    # Cell anchor follows global direction vs previous cell anchor.
                    spelled2, octv, midi = _place_spelled_note(
                        spelled,
                        prefer_midi=prefer if prev_anchor is None else prev_anchor + (2 if pass_dir == "ascending" else -2),
                        low=low,
                        high=high,
                        direction=pass_dir,
                        previous_midi=prev_anchor,
                    )
                    if (
                        prev_anchor is not None
                        and pass_dir == "ascending"
                        and midi + 1 < prev_anchor
                    ):
                        # Ceiling wrap between cells — restart near comfort floor.
                        spelled2, octv, midi = _place_spelled_note(
                            spelled,
                            prefer_midi=low + 4,
                            low=low,
                            high=high,
                            direction="",
                            previous_midi=None,
                        )
                    elif (
                        prev_anchor is not None
                        and pass_dir == "descending"
                        and midi > prev_anchor + 1
                    ):
                        spelled2, octv, midi = _place_spelled_note(
                            spelled,
                            prefer_midi=high - 4,
                            low=low,
                            high=high,
                            direction="",
                            previous_midi=None,
                        )
                    prev_anchor = midi
                    prefer = midi + (2 if pass_dir == "ascending" else -2)
                else:
                    # Inside a cell: keep local register near the anchor; no global forced leap.
                    spelled2, octv, midi = _place_spelled_note(
                        spelled,
                        prefer_midi=local_prev if local_prev is not None else prev_anchor or prefer,
                        low=low,
                        high=high,
                        direction="",
                        previous_midi=None,
                    )
                    # Prefer the candidate nearest the running local pitch without huge leaps.
                    best = (spelled2, octv, midi)
                    for oct_try in range(0, 9):
                        m_try = _midi(spelled, oct_try)
                        if not (low - 1 <= m_try <= high + 1):
                            continue
                        ref = local_prev if local_prev is not None else prev_anchor or prefer
                        if abs(m_try - ref) < abs(best[2] - ref):
                            best = (spelled, oct_try, m_try)
                    spelled2, octv, midi = best
                local_prev = midi
                cell_notes.append((spelled2, octv, deg, "pattern", cell_i))
            pitched.extend(cell_notes)
            cell_i += 1
        if direction == "both" and pass_dir == "ascending" and len(pitched) < need:
            pass_dir = "descending"
            prev_anchor = None
            prefer = high - 4
            continue
        if direction == "both" and pass_dir == "descending" and len(pitched) < need:
            pass_dir = "ascending"
            prev_anchor = None
            prefer = low + 4
            continue
        # Continue another ascending/descending pass for remaining bars.
        if pass_dir == "ascending":
            prefer = low + 4
            prev_anchor = None
        else:
            prefer = high - 4
            prev_anchor = None

    events = _pack_events_exact(
        pitched[:need],
        bars=bars,
        meter=idea.meter or "4/4",
        unit=unit,
        articulation=idea.articulation,
    )
    deg7 = scale[6] if len(scale) >= 7 else None
    comp = MusicalIdeaComposition(
        events=tuple(events),
        reference_key=tonic,
        meter=idea.meter or "4/4",
        bars=bars,
        object_type="pattern",
        style=idea.style or tonality,
        notation_profile=apply_register_override(profile, idea.register),
        strategy=f"scale_pattern:{direction}:{idea.interval_pattern or 'scalar'}",
        tonic=tonic,
        tonality=tonality,
        scale_spelling=tuple(scale),
    )
    ok, errs = validate_musical_idea_composition(
        comp, direction=direction, require_degree7=deg7 if "harmonic" in tonality else None
    )
    return replace(comp, validation_ok=ok, validation_errors=tuple(errs))


def generate_lick(
    idea: MusicalIdeaRequest,
    *,
    notation_instrument: str,
) -> MusicalIdeaComposition:
    tonic = _clean(idea.explicit_key) or "C"
    tonality = _clean(idea.tonality) or ("blues" if idea.style == "blues" else "natural minor")
    if idea.style == "blues" and not idea.tonality:
        tonality = "blues"
    scale = authoritative_scale_degrees(tonic, tonality)
    profile = notation_profile_for_instrument(notation_instrument)
    low, high, prefer = generation_window(
        profile,
        instrument=notation_instrument,
        register=idea.register,
        object_type="lick",
        difficulty=idea.difficulty or idea.level,
    )
    bars = int(idea.bars or 4)
    lvl = _level(idea)
    direction = _clean(idea.direction) or "arch"
    unit = _unit_duration(idea)
    if lvl == "beginner" and not idea.rhythm:
        unit = "quarter"

    if idea.style == "blues" or tonality == "blues":
        templates = {
            "beginner": [1, 1, 3, 1, 5, 3, 1, 5],
            "intermediate": [1, 3, 5, 6, 5, 3, 1, 5, 3, 1, 5, 1],
            "advanced": [1, 2, 3, 5, 6, 5, 3, 2, 1, 3, 5, 6, 5, 1],
        }
    elif idea.style in {"jazz", "bebop"}:
        templates = {
            "beginner": [1, 2, 3, 5, 3, 2, 1, 1],
            "intermediate": [1, 2, 3, 5, 6, 5, 3, 2, 1, 7, 1, 3],
            "advanced": [1, 7, 1, 2, 3, 5, 4, 3, 2, 1, 3, 5, 7, 1],
        }
    else:
        templates = {
            "beginner": [1, 2, 3, 2, 1, 5, 3, 1],
            "intermediate": [1, 3, 5, 4, 3, 2, 1, 5, 3, 2, 1, 1],
            "advanced": [1, 2, 3, 5, 6, 7, 5, 3, 2, 1, 3, 5, 3, 1],
        }
    degrees = list(templates.get(lvl, templates["intermediate"]))
    need = _events_needed(bars, idea.meter or "4/4", unit)
    # Phrase development: extend without mere modulo of bars 1–2.
    developed: list[int] = []
    phrase_i = 0
    while len(developed) < need:
        chunk = list(degrees)
        if phrase_i == 1 and lvl != "beginner":
            chunk = chunk[2:] + [5, 3, 1]
        elif phrase_i >= 2:
            chunk = [1, 2, 3, 5] + chunk[-4:]
        if direction == "descending":
            chunk = list(reversed(chunk))
        elif direction == "ascending":
            chunk = sorted({d for d in chunk}) + chunk
            chunk[0] = 1
        developed.extend(chunk)
        phrase_i += 1

    pitched: list[tuple[str, int, int | None, str, int | None]] = []
    prev_midi: int | None = None
    if direction == "ascending":
        prefer = low + 3
    elif direction == "descending":
        prefer = high - 3
    for i, deg in enumerate(developed[:need]):
        spelled, _ = _degree_spelling(scale, deg)
        if direction in {"ascending", "descending"}:
            dir_hint = direction
        elif i < need // 2:
            dir_hint = "ascending"
        else:
            dir_hint = "descending"
        spelled2, octv, midi = _place_spelled_note(
            spelled,
            prefer_midi=prefer,
            low=low,
            high=high,
            direction=dir_hint,
            previous_midi=prev_midi,
        )
        pitched.append((spelled2, octv, deg, "lick", i // max(1, len(degrees))))
        prev_midi = midi
        prefer = midi + (2 if dir_hint == "ascending" else -2)

    events = _pack_events_exact(
        pitched,
        bars=bars,
        meter=idea.meter or "4/4",
        unit=unit,
        articulation=idea.articulation,
    )
    comp = MusicalIdeaComposition(
        events=tuple(events),
        reference_key=tonic,
        meter=idea.meter or "4/4",
        bars=bars,
        object_type="lick",
        style=idea.style or tonality,
        notation_profile=apply_register_override(profile, idea.register),
        strategy=f"lick:{lvl}:{direction}",
        tonic=tonic,
        tonality=tonality,
        scale_spelling=tuple(scale),
    )
    ok, errs = validate_musical_idea_composition(comp, direction=direction if direction in {"ascending", "descending"} else "")
    return replace(comp, validation_ok=ok, validation_errors=tuple(errs))


def expand_harmony_timeline(chords: Sequence[str], bars: int) -> list[str]:
    """Deterministic bar-level chord timeline of exactly ``bars`` entries.

    Cycles the section progression when fewer chord slots than requested bars.
    Does not invent unrelated harmony — only repeats the given timeline.
    """
    usable = [_clean(c) for c in chords if _clean(c)]
    n = max(1, int(bars))
    if not usable:
        return ["C"] * n
    if len(usable) >= n:
        return list(usable[:n])
    out: list[str] = []
    i = 0
    while len(out) < n:
        out.append(usable[i % len(usable)])
        i += 1
    return out


def generate_idea_over_chords(
    idea: MusicalIdeaRequest,
    chords: Sequence[str],
    *,
    notation_instrument: str,
    reference_key: str,
    object_type: str = "phrase",
) -> MusicalIdeaComposition:
    """Song-relative lick/phrase/riff over a resolved harmonic timeline."""
    obj = _clean(object_type) or _clean(idea.object_type) or "phrase"
    profile = notation_profile_for_instrument(notation_instrument)
    low, high, prefer = generation_window(
        profile,
        instrument=notation_instrument,
        register=idea.register,
        object_type="phrase" if obj in {"melody", "phrase"} else "lick",
        difficulty=idea.difficulty or idea.level,
    )
    bars = int(idea.bars or 4)
    timeline = expand_harmony_timeline(chords, bars)
    lvl = _level(idea)
    ref = _clean(reference_key) or _clean(idea.explicit_key) or "C"
    meter = idea.meter or "4/4"
    from music_coach_ami.melodic_motion import generate_horizontal_line

    line = generate_horizontal_line(
        timeline,
        reference_key=ref,
        level=lvl,
        object_type=obj,
        meter=meter,
        low=low,
        high=high,
        prefer=prefer,
        style=idea.style or "",
    )
    events = _events_from_motion_line(line, role=obj, articulation=idea.articulation)

    return MusicalIdeaComposition(
        events=tuple(events),
        reference_key=ref,
        meter=meter,
        bars=bars,
        object_type=obj,
        style=idea.style or f"song_{obj}",
        notation_profile=apply_register_override(profile, idea.register),
        strategy=f"{obj}_over_chords:{lvl}:horizontal_motion",
        tonic=ref,
        tonality="",
        scale_spelling=(),
    )


def generate_phrase_over_chords(
    idea: MusicalIdeaRequest,
    chords: Sequence[str],
    *,
    notation_instrument: str,
    reference_key: str,
) -> MusicalIdeaComposition:
    return generate_idea_over_chords(
        idea,
        chords,
        notation_instrument=notation_instrument,
        reference_key=reference_key,
        object_type="phrase",
    )


def generate_lick_over_chords(
    idea: MusicalIdeaRequest,
    chords: Sequence[str],
    *,
    notation_instrument: str,
    reference_key: str,
) -> MusicalIdeaComposition:
    return generate_idea_over_chords(
        idea,
        chords,
        notation_instrument=notation_instrument,
        reference_key=reference_key,
        object_type="lick",
    )


def generate_sequence(
    idea: MusicalIdeaRequest,
    *,
    notation_instrument: str,
) -> MusicalIdeaComposition:
    idea2 = replace(
        idea,
        object_type="sequence",
        interval_pattern=idea.interval_pattern or "1-2-3",
    )
    comp = generate_scale_pattern(idea2, notation_instrument=notation_instrument)
    return replace(comp, object_type="sequence", strategy=f"sequence:{idea.interval_pattern or '1-2-3'}")


def _events_from_motion_line(
    line: Sequence[dict[str, Any]],
    *,
    role: str,
    articulation: str,
) -> list[MusicalEvent]:
    events: list[MusicalEvent] = []
    for item in line:
        events.append(
            MusicalEvent(
                spelled=str(item.get("spelled") or "C"),
                octave=int(item.get("octave") or 4),
                duration=str(item.get("duration") or "quarter"),
                bar_index=int(item.get("bar_index") or 0),
                beat=float(item.get("beat") or 0.0),
                articulation=articulation,
                pitch_class=item.get("pitch_class"),
                chord=str(item.get("chord") or ""),
                role=role,
                cell_index=int(item.get("bar_index") or 0),
                domain="concert",
                tone_role=str(item.get("tone_role") or ""),
            )
        )
    return events


def infer_piano_role(idea: MusicalIdeaRequest, question: str = "") -> str:
    role = _clean(getattr(idea, "piano_role", "") or "")
    if role:
        return role
    low = _clean(question).lower()
    if re.search(r"\b(two[- ]?hands?|both hands|grand staff)\b", low):
        return "both_hands"
    if re.search(r"\b(left[- ]?hand|\blh\b)\b", low):
        return "left_hand"
    if re.search(r"\b(right[- ]?hand|\brh\b)\b", low):
        return "right_hand"
    obj = _clean(idea.object_type)
    if obj == "accompaniment":
        return "left_hand"
    if obj in {"improvisation", "melody", "solo"}:
        return "right_hand"
    return ""


def _chord_tone_list(chord: str, reference_key: str) -> list[str]:
    from improvisation_motif import chord_tone_names
    from music_theory import chord_root_for_theory, normalize_chord_for_theory

    tones = [t for t in (chord_tone_names(chord, reference_key=reference_key) or []) if t]
    if tones:
        return tones
    root = chord_root_for_theory(normalize_chord_for_theory(chord)) or "C"
    return [root]


def _rh_motif_for_bar(
    tones: list[str],
    *,
    obj: str,
    lvl: str,
    phase: int,
    ref: str,
) -> list[tuple[str, str]]:
    """Return (spelled, duration) pairs for one RH bar — phrase shape, not arpeggio dump."""
    root = tones[0]
    third = tones[min(1, len(tones) - 1)]
    fifth = tones[min(2, len(tones) - 1)] if len(tones) > 2 else root
    seventh = tones[min(3, len(tones) - 1)] if len(tones) > 3 else third
    if obj == "melody":
        if lvl == "beginner":
            cells = [(root, "half"), (third, "half")]
            if phase == 3:
                cells = [(root, "whole")]
            elif phase == 2:
                cells = [(third, "half"), (root, "half")]
        elif lvl == "advanced":
            cells = [(third, "quarter"), (fifth, "quarter"), (seventh, "quarter"), (root, "quarter")]
            if phase == 2:
                cells = [(fifth, "eighth"), (seventh, "eighth"), (root, "quarter"), (third, "half")]
            if phase == 3:
                cells = [(third, "half"), (root, "half")]
        else:
            cells = [(root, "quarter"), (third, "quarter"), (fifth, "half")]
            if phase == 2:
                cells = [(third, "quarter"), (fifth, "quarter"), (root, "half")]
            if phase == 3:
                cells = [(fifth, "half"), (root, "half")]
        return cells

    # Improvisation / solo — freer chord-tone line with level-sensitive density.
    if lvl == "beginner":
        cells = [(root, "quarter"), (third, "quarter"), (root, "quarter"), (fifth, "quarter")]
        if phase == 0:
            cells = [(root, "quarter"), (third, "quarter"), (fifth, "half")]
        elif phase == 3:
            cells = [(third, "half"), (root, "half")]
    elif lvl == "advanced":
        cells = [
            (third, "eighth"),
            (fifth, "eighth"),
            (seventh, "quarter"),
            (root, "quarter"),
            (third, "quarter"),
        ]
        if phase == 2:
            cells = [(fifth, "eighth"), (seventh, "eighth"), (root, "eighth"), (third, "eighth"), (fifth, "half")]
        if phase == 3:
            cells = [(seventh, "quarter"), (fifth, "quarter"), (third, "quarter"), (root, "quarter")]
    else:
        cells = [(third, "quarter"), (fifth, "quarter"), (root, "quarter"), (third, "quarter")]
        if phase == 0:
            cells = [(root, "quarter"), (third, "quarter"), (fifth, "half")]
        elif phase == 2:
            cells = [(third, "quarter"), (fifth, "eighth"), (seventh, "eighth"), (root, "half")]
        elif phase == 3:
            cells = [(fifth, "half"), (root, "half")]
    del ref
    return cells


def _lh_motif_for_bar(tones: list[str], *, lvl: str, phase: int) -> list[tuple[str, str]]:
    """Supportive LH — shells / bass, not a copy of the RH melody."""
    root = tones[0]
    third = tones[min(1, len(tones) - 1)]
    fifth = tones[min(2, len(tones) - 1)] if len(tones) > 2 else root
    seventh = tones[min(3, len(tones) - 1)] if len(tones) > 3 else fifth
    if lvl == "beginner":
        if phase == 3:
            return [(root, "whole")]
        return [(root, "half"), (fifth, "half")]
    if lvl == "advanced":
        if phase == 3:
            return [(fifth, "half"), (root, "half")]
        return [(root, "quarter"), (fifth, "quarter"), (seventh, "quarter"), (root, "quarter")]
    if phase == 3:
        return [(root, "half"), (fifth, "half")]
    return [(root, "quarter"), (fifth, "quarter"), (root, "half")] if phase == 0 else [
        (root, "quarter"),
        (third, "quarter"),
        (fifth, "half"),
    ]


def _events_from_hand_motifs(
    *,
    timeline: list[str],
    motifs: list[list[tuple[str, str]]],
    role: str,
    low: int,
    high: int,
    prefer: int,
    meter: str,
    articulation: str,
) -> list[MusicalEvent]:
    events: list[MusicalEvent] = []
    prev_midi: int | None = None
    prefer_cur = prefer
    beats_bar = _beats_per_bar(meter)
    for bar_i, (chord, cells) in enumerate(zip(timeline, motifs)):
        beat = 0.0
        phase = bar_i % 4
        dir_hint = "ascending" if phase < 2 else "descending"
        for spelled, dur in cells:
            ub = _dur_beats(dur, meter)
            if beat + ub > beats_bar + 1e-9:
                break
            spelled2, octv, midi = _place_spelled_note(
                spelled,
                prefer_midi=prefer_cur,
                low=low,
                high=high,
                direction=dir_hint,
                previous_midi=prev_midi,
            )
            events.append(
                MusicalEvent(
                    spelled=spelled2,
                    octave=octv,
                    duration=dur,
                    bar_index=bar_i,
                    beat=beat,
                    articulation=articulation,
                    pitch_class=_pc(spelled2),
                    chord=chord,
                    role=role,
                    cell_index=bar_i,
                    domain="concert",
                )
            )
            prev_midi = midi
            prefer_cur = midi + (2 if dir_hint == "ascending" else -2)
            beat += ub
        if beat < beats_bar - 1e-9 and events and events[-1].bar_index == bar_i:
            # Stretch the last event to fill the bar rather than leaving empty beats.
            last = events[-1]
            remain = beats_bar - last.beat
            fill = "whole" if remain >= 3.5 else "half" if remain >= 1.5 else last.duration
            events[-1] = replace(last, duration=fill)
    return events


def generate_piano_section_improvisation(
    idea: MusicalIdeaRequest,
    chords: Sequence[str],
    *,
    reference_key: str,
    piano_role: str = "",
    question: str = "",
) -> MusicalIdeaComposition:
    """Piano RH / LH / both-hands line over the real section harmonic timeline."""
    role = infer_piano_role(idea, question) or _clean(piano_role) or "right_hand"
    obj = _clean(idea.object_type) or "improvisation"
    if obj not in {"improvisation", "melody", "accompaniment", "solo"}:
        obj = "improvisation" if role != "left_hand" else "accompaniment"
    profile = notation_profile_for_piano_role(role)
    bars = int(idea.bars or max(4, len([c for c in chords if _clean(c)]) or 4))
    timeline = expand_harmony_timeline(chords, bars)
    lvl = _level(idea)
    ref = _clean(reference_key) or _clean(idea.explicit_key) or "C"
    meter = idea.meter or "4/4"
    rh_profile = notation_profile_for_piano_role("right_hand")
    lh_profile = notation_profile_for_piano_role("left_hand")

    lh_motifs = [
        _lh_motif_for_bar(_chord_tone_list(ch, ref), lvl=lvl, phase=i % 4) for i, ch in enumerate(timeline)
    ]

    events: list[MusicalEvent] = []
    if role in {"right_hand", "both_hands"}:
        from music_coach_ami.melodic_motion import generate_horizontal_line

        rh_low, rh_high, rh_prefer = generation_window(
            rh_profile, instrument="Piano", register=idea.register, object_type=obj, difficulty=lvl
        )
        rh_line = generate_horizontal_line(
            timeline,
            reference_key=ref,
            level=lvl,
            object_type=obj if obj != "accompaniment" else "improvisation",
            meter=meter,
            low=rh_low,
            high=rh_high,
            prefer=rh_prefer,
            style=idea.style or "",
        )
        events.extend(_events_from_motion_line(rh_line, role="rh", articulation=idea.articulation))
    if role in {"left_hand", "both_hands"}:
        lh_low, lh_high, lh_prefer = generation_window(
            lh_profile, instrument="Piano", register="low", object_type="accompaniment", difficulty=lvl
        )
        events.extend(
            _events_from_hand_motifs(
                timeline=timeline,
                motifs=lh_motifs,
                role="lh",
                low=lh_low,
                high=lh_high,
                prefer=lh_prefer,
                meter=meter,
                articulation=idea.articulation,
            )
        )
    events.sort(key=lambda e: (e.bar_index, 0 if e.role == "rh" else 1, e.beat))
    strategy = f"piano_{role}:{obj}:{lvl}:horizontal_motion"
    comp = MusicalIdeaComposition(
        events=tuple(events),
        reference_key=ref,
        meter=meter,
        bars=bars,
        object_type=obj,
        style=idea.style or obj,
        notation_profile=apply_register_override(profile, idea.register),
        strategy=strategy,
        tonic=ref,
        tonality="",
        scale_spelling=(),
    )
    ok, errs = validate_musical_idea_composition(comp)
    return replace(comp, validation_ok=ok, validation_errors=tuple(errs))


def composition_to_abc(
    composition: MusicalIdeaComposition,
    *,
    title: str,
    bpm: int | None = None,
) -> tuple[str, dict[str, Any]]:
    from music_coach_ami.notation_validate import validate_notation_structure
    from music_coach_ami.scale_engine import (
        _abc_beam_within_measure,
        _abc_default_length,
        _abc_key_field,
        _abc_layout_systems_from_lines,
        _abc_tune_block,
        _note_to_abc,
    )

    meter = composition.meter or "4/4"
    tonic = composition.tonic or composition.reference_key or "C"
    tonality = composition.tonality or "major"
    clef = composition.notation_profile.clef or "treble"
    q = int(bpm or 96)
    key_field = _abc_key_field(tonic, tonality)

    def _event_token(ev: MusicalEvent, *, with_chord: bool) -> str:
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
        if with_chord and ev.chord:
            chord_label = str(ev.chord).replace('"', "'")
            return f'"{chord_label}"{tok}{suffix}'
        return f"{tok}{suffix}"

    def _voice_measure_lines(role: str | None) -> list[str]:
        by_bar: dict[int, list[MusicalEvent]] = {}
        for ev in composition.events:
            if role and ev.role not in {role, ""} and not (role == "rh" and ev.role not in {"lh", "rh"}):
                continue
            if role == "lh" and ev.role == "rh":
                continue
            if role == "rh" and ev.role == "lh":
                continue
            by_bar.setdefault(ev.bar_index, []).append(ev)
        lines: list[str] = []
        for bar_i in range(composition.bars):
            evs = sorted(by_bar.get(bar_i) or [], key=lambda e: e.beat)
            parts: list[str] = []
            for idx, ev in enumerate(evs):
                parts.append(_event_token(ev, with_chord=idx == 0 and role != "lh"))
            if not parts:
                parts = ["z4"]
            lines.append(_abc_beam_within_measure(parts, meter, _abc_default_length("quarter")) + " |")
        return lines

    if clef == "grand":
        rh_lines = _voice_measure_lines("rh")
        lh_lines = _voice_measure_lines("lh")
        rh_music = _abc_layout_systems_from_lines(rh_lines, lines_per_system=4)
        lh_music = _abc_layout_systems_from_lines(lh_lines, lines_per_system=4)
        abc = (
            f"X:1\nT:{title}\nM:{meter}\nL:1/4\nQ:1/4={q}\nK:{key_field}\n"
            f"%%score {{(1 2)}}\n"
            f"V:1 clef=treble\n{rh_music}\n"
            f"V:2 clef=bass\n{lh_music}"
        )
        validation_clef = ""
    else:
        measure_lines = _voice_measure_lines(None)
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
        validation_clef = clef
    if clef == "grand":
        from music_coach_ami.notation_validate import NotationValidationResult

        g_errors: list[str] = []
        if "K:" not in abc or "M:" not in abc:
            g_errors.append("missing_key_or_meter")
        if "clef=treble" not in abc or "clef=bass" not in abc:
            g_errors.append("missing_grand_clefs")
        if "|" not in abc:
            g_errors.append("missing_bar_lines")
        validation = NotationValidationResult(
            ok=not g_errors,
            errors=g_errors,
            meter=meter,
            clef="grand",
        )
    else:
        validation = validate_notation_structure(
            abc, meter=meter, clef=validation_clef, profile=composition.notation_profile
        )
    musical_ok = bool(composition.validation_ok)
    musical_errs = list(composition.validation_errors)
    notation_ok = bool(getattr(validation, "ok", True))
    notation_errs = list(getattr(validation, "errors", []) or [])
    diag = {
        "notation_validation_ok": notation_ok and musical_ok,
        "notation_validation_errors": notation_errs + musical_errs,
        "notation_validation_warnings": list(getattr(validation, "warnings", []) or []),
        "abc_key_field": f"K:{key_field} clef={clef}",
        "tonality": tonality,
        "tonic": tonic,
        "scale_spelling": list(composition.scale_spelling),
        "musical_validation_ok": musical_ok,
        "musical_validation_errors": musical_errs,
    }
    if not notation_ok or not musical_ok:
        # Surface failures in diagnostics — do not silently swallow.
        diag["notation_validation_failed"] = True
    return abc, diag


def validate_musical_idea_composition(
    composition: MusicalIdeaComposition,
    *,
    direction: str = "",
    require_degree7: str | None = None,
) -> tuple[bool, list[str]]:
    """Structural/musical checks beyond ABC syntax."""
    errors: list[str] = []
    if composition.bars <= 0:
        errors.append("bars_must_be_positive")
    if not composition.events:
        errors.append("no_events")
    bar_set = {e.bar_index for e in composition.events}
    for b in range(composition.bars):
        if b not in bar_set:
            errors.append(f"missing_bar_{b}")
    if composition.scale_spelling:
        allowed_pc = {_pc(n) for n in composition.scale_spelling}
        for ev in composition.events:
            if ev.pitch_class is None:
                continue
            if int(ev.pitch_class) % 12 not in allowed_pc and ev.role == "pattern":
                errors.append(f"out_of_scale:{ev.spelled}")
                break
        for note in composition.scale_spelling:
            if "#" in note and note.replace("#", "b") in {"A#"}:
                pass
        if any(n == "A#" for n in composition.scale_spelling):
            errors.append("forbidden_enharmonic_A#")
        if require_degree7 and require_degree7 not in composition.scale_spelling:
            errors.append(f"missing_degree7_spelling:{require_degree7}")
        # Generated degree-7 events must use authoritative spelling when present.
        if require_degree7 and len(composition.scale_spelling) >= 7:
            deg7 = composition.scale_spelling[6]
            for ev in composition.events:
                if ev.scale_degree == 7 and ev.spelled != deg7:
                    errors.append(f"degree7_respell:{ev.spelled}!={deg7}")
                    break
    profile = composition.notation_profile
    for ev in composition.events:
        midi = _midi(ev.spelled, ev.octave)
        if midi < profile.midi_low - 2 or midi > profile.midi_high + 2:
            errors.append(f"out_of_instrument_range:{ev.spelled}{ev.octave}")
            break
    anchors = cell_anchor_midis(composition)
    if direction == "ascending" and len(anchors) >= 3:
        # Allow at most one wrap restart; before first wrap, anchors must not fall.
        wrap_i = None
        for i in range(1, len(anchors)):
            if anchors[i] + 1 < anchors[i - 1]:
                wrap_i = i
                break
        end = wrap_i if wrap_i is not None else len(anchors)
        for i in range(1, end):
            if anchors[i] + 1 < anchors[i - 1]:
                errors.append("ascending_cell_anchors_not_rising")
                break
    if direction == "descending" and len(anchors) >= 3:
        wrap_i = None
        for i in range(1, len(anchors)):
            if anchors[i] > anchors[i - 1] + 1:
                wrap_i = i
                break
        end = wrap_i if wrap_i is not None else len(anchors)
        for i in range(1, end):
            if anchors[i] > anchors[i - 1] + 1:
                errors.append("descending_cell_anchors_not_falling")
                break
    return (len(errors) == 0), errors


def play_summary(composition: MusicalIdeaComposition) -> list[str]:
    lines: list[str] = []
    by_bar: dict[int, list[MusicalEvent]] = {}
    for ev in composition.events:
        by_bar.setdefault(ev.bar_index, []).append(ev)
    two_hand = any(e.role == "rh" for e in composition.events) and any(
        e.role == "lh" for e in composition.events
    )
    for bar_i in range(composition.bars):
        evs = by_bar.get(bar_i) or []
        chord_sym = next((e.chord for e in evs if e.chord), "")
        chord = f" ({chord_sym})" if chord_sym else ""
        if two_hand:
            rh = [e.spelled for e in evs if e.role == "rh"][:8]
            lh = [e.spelled for e in evs if e.role == "lh"][:8]
            lines.append(f"Bar {bar_i + 1}{chord}")
            if rh:
                lines.append(f"RH: {' '.join(rh)}")
            if lh:
                lines.append(f"LH: {' '.join(lh)}")
        else:
            names = " ".join(e.spelled for e in evs[:8])
            lines.append(f"Bar {bar_i + 1}{chord}: {names}")
    return lines


def cell_anchor_midis(composition: MusicalIdeaComposition) -> list[int]:
    """First MIDI of each pattern cell — used for direction assertions."""
    anchors: list[int] = []
    seen: set[int] = set()
    for ev in composition.events:
        cell = ev.cell_index if ev.cell_index is not None else ev.bar_index
        if cell in seen:
            continue
        seen.add(cell)
        anchors.append(_midi(ev.spelled, ev.octave))
    return anchors


def composition_diagnostics(composition: MusicalIdeaComposition) -> dict[str, Any]:
    from music_coach_ami.melodic_motion import melodic_motion_metrics

    midis: list[int] = []
    for ev in composition.events:
        midis.append(_midi(ev.spelled, ev.octave))
    rh = [e for e in composition.events if e.role == "rh"]
    line_events = rh or list(composition.events)
    motion = melodic_motion_metrics(line_events)
    motion["phrase_strategy"] = composition.strategy
    return {
        "bars_generated": composition.bars,
        "event_count": len(composition.events),
        "strategy": composition.strategy,
        "notation_clef": composition.notation_profile.clef,
        "tonic": composition.tonic,
        "tonality": composition.tonality,
        "scale_spelling": list(composition.scale_spelling),
        "written_midi_range_used": [min(midis), max(midis)] if midis else None,
        "contour_first_last_midi": [midis[0], midis[-1]] if len(midis) >= 2 else midis,
        "cell_anchor_midis": cell_anchor_midis(composition)[:12],
        "validation_ok": composition.validation_ok,
        "validation_errors": list(composition.validation_errors),
        "melodic_motion": motion,
    }

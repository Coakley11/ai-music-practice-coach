"""Compose playable bass lines from active chart harmony + ABC notation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from music_coach_ami.notation_profile import NotationProfile, notation_profile_for_instrument


def _clean(text: object) -> str:
    return str(text or "").strip()


def _level_label(level: str) -> str:
    low = _clean(level).lower()
    if "advanced" in low:
        return "advanced"
    if "begin" in low or "easy" in low or "simple" in low:
        return "beginner"
    return "intermediate"


def _is_walking_focus(focus: str, *, style: str = "") -> bool:
    blob = f"{focus} {style}".lower()
    return "walking" in blob or "walk bass" in blob


def _spell_root(chord: str, reference_key: str) -> str:
    from music_theory import (
        chord_root_for_theory,
        normalize_chord_for_theory,
        pitch_class_from_spelled_note,
        spell_note_in_key,
    )

    theory = normalize_chord_for_theory(chord)
    root_name = chord_root_for_theory(theory)
    if not root_name:
        return "?"
    pc = pitch_class_from_spelled_note(root_name)
    return spell_note_in_key(pc, reference_key or "C")


def _chord_tones(chord: str, reference_key: str) -> list[str]:
    from improvisation_motif import chord_tone_names

    return [t for t in chord_tone_names(chord, reference_key=reference_key) if t]


def _note_midi(note: str, octave: int) -> int:
    from music_theory import midi_from_spelled_note

    return int(midi_from_spelled_note(note, octave=octave))


def _midi_to_note(midi: int, reference_key: str) -> str:
    from music_theory import spell_note_in_key

    return spell_note_in_key(int(midi) % 12, reference_key)


def _clamp_midi(midi: int, low: int, high: int) -> int:
    while midi < low:
        midi += 12
    while midi > high:
        midi -= 12
    if midi < low:
        return low
    if midi > high:
        return high
    return midi


def _place_pitch(note: str, *, prefer_midi: int, low: int, high: int) -> tuple[str, int, int]:
    """Choose written octave so *note* lands near prefer_midi within [low, high]."""
    from music_theory import pitch_class_from_spelled_note

    pc = pitch_class_from_spelled_note(note)
    # Candidate midis for this pitch class near prefer_midi
    base = prefer_midi - ((prefer_midi - pc) % 12)
    candidates = [base - 12, base, base + 12, base + 24]
    best = None
    best_dist = 10**9
    for midi in candidates:
        clamped = _clamp_midi(midi, low, high)
        if clamped % 12 != pc % 12:
            continue
        dist = abs(clamped - prefer_midi)
        if dist < best_dist:
            best_dist = dist
            best = clamped
    if best is None:
        best = _clamp_midi(prefer_midi - (prefer_midi % 12) + (pc % 12), low, high)
    octave = (best // 12) - 1
    return note, octave, best


def _nearest_chord_tone_midi(
    tones: list[str],
    *,
    from_midi: int,
    low: int,
    high: int,
    reference_key: str,
    avoid_midi: int | None = None,
) -> tuple[str, int, int]:
    best: tuple[str, int, int] | None = None
    best_dist = 10**9
    for tone in tones:
        _n, octv, midi = _place_pitch(tone, prefer_midi=from_midi, low=low, high=high)
        if avoid_midi is not None and midi == avoid_midi:
            continue
        dist = abs(midi - from_midi)
        # Prefer stepwise motion when distances tie
        if dist < best_dist or (dist == best_dist and best is not None and midi < best[2]):
            best_dist = dist
            best = (tone, octv, midi)
    if best is None and tones:
        return _place_pitch(tones[0], prefer_midi=from_midi, low=low, high=high)
    if best is None:
        return _place_pitch("C", prefer_midi=from_midi, low=low, high=high)
    return best


def _approach_to_target(
    target_note: str,
    *,
    from_midi: int,
    target_midi: int,
    level: str,
    reference_key: str,
    low: int,
    high: int,
    avoid_midi: int | None = None,
) -> tuple[str, int, int]:
    """Chromatic or diatonic approach into the next root — never a duplicate of from_midi."""
    # Prefer half-step from below into target (classic walking approach).
    candidates = [
        target_midi - 1,
        target_midi + 1,
        target_midi - 2,
        from_midi + (1 if target_midi >= from_midi else -1),
    ]
    if level == "beginner":
        candidates = [target_midi - 1, target_midi - 2, target_midi + 1]
    for midi in candidates:
        midi = _clamp_midi(midi, low, high)
        if avoid_midi is not None and midi == avoid_midi:
            continue
        if midi == from_midi:
            continue
        if midi == target_midi:
            continue
        note = _midi_to_note(midi, reference_key)
        octave = (midi // 12) - 1
        return note, octave, midi
    # Fall back to a nearby chord tone of the *upcoming* root's neighborhood
    note, octave, midi = _place_pitch(target_note, prefer_midi=from_midi, low=low, high=high)
    if midi == from_midi:
        midi = _clamp_midi(from_midi - 2, low, high)
        note = _midi_to_note(midi, reference_key)
        octave = (midi // 12) - 1
    return note, octave, midi


def _scale_connector(
    from_midi: int,
    *,
    toward_midi: int,
    reference_key: str,
    low: int,
    high: int,
    avoid_midi: int | None = None,
) -> tuple[str, int, int]:
    step = 1 if toward_midi >= from_midi else -1
    midi = _clamp_midi(from_midi + step, low, high)
    if avoid_midi is not None and midi == avoid_midi:
        midi = _clamp_midi(from_midi + 2 * step, low, high)
    if midi == from_midi:
        midi = _clamp_midi(from_midi + 2 * step, low, high)
    note = _midi_to_note(midi, reference_key)
    return note, (midi // 12) - 1, midi


@dataclass(frozen=True)
class BassLineNote:
    note: str
    duration: str
    written_octave: int


@dataclass(frozen=True)
class BassLineBar:
    chord: str
    notes: tuple[BassLineNote, ...]


@dataclass(frozen=True)
class BassLineComposition:
    bars: tuple[BassLineBar, ...]
    reference_key: str
    meter: str
    section_label: str
    strategy: str
    notation_profile: NotationProfile
    style: str = ""


def compose_bass_line_from_chords(
    chords: list[str],
    *,
    reference_key: str,
    level: str,
    instrument: str,
    meter: str = "4/4",
    section_label: str = "",
    max_bars: int = 8,
    practice_focus: str = "",
    style: str = "",
    difficulty_override: str = "",
) -> BassLineComposition:
    """Deterministic phrase-aware bass line aligned to one chord per bar."""
    usable = [_clean(c) for c in chords if _clean(c)][:max_bars]
    lvl = _level_label(difficulty_override or level)
    walking = _is_walking_focus(practice_focus, style=style)
    profile = notation_profile_for_instrument(instrument)
    ref = _clean(reference_key) or "C"
    low, high = profile.midi_low, profile.midi_high
    center = (low + high) // 2

    bars: list[BassLineBar] = []
    prev_midi = center
    strategy = "beginner_walking" if walking and lvl == "beginner" else (
        "intermediate_walking" if walking and lvl == "intermediate" else (
            "advanced_walking" if walking else f"{lvl}_bass_line"
        )
    )

    roots = [_spell_root(c, ref) for c in usable]
    tone_sets = [_chord_tones(c, ref) for c in usable]

    for idx, chord in enumerate(usable):
        root = roots[idx]
        tones = tone_sets[idx] or [root]
        third = tones[1] if len(tones) >= 2 else root
        fifth = tones[2] if len(tones) >= 3 else (tones[1] if len(tones) >= 2 else root)
        seventh = tones[3] if len(tones) >= 4 else third
        next_root = roots[idx + 1] if idx + 1 < len(usable) else root

        root_note, root_oct, root_midi = _place_pitch(root, prefer_midi=prev_midi, low=low, high=high)
        # Prefer landing on root from previous approach when close
        if abs(root_midi - prev_midi) > 7:
            root_note, root_oct, root_midi = _place_pitch(root, prefer_midi=center, low=low, high=high)

        next_root_placed = _place_pitch(next_root, prefer_midi=root_midi, low=low, high=high)
        next_root_midi = next_root_placed[2]

        pitched: list[BassLineNote] = []

        if walking or lvl != "beginner":
            # Quarter-note walking / connected line
            n1 = BassLineNote(root_note, "quarter", root_oct)
            cur = root_midi

            # Beat 2 — chord tone with smooth voice leading
            if lvl == "advanced":
                prefer = seventh if (idx % 2 == 0) else third
            elif lvl == "intermediate":
                prefer = third if abs(_note_midi(third, root_oct) - cur) <= abs(_note_midi(fifth, root_oct) - cur) else fifth
            else:
                # Beginner walking: mostly 5th or 3rd nearby
                prefer = fifth if (idx % 3 != 1) else third
            t2, o2, m2 = _place_pitch(prefer, prefer_midi=cur + (1 if next_root_midi >= cur else -1), low=low, high=high)
            if m2 == cur:
                t2, o2, m2 = _nearest_chord_tone_midi(tones, from_midi=cur + 2, low=low, high=high, reference_key=ref, avoid_midi=cur)
            n2 = BassLineNote(t2, "quarter", o2)
            cur = m2

            # Beat 3 — scale/passing connector toward next root
            if lvl == "advanced":
                t3, o3, m3 = _scale_connector(cur, toward_midi=next_root_midi, reference_key=ref, low=low, high=high, avoid_midi=cur)
                # Occasionally use chromatic passing
                if abs(next_root_midi - cur) >= 3 and idx % 2 == 1:
                    chrom = _clamp_midi(cur + (1 if next_root_midi > cur else -1), low, high)
                    if chrom != cur:
                        t3, o3, m3 = _midi_to_note(chrom, ref), (chrom // 12) - 1, chrom
            elif lvl == "intermediate":
                t3, o3, m3 = _nearest_chord_tone_midi(
                    [third, fifth, seventh],
                    from_midi=(cur + next_root_midi) // 2,
                    low=low,
                    high=high,
                    reference_key=ref,
                    avoid_midi=cur,
                )
            else:
                t3, o3, m3 = _scale_connector(cur, toward_midi=next_root_midi, reference_key=ref, low=low, high=high, avoid_midi=cur)
            if m3 == cur:
                t3, o3, m3 = _scale_connector(cur, toward_midi=next_root_midi + 2, reference_key=ref, low=low, high=high, avoid_midi=cur)
            n3 = BassLineNote(t3, "quarter", o3)
            cur = m3

            # Beat 4 — approach into next root (never duplicate beat 3)
            t4, o4, m4 = _approach_to_target(
                next_root,
                from_midi=cur,
                target_midi=next_root_midi,
                level=lvl,
                reference_key=ref,
                low=low,
                high=high,
                avoid_midi=cur,
            )
            n4 = BassLineNote(t4, "quarter", o4)
            pitched = [n1, n2, n3, n4]
            prev_midi = m4
        else:
            # Beginner non-walking: root–fifth halves, smooth register
            fifth_n, fifth_o, fifth_m = _place_pitch(fifth, prefer_midi=root_midi + 7, low=low, high=high)
            if fifth_m == root_midi:
                fifth_n, fifth_o, fifth_m = _place_pitch(fifth, prefer_midi=root_midi - 5, low=low, high=high)
            pitched = [
                BassLineNote(root_note, "half", root_oct),
                BassLineNote(fifth_n, "half", fifth_o),
            ]
            prev_midi = fifth_m

        bars.append(BassLineBar(chord=chord, notes=tuple(pitched)))

    return BassLineComposition(
        bars=tuple(bars),
        reference_key=ref,
        meter=meter or "4/4",
        section_label=_clean(section_label),
        strategy=strategy,
        notation_profile=profile,
        style="walking_bass" if walking else _clean(style) or "bass_line",
    )


def build_bass_line_abc(
    composition: BassLineComposition,
    *,
    title: str = "Bass line",
    bpm: int = 84,
) -> str:
    from music_coach_ami.scale_engine import build_abc_from_chord_bass_line

    return build_abc_from_chord_bass_line(
        composition,
        title=title,
        bpm=bpm,
    )


def bass_line_play_summary(composition: BassLineComposition) -> list[str]:
    lines: list[str] = []
    for bar in composition.bars:
        note_text = " · ".join(f"**{n.note}** ({n.duration})" for n in bar.notes)
        lines.append(f"- **{bar.chord}:** {note_text}")
    return lines


def composition_to_diagnostics(composition: BassLineComposition, chart: dict[str, Any]) -> dict[str, Any]:
    profile = composition.notation_profile
    return {
        "generation_strategy": composition.strategy,
        "bass_line_style": composition.style,
        "notation_clef": profile.clef,
        "written_register_octave": profile.written_octave,
        "sounding_to_written_shift": profile.sounding_to_written_shift,
        "written_midi_range": [profile.midi_low, profile.midi_high],
        "reference_key_spelling": composition.reference_key,
        "meter": composition.meter,
        "section_label": composition.section_label,
        "bars_generated": len(composition.bars),
        "generated_notes": [
            {
                "chord": bar.chord,
                "notes": [
                    {"note": n.note, "duration": n.duration, "written_octave": n.written_octave}
                    for n in bar.notes
                ],
            }
            for bar in composition.bars
        ],
        "chart_source": chart.get("chart_source"),
        "chart_available": chart.get("chart_available"),
        "active_section": chart.get("active_section"),
        "chord_timeline_used": list(chart.get("active_section_chords") or []),
        "practice_key": chart.get("practice_key"),
        "original_key": chart.get("original_key"),
    }

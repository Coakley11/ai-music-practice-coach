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
    if "begin" in low:
        return "beginner"
    return "intermediate"


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

    return chord_tone_names(chord, reference_key=reference_key)


def _note_midi(note: str, octave: int) -> int:
    from music_theory import midi_from_spelled_note

    return int(midi_from_spelled_note(note, octave=octave))


def _midi_to_note(midi: int, reference_key: str) -> str:
    from music_theory import spell_note_in_key

    return spell_note_in_key(midi % 12, reference_key)


def _pick_fifth(root: str, tones: list[str]) -> str:
    if len(tones) >= 3:
        return tones[2]
    if len(tones) >= 2:
        return tones[1]
    return root


def _pick_third(root: str, tones: list[str]) -> str:
    if len(tones) >= 2:
        return tones[1]
    return root


def _approach_note(next_root: str, reference_key: str, *, advanced: bool) -> str:
    next_midi = _note_midi(next_root, 3)
    step = -1 if advanced else -2
    return _midi_to_note(next_midi + step, reference_key)


@dataclass(frozen=True)
class BassLineBar:
    chord: str
    notes: tuple[tuple[str, str], ...]  # (spelled_note, note_value)


@dataclass(frozen=True)
class BassLineComposition:
    bars: tuple[BassLineBar, ...]
    reference_key: str
    meter: str
    section_label: str
    strategy: str
    notation_profile: NotationProfile


def compose_bass_line_from_chords(
    chords: list[str],
    *,
    reference_key: str,
    level: str,
    instrument: str,
    meter: str = "4/4",
    section_label: str = "",
    max_bars: int = 8,
) -> BassLineComposition:
    """Deterministic bass-line bars — one chord per bar in 4/4 by default."""
    usable = [_clean(c) for c in chords if _clean(c)][:max_bars]
    lvl = _level_label(level)
    profile = notation_profile_for_instrument(instrument)
    octave = profile.default_octave
    ref = _clean(reference_key) or "C"
    bars: list[BassLineBar] = []

    for idx, chord in enumerate(usable):
        root = _spell_root(chord, ref)
        tones = _chord_tones(chord, ref)
        fifth = _pick_fifth(root, tones)
        third = _pick_third(root, tones)
        next_root = _spell_root(usable[idx + 1], ref) if idx + 1 < len(usable) else root

        if lvl == "beginner":
            notes = ((root, "half"), (fifth, "half"))
            strategy = "beginner_root_fifth"
        elif lvl == "advanced":
            approach = _approach_note(next_root, ref, advanced=True)
            passing = _midi_to_note(_note_midi(root, octave) - 1, ref)
            notes = (
                (root, "quarter"),
                (third, "quarter"),
                (passing, "quarter"),
                (approach, "quarter"),
            )
            strategy = "advanced_voice_leading"
        else:
            approach = _approach_note(next_root, ref, advanced=False)
            notes = (
                (root, "quarter"),
                (fifth, "quarter"),
                (third, "quarter"),
                (approach, "quarter"),
            )
            strategy = "intermediate_root_connection"

        bars.append(BassLineBar(chord=chord, notes=tuple(notes)))

    return BassLineComposition(
        bars=tuple(bars),
        reference_key=ref,
        meter=meter or "4/4",
        section_label=_clean(section_label),
        strategy=strategy,
        notation_profile=profile,
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
        note_text = " · ".join(f"**{n}** ({dur})" for n, dur in bar.notes)
        lines.append(f"- **{bar.chord}:** {note_text}")
    return lines


def composition_to_diagnostics(composition: BassLineComposition, chart: dict[str, Any]) -> dict[str, Any]:
    return {
        "generation_strategy": composition.strategy,
        "notation_clef": composition.notation_profile.clef,
        "written_register_octave": composition.notation_profile.default_octave,
        "reference_key_spelling": composition.reference_key,
        "meter": composition.meter,
        "section_label": composition.section_label,
        "bars_generated": len(composition.bars),
        "generated_notes": [
            {"chord": bar.chord, "notes": [{"note": n, "duration": d} for n, d in bar.notes]}
            for bar in composition.bars
        ],
        "chart_source": chart.get("chart_source"),
        "chart_available": chart.get("chart_available"),
        "active_section": chart.get("active_section"),
        "chord_timeline_used": list(chart.get("active_section_chords") or []),
        "practice_key": chart.get("practice_key"),
        "original_key": chart.get("original_key"),
    }

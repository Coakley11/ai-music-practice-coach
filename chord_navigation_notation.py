"""Chord-tone / arpeggio navigation exercises for the Practice page's
Notation / TAB tool.

This is deliberately **not** Generated Practice Melody. Practice Melody
composes a melodic line over the changes; this module builds an exercise
that teaches *navigating* the changes themselves -- a connected chord-tone
line (wind/vocal/generic instruments), connected close-position voicings
(piano), or shape-connected fretted positions (guitar, handled separately
in ``practice_notation.py`` since it reuses that module's existing
hand-curated shape data). The through-line for all three: each chord's
realization is chosen to minimize melodic/registral distance from what
came immediately before -- voice leading -- rather than independent
root-position shapes per chord.

Reuses existing infrastructure rather than inventing new ones:
- ``music_theory.spell_chord_tones`` for letter-correct chord-tone names
  (the same spelling the rest of the app uses for chord-tone display).
- ``harmonic_spelling.spell_pitch_classes_for_chord`` for approach/passing
  tones outside the chord, the same helper ``practice_melody_generator.py``
  uses for its own passing/approach tones.
- ``composition_melody_notation.build_abc_from_melody_events`` for the
  melodic-line ABC output -- the same chord-annotated ABC pipeline already
  used by Practice Melody and the existing Notation/TAB tool, so chord
  symbols land above the correct measures the same way everywhere.

Does not resolve or transpose keys itself: callers pass the same
already-projected ``display_key`` (chart/written key) the rest of Practice
already resolved, exactly like Practice Melody does.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from harmonic_spelling import spell_pitch_classes_for_chord
from music_theory import NOTE_TO_MIDI, normalize_root, spell_chord_tones

VALID_LEVELS = ("Beginner", "Intermediate", "Advanced")

# Tones per chord, rhythmic/directional character, and whether an approach
# tone bridges into the next chord -- mirrors the Beginner/Intermediate/
# Advanced differentiation already established for Generated Practice
# Melody, applied here to chord-navigation instead of melodic composition.
LEVEL_PROFILES: dict[str, dict[str, Any]] = {
    "Beginner": {
        "tones_per_chord": 2,
        "direction_changes": False,
        "approach_tones": False,
        "rest_tail": True,
    },
    "Intermediate": {
        "tones_per_chord": 3,
        "direction_changes": True,
        "approach_tones": False,
        "rest_tail": False,
    },
    "Advanced": {
        "tones_per_chord": 4,
        "direction_changes": True,
        "approach_tones": True,
        "rest_tail": False,
    },
}

PIANO_VOICING_RANGE = (48, 84)  # C3..C6 -- comfortable two-hand-adjacent reading range.

# Semitones the comfortable written register widens on each side per level --
# Beginner stays inside the instrument's own pedagogical "comfortable middle"
# register; higher levels progressively use more of the instrument's real
# playable range while staying inside it (never impossible/unplayable notes).
_LEVEL_REGISTER_EXPANSION: dict[str, int] = {"Beginner": 0, "Intermediate": 3, "Advanced": 6}


def _normalize_level(level: str) -> str:
    text = str(level or "").strip().title()
    return text if text in LEVEL_PROFILES else "Intermediate"


def instrument_register(instrument: str, level: str = "Intermediate") -> tuple[int, int, int]:
    """(midi_low, midi_high, start_midi) for *instrument* at *level*.

    Reuses the AMI per-instrument written-register table
    (``music_coach_ami.notation_profile``, already covering Alto/Tenor/
    Soprano/Bari Sax, Trumpet, Trombone, Tuba, Clarinet, Flute, Piano roles,
    Bass and Guitar) instead of inventing a second range table. Beginner
    uses that profile's own comfortable middle register unchanged; higher
    levels symmetrically widen it, still bounded by real instrument limits.
    """
    from music_coach_ami.notation_profile import notation_profile_for_instrument

    profile = notation_profile_for_instrument(instrument or "")
    expand = _LEVEL_REGISTER_EXPANSION.get(_normalize_level(level), 0)
    lo = max(21, int(profile.midi_low) - expand)
    hi = min(108, int(profile.midi_high) + expand)
    if hi <= lo:
        hi = lo + 12
    start = (lo + hi) // 2
    return lo, hi, start


def _nearest_octave_in_range(pc: int, near_midi: int, lo: int, hi: int) -> int:
    """Nearest MIDI with pitch class *pc* to *near_midi*, octave-shifted to
    stay inside [lo, hi] -- keeps the connected line both voice-led AND
    inside the instrument's playable register. Every register this module
    resolves spans at least an octave, so a representative of *pc* always
    exists in range."""
    candidate = _nearest_octave(pc, near_midi)
    while candidate < lo:
        candidate += 12
    while candidate > hi:
        candidate -= 12
    return candidate


def chord_tone_pool(chord: str) -> list[str]:
    """Letter-spelled root/3rd/5th/7th for *chord* (reuses music_theory)."""
    tones = spell_chord_tones(chord)
    return tones if tones else ["C"]


def _pc_of(name: str) -> int:
    return NOTE_TO_MIDI.get(normalize_root(name), 60) % 12


def _nearest_octave(pc: int, near_midi: int) -> int:
    """Nearest MIDI with pitch class *pc* to *near_midi* -- the voice-leading
    primitive: every successive chord tone is realized as close as possible
    to wherever the line/voicing already is, instead of defaulting to a
    fixed octave per chord."""
    pc = int(pc) % 12
    near_midi = int(near_midi)
    base = (near_midi // 12) * 12 + pc
    candidates = (base - 12, base, base + 12)
    return min(candidates, key=lambda m: abs(m - near_midi))


def _spelled_with_octave(name: str, midi: int) -> str:
    return f"{name}{midi // 12 - 1}"


@dataclass(frozen=True)
class ArpeggioEvent:
    """One note or rest in a connected chord-tone line."""

    chord: str
    measure: int
    beat: float
    duration_beats: float
    is_rest: bool
    pitch: str | None = None
    midi: int | None = None


def build_connected_arpeggio_line(
    chords: list[str],
    *,
    level: str = "Intermediate",
    beats_per_measure: int = 4,
    instrument: str = "",
    start_midi: int | None = None,
) -> list[ArpeggioEvent]:
    """A single connected melodic line through *chords* for wind/vocal/
    generic (non-piano, non-guitar) instruments -- each chord's tones
    realized at the register nearest the previous note, so the line
    audibly connects one harmony to the next instead of resetting to a
    fixed octave every measure. Register stays inside *instrument*'s
    playable written range for *level* (see ``instrument_register``);
    pass an explicit ``start_midi`` to override the derived register
    midpoint without changing the clamping bounds."""
    profile = LEVEL_PROFILES[_normalize_level(level)]
    reg_lo, reg_hi, reg_start = instrument_register(instrument, level)
    events: list[ArpeggioEvent] = []
    n_chords = len(chords)

    # Phase 1: decide each measure's tone order (direction) up front, so an
    # approach tone can target whichever tone the *next* measure actually
    # plays first -- not always that chord's root -- and so stay a genuine
    # one-semitone connection even when direction_changes reverses order.
    ordered_tones_by_measure: list[list[str]] = []
    for m_idx, chord in enumerate(chords):
        tones = chord_tone_pool(chord)
        n = min(int(profile["tones_per_chord"]), len(tones))
        ordered = tones[:n]
        if profile["direction_changes"] and m_idx % 2 == 1:
            ordered = list(reversed(ordered))
        ordered_tones_by_measure.append(ordered)

    prev_midi = int(start_midi) if start_midi is not None else int(reg_start)
    for m_idx, chord in enumerate(chords):
        ordered_tones = ordered_tones_by_measure[m_idx]
        measure_midis: list[int] = []
        cursor = prev_midi
        for tone in ordered_tones:
            realized = _nearest_octave_in_range(_pc_of(tone), cursor, reg_lo, reg_hi)
            measure_midis.append(realized)
            cursor = realized

        approach_name: str | None = None
        approach_midi: int | None = None
        has_next = m_idx + 1 < n_chords and ordered_tones_by_measure[m_idx + 1]
        if profile["approach_tones"] and has_next and measure_midis:
            next_first_tone = ordered_tones_by_measure[m_idx + 1][0]
            target = _nearest_octave_in_range(_pc_of(next_first_tone), measure_midis[-1], reg_lo, reg_hi)
            approach_midi = target - 1 if target >= measure_midis[-1] else target + 1
            approach_midi = max(reg_lo, min(reg_hi, approach_midi))
            approach_name = spell_pitch_classes_for_chord(
                [approach_midi % 12], chord, song_display_key=""
            )[0]

        slots = len(ordered_tones) + (1 if approach_midi is not None else 0)
        rest_tail = bool(profile["rest_tail"]) and beats_per_measure > slots
        usable_beats = beats_per_measure - (1.0 if rest_tail else 0.0)
        dur = usable_beats / max(1, slots)

        beat_cursor = 0.0
        for tone, midi_val in zip(ordered_tones, measure_midis):
            events.append(
                ArpeggioEvent(
                    chord=chord,
                    measure=m_idx,
                    beat=beat_cursor,
                    duration_beats=dur,
                    is_rest=False,
                    pitch=tone,
                    midi=midi_val,
                )
            )
            beat_cursor += dur
        if approach_midi is not None:
            events.append(
                ArpeggioEvent(
                    chord=chord,
                    measure=m_idx,
                    beat=beat_cursor,
                    duration_beats=dur,
                    is_rest=False,
                    pitch=approach_name,
                    midi=approach_midi,
                )
            )
            beat_cursor += dur
        if rest_tail:
            events.append(
                ArpeggioEvent(
                    chord=chord,
                    measure=m_idx,
                    beat=beat_cursor,
                    duration_beats=beats_per_measure - beat_cursor,
                    is_rest=True,
                )
            )
        if measure_midis:
            prev_midi = measure_midis[-1]
    return events


def arpeggio_events_to_melody_dicts(events: list[ArpeggioEvent]) -> list[dict[str, Any]]:
    """Adapt to the ``{pitch, is_rest, duration_beats}`` shape
    ``composition_melody_notation.build_abc_from_melody_events`` expects --
    the same adapter shape ``practice_melody_notation.py`` uses, so both
    tools render through the identical ABC pipeline."""
    out: list[dict[str, Any]] = []
    for ev in events:
        out.append(
            {
                "pitch": _spelled_with_octave(ev.pitch, ev.midi) if not ev.is_rest and ev.pitch else "rest",
                "is_rest": ev.is_rest,
                "duration_beats": ev.duration_beats,
            }
        )
    return out


@dataclass(frozen=True)
class VoicingEvent:
    """One connected close-position chord voicing (piano)."""

    chord: str
    measure: int
    pitches: tuple[str, ...]
    midis: tuple[int, ...]


def build_connected_piano_voicings(
    chords: list[str],
    *,
    level: str = "Intermediate",
    start_center: int = 64,
) -> list[VoicingEvent]:
    """Each chord realized as a close-position voicing chosen to minimize
    registral movement from the *previous* voicing -- "closest voicing"
    connection, not independent root-position stacks per chord."""
    profile = LEVEL_PROFILES[_normalize_level(level)]
    n_tones = 3 if _normalize_level(level) == "Beginner" else min(4, int(profile["tones_per_chord"]) + 1)
    expand = _LEVEL_REGISTER_EXPANSION.get(_normalize_level(level), 0)
    lo, hi = PIANO_VOICING_RANGE
    lo, hi = lo - expand, hi + expand
    events: list[VoicingEvent] = []
    prev_midis: list[int] = []
    for m_idx, chord in enumerate(chords):
        tones = chord_tone_pool(chord)[:n_tones]
        if not prev_midis:
            midis: list[int] = []
            cursor = start_center - 6
            for tone in tones:
                realized = _nearest_octave(_pc_of(tone), cursor)
                while midis and realized <= midis[-1]:
                    realized += 12
                midis.append(realized)
                cursor = realized
        else:
            ref = int(round(sum(prev_midis) / len(prev_midis)))
            midis = sorted(_nearest_octave(_pc_of(tone), ref) for tone in tones)
            for i in range(1, len(midis)):
                while midis[i] <= midis[i - 1]:
                    midis[i] += 12
        midis = [max(lo, min(hi, m)) for m in midis]
        pitches = tuple(_spelled_with_octave(t, m) for t, m in zip(tones, midis))
        events.append(VoicingEvent(chord=chord, measure=m_idx, pitches=pitches, midis=tuple(midis)))
        prev_midis = midis
    return events


def build_piano_voicing_abc(
    events: list[VoicingEvent],
    *,
    key: str,
    meter: str = "4/4",
    bpm: int = 96,
    title: str = "Chord navigation",
) -> str:
    """ABC text for connected piano voicings -- one chord-symbol-annotated
    voicing per measure, same chord-annotation convention
    (``"Chord"[notes]``) abcjs already renders for every other notation
    path in this app."""
    from composition_hum_transcription import parse_meter
    from composition_melody_notation import composition_abc_key_field
    from music_theory import abc_pitch_for_spelled_note

    num, den = parse_meter(meter)
    k_field = composition_abc_key_field(key)
    eighths_per_bar = max(1, int(round(num * 8 / den)))

    def _voicing_token(pitches: tuple[str, ...]) -> str:
        toks = []
        for p in pitches:
            i = len(p) - 1
            while i >= 0 and p[i].isdigit():
                i -= 1
            name, octave_str = p[: i + 1] or "C", p[i + 1 :]
            try:
                octave = int(octave_str)
            except ValueError:
                octave = 4
            toks.append(abc_pitch_for_spelled_note(name, octave=octave, k_field=k_field))
        return "[" + "".join(toks) + "]"

    bars = [f'"{ev.chord}"{_voicing_token(ev.pitches)}{eighths_per_bar}' for ev in events]
    music = " | ".join(bars) + " |" if bars else "z4 |"
    return f"""X:1
T:{title}
M:{num}/{den}
L:1/8
Q:1/4={int(bpm)}
K:{k_field}
{music}"""

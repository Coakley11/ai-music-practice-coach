"""Transposes a ``practice_melody_model.PracticeMelody`` to a new
``key_center``, preserving its musical identity.

This module exists to enforce one distinction precisely: a *key change* on
an already-generated Practice Melody must transpose it (same composition,
different projection), while "Generate Another Melody"
(``practice_melody_generator.generate_another_practice_melody``) is the
only thing that produces a new composition. A melody's identity --
``song_id``, ``level``, ``seed``, ``alt_index``, and therefore
``melody_id`` (which is derived from exactly those fields, never from
``key_center``) -- is unchanged by transposition; only ``key_center`` and
the pitch/chord content of its sections/events change.

Reuses existing canonical primitives rather than inventing transposition
math: ``music_theory.semitone_distance`` for the interval,
``music_theory.transpose_chord`` for chord-symbol respelling (the same
primitive ``composition_key_transpose.py`` uses for its own melody-event
transposition), and ``harmonic_spelling.spell_pitch_classes_for_chord`` --
the same per-event spelling primitive ``practice_melody_generator.py``
already uses to turn a generated pitch class into ``MelodyEvent.pitch`` --
for pitch respelling here too.

Sign convention: ``music_theory.semitone_distance`` returns an *unsigned*
0-11 value (always "up"). That's harmless for a chord symbol (chord
symbols carry no octave), but for a melody's absolute MIDI pitches,
always transposing up by as much as 11 semitones would shove a "C down to
B" change nearly an octave higher -- clearly wrong for a melody display.
This module instead uses the *signed shortest-path* interval (range
-5..+6), so the melody stays in its original register, matching ordinary
musical/visual expectation (down a semitone moves down a semitone). This
is a deliberate deviation from ``composition_key_transpose.py``'s
always-up convention, made because that module only transposes chord
symbols (register-agnostic) while this one transposes actual pitches.
"""

from __future__ import annotations

from dataclasses import replace as _dc_replace

from harmonic_spelling import spell_pitch_classes_for_chord
from music_theory import semitone_distance, transpose_chord
from practice_melody_model import MelodyEvent, MelodySection, PracticeMelody


def signed_semitone_interval(from_key: str, to_key: str) -> int:
    """Shortest-path signed semitone interval ``from_key -> to_key``.

    Range is -5..+6 (never the raw unsigned 0-11 that
    ``music_theory.semitone_distance`` returns), so e.g. ``D -> C`` is
    ``-2``, not ``10``.
    """
    raw = semitone_distance(from_key, to_key) % 12
    return raw - 12 if raw > 6 else raw


def _transpose_event(event: MelodyEvent, *, steps: int, new_key_center: str) -> MelodyEvent:
    new_chord = transpose_chord(event.chord, steps, reference_key=new_key_center) if event.chord else event.chord
    if event.is_rest or event.midi is None:
        return _dc_replace(event, chord=new_chord)
    new_midi = event.midi + steps
    new_pitch = spell_pitch_classes_for_chord(
        [new_midi % 12], new_chord, song_display_key=new_key_center
    )[0]
    return _dc_replace(event, midi=new_midi, pitch=new_pitch, chord=new_chord)


def _transpose_section(section: MelodySection, *, steps: int, new_key_center: str) -> MelodySection:
    new_chords = tuple(
        transpose_chord(c, steps, reference_key=new_key_center) if c else c for c in section.chords
    )
    new_events = tuple(
        _transpose_event(event, steps=steps, new_key_center=new_key_center) for event in section.events
    )
    return _dc_replace(section, chords=new_chords, events=new_events)


def transpose_practice_melody(melody: PracticeMelody, *, new_key_center: str) -> PracticeMelody:
    """Return the same composition re-projected into ``new_key_center``.

    ``song_id``, ``song_title``, ``level``, ``tempo_bpm``, ``style``,
    ``meter``, ``seed``, ``alt_index``, ``generator_version``,
    ``melody_id``, and ``section_order`` are all copied through unchanged
    -- this is a projection change, not a new generation. Only
    ``key_center`` and each section's ``chords``/``events`` (pitch, midi,
    chord symbol -- never duration, beat, measure, is_rest, or tone_role)
    change.

    A no-op (returns ``melody`` itself, not a copy) when ``new_key_center``
    is empty/blank or already equals ``melody.key_center``.
    """
    target = str(new_key_center or "").strip()
    if not target or target == melody.key_center:
        return melody
    steps = signed_semitone_interval(melody.key_center, target)
    new_sections = tuple(
        _transpose_section(section, steps=steps, new_key_center=target) for section in melody.sections
    )
    return _dc_replace(melody, key_center=target, sections=new_sections)

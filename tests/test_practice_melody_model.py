"""Structural tests for the Practice Melody data model (practice_melody_model.py)."""

from __future__ import annotations

import unittest

from practice_melody_model import (
    MelodyEvent,
    MelodySection,
    PracticeMelody,
    SCHEMA_VERSION,
    validate_practice_melody,
)


def _valid_section() -> MelodySection:
    events = (
        MelodyEvent(measure=0, beat=0.0, duration_beats=2.0, is_rest=False, pitch="G", midi=67, chord="G", tone_role="chord_tone"),
        MelodyEvent(measure=0, beat=2.0, duration_beats=2.0, is_rest=True, chord="G", tone_role="rest"),
        MelodyEvent(measure=1, beat=0.0, duration_beats=4.0, is_rest=False, pitch="C", midi=72, chord="C", tone_role="chord_tone"),
    )
    return MelodySection(
        section_id="Verse 1",
        section_type="Verse",
        measures=2,
        beats_per_measure=4.0,
        chords=("G", "C"),
        events=events,
    )


def _valid_melody() -> PracticeMelody:
    section = _valid_section()
    return PracticeMelody(
        schema_version=SCHEMA_VERSION,
        melody_id="pm:test:beginner:0:1",
        source="generated",
        song_id="test-song",
        song_title="Test Song",
        level="Beginner",
        key_center="C",
        meter=(4, 4),
        tempo_bpm=100.0,
        style="Pop",
        seed=1,
        alt_index=0,
        generator_version="practice-melody-gen-1",
        section_order=(section.section_id,),
        sections=(section,),
    )


class TestMelodyEventRoundtrip(unittest.TestCase):
    def test_to_dict_from_dict_roundtrip(self) -> None:
        event = MelodyEvent(
            measure=2, beat=1.5, duration_beats=0.5, is_rest=False,
            pitch="F#", midi=66, chord="D", tone_role="passing",
        )
        restored = MelodyEvent.from_dict(event.to_dict())
        self.assertEqual(event, restored)

    def test_rest_roundtrip(self) -> None:
        event = MelodyEvent(measure=0, beat=0.0, duration_beats=1.0, is_rest=True, chord="G", tone_role="rest")
        restored = MelodyEvent.from_dict(event.to_dict())
        self.assertEqual(event, restored)
        self.assertIsNone(restored.pitch)
        self.assertIsNone(restored.midi)


class TestPracticeMelodyRoundtrip(unittest.TestCase):
    def test_full_melody_roundtrip(self) -> None:
        melody = _valid_melody()
        restored = PracticeMelody.from_dict(melody.to_dict())
        self.assertEqual(melody, restored)

    def test_section_by_id(self) -> None:
        melody = _valid_melody()
        self.assertIsNotNone(melody.section_by_id("Verse 1"))
        self.assertIsNone(melody.section_by_id("Nonexistent"))


class TestValidatePracticeMelody(unittest.TestCase):
    def test_valid_melody_has_no_problems(self) -> None:
        self.assertEqual(validate_practice_melody(_valid_melody()), [])

    def test_detects_measure_duration_mismatch(self) -> None:
        bad_section = MelodySection(
            section_id="Verse 1",
            section_type="Verse",
            measures=1,
            beats_per_measure=4.0,
            chords=("G",),
            events=(
                MelodyEvent(measure=0, beat=0.0, duration_beats=2.0, is_rest=False, pitch="G", midi=67, chord="G", tone_role="chord_tone"),
            ),
        )
        melody = PracticeMelody(
            schema_version=SCHEMA_VERSION, melody_id="x", source="generated", song_id="s",
            song_title="S", level="Beginner", key_center="C", meter=(4, 4), tempo_bpm=100.0,
            style="", seed=1, alt_index=0, generator_version="v1",
            section_order=("Verse 1",), sections=(bad_section,),
        )
        problems = validate_practice_melody(melody)
        self.assertTrue(any("measure totals" in p for p in problems))

    def test_detects_overlap(self) -> None:
        bad_section = MelodySection(
            section_id="Verse 1", section_type="Verse", measures=1, beats_per_measure=4.0,
            chords=("G",),
            events=(
                MelodyEvent(measure=0, beat=0.0, duration_beats=2.0, is_rest=False, pitch="G", midi=67, chord="G", tone_role="chord_tone"),
                MelodyEvent(measure=0, beat=1.0, duration_beats=3.0, is_rest=False, pitch="B", midi=71, chord="G", tone_role="chord_tone"),
            ),
        )
        melody = PracticeMelody(
            schema_version=SCHEMA_VERSION, melody_id="x", source="generated", song_id="s",
            song_title="S", level="Beginner", key_center="C", meter=(4, 4), tempo_bpm=100.0,
            style="", seed=1, alt_index=0, generator_version="v1",
            section_order=("Verse 1",), sections=(bad_section,),
        )
        problems = validate_practice_melody(melody)
        self.assertTrue(any("gap/overlap" in p for p in problems))

    def test_detects_rest_with_pitch(self) -> None:
        bad_section = MelodySection(
            section_id="Verse 1", section_type="Verse", measures=1, beats_per_measure=4.0,
            chords=("G",),
            events=(
                MelodyEvent(measure=0, beat=0.0, duration_beats=4.0, is_rest=True, pitch="G", midi=67, chord="G", tone_role="rest"),
            ),
        )
        melody = PracticeMelody(
            schema_version=SCHEMA_VERSION, melody_id="x", source="generated", song_id="s",
            song_title="S", level="Beginner", key_center="C", meter=(4, 4), tempo_bpm=100.0,
            style="", seed=1, alt_index=0, generator_version="v1",
            section_order=("Verse 1",), sections=(bad_section,),
        )
        problems = validate_practice_melody(melody)
        self.assertTrue(any("rest event carries a pitch" in p for p in problems))

    def test_detects_sounding_event_missing_pitch(self) -> None:
        bad_section = MelodySection(
            section_id="Verse 1", section_type="Verse", measures=1, beats_per_measure=4.0,
            chords=("G",),
            events=(
                MelodyEvent(measure=0, beat=0.0, duration_beats=4.0, is_rest=False, pitch=None, midi=None, chord="G", tone_role="chord_tone"),
            ),
        )
        melody = PracticeMelody(
            schema_version=SCHEMA_VERSION, melody_id="x", source="generated", song_id="s",
            song_title="S", level="Beginner", key_center="C", meter=(4, 4), tempo_bpm=100.0,
            style="", seed=1, alt_index=0, generator_version="v1",
            section_order=("Verse 1",), sections=(bad_section,),
        )
        problems = validate_practice_melody(melody)
        self.assertTrue(any("missing pitch" in p for p in problems))

    def test_detects_chords_length_mismatch(self) -> None:
        bad_section = MelodySection(
            section_id="Verse 1", section_type="Verse", measures=2, beats_per_measure=4.0,
            chords=("G",),  # only 1 chord but measures=2
            events=(
                MelodyEvent(measure=0, beat=0.0, duration_beats=4.0, is_rest=False, pitch="G", midi=67, chord="G", tone_role="chord_tone"),
                MelodyEvent(measure=1, beat=0.0, duration_beats=4.0, is_rest=False, pitch="C", midi=72, chord="C", tone_role="chord_tone"),
            ),
        )
        melody = PracticeMelody(
            schema_version=SCHEMA_VERSION, melody_id="x", source="generated", song_id="s",
            song_title="S", level="Beginner", key_center="C", meter=(4, 4), tempo_bpm=100.0,
            style="", seed=1, alt_index=0, generator_version="v1",
            section_order=("Verse 1",), sections=(bad_section,),
        )
        problems = validate_practice_melody(melody)
        self.assertTrue(any("chords length" in p for p in problems))

    def test_detects_invalid_level_and_source(self) -> None:
        melody = _valid_melody()
        bad = melody.__class__(**{**melody.__dict__, "level": "Expert", "source": "stolen"})
        problems = validate_practice_melody(bad)
        self.assertTrue(any("invalid level" in p for p in problems))
        self.assertTrue(any("invalid source" in p for p in problems))


if __name__ == "__main__":
    unittest.main()

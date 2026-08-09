"""Pattern exercise register and profile selection tests."""

from __future__ import annotations

import unittest

from music_coach_ami.exercise_patterns import (
    PATTERN_LIBRARY,
    apply_exercise_profile,
    build_degree_pattern_pitched,
    select_pattern_for_profile,
    ExerciseProfile,
)
from music_coach_ami.pipeline import run_coach_pipeline
from music_coach_ami.scale_engine import parse_scale_practice_question, spell_scale
from music_theory import midi_from_spelled_note


class RegisterInvariantTests(unittest.TestCase):
    def test_d_dorian_four_note_cells_stay_compact(self) -> None:
        scale, _, _ = spell_scale("D", "dorian")
        pitched = build_degree_pattern_pitched(
            scale, (0, 1, 2, 3), octave_count=1, start_octave=4
        )
        self.assertGreaterEqual(len(pitched), 28)
        octaves = [o for _, o in pitched]
        self.assertLessEqual(max(octaves) - min(octaves), 2)
        first_eight = pitched[:8]
        expected = [
            ("D", 4),
            ("E", 4),
            ("F", 4),
            ("G", 4),
            ("E", 4),
            ("F", 4),
            ("G", 4),
            ("A", 4),
        ]
        self.assertEqual(first_eight, expected)

    def test_broken_thirds_no_runaway(self) -> None:
        scale, _, _ = spell_scale("D", "dorian")
        pitched = build_degree_pattern_pitched(
            scale, (0, 2, 1, 3), octave_count=1, start_octave=4
        )
        octaves = [o for _, o in pitched]
        self.assertLessEqual(max(octaves) - min(octaves), 3)

    def test_max_register_grows_with_octave_span_not_cell_count(self) -> None:
        scale, _, _ = spell_scale("D", "dorian")
        one = build_degree_pattern_pitched(scale, (0, 1, 2, 3), octave_count=1, start_octave=4)
        two = build_degree_pattern_pitched(scale, (0, 1, 2, 3), octave_count=2, start_octave=4)
        span_one = max(o for _, o in one) - min(o for _, o in one)
        span_two = max(o for _, o in two) - min(o for _, o in two)
        self.assertLessEqual(span_one, 2)
        self.assertGreater(span_two, span_one)
        self.assertLessEqual(span_two, 4)


class DifficultyProfileTests(unittest.TestCase):
    def test_beginner_difficult_uses_simple_pattern(self) -> None:
        spec = parse_scale_practice_question("Give me a difficult D dorian exercise")
        profile = apply_exercise_profile(spec, level="Beginner", practice_focus="", instrument="Flute")
        self.assertEqual(spec.pattern_id, "three_note_cell")
        self.assertEqual(spec.octave_count, 1)

    def test_intermediate_difficult_four_note(self) -> None:
        spec = parse_scale_practice_question("Give me a difficult D dorian exercise")
        apply_exercise_profile(spec, level="Intermediate", practice_focus="", instrument="")
        self.assertEqual(spec.pattern_id, "four_note_sequence")

    def test_advanced_difficult_complex_pattern(self) -> None:
        spec = parse_scale_practice_question("Give me a difficult D dorian exercise")
        apply_exercise_profile(spec, level="Advanced", practice_focus="", instrument="")
        self.assertIn(
            spec.pattern_id,
            ("broken_thirds_1324", "perm_1342", "triplet_three_note"),
        )

    def test_flute_tone_focus(self) -> None:
        spec = parse_scale_practice_question("Give me a difficult D dorian exercise")
        apply_exercise_profile(spec, level="Advanced", practice_focus="Tone", instrument="Flute")
        self.assertEqual(spec.pattern_id, "three_note_cell")

    def test_flute_articulation_focus(self) -> None:
        spec = parse_scale_practice_question("Give me a difficult D dorian exercise")
        apply_exercise_profile(spec, level="Intermediate", practice_focus="Articulation", instrument="Flute")
        self.assertEqual(spec.pattern_id, "four_note_sequence")

    def test_piano_harmony_focus(self) -> None:
        spec = parse_scale_practice_question("Give me a difficult D dorian exercise")
        apply_exercise_profile(spec, level="Intermediate", practice_focus="Harmony", instrument="Piano")
        self.assertEqual(spec.pattern_id, "broken_thirds_1324")

    def test_guitar_rhythm_focus(self) -> None:
        spec = parse_scale_practice_question("Give me a difficult D dorian exercise")
        apply_exercise_profile(spec, level="Advanced", practice_focus="Rhythm", instrument="Guitar")
        self.assertEqual(spec.pattern_id, "three_note_cell")


class CoachingCopyTests(unittest.TestCase):
    def test_flute_tone_no_piano_advice(self) -> None:
        resp = run_coach_pipeline(
            "Give me a difficult D dorian exercise",
            {"instrument": "Flute", "focus": "Tone", "level": "Advanced"},
        )
        assert resp is not None
        text = resp.composed_markdown().lower()
        self.assertIn("tone", text)
        self.assertNotIn("tonguing", text)

    def test_piano_harmony_no_tonguing(self) -> None:
        resp = run_coach_pipeline(
            "Give me a difficult D dorian exercise",
            {"instrument": "Piano", "focus": "Harmony", "level": "Intermediate"},
            ami_ctx={"instrument": "Piano", "focus": "Harmony", "level": "Intermediate"},
        )
        assert resp is not None
        text = resp.composed_markdown().lower()
        self.assertIn("modal", text)
        self.assertNotIn("tongue", text)


if __name__ == "__main__":
    unittest.main()

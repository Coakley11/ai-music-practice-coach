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
from music_coach_ami.scale_engine import (
    format_scale_request_summary,
    generate_scale_practice,
    parse_scale_practice_question,
    spell_scale,
)
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

    def test_broken_thirds_first_eight_cells(self) -> None:
        scale, _, _ = spell_scale("D", "dorian")
        pitched = build_degree_pattern_pitched(
            scale, (0, 2, 1, 3), octave_count=2, start_octave=4
        )
        expected_rows = [
            [("D", 4), ("F", 4), ("E", 4), ("G", 4)],
            [("E", 4), ("G", 4), ("F", 4), ("A", 4)],
            [("F", 4), ("A", 4), ("G", 4), ("B", 4)],
            [("G", 4), ("B", 4), ("A", 4), ("C", 5)],
            [("A", 4), ("C", 5), ("B", 4), ("D", 5)],
            [("B", 4), ("D", 5), ("C", 5), ("E", 5)],
            [("C", 5), ("E", 5), ("D", 5), ("F", 5)],
            [("D", 5), ("F", 5), ("E", 5), ("G", 5)],
        ]
        for idx, row in enumerate(expected_rows):
            self.assertEqual(pitched[idx * 4 : (idx + 1) * 4], row, msg=f"cell {idx + 1}")

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
        self.assertIn(
            spec.pattern_id,
            ("four_note_sequence", "broken_thirds_1324"),
        )

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
        self.assertEqual(spec.pattern_id, "four_note_sequence")

    def test_flute_articulation_focus(self) -> None:
        spec = parse_scale_practice_question("Give me a medium D dorian exercise for articulation on the flute")
        apply_exercise_profile(spec, level="intermediate", practice_focus="articulation", instrument="Flute")
        self.assertEqual(spec.pattern_id, "broken_thirds_1324")

    def test_piano_harmony_focus(self) -> None:
        spec = parse_scale_practice_question("Give me a difficult D dorian exercise")
        apply_exercise_profile(spec, level="Intermediate", practice_focus="Harmony", instrument="Piano")
        self.assertEqual(spec.pattern_id, "broken_thirds_1324")

    def test_guitar_rhythm_focus(self) -> None:
        spec = parse_scale_practice_question("Give me a difficult D dorian exercise")
        apply_exercise_profile(spec, level="Advanced", practice_focus="Rhythm", instrument="Guitar")
        self.assertEqual(spec.pattern_id, "three_note_cell")


class ExerciseIntentTests(unittest.TestCase):
    def test_medium_e_dorian_tone_flute_uses_pattern(self) -> None:
        q = "Give me a medium level E Dorian exercise thats good to build tone on the flute"
        spec = parse_scale_practice_question(q, instrument="Flute")
        self.assertTrue(spec.wants_structured_exercise)
        profile = apply_exercise_profile(
            spec,
            level="intermediate",
            practice_focus="tone",
            instrument="Flute",
            level_provenance="question",
            focus_provenance="question",
        )
        self.assertEqual(spec.pattern_id, "four_note_sequence")
        self.assertEqual(spec.articulation, "slurred")
        result = generate_scale_practice(spec)
        self.assertIn("Pattern", " ".join(format_scale_request_summary(spec)))

    def test_articulation_mixed_slurs_parsed(self) -> None:
        spec = parse_scale_practice_question(
            "Give me a difficult D Dorian articulation exercise with a mix of short notes and slurs",
            instrument="Flute",
        )
        self.assertEqual(spec.articulation, "slur2_short2")
        profile = apply_exercise_profile(
            spec,
            level="advanced",
            practice_focus="articulation",
            instrument="Flute",
        )
        self.assertTrue(spec.pattern_id)
        self.assertEqual(profile.articulation, "slur2_short2")

    def test_easy_medium_difficult_differ(self) -> None:
        cases = [
            ("Give me an easy D Dorian exercise.", "three_note_cell"),
            ("Give me a medium D Dorian exercise.", "four_note_sequence"),
            ("Give me a difficult D Dorian exercise.", "broken_thirds_1324"),
        ]
        ids: set[str] = set()
        for q, _expected in cases:
            spec = parse_scale_practice_question(q)
            apply_exercise_profile(
                spec,
                level={"easy": "beginner", "medium": "intermediate", "difficult": "advanced"}[
                    "easy" if "easy" in q else "medium" if "medium" in q else "difficult"
                ],
                practice_focus="",
                instrument="Flute",
            )
            ids.add(spec.pattern_id)
        self.assertEqual(len(ids), 3)

    def test_flute_in_question_overrides_empty_context(self) -> None:
        from music_coach_ami.router import route_question

        req = route_question(
            "Give me a medium E Dorian exercise on the flute",
            {"instrument": "Piano"},
        )
        self.assertEqual(req.entities.instrument, "Flute")

    def test_no_silent_piano_in_guidance(self) -> None:
        from music_coach_ami.router import route_question

        req = route_question("Give me a difficult D dorian pattern.", {})
        from music_coach_ami.solvers import solve_scale_practice

        resp = solve_scale_practice(req)
        assert resp is not None
        text = resp.composed_markdown()
        self.assertIn("your instrument", text.lower())
        self.assertNotIn("on **piano**", text.lower())

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
            "Give me a difficult D dorian harmony exercise on piano",
            {},
        )
        assert resp is not None
        text = resp.composed_markdown().lower()
        self.assertIn("modal", text)
        self.assertNotIn("tongue", text)


if __name__ == "__main__":
    unittest.main()

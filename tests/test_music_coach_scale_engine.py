"""Deterministic scale engine and router tests for AMI coach."""

from __future__ import annotations

import unittest

from music_coach_ami.pipeline import run_coach_submit
from music_coach_ami.router import CoachIntent, route_question
from music_coach_ami.scale_engine import (
    build_interval_pairs,
    generate_scale_practice,
    parse_scale_practice_question,
    spell_scale,
)
from music_coach_ami.solvers import solve_practice_plan
from music_coach_ami.types import CoachConstraints, CoachContext, CoachRequest, ExtractedEntities


class ScaleSpellingTests(unittest.TestCase):
    def test_c_major(self) -> None:
        notes, _, _ = spell_scale("C", "major")
        self.assertEqual(notes, ["C", "D", "E", "F", "G", "A", "B"])

    def test_eb_major(self) -> None:
        notes, _, _ = spell_scale("Eb", "major")
        self.assertEqual(notes, ["Eb", "F", "G", "Ab", "Bb", "C", "D"])
        self.assertNotIn("A#", notes)
        self.assertNotIn("D#", notes)

    def test_c_sharp_major(self) -> None:
        notes, _, _ = spell_scale("C#", "major")
        self.assertIn("E#", notes)
        self.assertIn("B#", notes)
        self.assertNotIn("F", notes[3:4])

    def test_g_natural_minor(self) -> None:
        notes, _, _ = spell_scale("G", "natural minor")
        self.assertIn("Bb", notes)
        self.assertIn("Eb", notes)
        self.assertNotIn("A#", notes)

    def test_f_harmonic_minor(self) -> None:
        notes, _, _ = spell_scale("F", "harmonic minor")
        self.assertEqual(notes[0], "F")
        self.assertIn("Ab", notes)
        self.assertIn("Db", notes)
        self.assertIn("E", notes)


class ScaleIntervalTests(unittest.TestCase):
    def test_c_major_thirds(self) -> None:
        scale, _, _ = spell_scale("C", "major")
        pairs = build_interval_pairs(scale, 2)
        self.assertEqual(pairs[0], ("C", "E"))
        self.assertEqual(pairs[1], ("D", "F"))

    def test_eb_major_thirds_spelling(self) -> None:
        scale, _, _ = spell_scale("Eb", "major")
        pairs = build_interval_pairs(scale, 2)
        flat_pair = pairs[0]
        self.assertEqual(flat_pair, ("Eb", "G"))

    def test_c_sharp_major_thirds(self) -> None:
        scale, _, _ = spell_scale("C#", "major")
        pairs = build_interval_pairs(scale, 2)
        self.assertTrue(any("E#" in p for pair in pairs for p in pair))

    def test_fourths_fifths(self) -> None:
        scale, _, _ = spell_scale("C", "major")
        self.assertEqual(build_interval_pairs(scale, 3)[0], ("C", "F"))
        self.assertEqual(build_interval_pairs(scale, 4)[0], ("C", "G"))


class ScaleRouterTests(unittest.TestCase):
    def test_show_d_major_thirds(self) -> None:
        req = route_question("Show me D major in thirds", {})
        self.assertEqual(req.intent, CoachIntent.SCALE_PRACTICE)

    def test_harmonic_minor_sixths(self) -> None:
        req = route_question("Write Eb harmonic minor in sixths", {})
        self.assertEqual(req.intent, CoachIntent.SCALE_PRACTICE)

    def test_what_is_major_scale_theory(self) -> None:
        req = route_question("What is a major scale?", {})
        self.assertEqual(req.intent, CoachIntent.THEORY_EXPLANATION)


class ScaleGeneratorTests(unittest.TestCase):
    def test_generates_abc(self) -> None:
        spec = parse_scale_practice_question("Show me the Eb major scale in sheet music.")
        result = generate_scale_practice(spec)
        self.assertIn("K:Eb", result.abc)
        self.assertNotIn("K:D\n", result.abc)
        self.assertEqual(result.abc_key, "Eb")

    def test_eb_major_straight_octave_sequence(self) -> None:
        spec = parse_scale_practice_question("Show me the E\u266d major scale in sheet music.")
        result = generate_scale_practice(spec)
        self.assertEqual(
            result.practice_sequence,
            ["Eb", "F", "G", "Ab", "Bb", "C", "D", "Eb"],
        )
        self.assertIn("E\u266d", result.written_sequence)
        self.assertIn("A\u266d", result.written_sequence)
        self.assertNotIn("interval pair", " ".join(result.practice_guidance).lower())
        self.assertTrue(all("interval pair" not in x.lower() for x in result.what_to_listen_for))

    def test_c_sharp_major_sequence(self) -> None:
        spec = parse_scale_practice_question("Show me C# major in sheet music.")
        result = generate_scale_practice(spec)
        self.assertEqual(result.practice_sequence[0], "C#")
        self.assertEqual(result.practice_sequence[-1], "C#")
        self.assertIn("E#", result.scale_degrees)
        self.assertIn("K:C#", result.abc)

    def test_g_natural_minor_sequence(self) -> None:
        spec = parse_scale_practice_question("Show me G minor scale in sheet music.")
        result = generate_scale_practice(spec)
        self.assertEqual(
            result.practice_sequence,
            ["G", "A", "Bb", "C", "D", "Eb", "F", "G"],
        )
        self.assertIn("K:Gm", result.abc)

    def test_thirds_allow_interval_pair_coaching(self) -> None:
        spec = parse_scale_practice_question("Show me Eb major in thirds")
        result = generate_scale_practice(spec)
        joined = " ".join(result.practice_guidance + result.what_to_listen_for).lower()
        self.assertIn("interval pair", joined)

    def test_composed_markdown_omits_raw_abc(self) -> None:
        _, resp = run_coach_submit("Show me the E\u266d major scale in sheet music.", {})
        assert resp is not None
        md = resp.composed_markdown()
        self.assertTrue(resp.notation_abc)
        self.assertNotIn("Sheet music (ABC)", md)
        self.assertNotIn("```abc", md)
        self.assertNotIn("X:1", md)
        self.assertNotIn("interval pair", md.lower())

    def test_multiple_interval_patterns(self) -> None:
        spec = parse_scale_practice_question(
            "Give me the Bb major scale in thirds, fourths, fifths, sixths and sevenths for practice."
        )
        self.assertGreater(len(spec.interval_patterns), 3)
        result = generate_scale_practice(spec)
        self.assertTrue(result.abc.count("X:1") >= 3)


class TonePracticePlanTests(unittest.TestCase):
    def _tone_req(self, **ctx: object) -> CoachRequest:
        return CoachRequest(
            raw_question="Give me a 30-minute flute practice plan focused on tone",
            normalized_question="Give me a 30-minute flute practice plan focused on tone",
            intent=CoachIntent.PRACTICE_PLAN,
            confidence=0.9,
            entities=ExtractedEntities(instrument="Flute"),
            constraints=CoachConstraints(requested_duration_minutes=30, tone_focus=True),
            context=CoachContext(
                instrument="Flute",
                level="Beginner",
                active_song_title=str(ctx.get("active_song_title") or ""),
                active_section=str(ctx.get("active_section") or ""),
            ),
        )

    def test_thirty_minute_total_in_blocks(self) -> None:
        resp = solve_practice_plan(self._tone_req())
        text = resp.composed_markdown()
        self.assertIn("30-minute", text)
        self.assertIn("8 min", text)
        self.assertIn("Today's goal", text)

    def test_actionable_not_generic_only(self) -> None:
        resp = solve_practice_plan(self._tone_req())
        text = resp.composed_markdown()
        self.assertIn("long tones", text.lower())
        self.assertIn("Listen for", text)
        self.assertIn("Ready when", text)
        self.assertNotIn("Anchor section work on Full Song", text)

    def test_song_integrated_naturally(self) -> None:
        resp = solve_practice_plan(self._tone_req(active_song_title="Say"))
        text = resp.composed_markdown()
        self.assertIn('"Say"', text)
        self.assertNotIn("Tie at least one block", text)

    def test_solver_pipeline_scale(self) -> None:
        _, resp = run_coach_submit("Give me Eb major in thirds", {}, ami_ctx={"instrument": "Flute"})
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertEqual(resp.source_solver, "ScalePracticeSolver")
        self.assertTrue(resp.notation_abc)


if __name__ == "__main__":
    unittest.main()

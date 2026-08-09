"""Deterministic scale engine and router tests for AMI coach."""

from __future__ import annotations

import unittest

from music_coach_ami.pipeline import run_coach_submit
from music_coach_ami.router import CoachIntent, route_question
from music_coach_ami.coach_instrument import resolve_coach_instrument
from music_coach_ami.scale_engine import (
    build_interval_pairs,
    build_interval_pairs_descending_over_octaves,
    build_interval_pairs_over_octaves,
    generate_scale_practice,
    pairs_to_pitched_notes,
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

    def test_modifier_prompts_still_scale_practice(self) -> None:
        prompts = [
            "Show me one octave of Eb major in quarter notes.",
            "Show me two octaves of Eb major in eighth notes.",
            "Give me Bb major, two octaves, slurred eighth notes.",
            "Show me Eb major descending.",
            "Give me Eb major, two octaves, slurred eighth notes at 80 BPM.",
        ]
        for q in prompts:
            req = route_question(q, {})
            self.assertEqual(req.intent, CoachIntent.SCALE_PRACTICE, msg=q)

    def test_pipeline_returns_solver_for_modifier_prompts(self) -> None:
        _, resp = run_coach_submit("Show me one octave of Eb major in quarter notes.", {})
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertEqual(resp.source_solver, "ScalePracticeSolver")

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
        spec = parse_scale_practice_question(
            "Show me one octave of the E\u266d major scale in sheet music."
        )
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
        spec = parse_scale_practice_question("Show me one octave of G minor scale in sheet music.")
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
        self.assertIn("pair", joined)

    def test_eb_major_abc_no_redundant_flats(self) -> None:
        spec = parse_scale_practice_question("Show me Eb major scale in sheet music")
        result = generate_scale_practice(spec)
        self.assertIn("K:Eb", result.abc)
        body = result.abc.split("K:Eb", 1)[-1]
        for token in ("_E", "_e", "_A", "_a", "_B", "_b"):
            self.assertNotIn(token, body, msg=f"redundant accidental {token} in {body[:120]}")

    def test_c_sharp_major_abc_no_redundant_sharps(self) -> None:
        spec = parse_scale_practice_question("Show me C# major in sheet music")
        result = generate_scale_practice(spec)
        self.assertIn("K:C#", result.abc)
        body = result.abc.split("K:C#", 1)[-1]
        for letter in ("C", "D", "E", "F", "G", "A", "B"):
            self.assertNotIn(f"^{letter}", body)
            self.assertNotIn(f"^{letter.lower()}", body)

    def test_f_harmonic_minor_raises_seventh_with_natural_sign(self) -> None:
        spec = parse_scale_practice_question("Show me F harmonic minor scale in sheet music")
        result = generate_scale_practice(spec)
        self.assertIn("K:Fm", result.abc)
        body = result.abc.split("K:Fm", 1)[-1]
        self.assertTrue("=E" in body or "=e" in body, body)

    def test_c_sharp_major_thirds_pairs_spelling(self) -> None:
        scale, _, ref = spell_scale("C#", "major")
        pairs = build_interval_pairs(scale, 2)
        expected = [
            ("C#", "E#"),
            ("D#", "F#"),
            ("E#", "G#"),
            ("F#", "A#"),
            ("G#", "B#"),
            ("A#", "C#"),
            ("B#", "D#"),
        ]
        self.assertEqual(pairs, expected)

    def test_c_sharp_major_thirds_octave_continuity(self) -> None:
        scale, _, _ = spell_scale("C#", "major")
        pairs = build_interval_pairs(scale, 2)
        pitched = pairs_to_pitched_notes(pairs, direction="ascending", start_octave=4)
        from music_theory import midi_from_spelled_note

        self.assertEqual(
            pitched,
            [
                ("C#", 4),
                ("E#", 4),
                ("D#", 4),
                ("F#", 4),
                ("E#", 4),
                ("G#", 4),
                ("F#", 4),
                ("A#", 4),
                ("G#", 4),
                ("B#", 4),
                ("A#", 4),
                ("C#", 5),
                ("B#", 4),
                ("D#", 5),
            ],
        )
        source_midis = [
            midi_from_spelled_note(n, octave=o) for n, o in pitched[0::2]
        ]
        target_midis = [
            midi_from_spelled_note(n, octave=o) for n, o in pitched[1::2]
        ]
        for i in range(len(source_midis) - 1):
            self.assertLess(source_midis[i], source_midis[i + 1])
        for src, tgt in zip(source_midis, target_midis):
            self.assertGreater(tgt, src)
        # Broken-thirds contour: next source sits below previous target.
        flat_midis = [midi_from_spelled_note(n, octave=o) for n, o in pitched]
        self.assertLess(flat_midis[2], flat_midis[1])

    def test_interval_octave_continuity_fourths_through_sevenths(self) -> None:
        scale, _, _ = spell_scale("C#", "major")
        from music_theory import midi_from_spelled_note

        for step, _label in ((3, "fourths"), (4, "fifths"), (5, "sixths"), (6, "sevenths")):
            pairs = build_interval_pairs(scale, step)
            pitched = pairs_to_pitched_notes(pairs, direction="ascending", start_octave=4)
            source_midis = [
                midi_from_spelled_note(n, octave=o) for n, o in pitched[0::2]
            ]
            target_midis = [
                midi_from_spelled_note(n, octave=o) for n, o in pitched[1::2]
            ]
            for i in range(len(source_midis) - 1):
                self.assertLess(source_midis[i], source_midis[i + 1])
            for src, tgt in zip(source_midis, target_midis):
                self.assertGreater(tgt, src)
            flat_midis = [midi_from_spelled_note(n, octave=o) for n, o in pitched]
            if len(flat_midis) >= 4:
                self.assertLess(flat_midis[2], flat_midis[1])

    def test_scale_reference_includes_upper_tonic(self) -> None:
        spec = parse_scale_practice_question("Show me C# major in sheet music")
        result = generate_scale_practice(spec)
        self.assertTrue(result.scale_reference.endswith("C#") or result.scale_reference.endswith("C\u266f"))

    def test_instrument_flute_from_context(self) -> None:
        spec = parse_scale_practice_question("Show me Eb major scale", instrument="Flute")
        result = generate_scale_practice(spec)
        self.assertIn("Flute", result.practice_guidance[0])

    def test_instrument_fallback_your_instrument(self) -> None:
        spec = parse_scale_practice_question("Show me Eb major scale", instrument="")
        result = generate_scale_practice(spec)
        self.assertIn("your instrument", result.practice_guidance[0].lower())

    def test_solver_markdown_no_diagnostic_spelling_label(self) -> None:
        _, resp = run_coach_submit("Show me the E\u266d major scale in sheet music.", {})
        assert resp is not None
        md = resp.composed_markdown()
        self.assertNotIn("flat key spelling", md.lower())
        self.assertNotIn("Use the staff below", md)
        self.assertIn("E\u266d major", md)

    def test_composed_markdown_omits_raw_abc(self) -> None:
        _, resp = run_coach_submit("Show me the E\u266d major scale in sheet music.", {})
        assert resp is not None
        md = resp.composed_markdown()
        self.assertTrue(resp.notation_abc)
        self.assertNotIn("Sheet music (ABC)", md)
        self.assertNotIn("```abc", md)
        self.assertNotIn("X:1", md)
        self.assertNotIn("interval pair", md.lower())

    def test_submit_uses_flute_not_default_piano(self) -> None:
        ss = {"instrument": "Flute", "instrument_change_source": "sidebar"}
        _, resp = run_coach_submit("Show me Eb major scale in sheet music", ss)
        assert resp is not None
        md = resp.composed_markdown()
        self.assertIn("Flute", md)
        self.assertNotIn("comfortable register on **Piano**", md)

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


class CoachInstrumentResolutionTests(unittest.TestCase):
    def test_default_piano_session_is_unknown(self) -> None:
        ss = {"instrument": "Piano"}
        self.assertEqual(resolve_coach_instrument(ss), "")

    def test_flute_session_is_used(self) -> None:
        ss = {"instrument": "Flute", "instrument_change_source": "sidebar"}
        self.assertEqual(resolve_coach_instrument(ss), "Flute")

    def test_explicit_piano_with_change_source(self) -> None:
        ss = {"instrument": "Piano", "instrument_change_source": "sidebar"}
        self.assertEqual(resolve_coach_instrument(ss), "Piano")

    def test_routed_submit_flute_not_piano(self) -> None:
        ss = {"instrument": "Flute", "instrument_change_source": "sidebar"}
        _, resp = run_coach_submit("Show me Eb major scale in sheet music", ss)
        assert resp is not None
        self.assertIn("Flute", resp.composed_markdown())
        self.assertNotIn("**Piano**", resp.composed_markdown())


class ScalePracticeRequestTests(unittest.TestCase):
    def test_one_octave_eb_quarters(self) -> None:
        spec = parse_scale_practice_question("Show me one octave of Eb major in quarter notes.")
        self.assertEqual(spec.octave_count, 1)
        self.assertTrue(spec.octave_count_explicit)
        self.assertEqual(spec.note_value, "quarter")
        result = generate_scale_practice(spec)
        self.assertIn("L:1/4", result.abc)
        self.assertEqual(len(result.practice_sequence), 8)

    def test_two_octaves_eb_eighths(self) -> None:
        spec = parse_scale_practice_question("Show me two octaves of Eb major in eighth notes.")
        self.assertEqual(spec.octave_count, 2)
        self.assertEqual(spec.note_value, "eighth")
        result = generate_scale_practice(spec)
        self.assertIn("L:1/8", result.abc)
        self.assertGreater(len(result.practice_sequence), 10)

    def test_c_sharp_thirds_two_octaves_eighths(self) -> None:
        spec = parse_scale_practice_question(
            "Give me C# major in thirds, two octaves, as eighth notes."
        )
        self.assertEqual(spec.octave_count, 2)
        self.assertEqual(spec.note_value, "eighth")
        pairs = build_interval_pairs_over_octaves(spell_scale("C#", "major")[0], 2, 2)
        self.assertEqual(len(pairs), 14)
        result = generate_scale_practice(spec)
        self.assertIn("L:1/8", result.abc)
        self.assertIn("K:C#", result.abc)

    def test_f_harmonic_minor_sixths_both_eighths_72(self) -> None:
        spec = parse_scale_practice_question(
            "Give me F harmonic minor in sixths, ascending and descending, in eighth notes at 72 BPM."
        )
        self.assertEqual(spec.direction, "both")
        self.assertEqual(spec.note_value, "eighth")
        self.assertEqual(spec.tempo_bpm, 72)
        result = generate_scale_practice(spec)
        self.assertIn("=E", result.abc.split("K:Fm", 1)[-1])
        self.assertIn("Q:1/4=72", result.abc)

    def test_d_major_descending_sixteenths_80(self) -> None:
        spec = parse_scale_practice_question(
            "Show me D major descending, one octave, in sixteenth notes at 80 BPM."
        )
        self.assertEqual(spec.direction, "descending")
        self.assertEqual(spec.octave_count, 1)
        self.assertEqual(spec.note_value, "sixteenth")
        self.assertEqual(spec.tempo_bpm, 80)
        result = generate_scale_practice(spec)
        self.assertIn("L:1/16", result.abc)

    def test_bb_slurred_eighths_two_octaves(self) -> None:
        spec = parse_scale_practice_question("Give me Bb major, two octaves, slurred eighth notes.")
        self.assertEqual(spec.articulation, "slurred")
        self.assertEqual(spec.note_value, "eighth")
        result = generate_scale_practice(spec)
        self.assertIn("(", result.abc)
        self.assertIn("L:1/8", result.abc)

    def test_default_octave_count_is_two(self) -> None:
        spec = parse_scale_practice_question("Show me Eb major scale")
        self.assertEqual(spec.octave_count, 2)
        self.assertFalse(spec.octave_count_explicit)

    def test_thirds_broken_contour_preserved(self) -> None:
        scale, _, _ = spell_scale("C#", "major")
        pairs = build_interval_pairs(scale, 2)
        pitched = pairs_to_pitched_notes(pairs, direction="ascending", start_octave=4)
        from music_theory import midi_from_spelled_note

        flat = [midi_from_spelled_note(n, octave=o) for n, o in pitched]
        self.assertLess(flat[2], flat[1])


class DescendingIntervalTests(unittest.TestCase):
    def test_f_harmonic_minor_descending_sixths_are_sixths_below(self) -> None:
        scale, _, _ = spell_scale("F", "harmonic minor")
        step = 5
        pairs = build_interval_pairs_descending_over_octaves(scale, step, 1)
        pitched = pairs_to_pitched_notes(
            pairs,
            direction="descending",
            start_octave=4,
            scale=scale,
            step=step,
            octave_count=1,
        )
        from music_theory import midi_from_spelled_note

        for (a, b), (pa, oa), (pb, ob) in zip(
            pairs, pitched[0::2], pitched[1::2], strict=True
        ):
            self.assertEqual(pa, a)
            self.assertEqual(pb, b)
            ai, bi = scale.index(a), scale.index(b)
            self.assertEqual((ai - bi) % len(scale), step)
            self.assertLess(midi_from_spelled_note(b, octave=ob), midi_from_spelled_note(a, octave=oa))

    def test_both_phases_not_reversed_ascending_stream(self) -> None:
        scale, _, _ = spell_scale("F", "harmonic minor")
        step = 5
        pitched = pairs_to_pitched_notes(
            [],
            direction="both",
            start_octave=4,
            scale=scale,
            step=step,
            octave_count=1,
        )
        up_len = len(build_interval_pairs_over_octaves(scale, step, 1)) * 2
        self.assertEqual(len(pitched), up_len * 2)
        down_pairs = build_interval_pairs_descending_over_octaves(scale, step, 1)
        self.assertEqual(down_pairs[0][0], scale[0])

    def test_descending_thirds_through_sevenths(self) -> None:
        scale, _, _ = spell_scale("C", "major")
        from music_theory import midi_from_spelled_note

        for step in (2, 3, 4, 6):
            pairs = build_interval_pairs_descending_over_octaves(scale, step, 1)
            pitched = pairs_to_pitched_notes(
                pairs,
                direction="descending",
                start_octave=4,
                scale=scale,
                step=step,
                octave_count=1,
            )
            for (a, b), (_, oa), (_, ob) in zip(pairs, pitched[0::2], pitched[1::2], strict=True):
                self.assertEqual((scale.index(a) - scale.index(b)) % len(scale), step)
                self.assertLess(
                    midi_from_spelled_note(b, octave=ob),
                    midi_from_spelled_note(a, octave=oa),
                )


if __name__ == "__main__":
    unittest.main()

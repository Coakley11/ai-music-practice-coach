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
    straight_scale_degree_count,
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
        joined = "\n".join(result.notation_sections or [result.abc])
        self.assertTrue(joined.count("X:1") >= 3)


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
        body = result.abc.split("K:Fm", 1)[-1]
        self.assertTrue("=E" in body or "=e" in body, msg=body)
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


class ScaleCoachingCopyTests(unittest.TestCase):
    def test_bb_major_listen_for_uses_only_scale_accidentals(self) -> None:
        spec = parse_scale_practice_question("Give me Bb major, two octaves, slurred eighth notes.")
        result = generate_scale_practice(spec)
        from music_theory import format_musician_note_name

        allowed = {format_musician_note_name(n, result.reference_key) for n in result.scale_degrees}
        joined = " ".join(result.what_to_listen_for)
        self.assertNotIn("A\u266d", joined)
        self.assertIn("B\u266d", joined)
        self.assertIn("E\u266d", joined)
        for token in joined.replace(",", " ").replace("and ", " ").split():
            if "\u266d" in token or "\u266f" in token:
                self.assertIn(token.rstrip("."), allowed, msg=f"{token} not in scale")

    def test_eb_major_listen_for_lists_eb_ab_bb(self) -> None:
        spec = parse_scale_practice_question("Show me one octave of Eb major.")
        result = generate_scale_practice(spec)
        joined = " ".join(result.what_to_listen_for)
        self.assertIn("E\u266d", joined)
        self.assertIn("A\u266d", joined)
        self.assertIn("B\u266d", joined)

    def test_straight_slurred_guidance_not_pair_wording(self) -> None:
        spec = parse_scale_practice_question("Give me Bb major, two octaves, slurred eighth notes.")
        result = generate_scale_practice(spec)
        joined = " ".join(result.practice_guidance).lower()
        self.assertNotIn("slurred pairs", joined)
        self.assertIn("smoothly connected", joined)

    def test_interval_both_shows_ascending_and_descending_pattern_labels(self) -> None:
        spec = parse_scale_practice_question(
            "Give me F harmonic minor in sixths, ascending and descending, in eighth notes at 72 BPM."
        )
        result = generate_scale_practice(spec)
        self.assertTrue(result.interval_pairs_display)
        self.assertTrue(result.interval_pairs_display_descending)
        self.assertIn("\u266d", result.interval_pairs_display_descending)

    def test_straight_slurred_abc_uses_phrase_slurs(self) -> None:
        spec = parse_scale_practice_question("Give me Bb major, two octaves, slurred eighth notes.")
        result = generate_scale_practice(spec)
        body = result.abc.split("K:Bb", 1)[-1]
        self.assertIn("(", body)
        self.assertRegex(body, r"\([^)]+\s[^)]+\s[^)]+\)")


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


class ModeParsingTests(unittest.TestCase):
    def test_e_flat_minor_dorian_phrase(self) -> None:
        spec = parse_scale_practice_question(
            "Show me E flat minor dorian scale in 2 octaves with quarter notes, 4/4 with measures."
        )
        self.assertEqual(spec.tonic, "Eb")
        self.assertEqual(spec.scale_type, "dorian")
        result = generate_scale_practice(spec)
        self.assertIn("dorian", result.display_label.lower())
        self.assertIn("Eb", result.scale_degrees[0])
        self.assertIn("Gb", result.scale_degrees)
        self.assertIn("Db", result.scale_degrees)

    def test_d_dorian_key_signature_is_c_major(self) -> None:
        spec = parse_scale_practice_question("Give me D dorian pattern difficult exercise")
        self.assertEqual(spec.tonic, "D")
        self.assertEqual(spec.scale_type, "dorian")
        self.assertEqual(spec.exercise_pattern, "four_note_sequence")
        result = generate_scale_practice(spec)
        self.assertIn("K:C", result.abc)

    def test_mode_tonic_spellings(self) -> None:
        cases = [
            ("Show me E flat dorian scale.", "Eb", "dorian"),
            ("Show me B flat dorian scale.", "Bb", "dorian"),
            ("Give me F sharp dorian scale.", "F#", "dorian"),
            ("Show me C sharp mixolydian scale.", "C#", "mixolydian"),
            ("Show me A flat lydian scale.", "Ab", "lydian"),
        ]
        for prompt, tonic, stype in cases:
            spec = parse_scale_practice_question(prompt)
            self.assertEqual(spec.tonic, tonic, msg=prompt)
            self.assertEqual(spec.scale_type, stype, msg=prompt)

    def test_melodic_minor_descending_two_octaves_on_staff(self) -> None:
        spec = parse_scale_practice_question(
            "Show me D melodic minor, ascending and descending, two octaves, "
            "in quarter notes. Put it in 4/4 time, with measures."
        )
        result = generate_scale_practice(spec)
        self.assertEqual(len(result.notation_sections), 2)
        desc = result.notation_sections[1]
        import music_coach_ami.scale_engine as se

        desc_deg = se.spell_scale_degrees_for_direction("D", "melodic minor", "descending")
        desc_seq = se._melodic_descending_note_sequence(desc_deg, 2)
        self.assertEqual(len(desc_seq), 15)


class TonicParserTests(unittest.TestCase):
    def test_article_a_d_major_not_a_tonic(self) -> None:
        spec = parse_scale_practice_question(
            "Give me a D major scale descending in half notes with measures in 3/4 time."
        )
        self.assertEqual(spec.tonic, "D")
        self.assertIn("scale_phrase", spec.tonic_provenance)
        result = generate_scale_practice(spec)
        self.assertIn("D major", result.display_label)

    def test_tonic_phrase_regressions(self) -> None:
        cases = [
            ("Give me a C major scale.", "C"),
            ("Show me a B\u266d major scale.", "Bb"),
            ("Write a G minor scale.", "G"),
            ("Give me an A major scale.", "A"),
            ("Give me A major.", "A"),
            ("Give me the D major scale.", "D"),
            ("Give me two octaves of D major.", "D"),
        ]
        for prompt, tonic in cases:
            spec = parse_scale_practice_question(prompt)
            self.assertEqual(spec.tonic, tonic, msg=prompt)


class StraightScaleInvariantTests(unittest.TestCase):
    def test_two_octaves_heptatonic_is_fifteen_events(self) -> None:
        spec = parse_scale_practice_question("Show me two octaves of B\u266d major in eighth notes.")
        result = generate_scale_practice(spec)
        self.assertEqual(len(result.practice_sequence), 15)
        self.assertEqual(straight_scale_degree_count(2), 15)

    def test_one_octave_heptatonic_is_eight_events(self) -> None:
        spec = parse_scale_practice_question("Show me one octave of Eb major in quarter notes.")
        result = generate_scale_practice(spec)
        self.assertEqual(len(result.practice_sequence), 8)

    def test_d_melodic_both_notation_sections(self) -> None:
        spec = parse_scale_practice_question(
            "Show me D melodic minor, ascending and descending, two octaves, "
            "in quarter notes. Put it in 4/4 time, with measures."
        )
        result = generate_scale_practice(spec)
        self.assertEqual(len(result.notation_sections), 2)
        self.assertEqual(len([n for n in result.practice_sequence[:15]]), 15)

    def test_half_notes_3_4_no_double_duration(self) -> None:
        spec = parse_scale_practice_question(
            "Give me a D major scale descending in half notes with measures in 3/4 time."
        )
        result = generate_scale_practice(spec)
        self.assertIn("L:1/2", result.abc)
        body = result.abc.split("K:D", 1)[-1]
        self.assertNotRegex(body, r"[A-Ga-g][^ \n|]*22")
        self.assertEqual(len(result.practice_sequence), 15)

    def test_bb_68_beams_not_slurs(self) -> None:
        spec = parse_scale_practice_question(
            "Give me B\u266d major in 6/8, two octaves, eighth notes, at 84 BPM."
        )
        result = generate_scale_practice(spec)
        body = result.abc.split("K:Bb", 1)[-1]
        self.assertGreaterEqual(body.count("|"), 2)
        self.assertNotIn("( ", body)
        self.assertEqual(len(result.practice_sequence), 15)

    def test_eb_triplets_start_with_tuplet(self) -> None:
        spec = parse_scale_practice_question(
            "Give me E\u266d major in thirds, two octaves, as eighth-note triplets at 72 BPM."
        )
        result = generate_scale_practice(spec)
        joined = "\n".join(result.notation_sections or [result.abc])
        idx = joined.find("K:Eb")
        body = joined[idx + 4 :] if idx >= 0 else joined
        first_music = body.split("\n", 1)[-1].lstrip()
        self.assertTrue(first_music.startswith("(3"))


class LiveAcceptanceRegressionTests(unittest.TestCase):
    _D_MELODIC_PROMPT = (
        "Show me D melodic minor, ascending and descending, two octaves, "
        "in quarter notes. Put it in 4/4 time, with measures."
    )

    def test_d_melodic_minor_spelling_and_display(self) -> None:
        from music_coach_ami.scale_engine import format_scale_request_summary, spell_scale_degrees_for_direction
        from music_theory import midi_from_spelled_note

        asc = spell_scale_degrees_for_direction("D", "melodic minor", "ascending")
        self.assertEqual(asc, ["D", "E", "F", "G", "A", "B", "C#"])
        self.assertIn("C#", asc)
        self.assertNotIn("Db", asc)

        spec = parse_scale_practice_question(self._D_MELODIC_PROMPT)
        self.assertTrue(spec.wants_measures)
        self.assertEqual(spec.meter, "4/4")
        self.assertTrue(spec.note_value_explicit)
        summary = format_scale_request_summary(spec)
        self.assertTrue(any("Quarter" in line for line in summary))
        self.assertTrue(any("4/4" in line for line in summary))

        result = generate_scale_practice(spec)
        listen = " ".join(result.what_to_listen_for)
        self.assertIn("way up", listen.lower())
        self.assertIn("way down", listen.lower())
        self.assertIn("C\u266f", result.scale_reference)
        self.assertNotIn("D\u266d", result.scale_reference)
        self.assertIn("B\u266d", result.scale_reference_descending)

        import music_coach_ami.scale_engine as se

        asc_deg = se.spell_scale_degrees_for_direction("D", "melodic minor", "ascending")
        desc_deg = se.spell_scale_degrees_for_direction("D", "melodic minor", "descending")
        asc_seq = se.extend_scale_octaves(asc_deg, spec.octave_count)
        up = se._octave_for_sequence(asc_seq, result.chosen_start_octave)
        desc_seq = se._melodic_descending_note_sequence(desc_deg, spec.octave_count)
        down = se._octave_for_sequence_descending(desc_seq, up[-1][1])
        midis = [se._midi_for_spelled(n, o) for n, o in up + down[1:]]
        peak = midis.index(max(midis))
        for i in range(peak, len(midis) - 1):
            self.assertLess(midis[i + 1], midis[i], msg=(allp := up + down[1:]))

        self.assertIn("M:4/4", result.abc)
        self.assertIn("L:1/4", result.abc)
        body = result.abc.split("K:Dm", 1)[-1]
        self.assertGreaterEqual(body.count("|"), 2)

    def test_a_melodic_minor_directional_degrees(self) -> None:
        from music_coach_ami.scale_engine import spell_scale_degrees_for_direction

        asc = spell_scale_degrees_for_direction("A", "melodic minor", "ascending")
        self.assertEqual(asc, ["A", "B", "C", "D", "E", "F#", "G#"])
        spec = parse_scale_practice_question(
            "Show me A melodic minor, ascending and descending, two octaves, in quarter notes."
        )
        result = generate_scale_practice(spec)
        self.assertIn("F\u266f", result.scale_reference)
        self.assertIn("G\u266f", result.scale_reference)
        self.assertIn("G ", result.scale_reference_descending)
        self.assertTrue(
            " B " in result.scale_reference_descending
            or result.scale_reference_descending.startswith("A G")
        )

    def test_eb_melodic_minor_flat_spelling(self) -> None:
        from music_coach_ami.scale_engine import spell_scale_degrees_for_direction

        asc = spell_scale_degrees_for_direction("Eb", "melodic minor", "ascending")
        self.assertIn("Eb", asc)
        self.assertTrue(any("b" in n or "#" in n for n in asc))

    def test_f_harmonic_minor_sixths_both_phases_in_abc(self) -> None:
        prompt = (
            "Give me F harmonic minor in sixths, ascending and descending, "
            "in eighth notes at 72 BPM."
        )
        spec = parse_scale_practice_question(prompt)
        result = generate_scale_practice(spec)
        self.assertEqual(len(result.notation_sections), 2)
        self.assertIn("ascending", result.notation_sections[0].lower())
        self.assertIn("descending", result.notation_sections[1].lower())
        scale, _, _ = spell_scale("F", "harmonic minor")
        step = 5
        up = pairs_to_pitched_notes(
            [],
            direction="both",
            start_octave=result.chosen_start_octave,
            scale=scale,
            step=step,
            octave_count=spec.octave_count,
        )
        up_count = len(build_interval_pairs_over_octaves(scale, step, spec.octave_count)) * 2
        self.assertEqual(len(up), up_count * 2)
        down_body = result.abc.split("X:2", 1)[-1]
        self.assertIn("|", down_body)

    def test_bb_major_68_measures_and_tempo(self) -> None:
        spec = parse_scale_practice_question(
            "Give me B\u266d major in 6/8, two octaves, eighth notes, at 84 BPM."
        )
        result = generate_scale_practice(spec)
        self.assertIn("M:6/8", result.abc)
        self.assertIn("L:1/8", result.abc)
        self.assertIn("Q:3/8=84", result.abc)
        body = result.abc.split("K:Bb", 1)[-1]
        self.assertGreaterEqual(body.count("|"), 2)

    def test_eb_major_thirds_triplet_abc(self) -> None:
        spec = parse_scale_practice_question(
            "Give me E\u266d major in thirds, two octaves, as eighth-note triplets at 72 BPM."
        )
        self.assertTrue(spec.rhythm_triplet)
        result = generate_scale_practice(spec)
        self.assertIn("(3", result.abc)
        body = result.abc.split("K:Eb", 1)[-1]
        self.assertNotRegex(body, r"[A-Ga-g][^ \n]*3(?!\))")
        joined = " ".join(result.practice_guidance).lower()
        self.assertIn("triplet", joined)
        self.assertNotIn("keep eighth notes even", joined)

    def test_c_sharp_fourths_frozen(self) -> None:
        spec = parse_scale_practice_question(
            "Give me C# major in fourths, two octaves, as eighth notes."
        )
        result = generate_scale_practice(spec)
        self.assertIn("E\u266f", result.interval_pairs_display or "")
        self.assertIn("B\u266f", result.interval_pairs_display or "")


if __name__ == "__main__":
    unittest.main()

"""AMI Slice 5 Stage 3b: advanced harmonic vocabulary across chord changes.

Multi-chord target-tone and bebop lines, an enclosure INSIDE the first chord that resolves into the next, and a pentatonic
framework with chromatic embellishment. The notes come from the existing span engines (``SpanConstraints`` through
``constraint_overrides``); these tests re-derive every musical claim from the pitches and the chords' tones, never from the
generator's own labels.
"""

from __future__ import annotations

import copy
import unittest
from fractions import Fraction

from music_coach_ami.exercise_intent import is_exercise_request, parse_exercise_intent
from music_coach_ami.exercise_model import TECHNIQUE_BEBOP, TECHNIQUE_ENCLOSURE, TECHNIQUE_TARGET_TONE
from music_coach_ami.exercise_span import open_exercise_in_missions, span_pattern_plan
from tests.test_ami_span_guide_tones import PROGRESSIONS, ask, exercise_of

ROLE_INDEX = {"R": 0, "3": 1, "5": 2, "7": 3}
MAJOR_KEYS = ("C", "F", "Eb", "Bb", "D")          # the ii-V spans of these keys carry bebop and pentatonic lines
ALL_KEYS = ("C", "F", "Eb", "Bb", "D", "Am", "Gm", "Em")


def tone_pcs(chord: str, key: str) -> list[int]:
    from improvisation_motif import _midi_from_note, chord_tone_names

    return [_midi_from_note(n, 4) % 12 for n in (chord_tone_names(chord, reference_key=key) or [])]


def arrival(ex, i: int) -> int:
    return next(j for j, a in enumerate(ex.chord_assignment) if a == i)


def lands_on_role(ex, roles: tuple[str, ...]) -> bool:
    key = ex.context.concert_key
    return all(ex.midi[arrival(ex, i)] % 12 in {tone_pcs(c, key)[ROLE_INDEX[r]] for r in roles}
               for i, c in enumerate(ex.chords))


def reached_by_step(ex) -> bool:
    return all(0 < abs(ex.midi[arrival(ex, i)] - ex.midi[arrival(ex, i) - 1]) <= 2 for i in range(1, len(ex.chords)))


def half_step_into(ex, i: int) -> bool:
    key, j = ex.context.concert_key, arrival(ex, i)
    return abs(ex.midi[j] - ex.midi[j - 1]) == 1 and ex.midi[j - 1] % 12 not in tone_pcs(ex.chords[i], key)


def inner_enclosure(ex, role: str) -> int | None:
    """Index of the first chord's ``role`` tone when two notes of that same chord surround it (opposite sides, within a whole step,
    one a half step away) and it is not the chord's opening note."""
    key = ex.context.concert_key
    pcs = tone_pcs(ex.chords[0], key)
    first, last = arrival(ex, 0), arrival(ex, 1) - 1
    for t in range(first + 2, last + 1):
        if ex.midi[t] % 12 != pcs[ROLE_INDEX[role]]:
            continue
        a, b = ex.midi[t - 2] - ex.midi[t], ex.midi[t - 1] - ex.midi[t]
        if a * b < 0 and 1 <= abs(a) <= 2 and 1 <= abs(b) <= 2 and 1 in (abs(a), abs(b)):
            return t
    return None


def event_list(ex):
    from melodic_rhythm_engine import events_from_json

    return [e for e in events_from_json(ex.rhythm_events) if not e.rest]


class TestParsing(unittest.TestCase):
    def test_the_requests_from_the_brief_are_understood(self) -> None:
        cases = {
            "Create a bebop line over the next three chords.": (TECHNIQUE_BEBOP, "span", 3),
            "Give me a bebop-style phrase through this ii–V–I.": (TECHNIQUE_BEBOP, "span", 3),
            "Target the third of each chord.": (TECHNIQUE_TARGET_TONE, "span", 0),
            "Create a line that targets the seventh of each chord.": (TECHNIQUE_TARGET_TONE, "span", 0),
            "Give me a chromatic bebop line that resolves into the next chord.": (TECHNIQUE_BEBOP, "span", 2),
            "Enclose the third of G7, then resolve into Cmaj7.": (TECHNIQUE_ENCLOSURE, "span", 2),
            "Create an enclosure in the first chord that leads into the next chord.": (TECHNIQUE_ENCLOSURE, "span", 2),
            "Start with an enclosure around the seventh, then resolve to the third of the next chord.": (TECHNIQUE_ENCLOSURE, "span", 2),
        }
        for q, (technique, scope, length) in cases.items():
            with self.subTest(q=q):
                i = parse_exercise_intent(q)
                self.assertEqual((i.technique, i.scope, i.span_length), (technique, scope, length))
                self.assertTrue(is_exercise_request(q), q)

    def test_first_chord_enclosures_carry_their_tones(self) -> None:
        i = parse_exercise_intent("Start with an enclosure around the seventh, then resolve to the third of the next chord.")
        self.assertEqual((i.inner_enclosure, i.inner_tone, i.resolve_tone), (True, "seventh", "third"))
        i = parse_exercise_intent("Enclose the third of G7, then resolve into Cmaj7.")
        self.assertEqual((i.inner_enclosure, i.inner_tone, i.span_chords), (True, "third", ("G7", "Cmaj7")))
        i = parse_exercise_intent("Create an enclosure in the first chord that leads into the next chord.")
        self.assertEqual((i.inner_enclosure, i.inner_tone), (True, ""))

    def test_an_enclosure_at_the_change_is_not_a_first_chord_enclosure(self) -> None:
        i = parse_exercise_intent("Create an enclosure targeting the third of each chord over the next two chords.")
        self.assertFalse(i.inner_enclosure)

    def test_a_pentatonic_framework_is_kept_when_the_chord_tones_are_the_targets(self) -> None:
        i = parse_exercise_intent("Use a pentatonic framework but approach the chord tones chromatically over the next two chords.")
        self.assertEqual((i.vocabulary, i.technique), ("pentatonic", "chromatic_approach"))

    def test_bebop_alone_still_means_the_old_scale_practice(self) -> None:
        self.assertEqual(parse_exercise_intent("Teach me the bebop scale").technique, "")


class TestPlans(unittest.TestCase):
    def test_each_request_maps_onto_an_existing_mission(self) -> None:
        for q, mission in (
            ("Target the third of each chord", "resolve_to_third"),
            ("Create a line that targets the seventh of each chord", "target_each_change"),
            ("Create a bebop line over the next three chords", "bebop_line"),
            ("Create an enclosure in the first chord that leads into the next chord", "approach_next_chord"),
            ("Create a pentatonic pattern with chromatic approaches over the next two chords", "pentatonic_per_chord"),
            ("Give me a pentatonic line with enclosures over the next two chords", "pentatonic_per_chord"),
        ):
            plan = span_pattern_plan(parse_exercise_intent(q))
            self.assertTrue(plan.supported, q)
            self.assertEqual(plan.mission_id, mission, q)

    def test_constraints_are_the_engines_own_fields(self) -> None:
        from span_motif_engine import SpanConstraints

        for q in ("Create an enclosure in the first chord that leads into the next chord",
                  "Give me a pentatonic line with enclosures over the next two chords",
                  "Give me a chromatic bebop line that resolves into the next chord"):
            plan = span_pattern_plan(parse_exercise_intent(q))
            built = SpanConstraints.from_dict(dict(plan.constraints))
            self.assertIsNotNone(built, q)
        inner = span_pattern_plan(parse_exercise_intent("Start with an enclosure around the seventh, then resolve to the third of the next chord"))
        self.assertEqual((inner.constraints["inner_enclosure"], inner.constraints["target_roles"]), ("7", ("3",)))

    def test_roots_and_fifths_are_a_stated_limit(self) -> None:
        plan = span_pattern_plan(parse_exercise_intent("Create a line that targets the fifth of each chord"))
        self.assertFalse(plan.supported)
        self.assertIn("not the fifth", plan.limitation)


class TestTargetToneAcrossChords(unittest.TestCase):
    def test_every_chord_starts_on_its_third_across_keys(self) -> None:
        for key in ALL_KEYS:
            with self.subTest(key=key):
                resp, _ = ask("Target the third of each chord.", key=key)
                ex = exercise_of(resp)
                self.assertIsNotNone(ex, resp.direct_answer[:160] if resp else "no response")
                self.assertTrue(lands_on_role(ex, ("3",)), (ex.chords, ex.notes))
                self.assertTrue(reached_by_step(ex), (ex.chords, ex.notes))
                self.assertEqual(ex.engine_detail, "resolve_to_third")

    def test_every_chord_starts_on_its_seventh_across_qualities_and_keys(self) -> None:
        for key in ALL_KEYS:
            with self.subTest(key=key):
                resp, _ = ask("Create a line that targets the seventh of each chord.", key=key)
                ex = exercise_of(resp)
                self.assertIsNotNone(ex, resp.direct_answer[:160] if resp else "no response")
                self.assertTrue(lands_on_role(ex, ("7",)), (ex.chords, ex.notes))
                self.assertTrue(reached_by_step(ex), (ex.chords, ex.notes))

    def test_three_chords_with_the_third_of_each(self) -> None:
        resp, _ = ask("Target the third of each chord over the next three chords.", key="C")
        ex = exercise_of(resp)
        self.assertEqual(len(ex.chords), 3)
        self.assertTrue(lands_on_role(ex, ("3",)))

    def test_chord_assignment_and_timing(self) -> None:
        resp, _ = ask("Target the third of each chord over the next three chords.", key="F")
        ex = exercise_of(resp)
        self.assertEqual(ex.chord_assignment, sorted(ex.chord_assignment))
        self.assertEqual(sorted(set(ex.chord_assignment)), [0, 1, 2])
        self.assertEqual(len(ex.chord_assignment), len(ex.midi))
        self.assertGreaterEqual(ex.bars, 3)

    def test_a_triad_has_no_seventh_and_says_so(self) -> None:
        resp, _ = ask("Create a line that targets the seventh of each chord over the next three chords.", key="Am")
        self.assertIsNone(exercise_of(resp))
        self.assertIn("has no 7th", resp.direct_answer)


class TestBebopAcrossChords(unittest.TestCase):
    def test_bebop_over_two_and_three_chords(self) -> None:
        for key in MAJOR_KEYS:
            for q, n in (("Create a bebop line over the next two chords.", 2), ("Create a bebop line over the next three chords.", 3)):
                with self.subTest(key=key, n=n):
                    resp, _ = ask(q, key=key)
                    ex = exercise_of(resp)
                    self.assertIsNotNone(ex, resp.direct_answer[:200] if resp else "")
                    self.assertEqual(len(ex.chords), n)
                    self.assertEqual(ex.engine_detail, "bebop_line")
                    self.assertTrue(ex.validation["ok"], ex.validation)

    def test_bebop_vocabulary_is_present_in_the_pitches_and_rhythm(self) -> None:
        from melodic_pattern_engine import build_context

        for key in MAJOR_KEYS:
            with self.subTest(key=key):
                resp, _ = ask("Create a bebop line over the next three chords.", key=key)
                ex = exercise_of(resp)
                center = ex.context.span.get("key_center") or key
                ctxs = [build_context(center, c) for c in ex.chords]
                events = event_list(ex)
                eighths = sum(1 for e in events if e.duration <= Fraction(1, 2)) / len(events)
                self.assertGreaterEqual(eighths, 0.5, (key, ex.notes))
                on_beat = [k for k, e in enumerate(events) if e.onset % 1 == 0]
                chord_tone = [k for k in on_beat if ex.midi[k] % 12 in ctxs[ex.chord_assignment[k]].chord_pcs]
                self.assertGreaterEqual(len(chord_tone) / len(on_beat), 0.5, (key, ex.notes))
                chromatic = [k for k in range(len(ex.midi)) if ex.midi[k] % 12 not in ctxs[ex.chord_assignment[k]].scale_pcs]
                self.assertTrue(chromatic, (key, ex.notes))
                for k in chromatic:                       # each chromatic passing note resolves by a half step
                    self.assertEqual(abs(ex.midi[k + 1] - ex.midi[k]), 1, (key, ex.notes, k))

    def test_every_chord_change_lands_on_a_chord_tone(self) -> None:
        for key in MAJOR_KEYS:
            with self.subTest(key=key):
                resp, _ = ask("Give me a bebop-style phrase through this ii–V–I.", key=key)
                ex = exercise_of(resp)
                self.assertEqual(len(ex.chords), 3)
                for i, chord in enumerate(ex.chords):
                    self.assertIn(ex.midi[arrival(ex, i)] % 12, tone_pcs(chord, key), (key, i, ex.notes))

    def test_a_chromatic_bebop_line_leans_into_the_next_chord(self) -> None:
        for key in MAJOR_KEYS:
            with self.subTest(key=key):
                resp, _ = ask("Give me a chromatic bebop line that resolves into the next chord.", key=key)
                ex = exercise_of(resp)
                self.assertIsNotNone(ex)
                self.assertEqual(len(ex.chords), 2)
                self.assertTrue(half_step_into(ex, 1), (key, ex.notes))

    def test_a_voice_led_line_is_not_independent_phrases(self) -> None:
        """One continuous line: no leap between neighbouring notes bigger than a sixth."""
        for key in MAJOR_KEYS:
            resp, _ = ask("Create a bebop line over the next three chords.", key=key)
            ex = exercise_of(resp)
            leaps = [abs(b - a) for a, b in zip(ex.midi, ex.midi[1:])]
            self.assertLessEqual(max(leaps), 9, (key, ex.notes, leaps))


class TestFirstChordEnclosure(unittest.TestCase):
    def test_the_third_is_enclosed_inside_the_first_chord_and_the_line_resolves_by_half_step(self) -> None:
        for key in ALL_KEYS:
            with self.subTest(key=key):
                resp, _ = ask("Create an enclosure in the first chord that leads into the next chord.", key=key)
                ex = exercise_of(resp)
                self.assertIsNotNone(ex, resp.direct_answer[:200] if resp else "")
                self.assertEqual(len(ex.chords), 2)
                t = inner_enclosure(ex, "3")
                self.assertIsNotNone(t, (key, ex.chords, ex.notes))
                self.assertLess(t, arrival(ex, 1))                                   # inside the first chord's window
                self.assertTrue(half_step_into(ex, 1), (key, ex.notes))           # then the half-step lean into the next chord
                self.assertIn(ex.midi[arrival(ex, 1)] % 12, tone_pcs(ex.chords[1], key))

    def test_the_seventh_is_enclosed_and_the_next_third_is_the_resolution(self) -> None:
        for key in ALL_KEYS:
            with self.subTest(key=key):
                resp, _ = ask("Start with an enclosure around the seventh, then resolve to the third of the next chord.", key=key)
                ex = exercise_of(resp)
                self.assertIsNotNone(ex, resp.direct_answer[:200] if resp else "")
                self.assertIsNotNone(inner_enclosure(ex, "7"), (key, ex.chords, ex.notes))
                self.assertEqual(ex.midi[arrival(ex, 1)] % 12, tone_pcs(ex.chords[1], key)[ROLE_INDEX["3"]], (key, ex.notes))
                self.assertTrue(half_step_into(ex, 1))

    def test_the_named_chords_are_the_ones_used(self) -> None:
        resp, _ = ask("Enclose the third of G7, then resolve into Cmaj7.", key="C")
        ex = exercise_of(resp)
        self.assertEqual(ex.chords, ["G7", "Cmaj7"])
        t = inner_enclosure(ex, "3")
        self.assertIsNotNone(t, ex.notes)
        self.assertEqual(ex.midi[t] % 12, 11)                                          # B, the 3rd of G7
        self.assertIn(ex.midi[arrival(ex, 1)] % 12, tone_pcs("Cmaj7", "C"))

    def test_the_enclosure_does_not_move_a_boundary_figure_earlier(self) -> None:
        resp, _ = ask("Create an enclosure in the first chord that leads into the next chord.", key="C")
        ex = exercise_of(resp)
        j = arrival(ex, 1)
        self.assertTrue(half_step_into(ex, 1))
        # the two notes right before the change are NOT an enclosure of the arrival (that would be the Stage 3 boundary figure)
        lead = ex.midi[j - 2:j]
        arr = ex.midi[j]
        self.assertFalse(any(m > arr for m in lead) and any(m < arr for m in lead) and all(abs(m - arr) <= 2 for m in lead))

    def test_checks_are_recorded(self) -> None:
        resp, _ = ask("Create an enclosure in the first chord that leads into the next chord.", key="F")
        names = {c["name"] for c in exercise_of(resp).validation["checks"]}
        self.assertTrue({"first_chord_enclosure", "resolves_into_next_chord", "mission_validator", "harmonic_boundaries"} <= names)

    def test_the_card_describes_the_first_chord_figure(self) -> None:
        resp, _ = ask("Create an enclosure in the first chord that leads into the next chord.", key="C")
        self.assertIn("Inside", resp.direct_answer)
        self.assertIn("enclose", resp.direct_answer)

    def test_a_chromatic_approach_in_the_first_chord_is_not_faked(self) -> None:
        resp, _ = ask("Approach the seventh of G7 chromatically, then resolve into Cmaj7.", key="C")
        self.assertIsNone(exercise_of(resp))


class TestPentatonicWithEmbellishment(unittest.TestCase):
    def _split(self, ex):
        from melodic_pattern_engine import build_context
        from span_motif_explain import _pentatonic_info

        center = ex.context.span.get("key_center") or ex.context.concert_key
        ctxs = [build_context(center, c) for c in ex.chords]
        pents = [set(_pentatonic_info(c, ch)["pcs"]) for c, ch in zip(ctxs, ex.chords)]
        core = [k for k in range(len(ex.midi)) if ex.midi[k] % 12 in pents[ex.chord_assignment[k]]]
        outside = [k for k in range(len(ex.midi)) if k not in core]
        return pents, core, outside

    def test_the_framework_stays_pentatonic_and_only_the_embellishment_leaves_it(self) -> None:
        for key in MAJOR_KEYS:
            for q, allowed in (("Create a pentatonic pattern with chromatic approaches over the next two chords.", 1),
                               ("Give me a pentatonic line with enclosures over the next two chords.", 2)):
                with self.subTest(key=key, q=q[:40]):
                    resp, _ = ask(q, key=key)
                    ex = exercise_of(resp)
                    self.assertIsNotNone(ex, resp.direct_answer[:200] if resp else "")
                    pents, core, outside = self._split(ex)
                    self.assertTrue(outside, ex.notes)                         # there IS chromatic embellishment
                    self.assertGreaterEqual(len(core) / len(ex.midi), 0.6)      # the framework is the line
                    last = arrival(ex, 1) - 1
                    for k in outside:
                        self.assertEqual(ex.chord_assignment[k], 0)                # none in the final chord
                        self.assertGreater(k, last - allowed)                      # only just before the change
                    j = arrival(ex, 1)
                    self.assertIn(ex.midi[j] % 12, pents[1] & set(tone_pcs(ex.chords[1], key)))   # resolves into the framework

    def test_each_kind_of_note_is_told_apart_on_the_card(self) -> None:
        resp, _ = ask("Create a pentatonic pattern with chromatic approaches over the next two chords.", key="C")
        self.assertIn("**Framework:**", resp.direct_answer)
        self.assertIn("**Embellishment (not pentatonic):**", resp.direct_answer)

    def test_the_card_is_honest_about_a_bluesy_request(self) -> None:
        resp, _ = ask("Give me a bluesy pentatonic line with enclosures over the next two chords.", key="C")
        self.assertIn("blues scales aren't available across chords", resp.direct_answer)

    def test_a_chord_with_no_true_pentatonic_is_refused_not_relabelled(self) -> None:
        resp, _ = ask("Create a pentatonic pattern with chromatic approaches over the next two chords.", key="Am")
        self.assertIsNone(exercise_of(resp))
        self.assertIn("pentatonic", resp.direct_answer)
        self.assertEqual(resp.notation_abc, "")

    def test_over_one_chord_it_is_not_silently_turned_into_a_plain_pattern(self) -> None:
        resp, _ = ask("Create a pentatonic pattern with chromatic approaches.", key="C")
        self.assertIsNone(exercise_of(resp))
        self.assertIn("needs a chord change to resolve into", resp.direct_answer)

    def test_blues_across_chords_stays_unsupported(self) -> None:
        resp, _ = ask("Give me a blues line with enclosures over the next two chords.", key="C")
        self.assertIsNone(exercise_of(resp))


class TestInstrumentsKeysAndSpelling(unittest.TestCase):
    def test_guitar_gets_tab_for_each_new_exercise(self) -> None:
        for q in ("Create a bebop line over the next three chords.", "Target the third of each chord.",
                  "Create an enclosure in the first chord that leads into the next chord.",
                  "Create a pentatonic pattern with chromatic approaches over the next two chords."):
            with self.subTest(q=q[:40]):
                resp, _ = ask(q, key="F", instrument="Guitar")
                ex = exercise_of(resp)
                self.assertIsNotNone(ex)
                self.assertTrue(resp.diagnostics["guitar_tab_present"])
                self.assertIn("e|", resp.direct_answer)
                self.assertEqual(ex.context.concert_key, "F")
                self.assertIn("K:F", resp.notation_abc)

    def test_flat_keys_are_spelled_with_flats_and_sharp_keys_with_sharps(self) -> None:
        # chord tones (the notes the key's own chords spell) carry the key's accidental; a chromatic approach from below may
        # legitimately be a sharp (F#-G in Eb), so only chord tones are held to the key's spelling
        for key, accidental in (("Eb", "b"), ("Bb", "b"), ("D", "#")):
            resp, _ = ask("Create a bebop line over the next three chords.", key=key)
            ex = exercise_of(resp)
            for name, midi, a in zip(ex.notes, ex.midi, ex.chord_assignment):
                if len(name) > 1 and midi % 12 in tone_pcs(ex.chords[a], key):
                    self.assertEqual(name[1], accidental, (key, name, ex.notes))

    def test_the_practice_key_decides_the_pitches(self) -> None:
        a, _ = ask("Target the third of each chord.", key="C")
        b, _ = ask("Target the third of each chord.", key="Eb")
        ea, eb = exercise_of(a), exercise_of(b)
        self.assertEqual(ea.context.concert_key, "C")
        self.assertEqual(eb.context.concert_key, "Eb")
        self.assertNotEqual(ea.chords, eb.chords)


class TestMissionsTransfer(unittest.TestCase):
    def _transfer(self, question: str, mission: str, key: str = "C") -> None:
        resp, session = ask(question, key=key)
        action = resp.diagnostics["open_in_missions"]
        ex = exercise_of(resp)
        before = copy.deepcopy(action["example"])
        result = open_exercise_in_missions(session, action)
        self.assertTrue(result["ok"], result)
        staged = session["improv_span_mission"]["example"]
        self.assertEqual(staged, before, question)                                     # never regenerated
        self.assertEqual(staged["mission_id"], mission, question)                     # the Mission it demonstrates
        self.assertEqual(staged["motif"]["midi"], ex.midi)
        self.assertEqual(staged["motif"]["note_chord_index"], ex.chord_assignment)
        self.assertEqual(staged["handoff"]["practice_key"], key)
        self.assertEqual(session["_improv_span_mission_choice"], mission)

    def test_every_new_exercise_opens_as_the_exact_example(self) -> None:
        for q, mission in (
            ("Create a bebop line over the next three chords.", "bebop_line"),
            ("Target the third of each chord.", "resolve_to_third"),
            ("Create a line that targets the seventh of each chord.", "target_each_change"),
            ("Create an enclosure in the first chord that leads into the next chord.", "approach_next_chord"),
            ("Create a pentatonic pattern with chromatic approaches over the next two chords.", "pentatonic_per_chord"),
        ):
            with self.subTest(q=q[:50]):
                self._transfer(q, mission)

    def test_the_card_names_the_mission_it_opens(self) -> None:
        resp, _ = ask("Create an enclosure in the first chord that leads into the next chord.", key="C")
        self.assertEqual(resp.diagnostics["open_in_missions"]["mission_id"], "approach_next_chord")
        self.assertEqual(resp.diagnostics["open_in_missions"]["label"], "Open in Missions")


class TestRegressionProtection(unittest.TestCase):
    def test_stage_one_to_three_requests_are_unchanged(self) -> None:
        for q, mission in (
            ("Give me a guide-tone pattern through the next three chords", "guide_tone_voice_leading"),
            ("Give me an enclosure across the next two chords", "enclose_next_target"),
            ("Create an enclosure targeting the third of each chord over the next two chords.", "enclose_next_target"),
            ("Create a chromatic approach to the next chord's third.", "approach_next_chord"),
            ("Give me guide tones with chromatic approaches over the next two chords.", "guide_tone_voice_leading"),
        ):
            with self.subTest(q=q[:50]):
                resp, _ = ask(q, key="C")
                self.assertEqual(exercise_of(resp).engine_detail, mission)

    def test_single_chord_requests_still_use_the_pattern_engine(self) -> None:
        resp, _ = ask("Give me an enclosure exercise targeting the third of G7", key="C")
        self.assertEqual(exercise_of(resp).provenance["engine"], "melodic_pattern_engine")
        resp, _ = ask("Give me a bebop line over G7", key="C")
        self.assertEqual(exercise_of(resp).provenance["engine"], "melodic_pattern_engine")

    def test_a_requested_direction_is_not_silently_dropped(self) -> None:
        resp, _ = ask("Create a descending bebop line over the next three chords.", key="C")
        self.assertIsNotNone(exercise_of(resp))
        self.assertIn("direction", resp.direct_answer)
        self.assertIn("not applied", resp.direct_answer)

    def test_the_fixture_progressions_exist(self) -> None:
        for key in ALL_KEYS:
            self.assertIn(key, PROGRESSIONS)


if __name__ == "__main__":
    unittest.main()

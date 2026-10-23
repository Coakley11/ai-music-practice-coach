"""AMI Slice 5 Stage 3: composite musical techniques (a technique aimed at a named chord tone, guide tones with approaches or
enclosures, across one chord or a 2-/3-chord harmonic span).

The notes come from the existing engines (the span Missions through ``SpanConstraints`` overrides, and the pattern engine for one
chord). These tests re-derive every musical claim from the pitches and chord tones themselves, never from the generator's labels.
"""

from __future__ import annotations

import copy
import unittest

from music_coach_ami.exercise_intent import is_exercise_request, parse_exercise_intent
from music_coach_ami.exercise_model import (
    ROUTE_BRIDGE,
    TECHNIQUE_CHROMATIC_APPROACH,
    TECHNIQUE_COMPOSITE,
    TECHNIQUE_ENCLOSURE,
)
from music_coach_ami.exercise_single import single_plan
from music_coach_ami.exercise_span import open_exercise_in_missions, span_pattern_plan
from tests.test_ami_span_guide_tones import PROGRESSIONS, ask, exercise_of, session_for

ROLE_INDEX = {"R": 0, "3": 1, "5": 2, "7": 3}


def chord_pcs(chord: str, key: str) -> list[int]:
    from improvisation_motif import _midi_from_note, chord_tone_names

    return [_midi_from_note(n, 4) % 12 for n in (chord_tone_names(chord, reference_key=key) or [])]


def arrival_index(ex, i: int) -> int:
    return next(j for j, a in enumerate(ex.chord_assignment) if a == i)


def lead_notes(ex, i: int, n: int) -> list[int]:
    """The ``n`` notes sounding before chord ``i`` begins (they belong to earlier chords)."""
    first = arrival_index(ex, i)
    return [m for m, a in zip(ex.midi[:first], ex.chord_assignment[:first]) if a < i][-n:]


def lands_on(ex, roles: tuple[str, ...]) -> bool:
    key = ex.context.concert_key
    for i, chord in enumerate(ex.chords):
        pcs = chord_pcs(chord, key)
        wanted = {pcs[ROLE_INDEX[r]] for r in roles}
        if ex.midi[arrival_index(ex, i)] % 12 not in wanted:
            return False
    return True


def approached_by_half_step(ex) -> bool:
    key = ex.context.concert_key
    for i in range(1, len(ex.chords)):
        lead = lead_notes(ex, i, 1)
        arrival = ex.midi[arrival_index(ex, i)]
        if not (lead and abs(lead[-1] - arrival) == 1 and lead[-1] % 12 not in chord_pcs(ex.chords[i], key)):
            return False
    return True


def enclosed(ex) -> bool:
    for i in range(1, len(ex.chords)):
        lead = lead_notes(ex, i, 2)
        arrival = ex.midi[arrival_index(ex, i)]
        if not (len(lead) == 2 and any(m > arrival for m in lead) and any(m < arrival for m in lead)
                and all(0 < abs(m - arrival) <= 3 for m in lead)):
            return False
    return True


class TestCompositeParsing(unittest.TestCase):
    def test_the_requests_from_the_brief_are_understood(self) -> None:
        cases = {
            "Create an enclosure targeting the third of each chord.": (TECHNIQUE_ENCLOSURE, "third", "each", "", "span"),
            "Create a chromatic approach to the next chord's third.": (TECHNIQUE_CHROMATIC_APPROACH, "third", "next", "", "span"),
            "Approach the seventh of G7 chromatically.": (TECHNIQUE_CHROMATIC_APPROACH, "seventh", "", "G7", "single_chord"),
            "Give me guide tones with chromatic approaches.": (TECHNIQUE_CHROMATIC_APPROACH, "", "", "", "single_chord"),
            "Give me a chord-tone exercise with enclosures.": (TECHNIQUE_ENCLOSURE, "", "", "", "single_chord"),
            "Give me an enclosure around the third of G7, then resolve into Cmaj7.": (TECHNIQUE_ENCLOSURE, "third", "", "G7", "span"),
        }
        for q, (technique, tone, dest, chord, scope) in cases.items():
            with self.subTest(q=q):
                i = parse_exercise_intent(q)
                self.assertEqual((i.technique, i.target_tone, i.target_destination, i.explicit_chord, i.scope),
                                 (technique, tone, dest, chord, scope))
                self.assertEqual(i.engine_route, ROUTE_BRIDGE)
                self.assertTrue(is_exercise_request(q), q)

    def test_a_named_chord_sequence_is_read(self) -> None:
        i = parse_exercise_intent("Give me an enclosure around the third of G7, then resolve into Cmaj7.")
        self.assertEqual((i.span_chords, i.span_length, i.target_chord), (("G7", "Cmaj7"), 2, "G7"))

    def test_guide_tones_with_a_technique_keep_both_parts(self) -> None:
        i = parse_exercise_intent("Give me guide tones with chromatic approaches.")
        self.assertEqual((i.vocabulary, i.technique), ("guide_tones", TECHNIQUE_CHROMATIC_APPROACH))
        self.assertIn("vocabulary", i.explicit_fields)

    def test_requests_that_must_not_be_redirected(self) -> None:
        for q in ("Give me the third of G7", "Give me a guide-tone line through these chords.", "Create a pentatonic pattern I can practice.",
                  "Give me a blues lick over this chord."):
            self.assertNotIn(parse_exercise_intent(q).technique, (TECHNIQUE_ENCLOSURE, TECHNIQUE_CHROMATIC_APPROACH), q)

    def test_both_techniques_in_one_line_is_still_flagged(self) -> None:
        self.assertEqual(parse_exercise_intent("Give me chromatic approaches and enclosures over G7").technique, TECHNIQUE_COMPOSITE)


class TestCompositePlans(unittest.TestCase):
    def test_a_target_tone_becomes_a_constraint_on_the_missions_own_plan(self) -> None:
        for q, mission in (("Create an enclosure targeting the third of each chord", "enclose_next_target"),
                           ("Create a chromatic approach to the next chord's third", "approach_next_chord")):
            plan = span_pattern_plan(parse_exercise_intent(q))
            self.assertTrue(plan.supported, q)
            self.assertEqual((plan.mission_id, plan.target_roles, plan.constraints), (mission, ("3",), {"target_roles": ("3",)}), q)

    def test_guide_tones_keep_their_mission_and_narrow_the_connector(self) -> None:
        plan = span_pattern_plan(parse_exercise_intent("Give me guide tones with chromatic approaches over the next two chords"))
        self.assertEqual((plan.mission_id, plan.target_roles, plan.constraints["connector"]), ("guide_tone_voice_leading", ("3", "7"), "chromatic"))
        plan = span_pattern_plan(parse_exercise_intent("Give me guide tones with enclosures over the next two chords"))
        self.assertEqual(plan.constraints["connector"], "enclosure")

    def test_single_chord_guide_tones_with_a_technique_use_the_techniques_mission(self) -> None:
        plan = single_plan(parse_exercise_intent("Give me guide tones with chromatic approaches over G7"))
        self.assertTrue(plan.supported)
        self.assertEqual((plan.mission_id, plan.target_roles), ("Approach a chord tone chromatically", ("3", "7")))

    def test_unsupported_combinations_say_why(self) -> None:
        for q, why in (
            ("Create a pentatonic pattern with enclosures over G7", "chromatic embellishments"),
            ("Create a pentatonic pattern with enclosures over the next two chords", "chromatic embellishments"),
            ("Give me chromatic approaches and enclosures over G7", "in one line"),
        ):
            i = parse_exercise_intent(q)
            plan = span_pattern_plan(i) if i.scope == "span" else single_plan(i)
            self.assertFalse(plan.supported, q)
            self.assertIn(why, plan.limitation, q)


class TestSpanCompositeMusicalCorrectness(unittest.TestCase):
    def test_enclosing_the_third_of_each_chord_surrounds_and_lands_on_the_third(self) -> None:
        for key in ("C", "F", "Eb", "Am", "Gm", "Em", "D"):
            with self.subTest(key=key):
                resp, _ = ask("Create an enclosure targeting the third of each chord over the next two chords.", key=key)
                ex = exercise_of(resp)
                self.assertIsNotNone(ex, resp.direct_answer[:140])
                self.assertEqual(len(ex.chords), 2)
                self.assertTrue(lands_on(ex, ("3",)), (ex.chords, ex.notes))
                self.assertTrue(enclosed(ex), (ex.chords, ex.notes))

    def test_a_chromatic_approach_to_the_next_chords_third_is_a_half_step_at_the_boundary(self) -> None:
        for key in ("C", "Bb", "D", "Am", "Gm"):
            with self.subTest(key=key):
                resp, _ = ask("Create a chromatic approach to the next chord's third.", key=key)
                ex = exercise_of(resp)
                self.assertIsNotNone(ex, resp.direct_answer[:140])
                self.assertTrue(lands_on(ex, ("3",)), (ex.chords, ex.notes))
                self.assertTrue(approached_by_half_step(ex), (ex.chords, ex.notes))

    def test_sevenths_across_different_chord_qualities(self) -> None:
        for key, prog_chords in (("C", "Dm7 -> G7"), ("Am", "Bm7b5 -> E7"), ("Eb", "Fm7 -> Bb7")):
            with self.subTest(key=key):
                resp, _ = ask("Create an enclosure targeting the seventh of each chord over the next two chords.", key=key)
                ex = exercise_of(resp)
                self.assertIsNotNone(ex, resp.direct_answer[:140])
                self.assertTrue(lands_on(ex, ("7",)), (ex.chords, ex.notes))
                self.assertTrue(enclosed(ex), (ex.chords, ex.notes))

    def test_three_chord_spans_resolve_at_every_boundary(self) -> None:
        resp, _ = ask("Create an enclosure targeting the third of each chord over the next three chords.", key="C")
        ex = exercise_of(resp)
        self.assertIsNotNone(ex)
        self.assertEqual(len(ex.chords), 3)
        self.assertTrue(lands_on(ex, ("3",)) and enclosed(ex), (ex.chords, ex.notes))

    def test_chord_assignment_and_timing_follow_the_harmony(self) -> None:
        resp, _ = ask("Create a chromatic approach to the next chord's third.", key="C")
        ex = exercise_of(resp)
        self.assertEqual(ex.chord_assignment, sorted(ex.chord_assignment))
        self.assertEqual(sorted(set(ex.chord_assignment)), list(range(len(ex.chords))))
        slots = ex.explanation_facts["mission_example"]["motif"]["chord_timeline"]
        for i, slot in enumerate(slots):
            self.assertEqual(arrival_index(ex, i), slot["first_note"])        # each chord's first note is on its own downbeat
        # the approach note is the last note of the PREVIOUS chord
        self.assertLess(arrival_index(ex, 1) - 1, arrival_index(ex, 1))
        self.assertEqual(ex.chord_assignment[arrival_index(ex, 1) - 1], 0)

    def test_guide_tones_with_chromatic_approaches_land_on_thirds_and_sevenths(self) -> None:
        for key in ("C", "F", "Am"):
            with self.subTest(key=key):
                resp, _ = ask("Give me guide tones with chromatic approaches over the next three chords.", key=key)
                ex = exercise_of(resp)
                self.assertIsNotNone(ex, resp.direct_answer[:140])
                pcs = [chord_pcs(c, key) for c in ex.chords]
                for i, p in enumerate(pcs):                      # guide tones: the 3rd, and the 7th where the chord has one
                    self.assertIn(ex.midi[arrival_index(ex, i)] % 12, {p[1]} | ({p[3]} if len(p) > 3 else set()))
                self.assertTrue(approached_by_half_step(ex), (ex.chords, ex.notes))
                self.assertEqual(ex.provenance["mission_vocabulary"], "guide_tone_voice_leading")

    def test_guide_tones_with_enclosures_surround_each_arrival(self) -> None:
        resp, _ = ask("Give me guide tones with enclosures over the next two chords.", key="C")
        ex = exercise_of(resp)
        self.assertIsNotNone(ex)
        self.assertTrue(enclosed(ex), (ex.chords, ex.notes))

    def test_every_check_is_recorded_and_passed(self) -> None:
        resp, _ = ask("Create an enclosure targeting the third of each chord", key="C")
        ex = exercise_of(resp)
        names = {c["name"] for c in ex.validation["checks"]}
        self.assertTrue(ex.validation["ok"])
        for expected in ("mission_validator", "harmonic_boundaries", "landing_tone_each_chord", "enclosure_at_each_chord_change"):
            self.assertIn(expected, names)

    def test_the_card_explains_each_chord_change_from_the_notes(self) -> None:
        resp, _ = ask("Create an enclosure targeting the third of each chord", key="C")
        self.assertIn("At each chord change", resp.direct_answer)
        self.assertIn("surround", resp.direct_answer)
        self.assertIn("3rd of G7", resp.direct_answer.replace("♭", "b"))

    def test_guitar_gets_a_tab_and_practice_key_agrees(self) -> None:
        resp, _ = ask("Create a chromatic approach to the next chord's third.", key="F", instrument="Guitar")
        ex = exercise_of(resp)
        self.assertTrue(resp.diagnostics["guitar_tab_present"])
        self.assertIn("e|", resp.direct_answer)
        self.assertEqual(ex.context.concert_key, "F")
        self.assertIn("K:F", resp.notation_abc)


class TestCompositeLimits(unittest.TestCase):
    def test_a_tone_a_chord_does_not_have_is_refused_by_name(self) -> None:
        session = session_for("C")
        session["home_sections"] = {"Verse 1": ["C", "F", "G", "C"]}            # triads have no 7th
        resp, _ = ask("Create an enclosure targeting the seventh of each chord over the next two chords.", session=session)
        self.assertIsNone(exercise_of(resp))
        self.assertIn("has no 7th", resp.direct_answer)

    def test_an_enclosure_in_the_first_chord_then_a_resolution_is_not_faked(self) -> None:
        resp, _ = ask("Give me an enclosure around the third of G7, then resolve into Cmaj7.", key="C")
        self.assertIsNone(exercise_of(resp))
        self.assertIn("only places these figures at the chord change", resp.direct_answer)
        self.assertIn("targeting the 3rd of each chord", resp.direct_answer)
        self.assertEqual(resp.notation_abc, "")

    def test_pentatonic_with_enclosures_is_refused_with_the_reason(self) -> None:
        for q in ("Create a pentatonic pattern with enclosures over G7", "Create a pentatonic pattern with enclosures over the next two chords"):
            resp, _ = ask(q, key="C")
            self.assertIsNone(exercise_of(resp), q)
            self.assertIn("chromatic embellishments", resp.direct_answer, q)

    def test_a_named_sequence_that_is_not_in_the_song_is_not_invented(self) -> None:
        resp, _ = ask("Give me an enclosure targeting the third of each chord, D7 then resolve into Cmaj7", key="C")
        self.assertIsNone(exercise_of(resp))

    def test_stage_one_and_two_behaviour_is_unchanged(self) -> None:
        plain, _ = ask("Give me an enclosure across the next two chords", key="C")
        self.assertEqual(exercise_of(plain).provenance["mission_vocabulary"], "enclose_next_target")
        single, _ = ask("Give me an enclosure exercise targeting the third of G7", key="C")
        self.assertEqual(exercise_of(single).provenance["engine"], "melodic_pattern_engine")


class TestSingleChordComposites(unittest.TestCase):
    def test_guide_tones_with_chromatic_approaches_land_on_the_third_and_the_seventh(self) -> None:
        for key, chord in (("C", "G7"), ("C", "Cmaj7"), ("C", "Dm7"), ("Eb", "Bb7")):
            with self.subTest(chord=chord):
                resp, _ = ask(f"Give me guide tones with chromatic approaches over {chord}.", key=key)
                ex = exercise_of(resp)
                self.assertIsNotNone(ex, resp.direct_answer[:140])
                p = chord_pcs(chord, key)
                landed = {ex.midi[i] % 12 for i in range(1, len(ex.midi))
                          if abs(ex.midi[i - 1] - ex.midi[i]) == 1 and ex.chord_roles[i] and ex.chord_roles[i - 1] == ""}
                self.assertEqual(landed, {p[1], p[3]}, (ex.notes, ex.chord_roles))

    def test_guide_tones_with_enclosures_surround_both_guide_tones(self) -> None:
        resp, _ = ask("Give me guide tones with enclosures over Cmaj7.", key="C")
        ex = exercise_of(resp)
        p = chord_pcs("Cmaj7", "C")
        found = set()
        for i in range(2, len(ex.midi)):
            lead = [ex.midi[i - 2], ex.midi[i - 1]]
            t = ex.midi[i]
            if any(m > t for m in lead) and any(m < t for m in lead) and all(0 < abs(m - t) <= 3 for m in lead):
                found.add(t % 12)
        self.assertTrue({p[1], p[3]} <= found, (ex.notes, found))

    def test_approaching_the_seventh_chromatically_lands_on_the_seventh_every_time(self) -> None:
        resp, _ = ask("Approach the seventh of G7 chromatically.", key="C")
        ex = exercise_of(resp)
        self.assertIsNotNone(ex)
        seventh = chord_pcs("G7", "C")[3]
        landings = [i for i in range(1, len(ex.midi)) if abs(ex.midi[i - 1] - ex.midi[i]) == 1 and ex.chord_roles[i] and not ex.chord_roles[i - 1]]
        self.assertTrue(landings)
        self.assertTrue(all(ex.midi[i] % 12 == seventh for i in landings), (ex.notes, landings))

    def test_a_guide_tone_line_cannot_target_the_fifth(self) -> None:
        resp, _ = ask("Give me guide tones with chromatic approaches targeting the fifth over G7", key="C")
        self.assertIsNone(exercise_of(resp))
        self.assertIn("guide tones are the 3rd and the 7th", resp.direct_answer)


class TestCompositeMissionsTransfer(unittest.TestCase):
    def test_a_span_composite_opens_as_the_exact_example_of_its_own_mission(self) -> None:
        resp, session = ask("Create an enclosure targeting the third of each chord over the next two chords.", key="C")
        action = resp.diagnostics["open_in_missions"]
        ex = exercise_of(resp)
        before = copy.deepcopy(action["example"])
        result = open_exercise_in_missions(session, action)
        self.assertTrue(result["ok"], result)
        staged = session["improv_span_mission"]["example"]
        self.assertEqual(staged, before)                                              # not regenerated
        self.assertEqual(staged["mission_id"], "enclose_next_target")                # labelled as what it is
        self.assertEqual(staged["motif"]["midi"], ex.midi)
        self.assertEqual(staged["motif"]["note_chord_index"], ex.chord_assignment)  # chord assignment preserved
        self.assertEqual(staged["handoff"]["practice_key"], "C")
        self.assertEqual(session["_improv_span_mission_choice"], "enclose_next_target")

    def test_the_guide_tone_composite_keeps_the_guide_tone_mission(self) -> None:
        resp, session = ask("Give me guide tones with chromatic approaches over the next two chords.", key="C")
        self.assertTrue(open_exercise_in_missions(session, resp.diagnostics["open_in_missions"])["ok"])
        self.assertEqual(session["improv_span_mission"]["example"]["mission_id"], "guide_tone_voice_leading")

    def test_a_single_chord_composite_opens_as_the_techniques_mission(self) -> None:
        from improvisation_missions import MISSION_EXAMPLE_KEY

        resp, session = ask("Give me guide tones with chromatic approaches over G7.", key="C")
        ex = exercise_of(resp)
        self.assertTrue(open_exercise_in_missions(session, resp.diagnostics["open_in_missions"])["ok"])
        stored = session[MISSION_EXAMPLE_KEY]
        self.assertEqual(stored["mission"], "Approach a chord tone chromatically")
        self.assertEqual((stored["motif"]["notes"], stored["motif"]["midi"]), (ex.notes, ex.midi))


class TestPickerAndStageCompatibility(unittest.TestCase):
    def test_stage_two_and_span_requests_still_work_together(self) -> None:
        for q, vocab in (("Give me a guide-tone pattern through the next three chords", "guide_tones"),
                         ("Create chromatic approaches over the next three chords", "chord_tones")):
            resp, _ = ask(q, key="Am")
            ex = exercise_of(resp)
            self.assertIsNotNone(ex, q)
            self.assertEqual(ex.vocabulary, vocab)

    def test_progressions_used_here_exist(self) -> None:
        for key in ("C", "F", "Eb", "Am", "Gm", "D", "Bb", "Em"):
            self.assertIn(key, PROGRESSIONS)


if __name__ == "__main__":
    unittest.main()

"""AMI Slice 5 Stage 2: advanced single-chord improvisation vocabulary (enclosures, chromatic approaches, bebop, target-the-3rd).

The notes come from the app's pattern engine (``melodic_pattern_engine``) and, for a plain "target the 3rd", from the Mission
engine; AMI only maps the request onto them and verifies the result. These tests re-derive the musical facts from the notes
themselves (pitches and chord tones), not from the engine's own labels.
"""

from __future__ import annotations

import copy
import re
import unittest

from instrument_transposition import CHART_IN_INSTRUMENT_KEY_KEY, SELECTED_TRANSPOSING_INSTRUMENT_KEY
from music_coach_ami.exercise_bridge import AMI_LAST_EXERCISE_KEY
from music_coach_ami.exercise_intent import is_exercise_request, parse_exercise_intent
from music_coach_ami.exercise_model import (
    ROUTE_BRIDGE,
    ROUTE_LEGACY,
    TECHNIQUE_BEBOP,
    TECHNIQUE_CHROMATIC_APPROACH,
    TECHNIQUE_COMPOSITE,
    TECHNIQUE_ENCLOSURE,
    TECHNIQUE_TARGET_TONE,
)
from music_coach_ami.exercise_single import single_plan
from music_coach_ami.exercise_span import open_exercise_in_missions
from tests.test_ami_span_guide_tones import PROGRESSIONS, ask, exercise_of, session_for

THIRD_OF = {"G7": 11, "A7": 1, "Dm7": 5, "Cmaj7": 4, "Bb7": 2, "Am7": 0, "D7": 6, "F7": 9}   # pitch classes (B, C#, F, E, D, C, F#, A)
ROLE_OFFSETS = {"R": (0,), "3": (3, 4), "5": (6, 7, 8), "7": (10, 11)}
NAME_RE = re.compile(r"^[A-G](#|b)?$")


def chord_root_pc(chord: str) -> int:
    from improvisation_motif import _midi_from_note

    m = re.match(r"([A-G](?:#|b)?)", chord)
    return _midi_from_note(m.group(1), 4) % 12


def role_pcs(chord: str, role: str) -> set[int]:
    return {(chord_root_pc(chord) + o) % 12 for o in ROLE_OFFSETS[role]}


def target_indices(ex, role: str) -> list[int]:
    """Indices where the exercise lands on a chord tone of ``role`` after a lead-in (derived from pitches only)."""
    pcs = role_pcs(ex.chord, role)
    return [i for i, m in enumerate(ex.midi) if i >= 1 and m % 12 in pcs and ex.chord_roles[i] == role]


def surrounded(ex, i: int) -> bool:
    """Notes i-2 and i-1 are within a minor third of the target, one above and one below, and are not that note."""
    if i < 2:
        return False
    t = ex.midi[i]
    lead = [ex.midi[i - 2], ex.midi[i - 1]]
    return any(m > t for m in lead) and any(m < t for m in lead) and all(0 < abs(m - t) <= 3 for m in lead)


def half_step_approach(ex, i: int) -> bool:
    return i >= 1 and abs(ex.midi[i - 1] - ex.midi[i]) == 1 and ex.chord_roles[i - 1] == ""


class TestIntentClassification(unittest.TestCase):
    CASES = {
        "Give me an enclosure exercise targeting the third of G7.": (TECHNIQUE_ENCLOSURE, "third", "", "", "G7"),
        "Create chromatic approaches over Dm7.": (TECHNIQUE_CHROMATIC_APPROACH, "", "", "", "Dm7"),
        "Create a bebop-style pattern over G7.": (TECHNIQUE_BEBOP, "", "", "", "G7"),
        "Give me a chord-tone pattern with approach notes.": (TECHNIQUE_CHROMATIC_APPROACH, "", "", "", ""),
        "Create an ascending enclosure exercise.": (TECHNIQUE_ENCLOSURE, "", "ascending", "", ""),
        "Make an easier pattern targeting the third.": (TECHNIQUE_TARGET_TONE, "third", "", "easier", ""),
        "Give me a descending chromatic approach exercise over G7 targeting the root": (TECHNIQUE_CHROMATIC_APPROACH, "root", "descending", "", "G7"),
        "Give me a harder enclosure exercise over Cmaj7": (TECHNIQUE_ENCLOSURE, "", "", "harder", "Cmaj7"),
    }

    def test_requests_are_split_into_technique_target_direction_difficulty_and_chord(self) -> None:
        for question, (technique, tone, direction, difficulty, chord) in self.CASES.items():
            with self.subTest(question=question):
                i = parse_exercise_intent(question)
                self.assertEqual((i.technique, i.target_tone, i.direction, i.difficulty_request, i.explicit_chord),
                                 (technique, tone, direction, difficulty, chord))
                self.assertEqual((i.scope, i.engine_route), ("single_chord", ROUTE_BRIDGE))
                self.assertTrue(is_exercise_request(question))

    def test_pitch_vocabulary_stays_separate_from_technique(self) -> None:
        i = parse_exercise_intent("Create chromatic approaches over Dm7.")
        self.assertEqual(i.vocabulary, "chord_tones")
        self.assertNotIn("vocabulary", i.explicit_fields)             # inferred target space, not words the user said
        self.assertEqual(i.explicit_fields["technique"], "user")

    def test_register_is_read(self) -> None:
        self.assertEqual(parse_exercise_intent("Create an enclosure exercise in a high register").register_request, "high")
        self.assertEqual(parse_exercise_intent("Create an enclosure exercise in a low register").register_request, "low")

    def test_legacy_and_theory_requests_are_not_redirected(self) -> None:
        for q in ("Give me a bebop line", "Give me a bebop scale pattern", "Give me the third of G7", "What is the third of G7?",
                  "Give me a C major blues line using the flat 3rd and major 3rd, with staccato approach notes and a crescendo.",
                  "Give me an A minor pentatonic line", "Give me a guide-tone pattern over E7.", "Give me a blues lick over this chord.",
                  "Give me a chord-tone exercise in A minor."):
            with self.subTest(question=q):
                self.assertEqual(parse_exercise_intent(q).technique, "")
        self.assertEqual(parse_exercise_intent("Give me a bebop scale pattern").engine_route, ROUTE_LEGACY)
        self.assertFalse(is_exercise_request("Give me the third of G7"))

    def test_span_requests_with_a_technique_still_go_to_the_span_path(self) -> None:
        for q in ("Give me an enclosure across the next two chords", "Create chromatic approaches over the next three chords"):
            self.assertEqual(parse_exercise_intent(q).scope, "span", q)

    def test_composites_are_flagged(self) -> None:
        self.assertEqual(parse_exercise_intent("Give me a bebop line with chromatic approaches over G7").technique, TECHNIQUE_COMPOSITE)
        self.assertEqual(parse_exercise_intent("Give me chromatic approaches and enclosures over G7").technique, TECHNIQUE_COMPOSITE)


class TestPatternPlan(unittest.TestCase):
    def test_each_technique_maps_to_the_single_chord_mission_that_owns_it(self) -> None:
        expect = {
            "Give me an enclosure exercise over G7": "Enclose a target chord tone before resolving",
            "Create chromatic approaches over G7": "Approach a chord tone chromatically",
            "Create a bebop-style pattern over G7": "Create a bebop-style line",
            "Give me a lick targeting the third over G7": "Resolve convincingly to the chord's 3rd",
        }
        for q, mission in expect.items():
            plan = single_plan(parse_exercise_intent(q))
            self.assertTrue(plan.supported, q)
            self.assertEqual((plan.mission_id, plan.action_kind), (mission, "single_technique"), q)

    def test_unsupported_combinations_say_why(self) -> None:
        for q, why in (
            ("Give me a pentatonic enclosure over G7", "needs a chord change to resolve into"),
            ("Give me a bebop line with chromatic approaches over G7", "in one line"),
            ("Give me a lick targeting the fifth over G7", "on its own is not a Mission yet"),
        ):
            plan = single_plan(parse_exercise_intent(q))
            self.assertFalse(plan.supported, q)
            self.assertIn(why, plan.limitation, q)


class TestMusicalCorrectness(unittest.TestCase):
    def test_an_enclosure_targeting_the_third_surrounds_and_lands_on_the_third(self) -> None:
        for key, chord in (("C", "G7"), ("D", "A7"), ("F", "C7"), ("Eb", "Bb7")):
            with self.subTest(chord=chord):
                resp, _ = ask(f"Give me an enclosure exercise targeting the third of {chord}.", key=key)
                ex = exercise_of(resp)
                self.assertIsNotNone(ex, resp.direct_answer[:100])
                self.assertEqual(ex.chord, chord)
                targets = target_indices(ex, "3")
                self.assertTrue(targets, ex.notes)
                for i in targets:
                    self.assertTrue(surrounded(ex, i), (ex.notes, i))
                    self.assertIn(ex.midi[i] % 12, role_pcs(chord, "3"))
                # every landing in the exercise is the 3rd: no other chord tone is the target of a lead-in
                for role in ("R", "5", "7"):
                    self.assertFalse(any(surrounded(ex, i) for i in target_indices(ex, role)), (role, ex.notes))

    def test_enclosure_targets_each_requested_chord_tone(self) -> None:
        for tone, role in (("root", "R"), ("third", "3"), ("fifth", "5"), ("seventh", "7")):
            with self.subTest(tone=tone):
                resp, _ = ask(f"Give me an enclosure exercise targeting the {tone} of G7", key="C")
                ex = exercise_of(resp)
                self.assertIsNotNone(ex, resp.direct_answer[:100])
                idx = [i for i in target_indices(ex, role) if surrounded(ex, i)]
                self.assertTrue(idx, (tone, ex.notes))

    def test_a_chromatic_approach_resolves_by_half_step_onto_a_chord_tone(self) -> None:
        for key, chord in (("C", "Dm7"), ("C", "Cmaj7"), ("F", "C7"), ("Eb", "Bb7")):
            with self.subTest(chord=chord):
                resp, _ = ask(f"Create chromatic approaches over {chord}.", key=key)
                ex = exercise_of(resp)
                self.assertIsNotNone(ex, resp.direct_answer[:100])
                landings = [i for i in range(1, len(ex.midi)) if ex.chord_roles[i] and half_step_approach(ex, i)]
                self.assertTrue(landings, ex.notes)
                for i in landings:
                    self.assertIn(ex.midi[i] % 12, {m % 12 for m, r in zip(ex.midi, ex.chord_roles) if r})

    def test_chromatic_approach_to_a_named_tone_lands_on_that_tone(self) -> None:
        resp, _ = ask("Give me a chromatic approach exercise over G7 targeting the third", key="C")
        ex = exercise_of(resp)
        self.assertIsNotNone(ex)
        landings = [i for i in target_indices(ex, "3") if half_step_approach(ex, i)]
        self.assertTrue(landings, ex.notes)

    def test_plain_target_the_third_ends_on_the_third_at_every_difficulty(self) -> None:
        for word in ("", "easier ", "harder "):
            with self.subTest(word=word):
                resp, _ = ask(f"Make an {word}pattern targeting the third over G7.".replace("an pattern", "a pattern"), key="C")
                ex = exercise_of(resp)
                self.assertIsNotNone(ex, resp.direct_answer[:100])
                self.assertEqual(ex.midi[-1] % 12, THIRD_OF["G7"])
                self.assertEqual(ex.chord_roles[-1], "3")
                self.assertEqual(ex.provenance["mission_vocabulary"], "Resolve convincingly to the chord's 3rd")

    def test_bebop_line_is_grounded_in_the_chord(self) -> None:
        resp, _ = ask("Create a bebop-style pattern over G7.", key="C")
        ex = exercise_of(resp)
        self.assertIsNotNone(ex)
        self.assertEqual(ex.explanation_facts["family"]["category"], "bebop")
        self.assertGreaterEqual(sum(1 for r in ex.chord_roles if r), 2)
        self.assertGreaterEqual(len(ex.notes), 4)

    def test_spelling_is_pipeline_safe_in_sharp_and_flat_keys(self) -> None:
        from improvisation_motif import _midi_from_note

        for key, chord in (("C", "G7"), ("D", "A7"), ("F", "C7"), ("Eb", "Bb7"), ("Bb", "F7"), ("Am", "E7"), ("Gm", "D7")):
            for q in (f"Give me an enclosure exercise over {chord}", f"Create chromatic approaches over {chord}"):
                with self.subTest(q=q, key=key):
                    resp, _ = ask(q, key=key if key in PROGRESSIONS else "Am")
                    ex = exercise_of(resp)
                    self.assertIsNotNone(ex, resp.direct_answer[:100])
                    for name, midi in zip(ex.notes, ex.midi):
                        self.assertRegex(name, NAME_RE)
                        self.assertEqual(_midi_from_note(name, 4) % 12, midi % 12)

    def test_the_card_spells_the_line_the_way_the_missions_page_will(self) -> None:
        """AMI uses the Mission engine's own chord-aware speller, so the card and the opened example never disagree."""
        from improvisation_missions import MISSION_EXAMPLE_KEY

        for key, chord in (("D", "Dmaj7"), ("C", "G7"), ("Eb", "Bb7")):
            with self.subTest(chord=chord):
                resp, session = ask(f"Give me a harder descending enclosure exercise over {chord}", key=key)
                ex = exercise_of(resp)
                self.assertTrue(open_exercise_in_missions(session, resp.diagnostics["open_in_missions"])["ok"])
                self.assertEqual(session[MISSION_EXAMPLE_KEY]["motif"]["notes"], ex.notes)
                self.assertEqual(session[MISSION_EXAMPLE_KEY]["motif"]["midi"], ex.midi)

    def test_direction_is_honoured(self) -> None:
        for direction in ("ascending", "descending"):
            with self.subTest(direction=direction):
                resp, _ = ask(f"Create an {direction} enclosure exercise over G7", key="C")
                ex = exercise_of(resp)
                self.assertIsNotNone(ex)
                self.assertEqual(ex.explanation_facts["direction"], direction)
                landings = [i for i in range(2, len(ex.midi)) if surrounded(ex, i)]
                self.assertGreaterEqual(len(landings), 2, ex.notes)
                steps = [ex.midi[b] - ex.midi[a] for a, b in zip(landings, landings[1:])]
                self.assertTrue(all(s > 0 for s in steps) if direction == "ascending" else all(s < 0 for s in steps), (direction, steps))

    def test_a_targeted_exercise_repeats_its_cell_an_octave_away_in_the_requested_direction(self) -> None:
        for direction, sign in (("ascending", 1), ("descending", -1)):
            resp, _ = ask(f"Give me a {direction} enclosure exercise targeting the third of G7", key="C")
            ex = exercise_of(resp)
            half = len(ex.midi) // 2
            self.assertEqual([m - ex.midi[0] for m in ex.midi[half:]], [m - ex.midi[0] for m in ex.midi[:half]][:0] or
                             [m + 12 * sign - ex.midi[0] for m in ex.midi[:half]], direction)

    def test_difficulty_moves_the_pattern_family_up_or_down(self) -> None:
        rank = {"Beginner": 0, "Intermediate": 1, "Advanced": 2}
        easier, _ = ask("Give me an easier chromatic approach exercise over Cmaj7", key="C")
        harder, _ = ask("Give me a harder chromatic approach exercise over Cmaj7", key="C")
        e, h = exercise_of(easier), exercise_of(harder)
        self.assertLess(rank[e.explanation_facts["family"]["difficulty"]], rank[h.explanation_facts["family"]["difficulty"]])

    def test_a_level_the_engine_has_no_pattern_for_is_said_not_hidden(self) -> None:
        session = session_for("C", level="Beginner")
        resp, _ = ask("Give me an enclosure exercise over G7", session=session)
        ex = exercise_of(resp)
        self.assertIsNotNone(ex)
        self.assertEqual(ex.explanation_facts["family"]["difficulty"], "Intermediate")
        self.assertIn("closest", resp.direct_answer)

    def test_register_is_respected(self) -> None:
        high, _ = ask("Create an enclosure exercise over G7 in a high register", key="C")
        low, _ = ask("Create an enclosure exercise over G7 in a low register", key="C")
        self.assertGreaterEqual(min(exercise_of(high).midi), 67)
        self.assertLessEqual(max(exercise_of(low).midi), 74)

    def test_guitar_gets_playable_notes_and_a_tab(self) -> None:
        resp, _ = ask("Give me an enclosure exercise targeting the third of G7", key="C", instrument="Guitar")
        self.assertIn("e|", resp.direct_answer)
        self.assertTrue(resp.diagnostics["guitar_tab_present"])
        self.assertTrue(all(c["ok"] for c in resp.diagnostics["exercise_validation"]["checks"]))

    def test_every_check_passed_and_is_recorded(self) -> None:
        resp, _ = ask("Give me an enclosure exercise targeting the third of G7.", key="C")
        ex = exercise_of(resp)
        names = [c["name"] for c in ex.validation["checks"]]
        self.assertTrue(ex.validation["ok"])
        for expected in ("pattern_engine_validator", "enclosure_resolves_to_target", "target_is_requested_tone", "playable_on_instrument"):
            self.assertIn(expected, names)
        self.assertEqual(ex.provenance["engine"], "melodic_pattern_engine")


class TestKeyAndInstrumentContext(unittest.TestCase):
    def test_practice_key_is_the_sessions_and_the_staff_agrees(self) -> None:
        for key in ("C", "F", "D", "Eb"):
            with self.subTest(key=key):
                resp, _ = ask("Give me an enclosure exercise over G7", key=key, session=None)
                ex = exercise_of(resp)
                self.assertEqual(ex.context.concert_key, key)
                self.assertIn(f"K:{key}", resp.notation_abc)

    def test_a_transposing_instrument_gets_a_natively_spelled_written_line_and_no_handoff(self) -> None:
        session = session_for("C", instrument="Clarinet", **{CHART_IN_INSTRUMENT_KEY_KEY: True, SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Bb Clarinet"})
        resp, _ = ask("Give me an enclosure exercise targeting the third of G7", session=session)
        ex = exercise_of(resp)
        self.assertIsNotNone(ex, resp.direct_answer[:120])
        w = ex.written
        self.assertTrue(w["applied"])
        # the concert line moved by the transposition (possibly an octave away, to sit in the clarinet's written range)
        self.assertTrue(all((wm - cm) % 12 == 2 for wm, cm in zip(w["midi"], ex.midi)), (w["midi"], ex.midi))
        self.assertEqual([b - a for a, b in zip(w["midi"], w["midi"][1:])], [b - a for a, b in zip(ex.midi, ex.midi[1:])])
        self.assertEqual(w["chord"], "A7")
        for name, midi in zip(w["notes"], w["midi"]):
            self.assertRegex(name, NAME_RE)
        self.assertEqual([n for n in w["notes"][:4]], ["C", "D", "C#", "E"])  # a half-step below, whole step above, the 3rd, then up
        self.assertNotIn("open_in_missions", resp.diagnostics)
        self.assertTrue(any("concert pitch for now" in s for s in resp.practice_steps), resp.practice_steps)


class TestLimitations(unittest.TestCase):
    def test_unsupported_requests_are_stated_and_produce_no_exercise(self) -> None:
        for q, why in (
            ("Give me a pentatonic enclosure over G7", "needs a chord change to resolve into"),
            ("Give me a bebop line with chromatic approaches over G7", "in one line"),
            ("Give me a lick targeting the fifth over A7", "on its own is not a Mission yet"),
            ("Give me a blues pattern with enclosures over G7", "blues pitch vocabulary"),
        ):
            with self.subTest(q=q):
                resp, _ = ask(q, key="C")
                self.assertIsNone(exercise_of(resp))
                self.assertIn(why, resp.direct_answer)
                self.assertEqual(resp.notation_abc, "")

    def test_span_requests_for_single_chord_techniques_are_truthful(self) -> None:
        # (bebop across chords became supported in Stage 3b; a fifth-targeting span line is still refused)
        resp, _ = ask("Create a line that targets the fifth of each chord", key="C")
        self.assertIsNone(exercise_of(resp))
        self.assertIn("not the fifth", resp.direct_answer)

    def test_followups_on_a_technique_exercise_are_developed_in_stage_4b(self) -> None:
        # Stage 4b: a follow-up is built from the stored exercise (same chord, technique and target
        # tone) or refused with the stored exercise untouched. The old "not available yet" is gone.
        resp, session = ask("Give me an enclosure exercise targeting the third of G7", key="C")
        before = copy.deepcopy(session[AMI_LAST_EXERCISE_KEY])
        again, _ = ask("Make it easier.", session=session)
        self.assertNotIn("yet", again.direct_answer.split("Try this")[0])
        after = session[AMI_LAST_EXERCISE_KEY]
        if "built from your previous exercise" in again.direct_answer:
            self.assertEqual(after["intent"]["technique"], "enclosure")
            self.assertEqual(after["intent"]["target_tone"], "third")
            self.assertEqual(after["intent"]["explicit_chord"], "G7")
            self.assertNotEqual(after, before)
        else:
            self.assertEqual(after, before)

    def test_slice_one_and_four_behaviour_is_unchanged(self) -> None:
        single, _ = ask("Give me a guide-tone pattern over E7.", key="Am")
        self.assertEqual(exercise_of(single).intent.technique, "")
        span, _ = ask("Show me voice leading through this ii–V–I.", key="Am")
        self.assertEqual(exercise_of(span).chords, ["Bm7b5", "E7", "Am"])


class TestOpenInMissions(unittest.TestCase):
    def opened(self, question="Give me an enclosure exercise targeting the third of G7.", key="C", **kw):
        resp, session = ask(question, key=key, **kw)
        action = resp.diagnostics.get("open_in_missions")
        return resp, session, action

    def test_the_card_offers_the_action_with_the_exact_motif(self) -> None:
        resp, _, action = self.opened()
        ex = exercise_of(resp)
        self.assertEqual((action["kind"], action["label"], action["chord"]), ("single_technique", "Open in Missions", "G7"))
        self.assertEqual(action["motif"]["midi"], ex.midi)
        self.assertEqual(action["motif"]["notes"], ex.notes)

    def test_open_stages_the_exact_exercise_as_the_missions_example(self) -> None:
        from improvisation_missions import MISSION_EXAMPLE_KEY

        resp, session, action = self.opened()
        ex = exercise_of(resp)
        result = open_exercise_in_missions(session, action)
        self.assertTrue(result["ok"], result)
        stored = session[MISSION_EXAMPLE_KEY]
        self.assertEqual(stored["mission"], "Enclose a target chord tone before resolving")
        self.assertEqual((stored["motif"]["notes"], stored["motif"]["midi"]), (ex.notes, ex.midi))
        self.assertEqual(stored["motif"]["rhythm_events"], ex.rhythm_events)             # rhythm preserved, not re-picked
        self.assertEqual(stored["chord"], "G7")
        self.assertEqual(session["ii_selected_chord"], "G7")
        self.assertEqual(session["improv_active_mission"], "Enclose a target chord tone before resolving")
        self.assertEqual(session["improv_intelligence_tab"], "Missions")
        self.assertEqual(session["studio_page"], "creative")
        self.assertEqual(stored["concert_key"], "C")

    def test_repeated_opens_do_not_change_the_example(self) -> None:
        from improvisation_missions import MISSION_EXAMPLE_KEY

        _resp, session, action = self.opened()
        open_exercise_in_missions(session, action)
        first = copy.deepcopy(session[MISSION_EXAMPLE_KEY]["motif"])
        for _ in range(2):
            self.assertTrue(open_exercise_in_missions(session, action)["ok"])
            self.assertEqual(session[MISSION_EXAMPLE_KEY]["motif"]["midi"], first["midi"])

    def test_a_chord_that_is_not_in_the_song_is_refused_with_the_reason(self) -> None:
        _resp, session, action = self.opened("Give me an enclosure exercise targeting the third of E7.", key="C")
        result = open_exercise_in_missions(session, action)
        self.assertFalse(result["ok"])
        self.assertIn("not one of this song's chords", result["message"])
        self.assertNotIn("improv_mission_example", session)

    def test_a_practice_key_change_since_the_exercise_was_made_is_refused(self) -> None:
        _resp, session, action = self.opened()
        other = session_for("F")
        session["home_sections"] = other["home_sections"]
        session["display_key"] = session["concert_key"] = "F"
        result = open_exercise_in_missions(session, action)
        self.assertFalse(result["ok"])
        self.assertIn("Practice Key has changed", result["message"])

    def test_plain_target_the_third_opens_as_its_own_mission(self) -> None:
        from improvisation_missions import MISSION_EXAMPLE_KEY

        resp, session, action = self.opened("Make an easier pattern targeting the third over G7.")
        self.assertTrue(open_exercise_in_missions(session, action)["ok"])
        self.assertEqual(session[MISSION_EXAMPLE_KEY]["mission"], "Resolve convincingly to the chord's 3rd")
        self.assertEqual(session[MISSION_EXAMPLE_KEY]["motif"]["midi"], exercise_of(resp).midi)

    def test_the_button_label_still_carries_the_missions_icon(self) -> None:
        # the Stage 1 button test covers rendering; this pins that single-chord actions use the same control
        from applied_math_return_insight import _render_open_in_missions_action
        from music_feature_icons import FEATURE_ICONS

        _resp, _session, action = self.opened()
        seen = {}

        class FakeSt:
            def button(self, label, **kw):
                seen["label"] = label
                return False

        _render_open_in_missions_action(FakeSt(), {"open_in_missions": action}, app="music")
        self.assertEqual(seen["label"], f"{FEATURE_ICONS['mission']} Open in Missions")


if __name__ == "__main__":
    unittest.main()

"""AMI Slice 5 Stage 1: existing validated span Missions exposed through AMI."""

from __future__ import annotations

import copy
import unittest

from melodic_pattern_engine import build_context
from music_coach_ami.exercise_intent import is_exercise_request, parse_exercise_intent
from music_coach_ami.exercise_model import (
    ROUTE_BRIDGE,
    TECHNIQUE_CHROMATIC_APPROACH,
    TECHNIQUE_ENCLOSURE,
    VOCAB_CHORD_TONES,
)
from music_coach_ami.exercise_span import open_exercise_in_missions, span_pattern_plan
from tests.test_ami_span_guide_tones import PROGRESSIONS, ask, exercise_of


CASES = {
    "Give me a pentatonic pattern across the next two chords": "pentatonic_per_chord",
    "Create a chord-tone pattern over the next three chords": "chord_tones_each_chord",
    "Create chromatic approaches to the next chord": "approach_next_chord",
    "Give me enclosures targeting the next chord": "enclose_next_target",
}


def _example(ex):
    return ex.explanation_facts["mission_example"]


class TestStage1IntentAndPlan(unittest.TestCase):
    def test_natural_language_selects_existing_missions(self) -> None:
        for question, mission_id in CASES.items():
            with self.subTest(question=question):
                intent = parse_exercise_intent(question)
                plan = span_pattern_plan(intent)
                self.assertTrue(is_exercise_request(question))
                self.assertEqual((intent.scope, intent.engine_route), ("span", ROUTE_BRIDGE))
                self.assertEqual(plan.mission_id, mission_id)
                self.assertTrue(plan.supported)

    def test_pitch_vocabulary_and_technique_are_separate(self) -> None:
        approach = parse_exercise_intent("Create chromatic approaches to the next chord")
        enclosure = parse_exercise_intent("Give me enclosures targeting the next chord")
        self.assertEqual((approach.vocabulary, approach.technique),
                         (VOCAB_CHORD_TONES, TECHNIQUE_CHROMATIC_APPROACH))
        self.assertEqual((enclosure.vocabulary, enclosure.technique),
                         (VOCAB_CHORD_TONES, TECHNIQUE_ENCLOSURE))
        self.assertNotIn("vocabulary", approach.explicit_fields)  # inferred target space, not words the user said
        self.assertEqual(approach.explicit_fields["technique"], "user")

    def test_two_and_three_chord_phrasing_is_preserved(self) -> None:
        for count, word in ((2, "two"), (3, "three")):
            for vocabulary in ("pentatonic", "chord-tone"):
                question = f"Give me a {vocabulary} pattern over the next {word} chords"
                with self.subTest(question=question):
                    intent = parse_exercise_intent(question)
                    self.assertEqual((intent.scope, intent.span_length), ("span", count))

    def test_unsupported_requests_are_truthful(self) -> None:
        cases = (
            ("Give me a blues pattern over the next two chords", "blues exercises across several chords"),
            # (guide tones + approaches became supported in Stage 3, bebop and a pentatonic framework with embellishments in 3b)
            ("Create a line that targets the fifth of each chord", "not the fifth"),
            ("Give me a blues line with enclosures over the next two chords", "blues exercises across several chords"),
            ("Give me chromatic approaches and enclosures over the next two chords", "combining chromatic approaches"),
        )
        for question, reason in cases:
            with self.subTest(question=question):
                response, _session = ask(question)
                self.assertIsNone(exercise_of(response))
                self.assertIn(reason, response.direct_answer)
                self.assertEqual(response.notation_abc, "")


class TestStage1Generation(unittest.TestCase):
    def test_every_new_vocabulary_generates_two_and_three_chord_examples(self) -> None:
        prompts = (
            ("pentatonic pattern", "pentatonic_per_chord"),
            ("chord-tone pattern", "chord_tones_each_chord"),
            ("chromatic approach exercise", "approach_next_chord"),
            ("enclosure exercise", "enclose_next_target"),
        )
        for count, word in ((2, "two"), (3, "three")):
            for phrase, mission_id in prompts:
                question = f"Give me a {phrase} over the next {word} chords"
                with self.subTest(question=question):
                    response, _session = ask(question)
                    ex = exercise_of(response)
                    self.assertIsNotNone(ex, response.direct_answer)
                    self.assertEqual((len(ex.chords), ex.engine_detail), (count, mission_id))
                    self.assertEqual(sorted(set(ex.chord_assignment)), list(range(count)))
                    self.assertTrue(ex.validation["ok"], ex.validation)
                    self.assertEqual(response.diagnostics["open_in_missions"]["mission_id"], mission_id)

    def test_harmonic_timeline_and_note_assignment_have_the_same_boundaries(self) -> None:
        for question in CASES:
            with self.subTest(question=question):
                response, _session = ask(question)
                ex = exercise_of(response)
                timeline = _example(ex)["motif"]["chord_timeline"]
                self.assertEqual(len(ex.chord_assignment), len(ex.midi))
                for idx, slot in enumerate(timeline):
                    owned = [n for n, chord_idx in enumerate(ex.chord_assignment) if chord_idx == idx]
                    self.assertEqual((owned[0], owned[-1]), (slot["first_note"], slot["last_note"]))
                    self.assertEqual(slot["chord"], ex.chords[idx])

    def test_chord_tone_pattern_uses_only_the_sounding_chord(self) -> None:
        response, _session = ask("Create a chord-tone pattern over the next three chords")
        ex = exercise_of(response)
        for midi, chord_idx in zip(ex.midi, ex.chord_assignment):
            self.assertIn(midi % 12, build_context(ex.context.concert_key, ex.chords[chord_idx]).chord_pcs)
        evidence = [e["check"] for e in _example(ex)["evidence"]]
        self.assertIn("only chord tones of the sounding chord", evidence)

    def test_pentatonic_pattern_uses_each_chords_collection(self) -> None:
        from span_motif_engine import _pentatonic

        response, _session = ask("Give me a pentatonic pattern across the next three chords")
        ex = exercise_of(response)
        motif = _example(ex)["motif"]
        timeline = motif["chord_timeline"]
        for idx, slot in enumerate(timeline):
            context = build_context(ex.context.concert_key, slot["chord"])
            allowed = set(_pentatonic(context))
            # The final note before a change may be the validated connector into
            # the next chord; all core notes remain in this chord's pentatonic.
            indices = list(range(slot["first_note"], slot["last_note"] + 1))
            if idx + 1 < len(timeline):
                indices = indices[:-1]
            self.assertTrue(all(ex.midi[n] % 12 in allowed for n in indices), (slot, ex.notes))

    def test_chromatic_approach_resolves_at_each_change(self) -> None:
        response, _session = ask("Create chromatic approaches over the next three chords")
        ex = exercise_of(response)
        timeline = _example(ex)["motif"]["chord_timeline"]
        for slot in timeline[1:]:
            target = slot["first_note"]
            self.assertEqual(abs(ex.midi[target] - ex.midi[target - 1]), 1)
            chord_idx = ex.chord_assignment[target]
            self.assertIn(ex.midi[target] % 12, build_context(ex.context.concert_key, ex.chords[chord_idx]).chord_pcs)

    def test_enclosure_surrounds_and_resolves_at_each_change(self) -> None:
        response, _session = ask("Give me enclosures across the next three chords")
        ex = exercise_of(response)
        timeline = _example(ex)["motif"]["chord_timeline"]
        for slot in timeline[1:]:
            target = slot["first_note"]
            before = [ex.midi[target - 2] - ex.midi[target], ex.midi[target - 1] - ex.midi[target]]
            self.assertLess(before[0] * before[1], 0, before)
            chord_idx = ex.chord_assignment[target]
            self.assertIn(ex.midi[target] % 12, build_context(ex.context.concert_key, ex.chords[chord_idx]).chord_pcs)

    def test_flat_and_sharp_keys_keep_valid_chord_aware_spelling(self) -> None:
        from improvisation_motif import _midi_from_note

        for key in ("Gm", "Em", "Bb"):
            with self.subTest(key=key):
                response, _session = ask("Create a chord-tone pattern over the next three chords", key=key)
                ex = exercise_of(response)
                self.assertEqual(ex.chords, PROGRESSIONS[key][:3])
                self.assertTrue(all(_midi_from_note(note, 4) % 12 == midi % 12 for note, midi in zip(ex.notes, ex.midi)))
                if key == "Em":
                    self.assertIn("D#", ex.notes)  # B7's chord-defining major 3rd, not Eb
                if key == "Bb":
                    self.assertIn("Eb", ex.notes)

    def test_practice_key_is_the_single_key_authority(self) -> None:
        response, _session = ask("Give me a pentatonic pattern across the next three chords", key="Gm")
        ex = exercise_of(response)
        action = response.diagnostics["open_in_missions"]
        self.assertEqual((ex.context.concert_key, action["concert_key"], action["example"]["handoff"]["practice_key"]),
                         ("Gm", "Gm", "Gm"))


class TestStage1MissionTransfer(unittest.TestCase):
    def test_every_new_route_transfers_the_exact_example_and_dynamic_mission_id(self) -> None:
        for question, mission_id in CASES.items():
            with self.subTest(question=question):
                response, session = ask(question)
                action = response.diagnostics["open_in_missions"]
                before = copy.deepcopy(action["example"])
                result = open_exercise_in_missions(session, action)
                self.assertTrue(result["ok"], result)
                state = session["improv_span_mission"]
                self.assertEqual(state["example"], before)
                self.assertEqual(state["ami_handoff"]["mission_id"], mission_id)
                self.assertEqual(session["_improv_span_mission_choice"], mission_id)
                self.assertEqual(session["studio_page"], "creative")

    def test_mismatched_action_and_example_are_refused_without_state_changes(self) -> None:
        response, session = ask("Give me a pentatonic pattern across the next two chords")
        action = copy.deepcopy(response.diagnostics["open_in_missions"])
        action["mission_id"] = "chord_tones_each_chord"
        result = open_exercise_in_missions(session, action)
        self.assertFalse(result["ok"])
        self.assertIn("no longer matches", result["message"])
        self.assertNotIn("improv_span_mission", session)

    def test_new_mission_identity_survives_backing_and_return_staging(self) -> None:
        from backing_owner_envelope import OWNER_MISSION, live_backing_owner
        from mission_return_destination import peek_mission_return_destination
        from mission_span_ui import start_span_mission_backing
        from music_workflow_mission_backing_click import peek_mission_backing_click_intent

        response, session = ask("Give me a pentatonic pattern across the next three chords")
        action = response.diagnostics["open_in_missions"]
        self.assertTrue(open_exercise_in_missions(session, action)["ok"])
        example = session["improv_span_mission"]["example"]

        start_span_mission_backing(
            session,
            example=example,
            heading="i-bVII-bVI",
            section_label="Verse 1",
            practice_key="Am",
            with_practice_lick=True,
            instrument="Guitar",
            level="Intermediate",
            style="rock",
            focus="",
            bpm=100,
        )

        click_intent = peek_mission_backing_click_intent(session)
        self.assertEqual(click_intent["mission"], example["mission_label"])
        self.assertEqual(live_backing_owner(session), OWNER_MISSION)
        destination = peek_mission_return_destination(session)
        self.assertEqual(destination["mission_id"], example["mission_label"])
        self.assertEqual(destination["backing_scope"], "mission_span")
        self.assertEqual(session["improv_span_mission"]["example"], example)

    def test_slice4_guide_tone_contract_remains_unchanged(self) -> None:
        response, _session = ask("Give me a guide-tone pattern through the next three chords")
        ex = exercise_of(response)
        checks = {c["name"]: c["ok"] for c in ex.validation["checks"]}
        self.assertEqual(ex.engine_detail, "guide_tone_voice_leading")
        self.assertEqual(response.diagnostics["open_in_missions"]["kind"], "span_guide_tones")
        self.assertTrue(checks["guide_tone_on_each_arrival"])
        self.assertTrue(checks["guide_tone_voice_leading"])


if __name__ == "__main__":
    unittest.main()


class TestOpenInMissionsButtonIcon(unittest.TestCase):
    """The AMI card's Open in Missions button carries the app's canonical Missions icon, left of the unchanged label."""

    def test_button_label_is_the_missions_icon_then_the_label(self) -> None:
        from applied_math_return_insight import _render_open_in_missions_action
        from music_feature_icons import FEATURE_ICONS

        seen = {}

        class FakeSt:
            def button(self, label, **kw):
                seen["label"], seen["key"], seen["kw"] = label, kw.get("key"), kw
                return False

            def warning(self, *_a, **_k):
                raise AssertionError("no warning expected")

        action = {"kind": "span_exercise", "exercise_id": "ex-abc", "label": "Open in Missions", "example": {"motif": {}}}
        _render_open_in_missions_action(FakeSt(), {"open_in_missions": action}, app="music")
        self.assertEqual(seen["label"], f"{FEATURE_ICONS['mission']} Open in Missions")
        self.assertTrue(seen["label"].endswith("Open in Missions"))             # the label text is unchanged
        self.assertEqual(seen["key"], "ami_open_missions_ex-abc")                # and so is the control's identity
        self.assertTrue(seen["kw"].get("use_container_width"))

    def test_no_button_without_an_example_or_off_the_music_app(self) -> None:
        from applied_math_return_insight import _render_open_in_missions_action

        class FakeSt:
            def button(self, *_a, **_k):
                raise AssertionError("must not render")

        _render_open_in_missions_action(FakeSt(), {"open_in_missions": {"label": "Open in Missions"}}, app="music")
        _render_open_in_missions_action(FakeSt(), {"open_in_missions": {"example": {"motif": {}}}}, app="investment")

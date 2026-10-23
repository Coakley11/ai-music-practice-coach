"""AMI Slice 4: guide-tone exercises across a 2-/3-chord HarmonicSpan, and "Open in Missions".

Requests -> ExerciseIntent (span structure) -> the span the Missions page would offer -> generate_mission_span_example
-> canonical GeneratedExercise (chords + chord_assignment) -> card -> staged Missions state (the same example).

Concert pitch only: transposing-instrument / capo spans are refused, not shown with wrong written notes (the chord-aware
respell in ``project_span_motif`` is a separate piece of work).
"""

from __future__ import annotations

import copy
import json
import unittest

from instrument_transposition import CHART_IN_INSTRUMENT_KEY_KEY, SELECTED_TRANSPOSING_INSTRUMENT_KEY
from music_coach_ami.exercise_bridge import AMI_LAST_EXERCISE_KEY
from music_coach_ami.exercise_intent import is_exercise_request, parse_exercise_intent
from music_coach_ami.exercise_model import ROUTE_BRIDGE, ROUTE_LEGACY, GeneratedExercise
from music_coach_ami.exercise_span import SPAN_MISSION_ID, open_exercise_in_missions
from music_coach_ami.pipeline import run_coach_submit

# Autumn-Leaves-shaped verse; the same shape moved to each key under test.
PROGRESSIONS = {
    "Am": ["Bm7b5", "E7", "Am", "Am", "Dm7", "G7", "Cmaj7", "Fmaj7"],
    "Gm": ["Am7b5", "D7", "Gm", "Gm", "Cm7", "F7", "Bbmaj7", "Ebmaj7"],
    "Em": ["F#m7b5", "B7", "Em", "Em", "Am7", "D7", "Gmaj7", "Cmaj7"],
    "Bb": ["Cm7", "F7", "Bbmaj7", "Bbmaj7", "Ebmaj7", "Ab7", "Dm7", "G7"],   # a flat key
    "Eb": ["Fm7", "Bb7", "Ebmaj7", "Abmaj7", "Gm7", "C7", "Fm7", "Bb7"],
}


def session_for(key="Am", instrument="Piano", **extra):
    s = {"instrument": instrument, "level": "Intermediate", "display_key": key, "concert_key": key, "song": "Shape",
         "artist": "Artist", "home_sections": {"Verse 1": list(PROGRESSIONS[key])}, "backing_track_bpm": 100,
         "studio_page": "practice"}
    s.update(extra)
    return s


def ask(question, **kw):
    session = kw.pop("session", None) or session_for(**kw)
    req, resp = run_coach_submit(question, session, ami_ctx={})
    return resp, session


def exercise_of(resp):
    raw = (resp.diagnostics or {}).get("generated_exercise")
    return GeneratedExercise.from_dict(raw) if raw else None


def midi_pcs(names):
    from improvisation_motif import _midi_from_note

    return [_midi_from_note(n, 4) % 12 for n in names]


def guide_pcs(chord, key):
    from improvisation_motif import chord_tone_names

    pcs = midi_pcs(chord_tone_names(chord, reference_key=key))
    return {pcs[1]} | ({pcs[3]} if len(pcs) > 3 else set())


class TestSpanRequestParsing(unittest.TestCase):
    def parse(self, q):
        return parse_exercise_intent(q)

    def test_the_requests_from_the_brief_are_span_exercises(self) -> None:
        cases = {
            "Show me a guide-tone line through these chords.": (0, ""),
            "Connect the thirds and sevenths.": (0, ""),
            "Give me a guide-tone exercise over the next two chords.": (2, ""),
            "Show me voice leading through this ii–V–I.": (3, "ii_V_I"),
            "Give me a guide-tone pattern through the next three chords.": (3, ""),
        }
        for q, (length, rel) in cases.items():
            i = self.parse(q)
            self.assertEqual((i.scope, i.engine_route, i.vocabulary), ("span", ROUTE_BRIDGE, "guide_tones"), q)
            self.assertEqual((i.span_length, i.span_relationship), (length, rel), q)
            self.assertTrue(is_exercise_request(q), q)
            self.assertEqual(i.span_unsupported, "", q)

    def test_relationship_words_set_the_length(self) -> None:
        self.assertEqual((self.parse("Give me a guide-tone line over this ii-V").span_length, self.parse("Give me a guide-tone line over this ii-V").span_relationship), (2, "ii_V"))
        self.assertEqual(self.parse("Give me a guide tone line over the ii–V–I in G").span_length, 3)
        self.assertEqual(self.parse("Give me a guide-tone line over the 2-5-1").span_relationship, "ii_V_I")

    def test_single_chord_guide_tone_requests_are_unchanged(self) -> None:
        for q in ("Give me a guide-tone pattern over E7.", "Give me a guide-tone pattern", "Give me a guide-tone pattern over the chorus",
                  "Give me a chord-tone exercise in A minor.", "Give me a blues lick over this chord."):
            i = self.parse(q)
            self.assertNotEqual(i.scope, "span", q)
            self.assertEqual(i.span_length, 0, q)
            self.assertEqual(i.engine_route, ROUTE_BRIDGE, q)

    def test_generic_voice_leading_talk_is_not_an_exercise_request(self) -> None:
        for q in ("Explain voice leading to me", "Show me voice leading", "What are guide tones?"):
            self.assertFalse(is_exercise_request(q), q)
            self.assertEqual(self.parse(q).scope, "single_chord", q)

    def test_stage_1_vocabularies_over_a_span_route_to_the_span_bridge(self) -> None:
        for q in ("Give me a pentatonic lick over the next two chords", "Give me a pentatonic line over this ii-V-I"):
            i = self.parse(q)
            self.assertEqual((i.scope, i.engine_route), ("span", ROUTE_BRIDGE), q)
            self.assertEqual(i.span_unsupported, "", q)
        self.assertEqual(self.parse("Give me a pentatonic line over the changes").scope, "span")

    def test_generic_patterns_still_use_the_legacy_generators(self) -> None:
        self.assertEqual(self.parse("Give me an A minor pentatonic pattern.").engine_route, ROUTE_LEGACY)


class TestSpanExerciseGeneration(unittest.TestCase):
    def test_a_two_chord_request_builds_exactly_two_chords(self) -> None:
        resp, _ = ask("Give me a guide-tone exercise over the next two chords.")
        ex = exercise_of(resp)
        self.assertEqual(ex.chords, ["Bm7b5", "E7"])
        self.assertEqual(sorted(set(ex.chord_assignment)), [0, 1])
        self.assertEqual(ex.context.span["length"], 2)
        self.assertTrue(ex.validation["ok"], ex.validation)

    def test_a_three_chord_request_builds_exactly_three_chords(self) -> None:
        resp, _ = ask("Give me a guide-tone pattern through the next three chords.")
        ex = exercise_of(resp)
        self.assertEqual(ex.chords, ["Bm7b5", "E7", "Am"])
        self.assertEqual(sorted(set(ex.chord_assignment)), [0, 1, 2])
        self.assertEqual(ex.context.span["length"], 3)

    def test_ii_v_i_request_finds_the_ii_v_i(self) -> None:
        resp, _ = ask("Show me voice leading through this ii–V–I.")
        ex = exercise_of(resp)
        self.assertEqual((ex.chords, ex.context.span["relationship"], ex.context.span["selection_source"]),
                         (["Bm7b5", "E7", "Am"], "ii_V_I", "relationship_match"))

    def test_unnumbered_request_says_how_long_it_made_it(self) -> None:
        resp, _ = ask("Connect the thirds and sevenths.")
        ex = exercise_of(resp)
        self.assertEqual(ex.context.span["length_source"], "default_two")
        self.assertIn("You didn't say how many chords", resp.direct_answer)

    def test_voice_leading_is_real_in_every_key(self) -> None:
        """Guide tone (3rd/7th) on beat 1 of every chord, and the arrival notes move by step or stay."""
        for key in PROGRESSIONS:
            for question in ("Give me a guide-tone exercise over the next two chords.",
                             "Give me a guide-tone pattern through the next three chords."):
                resp, _ = ask(question, key=key)
                ex = exercise_of(resp)
                self.assertIsNotNone(ex, (key, question))
                tl = ex.explanation_facts["mission_example"]["motif"]["chord_timeline"]
                arrivals = []
                for slot in tl:
                    first = slot["first_note"]
                    self.assertIn(ex.midi[first] % 12, guide_pcs(slot["chord"], key), (key, slot["chord"]))
                    arrivals.append(ex.midi[first])
                for a, b in zip(arrivals, arrivals[1:]):
                    self.assertLessEqual(abs(b - a), 2, (key, arrivals))
                self.assertEqual(ex.context.concert_key, key)
                self.assertEqual(ex.chords[0], PROGRESSIONS[key][0])

    def test_every_note_belongs_to_the_chord_it_is_assigned_to(self) -> None:
        resp, _ = ask("Give me a guide-tone pattern through the next three chords.")
        ex = exercise_of(resp)
        self.assertEqual(len(ex.chord_assignment), len(ex.notes))
        self.assertEqual(ex.chord_assignment, sorted(ex.chord_assignment))      # chords are played in order
        tl = ex.explanation_facts["mission_example"]["motif"]["chord_timeline"]
        for idx, slot in enumerate(tl):
            owned = [i for i, a in enumerate(ex.chord_assignment) if a == idx]
            self.assertEqual((owned[0], owned[-1]), (slot["first_note"], slot["last_note"]))
        self.assertEqual(len(ex.roles), len(ex.notes))
        self.assertTrue(ex.chord_roles[0] in ("3", "7"))                       # the first note is a guide tone

    def test_explanation_comes_from_the_engines_evidence(self) -> None:
        resp, _ = ask("Show me voice leading through this ii–V–I.")
        ex = exercise_of(resp)
        for item in ex.explanation_facts["evidence"]:
            if item["check"] == "guide tones voice-led":
                self.assertIn(item["text"].replace("♭", "b").replace("♯", "#"),
                              resp.direct_answer.replace("♭", "b").replace("♯", "#"))
        self.assertIn("Where it lands", resp.direct_answer)
        self.assertIn("Voice leading", resp.direct_answer)
        arrivals = ex.explanation_facts["arrivals"]
        self.assertEqual([a["chord"] for a in arrivals], ["Bm7b5", "E7", "Am"])

    def test_guitar_gets_tab_and_piano_does_not(self) -> None:
        guitar, _ = ask("Give me a guide-tone exercise over the next two chords.", instrument="Guitar")
        self.assertIn("```", guitar.direct_answer)
        self.assertIn("e|", guitar.direct_answer)
        self.assertTrue(guitar.diagnostics["guitar_tab_present"])
        piano, _ = ask("Give me a guide-tone exercise over the next two chords.", instrument="Piano")
        self.assertNotIn("```", piano.direct_answer)
        self.assertFalse(piano.diagnostics["guitar_tab_present"])

    def test_notation_has_the_chord_symbols_and_the_span_key(self) -> None:
        resp, _ = ask("Give me a guide-tone pattern through the next three chords.", key="Gm")
        abc = resp.notation_abc
        self.assertIn("K:Gm", abc)
        for chord in ("Am7b5", "D7", "Gm"):
            self.assertIn(f'"{chord}"', abc)

    def test_the_last_exercise_is_stored_as_the_canonical_object(self) -> None:
        resp, session = ask("Give me a guide-tone exercise over the next two chords.")
        stored = GeneratedExercise.from_dict(session[AMI_LAST_EXERCISE_KEY])
        self.assertEqual(stored.id, exercise_of(resp).id)
        self.assertEqual(stored.intent.scope, "span")

    def test_provenance_records_how_the_span_and_key_were_chosen(self) -> None:
        resp, _ = ask("Give me a guide-tone exercise over the next two chords.")
        ex = exercise_of(resp)
        prov = ex.provenance
        self.assertEqual((prov["engine"], prov["engine_function"], prov["mission_vocabulary"]),
                         ("mission_span_engine", "generate_mission_span_example", SPAN_MISSION_ID))
        self.assertEqual(prov["span_selection"]["selection_source"], "selected_chord_window")
        self.assertEqual(prov["span_selection"]["anchor_origin"], "section_first_chord")
        self.assertEqual((prov["key_source"], prov["concert_key"]), (ex.context.key_source, "Am"))
        json.dumps(resp.diagnostics["generated_exercise"], default=str)


class TestSpanLimitsAreStatedNotApproximated(unittest.TestCase):
    def test_transposing_instruments_are_refused_with_a_reason(self) -> None:
        resp, _ = ask(
            "Show me voice leading through this ii–V–I.",
            session=session_for(instrument="Clarinet", **{CHART_IN_INSTRUMENT_KEY_KEY: True,
                                                          SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Bb Clarinet"}))
        self.assertIsNone(exercise_of(resp))
        self.assertIn("transposed written key", resp.direct_answer)
        self.assertEqual(resp.diagnostics["exercise_context"]["instrument"], "Clarinet")   # "voice leading" is not the Voice instrument
        self.assertEqual(resp.notation_abc, "")
        self.assertTrue(resp.diagnostics["exercise_failed"])

    def test_unsupported_blues_span_is_not_silently_substituted(self) -> None:
        resp, _ = ask("Give me a blues lick over the next two chords")
        self.assertIn("blues exercises across several chords", resp.direct_answer)
        self.assertEqual(resp.notation_abc, "")
        self.assertIsNone(exercise_of(resp))

    def test_a_span_that_does_not_exist_is_explained(self) -> None:
        session = session_for()
        session["home_sections"] = {"Verse 1": ["Am", "Am", "Am", "Am"]}
        resp, _ = ask("Show me voice leading through this ii–V–I.", session=session)
        self.assertIn("couldn't find a ii–V–I", resp.direct_answer)
        self.assertIsNone(exercise_of(resp))

    def test_no_song_chords_is_explained(self) -> None:
        session = session_for()
        session["home_sections"] = {}
        resp, _ = ask("Give me a guide-tone exercise over the next two chords.", session=session)
        self.assertIsNone(exercise_of(resp))
        self.assertTrue(resp.diagnostics.get("exercise_failed") or "chords" in resp.direct_answer)

    def test_a_named_key_that_is_not_the_practice_key_is_not_silently_ignored(self) -> None:
        resp, _ = ask("Give me a guide-tone exercise over the next two chords in Gm.")
        self.assertIsNone(exercise_of(resp))
        self.assertIn("Practice Key", resp.direct_answer)

    def test_followups_on_a_span_exercise_say_they_are_not_available(self) -> None:
        resp, session = ask("Give me a guide-tone exercise over the next two chords.")
        before = copy.deepcopy(session[AMI_LAST_EXERCISE_KEY])
        again, _ = ask("Make it easier.", session=session)
        self.assertIn("can't change a multi-chord exercise yet", again.direct_answer)
        self.assertEqual(session[AMI_LAST_EXERCISE_KEY], before)                 # the exercise is unchanged

    def test_single_chord_exercises_and_their_followups_are_unaffected(self) -> None:
        resp, session = ask("Give me a guide-tone pattern over E7.")
        ex = exercise_of(resp)
        self.assertEqual((ex.chord, ex.intent.scope, len(ex.chords)), ("E7", "single_chord", 1))
        again, _ = ask("Make it easier.", session=session)
        self.assertNotIn("can't change a multi-chord exercise", again.direct_answer)


class TestSpanAuthority(unittest.TestCase):
    def test_the_missions_span_selection_wins_when_a_mission_is_engaged(self) -> None:
        from improvisation_intelligence_ui import _mission_improv_ctx_from_session, resolve_span_options
        from improvisation_motif import resolve_improv_section_rows

        session = session_for(studio_page="creative", improv_intelligence_tab="Missions")
        probe = dict(session)
        ictx = _mission_improv_ctx_from_session(probe)
        opts = resolve_span_options(probe, ictx, resolve_improv_section_rows(probe, ictx), scope="span2", level="Intermediate")
        later = next(s for s in opts.ordered if s.chords[0] == "Dm7")
        session["_improv_mission_span_selection"] = {"progression_key": opts.progression_key, "span2": later.span_id}
        session["improv_active_mission"] = SPAN_MISSION_ID
        session["improv_span_mission"] = {"example": {"mission_id": SPAN_MISSION_ID}, "history": []}   # deliberate engagement
        resp, _ = ask("Give me a guide-tone exercise over the next two chords.", session=session)
        ex = exercise_of(resp)
        self.assertEqual((ex.chords, ex.context.span["selection_source"]), (["Dm7", "G7"], "mission_span_selection"))
        self.assertTrue(ex.context.mission_active)

    def test_a_stale_mission_selection_is_ignored_when_no_mission_is_engaged(self) -> None:
        session = session_for(studio_page="practice")
        session["_improv_mission_span_selection"] = {"progression_key": "x", "span2": "x"}
        resp, _ = ask("Give me a guide-tone exercise over the next two chords.", session=session)
        ex = exercise_of(resp)
        self.assertEqual((ex.chords, ex.context.span["selection_source"]), (["Bm7b5", "E7"], "selected_chord_window"))

    def test_resolving_the_span_does_not_write_to_the_session(self) -> None:
        """A span request writes exactly what any AMI exercise request writes — never Mission/Missions state."""
        single = session_for()
        before_single = set(single)
        ask("Give me a guide-tone pattern over E7.", session=single)
        baseline = set(single) - before_single
        session = session_for()
        keys_before = set(session)
        ask("Give me a guide-tone exercise over the next two chords.", session=session)
        self.assertEqual(set(session) - keys_before, baseline)
        for k in ("improv_span_mission", "_improv_mission_span_selection", "improv_intelligence_tab", "studio_page",
                  "_improv_mission_target_scope_choice", "creative_improv_intelligence_tab"):
            self.assertEqual(session.get(k), session_for().get(k), k)

    def test_duplicate_sends_do_not_change_the_exercise(self) -> None:
        q = "Give me a guide-tone pattern through the next three chords."
        a, session = ask(q)
        b, _ = ask(q, session=session)
        self.assertEqual(exercise_of(a).id, exercise_of(b).id)


class TestOpenInMissions(unittest.TestCase):
    def action(self, question="Give me a guide-tone pattern through the next three chords.", **kw):
        resp, session = ask(question, **kw)
        return resp.diagnostics["open_in_missions"], session

    def test_the_card_carries_the_exact_example(self) -> None:
        resp, _ = ask("Give me a guide-tone exercise over the next two chords.")
        action = resp.diagnostics["open_in_missions"]
        self.assertEqual(action["label"], "Open in Missions")
        ex = exercise_of(resp)
        self.assertEqual(action["example"]["motif"]["midi"], ex.midi)
        self.assertEqual(action["example"]["motif"]["notes"], ex.notes)
        json.dumps(action)                                                        # survives persistence with the card

    def test_open_stages_the_same_example_without_regenerating(self) -> None:
        action, session = self.action()
        before = copy.deepcopy(action["example"])
        result = open_exercise_in_missions(session, action)
        self.assertTrue(result["ok"], result)
        state = session["improv_span_mission"]
        self.assertEqual(state["example"], before)                                # byte-for-byte the AMI example
        self.assertEqual(session["_improv_mission_target_scope_choice"], "span3")
        self.assertEqual(session["_improv_mission_ami_span_pick"],
                         {"scope": "span3", "chords": ["Bm7b5", "E7", "Am"], "section": "Verse 1", "start_event": 0})
        self.assertEqual(session["_improv_span_mission_choice"], SPAN_MISSION_ID)
        self.assertEqual(session["improv_intelligence_tab"], "Missions")
        self.assertEqual(session["studio_page"], "creative")
        self.assertEqual(state["example"]["handoff"]["practice_key"], "Am")

    def test_the_missions_page_adopts_the_example_whatever_its_own_style_says(self) -> None:
        action, session = self.action()
        open_exercise_in_missions(session, action)
        from mission_span_ui import span_mission_context

        state = session["improv_span_mission"]
        page_context = span_mission_context(SPAN_MISSION_ID, action["span_id"], "Intermediate", "Shape", "jazz")
        self.assertNotEqual(state["context"], page_context)                       # the page would have reset it ...
        handoff = state["ami_handoff"]
        self.assertEqual((handoff["mission_id"], handoff["chords"], handoff["section"]),
                         (SPAN_MISSION_ID, ["Bm7b5", "E7", "Am"], "Verse 1"))                    # ... but adopts it

    def test_open_is_refused_when_the_song_changed(self) -> None:
        action, session = self.action()
        session["home_sections"] = {"Verse 1": ["C", "F", "G", "C"]}
        result = open_exercise_in_missions(session, action)
        self.assertFalse(result["ok"])
        self.assertIn("progression has changed", result["message"])
        self.assertNotIn("improv_span_mission", session)

    def test_repeated_opens_do_not_regenerate_or_pile_up_state(self) -> None:
        action, session = self.action()
        for _ in range(3):
            self.assertTrue(open_exercise_in_missions(session, action)["ok"])
            self.assertEqual(session["improv_span_mission"]["example"]["handoff"]["example_id"], action["example"]["handoff"]["example_id"])
        self.assertEqual(len(session["improv_span_mission"]["history"]), 1)

    def test_an_example_that_cannot_be_opened_says_so(self) -> None:
        self.assertFalse(open_exercise_in_missions({}, {"kind": "span_guide_tones"})["ok"])

    def test_guitar_tab_follows_live_key_after_creative_snapshot_return(self) -> None:
        """AMI span -> Backing key up -> Mission return derives staff and TAB from the same live pitches."""
        from harmonic_span_analyzer import analyze_harmonic_spans
        from improvisation_motif import (
            build_motif_abc,
            build_motif_guitar_tab,
            midi_from_guitar_position,
            motif_guitar_tab_placements,
        )
        from mission_span_ui import span_example_projection
        from studio_page_persistence import apply_page_snapshot, capture_page_snapshot
        from tests.abc_pitch_decoder import decode_abc_midis

        action, session = self.action(instrument="Guitar")
        self.assertTrue(open_exercise_in_missions(session, action)["ok"])
        original = copy.deepcopy(session["improv_span_mission"]["example"])
        original_tab = build_motif_guitar_tab(original["motif"])
        snapshot = capture_page_snapshot(session, "creative")
        self.assertEqual(snapshot["improv_span_mission"]["example"], original)

        # Return at a Practice Key two semitones higher. Global key authority is
        # deliberately live and therefore is not overwritten by the page snapshot.
        returned = session_for("Am", instrument="Guitar")
        returned.update({"concert_key": "Bm", "display_key": "Bm"})
        apply_page_snapshot(returned, snapshot)
        restored = returned["improv_span_mission"]["example"]
        self.assertEqual(restored, original)  # exact generated example, never regenerated/transposed in storage
        rows = [("Verse 1", ["C#m7b5", "F#7", "Bm"], ["C#m7b5", "F#7", "Bm"])]
        moved_span = analyze_harmonic_spans(rows, key_center="Bm", length=3, source_id="returned")[0]
        shown, _chords, abc_key, reread = span_example_projection(
            restored, moved_span, concert_key="Bm", chart_key="Bm", project=lambda chord: chord,
        )
        self.assertTrue(reread)
        self.assertEqual([b - a for a, b in zip(original["motif"]["midi"], shown["midi"])], [2] * len(shown["midi"]))
        self.assertEqual(decode_abc_midis(build_motif_abc(shown, key_center=abc_key)), shown["midi"])
        returned_tab = build_motif_guitar_tab(shown)
        self.assertNotEqual(returned_tab, original_tab)
        sounded = [midi_from_guitar_position(string, fret) for string, fret in motif_guitar_tab_placements(shown)]
        self.assertEqual(sounded, shown["midi"])  # TAB and staff are the same authoritative pitches

    def test_span_backing_return_uses_the_span_mission_identity(self) -> None:
        """A fresh AMI span must not depend on absent/stale single-chord Mission state."""
        from mission_span_ui import start_span_mission_backing
        from unittest import mock

        action, session = self.action(instrument="Guitar")
        self.assertTrue(open_exercise_in_missions(session, action)["ok"])
        example = session["improv_span_mission"]["example"]
        session.pop("improv_mission_pick", None)
        session.pop("improv_active_mission", None)
        with mock.patch("music_workflow_mission_backing_click.capture_mission_backing_click_intent") as capture:
            start_span_mission_backing(
                session, example=example, heading="ii-V-I", section_label="Verse 1", practice_key="Am",
                with_practice_lick=True, instrument="Guitar", level="Intermediate", style="jazz", focus="",
                bpm=100, relationship_label="ii_V_I",
            )
        self.assertEqual(capture.call_args.kwargs["mission"], example["mission_label"])
        from mission_return_destination import peek_mission_return_destination

        destination = peek_mission_return_destination(session)
        self.assertIsNotNone(destination)
        self.assertEqual(destination["mission_id"], example["mission_label"])
        self.assertEqual(destination["backing_scope"], "mission_span")
        from mission_owner_contract import stamp_mission_backing_handoff

        stamp_mission_backing_handoff(session, concert_practice_key="Am")
        self.assertEqual(peek_mission_return_destination(session), destination)
        from backing_practice_key_control import OWNER_MISSION, commit_backing_practice_key

        with mock.patch("backing_practice_key_control.resolve_backing_pk_control_owner", return_value=OWNER_MISSION):
            commit_backing_practice_key(session, "Bm")
        moved_destination = peek_mission_return_destination(session)
        self.assertEqual((moved_destination["concert_key"], moved_destination["display_key"]), ("Bm", "Bm"))

        # A repeated Backing journey may retain the prior launch token. The
        # rendered Mission BackingContext is authoritative when return is queued.
        from mission_owner_contract import HANDOFF_PRACTICE_KEY
        from music_workflow_pending_mission_return import queue_pending_mission_return_from_backing

        session[HANDOFF_PRACTICE_KEY] = "Am"
        pending = queue_pending_mission_return_from_backing(session)
        self.assertIsNotNone(pending)
        self.assertEqual(
            (pending["return_destination"]["concert_key"], pending["return_destination"]["display_key"]),
            ("Bm", "Bm"),
        )
        self.assertEqual(session[HANDOFF_PRACTICE_KEY], "Bm")
        from music_workflow_pending_mission_return import _apply_return_destination_session_fields
        from songs.practice_key_state import set_practice_concert_key

        pick = str(pending["return_destination"].get("song_pick_key") or "")
        if pick:
            set_practice_concert_key(session, "C#m", pick_key=pick, allow_restore_original=True)
        _apply_return_destination_session_fields(session, pending["return_destination"])
        self.assertEqual(session["improv_mission_concert_key"], "Bm")

    def test_guitar_tab_stays_synchronized_through_down_up_and_repeated_key_changes(self) -> None:
        from harmonic_span_analyzer import analyze_harmonic_spans
        from improvisation_motif import midi_from_guitar_position, motif_guitar_tab_placements
        from mission_span_ui import span_example_projection

        action, session = self.action(instrument="Guitar")
        self.assertTrue(open_exercise_in_missions(session, action)["ok"])
        example = session["improv_span_mission"]["example"]
        cases = (
            ("Gm", ["Am7b5", "D7", "Gm"], -2),
            ("Bm", ["C#m7b5", "F#7", "Bm"], 2),
            ("Em", ["F#m7b5", "B7", "Em"], -5),
            ("Am", ["Bm7b5", "E7", "Am"], 0),
        )
        for live_key, live_chords, expected_shift in cases:
            rows = [("Verse 1", live_chords, live_chords)]
            live_span = analyze_harmonic_spans(rows, key_center=live_key, length=3, source_id=live_key)[0]
            shown, _chords, _abc_key, _reread = span_example_projection(
                example, live_span, concert_key=live_key, chart_key=live_key, project=lambda chord: chord,
            )
            # Register normalization may octave-lift a downward move to keep the
            # whole phrase playable; the requested key interval remains exact.
            self.assertEqual(
                [(b - a) % 12 for a, b in zip(example["motif"]["midi"], shown["midi"])],
                [expected_shift % 12] * len(shown["midi"]),
            )
            sounded = [midi_from_guitar_position(string, fret) for string, fret in motif_guitar_tab_placements(shown)]
            self.assertEqual(sounded, shown["midi"], live_key)


class TestPickerRefactorKeepsBehaviour(unittest.TestCase):
    def test_resolve_span_options_matches_the_pickers_inputs(self) -> None:
        from improvisation_intelligence_ui import _mission_improv_ctx_from_session, resolve_span_options
        from improvisation_motif import resolve_improv_section_rows

        session = session_for("Gm", studio_page="creative", improv_intelligence_tab="Missions")
        ictx = _mission_improv_ctx_from_session(session)
        opts2 = resolve_span_options(session, ictx, resolve_improv_section_rows(session, ictx), scope="span2", level="Intermediate")
        opts3 = resolve_span_options(session, ictx, resolve_improv_section_rows(session, ictx), scope="span3", level="Intermediate")
        self.assertEqual(opts2.concert_key, "Gm")
        self.assertEqual([s.chords for s in opts2.ordered][:2], [("Am7b5", "D7"), ("D7", "Gm")])
        self.assertEqual(opts3.ordered[0].relationship, "ii_V_I")
        self.assertTrue(all(len(s.chords) == 3 for s in opts3.ordered))
        # span ids are what the Missions page stores and finds again
        self.assertEqual(len({s.span_id for s in opts2.spans}), len(opts2.spans))


if __name__ == "__main__":
    unittest.main()

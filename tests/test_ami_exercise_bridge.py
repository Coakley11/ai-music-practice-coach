"""AMI Slice 1: structured exercise intent, active context, canonical GeneratedExercise and the Mission bridge."""

from __future__ import annotations

import json
import unittest

from instrument_transposition import CHART_IN_INSTRUMENT_KEY_KEY, SELECTED_TRANSPOSING_INSTRUMENT_KEY
from music_coach_ami.exercise_bridge import AMI_LAST_EXERCISE_KEY, ENGINE_NAME
from music_coach_ami.exercise_intent import is_exercise_request, parse_exercise_intent
from music_coach_ami.exercise_model import ROUTE_BRIDGE, ROUTE_LEGACY
from music_coach_ami.musical_idea_request import resolve_musical_idea_request
from music_coach_ami.pipeline import run_coach_submit

MISSION_SESSION = {
    "studio_page": "creative",
    "improv_intelligence_tab": "Missions",
    "improv_active_mission": "Improvise using only chord tones",
    "ii_selected_chord": "Dm7",
    "ii_selected_section": "Verse 1",
    # a Mission example generated for the open Mission: the deliberate action that engages it
    "improv_mission_example": {"mission": "Improvise using only chord tones", "chord": "Dm7"},
}


def _pcs(notes):
    from improvisation_motif import _midi_from_note

    return [_midi_from_note(n, 4) % 12 for n in notes]


def submit(question, *, instrument="Piano", key="Am", level="Intermediate", extra_session=None, ami=None):
    session = {"instrument": instrument, "level": level, "display_key": key, "concert_key": key}
    session.update(extra_session or {})
    req, resp = run_coach_submit(question, session, ami_ctx=ami or {})
    return req, resp, session


def exercise_of(resp):
    return (resp.diagnostics or {}).get("generated_exercise")


class TestParserRouting(unittest.TestCase):
    def route(self, q):
        idea = resolve_musical_idea_request(q, default_object="lick", level="Intermediate")
        return parse_exercise_intent(q, idea)

    def test_generic_degree_patterns_stay_on_the_ami_generators(self) -> None:
        for q in (
            "Give me an A minor pentatonic pattern.",
            "Give me a blues pattern",
            "Give me a pentatonic pattern in thirds",
            "Show me a sequence in A minor pentatonic",
            "Give me a left hand blues lick",
            "Give me a minor pentatonic lick over the chorus",
            "Give me a lick in A minor",
        ):
            self.assertEqual(self.route(q).engine_route, ROUTE_LEGACY, q)

    def test_phrase_and_mission_vocabulary_go_to_the_bridge(self) -> None:
        for q in (
            "Give me an A minor pentatonic line.",
            "Give me a pentatonic lick",
            "Give me a pentatonic exercise over this chord",
            "Give me a guide-tone pattern",
            "Give me a chord-tone exercise in A minor.",
            "Give me a C major blues line using the flat 3rd and major 3rd.",
            "Give me a blues pattern using the flat 3rd and major 3rd",
            "Give me a guide-tone pattern over E7.",
            "Give me a guide-tone pattern over the chorus",
        ):
            self.assertEqual(self.route(q).engine_route, ROUTE_BRIDGE, q)

    def test_the_word_pattern_alone_is_not_routing_evidence(self) -> None:
        self.assertEqual(self.route("Give me a pentatonic pattern").engine_route, ROUTE_LEGACY)
        self.assertEqual(self.route("Give me a pentatonic pattern over this chord").engine_route, ROUTE_BRIDGE)
        self.assertEqual(self.route("Give me a guide-tone pattern").engine_route, ROUTE_BRIDGE)

    def test_exercise_requests_are_recognised_by_the_router_helper(self) -> None:
        self.assertTrue(is_exercise_request("Give me an A minor pentatonic line"))
        self.assertTrue(is_exercise_request("give me a guide-tone exercise"))
        self.assertFalse(is_exercise_request("Give me an exercise for tone"))
        self.assertFalse(is_exercise_request("What is a pentatonic scale"))

    def test_explicit_fields_record_what_the_user_said(self) -> None:
        i = self.route("Give me a C major blues line using the flat 3rd and major 3rd, advanced, 4 bars")
        self.assertEqual(i.collection, "major blues")
        self.assertTrue(i.both_thirds)
        self.assertEqual(i.explicit_key, "C")
        self.assertEqual(i.level_override, "Advanced")
        self.assertEqual(i.length_bars, 4)
        for k in ("vocabulary", "collection", "both_thirds", "key", "level", "length_bars", "form"):
            self.assertEqual(i.explicit_fields.get(k), "user", k)
        j = self.route("Give me a blues line")
        self.assertNotIn("key", j.explicit_fields)
        self.assertNotIn("length_bars", j.explicit_fields)       # the resolver's default length is not the user's
        k = self.route("Give me a chord-tone exercise in a minor")
        self.assertEqual(k.explicit_key, "Am")

    def test_articulation_and_dynamics_are_only_recorded(self) -> None:
        i = self.route("Give me an A blues line, staccato with a crescendo")
        self.assertEqual(i.articulation_request, "staccato")
        self.assertEqual(i.dynamics_request, "crescendo")


class TestBridgeEndToEnd(unittest.TestCase):
    def test_a_minor_pentatonic_line_is_pentatonic_and_canonical(self) -> None:
        req, resp, _s = submit("Give me an A minor pentatonic line.")
        self.assertTrue(resp.diagnostics["exercise_bridge"])
        ex = exercise_of(resp)
        self.assertEqual(ex["engine"], ENGINE_NAME)
        self.assertEqual(ex["collection_label"], "A minor pentatonic")
        self.assertEqual(ex["collection_notes"], ["A", "C", "D", "E", "G"])
        self.assertTrue(set(_pcs(ex["notes"])) <= {9, 0, 2, 4, 7})
        self.assertTrue(ex["validation"]["ok"], ex["validation"])
        n = len(ex["notes"])
        self.assertGreater(n, 0)
        for field in ("midi", "roles", "chord_roles", "chord_assignment", "articulation", "dynamics"):
            self.assertEqual(len(ex[field]), n, field)
        self.assertEqual(ex["articulation"], [""] * n)            # placeholders only in Slice 1
        self.assertEqual(ex["dynamics"], [""] * n)
        self.assertTrue(ex["rhythm_events"] or ex["rhythm_symbols"])
        self.assertTrue(resp.notation_abc.startswith("X:1"))
        json.dumps(ex)                                            # canonical object is plain data

    def test_c_major_pentatonic_membership(self) -> None:
        _r, resp, _s = submit("Give me a C major pentatonic line.")
        ex = exercise_of(resp)
        self.assertEqual(ex["collection_notes"], ["C", "D", "E", "G", "A"])
        self.assertTrue(set(_pcs(ex["notes"])) <= {0, 2, 4, 7, 9})

    def test_major_blues_keeps_flat_and_natural_third_as_different_degrees(self) -> None:
        _r, resp, _s = submit("Give me a C major blues line using the flat 3rd and major 3rd.")
        ex = exercise_of(resp)
        self.assertEqual(ex["provenance"]["relationship"], "root_major_blues")
        self.assertEqual(ex["collection_notes"], ["C", "D", "Eb", "E", "G", "A"])
        notes = ex["notes"]
        self.assertIn("Eb", notes)
        self.assertIn("E", notes)
        self.assertEqual({r for n, r in zip(notes, ex["roles"]) if n == "Eb"}, {"b3"})
        self.assertEqual({r for n, r in zip(notes, ex["roles"]) if n == "E"}, {"3"})
        self.assertTrue(ex["explanation_facts"]["both_thirds_present"])
        self.assertTrue(any(c["name"] == "both_thirds" and c["ok"] for c in ex["validation"]["checks"]))
        self.assertIn("natural 3", resp.direct_answer)

    def test_minor_blues_has_the_flat_third_and_no_natural_third(self) -> None:
        _r, resp, _s = submit("Give me an A minor blues line.")
        ex = exercise_of(resp)
        self.assertEqual(ex["provenance"]["relationship"], "root_minor_blues")
        self.assertEqual(ex["collection_notes"], ["A", "C", "D", "Eb", "E", "G"])
        self.assertNotIn(1, set(_pcs(ex["notes"])))               # no C#
        self.assertEqual(ex["explanation_facts"]["natural_third"], "")
        self.assertIn("Eb", ex["collection_notes"])

    def test_both_thirds_over_a_minor_blues_chord_is_refused_not_silently_changed(self) -> None:
        _r, resp, _s = submit("Give me a blues line using the flat 3rd and major 3rd over A7")
        diag = resp.diagnostics
        self.assertTrue(diag.get("exercise_failed"))
        self.assertIn("natural 3rd", diag["exercise_failure_reason"])
        self.assertEqual(resp.notation_abc, "")

    def test_chord_tone_exercise_uses_only_chord_tones(self) -> None:
        _r, resp, _s = submit("Give me a chord-tone exercise in A minor.")
        ex = exercise_of(resp)
        self.assertEqual(ex["chord"], "Am7")
        self.assertTrue(set(_pcs(ex["notes"])) <= {9, 0, 4, 7})
        self.assertTrue(all(ex["chord_roles"]))
        self.assertTrue(ex["validation"]["ok"])

    def test_guide_tone_pattern_over_a_named_chord(self) -> None:
        _r, resp, _s = submit("Give me a guide-tone pattern over E7.")
        ex = exercise_of(resp)
        self.assertEqual(ex["chord"], "E7")
        self.assertTrue(set(_pcs(ex["notes"])) <= {8, 2})         # G# (3rd) and D (7th)
        self.assertEqual(set(ex["roles"]) - {"3", "b7"}, set())
        self.assertEqual(ex["explanation_facts"]["collection_notes"], ["G#", "D"])
        self.assertEqual(ex["provenance"]["chord_source"], "explicit_request")

    def test_the_same_request_is_deterministic(self) -> None:
        a = exercise_of(submit("Give me an A minor pentatonic line.")[1])
        b = exercise_of(submit("Give me an A minor pentatonic line.")[1])
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(a["notes"], b["notes"])

    def test_level_changes_the_engine_input(self) -> None:
        ex = exercise_of(submit("Give me an A minor pentatonic line.", level="Beginner")[1])
        self.assertEqual(ex["context"]["level"], "Beginner")
        self.assertEqual(ex["context"]["level_source"], "context")
        ex2 = exercise_of(submit("Give me an advanced A minor pentatonic line.", level="Beginner")[1])
        self.assertEqual(ex2["context"]["level"], "Advanced")
        self.assertEqual(ex2["context"]["level_source"], "explicit_request")

    def test_articulation_request_is_reported_as_not_applied(self) -> None:
        _r, resp, _s = submit("Give me an A minor pentatonic line, staccato")
        ex = exercise_of(resp)
        self.assertEqual(ex["intent"]["articulation_request"], "staccato")
        self.assertEqual(ex["articulation"], [""] * len(ex["notes"]))
        self.assertIn("aren't applied", resp.direct_answer)


class TestKeyAuthority(unittest.TestCase):
    def test_mission_practice_key_wins_in_an_active_mission_context(self) -> None:
        ami = {"display_key": "Am", "active_song": {"title": "Autumn Leaves", "key": "Bm"}}
        _r, resp, _s = submit("Give me a guide-tone pattern.", key="Dm", extra_session=MISSION_SESSION, ami=ami)
        ctx = exercise_of(resp)["context"]
        self.assertEqual(ctx["concert_key"], "Dm")
        self.assertEqual(ctx["key_source"], "mission_practice_key")
        self.assertTrue(ctx["mission_active"])
        self.assertEqual(ctx["selected_chord"], "Dm7")
        self.assertEqual(exercise_of(resp)["chord"], "Dm7")
        self.assertEqual(ctx["key_candidates"].get("catalog_original_key"), "Bm")   # recorded, never used
        self.assertNotEqual(ctx["concert_key"], "Bm")

    def test_normal_practice_key_outside_a_mission(self) -> None:
        ami = {"active_song": {"title": "Autumn Leaves", "key": "Bm"}}
        _r, resp, _s = submit("Give me a chord-tone exercise.", key="Am", ami=ami)
        ctx = exercise_of(resp)["context"]
        self.assertEqual(ctx["concert_key"], "Am")
        self.assertEqual(ctx["key_source"], "practice_chart_key")
        self.assertFalse(ctx["mission_active"])
        self.assertEqual(ctx["field_sources"]["chord"], "tonic_of_key")

    def test_an_explicit_key_beats_the_mission_key(self) -> None:
        _r, resp, _s = submit("Give me an A minor pentatonic line.", key="Dm", extra_session=MISSION_SESSION)
        ctx = exercise_of(resp)["context"]
        self.assertEqual(ctx["concert_key"], "Am")
        self.assertEqual(ctx["key_source"], "explicit_request")
        self.assertEqual(ctx["key_candidates"].get("mission_practice_key"), "Dm")
        self.assertEqual(exercise_of(resp)["chord"], "Am7")

    def test_the_mission_chord_is_used_when_nothing_is_named(self) -> None:
        _r, resp, _s = submit("Give me a pentatonic lick", key="Dm", extra_session=MISSION_SESSION)
        ex = exercise_of(resp)
        self.assertEqual(ex["chord"], "Dm7")
        self.assertEqual(ex["context"]["chord_source"], "mission_selected_chord")


class TestWrittenKeyProjection(unittest.TestCase):
    def _transposing(self, subtype):
        return {CHART_IN_INSTRUMENT_KEY_KEY: True, SELECTED_TRANSPOSING_INSTRUMENT_KEY: subtype}

    def test_generation_is_concert_first_and_written_is_derived(self) -> None:
        concert = exercise_of(submit("Give me an A minor pentatonic line.")[1])
        for inst, subtype, steps, key in (
            ("Clarinet", "Bb Clarinet", 2, "Bm"),
            ("Saxophone", "Tenor saxophone (Bb)", 2, "Bm"),
            ("Saxophone", "Alto saxophone (Eb)", 9, "F#m"),
        ):
            _r, resp, _s = submit("Give me an A minor pentatonic line.", instrument=inst, extra_session=self._transposing(subtype))
            ex = exercise_of(resp)
            self.assertEqual(ex["notes"], concert["notes"], inst)           # concert notes identical
            self.assertEqual(ex["midi"], concert["midi"], inst)
            self.assertTrue(ex["written"]["applied"], inst)
            self.assertEqual(ex["written"]["key"], key, (inst, subtype))
            self.assertEqual(ex["written"]["semitones"], steps)
            self.assertEqual([m % 12 for m in ex["written"]["midi"]], [(m + steps) % 12 for m in ex["midi"]])
            self.assertEqual(_pcs(ex["written"]["notes"]), [m % 12 for m in ex["written"]["midi"]])
            self.assertIn(f"K:{key}", resp.notation_abc)

    def test_written_spelling_is_key_correct_for_blues(self) -> None:
        _r, resp, _s = submit(
            "Give me a C major blues line using the flat 3rd and major 3rd.",
            instrument="Clarinet", extra_session=self._transposing("Bb Clarinet"),
        )
        ex = exercise_of(resp)
        self.assertEqual(ex["written"]["key"], "D")
        self.assertEqual(ex["written"]["chord"], "D")
        # D major blues: D E F F# A B — flat third spelled F (not E#), natural third F#, never a sharp spelling of a flat.
        self.assertEqual(sorted(set(_pcs(ex["written"]["notes"])) - {2, 4, 5, 6, 9, 11}), [])
        self.assertTrue({"F", "F#"} <= set(ex["written"]["notes"]) or ex["explanation_facts"]["both_thirds_present"])
        self.assertFalse({"E#", "Fb", "Gb", "A#", "D#"} & set(ex["written"]["notes"]))
        concert_roles = ex["roles"]
        written_pairs = {(n, r) for n, r in zip(ex["written"]["notes"], concert_roles)}
        self.assertTrue({r for n, r in written_pairs if n == "F"} <= {"b3"})
        self.assertTrue({r for n, r in written_pairs if n == "F#"} <= {"3"})


class TestLegacyPathPreserved(unittest.TestCase):
    def test_generic_pentatonic_pattern_is_not_bridged(self) -> None:
        _r, resp, session = submit("Give me an A minor pentatonic pattern.")
        d = resp.diagnostics
        self.assertNotIn("exercise_bridge", d)
        self.assertTrue(d.get("musical_idea_content"))
        self.assertIn("Pentatonic", resp.notation_abc)
        self.assertNotIn(AMI_LAST_EXERCISE_KEY, session)

    def test_interval_patterns_sequences_and_piano_roles_are_not_bridged(self) -> None:
        for q in (
            "Give me a pentatonic pattern in thirds",
            "Give me a sequence in A minor",
            "Give me a left hand blues lick",
        ):
            _r, resp, session = submit(q)
            self.assertNotIn("exercise_bridge", resp.diagnostics, q)
            self.assertNotIn(AMI_LAST_EXERCISE_KEY, session, q)

    def test_section_relative_licks_are_not_bridged(self) -> None:
        ami = {"chart_sections": {"Chorus": ["Am7", "D7", "Gmaj7", "Cmaj7"]}, "chart_sections_key": "Am",
               "chart_sections_in_practice_key": True, "practice_focus_section": "Chorus"}
        _r, resp, session = submit("Give me a minor pentatonic lick over the chorus", ami=ami)
        self.assertNotIn("exercise_bridge", resp.diagnostics)
        self.assertNotIn(AMI_LAST_EXERCISE_KEY, session)


class TestLastExerciseIsolation(unittest.TestCase):
    def test_storing_the_last_exercise_does_not_touch_mission_state(self) -> None:
        sentinel = {"motif": {"notes": ["A", "C"], "midi": [57, 60]}, "mission": "Improvise using only chord tones", "chord": "Dm7"}
        extra = dict(MISSION_SESSION)
        extra["improv_mission_example"] = json.loads(json.dumps(sentinel))
        extra["improv_mission_concert_key"] = "Dm"
        _r, resp, session = submit("Give me a guide-tone pattern.", key="Dm", extra_session=extra)
        self.assertEqual(session["improv_mission_example"], sentinel)
        self.assertEqual(session["improv_mission_concert_key"], "Dm")
        for k, v in MISSION_SESSION.items():
            if k != "improv_mission_example":                       # replaced by the sentinel above
                self.assertEqual(session[k], v, k)
        stored = session[AMI_LAST_EXERCISE_KEY]
        self.assertEqual(stored["id"], exercise_of(resp)["id"])
        self.assertEqual(stored["context"]["key_source"], "mission_practice_key")
        written = [k for k in session if k not in extra and k not in {"instrument", "level", "display_key", "concert_key"}]
        self.assertIn(AMI_LAST_EXERCISE_KEY, written)
        self.assertFalse([k for k in written if k.startswith(("improv_", "ii_", "mission"))])


if __name__ == "__main__":
    unittest.main()

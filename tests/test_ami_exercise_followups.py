"""AMI Slice 2: follow-ups transform the last canonical GeneratedExercise (never rendered text)."""

from __future__ import annotations

import json
import unittest
from fractions import Fraction

from instrument_transposition import CHART_IN_INSTRUMENT_KEY_KEY, SELECTED_TRANSPOSING_INSTRUMENT_KEY
from mission_degree_shift import shift_midis_by_degree
from music_coach_ami.exercise_bridge import AMI_LAST_EXERCISE_KEY
from music_coach_ami.exercise_context import exercise_authority_signature
from music_coach_ami.exercise_followup import (
    KIND_EASIER,
    KIND_HARDER,
    KIND_MOVE,
    KIND_SAME_NOTES,
    KIND_SAME_RHYTHM,
    KIND_SEQUENCE,
    KIND_VARIATION,
    complexity,
    is_exercise_followup,
    last_exercise,
    parse_followup,
    rhythm_signature,
)
from music_coach_ami.pipeline import run_coach_submit

A_MINOR_PENT = {9, 0, 2, 4, 7}
C_MAJOR_BLUES = {0, 2, 3, 4, 7, 9}


def pcs(notes):
    from improvisation_motif import _midi_from_note

    return [_midi_from_note(n, 4) % 12 for n in notes]


class Conv:
    """A conversation: one session, several AMI questions."""

    def __init__(self, *, instrument="Piano", level="Intermediate", key="Am", **session):
        self.ss = {"instrument": instrument, "level": level, "display_key": key, "concert_key": key, **session}
        self.resp = None
        self.ex = None

    def ask(self, question, ami=None):
        _req, self.resp = run_coach_submit(question, self.ss, ami_ctx=ami or {})
        self.diag = (self.resp.diagnostics if self.resp else {}) or {}
        self.ex = self.diag.get("generated_exercise")
        return self.ex

    @property
    def failed(self):
        return bool(self.diag.get("exercise_followup_failed") or self.diag.get("exercise_failed"))

    @property
    def stored(self):
        return self.ss.get(AMI_LAST_EXERCISE_KEY)


class TestFollowUpParsing(unittest.TestCase):
    def kind(self, q):
        fu = parse_followup(q)
        return fu.kind if fu else None

    def test_recognised_follow_ups(self) -> None:
        table = {
            "Another one": KIND_VARIATION, "Give me another variation": KIND_VARIATION, "one more": KIND_VARIATION,
            "Make it easier": KIND_EASIER, "Give me a simpler version": KIND_EASIER,
            "Make it harder": KIND_HARDER, "Make it more advanced": KIND_HARDER,
            "Keep the rhythm but change the notes": KIND_SAME_RHYTHM, "Another one with the same rhythm": KIND_SAME_RHYTHM,
            "Keep the notes but change the rhythm": KIND_SAME_NOTES, "Give me the same idea in a different rhythm": KIND_SAME_NOTES,
            "Move it up": KIND_MOVE, "Move it down": KIND_MOVE, "Move it up one scale degree": KIND_MOVE,
            "Move it down one pentatonic degree": KIND_MOVE,
            "Sequence it upward": KIND_SEQUENCE, "Repeat the motif but start one degree higher": KIND_SEQUENCE,
        }
        for q, kind in table.items():
            self.assertEqual(self.kind(q), kind, q)

    def test_directions_degrees_and_words(self) -> None:
        up, down = parse_followup("Move it up"), parse_followup("Move it down one pentatonic degree")
        self.assertEqual((up.direction, up.degrees), (1, 1))
        self.assertEqual((down.direction, down.degrees, down.collection_word), (-1, 1, "pentatonic"))
        self.assertEqual(parse_followup("Move it up two degrees").degrees, 2)
        self.assertEqual(parse_followup("Sequence it downward").direction, -1)

    def test_explicit_overrides_are_parsed(self) -> None:
        fu = parse_followup("Make it harder in D minor")
        self.assertEqual((fu.kind, fu.explicit_key), (KIND_HARDER, "Dm"))
        self.assertEqual(parse_followup("Another one over E7").explicit_chord, "E7")
        self.assertTrue(parse_followup("Give me another one for the current chord").current_context)
        fu = parse_followup("Move it up but keep it staccato")
        self.assertEqual((fu.kind, fu.articulation_request), (KIND_MOVE, "staccato"))
        self.assertEqual(parse_followup("Another one at advanced level").level, "Advanced")

    def test_unrelated_utterances_are_not_follow_ups(self) -> None:
        for q in (
            "What should I practice today?", "How do I make it easier to play fast passages?",
            "Give me an A minor pentatonic line", "Give me another blues line", "Another song like this one please",
            "Make it to the bridge", "Why does a pentatonic scale sound good?", "Move the left hand to the bass clef",
        ):
            self.assertIsNone(parse_followup(q), q)
        self.assertFalse(is_exercise_followup("Give me a guide-tone pattern"))


class TestVariations(unittest.TestCase):
    def setUp(self) -> None:
        self.c = Conv()
        self.first = self.c.ask("Give me an A minor pentatonic line")

    def test_another_one_is_a_new_exercise_with_the_same_ingredients(self) -> None:
        a = self.c.ask("Another one")
        self.assertFalse(self.c.failed)
        self.assertNotEqual(a["midi"], self.first["midi"])
        self.assertEqual(a["parent_id"], self.first["id"])
        self.assertNotEqual(a["id"], self.first["id"])
        for k in ("vocabulary", "collection_label", "chord"):
            self.assertEqual(a[k], self.first[k], k)
        self.assertEqual(a["context"]["concert_key"], "Am")
        self.assertEqual(a["context"]["level"], self.first["context"]["level"])
        self.assertTrue(set(pcs(a["notes"])) <= A_MINOR_PENT)
        self.assertEqual(a["transform"]["kind"], KIND_VARIATION)
        self.assertEqual(self.c.stored["id"], a["id"])                       # the new one is now "the last exercise"

    def test_successive_variations_use_successive_nonces_and_never_replay(self) -> None:
        seen = {tuple(self.first["midi"])}
        nonces = []
        for _ in range(4):
            a = self.c.ask("Another one")
            self.assertNotIn(tuple(a["midi"]), {tuple(m) for m in [self.first["midi"]]})
            nonces.append(a["transform"]["nonce"])
            seen.add(tuple(a["midi"]))
        self.assertEqual(nonces, sorted(set(nonces)))
        self.assertGreaterEqual(len(seen), 3)

    def test_the_conversation_is_deterministic(self) -> None:
        other = Conv()
        other.ask("Give me an A minor pentatonic line")
        for q in ("Another one", "Make it harder", "Keep the rhythm but change the notes"):
            a, b = self.c.ask(q), other.ask(q)
            self.assertEqual((a["id"], a["midi"]), (b["id"], b["midi"]), q)

    def test_another_with_the_same_rhythm_keeps_the_rhythm(self) -> None:
        a = self.c.ask("Another one with the same rhythm")
        self.assertEqual(a["transform"]["kind"], KIND_SAME_RHYTHM)
        self.assertEqual(rhythm_signature_of(a), rhythm_signature_of(self.first))


def rhythm_signature_of(d):
    return {"events": [{k: e.get(k) for k in ("on", "dur", "rest", "tup")} for e in d["rhythm_events"]],
            "symbols": list(d["rhythm_symbols"]), "meter": d["meter"]}


class TestRhythmAndNotes(unittest.TestCase):
    def setUp(self) -> None:
        self.c = Conv()
        self.base = self.c.ask("Give me an A minor pentatonic line")

    def test_same_rhythm_new_notes_preserves_the_rhythm_structurally(self) -> None:
        a = self.c.ask("Keep the rhythm but change the notes")
        self.assertFalse(self.c.failed, self.diag_reason())
        self.assertEqual(a["rhythm_events"], self.base["rhythm_events"])           # event-for-event equal
        self.assertEqual(a["rhythm_symbols"], self.base["rhythm_symbols"])
        self.assertEqual((a["meter"], a["bars"]), (self.base["meter"], self.base["bars"]))
        self.assertNotEqual(a["midi"], self.base["midi"])
        self.assertEqual(len(a["notes"]), len(self.base["notes"]))
        self.assertTrue(set(pcs(a["notes"])) <= A_MINOR_PENT)
        self.assertTrue(a["validation"]["ok"])
        t = a["transform"]
        self.assertEqual(t["preserved"]["rhythm_sha1"], t["parent_fingerprints"]["rhythm_sha1"])
        self.assertNotEqual(t["preserved"]["notes_sha1"], t["parent_fingerprints"]["notes_sha1"])
        self.assertEqual((t["inherited"].count("rhythm"), t["changed"]), (1, ["notes"]))

    def test_same_notes_new_rhythm_preserves_the_pitch_sequence(self) -> None:
        a = self.c.ask("Keep the notes but change the rhythm")
        self.assertFalse(self.c.failed, self.diag_reason())
        self.assertEqual((a["notes"], a["midi"]), (self.base["notes"], self.base["midi"]))
        self.assertEqual(a["roles"], self.base["roles"])
        self.assertNotEqual(rhythm_signature_of(a), rhythm_signature_of(self.base))
        beats_bar = {"3/4": 3, "6/8": 3, "2/4": 2}.get(a["meter"], 4)
        end = max((Fraction(str(e["on"])) + Fraction(str(e["dur"])) for e in a["rhythm_events"]), default=Fraction(0))
        self.assertLessEqual(end, a["bars"] * beats_bar)                           # fits its bars
        ons = [Fraction(str(e["on"])) for e in a["rhythm_events"]]
        self.assertEqual(ons, sorted(ons))
        t = a["transform"]
        self.assertEqual(t["preserved"]["notes_sha1"], t["parent_fingerprints"]["notes_sha1"])
        self.assertNotEqual(t["preserved"]["rhythm_sha1"], t["parent_fingerprints"]["rhythm_sha1"])
        self.assertEqual(t["changed"], ["rhythm"])

    def test_a_same_notes_result_can_be_followed_by_same_rhythm_new_notes(self) -> None:
        b = self.c.ask("Keep the notes but change the rhythm")
        c = self.c.ask("Keep the rhythm but change the notes")
        self.assertEqual(c["rhythm_events"], b["rhythm_events"])
        self.assertNotEqual(c["midi"], b["midi"])
        self.assertEqual(c["parent_id"], b["id"])

    def diag_reason(self):
        return self.c.diag.get("exercise_followup_failure_reason")


class TestDifficulty(unittest.TestCase):
    def test_easier_and_harder_move_one_level_and_the_score_follows(self) -> None:
        c = Conv(level="Intermediate")
        base = c.ask("Give me an A minor pentatonic line")
        score0 = complexity(base["midi"], base["rhythm_events"], len(base["notes"]))
        easy = c.ask("Make it easier")
        self.assertEqual((easy["context"]["level"], easy["transform"]["level_from"], easy["transform"]["level_to"]),
                         ("Beginner", "Intermediate", "Beginner"))
        self.assertLess(complexity(easy["midi"], easy["rhythm_events"], len(easy["notes"])), score0)
        self.assertEqual(easy["vocabulary"], base["vocabulary"])
        self.assertEqual(easy["chord"], base["chord"])
        self.assertTrue(set(pcs(easy["notes"])) <= A_MINOR_PENT)
        hard = c.ask("Make it harder")
        hard2 = c.ask("Make it harder")
        self.assertEqual((hard["context"]["level"], hard2["context"]["level"]), ("Intermediate", "Advanced"))
        self.assertGreater(complexity(hard2["midi"], hard2["rhythm_events"], len(hard2["notes"])),
                           complexity(hard["midi"], hard["rhythm_events"], len(hard["notes"])))
        self.assertTrue(set(pcs(hard2["notes"])) <= A_MINOR_PENT)               # harder is still pentatonic
        self.assertEqual(hard2["provenance"]["relationship"], base["provenance"]["relationship"])
        self.assertEqual(hard2["transform"]["changed"], ["level", "notes", "rhythm"])

    def test_the_ends_of_the_scale_are_explained_and_nothing_changes(self) -> None:
        c = Conv(level="Beginner")
        base = c.ask("Give me an A minor pentatonic line")
        c.ask("Make it easier")
        self.assertTrue(c.failed)
        self.assertIn("easiest level", c.resp.direct_answer)
        self.assertEqual(c.stored["id"], base["id"])
        c2 = Conv(level="Advanced")
        top = c2.ask("Give me an A minor pentatonic line")
        c2.ask("Make it harder")
        self.assertTrue(c2.failed)
        self.assertIn("hardest level", c2.resp.direct_answer)
        self.assertEqual(c2.stored["id"], top["id"])


class TestMovement(unittest.TestCase):
    def test_pentatonic_up_then_down_restores_the_exact_exercise(self) -> None:
        c = Conv()
        base = c.ask("Give me an A minor pentatonic line")
        up = c.ask("Move it up")
        self.assertFalse(c.failed)
        self.assertEqual(up["midi"], shift_midis_by_degree(base["midi"], A_MINOR_PENT, +1))
        self.assertTrue(set(pcs(up["notes"])) <= A_MINOR_PENT)
        self.assertEqual(rhythm_signature_of(up), rhythm_signature_of(base))
        down = c.ask("Move it down")
        self.assertEqual((down["notes"], down["midi"]), (base["notes"], base["midi"]))
        self.assertEqual(rhythm_signature_of(down), rhythm_signature_of(base))
        self.assertEqual(down["roles"], base["roles"])
        self.assertEqual([down["parent_id"], up["parent_id"]], [up["id"], base["id"]])
        self.assertNotEqual(down["id"], base["id"])                                 # a new object with its own lineage

    def test_move_by_the_exercises_own_degrees_only(self) -> None:
        c = Conv()
        c.ask("Give me an A minor pentatonic line")
        up2 = c.ask("Move it up two pentatonic degrees")
        self.assertEqual(up2["transform"]["degrees"], 2)
        c.ask("Move it down one blues degree")
        self.assertTrue(c.failed)
        self.assertIn("minor pentatonic", c.resp.direct_answer)
        self.assertEqual(c.stored["id"], up2["id"])

    def test_c_major_blues_keeps_the_flat_and_natural_third_distinct_through_moves(self) -> None:
        c = Conv()
        base = c.ask("Give me a C major blues line using the flat 3rd and major 3rd")
        self.assertTrue(base["explanation_facts"]["both_thirds_present"])
        up = c.ask("Move it up")
        self.assertFalse(c.failed)
        self.assertEqual(up["midi"], shift_midis_by_degree(base["midi"], C_MAJOR_BLUES, +1))
        self.assertTrue(set(pcs(up["notes"])) <= C_MAJOR_BLUES)
        for old, new, role_old in zip(base["notes"], up["notes"], base["roles"]):
            if role_old == "b3":
                self.assertEqual(new, "E")                                           # E♭ → E, the next blues degree
            if role_old == "3":
                self.assertEqual(new, "G")                                           # E → G, never a semitone slide
        self.assertEqual(up["provenance"]["relationship"], "root_major_blues")
        down = c.ask("Move it down")
        self.assertEqual((down["notes"], down["midi"], down["roles"]), (base["notes"], base["midi"], base["roles"]))
        self.assertIn("b3", down["roles"])
        self.assertIn("3", down["roles"])

    def test_range_boundary_is_refused_and_the_exercise_is_unchanged(self) -> None:
        c = Conv()
        c.ask("Give me an A minor pentatonic line")
        last = None
        for _ in range(40):
            c.ask("Move it up")
            if c.failed:
                break
            last = c.ex
        self.assertTrue(c.failed)
        self.assertIn("staff range", c.resp.direct_answer)
        self.assertIsNotNone(last)
        self.assertEqual(c.stored["id"], last["id"])

    def test_guide_tone_exercise_moves_by_guide_tones_or_is_refused_with_a_reason(self) -> None:
        c = Conv()
        base = c.ask("Give me a guide-tone pattern over E7")
        up = c.ask("Move it up")
        if c.failed:
            self.assertTrue(c.resp.direct_answer)
            self.assertEqual(c.stored["id"], base["id"])
        else:
            self.assertTrue(set(pcs(up["notes"])) <= {8, 2})                         # G♯ and D only
            self.assertEqual(up["vocabulary"], "guide_tones")

    def test_sequence_states_the_idea_then_restates_it_one_degree_higher(self) -> None:
        c = Conv()
        base = c.ask("Give me an A minor pentatonic line")
        seq = c.ask("Sequence it upward")
        self.assertFalse(c.failed)
        n = len(base["notes"])
        self.assertEqual(seq["midi"][:n], base["midi"])
        self.assertEqual(seq["midi"][n:], shift_midis_by_degree(base["midi"], A_MINOR_PENT, +1))
        self.assertEqual(seq["bars"], base["bars"] * 2)
        self.assertTrue(seq["validation"]["ok"])


class TestContextAuthority(unittest.TestCase):
    def test_the_stored_context_stays_authoritative_after_the_live_context_changes(self) -> None:
        c = Conv()
        base = c.ask("Give me an A minor pentatonic line")
        c.ss.update({"display_key": "Dm", "concert_key": "Dm", "studio_page": "creative", "improv_intelligence_tab": "Missions",
                     "improv_active_mission": "Improvise using only chord tones", "ii_selected_chord": "Gm7",
                     "improv_mission_concert_key": "Dm",
                     "improv_mission_example": {"mission": "Improvise using only chord tones", "chord": "Gm7"}})
        for q in ("Another one", "Make it harder", "Move it up"):
            ex = c.ask(q)
            self.assertFalse(c.failed, q)
            self.assertEqual(ex["context"]["concert_key"], "Am", q)
            self.assertEqual(ex["context"]["key_source"], "explicit_request", q)     # as recorded on the parent
            self.assertEqual(ex["chord"], base["chord"], q)
            self.assertEqual(ex["transform"]["context_mode"], "stored_context", q)
            self.assertFalse(ex["context"]["mission_active"], q)

    def test_an_explicit_key_outranks_the_stored_context(self) -> None:
        c = Conv()
        c.ask("Give me an A minor pentatonic line")
        d = c.ask("Another one in D minor")
        self.assertFalse(c.failed)
        self.assertEqual((d["context"]["concert_key"], d["context"]["key_source"]), ("Dm", "explicit_request"))
        self.assertEqual(d["collection_label"], "D minor pentatonic")
        self.assertEqual(d["chord"], "Dm7")
        self.assertTrue(set(pcs(d["notes"])) <= {2, 5, 7, 9, 0})
        self.assertEqual(d["transform"]["overridden"], ["key"])
        self.assertEqual(d["context"]["key_candidates"].get("previous_exercise_key"), "Am")

    def test_an_explicit_chord_outranks_the_stored_chord(self) -> None:
        c = Conv()
        c.ask("Give me an A minor pentatonic line")
        e = c.ask("Another one over E7")
        self.assertFalse(c.failed)
        self.assertEqual(e["chord"], "E7")
        self.assertEqual(e["transform"]["overridden"], ["chord"])
        self.assertEqual(e["vocabulary"], "pentatonic")

    def test_harder_in_a_new_key_overrides_the_key_and_raises_the_level(self) -> None:
        c = Conv()
        c.ask("Give me an A minor pentatonic line")
        h = c.ask("Make it harder in D minor")
        self.assertFalse(c.failed, c.diag.get("exercise_followup_failure_reason"))
        self.assertEqual((h["context"]["concert_key"], h["context"]["level"]), ("Dm", "Advanced"))

    def test_asking_for_the_current_context_regenerates_there_and_records_it(self) -> None:
        c = Conv()
        base = c.ask("Give me an A minor pentatonic line")
        c.ss.update({"display_key": "Dm", "concert_key": "Dm"})
        e = c.ask("Give me another one for the current chord")
        self.assertFalse(c.failed, c.diag.get("exercise_followup_failure_reason"))
        self.assertEqual(e["transform"]["context_mode"], "current_context")
        self.assertEqual(e["context"]["concert_key"], "Dm")
        self.assertEqual(e["context"]["key_source"], "practice_chart_key")
        self.assertEqual(e["parent_id"], base["id"])
        self.assertEqual(e["vocabulary"], base["vocabulary"])

    def test_the_players_current_instrument_is_the_only_live_input(self) -> None:
        c = Conv()
        base = c.ask("Give me an A minor pentatonic line")
        c.ss.update({"instrument": "Clarinet", CHART_IN_INSTRUMENT_KEY_KEY: True, SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Bb Clarinet"})
        up = c.ask("Move it up")
        self.assertFalse(c.failed)
        self.assertEqual(up["context"]["concert_key"], "Am")
        self.assertTrue(up["written"]["applied"])
        self.assertEqual(up["written"]["key"], "Bm")
        self.assertEqual([m % 12 for m in up["written"]["midi"]], [(m + 2) % 12 for m in up["midi"]])
        self.assertTrue(up["transform"]["instrument_rebound"])
        self.assertIn("K:Bm", c.resp.notation_abc)
        self.assertEqual(up["midi"], shift_midis_by_degree(base["midi"], A_MINOR_PENT, +1))   # concert-first


class TestRoutingSafety(unittest.TestCase):
    def test_no_prior_exercise_is_explained(self) -> None:
        for q in ("Make it harder", "Another one", "Move it up", "Keep the rhythm but change the notes"):
            c = Conv()
            c.ask(q)
            self.assertTrue(c.failed, q)
            self.assertEqual(c.diag["exercise_followup_failure_reason"], "no_prior_exercise")
            self.assertIn("no generated exercise", c.resp.direct_answer)
            self.assertNotIn(AMI_LAST_EXERCISE_KEY, c.ss)

    def test_unrelated_questions_do_not_touch_the_last_exercise(self) -> None:
        c = Conv()
        base = c.ask("Give me an A minor pentatonic line")
        before = json.dumps(c.stored, sort_keys=True)
        for q in ("What is a pentatonic scale?", "How do I make it easier to play fast passages?"):
            c.ask(q)
            self.assertFalse(c.diag.get("exercise_followup"), q)
        self.assertEqual(json.dumps(c.stored, sort_keys=True), before)
        self.assertEqual(last_exercise(c.ss).id, base["id"])

    def test_a_legacy_ami_answer_ends_the_previous_exercise(self) -> None:
        c = Conv()
        c.ask("Give me an A minor pentatonic line")
        c.ask("Give me an A minor pentatonic pattern")            # AMI's own degree-pattern generator
        self.assertNotIn(AMI_LAST_EXERCISE_KEY, c.ss)
        c.ask("Another one")
        self.assertEqual(c.diag["exercise_followup_failure_reason"], "no_prior_exercise")

    def test_follow_ups_never_write_mission_or_chart_state(self) -> None:
        extra = {"improv_mission_example": {"mission": "m", "chord": "Dm7", "motif": {"notes": ["A"], "midi": [57]}},
                 "improv_mission_concert_key": "Dm", "ii_selected_chord": "Dm7", "improv_active_mission": "m"}
        c = Conv(**extra)
        c.ask("Give me an A minor pentatonic line")
        for q in ("Another one", "Make it harder", "Keep the notes but change the rhythm", "Move it up", "Move it down"):
            c.ask(q)
        for k, v in extra.items():
            self.assertEqual(c.ss[k], v, k)
        written = {k for k in c.ss if k not in extra and k not in {"instrument", "level", "display_key", "concert_key"}}
        self.assertFalse([k for k in written if k.startswith(("improv_", "ii_", "mission"))])
        self.assertEqual(c.ss["display_key"], "Am")


class TestProvenanceAndFingerprint(unittest.TestCase):
    def test_every_transform_links_to_its_parent_with_inherited_and_changed_fields(self) -> None:
        c = Conv()
        chain = [c.ask("Give me an A minor pentatonic line")]
        for q in ("Another one", "Keep the rhythm but change the notes", "Make it harder", "Move it up"):
            chain.append(c.ask(q))
        self.assertEqual(chain[0]["parent_id"], "")
        for parent, child in zip(chain, chain[1:]):
            t = child["transform"]
            self.assertEqual((child["parent_id"], t["parent"]), (parent["id"], parent["id"]))
            self.assertTrue(t["inherited"] and t["changed"])
            self.assertIn("kind", t)
            self.assertEqual(child["provenance"]["parent"], parent["id"])
            self.assertTrue(child["validation"]["ok"])
            self.assertEqual(child["engine"], "mission_motif_engine")
        self.assertEqual(len({e["id"] for e in chain}), len(chain))

    def test_the_duplicate_send_fingerprint_changes_with_the_last_exercise(self) -> None:
        c = Conv()
        c.ask("Give me an A minor pentatonic line")
        first = exercise_authority_signature(c.ss, "Another one")
        c.ask("Another one")
        second = exercise_authority_signature(c.ss, "Another one")
        self.assertNotEqual(first, second)                           # asking "Another one" twice is two requests
        self.assertTrue(first.startswith("followup|last=ex-"))
        self.assertEqual(exercise_authority_signature(c.ss, "Give me an A minor pentatonic line"), "none")
        self.assertEqual(exercise_authority_signature({}, "Another one").split("|")[1], "last=none")


if __name__ == "__main__":
    unittest.main()

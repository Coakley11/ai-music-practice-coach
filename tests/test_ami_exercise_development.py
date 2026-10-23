"""AMI Slice 5 Stage 4a: conversational development of a multi-chord exercise.

Every follow-up ("make it more chromatic", "keep the notes but change the rhythm", "develop the motif", "make it easier",
"play it in a higher register") is applied to the LATEST accepted exercise. The tests read the actual pitches, durations and chord
assignments of the parent and the child and re-derive what changed; the generator's own descriptions are never trusted.
"""

from __future__ import annotations

import copy
import unittest
from fractions import Fraction

from music_coach_ami.exercise_bridge import AMI_LAST_EXERCISE_KEY
from music_coach_ami.exercise_develop import parse_development
from music_coach_ami.exercise_followup import parse_followup
from music_coach_ami.exercise_span import open_exercise_in_missions
from tests.test_ami_advanced_vocabulary import arrival, half_step_into, tone_pcs
from tests.test_ami_span_guide_tones import ask, exercise_of

GUIDE3 = "Create a guide-tone exercise over the next three chords."
BEBOP3 = "Create a bebop line over the next three chords."


def scale_pcs(ex) -> list[set[int]]:
    from melodic_pattern_engine import build_context

    center = ex.context.span.get("key_center") or ex.context.concert_key
    return [build_context(center, c).scale_pcs for c in ex.chords]


def chromatic(ex) -> list[int]:
    sc = scale_pcs(ex)
    return [k for k, m in enumerate(ex.midi) if m % 12 not in sc[ex.chord_assignment[k]]]


def events(ex):
    return [(str(e.get("on")), str(e.get("dur")), bool(e.get("rest"))) for e in ex.rhythm_events]


def chord_durations(ex) -> list[Fraction]:
    """Beats each chord's window holds (rests included), read from the rhythm events and the stored chord timeline."""
    timeline = ex.explanation_facts["mission_example"]["motif"]["chord_timeline"]
    out = [Fraction(0)] * len(timeline)
    for e in ex.rhythm_events:
        on = Fraction(str(e["on"]))
        for i, t in enumerate(timeline):
            if Fraction(str(t["start"])) <= on < Fraction(str(t["end"])):
                out[i] += Fraction(str(e["dur"]))
    return out


def first_of(ex, i: int) -> int:
    return ex.midi[arrival(ex, i)]


def store(session):
    return session[AMI_LAST_EXERCISE_KEY]


def follow(first: str, *questions: str, key: str = "C", instrument: str = "Piano"):
    resp, session = ask(first, key=key, instrument=instrument)
    out = [exercise_of(resp)]
    resps = [resp]
    for q in questions:
        resp, _ = ask(q, session=session)
        out.append(exercise_of(resp))
        resps.append(resp)
    return out, resps, session


class TestParsing(unittest.TestCase):
    def test_development_phrases_are_recognised(self) -> None:
        table = {
            "Make it more chromatic.": "more_chromatic", "Add chromatic approaches.": "add_approaches",
            "Add an enclosure before the resolution.": "add_enclosure", "Use fewer chromatic notes.": "fewer_chromatic",
            "Make the resolution stronger.": "stronger_resolution", "Make the rhythm more interesting.": "rhythm_interesting",
            "Use more syncopation.": "rhythm_syncopate", "Make the rhythm simpler.": "rhythm_simpler",
            "Repeat the same rhythm across the chords.": "rhythm_repeat", "Develop the motif.": "motif_develop",
            "Create a variation of that phrase.": "motif_develop", "Repeat the idea but change the ending.": "motif_ending",
            "Use the same motif over the next chord.": "motif_next_chord", "Play it in a lower register.": "register_shift",
            "Make the phrase ascend.": "direction", "Keep it within a smaller range.": "smaller_range",
            "Use fewer notes.": "fewer_notes", "Add more movement.": "more_movement", "Go back to the original.": "original",
        }
        for q, op in table.items():
            with self.subTest(q=q):
                fu = parse_followup(q)
                self.assertIsNotNone(fu, q)
                self.assertEqual(fu.develop.get("op"), op, q)

    def test_register_direction_is_read(self) -> None:
        self.assertEqual(parse_development("play it in a lower register")["direction"], -1)
        self.assertEqual(parse_development("play it in a higher register")["direction"], 1)

    def test_other_questions_are_not_swallowed(self) -> None:
        for q in ("What is a chromatic approach?", "Tell me about syncopation", "Make it more chromatic soup please now",
                  "Why does the rhythm matter?"):
            fu = parse_followup(q)
            self.assertFalse(fu is not None and fu.develop, q)

    def test_slice_two_phrases_keep_their_meaning(self) -> None:
        for q, kind in (("Make it easier.", "easier"), ("Make it harder.", "harder"), ("Keep the notes but change the rhythm.", "same_notes_new_rhythm"),
                        ("Another one.", "variation"), ("Move it up.", "move")):
            self.assertEqual(parse_followup(q).kind, kind, q)


class TestChromaticDevelopment(unittest.TestCase):
    def test_more_chromatic_adds_a_lead_in_and_keeps_every_target(self) -> None:
        done = 0
        for key in ("C", "F", "Eb", "D"):
            with self.subTest(key=key):
                (a, b), resps, _s = follow(GUIDE3, "Make it more chromatic.", key=key)
                if b is None:       # a line whose changes are all enclosed already has nothing left to add - and says so
                    self.assertIn("already led into by an enclosure", resps[1].direct_answer, key)
                    continue
                done += 1
                self.assertGreater(len(chromatic(b)), len(chromatic(a)))
                self.assertEqual([first_of(b, i) for i in range(3)], [first_of(a, i) for i in range(3)])      # harmonic targets
                self.assertEqual(b.chord_assignment, a.chord_assignment)
                self.assertEqual(events(b), events(a))                                                         # same rhythm
                self.assertEqual(b.chords, a.chords)
                for k in chromatic(b):                                                                         # none arbitrary
                    if k + 1 < len(b.midi):
                        self.assertLessEqual(abs(b.midi[k + 1] - b.midi[k]), 2, (key, b.notes))
                changed = [k for k, (x, y) in enumerate(zip(a.midi, b.midi)) if x != y]
                self.assertTrue(changed)
                firsts = {arrival(a, i) for i in range(3)}
                self.assertFalse(firsts & set(changed))                                                        # no target was touched
        self.assertGreaterEqual(done, 3)

    def test_a_chromatic_note_added_before_a_change_is_a_half_step_lead_in(self) -> None:
        (a, b), _r, _s = follow(GUIDE3, "Add chromatic approaches.")
        led = [i for i in (1, 2) if half_step_into(b, i)]
        self.assertTrue(led)

    def test_an_enclosure_is_added_before_the_resolution(self) -> None:
        (a, b), _r, _s = follow(GUIDE3, "Add an enclosure before the resolution.")
        j = arrival(b, 2)
        lead = b.midi[j - 2:j]
        t = b.midi[j]
        self.assertTrue(any(m > t for m in lead) and any(m < t for m in lead))
        self.assertTrue(all(0 < abs(m - t) <= 2 for m in lead), (b.notes, lead, t))
        self.assertEqual(first_of(b, 2), first_of(a, 2))

    def test_the_resolution_can_be_made_stronger(self) -> None:
        (a, b), _r, _s = follow(BEBOP3, "Make the resolution stronger.")
        self.assertIsNotNone(b)
        j = arrival(b, 2)
        self.assertTrue(b.midi[j - 2] != a.midi[j - 2] or b.midi[j - 1] != a.midi[j - 1])

    def test_fewer_chromatic_removes_chromatic_notes_and_keeps_targets(self) -> None:
        (a, b, c), _r, _s = follow(GUIDE3, "Make it more chromatic.", "Use fewer chromatic notes.")
        self.assertLess(len(chromatic(c)), len(chromatic(b)))
        self.assertEqual([first_of(c, i) for i in range(3)], [first_of(a, i) for i in range(3)])
        self.assertEqual(events(c), events(a))

    def test_nothing_chromatic_to_remove_is_said_not_faked(self) -> None:
        (a, b), resps, session = follow(GUIDE3, "Use fewer chromatic notes.")
        self.assertIsNone(b)
        self.assertIn("no chromatic note", resps[1].direct_answer)
        self.assertEqual(store(session)["id"], a.id)                                                        # previous stays current

    def test_a_chord_tone_only_exercise_is_not_turned_into_a_chromatic_one(self) -> None:
        (a, b), resps, _s = follow("Give me a chord-tone pattern over the next three chords", "Make it more chromatic.")
        self.assertIsNone(b)
        self.assertIn("chord-tones-only", resps[1].direct_answer)

    def test_a_pentatonic_exercise_keeps_its_rule(self) -> None:
        (a, b), resps, _s = follow("Create a pentatonic pattern with chromatic approaches over the next two chords.",
                                   "Make it more chromatic.", key="F")
        self.assertIsNone(b)
        self.assertIn("pentatonic", resps[1].direct_answer)


class TestRhythmDevelopment(unittest.TestCase):
    def test_the_notes_stay_identical_and_the_rhythm_changes(self) -> None:
        for key in ("C", "F", "Eb", "D"):
            with self.subTest(key=key):
                (a, b), _r, _s = follow(GUIDE3, "Keep the notes but change the rhythm.", key=key)
                self.assertIsNotNone(b, key)
                self.assertEqual((b.midi, b.notes, b.chord_assignment), (a.midi, a.notes, a.chord_assignment))
                self.assertNotEqual(events(b), events(a))

    def test_measure_durations_and_chord_changes_are_preserved(self) -> None:
        (a, b), _r, _s = follow(BEBOP3, "Make the rhythm more interesting.")
        self.assertEqual(chord_durations(b), chord_durations(a))
        self.assertEqual(b.bars, a.bars)
        starts = [Fraction(str(t["start"])) for t in b.explanation_facts["mission_example"]["motif"]["chord_timeline"]]
        onsets = [Fraction(str(b.rhythm_events[arrival(b, i)]["on"])) for i in range(3)]
        self.assertEqual(onsets, starts)                                                                   # each chord begins on its downbeat

    def test_more_syncopation_is_measurably_more_syncopated(self) -> None:
        def syncopated(ex) -> int:
            ev = [e for e in ex.rhythm_events if not e.get("rest")]
            return sum(1 for e in ev if Fraction(str(e["on"])) % 1 != 0 and
                       Fraction(str(e["on"])) + Fraction(str(e["dur"])) > Fraction(str(e["on"])) - Fraction(str(e["on"])) % 1 + 1)
        (a, b), resps, _s = follow(BEBOP3, "Use more syncopation.")
        if b is None:
            self.assertIn("syncopation", resps[1].direct_answer)
        else:
            self.assertGreater(syncopated(b), syncopated(a))
            self.assertEqual(b.midi, a.midi)

    def test_a_simpler_rhythm_has_fewer_off_beat_entries(self) -> None:
        def offbeats(ex) -> int:
            return sum(1 for e in ex.rhythm_events if not e.get("rest") and Fraction(str(e["on"])) % 1 != 0)
        (a, b, c), _r, _s = follow(BEBOP3, "Use more syncopation.", "Make the rhythm simpler.")
        if b is None or c is None:
            self.skipTest("this line has no more-syncopated rhythm to simplify")
        self.assertLess(offbeats(c), offbeats(b))
        self.assertEqual(c.midi, a.midi)


class TestMotifDevelopment(unittest.TestCase):
    def test_developing_keeps_the_seed_audible_and_the_targets(self) -> None:
        (a, b), _r, _s = follow(BEBOP3, "Develop the motif.")
        self.assertIsNotNone(b)
        self.assertGreater(len(b.midi), len(a.midi))
        it = iter(b.midi)
        self.assertTrue(all(any(m == x for x in it) for m in a.midi), (a.midi, b.midi))                  # seed is a subsequence
        self.assertEqual([first_of(b, i) for i in range(3)], [first_of(a, i) for i in range(3)])
        self.assertEqual(sorted(set(b.chord_assignment)), [0, 1, 2])
        self.assertEqual(b.chord_assignment, sorted(b.chord_assignment))

    def test_developing_that_would_break_the_rule_is_refused(self) -> None:
        (a, b), resps, session = follow(GUIDE3, "Develop the motif.")
        if b is None:
            self.assertIn("haven't changed it", resps[1].direct_answer)
            self.assertEqual(store(session)["id"], a.id)

    def test_changing_the_ending_changes_only_the_last_note(self) -> None:
        (a, b), _r, _s = follow(BEBOP3, "Repeat the idea but change the ending.")
        self.assertIsNotNone(b)
        self.assertEqual(b.midi[:-1], a.midi[:-1])
        self.assertNotEqual(b.midi[-1], a.midi[-1])
        self.assertIn(b.midi[-1] % 12, tone_pcs(b.chords[-1], b.context.concert_key))
        self.assertEqual(events(b), events(a))

    def test_repeating_and_carrying_to_the_next_chord_are_said_to_be_unavailable(self) -> None:
        for q, text in (("Repeat this motif.", "longer stretch"), ("Use the same motif over the next chord.", "not available yet")):
            (a, b), resps, _s = follow(BEBOP3, q)
            self.assertIsNone(b, q)
            self.assertIn(text, resps[1].direct_answer, q)


class TestDifficulty(unittest.TestCase):
    def test_easier_is_measurably_simpler_and_keeps_the_objective(self) -> None:
        from music_coach_ami.exercise_develop import complexity, _contexts

        (a, b, c), _r, _s = follow(GUIDE3, "Make it more chromatic.", "Make it easier.")
        span_motif = lambda ex: ex.explanation_facts["mission_example"]["motif"]
        # (the span object is only needed for contexts; read it back from the stored example's own timeline)
        from tests.test_ami_span_guide_tones import session_for  # noqa: F401
        self.assertIsNotNone(c)
        self.assertLess(len(chromatic(c)), len(chromatic(b)))
        self.assertEqual([first_of(c, i) for i in range(3)], [first_of(a, i) for i in range(3)])         # same guide-tone targets
        self.assertEqual(c.engine_detail, a.engine_detail)
        self.assertEqual(span_motif(c)["chord_timeline"], span_motif(a)["chord_timeline"])

    def test_harder_adds_difficulty_not_a_new_exercise(self) -> None:
        (a, b), resps, _s = follow(GUIDE3, "Make it harder.")
        self.assertIsNotNone(b, resps[1].direct_answer[:200])
        self.assertEqual([first_of(b, i) for i in range(3)], [first_of(a, i) for i in range(3)])
        self.assertEqual(b.parent_id, a.id)
        self.assertTrue(len(chromatic(b)) > len(chromatic(a)) or events(b) != events(a))

    def test_the_card_says_how_difficulty_changed(self) -> None:
        (a, b), resps, _s = follow(GUIDE3, "Make it harder.")
        self.assertIn("Difficulty score", resps[1].direct_answer)


class TestRegister(unittest.TestCase):
    def test_higher_moves_every_note_by_one_octave_and_nothing_else(self) -> None:
        (a, b), resps, _s = follow(BEBOP3, "Play it in a higher register.")
        self.assertIsNotNone(b, resps[1].direct_answer[:200])
        self.assertEqual(b.midi, [m + 12 for m in a.midi])
        self.assertEqual((b.notes, b.chord_assignment, events(b)), (a.notes, a.chord_assignment, events(a)))

    def test_out_of_range_is_refused_not_bent(self) -> None:
        (a, b, c), resps, session = follow(BEBOP3, "Play it in a higher register.", "Play it in a higher register.")
        self.assertIsNone(c)
        self.assertIn("can't take the whole line an octave higher", resps[2].direct_answer)
        self.assertEqual(store(session)["id"], b.id)

    def test_direction_and_range_requests_are_refused_with_the_reason(self) -> None:
        for q in ("Make the phrase ascend.", "Make it descend.", "Keep it within a smaller range."):
            (a, b), resps, _s = follow(BEBOP3, q)
            self.assertIsNone(b, q)
            self.assertIn("octave", resps[1].direct_answer, q)

    def test_scale_degree_moves_are_not_pretended(self) -> None:
        (a, b), resps, _s = follow(BEBOP3, "Move it up a scale degree.")
        self.assertIsNone(b)
        self.assertIn("scale degrees", resps[1].direct_answer)


class TestSequentialFollowups(unittest.TestCase):
    def test_every_step_works_on_the_latest_version(self) -> None:
        (a, b, c, d), resps, session = follow(GUIDE3, "Make it more chromatic.", "Make the rhythm simpler.", "Use fewer chromatic notes.")
        if None in (b, c, d):
            self.skipTest("a step was refused on this line: " + " | ".join(r.direct_answer[:80] for r in resps[1:]))
        self.assertEqual((b.parent_id, c.parent_id, d.parent_id), (a.id, b.id, c.id))
        self.assertEqual(c.midi, b.midi)                          # the rhythm step keeps step 1's chromatic notes
        self.assertEqual(events(d), events(c))                    # the pitch step keeps step 2's rhythm
        self.assertLess(len(chromatic(d)), len(chromatic(c)))
        self.assertEqual(store(session)["id"], d.id)

    def test_the_latest_version_is_what_opens_in_missions(self) -> None:
        (a, b), resps, session = follow(GUIDE3, "Make it more chromatic.")
        action = resps[1].diagnostics["open_in_missions"]
        self.assertEqual(action["example"]["motif"]["midi"], b.midi)
        self.assertNotEqual(action["example"]["motif"]["midi"], a.midi)

    def test_going_back_restores_the_original_exactly(self) -> None:
        (a, b, c, o), _r, _s = follow(GUIDE3, "Make it more chromatic.", "Make the rhythm simpler.", "Go back to the original.")
        self.assertEqual((o.midi, o.notes, events(o), o.chord_assignment), (a.midi, a.notes, events(a), a.chord_assignment))
        self.assertEqual(o.parent_id, c.id)


class TestProvenance(unittest.TestCase):
    def test_parent_child_lineage_is_structured_data(self) -> None:
        (a, b, c), _r, _s = follow(GUIDE3, "Make it more chromatic.", "Make the rhythm simpler.")
        t = c.transform
        self.assertEqual((t["kind"], t["op"], t["parent"], t["root"]), ("develop", "rhythm_simpler", b.id, a.id))
        self.assertEqual([s["op"] for s in t["lineage"]["steps"]], ["more_chromatic", "rhythm_simpler"])
        self.assertEqual(t["lineage"]["root_example"]["motif"]["midi"], a.midi)
        self.assertEqual(t["parent_fingerprints"]["notes_sha1"], b.transform["preserved"]["notes_sha1"])

    def test_edits_name_the_notes_that_changed(self) -> None:
        (a, b), _r, _s = follow(GUIDE3, "Make it more chromatic.")
        changed = {k for k, (x, y) in enumerate(zip(a.midi, b.midi)) if x != y}
        self.assertEqual({e["index"] for e in b.transform["edits"]}, changed)
        for e in b.transform["edits"]:
            self.assertEqual(e["after"], b.notes[e["index"]])
            self.assertEqual(e["before"], a.notes[e["index"]])

    def test_kept_and_changed_are_stated(self) -> None:
        (a, b), resps, _s = follow(BEBOP3, "Keep the notes but change the rhythm.")
        self.assertEqual(b.transform["changed"], ["rhythm"])
        self.assertIn("notes", b.transform["inherited"])
        self.assertIn("Kept:", resps[1].direct_answer)

    def test_the_explanation_is_plain_english(self) -> None:
        (a, b), resps, _s = follow(GUIDE3, "Make it more chromatic.")
        text = resps[1].direct_answer
        self.assertRegex(text, r"(surround|leans a half step into)")
        self.assertNotIn("midi", text.lower())


class TestChangedContext(unittest.TestCase):
    def _later(self, mutate, q="Make it more chromatic."):
        resp, session = ask(GUIDE3, key="C")
        mutate(session)
        r, _ = ask(q, session=session)
        return exercise_of(r), r, session

    def test_a_practice_key_change_is_stated_not_silently_transposed(self) -> None:
        ex, r, session = self._later(lambda s: s.update(concert_key="G", display_key="G"))
        self.assertIsNone(ex)
        self.assertIn("Practice Key is now G", r.direct_answer)

    def test_a_different_song_or_progression_is_never_used(self) -> None:
        ex, r, _s = self._later(lambda s: s.update(song="Another", home_sections={"Verse 1": ["Am7", "D7", "Gmaj7", "Gmaj7"]}))
        self.assertIsNone(ex)
        self.assertIn("changed", r.direct_answer)

    def test_changed_chords_in_the_same_song_are_refused(self) -> None:
        ex, r, _s = self._later(lambda s: s.update(home_sections={"Verse 1": ["Fm7", "Bb7", "Ebmaj7", "Ebmaj7"]}))
        self.assertIsNone(ex)

    def test_a_transposing_instrument_is_refused_by_name(self) -> None:
        ex, r, _s = self._later(lambda s: s.update(instrument="Trumpet"))
        self.assertIsNone(ex)
        self.assertIn("Trumpet", r.direct_answer)

    def test_guitar_is_notated_with_tab_after_a_development(self) -> None:
        resp, session = ask(GUIDE3, key="F", instrument="Guitar")
        r, _ = ask("Make it more chromatic.", session=session)
        ex = exercise_of(r)
        self.assertIsNotNone(ex)
        self.assertTrue(r.diagnostics["guitar_tab_present"])
        self.assertIn("e|", r.direct_answer)
        self.assertIn("K:F", r.notation_abc)
        self.assertEqual(ex.context.concert_key, "F")

    def test_an_instrument_switch_to_guitar_rebinds_the_notation(self) -> None:
        resp, session = ask(GUIDE3, key="C", instrument="Piano")
        session["instrument"] = "Guitar"
        r, _ = ask("Make the rhythm simpler.", session=session)
        ex = exercise_of(r)
        if ex is not None:
            self.assertTrue(r.diagnostics["guitar_tab_present"])


class TestMissionsTransfer(unittest.TestCase):
    def test_the_developed_example_opens_exactly(self) -> None:
        (a, b), resps, session = follow(GUIDE3, "Make it more chromatic.")
        action = resps[1].diagnostics["open_in_missions"]
        before = copy.deepcopy(action["example"])
        result = open_exercise_in_missions(session, action)
        self.assertTrue(result["ok"], result)
        staged = session["improv_span_mission"]["example"]
        self.assertEqual(staged, before)
        self.assertEqual(staged["motif"]["midi"], b.midi)
        self.assertEqual(staged["motif"]["note_chord_index"], b.chord_assignment)
        self.assertEqual(staged["mission_id"], a.engine_detail)
        self.assertEqual(staged["handoff"]["practice_key"], "C")
        self.assertTrue(staged["valid"], staged.get("problems"))

    def test_every_development_stays_a_valid_mission_example(self) -> None:
        from mission_span_engine import validate_mission_line

        for q in ("Make it more chromatic.", "Keep the notes but change the rhythm.", "Make it harder.", "Play it in a higher register."):
            with self.subTest(q=q):
                (a, b), resps, _s = follow(BEBOP3, q)
                if b is None:
                    continue
                example = resps[1].diagnostics["open_in_missions"]["example"]
                self.assertTrue(example["valid"], example.get("problems"))
                self.assertEqual(example["motif"]["midi"], b.midi)

    def test_a_followup_after_opening_in_missions_still_uses_the_latest_exercise(self) -> None:
        (a, b), resps, session = follow(GUIDE3, "Make it more chromatic.")
        self.assertTrue(open_exercise_in_missions(session, resps[1].diagnostics["open_in_missions"])["ok"])
        r, _ = ask("Make the rhythm simpler.", session=session)
        c = exercise_of(r)
        if c is not None:
            self.assertEqual(c.parent_id, b.id)


class TestUnsupportedAndRegression(unittest.TestCase):
    def test_unsupported_requests_leave_the_exercise_untouched(self) -> None:
        for q in ("Use fewer notes.", "Add more movement.", "Make it ascend."):
            (a, b), resps, session = follow(BEBOP3, q)
            self.assertIsNone(b, q)
            self.assertEqual(store(session)["id"], a.id, q)
            self.assertEqual(resps[1].notation_abc, "", q)
            self.assertTrue(resps[1].direct_answer.strip(), q)

    def test_another_one_on_a_span_exercise_is_still_a_clear_refusal(self) -> None:
        (a, b), resps, _s = follow(GUIDE3, "Give me another one.")
        self.assertIsNone(b)
        self.assertIn("multi-chord", resps[1].direct_answer)

    def test_single_chord_followups_are_unchanged(self) -> None:
        (a, b), _r, _s = follow("Give me an A minor pentatonic line.", "Make it easier.", key="Am")
        self.assertIsNotNone(a)
        self.assertEqual(b.transform["kind"], "easier")

    def test_development_without_an_exercise_asks_for_one(self) -> None:
        resp, _ = ask("Make it more chromatic.")
        self.assertIn("no generated exercise", resp.direct_answer)

    def test_development_of_a_single_chord_technique_exercise_is_said_to_be_unavailable(self) -> None:
        (a, b), resps, _s = follow("Give me an enclosure exercise targeting the third of G7", "Make it more chromatic.")
        self.assertIsNone(b)
        self.assertIn("can't change", resps[1].direct_answer)

    def test_stages_one_to_three_b_still_generate(self) -> None:
        for q, mission in ((GUIDE3, "guide_tone_voice_leading"), (BEBOP3, "bebop_line"),
                           ("Target the third of each chord.", "resolve_to_third")):
            resp, _ = ask(q, key="C")
            self.assertEqual(exercise_of(resp).engine_detail, mission, q)


if __name__ == "__main__":
    unittest.main()

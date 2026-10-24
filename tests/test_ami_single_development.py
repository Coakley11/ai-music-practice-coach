"""AMI Slice 5 Stage 4b: conversational development of SINGLE-CHORD exercises (enclosure, chromatic approach, bebop, plain lines).

Every assertion reads the generated pitches and durations (not a label): an accepted change must keep the defining technique and its
target tone, operate on the latest accepted exercise, keep a full parent/root lineage, and open in Missions with exactly the
transformed notes. A refused change leaves the stored exercise untouched.
"""

from __future__ import annotations

import copy
import re
import unittest
from fractions import Fraction

from music_coach_ami.exercise_bridge import AMI_LAST_EXERCISE_KEY
from music_coach_ami.exercise_model import GeneratedExercise
from tests.test_ami_active_song_isolation import activate_catalog, activate_custom, ask, fresh
from tests.test_ami_notation_barlines import abc_bars, abc_body, tab_note_counts, tab_rows

ENCLOSURE = "Give me an enclosure exercise over G7"
APPROACH = "Give me a chromatic approach to the 7th of Dm7"
BEBOP = "Give me a bebop line over Dm7"
CHORD_TONES = "Give me a chord tone exercise over G7"
IN_SONG = "Give me an enclosure exercise over Bm"             # Bm is a chord of the catalog song, so it can open in Missions


def session(instrument: str = "Piano") -> dict:
    s = fresh()
    s["instrument"] = instrument
    activate_catalog(s)
    return s


def started(question: str, instrument: str = "Piano"):
    s = session(instrument)
    resp, ex = ask(question, s)
    assert ex is not None, resp.direct_answer[:200]
    return s, ex


def stored(s: dict) -> dict:
    return copy.deepcopy(s.get(AMI_LAST_EXERCISE_KEY))


def motif(ex: GeneratedExercise) -> dict:
    return ex.explanation_facts["motif"]


def roles(ex: GeneratedExercise) -> list[str]:
    r = list(motif(ex).get("pattern_note_roles") or [])
    return r if len(r) == len(ex.midi) else [""] * len(ex.midi)


def figure_before(ex: GeneratedExercise, t: int) -> list[int]:
    out, j = [], t - 1
    while j >= 0 and roles(ex)[j] in ("approach", "neighbor"):
        out.insert(0, ex.midi[j])
        j -= 1
    return out


def target_indexes(ex: GeneratedExercise) -> list[int]:
    return [i for i, r in enumerate(roles(ex)) if r == "target"]


def onsets(ex: GeneratedExercise) -> list[Fraction]:
    return [Fraction(str(e["on"])) for e in ex.rhythm_events if not e.get("rest")]


def durations(ex: GeneratedExercise) -> list[Fraction]:
    return [Fraction(str(e["dur"])) for e in ex.rhythm_events if not e.get("rest")]


def assert_enclosure(tc: unittest.TestCase, ex: GeneratedExercise) -> None:
    ts = target_indexes(ex)
    tc.assertTrue(ts, "an enclosure has a target")
    for t in ts:
        lead = figure_before(ex, t)
        tc.assertEqual(len(lead), 2, "two enclosing notes before every target")
        tc.assertTrue(any(v > ex.midi[t] for v in lead) and any(v < ex.midi[t] for v in lead), "one note above and one below the target")
        tc.assertTrue(all(0 < abs(v - ex.midi[t]) <= 3 for v in lead), "within a minor third of the target")


def assert_approach(tc: unittest.TestCase, ex: GeneratedExercise) -> None:
    ts = target_indexes(ex)
    tc.assertTrue(ts)
    for t in ts:
        tc.assertEqual(abs(ex.midi[t - 1] - ex.midi[t]), 1, "the note before the target is a half step away")


class TestEnclosureDevelopment(unittest.TestCase):
    def test_every_accepted_change_keeps_a_real_enclosure_of_the_same_targets(self) -> None:
        for q in ("make it harder", "make it more chromatic", "change the rhythm", "develop the motif", "make it easier",
                  "play it in a higher register"):
            with self.subTest(q=q):
                s, base = started(ENCLOSURE)
                assert_enclosure(self, base)
                resp, ex = ask(q, s)
                self.assertIsNotNone(ex, resp.direct_answer[:200])
                self.assertEqual(ex.parent_id, base.id)
                assert_enclosure(self, ex)
                shift = 12 if "higher" in q else 0
                self.assertEqual([ex.midi[t] % 12 for t in target_indexes(ex)], [base.midi[t] % 12 for t in target_indexes(base)])
                self.assertEqual([ex.midi[t] for t in target_indexes(ex)], [base.midi[t] + shift for t in target_indexes(base)])
                self.assertEqual(ex.chord, "G7")
                self.assertEqual(ex.intent.technique, "enclosure")

    def test_harder_closes_the_enclosure_to_half_steps_around_the_same_target(self) -> None:
        s, base = started(ENCLOSURE)
        resp, ex = ask("make it harder", s)
        for t in target_indexes(ex):
            gaps = sorted(abs(v - ex.midi[t]) for v in figure_before(ex, t))
            self.assertLessEqual(sum(gaps), sum(sorted(abs(v - base.midi[t]) for v in figure_before(base, t))))
        self.assertNotEqual(ex.midi, base.midi)


class TestChromaticApproachDevelopment(unittest.TestCase):
    def test_rhythm_change_keeps_every_pitch_and_the_approach_resolves_to_the_seventh(self) -> None:
        s, base = started(APPROACH)
        assert_approach(self, base)
        resp, ex = ask("change the rhythm", s)
        self.assertIsNotNone(ex, resp.direct_answer[:200])
        self.assertEqual(ex.midi, base.midi)
        self.assertNotEqual([(str(e["on"]), str(e["dur"])) for e in ex.rhythm_events], [(str(e["on"]), str(e["dur"])) for e in base.rhythm_events])
        assert_approach(self, ex)
        self.assertEqual({ex.midi[t] % 12 for t in target_indexes(ex)}, {0}, "the target is still C, the 7th of Dm7")
        self.assertEqual(ex.bars, base.bars)
        self.assertTrue(all(o % 1 == 0 for o in (onsets(ex)[t] for t in target_indexes(ex))), "the target still lands on a beat")

    def test_harder_and_easier_keep_the_resolution(self) -> None:
        for q in ("make it harder", "make it easier", "make it more chromatic", "develop the motif"):
            with self.subTest(q=q):
                s, base = started(APPROACH)
                resp, ex = ask(q, s)
                self.assertIsNotNone(ex, resp.direct_answer[:200])
                assert_approach(self, ex)
                self.assertEqual({ex.midi[t] % 12 for t in target_indexes(ex)}, {0})


class TestBebopDevelopment(unittest.TestCase):
    def test_rhythm_and_motif_changes_keep_the_bebop_line_grounded_on_chord_tones(self) -> None:
        for q in ("change the rhythm", "develop the motif", "make it easier", "make it harder"):
            with self.subTest(q=q):
                s, base = started(BEBOP)
                resp, ex = ask(q, s)
                self.assertIsNotNone(ex, resp.direct_answer[:200])
                pcs = {2, 5, 9, 0}   # Dm7: D F A C
                self.assertGreaterEqual(sum(1 for v in ex.midi if v % 12 in pcs), 2)
                self.assertEqual(ex.midi[-1], base.midi[-1], "a bebop line still resolves to the same last note")
                self.assertEqual(ex.intent.technique, "bebop")
                self.assertEqual(ex.chord, "Dm7")


class TestOperations(unittest.TestCase):
    def test_a_rhythm_only_change_keeps_exact_pitches_and_total_length(self) -> None:
        for base_q in (ENCLOSURE, APPROACH, BEBOP):
            with self.subTest(base=base_q):
                s, base = started(base_q)
                resp, ex = ask("change the rhythm", s)
                self.assertIsNotNone(ex, resp.direct_answer[:200])
                self.assertEqual(ex.midi, base.midi)
                self.assertEqual(ex.notes, base.notes)
                self.assertNotEqual(durations(ex) + onsets(ex), durations(base) + onsets(base))
                end = lambda e: max(o + d for o, d in zip(onsets(e), durations(e)))
                self.assertEqual(end(ex), end(base))
                self.assertEqual(ex.transform["changed"], ["rhythm"])

    def test_register_shift_moves_every_note_exactly_one_octave_and_nothing_else(self) -> None:
        s, base = started(BEBOP)
        resp, ex = ask("play it in a higher register", s)
        self.assertIsNotNone(ex, resp.direct_answer[:200])
        self.assertEqual(ex.midi, [v + 12 for v in base.midi])
        self.assertEqual([(str(e["on"]), str(e["dur"])) for e in ex.rhythm_events], [(str(e["on"]), str(e["dur"])) for e in base.rhythm_events])

    def test_a_register_move_that_would_leave_the_range_is_refused_without_bending_notes(self) -> None:
        s, base = started(BEBOP)
        before = stored(s)
        resp, ex = ask("play it in a lower register", s)
        self.assertIsNone(ex)
        self.assertIn("haven't changed it", resp.direct_answer)
        self.assertEqual(stored(s), before)

    def test_plain_lines_keep_their_notes_when_the_rhythm_changes(self) -> None:
        s, base = started("Give me a pentatonic line over Am7")
        resp, ex = ask("change the rhythm", s)
        self.assertIsNotNone(ex, resp.direct_answer[:200])
        self.assertEqual(ex.midi, base.midi)

    def test_a_fixed_rhythm_line_is_refused_honestly_for_rhythm_and_chromatic_changes(self) -> None:
        s, base = started(CHORD_TONES)
        before = stored(s)
        for q in ("make the rhythm simpler", "make it more chromatic"):
            resp, ex = ask(q, s)
            self.assertIsNone(ex)
            self.assertIn("fixed rhythm", resp.direct_answer)
            self.assertEqual(stored(s), before)

    def test_unknown_or_unsupported_changes_leave_the_exercise_alone(self) -> None:
        s, base = started(ENCLOSURE)
        before = stored(s)
        resp, ex = ask("add more movement", s)
        self.assertIsNone(ex)
        self.assertEqual(stored(s), before)


class TestSequentialLineageAndRestore(unittest.TestCase):
    def test_each_step_uses_the_latest_accepted_exercise_and_the_original_restores_exactly(self) -> None:
        s, e0 = started(ENCLOSURE)
        resp, e1 = ask("make it harder", s)
        resp, e2 = ask("change the rhythm", s)
        resp, e3 = ask("develop the motif", s)
        for child, parent in ((e1, e0), (e2, e1), (e3, e2)):
            self.assertIsNotNone(child, resp.direct_answer[:200])
            self.assertEqual(child.parent_id, parent.id)
            self.assertEqual(child.transform["before"]["midi"], parent.midi)
            self.assertEqual(child.transform["after"]["midi"], child.midi)
        self.assertEqual(e2.midi, e1.midi, "the rhythm step built on the harder step's notes, not the original's")
        self.assertEqual(e3.transform["lineage"]["root_id"], e0.id)
        self.assertEqual([st["parent"] for st in e3.transform["lineage"]["steps"]], [e0.id, e1.id, e2.id])
        resp, back = ask("go back to the original", s)
        self.assertIsNotNone(back, resp.direct_answer[:200])
        self.assertEqual(back.midi, e0.midi)
        self.assertEqual(back.notes, e0.notes)
        self.assertEqual([(str(e["on"]), str(e["dur"])) for e in back.rhythm_events], [(str(e["on"]), str(e["dur"])) for e in e0.rhythm_events])
        self.assertEqual(stored(s)["id"], back.id)

    def test_a_refused_step_keeps_the_stored_exercise_and_the_next_step_builds_on_it(self) -> None:
        s, e0 = started(BEBOP)
        resp, e1 = ask("make it harder", s)
        kept = stored(s)
        resp, none = ask("play it in a lower register", s)      # refused: out of range
        self.assertIsNone(none)
        self.assertEqual(stored(s), kept)
        resp, e2 = ask("change the rhythm", s)
        self.assertEqual(e2.parent_id, e1.id)


class TestSourceAndKeyOwnership(unittest.TestCase):
    def test_changing_the_active_song_refuses_the_follow_up_and_never_borrows_the_other_song(self) -> None:
        s, base = started(IN_SONG)
        activate_custom(s)                                      # F minor Custom progression becomes the live song
        before = stored(s)
        resp, ex = ask("make it harder", s)
        self.assertIsNone(ex)
        self.assertEqual(stored(s), before)
        self.assertRegex(resp.direct_answer, r"song has changed|Practice Key is now")
        self.assertNotIn("Fm7", resp.direct_answer.replace("Practice Key is now Fm", ""))

    def test_a_practice_key_change_is_never_transposed_silently(self) -> None:
        s, base = started(IN_SONG)
        s["display_key"] = s["concert_key"] = "Am"
        before = stored(s)
        resp, ex = ask("change the rhythm", s)
        self.assertIsNone(ex)
        self.assertIn("Practice Key is now", resp.direct_answer)
        self.assertEqual(stored(s), before)

    def test_capo_state_is_never_changed_by_a_follow_up(self) -> None:
        from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY

        s = session("Guitar")
        s[CAPO_ENABLED_KEY], s[CAPO_SHAPE_KEY] = False, "B"
        resp, base = ask(IN_SONG, s)
        resp, ex = ask("change the rhythm", s)
        self.assertIsNotNone(ex, resp.direct_answer[:200])
        self.assertEqual((s[CAPO_ENABLED_KEY], s[CAPO_SHAPE_KEY]), (False, "B"))


class TestNotationAndMissionsHandoff(unittest.TestCase):
    def test_guitar_tab_and_staff_break_at_the_same_measures_after_a_development(self) -> None:
        s = session("Guitar")
        resp, base = ask(ENCLOSURE, s)
        for q in ("make it harder", "change the rhythm"):
            resp, ex = ask(q, s)
            self.assertIsNotNone(ex, resp.direct_answer[:200])
            staff = abc_bars(resp.notation_abc)
            rows = tab_rows("\n".join([*resp.practice_steps, resp.direct_answer]))
            self.assertEqual(len(staff), ex.bars)
            self.assertEqual(tab_note_counts(rows), [sum(1 for t, _b in bar if not t.startswith("z")) for bar in staff])
            self.assertTrue(abc_body(resp.notation_abc).rstrip().endswith("|"))

    def test_a_chord_that_holds_through_the_bars_makes_no_false_barline(self) -> None:
        s, base = started(ENCLOSURE)
        resp, ex = ask("change the rhythm", s)
        self.assertEqual(abc_body(resp.notation_abc).count("|"), ex.bars)
        for bar in abc_bars(resp.notation_abc):
            self.assertEqual(sum(b for _t, b in bar), 4)

    def test_the_transformed_exercise_opens_in_missions_with_exactly_its_notes(self) -> None:
        from music_coach_ami.exercise_single import open_single_in_missions

        s, base = started(IN_SONG)
        resp, ex = ask("make it harder", s)
        self.assertIsNotNone(ex, resp.direct_answer[:200])
        action = resp.diagnostics["open_in_missions"]
        self.assertEqual(action["exercise_id"], ex.id)
        self.assertEqual(action["motif"]["midi"], ex.midi)
        result = open_single_in_missions(s, action)
        self.assertTrue(result["ok"], result.get("message"))
        example = s["improv_mission_example"]
        self.assertEqual(example["motif"]["midi"], ex.midi)
        self.assertNotEqual(example["motif"]["midi"], base.midi)
        self.assertEqual(abc_body(example["abc"]).count("|"), ex.bars)

    def test_the_card_carries_the_lineage_and_what_changed(self) -> None:
        s, base = started(ENCLOSURE)
        resp, ex = ask("make it more chromatic", s)
        self.assertIn("built from your previous exercise", resp.direct_answer)
        self.assertEqual(ex.transform["op"], "more_chromatic")
        self.assertEqual(ex.transform["parent"], base.id)
        self.assertEqual(ex.transform["lineage"]["root_id"], base.id)


class TestStage4aStillWorks(unittest.TestCase):
    def test_multi_chord_exercises_are_still_developed(self) -> None:
        s = session()
        resp, base = ask("Give me an enclosure exercise over the first two chords of the verse", s)
        self.assertIsNotNone(base)
        resp, ex = ask("change the rhythm", s)
        self.assertIsNotNone(ex, resp.direct_answer[:200])
        self.assertEqual(ex.parent_id, base.id)
        self.assertEqual(ex.midi, base.midi)


if __name__ == "__main__":
    unittest.main()


class TestDevelopedExerciseUsesTheCanonicalMissionModel(unittest.TestCase):
    def test_a_developed_exercise_survives_a_practice_key_cycle_exactly(self) -> None:
        from improvisation_missions import MISSION_EXAMPLE_KEY, transpose_stored_mission_example
        from music_coach_ami.exercise_single import open_single_in_missions

        s, base = started(IN_SONG)
        resp, ex = ask("make it harder", s)
        self.assertIsNotNone(ex, resp.direct_answer[:200])
        self.assertTrue(open_single_in_missions(s, resp.diagnostics["open_in_missions"])["ok"])
        home = s["concert_key"]
        original = list(s[MISSION_EXAMPLE_KEY]["motif"]["midi"])
        rhythm = list(s[MISSION_EXAMPLE_KEY]["motif"].get("rhythm_events") or [])
        cur = home
        for k in ("A", "Bb", "E", "F#", "Bb", home):
            self.assertTrue(transpose_stored_mission_example(s, from_key=cur, to_key=k))
            cur = k
            s["concert_key"] = s["display_key"] = k
        example = s[MISSION_EXAMPLE_KEY]
        self.assertEqual(example["motif"]["midi"], original)              # no octave drift, exact restore
        self.assertEqual(list(example["motif"].get("rhythm_events") or []), rhythm)
        self.assertEqual(example["chord"], "Bm")
        self.assertEqual(example["mission"], "Enclose a target chord tone before resolving")

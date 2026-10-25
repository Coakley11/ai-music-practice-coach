"""An exercise length the player names ("a 4 bar enclosure") is either built at exactly that many bars, or refused with the real
length: AMI never presents a 3-bar phrase as 4 bars. Length comes from the real meter and note durations (the staff's measures)."""

from __future__ import annotations

import re
import unittest

from music_coach_ami.exercise_model import GeneratedExercise
from tests.test_ami_active_song_isolation import activate_catalog, ask, fresh
from tests.test_ami_notation_barlines import abc_bars


def catalog_session(instrument: str = "Piano") -> dict:
    s = fresh()
    s["instrument"] = instrument
    activate_catalog(s)
    return s


class TestNamedBarCounts(unittest.TestCase):
    def test_a_supported_length_is_built_at_exactly_that_length(self) -> None:
        s = catalog_session()
        resp, ex = ask("Give me a 3 bar enclosure over Bm7", s)
        self.assertIsNotNone(ex, resp.direct_answer[:200])
        self.assertEqual(ex.bars, 3)
        self.assertEqual(len(abc_bars(resp.notation_abc)), 3)

    def test_an_unsupported_single_chord_length_is_refused_with_the_real_length(self) -> None:
        for q, wanted, real in (("Give me a 4 bar enclosure over Bm7", 4, 3), ("Give me a 2 bar enclosure over Bm7", 2, 3),
                                ("Give me a four bar bebop line over Bm7", 4, 2)):
            with self.subTest(q=q):
                s = catalog_session()
                resp, ex = ask(q, s)
                self.assertIsNone(ex)
                self.assertEqual(resp.notation_abc, "")
                text = resp.direct_answer
                self.assertIn(f"{wanted} bars", text)
                self.assertRegex(text, rf"\b{real} bars? long")
                self.assertIn("can't reliably build", text)
                self.assertEqual(resp.diagnostics.get("requested_bars"), wanted)

    def test_the_mission_engine_exercises_refuse_too(self) -> None:
        for q in ("Give me a 4 bar chord tone exercise over Bm7", "Give me a 4 bar pentatonic line over Bm7"):
            with self.subTest(q=q):
                resp, ex = ask(q, catalog_session())
                self.assertIsNone(ex)
                self.assertRegex(resp.direct_answer, r"you asked for 4 bars, but the generator's phrase here is \d bars? long")

    def test_a_multi_chord_exercise_is_one_bar_per_chord_and_refuses_other_lengths(self) -> None:
        resp, ex = ask("Give me a 4 bar enclosure exercise over the first two chords of the verse", catalog_session())
        self.assertIsNone(ex)
        self.assertIn("one bar per chord", resp.direct_answer)
        resp, ex = ask("Give me a 2 bar enclosure exercise over the first two chords of the verse", catalog_session())
        self.assertIsNotNone(ex)
        self.assertEqual(ex.bars, 2)

    def test_no_length_named_is_unchanged(self) -> None:
        for q, bars in (("Give me an enclosure over Bm7", 3), ("Give me an enclosure exercise over the first three chords of the verse", 3)):
            resp, ex = ask(q, catalog_session())
            self.assertEqual(ex.bars, bars)

    def test_a_refusal_leaves_the_stored_exercise_unchanged(self) -> None:
        s = catalog_session()
        resp, first = ask("Give me an enclosure over Bm7", s)
        keys = {k: s.get(k) for k in s if "last_exercise" in k or "ami_last" in k}
        self.assertTrue(keys, "the first exercise is stored")
        resp, ex = ask("Give me a 4 bar enclosure over Bm7", s)
        self.assertIsNone(ex)
        self.assertEqual({k: s.get(k) for k in keys}, keys)

    def test_the_message_never_claims_the_requested_count_for_a_different_length(self) -> None:
        resp, ex = ask("Give me a 4 bar enclosure over Bm7", catalog_session())
        self.assertNotRegex(resp.direct_answer, r"(?i)try this enclosure")
        self.assertFalse(re.search(r"\|", resp.notation_abc or ""))


if __name__ == "__main__":
    unittest.main()

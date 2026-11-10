"""The mode selector must not imply it works where it does not - and must not deny it where it does.

Guitar, Piano and Bass all have builders that predate the exercise modes. This file used to
assert that all three routed around them, which was true then: offering a Scales / Arpeggios
choice that silently changes nothing is worse than saying so.

Two of the three have since been given real exercise paths - the guitar through
``guitar_exercise_tab`` (absolute pitches mapped onto the fretboard) and the piano through
``piano_grand_staff`` (two staves, hands with roles) - so the claim has to move with them.
Bass still comps a walking line and is still declared honestly. The tests that matter here
are the ones that check the *claim against the output*, in both directions: an instrument
called supported must actually change what it renders, and one called unsupported must
actually render the same thing.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from practice_notation import (
    exercise_mode_supported,
    exercise_mode_unsupported_reason,
    generate_practice_notation,
)

ROOT = Path(__file__).resolve().parents[1]
CHORDS = ["Am6", "C7"]

# Exactly what the Practice page offers, so the claims are checked against real choices
# rather than instruments nobody can select.
from practice_setup_controls import DEFAULT_INSTRUMENT_OPTIONS

DEFERRED = ("Bass",)
SUPPORTED = tuple(i for i in DEFAULT_INSTRUMENT_OPTIONS if i not in DEFERRED) + ("Keyboard",)


def _abc(instrument, mode):
    return generate_practice_notation(
        song_title="T", artist="", display_key="Am", original_key="Am", bpm=100,
        groove_style="Jazz swing", instrument=instrument, focus="Improvisation",
        section_focus=None, sections={"A": CHORDS}, difficulty="advanced",
        exercise_mode=mode,
    )


def _rendering(res) -> tuple:
    """Everything a musician would see, whichever builder produced it."""
    return (res.abc, res.body, res.html)


class WhichInstrumentsTheModeReaches(unittest.TestCase):
    def test_single_line_instruments_are_supported(self):
        for inst in ("Saxophone", "Flute", "Trumpet", "Clarinet", "Voice", "Other"):
            with self.subTest(instrument=inst):
                self.assertTrue(exercise_mode_supported(inst))
                self.assertEqual(exercise_mode_unsupported_reason(inst), "")

    def test_guitar_and_piano_are_supported_now_that_they_have_exercise_paths(self):
        for inst in ("Guitar", "Piano", "Keyboard"):
            with self.subTest(instrument=inst):
                self.assertTrue(exercise_mode_supported(inst))
                self.assertEqual(exercise_mode_unsupported_reason(inst), "")

    def test_bass_is_still_deferred(self):
        for inst in DEFERRED:
            with self.subTest(instrument=inst):
                self.assertFalse(exercise_mode_supported(inst))
                self.assertTrue(exercise_mode_unsupported_reason(inst))

    def test_every_offered_instrument_is_accounted_for(self):
        """No option on the page falls through to an unexamined answer."""
        from practice_notation import notation_builder_kind

        for inst in DEFAULT_INSTRUMENT_OPTIONS:
            with self.subTest(instrument=inst):
                self.assertIn(
                    notation_builder_kind(inst), ("guitar", "piano", "bass", "line")
                )

    def test_the_claim_cannot_contradict_the_routing(self):
        """The property that caught a real bug, so it stays checked.

        Support used to be decided by scanning the instrument name separately from the
        router's own precedence. An instrument matching both "bass" and "guitar" routed to
        the guitar builder while being declared a bass, so the selector claimed to change
        nothing and changed the output. Both now ask one function.
        """
        from practice_notation import notation_builder_kind

        for inst in list(DEFAULT_INSTRUMENT_OPTIONS) + ["Keyboard", "Bass Guitar", "", "Theremin"]:
            with self.subTest(instrument=inst):
                deferred = notation_builder_kind(inst) in ("bass",)
                self.assertEqual(exercise_mode_supported(inst), not deferred)
                changes = _rendering(_abc(inst, "arpeggios")) != _rendering(_abc(inst, "scales"))
                self.assertEqual(
                    changes,
                    exercise_mode_supported(inst),
                    f"{inst}: selector says supported={exercise_mode_supported(inst)} "
                    f"but output changes={changes}",
                )

    def test_the_reason_names_the_instrument_and_what_it_renders(self):
        self.assertIn("Bass", exercise_mode_unsupported_reason("Bass"))
        self.assertIn("walking", exercise_mode_unsupported_reason("Bass"))

    def test_the_claim_matches_reality_for_deferred_instruments(self):
        """Assert the output really is identical, so the message is not a guess."""
        for inst in DEFERRED:
            with self.subTest(instrument=inst):
                self.assertEqual(
                    _rendering(_abc(inst, "arpeggios")), _rendering(_abc(inst, "scales"))
                )

    def test_the_claim_matches_reality_for_supported_instruments(self):
        """And that every instrument called supported really does change."""
        for inst in SUPPORTED:
            with self.subTest(instrument=inst):
                self.assertNotEqual(
                    _rendering(_abc(inst, "arpeggios")), _rendering(_abc(inst, "scales"))
                )

    def test_auto_differs_from_both_explicit_modes_everywhere_it_is_supported(self):
        for inst in SUPPORTED:
            with self.subTest(instrument=inst):
                auto = _rendering(_abc(inst, "auto"))
                self.assertNotEqual(auto, _rendering(_abc(inst, "scales")))
                self.assertNotEqual(auto, _rendering(_abc(inst, "arpeggios")))

    def test_keyboard_is_still_treated_like_piano(self):
        self.assertEqual(
            exercise_mode_supported("Keyboard"), exercise_mode_supported("Piano")
        )

    def test_blank_and_unknown_instruments_do_not_crash(self):
        for inst in ("", "   ", "Theremin"):
            with self.subTest(instrument=inst):
                self.assertIsInstance(exercise_mode_supported(inst), bool)


class ThePracticePageDisablesIt(unittest.TestCase):
    """The selector still has to disable itself for whatever remains deferred."""

    def setUp(self):
        self.src = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        i = self.src.index('key="practice_notation_exercise_mode"')
        self.window = self.src[max(0, i - 1200) : i + 900]

    def test_the_selector_is_disabled_when_unsupported(self):
        self.assertIn("disabled=not _mode_ok", self.window)

    def test_support_is_decided_by_the_shared_helper(self):
        self.assertIn("exercise_mode_supported(instrument)", self.window)

    def test_the_reason_is_shown_to_the_musician(self):
        self.assertIn("exercise_mode_unsupported_reason(instrument)", self.window)

    def test_an_unsupported_instrument_falls_back_to_auto(self):
        self.assertIn('_notation_exercise_mode = "auto"', self.window)


if __name__ == "__main__":
    unittest.main()

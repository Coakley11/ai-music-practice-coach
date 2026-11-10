"""The mode selector must not imply it works where it does not.

Guitar renders TAB, Piano renders connected voicings and Bass renders a walking line -
three builders that predate the exercise modes and route around them entirely. Offering a
Scales / Arpeggios choice that silently changes nothing is worse than saying so.
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


def _abc(instrument, mode):
    return generate_practice_notation(
        song_title="T", artist="", display_key="Am", original_key="Am", bpm=100,
        groove_style="Jazz swing", instrument=instrument, focus="Improvisation",
        section_focus=None, sections={"A": CHORDS}, difficulty="advanced",
        exercise_mode=mode,
    )


class WhichInstrumentsTheModeReaches(unittest.TestCase):
    def test_single_line_instruments_are_supported(self):
        for inst in ("Saxophone", "Flute", "Trumpet", "Clarinet", "Voice", "Other"):
            with self.subTest(instrument=inst):
                self.assertTrue(exercise_mode_supported(inst))
                self.assertEqual(exercise_mode_unsupported_reason(inst), "")

    def test_tab_voicing_and_walking_bass_instruments_are_not(self):
        for inst in ("Guitar", "Piano", "Bass"):
            with self.subTest(instrument=inst):
                self.assertFalse(exercise_mode_supported(inst))
                self.assertTrue(exercise_mode_unsupported_reason(inst))

    def test_the_reason_names_the_instrument_and_what_it_renders(self):
        self.assertIn("Guitar", exercise_mode_unsupported_reason("Guitar"))
        self.assertIn("TAB", exercise_mode_unsupported_reason("Guitar"))
        self.assertIn("voicings", exercise_mode_unsupported_reason("Piano"))
        self.assertIn("walking", exercise_mode_unsupported_reason("Bass"))

    def test_the_claim_matches_reality_for_unsupported_instruments(self):
        """Assert the output really is identical, so the message is not a guess."""
        for inst in ("Guitar", "Piano", "Bass"):
            with self.subTest(instrument=inst):
                a = _abc(inst, "arpeggios")
                s = _abc(inst, "scales")
                self.assertEqual((a.abc, a.body, a.html), (s.abc, s.body, s.html))

    def test_the_claim_matches_reality_for_supported_instruments(self):
        for inst in ("Flute", "Saxophone"):
            with self.subTest(instrument=inst):
                self.assertNotEqual(_abc(inst, "arpeggios").abc, _abc(inst, "scales").abc)

    def test_keyboard_is_treated_like_piano(self):
        self.assertFalse(exercise_mode_supported("Keyboard"))

    def test_blank_and_unknown_instruments_do_not_crash(self):
        for inst in ("", "   ", "Theremin"):
            with self.subTest(instrument=inst):
                self.assertIsInstance(exercise_mode_supported(inst), bool)


class ThePracticePageDisablesIt(unittest.TestCase):
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

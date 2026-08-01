"""Piano keyboard visualization for Creative Missions."""

from __future__ import annotations

import unittest

from improvisation_missions import _piano_keyboard_html
from improvisation_motif import chord_tone_names, generate_motif_for_chord


class TestPianoKeyboardMissions(unittest.TestCase):
    def test_bm_chord_shows_f_sharp_black_key(self) -> None:
        tones = chord_tone_names("Bm", reference_key="Bm")
        html = _piano_keyboard_html(tones, tones, reference_key="Bm")
        self.assertIn("F#", html)
        self.assertIn("pk black", html)
        self.assertIn("hi", html)

    def test_motif_complexity_scales_with_level(self) -> None:
        beg = generate_motif_for_chord("Am7", key_center="G", level="Beginner")
        adv = generate_motif_for_chord("Am7", key_center="G", level="Advanced")
        self.assertLessEqual(len(beg["notes"]), 2)
        self.assertGreaterEqual(len(adv["notes"]), 3)

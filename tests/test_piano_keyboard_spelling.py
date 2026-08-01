"""Piano keyboard display uses chart-key spelling."""

from __future__ import annotations

import unittest

from piano_keyboard_display import build_piano_keyboard_html, pitch_class_label
from improvisation_missions import _piano_keyboard_html
from improvisation_motif import chord_tone_names


class TestPianoKeyboardSpelling(unittest.TestCase):
    def test_flat_key_uses_bb_not_a_sharp(self) -> None:
        tones = chord_tone_names("Gm7", reference_key="F")
        html = build_piano_keyboard_html(tones, tones, reference_key="F")
        self.assertIn("Bb", html)
        self.assertNotIn("A#", html)

    def test_sharp_key_uses_f_sharp(self) -> None:
        self.assertEqual(pitch_class_label(6, "D"), "F#")
        tones = chord_tone_names("Bm", reference_key="Bm")
        html = _piano_keyboard_html(tones, tones, reference_key="Bm")
        self.assertIn("F#", html)
        self.assertIn("pk black", html)


if __name__ == "__main__":
    unittest.main()

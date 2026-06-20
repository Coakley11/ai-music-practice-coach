"""Major/minor-only key dropdown behavior."""

from __future__ import annotations

import unittest

from music_theory import (
    coerce_key_to_mode,
    display_key_options,
    key_is_minor,
    key_mode,
    practice_keys_for_mode,
)
from instrument_transposition import _transpose_key_center


class TestKeyModeOptions(unittest.TestCase):
    def test_major_song_excludes_minor_keys(self) -> None:
        opts = display_key_options("Eb")
        self.assertIn("Eb", opts)
        self.assertIn("D#", opts)
        self.assertNotIn("Ebm", opts)
        self.assertNotIn("Dm", opts)
        self.assertEqual(len(opts), 17)

    def test_minor_song_excludes_major_keys(self) -> None:
        opts = display_key_options("F#m")
        self.assertIn("F#m", opts)
        self.assertIn("Gbm", opts)
        self.assertNotIn("F#", opts)
        self.assertNotIn("G", opts)
        self.assertEqual(len(opts), 17)

    def test_custom_major_inferred_from_key(self) -> None:
        self.assertEqual(key_mode("A"), "major")
        opts = display_key_options("A")
        self.assertTrue(all(not key_is_minor(k) for k in opts))

    def test_custom_minor_inferred_from_key(self) -> None:
        self.assertEqual(key_mode("C#m"), "minor")
        opts = display_key_options("C#m")
        self.assertTrue(all(key_is_minor(k) for k in opts))

    def test_written_transpose_preserves_major_mode(self) -> None:
        written = _transpose_key_center("Eb", 2)
        self.assertEqual(key_mode(written), "major")
        self.assertFalse(key_is_minor(written))

    def test_written_transpose_preserves_minor_mode(self) -> None:
        written = _transpose_key_center("Em", 2)
        self.assertEqual(key_mode(written), "minor")
        self.assertTrue(key_is_minor(written))

    def test_enharmonic_major_options_include_both_spellings(self) -> None:
        opts = practice_keys_for_mode("major")
        self.assertIn("Bb", opts)
        self.assertIn("A#", opts)
        self.assertIn("Db", opts)
        self.assertIn("C#", opts)

    def test_coerce_invalid_saved_minor_to_major(self) -> None:
        fixed = coerce_key_to_mode("Dm", "major")
        self.assertEqual(fixed, "D")
        self.assertIn(fixed, practice_keys_for_mode("major"))

    def test_coerce_invalid_saved_major_to_minor(self) -> None:
        fixed = coerce_key_to_mode("G", "minor")
        self.assertEqual(fixed, "Gm")
        self.assertIn(fixed, practice_keys_for_mode("minor"))


if __name__ == "__main__":
    unittest.main()

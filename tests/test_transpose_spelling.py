"""Chord/key transposition preserves sharp vs flat spelling families."""

from __future__ import annotations

import unittest

from instrument_transposition import written_key_for_type
from music_theory import transpose_chord


class TestTransposeSpelling(unittest.TestCase):
    def test_flat_concert_key_transposes_chords_with_flats(self) -> None:
        self.assertEqual(transpose_chord("Bbm", 2, reference_key="Db"), "Cm")
        self.assertEqual(transpose_chord("Eb", 0, reference_key="Db"), "Eb")

    def test_sharp_concert_key_transposes_chords_with_sharps(self) -> None:
        self.assertEqual(transpose_chord("Em", 2, reference_key="G"), "F#m")
        self.assertEqual(transpose_chord("C#m", 2, reference_key="E"), "D#m")
        self.assertEqual(transpose_chord("Em", 9, reference_key="Em"), "C#m")

    def test_written_key_follows_concert_accidental_style(self) -> None:
        self.assertEqual(written_key_for_type("Db", "Alto saxophone (Eb)"), "Bb")
        self.assertEqual(written_key_for_type("G", "Tenor saxophone (Bb)"), "A")
        self.assertEqual(written_key_for_type("E", "Tenor saxophone (Bb)"), "F#")
        self.assertEqual(written_key_for_type("Am", "Alto saxophone (Eb)"), "F#m")

    def test_transpose_pipe_subdivisions(self) -> None:
        steps = 8  # C#m -> Am
        self.assertEqual(
            transpose_chord("C#m7|B", steps, reference_key="Am"),
            "Am7|G",
        )
        self.assertEqual(
            transpose_chord("A|B", steps, reference_key="Am"),
            "F|G",
        )
        self.assertEqual(
            transpose_chord("G#sus4", steps, reference_key="Am"),
            "Esus4",
        )


if __name__ == "__main__":
    unittest.main()

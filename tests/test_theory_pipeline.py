"""Canonical theory pipeline — normalize playback tokens before quality and chord tones."""

from __future__ import annotations

import unittest

from improvisation_intelligence import chord_coach_insight
from improvisation_motif import chord_tone_names
from music_theory import (
    chord_quality_label,
    chord_root_for_theory,
    classify_chord_quality,
    normalize_chord_for_theory,
)


class TestNormalizeChordForTheory(unittest.TestCase):
    def test_weighted_subdivision_with_push(self) -> None:
        self.assertEqual(normalize_chord_for_theory("Em:3.5|D:0.5p"), "Em")

    def test_weighted_split_bar(self) -> None:
        self.assertEqual(normalize_chord_for_theory("C#m:2|A:2"), "C#m")

    def test_bar_weight_suffix(self) -> None:
        self.assertEqual(normalize_chord_for_theory("G7sus4:4"), "G7sus4")
        self.assertEqual(normalize_chord_for_theory("F#m7b5:2"), "F#m7b5")


class TestClassifyChordQuality(unittest.TestCase):
    def test_regression_qualities(self) -> None:
        cases = {
            "Em:3.5|D:0.5p": "minor",
            "C#m:2|A:2": "minor",
            "G7sus4:4": "sus",
            "G#7": "dom",
            "G#7sus4": "sus",
            "Bbmaj7": "maj7",
            "F#m7b5:2": "half-dim",
            "Bdim": "dim",
            "Csus2": "sus",
            "Csus4": "sus",
            "Eaug": "aug",
        }
        for token, expected in cases.items():
            with self.subTest(token=token):
                self.assertEqual(classify_chord_quality(token), expected)

    def test_lab_labels_match_buckets(self) -> None:
        self.assertEqual(chord_quality_label("G#7"), "dominant seventh")
        self.assertEqual(chord_quality_label("Bdim"), "diminished")


class TestChordTonesAndCoaching(unittest.TestCase):
    def test_em_subdivision_minor_third(self) -> None:
        tones = chord_tone_names("Em:3.5|D:0.5p", reference_key="G")
        self.assertIn("G", tones)
        self.assertNotIn("G#", tones)

    def test_c_sharp_minor_root(self) -> None:
        self.assertEqual(chord_root_for_theory("C#m:2|A:2"), "C#")

    def test_bdim_triad(self) -> None:
        self.assertEqual(chord_tone_names("Bdim")[:3], ["B", "D", "F"])

    def test_ebdim7_uses_diminished_fifth_not_perfect_fifth(self) -> None:
        tones = chord_tone_names("Ebdim7")
        pcs = {__import__("music_theory").pitch_class_from_spelled_note(t) % 12 for t in tones}
        self.assertEqual(pcs, {3, 6, 9, 0})
        self.assertIn("Eb", tones)
        self.assertIn("Gb", tones)
        joined = " ".join(tones)
        self.assertNotIn("Bb", joined)
        self.assertTrue(any(t in {"A", "Bbb"} for t in tones))
        self.assertTrue(any(t in {"C", "Dbb", "B#"} for t in tones))

    def test_csus2_and_csus4(self) -> None:
        self.assertEqual(chord_tone_names("Csus2")[:3], ["C", "D", "G"])
        self.assertEqual(chord_tone_names("Csus4")[:3], ["C", "F", "G"])

    def test_eaug_triad(self) -> None:
        tones = chord_tone_names("Eaug", reference_key="E")
        self.assertEqual(tones[0], "E")
        self.assertEqual(tones[1], "G#")
        # Augmented fifth of E is letter B → B# (enharmonic C).
        self.assertIn(tones[2], ("B#", "C"))

    def test_g7sus4_coaching_uses_sus_quality(self) -> None:
        self.assertEqual(classify_chord_quality("G7sus4:4"), "sus")
        tones = chord_tone_names("G7sus4:4", reference_key="C")
        self.assertEqual(tones[0], "G")
        self.assertIn(tones[1], ("C", "F"))


if __name__ == "__main__":
    unittest.main()

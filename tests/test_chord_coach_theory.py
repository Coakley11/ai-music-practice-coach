"""Live Coach / chord_coach_insight must respect chord quality, including subdivided bars."""

from __future__ import annotations

import unittest

from improvisation_intelligence import chord_coach_insight
from music_theory import classify_chord_quality, normalize_chord_for_theory


class TestChordNormalization(unittest.TestCase):
    def test_weighted_subdivision_bar(self) -> None:
        self.assertEqual(normalize_chord_for_theory("Em:3.5|D:0.5p"), "Em")

    def test_classify_minor_from_subdivision(self) -> None:
        self.assertEqual(classify_chord_quality("Em:3.5|D:0.5p"), "minor")


class TestChordCoachInsight(unittest.TestCase):
    def test_em_subdivision_bar_minor_tones(self) -> None:
        insight = chord_coach_insight(
            "Em:3.5|D:0.5p",
            key_center="G",
            instrument="Guitar",
            level="Intermediate",
        )
        self.assertIn("G", insight.chord_tones)
        self.assertNotIn("G#", insight.chord_tones)
        scale_text = " ".join(insight.scales).lower()
        self.assertTrue("dorian" in scale_text or "minor" in scale_text)

    def test_am7(self) -> None:
        insight = chord_coach_insight("Am7", key_center="G")
        self.assertEqual(insight.chord_tones[:3], ["A", "C", "E"])

    def test_cmaj7(self) -> None:
        insight = chord_coach_insight("Cmaj7", key_center="C")
        self.assertIn("E", insight.chord_tones)
        self.assertIn("B", insight.chord_tones)

    def test_g7_dominant(self) -> None:
        insight = chord_coach_insight("G7", key_center="C")
        self.assertIn("mixolydian", " ".join(insight.scales).lower())

    def test_bdim(self) -> None:
        self.assertEqual(classify_chord_quality("Bdim"), "dim")
        insight = chord_coach_insight("Bdim", key_center="G")
        self.assertEqual(insight.chord_tones[:3], ["B", "D", "F"])

    def test_f_sharp_half_dim(self) -> None:
        insight = chord_coach_insight("F#m7b5", key_center="Bm")
        self.assertIn("A", insight.chord_tones)
        labels = " ".join(s.label for s in insight.scale_suggestions)
        self.assertIn("Half-Diminished", labels)
        for sug in insight.scale_suggestions:
            self.assertTrue(all(len(n) <= 3 for n in sug.notes))


if __name__ == "__main__":
    unittest.main()

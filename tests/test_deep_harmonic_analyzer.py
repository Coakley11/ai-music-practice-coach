"""Regression tests for deep harmonic analysis."""

from __future__ import annotations

import unittest

from deep_harmonic_analyzer import HarmonicAnalysisInput, build_deep_harmonic_analysis, build_deep_harmonic_lesson


class TestDeepHarmonicAnalyzer(unittest.TestCase):
    def test_lesson_priorities_for_repeating_loop(self) -> None:
        lesson = build_deep_harmonic_lesson(
            HarmonicAnalysisInput(
                song_title="Shape of You",
                artist="Ed Sheeran",
                key_center="C#m",
                display_key="Bm",
                sections={"Verse": ["Bm", "G", "A", "Bm"], "Chorus": ["Bm", "G", "A", "Bm"]},
                instrument="Piano",
                level="Beginner",
                focus="Improvisation",
                progression_flat=["Bm", "G", "A", "Bm"],
            )
        )
        joined = " ".join(lesson["priorities"]).lower()
        self.assertIn("loop", joined)
        self.assertTrue(len(lesson["steps"]) >= 3)
        self.assertTrue(lesson["loop"]["repeating"])

    def test_wind_playbook_triad_does_not_index_seventh(self) -> None:
        """Triad chords (no 7th) must not crash Creative / Harmonic Analysis."""
        lesson = build_deep_harmonic_lesson(
            HarmonicAnalysisInput(
                song_title="Triad Song",
                artist="Test Artist",
                key_center="C",
                display_key="C",
                sections={"Verse": ["C", "G", "Am"]},
                instrument="Saxophone",
                level="Intermediate",
                focus="Improvisation",
                progression_flat=["C", "G", "Am"],
            )
        )
        playbook = next(
            (d for d in lesson["deep_dive"] if "playbook" in d["title"].lower()),
            None,
        )
        self.assertIsNotNone(playbook)
        self.assertIn("Home sonority **C**", playbook["markdown"])
        self.assertIn("root, 3rd, 5th", playbook["markdown"])

    def test_compact_markdown_export(self) -> None:
        text = build_deep_harmonic_analysis(
            HarmonicAnalysisInput(
                song_title="Triad Song",
                artist="Test Artist",
                key_center="C",
                display_key="C",
                sections={"Verse": ["C", "G", "Am"]},
                instrument="Saxophone",
                level="Intermediate",
                focus="Improvisation",
                progression_flat=["C", "G", "Am"],
            )
        )
        self.assertIn("Start here", text)


if __name__ == "__main__":
    unittest.main()

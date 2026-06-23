"""Regression tests for deep harmonic analysis."""

from __future__ import annotations

import unittest

from deep_harmonic_analyzer import HarmonicAnalysisInput, build_deep_harmonic_analysis


class TestDeepHarmonicAnalyzer(unittest.TestCase):
    def test_wind_playbook_triad_does_not_index_seventh(self) -> None:
        """Triad chords (no 7th) must not crash Creative / Harmonic Analysis."""
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
        self.assertIn("Home sonority **C**", text)
        self.assertIn("root, 3rd, 5th", text)


if __name__ == "__main__":
    unittest.main()

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
        self.assertGreaterEqual(len(lesson["deep_dive"]), 2)

    def test_beginner_lesson_includes_go_deeper_blocks(self) -> None:
        lesson = build_deep_harmonic_lesson(
            HarmonicAnalysisInput(
                song_title="Shape of You",
                artist="Ed Sheeran",
                key_center="C#m",
                display_key="Bm",
                sections={"Verse": ["Bm", "G", "A"], "Chorus": ["Bm", "G", "A"]},
                instrument="Piano",
                level="Beginner",
                focus="Improvisation",
                progression_flat=["Bm", "G", "A"],
            )
        )
        titles = " ".join(
            c.get("title", "").lower() for c in lesson.get("reference_cards") or lesson["deep_dive"]
        )
        self.assertIn("playbook", titles)
        self.assertTrue(all(str(d.get("markdown") or "").strip() for d in lesson["deep_dive"]))

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
            (
                d
                for d in (lesson.get("reference_cards") or lesson["deep_dive"])
                if "playbook" in str(d.get("title", "")).lower()
            ),
            None,
        )
        self.assertIsNotNone(playbook)
        md = str(playbook.get("markdown") or "")
        self.assertIn("Home sonority **C**", md)
        self.assertIn("root, 3rd, 5th", md)

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

"""Tests for practice-level chart arrangement (harmony + form)."""

from __future__ import annotations

import unittest

from chart_level_arrangement import (
    normalize_chord_for_intermediate,
    resolve_level_chart,
    select_intermediate_section_names,
    select_section_names_for_level,
    simplify_chord_for_beginner,
)


class TestChartLevelHarmony(unittest.TestCase):
    def test_beginner_strips_slash_and_extensions(self) -> None:
        self.assertEqual(simplify_chord_for_beginner("Gmaj9"), "G")
        self.assertEqual(simplify_chord_for_beginner("D/F#"), "D")
        self.assertEqual(simplify_chord_for_beginner("Em7"), "Em")
        self.assertEqual(simplify_chord_for_beginner("Cmaj7"), "C")

    def test_intermediate_keeps_add9_and_sus(self) -> None:
        self.assertEqual(normalize_chord_for_intermediate("Cadd9"), "Cadd9")
        self.assertEqual(normalize_chord_for_intermediate("Dsus4"), "Dsus4")
        self.assertEqual(normalize_chord_for_intermediate("Em7"), "Em7")
        self.assertEqual(normalize_chord_for_intermediate("Gmaj9"), "Gmaj7")

    def test_advanced_preserves_full_chords(self) -> None:
        song = {
            "genre": "Pop",
            "key": "G",
            "section_order": ["Intro", "Verse 1", "Chorus"],
            "sections": {
                "Intro": ["Gmaj9", "D/F#"],
                "Verse 1": ["Em7", "Cmaj7"],
                "Chorus": ["G", "D"],
            },
        }
        _view, sections = resolve_level_chart(song, "Advanced")
        self.assertEqual(sections["Intro"], ["Gmaj9", "D/F#"])
        self.assertEqual(len(_view.get("section_order") or []), 3)


class TestChartLevelForm(unittest.TestCase):
    _FULL_ORDER = [
        "Intro",
        "Verse 1",
        "Chorus 1",
        "Turnaround",
        "Verse 2",
        "Chorus 2",
        "Bridge",
        "Guitar Solo",
        "Verse 3",
        "Final Chorus",
        "Outro",
    ]

    def test_beginner_drops_solo_and_shortens_form(self) -> None:
        picked = select_section_names_for_level(self._FULL_ORDER, "Beginner")
        self.assertIn("Intro", picked)
        self.assertIn("Verse 1", picked)
        self.assertIn("Chorus 1", picked)
        self.assertNotIn("Guitar Solo", picked)
        self.assertNotIn("Turnaround", picked)
        self.assertNotIn("Bridge", picked)
        self.assertLess(len(picked), len(self._FULL_ORDER))

    def test_intermediate_keeps_bridge_drops_solo(self) -> None:
        picked = select_intermediate_section_names(self._FULL_ORDER)
        self.assertIn("Bridge", picked)
        self.assertNotIn("Guitar Solo", picked)
        self.assertNotIn("Turnaround", picked)
        self.assertIn("Final Chorus", picked)

    def test_resolve_level_chart_filters_sections(self) -> None:
        song = {
            "genre": "Pop",
            "key": "G",
            "section_order": self._FULL_ORDER,
            "sections": {name: ["G", "C"] for name in self._FULL_ORDER},
        }
        view, sections = resolve_level_chart(song, "Beginner")
        self.assertLess(len(sections), len(self._FULL_ORDER))
        self.assertEqual(set(sections.keys()), set(view.get("section_order") or []))


if __name__ == "__main__":
    unittest.main()

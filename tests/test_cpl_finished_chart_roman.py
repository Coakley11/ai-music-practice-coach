"""Finished-song chart omits Roman numerals; editing views still show them."""

from __future__ import annotations

import unittest

from custom_progression_lab import (
    cpl_progression_bar_chart_html,
    entries_chord_tiles_html,
    song_structure_overview_html,
)


def _active() -> dict:
    entries = [{"chord": "C", "bars": 1}, {"chord": "Am", "bars": 1}, {"chord": "F", "bars": 1}, {"chord": "G", "bars": 1}]
    return {
        "name": "Demo",
        "time_signature": "4/4",
        "original_key": "C",
        "original_sections": {"Verse": entries},
    }


class TestFinishedChartRoman(unittest.TestCase):
    def test_overview_default_keeps_roman(self) -> None:
        html = song_structure_overview_html(_active(), "C")
        self.assertIn("cpl-bar-roman", html)

    def test_overview_finished_has_no_roman(self) -> None:
        html = song_structure_overview_html(_active(), "C", show_roman=False)
        self.assertNotIn("cpl-bar-roman", html)
        self.assertEqual(html.count("cpl-bar-chord-cell"), 4)

    def test_editing_views_keep_roman_when_asked(self) -> None:
        entries = [{"chord": "Fm6", "bars": 1}]
        self.assertIn("cpl-bar-roman", cpl_progression_bar_chart_html(entries, key_center="C"))
        self.assertIn("cpl-roman-label", entries_chord_tiles_html(entries, key_center="C"))

    def test_tiles_without_key_center_have_no_roman(self) -> None:
        entries = [{"chord": "Fm6", "bars": 1}, {"chord": "Db7", "bars": 1}]
        html = entries_chord_tiles_html(entries)
        self.assertNotIn("cpl-roman-label", html)
        self.assertIn("Fm6", html)
        self.assertIn("Db7", html)


if __name__ == "__main__":
    unittest.main()

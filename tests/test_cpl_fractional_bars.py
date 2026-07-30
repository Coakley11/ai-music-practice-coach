"""Tests for CPL fractional bar application."""

from __future__ import annotations

import unittest

from custom_progression_lab import (
    cpl_apply_chord_with_bars_to_session,
    default_active_progression,
)


class TestCplFractionalBars(unittest.TestCase):
    def test_half_bar_merges_with_previous(self) -> None:
        ss = {"cpl_active_progression": default_active_progression()}
        active = ss["cpl_active_progression"]
        active["original_sections"]["Verse"] = [{"chord": "C", "bars": 1}]
        ss["cpl_active_progression"] = active
        cpl_apply_chord_with_bars_to_session(
            ss,
            section_name="Verse",
            chord="G",
            bars=0.5,
            persist=False,
        )
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(len(entries), 1)
        self.assertIn("|", entries[0]["chord"])
        self.assertIn("G", entries[0]["chord"])

    def test_quarter_bar_standalone(self) -> None:
        ss = {"cpl_active_progression": default_active_progression()}
        cpl_apply_chord_with_bars_to_session(
            ss,
            section_name="Verse",
            chord="Am",
            bars=0.25,
            persist=False,
        )
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(entries[-1]["chord"], "Am:1")


if __name__ == "__main__":
    unittest.main()

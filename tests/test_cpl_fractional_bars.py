"""Tests for CPL fractional bar application."""

from __future__ import annotations

import unittest

from custom_progression_lab import (
    cpl_apply_chord_with_bars_to_session,
    default_active_progression,
)


class TestCplFractionalBars(unittest.TestCase):
    def _session(self):
        ss = {"cpl_active_progression": default_active_progression()}
        return ss

    def test_half_bar_does_not_shorten_previous_full_bar(self) -> None:
        """Adding a ½-bar chord must never silently shorten the previous chord."""
        ss = self._session()
        active = ss["cpl_active_progression"]
        active["original_sections"]["Verse"] = [{"chord": "Fm6", "bars": 1}]
        ss["cpl_active_progression"] = active
        cpl_apply_chord_with_bars_to_session(
            ss, section_name="Verse", chord="Db7", bars=0.5, persist=False,
        )
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        # Previous Fm6 stays as-is; Db7 is a new entry
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["chord"], "Fm6")
        self.assertEqual(entries[0]["bars"], 1)
        self.assertIn("Db7", entries[1]["chord"])

    def test_two_consecutive_half_bars_merge(self) -> None:
        """Two ½-bar chords should combine into one subdivided bar."""
        ss = self._session()
        cpl_apply_chord_with_bars_to_session(
            ss, section_name="Verse", chord="Db7", bars=0.5, persist=False,
        )
        cpl_apply_chord_with_bars_to_session(
            ss, section_name="Verse", chord="C7", bars=0.5, persist=False,
        )
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        # The two half-bars merge into one subdivided bar
        self.assertEqual(len(entries), 1)
        self.assertIn("|", entries[0]["chord"])
        self.assertIn("Db7", entries[0]["chord"])
        self.assertIn("C7", entries[0]["chord"])

    def test_full_bar_then_two_half_bars(self) -> None:
        """Fm6 (full) then Db7 (½) + C7 (½) → 2 entries: Fm6 + Db7:2|C7:2."""
        ss = self._session()
        active = ss["cpl_active_progression"]
        active["original_sections"]["Verse"] = [{"chord": "Fm6", "bars": 1}]
        ss["cpl_active_progression"] = active
        cpl_apply_chord_with_bars_to_session(
            ss, section_name="Verse", chord="Db7", bars=0.5, persist=False,
        )
        cpl_apply_chord_with_bars_to_session(
            ss, section_name="Verse", chord="C7", bars=0.5, persist=False,
        )
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["chord"], "Fm6")
        self.assertEqual(entries[0]["bars"], 1)
        self.assertIn("|", entries[1]["chord"])
        self.assertIn("Db7", entries[1]["chord"])
        self.assertIn("C7", entries[1]["chord"])

    def test_quarter_bar_standalone(self) -> None:
        ss = self._session()
        cpl_apply_chord_with_bars_to_session(
            ss, section_name="Verse", chord="Am", bars=0.25, persist=False,
        )
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(entries[-1]["chord"], "Am:1")

    def test_quarter_bar_does_not_shorten_previous_full_bar(self) -> None:
        """Adding ¼-bar chord must not merge into a previous full-bar chord."""
        ss = self._session()
        active = ss["cpl_active_progression"]
        active["original_sections"]["Verse"] = [{"chord": "Fm6", "bars": 1}]
        ss["cpl_active_progression"] = active
        cpl_apply_chord_with_bars_to_session(
            ss, section_name="Verse", chord="C7", bars=0.25, persist=False,
        )
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["chord"], "Fm6")
        self.assertEqual(entries[0]["bars"], 1)

    def test_quarter_merges_into_existing_partial(self) -> None:
        """¼-bar chord should merge into a previous partial-bar entry."""
        ss = self._session()
        # Start with a half-bar stub
        cpl_apply_chord_with_bars_to_session(
            ss, section_name="Verse", chord="Db7", bars=0.5, persist=False,
        )
        # Then add a quarter to the same bar
        cpl_apply_chord_with_bars_to_session(
            ss, section_name="Verse", chord="C7", bars=0.25, persist=False,
        )
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        # Both chords in one bar
        self.assertEqual(len(entries), 1)
        combined = entries[0]["chord"]
        self.assertIn("Db7", combined)
        self.assertIn("C7", combined)


if __name__ == "__main__":
    unittest.main()

"""Tests for CPL section copy/paste/duplicate."""

from __future__ import annotations

import unittest

from custom_progression_lab import (
    CPL_CLIPBOARD_KEY,
    cpl_copy_section,
    cpl_duplicate_section,
    cpl_paste_section,
    default_active_progression,
)


def _session_with_chords(
    chords: list[dict], section: str = "Verse",
) -> dict:
    ss: dict = {"cpl_active_progression": default_active_progression()}
    active = ss["cpl_active_progression"]
    active["original_sections"][section] = list(chords)
    ss["cpl_active_progression"] = active
    return ss


class TestCopySection(unittest.TestCase):
    def test_copy_stores_to_clipboard(self) -> None:
        ss = _session_with_chords([{"chord": "C", "bars": 1}, {"chord": "G", "bars": 2}])
        ok = cpl_copy_section(ss, section_name="Verse")
        self.assertTrue(ok)
        self.assertEqual(len(ss[CPL_CLIPBOARD_KEY]), 2)
        self.assertEqual(ss[CPL_CLIPBOARD_KEY][0]["chord"], "C")

    def test_copy_empty_section_returns_false(self) -> None:
        ss = _session_with_chords([])
        ok = cpl_copy_section(ss, section_name="Verse")
        self.assertFalse(ok)

    def test_copy_is_deep(self) -> None:
        chords = [{"chord": "Am", "bars": 1}]
        ss = _session_with_chords(chords)
        cpl_copy_section(ss, section_name="Verse")
        ss[CPL_CLIPBOARD_KEY][0]["chord"] = "MODIFIED"
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(entries[0]["chord"], "Am")


class TestPasteSection(unittest.TestCase):
    def test_paste_appends_to_section(self) -> None:
        ss = _session_with_chords([{"chord": "Am", "bars": 1}])
        ss[CPL_CLIPBOARD_KEY] = [{"chord": "F", "bars": 2}, {"chord": "G", "bars": 1}]
        ok = cpl_paste_section(ss, section_name="Verse")
        self.assertTrue(ok)
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[1]["chord"], "F")
        self.assertEqual(entries[2]["chord"], "G")

    def test_paste_no_clipboard_returns_false(self) -> None:
        ss = _session_with_chords([{"chord": "Am", "bars": 1}])
        ok = cpl_paste_section(ss, section_name="Verse")
        self.assertFalse(ok)

    def test_paste_into_empty_section(self) -> None:
        ss = _session_with_chords([])
        ss[CPL_CLIPBOARD_KEY] = [{"chord": "Dm", "bars": 1}]
        cpl_paste_section(ss, section_name="Chorus")
        entries = ss["cpl_active_progression"]["original_sections"]["Chorus"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["chord"], "Dm")


class TestDuplicateSection(unittest.TestCase):
    def test_duplicate_copies_to_target(self) -> None:
        ss = _session_with_chords([
            {"chord": "C", "bars": 1},
            {"chord": "Am", "bars": 2},
        ])
        ok = cpl_duplicate_section(
            ss, from_section="Verse", to_section="Chorus",
        )
        self.assertTrue(ok)
        chorus = ss["cpl_active_progression"]["original_sections"]["Chorus"]
        self.assertEqual(len(chorus), 2)
        self.assertEqual(chorus[0]["chord"], "C")
        self.assertEqual(chorus[1]["chord"], "Am")

    def test_duplicate_same_section_returns_false(self) -> None:
        ss = _session_with_chords([{"chord": "C", "bars": 1}])
        ok = cpl_duplicate_section(
            ss, from_section="Verse", to_section="Verse",
        )
        self.assertFalse(ok)

    def test_duplicate_empty_source_returns_false(self) -> None:
        ss = _session_with_chords([])
        ok = cpl_duplicate_section(
            ss, from_section="Verse", to_section="Chorus",
        )
        self.assertFalse(ok)

    def test_duplicate_is_deep_copy(self) -> None:
        ss = _session_with_chords([{"chord": "Em", "bars": 1}])
        cpl_duplicate_section(
            ss, from_section="Verse", to_section="Bridge",
        )
        bridge = ss["cpl_active_progression"]["original_sections"]["Bridge"]
        bridge[0]["chord"] = "MODIFIED"
        verse = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(verse[0]["chord"], "Em")


if __name__ == "__main__":
    unittest.main()

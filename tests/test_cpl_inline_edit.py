"""Tests for CPL inline chord editing (click-to-edit)."""

from __future__ import annotations

import unittest

from custom_progression_lab import (
    cpl_replace_chord_in_section,
    editable_chord_options_for_key,
    default_active_progression,
    cpl_apply_chord_with_bars_to_session,
)


def _session_with_chords(chords: list[dict], section: str = "Verse") -> dict:
    from custom_progression_lab import default_active_progression

    ss: dict = {"cpl_active_progression": default_active_progression()}
    active = ss["cpl_active_progression"]
    active["original_sections"][section] = list(chords)
    ss["cpl_active_progression"] = active
    return ss


class TestEditableChordOptions(unittest.TestCase):
    def test_major_key_has_diatonic_triads(self) -> None:
        opts = editable_chord_options_for_key("C")
        for ch in ("C", "Dm", "Em", "F", "G", "Am"):
            self.assertIn(ch, opts)

    def test_major_key_has_seventh_chords(self) -> None:
        opts = editable_chord_options_for_key("C")
        for ch in ("Cmaj7", "Dm7", "G7"):
            self.assertIn(ch, opts)

    def test_minor_key_has_diatonic(self) -> None:
        opts = editable_chord_options_for_key("Am")
        for ch in ("Am", "C", "Dm", "Em", "F", "G"):
            self.assertIn(ch, opts)

    def test_minor_key_has_extensions(self) -> None:
        opts = editable_chord_options_for_key("Am")
        for ch in ("Am7", "G7"):
            self.assertIn(ch, opts)

    def test_no_duplicates(self) -> None:
        opts = editable_chord_options_for_key("G")
        self.assertEqual(len(opts), len(set(opts)))

    def test_transposed_key(self) -> None:
        opts = editable_chord_options_for_key("Eb")
        self.assertIn("Eb", opts)
        self.assertIn("Bb", opts)


class TestReplaceChordInSection(unittest.TestCase):
    def test_replace_simple_chord(self) -> None:
        ss = _session_with_chords([
            {"chord": "C", "bars": 1},
            {"chord": "G", "bars": 2},
        ])
        ok = cpl_replace_chord_in_section(
            ss, section_name="Verse", index=0, new_chord="Am",
        )
        self.assertTrue(ok)
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(entries[0]["chord"], "Am")
        self.assertEqual(entries[0]["bars"], 1)
        self.assertEqual(entries[1]["chord"], "G")
        self.assertEqual(entries[1]["bars"], 2)

    def test_replace_preserves_bars(self) -> None:
        ss = _session_with_chords([{"chord": "F", "bars": 4}])
        cpl_replace_chord_in_section(
            ss, section_name="Verse", index=0, new_chord="Dm7",
        )
        entry = ss["cpl_active_progression"]["original_sections"]["Verse"][0]
        self.assertEqual(entry["chord"], "Dm7")
        self.assertEqual(entry["bars"], 4)

    def test_replace_subdivided_chord(self) -> None:
        ss = _session_with_chords([{"chord": "C:2|G:2", "bars": 1}])
        cpl_replace_chord_in_section(
            ss, section_name="Verse", index=0, new_chord="Am",
        )
        entry = ss["cpl_active_progression"]["original_sections"]["Verse"][0]
        self.assertIn("Am", entry["chord"])
        self.assertIn("G", entry["chord"])
        self.assertIn("|", entry["chord"])

    def test_out_of_bounds_returns_false(self) -> None:
        ss = _session_with_chords([{"chord": "C", "bars": 1}])
        ok = cpl_replace_chord_in_section(
            ss, section_name="Verse", index=5, new_chord="Am",
        )
        self.assertFalse(ok)

    def test_empty_chord_returns_false(self) -> None:
        ss = _session_with_chords([{"chord": "C", "bars": 1}])
        ok = cpl_replace_chord_in_section(
            ss, section_name="Verse", index=0, new_chord="",
        )
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()

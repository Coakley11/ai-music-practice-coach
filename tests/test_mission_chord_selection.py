"""Mission chord selection keyed by section position, not chord name."""

from __future__ import annotations

import unittest

from improvisation_intelligence_ui import (
    II_SELECTED_CHORD_INDEX,
    II_SELECTED_SECTION,
    _ensure_chord_selection,
)
from improvisation_motif import flatten_section_map, section_and_chord_at_global_index


class TestMissionChordSelection(unittest.TestCase):
    def test_global_index_maps_chorus_duplicate_chords(self) -> None:
        section_map = [
            ("Verse 1", ["Bm", "Em", "G", "A"]),
            ("Chorus", ["Bm", "Em", "G", "A"]),
        ]
        sec, ch = section_and_chord_at_global_index(section_map, 7)
        self.assertEqual(sec, "Chorus")
        self.assertEqual(ch, "A")

    def test_ensure_selection_keeps_chorus_a_not_verse_a(self) -> None:
        section_map = [
            ("Verse 1", ["Bm", "Em", "G", "A"]),
            ("Chorus", ["Bm", "Em", "G", "A"]),
        ]
        chords = flatten_section_map(section_map)
        session = {
            II_SELECTED_CHORD_INDEX: 7,
            "ii_selected_chord": "A",
            II_SELECTED_SECTION: "Chorus",
        }
        _ensure_chord_selection(session, chords, section_map)
        self.assertEqual(session[II_SELECTED_CHORD_INDEX], 7)
        self.assertEqual(session[II_SELECTED_SECTION], "Chorus")
        self.assertEqual(session["ii_selected_chord"], "A")


if __name__ == "__main__":
    unittest.main()

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

    def test_leftover_ab_intro_not_on_em_map_is_discarded(self) -> None:
        """Slow Dancing Em map is Em/C/G/D — leftover Ab/Intro must not pin the heading."""
        from creative_chord_selection_authority import resolve_authoritative_chord_selection

        section_map = [
            ("Intro", ["Em", "C", "G", "D"]),
            ("Verse", ["Em", "C", "G", "D"]),
        ]
        chords = flatten_section_map(section_map)
        session = {
            II_SELECTED_CHORD_INDEX: 0,
            "ii_selected_chord": "Ab",
            II_SELECTED_SECTION: "Intro",
            "display_key": "Em",
            "concert_key": "Em",
            "_mission_chord_click_authority": {
                "chord": "Ab",
                "section": "Intro",
                "chord_index": 0,
                "practice_key": "Em",
            },
            "_mission_chord_snapshot": {
                "concert_chord": "Ab",
                "section": "Intro",
                "chord_index": 0,
            },
        }
        _ensure_chord_selection(session, chords, section_map)
        self.assertNotEqual(session.get("ii_selected_chord"), "Ab")
        self.assertIn(str(session.get("ii_selected_chord") or ""), {"Em", "C", "G", "D"})
        leftover = (session.get("_mission_chord_click_authority") or {}).get("chord")
        self.assertNotEqual(leftover, "Ab")
        sym, sec, _idx = resolve_authoritative_chord_selection(
            {
                "display_key": "Em",
                "concert_key": "Em",
                "ii_selected_chord": "Ab",
                "ii_selected_section": "Intro",
                "ii_selected_chord_index": 0,
                "_mission_chord_click_authority": {
                    "chord": "Ab",
                    "section": "Intro",
                    "chord_index": 0,
                    "practice_key": "Em",
                },
            },
            section_map,
        )
        self.assertNotEqual(sym, "Ab")
        self.assertIn(sym, {"Em", "C", "G", "D"})
        self.assertNotEqual(sec, "")


if __name__ == "__main__":
    unittest.main()

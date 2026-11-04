"""So What is AABA: A (Dm7 x8), A2 (Dm7 x8), Bridge (Ebm7 x8), Final A (Dm7 x8)."""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records

ORDER = ["A Section", "A2", "Bridge", "Final A"]
EXPECT = {
    "Beginner": {"A Section": ["Dm"] * 8, "A2": ["Dm"] * 8, "Bridge": ["Ebm"] * 8, "Final A": ["Dm"] * 8},
    "Intermediate": {"A Section": ["Dm7"] * 8, "A2": ["Dm7"] * 8, "Bridge": ["Ebm7"] * 8, "Final A": ["Dm7"] * 8},
    "Advanced": {"A Section": ["Dm7"] * 8, "A2": ["Dm7"] * 8, "Bridge": ["Ebm7"] * 8, "Final A": ["Dm7"] * 8},
}


class SoWhatChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "So What"))

    def test_base_sections_are_aaba_32_bars(self) -> None:
        self.assertEqual(list(self.rec["sections"]), ORDER)
        self.assertEqual(self.rec["section_order"], ORDER)
        self.assertEqual(self.rec["sections"], EXPECT["Intermediate"])
        self.assertEqual(self.rec["key"], "Dm")

    def test_every_level_plays_all_four_sections_32_bars(self) -> None:
        for level, expected in EXPECT.items():
            view, sections = resolve_level_chart(self.rec, level)
            self.assertEqual(list(view["section_order"]) if view.get("section_order") else list(sections), ORDER, level)
            self.assertEqual(sections, expected, level)
            self.assertEqual(sum(len(v) for v in sections.values()), 32, level)

    def test_beginner_keeps_the_bridge_shift(self) -> None:
        _, sections = resolve_level_chart(self.rec, "Beginner")
        self.assertEqual(sections["Bridge"], ["Ebm"] * 8)

    def test_cells_validate_and_one_pass_length(self) -> None:
        for level, expected in EXPECT.items():
            events = sections_dict_to_events(expected, time_signature="4/4", section_order=ORDER)
            self.assertEqual(len(events), 32)
            self.assertEqual(validate_chord_events(events, time_signature="4/4"), [], level)
        beats = sum(s.weight for bars in EXPECT["Advanced"].values() for t in bars for s in parse_subdivisions(t))
        self.assertAlmostEqual(beats * 60.0 / 100, 76.8, places=6)  # fallback 100 BPM


if __name__ == "__main__":
    unittest.main()

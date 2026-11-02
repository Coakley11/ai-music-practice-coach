"""Take the A Train is AABA (32 bars), not A-B (16)."""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records

ORDER = ["A Section", "A2", "B Section", "A3"]
ADV = {
    "A Section": ["Cmaj7", "Cmaj7", "D7", "D7", "Dm7", "G7", "Cmaj7", "G7"],
    "A2": ["Cmaj7", "Cmaj7", "D7", "D7", "Dm7", "G7", "Cmaj7", "C7"],
    "B Section": ["Fmaj7", "Fmaj7", "D7", "D7", "Dm7", "G7", "Cmaj7", "G7"],
    "A3": ["Cmaj7", "Cmaj7", "D7", "D7", "Dm7", "G7", "Cmaj7", "Cmaj7"],
}
BEG = {
    "A Section": ["C", "C", "D7", "D7", "Dm", "G7", "C", "G7"],
    "A2": ["C", "C", "D7", "D7", "Dm", "G7", "C", "C7"],
    "B Section": ["F", "F", "D7", "D7", "Dm", "G7", "C", "G7"],
    "A3": ["C", "C", "D7", "D7", "Dm", "G7", "C", "C"],
}


class ATrainChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "Take the A Train"))

    def test_levels_are_aaba_32_bars(self) -> None:
        for level, expected in (("Beginner", BEG), ("Intermediate", ADV), ("Advanced", ADV)):
            view, sections = resolve_level_chart(self.rec, level)
            self.assertEqual(list(sections), ORDER, level)
            self.assertEqual(sections, expected, level)
            self.assertEqual(sum(len(v) for v in sections.values()), 32, level)

    def test_beginner_keeps_dominant_sevenths(self) -> None:
        for bars in BEG.values():
            self.assertNotIn("DD", bars)
        _, sections = resolve_level_chart(self.rec, "Beginner")
        self.assertEqual(sections["A Section"][2:4], ["D7", "D7"])

    def test_second_ending_goes_c7_into_the_bridge(self) -> None:
        self.assertEqual(self.rec["sections"]["A2"][-1], "C7")
        self.assertEqual(self.rec["sections"]["A3"][-1], "Cmaj7")

    def test_cells_validate_and_one_pass_length(self) -> None:
        for expected in (ADV, BEG):
            events = sections_dict_to_events(expected, time_signature="4/4", section_order=ORDER)
            self.assertEqual(len(events), 32)
            self.assertEqual(validate_chord_events(events, time_signature="4/4"), [])
        beats = sum(s.weight for bars in ADV.values() for t in bars for s in parse_subdivisions(t))
        self.assertAlmostEqual(beats * 60.0 / 100, 76.8, places=6)


if __name__ == "__main__":
    unittest.main()

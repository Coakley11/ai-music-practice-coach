"""All of Me (jazz standard entry): ABAC, 32 bars, two bars per chord in A and B."""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records

ORDER = ["A", "B", "A2", "C"]
A_ADV = ["Cmaj7", "Cmaj7", "E7", "E7", "A7", "A7", "Dm7", "Dm7"]
ADV = {
    "A": A_ADV,
    "B": ["E7", "E7", "Am7", "Am7", "D7", "D7", "Dm7", "G7"],
    "A2": A_ADV,
    "C": ["F6", "Fm6", "Em7", "A7", "Dm7", "G7", "C6|Ebdim7", "Dm7|G7"],
}
A_BEG = ["C", "C", "E7", "E7", "A7", "A7", "Dm", "Dm"]
BEG = {
    "A": A_BEG,
    "B": ["E7", "E7", "Am", "Am", "D7", "D7", "Dm", "G7"],
    "A2": A_BEG,
    "C": ["F", "Fm", "Em", "A7", "Dm", "G7", "C|Ebdim", "Dm|G7"],
}


class AllOfMeJazzChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(
            next(r for r in curated_song_records() if r["title"] == "All of Me" and r["artist"] == "Jazz Standard")
        )

    def test_exact_levels(self) -> None:
        cv = self.rec["chart_versions"]
        self.assertEqual(cv["Advanced"], ADV)
        self.assertEqual(cv["Intermediate"], ADV)
        self.assertEqual(cv["Beginner"], BEG)
        self.assertEqual(self.rec["sections"], ADV)
        self.assertEqual(self.rec["section_order"], ORDER)
        self.assertEqual(self.rec["key"], "C")

    def test_pop_entry_untouched(self) -> None:
        pop = next(r for r in curated_song_records() if r["title"] == "All of Me" and r["artist"] == "John Legend")
        self.assertEqual(pop["key"], "Em")

    def test_beginner_keeps_secondary_dominants_not_doubled_roots(self) -> None:
        _, sections = resolve_level_chart(self.rec, "Beginner")
        cells = [c for bars in sections.values() for c in bars]
        self.assertIn("E7", cells)
        self.assertIn("A7", cells)
        for bad in ("EE", "AA", "DD", "GG", "Ebm", "C|Ebm"):
            self.assertNotIn(bad, cells)

    def test_all_levels_full_form_32_bars(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            view, sections = resolve_level_chart(self.rec, level)
            self.assertEqual(list(sections), ORDER, level)
            self.assertEqual(sum(len(v) for v in sections.values()), 32, level)

    def test_cells_validate_and_duration(self) -> None:
        for chart in (ADV, BEG):
            events = sections_dict_to_events(chart, time_signature="4/4", section_order=ORDER)
            self.assertEqual(validate_chord_events(events, time_signature="4/4"), [])
        beats = sum(s.weight for bars in ADV.values() for t in bars for s in parse_subdivisions(t))
        self.assertAlmostEqual(beats * 60.0 / 100, 76.8, places=6)


if __name__ == "__main__":
    unittest.main()

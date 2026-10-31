"""Satin Doll: Abm7|Db7 in bar 6 of every A, Am7|D7 in bridge bars 5-6, plain C bar 7.

Source classification (sources: Bruno Jazz, jazz-guitar-licks.com real-book
version, Guitar Composer's Toolbox, Jazz Library):

HIGH confidence (all consulted editions agree):
  * A bar 6 = Abm7|Db7 (every A); bridge bars 5-6 = Am7|D7;
  * A / A3 bar 7 = plain Cmaj7 (three sources print plain C).

Edition choices (sources differ; the catalog states one reading):
  * A bar 8 = Em7b5|A7b9 (Jazz Library; Bruno Jazz prints a plain A7);
  * bridge bar 7 = Dm7|G7 (Jazz Library; Bruno Jazz prints Dm7);
  * bridge bar 8 (Dm7|G7 vs Em7|A7 vs G7|A7) and the Turnaround tag are
    edition-dependent and were deliberately NOT changed from the prior chart.
"""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records

ORDER = ["A", "A2", "B (Bridge)", "A3", "Turnaround"]
A_HEAD = ["Dm7|G7", "Dm7|G7", "Em7|A7", "Em7|A7", "Am7|D7", "Abm7|Db7"]
ADV = {
    "A": A_HEAD + ["Cmaj7", "Em7b5|A7b9"],
    "A2": A_HEAD + ["Cmaj7", "Cmaj7"],
    "B (Bridge)": ["Gm7|C7", "Gm7|C7", "Fmaj7", "Fmaj7", "Am7|D7", "Am7|D7", "Dm7|G7", "Dm7|G7"],
    "A3": A_HEAD + ["Cmaj7", "Cmaj7"],
    "Turnaround": ["Dm7|G7", "Em7|A7", "Am7|D7", "G7"],
}
B_HEAD = ["Dm|G", "Dm|G", "Em|A", "Em|A", "Am|D", "Abm|Db"]
BEG = {
    "A": B_HEAD + ["C", "Em|A"],
    "A2": B_HEAD + ["C", "C"],
    "B (Bridge)": ["Gm|C", "Gm|C", "F", "F", "Am|D", "Am|D", "Dm|G", "Dm|G"],
    "A3": B_HEAD + ["C", "C"],
    "Turnaround": ["Dm|G", "Em|A", "Am|D", "G"],
}


class SatinDollChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "Satin Doll"))

    def test_explicit_charts(self) -> None:
        cv = self.rec["chart_versions"]
        self.assertEqual(cv["Advanced"], ADV)
        self.assertEqual(cv["Intermediate"], ADV)
        self.assertEqual(cv["Beginner"], BEG)
        self.assertEqual(self.rec["sections"], ADV)
        self.assertEqual(self.rec["section_order"], ORDER)

    def test_bar_six_is_the_chromatic_ii_v_in_every_a(self) -> None:
        for level, chart in (("Advanced", ADV), ("Beginner", BEG)):
            for name in ("A", "A2", "A3"):
                self.assertEqual(self.rec["chart_versions"][level][name][5], chart[name][5])
        self.assertEqual(self.rec["chart_versions"]["Advanced"]["A2"][5], "Abm7|Db7")

    def test_level_views_are_whole_sections_and_in_sync(self) -> None:
        expect = {"Beginner": (ORDER, 36), "Intermediate": (ORDER[:4], 32), "Advanced": (ORDER, 36)}
        for level, (order, bars) in expect.items():
            view, sections = resolve_level_chart(self.rec, level)
            self.assertEqual(list(sections), order, level)
            self.assertEqual(sum(len(v) for v in sections.values()), bars, level)

    def test_cells_validate_and_duration(self) -> None:
        for chart in (ADV, BEG):
            events = sections_dict_to_events(chart, time_signature="4/4", section_order=ORDER)
            self.assertEqual(validate_chord_events(events, time_signature="4/4"), [])
        beats = sum(s.weight for bars in ADV.values() for t in bars for s in parse_subdivisions(t))
        self.assertAlmostEqual(beats * 60.0 / 128, 67.5, places=6)


if __name__ == "__main__":
    unittest.main()

"""Meditation (Jobim): the published 56-bar form, A A B A + Coda (D.C. al Coda).

The catalog held a 14-bar chart whose A bars 3-8 (Bm7b5 E7 Am7 D7 Dm7 G7) are
not the published A (B7 x2, Cmaj7 x2, Em7 A7, Dm7 x2, Fm6 x2, Em7 A7, Dm7 G7).
Sources: Learn Jazz Standards chart (56 bars), Guitar Composer Toolbox
(A bar-for-bar identical), standardrepertoire.com (56 bars).
"""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import keeps_full_form, resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records

ORDER = ["A Section", "A Section (Repeat)", "B Section", "A Section (to Coda)", "Coda"]
BARS = {"A Section": 16, "A Section (Repeat)": 16, "B Section": 8, "A Section (to Coda)": 12, "Coda": 4}
A_INT = ["Cmaj7", "Cmaj7", "B7", "B7", "Cmaj7", "Cmaj7", "Em7", "A7",
         "Dm7", "Dm7", "Fm6", "Fm6", "Em7", "A7", "Dm7", "G7"]
A_BEG = ["C", "C", "B7", "B7", "C", "C", "Em", "A7",
         "Dm", "Dm", "Fm", "Fm", "Em", "A7", "Dm", "G7"]
A_ADV = ["Cmaj9", "Cmaj9", "B7", "B7", "Cmaj9", "Cmaj9", "Em7", "A7b13",
         "Dm9", "Dm9", "Fm6", "Fm6", "Em7", "A7b13", "Dm9", "G7#5"]
B_INT = ["Fmaj7", "Fmaj7", "Fm6", "Fm6", "Em7", "Ebdim7", "Dm7", "G7"]
CODA_INT = ["Em7|A7", "Dm7|G7", "Cmaj7", "Dm7|G7"]
LEVELS = ("Beginner", "Intermediate", "Advanced")


class MeditationChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "Meditation"))

    def test_intermediate_is_the_published_chart(self) -> None:
        s = self.rec["chart_versions"]["Intermediate"]
        self.assertEqual(list(s), ORDER)
        self.assertEqual(s["A Section"], A_INT)
        self.assertEqual(s["A Section (Repeat)"], A_INT)
        self.assertEqual(s["B Section"], B_INT)
        self.assertEqual(s["A Section (to Coda)"], A_INT[:12])
        self.assertEqual(s["Coda"], CODA_INT)
        self.assertEqual(self.rec["sections"], s)

    def test_beginner_and_advanced_same_bars(self) -> None:
        beg = self.rec["chart_versions"]["Beginner"]
        adv = self.rec["chart_versions"]["Advanced"]
        self.assertEqual(beg["A Section"], A_BEG)
        self.assertEqual(beg["B Section"], ["F", "F", "Fm", "Fm", "Em", "Ebdim", "Dm", "G7"])
        self.assertEqual(beg["Coda"], ["Em|A7", "Dm|G7", "C", "Dm|G7"])
        self.assertEqual(adv["A Section"], A_ADV)
        self.assertEqual(adv["Coda"][2], "Cmaj9")
        for lv in ("Beginner", "Advanced"):
            self.assertEqual({k: len(v) for k, v in self.rec["chart_versions"][lv].items()}, BARS, lv)

    def test_old_wrong_bars_are_gone(self) -> None:
        for lv in LEVELS:
            flat = [c for bars in self.rec["chart_versions"][lv].values() for c in bars]
            for bad in ("Bm7b5", "E7", "Bm", "Am7", "D7"):
                self.assertNotIn(bad, flat, (lv, bad))

    def test_all_levels_play_the_full_56_bar_form(self) -> None:
        for lv in LEVELS:
            _view, sections = resolve_level_chart(self.rec, lv)
            self.assertEqual(list(sections), ORDER, lv)
            self.assertEqual(sum(len(v) for v in sections.values()), 56, lv)
        self.assertTrue(keeps_full_form(self.rec, "Beginner"))
        self.assertTrue(keeps_full_form(self.rec, "Intermediate"))

    def test_events_validate(self) -> None:
        for lv in LEVELS:
            events = sections_dict_to_events(
                self.rec["chart_versions"][lv], time_signature="4/4", section_order=ORDER
            )
            self.assertEqual(len(events), 59, lv)  # 56 bars; 3 split Coda bars give 2 events each
            self.assertEqual(validate_chord_events(events, time_signature="4/4"), [], lv)

    def test_split_bars_total_four_beats(self) -> None:
        for lv in LEVELS:
            for bar in self.rec["chart_versions"][lv]["Coda"]:
                self.assertAlmostEqual(sum(p.weight for p in parse_subdivisions(bar)), 4.0)

    def test_identity(self) -> None:
        self.assertEqual((self.rec["key"], self.rec["artist"]), ("C", "Antonio Carlos Jobim"))


if __name__ == "__main__":
    unittest.main()

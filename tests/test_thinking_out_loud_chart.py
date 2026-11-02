"""Thinking Out Loud (Ed Sheeran): default tempo 79 BPM, not 75.

Sources: Hooktheory TheoryTab (79 BPM, 4/4, D major); Wikipedia infobox (79 BPM);
Musicnotes listings print "around 80". Metadata-only: chart cells untouched.
Chart held (UNVERIFIED): recording 4:41 = 281 s = ~94 bars at 79 BPM; catalog
has 86/100/143 bars (Advanced adds Turnaround 8, Ending Tag 7, Instrumental 16
without a score). No anticipation/push evidence, none encoded.
"""
from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

BARS = {"Beginner": 86, "Intermediate": 100, "Advanced": 143}


class ThinkingOutLoudTempoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(
            next(r for r in curated_song_records() if r["title"] == "Thinking Out Loud")
        )

    def test_bpm_and_meter(self) -> None:
        ext = self.rec["extensions"]
        self.assertEqual(ext["default_bpm"], 79)
        self.assertEqual(ext["time_signature"], "4/4")
        self.assertEqual(self.rec["key"], "C")
        self.assertIn("79 BPM", ext["arrangement_notes"])
        self.assertNotIn("75 BPM", ext["arrangement_notes"])

    def test_cells_unchanged_and_duration(self) -> None:
        for level, n in BARS.items():
            _v, secs = resolve_level_chart(self.rec, level)
            self.assertEqual(sum(len(v) for v in secs.values()), n, level)
        self.assertAlmostEqual(143 * meter_timing(79, "4/4").bar_sec, 143 * 240 / 79, places=6)  # 434 s
        _v, adv = resolve_level_chart(self.rec, "Advanced")
        self.assertEqual(adv["Verse 1"][:4], ["C", "C/E", "F", "G"])
        self.assertEqual(adv["Pre-Chorus 1"][:3], ["Dm", "G", "C"])


if __name__ == "__main__":
    unittest.main()

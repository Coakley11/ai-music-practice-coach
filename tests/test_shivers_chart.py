"""Shivers (Ed Sheeran): default tempo 141 BPM, 4/4, not the 100 BPM fallback.

Sources for 141: Hooktheory (141 BPM, B minor, 4/4) and Musicnotes official Ed Sheeran piano/vocal/guitar edition MN0241810 (fast driving beat, 141; also MN0242750 and MN0241394 at 141). Quarter-note pulse (upbeat dance-pop; no half-time reading).

Metadata-only change: the 12-bar rehearsal skeleton is unchanged (Hooktheory lists no per-section chords or bar counts (only i VI III VII); section lengths MED, held).

One-pass seconds (4/4 bar = 1.7021 s):
  before (fallback 100): Beginner 12 bars 28.8 s, Intermediate 12 bars 28.8 s, Advanced 12 bars 28.8 s
  after  (141 BPM): Beginner 20.4 s, Intermediate 20.4 s, Advanced 20.4 s
vs 207 s recording (Wikipedia infobox 3:27 (single)).
"""
from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

BARS = {'Beginner': 12, 'Intermediate': 12, 'Advanced': 12}
RECORDING_SEC = 207.0


class ShiversTempoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == 'Shivers'))

    def test_tempo_and_meter(self) -> None:
        ext = self.rec["extensions"]
        self.assertEqual(ext["default_bpm"], 141)
        self.assertEqual(ext["time_signature"], '4/4')
        self.assertEqual(self.rec["key"], 'Bm')

    def test_cells_unchanged_and_one_pass_seconds(self) -> None:
        bar = meter_timing(141, '4/4').bar_sec
        self.assertAlmostEqual(bar, 1.702127659574468, places=9)
        for level, n in BARS.items():
            _v, secs = resolve_level_chart(self.rec, level)
            self.assertEqual(sum(len(v) for v in secs.values()), n, level)
        _v, adv = resolve_level_chart(self.rec, "Advanced")
        self.assertEqual(adv['Verse'], ['Bm', 'G', 'D', 'A'])
        self.assertEqual(adv['Pre-Chorus'], ['Bm', 'G', 'D', 'A'])
        self.assertEqual(adv['Chorus'], ['Bm', 'G', 'D', 'A'])
        self.assertAlmostEqual(BARS["Advanced"] * bar, 20.426, places=2)
        self.assertAlmostEqual(BARS["Advanced"] * bar / RECORDING_SEC, 0.099, places=2)


if __name__ == "__main__":
    unittest.main()

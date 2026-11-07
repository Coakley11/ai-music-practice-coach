"""Paradise (Coldplay): default tempo 140 BPM, 4/4, not the 100 BPM fallback.

Sources for 140: Hooktheory (140 BPM, 4/4, F major) and the UBC audio-feature database (139.7 for the original). Album version is 4:37 (Wikipedia; single 4:38, radio edit 4:20). Quarter-note pulse: four-on-the-floor dance-rock, no half-time reading.

Metadata-only change: the 24-bar rehearsal skeleton is unchanged (Hooktheory gives progressions only (intro ii7-V-vi-I-V, verse vi7-IVsus2-I-V6, pre-chorus ii7-IV(add9)-I-V, chorus ii-IV(add9)-I-V6) with no bar counts; these differ from the catalog skeleton, MED, held).

One-pass seconds (4/4 bar = 1.7143 s):
  before (fallback 100): Beginner 20 bars 48.0 s, Intermediate/Advanced 24 bars 57.6 s
  after  (140 BPM): Beginner 34.3 s, Intermediate/Advanced 41.1 s
vs 277 s recording (Wikipedia album version 4:37).
"""
from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

BARS = {'Beginner': 20, 'Intermediate': 24, 'Advanced': 24}
RECORDING_SEC = 277.0


class ParadiseTempoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == 'Paradise'))

    def test_tempo_and_meter(self) -> None:
        ext = self.rec["extensions"]
        self.assertEqual(ext["default_bpm"], 140)
        self.assertEqual(ext["time_signature"], '4/4')
        self.assertEqual(self.rec["key"], 'F')

    def test_cells_unchanged_and_one_pass_seconds(self) -> None:
        bar = meter_timing(140, '4/4').bar_sec
        self.assertAlmostEqual(bar, 1.7142857142857142, places=9)
        for level, n in BARS.items():
            _v, secs = resolve_level_chart(self.rec, level)
            self.assertEqual(sum(len(v) for v in secs.values()), n, level)
        _v, adv = resolve_level_chart(self.rec, "Advanced")
        self.assertEqual(adv['Verse'], ['F', 'Gm', 'Bb', 'Dm'])
        self.assertEqual(adv['Chorus'], ['Bb', 'F', 'C', 'Dm'])
        self.assertEqual(adv['Pre-Chorus'], ['Gm', 'Bb', 'F', 'C'])
        self.assertAlmostEqual(BARS["Advanced"] * bar, 41.143, places=2)
        self.assertAlmostEqual(BARS["Advanced"] * bar / RECORDING_SEC, 0.149, places=2)


if __name__ == "__main__":
    unittest.main()

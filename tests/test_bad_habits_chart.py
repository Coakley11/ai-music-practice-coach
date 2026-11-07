"""Bad Habits (Ed Sheeran): default tempo 126 BPM, 4/4, not the 100 BPM fallback.

Sources for 126: Hooktheory (126 BPM, B minor, 4/4; verse/pre-chorus i-III-VI-VII, chorus/bridge/instrumental i-III-VI-VII-i) and Wikipedia, which cites the published sheet music (126 BPM, B minor). Quarter-note pulse.

Metadata-only change: the 16-bar rehearsal skeleton is unchanged (Hooktheory gives no bar counts; chord loop agrees with the catalog Bm G D A, but section lengths are MED, held).

One-pass seconds (4/4 bar = 1.9048 s):
  before (fallback 100): Beginner 12 bars 28.8 s, Intermediate 16 bars 38.4 s, Advanced 16 bars 38.4 s
  after  (126 BPM): Beginner 22.9 s, Intermediate 30.5 s, Advanced 30.5 s
vs 231 s recording (Wikipedia original single 3:51 (acoustic 3:52, BMTH remix 4:10)).
"""
from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

BARS = {'Beginner': 12, 'Intermediate': 16, 'Advanced': 16}
RECORDING_SEC = 231.0


class BadHabitsTempoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == 'Bad Habits'))

    def test_tempo_and_meter(self) -> None:
        ext = self.rec["extensions"]
        self.assertEqual(ext["default_bpm"], 126)
        self.assertEqual(ext["time_signature"], '4/4')
        self.assertEqual(self.rec["key"], 'Bm')

    def test_cells_unchanged_and_one_pass_seconds(self) -> None:
        bar = meter_timing(126, '4/4').bar_sec
        self.assertAlmostEqual(bar, 1.9047619047619047, places=9)
        for level, n in BARS.items():
            _v, secs = resolve_level_chart(self.rec, level)
            self.assertEqual(sum(len(v) for v in secs.values()), n, level)
        _v, adv = resolve_level_chart(self.rec, "Advanced")
        self.assertEqual(adv['Verse'], ['Bm', 'G', 'D', 'A'])
        self.assertEqual(adv['Pre-Chorus'], ['Bm', 'G', 'D', 'A'])
        self.assertEqual(adv['Chorus'], ['Bm', 'G', 'D', 'A'])
        self.assertEqual(adv['Bridge'], ['G', 'A', 'Bm', 'D'])
        self.assertAlmostEqual(BARS["Advanced"] * bar, 30.476, places=2)
        self.assertAlmostEqual(BARS["Advanced"] * bar / RECORDING_SEC, 0.132, places=2)


if __name__ == "__main__":
    unittest.main()

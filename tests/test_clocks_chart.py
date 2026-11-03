"""Clocks (Coldplay): default tempo 131 BPM, 4/4, not the 100 BPM fallback.

Sources for 131: Hooktheory (131 BPM, 4/4, Eb Mixolydian I-v-ii7 ostinato), songbpm.com (131), University of Waterloo audio-feature database (131.0 for the album version); Musicnotes prints a swing-style 126 marking for its arrangement and a tab site's 200 is a notation setting. Album version is 5:07 (Wikipedia; radio edit 4:16, single 5:09). The quarter-note pulse is 131 (no half-time reading: the piano ostinato is eighth-note driven).

Metadata-only change: the 20-bar rehearsal skeleton is unchanged (Hooktheory gives no bar counts; Hooktheory bridge is Db (IV7sus2-I-V(add6)) while the catalog bridge reads Db Ab Eb Bbm, MED, held).

One-pass seconds (4/4 bar = 1.8321 s):
  before (fallback 100): Beginner 12 bars 28.8 s, Intermediate 16 bars 38.4 s, Advanced 20 bars 48.0 s
  after  (131 BPM): Beginner 22.0 s, Intermediate 29.3 s, Advanced 36.6 s
vs 307 s recording (Wikipedia album version 5:07).
"""
from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

BARS = {'Beginner': 12, 'Intermediate': 16, 'Advanced': 20}
RECORDING_SEC = 307.0


class ClocksTempoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == 'Clocks'))

    def test_tempo_and_meter(self) -> None:
        ext = self.rec["extensions"]
        self.assertEqual(ext["default_bpm"], 131)
        self.assertEqual(ext["time_signature"], '4/4')
        self.assertEqual(self.rec["key"], 'Eb')

    def test_cells_unchanged_and_one_pass_seconds(self) -> None:
        bar = meter_timing(131, '4/4').bar_sec
        self.assertAlmostEqual(bar, 1.83206106870229, places=9)
        for level, n in BARS.items():
            _v, secs = resolve_level_chart(self.rec, level)
            self.assertEqual(sum(len(v) for v in secs.values()), n, level)
        _v, adv = resolve_level_chart(self.rec, "Advanced")
        self.assertEqual(adv['Intro / Piano Riff'], ['Eb', 'Bbm', 'Fm', 'Fm'])
        self.assertEqual(adv['Chorus'], ['Ab', 'Eb', 'Bbm', 'Fm'])
        self.assertEqual(adv['Bridge'], ['Db', 'Ab', 'Eb', 'Bbm'])
        self.assertAlmostEqual(BARS["Advanced"] * bar, 36.641, places=2)
        self.assertAlmostEqual(BARS["Advanced"] * bar / RECORDING_SEC, 0.119, places=2)


if __name__ == "__main__":
    unittest.main()

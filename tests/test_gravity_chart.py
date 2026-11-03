"""Gravity (John Mayer): default tempo 42 BPM, 6/8, not the 100 BPM fallback.

Meter and tempo come from two published scores plus Hooktheory: Musicnotes Piano/Vocal/Chords MN0109828 (6/8, 'Slowly, in 2', dotted-quarter = 40), Musicnotes Easy Guitar TAB MN0100066 (6/8, 'Slowly, in 2', 42) and Hooktheory (6/8, 125 = eighth-note count, i.e. 41.7 dotted-quarters). The app's 6/8 BPM unit is the dotted-quarter pulse (songs/meter.py), so 42 is the pulse-unit tempo; one chord per 6/8 bar is two dotted-quarter beats. Continuum album track is 4:05 (Wikipedia infobox, UNVERIFIED as album-edit).

Metadata-only change: the 32-bar rehearsal skeleton is unchanged (no bar-counted score was found; the form (verse/chorus/solo lengths) is MED, held; 16/16/32 bars).

One-pass seconds (6/8 bar = 2.8571 s):
  before (fallback 100): Beginner/Intermediate 16 bars 38.4 s, Advanced 32 bars 76.8 s (as 4/4 at 100)
  after  (42 BPM): 6/8 dotted-quarter 42: Beginner/Intermediate 45.7 s, Advanced 91.4 s
vs 245 s recording (Wikipedia infobox 4:05, album unverified).
"""
from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

BARS = {'Beginner': 16, 'Intermediate': 16, 'Advanced': 32}
RECORDING_SEC = 245.0


class GravityMeterTempoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == 'Gravity'))

    def test_tempo_and_meter(self) -> None:
        ext = self.rec["extensions"]
        self.assertEqual(ext["default_bpm"], 42)
        self.assertEqual(ext["time_signature"], '6/8')
        self.assertEqual(self.rec["key"], 'G')

    def test_cells_unchanged_and_one_pass_seconds(self) -> None:
        bar = meter_timing(42, '6/8').bar_sec
        self.assertAlmostEqual(bar, 2.857142857142857, places=9)
        for level, n in BARS.items():
            _v, secs = resolve_level_chart(self.rec, level)
            self.assertEqual(sum(len(v) for v in secs.values()), n, level)
        _v, adv = resolve_level_chart(self.rec, "Advanced")
        self.assertEqual(adv['Intro / Verse Groove'], ['G6', 'Cmaj9/G', 'G6', 'Cmaj9/G'])
        self.assertEqual(adv['Chorus'], ['Em9', 'Cmaj9', 'G/D', 'D13sus', 'Em9', 'Cmaj9', 'G6', 'D13'])
        self.assertAlmostEqual(BARS["Advanced"] * bar, 91.429, places=2)
        self.assertAlmostEqual(BARS["Advanced"] * bar / RECORDING_SEC, 0.373, places=2)


if __name__ == "__main__":
    unittest.main()

"""Yellow (Coldplay): default tempo 87 BPM, 4/4, not the 100 BPM fallback.

Sources for ~87: Hooktheory (87 BPM, 4/4; outro 86), Wikipedia (88 BPM), tab sites (86). The album track is 4:29 (Wikipedia; CD single 4:31). Quarter-note pulse; the band famously struggled to settle on tempo (Wikipedia), hence 86-88.

Metadata-only change: the 28-bar rehearsal skeleton is unchanged (Hooktheory prints no bar counts; chord form I-iii6/5-Vsus2(add6)-ii6/5-IV7 for intro/outro and verse I-iii6/5-IV7 differs from the catalog's B F#/A# E B skeleton, MED, held).

One-pass seconds (4/4 bar = 2.7586 s):
  before (fallback 100): Beginner 24 bars 57.6 s, Intermediate/Advanced 28 bars 67.2 s
  after  (87 BPM): Beginner 66.2 s, Intermediate/Advanced 77.2 s
vs 269 s recording (Wikipedia infobox 4:29).
"""
from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

BARS = {'Beginner': 24, 'Intermediate': 28, 'Advanced': 28}
RECORDING_SEC = 269.0


class YellowTempoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == 'Yellow'))

    def test_tempo_and_meter(self) -> None:
        ext = self.rec["extensions"]
        self.assertEqual(ext["default_bpm"], 87)
        self.assertEqual(ext["time_signature"], '4/4')
        self.assertEqual(self.rec["key"], 'B')

    def test_cells_unchanged_and_one_pass_seconds(self) -> None:
        bar = meter_timing(87, '4/4').bar_sec
        self.assertAlmostEqual(bar, 2.7586206896551726, places=9)
        for level, n in BARS.items():
            _v, secs = resolve_level_chart(self.rec, level)
            self.assertEqual(sum(len(v) for v in secs.values()), n, level)
        _v, adv = resolve_level_chart(self.rec, "Advanced")
        self.assertEqual(adv['Verse'], ['B', 'F#/A#', 'E', 'B'])
        self.assertEqual(adv['Chorus'], ['E', 'B', 'F#sus4', 'F#', 'E', 'B', 'F#', 'E'])
        self.assertAlmostEqual(BARS["Advanced"] * bar, 77.241, places=2)
        self.assertAlmostEqual(BARS["Advanced"] * bar / RECORDING_SEC, 0.287, places=2)


if __name__ == "__main__":
    unittest.main()

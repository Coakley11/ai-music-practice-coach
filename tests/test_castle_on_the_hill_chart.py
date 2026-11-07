"""Castle on the Hill (Ed Sheeran): default tempo 135 BPM, 4/4, not the 100 BPM fallback.

Sources for 135: Hooktheory (135 BPM, 4/4, chorus I-IV-vi-V = D G Bm A), karaoke-version.com (original tempo 135), Musicnotes TutorialsByHugo arrangement (135, 4/4, D), a piano-lesson site (135); klang.io and SFR Beats print 136; Super Simple Piano's 130-132 are simplified arrangements; a ukulele site's 230 is a doubling error. Quarter-note pulse.

Metadata-only change: the 16-bar rehearsal skeleton is unchanged (Hooktheory shows only the chorus loop (64 beats of melody, no per-section bars); verse/pre-chorus/bridge lengths MED, held).

One-pass seconds (4/4 bar = 1.7778 s):
  before (fallback 100): Beginner 12 bars 28.8 s, Intermediate 16 bars 38.4 s, Advanced 16 bars 38.4 s
  after  (135 BPM): Beginner 21.3 s, Intermediate 28.4 s, Advanced 28.4 s
vs 261 s recording (Wikipedia infobox 4:21 (album track)).
"""
from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

BARS = {'Beginner': 12, 'Intermediate': 16, 'Advanced': 16}
RECORDING_SEC = 261.0


class CastleOnTheHillTempoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == 'Castle on the Hill'))

    def test_tempo_and_meter(self) -> None:
        ext = self.rec["extensions"]
        self.assertEqual(ext["default_bpm"], 135)
        self.assertEqual(ext["time_signature"], '4/4')
        self.assertEqual(self.rec["key"], 'D')

    def test_cells_unchanged_and_one_pass_seconds(self) -> None:
        bar = meter_timing(135, '4/4').bar_sec
        self.assertAlmostEqual(bar, 1.7777777777777777, places=9)
        for level, n in BARS.items():
            _v, secs = resolve_level_chart(self.rec, level)
            self.assertEqual(sum(len(v) for v in secs.values()), n, level)
        _v, adv = resolve_level_chart(self.rec, "Advanced")
        self.assertEqual(adv['Verse'], ['D', 'G', 'Bm', 'A'])
        self.assertEqual(adv['Pre-Chorus'], ['G', 'A', 'Bm', 'D'])
        self.assertEqual(adv['Chorus'], ['D', 'G', 'Bm', 'A'])
        self.assertEqual(adv['Bridge'], ['G', 'D', 'A', 'Bm'])
        self.assertAlmostEqual(BARS["Advanced"] * bar, 28.444, places=2)
        self.assertAlmostEqual(BARS["Advanced"] * bar / RECORDING_SEC, 0.109, places=2)


if __name__ == "__main__":
    unittest.main()

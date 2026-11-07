"""Fix You (Coldplay): default tempo is 69 BPM, not the 100 BPM fallback.

Sources for ~69: Hooktheory (69 BPM, 4/4), Wikipedia infobox/composition (69 BPM, E-flat,
4/4), Musicnotes lead sheet (quarter = 70) and Super Simple Piano (70); one further site
prints 67. 138 BPM (Tunebat-style analyzers) is the double-time count of the same ballad;
the felt pulse is the slow quarter note, so 69 is the pulse-unit tempo. Album version is
4:54 (Wikipedia; the plan's 4:55 is within a second).

Metadata-only change: the 24-bar rehearsal skeleton is unchanged because no source with
bar counts was found (Hooktheory prints no bar counts; heartwoodguitar's capo-3 chart is
line-based with unclear beat units), so the real form (organ intro, long verses, chorus,
guitar-riff and bridge builds, piano outro) is HELD (MED).

One-pass seconds at the 4/4 bar of 4 x 60/BPM:
  before (fallback 100): Beginner 20 bars 48.0 s, Intermediate/Advanced 24 bars 57.6 s
  after  (69 BPM):       Beginner 69.6 s, Intermediate/Advanced 83.5 s
vs 294 s recording: ratio 0.24 / 0.28 (still skeleton; form is the remaining defect).
"""
from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

BARS = {"Beginner": 20, "Intermediate": 24, "Advanced": 24}
RECORDING_SEC = 294.0


class FixYouTempoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "Fix You"))

    def test_tempo_meter_groove(self) -> None:
        ext = self.rec["extensions"]
        self.assertEqual(ext["default_bpm"], 69)
        self.assertEqual(ext["time_signature"], "4/4")
        self.assertEqual(ext["default_groove"], "Ballad")
        self.assertEqual(self.rec["key"], "Eb")

    def test_cells_unchanged_and_one_pass_seconds(self) -> None:
        bar = meter_timing(69, "4/4").bar_sec
        self.assertAlmostEqual(bar, 240.0 / 69, places=9)
        for level, n in BARS.items():
            _v, secs = resolve_level_chart(self.rec, level)
            self.assertEqual(sum(len(v) for v in secs.values()), n, level)
        _v, adv = resolve_level_chart(self.rec, "Advanced")
        self.assertEqual(adv["Verse"], ["Eb", "Gm", "Cm", "Bb"])
        self.assertEqual(adv["Chorus"], ["Ab", "Eb", "Bb", "Cm"])
        self.assertAlmostEqual(24 * bar, 83.478, places=2)
        self.assertAlmostEqual(24 * bar / RECORDING_SEC, 0.284, places=2)


if __name__ == "__main__":
    unittest.main()

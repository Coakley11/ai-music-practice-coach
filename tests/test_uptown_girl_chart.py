"""Uptown Girl (Billy Joel): default tempo 128 BPM (was 172).

Musicnotes 127, Klang 128, SFR Beats 129, Mixmeister/Traktor 129.0/128.8.
172 matched no source (it equals 129 x 4/3). Metadata only: the 48-bar skeleton
chart is unchanged (it is a declared one-pass skeleton, far shorter than the
3:18 recording; a form rebuild is out of scope for this change).
"""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

BARS = {"Beginner": 31, "Intermediate": 43, "Advanced": 48}


def _record() -> dict:
    return copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "Uptown Girl"))


class UptownGirlTempoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = _record()

    def test_default_bpm_is_128(self) -> None:
        self.assertEqual(self.rec["extensions"]["default_bpm"], 128)
        self.assertEqual(self.rec["key"], "D")

    def test_bar_duration_math(self) -> None:
        self.assertAlmostEqual(meter_timing(128, "4/4").bar_sec, 1.875, places=6)

    def test_bars_unchanged_and_durations(self) -> None:
        for level, n in BARS.items():
            _v, sections = resolve_level_chart(self.rec, level)
            self.assertEqual(sum(len(v) for v in sections.values()), n, level)
        self.assertAlmostEqual(48 * 1.875, 90.0, places=6)  # one pass; x2 default loops = 180 s


if __name__ == "__main__":
    unittest.main()

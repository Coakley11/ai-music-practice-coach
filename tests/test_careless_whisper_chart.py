"""Careless Whisper (George Michael): add default tempo 76 BPM.

Musicnotes q = 76 (4/4, "Moderately"), Hooktheory 77. The song had no
default_bpm so the app fell back to 100 (31% too fast). Metadata only: the
44-bar skeleton chart is unchanged (a declared simplified form).
"""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

BARS = {"Beginner": 36, "Intermediate": 44, "Advanced": 44}


def _record() -> dict:
    return copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "Careless Whisper"))


class CarelessWhisperTempoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = _record()

    def test_default_bpm_is_76(self) -> None:
        self.assertEqual(self.rec["extensions"]["default_bpm"], 76)
        self.assertEqual(self.rec["key"], "Dm")

    def test_bars_unchanged_and_durations(self) -> None:
        for level, n in BARS.items():
            _v, sections = resolve_level_chart(self.rec, level)
            self.assertEqual(sum(len(v) for v in sections.values()), n, level)
        self.assertAlmostEqual(44 * meter_timing(76, "4/4").bar_sec, 44 * 240 / 76, places=6)  # 138.9 s


if __name__ == "__main__":
    unittest.main()

"""Vienna (Billy Joel): BPM is the quarter-note figure 126, not the half-note 63.

Musicnotes MN0223309 prints "Slowly, with a slight lilt" q = 126; the other
edition (MN0266445) prints h = 63. The catalog had typed the half-note figure
into a quarter-note field, doubling every bar. Metadata only; cells unchanged.
"""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

BARS = {"Beginner": 78, "Intermediate": 92, "Advanced": 115}
RECORDING_SECONDS = 214  # 3:34


def _record() -> dict:
    return copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "Vienna"))


class ViennaTempoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = _record()

    def test_default_bpm_is_126_in_4_4(self) -> None:
        ext = self.rec["extensions"]
        self.assertEqual(ext["default_bpm"], 126)
        self.assertEqual(ext["time_signature"], "4/4")
        self.assertEqual(self.rec["key"], "G")

    def test_bar_duration_math(self) -> None:
        self.assertAlmostEqual(meter_timing(126, "4/4").bar_sec, 4 * 60 / 126, places=6)

    def test_bars_unchanged_and_one_pass_matches_recording(self) -> None:
        for level, n in BARS.items():
            _v, sections = resolve_level_chart(self.rec, level)
            self.assertEqual(sum(len(v) for v in sections.values()), n, level)
        one = 115 * meter_timing(126, "4/4").bar_sec
        self.assertAlmostEqual(one, 219.047619, places=5)
        self.assertLess(abs(one - RECORDING_SECONDS) / RECORDING_SECONDS, 0.05)

    def test_notes_quote_new_tempo(self) -> None:
        notes = self.rec["extensions"]["arrangement_notes"]
        self.assertIn("126 BPM", notes)
        self.assertNotIn("~63 BPM", notes)


if __name__ == "__main__":
    unittest.main()

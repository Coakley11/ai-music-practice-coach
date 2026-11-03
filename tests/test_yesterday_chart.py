"""Yesterday: Pollack form (7-bar verses, two bridges) and real tempo (Wave 3, stream A1, W3-14).

YESTERDAY (97 BPM, 4/4; recording 2:03-2:06, Wikipedia EP 2:03, Tunebat/SongBPM 2:06, 2:05
  2015 remaster) - tempo: Hooktheory 97/98, Tunebat 97, SongBPM 97, Audiokeychain 98.
  Form (Pollack, "Notes on Yesterday", .../awp/y.html): Intro 2 bars (open-fifth F), Verse of 7
  bars (3+2+2: F | Em7b5 A7 | Dm | Bb C7 | F | Dm G | Bb F), Verse, Bridge 8 bars
  (|Em7b5 A7|Dm Bb|Gm C|F| x2), Verse, Bridge, Verse, Outro 2 bars = 48 bars = 118.8 s
  (ratio 0.95 vs 125 s).  Two-chord bars are even 2+2 splits (UNVERIFIED beat placement).
  Old chart: 8-bar verse, Beginner 10 bars with no middle eight.
"""
from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

LEVELS = ("Beginner", "Intermediate", "Advanced")


def _rec(title: str) -> dict:
    return copy.deepcopy(next(r for r in curated_song_records() if r["title"] == title))


def _bars(secs) -> int:
    return sum(len(v) for v in secs.values())


class YesterdayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = _rec("Yesterday")

    def test_tempo_meter_order(self) -> None:
        ext = self.rec["extensions"]
        self.assertEqual(ext["default_bpm"], 97)
        self.assertEqual(ext["time_signature"], "4/4")
        self.assertEqual(ext["default_groove"], "Ballad")
        self.assertEqual(
            self.rec["section_order"],
            ["Intro", "Verse 1", "Verse 2", "Bridge 1", "Verse 3", "Bridge 2", "Verse 4", "Outro"],
        )

    def test_form_kept_at_every_level(self) -> None:
        want = {"Intro": 2, "Verse 1": 7, "Verse 2": 7, "Bridge 1": 8, "Verse 3": 7,
                "Bridge 2": 8, "Verse 4": 7, "Outro": 2}
        for level in LEVELS:
            _v, secs = resolve_level_chart(self.rec, level)
            self.assertEqual({k: len(v) for k, v in secs.items()}, want, level)
            self.assertEqual(_bars(secs), 48, level)

    def test_hand_written_cells(self) -> None:
        _v, inter = resolve_level_chart(self.rec, "Intermediate")
        self.assertEqual(
            inter["Verse 1"],
            ["F", "Em7b5|A7", "Dm", "Bb|C7", "F", "Dm|G7", "Bb|F"],
        )
        self.assertEqual(
            inter["Bridge 1"],
            ["Em7b5|A7", "Dm|Bb", "Gm|C7", "F"] * 2,
        )
        self.assertEqual(inter["Outro"], ["Dm|G7", "Bb|F"])
        self.assertEqual(inter["Intro"], ["F", "F"])
        _v, beg = resolve_level_chart(self.rec, "Beginner")
        self.assertEqual(beg["Verse 4"], ["F", "Em|A", "Dm", "Bb|C", "F", "Dm|G", "Bb|F"])

    def test_one_pass_ratio_vs_recording(self) -> None:
        bar = meter_timing(97, "4/4").bar_sec
        for level in LEVELS:
            _v, secs = resolve_level_chart(self.rec, level)
            ratio = _bars(secs) * bar / 125.0  # 2:05 (2015 remaster; EP 2:03, Tunebat 2:06)
            self.assertTrue(0.85 <= ratio <= 1.2, (level, ratio))


if __name__ == "__main__":
    unittest.main()

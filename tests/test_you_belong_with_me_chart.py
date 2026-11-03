"""You Belong With Me (Taylor Swift) harmonic-rhythm correction (Wave 3, stream C2).

Source: Wikipedia "You Belong with Me", Composition (describes the published sheet music):
verse and chorus I-V-ii-IV (F#, C#, D#m, B) with each chord held TWO measures; pre-chorus
ii-IV-I-V (D#m, B, F#, C#) with each chord ONE measure; sections are eight-measure phrases;
recording length 3:51 (231 s, album and Taylor's Version).  Base had every chord held FOUR
bars and the pre-chorus identical to the verse (192 Advanced bars, 354 s = 1.53x).

No pushes/splits in this chart (whole-bar holds only).  Section repeat counts
(16-bar verse/chorus/bridge, 8-bar link/outro) are medium confidence, fitted to 231 s.
One-pass Advanced at 130 BPM: 124 bars = 228.9 s (ratio 0.99 vs 231 s, band 0.85-1.2,
basis: album single 3:51 per Wikipedia).
"""
from __future__ import annotations

import unittest

from chart_level_arrangement import resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

REC_SEC = 231.0


class YouBelongWithMeChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = [r for r in curated_song_records() if r["title"] == "You Belong With Me"][0]
        cls.mt = meter_timing(130, "4/4")

    def test_verse_chord_durations(self) -> None:
        self.assertEqual(
            self.rec["sections"]["Verse 1"],
            ["F#", "F#", "C#", "C#", "D#m", "D#m", "B", "B"] * 2,
        )

    def test_prechorus_is_ii_IV_I_V_one_bar_each(self) -> None:
        self.assertEqual(self.rec["sections"]["Pre-Chorus 1"], ["D#m", "B", "F#", "C#"])
        self.assertEqual(self.rec["sections"]["Pre-Chorus 2"], ["D#m", "B", "F#", "C#"])

    def test_advanced_bars_and_one_pass_ratio(self) -> None:
        _, secs = resolve_level_chart(self.rec, "Advanced")
        bars = sum(len(v) for v in secs.values())
        self.assertEqual(bars, 124)
        ratio = bars * self.mt.bar_sec / REC_SEC
        self.assertGreaterEqual(ratio, 0.85)
        self.assertLessEqual(ratio, 1.2)

    def test_intermediate_bars(self) -> None:
        _, secs = resolve_level_chart(self.rec, "Intermediate")
        self.assertEqual(sum(len(v) for v in secs.values()), 120)

    def test_notes_do_not_claim_four_bars_per_chord(self) -> None:
        self.assertNotIn("each chord = 4 measures", self.rec["extensions"]["arrangement_notes"])


if __name__ == "__main__":
    unittest.main()

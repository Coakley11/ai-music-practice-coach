"""You Belong With Me (Taylor Swift) harmonic-rhythm correction (Wave 3, stream C2).

Source: Wikipedia "You Belong with Me", Composition (describes the published sheet music):
verse and chorus I-V-ii-IV (F#, C#, G#m, B) with each chord held TWO measures; pre-chorus
ii-IV-I-V (G#m, B, F#, C#) with each chord ONE measure; sections are eight-measure phrases;
recording length 3:51 (231 s, album and Taylor's Version).  Base had every chord held FOUR
bars and the pre-chorus identical to the verse (192 Advanced bars, 354 s = 1.53x).

No pushes/splits in this chart (whole-bar holds only).  Section repeat counts
(16-bar verse/chorus/bridge, 8-bar link/outro) are medium confidence, fitted to 231 s.
Review (v2): ii of F# major is G#m, not D#m (vi): Wikipedia (g-sharp), Hooktheory (ii) and
tab sites in D with capo 4 (D A Em G) agree.  Pre-chorus is two 4-bar passes (8-bar phrases).
Intro 4, verse/chorus/bridge 16, link/outro 8 and repeat counts are NOT independently documented.
One-pass Advanced at 130 BPM: 132 bars = 243.7 s (ratio 1.055 vs 231 s, band 0.85-1.2,
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
            ["F#", "F#", "C#", "C#", "G#m", "G#m", "B", "B"] * 2,
        )

    def test_prechorus_is_ii_IV_I_V_one_bar_each(self) -> None:
        self.assertEqual(self.rec["sections"]["Pre-Chorus 1"], ["G#m", "B", "F#", "C#"] * 2)
        self.assertEqual(self.rec["sections"]["Pre-Chorus 2"], ["G#m", "B", "F#", "C#"] * 2)

    def test_advanced_bars_and_one_pass_ratio(self) -> None:
        _, secs = resolve_level_chart(self.rec, "Advanced")
        bars = sum(len(v) for v in secs.values())
        self.assertEqual(bars, 132)
        ratio = bars * self.mt.bar_sec / REC_SEC
        self.assertGreaterEqual(ratio, 0.85)
        self.assertLessEqual(ratio, 1.2)

    def test_intermediate_bars(self) -> None:
        _, secs = resolve_level_chart(self.rec, "Intermediate")
        self.assertEqual(sum(len(v) for v in secs.values()), 124)

    def test_notes_do_not_claim_four_bars_per_chord(self) -> None:
        self.assertNotIn("each chord = 4 measures", self.rec["extensions"]["arrangement_notes"])


if __name__ == "__main__":
    unittest.main()

"""We Are the Champions (Queen): the published score is 6/8, not 4/4.

Sources: Musicnotes MN0197341 (piano solo, C minor, 6/8, ~62) and MN0063752
(PVG, C minor, 6/8, ~70); Hooktheory (6/8, 193 eighths/min = 64.3 dotted
quarters). In the app 6/8 BPM counts dotted quarters (songs/meter.py), two per
bar, so one chart cell (one 6/8 bar) lasts 2*60/65 = 1.85 s, not the 3.69 s a
4/4 bar at 65 gave (one pass was 458 s vs a 179 s recording; now ~229 s).
Chart cells are unchanged (the `Bb|C7` split bar stays: half a 6/8 bar each,
3 eighths + 3 eighths; its beat placement is not source-verified).
"""
from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

BARS = {"Beginner": 105, "Intermediate": 99, "Advanced": 105}


class ChampionsMeterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(
            next(r for r in curated_song_records() if r["title"] == "We Are the Champions")
        )

    def test_meter_and_bpm(self) -> None:
        ext = self.rec["extensions"]
        self.assertEqual(ext["time_signature"], "6/8")
        self.assertEqual(ext["default_bpm"], 65)
        self.assertEqual(self.rec["key"], "Cm")

    def test_bar_math(self) -> None:
        t = meter_timing(65, "6/8")
        self.assertAlmostEqual(t.bar_sec, 2 * 60 / 65, places=6)
        self.assertAlmostEqual(124 * t.bar_sec, 124 * 120 / 65, places=6)  # 228.9 s (old Advanced)
        self.assertAlmostEqual(105 * t.bar_sec, 193.85, places=2)

    def test_cells_unchanged(self) -> None:
        for level, n in BARS.items():
            _v, secs = resolve_level_chart(self.rec, level)
            self.assertEqual(sum(len(v) for v in secs.values()), n, level)
        _v, adv = resolve_level_chart(self.rec, "Advanced")
        self.assertEqual(adv["Chorus 1"][3], "Bb|C7")
        self.assertEqual(len(adv["Verse 1"]), 21)

    def test_outro_duplicate_chorus_removed_three_choruses(self) -> None:
        """Wave 3: the 1977 single (2:59) has three choruses; the 4th (Outro) was a duplicate.

        Basis: Wikipedia infobox 2:59 (Raw Sessions has two MORE choruses than the single),
        Tony Conniff (chorus ~9 12/8 bars = 33.8 s vs chart 19 x 1.846 = 35.1 s). V1+C1+V2+C2+C3
        = 99 bars x 1.846 s = 182.8 s vs 179 s (ratio 1.02); a 4th chorus gave 218 s (1.22).
        MED-HIGH (no timestamped score). Ending Tag (6 bars Fm/Gm7) kept, unverified.
        """
        for level, (n, hi) in {
            "Beginner": (105, 1.2), "Intermediate": (99, 1.2), "Advanced": (105, 1.2),
        }.items():
            _v, secs = resolve_level_chart(self.rec, level)
            self.assertNotIn("Outro", secs, level)
            self.assertEqual(list(secs)[-1], "Final Chorus", level)
            sec = sum(len(v) for v in secs.values()) * meter_timing(65, "6/8").bar_sec
            self.assertTrue(0.85 <= sec / 179 <= hi, (level, sec))
        _v, inter = resolve_level_chart(self.rec, "Intermediate")
        self.assertEqual(
            [k for k in inter if k.startswith(("Chorus", "Final"))],
            ["Chorus 1", "Chorus 2", "Final Chorus"],
        )

    def test_notes_say_6_8(self) -> None:
        notes = self.rec["extensions"]["arrangement_notes"]
        self.assertIn("6/8", notes)
        self.assertNotIn("4/4", notes)


if __name__ == "__main__":
    unittest.main()

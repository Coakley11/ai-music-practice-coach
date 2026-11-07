"""Come Together: Beginner/Intermediate keep all 15 sections (verses 3-4, solo, final chorus).

Before (base e812c09e) Beginner resolved to 6 sections / 28 bars (82.0 s at 82 BPM:
Intro, V1, Ch1, V2, Ch2, Outro) and Intermediate to 46 bars without the Solo or any
tag; the Wave 2 chart (70 bars) was only reachable at Advanced.  The record now declares
``extensions.full_form_levels = ["Beginner", "Intermediate"]`` and cues for the sections
that lacked one (Verse 3/4, Chorus 2, Instrumental 2-4; descriptive, no lyric text).
Chords, BPM 82 and meter are unchanged; the held 4-bar outro is untouched.
"""

from __future__ import annotations

import unittest

from chart_level_arrangement import keeps_full_form, resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

ORDER = ["Intro", "Verse 1", "Instrumental 1", "Verse 2", "Chorus 1", "Instrumental 2", "Verse 3",
         "Chorus 2", "Instrumental 3", "Solo", "Instrumental 4", "Verse 4", "Final Chorus",
         "Instrumental 5", "Outro (Fade)"]
BARS = [4, 8, 4, 8, 2, 4, 8, 2, 2, 8, 2, 8, 2, 4, 4]


class ComeTogetherBeginnerFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = next(r for r in curated_song_records() if r["title"] == "Come Together")

    def test_declared(self):
        for level in ("Beginner", "Intermediate"):
            self.assertTrue(keeps_full_form(self.rec, level), level)
        self.assertEqual(self.rec["extensions"]["default_bpm"], 82)

    def test_all_levels_play_15_sections_70_bars(self):
        for level in ("Beginner", "Intermediate", "Advanced"):
            view, sec = resolve_level_chart(self.rec, level)
            self.assertEqual(list(sec), ORDER, level)
            self.assertEqual(view["section_order"], ORDER, level)
            self.assertEqual([len(sec[n]) for n in ORDER], BARS, level)
            self.assertEqual(sum(BARS), 70)

    def test_beginner_keeps_solo_final_chorus_and_simplified_cells(self):
        _v, beg = resolve_level_chart(self.rec, "Beginner")
        self.assertEqual(beg["Solo"], ["Dm"] * 4 + ["A"] * 4)
        self.assertEqual(beg["Final Chorus"], ["Bm", "G|A"])
        self.assertEqual(beg["Verse 4"], ["Dm", "Dm", "Dm", "Dm", "A", "A", "G", "N.C."])
        self.assertEqual(beg["Instrumental 5"], ["Dm"] * 4)

    def test_every_section_has_a_cue(self):
        self.assertEqual(set(self.rec["lyric_cues"]), set(ORDER))
        self.assertEqual(set(ORDER) - set(self.rec["lyric_cues"]), set())

    def test_seconds(self):
        bar = meter_timing(82, "4/4").bar_sec
        self.assertAlmostEqual(70 * bar, 204.9, places=1)  # Beginner was 28 bars = 82.0 s, Intermediate 46 = 134.6 s


if __name__ == "__main__":
    unittest.main()

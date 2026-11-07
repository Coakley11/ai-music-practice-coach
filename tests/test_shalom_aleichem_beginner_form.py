"""Shalom Aleichem: Beginner/Intermediate play all six sections.

Before (base e812c09e) Beginner resolved to Verse 1 + Outro (21 bars, 70.0 s at 72 BPM)
and Intermediate (65 bars) lacked the 16-bar Instrumental.  The pack authors every
section at every level, so the record now declares
``extensions.full_form_levels = ["Beginner", "Intermediate"]``.  Chords, BPM 72 and
meter are unchanged (Advanced identical).
"""

from __future__ import annotations

import unittest

from chart_level_arrangement import keeps_full_form, resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

ORDER = ["Verse 1", "Verse 2", "Verse 3", "Instrumental", "Verse 4", "Outro"]
BARS = [18, 18, 8, 16, 18, 3]


class ShalomAleichemBeginnerFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = next(r for r in curated_song_records()
                       if r["title"] == "Shalom Aleichem" and r["artist"].startswith("Traditional Jewish"))

    def test_declared(self):
        for level in ("Beginner", "Intermediate"):
            self.assertTrue(keeps_full_form(self.rec, level), level)
        self.assertEqual(self.rec["extensions"]["default_bpm"], 72)

    def test_all_levels_play_the_whole_81_bar_form(self):
        for level in ("Beginner", "Intermediate", "Advanced"):
            view, sec = resolve_level_chart(self.rec, level)
            self.assertEqual(list(sec), ORDER, level)
            self.assertEqual(view["section_order"], ORDER, level)
            self.assertEqual([len(sec[n]) for n in ORDER], BARS, level)
            self.assertEqual(sum(BARS), 81)

    def test_instrumental_and_outro_cells(self):
        _v, beg = resolve_level_chart(self.rec, "Beginner")
        self.assertEqual(beg["Instrumental"][:4], ["Dm", "F", "C", "C"])
        self.assertEqual(beg["Outro"], ["Dm", "A", "Dm"])
        self.assertEqual(beg["Verse 3"], ["Dm", "A", "Dm", "A", "Dm", "A", "Gm", "A"])

    def test_seconds(self):
        bar = meter_timing(72, "4/4").bar_sec
        self.assertAlmostEqual(81 * bar, 270.0, places=1)  # Beginner was 21 bars = 70.0 s; Intermediate 65 = 216.7 s


if __name__ == "__main__":
    unittest.main()

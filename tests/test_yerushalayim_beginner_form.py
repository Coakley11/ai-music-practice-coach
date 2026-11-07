"""Yerushalayim Shel Zahav: Beginner plays Verse 1, Verse 2 and the Bridge.

Before (base e812c09e) the global Beginner derivation left a single 8-bar Verse
(25.3 s at 76 BPM) and dropped the Bridge (the emotional peak per the lyric cues).
The record now declares ``extensions.full_form_levels = ["Beginner"]``.  Chords,
BPM 76 and meter are unchanged; the shorter Beginner Verse chords (Am x3) are the
authored ``beginner`` chart.
"""

from __future__ import annotations

import unittest

from chart_level_arrangement import keeps_full_form, resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

ORDER = ["Verse 1", "Verse 2", "Bridge"]


class YerushalayimBeginnerFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = next(r for r in curated_song_records() if r["title"] == "Yerushalayim Shel Zahav")

    def test_declared(self):
        self.assertTrue(keeps_full_form(self.rec, "Beginner"))
        self.assertEqual(self.rec["extensions"]["default_bpm"], 76)

    def test_every_level_plays_three_8_bar_sections(self):
        for level in ("Beginner", "Intermediate", "Advanced"):
            view, sec = resolve_level_chart(self.rec, level)
            self.assertEqual(list(sec), ORDER, level)
            self.assertEqual(view["section_order"], ORDER, level)
            self.assertEqual([len(sec[n]) for n in ORDER], [8, 8, 8], level)

    def test_cells(self):
        _v, beg = resolve_level_chart(self.rec, "Beginner")
        self.assertEqual(beg["Verse 1"], ["Am", "Am", "Am", "Em", "F", "C", "G", "Am"])
        self.assertEqual(beg["Bridge"], ["F", "C", "G", "Am", "F", "C", "G", "Am"])
        _v, adv = resolve_level_chart(self.rec, "Advanced")
        self.assertEqual(adv["Verse 1"], ["Am", "Em", "Am", "Em", "F", "C", "G", "Am"])

    def test_seconds(self):
        bar = meter_timing(76, "4/4").bar_sec
        self.assertAlmostEqual(24 * bar, 75.8, places=1)  # Beginner was 8 bars = 25.3 s


if __name__ == "__main__":
    unittest.main()

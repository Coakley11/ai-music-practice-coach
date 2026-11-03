"""Iris: Beginner/Intermediate keep all 13 sections (Final Chorus, Instrumental, Coda).

Before (base e812c09e) Beginner resolved to 6 sections / 69 bars (107.5 s at 154 BPM)
and Intermediate to 9 / 117 bars: the Interlude, Instrumental, Ending Build, Final
Chorus (Beginner) and Outro/Coda were dropped.  The pack authors every section at every
level (Beginner = same bars with simplified chords), so the record now declares
``extensions.full_form_levels = ["Beginner", "Intermediate"]``.  Advanced content,
BPM 154 and meter are unchanged.
"""

from __future__ import annotations

import unittest

from chart_level_arrangement import keeps_full_form, resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

ORDER = ["Intro", "Verse 1", "Verse 2", "Chorus 1", "Interlude", "Verse 3", "Chorus 2",
         "Instrumental", "Build", "Ending Build", "Final Chorus", "Outro", "Coda"]
BARS = [5, 12, 12, 12, 5, 12, 12, 30, 12, 16, 24, 9, 16]


class IrisBeginnerFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = next(r for r in curated_song_records() if r["title"] == "Iris")

    def test_declared(self):
        for level in ("Beginner", "Intermediate"):
            self.assertTrue(keeps_full_form(self.rec, level), level)
        self.assertEqual(self.rec["extensions"]["default_bpm"], 154)

    def test_every_level_has_all_13_sections_177_bars(self):
        for level in ("Beginner", "Intermediate", "Advanced"):
            view, sec = resolve_level_chart(self.rec, level)
            self.assertEqual(list(sec), ORDER, level)
            self.assertEqual(view["section_order"], ORDER, level)
            self.assertEqual([len(sec[n]) for n in ORDER], BARS, level)
            self.assertEqual(sum(BARS), 177)

    def test_beginner_chords_are_simplified_advanced_chords(self):
        _v, beg = resolve_level_chart(self.rec, "Beginner")
        _v, adv = resolve_level_chart(self.rec, "Advanced")
        self.assertEqual(beg["Intro"], ["Bm", "Bm", "G", "G", "G"])
        self.assertEqual(adv["Intro"], ["Bm", "Bsus2", "G", "Gmaj7", "G"])
        self.assertEqual(beg["Build"][:4], ["G", "F#", "G", "Bm"])
        self.assertEqual(beg["Coda"], ["Bm", "Bm", "G", "G"] * 4)

    def test_cued_sections_survive(self):
        for name in self.rec["lyric_cues"]:
            self.assertIn(name, ORDER)

    def test_seconds(self):
        bar = meter_timing(154, "4/4").bar_sec
        self.assertAlmostEqual(177 * bar, 275.8, places=1)  # Beginner was 69 bars = 107.5 s

    def test_events_validate(self):
        for level in ("Beginner", "Intermediate", "Advanced"):
            view, sections = resolve_level_chart(self.rec, level)
            events = sections_dict_to_events(sections, section_order=view["section_order"])
            self.assertEqual(validate_chord_events(events), [], level)


if __name__ == "__main__":
    unittest.main()

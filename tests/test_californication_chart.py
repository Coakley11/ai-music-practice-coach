"""Californication chorus/outro are C-Gmaj7-Dm9-Am (Wikipedia; AZChords; Songsterr).

Previously Chorus/Outro reused the verse loop Am F C G. Bar counts (36), section names,
the verse riff, Pre-Chorus (verse second half) and the solo are unchanged.
"""
from __future__ import annotations

import copy
import unittest

from chord_events import sections_dict_to_events, validate_chord_events
from song_catalog.catalog import curated_song_records

ORDER = ["Intro / Verse Riff", "Pre-Chorus", "Chorus", "Guitar Solo", "Outro"]
BARS = {"Intro / Verse Riff": 8, "Pre-Chorus": 8, "Chorus": 8, "Guitar Solo": 8, "Outro": 4}
CHORUS = {
    "Beginner": ["C", "G", "Dm", "Am", "C", "G", "Dm", "Am"],
    "Intermediate": ["C", "Gmaj7", "Dm9", "Am", "C", "G", "Dm9", "Am"],
}
CHORUS["Advanced"] = CHORUS["Intermediate"]
OUTRO = {"Beginner": ["C", "G", "Dm", "Am"], "Intermediate": ["C", "Gmaj7", "Dm9", "Am"]}
OUTRO["Advanced"] = OUTRO["Intermediate"]


class CalifornicationChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "Californication"))

    def test_chorus_and_outro_exact(self):
        for lv in CHORUS:
            ch = self.rec["chart_versions"][lv]
            self.assertEqual(ch["Chorus"], CHORUS[lv], lv)
            self.assertEqual(ch["Outro"], OUTRO[lv], lv)
        self.assertEqual(self.rec["sections"]["Chorus"], CHORUS["Intermediate"])

    def test_other_sections_unchanged(self):
        beg = self.rec["chart_versions"]["Beginner"]
        self.assertEqual(beg["Intro / Verse Riff"], ["Am", "F"] * 4)
        self.assertEqual(beg["Pre-Chorus"], ["C", "G", "F", "Dm"] * 2)
        inter = self.rec["chart_versions"]["Intermediate"]
        self.assertEqual(inter["Intro / Verse Riff"], ["Am", "Fmaj7"] * 4)
        self.assertEqual(inter["Pre-Chorus"], ["C", "G", "Fmaj7", "Dm"] * 2)
        for lv in CHORUS:
            self.assertEqual(self.rec["chart_versions"][lv]["Guitar Solo"],
                             ["F#m", "D", "F#m", "D", "Bm", "D", "A", "E"], lv)

    def test_bars_and_identity(self):
        self.assertEqual(self.rec["key"], "Am")
        for lv in CHORUS:
            ch = self.rec["chart_versions"][lv]
            self.assertEqual(list(ch), ORDER)
            self.assertEqual({k: len(v) for k, v in ch.items()}, BARS)
            self.assertEqual(sum(map(len, ch.values())), 36)
            ev = sections_dict_to_events(ch, time_signature="4/4", section_order=ORDER)
            self.assertEqual(validate_chord_events(ev, time_signature="4/4"), [])

    def test_tabs_cover_every_chord_used_in_chorus(self):
        tabs = self.rec["guitar_tabs"]
        for chord in ("C", "G", "Gmaj7", "Dm", "Dm9", "Am"):
            self.assertIn(chord, tabs)

    def test_notes_and_no_bpm_added(self):
        notes = self.rec["extensions"]["arrangement_notes"]
        self.assertIn("C-Gmaj7-Dm9-Am", notes)
        self.assertNotIn("default_bpm", self.rec["extensions"])


if __name__ == "__main__":
    unittest.main()

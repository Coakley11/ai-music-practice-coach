"""I'm Yours: Beginner keeps all nine sections incl. the Bridge and final chorus.

Before (base e812c09e) Beginner resolved to 6 sections / 26 bars (83.2 s at 75 BPM)
and lacked the Bridge, Verse 3 and the Final Chorus / Outro Build.  The pack authors
a shortened chart for every section (one loop pass per repeat), so the record now
declares ``extensions.full_form_levels = ["Beginner"]``.  Advanced content (including
the separately-tracked ``Em77`` / ``Gmaj7maj7`` chord-name defects), BPM 75, capo note
and meter are unchanged.
"""

from __future__ import annotations

import unittest

from chart_level_arrangement import keeps_full_form, resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

ORDER = ["Intro", "Verse 1", "Chorus 1", "Verse 2", "Chorus 2", "Bridge", "Verse 3",
         "Final Chorus / Outro Build", "Outro"]
BEGINNER_BARS = [4, 4, 4, 5, 4, 9, 4, 5, 5]
FULL_BARS = [4, 8, 8, 9, 8, 10, 8, 9, 9]
LOOP = ["B", "F#", "G#m", "E"]  # concert key B (G shapes with capo 4)


class ImYoursBeginnerFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = next(r for r in curated_song_records() if r["title"] == "I'm Yours")

    def test_declared(self):
        self.assertTrue(keeps_full_form(self.rec, "Beginner"))
        self.assertEqual(self.rec["extensions"]["full_form_levels"], ["Beginner"])
        self.assertEqual(self.rec["extensions"]["default_bpm"], 75)

    def test_beginner_keeps_every_section(self):
        view, beg = resolve_level_chart(self.rec, "Beginner")
        self.assertEqual(list(beg), ORDER)
        self.assertEqual(view["section_order"], ORDER)
        self.assertEqual([len(beg[n]) for n in ORDER], BEGINNER_BARS)
        self.assertEqual(beg["Bridge"], ["B", "F#", "G#m", "E", "C#7", "B|F#/A#", "G#m|F#", "E", "C#7"])
        self.assertEqual(beg["Final Chorus / Outro Build"], ["B", "F#|F#sus4", "G#m", "E", "C#7"])
        self.assertEqual(beg["Verse 3"], LOOP)
        self.assertEqual(beg["Outro"], ["N.C."] + LOOP)
        self.assertEqual(sum(BEGINNER_BARS), 44)

    def test_intermediate_and_advanced_unchanged(self):
        for level in ("Intermediate", "Advanced"):
            _v, sec = resolve_level_chart(self.rec, level)
            self.assertEqual(list(sec), ORDER, level)
            self.assertEqual([len(sec[n]) for n in ORDER], FULL_BARS, level)

    def test_lyric_cues_cover_every_section(self):
        self.assertEqual(set(ORDER), set(self.rec["lyric_cues"]))

    def test_seconds(self):
        bar = meter_timing(75, "4/4").bar_sec
        self.assertAlmostEqual(44 * bar, 140.8, places=1)  # Beginner was 26 bars = 83.2 s

    def test_events_validate(self):
        for level in ("Beginner", "Intermediate"):
            view, sections = resolve_level_chart(self.rec, level)
            events = sections_dict_to_events(sections, section_order=view["section_order"])
            self.assertEqual(validate_chord_events(events), [], level)


if __name__ == "__main__":
    unittest.main()

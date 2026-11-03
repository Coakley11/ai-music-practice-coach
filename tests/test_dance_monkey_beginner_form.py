"""Dance Monkey: Beginner/Intermediate keep all 12 sections.

Before (base e812c09e) Beginner was 30 bars (73.5 s at 98 BPM) with no Bridge,
Final Chorus, Final Chorus Repeat, Pre-Chorus 2 or Chorus 3, and Intermediate
(69 bars) lacked Pre-Chorus 2 and Chorus 3.  The pack authors every section at
every level (Beginner = one loop pass per repeat), so the record now declares
``extensions.full_form_levels = ["Beginner", "Intermediate"]``.  Advanced content
(including the separately-tracked ``Emaj7maj7.hit`` chord-name defect), BPM 98 and
meter are unchanged.
"""

from __future__ import annotations

import unittest

from chart_level_arrangement import keeps_full_form, resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

ORDER = ["Intro", "Verse 1", "Pre-Chorus 1", "Chorus 1", "Verse 2", "Pre-Chorus 2",
         "Chorus 2", "Chorus 3", "Bridge", "Final Chorus", "Final Chorus Repeat", "Outro"]
LOOP = ["F#m", "D", "E", "C#m"]
BEGINNER_BARS = [4, 8, 5, 4, 4, 5, 4, 4, 5, 4, 4, 1]
FULL_BARS = [4, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 1]


class DanceMonkeyBeginnerFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = next(r for r in curated_song_records() if r["title"] == "Dance Monkey")

    def test_declared(self):
        self.assertEqual(self.rec["extensions"]["full_form_levels"], ["Beginner", "Intermediate"])
        self.assertTrue(keeps_full_form(self.rec, "Beginner"))
        self.assertTrue(keeps_full_form(self.rec, "Intermediate"))
        self.assertEqual(self.rec["extensions"]["default_bpm"], 98)

    def test_beginner_bars_and_cells(self):
        view, beg = resolve_level_chart(self.rec, "Beginner")
        self.assertEqual(list(beg), ORDER)
        self.assertEqual(view["section_order"], ORDER)
        self.assertEqual([len(beg[n]) for n in ORDER], BEGINNER_BARS)
        self.assertEqual(beg["Chorus 1"], LOOP)
        self.assertEqual(beg["Bridge"], LOOP + ["N.C."])
        self.assertEqual(beg["Final Chorus Repeat"], LOOP)
        self.assertEqual(sum(BEGINNER_BARS), 52)

    def test_intermediate_and_advanced_bars(self):
        for level in ("Intermediate", "Advanced"):
            _v, sec = resolve_level_chart(self.rec, level)
            self.assertEqual(list(sec), ORDER, level)
            self.assertEqual([len(sec[n]) for n in ORDER], FULL_BARS, level)
            self.assertEqual(sum(len(v) for v in sec.values()), 85, level)

    def test_lyric_cues_cover_every_section(self):
        self.assertEqual(set(ORDER), set(self.rec["lyric_cues"]))

    def test_seconds(self):
        bar = meter_timing(98, "4/4").bar_sec
        self.assertAlmostEqual(52 * bar, 127.3, places=1)   # Beginner was 30 bars = 73.5 s
        self.assertAlmostEqual(85 * bar, 208.2, places=1)   # Intermediate was 69 bars = 169.0 s

    def test_events_validate(self):
        for level in ("Beginner", "Intermediate", "Advanced"):
            view, sections = resolve_level_chart(self.rec, level)
            events = sections_dict_to_events(sections, section_order=view["section_order"])
            self.assertEqual(validate_chord_events(events), [], level)


if __name__ == "__main__":
    unittest.main()

"""Day Tripper: Beginner plays the whole 94-bar form, not a 34-bar fragment.

Before (base e812c09e) the global Beginner derivation kept Intro Riff, Verse 1 and
Outro only (34 bars, 59.1 s at 138 BPM) and dropped Verse 2/3, the 12-bar B7
Guitar Break and the riff returns.  The pack already authors every section at
every level (see tests/test_day_tripper_chart.py); the record now declares
``extensions.full_form_levels = ["Beginner"]``.  Chords, BPM 138 and Advanced
content are unchanged.
"""

from __future__ import annotations

import unittest

from chart_level_arrangement import keeps_full_form, resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

ORDER = ["Intro Riff", "Verse 1", "Riff Return", "Verse 2", "Guitar Break",
         "Riff Return 2", "Verse 3", "Riff Return 3", "Outro"]
BARS = [10, 16, 4, 16, 12, 4, 16, 8, 8]


class DayTripperBeginnerFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = next(r for r in curated_song_records() if r["title"] == "Day Tripper")

    def test_declared_and_settings_unchanged(self):
        self.assertTrue(keeps_full_form(self.rec, "Beginner"))
        self.assertEqual(self.rec["extensions"]["full_form_levels"], ["Beginner"])
        self.assertEqual(self.rec["extensions"]["default_bpm"], 138)

    def test_all_levels_play_nine_sections_94_bars(self):
        for level in ("Beginner", "Intermediate", "Advanced"):
            view, sections = resolve_level_chart(self.rec, level)
            self.assertEqual(list(sections), ORDER, level)
            self.assertEqual([len(sections[n]) for n in ORDER], BARS, level)
            self.assertEqual(view["section_order"], ORDER, level)

    def test_beginner_guitar_break_is_12_bars_of_b7(self):
        _v, beg = resolve_level_chart(self.rec, "Beginner")
        self.assertEqual(beg["Guitar Break"], ["B7"] * 12)
        self.assertEqual(beg["Verse 2"][8:12], ["F#7"] * 4)

    def test_guitar_break_cue_survives(self):
        self.assertIn("Guitar Break", self.rec["lyric_cues"])

    def test_beginner_seconds(self):
        bar = meter_timing(138, "4/4").bar_sec
        self.assertAlmostEqual(94 * bar, 163.48, places=1)  # was 34 bars = 59.1 s

    def test_events_validate(self):
        for level in ("Beginner", "Intermediate", "Advanced"):
            view, sections = resolve_level_chart(self.rec, level)
            events = sections_dict_to_events(sections, section_order=view["section_order"])
            self.assertEqual(validate_chord_events(events), [], level)


if __name__ == "__main__":
    unittest.main()

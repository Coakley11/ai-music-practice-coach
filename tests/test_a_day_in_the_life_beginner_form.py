"""A Day in the Life: Beginner plays the whole authored form, not the 4-bar Verse.

Before (base e812c09e) the global Beginner derivation kept only "Verse" (4 bars,
9.6 s at the 100 BPM fallback) and dropped the Orchestral Bridge and the Final
section.  The record now declares ``extensions.full_form_levels = ["Beginner"]``
(data only; chart_level_arrangement.py, Advanced chords, BPM and meter are
unchanged).  The authored chart is still the 12-bar skeleton; fuller form/tempo
work for this Beatles song is outside this change.
"""

from __future__ import annotations

import unittest

from chart_level_arrangement import keeps_full_form, resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

ORDER = ["Verse", "Orchestral Bridge", "Final"]
LEVELS = ("Beginner", "Intermediate", "Advanced")


class ADayInTheLifeBeginnerFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = next(r for r in curated_song_records() if r["title"] == "A Day in the Life")

    def test_declares_full_form_for_beginner(self):
        self.assertTrue(keeps_full_form(self.rec, "Beginner"))
        self.assertEqual(self.rec["extensions"]["full_form_levels"], ["Beginner"])

    def test_every_level_has_the_three_sections_and_12_bars(self):
        for level in LEVELS:
            _view, sections = resolve_level_chart(self.rec, level)
            self.assertEqual(list(sections), ORDER, level)
            self.assertEqual(sum(len(v) for v in sections.values()), 12, level)

    def test_beginner_cells_are_triads_of_the_advanced_chords(self):
        _v, beg = resolve_level_chart(self.rec, "Beginner")
        self.assertEqual(beg["Verse"], ["G", "Bm", "Em", "Em"])
        self.assertEqual(beg["Orchestral Bridge"], ["E"] * 4)
        self.assertEqual(beg["Final"], ["G", "Bm", "Em", "C"])

    def test_advanced_chords_unchanged(self):
        _v, adv = resolve_level_chart(self.rec, "Advanced")
        self.assertEqual(adv["Verse"], ["G", "Bm", "Em", "Em7"])
        self.assertEqual(adv["Orchestral Bridge"], ["E"] * 4)

    def test_one_pass_seconds_at_fallback_bpm(self):
        bar = meter_timing(100, "4/4").bar_sec
        self.assertAlmostEqual(12 * bar, 28.8, places=3)  # Beginner was 4 bars = 9.6 s

    def test_events_validate_at_all_levels(self):
        for level in LEVELS:
            view, sections = resolve_level_chart(self.rec, level)
            events = sections_dict_to_events(sections, section_order=view.get("section_order") or list(sections))
            self.assertEqual(validate_chord_events(events), [], level)


if __name__ == "__main__":
    unittest.main()

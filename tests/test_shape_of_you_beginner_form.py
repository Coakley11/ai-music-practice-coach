"""Shape of You: Beginner keeps the whole 8-section form (one loop pass each).

Before (base e812c09e) only Intermediate was in ``full_form_levels``; Beginner
resolved to 5 sections / 10 bars (25.0 s at 96 BPM),
losing Pre-Chorus 2, the Bridge (with its N.C. drum break) and the Final Chorus.
The pack already authors a full Beginner chart ("one main-loop pass per section
... the bridge keeps the tacet bars"), so the intent was always the full form;
only the level flag was missing.  Chords, pushes (the unsourced ``Em:2p`` / ``A:2p``
arrivals, held by Wave 2), BPM 96 and Advanced content are unchanged.
"""

from __future__ import annotations

import unittest

from chart_level_arrangement import keeps_full_form, resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

ORDER = ["Verse 1", "Pre-Chorus 1", "Chorus 1", "Verse 2", "Pre-Chorus 2",
         "Chorus 2", "Bridge", "Final Chorus"]
LOOP = ["Bm:2|Em:2p", "G:2|A:2p"]


class ShapeOfYouBeginnerFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = next(r for r in curated_song_records() if r["title"] == "Shape of You")

    def test_beginner_and_intermediate_declared(self):
        self.assertEqual(self.rec["extensions"]["full_form_levels"], ["Beginner", "Intermediate"])
        self.assertTrue(keeps_full_form(self.rec, "Beginner"))
        self.assertEqual(self.rec["extensions"]["default_bpm"], 96)

    def test_beginner_plays_all_eight_sections(self):
        view, sections = resolve_level_chart(self.rec, "Beginner")
        self.assertEqual(list(sections), ORDER)
        self.assertEqual(view["section_order"], ORDER)
        for name in ORDER:
            exp = ["N.C.", "N.C.", *LOOP] if name == "Bridge" else LOOP
            self.assertEqual(sections[name], exp, name)
        self.assertEqual(sum(len(v) for v in sections.values()), 18)

    def test_intermediate_and_advanced_unchanged_92_bars(self):
        for level in ("Intermediate", "Advanced"):
            _v, sections = resolve_level_chart(self.rec, level)
            self.assertEqual(list(sections), ORDER, level)
            self.assertEqual(sum(len(v) for v in sections.values()), 92, level)
            self.assertEqual(len(sections["Bridge"]), 12, level)

    def test_lyric_cues_cover_every_beginner_section(self):
        self.assertEqual(set(ORDER), set(self.rec["lyric_cues"]))

    def test_beginner_one_pass_seconds(self):
        bar = meter_timing(96, "4/4").bar_sec
        self.assertAlmostEqual(18 * bar, 45.0, places=2)  # was 10 bars = 25.0 s

    def test_events_validate_at_all_levels(self):
        for level in ("Beginner", "Intermediate", "Advanced"):
            view, sections = resolve_level_chart(self.rec, level)
            events = sections_dict_to_events(sections, section_order=view["section_order"])
            self.assertEqual(validate_chord_events(events), [], level)


if __name__ == "__main__":
    unittest.main()

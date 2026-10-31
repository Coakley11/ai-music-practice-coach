"""Day Tripper: 94 bars matching Pollack's form (10-bar intro, 16-bar verse, 12-bar B bridge).

The earlier pack invented a 24-bar E7/E/A7 verse, a 5-bar pre-chorus, a one-bar
vocal break and a 20-bar intro (159 bars, ~4:36 per pass at 138 BPM against ~2:50).
Sources: Alan W. Pollack 'Notes on Day Tripper' (intro 10, verse 16, bridge 12 on B),
Krerowicz timing table, Wikipedia. Riff-return/coda lengths are inferred from timestamps.
"""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records

LEVELS = ("Beginner", "Intermediate", "Advanced")
ORDER = ["Intro Riff", "Verse 1", "Riff Return", "Verse 2", "Guitar Break",
         "Riff Return 2", "Verse 3", "Riff Return 3", "Outro"]
BARS = {"Intro Riff": 10, "Verse 1": 16, "Riff Return": 4, "Verse 2": 16, "Guitar Break": 12,
        "Riff Return 2": 4, "Verse 3": 16, "Riff Return 3": 8, "Outro": 8}
BPM = 138
VERSE = ["E7", "E7", "E7", "E7", "A7", "A7", "E7", "E7",
         "F#7", "F#7", "F#7", "F#7", "A7", "G#7", "C#7", "B7"]
RIFF4 = ["E7", "E", "E7", "E"]
EXPECTED = {
    "Intro Riff": RIFF4 * 2 + ["E7", "E"],
    "Verse 1": VERSE, "Riff Return": RIFF4, "Verse 2": VERSE,
    "Guitar Break": ["B7"] * 12, "Riff Return 2": RIFF4, "Verse 3": VERSE,
    "Riff Return 3": RIFF4 * 2, "Outro": RIFF4 * 2,
}


class DayTripperFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "Day Tripper"))

    def test_identity_and_settings_unchanged(self):
        r = self.rec
        self.assertEqual((r["artist"], r["key"]), ("The Beatles", "E"))
        self.assertEqual(r["extensions"]["default_bpm"], BPM)
        self.assertEqual(r["extensions"]["time_signature"], "4/4")
        self.assertEqual(r["extensions"]["default_groove"], "Rock groove")
        self.assertTrue(r["extensions"]["riff_driven"])
        self.assertEqual(r["section_order"], ORDER)

    def test_exact_cells_every_level(self):
        for level in LEVELS:
            got = self.rec["chart_versions"][level]
            self.assertEqual(list(got), ORDER, level)
            self.assertEqual({k: len(v) for k, v in got.items()}, BARS, level)
            self.assertEqual(sum(len(v) for v in got.values()), 94, level)
            self.assertEqual(got, EXPECTED, level)

    def test_verse_is_pollack_16_bars_and_bridge_stays_on_b(self):
        v = self.rec["chart_versions"]["Intermediate"]["Verse 1"]
        self.assertEqual(v[:4], ["E7"] * 4)
        self.assertEqual(v[8:12], ["F#7"] * 4)
        self.assertEqual(v[12:], ["A7", "G#7", "C#7", "B7"])
        self.assertEqual(set(self.rec["chart_versions"]["Intermediate"]["Guitar Break"]), {"B7"})

    def test_invented_sections_removed(self):
        names = " ".join(self.rec["chart_versions"]["Intermediate"])
        self.assertNotIn("Pre-Chorus", names)
        self.assertNotIn("Vocal Break", names)

    def test_base_sections_are_intermediate(self):
        self.assertEqual(self.rec["sections"], self.rec["chart_versions"]["Intermediate"])

    def test_every_chord_has_a_guitar_tab(self):
        tabs = self.rec["guitar_tabs"]
        for chord in ("E7", "E", "A7", "F#7", "G#7", "C#7", "B7"):
            self.assertIn(chord, tabs)

    def test_all_cells_validate_as_events(self):
        for level in LEVELS:
            ev = sections_dict_to_events(self.rec["chart_versions"][level], time_signature="4/4", section_order=ORDER)
            self.assertEqual(len(ev), 94, level)
            self.assertEqual(validate_chord_events(ev, time_signature="4/4"), [], level)

    def test_duration_and_documented_timestamps(self):
        def secs(bars):
            return bars * 4 * 60.0 / BPM
        beats = sum(s.weight for bars in self.rec["chart_versions"]["Advanced"].values()
                    for t in bars for s in parse_subdivisions(t))
        one = beats * 60.0 / BPM
        self.assertAlmostEqual(one, 163.478260, places=3)
        self.assertLess(abs(one - 170) / 170, 0.05)  # ~2:50 recording, fade included
        self.assertAlmostEqual(secs(16), 27.83, places=2)  # Krerowicz verse 0:18-0:46 = 28 s
        self.assertAlmostEqual(secs(12), 20.87, places=2)  # break 1:21-1:42 = 21 s
        self.assertAlmostEqual(secs(10), 17.39, places=2)  # intro 0:00-0:18

    def test_level_views_trim_whole_sections_only(self):
        for level in LEVELS:
            view, sections = resolve_level_chart(self.rec, level)
            for name in view["section_order"]:
                self.assertEqual(sections[name], self.rec["chart_versions"][level][name], (level, name))

    def test_notes_and_cues_match_form(self):
        notes = self.rec["extensions"]["arrangement_notes"]
        self.assertIn("94 bars", notes)
        self.assertIn("F#7", notes)
        cues = " ".join(" ".join(v) for v in self.rec["lyric_cues"].values())
        self.assertNotIn("×5 before vocal", cues)
        self.assertNotIn("Pre-Chorus", self.rec["lyric_cues"])
        for k in self.rec["lyric_cues"]:
            self.assertIn(k, ORDER)


if __name__ == "__main__":
    unittest.main()

"""Imagine: 60 bars with shared (split) bars, matching Wikipedia's 4/12->8/8/4 form.

The earlier pack gave every chord its own bar (109 bars, 5:44 at 76 BPM against 3:03).
Sources: Wikipedia (intro 4, verse 8, chorus 8, outro 4 bars; C major, ~75 BPM, 3:03),
AZChords/Chordie charts (verse = 'C Cmaj7 F' x4 then the 7-chord descent). Cells use the
app's split-bar grammar (A|B = two beats each). Placement of the bridge's 7-chord tag
and the outro ending are LOW-MED (documented, not source-verified bar-for-bar).
"""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records

LEVELS = ("Beginner", "Intermediate", "Advanced")
ORDER = ["Intro", "Verse 1", "Bridge 1", "Verse 2", "Bridge 2", "Chorus", "Verse 3",
         "Bridge 3", "Final Chorus", "Outro"]
BARS = {"Intro": 4, "Verse 1": 8, "Bridge 1": 4, "Verse 2": 8, "Bridge 2": 4, "Chorus": 8,
        "Verse 3": 8, "Bridge 3": 4, "Final Chorus": 8, "Outro": 4}
BPM = 76
RECORDING_SECONDS = 183  # 3:03

BRIDGE = ["F|Am/E", "Dm7|F/C", "G|C/G", "G7"]


def _expected(c_open: str):
    # c_open: how the open C is spelled at this level (C or Cadd9)
    a = f"{c_open}|Cmaj7"
    verse = [a, "F"] * 4
    chorus = ["F|G", f"{c_open}|E7"] * 3 + ["F|G", a]
    return {
        "Intro": [a, "F", a, "F"], "Verse 1": verse, "Bridge 1": BRIDGE, "Verse 2": verse,
        "Bridge 2": BRIDGE, "Chorus": chorus, "Verse 3": verse, "Bridge 3": BRIDGE,
        "Final Chorus": chorus, "Outro": [a, "F", a, c_open],
    }


class ImagineSplitBarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "Imagine" and r["artist"] == "John Lennon"))

    def test_identity_and_settings_unchanged(self):
        r = self.rec
        self.assertEqual(r["key"], "C")
        self.assertEqual(r["section_order"], ORDER)
        self.assertEqual(r["extensions"]["default_bpm"], BPM)
        self.assertEqual(r["extensions"]["time_signature"], "4/4")
        self.assertEqual(r["extensions"]["default_groove"], "Ballad")

    def test_exact_cells_every_level(self):
        for level, c_open in (("Beginner", "C"), ("Intermediate", "C"), ("Advanced", "Cadd9")):
            got = self.rec["chart_versions"][level]
            self.assertEqual(list(got), ORDER, level)
            self.assertEqual({k: len(v) for k, v in got.items()}, BARS, level)
            self.assertEqual(sum(len(v) for v in got.values()), 60, level)
            self.assertEqual(got, _expected(c_open), level)

    def test_bridge_keeps_all_seven_chords_in_order(self):
        flat = [p for cell in self.rec["chart_versions"]["Intermediate"]["Bridge 1"] for p in cell.split("|")]
        self.assertEqual(flat, ["F", "Am/E", "Dm7", "F/C", "G", "C/G", "G7"])

    def test_split_cells_are_even_two_beat_halves(self):
        for cell in ("C|Cmaj7", "F|G", "C|E7", "F|Am/E", "Dm7|F/C", "G|C/G"):
            subs = parse_subdivisions(cell)
            self.assertEqual([s.weight for s in subs], [2.0, 2.0], cell)

    def test_base_sections_are_intermediate(self):
        self.assertEqual(self.rec["sections"], self.rec["chart_versions"]["Intermediate"])

    def test_all_cells_validate_as_events(self):
        for level in LEVELS:
            ev = sections_dict_to_events(self.rec["chart_versions"][level], time_signature="4/4", section_order=ORDER)
            # split bars emit one event per chord: 60 bars, 41 of them split in two
            split_bars = sum(1 for b in self.rec['chart_versions'][level].values() for c in b if '|' in c)
            self.assertEqual(len(ev), 60 + split_bars, level)
            self.assertEqual(validate_chord_events(ev, time_signature="4/4"), [], level)

    def test_one_pass_matches_recording(self):
        beats = sum(s.weight for bars in self.rec["chart_versions"]["Advanced"].values()
                    for t in bars for s in parse_subdivisions(t))
        one = beats * 60.0 / BPM
        self.assertAlmostEqual(one, 189.473684, places=3)
        self.assertLess(abs(one - RECORDING_SECONDS) / RECORDING_SECONDS, 0.05)

    def test_level_views_trim_whole_sections_only(self):
        for level in LEVELS:
            view, sections = resolve_level_chart(self.rec, level)
            for name in view["section_order"]:
                self.assertEqual(sections[name], self.rec["chart_versions"][level][name], (level, name))

    def test_notes_and_guitar_tabs(self):
        self.assertIn("60 bars", self.rec["extensions"]["arrangement_notes"])
        for chord in ("C", "Cadd9", "Cmaj7", "F", "G", "Am/E", "Dm7", "F/C", "C/G", "G7", "E7"):
            self.assertIn(chord, self.rec["guitar_tabs"])


if __name__ == "__main__":
    unittest.main()

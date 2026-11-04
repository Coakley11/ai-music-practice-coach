"""Photograph is charted two bars per chord (pre-chorus one bar): 116 bars ~ 4:19 recording.

The earlier pack held every chord twice as long (232 bars, 8:36 per pass at 108 BPM
against a 4:19 recording). Chords, voicings, section names/order, key and BPM are unchanged.
"""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records

LEVELS = ("Beginner", "Intermediate", "Advanced")
ORDER = ["Intro", "Verse 1", "Pre-Chorus 1", "Chorus 1", "Verse 2", "Pre-Chorus 2",
         "Chorus 2", "Bridge", "Chorus 3", "Outro"]
BARS = {"Intro": 8, "Verse 1": 16, "Pre-Chorus 1": 8, "Chorus 1": 10, "Verse 2": 16,
        "Pre-Chorus 2": 8, "Chorus 2": 16, "Bridge": 8, "Chorus 3": 24, "Outro": 2}
# Hand-written role chords: I, vi, V, IV
ROLES = {
    "Beginner": ("E", "C#m", "B", "A"),
    "Intermediate": ("Eadd9", "C#m7", "Bsus4", "Aadd9"),
    "Advanced": ("Emaj9", "C#m11", "B11sus", "Amaj9"),
}
BPM = 108
RECORDING_SECONDS = 259  # 4:19


def _x2(*chords):
    return [c for c in chords for _ in range(2)]


def _expected(level):
    i, vi, v, iv = ROLES[level]
    verse = _x2(i, vi, v, iv)
    pre = [vi, iv, i, v] * 2
    chorus = _x2(i, v, vi, iv)
    return {
        "Intro": list(verse),
        "Verse 1": verse * 2,
        "Pre-Chorus 1": list(pre),
        "Chorus 1": chorus + [i, i],
        "Verse 2": verse * 2,
        "Pre-Chorus 2": list(pre),
        "Chorus 2": chorus * 2,
        "Bridge": _x2(vi, iv, i, v),
        "Chorus 3": chorus * 3,
        "Outro": [i, i],
    }


class PhotographHalvedHoldsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "Photograph"))

    def test_identity_and_settings_unchanged(self):
        r = self.rec
        self.assertEqual((r["artist"], r["key"]), ("Ed Sheeran", "E"))
        self.assertEqual(r["section_order"], ORDER)
        self.assertEqual(r["extensions"]["default_bpm"], BPM)
        self.assertEqual(r["extensions"]["time_signature"], "4/4")
        self.assertEqual(r["extensions"]["default_groove"], "Modern Acoustic Pop Ballad")

    def test_exact_cells_every_level(self):
        for level in LEVELS:
            sections = self.rec["chart_versions"][level]
            self.assertEqual(list(sections), ORDER, level)
            self.assertEqual({k: len(v) for k, v in sections.items()}, BARS, level)
            self.assertEqual(sum(len(v) for v in sections.values()), 116, level)
            self.assertEqual(sections, _expected(level), level)

    def test_literal_intermediate_intro_and_pre_chorus(self):
        s = self.rec["chart_versions"]["Intermediate"]
        self.assertEqual(s["Intro"], ["Eadd9", "Eadd9", "C#m7", "C#m7", "Bsus4", "Bsus4", "Aadd9", "Aadd9"])
        self.assertEqual(s["Pre-Chorus 1"], ["C#m7", "Aadd9", "Eadd9", "Bsus4"] * 2)
        self.assertEqual(s["Outro"], ["Eadd9", "Eadd9"])

    def test_base_sections_are_intermediate(self):
        self.assertEqual(self.rec["sections"], self.rec["chart_versions"]["Intermediate"])

    def test_all_cells_validate_as_events(self):
        for level in LEVELS:
            ev = sections_dict_to_events(self.rec["chart_versions"][level], time_signature="4/4", section_order=ORDER)
            self.assertEqual(len(ev), 116, level)
            self.assertEqual(validate_chord_events(ev, time_signature="4/4"), [], level)

    def test_one_pass_matches_recording(self):
        beats = sum(s.weight for bars in self.rec["chart_versions"]["Advanced"].values()
                    for t in bars for s in parse_subdivisions(t))
        one = beats * 60.0 / BPM
        self.assertAlmostEqual(one, 257.7777777, places=3)
        self.assertLess(abs(one - RECORDING_SECONDS) / RECORDING_SECONDS, 0.02)

    def test_level_views_trim_whole_sections_only(self):
        for level in LEVELS:
            view, sections = resolve_level_chart(self.rec, level)
            for name in view["section_order"]:
                self.assertEqual(sections[name], self.rec["chart_versions"][level][name], (level, name))

    def test_notes_and_cues_match_new_pacing(self):
        notes = self.rec["extensions"]["arrangement_notes"]
        for stale in ("4 bars", "(20 bars", "(32 bars", "(48 bars", "4-bar"):
            self.assertNotIn(stale, notes)
        for needle in ("116 bars", "2 bars", "every bar"):
            self.assertIn(needle, notes)
        cues = " ".join(" ".join(v) for v in self.rec["lyric_cues"].values())
        for stale in ("4 full bars", "4-bar", "2-bar holds"):
            self.assertNotIn(stale, cues)
        self.assertEqual(list(self.rec["lyric_cues"]), ORDER)


if __name__ == "__main__":
    unittest.main()

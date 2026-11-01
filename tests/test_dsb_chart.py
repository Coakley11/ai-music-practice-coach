"""Don't Stop Believin' is charted one chord per bar (125 bars ~ the 4:11 recording).

The earlier pack held every piano-cycle chord two bars and every chorus pedal four
(239 bars, ~8:00 per pass at 119 BPM against 4:11). The recording's piano intro is
eight chords in about 17 s, i.e. one bar each. Chorus tag cells (1-bar B/E/B...) are
unchanged. Chords, voicings, section names/order, key and BPM are unchanged.
"""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records

LEVELS = ("Beginner", "Intermediate", "Advanced")
ORDER = ["Intro", "Verse 1", "Interlude 1", "Verse 2", "Chorus 1", "Interlude 2",
         "Verse 3", "Chorus 2", "Guitar Solo / Interlude", "Outro"]
BARS = {"Intro": 8, "Verse 1": 16, "Interlude 1": 8, "Verse 2": 8, "Chorus 1": 20,
        "Interlude 2": 4, "Verse 3": 16, "Chorus 2": 19, "Guitar Solo / Interlude": 8, "Outro": 18}
BPM = 119
RECORDING_SECONDS = 251  # 4:11

# Hand-written cells per level.
CYCLE = {
    "Beginner": ["E", "B", "C#m", "A", "E", "B", "G#m", "A"],
    "Intermediate": ["E", "B/D#", "C#m7", "Aadd9", "E", "B/D#", "G#m7", "Aadd9"],
    "Advanced": ["Eadd9", "B/D#", "C#m9", "Amaj9", "Eadd9", "B/D#", "G#m9", "Amaj9"],
}
PEDAL = {  # 14-bar chorus body: A A E E x3, A A
    "Beginner": ("A", "E"),
    "Intermediate": ("Aadd9", "E"),
    "Advanced": ("Amaj9", "Eadd9"),
}
TAG1 = {  # B E B A A A
    "Beginner": ["B", "E", "B", "A", "A", "A"],
    "Intermediate": ["B", "E", "B", "Aadd9", "Aadd9", "Aadd9"],
    "Advanced": ["B13sus", "Eadd9", "B13sus", "Amaj9", "Amaj9", "Amaj9"],
}
TAG2 = {  # B E B B B
    "Beginner": ["B", "E", "B", "B", "B"],
    "Intermediate": ["B", "E", "B", "B", "B"],
    "Advanced": ["B13sus", "Eadd9", "B13sus", "B13sus", "B13sus"],
}


def _body(level):
    a, e = PEDAL[level]
    return ([a, a, e, e] * 3) + [a, a]


class DsbOneBarPerChordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "Don't Stop Believin'"))

    def test_identity_and_settings_unchanged(self):
        r = self.rec
        self.assertEqual((r["artist"], r["key"]), ("Journey", "E"))
        self.assertEqual(r["section_order"], ORDER)
        self.assertEqual(r["extensions"]["default_bpm"], BPM)
        self.assertEqual(r["extensions"]["time_signature"], "4/4")
        self.assertEqual(r["extensions"]["default_groove"], "Rock groove")

    def test_exact_cells_every_level(self):
        for level in LEVELS:
            c = CYCLE[level]
            exp = {
                "Intro": c, "Verse 1": c * 2, "Interlude 1": c, "Verse 2": c,
                "Chorus 1": _body(level) + TAG1[level],
                "Interlude 2": c[:4], "Verse 3": c * 2,
                "Chorus 2": _body(level) + TAG2[level],
                "Guitar Solo / Interlude": c, "Outro": c * 2 + c[:2],
            }
            got = self.rec["chart_versions"][level]
            self.assertEqual(list(got), ORDER, level)
            self.assertEqual({k: len(v) for k, v in got.items()}, BARS, level)
            self.assertEqual(sum(len(v) for v in got.values()), 125, level)
            self.assertEqual(got, exp, level)

    def test_piano_intro_is_eight_chords_one_bar_each(self):
        intro = self.rec["chart_versions"]["Intermediate"]["Intro"]
        self.assertEqual(intro, ["E", "B/D#", "C#m7", "Aadd9", "E", "B/D#", "G#m7", "Aadd9"])
        self.assertAlmostEqual(8 * 4 * 60.0 / BPM, 16.13, places=2)  # recording intro ~17 s

    def test_base_sections_are_intermediate(self):
        self.assertEqual(self.rec["sections"], self.rec["chart_versions"]["Intermediate"])

    def test_all_cells_validate_as_events(self):
        for level in LEVELS:
            ev = sections_dict_to_events(self.rec["chart_versions"][level], time_signature="4/4", section_order=ORDER)
            self.assertEqual(len(ev), 125, level)
            self.assertEqual(validate_chord_events(ev, time_signature="4/4"), [], level)

    def test_one_pass_matches_recording(self):
        beats = sum(s.weight for bars in self.rec["chart_versions"]["Advanced"].values()
                    for t in bars for s in parse_subdivisions(t))
        one = beats * 60.0 / BPM
        self.assertAlmostEqual(one, 252.100840, places=3)
        self.assertLess(abs(one - RECORDING_SECONDS) / RECORDING_SECONDS, 0.02)

    def test_level_views_trim_whole_sections_only(self):
        for level in LEVELS:
            view, sections = resolve_level_chart(self.rec, level)
            for name in view["section_order"]:
                self.assertEqual(sections[name], self.rec["chart_versions"][level][name], (level, name))

    def test_notes_and_cues_match_new_pacing(self):
        notes = self.rec["extensions"]["arrangement_notes"]
        for stale in ("honest", "239", "4-bar holds", "E(2) -> B(2)", "16-bar"):
            self.assertNotIn(stale, notes)
        for needle in ("125 bars", "one chord per bar", "2-bar holds"):
            self.assertIn(needle, notes)
        cues = " ".join(" ".join(v) for v in self.rec["lyric_cues"].values())
        for stale in ("16-bar", "4-bar holds", "E (2) / B (2)", "long holds", "Short 8-bar"):
            self.assertNotIn(stale, cues)
        self.assertEqual(list(self.rec["lyric_cues"]), ORDER)


if __name__ == "__main__":
    unittest.main()

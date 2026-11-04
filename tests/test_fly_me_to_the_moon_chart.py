"""Fly Me to the Moon (Bart Howard) is the complete 32-bar form at every level.

Reference: printed lead sheet in C (Cleary/UVM MU 104 charts, "Fly Me to the
Moon" c major; bars numbered 1-32), cross-checked with 8notes and Learn Jazz
Standards.  Form: A (1-8) B (9-16) A' (17-24) B' (25-32):
 A : Am7 Dm7 G7 Cmaj7 | Fmaj7 Bm7b5 E7(b9) Am7
 B : Dm7 G7(G9|G7b9) Cmaj7 Am7 | Dm7 G7 Cmaj7 Bm7|E7   (bar 16 two chords)
 A': as A
 B': Dm7 G9 Em7b5 A7(b9) | Dm7 G7b9 C6 Bm7|E7
Split bars `Bm7|E7` are 2 beats each (bar 16 and 32 of the lead sheet print
Bm7 on beat 1 and E7 on beat 3).  NOT encoded (single source or beat placement
uncertain): A7b9 on the last beat of bars 8/24, Fdim7 passing chord in bar 15,
G9|G7b9 split in bars 10/26, and the coda (Fm7 Bb7 B7 C6/9).
The old chart had A2 = A7 Dm7 G7 Cmaj7 E7 Am7 A7 Dm7 (not in any source) and
Beginner/Intermediate stopped after A2 / dropped the last A.
"""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records

ORDER = ["A1", "B1", "A2", "B2"]
EXPECT = {
    "Beginner": {
        "A1": ["Am", "Dm", "G7", "C", "F", "Bm7b5", "E7", "Am"],
        "B1": ["Dm", "G7", "C", "Am", "Dm", "G7", "C", "Bm|E7"],
        "A2": ["Am", "Dm", "G7", "C", "F", "Bm7b5", "E7", "Am"],
        "B2": ["Dm", "G7", "Em7b5", "A7", "Dm", "G7", "C", "Bm|E7"],
    },
    "Intermediate": {
        "A1": ["Am7", "Dm7", "G7", "Cmaj7", "Fmaj7", "Bm7b5", "E7", "Am7"],
        "B1": ["Dm7", "G7", "Cmaj7", "Am7", "Dm7", "G7", "Cmaj7", "Bm7|E7"],
        "A2": ["Am7", "Dm7", "G7", "Cmaj7", "Fmaj7", "Bm7b5", "E7", "Am7"],
        "B2": ["Dm7", "G7", "Em7b5", "A7", "Dm7", "G7", "C6", "Bm7|E7"],
    },
    "Advanced": {
        "A1": ["Am9", "Dm9", "G13", "Cmaj9", "Fmaj9", "Bm7b5", "E7b9", "Am9"],
        "B1": ["Dm9", "G13", "Cmaj9", "Am9", "Dm9", "G13", "Cmaj9", "Bm7|E7"],
        "A2": ["Am9", "Dm9", "G13", "Cmaj9", "Fmaj9", "Bm7b5", "E7b9", "Am9"],
        "B2": ["Dm9", "G13", "Em7b5", "A7b9", "Dm9", "G7b9", "C6", "Bm7|E7"],
    },
}


class FlyMeToTheMoonChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(
            next(r for r in curated_song_records() if r["title"] == "Fly Me to the Moon")
        )

    def test_every_level_plays_all_four_sections_32_bars(self) -> None:
        self.assertEqual(self.rec["key"], "C")
        for level, expected in EXPECT.items():
            view, sections = resolve_level_chart(self.rec, level)
            self.assertEqual(list(sections), ORDER, level)
            self.assertEqual(sections, expected, level)
            self.assertEqual(sum(len(v) for v in sections.values()), 32, level)

    def test_turnaround_bars_are_two_chords(self) -> None:
        for level, expected in EXPECT.items():
            for name in ("B1", "B2"):
                self.assertEqual(expected[name][7].count("|"), 1)
                self.assertTrue(expected[name][7].endswith("E7"))

    def test_events_validate_and_one_pass_length(self) -> None:
        for level, expected in EXPECT.items():
            events = sections_dict_to_events(expected, time_signature="4/4", section_order=ORDER)
            self.assertEqual(len(events), 34, level)  # 32 bars + 2 split bars
            self.assertEqual(validate_chord_events(events, time_signature="4/4"), [], level)
            beats = sum(s.weight for bars in expected.values() for t in bars for s in parse_subdivisions(t))
            self.assertAlmostEqual(beats, 128.0, places=6)
            self.assertAlmostEqual(beats * 60.0 / 100, 76.8, places=6)  # fallback 100 BPM


if __name__ == "__main__":
    unittest.main()

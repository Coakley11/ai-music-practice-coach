"""Autumn Leaves (both catalog entries) is the 32-bar AABC head, at every level.

Reference form (G minor, transposed +4 semitones to the catalog key Bm):
  printed Real Book chart (Em; Open Studio Jazz "Lead Sheet Breakdown"
  transcription), Dave Jones lead sheet (Gm; A, B, C, D blocks of 8 bars),
  Better Bass Lessons / Ensemble PR #1891 (bars 27-30 walk-down).
A  (8): Cm7 F7 Bbmaj7 Ebmaj7 | Am7b5 D7 Gm Gm
A2 (8): same
B  (8): Am7b5 D7 Gm Gm | Cm7 F7 Bbmaj7 Ebmaj7
C  (8): Am7b5 D7 | Gm7|Gb7 | Fm7|E7 | Ebmaj7 | D7 | Gm Gm
Split bars (chord|chord) are two chords in one 4/4 bar, 2 beats each; the
Real Book prints Em7 Eb7 / Dm7 Db7 (G minor: Gm7 Gb7 / Fm7 E7) as two bars
of two chords.  Edition-dependent and NOT encoded: diatonic Gm7|C7 Fm7|Bb7,
Am7b5 instead of Ebmaj7 in bar 29, a final G7 turnaround.
Bm is the catalog key; no key-label change.
"""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records

ORDER = ["A Section", "A2", "B Section", "C Section"]
A_I = ["Em7", "A7", "Dmaj7", "Gmaj7", "C#m7b5", "F#7", "Bm", "Bm"]
EXPECT = {
    "Beginner": {
        "A Section": ["Em", "A7", "D", "G", "C#dim", "F#7", "Bm", "Bm"],
        "A2": ["Em", "A7", "D", "G", "C#dim", "F#7", "Bm", "Bm"],
        "B Section": ["C#dim", "F#7", "Bm", "Bm", "Em", "A7", "D", "G"],
        "C Section": ["C#dim", "F#7", "Bm|Bb7", "Am|G#7", "G", "F#7", "Bm", "Bm"],
    },
    "Intermediate": {
        "A Section": A_I,
        "A2": A_I,
        "B Section": ["C#m7b5", "F#7", "Bm", "Bm", "Em7", "A7", "Dmaj7", "Gmaj7"],
        "C Section": ["C#m7b5", "F#7", "Bm7|Bb7", "Am7|G#7", "Gmaj7", "F#7", "Bm", "Bm"],
    },
    "Advanced": {
        "A Section": ["Em9", "A13", "Dmaj9", "Gmaj9", "C#m7b5", "F#7b9", "Bm9", "Bm9"],
        "A2": ["Em9", "A13", "Dmaj9", "Gmaj9", "C#m7b5", "F#7b9", "Bm9", "Bm9"],
        "B Section": ["C#m7b5", "F#7b9", "Bm9", "Bm9", "Em9", "A13", "Dmaj9", "Gmaj9"],
        "C Section": ["C#m7b5", "F#7b9", "Bm7|Bb7", "Am7|G#7", "Gmaj9", "F#7b9", "Bm9", "Bm9"],
    },
}


class AutumnLeavesChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.recs = [
            copy.deepcopy(r)
            for r in curated_song_records()
            if r["title"] == "Autumn Leaves"
        ]

    def test_both_entries_exist_and_match(self) -> None:
        self.assertEqual(
            sorted(r["artist"] for r in self.recs), ["Eric Clapton", "Jazz Standard"]
        )
        a, b = self.recs
        self.assertEqual(a["chart_versions"], b["chart_versions"])
        self.assertEqual(a["section_order"], b["section_order"])
        for r in self.recs:
            self.assertEqual(r["key"], "Bm")
            self.assertEqual(r["extensions"]["default_bpm"], 82)

    def test_every_level_is_the_full_32_bar_aabc_form(self) -> None:
        for r in self.recs:
            for level, expected in EXPECT.items():
                view, sections = resolve_level_chart(r, level)
                self.assertEqual(list(sections), ORDER, (r["artist"], level))
                self.assertEqual(sections, expected, (r["artist"], level))
                self.assertEqual(sum(len(v) for v in sections.values()), 32)

    def test_walk_down_bars_are_two_chords_each(self) -> None:
        for level, expected in EXPECT.items():
            cells = expected["C Section"]
            self.assertEqual([c.count("|") for c in cells], [0, 0, 1, 1, 0, 0, 0, 0])
            self.assertTrue(cells[2].startswith("Bm") and cells[2].endswith("Bb7"))
            self.assertTrue(cells[3].startswith("Am") and cells[3].endswith("G#7"))

    def test_events_validate_and_duration(self) -> None:
        for level, expected in EXPECT.items():
            events = sections_dict_to_events(expected, time_signature="4/4", section_order=ORDER)
            self.assertEqual(len(events), 34, level)  # 32 bars, 2 split bars = 2 extra events
            self.assertEqual(validate_chord_events(events, time_signature="4/4"), [], level)
            beats = sum(s.weight for bars in expected.values() for t in bars for s in parse_subdivisions(t))
            self.assertAlmostEqual(beats, 128.0, places=6)
            self.assertAlmostEqual(beats * 60.0 / 82, 93.658536, places=5)


if __name__ == "__main__":
    unittest.main()

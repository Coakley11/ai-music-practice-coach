"""All the Things You Are (both catalog entries): A / A2 / Bridge / A3, 36 bars, ends on Ab."""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records

ORDER = ["A", "A2", "Bridge", "A3"]
ADV = {
    "A": ["Fm7", "Bbm7", "Eb7", "Abmaj7", "Dbmaj7", "G7", "Cmaj7", "Cmaj7"],
    "A2": ["Cm7", "Fm7", "Bb7", "Ebmaj7", "Abmaj7", "Am7|D7", "Gmaj7", "Gmaj7"],
    "Bridge": ["Am7", "D7", "Gmaj7", "Gmaj7", "F#m7", "B7", "Emaj7", "C7#5"],
    "A3": ["Fm7", "Bbm7", "Eb7", "Abmaj7", "Dbmaj7", "Dbm7", "Cm7", "Bdim7", "Bbm7", "Eb7", "Abmaj7", "Abmaj7"],
}
BEG = {
    "A": ["Fm", "Bbm", "Eb7", "Ab", "Db", "G7", "C", "C"],
    "A2": ["Cm", "Fm", "Bb7", "Eb", "Ab", "Am|D7", "G", "G"],
    "Bridge": ["Am", "D7", "G", "G", "F#m", "B7", "E", "C7"],
    "A3": ["Fm", "Bbm", "Eb7", "Ab", "Db", "Dbm", "Cm", "Bdim", "Bbm", "Eb7", "Ab", "Ab"],
}


class AttyaChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.recs = [
            copy.deepcopy(r)
            for r in curated_song_records()
            if r["title"] == "All the Things You Are"
        ]

    def test_both_catalog_entries_exist_and_are_identical(self) -> None:
        self.assertEqual({r["artist"] for r in self.recs}, {"Jazz Standard", "Jerome Kern"})
        a, b = self.recs
        for key in ("sections", "chart_versions", "section_order", "lyric_cues"):
            self.assertEqual(a[key], b[key], key)

    def test_levels_exact(self) -> None:
        for rec in self.recs:
            self.assertEqual(rec["key"], "Ab")
            self.assertEqual(rec["section_order"], ORDER)
            cv = rec["chart_versions"]
            self.assertEqual(cv["Advanced"], ADV)
            self.assertEqual(cv["Intermediate"], ADV)
            self.assertEqual(cv["Beginner"], BEG)
            self.assertEqual(rec["sections"], ADV)
            for level in ("Beginner", "Intermediate", "Advanced"):
                self.assertEqual(sum(len(v) for v in cv[level].values()), 36, level)

    def test_every_level_plays_the_whole_form_ending_on_ab(self) -> None:
        for rec in self.recs:
            for level, last in (("Beginner", "Ab"), ("Intermediate", "Abmaj7"), ("Advanced", "Abmaj7")):
                view, sections = resolve_level_chart(rec, level)
                self.assertEqual(list(sections), ORDER, level)
                self.assertEqual(sections["A3"][-1], last, level)
                self.assertEqual(sum(len(v) for v in sections.values()), 36, level)

    def test_lyric_cues_follow_new_section_names(self) -> None:
        for rec in self.recs:
            self.assertEqual(list(rec["lyric_cues"]), ORDER)

    def test_cells_validate_and_duration_unchanged(self) -> None:
        for chart in (ADV, BEG):
            events = sections_dict_to_events(chart, time_signature="4/4", section_order=ORDER)
            self.assertEqual(validate_chord_events(events, time_signature="4/4"), [])
        beats = sum(s.weight for bars in ADV.values() for t in bars for s in parse_subdivisions(t))
        self.assertAlmostEqual(beats * 60.0 / 72, 120.0, places=6)


if __name__ == "__main__":
    unittest.main()

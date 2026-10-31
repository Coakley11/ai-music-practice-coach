"""Misty: AABA 32 bars with Abmaj7 and the Abm7|Db7 backdoor ii-V; explicit Beginner keeps dominants.

Reference edition: the chord-melody lead sheet at jazz-guitar-licks.com and the
Guitar Composer's Toolbox chart (in Eb), cross-checked against the Learn Jazz
Standards prose, jazzstandards.com and standardrepertoire.com.

HIGH confidence: A bars 1-6 and bridge bars 1-5 (Ebmaj7, Bbm7|Eb7, Abmaj7,
Abm7|Db7, Ebmaj7|Cm7, Fm7|Bb7; Bbm7, Eb7, Abmaj7, Abmaj7, Am7).
MED: bridge bars 6-8 placement and the two A-section endings (Gm7|C7 Fm7|Bb7
first ending, Eb6 Eb6 second ending).
Edition choice: the bridge uses the simpler Am7, D7, Gm7|C7, Fm7|Bb7 reading;
the richer single-edition variant (D7|F7, Gm7b5|C7b9) is NOT used.
The song has no default_bpm, so it plays at the 100 BPM fallback.
"""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records

ORDER = ["A", "A2", "Bridge", "A3"]
HEAD = ["Ebmaj7", "Bbm7|Eb7", "Abmaj7", "Abm7|Db7", "Ebmaj7|Cm7", "Fm7|Bb7"]
ADV = {
    "A": HEAD + ["Gm7|C7", "Fm7|Bb7"],
    "A2": HEAD + ["Eb6", "Eb6"],
    "Bridge": ["Bbm7", "Eb7", "Abmaj7", "Abmaj7", "Am7", "D7", "Gm7|C7", "Fm7|Bb7"],
    "A3": HEAD + ["Eb6", "Eb6"],
}
BHEAD = ["Eb", "Bbm|Eb7", "Ab", "Abm|Db7", "Eb|Cm", "Fm|Bb7"]
BEG = {
    "A": BHEAD + ["Gm|C7", "Fm|Bb7"],
    "A2": BHEAD + ["Eb", "Eb"],
    "Bridge": ["Bbm", "Eb7", "Ab", "Ab", "Am", "D7", "Gm|C7", "Fm|Bb7"],
    "A3": BHEAD + ["Eb", "Eb"],
}


class MistyChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "Misty"))

    def test_exact_levels(self) -> None:
        cv = self.rec["chart_versions"]
        self.assertEqual(cv["Advanced"], ADV)
        self.assertEqual(cv["Intermediate"], ADV)
        self.assertEqual(cv["Beginner"], BEG)
        self.assertEqual(self.rec["sections"], ADV)
        self.assertEqual(self.rec["section_order"], ORDER)
        self.assertEqual(self.rec["key"], "Eb")

    def test_signature_chords_present_and_old_chords_gone(self) -> None:
        cells = " ".join(c for bars in ADV.values() for c in bars)
        self.assertIn("Abmaj7", cells)
        self.assertIn("Abm7|Db7", cells)
        self.assertNotIn("Am7b5", cells)

    def test_beginner_has_no_doubled_roots_and_keeps_backdoor_dominant(self) -> None:
        _, sections = resolve_level_chart(self.rec, "Beginner")
        cells = [c for bars in sections.values() for c in bars]
        self.assertIn("Abm|Db7", cells)
        for bad in ("EbEb", "DbDb", "BbBb", "CC", "DD", "FF"):
            self.assertFalse(any(bad in c for c in cells), bad)

    def test_all_levels_32_bars_whole_form(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            _, sections = resolve_level_chart(self.rec, level)
            self.assertEqual(list(sections), ORDER, level)
            self.assertEqual(sum(len(v) for v in sections.values()), 32, level)

    def test_cells_validate_and_duration(self) -> None:
        for chart in (ADV, BEG):
            events = sections_dict_to_events(chart, time_signature="4/4", section_order=ORDER)
            self.assertEqual(validate_chord_events(events, time_signature="4/4"), [])
        beats = sum(s.weight for bars in ADV.values() for t in bars for s in parse_subdivisions(t))
        self.assertAlmostEqual(beats * 60.0 / 100, 76.8, places=6)


if __name__ == "__main__":
    unittest.main()

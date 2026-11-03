"""Wave (Jobim): published AABA form, 12-bar A + 8-bar bridge (44-bar head).

The catalog had a 16-bar verse (Dmaj9 Bbdim7 Am7 D7b9 Gmaj7 Gm6 F#7 B7b9 Bm7 E7
Bb7 A7 Dm7 G7 Dm7 G7; Bm7 is not in any published chart) and an 8-bar bridge
Gm7 C7 Am7 Am6 Ab6 Bb7b9 Gm7 A7#5. Sources:
 * Guitar Composer Toolbox "Wave in D" (bar grid: Dmaj7 Bbdim7 Am7 D7b9 Gmaj7
   Gm6 F#13|F#7b13 B9|B7b9 E9 Bb7|A7 Dm7|G7 Dm7|G7).
 * guitartabs.cc Wave chords: 10-bar A (Dmaj7 | Bb | Am7 | A/D | Gmaj7 | Gm6 |
   F#6 | B7 | E7sus2 | Bb7 A7) then `Dm7 G7` vamp (4x); 8-bar bridge.
 * standardrepertoire.com: 44 bars, AABA (12+12+8+12).
 * jazzguitar.be forum: A is a reharmonised 12-bar blues with A7 in the 2nd
   half of bar 10; PianoGroove (Real Book): B7b9 on beat 3 of bar 24 = bar 8 of
   the second A (`B9|B7b9`, beat 3).
Split bars (beats): `Bb7|A7` = 2+2 in bar 10 (A7 on beat 3); `Dm7|G7` = 2+2
(G7 on beat 3); `F#13|F#7b13`, `B9|B7b9` = 2+2.
Held (MED): bridge bar 7 (Gm7 vs guitartabs Ebmaj7).
"""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import keeps_full_form, resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records

ORDER = ["Intro", "Verse 1", "Verse 2", "Bridge", "Verse 3", "Instrumental", "Bridge 2", "Final Verse", "Outro"]
BARS = {"Intro": 4, "Verse 1": 12, "Verse 2": 12, "Bridge": 8, "Verse 3": 12,
        "Instrumental": 12, "Bridge 2": 8, "Final Verse": 12, "Outro": 4}
LEVELS = ("Beginner", "Intermediate", "Advanced")
A_INT = ["Dmaj7", "Bbdim7", "Am7", "D7b9", "Gmaj7", "Gm6", "F#7", "B7b9",
         "E7", "Bb7|A7", "Dm7|G7", "Dm7|G7"]
A_ADV = ["Dmaj7", "Bbdim7", "Am7", "D7b9", "Gmaj7", "Gm6", "F#13|F#7b13", "B9|B7b9",
         "E9", "Bb7|A7", "Dm7|G7", "Dm7|G7"]
A_BEG = ["D", "Bbdim", "Am", "D7", "G", "Gm", "F#7", "B7",
         "E7", "Bb7|A7", "Dm|G7", "Dm|G7"]
BR_INT = ["Gm7", "C7", "Fmaj7", "Fmaj7", "Fm7", "Bb7", "Gm7", "A7"]
BR_ADV = ["Gm7/Bb", "C7/Bb", "Fmaj7/A", "Fmaj7/A", "Fm7/Ab", "Bb7/Ab", "Gm7", "A7"]


class WaveChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "Wave"))

    def test_intermediate_cells(self) -> None:
        s = self.rec["chart_versions"]["Intermediate"]
        self.assertEqual(list(s), ORDER)
        for name in ("Verse 1", "Verse 2", "Verse 3", "Instrumental", "Final Verse"):
            self.assertEqual(s[name], A_INT, name)
        self.assertEqual(s["Bridge"], BR_INT)
        self.assertEqual(s["Intro"], ["Dm7|G7"] * 4)
        self.assertEqual(s["Outro"], ["Dm7|G7"] * 4)

    def test_beginner_and_advanced_cells(self) -> None:
        beg = self.rec["chart_versions"]["Beginner"]
        adv = self.rec["chart_versions"]["Advanced"]
        self.assertEqual(beg["Verse 1"], A_BEG)
        self.assertEqual(beg["Bridge"], ["Gm", "C7", "F", "F", "Fm", "Bb7", "Gm", "A7"])
        self.assertEqual(adv["Verse 1"], A_ADV)
        self.assertEqual(adv["Bridge"], BR_ADV)
        for lv in LEVELS:
            self.assertEqual({k: len(v) for k, v in self.rec["chart_versions"][lv].items()}, BARS, lv)

    def test_unsourced_bars_are_gone(self) -> None:
        for lv in LEVELS:
            flat = [c for bars in self.rec["chart_versions"][lv].values() for c in bars]
            for bad in ("Bm7", "Bm", "A7#5", "Am6", "Ab6", "Bb7b9", "G13", "Dmaj9"):
                self.assertNotIn(bad, flat, (lv, bad))

    def test_split_bars_total_four_beats(self) -> None:
        for lv in LEVELS:
            for sec, bars in self.rec["chart_versions"][lv].items():
                for bar in bars:
                    parts = parse_subdivisions(bar)
                    self.assertAlmostEqual(sum(p.weight for p in parts), 4.0, msg=(lv, sec, bar))
                    if "|" in bar:
                        self.assertEqual([p.weight for p in parts], [2.0, 2.0], (lv, sec, bar))

    def test_all_levels_play_the_full_form(self) -> None:
        for lv in LEVELS:
            _view, sections = resolve_level_chart(self.rec, lv)
            self.assertEqual(list(sections), ORDER, lv)
            self.assertEqual(sum(len(v) for v in sections.values()), 84, lv)
        self.assertTrue(keeps_full_form(self.rec, "Beginner"))
        self.assertTrue(keeps_full_form(self.rec, "Intermediate"))

    def test_duration_at_120_bpm(self) -> None:
        # 84 bars x 4 beats x 0.5 s = 168 s per pass
        self.assertEqual(self.rec["extensions"]["default_bpm"], 120)
        for lv in LEVELS:
            _v, sections = resolve_level_chart(self.rec, lv)
            beats = sum(sum(p.weight for p in parse_subdivisions(c)) for b in sections.values() for c in b)
            self.assertAlmostEqual(beats * 60 / 120, 168.0, msg=lv)

    def test_events_validate(self) -> None:
        for lv in LEVELS:
            _v, sections = resolve_level_chart(self.rec, lv)
            events = sections_dict_to_events(sections, time_signature="4/4", section_order=ORDER)
            self.assertEqual(validate_chord_events(events, time_signature="4/4"), [], lv)


if __name__ == "__main__":
    unittest.main()

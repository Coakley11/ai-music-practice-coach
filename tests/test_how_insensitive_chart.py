"""How Insensitive (Jobim): published 32-bar AB form, two-bar chords.

Catalog had A `Dm9 Dm9/C Bdim7 Bbmaj7 A7 A7 Dm Dm` and B `Gm7 C7 Fmaj7 Bbmaj7
Em7b5 A7 Dm A7`: not the published changes (those descend D-C#-C-B-Bb in the
bass).  Sources: Guitar Composer Toolbox "How Insensitive in D" (A: Dm % C#dim7
% Cm6 % G7/B % Bbmaj7 % Ebmaj7#11 % Em7b5 A7b9 Dm C#7; B: Cm6 % Bdim7 % Bbmaj7
Em7b5|A7b9 Dm C#7 Cm7 F7 Bm7 E7b9 Bbmaj7 A7b9 Dm %), its Real Book variant
(A7/C# for C#dim7; 32 bars, same A), standardrepertoire.com (32 bars, AB) and a
jazzguitar.be player chart (Dm9 C#dim7 Cm6 G/B Bbmaj7).  Bdim7 is NOT suspect:
it is the B section's bars 3-4.  Beats: `%` = the previous bar repeated, so every
whole chord lasts 2 bars (8 beats); `Em7b5|A7b9` = 2+2 beats (A7b9 on beat 3 of
B bar 6).  Held (MED): B bars 1-4 (Real Book variant prints Cm7 F9 Bm7b5 %).
"""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records

LEVELS = ("Beginner", "Intermediate", "Advanced")
A_INT = ["Dm7", "Dm7", "C#dim7", "C#dim7", "Cm6", "Cm6", "G7/B", "G7/B",
         "Bbmaj7", "Bbmaj7", "Ebmaj7", "Ebmaj7", "Em7b5", "A7b9", "Dm7", "C#7"]
B_INT = ["Cm6", "Cm6", "Bdim7", "Bdim7", "Bbmaj7", "Em7b5|A7b9", "Dm7", "C#7",
         "Cm7", "F7", "Bm7", "E7b9", "Bbmaj7", "A7b9", "Dm7", "Dm7"]


class HowInsensitiveChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "How Insensitive"))

    def test_intermediate_cells(self) -> None:
        s = self.rec["chart_versions"]["Intermediate"]
        self.assertEqual(s["A Section"], A_INT)
        self.assertEqual(s["B Section"], B_INT)

    def test_advanced_and_beginner(self) -> None:
        adv = self.rec["chart_versions"]["Advanced"]
        self.assertEqual(adv["A Section"][0], "Dm9")
        self.assertEqual(adv["A Section"][10], "Ebmaj7#11")
        self.assertEqual(adv["B Section"][2:4], ["Bdim7", "Bdim7"])
        beg = self.rec["chart_versions"]["Beginner"]
        self.assertEqual(beg["A Section"][:8], ["Dm", "Dm", "C#dim", "C#dim", "Cm", "Cm", "G7", "G7"])
        self.assertEqual(beg["B Section"][5], "Em|A7")

    def test_old_chart_is_gone(self) -> None:
        for lv in LEVELS:
            _v, sections = resolve_level_chart(self.rec, lv)
            flat = [c for b in sections.values() for c in b]
            for bad in ("Dm9/C", "Gm7", "C7", "Fmaj7"):
                self.assertNotIn(bad, flat, (lv, bad))

    def test_32_bars_16_plus_16_at_every_level(self) -> None:
        for lv in LEVELS:
            _v, sections = resolve_level_chart(self.rec, lv)
            self.assertEqual({k: len(v) for k, v in sections.items()}, {"A Section": 16, "B Section": 16}, lv)

    def test_beats_and_events(self) -> None:
        for lv in LEVELS:
            _v, sections = resolve_level_chart(self.rec, lv)
            for bars in sections.values():
                for bar in bars:
                    self.assertAlmostEqual(sum(p.weight for p in parse_subdivisions(bar)), 4.0)
            events = sections_dict_to_events(sections, time_signature="4/4", section_order=list(sections))
            self.assertEqual(len(events), 33, lv)  # 32 bars, one split bar
            self.assertEqual(validate_chord_events(events, time_signature="4/4"), [], lv)


if __name__ == "__main__":
    unittest.main()

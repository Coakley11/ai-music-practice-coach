"""The Girl from Ipanema: AABA = 40 bars (A 8 + A 8 + B 16 + A 8), complete at all levels.

Edition: Real Book style lead sheet in F (the Getz/Gilberto record is in Db).
Sources: pianowithjonny.com 'play girl from ipanema on piano' (AABA 40 bars,
bridge 16 = 12 ambiguous measures + 4 of iii-VI-ii-V; 1st ending Fmaj7 | Gb7
one bar each; 2nd ending two bars Fmaj7; final A Fmaj9 two measures) and the
ladydpiano.blogspot.com 2017/02 chart (bridge Gbmaj7, B, F#m7, D, Gm7, Eb,
Am7 D7b9, Gm7 C7b9). No push/split bars are encoded (one chord per bar).
The old 4-bar Intro (Gm7 C7) is not in the published lead sheet and was removed.
Tempo: default_bpm 130 from two recording measurements (Mixmeister 131.9 /
Traktor 131.4 for the 1964 track, DJ-database pages at cs.ubc.ca/~davet and
cs.uwaterloo.ca/~dtompkin, plus karaoke-version.com 'about 130'); the 4/4 pulse
is the quarter note. One-pass: before 24 bars at the fallback 100 BPM = 57.6 s,
after 40 bars at 130 BPM = 73.8 s at every level.
"""
from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

ORDER = ["A Section", "A Section (2nd ending)", "B Section", "Final A / Outro"]
INTER_BRIDGE = [
    "Gbmaj7", "Gbmaj7", "B7", "B7", "F#m7", "F#m7", "D7", "D7",
    "Gm7", "Gm7", "Eb7", "Eb7", "Am7", "D7b9", "Gm7", "C7b9",
]
A_CORE = ["Fmaj7", "Fmaj7", "G7", "G7", "Gm7", "Gb7"]


class IpanemaChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(
            [r for r in curated_song_records() if r["title"] == "The Girl from Ipanema"][0]
        )

    def test_intermediate_cells(self) -> None:
        _, s = resolve_level_chart(self.rec, "Intermediate")
        self.assertEqual(list(s), ORDER)
        self.assertEqual(s["A Section"], A_CORE + ["Fmaj7", "Gb7"])
        self.assertEqual(s["A Section (2nd ending)"], A_CORE + ["Fmaj7", "Fmaj7"])
        self.assertEqual(s["B Section"], INTER_BRIDGE)
        self.assertEqual(s["Final A / Outro"], A_CORE + ["Fmaj7", "Fmaj7"])

    def test_all_levels_keep_40_bars_aaba(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            view, s = resolve_level_chart(self.rec, level)
            self.assertEqual(list(view["section_order"]), ORDER, level)
            self.assertEqual([len(s[k]) for k in ORDER], [8, 8, 16, 8], level)
        _, beg = resolve_level_chart(self.rec, "Beginner")
        self.assertEqual(beg["A Section"], ["F", "F", "G7", "G7", "Gm", "Gb7", "F", "Gb7"])
        self.assertEqual(beg["B Section"][-4:], ["Am", "D7", "Gm", "C7"])
        _, adv = resolve_level_chart(self.rec, "Advanced")
        self.assertEqual(adv["B Section"][-4:], ["Am9", "D7b9", "Gm9", "C7b9"])
        self.assertEqual(adv["Final A / Outro"][-2:], ["Fmaj9", "Fmaj9"])

    def test_tempo_and_duration(self) -> None:
        ext = self.rec["extensions"]
        self.assertEqual(ext["default_bpm"], 130)
        bars = 0
        for level in ("Beginner", "Intermediate", "Advanced"):
            _, s = resolve_level_chart(self.rec, level)
            beats = sum(
                sub.weight for k in ORDER for cell in s[k] for sub in parse_subdivisions(cell)
            )
            self.assertAlmostEqual(beats, 160.0)
            self.assertAlmostEqual(40 * meter_timing(130, "4/4").bar_sec, 73.846, places=2)
            bars = beats / 4
        self.assertEqual(bars, 40)

    def test_events_validate(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            view, s = resolve_level_chart(self.rec, level)
            ev = sections_dict_to_events(s, time_signature="4/4", section_order=ORDER)
            self.assertEqual(validate_chord_events(ev, time_signature="4/4"), [])

    def test_no_invented_intro(self) -> None:
        self.assertNotIn("Intro", " ".join(self.rec["sections"]))
        self.assertEqual(list(self.rec["lyric_cues"]), ORDER)


if __name__ == "__main__":
    unittest.main()

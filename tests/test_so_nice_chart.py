"""So Nice / Summer Samba (Valle): published 32-bar form.

The catalog had a 16-bar invented Verse (F x4, Bm E7 x2, Bb x4, Bbm x4), an
11-bar Chorus with each split chord expanded to a bar (Em7b5 A7#5 Dm9 G13 Gm7
C#9 C9) and a 7-bar alternate chorus.  Sources: Guitar Composer Toolbox "So
Nice (Summer Samba) in F" (32 bars: Fmaj7 % Bm7 E7b13 Bbmaj7 % Eb7 % Am7 D7b9
Gm7 Em7b5|A7b13 Dm7 G7 Gm7 C#7|C7, repeat to bar 11 then C7b9 Fmaj7 Bb7 F6
Gm7|C7) and its Real Book variant "Summer Samba" (same A, Bm7b5 for bar 3, ending
C7b9 FMaj7 Bb7 F).  The old 7-bar alternate chorus was exactly bars 9-15 of the
real ending.  Beats: `Em7b5|A7`, `C#7|C7`, `Gm7|C7` = 2+2 (second chord on
beat 3).  Held (MED): the 8-bar Intro (no source), bar 3-4 qualities (Bm7 vs
Bm7b5, E7 vs E7#9/E7b13).
"""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import keeps_full_form, resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records

LEVELS = ("Beginner", "Intermediate", "Advanced")
ORDER = ["Intro", "Chorus", "Chorus (alternate)"]
CH_INT = ["Fmaj7", "Fmaj7", "Bm7b5", "E7", "Bbmaj7", "Bbmaj7", "Eb7", "Eb7",
          "Am7", "D7b9", "Gm7", "Em7b5|A7", "Dm7", "G7", "Gm7", "C#7|C7"]
ALT_INT = ["Fmaj7", "Fmaj7", "Bm7b5", "E7", "Bbmaj7", "Bbmaj7", "Eb7", "Eb7",
           "Am7", "D7b9", "Gm7", "C7b9", "Fmaj7", "Bb7", "F6", "Gm7|C7"]


class SoNiceChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "So Nice (Summer Samba)"))

    def test_intermediate_cells(self) -> None:
        s = self.rec["chart_versions"]["Intermediate"]
        self.assertEqual(list(s), ORDER)
        self.assertEqual(s["Chorus"], CH_INT)
        self.assertEqual(s["Chorus (alternate)"], ALT_INT)

    def test_advanced_and_beginner(self) -> None:
        adv = self.rec["chart_versions"]["Advanced"]
        self.assertEqual(adv["Chorus"][3], "E7b13")
        self.assertEqual(adv["Chorus"][11], "Em7b5|A7b13")
        beg = self.rec["chart_versions"]["Beginner"]
        self.assertEqual(beg["Chorus"][:4], ["F", "F", "Bdim", "E7"])
        self.assertEqual(beg["Chorus (alternate)"][-1], "Gm|C7")

    def test_old_invented_bars_gone(self) -> None:
        for lv in LEVELS:
            flat = [c for b in self.rec["chart_versions"][lv].values() for c in b]
            for bad in ("Bbm7", "Bbm6", "Bbm", "A7#5", "G13", "C9", "C#9", "Bb6"):
                self.assertNotIn(bad, flat, (lv, bad))

    def test_bars_all_levels(self) -> None:
        for lv in LEVELS:
            _v, sections = resolve_level_chart(self.rec, lv)
            self.assertEqual({k: len(v) for k, v in sections.items()},
                             {"Intro": 8, "Chorus": 16, "Chorus (alternate)": 16}, lv)
        self.assertTrue(keeps_full_form(self.rec, "Beginner"))
        self.assertTrue(keeps_full_form(self.rec, "Intermediate"))

    def test_duration_at_135_bpm(self) -> None:
        self.assertEqual(self.rec["extensions"]["default_bpm"], 135)
        for lv in LEVELS:
            _v, sections = resolve_level_chart(self.rec, lv)
            beats = sum(sum(p.weight for p in parse_subdivisions(c)) for b in sections.values() for c in b)
            self.assertAlmostEqual(beats * 60 / 135, 40 * 4 * 60 / 135, msg=lv)

    def test_events_validate(self) -> None:
        for lv in LEVELS:
            _v, sections = resolve_level_chart(self.rec, lv)
            events = sections_dict_to_events(sections, time_signature="4/4", section_order=ORDER)
            self.assertEqual(validate_chord_events(events, time_signature="4/4"), [], lv)


if __name__ == "__main__":
    unittest.main()

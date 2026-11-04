"""Hey Jude: full one-pass form and real tempo (Wave 3, stream A1, W3-11).

HEY JUDE (74 BPM, 4/4; recording 7:11 = 431 s, Walter Everett via Wikipedia, infobox 7:12)
  Form (Alan W. Pollack, "Notes on Hey Jude", recmusicbeatles.com/public/files/awp/hj-1.html;
  Wikipedia "Hey Jude": four verses, two bridges, ~3 min then a ~4 min coda of 19 rounds):
  Verse 1 (8) | Verse 2 (9) | Bridge (11.5) | Verse 3 (9) | Bridge (11.5) | Verse 4 (8) |
  Coda 19 x 4 bars F Eb Bb F.  Count and cycle length are from the analyses, NOT fitted to the
  length: Pollack's form line "19X", "no less than nineteen repetitions of a four measure
  phrase" (walkthrough says "eighteen and a half"), Everett via Wikipedia "nineteen rounds of
  the double plagal cadence"; Pollack: fade begins as early as the 10th repetition.
  Tempo 74: Hooktheory (74/75), SongBPM/Tunebat Love-version listings; the 2009/2015
  remaster analyzers report ~147 = double time.  Length is only a consistency check: 133.5 bars *
  3.243 s = 433 s vs 431 s.  Old chart: 28 bars at the fallback 100 BPM = 67 s (ratio 0.16), no coda.
  Push / split bars: none in the verse.  Bridge bar 10 is ``F7:2|C7:2`` - Pollack halves the F7
  bar and adds a 2-bar C7 na-na tag, but the half bar cannot be a bar here so the
  bridge is 12 bars (0.5 bar over); beat placement of the C7 change on beat 3 is derived from
  "shortens the measure with the F7 chord by half".  Verse inversions C/E and F/A (Interm/Adv)
  are the prior chart's, not contradicted but UNVERIFIED.
"""
from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

LEVELS = ("Beginner", "Intermediate", "Advanced")


def _rec(title: str) -> dict:
    return copy.deepcopy(next(r for r in curated_song_records() if r["title"] == title))


def _bars(secs) -> int:
    return sum(len(v) for v in secs.values())


class HeyJudeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = _rec("Hey Jude")

    def test_tempo_meter_order(self) -> None:
        ext = self.rec["extensions"]
        self.assertEqual(ext["default_bpm"], 74)
        self.assertEqual(ext["time_signature"], "4/4")
        self.assertEqual(
            self.rec["section_order"],
            ["Verse 1", "Verse 2", "Bridge 1", "Verse 3", "Bridge 2", "Verse 4",
             "Coda 1", "Coda 2", "Coda 3", "Coda 4"],
        )
        self.assertNotIn("Intro", self.rec["sections"])

    def test_bar_counts_all_levels(self) -> None:
        want = {"Verse 1": 8, "Verse 2": 9, "Bridge 1": 12, "Verse 3": 9, "Bridge 2": 12,
                "Verse 4": 8, "Coda 1": 20, "Coda 2": 20, "Coda 3": 20, "Coda 4": 16}
        for level in LEVELS:
            _v, secs = resolve_level_chart(self.rec, level)
            self.assertEqual({k: len(v) for k, v in secs.items()}, want, level)
            self.assertEqual(_bars(secs), 134, level)
            self.assertEqual(list(secs), list(want), level)

    def test_hand_written_cells(self) -> None:
        _v, adv = resolve_level_chart(self.rec, "Advanced")
        self.assertEqual(adv["Verse 1"], ["F", "C/E", "C7", "F", "Bb", "F/A", "C7", "F"])
        self.assertEqual(adv["Verse 2"][-1], "F7")
        self.assertEqual(adv["Verse 3"][-1], "F7")
        self.assertEqual(len(adv["Verse 4"]), 8)
        self.assertEqual(
            adv["Bridge 1"],
            ["Bb", "Gm", "C", "F", "F7", "Bb", "Gm", "C", "F", "F7:2|C7:2", "C7", "C7"],
        )
        self.assertEqual(adv["Coda 1"][:8], ["F", "Eb", "Bb", "F"] * 2)
        self.assertEqual(adv["Coda 4"], ["F", "Eb", "Bb", "F"] * 4)
        _v, beg = resolve_level_chart(self.rec, "Beginner")
        self.assertEqual(beg["Bridge 1"][:5], ["Bb", "Gm", "C", "F", "F"])
        self.assertEqual(beg["Bridge 2"][9], "F:2|C:2")

    def test_split_bar_weights(self) -> None:
        subs = parse_subdivisions("F7:2|C7:2", beats_per_bar=4.0)
        self.assertEqual([(s.chord, s.weight) for s in subs], [("F7", 2.0), ("C7", 2.0)])

    def test_one_pass_ratio_vs_recording(self) -> None:
        bar = meter_timing(74, "4/4").bar_sec
        self.assertAlmostEqual(bar, 240 / 74, places=6)
        for level in LEVELS:
            _v, secs = resolve_level_chart(self.rec, level)
            ratio = _bars(secs) * bar / 431.0  # Everett 7:11 (album/single)
            self.assertTrue(0.85 <= ratio <= 1.2, (level, ratio))


if __name__ == "__main__":
    unittest.main()

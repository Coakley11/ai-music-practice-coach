"""In My Life (Beatles, A, ~102 BPM, 4/4) - W3-18 full form + bridge correction.

Base: Intro 4 / Verse 8 / Chorus 8 / [Piano Solo 8 Advanced only] / Outro 4 = 24/24/32 bars at the
fallback 100 BPM (57.6-76.8 s vs 2:27 = 147 s album track; ratio 0.39-0.52).

Evidence
* Alan W. Pollack, "Notes on In My Life" (icce.rug.nl/~soundscapes/DATABASES/AWP/iml.shtml, read via
  the recmusicbeatles.com mirror): Intro -> Verse -> Bridge -> half-intro -> Verse -> Bridge ->
  Verse (instrumental, George Martin's piano) -> Bridge -> Outro; intro 4 bars (2-bar motif x2),
  verse 8, bridge 8; bridge = F#m D G A | F#m B Dm A.
* Walker & Don, "A Geometric Analysis of the Harmonic Structure of In My Life" (arxiv 2008.11749)
  lead sheet: bridge f# - D - G - A - f# - B7 - d - A (one chord per measure) - agrees with
  Pollack, which corrects base bars 7-8 (E, E7 -> Dm, A).
* Aaron Krerowicz Formal Structure (timestamps): Intro 0:00-0:09, V1 0:09-0:28, Middle 8
  0:28-0:46, Trans 0:46-0:51 ("intro halved"), V2 0:51-1:10, M8 1:10-1:28, Solo 1:28-1:47
  ("replaces a verse"), M8 1:47-2:05, Trans 2:05-2:10, Coda (m8, trans.) 2:10-2:25.  8 bars =
  18-19 s => 2.35-2.4 s/bar (~101-102 BPM); intro 9 s = 4 bars; trans 5 s = 2 bars; coda 15 s =
  4 bars of m8 + 2 trans = 6.
* Tempo ~102: Chordintel 103, Bonedo 102, Krerowicz-derived 101.  62 bars x 2.353 s = 145.9 s.
  Recording 147 s: album track 2:27 (ratio 0.99; Krerowicz ends the coda at 2:25).
Encoded: 62 bars; solo = verse harmony (HIGH per Krerowicz "replaces a verse"); coda = last four
bridge bars + closing A A (the final 'modified spacer' voicing is MED).
HELD: Pollack's verse chart places TWO chords in some bars (A|E, F#m|A7, D|Dm per bar, 4-bar
phrase x2); the base one-chord-per-bar reading is kept (same 8 bars; split placement is MED, only
an ASCII chart).  No pushes.
"""

from __future__ import annotations

import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from songs.meter import meter_timing
from song_catalog.catalog import curated_song_records

ORDER = ["Intro", "Verse 1", "Bridge 1", "Transition 1", "Verse 2", "Bridge 2",
         "Piano Solo", "Bridge 3", "Transition 2", "Coda"]
LEN = [4, 8, 8, 2, 8, 8, 8, 8, 2, 6]


def _rec():
    return [r for r in curated_song_records() if r["title"] == "In My Life"][0]


def _beats(secs):
    return sum(s.weight for bars in secs.values() for t in bars for s in parse_subdivisions(t))


class InMyLifeChart(unittest.TestCase):
    def test_form_every_level(self):
        rec = _rec()
        self.assertEqual(list(rec["section_order"]), ORDER)
        for lv in ("Beginner", "Intermediate", "Advanced"):
            _, secs = resolve_level_chart(rec, lv)
            self.assertEqual(list(secs), ORDER, lv)
            self.assertEqual([len(secs[n]) for n in ORDER], LEN, lv)
            self.assertEqual(_beats(secs) / 4, 62, lv)

    def test_bridge_fixed_bars_7_8(self):
        _, adv = resolve_level_chart(_rec(), "Advanced")
        for n in ("Bridge 1", "Bridge 2", "Bridge 3"):
            self.assertEqual(adv[n], ["F#m7", "D", "G", "A", "F#m7", "B7", "Dm", "A"])
        _, beg = resolve_level_chart(_rec(), "Beginner")
        self.assertEqual(beg["Bridge 1"], ["F#m", "D", "G", "A", "F#m", "B7", "Dm", "A"])

    def test_solo_is_verse_and_coda(self):
        _, adv = resolve_level_chart(_rec(), "Advanced")
        self.assertEqual(adv["Piano Solo"], adv["Verse 1"])
        self.assertEqual(adv["Transition 1"], ["A", "E/G#"])
        self.assertEqual(adv["Coda"], ["F#m7", "B7", "Dm", "A", "A", "A"])
        self.assertEqual(adv["Intro"], ["A", "E/G#", "A", "E/G#"])

    def test_tempo_and_ratio(self):
        rec = _rec()
        self.assertEqual(rec["extensions"]["default_bpm"], 102)
        sec = 62 * meter_timing(102, "4/4").bar_sec
        self.assertAlmostEqual(sec, 145.9, places=1)
        self.assertTrue(0.85 <= sec / 147.0 <= 1.2)  # 2:27 album track

    def test_events_valid_no_pushes(self):
        for lv in ("Beginner", "Intermediate", "Advanced"):
            _, secs = resolve_level_chart(_rec(), lv)
            validate_chord_events(sections_dict_to_events(secs))
            self.assertFalse(any(s.push for b in secs.values() for t in b for s in parse_subdivisions(t)))


if __name__ == "__main__":
    unittest.main()

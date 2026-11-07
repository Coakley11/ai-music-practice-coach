"""While My Guitar Gently Weeps (Beatles, Am, ~114 BPM, 4/4) - W3-16 full-form correction.

Base chart: Verse 8 / Chorus 8 / Bridge 4 = 16-20 bars at the fallback 100 BPM (48 s vs a
4:45 = 285 s White Album track, ratio 0.17).

Evidence
* Alan W. Pollack, "Notes on While My Guitar Gently Weeps" (icce.rug.nl/~soundscapes/DATABASES/AWP/
  wmggw.shtml; read via the recmusicbeatles.com mirror): form Intro -> Verse -> Bridge -> Verse ->
  Verse (solo) -> Bridge -> Verse -> Outro; intro 8 bars ending on V; every verse a "square"
  16 bars (two 8-bar couplets: i-i-i-VI | i-VII-IV-V, then ... i-V/III-III-V); bridge 16 bars =
  an 8-bar phrase in A major repeated; outro "close to" 32 bars (about two verse cycles), fade.
* Aaron Krerowicz, Formal Structure #136: each middle 8 is 16 measures ~34 s (= 2.125 s/bar =
  113 BPM) and the two together are 23.7 % of the song (=> ~287 s): bar count and tempo agree
  with Pollack independently.
* Tempo ~114 (Musicnotes ~114, Chordintel 114, GetSongBPM 116, Krerowicz-derived 113);
  4/4 pulse = quarter note, so no half/double ambiguity (136 bars x 2.105 s = 286 s = the
  recording length, which independently excludes 57 or 228 BPM).
Chord placement: one chord per bar, no pushes/splits encoded (none sourced). The second verse
couplet's final three bars (G | C | E) come from Pollack's roman numerals (V/III, III, V).
HELD (MED): bridge bars 6-7 - Pollack's ASCII shows Bm held then E held, base chart has
Bm | E | A | E; base chords kept, repeated twice. Intro chords are the verse's first couplet
(Pollack gives length and the V ending, not a chord list) - MED. Outro bars 7 and 15 of the
last repeat are flagged by Pollack as unclear.
Recording length 285 s: album track (VERIFIED in WAVE3_PLAN).
"""

from __future__ import annotations

import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from songs.meter import meter_timing
from song_catalog.catalog import curated_song_records

V1 = ["Am", "Am/G", "D/F#", "F", "Am", "G", "D", "E"]
V2 = ["Am", "Am/G", "D/F#", "F", "Am", "G", "C", "E"]
BR = ["A", "C#m", "F#m", "C#m", "Bm", "E", "A", "E"]
ORDER = ["Intro", "Verse 1", "Bridge 1", "Verse 2", "Guitar Solo (Verse Form)",
         "Bridge 2", "Verse 3", "Outro (Fade)"]
LEN = [8, 16, 16, 16, 16, 16, 16, 32]


def _rec():
    return [r for r in curated_song_records() if r["title"] == "While My Guitar Gently Weeps"][0]


def _beats(secs):
    return sum(s.weight for bars in secs.values() for t in bars for s in parse_subdivisions(t))


class WmggwChart(unittest.TestCase):
    def test_form_and_bar_counts_every_level(self):
        rec = _rec()
        self.assertEqual(list(rec["section_order"]), ORDER)
        for lv in ("Beginner", "Intermediate", "Advanced"):
            _, secs = resolve_level_chart(rec, lv)
            self.assertEqual(list(secs), ORDER, lv)
            self.assertEqual([len(secs[n]) for n in ORDER], LEN, lv)
            self.assertEqual(_beats(secs) / 4, 136, lv)

    def test_hand_written_cells_advanced(self):
        _, secs = resolve_level_chart(_rec(), "Advanced")
        self.assertEqual(secs["Intro"], V1)
        self.assertEqual(secs["Verse 1"], V1 + V2)
        self.assertEqual(secs["Guitar Solo (Verse Form)"], V1 + V2)
        self.assertEqual(secs["Bridge 1"], BR + BR)
        self.assertEqual(secs["Bridge 2"], BR + BR)
        self.assertEqual(secs["Outro (Fade)"], (V1 + V2) * 2)
        self.assertEqual(secs["Verse 1"][13:16], ["G", "C", "E"])

    def test_beginner_drops_slashes_only(self):
        _, secs = resolve_level_chart(_rec(), "Beginner")
        self.assertEqual(secs["Verse 1"][:4], ["Am", "Am", "D", "F"])
        self.assertEqual(secs["Bridge 1"][:8], BR)

    def test_tempo_and_one_pass_duration(self):
        rec = _rec()
        self.assertEqual(rec["extensions"]["default_bpm"], 114)
        bar = meter_timing(114, "4/4").bar_sec
        self.assertAlmostEqual(136 * bar, 286.3, places=1)
        ratio = 136 * bar / 285.0  # 4:45 White Album track
        self.assertTrue(0.85 <= ratio <= 1.2, ratio)

    def test_no_pushes_and_events_valid(self):
        rec = _rec()
        for lv in ("Beginner", "Intermediate", "Advanced"):
            _, secs = resolve_level_chart(rec, lv)
            self.assertFalse(any(s.push for b in secs.values() for t in b for s in parse_subdivisions(t)))
            validate_chord_events(sections_dict_to_events(secs))


if __name__ == "__main__":
    unittest.main()

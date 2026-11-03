"""Come Together (Beatles, Dm, 82 BPM, 4/4) - W2-06 form correction.

Evidence (recording 4:19 = 259 s = ~88.5 bars at 82 BPM; old chart 59 bars = 173 s, ratio 0.67):
* spytunes.com/come-together-chords: verse = 8 bars (Dm7 x4, A5 x2, G5, N.C.); refrain
  "B5 A5 | G5 A5"; order V1, inst, V2, Ch1, inst, V3, Ch2, inst, solo, V4, Ch3, inst, outro.
* bellandcomusic.com/come-together.html: 83 BPM, verse ~8 bars, refrain Bm | G-A7 (2 bars),
  4-bar Dm7 breaks.
* aaronkrerowicz.com Formal Structure #179 (timestamps): verse 24 s (= 8 bars @82), refrain 6 s
  (= 2 bars), tags 11 s (4 bars) after V1 and after the refrains, 6 s (2 bars) after Ch2 and
  before/after the solo.  Chorus follows verses 2, 3, 4 only (not verse 1).
Harmonic rhythm: whole-bar changes on the downbeat except the refrain, where each bar holds two
chords (half-bar split: Bm|Bm/A, G|A) - MED (chord names from two chart sites, split point from
the pair of sites; no score).  No push is encoded.
Held: Outro (real coda 3:12-4:20, ~17-23 bars) stays a 4-bar fade vamp; N.C. after the refrain
unverified (Spytunes lists it; it would fall inside the tag time).
"""

from __future__ import annotations

import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records

V = ["Dm", "Dm", "Dm", "Dm", "A", "A", "G", "N.C."]
CH = ["Bm|Bm/A", "G|A"]
R4 = ["Dm7"] * 4
R2 = ["Dm7"] * 2
ADV = {
    "Intro": R4, "Verse 1": V, "Instrumental 1": R4, "Verse 2": V, "Chorus 1": CH,
    "Instrumental 2": R4, "Verse 3": V, "Chorus 2": CH, "Instrumental 3": R2,
    "Solo": ["Dm"] * 4 + ["A"] * 4, "Instrumental 4": R2, "Verse 4": V,
    "Final Chorus": CH, "Instrumental 5": R4, "Outro (Fade)": ["Dm"] * 4,
}


def _rec():
    return [r for r in curated_song_records() if r["title"] == "Come Together"][0]


def _beats(sections):
    return sum(s.weight for bars in sections.values() for t in bars for s in parse_subdivisions(t))


class ComeTogetherChart(unittest.TestCase):
    def test_advanced_exact(self):
        rec = _rec()
        self.assertEqual(rec["chart_versions"]["Advanced"], ADV)
        self.assertEqual(list(rec["section_order"]), list(ADV))
        self.assertEqual(rec["key"], "Dm")

    def test_bars_and_duration(self):
        rec = _rec()
        for level, bars in (("Beginner", 28), ("Intermediate", 46), ("Advanced", 70)):
            _, secs = resolve_level_chart(rec, level)
            self.assertEqual(_beats(secs) / 4, bars, level)
        _, adv = resolve_level_chart(rec, "Advanced")
        self.assertAlmostEqual(_beats(adv) * 60 / 82, 70 * 4 * 60 / 82, places=6)  # 204.9 s

    def test_verse_is_8_bars_with_nc_last_at_every_level(self):
        rec = _rec()
        for level in ("Beginner", "Intermediate", "Advanced"):
            _, secs = resolve_level_chart(rec, level)
            for name, bars in secs.items():
                if name.startswith("Verse"):
                    self.assertEqual(len(bars), 8, (level, name))
                    self.assertEqual(bars[-1], "N.C.")

    def test_refrain_is_two_split_bars_weights(self):
        _, secs = resolve_level_chart(_rec(), "Advanced")
        for name in ("Chorus 1", "Chorus 2", "Final Chorus"):
            self.assertEqual(secs[name], CH)
            self.assertEqual([s.weight for s in parse_subdivisions(secs[name][0])], [2.0, 2.0])
            self.assertEqual([s.weight for s in parse_subdivisions(secs[name][1])], [2.0, 2.0])
            self.assertFalse(any(s.push for t in secs[name] for s in parse_subdivisions(t)))

    def test_beginner_refrain_simplified(self):
        _, secs = resolve_level_chart(_rec(), "Beginner")
        self.assertEqual(secs["Chorus 1"], ["Bm", "G|A"])

    def test_events_validate(self):
        rec = _rec()
        for level in ("Beginner", "Intermediate", "Advanced"):
            view, secs = resolve_level_chart(rec, level)
            ev = sections_dict_to_events(secs, time_signature="4/4", section_order=list(secs))
            self.assertEqual(validate_chord_events(ev, time_signature="4/4"), [], level)


if __name__ == "__main__":
    unittest.main()

"""Heal The World (MJ, A, 80 BPM, 4/4) - W2-24 encoding of the beat-4 passing chord.

The chorus bar 7 was written ``A|A|A|E/G#``: a 4-way equal split (parse_subdivisions gives four
1-beat items; chord_events.validate_chord_events accepts it).  The intent (tests/test_heal_the_world_bars.py:
E/G# is a passing chord inside the A bar, i.e. A for beats 1-3, E/G# on beat 4) is exactly
``A:3|E/G#:1``; the 4-way form re-attacks the A on beats 2 and 3 in the backing (measured onset
ratio at beat 2: 3.9 vs 0.85 sustained).  Chord timing is unchanged (3 + 1 beats); no push is encoded.
Chorus bars: 15 (A2 Bm7 2 D/E 2 | A:3 E/G#:1 | F#m7 C#m7 D C#m7 Bm7 2 D/E 2) = 60 beats.
Source note: only Cifra Club shows E/G# F#m7 in the chorus; no score gives the beat of E/G# (UNVERIFIED, left as is).
"""

from __future__ import annotations

import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records

CHORUS = ["A", "A", "Bm7", "Bm7", "D/E", "D/E", "A:3|E/G#:1", "F#m7",
          "C#m7", "D", "C#m7", "Bm7", "Bm7", "D/E", "D/E"]


class HealChart(unittest.TestCase):
    def test_chorus_cells_every_level(self):
        rec = [r for r in curated_song_records() if r["title"] == "Heal The World"][0]
        self.assertEqual(rec["key"], "A")
        for level, names in (("Beginner", ["Chorus 1", "Chorus 2"]),
                             ("Intermediate", ["Chorus 1", "Chorus 2", "Final Chorus"]),
                             ("Advanced", ["Chorus 1", "Chorus 2", "Chorus 3", "Final Chorus"])):
            _, secs = resolve_level_chart(rec, level)
            for n in names:
                self.assertEqual(secs[n], CHORUS, (level, n))
            ev = sections_dict_to_events(secs, time_signature="4/4", section_order=list(secs))
            self.assertEqual(validate_chord_events(ev, time_signature="4/4"), [])

    def test_beat_weights_and_bar_math(self):
        subs = parse_subdivisions("A:3|E/G#:1")
        self.assertEqual([(s.chord, s.weight, s.push) for s in subs], [("A", 3.0, False), ("E/G#", 1.0, False)])
        self.assertEqual(sum(s.weight for t in CHORUS for s in parse_subdivisions(t)), 60.0)
        rec = [r for r in curated_song_records() if r["title"] == "Heal The World"][0]
        for level, bars in (("Beginner", 66), ("Intermediate", 122), ("Advanced", 145)):
            _, secs = resolve_level_chart(rec, level)
            self.assertEqual(sum(s.weight for b in secs.values() for t in b for s in parse_subdivisions(t)) / 4, bars)


if __name__ == "__main__":
    unittest.main()

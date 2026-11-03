"""12-Bar Blues in F keeps all 12 bars at every level (Beginner used to drop bars 9-12).

Standard 12-bar form: F7 Bb7 F7 F7 | Bb7 Bb7 F7 F7 | C7 Bb7 F7 C7 (quick-change
IV in bar 2, V-IV-I-V turnaround in bars 9-12). Textbook form (any blues
method); no pushes. One pass at the 100 BPM fallback = 12 bars x 2.4 s = 28.8 s
at every level (Beginner was 8 bars = 19.2 s).
"""
from __future__ import annotations

import unittest

from chart_level_arrangement import resolve_level_chart
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records

FORM = {
    "Bars 1-4": ["F7", "Bb7", "F7", "F7"],
    "Bars 5-8": ["Bb7", "Bb7", "F7", "F7"],
    "Bars 9-12": ["C7", "Bb7", "F7", "C7"],
}


class TwelveBarBluesTests(unittest.TestCase):
    def test_every_level_has_all_twelve_bars(self) -> None:
        rec = [r for r in curated_song_records() if r["title"] == "12-Bar Blues in F"][0]
        for level in ("Beginner", "Intermediate", "Advanced"):
            _, s = resolve_level_chart(rec, level)
            self.assertEqual(s, FORM, level)
            beats = sum(x.weight for v in s.values() for c in v for x in parse_subdivisions(c))
            self.assertAlmostEqual(beats * 60.0 / 100, 28.8, places=6)


if __name__ == "__main__":
    unittest.main()

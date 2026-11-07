"""Here Comes the Sun (Beatles, A) - W3-13: TEMPO ONLY (129); form HELD.

Base: fallback 100 BPM; chart 24/32/32 bars.  Recording 3:07 = 187 s (album track).
Tempo 129 (quarter note, 4/4 verse): bonedo.de drum lesson 129; tempo listing 129; Mixmeister
128.5 / Traktor 128.7 on the Abbey Road track.  Recording-length check: Pollack's form (intro 8,
five 9-bar refrains with a 7/8 last bar, three 8-bar verses, a 21-bar 11/8-4/4-7/8 bridge, outro)
is ~98 bars + outro; at 129 BPM a 4/4 bar is 1.86 s, so ~100 bars ~ 187 s; at 100 BPM it would be
~240 s, so 129 (not 64 or 258) is the right pulse.
Form HELD: Pollack's bar/meter structure was only readable as an ASCII diagram and the 11/8, 4/4,
7/8 bridge and 7/8 refrain-ending bars cannot be written on the fixed 4/4 grid.  Chart unchanged.
"""

from __future__ import annotations

import unittest

from songs.meter import meter_timing
from song_catalog.catalog import curated_song_records


class HctsTempo(unittest.TestCase):
    def test_tempo_129_and_chart_unchanged(self):
        rec = [r for r in curated_song_records() if r["title"] == "Here Comes the Sun"][0]
        self.assertEqual(rec["extensions"]["default_bpm"], 129)
        self.assertEqual(rec["chart_versions"]["Intermediate"]["Bridge"][-1], "E7")
        self.assertEqual(len(rec["chart_versions"]["Advanced"]["Verse"]), 8)
        self.assertAlmostEqual(32 * meter_timing(129, "4/4").bar_sec, 59.5, places=1)


if __name__ == "__main__":
    unittest.main()

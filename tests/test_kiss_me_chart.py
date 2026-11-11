"""Kiss Me (Sixpence None the Richer): default tempo is ~100 BPM, not 124.

The chart is now stored in the recording's concert key, Eb major; the old D
spelling was the capo-1 open-D shape set. See test_kiss_me_concert_key.py for
that correction and its sources. Tempo, meter and bar counts are unchanged.

Sources agreeing on ~100: Hooktheory (100 BPM, 4/4), karaoke-version.com
(original tempo 100), klang.io (100), Traktor analysis of the radio edit
(100.1); Musicnotes (via Wikipedia) prints 96 and AcousticBrainz 102, so the
published range is 96-102 and nothing supports 124. The tempo change itself was
metadata-only.

The bar grid was corrected later, in W21: the cells had been written at half-bar
granularity (two cells per played bar), so one pass ran 176 bars * 2.4 s = 422 s
against a 3:30 (210 s) recording. It is now one chord per bar in the intro and
verse and two chords per bar in the chorus and instrumental - 88 bars = 211.2 s.
See test_kiss_me_form_grid.py for that correction and its source.
"""
from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

BARS = {"Beginner": 59, "Intermediate": 63, "Advanced": 88}


class KissMeTempoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "Kiss Me"))

    def test_default_bpm_100_and_meter(self) -> None:
        ext = self.rec["extensions"]
        self.assertEqual(ext["default_bpm"], 100)
        self.assertEqual(ext["time_signature"], "4/4")
        self.assertEqual(self.rec["key"], "Eb")

    def test_notes_do_not_claim_124(self) -> None:
        notes = self.rec["extensions"]["arrangement_notes"]
        self.assertNotIn("124", notes)
        self.assertIn("100 BPM", notes)

    def test_bar_counts_and_duration(self) -> None:
        """Renamed from test_cells_unchanged_and_duration: the cells did change
        in W21, when the half-bar grid was corrected."""
        for level, n in BARS.items():
            _v, secs = resolve_level_chart(self.rec, level)
            self.assertEqual(sum(len(v) for v in secs.values()), n, level)
        self.assertAlmostEqual(88 * meter_timing(100, "4/4").bar_sec, 211.2, places=6)
        _v, adv = resolve_level_chart(self.rec, "Advanced")
        self.assertEqual(adv["Intro"][:4], ["Ebadd9", "Ebmaj9", "Eb9", "Ebmaj9"])
        self.assertEqual(adv["Chorus 1"][:2], ["Fm9|Bbsus2", "Ebadd9|Cm9"])


if __name__ == "__main__":
    unittest.main()

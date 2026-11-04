"""Kiss Me (Sixpence None the Richer): default tempo is ~100 BPM, not 124.

Sources agreeing on ~100: Hooktheory (100 BPM, 4/4), karaoke-version.com
(original tempo 100), klang.io (100), Traktor analysis of the radio edit
(100.1); Musicnotes (via Wikipedia) prints 96 and AcousticBrainz 102, so the
published range is 96-102 and nothing supports 124. Metadata-only change: the
chart cells (2 bars per chord in intro/verse, 1 bar per chord in chorus) are
untouched. Chart holds: at 100 BPM one pass is 176 bars * 2.4 s = 422 s versus a
3:30 (210 s) recording, so the form length is MED-held (UNVERIFIED).
"""
from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

BARS = {"Beginner": 118, "Intermediate": 126, "Advanced": 176}


class KissMeTempoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "Kiss Me"))

    def test_default_bpm_100_and_meter(self) -> None:
        ext = self.rec["extensions"]
        self.assertEqual(ext["default_bpm"], 100)
        self.assertEqual(ext["time_signature"], "4/4")
        self.assertEqual(self.rec["key"], "D")

    def test_notes_do_not_claim_124(self) -> None:
        notes = self.rec["extensions"]["arrangement_notes"]
        self.assertNotIn("124", notes)
        self.assertIn("100 BPM", notes)

    def test_cells_unchanged_and_duration(self) -> None:
        for level, n in BARS.items():
            _v, secs = resolve_level_chart(self.rec, level)
            self.assertEqual(sum(len(v) for v in secs.values()), n, level)
        self.assertAlmostEqual(176 * meter_timing(100, "4/4").bar_sec, 422.4, places=6)
        _v, adv = resolve_level_chart(self.rec, "Advanced")
        self.assertEqual(adv["Intro"][:4], ["Dadd9", "Dadd9", "Dmaj9", "Dmaj9"])
        self.assertEqual(adv["Chorus 1"][:4], ["Em9", "Asus2", "Dadd9", "Bm9"])


if __name__ == "__main__":
    unittest.main()

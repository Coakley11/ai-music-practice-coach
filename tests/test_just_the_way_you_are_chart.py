"""Just the Way You Are (Billy Joel): default tempo 138 BPM (was 76).

Musicnotes prints 2/2 at half-note 69 (= 4/4 at 138); Mixmeister 138.9,
Traktor 139.3, Karaoke-Version 139. At 76 the 170-bar chart would take 8:57 per
pass against a 4:47 recording, and no source notates 4/4 at 76 with this bar
count, so 76 is not a half-time practice tempo for this chart. Metadata only.
Saved per-song BPM is untouched (resolve_source_bpm_for_pick prefers saved).
"""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.bpm_state import BACKING_BPM_MAX, BACKING_BPM_MIN
from songs.meter import meter_timing
from songs.practice_key_state import resolve_source_bpm_for_pick

BARS = {"Beginner": 92, "Intermediate": 100, "Advanced": 170}
RECORDING_SECONDS = 287  # 4:47


def _record() -> dict:
    return copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "Just the Way You Are"))


class JustTheWayYouAreTempoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = _record()

    def test_default_bpm_is_138_in_4_4(self) -> None:
        ext = self.rec["extensions"]
        self.assertEqual(ext["default_bpm"], 138)
        self.assertEqual(ext["time_signature"], "4/4")
        self.assertEqual(self.rec["key"], "D")
        self.assertTrue(BACKING_BPM_MIN <= 138 <= BACKING_BPM_MAX)

    def test_bar_duration_matches_2_2_at_half_note_69(self) -> None:
        self.assertAlmostEqual(meter_timing(138, "4/4").bar_sec, 2 * 60 / 69, places=6)

    def test_bars_unchanged_and_one_pass_matches_recording(self) -> None:
        for level, n in BARS.items():
            _v, sections = resolve_level_chart(self.rec, level)
            self.assertEqual(sum(len(v) for v in sections.values()), n, level)
        one = 170 * 240 / 138
        self.assertAlmostEqual(one, 295.652174, places=5)
        self.assertLess(abs(one - RECORDING_SECONDS) / RECORDING_SECONDS, 0.05)

    def test_saved_bpm_still_beats_new_default(self) -> None:
        # Existing users who saved a tempo keep it; only unsaved songs see 138.
        from songs.practice_key_state import BPM_BY_SOURCE_KEY

        pick = "pk::Pop::Just the Way You Are — Billy Joel"
        saved = {BPM_BY_SOURCE_KEY: {pick: 76}}
        self.assertEqual(resolve_source_bpm_for_pick(saved, pick, default_bpm=138), 76)
        self.assertEqual(resolve_source_bpm_for_pick({}, pick, default_bpm=138), 138)

    def test_notes_quote_new_tempo(self) -> None:
        notes = self.rec["extensions"]["arrangement_notes"]
        self.assertIn("138 BPM", notes)
        self.assertNotIn("~76 BPM", notes)


if __name__ == "__main__":
    unittest.main()

"""Hotel California is charted one bar per chord (120 bars, one pass ~ the recording).

The earlier pack held every chord four bars (480 bars, 25:36 per pass at 75 BPM
against a ~6:30 recording). The published form is fifteen eight-chord cycles;
at one bar per chord the chart plays 384 s against 390 s. Chords, voicings,
section names, levels and the key are unchanged -- only the holds are shorter.
"""

from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import keeps_full_form, resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from song_catalog.catalog import curated_song_records

SECTION_ORDER = [
    "Intro", "Verse 1A", "Verse 1B", "Chorus 1", "Verse 2A", "Verse 2B",
    "Chorus 2", "Verse 3A", "Verse 3B", "Outro Solo",
]
BARS = {
    "Intro": 16, "Verse 1A": 8, "Verse 1B": 8, "Chorus 1": 8, "Verse 2A": 8,
    "Verse 2B": 8, "Chorus 2": 8, "Verse 3A": 8, "Verse 3B": 8, "Outro Solo": 40,
}
# One verse cycle and one chorus cycle per level, written out by hand (not derived).
VERSE = {
    "Beginner": ["Bm", "F#7", "A", "E", "G", "D", "Em", "F#7"],
    "Intermediate": ["Bm", "F#7/A#", "A", "E/G#", "G", "D/F#", "Em", "F#7"],
    "Advanced": ["Bm9", "F#7/A#", "Aadd9", "E/G#", "Gmaj9", "D/F#", "Em9", "F#7b9"],
}
CHORUS = {
    "Beginner": ["G", "D", "F#7", "Bm", "G", "D", "Em", "F#7"],
    "Intermediate": ["G", "D/F#", "F#7/A#", "Bm", "G", "D/F#", "Em", "F#7"],
    "Advanced": ["Gmaj9", "D/F#", "F#7/A#", "Bm9", "Gmaj9", "D/F#", "Em9", "F#7b9"],
}
LEVELS = ("Beginner", "Intermediate", "Advanced")
BPM = 75
RECORDING_SECONDS = 390  # 6:30, Wikipedia album length


def _record() -> dict:
    return copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "Hotel California"))


def _expected(level: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for name in SECTION_ORDER:
        if name.startswith("Chorus"):
            out[name] = list(CHORUS[level])
        elif name == "Intro":
            out[name] = VERSE[level] * 2
        elif name == "Outro Solo":
            out[name] = VERSE[level] * 5
        else:
            out[name] = list(VERSE[level])
    return out


def _seconds(sections: dict[str, list[str]]) -> float:
    beats = sum(s.weight for bars in sections.values() for t in bars for s in parse_subdivisions(t))
    return beats * 60.0 / BPM


class HotelCaliforniaOneBarPerChordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = _record()

    def test_identity_and_settings_unchanged(self) -> None:
        r = self.rec
        self.assertEqual((r["title"], r["artist"], r["key"]), ("Hotel California", "Eagles", "Bm"))
        self.assertEqual(r["section_order"], SECTION_ORDER)
        self.assertEqual(r["chart_status"], "practice_level_verified")
        ext = r["extensions"]
        self.assertEqual(ext["default_bpm"], BPM)
        self.assertEqual(ext["time_signature"], "4/4")
        self.assertEqual(ext["default_groove"], "Rock groove")
        self.assertIsNone(ext.get("full_form_levels"))

    def test_every_level_has_the_exact_120_bar_chart(self) -> None:
        for level in LEVELS:
            sections = self.rec["chart_versions"][level]
            self.assertEqual(list(sections), SECTION_ORDER, level)
            self.assertEqual({k: len(v) for k, v in sections.items()}, BARS, level)
            self.assertEqual(sum(len(v) for v in sections.values()), 120, level)
            self.assertEqual(sections, _expected(level), level)

    def test_base_sections_are_the_intermediate_chart(self) -> None:
        self.assertEqual(self.rec["sections"], self.rec["chart_versions"]["Intermediate"])

    def test_levels_stay_in_sync_bar_by_bar(self) -> None:
        def root(cell: str) -> str:
            head = cell.split("/")[0]
            return head[:2] if len(head) > 1 and head[1] in "#b" else head[:1]

        adv = self.rec["chart_versions"]["Advanced"]
        for level in ("Beginner", "Intermediate"):
            sections = self.rec["chart_versions"][level]
            for name in SECTION_ORDER:
                self.assertEqual(len(sections[name]), len(adv[name]))
                self.assertEqual([root(c) for c in sections[name]], [root(c) for c in adv[name]], (level, name))

    def test_cadential_f_sharp_is_plain_or_altered_not_inverted(self) -> None:
        for level, last in (("Beginner", "F#7"), ("Intermediate", "F#7"), ("Advanced", "F#7b9")):
            sections = self.rec["chart_versions"][level]
            for name, bars in sections.items():
                for start in range(0, len(bars), 8):
                    self.assertEqual(bars[start + 7], last, (level, name, start))

    def test_no_chord_is_held_longer_than_it_is_written(self) -> None:
        # One bar per chord: the verse/chorus cycles never repeat a cell back to back.
        for level in LEVELS:
            for name, bars in self.rec["chart_versions"][level].items():
                self.assertFalse(any(a == b for a, b in zip(bars, bars[1:])), (level, name))

    def test_all_cells_parse_and_validate_as_chord_events(self) -> None:
        for level in LEVELS:
            events = sections_dict_to_events(
                self.rec["chart_versions"][level], time_signature="4/4", section_order=SECTION_ORDER
            )
            self.assertEqual(len(events), 120, level)
            self.assertEqual(validate_chord_events(events, time_signature="4/4"), [], level)

    def test_one_pass_matches_the_recording_and_default_two_loops_double_it(self) -> None:
        one = _seconds(self.rec["chart_versions"]["Advanced"])
        self.assertAlmostEqual(one, 384.0, places=6)
        self.assertLess(abs(one - RECORDING_SECONDS) / RECORDING_SECONDS, 0.10)
        self.assertAlmostEqual(2 * one, 768.0, places=6)  # BACKING_LOOPS_DEFAULT == 2
        from backing_track_state import BACKING_LOOPS_DEFAULT

        self.assertEqual(BACKING_LOOPS_DEFAULT, 2)

    def test_level_views_trim_whole_sections_only(self) -> None:
        expect = {
            "Beginner": (["Intro", "Verse 1A", "Chorus 1", "Verse 1B", "Chorus 2"], 48),
            "Intermediate": (["Intro", "Verse 1A", "Verse 1B", "Chorus 1", "Verse 2A", "Verse 2B", "Chorus 2"], 64),
            "Advanced": (SECTION_ORDER, 120),
        }
        for level, (order, bars) in expect.items():
            view, sections = resolve_level_chart(self.rec, level)
            self.assertEqual(list(view["section_order"]), order, level)
            self.assertEqual(sum(len(v) for v in sections.values()), bars, level)
            for name in order:
                self.assertEqual(sections[name], self.rec["chart_versions"][level][name], (level, name))
        self.assertTrue(keeps_full_form(self.rec, "Advanced"))
        self.assertFalse(keeps_full_form(self.rec, "Intermediate"))

    def test_notes_and_cues_no_longer_claim_four_bar_holds(self) -> None:
        notes = self.rec["extensions"]["arrangement_notes"]
        for stale in ("4 full bars", "four full bars", "160 bars", "64 bars", "(32 bars)", "4-bar"):
            self.assertNotIn(stale, notes)
        for needle in ("120 bars", "one bar", "75 BPM"):
            self.assertIn(needle, notes)
        cues = " ".join(" ".join(v) for v in self.rec["lyric_cues"].values())
        self.assertNotIn("4 full bars", cues)
        self.assertEqual(list(self.rec["lyric_cues"]), SECTION_ORDER)


if __name__ == "__main__":
    unittest.main()

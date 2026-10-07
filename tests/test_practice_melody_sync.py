"""Tests for practice_melody_sync.py -- the pure timeline-joining logic
behind Slice F2's measure highlighting. No browser/Streamlit involved;
``follow_timeline`` rows are constructed by hand to mirror exactly what
``build_chord_event_timeline`` in streamlit_music_practice_app.py produces.
"""

from __future__ import annotations

import unittest

from practice_melody_generator import generate_practice_melody
from practice_melody_sync import build_melody_measure_sync_data, resolve_melody_measure_timing

_SECTIONS = {
    "Verse 1": ["C", "Am", "F", "G"],
    "Chorus": ["F", "C", "G", "Am"],
}


def _melody(level="Intermediate"):
    return generate_practice_melody(
        song_id="sync-test", song_title="Sync Test", sections=_SECTIONS,
        key_center="C", level=level, tempo_bpm=100.0, style="Pop",
    )


def _ft_row(*, section, bar_in_section, absolute_bar, start, end):
    return {
        "section": section,
        "bar_in_section": bar_in_section,
        "absolute_bar": absolute_bar,
        "start_time": start,
        "end_time": end,
        "chord": "x",
    }


class TestBuildMeasureSyncData(unittest.TestCase):
    def test_one_entry_per_measure_across_sections(self) -> None:
        melody = _melody()
        data = build_melody_measure_sync_data(melody.sections)
        total_measures = sum(s.measures for s in melody.sections)
        self.assertEqual(len(data), total_measures)

    def test_bar_in_section_is_one_based(self) -> None:
        melody = _melody()
        data = build_melody_measure_sync_data([melody.sections[0]])
        self.assertEqual([d["bar_in_section"] for d in data], list(range(1, melody.sections[0].measures + 1)))

    def test_note_index_ranges_are_contiguous_and_non_overlapping(self) -> None:
        melody = _melody()
        data = build_melody_measure_sync_data(melody.sections)
        cursor = 0
        for entry in data:
            self.assertEqual(entry["note_start_index"], cursor)
            self.assertGreaterEqual(entry["note_end_index"], entry["note_start_index"])
            cursor = entry["note_end_index"]

    def test_note_count_matches_actual_sounding_events(self) -> None:
        melody = _melody()
        data = build_melody_measure_sync_data(melody.sections)
        total_notes_from_sync = data[-1]["note_end_index"] if data else 0
        total_notes_actual = sum(
            1 for s in melody.sections for e in s.events if not e.is_rest
        )
        self.assertEqual(total_notes_from_sync, total_notes_actual)

    def test_section_scoped_subset_only_covers_that_section(self) -> None:
        melody = _melody()
        verse = melody.section_by_id("Verse 1")
        data = build_melody_measure_sync_data([verse])
        self.assertTrue(all(d["section"] == "Verse 1" for d in data))
        self.assertEqual(len(data), verse.measures)


class TestResolveMeasureTiming(unittest.TestCase):
    def test_basic_join_produces_one_window_per_measure(self) -> None:
        melody = _melody()
        measure_data = build_melody_measure_sync_data(melody.sections)
        follow_timeline = [
            _ft_row(section="Verse 1", bar_in_section=1, absolute_bar=1, start=0.0, end=2.0),
            _ft_row(section="Verse 1", bar_in_section=2, absolute_bar=2, start=2.0, end=4.0),
            _ft_row(section="Verse 1", bar_in_section=3, absolute_bar=3, start=4.0, end=6.0),
            _ft_row(section="Verse 1", bar_in_section=4, absolute_bar=4, start=6.0, end=8.0),
            _ft_row(section="Chorus", bar_in_section=1, absolute_bar=5, start=8.0, end=10.0),
            _ft_row(section="Chorus", bar_in_section=2, absolute_bar=6, start=10.0, end=12.0),
            _ft_row(section="Chorus", bar_in_section=3, absolute_bar=7, start=12.0, end=14.0),
            _ft_row(section="Chorus", bar_in_section=4, absolute_bar=8, start=14.0, end=16.0),
        ]
        timing = resolve_melody_measure_timing(measure_data, follow_timeline)
        self.assertEqual(len(timing), 8)
        self.assertEqual(timing[0]["start"], 0.0)
        self.assertEqual(timing[0]["key"], "Verse 1:1")
        self.assertEqual(timing[-1]["key"], "Chorus:4")

    def test_results_are_sorted_by_start_time(self) -> None:
        melody = _melody()
        measure_data = build_melody_measure_sync_data(melody.sections)
        follow_timeline = [
            _ft_row(section="Verse 1", bar_in_section=2, absolute_bar=2, start=2.0, end=4.0),
            _ft_row(section="Verse 1", bar_in_section=1, absolute_bar=1, start=0.0, end=2.0),
        ]
        timing = resolve_melody_measure_timing(measure_data, follow_timeline)
        self.assertEqual([t["start"] for t in timing], sorted(t["start"] for t in timing))

    def test_rows_outside_the_displayed_melody_are_skipped(self) -> None:
        melody = _melody()
        verse_only = build_melody_measure_sync_data([melody.section_by_id("Verse 1")])
        follow_timeline = [
            _ft_row(section="Verse 1", bar_in_section=1, absolute_bar=1, start=0.0, end=2.0),
            _ft_row(section="Chorus", bar_in_section=1, absolute_bar=5, start=8.0, end=10.0),
        ]
        timing = resolve_melody_measure_timing(verse_only, follow_timeline)
        self.assertEqual(len(timing), 1)
        self.assertEqual(timing[0]["key"], "Verse 1:1")

    def test_repeated_loop_passes_produce_separate_windows_same_note_range(self) -> None:
        """Multiple loops: the same melody measure sounds more than once --
        each occurrence must get its own time window, but all pointing at
        the identical note range (the melody doesn't change between loops)."""
        melody = _melody()
        measure_data = build_melody_measure_sync_data([melody.section_by_id("Verse 1")])
        follow_timeline = [
            # Loop 1
            _ft_row(section="Verse 1", bar_in_section=1, absolute_bar=1, start=0.0, end=2.0),
            _ft_row(section="Verse 1", bar_in_section=2, absolute_bar=2, start=2.0, end=4.0),
            _ft_row(section="Verse 1", bar_in_section=3, absolute_bar=3, start=4.0, end=6.0),
            _ft_row(section="Verse 1", bar_in_section=4, absolute_bar=4, start=6.0, end=8.0),
            # Loop 2 (absolute_bar keeps counting up; bar_in_section restarts)
            _ft_row(section="Verse 1", bar_in_section=1, absolute_bar=5, start=8.0, end=10.0),
            _ft_row(section="Verse 1", bar_in_section=2, absolute_bar=6, start=10.0, end=12.0),
            _ft_row(section="Verse 1", bar_in_section=3, absolute_bar=7, start=12.0, end=14.0),
            _ft_row(section="Verse 1", bar_in_section=4, absolute_bar=8, start=14.0, end=16.0),
        ]
        timing = resolve_melody_measure_timing(measure_data, follow_timeline)
        self.assertEqual(len(timing), 8, "two loops of 4 bars must produce 8 distinct time windows")
        bar1_windows = [t for t in timing if t["key"] == "Verse 1:1"]
        self.assertEqual(len(bar1_windows), 2)
        self.assertEqual(bar1_windows[0]["note_start"], bar1_windows[1]["note_start"])
        self.assertEqual(bar1_windows[0]["note_end"], bar1_windows[1]["note_end"])
        self.assertNotEqual(bar1_windows[0]["start"], bar1_windows[1]["start"])

    def test_subchord_rows_for_the_same_bar_are_merged_into_one_window(self) -> None:
        """A bar subdivided into multiple chords in follow_timeline (same
        absolute_bar, several sub-chord rows) must collapse into a single
        measure-level window spanning the whole bar, not several."""
        melody = _melody()
        measure_data = build_melody_measure_sync_data([melody.section_by_id("Verse 1")])
        follow_timeline = [
            _ft_row(section="Verse 1", bar_in_section=1, absolute_bar=1, start=0.0, end=1.0),
            _ft_row(section="Verse 1", bar_in_section=1, absolute_bar=1, start=1.0, end=2.0),
        ]
        timing = resolve_melody_measure_timing(measure_data, follow_timeline)
        self.assertEqual(len(timing), 1)
        self.assertEqual(timing[0]["start"], 0.0)
        self.assertEqual(timing[0]["end"], 2.0)

    def test_empty_follow_timeline_produces_no_windows(self) -> None:
        melody = _melody()
        measure_data = build_melody_measure_sync_data(melody.sections)
        self.assertEqual(resolve_melody_measure_timing(measure_data, []), [])


if __name__ == "__main__":
    unittest.main()

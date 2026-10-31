"""Regression tests for Composition melody synced highlighting (P3).

Ensures build_composition_measure_sync_data produces correct measure-level
sync data that can be joined against the backing follow_timeline.
"""

from __future__ import annotations

import unittest


class TestBuildCompositionMeasureSyncData(unittest.TestCase):
    """build_composition_measure_sync_data groups events by bar and tracks note DOM indices."""

    def _build(self, section, events, meter="4/4"):
        from composition_playback_sync import build_composition_measure_sync_data
        return build_composition_measure_sync_data(section, events, meter=meter)

    def test_empty_events_returns_empty(self):
        self.assertEqual(self._build("Verse", []), [])
        self.assertEqual(self._build("Verse", None), [])

    def test_single_bar_single_note(self):
        events = [{"pitch": "C4", "beat": 0, "duration_beats": 4}]
        result = self._build("Verse", events)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["section"], "Verse")
        self.assertEqual(result[0]["bar_in_section"], 1)
        self.assertEqual(result[0]["note_start_index"], 0)
        self.assertEqual(result[0]["note_end_index"], 1)

    def test_rest_excluded_from_note_count(self):
        events = [
            {"pitch": "C4", "beat": 0, "duration_beats": 2},
            {"pitch": "rest", "beat": 2, "duration_beats": 2, "is_rest": True},
        ]
        result = self._build("Verse", events)
        self.assertEqual(result[0]["note_end_index"], 1)

    def test_two_bars_four_notes(self):
        events = [
            {"pitch": "C4", "beat": 0, "duration_beats": 2},
            {"pitch": "D4", "beat": 2, "duration_beats": 2},
            {"pitch": "E4", "beat": 4, "duration_beats": 2},
            {"pitch": "F4", "beat": 6, "duration_beats": 2},
        ]
        result = self._build("Chorus", events, meter="4/4")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["bar_in_section"], 1)
        self.assertEqual(result[0]["note_start_index"], 0)
        self.assertEqual(result[0]["note_end_index"], 2)
        self.assertEqual(result[1]["bar_in_section"], 2)
        self.assertEqual(result[1]["note_start_index"], 2)
        self.assertEqual(result[1]["note_end_index"], 4)

    def test_three_four_meter(self):
        events = [
            {"pitch": "C4", "beat": 0, "duration_beats": 3},
            {"pitch": "D4", "beat": 3, "duration_beats": 3},
        ]
        result = self._build("Waltz", events, meter="3/4")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["bar_in_section"], 1)
        self.assertEqual(result[1]["bar_in_section"], 2)


class TestResolveWithFollowTimeline(unittest.TestCase):
    """Composition measure sync data joins against follow_timeline."""

    def test_join_produces_timed_windows(self):
        from practice_melody_sync import resolve_melody_measure_timing

        measure_entries = [
            {"section": "Verse", "bar_in_section": 1, "note_start_index": 0, "note_end_index": 2},
            {"section": "Verse", "bar_in_section": 2, "note_start_index": 2, "note_end_index": 4},
        ]
        follow_timeline = [
            {"section": "Verse", "bar_in_section": 1, "absolute_bar": 0, "start_time": 0.0, "end_time": 2.5},
            {"section": "Verse", "bar_in_section": 2, "absolute_bar": 1, "start_time": 2.5, "end_time": 5.0},
        ]
        result = resolve_melody_measure_timing(measure_entries, follow_timeline)
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[0]["start"], 0.0)
        self.assertAlmostEqual(result[0]["end"], 2.5)
        self.assertEqual(result[0]["note_start"], 0)
        self.assertEqual(result[0]["note_end"], 2)

    def test_unmatched_sections_skipped(self):
        from practice_melody_sync import resolve_melody_measure_timing

        measure_entries = [
            {"section": "Verse", "bar_in_section": 1, "note_start_index": 0, "note_end_index": 2},
        ]
        follow_timeline = [
            {"section": "Chorus", "bar_in_section": 1, "absolute_bar": 0, "start_time": 0.0, "end_time": 2.5},
        ]
        result = resolve_melody_measure_timing(measure_entries, follow_timeline)
        self.assertEqual(len(result), 0)


class TestPracticeOriginalMelodySyncInSource(unittest.TestCase):
    """The Original Melody expander passes measure_sync to render_abc."""

    def test_render_abc_receives_measure_sync(self):
        from pathlib import Path
        src = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        block_start = src.index("Original Melody")
        block_end = src.index("elif _composition_doc", block_start)
        block = src[block_start:block_end]
        self.assertIn("build_composition_measure_sync_data", block)
        self.assertIn("resolve_melody_measure_timing", block)
        self.assertIn("measure_sync=_cm_msync", block)


class TestBackingOriginalMelodyPanelInSource(unittest.TestCase):
    """Backing shows ONE synchronized score that follows the main transport.

    The former panel had its own Play / Stop, a mini score, a chord list and an audio
    player (with the melody voice) duplicating Backing's transport; it was removed on
    purpose.
    """

    def _block(self) -> str:
        from pathlib import Path
        src = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        panel_start = src.index("Original Melody panel (Composition songs only)")
        panel_end = src.index("\n    try:", panel_start + 100)
        return src[panel_start:panel_end]

    def test_backing_panel_has_measure_sync(self):
        block = self._block()
        self.assertIn("build_composition_measure_sync_data", block)
        self.assertIn("measure_sync=_bk_msync", block)

    def test_backing_panel_has_no_second_transport_or_melody_audio(self):
        block = self._block()
        for forbidden in (
            "mount_synced_score_playback",
            "generate_preview_wav",
            "_backing_melody_playing_",
            "backing_melody_play_",
            "backing_melody_stop_",
            "include_melody",
        ):
            self.assertNotIn(forbidden, block)
        self.assertNotIn("st.button", block)

    def test_backing_panel_uses_shared_projection(self):
        block = self._block()
        self.assertIn("project_melody_events", block)
        self.assertNotIn("semitone_distance", block)


if __name__ == "__main__":
    unittest.main()

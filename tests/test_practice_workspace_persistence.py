"""Canonical practice_workspace_state save, apply, migration, and projection."""

from __future__ import annotations

import copy
import unittest

from music_persistent_state import apply_music_disk_state, build_music_disk_state
from practice_tools_ui import PRACTICE_ACTIVE_TOOL_KEY
from practice_workspace_persistence import (
    PRACTICE_METRONOME_BPM_KEY,
    PRACTICE_METRONOME_METER_KEY,
    PRACTICE_METRONOME_SUBDIVISION_KEY,
    PRACTICE_TONE_OCTAVE_KEY,
    PRACTICE_TONE_PITCH_CLASS_KEY,
    PRACTICE_TUNER_INSTRUMENT_CONTEXT_KEY,
    PRACTICE_TUNER_REFERENCE_PITCH_KEY,
    PRACTICE_TUNER_UI_MODE_KEY,
    PRACTICE_WORKSPACE_MIGRATED_KEY,
    PRACTICE_WORKSPACE_RESTORED_KEY,
    PRACTICE_WORKSPACE_STATE_KEY,
    apply_practice_workspace_from_payload,
    commit_practice_tool_selection,
    default_practice_workspace_state,
    migrate_legacy_practice_workspace_once,
    prepare_practice_workspace_for_render,
    project_practice_workspace_to_session,
    sync_practice_workspace_before_persist,
    upgrade_practice_workspace_blob,
)
from studio_page_state import init_practice_page_state


class _FakeSt:
    def __init__(self, ss: dict):
        self.session_state = ss


class TestPracticeWorkspacePersistence(unittest.TestCase):
    def test_tool_selection_round_trip(self) -> None:
        ss: dict = {"studio_page": "practice"}
        commit_practice_tool_selection(ss, "chart")
        st = _FakeSt(ss)
        blob = build_music_disk_state(st)
        self.assertIn("practice_workspace_state", blob)
        self.assertEqual(blob["practice_workspace_state"]["selected_practice_tool"], "chart")
        fresh = _FakeSt({"studio_page": "practice"})
        apply_music_disk_state(
            fresh,
            blob,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        self.assertEqual(fresh.session_state.get(PRACTICE_ACTIVE_TOOL_KEY), "chart")
        self.assertTrue(fresh.session_state.get(PRACTICE_WORKSPACE_RESTORED_KEY))

    def test_time_pitch_view_persists(self) -> None:
        ss: dict = {"studio_page": "practice"}
        commit_practice_tool_selection(ss, "time_and_pitch")
        from practice_tools_ui import PRACTICE_TIME_PITCH_VIEW_KEY
        from practice_workspace_persistence import (
            TIME_PITCH_VIEW_LIVE_TUNER,
            TIME_PITCH_VIEW_TONE_SUSTAIN,
            commit_practice_time_pitch_view,
        )

        commit_practice_time_pitch_view(ss, TIME_PITCH_VIEW_LIVE_TUNER)
        sync_practice_workspace_before_persist(ss)
        self.assertEqual(ss[PRACTICE_WORKSPACE_STATE_KEY]["time_pitch_view"], TIME_PITCH_VIEW_LIVE_TUNER)
        commit_practice_time_pitch_view(ss, TIME_PITCH_VIEW_TONE_SUSTAIN)
        sync_practice_workspace_before_persist(ss)
        self.assertEqual(ss[PRACTICE_WORKSPACE_STATE_KEY]["time_pitch_view"], TIME_PITCH_VIEW_TONE_SUSTAIN)

    def test_legacy_time_pitch_mode_migrates_to_view(self) -> None:
        blob = default_practice_workspace_state()
        blob.pop("time_pitch_view", None)
        blob["selected_time_pitch_mode"] = "tone"
        upgraded = upgrade_practice_workspace_blob(blob)
        from practice_workspace_persistence import TIME_PITCH_VIEW_TONE_SUSTAIN

        self.assertEqual(upgraded["time_pitch_view"], TIME_PITCH_VIEW_TONE_SUSTAIN)

    def test_metronome_settings_persist(self) -> None:
        ss = {
            "studio_page": "practice",
            PRACTICE_ACTIVE_TOOL_KEY: "timing",
            PRACTICE_METRONOME_BPM_KEY: 92,
            PRACTICE_METRONOME_METER_KEY: "3/4",
            PRACTICE_METRONOME_SUBDIVISION_KEY: "eighth",
        }
        st = _FakeSt(ss)
        blob = build_music_disk_state(st)
        metro = blob["practice_workspace_state"]["metronome"]
        self.assertEqual(metro["bpm"], 92)
        self.assertEqual(metro["meter"], "3/4")
        self.assertEqual(metro["subdivision"], "eighth")

    def test_tuner_and_tone_settings_persist(self) -> None:
        ss = {
            "studio_page": "practice",
            PRACTICE_ACTIVE_TOOL_KEY: "tuner",
            PRACTICE_TUNER_REFERENCE_PITCH_KEY: 442,
            PRACTICE_TUNER_INSTRUMENT_CONTEXT_KEY: "guitar",
            PRACTICE_TONE_PITCH_CLASS_KEY: "Eb",
            PRACTICE_TONE_OCTAVE_KEY: 3,
        }
        sync_practice_workspace_before_persist(ss)
        st = _FakeSt(ss)
        blob = build_music_disk_state(st)
        self.assertEqual(blob["practice_workspace_state"]["tuner"]["reference_pitch"], 442)
        self.assertEqual(blob["practice_workspace_state"]["tone"]["pitch_class"], "Eb")
        self.assertEqual(blob["practice_workspace_state"]["tone"]["octave"], 3)

    def test_legacy_snapshot_migrates_once(self) -> None:
        ss: dict = {}
        payload = {
            "session": {
                "_studio_page_snapshots": {"practice": {"practice_active_tool": "timing"}},
            }
        }
        migrated = migrate_legacy_practice_workspace_once(ss, payload)
        self.assertIsNotNone(migrated)
        self.assertEqual(migrated["selected_practice_tool"], "time_and_pitch")
        self.assertEqual(migrated["time_pitch_view"], "live_tuner")
        self.assertTrue(ss.get(PRACTICE_WORKSPACE_MIGRATED_KEY))
        self.assertIsNone(migrate_legacy_practice_workspace_once(ss, payload))

    def test_missing_fields_get_defaults_without_clobber(self) -> None:
        ss: dict = {PRACTICE_METRONOME_BPM_KEY: 88}
        blob = default_practice_workspace_state()
        blob["metronome"] = {"bpm": 120}
        apply_practice_workspace_from_payload(
            ss,
            {PRACTICE_WORKSPACE_STATE_KEY: blob},
            authoritative=True,
        )
        self.assertEqual(ss[PRACTICE_METRONOME_BPM_KEY], 120)

    def test_init_practice_page_does_not_clear_restored_tool(self) -> None:
        ss = {
            PRACTICE_WORKSPACE_RESTORED_KEY: True,
            PRACTICE_ACTIVE_TOOL_KEY: "coach",
            "practice_workspace_state": {"selected_practice_tool": "coach"},
        }
        init_practice_page_state(ss)
        self.assertEqual(ss[PRACTICE_ACTIVE_TOOL_KEY], "coach")

    def test_widget_init_cannot_overwrite_after_project(self) -> None:
        ss = {
            PRACTICE_WORKSPACE_STATE_KEY: {
                **default_practice_workspace_state(),
                "selected_practice_tool": "lyrics",
            },
            PRACTICE_WORKSPACE_RESTORED_KEY: True,
        }
        project_practice_workspace_to_session(ss, overwrite=True)
        init_practice_page_state(ss)
        prepare_practice_workspace_for_render(ss)
        self.assertEqual(ss[PRACTICE_ACTIVE_TOOL_KEY], "lyrics")

    def test_cross_device_cloud_apply(self) -> None:
        phone = _FakeSt({"studio_page": "practice"})
        commit_practice_tool_selection(phone.session_state, "transpose")
        cloud_blob = build_music_disk_state(phone)
        dell = _FakeSt({"studio_page": "practice", PRACTICE_ACTIVE_TOOL_KEY: ""})
        apply_music_disk_state(
            dell,
            cloud_blob,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        self.assertEqual(dell.session_state.get(PRACTICE_ACTIVE_TOOL_KEY), "transpose")

    def test_envelope_includes_music_workspace_state_section(self) -> None:
        ss = {"studio_page": "practice", PRACTICE_ACTIVE_TOOL_KEY: "time_and_pitch"}
        sync_practice_workspace_before_persist(ss)
        st = _FakeSt(ss)
        state = build_music_disk_state(st)
        ws = state.get("music_workspace_state") or {}
        self.assertIn("practice_workspace_state", ws)
        self.assertEqual(ws["practice_workspace_state"]["selected_practice_tool"], "time_and_pitch")


if __name__ == "__main__":
    unittest.main()

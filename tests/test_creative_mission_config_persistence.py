"""Phase 1 Item 2 — mission configuration persistence."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from creative_mission_config_persistence import (
    CREATIVE_MISSION_HYDRATED_SNAPSHOT_KEY,
    CREATIVE_MISSION_NEEDS_WIDGET_PROJECTION_KEY,
    CREATIVE_MISSION_PERSISTENCE_REQUESTED_KEY,
    CREATIVE_MISSION_WIDGETS_INSTANTIATED_KEY,
    CREATIVE_WORKSPACE_STATE_KEY,
    SAVE_REASON_MISSION_PICK,
    SAVE_REASON_MISSION_TARGET,
    VIOLATION_PASSIVE_MISSION_STARTUP_WRITE,
    VIOLATION_POST_INSTANTIATION_WIDGET_WRITE,
    canonical_mission_config_value,
    commit_mission_config_to_canonical,
    handle_user_mission_metrics_change,
    handle_user_mission_pick_change,
    handle_user_mission_target_selection,
    mark_mission_widgets_instantiated,
    note_passive_mission_config_persist,
    project_mission_config_from_canonical_before_widgets,
    should_gather_mission_config_from_session,
    snapshot_hydrated_mission_config,
)
from creative_workspace_state_persistence import (
    default_creative_workspace_state,
    gather_creative_workspace_from_session,
    sync_creative_workspace_state_before_persist,
)


class TestMissionConfigGather(unittest.TestCase):
    def test_autosave_does_not_overwrite_canonical_mission_pick(self) -> None:
        ss: dict = {
            "_creative_selector_hydration_complete": True,
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_active_mission": "Use only chord tones",
                "improv_mission_pick": "Use only chord tones",
            },
            CREATIVE_MISSION_HYDRATED_SNAPSHOT_KEY: {
                "improv_active_mission": "Use only chord tones",
                "improv_mission_pick": "Use only chord tones",
            },
            "improv_mission_pick": "Rhythm-first, note-second",
            "improv_active_mission": "Rhythm-first, note-second",
        }
        self.assertFalse(
            should_gather_mission_config_from_session(
                ss, "improv_mission_pick", "Rhythm-first, note-second", persist_reason="autosave"
            )
        )
        gathered = gather_creative_workspace_from_session(ss)
        self.assertEqual(gathered.get("improv_mission_pick"), "Use only chord tones")

    def test_user_save_reason_allows_gather(self) -> None:
        ss: dict = {
            CREATIVE_WORKSPACE_STATE_KEY: default_creative_workspace_state(),
            "improv_mission_pick": "Target tone drill",
        }
        self.assertTrue(
            should_gather_mission_config_from_session(
                ss, "improv_mission_pick", "Target tone drill", persist_reason=SAVE_REASON_MISSION_PICK
            )
        )


class TestMissionConfigUserSave(unittest.TestCase):
    def test_pick_change_requests_cloud_save(self) -> None:
        ss: dict = {
            "_script_run_seq": 3,
            CREATIVE_WORKSPACE_STATE_KEY: default_creative_workspace_state(),
            "improv_mission_pick": "ii–V–I drill",
        }
        with patch(
            "creative_mission_config_persistence.request_mission_config_cloud_save",
            return_value=True,
        ) as save:
            handle_user_mission_pick_change(ss)
            save.assert_called_once()
            self.assertEqual(save.call_args.kwargs.get("save_reason"), SAVE_REASON_MISSION_PICK)
        self.assertEqual(canonical_mission_config_value(ss, "improv_mission_pick"), "ii–V–I drill")


class TestMissionConfigPassiveWrite(unittest.TestCase):
    def test_passive_violation_when_canonical_drift(self) -> None:
        ss: dict = {
            CREATIVE_MISSION_HYDRATED_SNAPSHOT_KEY: {"improv_mission_pick": "Use only chord tones"},
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_mission_pick": "Rhythm-first, note-second",
            },
        }
        note_passive_mission_config_persist(ss, reason="autosave")
        codes = [v.get("code") for v in (ss.get("_creative_mission_config_diag") or {}).get("violations") or []]
        self.assertIn(VIOLATION_PASSIVE_MISSION_STARTUP_WRITE, codes)

    def test_sync_autosave_no_passive_when_snapshot_matches(self) -> None:
        ss: dict = {
            "_creative_selector_hydration_complete": True,
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_mission_pick": "Use only chord tones",
            },
            CREATIVE_MISSION_HYDRATED_SNAPSHOT_KEY: {"improv_mission_pick": "Use only chord tones"},
            "improv_mission_pick": "Use only chord tones",
        }
        snapshot_hydrated_mission_config(ss, source="test")
        sync_creative_workspace_state_before_persist(ss, reason="autosave")
        note_passive_mission_config_persist(ss, reason="autosave")
        codes = [v.get("code") for v in (ss.get("_creative_mission_config_diag") or {}).get("violations") or []]
        self.assertNotIn(VIOLATION_PASSIVE_MISSION_STARTUP_WRITE, codes)


class TestMissionWidgetLifecycle(unittest.TestCase):
    def test_chord_target_updates_canonical_without_widget_write_after_instantiation(self) -> None:
        ss: dict = {
            "_script_run_seq": 7,
            CREATIVE_WORKSPACE_STATE_KEY: default_creative_workspace_state(),
            "ii_selected_chord_index": 0,
            "ii_selected_chord": "C",
            "ii_selected_section": "Verse",
            "ii_selected_chord_label": "Verse · C",
        }
        mark_mission_widgets_instantiated(ss)
        before_index = ss["ii_selected_chord_index"]
        with patch(
            "creative_mission_config_persistence.request_mission_config_cloud_save",
            return_value=True,
        ) as save:
            handle_user_mission_target_selection(
                ss,
                chord="Am",
                section="Chorus",
                chord_index=5,
                chord_label="Chorus · Am",
            )
            save.assert_called_once()
            self.assertEqual(save.call_args.kwargs.get("save_reason"), SAVE_REASON_MISSION_TARGET)
        self.assertEqual(ss["ii_selected_chord_index"], before_index)
        self.assertEqual(canonical_mission_config_value(ss, "ii_selected_chord_index"), 5)
        self.assertEqual(canonical_mission_config_value(ss, "ii_selected_chord"), "Am")
        self.assertTrue(ss.get(CREATIVE_MISSION_NEEDS_WIDGET_PROJECTION_KEY))

    def test_next_rerun_projects_canonical_into_widgets_before_creation(self) -> None:
        ss: dict = {
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "ii_selected_chord_index": 5,
                "ii_selected_chord": "Am",
                "ii_selected_section": "Chorus",
                "ii_selected_chord_label": "Chorus · Am",
            },
            "ii_selected_chord_index": 0,
            CREATIVE_MISSION_NEEDS_WIDGET_PROJECTION_KEY: True,
        }
        project_mission_config_from_canonical_before_widgets(ss)
        self.assertEqual(ss.get("ii_selected_chord_index"), 5)
        self.assertEqual(ss.get("ii_selected_chord"), "Am")
        self.assertFalse(ss.get(CREATIVE_MISSION_NEEDS_WIDGET_PROJECTION_KEY))

    def test_commit_records_violation_on_post_instantiation_widget_write(self) -> None:
        ss: dict = {
            CREATIVE_WORKSPACE_STATE_KEY: default_creative_workspace_state(),
            CREATIVE_MISSION_WIDGETS_INSTANTIATED_KEY: True,
            "ii_selected_chord_index": 1,
        }
        commit_mission_config_to_canonical(
            ss,
            reason="test",
            values={"ii_selected_chord_index": 9},
            project_widget_keys=True,
        )
        codes = [v.get("code") for v in (ss.get("_creative_mission_config_diag") or {}).get("violations") or []]
        self.assertIn(VIOLATION_POST_INSTANTIATION_WIDGET_WRITE, codes)
        self.assertEqual(ss.get("ii_selected_chord_index"), 1)

    def test_metrics_callback_does_not_rewrite_widget_ids_after_instantiation(self) -> None:
        ss: dict = {
            "_script_run_seq": 8,
            CREATIVE_WORKSPACE_STATE_KEY: default_creative_workspace_state(),
            "improv_ai_metric_multiselect": ["Rhythm accuracy"],
            "improv_ai_metric_ids": ["old"],
        }
        mark_mission_widgets_instantiated(ss)
        with patch(
            "creative_mission_config_persistence.request_mission_config_cloud_save",
            return_value=True,
        ):
            handle_user_mission_metrics_change(ss)
        self.assertEqual(ss.get("improv_ai_metric_ids"), ["old"])

    def test_mission_pick_single_persistence_request(self) -> None:
        ss: dict = {
            CREATIVE_WORKSPACE_STATE_KEY: default_creative_workspace_state(),
            "improv_mission_pick": "Target tone drill",
        }
        with patch(
            "creative_mission_config_persistence.request_mission_config_cloud_save",
            return_value=True,
        ) as save:
            handle_user_mission_pick_change(ss)
            self.assertEqual(save.call_count, 1)


if __name__ == "__main__":
    unittest.main()

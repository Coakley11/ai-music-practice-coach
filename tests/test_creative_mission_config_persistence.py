"""Phase 1 Item 2 — mission configuration persistence."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from creative_mission_config_persistence import (
    CREATIVE_MISSION_HYDRATED_SNAPSHOT_KEY,
    CREATIVE_MISSION_PERSISTENCE_REQUESTED_KEY,
    CREATIVE_WORKSPACE_STATE_KEY,
    SAVE_REASON_MISSION_PICK,
    SAVE_REASON_MISSION_TARGET,
    VIOLATION_PASSIVE_MISSION_STARTUP_WRITE,
    canonical_mission_config_value,
    commit_mission_config_to_canonical,
    handle_user_mission_pick_change,
    note_passive_mission_config_persist,
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


if __name__ == "__main__":
    unittest.main()

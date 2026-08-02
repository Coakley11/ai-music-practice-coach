"""Restore/save deadlock — bootstrap dirty must not block cloud apply."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from music_workspace_restore_mode import (
    clear_bootstrap_local_dirty_flags,
    complete_workspace_restore_after_apply,
    prepare_music_cold_start_restore,
    should_record_user_local_dirty,
    workspace_restore_in_progress,
)
from suite_user_persistence import _local_dirty_key, sync_workspace_protocol


class RestoreModeDirtyGatingTests(unittest.TestCase):
    def test_bootstrap_dirty_not_recorded_during_restore(self) -> None:
        ss: dict = {}
        prepare_music_cold_start_restore(ss, "music")
        self.assertTrue(workspace_restore_in_progress(ss))
        self.assertFalse(should_record_user_local_dirty(ss))

    def test_user_dirty_after_restore_complete(self) -> None:
        ss: dict = {}
        prepare_music_cold_start_restore(ss, "music")
        complete_workspace_restore_after_apply(
            ss,
            source="cloud",
            payload={"core": {"pick_key": "Pop::Say — John Mayer"}, "workspace_revision": 3},
        )
        self.assertFalse(workspace_restore_in_progress(ss))
        self.assertTrue(should_record_user_local_dirty(ss))

    def test_cold_start_clears_suite_local_dirty(self) -> None:
        ss = {_local_dirty_key("music"): True, "active_song_state_dirty": True}
        prepare_music_cold_start_restore(ss, "music")
        self.assertFalse(ss.get(_local_dirty_key("music")))
        self.assertFalse(ss.get("active_song_state_dirty"))

    def test_revision_consistency_after_apply(self) -> None:
        ss: dict = {}
        complete_workspace_restore_after_apply(
            ss,
            source="cloud",
            payload={"music_workspace_state": {"workspace_revision": 5}, "workspace_revision": 5},
        )
        from music_workspace_restore_mode import authoritative_payload_applied, collect_revision_consistency_diagnostics

        self.assertTrue(authoritative_payload_applied(ss))
        diag = collect_revision_consistency_diagnostics(ss)
        self.assertTrue(diag.get("cloud_state_applied"))
        self.assertEqual(diag.get("selected_payload_revision"), 5)


class SyncProtocolBootstrapDirtyTests(unittest.TestCase):
    def test_startup_dirty_does_not_skip_cloud_apply(self) -> None:
        cloud = {
            "core": {"studio_page": "practice", "pick_key": "Pop::Say — John Mayer"},
            "workspace_revision": 2,
        }
        st = SimpleNamespace(
            session_state={
                _local_dirty_key("music"): True,
                "_active_song_local_dirty": True,
                "active_song_state_dirty": True,
                "studio_page": "picker",
                "active_catalog_pick_key": "Folk::Hevenu Shalom Aleichem",
            }
        )
        applied: dict = {}

        def apply_state(_st: object, state: dict) -> None:
            applied.update(state)

        with patch("suite_cloud_state.load_cloud_full_session", return_value=(cloud, "2026-01-02T00:00:00Z")), patch(
            "suite_user_persistence._load_raw", return_value=({}, None, None)
        ), patch("suite_user_persistence.save_user_state", return_value=True), patch(
            "music_workspace_hydration.workspace_blob_hydrated", return_value=False
        ), patch("suite_user.get_account_user_id", return_value="user-1"):
            ok = sync_workspace_protocol(
                st,
                "music",
                apply_state=apply_state,
                cloud_first=True,
            )
        self.assertTrue(ok)
        self.assertEqual(applied.get("core", {}).get("pick_key"), "Pop::Say — John Mayer")


if __name__ == "__main__":
    unittest.main()

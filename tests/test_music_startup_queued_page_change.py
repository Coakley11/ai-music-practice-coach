"""Queued Creative page_change must flush after startup suppression releases."""

from __future__ import annotations

import copy
import os
import unittest
from contextlib import ExitStack
from typing import Any
from unittest.mock import MagicMock, patch

import suite_storage
from music_egress_config import MUSIC_EGRESS_STRICT_KEY
from music_page_save_pipeline_trace import payload_pages_from_state
from music_persistent_state import apply_music_disk_state
from music_startup_save_suppression import (
    STARTUP_SUPPRESSION_ARMED_KEY,
    record_hydrated_canonical_fingerprint,
    set_page_change_origin,
)
from studio_nav_history import navigate_studio_page
from studio_nav_state import STUDIO_NAV_STATE_KEY, prepare_studio_nav
from suite_cloud_state import CloudSaveResult
from suite_user_persistence import _local_dirty_key
from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY


def _backing_payload(rev: int = 7) -> dict[str, Any]:
    return {
        "core": {
            "pick_key": "Traditional::Hevenu Shalom Aleichem",
            "studio_page": "backing",
            "page": "backing",
            "instrument": "Piano",
            "level": "Beginner",
            "focus": "Left-Hand Patterns",
            "display_key": "C",
        },
        "session": {"studio_page": "backing"},
        "studio_nav_state": {"studio_page": "backing", "page": "backing"},
        "active_song_state": {
            "pick_key": "Traditional::Hevenu Shalom Aleichem",
            "instrument": "Piano",
            "level": "Beginner",
            "focus": "Left-Hand Patterns",
            "display_key": "C",
            "display_key_owner_identity": "cloud-owner",
        },
        "creative_workspace_state": {
            "improv_mission_workspace_updated_at": "2026-01-01T00:00:00Z",
        },
        "music_workspace_state": {
            "workspace_revision": rev,
            "studio_page": "backing",
            "page": "backing",
            "creative_workspace_state": {
                "improv_mission_workspace_updated_at": "2026-01-02T00:00:00Z",
            },
        },
        "workspace_revision": rev,
    }


class _FakeSessionState(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class StartupQueuedPageChangeTests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop(MUSIC_EGRESS_STRICT_KEY, None)

    def _cloud_patches(self, ss: dict[str, Any], cloud_writes: list[dict[str, Any]]):
        stack = ExitStack()

        def _save_cloud(_app: str, state: dict, **kwargs: object) -> CloudSaveResult:
            import copy as copy_mod

            cloud_writes.append(copy_mod.deepcopy(state))
            ss["_suite_persist_last_save_cloud"] = True
            return CloudSaveResult(success=True, save_cloud_full_session_return_value=True)

        for ctx in (
            patch("music_workspace_cloud_save._cloud_enabled", return_value=True),
            patch("suite_user_persistence.save_user_state", return_value=True),
            patch("suite_storage_config.cloud_storage_enabled", return_value=True),
            patch("suite_storage_config.get_cloud_config", return_value=object()),
            patch("suite_cloud_state._import_storage", return_value=(suite_storage, "suite_storage")),
            patch("suite_cloud_state._cloud_storage_app_id", return_value="music"),
            patch.object(suite_storage, "save_current_state"),
            patch("suite_cloud_state._streamlit_session", return_value=ss),
            patch("suite_cloud_state.save_cloud_full_session", side_effect=_save_cloud),
            patch("music_egress_config.skip_cloud_readback_after_write", return_value=True),
        ):
            stack.enter_context(ctx)
        return stack

    def _armed_backing_session(self) -> _FakeSessionState:
        payload = _backing_payload()
        ss = _FakeSessionState(
            {
                "developer_mode": True,
                "_phase1_write_journal_force": True,
                "_music_workspace_blob_hydrated": True,
                STARTUP_SUPPRESSION_ARMED_KEY: True,
                "_script_run_seq": 99,
                SELECTED_SONG_STATE_KEY: {"pick_key": payload["core"]["pick_key"]},
                ACTIVE_CATALOG_PICK_KEY: payload["core"]["pick_key"],
                "studio_page": "backing",
                STUDIO_NAV_STATE_KEY: dict(payload["studio_nav_state"]),
                "music_workspace_state": copy.deepcopy(payload["music_workspace_state"]),
                "active_song_state": copy.deepcopy(payload["active_song_state"]),
                "creative_workspace_state": copy.deepcopy(payload["creative_workspace_state"]),
                "_suite_last_cloud_fetch_payload": payload,
                _local_dirty_key("music"): True,
            }
        )
        record_hydrated_canonical_fingerprint(ss, payload, stage="test:armed_backing")
        set_page_change_origin(ss, "user_navigation")
        return ss

    def test_creative_click_flushes_after_suppression_release(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        ss = self._armed_backing_session()
        cloud_writes: list[dict[str, Any]] = []

        def _release_finalize(st: MagicMock, *, stage: str = "") -> bool:
            st.session_state["startup_suppression_released"] = True
            st.session_state["startup_fingerprint_matches"] = True
            st.session_state["startup_restore_in_progress"] = False
            st.session_state["startup_revision_final"] = st.session_state.get("startup_revision_loaded")
            return True

        with self._cloud_patches(ss, cloud_writes):
            with patch(
                "music_startup_save_suppression.finalize_startup_canonical_alignment",
                side_effect=_release_finalize,
            ):
                self.assertTrue(navigate_studio_page(ss, "creative"))

        self.assertEqual(ss.get("studio_page"), "creative")
        self.assertTrue(ss.get("queued_page_change_flushed"))
        self.assertTrue(ss.get("_music_page_change_payload_built"))
        self.assertGreaterEqual(len(cloud_writes), 1)

        pages = payload_pages_from_state(cloud_writes[-1])
        for val in pages.values():
            if val:
                self.assertEqual(val, "creative")

        tx = ss.get("_music_workspace_save_transaction") or {}
        self.assertNotEqual(tx.get("force_save_early_return_reason"), "startup_suppression_armed_page_change")

        ss2 = _FakeSessionState({"developer_mode": True})
        st2 = MagicMock()
        st2.session_state = ss2
        apply_music_disk_state(
            st2,
            cloud_writes[-1],
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        self.assertEqual(prepare_studio_nav(ss2), "creative")

    def test_metadata_only_diff_allows_fingerprint_match(self) -> None:
        from music_startup_save_suppression import _metadata_only_canonical_diff

        differing = [
            "active_song_state.display_key_owner_identity",
            "creative_workspace_state.improv_mission_workspace_updated_at",
            "music_workspace_state.creative_workspace_state.improv_mission_workspace_updated_at",
        ]
        self.assertTrue(_metadata_only_canonical_diff(differing))
        self.assertFalse(_metadata_only_canonical_diff(["core.studio_page"]))


if __name__ == "__main__":
    unittest.main()

"""Startup suppression vs explicit sidebar display_key_change."""

from __future__ import annotations

import os
import unittest
from contextlib import ExitStack
from typing import Any
from unittest.mock import MagicMock, patch

import suite_storage
from display_key_startup_save_queue import (
    QUEUED_DISPLAY_KEY_CHANGE_KEY,
    flush_queued_display_key_change_once,
    has_queued_display_key_change,
    queue_explicit_display_key_change,
)
from music_egress_config import MUSIC_EGRESS_STRICT_KEY
from music_startup_save_suppression import (
    RESTORE_FINALIZED_STAGE_KEY,
    STARTUP_FINGERPRINT_MATCHES_KEY,
    STARTUP_RESTORE_IN_PROGRESS_KEY,
    STARTUP_REVISION_LOADED_KEY,
    STARTUP_SUPPRESSION_ARMED_KEY,
    STARTUP_SUPPRESSION_RELEASED_KEY,
    _volatile_only_canonical_diff,
    finalize_startup_canonical_alignment,
    run_late_startup_restore_guard,
)
from music_workspace_canonical_fingerprint import workspace_canonical_content_fingerprint
from suite_user_persistence import _local_dirty_key


class TestDisplayKeyStartupSaveQueue(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop(MUSIC_EGRESS_STRICT_KEY, None)

    def test_scenario_d_volatile_fingerprint_diff(self) -> None:
        differing = ["creative_workspace_state.creative_session.updated_at"]
        self.assertTrue(_volatile_only_canonical_diff(differing))
        a = {
            "core": {"display_key": "Dm", "studio_page": "creative"},
            "active_song_state": {"display_key": "Dm"},
            "creative_workspace_state": {"creative_session": {"updated_at": "a"}},
        }
        b = {
            "core": {"display_key": "Dm", "studio_page": "creative"},
            "active_song_state": {"display_key": "Dm"},
            "creative_workspace_state": {"creative_session": {"updated_at": "b"}},
        }
        self.assertEqual(
            workspace_canonical_content_fingerprint(a),
            workspace_canonical_content_fingerprint(b),
        )

    def test_scenario_c_passive_startup_no_queue(self) -> None:
        ss: dict[str, Any] = {
            STARTUP_SUPPRESSION_ARMED_KEY: True,
            "display_key": "Dm",
        }
        self.assertFalse(has_queued_display_key_change(ss))

    def test_scenario_a_queue_then_late_flush(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        from music_startup_save_suppression import HYDRATED_PAYLOAD_SNAPSHOT_KEY, record_hydrated_canonical_fingerprint

        hydrated = {
            "core": {"display_key": "Dm", "studio_page": "creative", "pick_key": "Traditional::X"},
            "active_song_state": {"display_key": "Dm", "pick_key": "Traditional::X"},
            "workspace_revision": 3,
        }
        ss: dict[str, Any] = {
            "developer_mode": True,
            "_music_workspace_blob_hydrated": True,
            STARTUP_SUPPRESSION_ARMED_KEY: True,
            STARTUP_RESTORE_IN_PROGRESS_KEY: True,
            STARTUP_REVISION_LOADED_KEY: 3,
            _local_dirty_key("music"): True,
            "display_key": "Cm",
            "display_key_change_source": "sidebar_on_change",
            HYDRATED_PAYLOAD_SNAPSHOT_KEY: hydrated,
        }
        record_hydrated_canonical_fingerprint(ss, hydrated, stage="test")
        queue_explicit_display_key_change(
            ss,
            transaction_id="tx-a",
            old_value="Dm",
            new_value="Cm",
        )
        self.assertTrue(has_queued_display_key_change(ss))
        st = MagicMock()
        st.session_state = ss

        rev = 3

        def build_state(_st: object) -> dict[str, Any]:
            return {
                "core": {"display_key": "Cm", "studio_page": "creative", "pick_key": "Traditional::X"},
                "active_song_state": {"display_key": "Cm", "pick_key": "Traditional::X"},
                "workspace_revision": rev,
            }

        def stamp(_s: object, state: dict, **_kw: object) -> dict:
            out = dict(state)
            out["workspace_revision"] = rev + 1
            return out

        cloud_calls: list[Any] = []

        def _cloud_save(st_obj: Any, state: dict, **_kw: Any) -> bool:
            cloud_calls.append(state.get("core", {}).get("display_key"))
            st_obj.session_state["_music_last_cloud_write_ok"] = True
            st_obj.session_state["_suite_persist_last_save_cloud"] = True
            st_obj.session_state["_music_force_save_ok"] = True
            from music_workspace_cloud_save import record_save_transaction

            record_save_transaction(
                st_obj.session_state,
                cloud_write_attempted=True,
                cloud_upsert_succeeded=True,
                reserved_write_revision=rev + 1,
                payload_core_display_key="Cm",
                cloud_confirmed=True,
            )
            try:
                from display_key_sidebar_cloud_confirmation import record_display_key_supabase_result

                record_display_key_supabase_result(st_obj.session_state, saved=True)
            except ImportError:
                pass
            return True

        readback = build_state(st)
        readback["workspace_revision"] = rev + 1

        def _load_network(_app: str, *, force: bool = False) -> tuple[dict[str, Any], str]:
            ss["_music_last_cloud_fetch_source"] = "network"
            return readback, "2026-01-01T00:00:00Z"

        with ExitStack() as stack:
            for ctx in (
                patch("music_workspace_cloud_save._cloud_enabled", return_value=True),
                patch("suite_user_persistence.save_user_state", return_value=True),
                patch("music_persistent_state.build_music_disk_state", side_effect=build_state),
                patch("music_persistent_state.stamp_music_payload_for_write", side_effect=stamp),
                patch("music_persistent_state.save_music_cloud_session", side_effect=_cloud_save),
                patch("suite_storage_config.cloud_storage_enabled", return_value=True),
                patch("suite_cloud_state.load_cloud_full_session", side_effect=_load_network),
                patch("suite_cloud_state.session_page_summary", return_value=("creative", "x")),
            ):
                stack.enter_context(ctx)
            ss[RESTORE_FINALIZED_STAGE_KEY] = "late_end_of_run"
            run_late_startup_restore_guard(st)

        self.assertTrue(ss.get(STARTUP_SUPPRESSION_RELEASED_KEY))
        self.assertFalse(has_queued_display_key_change(ss))
        self.assertGreaterEqual(len(cloud_calls), 1)
        self.assertEqual(cloud_calls[0], "Cm")

    def test_scenario_b_stale_release_allows_immediate_save(self) -> None:
        from display_key_startup_save_queue import attempt_release_stale_startup_suppression_for_display_key
        from display_key_sidebar_persistence_trace import arm_explicit_sidebar_display_key_save

        ss: dict[str, Any] = {
            STARTUP_SUPPRESSION_ARMED_KEY: True,
            STARTUP_RESTORE_IN_PROGRESS_KEY: True,
            RESTORE_FINALIZED_STAGE_KEY: "late_end_of_run",
            "display_key": "Cm",
            "display_key_change_source": "sidebar_on_change",
        }
        arm_explicit_sidebar_display_key_save(ss, transaction_id="tx-b", selected_display_key="Cm")
        st = MagicMock()
        st.session_state = ss
        self.assertTrue(attempt_release_stale_startup_suppression_for_display_key(st))
        self.assertTrue(ss.get(STARTUP_SUPPRESSION_RELEASED_KEY))
        self.assertFalse(ss.get(STARTUP_RESTORE_IN_PROGRESS_KEY))


if __name__ == "__main__":
    unittest.main()

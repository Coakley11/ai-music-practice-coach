"""Explicit sidebar display_key save must propagate force_save / cloud session returns."""

from __future__ import annotations

import os
import unittest
from contextlib import ExitStack, contextmanager
from typing import Any
from unittest.mock import MagicMock, patch

import suite_storage
from display_key_sidebar_persistence_trace import (
    DISPLAY_KEY_SIDEBAR_TRACE_KEY,
    arm_explicit_sidebar_display_key_save,
    begin_display_key_sidebar_transaction,
    collect_display_key_sidebar_trace,
)
from music_egress_config import MUSIC_EGRESS_STRICT_KEY
from suite_user_persistence import _local_dirty_key


class TestDisplayKeySidebarSaveReturnPath(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop(MUSIC_EGRESS_STRICT_KEY, None)

    def _hevenu_state(self, *, display_key: str, rev: int) -> dict[str, Any]:
        return {
            "core": {
                "pick_key": "Traditional::Hevenu Shalom Aleichem",
                "studio_page": "creative",
                "display_key": display_key,
            },
            "active_song_state": {
                "pick_key": "Traditional::Hevenu Shalom Aleichem",
                "instrument": "Piano",
                "level": "Intermediate",
                "focus": "Melody",
                "display_key": display_key,
                "selected_song": {"pick_key": "Traditional::Hevenu Shalom Aleichem", "key": "Cm"},
            },
            "workspace_revision": rev,
        }

    @contextmanager
    def _save_patches(self, ss: dict[str, Any], stamp):
        with ExitStack() as stack:
            for ctx in (
                patch("music_workspace_cloud_save._cloud_enabled", return_value=True),
                patch("suite_user_persistence.save_user_state", return_value=True),
                patch("music_persistent_state.stamp_music_payload_for_write", side_effect=stamp),
                patch("suite_storage_config.cloud_storage_enabled", return_value=True),
                patch("suite_storage_config.get_cloud_config", return_value=object()),
                patch("suite_cloud_state._import_storage", return_value=(suite_storage, "suite_storage")),
                patch("suite_cloud_state._cloud_storage_app_id", return_value="music"),
                patch.object(suite_storage, "save_current_state"),
                patch("suite_cloud_state._streamlit_session", return_value=ss),
                patch("suite_cloud_state.session_page_summary", return_value=("creative", "Hevenu")),
            ):
                stack.enter_context(ctx)
            yield

    def test_commit_propagates_save_music_cloud_session_return_not_none(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        from music_startup_save_suppression import STARTUP_FINGERPRINT_MATCHES_KEY
        from songs.key_state import commit_explicit_sidebar_display_key_transaction

        ss: dict[str, Any] = {
            "developer_mode": True,
            "_music_workspace_blob_hydrated": True,
            _local_dirty_key("music"): True,
            "display_key": "Cm",
            "display_key_change_source": "sidebar_on_change",
            STARTUP_FINGERPRINT_MATCHES_KEY: True,
        }
        tx = begin_display_key_sidebar_transaction(ss, caller="mark_display_key_changed")
        arm_explicit_sidebar_display_key_save(
            ss,
            transaction_id=tx,
            selected_display_key="Cm",
            cloud_display_key_before="Dm",
        )
        st = MagicMock()
        st.session_state = ss
        rev = 20

        def build_state(_st: object) -> dict[str, Any]:
            return self._hevenu_state(display_key="Cm", rev=rev)

        def stamp(_s: object, state: dict, **_kw: object) -> dict:
            out = dict(state)
            out["workspace_revision"] = rev + 1
            return out

        cloud_save_calls: list[dict[str, Any]] = []

        def _realistic_cloud_save(st_obj: Any, state: dict, **_kw: Any) -> bool:
            cloud_save_calls.append({"display_key": state.get("core", {}).get("display_key")})
            st_obj.session_state["_music_last_cloud_write_ok"] = True
            st_obj.session_state["_music_last_cloud_save_diag"] = {
                "cloud_upsert_attempted": True,
                "cloud_upsert_succeeded": True,
                "cloud_payload_revision": rev + 1,
            }
            st_obj.session_state["_suite_persist_last_save_cloud"] = True
            st_obj.session_state["_music_force_save_ok"] = True
            from music_workspace_cloud_save import record_save_transaction

            record_save_transaction(
                st_obj.session_state,
                cloud_write_attempted=True,
                cloud_upsert_succeeded=True,
                reserved_write_revision=rev + 1,
                payload_core_display_key="Cm",
                strict_egress_plan_action="immediate",
                duplicate_write_skipped=False,
            )
            from display_key_sidebar_cloud_confirmation import record_display_key_supabase_result

            record_display_key_supabase_result(st_obj.session_state, saved=True)
            return True

        readback = self._hevenu_state(display_key="Cm", rev=rev + 1)

        def _load_network(_app: str, *, force: bool = False) -> tuple[dict[str, Any], str]:
            ss["_music_last_cloud_fetch_source"] = "network"
            return readback, "2026-01-01T00:00:00Z"

        with self._save_patches(ss, stamp):
            with patch("music_persistent_state.build_music_disk_state", side_effect=build_state):
                with patch("music_persistent_state.save_music_cloud_session", side_effect=_realistic_cloud_save):
                    with patch("suite_cloud_state.load_cloud_full_session", side_effect=_load_network):
                        with patch(
                            "active_song_state.flush_global_control_edits",
                            lambda _s, **_: None,
                        ):
                            with patch(
                                "active_song_state.mark_active_song_local_edit",
                                lambda _s: None,
                            ):
                                ok = commit_explicit_sidebar_display_key_transaction(
                                    st,
                                    caller="mark_display_key_changed",
                                    transaction_id=tx,
                                )

        self.assertTrue(ok, ss.get("_music_force_save_blocked_reason"))
        self.assertEqual(len(cloud_save_calls), 1)
        trace = collect_display_key_sidebar_trace(ss)
        save_tx = trace.get("save_transaction") or {}
        self.assertTrue(save_tx.get("cloud_write_attempted"), save_tx)
        self.assertEqual(str(save_tx.get("payload_core_display_key") or ""), "Cm")
        smc_ret = save_tx.get("save_music_cloud_session_return_value")
        self.assertIsNotNone(smc_ret)
        self.assertTrue(smc_ret)
        forensic = trace.get("confirmation_forensic") or {}
        self.assertTrue(forensic.get("confirmed"), forensic)
        self.assertEqual(trace.get("violations") or [], [])

    def test_startup_suppressed_flush_global_does_not_block_force_save_path(self) -> None:
        """commit uses force_save_music_state, not flush_global_control_edits_and_save startup gate."""
        from display_key_sidebar_save_pipeline import run_explicit_display_key_cloud_save

        ss: dict[str, Any] = {
            "developer_mode": True,
            "display_key": "Cm",
            "display_key_change_source": "sidebar_on_change",
        }
        tx = begin_display_key_sidebar_transaction(ss, caller="test")
        arm_explicit_sidebar_display_key_save(ss, transaction_id=tx, selected_display_key="Cm")
        st = MagicMock()
        st.session_state = ss

        with patch(
            "music_persistent_state.flush_global_control_edits_and_save",
            return_value=False,
        ) as flush_save:
            with patch(
                "music_persistent_state.force_save_music_state",
                return_value=True,
            ) as force_save:
                with patch(
                    "display_key_sidebar_cloud_confirmation.finalize_display_key_sidebar_save_outcome",
                    return_value=True,
                ):
                    ok = run_explicit_display_key_cloud_save(st, transaction_id=tx, caller="test")
        self.assertTrue(ok)
        flush_save.assert_not_called()
        force_save.assert_called_once()


if __name__ == "__main__":
    unittest.main()

"""Explicit sidebar display_key_change must reach cloud under strict egress."""

from __future__ import annotations

import os
import unittest
from contextlib import ExitStack, contextmanager
from typing import Any
from unittest.mock import MagicMock, patch

import suite_storage
from display_key_sidebar_persistence_trace import (
    DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY,
    active_sidebar_display_key_transaction_id,
    arm_explicit_sidebar_display_key_save,
    begin_display_key_sidebar_transaction,
    should_force_display_key_cloud_write,
)
from music_egress_config import MUSIC_EGRESS_STRICT_KEY
from music_egress_strict_save import plan_strict_egress_cloud_write
from suite_user_persistence import _local_dirty_key


class TestDisplayKeySidebarCloudSave(unittest.TestCase):
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

    def test_force_plan_when_sidebar_armed_dm_to_cm(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        ss: dict[str, Any] = {
            "display_key": "Cm",
            "display_key_change_source": "sidebar_on_change",
            "_music_last_confirmed_cloud_fp": "old_fp_dm",
        }
        tx = begin_display_key_sidebar_transaction(ss, caller="test")
        arm_explicit_sidebar_display_key_save(
            ss,
            transaction_id=tx,
            selected_display_key="Cm",
            cloud_display_key_before="Dm",
            canonical_display_key_before="Dm",
        )
        self.assertTrue(should_force_display_key_cloud_write(ss, save_reason="display_key_change", payload_fp="old_fp_dm"))
        plan = plan_strict_egress_cloud_write(ss, save_reason="display_key_change", payload_fp="old_fp_dm")
        self.assertFalse(plan.duplicate_write_skipped)
        self.assertTrue(plan.allow_cloud_write)
        self.assertTrue(plan.payload_changed_since_last_confirmed_save)

    def test_display_key_change_cloud_save_succeeds_under_strict_egress(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        from music_workspace_cloud_save import force_music_workspace_save

        from music_startup_save_suppression import STARTUP_FINGERPRINT_MATCHES_KEY

        ss: dict[str, Any] = {
            "developer_mode": True,
            "_music_workspace_blob_hydrated": True,
            _local_dirty_key("music"): True,
            "display_key": "Cm",
            "display_key_change_source": "sidebar_on_change",
            STARTUP_FINGERPRINT_MATCHES_KEY: False,
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
        rev = 12

        def build_state(_st: object) -> dict[str, Any]:
            return self._hevenu_state(display_key="Cm", rev=rev)

        def stamp(_s: object, state: dict, **_kw: object) -> dict:
            out = dict(state)
            out["workspace_revision"] = rev + 1
            return out

        with self._save_patches(ss, stamp):
            def _fake_cloud_save(st: Any, state: dict, **_kw: Any) -> bool:
                st.session_state["_music_last_cloud_save_diag"] = {
                    "cloud_upsert_attempted": True,
                    "cloud_upsert_succeeded": True,
                    "cloud_payload_revision": rev + 1,
                }
                st.session_state["_music_workspace_save_transaction"] = {
                    **(st.session_state.get("_music_workspace_save_transaction") or {}),
                    "cloud_write_attempted": True,
                    "cloud_upsert_succeeded": True,
                    "reserved_write_revision": rev + 1,
                }
                try:
                    from display_key_sidebar_cloud_confirmation import record_display_key_supabase_result

                    record_display_key_supabase_result(st.session_state, saved=True)
                except ImportError:
                    pass
                return True

            readback_state = self._hevenu_state(display_key="Cm", rev=rev + 1)

            def _load_network(_app: str, *, force: bool = False) -> tuple[dict[str, Any], str]:
                ss["_music_last_cloud_fetch_source"] = "network"
                return readback_state, "2026-01-01T00:00:00Z"

            with patch("music_persistent_state.save_music_cloud_session", side_effect=_fake_cloud_save):
                with patch("suite_cloud_state.load_cloud_full_session", side_effect=_load_network):
                    ok = force_music_workspace_save(st, reason="display_key_change", build_state=build_state)

        self.assertTrue(ok, ss.get("_music_force_save_blocked_reason"))
        self.assertTrue(ss.get("_suite_persist_last_save_cloud"))
        self.assertEqual(active_sidebar_display_key_transaction_id(ss), tx)
        tx_diag = ss.get("_music_workspace_save_transaction") or {}
        self.assertEqual(str(tx_diag.get("payload_core_display_key") or ""), "Cm")


if __name__ == "__main__":
    unittest.main()

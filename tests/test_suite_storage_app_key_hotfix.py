"""Regression: cloud save must not call normalize_app_key on suite_storage shim."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import suite_storage
from suite_cloud_state import save_cloud_full_session
from suite_storage_supabase import normalize_app_key
from suite_workspace import logical_storage_app_key


class SuiteStorageAppKeyHotfixTests(unittest.TestCase):
    def test_suite_storage_shim_does_not_export_normalize_app_key(self) -> None:
        self.assertFalse(hasattr(suite_storage, "normalize_app_key"))

    def test_suite_cloud_state_does_not_call_storage_normalize_app_key(self) -> None:
        source = Path(__file__).resolve().parents[1].joinpath("suite_cloud_state.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("storage.normalize_app_key", source)

    def test_canonical_helpers_music_and_scoped_profile(self) -> None:
        self.assertEqual(normalize_app_key("music"), "music")
        self.assertEqual(logical_storage_app_key("music"), "music")
        self.assertEqual(normalize_app_key("music__ariel"), "music__ariel")
        self.assertEqual(logical_storage_app_key("music__ariel"), "music")

    def test_save_reaches_writer_with_real_suite_storage_shim(self) -> None:
        state = {"core": {"pick_key": "x"}, "workspace_revision": 1}
        session: dict = {}
        with patch("suite_cloud_state._streamlit_session", return_value=session), patch(
            "suite_storage_config.cloud_storage_enabled", return_value=True
        ), patch("suite_storage_config.get_cloud_config", return_value=object()), patch(
            "suite_cloud_state._import_storage", return_value=(suite_storage, "suite_storage")
        ), patch("suite_cloud_state._cloud_storage_app_id", return_value="music"), patch.object(
            suite_storage, "save_current_state"
        ) as mock_save:
            result = save_cloud_full_session("music", state)

        self.assertTrue(result.success, result.failure_stage)
        self.assertTrue(result.cloud_upsert_succeeded)
        mock_save.assert_called_once()
        self.assertEqual(mock_save.call_args.args[0], "music")

    def test_scoped_profile_passes_active_app_validation(self) -> None:
        state = {"core": {}, "workspace_revision": 1}
        session: dict = {}
        with patch("suite_cloud_state._streamlit_session", return_value=session), patch(
            "suite_storage_config.cloud_storage_enabled", return_value=True
        ), patch("suite_storage_config.get_cloud_config", return_value=object()), patch(
            "suite_cloud_state._import_storage", return_value=(suite_storage, "suite_storage")
        ), patch("suite_cloud_state._cloud_storage_app_id", return_value="music__ariel"), patch.object(
            suite_storage, "save_current_state"
        ) as mock_save:
            result = save_cloud_full_session("music", state)

        self.assertNotEqual(result.failure_stage, "inactive_app_key")
        self.assertTrue(result.success)
        self.assertEqual(result.storage_app_key, "music__ariel")
        mock_save.assert_called_once_with("music__ariel", page="", summary="Last session", metrics=ANY)

    def test_save_music_cloud_session_real_import_path(self) -> None:
        from music_persistent_state import save_music_cloud_session

        st = MagicMock()
        st.session_state = {}
        state = {"core": {"pick_key": "x"}, "workspace_revision": 2}
        with patch("suite_cloud_state._streamlit_session", return_value=st.session_state), patch(
            "suite_storage_config.cloud_storage_enabled", return_value=True
        ), patch("suite_storage_config.get_cloud_config", return_value=object()), patch(
            "suite_cloud_state._import_storage", return_value=(suite_storage, "suite_storage")
        ), patch("suite_cloud_state._cloud_storage_app_id", return_value="music"), patch.object(
            suite_storage, "save_current_state"
        ):
            ok = save_music_cloud_session(st, state, write_path="hotfix_test")

        self.assertTrue(ok)
        diag = st.session_state.get("_suite_last_cloud_save_result", {})
        self.assertTrue(diag.get("save_cloud_full_session_return_value"))
        self.assertTrue(diag.get("cloud_upsert_succeeded"))

    def test_successful_force_save_end_to_end_diag_flags(self) -> None:
        from music_workspace_cloud_save import force_music_workspace_save
        from suite_user_persistence import _local_dirty_key

        ss = {
            "_music_workspace_blob_hydrated": True,
            _local_dirty_key("music"): True,
        }
        st = MagicMock()
        st.session_state = ss
        rev = 1

        def build_state(_st: object) -> dict:
            return {"core": {"pick_key": "x"}, "workspace_revision": rev}

        def stamp(_st: object, state: dict, **_kw: object) -> dict:
            out = dict(state)
            out["workspace_revision"] = rev + 1
            return out

        stamped: dict = {}

        def _stamp(_s: object, state: dict, **kw: object) -> dict:
            stamped.clear()
            stamped.update(stamp(_s, state, **kw))
            return stamped

        def _load_cloud(*_a: object, **_k: object) -> tuple[dict, str]:
            return dict(stamped), "2026-01-01T00:00:00Z"

        with patch("music_workspace_cloud_save._cloud_enabled", return_value=True), patch(
            "suite_user_persistence.save_user_state", return_value=True
        ), patch("music_egress_config.music_cloud_write_allowed", return_value=True), patch(
            "music_persistent_state.stamp_music_payload_for_write", side_effect=_stamp
        ), patch("music_egress_config.skip_cloud_readback_after_write", return_value=False), patch(
            "suite_storage_config.cloud_storage_enabled", return_value=True
        ), patch("suite_storage_config.get_cloud_config", return_value=object()), patch(
            "suite_cloud_state._import_storage", return_value=(suite_storage, "suite_storage")
        ), patch("suite_cloud_state._cloud_storage_app_id", return_value="music"), patch.object(
            suite_storage, "save_current_state"
        ), patch("suite_cloud_state._streamlit_session", return_value=ss), patch(
            "suite_cloud_state.load_cloud_full_session", side_effect=_load_cloud
        ), patch(
            "suite_cloud_state.session_page_summary", return_value=("Creative", "test")
        ):
            ok = force_music_workspace_save(st, reason="song_edit", build_state=build_state)

        self.assertTrue(ok)
        cloud_diag = ss.get("_suite_last_cloud_save_result", {})
        self.assertTrue(cloud_diag.get("save_cloud_full_session_return_value"))
        self.assertTrue(cloud_diag.get("cloud_upsert_succeeded"))
        tx = ss.get("_music_workspace_save_transaction", {})
        self.assertTrue(tx.get("cloud_write_succeeded"))
        self.assertTrue(tx.get("cloud_readback_matches"))
        self.assertTrue(ss.get("_suite_persist_last_save_cloud"))


if __name__ == "__main__":
    unittest.main()

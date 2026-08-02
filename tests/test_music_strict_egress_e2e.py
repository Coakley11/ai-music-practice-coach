"""End-to-end strict egress: page_change through Supabase upsert."""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import suite_storage
from music_workspace_cloud_save import music_autosave_if_changed
from suite_user_persistence import _local_dirty_key, force_autosave


class StrictEgressGateUnificationTests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("MUSIC_EGRESS_STRICT", None)

    @contextmanager
    def _cloud_patches(self, ss: dict, stamp):
        with patch("suite_user_persistence.save_user_state", return_value=True), patch(
            "music_persistent_state.stamp_music_payload_for_write",
            side_effect=stamp,
        ), patch("suite_storage_config.cloud_storage_enabled", return_value=True), patch(
            "suite_storage_config.get_cloud_config", return_value=object()
        ), patch(
            "suite_cloud_state._import_storage",
            return_value=(suite_storage, "suite_storage"),
        ), patch("suite_cloud_state._cloud_storage_app_id", return_value="music"), patch.object(
            suite_storage, "save_current_state"
        ) as mock_upsert, patch("suite_cloud_state._streamlit_session", return_value=ss), patch(
            "suite_cloud_state.session_page_summary", return_value=("Creative", "page")
        ):
            yield mock_upsert

    def test_page_change_e2e_one_cloud_write(self) -> None:
        os.environ["MUSIC_EGRESS_STRICT"] = "1"
        ss = {"_music_workspace_blob_hydrated": True, _local_dirty_key("music"): True}
        st = MagicMock()
        st.session_state = ss

        def build_state(_st: object) -> dict:
            return {"core": {"studio_page": "Creative"}, "workspace_revision": 1}

        def stamp(_s: object, state: dict, **_kw: object) -> dict:
            out = dict(state)
            out["workspace_revision"] = 2
            return out

        with self._cloud_patches(ss, stamp) as mock_upsert:
            ok = force_autosave(st, "music", build_state=build_state, reason="page_change")

        self.assertTrue(ok)
        self.assertTrue(ss.get("_suite_persist_last_save_cloud"))
        mock_upsert.assert_called_once()
        tx = ss.get("_music_workspace_save_transaction", {})
        self.assertTrue(tx.get("strict_egress_user_write_allowed"))
        self.assertEqual(tx.get("strict_egress_plan_action"), "immediate")
        self.assertTrue(tx.get("strict_egress_approved"))
        self.assertTrue(tx.get("cloud_write_attempted"))
        self.assertTrue(tx.get("cloud_write_succeeded"))
        self.assertNotEqual(tx.get("force_save_block_reason"), "music_egress_strict")

        # End-of-run passive autosave must not overwrite intentional cloud success.
        autosave = music_autosave_if_changed(st, build_state=build_state)
        self.assertTrue(autosave.get("skipped"))
        self.assertTrue(ss.get("_suite_persist_last_save_cloud"))
        self.assertNotEqual(ss.get("_music_workspace_save_transaction", {}).get("force_save_block_reason"), "music_egress_strict")

    def test_passive_autosave_stays_blocked(self) -> None:
        os.environ["MUSIC_EGRESS_STRICT"] = "1"
        ss = {"_music_workspace_blob_hydrated": True, _local_dirty_key("music"): True}
        st = MagicMock()
        st.session_state = ss

        def build_state(_st: object) -> dict:
            return {"core": {"studio_page": "Practice"}, "workspace_revision": 5}

        autosave = music_autosave_if_changed(st, build_state=build_state)
        self.assertTrue(autosave.get("skipped"))
        self.assertEqual(autosave.get("skip_reason"), "music_egress_strict")
        self.assertFalse(ss.get("_suite_persist_last_save_cloud"))


if __name__ == "__main__":
    unittest.main()

"""CloudSaveResult failure stages for save_cloud_full_session."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from suite_cloud_state import CloudSaveResult, save_cloud_full_session


class CloudSaveResultTests(unittest.TestCase):
    def test_empty_state_failure_stage(self) -> None:
        with patch("suite_cloud_state._streamlit_session", return_value={}):
            result = save_cloud_full_session("music", {})
        self.assertFalse(result.success)
        self.assertEqual(result.failure_stage, "empty_state")

    def test_cloud_disabled_failure_stage(self) -> None:
        state = {"core": {}, "workspace_revision": 1}
        with patch("suite_cloud_state._streamlit_session", return_value={}), patch(
            "suite_storage_config.cloud_storage_enabled", return_value=False
        ):
            result = save_cloud_full_session("music", state)
        self.assertEqual(result.failure_stage, "cloud_storage_disabled")

    def test_success_sets_upsert_flags(self) -> None:
        mock_storage = MagicMock()
        mock_storage.normalize_app_key = lambda app: app
        mock_storage.ACTIVE_APP_KEYS = frozenset({"music"})
        state = {"core": {"pick_key": "x"}, "workspace_revision": 2}
        session: dict = {}
        with patch("suite_cloud_state._streamlit_session", return_value=session), patch(
            "suite_storage_config.cloud_storage_enabled", return_value=True
        ), patch("suite_storage_config.get_cloud_config", return_value=object()), patch(
            "suite_cloud_state._import_storage", return_value=(mock_storage, "suite_storage_supabase")
        ), patch("suite_cloud_state._cloud_storage_app_id", return_value="music__ariel"):
            mock_storage.ACTIVE_APP_KEYS = frozenset({"music"})
            result = save_cloud_full_session("music", state)
        self.assertTrue(result.success)
        self.assertTrue(result.cloud_upsert_succeeded)
        self.assertIn("save_cloud_full_session_return_value", session.get("_suite_last_cloud_save_result", {}))


if __name__ == "__main__":
    unittest.main()

"""Workspace isolation dev snapshot."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from workspace_isolation_diagnostics import build_workspace_isolation_snapshot


class TestWorkspaceIsolationDiagnostics(unittest.TestCase):
    def test_coakley_snapshot_flags_daniel_active_mismatch(self) -> None:
        class _FakeSt:
            session_state = {
                "_suite_auth_session": True,
                "_suite_auth_user_id": "uuid-coakley",
                "_suite_auth_user_email": "coakley11@aol.com",
                "_suite_auth_external_id": "coakley11",
                "_suite_active_workspace_id": "daniel",
                "_suite_owned_workspace_id": "coakley11",
            }

        st = _FakeSt()
        with patch("suite_auth.is_auth_enabled", return_value=True), patch(
            "suite_auth.is_authenticated", return_value=True
        ), patch("suite_auth.current_auth_email", return_value="coakley11@aol.com"), patch(
            "suite_auth.resolve_auth_external_id", return_value="coakley11"
        ), patch("suite_auth.allowed_workspaces_for_session", return_value=("coakley11",)), patch(
            "suite_workspace_registry.get_owned_workspace_id", return_value="coakley11"
        ), patch("suite_workspace.get_active_workspace_id", return_value="daniel"), patch(
            "suite_workspace.scoped_cloud_app_id", return_value="music__daniel"
        ), patch(
            "music_workspace_paths.music_data_path",
            return_value=__import__("pathlib").Path("data/workspaces/daniel/practice_history.json"),
        ), patch(
            "suite_user_persistence.state_file_path",
            return_value=__import__("pathlib").Path("data/workspaces/daniel/music_user_state.json"),
        ), patch("workspace_isolation_diagnostics._git_short", return_value="714655a"), patch(
            "workspace_isolation_diagnostics._secrets_auth_enabled", return_value=True
        ):
            snap = build_workspace_isolation_snapshot(st=st)

        self.assertEqual(snap["signed_in_email"], "coakley11@aol.com")
        self.assertEqual(snap["owned_workspace_id"], "coakley11")
        self.assertEqual(snap["active_workspace_id"], "daniel")
        self.assertTrue(snap["mismatch_active_vs_owned"])
        self.assertIn("daniel", snap["likely_root_cause"])


if __name__ == "__main__":
    unittest.main()

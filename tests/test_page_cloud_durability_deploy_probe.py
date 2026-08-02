"""Standalone page cloud durability deploy probe (?dev=1)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class TestPageCloudDurabilityDeployProbe(unittest.TestCase):
    def test_build_payload_imports_ok(self) -> None:
        from music_page_cloud_durability_deploy_probe import (
            PAGE_CLOUD_DURABILITY_DEPLOY_MARKER,
            build_deploy_probe_payload,
        )

        self.assertIn("PAGE_CLOUD_DURABILITY_DEPLOY:", PAGE_CLOUD_DURABILITY_DEPLOY_MARKER)
        payload = build_deploy_probe_payload()
        self.assertTrue(payload["durability_module_import"]["ok"])
        self.assertTrue(payload["journal_module_import"]["ok"])
        self.assertTrue(payload["journal_renderer_import"]["ok"])
        self.assertIn("deployed_commit", payload)
        self.assertIn("deployed_branch", payload)

    def test_render_skipped_when_not_dev(self) -> None:
        from music_page_cloud_durability_deploy_probe import render_page_cloud_durability_deploy_sidebar

        st = MagicMock()
        st.session_state = {}
        st.query_params = {}
        render_page_cloud_durability_deploy_sidebar(st)
        st.sidebar.markdown.assert_not_called()

    def test_suite_deploy_marker_resolves_local_git(self) -> None:
        from suite_deploy_marker import resolve_git_branch, resolve_git_commit_short

        commit = resolve_git_commit_short()
        branch = resolve_git_branch()
        self.assertNotEqual(commit, "")
        self.assertNotEqual(branch, "")


if __name__ == "__main__":
    unittest.main()

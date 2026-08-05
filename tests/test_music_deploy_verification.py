"""Deploy verification scans and preflight for Missions hotfix."""

from __future__ import annotations

import unittest

from music_deploy_verification import (
    REQUIRED_MISSIONS_HOTFIX_PREFIX,
    evaluate_deploy_preflight,
    scan_late_missions_activation_in_source,
)


class TestMusicDeployVerification(unittest.TestCase):
    def test_tab_missions_has_no_late_workflow_activation(self) -> None:
        scan = scan_late_missions_activation_in_source()
        self.assertFalse(
            scan.get("present"),
            msg=f"late missions activation findings: {scan.get('findings')}",
        )
        self.assertTrue(scan.get("pending_activation_module"))

    def test_artifact_freeze_has_no_session_display_key_write(self) -> None:
        from music_deploy_verification import scan_late_artifact_freeze_in_source

        scan = scan_late_artifact_freeze_in_source()
        self.assertFalse(scan.get("present"), msg=f"findings: {scan.get('findings')}")

    def test_emit_deploy_startup_log_format(self) -> None:
        from io import StringIO
        from unittest.mock import patch

        from music_deploy_verification import emit_deploy_startup_log

        buf = StringIO()
        with patch("sys.stdout", buf), patch("music_deploy_verification._PROCESS_DEPLOY_LOGGED", False):
            emit_deploy_startup_log(force=True)
        out = buf.getvalue()
        self.assertIn("[music_deploy]", out)
        self.assertIn("python=", out)
        self.assertIn("late_missions_activation=", out)
        self.assertIn("late_artifact_freeze=", out)

    def test_preflight_ok_on_current_tree(self) -> None:
        from music_deploy_verification import scan_late_artifact_freeze_in_source

        scan = scan_late_missions_activation_in_source()
        art = scan_late_artifact_freeze_in_source()
        pre = evaluate_deploy_preflight(scan=scan, artifact_scan=art)
        self.assertEqual(pre.get("status"), "OK")


if __name__ == "__main__":
    unittest.main()

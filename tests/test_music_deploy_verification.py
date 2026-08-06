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

    def test_creative_owner_preview_modules_present(self) -> None:
        from music_deploy_verification import scan_creative_owner_preview_modules_in_source

        scan = scan_creative_owner_preview_modules_in_source()
        self.assertFalse(scan.get("present"), msg=f"missing: {scan.get('missing')}")

    def test_preview_branch_accepts_bb151cd_functional_line(self) -> None:
        from music_deploy_verification import (
            CREATIVE_OWNER_PREVIEW_BRANCH,
            CREATIVE_OWNER_PREVIEW_FUNCTIONAL_SHA,
            matches_creative_owner_preview_deploy,
        )

        ident = {
            "branch": CREATIVE_OWNER_PREVIEW_BRANCH,
            "sha_short": CREATIVE_OWNER_PREVIEW_FUNCTIONAL_SHA[:12],
            "sha_full": CREATIVE_OWNER_PREVIEW_FUNCTIONAL_SHA,
        }
        self.assertTrue(matches_creative_owner_preview_deploy(ident))
        pre = evaluate_deploy_preflight(ident)
        self.assertEqual(pre.get("status"), "OK")
        self.assertTrue(pre.get("creative_owner_preview"))

    def test_dev_branch_does_not_use_preview_bypass(self) -> None:
        from music_deploy_verification import matches_creative_owner_preview_deploy

        ident = {"branch": "dev", "sha_short": "5049c171771b", "sha_full": "5049c171771b1ecd7d77643a1fa5c292a68a9e55"}
        self.assertFalse(matches_creative_owner_preview_deploy(ident))


if __name__ == "__main__":
    unittest.main()

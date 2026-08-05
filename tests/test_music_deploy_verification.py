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

    def test_preflight_ok_on_current_tree(self) -> None:
        scan = scan_late_missions_activation_in_source()
        pre = evaluate_deploy_preflight(scan=scan)
        # Local git HEAD may differ from Cloud; when sha matches required, must be OK.
        if str(pre.get("actual_sha") or "")[:7] == REQUIRED_MISSIONS_HOTFIX_PREFIX:
            self.assertEqual(pre.get("status"), "OK")
        else:
            self.assertIn("NOT_RUN", str(pre.get("status") or ""))


if __name__ == "__main__":
    unittest.main()

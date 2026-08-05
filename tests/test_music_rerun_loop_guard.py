"""Rerun loop guard — availability fail-safe."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from music_rerun_loop_guard import (
    RERUN_LOOP_BLOCKED_KEY,
    build_route_restore_fingerprint,
    safe_rerun,
    should_block_rerun,
)


class TestMusicRerunLoopGuard(unittest.TestCase):
    def test_blocks_after_identical_fingerprint_repeats(self) -> None:
        ss: dict = {"_script_run_seq": 5, "studio_page": "analysis", "_pending_upload_route_lock": True}
        fp = build_route_restore_fingerprint(ss, reason="hydration_wait")
        self.assertFalse(should_block_rerun(ss, reason="hydration_wait", fingerprint=fp))
        self.assertFalse(should_block_rerun(ss, reason="hydration_wait", fingerprint=fp))
        self.assertTrue(should_block_rerun(ss, reason="hydration_wait", fingerprint=fp))
        self.assertTrue(ss.get(RERUN_LOOP_BLOCKED_KEY))

    def test_safe_rerun_skips_when_blocked(self) -> None:
        ss: dict = {"_script_run_seq": 1}
        st = MagicMock()
        fp = build_route_restore_fingerprint(ss, reason="x")
        for _ in range(3):
            should_block_rerun(ss, reason="x", fingerprint=fp)
        safe_rerun(st, ss, reason="x", fingerprint=fp)
        st.rerun.assert_not_called()

    def test_fingerprint_changes_when_take_applied(self) -> None:
        ss: dict = {"studio_page": "practice"}
        a = build_route_restore_fingerprint(ss, reason="r")
        ss["_pending_upload_route_applied_take_id"] = "t1"
        b = build_route_restore_fingerprint(ss, reason="r")
        self.assertNotEqual(a, b)

    def test_different_reason_not_blocked_by_other_fingerprint_block(self) -> None:
        ss: dict = {"_script_run_seq": 1, "studio_page": "practice"}
        fp_a = build_route_restore_fingerprint(ss, reason="workspace_hydration_wait")
        for _ in range(3):
            should_block_rerun(ss, reason="workspace_hydration_wait", fingerprint=fp_a)
        self.assertTrue(should_block_rerun(ss, reason="workspace_hydration_wait", fingerprint=fp_a))
        fp_b = build_route_restore_fingerprint(ss, reason="chart_bundle_recovery")
        self.assertFalse(should_block_rerun(ss, reason="chart_bundle_recovery", fingerprint=fp_b))


if __name__ == "__main__":
    unittest.main()

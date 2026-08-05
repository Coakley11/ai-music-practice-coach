"""Second availability hotfix — lifecycle, fingerprint stability, chart exempt pages."""

from __future__ import annotations

import unittest

from music_rerun_loop_guard import build_route_restore_fingerprint, should_block_rerun
from music_run_lifecycle import (
    begin_script_run_lifecycle,
    complete_script_run_lifecycle,
)
from songs.chart_bundle_startup import (
    minimal_chart_bundle_stub,
    studio_page_exempt_from_chart_bundle,
)


class TestAvailabilityHotfix2(unittest.TestCase):
    def test_fingerprint_stable_when_hydration_attempts_increment(self) -> None:
        ss: dict = {
            "studio_page": "analysis",
            "_suite_persist_restore_applied": False,
            "_music_hydration_ui_wait_attempts": 0,
        }
        a = build_route_restore_fingerprint(ss, reason="workspace_hydration_wait")
        ss["_music_hydration_ui_wait_attempts"] = 2
        b = build_route_restore_fingerprint(ss, reason="workspace_hydration_wait")
        self.assertEqual(a, b)
        for _ in range(2):
            self.assertFalse(
                should_block_rerun(ss, reason="workspace_hydration_wait", fingerprint=a)
            )
        self.assertTrue(should_block_rerun(ss, reason="workspace_hydration_wait", fingerprint=a))

    def test_analysis_page_exempt_from_chart_bundle_gate(self) -> None:
        self.assertTrue(studio_page_exempt_from_chart_bundle("analysis"))
        self.assertFalse(studio_page_exempt_from_chart_bundle("practice"))
        stub = minimal_chart_bundle_stub(genre="Pop", song="Test", song_data={"key": "G"})
        self.assertEqual(stub["original_key"], "G")
        self.assertTrue(stub.get("chart_bundle_exempt"))

    def test_run_lifecycle_reaches_completed(self) -> None:
        ss: dict = {"_script_run_seq": 4, "studio_page": "practice"}
        begin_script_run_lifecycle(ss, st=None)
        complete_script_run_lifecycle(ss, st=None)
        lc = ss.get("_music_run_lifecycle") or {}
        self.assertEqual(lc.get("status"), "RUN_COMPLETED")


if __name__ == "__main__":
    unittest.main()

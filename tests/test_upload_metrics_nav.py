"""Navigation helpers for Upload ↔ Metrics & AI criteria flow."""

from __future__ import annotations

import unittest

from mission_analysis_ui import (
    ANALYSIS_CRITERIA_LOCKED,
    ANALYSIS_RETURN_TO_METRICS,
    open_upload_analysis_from_metrics,
    prepare_metrics_upload_workflow,
)


class MetricsUploadNavTests(unittest.TestCase):
    def test_prepare_metrics_locks_and_returns(self) -> None:
        session = {"improv_ai_metric_ids": ["phrase_structure", "tone"]}
        prepare_metrics_upload_workflow(session)
        self.assertTrue(session.get(ANALYSIS_CRITERIA_LOCKED))
        self.assertTrue(session.get(ANALYSIS_RETURN_TO_METRICS))
        self.assertEqual(session.get("analysis_ai_metric_ids"), ["phrase_structure", "tone"])
        self.assertEqual(session.get("analysis_effective_metric_ids"), ["phrase_structure", "tone"])

    def test_open_upload_from_metrics_preserves_prep(self) -> None:
        session = {
            "improv_ai_metric_ids": ["melodic_diversity_goal"],
            "_analysis_prepared_upload": object(),
            "last_analysis_result": {"ok": True, "coach_summary": "keep me"},
        }
        open_upload_analysis_from_metrics(session)
        self.assertTrue(session.get(ANALYSIS_CRITERIA_LOCKED))
        self.assertTrue(session.get(ANALYSIS_RETURN_TO_METRICS))
        self.assertIsNotNone(session.get("_analysis_prepared_upload"))
        self.assertEqual(session["last_analysis_result"]["coach_summary"], "keep me")
        self.assertTrue(session.get("analysis_return_preserve_recording"))


if __name__ == "__main__":
    unittest.main()

"""Regression: Practice Log → AMI handoff requires submit_practice_log_analysis_handoff."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class TestPracticeLogAmiHandoffExport(unittest.TestCase):
    def test_submit_practice_log_analysis_handoff_export_present(self) -> None:
        from suite_analytical_question import submit_practice_log_analysis_handoff

        self.assertTrue(callable(submit_practice_log_analysis_handoff))

    def test_command_center_handoff_calls_saq_submit(self) -> None:
        from practice_log_analysis_handoff import submit_practice_analysis_command_center_handoff

        session: dict = {"_suite_runtime_app_id": "music"}
        entries = [
            {
                "date": "2026-07-01",
                "minutes": 30,
                "song": "Autumn Leaves",
                "instrument": "Piano",
            }
        ]
        captured: dict = {}

        def _fake_submit(**kwargs):
            captured.update(kwargs)
            return {"handoff_success": True, "question_id": "q-test"}

        st = MagicMock()
        with patch(
            "suite_analytical_question.submit_practice_log_analysis_handoff",
            side_effect=_fake_submit,
        ), patch(
            "practice_history_synthesis.store_latest_practice_analysis"
        ), patch(
            "practice_log_ami.build_practice_log_ami_payload",
            return_value={
                "songs": ["Autumn Leaves"],
                "window_days": 14,
                "safety_checks": {
                    "raw_audio_excluded": True,
                    "base64_excluded": True,
                    "blob_fields_excluded": True,
                },
            },
        ), patch(
            "practice_log_state.load_entries",
            return_value=entries,
        ), patch(
            "music_coach_context.build_source_state",
            return_value={"source_app": "music"},
        ):
            result = submit_practice_analysis_command_center_handoff(
                st,
                session,
                entries=entries,
                window_days=14,
            )

        self.assertEqual(captured.get("source_page"), "log")
        self.assertTrue(result.get("handoff_success"))


if __name__ == "__main__":
    unittest.main()

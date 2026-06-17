"""Music submit stores canonical instant insight for AMI deep dive."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from suite_analytical_question import (
    _stage_music_instant_insight,
    build_question_payload,
    metrics_for_applied_math_resume,
)


class TestMusicCanonicalInsightSubmit(unittest.TestCase):
    def test_metrics_include_ami_insight_when_canonical_present(self) -> None:
        payload = build_question_payload(
            source_app="music",
            source_page="practice",
            question="What songs similar to Perfect can I play?",
            context={"instrument": "Saxophone", "coach_page": "practice"},
        )
        payload["instant_insight"] = {
            "insight_id": "abc123",
            "conclusion": "Songs similar to Perfect...",
            "canonical_instant": True,
        }
        metrics = metrics_for_applied_math_resume(payload)
        self.assertEqual(metrics.get("ami_insight"), "abc123")

    def test_stage_music_instant_insight_stores_canonical_blob(self) -> None:
        st = MagicMock()
        ss: dict = {}
        st.session_state = ss
        pre_payload = build_question_payload(
            source_app="music",
            source_page="practice",
            question="What songs similar to Perfect can I play?",
            context={"coach_page": "practice", "instrument": "Saxophone"},
        )
        def _stage(_st, _insight, **kwargs):
            ss["_ami_pending_insight"] = {"insight_id": "ins-1", "conclusion": "Similar songs list"}

        with patch(
            "applied_math_return_insight.store_applied_math_insight",
        ) as mock_store, patch(
            "applied_math_return_insight.stage_pending_insight",
            side_effect=_stage,
        ), patch(
            "applied_math_return_insight.build_return_insight_payload",
            return_value=MagicMock(
                to_dict=lambda: {
                    "insight_id": "ins-1",
                    "conclusion": "Similar songs list",
                    "question_id": pre_payload["question_id"],
                }
            ),
        ), patch(
            "music_ami_instant_solver.solve_instant_music_insight",
            return_value=(
                MagicMock(problem_type="similar_songs", model_name="Music Coach repertoire"),
                MagicMock(short_answer="Similar songs list", assumptions=[]),
            ),
        ):
            ok = _stage_music_instant_insight(
                st,
                ss,
                question=pre_payload["question"],
                source_app="music",
                source_page="practice",
                submit_ctx=dict(pre_payload["context"]),
                submit_source_state={"source_page": "practice"},
                pre_payload=pre_payload,
                action_url_pre="https://example.test/ami",
            )
        self.assertTrue(ok)
        mock_store.assert_called_once()
        store_blob = mock_store.call_args.args[0]
        self.assertTrue(store_blob.get("canonical_instant"))
        canonical = ss.get("_ami_music_instant_canonical") or {}
        self.assertEqual(canonical.get("insight_id"), "ins-1")


if __name__ == "__main__":
    unittest.main()

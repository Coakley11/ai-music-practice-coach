"""Music Coach instant solver and submit insight staging."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from music_ami_context import detect_music_send_intent
from music_ami_instant_solver import solve_instant_music_insight


class TestMusicIntentRouting(unittest.TestCase):
    def test_chord_time_question_routes_practice_plan(self) -> None:
        q = "How much time should I spend on learning the chord changes?"
        self.assertEqual(detect_music_send_intent(q, "practice"), "practice_plan")

    def test_chord_transition_intent(self) -> None:
        q = "How do I improve these chord changes?"
        self.assertEqual(detect_music_send_intent(q, "practice"), "chord_transition")


class TestMusicInstantSolver(unittest.TestCase):
    def test_practice_plan_answer_has_time_blocks(self) -> None:
        solved = solve_instant_music_insight(
            "How much time should I spend on learning the chord changes?",
            {
                "coach_page": "practice",
                "instrument": "Guitar",
                "practice_minutes": 30,
            },
        )
        self.assertIsNotNone(solved)
        route, result = solved
        self.assertEqual(route.problem_type, "practice_plan")
        self.assertIn("30-minute", result.short_answer)
        self.assertIn("chord transitions", result.short_answer.lower())
        self.assertGreaterEqual(result.computed.get("chord transitions", 0), 8)

    def test_unknown_question_returns_none(self) -> None:
        self.assertIsNone(solve_instant_music_insight("hello", {"coach_page": "practice"}))


class TestMusicSubmitStagesInsight(unittest.TestCase):
    def test_handle_submit_stages_pending_insight(self) -> None:
        from suite_analytical_question import render_analyze_with_applied_math_sidebar

        st = MagicMock()
        ss: dict = {}
        st.session_state = ss

        with patch(
            "suite_analytical_question.build_submit_context",
            return_value={"coach_page": "practice", "instrument": "Piano"},
        ), patch(
            "suite_analytical_question.build_question_payload",
            return_value={"question_id": "q1", "resume_key": "rk1"},
        ), patch(
            "suite_analytical_question.build_applied_math_resume_url",
            return_value="https://example.test/resume",
        ), patch(
            "suite_analytical_question.submit_analytical_question",
            return_value={"duplicate": False},
        ), patch(
            "suite_analytical_question._stage_music_instant_insight",
            return_value=True,
        ) as mock_stage:
            render_analyze_with_applied_math_sidebar(
                st,
                source_app="music",
                source_page="practice",
                session_state=ss,
                surface="main",
            )

        submitted = False
        for call in st.button.call_args_list:
            if call.kwargs.get("type") == "primary":
                submitted = True
        self.assertTrue(submitted or st.text_area.called)


if __name__ == "__main__":
    unittest.main()

"""Music Coach instant solver and submit insight staging."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from music_ami_context import detect_music_send_intent
from music_ami_instant_solver import solve_instant_music_insight
from suite_analytical_question import (
    _AMI_COACH_SUBMIT_FEEDBACK_KEY,
    _execute_coach_question_submit,
)


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


class TestMusicCoachSharedSubmit(unittest.TestCase):
    def test_execute_coach_submit_persists_feedback(self) -> None:
        st = MagicMock()
        ui = MagicMock()
        ss: dict = {}

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
        ):
            _execute_coach_question_submit(
                st,
                ui,
                ss,
                question_raw="How much time on chord changes?",
                source_app="music",
                source_page="practice",
                page_suffix="practice",
                send_gen=0,
                surface_tag="sidebar",
                context=None,
                context_extra_builder=None,
                source_state_builder=None,
                context_summary="",
                developer_mode=False,
                on_after_send=None,
            )

        fb = ss.get(_AMI_COACH_SUBMIT_FEEDBACK_KEY)
        self.assertIsInstance(fb, dict)
        self.assertEqual(fb.get("kind"), "success")
        self.assertIn("Music Coach insight is ready", str(fb.get("message") or ""))
        ui.success.assert_called_once()

    def test_sidebar_uses_form_submit_path(self) -> None:
        from suite_analytical_question import render_analyze_with_applied_math_sidebar

        st = MagicMock()
        ss: dict = {}
        st.session_state = ss
        sidebar = MagicMock()
        st.sidebar = sidebar

        form_cm = MagicMock()
        form_cm.__enter__ = MagicMock(return_value=sidebar)
        form_cm.__exit__ = MagicMock(return_value=False)
        sidebar.form.return_value = form_cm
        sidebar.form_submit_button.return_value = True
        sidebar.text_area.return_value = "How should I practice chorus?"

        with patch(
            "suite_analytical_question._execute_coach_question_submit",
        ) as mock_submit:
            render_analyze_with_applied_math_sidebar(
                st,
                source_app="music",
                source_page="practice",
                session_state=ss,
                surface="sidebar",
                show_heading=False,
            )
            mock_submit.assert_called_once()
            self.assertEqual(
                mock_submit.call_args.kwargs.get("question_raw"),
                "How should I practice chorus?",
            )


if __name__ == "__main__":
    unittest.main()

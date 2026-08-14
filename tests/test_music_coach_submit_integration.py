"""Music Coach UI submit → routed AMI pipeline integration."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from applied_math_return_insight import SESSION_PENDING_KEY
from suite_analytical_question import (
    MUSIC_COACH_SUBMIT_DIAG_KEY,
    _AMI_COACH_SUBMIT_FEEDBACK_KEY,
    _execute_coach_question_submit,
)


class MusicCoachSubmitIntegrationTests(unittest.TestCase):
    def test_routed_submit_stages_insight_without_command_center(self) -> None:
        st = MagicMock()
        st.session_state = {}
        ui = MagicMock()
        ss: dict = st.session_state

        with patch(
            "suite_analytical_question.submit_analytical_question",
        ) as mock_cc, patch(
            "applied_math_return_insight.store_applied_math_insight",
            return_value="ins-routed",
        ), patch(
            "applied_math_return_insight.stage_pending_insight",
        ):
            out = _execute_coach_question_submit(
                    st,
                    ui,
                    ss,
                    question_raw="Where do I log my practice?",
                    source_app="music",
                    source_page="practice",
                    page_suffix="practice",
                    send_gen=0,
                    surface_tag="sidebar",
                    context={"coach_page": "practice", "instrument": "Flute"},
                    context_extra_builder=None,
                    source_state_builder=lambda: {"source_page": "practice"},
                    developer_mode=True,
                )

        mock_cc.assert_not_called()
        self.assertIsNotNone(out)
        assert out is not None
        self.assertTrue(out.get("routed"))
        diag = ss.get(MUSIC_COACH_SUBMIT_DIAG_KEY)
        self.assertIsInstance(diag, dict)
        assert isinstance(diag, dict)
        self.assertEqual(diag.get("result_path"), "routed_coach")
        self.assertEqual(diag.get("coach_intent"), "app_navigation")
        self.assertEqual(diag.get("solver"), "AppNavigationSolver")
        fb = ss.get(_AMI_COACH_SUBMIT_FEEDBACK_KEY)
        self.assertEqual(fb.get("result_path"), "routed_coach")

    def test_unsupported_question_falls_back_to_command_center(self) -> None:
        st = MagicMock()
        ui = MagicMock()
        ss: dict = {}

        with patch(
            "suite_analytical_question.submit_analytical_question",
            return_value={"duplicate": False, "question_id": "q-fallback"},
        ) as mock_cc:
            _execute_coach_question_submit(
                st,
                ui,
                ss,
                question_raw="hello there friend",
                source_app="music",
                source_page="practice",
                page_suffix="practice",
                send_gen=0,
                context={"coach_page": "practice"},
            )

        mock_cc.assert_called_once()
        diag = ss.get(MUSIC_COACH_SUBMIT_DIAG_KEY)
        self.assertIsInstance(diag, dict)
        assert isinstance(diag, dict)
        self.assertEqual(diag.get("result_path"), "legacy_fallback")
        self.assertFalse(str(diag.get("solver") or ""))

    def test_practice_plan_submit_exposes_solver_class(self) -> None:
        st = MagicMock()
        ui = MagicMock()
        ss: dict = {"instrument": "Flute", "level": "Beginner"}

        with patch("suite_analytical_question.submit_analytical_question"), patch(
            "applied_math_return_insight.store_applied_math_insight",
            return_value="ins-1",
        ), patch(
            "applied_math_return_insight.stage_pending_insight",
        ):
            _execute_coach_question_submit(
                st,
                ui,
                ss,
                question_raw="Give me a 30-minute flute practice plan focused on tone.",
                source_app="music",
                source_page="practice",
                page_suffix="practice",
                send_gen=0,
                context={"coach_page": "practice", "instrument": "Flute"},
            )

        diag = ss[MUSIC_COACH_SUBMIT_DIAG_KEY]
        self.assertEqual(diag["coach_intent"], "practice_plan")
        self.assertEqual(diag["solver"], "PracticePlanSolver")
        self.assertEqual(diag["result_path"], "routed_coach")

    def test_routed_submit_does_not_wipe_display_key(self) -> None:
        st = MagicMock()
        st.session_state = {"display_key": "Eb", "instrument": "Flute", "studio_page": "creative"}
        ui = MagicMock()
        ss = st.session_state
        before = dict(ss)

        with patch("suite_analytical_question.submit_analytical_question"), patch(
            "applied_math_return_insight.store_applied_math_insight",
            return_value="ins-2",
        ), patch(
            "applied_math_return_insight.stage_pending_insight",
        ):
            _execute_coach_question_submit(
                st,
                ui,
                ss,
                question_raw="What are Missions in Creative?",
                source_app="music",
                source_page="practice",
                page_suffix="practice",
                send_gen=0,
                context={"coach_page": "practice"},
            )

        self.assertEqual(ss.get("display_key"), before.get("display_key"))
        self.assertEqual(ss.get("studio_page"), before.get("studio_page"))
        pending = ss.get(SESSION_PENDING_KEY)
        self.assertIsInstance(pending, dict)


if __name__ == "__main__":
    unittest.main()

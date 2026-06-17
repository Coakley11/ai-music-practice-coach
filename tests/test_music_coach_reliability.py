"""Music Coach AMI reliability — render scope, routing regressions, deploy marker."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from applied_math_return_insight import (
    SESSION_PENDING_KEY,
    insight_page_scope_decision,
    render_suite_applied_math_insight_for_page,
)
from music_ami_context import detect_music_send_intent
from music_ami_instant_solver import MUSIC_AMI_BUILD_ID, solve_instant_music_insight

TRANSPOSE_QUESTION = (
    "If I want to play this song in F instead of E on Alto sax, what notes would I use?"
)
SIMILAR_SONGS_QUESTION = "What songs can I practice that are similar to Perfect?"
PRACTICE_PLAN_QUESTION = "I have 15 minutes to practice this song. What should I do?"


class TestMusicRoutingRegressions(unittest.TestCase):
    def test_transposition_exact_cloud_question(self) -> None:
        self.assertEqual(detect_music_send_intent(TRANSPOSE_QUESTION, "practice"), "music_transposition")

    def test_similar_songs_exact_cloud_question(self) -> None:
        self.assertEqual(detect_music_send_intent(SIMILAR_SONGS_QUESTION, "practice"), "similar_songs")

    def test_transposition_solver_not_practice_plan(self) -> None:
        solved = solve_instant_music_insight(
            TRANSPOSE_QUESTION,
            {"coach_page": "practice", "instrument": "Alto Sax"},
        )
        self.assertIsNotNone(solved)
        route, result = solved
        self.assertEqual(route.problem_type, "music_transposition")
        self.assertIn("Alto sax", result.short_answer)
        self.assertNotIn("practice split", result.short_answer.lower())
        self.assertNotIn("Piano", result.short_answer)

    def test_similar_songs_solver_not_practice_plan(self) -> None:
        solved = solve_instant_music_insight(
            SIMILAR_SONGS_QUESTION,
            {"coach_page": "practice", "instrument": "Alto Sax", "level": "Intermediate"},
        )
        self.assertIsNotNone(solved)
        route, result = solved
        self.assertEqual(route.problem_type, "similar_songs")
        self.assertIn("Thinking Out Loud", result.short_answer)
        self.assertNotIn("practice split", result.short_answer.lower())

    def test_practice_plan_still_works(self) -> None:
        self.assertEqual(detect_music_send_intent(PRACTICE_PLAN_QUESTION, "practice"), "practice_plan")
        solved = solve_instant_music_insight(
            PRACTICE_PLAN_QUESTION,
            {"coach_page": "practice", "instrument": "Alto Sax"},
        )
        self.assertIsNotNone(solved)
        _, result = solved
        self.assertIn("15-minute", result.short_answer)

    def test_solver_build_id_present(self) -> None:
        self.assertIn("music-ami", MUSIC_AMI_BUILD_ID)


class TestMusicInsightScope(unittest.TestCase):
    def test_insight_renders_on_submit_studio_page_not_coach_alias(self) -> None:
        insight = {
            "source_app": "music",
            "source_page": "picker",
            "conclusion": "Try a slower tempo.",
            "return_context": {
                "widget_params": {"studio_page": "picker"},
            },
        }
        scope = insight_page_scope_decision("music", "picker", insight)
        self.assertTrue(scope.get("should_render_insight_on_page"))

    def test_force_render_after_main_panel_submit(self) -> None:
        st = MagicMock()
        st.session_state = {
            SESSION_PENDING_KEY: {
                "source_app": "music",
                "source_page": "practice",
                "conclusion": "6 min chord transitions.",
                "question": PRACTICE_PLAN_QUESTION,
                "return_context": {"widget_params": {"studio_page": "practice"}},
            },
            "_ami_force_insight_render": True,
            "_ami_submit_render_insight_this_run": True,
            "_ami_last_submit_source_page": "practice",
            "studio_page": "practice",
        }
        with patch("applied_math_return_insight.render_applied_math_insight_panel", return_value=True):
            ok = render_suite_applied_math_insight_for_page(
                st,
                source_app="music",
                source_page="practice",
            )
        self.assertTrue(ok)
        self.assertTrue(st.session_state.get("_ami_insight_card_rendered"))


if __name__ == "__main__":
    unittest.main()

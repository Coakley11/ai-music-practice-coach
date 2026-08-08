"""Music Coach submit UX: same-page insight, Unicode tonics, page scope."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from applied_math_return_insight import (
    SESSION_PENDING_KEY,
    insight_page_scope_decision,
)
from music_coach_ami.entities import normalize_musical_accidentals, normalize_question
from music_coach_ami.pipeline import run_coach_submit
from music_coach_ami.router import CoachIntent, route_question
from music_coach_ami.scale_engine import parse_scale_practice_question
from suite_analytical_question import (
    MUSIC_COACH_SUBMIT_DIAG_KEY,
    _AMI_COACH_SUBMIT_FEEDBACK_KEY,
    _execute_coach_question_submit,
    _recent_duplicate_send,
    utc_now_iso,
)


class UnicodeAccidentalTests(unittest.TestCase):
    def test_normalize_flat_and_sharp(self) -> None:
        self.assertIn("Eb", normalize_question("Show me the E♭ major scale"))
        self.assertIn("C#", normalize_musical_accidentals("C♯ major"))

    def test_e_flat_unicode_parses_same_tonic_as_eb(self) -> None:
        u = parse_scale_practice_question("Show me the E♭ major scale in sheet music.")
        a = parse_scale_practice_question("Show me the Eb major scale in sheet music.")
        self.assertEqual(u.tonic, "Eb")
        self.assertEqual(a.tonic, "Eb")
        self.assertEqual(u.preferred_spelling, "E♭")
        self.assertEqual(a.preferred_spelling, "Eb")

    def test_unicode_routes_scale_practice(self) -> None:
        req = route_question("Show me the E♭ major scale in sheet music.", {})
        self.assertEqual(req.intent, CoachIntent.SCALE_PRACTICE)


class MusicInsightPageScopeTests(unittest.TestCase):
    def test_creative_studio_matches_custom_coach_insight(self) -> None:
        insight = {
            "source_app": "music",
            "source_page": "custom",
            "conclusion": "Eb major scale",
            "canonical_instant": True,
        }
        scope = insight_page_scope_decision("music", "creative", insight)
        self.assertTrue(scope.get("should_render_insight_on_page"))


class ScaleSubmitIntegrationTests(unittest.TestCase):
    def test_first_submit_stages_scale_with_notation(self) -> None:
        st = MagicMock()
        st.session_state = {}
        ui = MagicMock()
        ss: dict = st.session_state
        q = "Show me the E♭ major scale in sheet music."

        with patch("suite_analytical_question.submit_analytical_question") as mock_cc, patch(
            "applied_math_return_insight.store_applied_math_insight",
            return_value="ins-scale",
        ), patch(
            "applied_math_return_insight.stage_pending_insight",
        ):
            out = _execute_coach_question_submit(
                st,
                ui,
                ss,
                question_raw=q,
                source_app="music",
                source_page="practice",
                page_suffix="practice",
                send_gen=0,
            )

        mock_cc.assert_not_called()
        assert out is not None
        self.assertTrue(out.get("routed"))
        pending = ss.get(SESSION_PENDING_KEY)
        self.assertIsInstance(pending, dict)
        assert isinstance(pending, dict)
        self.assertTrue(pending.get("notation_abc"))
        self.assertTrue(ss.get("_ami_submit_render_insight_this_run"))
        diag = ss[MUSIC_COACH_SUBMIT_DIAG_KEY]
        self.assertEqual(diag["coach_intent"], "scale_practice")
        self.assertEqual(diag["solver"], "ScalePracticeSolver")
        self.assertEqual(diag["tonic"], "Eb")
        self.assertEqual(diag["preferred_spelling"], "E♭")
        self.assertTrue(diag["notation_abc_present"])
        self.assertTrue(diag["insight_staged"])
        fb = ss[_AMI_COACH_SUBMIT_FEEDBACK_KEY]
        self.assertEqual(fb["result_path"], "routed_coach")
        self.assertIn("below", fb["message"].lower())
        last = ss.get("_ami_last_send")
        self.assertEqual(last.get("result_path"), "routed_coach")

    def test_duplicate_routed_rearms_render(self) -> None:
        st = MagicMock()
        ui = MagicMock()
        ss: dict = {
            SESSION_PENDING_KEY: {
                "conclusion": "scale answer",
                "canonical_instant": True,
                "source_page": "practice",
            },
            "_ami_last_send": {
                "question_id": "same-id",
                "source_app": "music",
                "submitted_at": utc_now_iso(),
                "result_path": "routed_coach",
            },
        }
        st.session_state = ss

        with patch(
            "suite_analytical_question.build_question_payload",
            return_value={"question_id": "same-id"},
        ), patch(
            "suite_analytical_question._recent_duplicate_send",
            return_value=True,
        ):
            out = _execute_coach_question_submit(
                st,
                ui,
                ss,
                question_raw="Show me the E♭ major scale in sheet music.",
                source_app="music",
                source_page="practice",
                page_suffix="practice",
                send_gen=0,
            )

        assert out is not None
        self.assertTrue(out.get("duplicate"))
        self.assertTrue(out.get("routed"))
        self.assertTrue(ss.get("_ami_submit_render_insight_this_run"))
        st.rerun.assert_called_once()

    def test_pipeline_scale_no_legacy(self) -> None:
        req, resp = run_coach_submit(
            "Show me the E♭ major scale in sheet music.",
            {},
            ami_ctx={"coach_page": "practice"},
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertEqual(req.intent, CoachIntent.SCALE_PRACTICE)
        self.assertTrue(resp.notation_abc)


if __name__ == "__main__":
    unittest.main()

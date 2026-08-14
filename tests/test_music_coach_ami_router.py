"""AMI Music Coach router and pipeline tests."""

from __future__ import annotations

import unittest

from music_coach_ami.pipeline import run_coach_pipeline
from music_coach_ami.router import CoachIntent, route_question
from music_coach_ami.types import CoachContext
from music_ami_instant_solver import solve_instant_music_insight


class CoachRouterTests(unittest.TestCase):
    def test_practice_plan_routing(self) -> None:
        req = route_question("Give me a 30-minute practice routine", {})
        self.assertEqual(req.intent, CoachIntent.PRACTICE_PLAN)

    def test_technique_routing(self) -> None:
        req = route_question("My flute tone sounds airy", {})
        self.assertEqual(req.intent, CoachIntent.TECHNIQUE_PROBLEM)
        self.assertEqual(req.entities.instrument, "Flute")

    def test_app_navigation_routing(self) -> None:
        req = route_question("Where do I log my practice?", {})
        self.assertEqual(req.intent, CoachIntent.APP_NAVIGATION)
        self.assertEqual(req.entities.feature_id, "practice_log")

    def test_creative_help_routing(self) -> None:
        req = route_question("What are Missions in Creative?", {})
        self.assertEqual(req.intent, CoachIntent.CREATIVE_FEATURE_HELP)

    def test_improvisation_routing(self) -> None:
        req = route_question("How do I improvise?", {})
        self.assertEqual(req.intent, CoachIntent.IMPROVISATION_COACHING)

    def test_theory_routing(self) -> None:
        req = route_question("What is a ii-V-I?", {})
        self.assertEqual(req.intent, CoachIntent.THEORY_EXPLANATION)

    def test_repertoire_routing(self) -> None:
        req = route_question("What songs should I practice for learning improvisation?", {})
        self.assertEqual(req.intent, CoachIntent.REPERTOIRE_RECOMMENDATION)

    def test_app_question_not_theory(self) -> None:
        req = route_question("Where do I log practice?", {})
        self.assertNotEqual(req.intent, CoachIntent.THEORY_EXPLANATION)

    def test_duration_extracted(self) -> None:
        req = route_question("Give me a 30-minute flute practice plan focused on tone.", {})
        self.assertEqual(req.constraints.requested_duration_minutes, 30)


class CoachPipelineTests(unittest.TestCase):
    def test_technique_answer_measurable(self) -> None:
        resp = run_coach_pipeline("My flute tone sounds airy. What should I practice?", {})
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertEqual(resp.intent, CoachIntent.TECHNIQUE_PROBLEM)
        text = resp.composed_markdown()
        self.assertIn("8 seconds", text)
        self.assertIn("listen", text.lower())

    def test_practice_plan_honors_minutes(self) -> None:
        resp = run_coach_pipeline(
            "Give me a 30-minute flute practice plan focused on tone.",
            {},
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertIn("30", resp.composed_markdown())

    def test_instant_solver_uses_pipeline(self) -> None:
        solved = solve_instant_music_insight(
            "Where do I log my practice?",
            {"coach_page": "practice"},
        )
        self.assertIsNotNone(solved)
        route, result = solved
        self.assertEqual(route.problem_type, "app_navigation")
        self.assertIn("Practice Log", result.short_answer)

    def test_coach_does_not_mutate_session(self) -> None:
        session = {"display_key": "Dm", "instrument": "Flute", "studio_page": "practice"}
        before = {k: session[k] for k in ("display_key", "instrument", "studio_page")}
        run_coach_pipeline("What should I practice today?", session)
        # Musical state must stay read-only. Newer `dev` may lazy-init diagnostic
        # stores (`_music_workflow_state_store`, `_display_key_surface_trace`) on read.
        self.assertEqual(
            {k: session[k] for k in ("display_key", "instrument", "studio_page")},
            before,
        )


class CoachContextReaderTests(unittest.TestCase):
    def test_read_only_context_fields(self) -> None:
        from music_coach_ami.context_reader import read_coach_context

        ctx = read_coach_context(
            {
                "instrument": "Flute",
                "level": "Beginner",
                "focus": "Tone",
                "studio_page": "creative",
                "improv_intelligence_tab": "Missions",
                "display_key": "Eb",
            }
        )
        self.assertIsInstance(ctx, CoachContext)
        self.assertEqual(ctx.instrument, "Flute")
        self.assertEqual(ctx.creative_tab, "Missions")


if __name__ == "__main__":
    unittest.main()

"""App navigation and workflow coaching tests."""

from __future__ import annotations

import unittest

from music_coach_ami.app_knowledge import FEATURES, feature_by_question
from music_coach_ami.pipeline import run_coach_pipeline
from music_coach_ami.router import CoachIntent, route_question
from music_coach_ami.types import CoachContext


class AppWorkflowRouterTests(unittest.TestCase):
    def test_log_practice_navigation(self) -> None:
        req = route_question("How do I log my practice?", {})
        self.assertEqual(req.intent, CoachIntent.APP_NAVIGATION)

    def test_improv_on_song_not_navigation(self) -> None:
        req = route_question("How can I practice improvising on this song?", {})
        self.assertEqual(req.intent, CoachIntent.IMPROVISATION_COACHING)

    def test_repertoire_types(self) -> None:
        req = route_question("What kind of songs should I practice?", {})
        self.assertEqual(req.intent, CoachIntent.REPERTOIRE_RECOMMENDATION)

    def test_scale_help_recommendation(self) -> None:
        req = route_question(
            "What part of the app can I find scale help and chord theory?", {}
        )
        self.assertEqual(req.intent, CoachIntent.APP_FEATURE_RECOMMENDATION)

    def test_harmony_map_explanation(self) -> None:
        req = route_question("What is Harmony Map for?", {})
        self.assertEqual(req.intent, CoachIntent.FEATURE_EXPLANATION)

    def test_motif_theory_vs_coaching(self) -> None:
        self.assertEqual(route_question("What is a motif?", {}).intent, CoachIntent.THEORY_EXPLANATION)
        self.assertEqual(
            route_question("How should I practice developing a motif?", {}).intent,
            CoachIntent.IMPROVISATION_COACHING,
        )


class AppKnowledgeTests(unittest.TestCase):
    def test_practice_log_has_navigation_path(self) -> None:
        feat = FEATURES["practice_log"]
        self.assertIn("Practice Log", feat.navigation_path)

    def test_no_hallucinated_settings_path(self) -> None:
        joined = " ".join(f.navigation_path for f in FEATURES.values())
        self.assertNotIn("Settings >", joined)


class VerticalSliceTests(unittest.TestCase):
    def test_a_log_practice(self) -> None:
        resp = run_coach_pipeline("How do I log my practice?", {})
        assert resp is not None
        text = resp.composed_markdown()
        self.assertIn("Practice Log", text)
        self.assertNotIn("notebook", text.lower())

    def test_b_improv_with_song_context(self) -> None:
        ctx = {
            "active_song": {"title": "Autumn Leaves"},
            "practice_focus_section": "Head",
            "ii_selected_chord": "Am7",
        }
        resp = run_coach_pipeline(
            "How can I practice improvising on this song?",
            ctx,
            ami_ctx={"active_song": {"title": "Autumn Leaves"}, "practice_focus_section": "Head"},
        )
        assert resp is not None
        text = resp.composed_markdown()
        self.assertIn("Autumn Leaves", text)

    def test_b_improv_without_song_no_invented_title(self) -> None:
        resp = run_coach_pipeline("How can I practice improvising on this song?", {})
        assert resp is not None
        text = resp.composed_markdown()
        self.assertNotIn("Autumn Leaves", text)

    def test_c_repertoire_fallback_types(self) -> None:
        resp = run_coach_pipeline("What kind of songs should I practice?", {})
        assert resp is not None
        self.assertEqual(resp.intent, CoachIntent.REPERTOIRE_RECOMMENDATION)

    def test_d_scale_and_chord_destinations(self) -> None:
        resp = run_coach_pipeline(
            "What part of the app can I find scale help and chord theory?", {}
        )
        assert resp is not None
        text = resp.composed_markdown()
        self.assertIn("Music Coach", text)
        self.assertIn("Harmony Map", text)


if __name__ == "__main__":
    unittest.main()

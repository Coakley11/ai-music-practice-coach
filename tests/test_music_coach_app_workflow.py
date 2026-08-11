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
        self.assertNotIn("when when", text.lower())
        self.assertNotIn("**Where to go:**", text)
        self.assertIn("**Use:**", text)
        self.assertIn("Quick Save", text)

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
        self.assertIn("strong beats", text.lower())
        self.assertNotIn("beats 1 and 3", text.lower())
        self.assertIn("Backing Track Studio", text)
        self.assertNotIn("Jam Session Generator** in the same key", text)

    def test_b_improv_without_song_no_invented_title(self) -> None:
        resp = run_coach_pipeline("How can I practice improvising on this song?", {})
        assert resp is not None
        text = resp.composed_markdown()
        self.assertNotIn("Autumn Leaves", text)

    def test_b_improv_exact_progression_context(self) -> None:
        ctx = {
            "active_song": {
                "title": "Say",
                "progression_summary": "C–G–Am–F",
            },
            "practice_focus_section": "Chorus",
            "display_key": "G",
        }
        resp = run_coach_pipeline(
            "How can I practice improvising on this song?",
            ctx,
            ami_ctx=ctx,
        )
        assert resp is not None
        text = resp.composed_markdown()
        self.assertIn("Say", text)
        self.assertIn("C–G–Am–F", text)

    def test_c_repertoire_broad_not_similar_header(self) -> None:
        resp = run_coach_pipeline("What kind of songs should I practice?", {})
        assert resp is not None
        text = resp.composed_markdown()
        self.assertIn("Comfort piece", text)
        self.assertNotIn("Songs similar to", text)

    def test_c_repertoire_singular_song(self) -> None:
        resp = run_coach_pipeline("What song should I practice to improve improvisation?", {})
        assert resp is not None
        text = resp.composed_markdown()
        self.assertIn("Best choice", text)
        self.assertNotIn("on **Piano**", text)

    def test_d_scale_and_chord_destinations(self) -> None:
        resp = run_coach_pipeline(
            "What part of the app can I find scale help and chord theory?", {}
        )
        assert resp is not None
        text = resp.composed_markdown()
        self.assertIn("Music Coach", text)
        self.assertIn("Harmony Map", text)


class ExpandedRoutingTests(unittest.TestCase):
    def test_where_practice_log(self) -> None:
        self.assertEqual(route_question("Where is Practice Log?", {}).intent, CoachIntent.APP_NAVIGATION)

    def test_record_myself_navigation(self) -> None:
        self.assertEqual(route_question("Where can I record myself?", {}).intent, CoachIntent.APP_NAVIGATION)

    def test_analyze_recording_navigation(self) -> None:
        self.assertEqual(route_question("How do I analyze a recording?", {}).intent, CoachIntent.APP_NAVIGATION)

    def test_harmony_map_do(self) -> None:
        self.assertEqual(route_question("What does Harmony Map do?", {}).intent, CoachIntent.FEATURE_EXPLANATION)

    def test_backing_vs_jam(self) -> None:
        self.assertEqual(
            route_question("What's the difference between Backing and Jam Session Generator?", {}).intent,
            CoachIntent.FEATURE_EXPLANATION,
        )

    def test_missions_vs_live_coach(self) -> None:
        self.assertEqual(
            route_question("Should I use Missions or Live Coach?", {}).intent,
            CoachIntent.FEATURE_EXPLANATION,
        )

    def test_phrasing_recommendation(self) -> None:
        self.assertEqual(
            route_question("I want to improve my phrasing. What should I use?", {}).intent,
            CoachIntent.APP_FEATURE_RECOMMENDATION,
        )

    def test_timing_recommendation(self) -> None:
        self.assertEqual(
            route_question("I want to improve my timing. What should I use?", {}).intent,
            CoachIntent.APP_FEATURE_RECOMMENDATION,
        )

    def test_what_to_practice_today(self) -> None:
        req = route_question("What feature should I use if I don't know what to practice today?", {})
        self.assertIn(
            req.intent,
            (CoachIntent.APP_FEATURE_RECOMMENDATION, CoachIntent.PRACTICE_PLAN),
        )

    def test_similar_current_song(self) -> None:
        self.assertEqual(
            route_question("What songs are similar to my current song?", {}).intent,
            CoachIntent.REPERTOIRE_RECOMMENDATION,
        )


if __name__ == "__main__":
    unittest.main()

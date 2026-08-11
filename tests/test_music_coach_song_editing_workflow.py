"""Song editing / lyrics / chords / persistence vertical slice tests."""

from __future__ import annotations

import unittest

from music_coach_ami.pipeline import run_coach_pipeline
from music_coach_ami.router import CoachIntent, route_question


class SongEditingRouterTests(unittest.TestCase):
    def test_custom_song_edit_routes(self) -> None:
        self.assertEqual(
            route_question("I created a custom song before. How do I edit it now?", {}).intent,
            CoachIntent.SONG_EDITING_WORKFLOW,
        )

    def test_practice_key_vs_chords_routes_song_editing_not_comparison(self) -> None:
        self.assertEqual(
            route_question(
                "What's the difference between changing the Practice Key and editing the song's chords?",
                {},
            ).intent,
            CoachIntent.SONG_EDITING_WORKFLOW,
        )

    def test_eb_today_routes_song_editing_not_practice_plan(self) -> None:
        self.assertEqual(
            route_question(
                "I only want to practice this song in E-flat today. Do I need to edit the chords?",
                {},
            ).intent,
            CoachIntent.SONG_EDITING_WORKFLOW,
        )

    def test_genuine_practice_plan_still_routes(self) -> None:
        self.assertEqual(
            route_question("What should I practice today?", {}).intent,
            CoachIntent.PRACTICE_PLAN,
        )


class SongEditingVerticalSliceTests(unittest.TestCase):
    def test_a_custom_song_reopen_edit(self) -> None:
        resp = run_coach_pipeline("I created a custom song before. How do I edit it now?", {})
        assert resp is not None
        self.assertEqual(resp.intent, CoachIntent.SONG_EDITING_WORKFLOW)
        text = resp.composed_markdown()
        self.assertIn("Custom Progression", text)
        self.assertIn("Load saved", text)
        self.assertIn("Save to library", text)
        self.assertEqual(resp.diagnostics.get("song_edit_submode"), "custom_reopen_edit")

    def test_b_add_lyrics_save(self) -> None:
        resp = run_coach_pipeline("How do I add lyrics to a song and save them?", {})
        assert resp is not None
        self.assertEqual(resp.intent, CoachIntent.SONG_EDITING_WORKFLOW)
        text = resp.composed_markdown()
        self.assertIn("Lyrics & Cues", text)
        self.assertIn("Save Lyrics & Cues", text)
        self.assertIn("not", text.lower())
        self.assertEqual(resp.diagnostics.get("edit_target"), "lyrics")

    def test_c_save_chord_change(self) -> None:
        resp = run_coach_pipeline("I changed a chord in this song. How do I save the change?", {})
        assert resp is not None
        text = resp.composed_markdown()
        self.assertIn("Edit Song Chart", text)
        self.assertIn("Enable editing", text)
        self.assertIn("Save corrected chart", text)
        self.assertNotIn("user_chart_overrides", text.lower())

    def test_d_practice_key_vs_chord_edit(self) -> None:
        resp = run_coach_pipeline(
            "What's the difference between changing the Practice Key and editing the song's chords?",
            {},
        )
        assert resp is not None
        self.assertEqual(resp.intent, CoachIntent.SONG_EDITING_WORKFLOW)
        text = resp.composed_markdown()
        self.assertIn("Practice Key", text)
        self.assertIn("Edit Song Chart", text)
        self.assertIn("Use Practice Key when", text)
        self.assertNotIn("Songs / Catalog", text)
        self.assertNotIn("FeatureExplanationSolver", resp.source_solver)
        self.assertEqual(resp.diagnostics.get("song_edit_submode"), "practice_key_vs_chord_edit")

    def test_e_catalog_ownership(self) -> None:
        resp = run_coach_pipeline(
            "If I edit a catalog song, does it change the original or just my version?",
            {},
        )
        assert resp is not None
        text = resp.composed_markdown()
        self.assertIn("do not change", text.lower())
        self.assertIn("Revert", text)
        self.assertNotIn("sidecar", text.lower())
        self.assertNotIn("user_chart_overrides", text.lower())

    def test_f_return_later(self) -> None:
        resp = run_coach_pipeline("I edited a song yesterday. How do I get back to it?", {})
        assert resp is not None
        text = resp.composed_markdown()
        self.assertIn("Custom Progression", text)
        self.assertIn("Song Selection", text)
        self.assertEqual(resp.diagnostics.get("song_edit_submode"), "return_later")


class PracticeKeyRoutingTests(unittest.TestCase):
    def test_practice_key_permanent_semantics(self) -> None:
        resp = run_coach_pipeline("If I change Practice Key, does that permanently change my song?", {})
        assert resp is not None
        self.assertEqual(resp.intent, CoachIntent.SONG_EDITING_WORKFLOW)
        text = resp.composed_markdown()
        self.assertIn("Practice", text)
        self.assertIn("Edit Song Chart", text)

    def test_practice_key_transpose_saved_chords(self) -> None:
        resp = run_coach_pipeline(
            "Does changing Practice Key permanently transpose the saved chords?", {}
        )
        assert resp is not None
        self.assertEqual(resp.intent, CoachIntent.SONG_EDITING_WORKFLOW)
        text = resp.composed_markdown().lower()
        self.assertIn("practice", text)
        self.assertTrue("not" in text or "without" in text)

    def test_bb_today_without_changing_song(self) -> None:
        resp = run_coach_pipeline(
            "I want to practice this in Bb today without changing the song. What should I do?",
            {},
        )
        assert resp is not None
        self.assertEqual(resp.intent, CoachIntent.SONG_EDITING_WORKFLOW)
        self.assertIn("Practice", resp.composed_markdown())

    def test_permanent_chord_replace_routes_chart_edit(self) -> None:
        resp = run_coach_pipeline(
            "I want to permanently replace one chord in the chorus. What should I do?",
            {},
        )
        assert resp is not None
        self.assertEqual(resp.intent, CoachIntent.SONG_EDITING_WORKFLOW)
        text = resp.composed_markdown()
        self.assertIn("Edit Song Chart", text)


class SongEditingAdditionalTests(unittest.TestCase):
    def test_catalog_edit_question(self) -> None:
        resp = run_coach_pipeline("Can I edit one of the songs in the catalog?", {})
        assert resp is not None
        self.assertEqual(resp.intent, CoachIntent.SONG_EDITING_WORKFLOW)
        self.assertIn("Edit Song Chart", resp.composed_markdown())

    def test_practice_eb_without_edit(self) -> None:
        resp = run_coach_pipeline(
            "I only want to practice this song in Eb today. Do I have to edit all the chords?",
            {},
        )
        assert resp is not None
        self.assertEqual(resp.intent, CoachIntent.SONG_EDITING_WORKFLOW)
        self.assertIn("Practice", resp.composed_markdown())
        self.assertIn("**No", resp.composed_markdown())

    def test_practice_eb_need_edit_variant(self) -> None:
        resp = run_coach_pipeline(
            "I only want to practice this song in E-flat today. Do I need to edit the chords?",
            {},
        )
        assert resp is not None
        self.assertEqual(resp.intent, CoachIntent.SONG_EDITING_WORKFLOW)
        self.assertIn("No", resp.composed_markdown())
        self.assertIn("Practice", resp.composed_markdown())
        self.assertNotEqual(resp.source_solver, "PracticePlanSolver")

    def test_custom_songs_location(self) -> None:
        resp = run_coach_pipeline("Where are my custom songs?", {})
        assert resp is not None
        self.assertIn("Custom Progression", resp.composed_markdown())

    def test_lyrics_not_autosaved(self) -> None:
        resp = run_coach_pipeline("Are my lyrics saved automatically?", {})
        assert resp is not None
        text = resp.composed_markdown().lower()
        self.assertIn("save lyrics", text)
        self.assertTrue("not" in text or "explicit" in text)

    def test_unsaved_lyrics_close_leads_with_no(self) -> None:
        resp = run_coach_pipeline(
            "I typed new lyrics but haven't pressed save. If I close the app, will they still be there?",
            {},
        )
        assert resp is not None
        text = resp.composed_markdown()
        self.assertTrue(text.strip().startswith("**No"))
        self.assertIn("Save Lyrics & Cues", text)
        self.assertNotIn("not mounted in the current UI", text)


class RecordingRegressionTests(unittest.TestCase):
    def test_record_practice_still_practice_log(self) -> None:
        resp = run_coach_pipeline("How do I record what I practiced today?", {})
        assert resp is not None
        self.assertIn("Practice Log", resp.composed_markdown())

    def test_record_myself_still_dual_audio(self) -> None:
        resp = run_coach_pipeline("How do I record myself playing?", {})
        assert resp is not None
        text = resp.composed_markdown()
        self.assertNotIn("**Use:** Practice Log", text)
        self.assertIn("Upload", text)
        self.assertIn("Multitrack", text)


class ComparisonPolishTests(unittest.TestCase):
    def test_no_best_for_to_improvise(self) -> None:
        resp = run_coach_pipeline(
            "What's the difference between Style Jam and Jam Session Generator?", {}
        )
        assert resp is not None
        text = resp.composed_markdown()
        self.assertNotIn("Best for: to ", text)
        self.assertIn("**Best for:**", text)
        self.assertIn("Find it:", text)


if __name__ == "__main__":
    unittest.main()

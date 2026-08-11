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

    def test_practice_key_vs_chords_comparison(self) -> None:
        self.assertEqual(
            route_question(
                "What's the difference between changing the Practice Key and editing the song's chords?",
                {},
            ).intent,
            CoachIntent.FEATURE_EXPLANATION,
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
        self.assertIn("autosave", text.lower())
        self.assertEqual(resp.diagnostics.get("edit_target"), "lyrics")

    def test_c_save_chord_change(self) -> None:
        resp = run_coach_pipeline("I changed a chord in this song. How do I save the change?", {})
        assert resp is not None
        text = resp.composed_markdown()
        self.assertIn("Edit Song Chart", text)
        self.assertIn("Enable editing", text)
        self.assertIn("Save corrected chart", text)
        self.assertNotIn("generic Save button on the song page", text.replace("no generic Save button", ""))

    def test_d_practice_key_vs_chord_edit(self) -> None:
        resp = run_coach_pipeline(
            "What's the difference between changing the Practice Key and editing the song's chords?",
            {},
        )
        assert resp is not None
        self.assertEqual(resp.intent, CoachIntent.FEATURE_EXPLANATION)
        text = resp.composed_markdown()
        self.assertIn("Practice", text)
        self.assertIn("Edit Song Chart", text)
        self.assertIn("Find it:", text)

    def test_e_catalog_ownership(self) -> None:
        resp = run_coach_pipeline(
            "If I edit a catalog song, does it change the original or just my version?",
            {},
        )
        assert resp is not None
        text = resp.composed_markdown()
        self.assertIn("does **not** change", text)
        self.assertIn("sidecar", text.lower())
        self.assertIn("Revert", text)

    def test_f_return_later(self) -> None:
        resp = run_coach_pipeline("I edited a song yesterday. How do I get back to it?", {})
        assert resp is not None
        text = resp.composed_markdown()
        self.assertIn("Custom Progression", text)
        self.assertIn("Song Selection", text)
        self.assertEqual(resp.diagnostics.get("song_edit_submode"), "return_later")


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
        self.assertIn("Practice", resp.composed_markdown())
        self.assertIn("**do not** need", resp.composed_markdown())

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

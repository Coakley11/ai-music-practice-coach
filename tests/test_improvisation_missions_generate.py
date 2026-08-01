"""Regression: generate_mission_example must populate abc/tab outputs."""

from __future__ import annotations

import unittest

from improvisation_intelligence import ImprovSessionContext
from improvisation_missions import generate_mission_example


class TestGenerateMissionExample(unittest.TestCase):
    def test_generate_mission_example_sets_abc_tab_and_flags(self) -> None:
        ctx = ImprovSessionContext(
            song_title="Test Song",
            artist="Artist",
            key_center="D",
            display_key="D",
            instrument="Guitar",
            level="Intermediate",
            focus="Changes",
            sections={"Verse": ["D", "G"]},
        )
        example = generate_mission_example(
            "Target only guide tones (3rds & 7ths)",
            improv_ctx=ctx,
            chord="D",
            section="Verse",
            level="Intermediate",
            instrument="Guitar",
            focus="Changes",
        )
        self.assertTrue(example.abc)
        self.assertTrue(example.show_tab)
        self.assertFalse(example.show_piano)
        self.assertIsInstance(example.motif, dict)
        self.assertIn("Mission", example.abc)
        self.assertNotIn("Motif —", example.abc)
        self.assertNotIn("Motif -", example.abc)

    def test_harder_differs_from_normal(self) -> None:
        ctx = ImprovSessionContext(
            song_title="Shape",
            artist="Artist",
            key_center="F#m",
            display_key="F#m",
            instrument="Piano",
            level="Intermediate",
            focus="Improvisation",
            sections={"Chorus": ["Bm", "Em"]},
        )
        normal = generate_mission_example(
            "Rhythm-first, note-second",
            improv_ctx=ctx,
            chord="Em",
            section="Chorus",
            level="Beginner",
            instrument="Piano",
            focus="Improvisation",
            variant="normal",
        )
        harder = generate_mission_example(
            "Rhythm-first, note-second",
            improv_ctx=ctx,
            chord="Em",
            section="Chorus",
            level="Beginner",
            instrument="Piano",
            focus="Improvisation",
            variant="harder",
        )
        self.assertNotEqual(normal.motif.get("display"), harder.motif.get("display"))
        normal_len = len(normal.motif.get("notes") or [])
        harder_len = len(harder.motif.get("notes") or [])
        self.assertGreater(harder_len, normal_len)
        self.assertLessEqual(harder_len, 10)
        self.assertEqual(harder.motif.get("student_level"), "Beginner")
        self.assertEqual(harder.motif.get("difficulty_tier"), "harder")
        self.assertFalse(harder.motif.get("harder_example"))

    def test_advanced_harder_uses_long_phrase(self) -> None:
        ctx = ImprovSessionContext(
            song_title="Shape",
            artist="Artist",
            key_center="F#m",
            display_key="F#m",
            instrument="Piano",
            level="Advanced",
            focus="Improvisation",
            sections={"Chorus": ["Bm", "Em"]},
        )
        harder = generate_mission_example(
            "Rhythm-first, note-second",
            improv_ctx=ctx,
            chord="Em",
            section="Chorus",
            level="Advanced",
            instrument="Piano",
            focus="Improvisation",
            variant="harder",
        )
        self.assertGreaterEqual(len(harder.motif.get("notes") or []), 12)
        self.assertTrue(harder.motif.get("harder_example"))

    def test_new_idea_changes_each_nonce(self) -> None:
        ctx = ImprovSessionContext(
            song_title="Shape",
            artist="Artist",
            key_center="F#m",
            display_key="F#m",
            instrument="Piano",
            level="Intermediate",
            focus="Improvisation",
            sections={"Chorus": ["Em"]},
        )
        session: dict = {}
        first = generate_mission_example(
            "Rhythm-first, note-second",
            improv_ctx=ctx,
            chord="Em",
            section="Chorus",
            level="Intermediate",
            instrument="Piano",
            focus="Improvisation",
            variant="new",
            session_state=session,
        )
        second = generate_mission_example(
            "Rhythm-first, note-second",
            improv_ctx=ctx,
            chord="Em",
            section="Chorus",
            level="Intermediate",
            instrument="Piano",
            focus="Improvisation",
            variant="new",
            session_state=session,
        )
        self.assertNotEqual(first.motif.get("display"), second.motif.get("display"))
        third = generate_mission_example(
            "Rhythm-first, note-second",
            improv_ctx=ctx,
            chord="Em",
            section="Chorus",
            level="Intermediate",
            instrument="Piano",
            focus="Improvisation",
            variant="new",
            session_state=session,
        )
        displays = {
            first.motif.get("display"),
            second.motif.get("display"),
            third.motif.get("display"),
        }
        self.assertEqual(len(displays), 3)


if __name__ == "__main__":
    unittest.main()

"""Practice Chord Coach uses the same insight pipeline as Live Coach."""

from __future__ import annotations

import unittest

from improvisation_intelligence import chord_coach_insight, coaching_reference_key
from practice_chord_coach import (
    practice_chord_coach_insight,
    practice_scale_coach_markdown,
)
from improvisation_harmony import analyze_chord_for_harmony_map
from improvisation_intelligence import ImprovSessionContext


class TestPracticeLiveCoachParity(unittest.TestCase):
    def test_gm7_chord_tones_match_live_coach(self) -> None:
        ref = coaching_reference_key(key_center="F", display_key="F")
        live = chord_coach_insight("Gm7", key_center=ref, instrument="Guitar", level="Intermediate")
        practice = practice_chord_coach_insight(
            "Gm7",
            display_key="F",
            instrument="Guitar",
            level="Intermediate",
        )
        assert practice is not None
        self.assertEqual(practice.chord_tones, live.chord_tones)
        self.assertEqual(
            [s.label for s in practice.scale_suggestions],
            [s.label for s in live.scale_suggestions],
        )
        self.assertEqual(
            [s.notes for s in practice.scale_suggestions],
            [s.notes for s in live.scale_suggestions],
        )

    def test_scale_markdown_uses_format_scale_line(self) -> None:
        md = practice_scale_coach_markdown("Gm7", "F", "Intermediate", "Guitar")
        self.assertIn("→", md)
        self.assertIn("Bb", md)
        self.assertNotIn("natural minor ·", md)

    def test_harmony_stable_matches_harmony_map(self) -> None:
        ctx = ImprovSessionContext(
            song_title="Test",
            artist="",
            key_center="F",
            display_key="F",
            instrument="Guitar",
            level="Intermediate",
            focus="Harmony",
            sections={"Verse": ["Gm7"]},
        )
        guide = analyze_chord_for_harmony_map("Gm7", improv_ctx=ctx, section="Verse")
        practice = practice_chord_coach_insight(
            "Gm7", display_key="F", instrument="Guitar", level="Intermediate"
        )
        assert practice is not None
        for tone in guide.stable_tones:
            self.assertIn(tone, practice.chord_tones)


if __name__ == "__main__":
    unittest.main()

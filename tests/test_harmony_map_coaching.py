"""Harmony Map + Live Coach shared coaching pipeline (theory + spelling)."""

from __future__ import annotations

import re

import unittest

from improvisation_harmony import analyze_chord_for_harmony_map
from improvisation_intelligence import (
    ImprovSessionContext,
    chord_coach_insight,
    coaching_reference_key,
)


def _looks_like_pitch(name: str) -> bool:
    return bool(re.match(r"^[A-G][#b]?\d*$", str(name or "").strip()))


class TestCoachingReferenceKey(unittest.TestCase):
    def test_prefers_display_key(self) -> None:
        self.assertEqual(
            coaching_reference_key(key_center="G", display_key="F"),
            "F",
        )


class TestLiveCoachScaleSuggestions(unittest.TestCase):
    def test_half_dim_scales_are_valid_pitches(self) -> None:
        insight = chord_coach_insight("F#m7b5", key_center="Bm")
        self.assertGreaterEqual(len(insight.scale_suggestions), 3)
        for sug in insight.scale_suggestions:
            self.assertTrue(sug.notes, msg=sug.label)
            for note in sug.notes:
                self.assertTrue(
                    _looks_like_pitch(note),
                    msg=f"{sug.label} → {note}",
                )
            self.assertNotIn("half-diminished Major", sug.label)

    def test_gm7_in_f_major_spelling(self) -> None:
        insight = chord_coach_insight("Gm7", key_center="F")
        joined = " ".join(insight.chord_tones)
        self.assertIn("Bb", joined)
        self.assertNotIn("A#", joined)
        for sug in insight.scale_suggestions:
            self.assertNotIn("A#", " ".join(sug.notes))


class TestHarmonyMapGuide(unittest.TestCase):
    def _ctx(self, *, display_key: str = "F") -> ImprovSessionContext:
        return ImprovSessionContext(
            song_title="Girl from Ipanema",
            artist="Test",
            key_center="F",
            display_key=display_key,
            instrument="Guitar",
            level="Intermediate",
            focus="Harmony",
            sections={"Intro": ["Gm7", "C7"]},
        )

    def test_gm7_stable_tones_use_chart_spelling(self) -> None:
        guide = analyze_chord_for_harmony_map(
            "Gm7",
            improv_ctx=self._ctx(),
            section="Intro",
            next_chord="C7",
        )
        self.assertIn("Bb", guide.stable_tones)
        self.assertNotIn("A#", guide.stable_tones)

    def test_scale_lines_match_suggestion_pipeline(self) -> None:
        guide = analyze_chord_for_harmony_map(
            "Gm7",
            improv_ctx=self._ctx(),
            section="Intro",
        )
        self.assertTrue(guide.scale_lines)
        line = guide.scale_lines[0]
        self.assertIn("→", line)
        self.assertNotIn("A#", line)

    def test_c7_color_tones_flat_key(self) -> None:
        guide = analyze_chord_for_harmony_map(
            "C7",
            improv_ctx=self._ctx(),
            section="Intro",
        )
        notes = [c.note for c in guide.color_tones]
        joined = " ".join(notes)
        self.assertNotIn("A#", joined)


if __name__ == "__main__":
    unittest.main()

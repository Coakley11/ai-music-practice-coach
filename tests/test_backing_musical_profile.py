"""Tests for canonical backing musical profile and style recipes."""

from __future__ import annotations

import unittest

from backing_musical_profile import (
    resolve_backing_musical_profile,
    resolve_backing_musical_profile_from_context,
)
from backing_style_recipes import apply_profile_to_synthesis, style_recipe_id
from backing_audio import _style_patterns, synthesize_chords_to_numpy


class _FakeCtx:
    def __init__(self, **kwargs) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestBackingMusicalProfile(unittest.TestCase):
    def test_creative_blues_maps_to_blues_groove(self) -> None:
        prof = resolve_backing_musical_profile(style="Blues", mood="Mellow", intensity="Medium")
        self.assertEqual(prof.canonical_style(), "Blues groove")

    def test_context_resolves_mood_and_intensity(self) -> None:
        ctx = _FakeCtx(
            style="Funk",
            mood="Energetic",
            groove_intensity="Heavy",
            bpm=108,
            meter="4/4",
        )
        prof = resolve_backing_musical_profile_from_context(ctx, style="Funk", tempo=108)
        self.assertEqual(prof.mood, "Energetic")
        self.assertEqual(prof.intensity, "Heavy")
        self.assertEqual(prof.canonical_style(), "Funk groove")


class TestBackingStyleRecipes(unittest.TestCase):
    def test_funk_and_ballad_patterns_differ(self) -> None:
        funk_pat = _style_patterns("Funk groove", {}, time_signature="4/4")
        ballad_pat = _style_patterns("Ballad", {}, time_signature="4/4")
        self.assertNotEqual(funk_pat["bass_beats"], ballad_pat["bass_beats"])
        self.assertNotEqual(funk_pat["comp_dur"], ballad_pat["comp_dur"])

    def test_heavy_energetic_increases_density_vs_light_dreamy(self) -> None:
        base_profile = {"swing": 0.0, "kick_push": 1.0, "hat_soft": 1.0}
        base_patterns = _style_patterns("Pop groove", {}, time_signature="4/4")
        heavy = resolve_backing_musical_profile(
            style="Pop groove", mood="Energetic", intensity="Heavy"
        )
        light = resolve_backing_musical_profile(
            style="Pop groove", mood="Dreamy", intensity="Light"
        )
        _, heavy_pat = apply_profile_to_synthesis(
            style="Pop groove",
            song_profile=base_profile,
            patterns=base_patterns,
            profile=heavy,
        )
        sp_light, light_pat = apply_profile_to_synthesis(
            style="Pop groove",
            song_profile=base_profile,
            patterns=base_patterns,
            profile=light,
        )
        self.assertGreater(
            len(heavy_pat.get("comp_beats", [])),
            len(light_pat.get("comp_beats", [])),
        )
        self.assertGreater(float(heavy_pat.get("comp_dur", 0)), float(light_pat.get("comp_dur", 0)) * 0.5)

    def test_blues_recipe_replaces_pattern_grid(self) -> None:
        prof = resolve_backing_musical_profile(style="Blues groove")
        sp, pat = apply_profile_to_synthesis(
            style="Blues groove",
            song_profile={},
            patterns=_style_patterns("Pop groove", {}, time_signature="4/4"),
            profile=prof,
        )
        self.assertEqual(style_recipe_id("Blues groove"), "blues_groove")
        # Clear shuffle: strong swing and triplet-offset comp beats.
        self.assertGreaterEqual(float(sp.get("swing", 0.0)), 0.2)
        self.assertTrue(
            any(abs(float(b) - 0.67) < 0.02 for b in pat.get("comp_beats", [])),
            f"expected triplet shuffle comp beat near 0.67, got {pat.get('comp_beats')}",
        )
        self.assertTrue(
            any(abs(float(b) - 0.67) < 0.02 for b in pat.get("hat_beats", [])),
            "expected shuffled hi-hat on triplet subdivision",
        )


class TestStyleContrastAmplified(unittest.TestCase):
    def _apply(self, style, mood, intensity):
        prof = resolve_backing_musical_profile(style=style, mood=mood, intensity=intensity)
        base = _style_patterns(style, {}, time_signature="4/4")
        return apply_profile_to_synthesis(
            style=style,
            song_profile={"kick_push": 1.0, "hat_soft": 1.0, "swing": 0.0},
            patterns=base,
            profile=prof,
        )

    def test_heavy_adds_kick_hits_and_louder_kick(self) -> None:
        base = _style_patterns("Pop groove", {}, time_signature="4/4")
        sp_heavy, pat_heavy = self._apply("Pop groove", "Energetic", "Heavy")
        self.assertGreater(len(pat_heavy["kick_beats"]), len(base["kick_beats"]))
        self.assertGreater(float(sp_heavy["kick_push"]), 1.1)

    def test_light_sparser_comp_and_quieter_kit(self) -> None:
        sp_medium, pat_medium = self._apply("Pop groove", "Mellow", "Medium")
        sp_light, pat_light = self._apply("Pop groove", "Mellow", "Light")
        self.assertLess(len(pat_light["comp_beats"]), len(pat_medium["comp_beats"]))
        self.assertLess(float(sp_light["kick_push"]), float(sp_medium["kick_push"]))

    def test_funk_more_syncopation_than_pop(self) -> None:
        _, pop = self._apply("Pop groove", "Mellow", "Medium")
        _, funk = self._apply("Funk groove", "Mellow", "Medium")
        off_pop = [b for b in pop["comp_beats"] if float(b) != int(float(b))]
        off_funk = [b for b in funk["comp_beats"] if float(b) != int(float(b))]
        self.assertGreaterEqual(len(off_funk), len(off_pop))

    def test_dreamy_lengthens_sustain_and_thins_comp(self) -> None:
        _, medium = self._apply("Pop groove", "Mellow", "Medium")
        sp_dreamy, dreamy = self._apply("Pop groove", "Dreamy", "Medium")
        self.assertGreater(float(sp_dreamy.get("sustain_mul", 1.0)), 1.2)
        self.assertGreater(float(dreamy["comp_dur"]), float(medium["comp_dur"]))
        self.assertLessEqual(len(dreamy["comp_beats"]), len(medium["comp_beats"]))


class TestSynthesisProfileWiring(unittest.TestCase):
    def test_mood_intensity_changes_audio_output(self) -> None:
        chords = [{"chord": "C", "section": "Verse"}]
        heavy_prof = resolve_backing_musical_profile(
            style="Funk groove", mood="Energetic", intensity="Heavy"
        )
        light_prof = resolve_backing_musical_profile(
            style="Funk groove", mood="Dreamy", intensity="Light"
        )
        heavy, _ = synthesize_chords_to_numpy(
            chords,
            bpm=100,
            loops=1,
            style="Funk groove",
            musical_profile=heavy_prof,
        )
        light, _ = synthesize_chords_to_numpy(
            chords,
            bpm=100,
            loops=1,
            style="Funk groove",
            musical_profile=light_prof,
        )
        self.assertFalse((heavy == light).all())


if __name__ == "__main__":
    unittest.main()

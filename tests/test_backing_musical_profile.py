"""Tests for canonical backing musical profile and style recipes."""

from __future__ import annotations

import unittest
from typing import Any

from backing_musical_profile import (
    resolve_backing_musical_profile,
    resolve_backing_musical_profile_from_context,
)
from backing_style_recipes import (
    apply_profile_to_synthesis,
    style_pattern_for_recipe,
    style_recipe_id,
)
from backing_audio import _song_backing_profile, _style_patterns, synthesize_chords_to_numpy


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


class TestPhase2StyleIdentity(unittest.TestCase):
    _PROGRESSION = [
        {"chord": "Em7", "section": "Loop"},
        {"chord": "Am7", "section": "Loop"},
        {"chord": "D7", "section": "Loop"},
        {"chord": "Gmaj7", "section": "Loop"},
    ]
    _STYLES = (
        "Pop groove",
        "Rock groove",
        "Jazz swing",
        "Bossa nova",
        "Funk groove",
        "Blues groove",
    )

    def test_same_progression_differs_across_styles(self) -> None:
        outputs: dict[str, Any] = {}
        for style in self._STYLES:
            prof = resolve_backing_musical_profile(style=style, mood="Mellow", intensity="Medium")
            audio, _ = synthesize_chords_to_numpy(
                self._PROGRESSION,
                bpm=100,
                loops=1,
                style=style,
                musical_profile=prof,
            )
            outputs[style] = audio
        for i, style_a in enumerate(self._STYLES):
            for style_b in self._STYLES[i + 1 :]:
                self.assertFalse(
                    (outputs[style_a] == outputs[style_b]).all(),
                    f"{style_a} should differ from {style_b}",
                )

    @staticmethod
    def _spectral_features(audio: Any, sr: int = 44100) -> dict[str, float]:
        import numpy as np

        mag = np.abs(np.fft.rfft(audio))
        freqs = np.fft.rfftfreq(len(audio), 1.0 / sr)
        centroid = float((freqs * mag).sum() / (mag.sum() + 1e-9))
        low = float(mag[freqs < 200].sum())
        high = float(mag[freqs >= 2000].sum())
        tot = float(mag.sum()) + 1e-9
        rms = float(np.sqrt(np.mean(audio ** 2)))
        crest = float(np.max(np.abs(audio)) / (rms + 1e-9))
        return {
            "centroid": centroid,
            "low_ratio": low / tot,
            "high_ratio": high / tot,
            "crest": crest,
        }

    def test_style_timbre_fingerprints_differ(self) -> None:
        """Styles must differ in spectral character, not just waveform."""
        feats: dict[str, dict[str, float]] = {}
        for style in self._STYLES:
            prof = resolve_backing_musical_profile(style=style, mood="Mellow", intensity="Medium")
            audio, sr = synthesize_chords_to_numpy(
                self._PROGRESSION, bpm=100, loops=2, style=style, musical_profile=prof
            )
            feats[style] = self._spectral_features(audio, sr)

        # Rock/Funk are brighter + punchier than Jazz/Bossa.
        self.assertGreater(feats["Rock groove"]["centroid"], feats["Jazz swing"]["centroid"])
        self.assertGreater(feats["Funk groove"]["crest"], feats["Jazz swing"]["crest"])
        # Jazz carries more low-end weight (walking bass + soft kit) than Rock.
        self.assertGreater(feats["Jazz swing"]["low_ratio"], feats["Rock groove"]["low_ratio"])
        # Each style has a distinct spectral signature.
        sigs = {
            style: (round(f["centroid"], -2), round(f["crest"], 1))
            for style, f in feats.items()
        }
        self.assertGreaterEqual(len(set(sigs.values())), 5)

    def test_style_recipe_patterns_are_distinct(self) -> None:
        signatures = []
        for style in self._STYLES:
            recipe = style_recipe_id(style)
            grid = style_pattern_for_recipe(recipe)
            signatures.append(
                (
                    tuple(grid["bass_beats"]),
                    tuple(grid["comp_beats"]),
                    tuple(grid.get("hat_beats", [])),
                    float(grid["comp_dur"]),
                )
            )
        self.assertEqual(len(signatures), len(set(signatures)))

    def test_funk_combo_profiles_differ(self) -> None:
        heavy = resolve_backing_musical_profile(
            style="Funk groove", mood="Energetic", intensity="Heavy"
        )
        light = resolve_backing_musical_profile(
            style="Funk groove", mood="Dreamy", intensity="Light"
        )
        sp_heavy, pat_heavy = apply_profile_to_synthesis(
            style="Funk groove",
            song_profile={},
            patterns=style_pattern_for_recipe("funk_groove"),
            profile=heavy,
        )
        sp_light, pat_light = apply_profile_to_synthesis(
            style="Funk groove",
            song_profile={},
            patterns=style_pattern_for_recipe("funk_groove"),
            profile=light,
        )
        self.assertGreater(len(pat_heavy["kick_beats"]), len(pat_light["kick_beats"]))
        self.assertLess(len(pat_light["comp_beats"]), len(pat_heavy["comp_beats"]))
        self.assertGreater(float(sp_heavy["kick_push"]), float(sp_light["kick_push"]))

    def test_jazz_relaxed_vs_energetic_differ(self) -> None:
        relaxed = resolve_backing_musical_profile(
            style="Jazz swing", mood="Relaxed", intensity="Light"
        )
        energetic = resolve_backing_musical_profile(
            style="Jazz swing", mood="Energetic", intensity="Heavy"
        )
        sp_rel, pat_rel = apply_profile_to_synthesis(
            style="Jazz swing",
            song_profile={},
            patterns=style_pattern_for_recipe("jazz_swing"),
            profile=relaxed,
        )
        sp_en, pat_en = apply_profile_to_synthesis(
            style="Jazz swing",
            song_profile={},
            patterns=style_pattern_for_recipe("jazz_swing"),
            profile=energetic,
        )
        self.assertLess(len(pat_rel["comp_beats"]), len(pat_en["comp_beats"]))
        self.assertLess(float(sp_rel["kick_push"]), float(sp_en["kick_push"]))

    def test_song_override_blocked_when_style_locked(self) -> None:
        """Explicit style branches win; song groove_based cannot replace Funk grid."""
        song_profile = _song_backing_profile("Shape of You", "Ed Sheeran", "Funk groove")
        self.assertTrue(song_profile.get("groove_based"))
        song_profile["style_locked"] = True
        funk_pat = _style_patterns("Funk groove", song_profile, time_signature="4/4")
        # Pop groove now has its own explicit grid (not song override).
        pop_explicit = _style_patterns(
            "Pop groove",
            {"groove_based": True, "style_locked": False},
            time_signature="4/4",
        )
        self.assertEqual(funk_pat["comp_dur"], 0.20)
        self.assertEqual(pop_explicit["comp_dur"], 0.36)
        self.assertNotEqual(tuple(funk_pat["comp_beats"]), tuple(pop_explicit["comp_beats"]))

    def test_session_mood_merges_when_ctx_lacks_mood(self) -> None:
        ctx = _FakeCtx(style="Pop groove", groove_intensity="", mood="", bpm=100, meter="4/4")
        prof = resolve_backing_musical_profile_from_context(
            ctx,
            style="Pop groove",
            session_mood="Dreamy",
            session_intensity="Light",
        )
        self.assertEqual(prof.mood, "Dreamy")
        self.assertEqual(prof.intensity, "Light")


if __name__ == "__main__":
    unittest.main()

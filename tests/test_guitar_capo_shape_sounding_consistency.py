"""Issue 9: Practice/Concert key, shape key, capo, fingered shape and sounding chord always agree."""

from __future__ import annotations

import unittest

import guitar_capo as gc
from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY, build_capo_context
from music_theory import CHROMATIC, normalize_root, split_chord, transpose_chord

ROOTS = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def pc(chord: str) -> int:
    root, _suffix = split_chord(chord.split("/")[0])
    return CHROMATIC.index(normalize_root(root))


def quality(chord: str) -> str:
    base = chord.split("/")[0]
    root, suffix = split_chord(base)
    return suffix


def _ctx(sounding: str, shape: str, sections: dict):
    ss = {CAPO_ENABLED_KEY: True, CAPO_SHAPE_KEY: shape}
    return build_capo_context(ss, sections, concert_key=sounding, instrument="Guitar"), ss


class TestShapeVersusSounding(unittest.TestCase):
    def test_d_shape_with_capo_8_sounds_b_flat_major(self) -> None:
        # the reported case: a D-shape label with a B-flat sounding chord is CORRECT at capo 8
        ctx, _ = _ctx("Bb", "D", {"Verse": ["Bb", "Gm", "Eb", "F"]})
        self.assertEqual(ctx.capo_fret, 8)
        self.assertEqual(ctx.shape_sections["Verse"][0], "D")
        self.assertEqual(ctx.sounding_sections["Verse"][0], "Bb")

    def test_e_minor_shapes_with_capo_8_sound_in_c_minor(self) -> None:
        ctx, _ = _ctx("Cm", "E", {"Verse": ["Cm", "Ab", "Eb", "Bb"]})
        self.assertEqual(ctx.capo_fret, 8)
        self.assertEqual(ctx.shape_key, "Em")
        self.assertEqual(ctx.shape_sections["Verse"], ["Em", "C", "G", "D"])
        self.assertEqual(ctx.sounding_sections["Verse"], ["Cm", "Ab", "Eb", "Bb"])

    def test_every_chord_shape_plus_capo_equals_the_sounding_chord(self) -> None:
        prog = ["{r}", "{r}m", "{r}7", "{r}maj7", "{r}m7", "{r}sus4", "{r}/G"]
        for sounding in ROOTS:
            for mode in ("", "m"):
                for shape in ("C", "A", "G", "E", "D"):
                    chords = [p.format(r=sounding) for p in prog]
                    key = sounding + mode
                    with self.subTest(sounding=key, shape=shape):
                        ctx, _ = _ctx(key, shape, {"V": chords})
                        for shaped, sounded in zip(ctx.shape_sections["V"], ctx.sounding_sections["V"]):
                            self.assertEqual((pc(shaped) + ctx.capo_fret) % 12, pc(sounded), (shaped, sounded, ctx.capo_fret))
                            self.assertEqual(quality(shaped), quality(sounded), (shaped, sounded))

    def test_capo_fret_is_the_distance_from_the_shape_to_the_sounding_tonic(self) -> None:
        for sounding in ROOTS:
            for shape in ("C", "A", "G", "E", "D"):
                self.assertEqual(gc.capo_fret_for_shape(sounding, shape), (pc(sounding) - pc(shape)) % 12)

    def test_shape_chart_mode_follows_the_sounding_mode(self) -> None:
        self.assertEqual(gc.shape_chart_key_for_concert("Cm", "E"), "Em")
        self.assertEqual(gc.shape_chart_key_for_concert("Bb", "D"), "D")
        self.assertEqual(gc.shape_chart_key_for_concert("F#m", "D"), "Dm")

    def test_capo_off_charts_show_the_sounding_chords(self) -> None:
        ss = {CAPO_ENABLED_KEY: False}
        ctx = build_capo_context(ss, {"V": ["Bb", "Gm"]}, concert_key="Bb", instrument="Guitar")
        self.assertEqual((ctx.capo_fret, ctx.shape_sections["V"]), (0, ["Bb", "Gm"]))

    def test_non_guitar_instruments_are_not_capo_transposed(self) -> None:
        ss = {CAPO_ENABLED_KEY: True, CAPO_SHAPE_KEY: "D"}
        ctx = build_capo_context(ss, {"V": ["Bb"]}, concert_key="Bb", instrument="Piano")
        self.assertEqual((ctx.enabled, ctx.shape_sections["V"]), (False, ["Bb"]))

    def test_the_practice_key_change_keeps_the_players_shape_and_updates_capo(self) -> None:
        ctx1, ss = _ctx("Bb", "D", {"V": ["Bb"]})
        self.assertEqual(ctx1.capo_fret, 8)
        ctx2 = build_capo_context(ss, {"V": ["C"]}, concert_key="C", instrument="Guitar")
        self.assertEqual((ss[CAPO_SHAPE_KEY], ctx2.capo_fret, ctx2.shape_sections["V"]), ("D", 10, ["D"]))


if __name__ == "__main__":
    unittest.main()

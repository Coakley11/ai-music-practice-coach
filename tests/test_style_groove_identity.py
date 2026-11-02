"""Issues 14/20/3: a saved Blues song keeps a Blues groove everywhere; each style maps to its own."""

from __future__ import annotations

import unittest

from backing_audio import infer_groove_style
from custom_progression_lab import _CPL_STYLE_GROOVE_FALLBACK, apply_style_preset, cpl_default_groove_for_active

SUPPORTED = {"Pop groove", "Rock groove", "Jazz swing", "Bossa nova", "Funk groove", "Blues groove"}


class TestCustomStyleToGroove(unittest.TestCase):
    def test_saved_blues_style_gives_a_blues_groove_not_rock(self) -> None:
        active = {"groove_style": "Auto", "progression_style": "Blues", "original_key_center": "Fm"}
        self.assertEqual(cpl_default_groove_for_active(active), "Blues groove")

    def test_each_style_has_its_own_supported_groove(self) -> None:
        got = {s: cpl_default_groove_for_active({"groove_style": "Auto", "progression_style": s, "original_key_center": "C"})
               for s in ("Pop", "Soul/R&B", "Jazz", "Bossa", "Blues", "Funk", "Rock")}
        self.assertEqual(got["Blues"], "Blues groove")
        self.assertEqual(got["Rock"], "Rock groove")
        self.assertEqual(got["Pop"], "Pop groove")
        self.assertEqual(got["Jazz"], "Jazz swing")
        self.assertEqual(got["Bossa"], "Bossa nova")
        self.assertEqual(got["Funk"], "Funk groove")
        self.assertTrue(set(got.values()) <= SUPPORTED)

    def test_blues_is_the_only_style_that_maps_to_blues_and_rock_only_to_rock(self) -> None:
        self.assertEqual([s for s, g in _CPL_STYLE_GROOVE_FALLBACK.items() if g == "Blues groove"], ["Blues"])
        self.assertEqual([s for s, g in _CPL_STYLE_GROOVE_FALLBACK.items() if g == "Rock groove"], ["Rock"])

    def test_preset_and_fallback_agree(self) -> None:
        for style in ("Pop", "Jazz", "Blues", "Funk", "Rock", "Bossa Nova"):
            preset = apply_style_preset(style, "C")
            if preset:
                key = "Bossa" if style == "Bossa Nova" else style
                self.assertEqual(preset["groove_style"], _CPL_STYLE_GROOVE_FALLBACK.get(key, preset["groove_style"]), style)

    def test_an_explicit_groove_override_is_not_replaced_by_the_saved_style(self) -> None:
        active = {"groove_style": "Funk groove", "progression_style": "Blues", "original_key_center": "Fm"}
        self.assertEqual(cpl_default_groove_for_active(active), "Funk groove")

    def test_the_saved_style_is_never_rewritten_by_reading_the_default(self) -> None:
        active = {"groove_style": "Auto", "progression_style": "Blues", "original_key_center": "Fm"}
        cpl_default_groove_for_active(active)
        self.assertEqual((active["progression_style"], active["groove_style"]), ("Blues", "Auto"))

    def test_backing_inference_for_a_blues_catalog_record_is_blues(self) -> None:
        self.assertEqual(infer_groove_style({"genre": "Blues", "title": "x"}), "Blues groove")


if __name__ == "__main__":
    unittest.main()

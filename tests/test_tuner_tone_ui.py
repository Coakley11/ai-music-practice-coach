"""Tuner / tone sustain mode UX helpers."""

from __future__ import annotations

import unittest

from media_tone_catalog import (
    CHROMATIC_NOTE_OPTIONS,
    build_tone_take_fields,
    pitch_class_from_option,
    resolve_tone_target_from_pitch_class,
)
from tuner_tone import TonePracticeResult
from tuner_tone_modes import (
    MODE_TONE_SUSTAIN,
    MODE_TUNE_LIVE,
    is_tone_sustain_mode,
    is_tune_live_mode,
    shows_live_target_note_input,
    shows_tone_sustain_note_dropdown,
)
from tuner_tone_ui import render_tuner_tone_section


class TestTunerToneModes(unittest.TestCase):
    def test_chromatic_dropdown_has_twelve_enharmonic_labels(self) -> None:
        self.assertEqual(len(CHROMATIC_NOTE_OPTIONS), 12)
        self.assertIn("C#/Db", CHROMATIC_NOTE_OPTIONS)
        self.assertIn("A#/Bb", CHROMATIC_NOTE_OPTIONS)

    def test_tune_live_does_not_show_target_note_input(self) -> None:
        for profile_mode in ("wind", "voice", "chromatic", "strings"):
            self.assertFalse(shows_live_target_note_input(MODE_TUNE_LIVE, profile_mode))

    def test_tone_sustain_shows_note_dropdown(self) -> None:
        for profile_mode in ("wind", "voice", "chromatic", "strings"):
            self.assertTrue(shows_tone_sustain_note_dropdown(MODE_TONE_SUSTAIN, profile_mode))

    def test_tone_sustain_dropdown_not_shown_in_live_mode(self) -> None:
        self.assertFalse(shows_tone_sustain_note_dropdown(MODE_TUNE_LIVE, "wind"))

    def test_tune_live_section_has_no_optional_target_text(self) -> None:
        source = open(render_tuner_tone_section.__code__.co_filename, encoding="utf-8").read()
        self.assertNotIn("Target note (optional)", source)
        self.assertNotIn("target_input", source)
        self.assertNotIn("text_input", source)

    def test_tone_sustain_section_uses_selectbox_not_text_input(self) -> None:
        source = open(render_tuner_tone_section.__code__.co_filename, encoding="utf-8").read()
        self.assertIn("selectbox", source)
        self.assertIn("CHROMATIC_NOTE_OPTIONS", source)
        self.assertNotIn("text_input", source)

    def test_mode_labels(self) -> None:
        self.assertTrue(is_tune_live_mode(MODE_TUNE_LIVE))
        self.assertTrue(is_tone_sustain_mode(MODE_TONE_SUSTAIN))


class TestToneTargetTransposition(unittest.TestCase):
    def test_tenor_sax_written_a_concert_g(self) -> None:
        ctx = resolve_tone_target_from_pitch_class(
            "A",
            "Tenor saxophone (Bb)",
            is_transposing=True,
        )
        self.assertEqual(ctx["display_written"], "A")
        self.assertEqual(ctx["display_concert"], "G")
        self.assertEqual(ctx["target_note"], "A4")
        self.assertEqual(ctx["analysis_target_note"], "G4")

    def test_alto_sax_written_a_concert_c(self) -> None:
        ctx = resolve_tone_target_from_pitch_class(
            "A",
            "Alto saxophone (Eb)",
            is_transposing=True,
        )
        self.assertEqual(ctx["display_written"], "A")
        self.assertEqual(ctx["display_concert"], "C")

    def test_trumpet_written_a_concert_g(self) -> None:
        ctx = resolve_tone_target_from_pitch_class(
            "A",
            "Bb Trumpet",
            is_transposing=True,
        )
        self.assertEqual(ctx["display_written"], "A")
        self.assertEqual(ctx["display_concert"], "G")

    def test_flute_target_is_concert(self) -> None:
        ctx = resolve_tone_target_from_pitch_class("A", "", is_transposing=False)
        self.assertEqual(ctx["display_concert"], "A")
        self.assertIsNone(ctx["display_written"])
        self.assertEqual(ctx["target_note"], "A4")
        self.assertEqual(ctx["analysis_target_note"], "A4")

    def test_enharmonic_label_parses_sharp_side(self) -> None:
        self.assertEqual(pitch_class_from_option("A#/Bb"), "A#")
        self.assertEqual(pitch_class_from_option("C#/Db"), "C#")

    def test_saved_tenor_sax_stores_written_and_concert(self) -> None:
        ctx = resolve_tone_target_from_pitch_class(
            "A",
            "Tenor saxophone (Bb)",
            is_transposing=True,
        )
        fields = build_tone_take_fields(
            {"instrument": "Saxophone"},
            TonePracticeResult(
                duration_sec=18.0,
                median_note="G4",
                target_note=ctx["target_note"],
                mean_cents=6.0,
                max_cents_drift=10.0,
                pitch_stability_score=80.0,
                volume_stability_score=75.0,
                sustain_seconds=16.0,
            ),
            instrument="Tenor Saxophone",
            transposing_type="Tenor saxophone (Bb)",
            target_note=ctx["target_note"],
        )
        self.assertEqual(fields.get("written_note"), "A4")
        self.assertEqual(fields.get("concert_note"), "G4")
        self.assertEqual(fields.get("target_note"), "A4")

    def test_saved_alto_sax_stores_written_and_concert(self) -> None:
        ctx = resolve_tone_target_from_pitch_class(
            "A",
            "Alto saxophone (Eb)",
            is_transposing=True,
        )
        fields = build_tone_take_fields(
            {"instrument": "Saxophone"},
            TonePracticeResult(
                duration_sec=18.0,
                median_note="C5",
                target_note=ctx["target_note"],
                mean_cents=4.0,
                max_cents_drift=8.0,
                pitch_stability_score=82.0,
                volume_stability_score=76.0,
                sustain_seconds=15.0,
            ),
            instrument="Alto Saxophone",
            transposing_type="Alto saxophone (Eb)",
            target_note=ctx["target_note"],
        )
        self.assertEqual(fields.get("written_note"), "A4")
        self.assertEqual(fields.get("concert_note"), "C5")
        self.assertEqual(fields.get("target_note"), "A4")


if __name__ == "__main__":
    unittest.main()

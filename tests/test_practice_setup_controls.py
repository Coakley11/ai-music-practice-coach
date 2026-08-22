"""Tests for page-local Instrument / Level / Focus quick controls."""

from __future__ import annotations

import unittest

from practice_setup_controls import (
    DEFAULT_INSTRUMENT_OPTIONS,
    LEVEL_OPTIONS,
    _widget_value_for_global,
    focus_options_for_instrument,
    instrument_options_for_upload,
)


class TestPracticeSetupControls(unittest.TestCase):
    def test_widget_sync_never_mutates_global_keys(self) -> None:
        """Prefixed widget pre-fill must not write globals after sidebar widgets exist."""
        session = {
            "instrument": "Saxophone",
            "level": "Advanced",
            "focus": "Tone",
        }
        _widget_value_for_global(
            session,
            "practice_panel::qc_instrument",
            "instrument",
            DEFAULT_INSTRUMENT_OPTIONS,
        )
        _widget_value_for_global(
            session,
            "practice_panel::qc_level",
            "level",
            LEVEL_OPTIONS,
        )
        focus_opts = focus_options_for_instrument("Saxophone")
        _widget_value_for_global(
            session,
            "practice_panel::qc_focus",
            "focus",
            focus_opts,
        )
        self.assertEqual(session["instrument"], "Saxophone")
        self.assertEqual(session["level"], "Advanced")
        self.assertEqual(session["focus"], "Tone")
        self.assertEqual(session["practice_panel::qc_instrument"], "Saxophone")
        self.assertEqual(session["practice_panel::qc_level"], "Advanced")
        self.assertEqual(session["practice_panel::qc_focus"], "Tone")

    def test_widget_sync_clamps_display_without_global_write(self) -> None:
        session = {"instrument": "NotARealInstrument", "level": "Advanced", "focus": "Tone"}
        _widget_value_for_global(
            session,
            "backing_panel::qc_instrument",
            "instrument",
            DEFAULT_INSTRUMENT_OPTIONS,
        )
        self.assertEqual(session["instrument"], "NotARealInstrument")
        self.assertEqual(session["backing_panel::qc_instrument"], "Piano")

    def test_upload_instrument_options_include_four_saxophones(self) -> None:
        from instrument_transposition import saxophone_display_names

        opts = instrument_options_for_upload(DEFAULT_INSTRUMENT_OPTIONS)
        expected = list(saxophone_display_names())
        self.assertEqual(
            expected,
            [
                "Soprano Saxophone",
                "Alto Saxophone",
                "Tenor Saxophone",
                "Baritone Saxophone",
            ],
        )
        for name in expected:
            self.assertIn(name, opts)
        # Family label expanded — do not leave a bare Saxophone-only Upload choice.
        self.assertNotIn("Saxophone", opts)
        # Shared non-sax instruments remain.
        for name in ("Piano", "Guitar", "Flute", "Voice"):
            self.assertIn(name, opts)

    def test_sax_display_names_share_saxophone_focus_options(self) -> None:
        base = focus_options_for_instrument("Saxophone")
        for name in (
            "Soprano Saxophone",
            "Alto Saxophone",
            "Tenor Saxophone",
            "Baritone Saxophone",
        ):
            self.assertEqual(focus_options_for_instrument(name), base)
        # Legacy generic label still works for old saved analyses.
        self.assertIn("Tone", focus_options_for_instrument("Saxophone"))


if __name__ == "__main__":
    unittest.main()

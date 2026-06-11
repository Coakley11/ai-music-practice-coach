"""Tests for page-local Instrument / Level / Focus quick controls."""

from __future__ import annotations

import unittest

from practice_setup_controls import (
    DEFAULT_INSTRUMENT_OPTIONS,
    LEVEL_OPTIONS,
    _widget_value_for_global,
    focus_options_for_instrument,
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


if __name__ == "__main__":
    unittest.main()

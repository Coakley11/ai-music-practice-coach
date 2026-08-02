"""Regression: Practice setup panel after groove selector removal."""

from __future__ import annotations

import unittest

from app_ui import practice_setup_summary_text
from practice_state import resolve_practice_groove_style


def _setup_panel_groove_for_summary(session: dict, *, default_groove: str) -> str:
    """Mirror _render_practice_setup_panel groove path (must not use undefined locals)."""
    return resolve_practice_groove_style(session, default_groove=default_groove)


class TestPracticeSetupPanelGrooveHotfix(unittest.TestCase):
    def test_summary_path_no_name_error_and_uses_resolver(self) -> None:
        ss: dict = {
            "instrument": "Piano",
            "level": "Intermediate",
            "focus": "General",
            "practice_minutes": 40,
        }
        groove = _setup_panel_groove_for_summary(ss, default_groove="Ballad")
        self.assertEqual(groove, "Ballad")
        summary = practice_setup_summary_text(
            instrument="Piano",
            level="Intermediate",
            focus="General",
            groove=groove,
            minutes=40,
        )
        self.assertIn("Ballad", summary)

    def test_backing_studio_override_wins_over_song_default(self) -> None:
        ss = {
            "backing_groove_style": "Jazz swing",
            "practice_groove_style": "Pop groove",
        }
        groove = _setup_panel_groove_for_summary(ss, default_groove="Ballad")
        self.assertEqual(groove, "Jazz swing")
        self.assertEqual(ss["practice_groove_style"], "Jazz swing")

    def test_persisted_practice_groove_when_no_backing_override(self) -> None:
        ss = {"practice_groove_style": "Bossa nova"}
        groove = _setup_panel_groove_for_summary(ss, default_groove="Auto")
        self.assertEqual(groove, "Bossa nova")

    def test_practice_setup_panel_has_no_feel_selectbox(self) -> None:
        from pathlib import Path

        path = Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py"
        source = path.read_text(encoding="utf-8")
        panel_start = source.find("def _render_practice_setup_panel")
        panel_end = source.find("\ndef _", panel_start + 1)
        panel_src = source[panel_start:panel_end]
        self.assertNotIn('key="practice_groove_style"', panel_src)
        self.assertNotIn("Rhythm / groove feel", panel_src)
        self.assertNotIn('practice_groove_style", _groove)', panel_src)
        self.assertIn("groove=_resolved_groove", panel_src)


if __name__ == "__main__":
    unittest.main()

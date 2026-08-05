"""Widget callback signature regressions — Mission backing and Creative tab."""

from __future__ import annotations

import unittest
from typing import Any
from unittest import mock

from music_workflow_mission_backing_click import (
    MISSION_BACKING_CLICK_INTENT_KEY,
    apply_mission_backing_click_intent,
    capture_mission_backing_click_intent,
    peek_mission_backing_click_intent,
)
from widget_callback_diagnostics import validate_callback_kwargs


class TestImprovTabCallbackSignature(unittest.TestCase):
    def test_improv_tab_change_rejects_stale_session_state_kwarg(self) -> None:
        def _on_improv_tab_change() -> None:
            pass

        missing = validate_callback_kwargs(_on_improv_tab_change, {"session_state": {}})
        self.assertEqual(missing, ["session_state"])

    def test_improv_tab_source_has_no_session_state_kwargs(self) -> None:
        from pathlib import Path

        text = Path(__file__).resolve().parents[1].joinpath("improvisation_intelligence_ui.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('kwargs={"session_state": session_state}', text)


class TestMissionBackingClickCallback(unittest.TestCase):
    def test_capture_and_apply_same_as_streamlit_on_click(self) -> None:
        session: dict[str, Any] = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "instrument": "Piano",
            "backing_track_bpm": 100,
            "improv_groove": "Auto",
            "backing_time_signature": "4/4",
            "improv_mission_example": {
                "mission": "Outline chord tones",
                "variant": "normal",
                "chord": "Bb",
                "section": "A",
                "motif": {
                    "notes": ["Bb", "D", "F"],
                    "rhythm": "quarter quarter quarter",
                },
                "abc": "",
                "tab": "",
                "piano_html": "",
                "why": "",
                "practice_steps": [],
                "show_tab": False,
                "show_piano": True,
            },
        }

        def _on_practice_in_backing_jam() -> None:
            capture_mission_backing_click_intent(
                session,
                with_practice_lick=True,
                mission="Outline chord tones",
                cur_chord="Bb",
                section_label="A",
                chord_idx=0,
                song_title="Song",
                concert_key="Em",
                display_key="Em",
            )

        _on_practice_in_backing_jam()
        self.assertIsNotNone(peek_mission_backing_click_intent(session))
        with mock.patch("music_workflow_mission_backing_orchestration.prepare_deferred_mission_backing_handoff", return_value=True):
            self.assertTrue(apply_mission_backing_click_intent(session, st_module=mock.Mock()))
        self.assertIsNone(peek_mission_backing_click_intent(session))

    def test_mission_backing_buttons_use_on_click_not_inline_if(self) -> None:
        from pathlib import Path

        text = Path(__file__).resolve().parents[1].joinpath("improvisation_intelligence_ui.py").read_text(
            encoding="utf-8"
        )
        start = text.index("def _tab_missions(")
        end = text.index("\ndef ", start + 1)
        body = text[start:end]
        self.assertIn("on_click=_on_practice_in_backing_jam", body)
        self.assertNotIn("_open_mission_backing(with_practice_lick=", body)


if __name__ == "__main__":
    unittest.main()

"""Streamlit on_click model: one automatic rerun, pre-widget consume opens Backing."""

from __future__ import annotations

import unittest
from typing import Any
from unittest import mock

from improvisation_missions import MISSION_EXAMPLE_KEY
from music_workflow_mission_backing_click import (
    MISSION_BACKING_CLICK_APPLY_FAILURE_KEY,
    capture_mission_backing_click_intent,
    peek_mission_backing_click_intent,
)
from music_workflow_mission_backing_orchestration import run_pre_widget_mission_handoff_consumers
from music_workflow_pending_backing_handoff import peek_pending_backing_workflow_handoff


def _example_blob() -> dict[str, Any]:
    return {
        "mission": "Outline chord tones",
        "variant": "normal",
        "chord": "Bb",
        "section": "A",
        "motif": {"notes": ["Bb", "D", "F"], "rhythm": "quarter quarter quarter"},
        "abc": "",
        "tab": "",
        "piano_html": "",
        "why": "",
        "practice_steps": [],
        "show_tab": False,
        "show_piano": True,
    }


class TestMissionBackingOneClickCallbackModel(unittest.TestCase):
    def test_callback_capture_pre_widget_single_run_no_extra_rerun(self) -> None:
        session: dict[str, Any] = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "display_key": "Dm",
            "concert_key": "Dm",
            "instrument": "Piano",
            "backing_track_bpm": 100,
            "improv_groove": "Auto",
            "backing_time_signature": "4/4",
            MISSION_EXAMPLE_KEY: _example_blob(),
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
                concert_key="Dm",
                display_key="Dm",
            )

        _on_practice_in_backing_jam()
        self.assertIsNotNone(peek_mission_backing_click_intent(session))

        with mock.patch("music_app_rerun.request_app_rerun", return_value=False) as rerun:
            with mock.patch("music_workflow_activation.activate_workflow_simple") as activate:
                activate.return_value = mock.Mock(ok=True, trace={})
                with mock.patch("mission_backing_alignment.apply_pending_mission_backing_alignment", return_value=True):
                    with mock.patch("backing_context.open_backing_from_creative"):
                        phases = run_pre_widget_mission_handoff_consumers(session)

        rerun.assert_not_called()
        self.assertEqual(phases.get("mission_backing_click_intent"), "applied")
        self.assertEqual(phases.get("backing_handoff"), "applied")
        self.assertEqual(session.get("studio_page"), "backing")
        self.assertIsNone(peek_mission_backing_click_intent(session))
        self.assertIsNone(peek_pending_backing_workflow_handoff(session))

    def test_normalization_failure_surfaces_terminal_failure_not_requeue(self) -> None:
        session: dict[str, Any] = {
            "instrument": "Piano",
            "backing_track_bpm": 100,
            MISSION_EXAMPLE_KEY: {"chord": "Bb", "motif": {}},
        }
        capture_mission_backing_click_intent(
            session,
            with_practice_lick=True,
            mission="M",
            cur_chord="Bb",
            section_label="A",
            chord_idx=0,
            song_title="Song",
            concert_key="Dm",
            display_key="Dm",
        )
        phases = run_pre_widget_mission_handoff_consumers(session)
        self.assertEqual(phases.get("mission_backing_click_intent"), "failed")
        self.assertIsNone(peek_mission_backing_click_intent(session))
        self.assertIn(MISSION_BACKING_CLICK_APPLY_FAILURE_KEY, session)

    def test_missions_ui_does_not_request_explicit_click_rerun(self) -> None:
        from pathlib import Path

        text = Path(__file__).resolve().parents[1].joinpath("improvisation_intelligence_ui.py").read_text(
            encoding="utf-8"
        )
        start = text.index("def _tab_missions(")
        end = text.index("\ndef ", start + 1)
        body = text[start:end]
        self.assertNotIn("request_mission_backing_click_rerun", body)


if __name__ == "__main__":
    unittest.main()

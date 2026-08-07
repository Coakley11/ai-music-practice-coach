"""Two consecutive Practice Mission → Backing Jam handoffs replace context."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from mission_practice_context import MISSION_PRACTICE_CONTEXT_KEY, mark_mission_practice_context_dirty
from music_workflow_mission_backing_click import (
    capture_mission_backing_click_intent,
    peek_mission_backing_click_intent,
)
from music_workflow_pre_widget_bootstrap import (
    PRE_WIDGET_BOOTSTRAP_RAN_KEY,
    run_pre_widget_application_consumers,
)


class TestTwoMissionBackingsSameSession(unittest.TestCase):
    def _session(self) -> dict[str, Any]:
        return {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "instrument": "Guitar",
            "backing_track_bpm": 100,
            "improv_groove": "Auto",
            "backing_time_signature": "4/4",
            "_script_run_seq": 1,
            MISSION_PRACTICE_CONTEXT_KEY: {
                "mission_type": "Target Chord Tones",
                "mission_pick": "Target Chord Tones",
                "chord": {"symbol": "C#m", "section": "Melody A", "chord_index": 0},
            },
            "_mission_backing_handoff_sealed_for_page_change": True,
            "_mission_backing_handoff_confirmed_revision": 99,
        }

    def test_second_click_clears_sealed_state_and_queues_new_intent(self) -> None:
        session = self._session()
        capture_mission_backing_click_intent(
            session,
            with_practice_lick=False,
            mission="Rhythm & Time",
            cur_chord="G#7",
            section_label="Melody B",
            chord_idx=9,
            song_title="Hevenu",
            concert_key="C#",
            display_key="C#",
        )
        self.assertIsNotNone(peek_mission_backing_click_intent(session))
        self.assertNotIn("_mission_backing_handoff_sealed_for_page_change", session)
        intent = peek_mission_backing_click_intent(session)
        assert intent is not None
        self.assertEqual(intent.get("mission"), "Rhythm & Time")
        self.assertEqual(intent.get("cur_chord"), "G#7")

    def test_two_consecutive_apply_intent_cycles(self) -> None:
        session = self._session()

        def _click(mission: str, chord: str, sec: str, idx: int) -> None:
            capture_mission_backing_click_intent(
                session,
                with_practice_lick=False,
                mission=mission,
                cur_chord=chord,
                section_label=sec,
                chord_idx=idx,
                song_title="Hevenu",
                concert_key="C#",
                display_key="C#",
            )
            session.pop(PRE_WIDGET_BOOTSTRAP_RAN_KEY, None)
            with patch(
                "music_workflow_mission_backing_orchestration.prepare_deferred_mission_backing_handoff",
                return_value=True,
            ):
                with patch(
                    "music_workflow_pending_backing_handoff.consume_pending_backing_workflow_handoff",
                    return_value="applied",
                ):
                    phases = run_pre_widget_application_consumers(session, st=MagicMock())
            self.assertIn(phases.get("mission_backing_click_intent"), ("applied", "failed"))

        _click("Target Chord Tones", "C#m", "Melody A", 0)
        mark_mission_practice_context_dirty(session)
        session[MISSION_PRACTICE_CONTEXT_KEY] = {
            "mission_type": "Target Chord Tones",
            "chord": {"symbol": "C#m"},
        }
        _click("Rhythm & Time", "A", "Melody B", 14)
        intent = peek_mission_backing_click_intent(session)
        self.assertIsNone(intent)


if __name__ == "__main__":
    unittest.main()

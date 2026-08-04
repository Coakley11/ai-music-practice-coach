"""Analyze This Take handoff to Upload Analysis."""

from __future__ import annotations

import unittest

from mission_upload_handoff import handoff_mission_take_to_upload_analysis


class TestMissionUploadHandoff(unittest.TestCase):
    def test_handoff_preloads_take_and_leaves_criteria_unlocked(self) -> None:
        session: dict = {
            "song": "Tune",
            "improv_active_mission": "Develop one motif",
            "improv_mission_pick": "Develop one motif",
            "improv_mission_chord_options": ["Ab7"],
            "ii_selected_chord_index": 0,
            "ii_selected_chord": "Ab7",
            "improv_mission_evaluation_focus": "Melodic development",
        }
        audio = b"RIFF" + b"\x00" * 40 + b"data" + b"\x00" * 100
        handoff_mission_take_to_upload_analysis(
            session,
            audio_bytes=audio,
            filename="take.wav",
            source="upload",
        )
        self.assertIsNotNone(session.get("_analysis_prepared_upload"))
        self.assertFalse(session.get("analysis_criteria_locked"))
        self.assertTrue(session.get("_mission_upload_is_file_take"))
        self.assertFalse(session.get("_mission_upload_is_live_take"))


if __name__ == "__main__":
    unittest.main()

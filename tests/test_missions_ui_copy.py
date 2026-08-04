"""Missions tab must not repeat mission/chord/instrument metadata block."""

from __future__ import annotations

import inspect
import unittest

import improvisation_intelligence_ui as ui


class TestMissionsUiCopy(unittest.TestCase):
    def test_target_chord_metadata_card_removed(self) -> None:
        src = inspect.getsource(ui._tab_missions)
        self.assertNotIn("ui-card-sub", src)
        self.assertNotIn("Target chord", src)

    def test_recording_studio_single_compact_summary(self) -> None:
        from mission_upload_recording_ui import render_mission_live_recording_studio

        src = inspect.getsource(render_mission_live_recording_studio)
        self.assertIn("Mission:**", src)
        self.assertEqual(src.count("Evaluation focus"), 0)


if __name__ == "__main__":
    unittest.main()

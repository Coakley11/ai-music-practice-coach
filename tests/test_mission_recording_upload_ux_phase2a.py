"""Phase 2A UX — optional recording expander, evaluation focus, capture paths."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from mission_evaluation_focus import (
    EVALUATION_FOCUS_OPTIONS,
    MISSION_EVALUATION_FOCUS_KEY,
    default_mission_recording_expander_expanded,
)
from mission_practice_context import (
    MISSION_RECORDING_STUDIO_ENGAGED_KEY,
    enrich_analysis_context,
    mission_capture_allowed,
    recording_context_stale_warning,
    seal_recording_context,
)
from mission_upload_recording_ui import (
    MISSION_RECORDING_EXPANDER_LABEL,
    should_show_exact_chord_panel,
)


class TestMissionRecordingUploadUx(unittest.TestCase):
    def test_expander_closed_by_default(self) -> None:
        self.assertFalse(default_mission_recording_expander_expanded())
        self.assertIn("optional", MISSION_RECORDING_EXPANDER_LABEL.lower())

    def test_exact_chord_panel_deferred_until_studio_engaged(self) -> None:
        session = {
            "improv_active_mission": "Develop a Motif",
            "improv_mission_chord_options": ["Ab7"],
            "ii_selected_chord_index": 0,
        }
        self.assertFalse(should_show_exact_chord_panel(session))
        session[MISSION_RECORDING_STUDIO_ENGAGED_KEY] = True
        self.assertTrue(should_show_exact_chord_panel(session))

    def test_exact_chord_panel_hidden_on_upload_analysis_handoff(self) -> None:
        session = {
            "improv_active_mission": "Develop one motif for the entire solo",
            "improv_mission_chord_options": ["Ab7"],
            "ii_selected_chord_index": 0,
            MISSION_RECORDING_STUDIO_ENGAGED_KEY: True,
            "_mission_upload_analysis_handoff": True,
        }
        self.assertFalse(should_show_exact_chord_panel(session))

    def test_heavy_backing_panel_not_called_when_not_engaged(self) -> None:
        session = {"improv_active_mission": "Motif", "improv_mission_chord_options": ["C"]}
        with patch("mission_upload_recording_ui.render_mission_live_recording_studio") as studio:

            class _St:
                def expander(self, *a, **k):
                    return self

                def caption(self, *a, **k): ...

                def button(self, *a, **k):
                    return False

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

            from mission_upload_recording_ui import render_mission_recording_upload_expander

            render_mission_recording_upload_expander(_St(), session)
            studio.assert_not_called()

    def test_analysis_context_no_example_matching_by_default(self) -> None:
        session = {
            "improv_active_mission": "Develop a Motif",
            "improv_mission_chord_options": ["Ab7"],
            "ii_selected_chord_index": 0,
            "ii_selected_chord": "Ab7",
            MISSION_EVALUATION_FOCUS_KEY: "Melodic development",
            "improv_mission_example": {"motif": {"notes": ["C4", "Eb4"]}},
        }
        out = enrich_analysis_context(session, {})
        self.assertFalse(out.get("score_against_example"))
        self.assertTrue(out.get("optional_mission_example_only"))

    def test_upload_and_live_paths_are_distinct_modes(self) -> None:
        session = {
            "improv_active_mission": "Motif",
            "improv_mission_chord_options": ["G"],
            "ii_selected_chord_index": 0,
        }
        session["mission_upload_capture_mode"] = "upload"
        ok_upload, _ = mission_capture_allowed(
            session, require_mission_workflow=True, capture_path="upload"
        )
        self.assertTrue(ok_upload)
        session["mission_upload_capture_mode"] = "live"
        ok_live, _ = mission_capture_allowed(
            session, require_mission_workflow=True, capture_path="live"
        )
        self.assertTrue(ok_live)

    def test_mismatch_still_blocks_analysis(self) -> None:
        from mission_practice_context import MISSION_BACKING_SOUNDING_CHORD_KEY

        session = {
            "improv_active_mission": "Motif",
            "improv_mission_chord_options": ["Am7"],
            "ii_selected_chord_index": 0,
            "ii_selected_chord": "Am7",
            MISSION_BACKING_SOUNDING_CHORD_KEY: "Dm7",
        }
        ok, msg = mission_capture_allowed(
            session, require_mission_workflow=True, capture_path="analysis"
        )
        self.assertFalse(ok)
        self.assertIn("Am7", msg)

    def test_upload_caption_wording_module(self) -> None:
        import inspect
        from mission_upload_recording_ui import render_mission_live_recording_studio

        src = inspect.getsource(render_mission_live_recording_studio)
        self.assertIn("Upload Analysis", src)


if __name__ == "__main__":
    unittest.main()

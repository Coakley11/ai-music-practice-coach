"""Mission context isolation, pitch spelling, upload route lock tests."""

from __future__ import annotations

import struct
import unittest
from typing import Any
from unittest.mock import patch

from improvisation_motif import flatten_section_map
from mission_pitch_spelling import chord_coach_insight_for_mission, coaching_reference_for_mission_chord
from mission_workflow_context import reconcile_missions_workflow_context, resolve_missions_section_map
from pending_upload_route_precedence import (
    PENDING_UPLOAD_ROUTE_LOCK_KEY,
    guard_studio_page_write_for_pending_upload,
    pending_upload_should_restore_analysis_page,
)
from studio_nav_state import write_canonical_studio_nav_state


def _improv_ctx_hevenu() -> Any:
    from improvisation_intelligence import ImprovSessionContext

    sections = {
        "Melody A": ["Dm", "Gm", "A7", "Dm", "Bb", "A7", "Dm", "Dm"],
        "Melody B": ["Dm", "Gm", "A7", "Dm", "Bb", "A7", "Dm", "Dm"],
    }
    return ImprovSessionContext(
        song_title="Hevenu Shalom Aleichem",
        artist="Traditional",
        key_center="Dm",
        display_key="Dm",
        instrument="Guitar",
        level="Intermediate",
        focus="Improvisation",
        sections=sections,
        bpm=72,
        progression_flat=flatten_section_map(list(sections.items())),
        section_order=list(sections.keys()),
    )


class TestMissionWorkflowIsolation(unittest.TestCase):
    def test_missions_ignores_entry_jam_generated_sections(self) -> None:
        session: dict[str, Any] = {
            "improv_generated_sections": {
                "Head (Jazz Swing)": ["Am7", "D7", "Gmaj7", "C7"],
                "Bridge (Jazz Swing)": ["Em7", "A7", "Dm7", "G7"],
            },
            "home_sections": _improv_ctx_hevenu().sections,
        }
        ctx = _improv_ctx_hevenu()
        section_map, owner = resolve_missions_section_map(session, ctx)
        labels = [l for l, _ in section_map]
        self.assertIn("Melody A", labels)
        self.assertNotIn("Head (Jazz Swing)", labels)
        self.assertEqual(owner, "catalog_song_sections")

    def test_reconcile_clears_stale_jazz_example(self) -> None:
        from improvisation_missions import MISSION_EXAMPLE_KEY

        session: dict[str, Any] = {
            "improv_generated_sections": {"Head (Jazz Swing)": ["E7"]},
            "home_sections": _improv_ctx_hevenu().sections,
            MISSION_EXAMPLE_KEY: {
                "chord": "Ab7",
                "mission": "Develop one motif",
                "section": "Head (Jazz Swing)",
                "motif": {"notes": ["Ab"]},
            },
            "improv_style": "Jazz Swing",
        }
        ctx = _improv_ctx_hevenu()
        section_map, report = reconcile_missions_workflow_context(
            session,
            ctx,
            mission="Develop one motif",
            cur_chord="A7",
            section_label="Melody A",
        )
        self.assertTrue(any("Melody" in l for l, _ in section_map))
        self.assertNotIn(MISSION_EXAMPLE_KEY, session)


class TestMissionPitchSpelling(unittest.TestCase):
    def test_e7_mixolydian_uses_sharps(self) -> None:
        ref = coaching_reference_for_mission_chord("E7", song_display_key="Ab")
        self.assertEqual(ref, "E")
        insight = chord_coach_insight_for_mission("E7", song_display_key="Ab")
        self.assertIn("G#", " ".join(insight.chord_tones))
        mix = next((s for s in (insight.scale_suggestions or []) if "Mixolydian" in s.label), None)
        self.assertIsNotNone(mix)
        assert mix is not None
        self.assertIn("F#", " ".join(mix.notes))
        self.assertNotIn("Gb", " ".join(mix.notes))


class TestPendingUploadRouteLock(unittest.TestCase):
    def test_guard_blocks_creative_overwrite_while_locked(self) -> None:
        env = {
            "take_id": "t1",
            "analysis_status": "prepared",
            "navigation": {"resume_upload_analysis": True, "studio_page": "analysis"},
        }
        session: dict[str, Any] = {
            "studio_page": "analysis",
            "pending_upload_analysis_envelope": env,
            PENDING_UPLOAD_ROUTE_LOCK_KEY: True,
        }
        guarded = guard_studio_page_write_for_pending_upload(session, "creative", reason="workspace_restore")
        self.assertEqual(guarded, "analysis")
        write_canonical_studio_nav_state(session, "creative", reason="workspace_restore")
        self.assertEqual(str(session.get("studio_page")), "analysis")

    def test_payload_pins_analysis_when_route_lock(self) -> None:
        from pending_upload_route_precedence import (
            PENDING_UPLOAD_ROUTE_LOCK_KEY,
            apply_pending_upload_to_save_payload,
        )

        session: dict[str, Any] = {
            PENDING_UPLOAD_ROUTE_LOCK_KEY: True,
            "pending_upload_analysis_envelope": {
                "take_id": "t1",
                "analysis_status": "prepared",
                "navigation": {"resume_upload_analysis": True},
            },
        }
        state: dict[str, Any] = {"music_workspace_state": {"studio_page": "creative"}, "core": {}}
        apply_pending_upload_to_save_payload(session, state)
        self.assertEqual(state["music_workspace_state"]["studio_page"], "analysis")
        self.assertTrue(state["music_workspace_state"]["pending_upload_route"]["route_lock"])
        session = {
            "pending_upload_analysis_envelope": {
                "take_id": "x",
                "analysis_status": "prepared",
                "navigation": {"resume_upload_analysis": True},
            }
        }
        self.assertTrue(pending_upload_should_restore_analysis_page(session, None))


if __name__ == "__main__":
    unittest.main()

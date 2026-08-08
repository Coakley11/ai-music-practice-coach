"""Acceptance boundaries A–D: metadata, key identity, jam return, mission sidebar."""

from __future__ import annotations

import unittest
import uuid

from backing_context import _entry_jam_context_from_owner_snapshot
from generated_workflow_artifact import GeneratedWorkflowArtifactSnapshot
from generated_jam_key_context import (
    activate_generated_jam_key_ownership,
    deactivate_generated_jam_key_ownership,
    refresh_generated_jam_key_context_from_blob,
)
from musical_context_authority import resolve_authoritative_practice_key
from music_workflow_state_store import (
    ActiveWorkflowPointer,
    KeyAuthority,
    WorkflowStateBlob,
    save_workflow_blob,
    set_active_workflow_pointer,
)


def _bossa_snapshot(*, tonic: str = "C", mode: str = "major") -> GeneratedWorkflowArtifactSnapshot:
    return GeneratedWorkflowArtifactSnapshot(
        workflow_owner="jam_session_generator",
        workflow_session_id=str(uuid.uuid4()),
        artifact_id=str(uuid.uuid4()),
        artifact_revision=1,
        generation_request_token="t",
        generation_sequence=1,
        control_fingerprint="fp",
        practice_tonic=tonic,
        practice_mode=mode,
        style="Bossa Nova",
        mood="Bright",
        groove="",
        intensity="Medium",
        bpm=110,
        meter="4/4",
        level="Beginner",
        section_map={"A": ["Dm7", "G7", "Cmaj7", "Cmaj7"]},
        selected_scope="Full song",
        selected_section_ids=["A"],
        progression=["Dm7", "G7", "Cmaj7", "Cmaj7"],
        backing_configuration={},
        exact_return_destination="creative",
        entry_mode="Jam Session Generator",
        bound_pick_key="",
    )


class JamAcceptanceBoundaryTests(unittest.TestCase):
    def test_bossa_bright_beginner_no_jewish_ballad_groove_badge(self) -> None:
        session = {
            "improv_groove": "Jewish ballad",
            "improv_difficulty": "Beginner",
        }
        ctx = _entry_jam_context_from_owner_snapshot(session, _bossa_snapshot())
        self.assertNotIn("Jewish", str(ctx.groove_intensity or ""))
        self.assertNotIn("Jewish", str(ctx.groove or ""))

    def test_eb_major_blob_projects_eb_not_d_sharp_minor(self) -> None:
        sid = str(uuid.uuid4())
        session: dict = {
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_style": "Bossa Nova",
            "improv_jam_key": "Eb",
            "display_key": "D#m",
            "concert_key": "D#m",
            "active_catalog_pick_key": "Jewish|Hevenu",
            "improv_intelligence_tab": "Entry & Jam",
        }
        blob = WorkflowStateBlob(
            workflow_owner="jam_session_generator",
            workflow_session_id=sid,
            keys=KeyAuthority(
                practice_tonic="Eb",
                practice_mode="major",
                original_tonic="Eb",
                original_mode="major",
            ),
            section_map={"A": ["Fm7", "Bb7", "Ebmaj7", "Ebmaj7"]},
            style="Bossa Nova",
        )
        save_workflow_blob(session, blob, source="test")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="jam_session_generator", workflow_session_id=sid),
            source="test",
        )
        activate_generated_jam_key_ownership(session, entry_mode="Jam Session Generator")
        refresh_generated_jam_key_context_from_blob(session)
        self.assertEqual(str(session.get("concert_key") or ""), "Eb")
        raw = session.get("_generated_jam_key_context") or {}
        self.assertEqual(raw.get("practice_mode"), "major")
        self.assertEqual(raw.get("practice_tonic"), "Eb")

    def test_mission_catalog_ignores_stale_generated_display_key(self) -> None:
        from music_workflow_song_practice import song_based_blob_session_id

        session = {
            "active_catalog_pick_key": "Jewish|Hevenu",
            "improv_intelligence_tab": "Missions",
            "studio_page": "creative",
            "display_key": "D#m",
            "concert_key": "D#m",
            "practice_concert_key": "Dm",
        }
        sid = song_based_blob_session_id(session)
        blob = WorkflowStateBlob(
            workflow_owner="song_based_improvisation",
            workflow_session_id=sid,
            keys=KeyAuthority(
                practice_tonic="D",
                practice_mode="minor",
                original_tonic="D",
                original_mode="minor",
            ),
            section_map={"Verse": ["Dm", "Gm", "A7", "Dm"]},
        )
        save_workflow_blob(session, blob, source="test")
        pk = resolve_authoritative_practice_key(session)
        self.assertEqual(pk.practice_mode, "minor")
        self.assertEqual(pk.practice_tonic, "D")

    def test_deactivate_generated_restores_song_practice_key(self) -> None:
        session = {
            "display_key": "D#m",
            "concert_key": "D#m",
            "_song_practice_key_snapshot": {
                "display_key": "Dm",
                "concert_key": "Dm",
                "practice_concert_key": "Dm",
            },
            "_generated_jam_key_context": {"key_owner": "jam_session_generator", "practice_tonic": "Eb"},
            "_generated_jam_key_owner_active": True,
        }
        self.assertTrue(deactivate_generated_jam_key_ownership(session, pre_widget=True))
        self.assertEqual(str(session.get("concert_key") or ""), "Dm")


if __name__ == "__main__":
    unittest.main()

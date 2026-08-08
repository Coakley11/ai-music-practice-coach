"""WorkflowKeyIdentity projection — generated jam, missions reclaim, notation staff keys."""

from __future__ import annotations

import unittest
import uuid

from backing_musical_state import resolve_current_backing_musical_state
from creative_key_sync import creative_entry_concert_key
from generated_workflow_artifact import GeneratedWorkflowArtifactSnapshot, BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY
from music_workflow_state_store import (
    ActiveWorkflowPointer,
    KeyAuthority,
    WorkflowStateBlob,
    get_workflow_blob,
    save_workflow_blob,
    set_active_workflow_pointer,
)
from musical_context_authority import format_practice_concert_key_line, resolve_authoritative_practice_key
from sidebar_key_identity import resolve_sidebar_key_identity
from workflow_key_identity import resolve_practice_key_identity_for_ui


def _jam_blob(session: dict, *, tonic: str, mode: str, sid: str | None = None) -> str:
    sid = sid or str(uuid.uuid4())
    blob = WorkflowStateBlob(
        workflow_owner="jam_session_generator",
        workflow_session_id=sid,
        keys=KeyAuthority(
            practice_tonic=tonic,
            practice_mode=mode,
            original_tonic=tonic,
            original_mode=mode,
        ),
        section_map={"A": ["Dmaj7", "G7", "Em7", "A7"]},
        style="Bossa Nova",
    )
    save_workflow_blob(session, blob, source="test")
    set_active_workflow_pointer(
        session,
        ActiveWorkflowPointer(workflow_owner="jam_session_generator", workflow_session_id=sid),
        source="test",
    )
    snap = GeneratedWorkflowArtifactSnapshot(
        workflow_owner="jam_session_generator",
        workflow_session_id=sid,
        artifact_id=str(uuid.uuid4()),
        artifact_revision=1,
        generation_request_token="t",
        generation_sequence=1,
        control_fingerprint="fp",
        practice_tonic=tonic,
        practice_mode=mode,
        style="Bossa Nova",
        mood="Bright",
        section_map=blob.section_map,
        progression=["Dmaj7"],
        entry_mode="Jam Session Generator",
    )
    session[BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY] = snap.to_dict()
    return sid


class WorkflowKeyIdentityProjectionTests(unittest.TestCase):
    def test_generated_d_major_not_catalog_d_minor_on_backing(self) -> None:
        session: dict = {
            "studio_page": "backing",
            "improv_entry_mode": "Jam Session Generator",
            "improv_intelligence_tab": "Entry & Jam",
            "active_catalog_pick_key": "Jewish|Hevenu",
            "display_key": "Dm",
            "concert_key": "Dm",
            "improv_jam_key": "D",
        }
        session["practice_key_mode"] = "fixed"
        session["fixed_practice_key"] = "D"
        _jam_blob(session, tonic="D", mode="major")
        self.assertEqual(creative_entry_concert_key(session), "D")
        ident = resolve_sidebar_key_identity(session)
        self.assertEqual(ident.practice_mode, "major")
        self.assertEqual(ident.selector_token, "D")
        line = format_practice_concert_key_line(session)
        self.assertIn("major", line.lower())
        self.assertNotIn("minor", line.lower())

    def test_missions_reclaim_song_d_minor_not_generated_eb(self) -> None:
        pick = "Jewish|Hevenu"
        session: dict = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "active_catalog_pick_key": pick,
            "display_key": "Eb",
            "concert_key": "Eb",
        }
        song_sid = pick
        song_blob = WorkflowStateBlob(
            workflow_owner="song_based_improvisation",
            workflow_session_id=song_sid,
            keys=KeyAuthority(
                practice_tonic="D",
                practice_mode="minor",
                original_tonic="D",
                original_mode="minor",
            ),
            section_map={"Verse": ["Dm", "Gm", "A7", "Dm"]},
        )
        save_workflow_blob(session, song_blob, source="test")
        mission_sid = f"mission|catalog|{pick}"
        mission_blob = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id=mission_sid,
            keys=KeyAuthority(
                practice_tonic="Eb",
                practice_mode="minor",
                original_tonic="D",
                original_mode="minor",
            ),
            section_map={"Verse": ["Ebm"]},
        )
        save_workflow_blob(session, mission_blob, source="test")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id=mission_sid),
            source="test",
        )
        ident = resolve_practice_key_identity_for_ui(session)
        self.assertIsNotNone(ident)
        assert ident is not None
        self.assertEqual(ident.practice_tonic, "D")
        self.assertEqual(ident.practice_mode, "minor")
        pk = resolve_authoritative_practice_key(session)
        self.assertEqual(pk.practice_tonic, "D")
        self.assertEqual(pk.practice_mode, "minor")

    def test_mission_notation_staff_key_signatures(self) -> None:
        from harmonic_spelling import mission_notation_staff_key
        from improvisation_missions import abc_staff_key_matches_concert

        cases = [
            ("Dm", "Dm"),
            ("Ebm", "Ebm"),
            ("Fm", "Fm"),
            ("Bm", "Bm"),
        ]
        for concert, staff in cases:
            resolved = mission_notation_staff_key(song_concert_key=concert, song_display_key=concert)
            self.assertEqual(resolved, staff, concert)


if __name__ == "__main__":
    unittest.main()

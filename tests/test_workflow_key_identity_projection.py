"""WorkflowKeyIdentity projection — generated jam, missions reclaim, notation staff keys."""

from __future__ import annotations

import unittest
import uuid
from unittest.mock import MagicMock

from backing_musical_state import resolve_current_backing_musical_state
from creative_key_sync import creative_entry_concert_key, prepare_backing_context_sidebar_display_key
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
        self.assertEqual(ident.practice_mode, "major")
        self.assertNotIn("minor", line.lower())

    def test_jam_c_major_sidebar_not_fixed_catalog_c_minor_on_backing(self) -> None:
        session: dict = {
            "studio_page": "backing",
            "improv_entry_mode": "Jam Session Generator",
            "improv_intelligence_tab": "Entry & Jam",
            "active_catalog_pick_key": "Jewish|Hevenu",
            "display_key": "Eb",
            "concert_key": "C",
            "improv_jam_key": "C",
            "display_key_change_source": "sidebar_practice_key",
        }
        session["practice_key_mode"] = "fixed"
        session["fixed_practice_key"] = "D"
        _jam_blob(session, tonic="C", mode="major")
        st = MagicMock()
        options = prepare_backing_context_sidebar_display_key(st, session)
        self.assertEqual(session.get("concert_key"), "C")
        self.assertIn("C", options)
        ident = resolve_practice_key_identity_for_ui(session)
        self.assertIsNotNone(ident)
        assert ident is not None
        self.assertEqual(ident.practice_mode, "major")
        self.assertEqual(ident.practice_tonic, "C")
        state = resolve_current_backing_musical_state(session)
        self.assertEqual(state.practice_concert_key, "C")

    def test_missions_live_practice_key_owns_when_song_blob_missing(self) -> None:
        session: dict = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "Eb",
            "display_key": "Dm",
            "concert_key": "Dm",
            "active_catalog_pick_key": "hevenu_shalom",
        }
        ident = resolve_practice_key_identity_for_ui(session)
        self.assertIsNotNone(ident)
        assert ident is not None
        self.assertEqual(ident.practice_tonic, "D")
        self.assertEqual(ident.practice_mode, "minor")
        self.assertEqual(ident.practice_key_token.lower(), "dm")
        self.assertEqual(ident.workflow_owner, "song_based_improvisation")
        self.assertNotEqual(ident.source, "active_workflow_blob")
        pk = resolve_authoritative_practice_key(session)
        self.assertEqual(pk.practice_mode, "minor")
        self.assertEqual(pk.practice_key_token.lower(), "dm")

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
        from improvisation_missions import abc_staff_key_matches_concert, build_mission_notation_abc, parse_abc_k_field
        from improvisation_motif import _abc_key_header

        cases = [
            ("Dm", "Dm"),
            ("Ebm", "Ebm"),
            ("Fm", "Fm"),
            ("Bm", "Bm"),
        ]
        for concert, staff in cases:
            resolved = mission_notation_staff_key(song_concert_key=concert, song_display_key=concert)
            self.assertEqual(resolved, staff, concert)

        empty_motif = {"notes": ["C"], "rhythm": ["q"]}
        for token in ("C", "D", "Dm", "Bm", "Fm", "Ebm", "Dbm", "C#m"):
            k_hdr = _abc_key_header(token)
            abc = build_mission_notation_abc(empty_motif, mission="t", key_center=token, bpm=100)
            k_field = parse_abc_k_field(abc)
            self.assertTrue(
                abc_staff_key_matches_concert(abc, token),
                f"abc K mismatch for {token}: {k_field} vs hdr {k_hdr}",
            )
            self.assertEqual(k_hdr.lower(), str(k_field or "").lower()[: len(k_hdr)], token)
        # Dbm / C#m must not collapse to stale K:c (C minor) OR bare major K:Db / K:C#.
        self.assertNotEqual(_abc_key_header("Dbm").lower(), "c")
        self.assertNotEqual(_abc_key_header("C#m").lower(), "c")
        self.assertNotEqual(_abc_key_header("Dbm"), "Db")
        self.assertNotEqual(_abc_key_header("C#m"), "C#")
        self.assertIn(_abc_key_header("Dbm").lower(), {"dbm", "dbmin"})
        self.assertIn(_abc_key_header("C#m").lower(), {"c#m", "c#min"})
        # Ebm previously emitted bare Eb (ambiguous major); require explicit minor.
        self.assertTrue(
            _abc_key_header("Ebm").lower().endswith("m"),
            f"Ebm header must mark minor, got {_abc_key_header('Ebm')!r}",
        )


if __name__ == "__main__":
    unittest.main()

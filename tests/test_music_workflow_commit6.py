"""Commit 6 — durability, bootstrap fail-closed, mission session ID, persist confirm."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from music_workflow_canonical_persistence import apply_workflow_state_canonical_slice
from music_workflow_mission_bootstrap import ensure_mission_blob_from_song
from music_workflow_mission_session import mission_blob_session_id
from music_workflow_mutation import update_active_practice_key
from music_workflow_persist_confirmed import note_persist_confirmed
from music_workflow_persist_lifecycle import (
    WORKFLOW_PERSIST_PENDING_KEY,
    confirm_workflow_persist_after_cloud_save,
    request_workflow_canonical_persist,
    resolve_workflow_persist_reason,
)
from music_workflow_state_store import (
    ActiveWorkflowPointer,
    KeyAuthority,
    WorkflowStateBlob,
    get_workflow_blob,
    save_workflow_blob,
    set_active_workflow_pointer,
)


def _session(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"_suite_active_workspace_id": "daniel"}
    base.update(extra)
    return base


class TestMissionBootstrapFailClosed(unittest.TestCase):
    def test_never_c_major_on_failed_catalog(self) -> None:
        session = _session(active_catalog_pick_key="missing_song_xyz", display_key="D")
        with patch("songs.music_source.resolve_catalog_song_for_pick", return_value=(None, False)):
            blob = ensure_mission_blob_from_song(session, mission_blob_session_id(session))
        self.assertIsNone(blob)

    def test_ipanema_from_song_blob_f_major(self) -> None:
        session = _session(active_catalog_pick_key="girl_from_ipanema", display_key="D")
        song = WorkflowStateBlob(
            workflow_owner="song_based_improvisation",
            workflow_session_id="girl_from_ipanema",
            keys=KeyAuthority(practice_tonic="F", practice_mode="major"),
        )
        save_workflow_blob(session, song, source="t")
        m = ensure_mission_blob_from_song(session, mission_blob_session_id(session))
        assert m is not None
        self.assertEqual(m.keys.practice_tonic, "F")

    def test_mission_session_id_format(self) -> None:
        session = _session(active_catalog_pick_key="hevenu")
        self.assertEqual(mission_blob_session_id(session), "mission|catalog|hevenu")


class TestKeyChangePersistRequest(unittest.TestCase):
    def test_material_key_change_requests_persist(self) -> None:
        session = _session()
        blob = WorkflowStateBlob(
            workflow_owner="style_jam",
            workflow_session_id="Bossa",
            keys=KeyAuthority(practice_tonic="F", practice_mode="major"),
            section_map={"A": ["F", "C"]},
        )
        save_workflow_blob(session, blob, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id="Bossa"),
            source="t",
        )
        update_active_practice_key(session, "D", source="on_improv_style_key_change")
        self.assertIn(WORKFLOW_PERSIST_PENDING_KEY, session)
        self.assertEqual(
            resolve_workflow_persist_reason(session, fallback="autosave"),
            "material_workflow_key_change",
        )

    def test_noop_key_no_pending(self) -> None:
        session = _session()
        blob = WorkflowStateBlob(
            workflow_owner="style_jam",
            workflow_session_id="Bossa",
            keys=KeyAuthority(practice_tonic="D", practice_mode="major"),
        )
        save_workflow_blob(session, blob, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id="Bossa"),
            source="t",
        )
        update_active_practice_key(session, "D", source="on_improv_style_key_change")
        self.assertNotIn(WORKFLOW_PERSIST_PENDING_KEY, session)


class TestPersistConfirmExactMatch(unittest.TestCase):
    def test_mismatch_request_id_not_cleared(self) -> None:
        session = _session()
        rid = request_workflow_canonical_persist(
            session,
            "material_workflow_key_change",
            expected_revision=3,
            expected_fingerprint="abc123",
        )
        save_state = {
            "creative_workspace_state": {
                "music_workflow_state_v1": {
                    "persist_request": {"persist_request_id": "other-id", "persist_requested_revision": 3, "persist_requested_fingerprint": "abc123"},
                }
            }
        }
        confirm_workflow_persist_after_cloud_save(session, saved_cloud=True, save_state=save_state)
        self.assertIn(WORKFLOW_PERSIST_PENDING_KEY, session)
        self.assertNotEqual(rid, "other-id")

    def test_matching_request_clears(self) -> None:
        session = _session()
        request_workflow_canonical_persist(
            session,
            "material_workflow_key_change",
            expected_revision=2,
            expected_fingerprint="fp1",
        )
        pend = session[WORKFLOW_PERSIST_PENDING_KEY]
        save_state = {
            "creative_workspace_state": {
                "music_workflow_state_v1": {"persist_request": dict(pend)},
            }
        }
        confirm_workflow_persist_after_cloud_save(session, saved_cloud=True, save_state=save_state)
        self.assertNotIn(WORKFLOW_PERSIST_PENDING_KEY, session)


class TestCanonicalRestoreWorkspaceRevision(unittest.TestCase):
    def test_older_cloud_workspace_does_not_overwrite_confirmed_live(self) -> None:
        session = _session()
        live = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="mission|catalog|h",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
            selected_chord_symbol="B",
        )
        save_workflow_blob(session, live, source="t")
        note_persist_confirmed(
            session,
            request_id="r1",
            owner="mission_jam",
            session_id="mission|catalog|h",
            context_revision=1,
            material_fingerprint=str(live.material_fingerprint or ""),
            workspace_revision=20,
        )
        stale = live.to_dict()
        stale["selected_chord_symbol"] = "Ab"
        nested = {
            "schema_version": 2,
            "saved_workspace_revision": 10,
            "store": {"schema_version": 1, "blobs": {f"mission_jam|mission|catalog|h": stale}},
            "active_pointer": {
                "workflow_owner": "mission_jam",
                "workflow_session_id": "mission|catalog|h",
                "context_revision": 1,
            },
        }
        apply_workflow_state_canonical_slice(session, nested)
        kept = get_workflow_blob(session, "mission_jam", "mission|catalog|h")
        assert kept is not None
        self.assertEqual(kept.selected_chord_symbol, "B")


class TestKeyReconcileInvalidatesExample(unittest.TestCase):
    def test_mission_key_change_clears_example_fp(self) -> None:
        session = _session(active_catalog_pick_key="hevenu")
        blob = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="mission|catalog|hevenu",
            keys=KeyAuthority(practice_tonic="Eb", practice_mode="minor"),
            section_map={"A": ["Ebm", "Bb"]},
            selected_chord_index=1,
            selected_chord_symbol="Bb",
            example_fingerprint="oldexample",
            backing_handoff_chord="Bb",
        )
        save_workflow_blob(session, blob, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id="mission|catalog|hevenu"),
            source="t",
        )
        update_active_practice_key(session, "Em", source="sidebar_missions", transpose_progression=True)
        loaded = get_workflow_blob(session, "mission_jam", "mission|catalog|hevenu")
        assert loaded is not None
        self.assertEqual(loaded.keys.practice_tonic, "E")
        self.assertEqual(loaded.example_fingerprint, "")
        self.assertEqual(loaded.backing_handoff_chord, "")


if __name__ == "__main__":
    unittest.main()

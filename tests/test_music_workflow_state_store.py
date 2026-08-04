"""Phase 3 Commit 1 — MusicWorkflowStateStore foundation tests."""

from __future__ import annotations

import copy
import unittest
from typing import Any

from music_workflow_canonical_persistence import (
    apply_workflow_state_canonical_slice,
    gather_workflow_state_canonical_slice,
    should_gather_workflow_state_to_canonical,
)
from music_workflow_compatibility import build_workflow_blob_from_legacy
from music_workflow_dev_panel import build_workflow_architecture_snapshot
from music_workflow_state_store import (
    MUSIC_ACTIVE_WORKFLOW_KEY,
    MUSIC_WORKFLOW_STATE_STORE_KEY,
    ActiveWorkflowPointer,
    KeyAuthority,
    WorkflowStateBlob,
    get_active_workflow_pointer,
    get_music_workflow_state_store,
    get_workflow_blob,
    save_workflow_blob,
    set_active_workflow_pointer,
    validate_active_workflow_pointer,
    workflow_cache_identity,
)


class TestWorkflowStoreIsolation(unittest.TestCase):
    def test_multiple_blobs_coexist(self) -> None:
        session: dict[str, Any] = {"_suite_active_workspace_id": "daniel"}
        song = WorkflowStateBlob(
            workflow_owner="song_based_improvisation",
            workflow_session_id="hevenu",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
        )
        gen = WorkflowStateBlob(
            workflow_owner="jam_session_generator",
            workflow_session_id="jam-1",
            keys=KeyAuthority(practice_tonic="D", practice_mode="major"),
            style="Bossa Nova",
        )
        self.assertTrue(save_workflow_blob(session, song, source="test"))
        self.assertTrue(save_workflow_blob(session, gen, source="test"))
        loaded_song = get_workflow_blob(session, "song_based_improvisation", "hevenu")
        loaded_gen = get_workflow_blob(session, "jam_session_generator", "jam-1")
        assert loaded_song is not None and loaded_gen is not None
        self.assertEqual(loaded_song.keys.practice_tonic, "E")
        self.assertEqual(loaded_gen.keys.practice_tonic, "D")
        self.assertEqual(loaded_gen.style, "Bossa Nova")

    def test_single_active_pointer(self) -> None:
        session: dict[str, Any] = {"_suite_active_workspace_id": "daniel"}
        p1 = ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id="bossa", context_revision=1)
        p2 = ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id="mission|h", context_revision=2)
        self.assertTrue(set_active_workflow_pointer(session, p1, source="test"))
        self.assertTrue(set_active_workflow_pointer(session, p2, source="test"))
        active = get_active_workflow_pointer(session)
        assert active is not None
        self.assertEqual(active.workflow_owner, "mission_jam")

    def test_style_jam_does_not_mutate_song_blob(self) -> None:
        session: dict[str, Any] = {"_suite_active_workspace_id": "daniel"}
        song = WorkflowStateBlob(
            workflow_owner="song_based_improvisation",
            workflow_session_id="hevenu",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
            section_map={"Melody A": ["Em", "B"]},
        )
        save_workflow_blob(session, song, source="test")
        style = WorkflowStateBlob(
            workflow_owner="style_jam",
            workflow_session_id="Bossa",
            keys=KeyAuthority(practice_tonic="D", practice_mode="major"),
            section_map={"Head": ["Dm7", "G7"]},
        )
        save_workflow_blob(session, style, source="test")
        again = get_workflow_blob(session, "song_based_improvisation", "hevenu")
        assert again is not None
        self.assertEqual(again.keys.practice_mode, "minor")
        self.assertIn("Melody A", again.section_map)

    def test_missions_does_not_delete_generator_blob(self) -> None:
        session: dict[str, Any] = {"_suite_active_workspace_id": "daniel"}
        gen = WorkflowStateBlob(
            workflow_owner="jam_session_generator",
            workflow_session_id="g1",
            keys=KeyAuthority(practice_tonic="D", practice_mode="major"),
        )
        mission = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="mission|h",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
            selected_chord_symbol="B",
        )
        save_workflow_blob(session, gen, source="test")
        save_workflow_blob(session, mission, source="test")
        self.assertIsNotNone(get_workflow_blob(session, "jam_session_generator", "g1"))

    def test_tonic_and_mode_explicit(self) -> None:
        blob = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="x",
            keys=KeyAuthority(
                original_tonic="Eb",
                original_mode="minor",
                practice_tonic="E",
                practice_mode="minor",
            ),
        )
        self.assertEqual(blob.keys.practice_mode, "minor")
        self.assertEqual(blob.keys.practice_tonic, "E")

    def test_revision_increments_on_material_change_only(self) -> None:
        session: dict[str, Any] = {"_suite_active_workspace_id": "daniel"}
        b1 = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="m",
            selected_chord_symbol="B",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
        )
        self.assertTrue(save_workflow_blob(session, b1, source="test"))
        rev1 = get_workflow_blob(session, "mission_jam", "m")
        assert rev1 is not None
        self.assertEqual(rev1.context_revision, 1)
        b2 = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="m",
            selected_chord_symbol="B",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
        )
        self.assertFalse(save_workflow_blob(session, b2, source="test"))
        b3 = copy.deepcopy(b2)
        b3.selected_chord_symbol = "Ab"
        self.assertTrue(save_workflow_blob(session, b3, source="test"))
        rev3 = get_workflow_blob(session, "mission_jam", "m")
        assert rev3 is not None
        self.assertEqual(rev3.context_revision, 2)

    def test_wrong_workspace_cannot_read_other_store(self) -> None:
        session: dict[str, Any] = {"_suite_active_workspace_id": "daniel"}
        blob = WorkflowStateBlob(workflow_owner="style_jam", workflow_session_id="s1")
        save_workflow_blob(session, blob, source="test")
        session["_suite_active_workspace_id"] = "ariel"
        store = get_music_workflow_state_store(session)
        self.assertEqual(store.get("workspace_id"), "ariel")
        self.assertEqual(len(store.get("blobs") or {}), 0)

    def test_canonical_gather_only_explicit_reason(self) -> None:
        session: dict[str, Any] = {"_music_workflow_state_store": {"schema_version": 1, "blobs": {}}}
        self.assertFalse(should_gather_workflow_state_to_canonical(session, persist_reason="autosave"))
        self.assertTrue(
            should_gather_workflow_state_to_canonical(session, persist_reason="music_workflow_state_save")
        )

    def test_compat_reconstructs_legacy_mission(self) -> None:
        session: dict[str, Any] = {
            "display_key": "Em",
            "concert_key": "Em",
            "ii_selected_chord": "B",
            "improv_active_mission": "Outline chord tones",
            "improv_song_concert_sections": {"Melody A": ["Em", "B"]},
        }
        blob = build_workflow_blob_from_legacy(session, "mission_jam")
        self.assertEqual(blob.selected_chord_symbol, "B")
        self.assertEqual(blob.keys.practice_mode, "minor")

    def test_dev_snapshot_reports_legacy(self) -> None:
        session: dict[str, Any] = {
            "dev_mode": True,
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "display_key": "Em",
            "ii_selected_chord": "B",
        }
        snap = build_workflow_architecture_snapshot(session)
        self.assertEqual(snap.get("legacy_inferred_owner"), "mission_jam")
        self.assertTrue(len(snap.get("compat_fallbacks") or []) >= 1)

    def test_cache_identity_distinguishes_mission_vs_generator(self) -> None:
        session: dict[str, Any] = {"_suite_active_workspace_id": "daniel"}
        mission = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="m",
            selected_chord_symbol="B",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
        )
        gen = WorkflowStateBlob(
            workflow_owner="jam_session_generator",
            workflow_session_id="g",
            keys=KeyAuthority(practice_tonic="D", practice_mode="major"),
        )
        save_workflow_blob(session, mission, source="test")
        save_workflow_blob(session, gen, source="test")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id="m", context_revision=1),
            source="test",
        )
        id_m = workflow_cache_identity(session)
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(
                workflow_owner="jam_session_generator", workflow_session_id="g", context_revision=1
            ),
            source="test",
        )
        id_g = workflow_cache_identity(session)
        self.assertNotEqual(id_m, id_g)

    def test_pointer_workspace_validation(self) -> None:
        session: dict[str, Any] = {"_suite_active_workspace_id": "daniel"}
        session[MUSIC_ACTIVE_WORKFLOW_KEY] = {
            "workflow_owner": "style_jam",
            "workflow_session_id": "s",
            "workspace_id": "other",
            "context_revision": 1,
        }
        self.assertIn("ACTIVE_POINTER_WORKSPACE_MISMATCH", validate_active_workflow_pointer(session))

    def test_canonical_roundtrip_slice(self) -> None:
        session: dict[str, Any] = {"_suite_active_workspace_id": "daniel"}
        blob = WorkflowStateBlob(workflow_owner="song_based_improvisation", workflow_session_id="h")
        save_workflow_blob(session, blob, source="test")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="song_based_improvisation", workflow_session_id="h", context_revision=1),
            source="test",
        )
        nested = gather_workflow_state_canonical_slice(session)
        session2: dict[str, Any] = {"_suite_active_workspace_id": "daniel"}
        apply_workflow_state_canonical_slice(session2, nested)
        self.assertIn(MUSIC_WORKFLOW_STATE_STORE_KEY, session2)
        self.assertIn(MUSIC_ACTIVE_WORKFLOW_KEY, session2)


if __name__ == "__main__":
    unittest.main()

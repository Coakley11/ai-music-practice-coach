"""Commit 5 — P0 closure tests (transpose, generator, mission bootstrap, persist lifecycle)."""

from __future__ import annotations

import copy
import unittest
from typing import Any

from music_workflow_activation import ActivateWorkflowRequest, activate_workflow
from music_workflow_mission_bootstrap import ensure_mission_blob_from_song
from music_workflow_mutation import update_active_practice_key
from music_workflow_persist_lifecycle import (
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
from creative_workspace_state_persistence import gather_creative_workspace_from_session
from music_workflow_canonical_persistence import (
    CWS_WORKFLOW_STATE_NESTED_KEY,
    apply_workflow_state_canonical_slice,
)


def _session(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"_suite_active_workspace_id": "daniel"}
    base.update(extra)
    return base


class TestStyleJamSingleTranspose(unittest.TestCase):
    def test_f_to_d_transposes_once(self) -> None:
        session = _session(
            improv_style_key="D",
            improv_generated_sections={"A": ["F", "Dm", "Bb", "C"]},
        )
        blob = WorkflowStateBlob(
            workflow_owner="style_jam",
            workflow_session_id="Bossa",
            keys=KeyAuthority(practice_tonic="F", practice_mode="major"),
            section_map={"A": ["F", "Dm", "Bb", "C"]},
        )
        save_workflow_blob(session, blob, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id="Bossa"),
            source="t",
        )
        result = update_active_practice_key(session, "D", source="on_improv_style_key_change")
        self.assertTrue(result.ok)
        loaded = get_workflow_blob(session, "style_jam", "Bossa")
        assert loaded is not None
        first = loaded.section_map.get("A", [""])[0]
        self.assertIn(first, {"D", "Dmaj"})
        legacy = session.get("improv_generated_sections") or {}
        leg_first = legacy.get("A", [""])[0]
        self.assertEqual(leg_first, first)


class TestGeneratorKeyProgression(unittest.TestCase):
    def test_c_to_d_updates_blob_sections(self) -> None:
        session = _session(
            improv_jam_session={
                "id": "jam-1",
                "sections": {"Verse": ["C", "Am", "Dm", "G"]},
            },
        )
        blob = WorkflowStateBlob(
            workflow_owner="jam_session_generator",
            workflow_session_id="jam-1",
            keys=KeyAuthority(practice_tonic="C", practice_mode="major"),
            section_map={"Verse": ["C", "Am", "Dm", "G"]},
            generated_session_id="jam-1",
        )
        save_workflow_blob(session, blob, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="jam_session_generator", workflow_session_id="jam-1"),
            source="t",
        )
        result = update_active_practice_key(session, "D", source="on_improv_jam_key_change")
        self.assertTrue(result.ok)
        loaded = get_workflow_blob(session, "jam_session_generator", "jam-1")
        assert loaded is not None
        self.assertEqual(loaded.keys.practice_tonic, "D")
        chords = loaded.section_map.get("Verse") or []
        self.assertTrue(chords)
        self.assertNotIn("C", chords[0:1])
        jam = session.get("improv_jam_session") or {}
        jam_chords = (jam.get("sections") or {}).get("Verse") or []
        self.assertEqual(jam_chords, chords)


class TestMissionBootstrapFromSong(unittest.TestCase):
    def test_first_missions_uses_song_not_style_jam_display(self) -> None:
        session = _session(
            active_catalog_pick_key="girl_from_ipanema",
            display_key="D",
            concert_key="D",
            improv_style_key="D",
        )
        song = WorkflowStateBlob(
            workflow_owner="song_based_improvisation",
            workflow_session_id="girl_from_ipanema",
            keys=KeyAuthority(practice_tonic="F", practice_mode="major"),
            section_map={"A": ["Fmaj7"]},
            song_id="girl_from_ipanema",
        )
        save_workflow_blob(session, song, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id="Bossa"),
            source="t",
        )
        mission = ensure_mission_blob_from_song(session, "mission|girl_from_ipanema")
        assert mission is not None
        self.assertEqual(mission.keys.practice_tonic, "F")
        self.assertEqual(mission.keys.practice_mode, "major")

    def test_activation_missions_bootstrap(self) -> None:
        session = _session(active_catalog_pick_key="hevenu", display_key="D", concert_key="D")
        song = WorkflowStateBlob(
            workflow_owner="song_based_improvisation",
            workflow_session_id="hevenu",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
        )
        save_workflow_blob(session, song, source="t")
        activate_workflow(
            session,
            ActivateWorkflowRequest(
                target_owner="mission_jam",
                target_session_id="mission|hevenu",
                activation_source="creative_missions",
                navigation_intent="creative_missions",
            ),
        )
        m = get_workflow_blob(session, "mission_jam", "mission|hevenu")
        assert m is not None
        self.assertEqual(m.keys.practice_mode, "minor")
        self.assertEqual(m.keys.practice_tonic, "E")


class TestPersistLifecycle(unittest.TestCase):
    def test_gather_does_not_clear_pending(self) -> None:
        session = _session()
        request_workflow_canonical_persist(session, "music_workflow_activate", expected_revision=2)
        gather_creative_workspace_from_session(session)
        self.assertTrue(resolve_workflow_persist_reason(session, fallback="autosave"))

    def test_cloud_success_clears_pending(self) -> None:
        session = _session()
        rid = request_workflow_canonical_persist(session, "music_workflow_activate")
        confirm_workflow_persist_after_cloud_save(session, saved_cloud=True)
        self.assertNotIn("_music_workflow_persist_pending", session)

    def test_cloud_failure_retains_pending(self) -> None:
        session = _session()
        request_workflow_canonical_persist(session, "music_workflow_activate")
        confirm_workflow_persist_after_cloud_save(session, saved_cloud=False, error="stale")
        self.assertIn("_music_workflow_persist_pending", session)


class TestCanonicalRestorePrecedence(unittest.TestCase):
    def test_live_newer_blocks_restore(self) -> None:
        session = _session()
        live = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="m",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
            selected_chord_symbol="B",
            context_revision=5,
        )
        save_workflow_blob(session, live, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id="m", context_revision=5),
            source="t",
        )
        stale_blob = live.to_dict()
        stale_blob["selected_chord_symbol"] = "Ab"
        stale_blob["context_revision"] = 1
        nested = {
            "schema_version": 1,
            "store": {
                "schema_version": 1,
                "blobs": {f"mission_jam|m": stale_blob},
                "context_revision_seq": 1,
            },
            "active_pointer": {
                "workflow_owner": "mission_jam",
                "workflow_session_id": "m",
                "context_revision": 1,
            },
        }
        apply_workflow_state_canonical_slice(session, nested)
        kept = get_workflow_blob(session, "mission_jam", "m")
        assert kept is not None
        self.assertEqual(kept.selected_chord_symbol, "B")


class TestSongWorkflowRestoration(unittest.TestCase):
    def test_ipanema_style_jam_round_trip_keys(self) -> None:
        session = _session(active_catalog_pick_key="girl_from_ipanema")
        song = WorkflowStateBlob(
            workflow_owner="song_based_improvisation",
            workflow_session_id="girl_from_ipanema",
            keys=KeyAuthority(practice_tonic="F", practice_mode="major"),
        )
        style = WorkflowStateBlob(
            workflow_owner="style_jam",
            workflow_session_id="Bossa",
            keys=KeyAuthority(practice_tonic="D", practice_mode="major"),
        )
        save_workflow_blob(session, song, source="t")
        save_workflow_blob(session, style, source="t")
        activate_workflow(
            session,
            ActivateWorkflowRequest(target_owner="style_jam", target_session_id="Bossa", activation_source="t"),
        )
        activate_workflow(
            session,
            ActivateWorkflowRequest(
                target_owner="song_based_improvisation",
                target_session_id="girl_from_ipanema",
                activation_source="t",
            ),
        )
        b = get_workflow_blob(session, "song_based_improvisation", "girl_from_ipanema")
        assert b is not None
        self.assertEqual(b.keys.practice_tonic, "F")
        activate_workflow(
            session,
            ActivateWorkflowRequest(target_owner="style_jam", target_session_id="Bossa", activation_source="t"),
        )
        s = get_workflow_blob(session, "style_jam", "Bossa")
        assert s is not None
        self.assertEqual(s.keys.practice_tonic, "D")


if __name__ == "__main__":
    unittest.main()

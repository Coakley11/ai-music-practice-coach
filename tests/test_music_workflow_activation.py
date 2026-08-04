"""Commit 2 — activate_workflow() production authority tests."""

from __future__ import annotations

import unittest
from typing import Any

from music_workflow_activation import (
    WORKFLOW_BOOTSTRAP_DONE_KEY,
    WORKFLOW_PENDING_CANONICAL_REASON_KEY,
    ActivateWorkflowRequest,
    activate_workflow,
    bootstrap_active_workflow_if_needed,
)
from music_workflow_canonical_persistence import should_gather_workflow_state_to_canonical
from music_workflow_compatibility import build_workflow_blob_from_legacy
from music_workflow_state_store import (
    KeyAuthority,
    WorkflowStateBlob,
    get_active_workflow_pointer,
    get_workflow_blob,
    save_workflow_blob,
    set_active_workflow_pointer,
    ActiveWorkflowPointer,
    workflow_cache_identity,
)


def _session(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"_suite_active_workspace_id": "daniel"}
    base.update(extra)
    return base


class TestWorkflowBootstrap(unittest.TestCase):
    def test_bootstrap_creates_one_pointer(self) -> None:
        session = _session(
            improv_entry_mode="Song-Based Improvisation",
            display_key="Em",
            concert_key="Em",
            active_catalog_pick_key="hevenu",
        )
        out = bootstrap_active_workflow_if_needed(session)
        self.assertTrue(out.get("bootstrapped"))
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        self.assertEqual(ptr.workflow_owner, "song_based_improvisation")

    def test_bootstrap_not_repeated(self) -> None:
        session = _session(improv_intelligence_tab="Missions", display_key="Em", concert_key="Em")
        bootstrap_active_workflow_if_needed(session)
        ptr1 = get_active_workflow_pointer(session)
        bootstrap_active_workflow_if_needed(session)
        ptr2 = get_active_workflow_pointer(session)
        self.assertEqual(ptr1.to_dict(), ptr2.to_dict())
        self.assertTrue(session.get(WORKFLOW_BOOTSTRAP_DONE_KEY))


class TestMissionGeneratorIsolation(unittest.TestCase):
    def test_style_jam_d_major_then_missions_e_minor(self) -> None:
        session = _session(active_catalog_pick_key="hevenu")
        song = WorkflowStateBlob(
            workflow_owner="song_based_improvisation",
            workflow_session_id="hevenu",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
            section_map={"Melody A": ["Em", "B"]},
        )
        save_workflow_blob(session, song, source="test")
        mission = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="mission|hevenu",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
            selected_chord_symbol="B",
            selected_section="Melody A",
            section_map={"Melody A": ["Em", "B"]},
        )
        save_workflow_blob(session, mission, source="test")
        style = WorkflowStateBlob(
            workflow_owner="style_jam",
            workflow_session_id="Bossa",
            keys=KeyAuthority(practice_tonic="D", practice_mode="major"),
            style="Bossa",
            section_map={"Head": ["Dmaj7"]},
        )
        save_workflow_blob(session, style, source="test")
        activate_workflow(
            session,
            ActivateWorkflowRequest(target_owner="style_jam", target_session_id="Bossa", activation_source="test"),
        )
        activate_workflow(
            session,
            ActivateWorkflowRequest(
                target_owner="mission_jam",
                target_session_id="mission|hevenu",
                activation_source="test",
            ),
        )
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        self.assertEqual(ptr.workflow_owner, "mission_jam")
        blob = get_workflow_blob(session, "mission_jam", "mission|hevenu")
        assert blob is not None
        self.assertEqual(blob.keys.practice_tonic, "E")
        self.assertEqual(blob.keys.practice_mode, "minor")
        self.assertEqual(blob.selected_chord_symbol, "B")
        self.assertEqual(session.get("display_key"), "Em")

    def test_missions_then_style_jam_restores_d_major(self) -> None:
        session = _session()
        style = WorkflowStateBlob(
            workflow_owner="style_jam",
            workflow_session_id="Bossa",
            keys=KeyAuthority(practice_tonic="D", practice_mode="major"),
            style="Bossa",
        )
        mission = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="mission|h",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
            selected_chord_symbol="B",
        )
        save_workflow_blob(session, style, source="test")
        save_workflow_blob(session, mission, source="test")
        activate_workflow(
            session,
            ActivateWorkflowRequest(target_owner="mission_jam", target_session_id="mission|h", activation_source="test"),
        )
        activate_workflow(
            session,
            ActivateWorkflowRequest(target_owner="style_jam", target_session_id="Bossa", activation_source="test"),
        )
        blob = get_workflow_blob(session, "style_jam", "Bossa")
        assert blob is not None
        self.assertEqual(blob.keys.practice_tonic, "D")
        self.assertEqual(str(session.get("improv_style_key") or session.get("display_key")), "D")

    def test_generator_survives_inactive(self) -> None:
        session = _session()
        gen = WorkflowStateBlob(
            workflow_owner="jam_session_generator",
            workflow_session_id="jam-1",
            keys=KeyAuthority(practice_tonic="D", practice_mode="major"),
            style="Fusion",
            section_map={"A": ["D", "G"]},
        )
        save_workflow_blob(session, gen, source="test")
        activate_workflow(
            session,
            ActivateWorkflowRequest(target_owner="mission_jam", target_session_id="mission|x", activation_source="test"),
        )
        loaded = get_workflow_blob(session, "jam_session_generator", "jam-1")
        assert loaded is not None
        self.assertEqual(loaded.keys.practice_tonic, "D")
        self.assertEqual(loaded.section_map.get("A"), ["D", "G"])


class TestBackingOwners(unittest.TestCase):
    def test_mission_backing_keeps_mission_jam_owner(self) -> None:
        session = _session(
            improv_intelligence_tab="Missions",
            display_key="Em",
            concert_key="Em",
            ii_selected_chord="B",
        )
        activate_workflow(
            session,
            ActivateWorkflowRequest(
                target_owner="mission_jam",
                target_session_id="mission|hevenu",
                activation_source="open_backing",
                page_route="backing",
            ),
        )
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        self.assertEqual(ptr.workflow_owner, "mission_jam")


class TestActivationGuards(unittest.TestCase):
    def test_pointer_not_overwritten_by_bootstrap_after_set(self) -> None:
        session = _session(improv_intelligence_tab="Missions")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="jam_session_generator", workflow_session_id="jam-1"),
            source="test",
        )
        session[WORKFLOW_BOOTSTRAP_DONE_KEY] = True
        bootstrap_active_workflow_if_needed(session)
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        self.assertEqual(ptr.workflow_owner, "jam_session_generator")

    def test_wrong_workspace_fails_closed(self) -> None:
        session = _session()
        result = activate_workflow(
            session,
            ActivateWorkflowRequest(
                target_owner="mission_jam",
                target_session_id="m",
                activation_source="test",
                expected_workspace_id="other_ws",
            ),
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "WORKSPACE_MISMATCH")

    def test_stale_revision_fails_closed(self) -> None:
        session = _session()
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id="s", context_revision=5),
            source="test",
        )
        result = activate_workflow(
            session,
            ActivateWorkflowRequest(
                target_owner="mission_jam",
                target_session_id="m",
                activation_source="test",
                expected_context_revision=3,
            ),
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "STALE_REVISION")

    def test_unchanged_activation_skips(self) -> None:
        session = _session()
        blob = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="m1",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
        )
        save_workflow_blob(session, blob, source="test")
        activate_workflow(
            session,
            ActivateWorkflowRequest(target_owner="mission_jam", target_session_id="m1", activation_source="test"),
        )
        store = session["_music_workflow_state_store"]
        seq_before = store.get("context_revision_seq")
        skipped = activate_workflow(
            session,
            ActivateWorkflowRequest(target_owner="mission_jam", target_session_id="m1", activation_source="test"),
        )
        self.assertTrue(skipped.skipped)
        seq_after = session["_music_workflow_state_store"].get("context_revision_seq")
        self.assertEqual(seq_before, seq_after)
        self.assertNotIn(WORKFLOW_PENDING_CANONICAL_REASON_KEY, session)

    def test_durable_handoff_sets_persist_reason(self) -> None:
        session = _session(display_key="C", concert_key="C")
        activate_workflow(
            session,
            ActivateWorkflowRequest(
                target_owner="style_jam",
                target_session_id="Bossa",
                activation_source="backing_handoff",
                persist_policy="durable_handoff",
            ),
        )
        self.assertEqual(session.get(WORKFLOW_PENDING_CANONICAL_REASON_KEY), "music_workflow_activate")
        self.assertFalse(
            should_gather_workflow_state_to_canonical(session, persist_reason="autosave"),
        )


class TestCacheIdentity(unittest.TestCase):
    def test_cache_differs_mission_vs_generator(self) -> None:
        session = _session()
        m = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="m",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
            selected_chord_symbol="B",
        )
        g = WorkflowStateBlob(
            workflow_owner="jam_session_generator",
            workflow_session_id="g",
            keys=KeyAuthority(practice_tonic="D", practice_mode="major"),
        )
        save_workflow_blob(session, m, source="t")
        save_workflow_blob(session, g, source="t")
        activate_workflow(
            session,
            ActivateWorkflowRequest(target_owner="mission_jam", target_session_id="m", activation_source="t"),
        )
        id_m = workflow_cache_identity(session)
        activate_workflow(
            session,
            ActivateWorkflowRequest(target_owner="jam_session_generator", target_session_id="g", activation_source="t"),
        )
        id_g = workflow_cache_identity(session)
        self.assertNotEqual(id_m, id_g)


class TestLegacyProjection(unittest.TestCase):
    def test_projection_one_way_from_blob(self) -> None:
        session = _session(display_key="D", concert_key="D", improv_style_key="D")
        blob = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="m",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
            selected_chord_symbol="B",
        )
        activate_workflow(
            session,
            ActivateWorkflowRequest(target_owner="mission_jam", target_session_id="m", activation_source="t", incoming_blob=blob),
        )
        self.assertEqual(session.get("ii_selected_chord"), "B")
        peek = build_workflow_blob_from_legacy(session, "mission_jam")
        self.assertEqual(peek.keys.practice_tonic, "E")


if __name__ == "__main__":
    unittest.main()

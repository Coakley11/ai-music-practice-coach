"""Commit 4 — authority closure tests."""

from __future__ import annotations

import copy
import unittest
from typing import Any

from music_workflow_activation import ActivateWorkflowRequest, activate_workflow, capture_outgoing_blob
from music_workflow_canonical_persistence import (
    CWS_WORKFLOW_STATE_NESTED_KEY,
    should_gather_workflow_state_to_canonical,
)
from music_workflow_compatibility import build_workflow_blob_from_legacy
from music_workflow_guard import AUTHORITATIVE_SESSION_KEYS
from music_workflow_legacy_capture import capture_outgoing_workflow_blob
from music_workflow_mutation import should_project_mission_config_from_canonical, update_active_practice_key
from music_workflow_state_store import (
    KeyAuthority,
    WorkflowStateBlob,
    get_workflow_blob,
    save_workflow_blob,
    set_active_workflow_pointer,
    ActiveWorkflowPointer,
)


def _session(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"_suite_active_workspace_id": "daniel"}
    base.update(extra)
    return base


class TestLegacyCaptureBlocked(unittest.TestCase):
    def test_valid_blob_not_rebuilt_from_legacy(self) -> None:
        session = _session(improv_style_key="Eb", display_key="Eb")
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
        out = capture_outgoing_workflow_blob(session, owner="style_jam", session_id="Bossa")
        assert out is not None
        self.assertEqual(out.keys.practice_tonic, "D")
        legacy = build_workflow_blob_from_legacy(session, "style_jam")
        self.assertNotEqual(legacy.keys.practice_tonic, out.keys.practice_tonic)

    def test_tab_activation_preserves_blob(self) -> None:
        session = _session(improv_style_key="Eb", display_key="Eb")
        blob = WorkflowStateBlob(
            workflow_owner="style_jam",
            workflow_session_id="Bossa",
            keys=KeyAuthority(practice_tonic="D", practice_mode="major"),
        )
        save_workflow_blob(session, blob, source="t")
        activate_workflow(
            session,
            ActivateWorkflowRequest(
                target_owner="style_jam",
                target_session_id="Bossa",
                activation_source="creative_tab_change",
                navigation_intent="creative_tab",
            ),
        )
        loaded = get_workflow_blob(session, "style_jam", "Bossa")
        assert loaded is not None
        self.assertEqual(loaded.keys.practice_tonic, "D")


class TestCanonicalPrecedence(unittest.TestCase):
    def test_stale_ab_canonical_rejected_for_b_blob(self) -> None:
        session = _session()
        blob = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="mission|h",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
            selected_chord_symbol="B",
        )
        save_workflow_blob(session, blob, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id="mission|h"),
            source="t",
        )
        session["creative_workspace_state"] = {
            "ii_selected_chord": "Ab",
            "improv_mission_pick": "Outline chord tones",
        }
        self.assertFalse(should_project_mission_config_from_canonical(session))


class TestCanonicalPersistGather(unittest.TestCase):
    def test_explicit_reason_gathers_slice(self) -> None:
        session = _session()
        blob = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="m",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
        )
        save_workflow_blob(session, blob, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id="m"),
            source="t",
        )
        session["_music_workflow_pending_canonical_reason"] = "music_workflow_activate"
        session["_music_build_save_reason"] = "autosave"
        from music_workflow_canonical_persistence import resolve_workflow_persist_reason

        wf_reason = resolve_workflow_persist_reason(session, fallback="autosave")
        self.assertTrue(
            should_gather_workflow_state_to_canonical(session, persist_reason=wf_reason),
        )
        from creative_workspace_state_persistence import gather_creative_workspace_from_session

        cws = gather_creative_workspace_from_session(session)
        self.assertIn(CWS_WORKFLOW_STATE_NESTED_KEY, cws)


class TestSongWorkflowKeyIsolation(unittest.TestCase):
    def test_style_key_does_not_change_mission_blob(self) -> None:
        session = _session(active_catalog_pick_key="hevenu")
        mission = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="mission|hevenu",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
        )
        style = WorkflowStateBlob(
            workflow_owner="style_jam",
            workflow_session_id="Bossa",
            keys=KeyAuthority(practice_tonic="D", practice_mode="major"),
        )
        save_workflow_blob(session, mission, source="t")
        save_workflow_blob(session, style, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id="Bossa"),
            source="t",
        )
        update_active_practice_key(session, "G", source="on_improv_style_key_change")
        m = get_workflow_blob(session, "mission_jam", "mission|hevenu")
        assert m is not None
        self.assertEqual(m.keys.practice_tonic, "E")


class TestDirectWriteScan(unittest.TestCase):
    def test_authoritative_keys_documented(self) -> None:
        self.assertIn("_music_active_workflow", AUTHORITATIVE_SESSION_KEYS)


if __name__ == "__main__":
    unittest.main()

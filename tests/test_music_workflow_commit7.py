"""Commit 7 — canonical identity, run-scoped restore guards, persist confirm, key invalidation."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from music_workflow_activation import (
    WORKFLOW_ACTIVATION_ERROR_KEY,
    ActivateWorkflowRequest,
    activate_workflow,
    activation_user_notice,
)
from music_workflow_canonical_identity import (
    CANONICAL_IDENTITY_CONFLICT,
    VIOLATION_CANONICAL_RESTORE_LIVE_SESSION_CONFLICT,
    validate_pre_activation_identity,
)
from music_workflow_canonical_persistence import apply_workflow_state_canonical_slice, note_workflow_persist_performed
from music_workflow_legacy_projection import _project_session_field, project_active_blob_to_legacy_session
from music_workflow_mutation import update_active_practice_key
from music_workflow_persist_lifecycle import (
    WORKFLOW_PERSIST_PENDING_KEY,
    confirm_workflow_persist_after_cloud_save,
    request_workflow_canonical_persist,
)
from music_workflow_restore_guard import (
    MUSIC_SCRIPT_RUN_ID_KEY,
    activate_workflow_restore_guard,
    block_legacy_overwrite,
    complete_workflow_restore_guard,
    expire_stale_workflow_restore_guards,
    restore_guard_active,
)
from music_workflow_state_store import (
    ActiveWorkflowPointer,
    KeyAuthority,
    WorkflowStateBlob,
    get_active_workflow_pointer,
    get_workflow_blob,
    save_workflow_blob,
    set_active_workflow_pointer,
)


def _session(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"_suite_active_workspace_id": "daniel"}
    base.update(extra)
    return base


class TestCanonicalIdentityBeforeActivation(unittest.TestCase):
    def test_pending_backing_handoff_owner_mismatch_blocks_activation(self) -> None:
        session = _session()
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id="Bossa"),
            source="t",
        )
        session["_music_pending_backing_workflow_handoff"] = {
            "workflow_owner": "style_jam",
            "backing_source": "entry_jam",
        }
        result = activate_workflow(
            session,
            ActivateWorkflowRequest(
                target_owner="mission_jam",
                target_session_id="mission|catalog|hevenu",
                activation_source="test_mismatch",
            ),
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, CANONICAL_IDENTITY_CONFLICT)
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        self.assertEqual(ptr.workflow_owner, "style_jam")

    def test_validate_mission_session_song_identity(self) -> None:
        session = _session(active_catalog_pick_key="hevenu")
        identity = validate_pre_activation_identity(
            session,
            target_owner="mission_jam",
            target_session_id="mission|catalog|wrong_song",
            ptr_before=None,
        )
        self.assertFalse(identity.ok)
        self.assertIn("MISSION_SESSION_SONG_IDENTITY_MISMATCH", identity.violations)


class TestRunScopedRestoreGuard(unittest.TestCase):
    def test_guard_expires_on_new_script_run(self) -> None:
        session = {MUSIC_SCRIPT_RUN_ID_KEY: "run-a"}
        activate_workflow_restore_guard(session, run_id="run-a")
        self.assertTrue(restore_guard_active(session))
        session[MUSIC_SCRIPT_RUN_ID_KEY] = "run-b"
        expire_stale_workflow_restore_guards(session)
        self.assertFalse(restore_guard_active(session))

    def test_complete_guard_ends_protection(self) -> None:
        session = {MUSIC_SCRIPT_RUN_ID_KEY: "run-1"}
        activate_workflow_restore_guard(session, run_id="run-1")
        complete_workflow_restore_guard(session)
        self.assertFalse(restore_guard_active(session))

    def test_authoritative_projection_allowed_stale_legacy_blocked(self) -> None:
        """Guard is direction-aware: blob→legacy F allowed; stale G→session blocked."""
        session = _session(display_key="G", concert_key="G", **{MUSIC_SCRIPT_RUN_ID_KEY: "run-x"})
        blob = WorkflowStateBlob(
            workflow_owner="style_jam",
            workflow_session_id="Bossa",
            keys=KeyAuthority(practice_tonic="F", practice_mode="major"),
        )
        save_workflow_blob(session, blob, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id="Bossa"),
            source="t",
        )
        activate_workflow_restore_guard(session, run_id="run-x")
        project_active_blob_to_legacy_session(session, blob)
        self.assertEqual(session.get("display_key"), "F")
        self.assertEqual(session.get("concert_key"), "F")
        loaded = get_workflow_blob(session, "style_jam", "Bossa")
        assert loaded is not None
        self.assertEqual(loaded.keys.practice_tonic, "F")
        _project_session_field(session, "display_key", "G", authoritative_projection=False)
        self.assertEqual(session.get("display_key"), "F")
        self.assertTrue(
            block_legacy_overwrite(
                session,
                "display_key",
                caller="stale_legacy_adapter",
                value="G",
                authoritative_projection=False,
            )
        )
        complete_workflow_restore_guard(session)
        self.assertFalse(restore_guard_active(session))
        update_active_practice_key(session, "D", source="on_improv_style_key_change")
        loaded2 = get_workflow_blob(session, "style_jam", "Bossa")
        assert loaded2 is not None
        self.assertEqual(loaded2.keys.practice_tonic, "D")


class TestCanonicalRestoreIdentityFailClosed(unittest.TestCase):
    def test_no_live_pointer_allows_cloud_session_initialize(self) -> None:
        session = _session()
        nested = {
            "schema_version": 2,
            "saved_workspace_revision": 5,
            "store": {
                "schema_version": 1,
                "blobs": {
                    "song_based_improvisation|cloud-song": WorkflowStateBlob(
                        workflow_owner="song_based_improvisation",
                        workflow_session_id="cloud-song",
                        keys=KeyAuthority(practice_tonic="F", practice_mode="major"),
                    ).to_dict(),
                },
            },
            "active_pointer": {
                "workflow_owner": "song_based_improvisation",
                "workflow_session_id": "cloud-song",
                "context_revision": 1,
            },
        }
        apply_workflow_state_canonical_slice(session, nested)
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        self.assertEqual(ptr.workflow_session_id, "cloud-song")

    def test_live_pointer_agrees_allows_canonical_restore(self) -> None:
        session = _session(active_catalog_pick_key="hevenu")
        live = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="mission|catalog|hevenu",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
        )
        save_workflow_blob(session, live, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id="mission|catalog|hevenu"),
            source="t",
        )
        result = activate_workflow(
            session,
            ActivateWorkflowRequest(
                target_owner="mission_jam",
                target_session_id="mission|catalog|hevenu",
                activation_source="canonical_restore",
            ),
        )
        self.assertTrue(result.ok)

    def test_canonical_restore_cannot_bypass_live_session_conflict(self) -> None:
        session = _session(active_catalog_pick_key="hevenu")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id="mission|catalog|hevenu"),
            source="t",
        )
        result = activate_workflow(
            session,
            ActivateWorkflowRequest(
                target_owner="mission_jam",
                target_session_id="mission|catalog|other_song",
                activation_source="canonical_restore",
            ),
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, CANONICAL_IDENTITY_CONFLICT)
        self.assertIn(
            VIOLATION_CANONICAL_RESTORE_LIVE_SESSION_CONFLICT,
            (session.get("_music_workflow_canonical_identity_diag") or {}).get("violations", []),
        )
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        self.assertEqual(ptr.workflow_session_id, "mission|catalog|hevenu")

    def test_canonical_restore_label_alone_cannot_bypass_owner_conflict(self) -> None:
        session = _session()
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id="Bossa"),
            source="t",
        )
        identity = validate_pre_activation_identity(
            session,
            target_owner="mission_jam",
            target_session_id="mission|catalog|hevenu",
            ptr_before=get_active_workflow_pointer(session),
            activation_source="canonical_restore",
        )
        self.assertFalse(identity.ok)
        self.assertIn("CANONICAL_RESTORE_LIVE_OWNER_CONFLICT", identity.violations)


class TestPersistPendingUntilConfirmed(unittest.TestCase):
    def test_queue_does_not_clear_pending(self) -> None:
        session = _session()
        request_workflow_canonical_persist(session, "material_workflow_key_change", expected_revision=2)
        note_workflow_persist_performed(session, revision=2)
        self.assertIn(WORKFLOW_PERSIST_PENDING_KEY, session)

    def test_cas_workspace_regression_retains_pending(self) -> None:
        session = _session()
        request_workflow_canonical_persist(
            session,
            "material_workflow_key_change",
            expected_revision=2,
            expected_fingerprint="fp1",
            expected_workspace_revision=10,
        )
        pend = session[WORKFLOW_PERSIST_PENDING_KEY]
        save_state = {
            "workspace_revision": 8,
            "creative_workspace_state": {
                "music_workflow_state_v1": {"persist_request": dict(pend)},
            },
        }
        confirm_workflow_persist_after_cloud_save(session, saved_cloud=True, save_state=save_state)
        self.assertIn(WORKFLOW_PERSIST_PENDING_KEY, session)
        self.assertEqual(session[WORKFLOW_PERSIST_PENDING_KEY].get("persist_error"), "cas_workspace_revision_regression")

    def test_matching_confirm_clears_pending(self) -> None:
        session = _session()
        request_workflow_canonical_persist(
            session,
            "material_workflow_key_change",
            expected_revision=2,
            expected_fingerprint="fp1",
        )
        pend = session[WORKFLOW_PERSIST_PENDING_KEY]
        save_state = {
            "workspace_revision": 12,
            "creative_workspace_state": {
                "music_workflow_state_v1": {"persist_request": dict(pend)},
            },
        }
        confirm_workflow_persist_after_cloud_save(session, saved_cloud=True, save_state=save_state)
        self.assertNotIn(WORKFLOW_PERSIST_PENDING_KEY, session)


class TestKeyChangeInvalidatesDerivedState(unittest.TestCase):
    def test_mission_key_change_clears_example_session_projection(self) -> None:
        session = _session(active_catalog_pick_key="hevenu", improv_mission_example={"chord": "Bb"})
        session["_mission_example_output_fp"] = "stale"
        blob = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="mission|catalog|hevenu",
            keys=KeyAuthority(practice_tonic="Eb", practice_mode="minor"),
            section_map={"A": ["Ebm", "Bb"]},
            selected_chord_index=1,
            selected_chord_symbol="Bb",
            example_fingerprint="oldexample",
        )
        save_workflow_blob(session, blob, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id="mission|catalog|hevenu"),
            source="t",
        )
        update_active_practice_key(session, "Em", source="sidebar_missions", transpose_progression=True)
        self.assertNotIn("improv_mission_example", session)
        self.assertNotIn("_mission_example_output_fp", session)
        loaded = get_workflow_blob(session, "mission_jam", "mission|catalog|hevenu")
        assert loaded is not None
        self.assertEqual(loaded.example_fingerprint, "")


class TestMissionBootstrapUserNotice(unittest.TestCase):
    def test_failed_bootstrap_surfaces_notice(self) -> None:
        session = _session(active_catalog_pick_key="missing_song_xyz", display_key="D")
        with patch("songs.music_source.resolve_catalog_song_for_pick", return_value=(None, False)):
            result = activate_workflow(
                session,
                ActivateWorkflowRequest(
                    target_owner="mission_jam",
                    activation_source="missions_tab_render",
                ),
            )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "MISSION_BOOTSTRAP_FAILED")
        notice = activation_user_notice(session)
        self.assertIn("Mission could not be restored", notice)
        err = session.get(WORKFLOW_ACTIVATION_ERROR_KEY)
        assert isinstance(err, dict)
        self.assertIn("Mission could not be restored", str(err.get("message") or ""))


if __name__ == "__main__":
    unittest.main()

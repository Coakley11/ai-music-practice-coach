"""Optional canonical persistence slice for workflow store (explicit save reasons only)."""

from __future__ import annotations

import copy
from typing import Any

from music_workflow_state_store import (
    MUSIC_ACTIVE_WORKFLOW_KEY,
    MUSIC_WORKFLOW_STATE_STORE_KEY,
    SAVE_REASON_WORKFLOW_STATE,
)

CWS_WORKFLOW_STATE_NESTED_KEY = "music_workflow_state_v1"

WORKFLOW_PERSIST_STATS_KEY = "_music_workflow_persist_stats"

WORKFLOW_STATE_SAVE_REASONS: frozenset[str] = frozenset(
    {
        SAVE_REASON_WORKFLOW_STATE,
        "music_workflow_activate",
        "creative_mission_example_change",
        "creative_mission_target_change",
        "music_workflow_state_save",
        "durable_backing_handoff",
        "mission_recording_handoff",
        "pending_upload_analysis_handoff",
        "explicit_user_save",
        "material_workflow_key_change",
    }
)


def _persist_stats(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(WORKFLOW_PERSIST_STATS_KEY)
    if not isinstance(raw, dict):
        raw = {
            "workflow_persist_requested": 0,
            "workflow_persist_performed": 0,
            "workflow_persist_skipped_unchanged": 0,
            "workflow_persist_failed": 0,
            "workflow_persist_reason": "",
            "persisted_context_revision": 0,
        }
        session[WORKFLOW_PERSIST_STATS_KEY] = raw
    return raw


def resolve_workflow_persist_reason(session: dict[str, Any], *, fallback: str = "") -> str:
    try:
        from music_workflow_persist_lifecycle import resolve_workflow_persist_reason as _resolve

        return _resolve(session, fallback=fallback)
    except ImportError:
        pending = str(session.get("_music_workflow_pending_canonical_reason") or "").strip()
        if pending:
            return pending
        return str(fallback or "").strip()


def note_workflow_persist_requested(session: dict[str, Any], reason: str) -> None:
    s = _persist_stats(session)
    s["workflow_persist_requested"] = int(s.get("workflow_persist_requested") or 0) + 1
    s["workflow_persist_reason"] = str(reason or "")


def note_workflow_persist_performed(session: dict[str, Any], *, revision: int = 0) -> None:
    s = _persist_stats(session)
    s["workflow_persist_performed"] = int(s.get("workflow_persist_performed") or 0) + 1
    s["persisted_context_revision"] = int(revision or 0)


def note_workflow_persist_skipped(session: dict[str, Any]) -> None:
    s = _persist_stats(session)
    s["workflow_persist_skipped_unchanged"] = int(s.get("workflow_persist_skipped_unchanged") or 0) + 1


def apply_workflow_state_canonical_slice(session: dict[str, Any], nested: Any) -> None:
    """Restore from cloud/canonical — never overwrite newer live workflow state."""
    if not isinstance(nested, dict):
        return
    diag = session.setdefault("_music_workflow_canonical_restore_diag", {})
    if not isinstance(diag, dict):
        diag = {}
        session["_music_workflow_canonical_restore_diag"] = diag

    from music_workflow_state_store import (
        WorkflowStateBlob,
        get_active_workflow_pointer,
        get_workflow_blob,
        record_compat_fallback,
        resolve_workspace_identity,
        save_workflow_blob,
        set_active_workflow_pointer,
        ActiveWorkflowPointer,
    )

    ws, acct = resolve_workspace_identity(session)
    nested_ws = str(nested.get("workspace_id") or "").strip()
    if nested_ws and nested_ws != ws:
        record_compat_fallback(session, "CANONICAL_WORKSPACE_IDENTITY_MISMATCH", nested_ws)
        diag["decision"] = "blocked_workspace"
        diag["canonical_restore_decision"] = "blocked_workspace"
        return

    try:
        from music_workflow_persist_confirmed import get_persist_confirmed, has_unconfirmed_local_workflow_changes
    except ImportError:
        has_unconfirmed_local_workflow_changes = lambda _s: False  # type: ignore[assignment]
        get_persist_confirmed = lambda _s: {}  # type: ignore[assignment]

    canon_store = nested.get("store") if isinstance(nested.get("store"), dict) else {}
    canon_ptr_raw = nested.get("active_pointer") if isinstance(nested.get("active_pointer"), dict) else {}
    canon_ws_rev = int(nested.get("saved_workspace_revision") or 0)
    canon_saved_fp = str((nested.get("last_confirmed") or {}).get("last_confirmed_material_fingerprint") or "")
    local_confirmed = get_persist_confirmed(session)
    local_ws_rev = int(local_confirmed.get("last_confirmed_workspace_revision") or 0)
    unconfirmed = has_unconfirmed_local_workflow_changes(session)
    diag["canonical_restore_source"] = "cloud_slice"
    diag["has_unconfirmed_local_changes"] = unconfirmed
    diag["last_confirmed_workspace_revision"] = local_ws_rev
    diag["incoming_saved_workspace_revision"] = canon_ws_rev

    live_ptr = get_active_workflow_pointer(session)
    if unconfirmed and live_ptr:
        record_compat_fallback(session, "UNCONFIRMED_LOCAL_CHANGE_OVERWRITE_BLOCKED", str(canon_ws_rev))
        diag["decision"] = "unconfirmed_local_blocked"
        diag["canonical_restore_decision"] = "unconfirmed_local_blocked"
        return

    if canon_ws_rev and local_ws_rev and canon_ws_rev < local_ws_rev:
        record_compat_fallback(session, "CANONICAL_SAVE_ANCESTRY_CONFLICT", str(canon_ws_rev))
        diag["decision"] = "local_workspace_newer"
        diag["canonical_restore_decision"] = "local_workspace_newer"
        return

    if live_ptr and canon_ptr_raw:
        co = str(canon_ptr_raw.get("workflow_owner") or "")
        cs = str(canon_ptr_raw.get("workflow_session_id") or "")
        if co and cs and (co != live_ptr.workflow_owner or cs != live_ptr.workflow_session_id):
            record_compat_fallback(session, "CANONICAL_SESSION_IDENTITY_CONFLICT", cs)
            diag["decision"] = "inactive_session_store_only"
            diag["canonical_restore_decision"] = "inactive_session_store_only"

    blobs_in = (canon_store.get("blobs") or {}) if isinstance(canon_store, dict) else {}
    if not blobs_in and not canon_ptr_raw:
        diag["decision"] = "empty_slice"
        return

    try:
        from music_workflow_restore_guard import activate_workflow_restore_guard

        activate_workflow_restore_guard(session, source="canonical_restore")
    except ImportError:
        pass

    applied = 0
    for _key, raw in blobs_in.items():
        blob = WorkflowStateBlob.from_dict(raw if isinstance(raw, dict) else None)
        if not blob or not blob.workflow_owner:
            continue
        live_blob = get_workflow_blob(session, blob.workflow_owner, blob.workflow_session_id)
        if live_blob is not None and live_blob.material_fingerprint and blob.material_fingerprint:
            if live_blob.material_fingerprint == blob.material_fingerprint:
                continue
            try:
                from generated_jam_key_change import generated_key_hydrate_guard_blocks_blob

                if generated_key_hydrate_guard_blocks_blob(session, live_blob):
                    record_compat_fallback(session, "GENERATED_KEY_HYDRATE_GUARD_BLOCKED", blob.workflow_owner)
                    continue
            except ImportError:
                pass
            if unconfirmed:
                record_compat_fallback(session, "UNCONFIRMED_LOCAL_CHANGE_OVERWRITE_BLOCKED", blob.workflow_owner)
                continue
        if (
            live_blob is not None
            and canon_saved_fp
            and live_blob.material_fingerprint == canon_saved_fp
            and canon_ws_rev <= local_ws_rev
        ):
            continue
        save_workflow_blob(session, blob, source="canonical_hydrate")
        applied += 1
    diag["blobs_applied"] = applied

    if isinstance(canon_ptr_raw, dict) and canon_ptr_raw.get("workflow_owner"):
        owner = str(canon_ptr_raw.get("workflow_owner") or "")
        sid = str(canon_ptr_raw.get("workflow_session_id") or "")
        if owner and sid:
            try:
                from music_workflow_activation import ActivateWorkflowRequest, activate_workflow

                result = activate_workflow(
                    session,
                    ActivateWorkflowRequest(
                        target_owner=owner,
                        target_session_id=sid,
                        activation_source="canonical_restore",
                        persist_policy="none",
                    ),
                )
                if not result.ok:
                    diag["decision"] = "activation_blocked"
                    diag["canonical_restore_decision"] = result.error_code or "activation_failed"
                    try:
                        from music_workflow_restore_guard import complete_workflow_restore_guard

                        complete_workflow_restore_guard(session, reason="canonical_restore_activation_failed")
                    except ImportError:
                        pass
                    return
                try:
                    from music_workflow_restore_guard import complete_workflow_restore_guard

                    complete_workflow_restore_guard(session, reason="canonical_restore_activated")
                except ImportError:
                    pass
                diag["decision"] = "activated"
                diag["canonical_restore_decision"] = "activated"
                return
            except ImportError:
                pass
            ptr = ActiveWorkflowPointer.from_dict(canon_ptr_raw)
            if ptr:
                set_active_workflow_pointer(session, ptr, source="canonical_restore")
                try:
                    from music_workflow_restore_guard import complete_workflow_restore_guard

                    complete_workflow_restore_guard(session, reason="canonical_restore_pointer_only")
                except ImportError:
                    pass
                diag["decision"] = "pointer_only"


def gather_workflow_state_canonical_slice(session: dict[str, Any]) -> dict[str, Any]:
    """Nested blob for creative_workspace_state — caller must check should_gather first."""
    store = session.get(MUSIC_WORKFLOW_STATE_STORE_KEY)
    ptr = session.get(MUSIC_ACTIVE_WORKFLOW_KEY)
    if not isinstance(store, dict) and not isinstance(ptr, dict):
        return {}
    nested: dict[str, Any] = {
        "schema_version": 2,
        "store": copy.deepcopy(store) if isinstance(store, dict) else None,
        "active_pointer": copy.deepcopy(ptr) if isinstance(ptr, dict) else None,
    }
    try:
        from music_workflow_persist_confirmed import get_persist_confirmed
        from music_workflow_persist_lifecycle import WORKFLOW_PERSIST_PENDING_KEY

        pend = session.get(WORKFLOW_PERSIST_PENDING_KEY)
        if isinstance(pend, dict):
            nested["persist_request"] = copy.deepcopy(pend)
        confirmed = get_persist_confirmed(session)
        if confirmed:
            nested["last_confirmed"] = copy.deepcopy(confirmed)
        nested["saved_workspace_revision"] = int(session.get("_suite_applied_workspace_revision") or 0)
        if isinstance(ptr, dict):
            nested["saved_context_revision"] = int(ptr.get("context_revision") or 0)
    except ImportError:
        pass
    return nested


def should_gather_workflow_state_to_canonical(session: dict[str, Any], *, persist_reason: str) -> bool:
    """Gather only when the resolved save reason is material (not benign reruns/autosave alone)."""
    reason = str(persist_reason or "").strip()
    if reason not in WORKFLOW_STATE_SAVE_REASONS:
        return False
    note_workflow_persist_requested(session, reason)
    return True


__all__ = [
    "CWS_WORKFLOW_STATE_NESTED_KEY",
    "SAVE_REASON_WORKFLOW_STATE",
    "WORKFLOW_STATE_SAVE_REASONS",
    "apply_workflow_state_canonical_slice",
    "gather_workflow_state_canonical_slice",
    "should_gather_workflow_state_to_canonical",
]

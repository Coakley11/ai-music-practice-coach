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
    session.pop("_music_workflow_pending_canonical_reason", None)


def note_workflow_persist_skipped(session: dict[str, Any]) -> None:
    s = _persist_stats(session)
    s["workflow_persist_skipped_unchanged"] = int(s.get("workflow_persist_skipped_unchanged") or 0) + 1


def apply_workflow_state_canonical_slice(session: dict[str, Any], nested: Any) -> None:
    """Restore from cloud/canonical — rebind via activation when possible."""
    if not isinstance(nested, dict):
        return
    store = nested.get("store")
    ptr = nested.get("active_pointer")
    if isinstance(store, dict):
        session[MUSIC_WORKFLOW_STATE_STORE_KEY] = copy.deepcopy(store)
    if isinstance(ptr, dict):
        try:
            from music_workflow_activation import ActivateWorkflowRequest, activate_workflow

            owner = str(ptr.get("workflow_owner") or "")
            sid = str(ptr.get("workflow_session_id") or "")
            if owner and sid:
                activate_workflow(
                    session,
                    ActivateWorkflowRequest(
                        target_owner=owner,
                        target_session_id=sid,
                        activation_source="canonical_restore",
                        persist_policy="none",
                    ),
                )
                return
        except ImportError:
            pass
        session[MUSIC_ACTIVE_WORKFLOW_KEY] = copy.deepcopy(ptr)


def gather_workflow_state_canonical_slice(session: dict[str, Any]) -> dict[str, Any]:
    """Nested blob for creative_workspace_state — caller must check should_gather first."""
    store = session.get(MUSIC_WORKFLOW_STATE_STORE_KEY)
    ptr = session.get(MUSIC_ACTIVE_WORKFLOW_KEY)
    if not isinstance(store, dict) and not isinstance(ptr, dict):
        return {}
    return {
        "schema_version": 1,
        "store": copy.deepcopy(store) if isinstance(store, dict) else None,
        "active_pointer": copy.deepcopy(ptr) if isinstance(ptr, dict) else None,
    }


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

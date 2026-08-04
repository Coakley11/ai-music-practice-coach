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

WORKFLOW_STATE_SAVE_REASONS: frozenset[str] = frozenset(
    {
        SAVE_REASON_WORKFLOW_STATE,
        "music_workflow_activate",
    }
)


def should_gather_workflow_state_to_canonical(session: dict[str, Any], *, persist_reason: str) -> bool:
    return str(persist_reason or "").strip() in WORKFLOW_STATE_SAVE_REASONS


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


def apply_workflow_state_canonical_slice(session: dict[str, Any], nested: Any) -> None:
    """Restore from cloud/canonical — does not delete legacy keys."""
    if not isinstance(nested, dict):
        return
    store = nested.get("store")
    ptr = nested.get("active_pointer")
    if isinstance(store, dict):
        session[MUSIC_WORKFLOW_STATE_STORE_KEY] = copy.deepcopy(store)
    if isinstance(ptr, dict):
        session[MUSIC_ACTIVE_WORKFLOW_KEY] = copy.deepcopy(ptr)


__all__ = [
    "CWS_WORKFLOW_STATE_NESTED_KEY",
    "SAVE_REASON_WORKFLOW_STATE",
    "WORKFLOW_STATE_SAVE_REASONS",
    "apply_workflow_state_canonical_slice",
    "gather_workflow_state_canonical_slice",
    "should_gather_workflow_state_to_canonical",
]

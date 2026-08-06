"""Last confirmed durable workflow persist + unconfirmed local edit detection (Commit 6)."""

from __future__ import annotations

import copy
from typing import Any

WORKFLOW_PERSIST_CONFIRMED_KEY = "_music_workflow_persist_confirmed"


def get_persist_confirmed(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(WORKFLOW_PERSIST_CONFIRMED_KEY)
    return raw if isinstance(raw, dict) else {}


def note_persist_confirmed(
    session: dict[str, Any],
    *,
    request_id: str,
    owner: str,
    session_id: str,
    context_revision: int,
    material_fingerprint: str,
    workspace_revision: int = 0,
    reason: str = "",
) -> None:
    session[WORKFLOW_PERSIST_CONFIRMED_KEY] = {
        "last_confirmed_persist_request_id": str(request_id or ""),
        "last_confirmed_context_revision": int(context_revision or 0),
        "last_confirmed_material_fingerprint": str(material_fingerprint or "")[:32],
        "last_confirmed_workspace_revision": int(workspace_revision or 0),
        "last_confirmed_owner": str(owner or ""),
        "last_confirmed_session_id": str(session_id or ""),
        "last_confirmed_reason": str(reason or ""),
    }


def has_unconfirmed_local_workflow_changes(session: dict[str, Any]) -> bool:
    """True when live blob fingerprint differs from last confirmed durable save."""
    try:
        from music_workflow_persist_lifecycle import WORKFLOW_PERSIST_PENDING_KEY

        pend = session.get(WORKFLOW_PERSIST_PENDING_KEY)
        if isinstance(pend, dict) and not pend.get("persist_confirmed"):
            return True
    except ImportError:
        pass
    try:
        from generated_jam_key_change import GENERATED_KEY_PENDING_HYDRATE_GUARD_KEY

        if isinstance(session.get(GENERATED_KEY_PENDING_HYDRATE_GUARD_KEY), dict):
            return True
    except ImportError:
        pass
    try:
        from music_workflow_pending_generated_key_edit import peek_pending_generated_key_edit

        if peek_pending_generated_key_edit(session):
            return True
    except ImportError:
        pass
    confirmed = get_persist_confirmed(session)
    if not confirmed.get("last_confirmed_material_fingerprint"):
        return False
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if not ptr:
            return False
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        if blob is None:
            return False
        return str(blob.material_fingerprint or "") != str(confirmed.get("last_confirmed_material_fingerprint") or "")
    except ImportError:
        return False


def extract_workflow_persist_request_from_save_state(state: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    cws = state.get("creative_workspace_state")
    if not isinstance(cws, dict):
        ws = state.get("music_workspace_state")
        if isinstance(ws, dict):
            cws = ws.get("creative_workspace_state")
    if not isinstance(cws, dict):
        return {}
    nested = cws.get("music_workflow_state_v1")
    if not isinstance(nested, dict):
        return {}
    req = nested.get("persist_request")
    return copy.deepcopy(req) if isinstance(req, dict) else {}


__all__ = [
    "WORKFLOW_PERSIST_CONFIRMED_KEY",
    "extract_workflow_persist_request_from_save_state",
    "get_persist_confirmed",
    "has_unconfirmed_local_workflow_changes",
    "note_persist_confirmed",
]

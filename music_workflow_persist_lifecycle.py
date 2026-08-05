"""Workflow canonical persist request lifecycle — clear only after confirmed cloud save."""

from __future__ import annotations

import copy
import time
import uuid
from typing import Any

WORKFLOW_PERSIST_PENDING_KEY = "_music_workflow_persist_pending"
WORKFLOW_PENDING_CANONICAL_REASON_KEY = "_music_workflow_pending_canonical_reason"


def _pending(session: dict[str, Any]) -> dict[str, Any] | None:
    raw = session.get(WORKFLOW_PERSIST_PENDING_KEY)
    return raw if isinstance(raw, dict) else None


def request_workflow_canonical_persist(
    session: dict[str, Any],
    reason: str,
    *,
    expected_revision: int = 0,
    expected_fingerprint: str = "",
) -> str:
    """Material action requests durable workflow slice — not cleared until cloud save succeeds."""
    request_id = str(uuid.uuid4())
    payload = {
        "persist_request_id": request_id,
        "persist_reason": str(reason or "").strip(),
        "persist_requested_revision": int(expected_revision or 0),
        "persist_requested_fingerprint": str(expected_fingerprint or "")[:32],
        "persist_attempted": False,
        "persist_confirmed": False,
        "persist_error": "",
        "persist_cleared_reason": "",
        "requested_at": time.time(),
        "gather_called": False,
    }
    session[WORKFLOW_PERSIST_PENDING_KEY] = payload
    session[WORKFLOW_PENDING_CANONICAL_REASON_KEY] = payload["persist_reason"]
    try:
        from music_workflow_canonical_persistence import note_workflow_persist_requested

        note_workflow_persist_requested(session, payload["persist_reason"])
    except ImportError:
        pass
    return request_id


def resolve_workflow_persist_reason(session: dict[str, Any], *, fallback: str = "") -> str:
    pend = _pending(session)
    if pend and str(pend.get("persist_reason") or "").strip():
        return str(pend["persist_reason"]).strip()
    legacy = str(session.get(WORKFLOW_PENDING_CANONICAL_REASON_KEY) or "").strip()
    if legacy:
        return legacy
    return str(fallback or "").strip()


def note_workflow_gather_called(session: dict[str, Any]) -> None:
    pend = _pending(session)
    if pend is not None:
        pend["gather_called"] = True
        pend["persist_attempted"] = True


def confirm_workflow_persist_after_cloud_save(session: dict[str, Any], *, saved_cloud: bool, error: str = "") -> None:
    """Call from record_music_cloud_write_result — only successful saves clear matching pending request."""
    pend = _pending(session)
    if pend is None:
        session.pop(WORKFLOW_PENDING_CANONICAL_REASON_KEY, None)
        return
    if saved_cloud:
        pend["persist_confirmed"] = True
        pend["persist_cleared_reason"] = "cloud_save_ok"
        session.pop(WORKFLOW_PERSIST_PENDING_KEY, None)
        session.pop(WORKFLOW_PENDING_CANONICAL_REASON_KEY, None)
        try:
            from music_workflow_canonical_persistence import note_workflow_persist_performed

            ptr = session.get("_music_active_workflow")
            rev = int(ptr.get("context_revision") or 0) if isinstance(ptr, dict) else int(
                pend.get("persist_requested_revision") or 0
            )
            note_workflow_persist_performed(session, revision=rev)
        except ImportError:
            pass
    else:
        pend["persist_error"] = str(error or "cloud_save_failed")[:120]
        pend["persist_cleared_reason"] = "retained_for_retry"


def supersede_workflow_persist_request(session: dict[str, Any], *, reason: str) -> str:
    """Newer material change replaces pending request without clearing on old completion."""
    prev = _pending(session)
    if prev:
        prev["superseded_at"] = time.time()
    return request_workflow_canonical_persist(
        session,
        reason,
        expected_revision=int(prev.get("persist_requested_revision") or 0) if prev else 0,
    )


__all__ = [
    "WORKFLOW_PERSIST_PENDING_KEY",
    "WORKFLOW_PENDING_CANONICAL_REASON_KEY",
    "confirm_workflow_persist_after_cloud_save",
    "note_workflow_gather_called",
    "request_workflow_canonical_persist",
    "resolve_workflow_persist_reason",
    "supersede_workflow_persist_request",
]

"""Workflow canonical persist request lifecycle — clear only after confirmed cloud save."""

from __future__ import annotations

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
    owner: str = "",
    session_id: str = "",
    progression_fingerprint: str = "",
    source_type: str = "",
    song_or_session_id: str = "",
    expected_workspace_revision: int = 0,
) -> str:
    """Material action requests durable workflow slice — not cleared until matching cloud save succeeds."""
    request_id = str(uuid.uuid4())
    payload = {
        "persist_request_id": request_id,
        "persist_reason": str(reason or "").strip(),
        "persist_requested_revision": int(expected_revision or 0),
        "persist_requested_fingerprint": str(expected_fingerprint or "")[:32],
        "persist_requested_owner": str(owner or ""),
        "persist_requested_session_id": str(session_id or ""),
        "persist_requested_progression_fp": str(progression_fingerprint or "")[:32],
        "persist_source_type": str(source_type or ""),
        "persist_song_or_session_id": str(song_or_session_id or ""),
        "expected_workspace_base_revision": int(expected_workspace_revision or 0),
        "persist_attempted": False,
        "persist_confirmed": False,
        "persist_error": "",
        "persist_cleared_reason": "",
        "requested_at": time.time(),
        "gather_called": False,
        "superseded_by": "",
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


def confirm_workflow_persist_after_cloud_save(
    session: dict[str, Any],
    *,
    saved_cloud: bool,
    error: str = "",
    save_state: dict[str, Any] | None = None,
) -> None:
    """Clear pending only when saved payload confirms exact request id/revision/fingerprint."""
    pend = _pending(session)
    if pend is None:
        session.pop(WORKFLOW_PENDING_CANONICAL_REASON_KEY, None)
        return
    if not saved_cloud:
        pend["persist_error"] = str(error or "cloud_save_failed")[:120]
        pend["persist_cleared_reason"] = "retained_for_retry"
        pend["persist_confirmed"] = False
        return

    saved_ws = 0
    try:
        from music_workflow_persist_confirmed import extract_workflow_persist_request_from_save_state
        from music_workflow_state_store import record_compat_fallback

        saved_req = extract_workflow_persist_request_from_save_state(save_state or {})
        if not saved_req:
            record_compat_fallback(session, "UNRELATED_CLOUD_SUCCESS_NOT_WORKFLOW_CONFIRMATION", "no_slice")
            pend["persist_cleared_reason"] = "no_workflow_slice_in_payload"
            return
        saved_id = str(saved_req.get("persist_request_id") or "")
        pending_id = str(pend.get("persist_request_id") or "")
        if saved_id != pending_id:
            if pend.get("superseded_at"):
                pend["persist_cleared_reason"] = "superseded"
            else:
                record_compat_fallback(session, "PERSIST_CONFIRM_REQUEST_ID_MISMATCH", saved_id)
                pend["persist_cleared_reason"] = "request_id_mismatch"
            return
        if int(saved_req.get("persist_requested_revision") or 0) != int(pend.get("persist_requested_revision") or 0):
            record_compat_fallback(session, "PERSIST_CONFIRM_REVISION_MISMATCH", saved_id)
            pend["persist_cleared_reason"] = "revision_mismatch"
            return
        sf = str(saved_req.get("persist_requested_fingerprint") or "")[:32]
        pf = str(pend.get("persist_requested_fingerprint") or "")[:32]
        if sf and pf and sf != pf:
            record_compat_fallback(session, "PERSIST_CONFIRM_FINGERPRINT_MISMATCH", saved_id)
            pend["persist_cleared_reason"] = "fingerprint_mismatch"
            pend["persist_confirmed"] = False
            pend["persist_error"] = "fingerprint_mismatch"
            return
        saved_ws = 0
        if isinstance(save_state, dict):
            saved_ws = int(
                save_state.get("workspace_revision")
                or save_state.get("logical_revision")
                or save_state.get("suite_workspace_revision")
                or 0
            )
        expected_ws = int(pend.get("expected_workspace_base_revision") or 0)
        if expected_ws and saved_ws and saved_ws < expected_ws:
            record_compat_fallback(session, "PERSIST_CONFIRM_WORKSPACE_REVISION_REGRESSION", str(saved_ws))
            pend["persist_cleared_reason"] = "workspace_revision_regression"
            pend["persist_confirmed"] = False
            pend["persist_error"] = "cas_workspace_revision_regression"
            return
    except ImportError:
        saved_req = pend
        saved_ws = 0

    pend["persist_confirmed"] = True
    pend["persist_cleared_reason"] = "cloud_save_matched"
    cleared = dict(pend)
    session.pop(WORKFLOW_PERSIST_PENDING_KEY, None)
    session.pop(WORKFLOW_PENDING_CANONICAL_REASON_KEY, None)
    try:
        from music_workflow_persist_confirmed import note_persist_confirmed

        ws_rev = 0
        if isinstance(save_state, dict):
            ws_rev = int(save_state.get("workspace_revision") or save_state.get("logical_revision") or 0)
        note_persist_confirmed(
            session,
            request_id=str(cleared.get("persist_request_id") or saved_req.get("persist_request_id") or ""),
            owner=str(cleared.get("persist_requested_owner") or ""),
            session_id=str(cleared.get("persist_requested_session_id") or ""),
            context_revision=int(cleared.get("persist_requested_revision") or 0),
            material_fingerprint=str(cleared.get("persist_requested_fingerprint") or ""),
            workspace_revision=int(saved_ws or ws_rev),
            reason=str(cleared.get("persist_reason") or ""),
        )
        from music_workflow_canonical_persistence import note_workflow_persist_performed

        note_workflow_persist_performed(session, revision=int(cleared.get("persist_requested_revision") or 0))
    except ImportError:
        pass


def supersede_workflow_persist_request(
    session: dict[str, Any],
    *,
    reason: str,
    **kwargs: Any,
) -> str:
    """Newer material change replaces pending request."""
    prev = _pending(session)
    if prev:
        prev["superseded_at"] = time.time()
    return request_workflow_canonical_persist(
        session,
        reason,
        expected_revision=int(kwargs.get("expected_revision") or (prev.get("persist_requested_revision") if prev else 0) or 0),
        expected_fingerprint=str(kwargs.get("expected_fingerprint") or (prev.get("persist_requested_fingerprint") if prev else "")),
        owner=str(kwargs.get("owner") or (prev.get("persist_requested_owner") if prev else "")),
        session_id=str(kwargs.get("session_id") or (prev.get("persist_requested_session_id") if prev else "")),
        progression_fingerprint=str(kwargs.get("progression_fingerprint") or ""),
        source_type=str(kwargs.get("source_type") or ""),
        song_or_session_id=str(kwargs.get("song_or_session_id") or ""),
        expected_workspace_revision=int(kwargs.get("expected_workspace_revision") or 0),
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

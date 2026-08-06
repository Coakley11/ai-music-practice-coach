"""Pre-widget consume for Style Jam / Generator practice-key selectbox edits."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Literal

PENDING_GENERATED_KEY_EDIT_KEY = "_music_pending_generated_key_edit"
PENDING_GENERATED_KEY_EDIT_CONSUMED_SEQ_KEY = "_music_pending_generated_key_edit_consumed_seq"
PENDING_GENERATED_KEY_EDIT_USER_MESSAGE_KEY = "_music_pending_generated_key_edit_user_message"
PENDING_GENERATED_KEY_EDIT_TERMINAL_KEY = "_music_pending_generated_key_edit_terminal"

ConsumePhase = Literal["applied", "skipped", "failed", "already_consumed", "invalid"]

_OWNER_BY_WIDGET = {
    "improv_style_key": "style_jam",
    "improv_jam_key": "jam_session_generator",
}
_SOURCE_BY_WIDGET = {
    "improv_style_key": "on_improv_style_key_change",
    "improv_jam_key": "on_improv_jam_key_change",
}


def _next_seq(session: dict[str, Any]) -> int:
    raw = session.get(PENDING_GENERATED_KEY_EDIT_KEY)
    prev = int(raw.get("request_seq") or 0) if isinstance(raw, dict) else 0
    return prev + 1


def _parse_key_token(key: str) -> tuple[str, str]:
    try:
        from music_workflow_compatibility import _tonic_mode_from_token

        return _tonic_mode_from_token(str(key or "C"))
    except ImportError:
        token = str(key or "C").strip()
        if token.endswith("m") and len(token) > 1:
            return token[:-1], "minor"
        return token, "major"


def _key_token_from_blob(blob: Any) -> str:
    tonic = str(getattr(getattr(blob, "keys", None), "practice_tonic", "") or "").strip()
    mode = str(getattr(getattr(blob, "keys", None), "practice_mode", "major") or "major").strip().lower()
    if mode == "minor" and tonic and not tonic.endswith("m"):
        return f"{tonic}m"
    return tonic or "C"


def peek_pending_generated_key_edit(session: dict[str, Any]) -> dict[str, Any] | None:
    raw = session.get(PENDING_GENERATED_KEY_EDIT_KEY)
    return copy.deepcopy(raw) if isinstance(raw, dict) else None


def clear_pending_generated_key_edit(session: dict[str, Any]) -> None:
    session.pop(PENDING_GENERATED_KEY_EDIT_KEY, None)


def queue_pending_generated_key_edit(
    session: dict[str, Any],
    *,
    widget_key: str,
    selected_key_token: str,
) -> dict[str, Any] | None:
    """Capture typed intent from a widget callback — no canonical mutation."""
    wkey = str(widget_key or "").strip()
    owner = _OWNER_BY_WIDGET.get(wkey)
    source = _SOURCE_BY_WIDGET.get(wkey)
    selected = str(selected_key_token or session.get(wkey) or "").strip()
    if not owner or not source or not selected:
        return None
    try:
        from music_workflow_compatibility import legacy_session_id_for_owner
        from music_workflow_state_store import get_workflow_blob

        sid = str(legacy_session_id_for_owner(session, owner) or "").strip()
        if not sid:
            return None
        blob = get_workflow_blob(session, owner, sid)
        fp = str(getattr(blob, "material_fingerprint", "") or "") if blob else ""
        rev = int(getattr(blob, "context_revision", 0) or 0) if blob else 0
    except ImportError:
        sid = ""
        fp = ""
        rev = 0
    tonic, mode = _parse_key_token(selected)
    seq = _next_seq(session)
    payload = {
        "request_seq": seq,
        "request_token": hashlib.sha256(
            json.dumps(
                {
                    "seq": seq,
                    "owner": owner,
                    "sid": sid,
                    "wkey": wkey,
                    "key": selected,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()[:24],
        "workflow_owner": owner,
        "workflow_session_id": sid,
        "widget_key": wkey,
        "selected_key_token": selected,
        "practice_tonic": tonic,
        "practice_mode": mode,
        "callback_source": source,
        "material_fingerprint": fp[:32],
        "context_revision": rev,
    }
    session[PENDING_GENERATED_KEY_EDIT_KEY] = payload
    session.pop(PENDING_GENERATED_KEY_EDIT_TERMINAL_KEY, None)
    session.pop(PENDING_GENERATED_KEY_EDIT_USER_MESSAGE_KEY, None)
    return copy.deepcopy(payload)


def _validate_pending(session: dict[str, Any], pending: dict[str, Any]) -> str | None:
    wkey = str(pending.get("widget_key") or "").strip()
    owner = str(pending.get("workflow_owner") or "").strip()
    if _OWNER_BY_WIDGET.get(wkey) != owner:
        return "widget_owner_mismatch"
    if str(pending.get("callback_source") or "") != _SOURCE_BY_WIDGET.get(wkey, ""):
        return "callback_source_mismatch"
    try:
        from music_workflow_compatibility import legacy_session_id_for_owner

        live_sid = str(legacy_session_id_for_owner(session, owner) or "").strip()
        if live_sid and str(pending.get("workflow_session_id") or "").strip() != live_sid:
            return "session_id_mismatch"
    except ImportError:
        pass
    selected = str(pending.get("selected_key_token") or "").strip()
    if not selected:
        return "empty_key"
    return None


def _widgets_locked(session: dict[str, Any]) -> bool:
    try:
        from session_widget_safe import widgets_likely_instantiated

        return bool(widgets_likely_instantiated(session))
    except ImportError:
        return bool(session.get("_streamlit_widgets_locked_this_run"))


def _revert_widget_to_canonical(session: dict[str, Any], pending: dict[str, Any]) -> None:
    owner = str(pending.get("workflow_owner") or "")
    wkey = str(pending.get("widget_key") or "")
    sid = str(pending.get("workflow_session_id") or "")
    try:
        from music_workflow_compatibility import legacy_session_id_for_owner
        from music_workflow_state_store import get_workflow_blob

        live_sid = str(legacy_session_id_for_owner(session, owner) or "").strip() or sid
        blob = get_workflow_blob(session, owner, live_sid)
        if blob is not None and wkey:
            session[wkey] = _key_token_from_blob(blob)
    except ImportError:
        pass


def consume_pending_generated_key_edit(session: dict[str, Any], *, st: Any | None = None) -> ConsumePhase:
    pending = session.get(PENDING_GENERATED_KEY_EDIT_KEY)
    if not isinstance(pending, dict):
        return "skipped"
    seq = pending.get("request_seq")
    if seq is not None and session.get(PENDING_GENERATED_KEY_EDIT_CONSUMED_SEQ_KEY) == seq:
        clear_pending_generated_key_edit(session)
        return "already_consumed"
    if _widgets_locked(session):
        return "skipped"
    err = _validate_pending(session, pending)
    if err:
        session[PENDING_GENERATED_KEY_EDIT_TERMINAL_KEY] = {"reason": err, "pending": copy.deepcopy(pending)}
        session[PENDING_GENERATED_KEY_EDIT_USER_MESSAGE_KEY] = (
            "Could not apply the key change (invalid request). The previous key was restored."
        )
        _revert_widget_to_canonical(session, pending)
        clear_pending_generated_key_edit(session)
        return "invalid"
    try:
        from generated_jam_key_change import apply_pending_generated_key_edit_pre_widget

        ok = apply_pending_generated_key_edit_pre_widget(session, pending, st_like=st)
    except ImportError:
        ok = False
    if not ok:
        session[PENDING_GENERATED_KEY_EDIT_USER_MESSAGE_KEY] = (
            "Key change failed before the workflow could update. The previous key was restored — try again."
        )
        session[PENDING_GENERATED_KEY_EDIT_TERMINAL_KEY] = {
            "reason": "mutation_or_projection_failed",
            "pending": copy.deepcopy(pending),
        }
        _revert_widget_to_canonical(session, pending)
        clear_pending_generated_key_edit(session)
        return "failed"
    if seq is not None:
        session[PENDING_GENERATED_KEY_EDIT_CONSUMED_SEQ_KEY] = seq
    clear_pending_generated_key_edit(session)
    session.pop(PENDING_GENERATED_KEY_EDIT_USER_MESSAGE_KEY, None)
    return "applied"


def run_pre_widget_generated_key_edit_consumer(session: dict[str, Any], *, st: Any | None = None) -> ConsumePhase:
    return consume_pending_generated_key_edit(session, st=st)


__all__ = [
    "PENDING_GENERATED_KEY_EDIT_KEY",
    "PENDING_GENERATED_KEY_EDIT_CONSUMED_SEQ_KEY",
    "PENDING_GENERATED_KEY_EDIT_TERMINAL_KEY",
    "PENDING_GENERATED_KEY_EDIT_USER_MESSAGE_KEY",
    "clear_pending_generated_key_edit",
    "consume_pending_generated_key_edit",
    "peek_pending_generated_key_edit",
    "queue_pending_generated_key_edit",
    "run_pre_widget_generated_key_edit_consumer",
]

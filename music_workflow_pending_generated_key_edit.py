"""Pre-widget consume for Style Jam / Generator practice-key selectbox edits."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from typing import Any, Literal

_LOG = logging.getLogger("music.generated_key_change")

PENDING_GENERATED_KEY_EDIT_KEY = "_music_pending_generated_key_edit"
PENDING_GENERATED_KEY_EDIT_CONSUMED_SEQ_KEY = "_music_pending_generated_key_edit_consumed_seq"
PENDING_GENERATED_KEY_EDIT_USER_MESSAGE_KEY = "_music_pending_generated_key_edit_user_message"
PENDING_GENERATED_KEY_EDIT_TERMINAL_KEY = "_music_pending_generated_key_edit_terminal"
PENDING_GENERATED_KEY_EDIT_LAST_DIAG_KEY = "_music_pending_generated_key_edit_last_diag"

ConsumePhase = Literal["applied", "skipped", "failed", "already_consumed", "invalid"]

_OWNER_BY_WIDGET = {
    "improv_style_key": "style_jam",
    "improv_jam_key": "jam_session_generator",
}
_SOURCE_BY_WIDGET = {
    "improv_style_key": "on_improv_style_key_change",
    "improv_jam_key": "on_improv_jam_key_change",
}

_USER_MESSAGES = {
    "widget_owner_mismatch": "Key change rejected: widget does not match workflow owner.",
    "callback_source_mismatch": "Key change rejected: callback source mismatch.",
    "invalid_owner": "Key change rejected: unknown workflow owner.",
    "invalid_selected_key_token": "Key change rejected: empty or invalid key selection.",
    "invalid_tonic": "Key change rejected: could not parse key tonic.",
    "invalid_mode": "Key change rejected: could not parse key mode.",
    "session_id_mismatch": "Key change rejected: workflow session is no longer available.",
    "pointer_alignment_failure": "Key change failed: could not align the active workflow session.",
    "mutation_or_projection_failed": "Key change failed before the workflow could update.",
    "malformed_request_token": "Key change rejected: malformed pending request.",
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
    try:
        from music_theory import key_center_token

        tonic = str(getattr(getattr(blob, "keys", None), "practice_tonic", "") or "").strip()
        mode = str(getattr(getattr(blob, "keys", None), "practice_mode", "major") or "major").strip().lower()
        return key_center_token(tonic, mode)
    except ImportError:
        tonic = str(getattr(getattr(blob, "keys", None), "practice_tonic", "") or "").strip()
        mode = str(getattr(getattr(blob, "keys", None), "practice_mode", "major") or "major").strip().lower()
        if mode == "minor" and tonic and not tonic.endswith("m"):
            return f"{tonic}m"
        return tonic or "C"


def _workflow_identity_fingerprint(owner: str, session_id: str) -> str:
    return hashlib.sha256(f"{owner}|{session_id}".encode()).hexdigest()[:16]


def _collect_identity_snapshot(session: dict[str, Any], pending: dict[str, Any]) -> dict[str, Any]:
    owner = str(pending.get("workflow_owner") or "")
    pending_sid = str(pending.get("workflow_session_id") or "")
    snap: dict[str, Any] = {
        "request_seq": pending.get("request_seq"),
        "request_token": pending.get("request_token"),
        "workflow_owner": owner,
        "workflow_session_id": pending_sid,
        "widget_key": pending.get("widget_key"),
        "raw_widget_value": session.get(pending.get("widget_key")),
        "selected_key_token": pending.get("selected_key_token"),
        "practice_tonic": pending.get("practice_tonic"),
        "practice_mode": pending.get("practice_mode"),
        "callback_source": pending.get("callback_source"),
        "captured_context_revision": pending.get("context_revision"),
        "captured_material_fingerprint": pending.get("material_fingerprint"),
        "captured_identity_fingerprint": pending.get("identity_fingerprint"),
    }
    try:
        from music_workflow_compatibility import legacy_session_id_for_owner
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        snap["live_legacy_session_id"] = str(legacy_session_id_for_owner(session, owner) or "")
        ptr = get_active_workflow_pointer(session)
        if ptr:
            snap["active_pointer_owner"] = ptr.workflow_owner
            snap["active_pointer_session_id"] = ptr.workflow_session_id
        blob = get_workflow_blob(session, owner, pending_sid)
        if blob is not None:
            snap["current_context_revision"] = int(getattr(blob, "context_revision", 0) or 0)
            snap["current_material_fingerprint"] = str(getattr(blob, "material_fingerprint", "") or "")[:32]
            snap["current_identity_fingerprint"] = _workflow_identity_fingerprint(
                owner, str(blob.workflow_session_id or pending_sid)
            )
    except ImportError:
        pass
    return snap


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
        if blob is None:
            try:
                from music_workflow_compatibility import build_workflow_blob_from_legacy
                from music_workflow_state_store import save_workflow_blob

                blob = build_workflow_blob_from_legacy(session, owner)
                blob.workflow_owner = owner
                blob.workflow_session_id = sid
                save_workflow_blob(session, blob, source="generated_key_intent_capture")
            except ImportError:
                blob = None
        fp = str(getattr(blob, "material_fingerprint", "") or "") if blob else ""
        rev = int(getattr(blob, "context_revision", 0) or 0) if blob else 0
    except ImportError:
        sid = ""
        fp = ""
        rev = 0
    tonic, mode = _parse_key_token(selected)
    if not tonic:
        return None
    seq = _next_seq(session)
    payload = {
        "request_seq": seq,
        "request_token": hashlib.sha256(
            json.dumps(
                {"seq": seq, "owner": owner, "sid": sid, "wkey": wkey, "key": selected},
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
        "identity_fingerprint": _workflow_identity_fingerprint(owner, sid),
    }
    try:
        from music_workflow_pending_intent_scope import capture_pending_intent_scope

        payload["scope"] = capture_pending_intent_scope(session)
    except ImportError:
        pass
    session[PENDING_GENERATED_KEY_EDIT_KEY] = payload
    session.pop(PENDING_GENERATED_KEY_EDIT_TERMINAL_KEY, None)
    session.pop(PENDING_GENERATED_KEY_EDIT_USER_MESSAGE_KEY, None)
    return copy.deepcopy(payload)


def _validate_pending(session: dict[str, Any], pending: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    diag = _collect_identity_snapshot(session, pending)
    if not str(pending.get("request_token") or "").strip():
        diag["failed_predicate"] = "malformed_request_token"
        return "malformed_request_token", diag
    wkey = str(pending.get("widget_key") or "").strip()
    owner = str(pending.get("workflow_owner") or "").strip()
    if owner not in {"style_jam", "jam_session_generator"}:
        diag["failed_predicate"] = "invalid_owner"
        return "invalid_owner", diag
    if _OWNER_BY_WIDGET.get(wkey) != owner:
        diag["failed_predicate"] = "widget_owner_mismatch"
        return "widget_owner_mismatch", diag
    if str(pending.get("callback_source") or "") != _SOURCE_BY_WIDGET.get(wkey, ""):
        diag["failed_predicate"] = "callback_source_mismatch"
        return "callback_source_mismatch", diag
    selected = str(pending.get("selected_key_token") or "").strip()
    if not selected:
        diag["failed_predicate"] = "invalid_selected_key_token"
        return "invalid_selected_key_token", diag
    pt, pm = _parse_key_token(selected)
    if not pt:
        diag["failed_predicate"] = "invalid_tonic"
        return "invalid_tonic", diag
    if pm not in {"major", "minor"}:
        diag["failed_predicate"] = "invalid_mode"
        return "invalid_mode", diag
    pending["practice_tonic"] = pt
    pending["practice_mode"] = pm
    pending_sid = str(pending.get("workflow_session_id") or "").strip()
    if not pending_sid:
        diag["failed_predicate"] = "session_id_mismatch"
        return "session_id_mismatch", diag
    try:
        from music_workflow_state_store import get_workflow_blob

        if get_workflow_blob(session, owner, pending_sid) is None:
            diag["failed_predicate"] = "session_id_mismatch"
            return "session_id_mismatch", diag
    except ImportError:
        diag["failed_predicate"] = "session_id_mismatch"
        return "session_id_mismatch", diag
    diag["failed_predicate"] = None
    return None, diag


def _widgets_locked(session: dict[str, Any]) -> bool:
    try:
        from music_workflow_pre_widget_bootstrap import PRE_WIDGET_BOOTSTRAP_ACTIVE_KEY

        if session.get(PRE_WIDGET_BOOTSTRAP_ACTIVE_KEY):
            return False
    except ImportError:
        pass
    if session.get("_music_first_streamlit_widget"):
        return True
    try:
        from session_widget_safe import widgets_likely_instantiated

        return bool(widgets_likely_instantiated(session))
    except ImportError:
        return bool(session.get("_streamlit_widgets_locked_this_run"))


def _revert_widget_to_canonical(session: dict[str, Any], pending: dict[str, Any]) -> None:
    owner = str(pending.get("workflow_owner") or "")
    wkey = str(pending.get("widget_key") or "")
    pending_sid = str(pending.get("workflow_session_id") or "")
    try:
        from music_workflow_state_store import get_workflow_blob

        blob = get_workflow_blob(session, owner, pending_sid)
        if blob is not None and wkey:
            session[wkey] = _key_token_from_blob(blob)
    except ImportError:
        pass


def _fail_consume(
    session: dict[str, Any],
    pending: dict[str, Any],
    *,
    reason: str,
    diag: dict[str, Any],
) -> ConsumePhase:
    diag = {**diag, "reason": reason, "failed_predicate": reason}
    session[PENDING_GENERATED_KEY_EDIT_TERMINAL_KEY] = {
        "reason": reason,
        "pending": copy.deepcopy(pending),
        "diag": diag,
    }
    session[PENDING_GENERATED_KEY_EDIT_LAST_DIAG_KEY] = diag
    msg = _USER_MESSAGES.get(reason, f"Key change failed ({reason}).")
    session[PENDING_GENERATED_KEY_EDIT_USER_MESSAGE_KEY] = f"{msg} The previous key was restored."
    _LOG.info("[generated_key_change] consume_rejected %s", diag)
    _revert_widget_to_canonical(session, pending)
    clear_pending_generated_key_edit(session)
    return "failed" if reason == "mutation_or_projection_failed" else "invalid"


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
    err, diag = _validate_pending(session, pending)
    if err:
        return _fail_consume(session, pending, reason=err, diag=diag)
    try:
        from music_workflow_pending_intent_scope import (
            pending_intent_scope_matches,
            workflow_mutation_consume_allowed,
        )

        allowed, auth_reason = workflow_mutation_consume_allowed(session)
        if not allowed:
            session[PENDING_GENERATED_KEY_EDIT_LAST_DIAG_KEY] = {
                **diag,
                "failed_predicate": auth_reason,
                "consume_deferred": True,
            }
            return "skipped"
        scope_ok, scope_reason = pending_intent_scope_matches(session, pending)
        if not scope_ok:
            clear_pending_generated_key_edit(session)
            session[PENDING_GENERATED_KEY_EDIT_LAST_DIAG_KEY] = {**diag, "failed_predicate": scope_reason}
            return "invalid"
    except ImportError:
        pass
    try:
        from generated_jam_key_change import apply_pending_generated_key_edit_pre_widget

        ok = apply_pending_generated_key_edit_pre_widget(session, pending, st_like=st)
    except ImportError:
        ok = False
    if not ok:
        diag["failed_predicate"] = "pointer_alignment_failure"
        return _fail_consume(session, pending, reason="mutation_or_projection_failed", diag=diag)
    if seq is not None:
        session[PENDING_GENERATED_KEY_EDIT_CONSUMED_SEQ_KEY] = seq
    clear_pending_generated_key_edit(session)
    session.pop(PENDING_GENERATED_KEY_EDIT_USER_MESSAGE_KEY, None)
    session[PENDING_GENERATED_KEY_EDIT_LAST_DIAG_KEY] = {**diag, "result": "applied"}
    return "applied"


def run_pre_widget_generated_key_edit_consumer(session: dict[str, Any], *, st: Any | None = None) -> ConsumePhase:
    return consume_pending_generated_key_edit(session, st=st)


__all__ = [
    "PENDING_GENERATED_KEY_EDIT_KEY",
    "PENDING_GENERATED_KEY_EDIT_CONSUMED_SEQ_KEY",
    "PENDING_GENERATED_KEY_EDIT_LAST_DIAG_KEY",
    "PENDING_GENERATED_KEY_EDIT_TERMINAL_KEY",
    "PENDING_GENERATED_KEY_EDIT_USER_MESSAGE_KEY",
    "clear_pending_generated_key_edit",
    "consume_pending_generated_key_edit",
    "peek_pending_generated_key_edit",
    "queue_pending_generated_key_edit",
    "run_pre_widget_generated_key_edit_consumer",
]

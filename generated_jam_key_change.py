"""Structured trace + user practice-key edits for Style Jam / Jam Session Generator."""

from __future__ import annotations

import logging
from typing import Any

_LOG = logging.getLogger("music.generated_key_change")

GENERATED_KEY_CHANGE_DIAG_KEY = "_music_generated_key_change_diag"
GENERATED_KEY_USER_EDIT_CTX_KEY = "_music_generated_key_user_edit"
GENERATED_KEY_PENDING_HYDRATE_GUARD_KEY = "_music_generated_key_pending_hydrate_guard"

_STYLE_WIDGET = "improv_style_key"
_GEN_WIDGET = "improv_jam_key"
_OWNER_BY_WIDGET = {
    _STYLE_WIDGET: "style_jam",
    _GEN_WIDGET: "jam_session_generator",
}
_SOURCE_BY_WIDGET = {
    _STYLE_WIDGET: "on_improv_style_key_change",
    _GEN_WIDGET: "on_improv_jam_key_change",
}


def _widgets_locked(session: dict[str, Any]) -> bool:
    try:
        from session_widget_safe import widgets_likely_instantiated

        return bool(widgets_likely_instantiated(session))
    except ImportError:
        return bool(session.get("_streamlit_widgets_locked_this_run"))


def _restore_guard_active(session: dict[str, Any]) -> bool:
    try:
        from music_workflow_restore_guard import restore_guard_active

        return bool(restore_guard_active(session))
    except ImportError:
        return False


def _session_id_for_owner(session: dict[str, Any], owner: str) -> str:
    try:
        from music_workflow_compatibility import legacy_session_id_for_owner

        return str(legacy_session_id_for_owner(session, owner) or "")
    except ImportError:
        return ""


def _blob_key_snapshot(session: dict[str, Any], owner: str) -> tuple[str, str]:
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        sid = _session_id_for_owner(session, owner)
        if ptr and str(ptr.workflow_owner or "") == owner:
            sid = str(ptr.workflow_session_id or sid)
        blob = get_workflow_blob(session, owner, sid)
        if blob is None:
            return "", f"{owner}|{sid}"
        tonic = str(blob.keys.practice_tonic or "").strip()
        mode = str(blob.keys.practice_mode or "major").strip().lower()
        token = f"{tonic}m" if mode == "minor" and tonic and not tonic.endswith("m") else tonic
        return token, f"{owner}|{sid}"
    except ImportError:
        return "", ""


def log_generated_key_change(session: dict[str, Any], phase: str, **fields: Any) -> None:
    payload = {"phase": phase, **fields}
    diag = session.get(GENERATED_KEY_CHANGE_DIAG_KEY)
    if not isinstance(diag, list):
        diag = []
        session[GENERATED_KEY_CHANGE_DIAG_KEY] = diag
    diag.append(payload)
    _LOG.info("[generated_key_change] %s %s", phase, " ".join(f"{k}={v!r}" for k, v in fields.items()))


def mark_generated_key_hydrate_guard(
    session: dict[str, Any],
    *,
    owner: str,
    session_id: str,
    requested_key: str,
    material_fingerprint: str,
) -> None:
    session[GENERATED_KEY_PENDING_HYDRATE_GUARD_KEY] = {
        "owner": str(owner or ""),
        "session_id": str(session_id or ""),
        "requested_key": str(requested_key or ""),
        "material_fingerprint": str(material_fingerprint or "")[:32],
    }


def generated_key_hydrate_guard_blocks_blob(session: dict[str, Any], blob: Any) -> bool:
    guard = session.get(GENERATED_KEY_PENDING_HYDRATE_GUARD_KEY)
    if not isinstance(guard, dict):
        return False
    if str(getattr(blob, "workflow_owner", "") or "") != str(guard.get("owner") or ""):
        return False
    if str(getattr(blob, "workflow_session_id", "") or "") != str(guard.get("session_id") or ""):
        return False
    live_fp = str(getattr(blob, "material_fingerprint", "") or "")
    guard_fp = str(guard.get("material_fingerprint") or "")
    return bool(live_fp and guard_fp and live_fp == guard_fp)


def clear_generated_key_hydrate_guard(session: dict[str, Any]) -> None:
    session.pop(GENERATED_KEY_PENDING_HYDRATE_GUARD_KEY, None)


def align_generated_workflow_pointer_for_key_edit(session: dict[str, Any], owner: str) -> bool:
    """Point at the generated-workflow blob without activation restore over widget values."""
    try:
        from music_workflow_compatibility import build_workflow_blob_from_legacy, legacy_session_id_for_owner
        from music_workflow_state_store import (
            ActiveWorkflowPointer,
            get_active_workflow_pointer,
            get_workflow_blob,
            save_workflow_blob,
            set_active_workflow_pointer,
        )
    except ImportError:
        return False
    sid = str(legacy_session_id_for_owner(session, owner) or "").strip()
    if not sid:
        return False
    ptr = get_active_workflow_pointer(session)
    if ptr and str(ptr.workflow_owner or "") == owner and str(ptr.workflow_session_id or "") == sid:
        return True
    blob = get_workflow_blob(session, owner, sid)
    if blob is None:
        blob = build_workflow_blob_from_legacy(session, owner)
        blob.workflow_owner = owner
        blob.workflow_session_id = sid
        save_workflow_blob(session, blob, source="generated_key_edit_align")
    set_active_workflow_pointer(
        session,
        ActiveWorkflowPointer(workflow_owner=owner, workflow_session_id=sid),
        source="generated_key_edit_align",
    )
    return True


def apply_generated_workflow_practice_key_user_edit(
    session: dict[str, Any],
    *,
    widget_key: str,
    st_like: Any | None = None,
) -> bool:
    owner = _OWNER_BY_WIDGET.get(str(widget_key or "").strip())
    source = _SOURCE_BY_WIDGET.get(str(widget_key or "").strip())
    if not owner or not source:
        return False
    requested = str(session.get(widget_key) or "").strip()
    if not requested:
        return False
    old_blob_key, ptr_label = _blob_key_snapshot(session, owner)
    log_generated_key_change(
        session,
        "widget_event",
        workflow_owner=owner,
        widget_key=widget_key,
        widget_value=requested,
        old_blob_key=old_blob_key,
        new_requested_key=requested,
        callback_name=source,
        callback_source=source,
        widgets_locked=_widgets_locked(session),
        restore_guard_active=_restore_guard_active(session),
        active_pointer=ptr_label,
    )
    if not align_generated_workflow_pointer_for_key_edit(session, owner):
        log_generated_key_change(session, "owner_alignment", ok=False, owner=owner)
        return False
    log_generated_key_change(session, "owner_alignment", ok=True, owner=owner)
    session[GENERATED_KEY_USER_EDIT_CTX_KEY] = {
        "widget_key": widget_key,
        "owner": owner,
        "requested_key": requested,
        "source": source,
    }
    try:
        from music_workflow_mutation import update_active_practice_key

        log_generated_key_change(session, "mutation_start", requested_key=requested, owner=owner)
        result = update_active_practice_key(
            session,
            requested,
            source=source,
            transpose_progression=True,
        )
        log_generated_key_change(
            session,
            "mutation_result",
            ok=result.ok,
            error_code=result.error_code,
            trace=result.trace,
        )
        if not result.ok:
            session.pop(GENERATED_KEY_USER_EDIT_CTX_KEY, None)
            return False
    except ImportError:
        session.pop(GENERATED_KEY_USER_EDIT_CTX_KEY, None)
        return False
    new_blob_key, _ = _blob_key_snapshot(session, owner)
    log_generated_key_change(
        session,
        "projection_result",
        blob_key=new_blob_key,
        widget_key=session.get(widget_key),
        concert_key=session.get("concert_key"),
        display_key=session.get("display_key"),
    )
    try:
        from music_workflow_persist_lifecycle import WORKFLOW_PERSIST_PENDING_KEY

        pend = session.get(WORKFLOW_PERSIST_PENDING_KEY)
        log_generated_key_change(
            session,
            "persist_queued",
            pending=bool(isinstance(pend, dict) and not pend.get("persist_confirmed")),
            reason=str((pend or {}).get("persist_reason") or "") if isinstance(pend, dict) else "",
        )
    except ImportError:
        pass
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if ptr:
            blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
            if blob:
                mark_generated_key_hydrate_guard(
                    session,
                    owner=str(blob.workflow_owner or ""),
                    session_id=str(blob.workflow_session_id or ""),
                    requested_key=requested,
                    material_fingerprint=str(blob.material_fingerprint or ""),
                )
    except ImportError:
        pass
    session[widget_key] = requested
    if owner == "style_jam":
        try:
            from creative_key_sync import sync_style_jam_legacy_after_authoritative_key

            sync_style_jam_legacy_after_authoritative_key(session, requested, st_like=st_like)
        except ImportError:
            pass
    else:
        try:
            from creative_key_sync import (
                IMPROV_JAM_KEY_TRACKER,
                apply_creative_concert_key,
                invalidate_creative_backing_context,
            )

            apply_creative_concert_key(session, requested, st_like=st_like, source="creative_jam_session")
            session[IMPROV_JAM_KEY_TRACKER] = requested
            invalidate_creative_backing_context(session)
        except ImportError:
            pass
    try:
        from generated_jam_key_context import activate_generated_jam_key_ownership

        entry = "Style Jam Mode" if owner == "style_jam" else "Jam Session Generator"
        activate_generated_jam_key_ownership(session, entry_mode=entry, practice_key=requested)
    except ImportError:
        pass
    log_generated_key_change(
        session,
        "after_callback",
        widget_value=session.get(widget_key),
        blob_key=new_blob_key,
    )
    log_generated_key_change(
        session,
        "next_run_value",
        widget_key=widget_key,
        widget_value=session.get(widget_key),
        blob_key=_blob_key_snapshot(session, owner)[0],
        concert_key=session.get("concert_key"),
        display_key=session.get("display_key"),
    )
    session.pop(GENERATED_KEY_USER_EDIT_CTX_KEY, None)
    return True


__all__ = [
    "GENERATED_KEY_CHANGE_DIAG_KEY",
    "GENERATED_KEY_PENDING_HYDRATE_GUARD_KEY",
    "GENERATED_KEY_USER_EDIT_CTX_KEY",
    "apply_generated_workflow_practice_key_user_edit",
    "align_generated_workflow_pointer_for_key_edit",
    "clear_generated_key_hydrate_guard",
    "generated_key_hydrate_guard_blocks_blob",
    "log_generated_key_change",
    "mark_generated_key_hydrate_guard",
]

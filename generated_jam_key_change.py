"""Structured trace + pre-widget apply for Style Jam / Jam Session Generator keys."""

from __future__ import annotations

import logging
from typing import Any

_LOG = logging.getLogger("music.generated_key_change")

GENERATED_KEY_CHANGE_DIAG_KEY = "_music_generated_key_change_diag"
GENERATED_KEY_PENDING_HYDRATE_GUARD_KEY = "_music_generated_key_pending_hydrate_guard"
GENERATED_KEY_EDIT_OUTCOME_KEY = "_music_generated_key_edit_outcome"

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


def align_generated_workflow_pointer_for_key_edit(
    session: dict[str, Any],
    owner: str,
    *,
    session_id: str = "",
) -> bool:
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
    sid = str(session_id or "").strip() or str(legacy_session_id_for_owner(session, owner) or "").strip()
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


def capture_generated_key_edit_intent(session: dict[str, Any], *, widget_key: str) -> bool:
    """Widget callback — capture only; mutation runs pre-widget on the next script run."""
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
        mutation_deferred=True,
    )
    try:
        from music_workflow_pending_generated_key_edit import queue_pending_generated_key_edit

        pending = queue_pending_generated_key_edit(session, widget_key=widget_key, selected_key_token=requested)
        if not pending:
            return False
        log_generated_key_change(
            session,
            "intent_captured",
            request_seq=pending.get("request_seq"),
            workflow_owner=owner,
            workflow_session_id=pending.get("workflow_session_id"),
        )
        return True
    except ImportError:
        return False


def _finalize_generated_key_edit_after_mutation(
    session: dict[str, Any],
    *,
    owner: str,
    widget_key: str,
    requested: str,
    st_like: Any | None = None,
) -> None:
    """Sync widget-bound session keys only — canonical blob is already committed."""
    session[widget_key] = requested
    if owner == "style_jam":
        try:
            from generated_workflow_projection import sync_style_jam_legacy_from_active_blob

            sync_style_jam_legacy_from_active_blob(
                session,
                writer="_finalize_generated_key_edit",
                phase="post_mutation",
            )
        except ImportError:
            try:
                from creative_key_sync import IMPROV_STYLE_KEY_TRACKER, sync_style_jam_legacy_after_authoritative_key

                sync_style_jam_legacy_after_authoritative_key(session, requested, st_like=st_like)
                session[IMPROV_STYLE_KEY_TRACKER] = requested
            except ImportError:
                pass
    else:
        try:
            from creative_key_sync import IMPROV_JAM_KEY_TRACKER, invalidate_creative_backing_context

            session[IMPROV_JAM_KEY_TRACKER] = requested
            try:
                from music_workflow_generated_session import finalize_generated_jam_session_key_seal

                finalize_generated_jam_session_key_seal(session, requested)
            except ImportError:
                meta = dict(session.get("improv_style_meta") or {})
                meta["key"] = requested
                session["improv_style_meta"] = meta
            invalidate_creative_backing_context(session)
        except ImportError:
            pass


def apply_pending_generated_key_edit_pre_widget(
    session: dict[str, Any],
    pending: dict[str, Any],
    *,
    st_like: Any | None = None,
) -> bool:
    """Apply captured intent while widgets are not instantiated."""
    owner = str(pending.get("workflow_owner") or "").strip()
    source = str(pending.get("callback_source") or "").strip()
    widget_key = str(pending.get("widget_key") or "").strip()
    requested = str(pending.get("selected_key_token") or "").strip()
    if not owner or not source or not widget_key or not requested:
        return False
    old_blob_key, _ = _blob_key_snapshot(session, owner)
    log_generated_key_change(
        session,
        "pre_widget_consume_start",
        workflow_owner=owner,
        widget_key=widget_key,
        requested_key=requested,
        old_blob_key=old_blob_key,
        request_seq=pending.get("request_seq"),
    )
    if not align_generated_workflow_pointer_for_key_edit(
        session,
        owner,
        session_id=str(pending.get("workflow_session_id") or ""),
    ):
        log_generated_key_change(session, "owner_alignment", ok=False, owner=owner)
        return False
    log_generated_key_change(session, "owner_alignment", ok=True, owner=owner)
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
            session[GENERATED_KEY_EDIT_OUTCOME_KEY] = {
                "canonical_commit": "FAIL",
                "progression_rebuild": "FAIL",
                "backing_invalidation": "SKIPPED",
                "compatibility_projection": "SKIPPED",
                "error_code": result.error_code,
            }
            return False
    except ImportError:
        return False
    projection_status = "SUCCESS"
    if str(getattr(result, "error_code", "") or "") == "PROJECTION_DEFERRED":
        projection_status = "DEFERRED"
        try:
            from music_workflow_deferred_legacy_projection import try_complete_deferred_legacy_projection

            completed = try_complete_deferred_legacy_projection(session)
            if completed.get("compatibility_projection") == "SUCCESS":
                projection_status = "SUCCESS"
        except ImportError:
            pass
    ptr_after = None
    blob_after = None
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr_after = get_active_workflow_pointer(session)
        if ptr_after:
            blob_after = get_workflow_blob(session, ptr_after.workflow_owner, ptr_after.workflow_session_id)
    except ImportError:
        pass
    progression_ok = "SUCCESS"
    if blob_after is not None and old_blob_key and old_blob_key != requested:
        progression_ok = "SUCCESS" if blob_after.section_map else "FAIL"
    session[GENERATED_KEY_EDIT_OUTCOME_KEY] = {
        "canonical_commit": "SUCCESS",
        "progression_rebuild": progression_ok,
        "backing_invalidation": "SUCCESS",
        "compatibility_projection": projection_status,
    }
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
    _finalize_generated_key_edit_after_mutation(
        session, owner=owner, widget_key=widget_key, requested=requested, st_like=st_like
    )
    if owner == "style_jam":
        try:
            from music_workflow_generated_session import finalize_generated_style_jam_key_seal

            finalize_generated_style_jam_key_seal(session, requested)
        except ImportError:
            pass
        try:
            from creative_key_sync import invalidate_creative_backing_context

            invalidate_creative_backing_context(session)
        except ImportError:
            pass
    log_generated_key_change(
        session,
        "next_run_value",
        widget_key=widget_key,
        widget_value=session.get(widget_key),
        blob_key=new_blob_key,
        concert_key=session.get("concert_key"),
        display_key=session.get("display_key"),
    )
    return True


def mutate_generated_practice_key_from_control(
    session: dict[str, Any],
    new_key: str,
    *,
    control: str = "sidebar",
    st_like: Any | None = None,
) -> bool:
    """Canonical generated key change — shared by Jam/Style widget and sidebar Practice key."""
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
    except ImportError:
        return False
    if ptr is None or str(ptr.workflow_owner or "") not in {"style_jam", "jam_session_generator"}:
        return False
    owner = str(ptr.workflow_owner or "")
    source = "on_improv_jam_key_change" if owner == "jam_session_generator" else "on_improv_style_key_change"
    widget_key = "improv_jam_key" if owner == "jam_session_generator" else "improv_style_key"
    requested = str(new_key or "").strip()
    if not requested:
        return False
    try:
        from workflow_key_identity import normalize_user_practice_key_selection, resolve_active_workflow_key_identity

        default_mode = "major"
        cur = resolve_active_workflow_key_identity(session)
        if cur is not None:
            default_mode = cur.practice_mode
        _tonic, _mode, requested = normalize_user_practice_key_selection(
            requested,
            default_mode=default_mode,
        )
    except ImportError:
        pass
    log_generated_key_change(
        session,
        "control_mutation_start",
        workflow_owner=owner,
        control=control,
        requested_key=requested,
        widget_key=widget_key,
    )
    try:
        from music_workflow_mutation import update_active_practice_key

        result = update_active_practice_key(
            session,
            requested,
            source=source,
            transpose_progression=True,
        )
        if not result.ok:
            session[GENERATED_KEY_EDIT_OUTCOME_KEY] = {
                "canonical_commit": "FAIL",
                "error_code": result.error_code,
                "control": control,
            }
            return False
    except ImportError:
        return False
    _finalize_generated_key_edit_after_mutation(
        session,
        owner=owner,
        widget_key=widget_key,
        requested=requested,
        st_like=st_like,
    )
    try:
        from generated_workflow_projection import project_generated_owner_from_active_blob

        project_generated_owner_from_active_blob(session, writer=f"mutate_generated:{control}")
    except ImportError:
        pass
    if owner == "jam_session_generator":
        try:
            from improv_jam_session_projection import sync_improv_jam_session_from_active_blob

            sync_improv_jam_session_from_active_blob(
                session,
                writer=f"mutate_generated_practice_key:{control}",
                phase="post_mutation",
            )
        except ImportError:
            pass
    try:
        from generated_jam_key_context import refresh_generated_jam_key_context_from_blob

        refresh_generated_jam_key_context_from_blob(session)
    except ImportError:
        pass
    try:
        from musical_context_coherence import clear_coherence_handoff_block

        clear_coherence_handoff_block(session)
    except ImportError:
        session.pop("_musical_context_coherence_handoff_block", None)
    try:
        from creative_session_state import sync_creative_session_from_session

        sync_creative_session_from_session(session)
    except ImportError:
        pass
    log_generated_key_change(session, "control_mutation_done", workflow_owner=owner, requested_key=requested)
    return True


__all__ = [
    "GENERATED_KEY_CHANGE_DIAG_KEY",
    "GENERATED_KEY_EDIT_OUTCOME_KEY",
    "GENERATED_KEY_PENDING_HYDRATE_GUARD_KEY",
    "align_generated_workflow_pointer_for_key_edit",
    "apply_pending_generated_key_edit_pre_widget",
    "capture_generated_key_edit_intent",
    "clear_generated_key_hydrate_guard",
    "generated_key_hydrate_guard_blocks_blob",
    "log_generated_key_change",
    "mutate_generated_practice_key_from_control",
    "mark_generated_key_hydrate_guard",
]

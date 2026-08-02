"""Restore-phase gating — bootstrap projections must not block cloud apply or saves."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

WORKSPACE_RESTORE_IN_PROGRESS_KEY = "_music_workspace_restore_in_progress"
USER_EDIT_TRACKING_ENABLED_KEY = "_music_user_edit_tracking_enabled"
PENDING_USER_EDITS_KEY = "_music_pending_user_edits_queue"
AUTHORITATIVE_PAYLOAD_APPLIED_KEY = "_music_authoritative_payload_applied"
SELECTED_PAYLOAD_REVISION_KEY = "_music_selected_payload_revision"
ACCOUNT_RESOLUTION_DIAG_KEY = "_music_account_resolution_diag"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def workspace_restore_in_progress(session: dict[str, Any]) -> bool:
    return bool(session.get(WORKSPACE_RESTORE_IN_PROGRESS_KEY))


def user_edit_tracking_enabled(session: dict[str, Any]) -> bool:
    return bool(session.get(USER_EDIT_TRACKING_ENABLED_KEY))


def begin_workspace_restore(session: dict[str, Any]) -> None:
    session[WORKSPACE_RESTORE_IN_PROGRESS_KEY] = True
    session.pop(USER_EDIT_TRACKING_ENABLED_KEY, None)


def should_record_user_local_dirty(session: dict[str, Any]) -> bool:
    if workspace_restore_in_progress(session):
        return False
    if user_edit_tracking_enabled(session):
        return True
    try:
        from music_restore_phase import music_restore_phase_complete

        return music_restore_phase_complete(session)
    except ImportError:
        return bool(session.get("_music_restore_phase_complete"))


def clear_bootstrap_local_dirty_flags(session: dict[str, Any]) -> None:
    try:
        from active_song_state import clear_active_song_local_edit
        from backing_track_state import clear_backing_local_edit
        from practice_state import clear_practice_local_edit
        from studio_nav_state import clear_studio_nav_local_edit

        clear_active_song_local_edit(session)
        clear_practice_local_edit(session)
        clear_studio_nav_local_edit(session)
        clear_backing_local_edit(session)
    except ImportError:
        pass
    session.pop("_active_song_restore_skipped_reason", None)
    session.pop("_practice_restore_skipped_reason", None)
    session.pop("_studio_nav_restore_skipped_reason", None)
    session.pop("_backing_restore_skipped_reason", None)


def prepare_music_cold_start_restore(session: dict[str, Any], app_id: str) -> None:
    """Clear startup/bootstrap dirty so authoritative cloud/disk can apply."""
    if str(app_id or "").strip().lower() != "music":
        return
    begin_workspace_restore(session)
    try:
        from music_workspace_hydration import can_finalize_music_restore

        if can_finalize_music_restore(session) and user_edit_tracking_enabled(session):
            return
    except ImportError:
        if session.get("_music_workspace_blob_hydrated") and user_edit_tracking_enabled(session):
            return
    try:
        from suite_user_persistence import _local_dirty_key

        session.pop(_local_dirty_key(app_id), None)
    except ImportError:
        pass
    session.pop("_suite_autosave_block_reason", None)
    session.pop("_suite_workspace_sync_skipped_no_apply", None)
    clear_bootstrap_local_dirty_flags(session)


def complete_workspace_restore_after_apply(
    session: dict[str, Any],
    *,
    source: str,
    payload: dict[str, Any] | None,
) -> None:
    session.pop(WORKSPACE_RESTORE_IN_PROGRESS_KEY, None)
    session[USER_EDIT_TRACKING_ENABLED_KEY] = True
    clear_bootstrap_local_dirty_flags(session)
    if source in ("cloud", "disk") and isinstance(payload, dict) and payload:
        session[AUTHORITATIVE_PAYLOAD_APPLIED_KEY] = True
        try:
            from workspace_revision import stamp_applied_workspace_revision, workspace_revision_from_blob

            rev = workspace_revision_from_blob(payload)
            session[SELECTED_PAYLOAD_REVISION_KEY] = rev
            stamp_applied_workspace_revision(session, payload)
        except ImportError:
            pass
    try:
        from suite_user_persistence import clear_workspace_autosave_block

        clear_workspace_autosave_block(type("St", (), {"session_state": session})(), "music")
    except ImportError:
        session.pop("_suite_autosave_blocked::music", None)
    session.pop("_suite_autosave_block_reason", None)
    session.pop("_suite_workspace_sync_skipped_no_apply", None)
    merge_pending_user_edits_after_hydration(session)


def record_authoritative_payload_applied(
    session: dict[str, Any],
    *,
    source: str,
    payload: dict[str, Any] | None,
) -> None:
    if source not in ("cloud", "disk") or not isinstance(payload, dict) or not payload:
        session[AUTHORITATIVE_PAYLOAD_APPLIED_KEY] = False
        return
    session[AUTHORITATIVE_PAYLOAD_APPLIED_KEY] = True
    try:
        from workspace_revision import workspace_revision_from_blob

        session[SELECTED_PAYLOAD_REVISION_KEY] = workspace_revision_from_blob(payload)
    except ImportError:
        pass


def authoritative_payload_applied(session: dict[str, Any]) -> bool:
    return bool(session.get(AUTHORITATIVE_PAYLOAD_APPLIED_KEY))


def queue_pending_user_edit(session: dict[str, Any], field: str, *, reason: str = "") -> None:
    if not field:
        return
    queue = session.get(PENDING_USER_EDITS_KEY)
    if not isinstance(queue, list):
        queue = []
    queue.append(
        {
            "field": str(field),
            "reason": str(reason or ""),
            "created_at": _utc_now_iso(),
        }
    )
    session[PENDING_USER_EDITS_KEY] = queue


def merge_pending_user_edits_after_hydration(session: dict[str, Any]) -> None:
    queue = session.get(PENDING_USER_EDITS_KEY)
    if not isinstance(queue, list) or not queue:
        return
    session["_music_pending_edit_merged_after_hydration"] = True
    session["_music_pending_edit_fields"] = [str(x.get("field") or "") for x in queue if isinstance(x, dict)]
    session.pop(PENDING_USER_EDITS_KEY, None)


def record_account_workspace_identity(session: dict[str, Any], app_id: str) -> None:
    diag: dict[str, Any] = {
        "account_resolution_attempted": True,
        "account_id_resolved": False,
        "account_id": "",
        "workspace_key": "",
        "cloud_document_path": "",
        "authenticated": False,
        "account_hint": "(unknown)",
        "account_resolution_error": "",
    }
    try:
        from suite_user import get_account_user_id

        uid = str(get_account_user_id() or "").strip()
        if uid:
            diag["account_id_resolved"] = True
            diag["account_id"] = uid
            diag["authenticated"] = True
            diag["account_hint"] = uid
            session["_suite_cloud_user_hint"] = uid
    except Exception as exc:
        diag["account_resolution_error"] = str(exc)
    try:
        from suite_auth import AUTH_USER_EMAIL_KEY

        email = str(session.get(AUTH_USER_EMAIL_KEY) or session.get("user_email") or "").strip()
        if email:
            diag["account_hint"] = email
            session["_suite_cloud_user_hint"] = email
            diag["authenticated"] = True
    except ImportError:
        pass
    try:
        from suite_workspace import get_active_workspace_id, scoped_cloud_app_id

        ws = str(get_active_workspace_id() or "").strip()
        diag["workspace_key"] = ws
        diag["cloud_document_path"] = f"{scoped_cloud_app_id(app_id)}/{ws or '(default)'}"
    except Exception as exc:
        if not diag["account_resolution_error"]:
            diag["account_resolution_error"] = str(exc)
    session[ACCOUNT_RESOLUTION_DIAG_KEY] = diag


def collect_revision_consistency_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    try:
        from workspace_revision import (
            APPLIED_REVISION_KEY,
            CLOUD_REVISION_KEY,
            LOCAL_REVISION_KEY,
            workspace_revision_from_blob,
        )
    except ImportError:
        return {}
    selected_source = str(session.get("_music_cloud_payload_source") or "none")
    selected_rev = session.get(SELECTED_PAYLOAD_REVISION_KEY)
    cloud_rev = session.get(CLOUD_REVISION_KEY)
    applied = session.get(APPLIED_REVISION_KEY)
    local_rev = session.get(LOCAL_REVISION_KEY)
    payload = session.get("_suite_last_cloud_fetch_payload")
    disk_rev = workspace_revision_from_blob(payload if isinstance(payload, dict) else {})
    valid = True
    reasons: list[str] = []
    if session.get("_suite_persist_restore_applied") and not authoritative_payload_applied(session):
        valid = False
        reasons.append("restore_applied_without_authoritative_payload")
    if selected_source == "none" and authoritative_payload_applied(session):
        valid = False
        reasons.append("applied_without_payload_source")
    if applied is not None and selected_rev is not None and int(applied) != int(selected_rev):
        if selected_source in ("cloud", "disk"):
            valid = False
            reasons.append("applied_revision_ne_selected_payload_revision")
    if local_rev is not None and applied is not None and int(local_rev) > int(applied) + 1:
        reasons.append("local_revision_ahead_of_applied")
    return {
        "selected_payload_source": selected_source,
        "selected_payload_revision": selected_rev,
        "cloud_revision": cloud_rev,
        "disk_revision": disk_rev if disk_rev else None,
        "applied_revision": applied,
        "pending_local_revision": local_rev,
        "revision_consistency_valid": valid,
        "revision_inconsistency_reason": ",".join(reasons) if reasons else "",
        "cloud_state_applied": authoritative_payload_applied(session),
        "pending_user_edits": bool(session.get(PENDING_USER_EDITS_KEY)),
        "pending_edit_fields": session.get("_music_pending_edit_fields"),
        "pending_edit_merged_after_hydration": session.get("_music_pending_edit_merged_after_hydration"),
    }


def collect_restore_mode_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    diag = dict(session.get(ACCOUNT_RESOLUTION_DIAG_KEY) or {})
    diag.update(
        {
            "workspace_restore_in_progress": workspace_restore_in_progress(session),
            "user_edit_tracking_enabled": user_edit_tracking_enabled(session),
        }
    )
    diag.update(collect_revision_consistency_diagnostics(session))
    return diag


__all__ = [
    "ACCOUNT_RESOLUTION_DIAG_KEY",
    "AUTHORITATIVE_PAYLOAD_APPLIED_KEY",
    "PENDING_USER_EDITS_KEY",
    "SELECTED_PAYLOAD_REVISION_KEY",
    "USER_EDIT_TRACKING_ENABLED_KEY",
    "WORKSPACE_RESTORE_IN_PROGRESS_KEY",
    "authoritative_payload_applied",
    "begin_workspace_restore",
    "clear_bootstrap_local_dirty_flags",
    "collect_restore_mode_diagnostics",
    "collect_revision_consistency_diagnostics",
    "complete_workspace_restore_after_apply",
    "merge_pending_user_edits_after_hydration",
    "prepare_music_cold_start_restore",
    "queue_pending_user_edit",
    "record_account_workspace_identity",
    "record_authoritative_payload_applied",
    "should_record_user_local_dirty",
    "user_edit_tracking_enabled",
    "workspace_restore_in_progress",
]

"""Queue + flush explicit sidebar display_key_change during startup suppression."""

from __future__ import annotations

import copy
from typing import Any

from display_key_sidebar_persistence_trace import (
    DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY,
    DISPLAY_KEY_SIDEBAR_TRACE_KEY,
    active_sidebar_display_key_transaction_id,
    is_explicit_sidebar_display_key_save,
    record_display_key_user_change_violation,
)

QUEUED_DISPLAY_KEY_CHANGE_KEY = "_queued_explicit_sidebar_display_key_change"
DISPLAY_KEY_QUEUED_USER_CHANGE_NOT_FLUSHED = "DISPLAY_KEY_QUEUED_USER_CHANGE_NOT_FLUSHED"

_STARTUP_BLOCK_MARKERS: tuple[str, ...] = (
    "startup_suppression_armed",
    "startup_restore_in_progress",
    "startup_canonical_unchanged",
    "startup_suppression_not_released",
)


def _queued(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(QUEUED_DISPLAY_KEY_CHANGE_KEY)
    if isinstance(raw, dict):
        return raw
    return {}


def has_queued_display_key_change(session: dict[str, Any]) -> bool:
    q = _queued(session)
    return bool(q.get("armed")) and bool(str(q.get("new_value") or "").strip())


def is_genuine_queued_display_key_change(session: dict[str, Any]) -> bool:
    q = _queued(session)
    if not q.get("armed"):
        return False
    return str(q.get("source") or "").strip() == "sidebar_on_change"


def _active_song_identity(session: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        from songs.music_source import resolve_active_song_identity

        ident = resolve_active_song_identity(session)
        if isinstance(ident, dict):
            out = dict(ident)
    except ImportError:
        pass
    pick = str(session.get("active_catalog_pick_key") or "").strip()
    if pick:
        out.setdefault("pick_key", pick)
    return out


def queue_explicit_display_key_change(
    session: dict[str, Any],
    *,
    transaction_id: str = "",
    old_value: str = "",
    new_value: str = "",
    source: str = "sidebar_on_change",
    queued_stage: str = "",
    block_reason: str = "",
) -> None:
    if str(source or "").strip() != "sidebar_on_change":
        return
    tx_id = str(transaction_id or active_sidebar_display_key_transaction_id(session) or "").strip()
    active = session.get(DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY)
    if isinstance(active, dict):
        old_value = old_value or str(active.get("cloud_display_key_before") or active.get("canonical_display_key_before") or "")
        new_value = new_value or str(session.get("display_key") or active.get("selected_display_key") or "")
        tx_id = tx_id or str(active.get("transaction_id") or "")
    old_value = str(old_value or "").strip()
    new_value = str(new_value or "").strip()
    if not new_value or (old_value and old_value == new_value):
        return
    rev_loaded = None
    try:
        from music_startup_save_suppression import STARTUP_REVISION_LOADED_KEY

        if session.get(STARTUP_REVISION_LOADED_KEY) is not None:
            rev_loaded = int(session.get(STARTUP_REVISION_LOADED_KEY))
    except (TypeError, ValueError, ImportError):
        pass
    session[QUEUED_DISPLAY_KEY_CHANGE_KEY] = {
        "armed": True,
        "transaction_id": tx_id or None,
        "old_value": old_value or None,
        "new_value": new_value,
        "source": "sidebar_on_change",
        "save_reason": "display_key_change",
        "queued_stage": str(queued_stage or block_reason or "startup_blocked").strip() or None,
        "startup_revision_loaded": rev_loaded,
        "active_song_identity": _active_song_identity(session) or None,
        "block_reason": str(block_reason or "").strip() or None,
    }
    try:
        from active_song_state import mark_active_song_local_edit

        mark_active_song_local_edit(session)
    except ImportError:
        pass
    try:
        from suite_user_persistence import _local_dirty_key

        session[_local_dirty_key("music")] = True
    except ImportError:
        pass
    _sync_queued_diag(session)


def _sync_queued_diag(session: dict[str, Any]) -> None:
    if not session.get("developer_mode"):
        return
    trace = session.get(DISPLAY_KEY_SIDEBAR_TRACE_KEY)
    if not isinstance(trace, dict):
        trace = {}
        session[DISPLAY_KEY_SIDEBAR_TRACE_KEY] = trace
    q = _queued(session)
    if q:
        trace["queued_display_key_change"] = copy.deepcopy(q)


def record_startup_release_diag(
    session: dict[str, Any],
    *,
    release_stage: str,
    restore_finalized: bool,
    fingerprint_semantic_match: bool,
    ignored_volatile_paths: list[str] | None = None,
) -> None:
    if not session.get("developer_mode"):
        return
    trace = session.get(DISPLAY_KEY_SIDEBAR_TRACE_KEY)
    if not isinstance(trace, dict):
        trace = {}
        session[DISPLAY_KEY_SIDEBAR_TRACE_KEY] = trace
    trace["startup_release"] = {
        "release_stage": str(release_stage or "").strip() or None,
        "restore_finalized": bool(restore_finalized),
        "fingerprint_semantic_match": bool(fingerprint_semantic_match),
        "ignored_volatile_paths": list(ignored_volatile_paths or []) or None,
        "startup_suppression_released": session.get("startup_suppression_released"),
    }


def record_queued_flush_diag(session: dict[str, Any], **fields: Any) -> None:
    if not session.get("developer_mode"):
        return
    trace = session.get(DISPLAY_KEY_SIDEBAR_TRACE_KEY)
    if not isinstance(trace, dict):
        trace = {}
        session[DISPLAY_KEY_SIDEBAR_TRACE_KEY] = trace
    prev = trace.get("queued_flush")
    merged = dict(prev) if isinstance(prev, dict) else {}
    merged.update({k: v for k, v in fields.items() if v is not None})
    trace["queued_flush"] = merged


def _startup_block_reason(text: str) -> bool:
    low = str(text or "").lower()
    return any(m in low for m in _STARTUP_BLOCK_MARKERS)


def hydration_complete_for_explicit_user_save(session: dict[str, Any]) -> bool:
    stage = str(session.get("restore_finalized_stage") or "").strip()
    if stage in ("late_end_of_run", "early_finalize"):
        return True
    try:
        from music_workspace_hydration import can_finalize_music_restore, workspace_empty_confirmed

        return bool(can_finalize_music_restore(session) or workspace_empty_confirmed(session))
    except ImportError:
        return False


def attempt_release_stale_startup_suppression_for_display_key(st: Any) -> bool:
    """Scenario B: restore finalized but suppression still armed — release for explicit user key save."""
    ss = st.session_state
    if not is_genuine_queued_display_key_change(ss) and not is_explicit_sidebar_display_key_save(
        "display_key_change", ss
    ):
        return False
    armed = bool(ss.get("startup_suppression_armed")) and not ss.get("startup_suppression_released")
    if not armed:
        return False
    if not hydration_complete_for_explicit_user_save(ss):
        return False
    try:
        from music_startup_save_suppression import (
            STARTUP_RESTORE_IN_PROGRESS_KEY,
            STARTUP_SUPPRESSION_RELEASED_KEY,
            STARTUP_WRITE_ALLOWED_REASON_KEY,
            _apply_queued_display_key_startup_release,
        )

        _apply_queued_display_key_startup_release(ss, stage="explicit_display_key_stale_release")
        ss[STARTUP_SUPPRESSION_RELEASED_KEY] = True
        ss[STARTUP_RESTORE_IN_PROGRESS_KEY] = False
        ss[STARTUP_WRITE_ALLOWED_REASON_KEY] = "explicit_sidebar_display_key_after_restore_finalized"
        record_startup_release_diag(
            ss,
            release_stage="explicit_display_key_stale_release",
            restore_finalized=True,
            fingerprint_semantic_match=False,
        )
        return True
    except ImportError:
        return False


def attempt_release_startup_for_queued_display_key_change(st: Any, *, suppress_reason: str = "") -> bool:
    ss = st.session_state
    if not has_queued_display_key_change(ss) and not is_explicit_sidebar_display_key_save("display_key_change", ss):
        return False
    if hydration_complete_for_explicit_user_save(ss):
        if attempt_release_stale_startup_suppression_for_display_key(st):
            return True
    if not has_queued_display_key_change(ss):
        if _startup_block_reason(suppress_reason):
            queue_explicit_display_key_change(
                ss,
                queued_stage="force_save_blocked",
                block_reason=suppress_reason,
            )
        return bool(has_queued_display_key_change(ss))
    try:
        from music_startup_save_suppression import _apply_queued_display_key_startup_release

        _apply_queued_display_key_startup_release(ss, stage="display_key_change_release")
        record_startup_release_diag(
            ss,
            release_stage="display_key_change_release",
            restore_finalized=hydration_complete_for_explicit_user_save(ss),
            fingerprint_semantic_match=False,
        )
        return True
    except ImportError:
        return False


def clear_queued_display_key_change(session: dict[str, Any], *, clear_reason: str = "") -> None:
    session.pop(QUEUED_DISPLAY_KEY_CHANGE_KEY, None)
    record_queued_flush_diag(session, clear_reason=str(clear_reason or "").strip() or None)
    _sync_queued_diag(session)


def flush_queued_display_key_change_once(st: Any) -> bool:
    ss = st.session_state
    q = _queued(ss)
    if not q.get("armed"):
        return False
    if not is_genuine_queued_display_key_change(ss):
        return False
    tx_id = str(q.get("transaction_id") or "").strip()
    new_val = str(q.get("new_value") or ss.get("display_key") or "").strip()
    if new_val:
        ss["display_key"] = new_val
    try:
        from display_key_sidebar_persistence_trace import arm_explicit_sidebar_display_key_save

        arm_explicit_sidebar_display_key_save(
            ss,
            transaction_id=tx_id,
            selected_display_key=new_val,
            cloud_display_key_before=str(q.get("old_value") or ""),
            canonical_display_key_before=str(q.get("old_value") or ""),
        )
    except ImportError:
        pass
    record_queued_flush_diag(ss, attempted=True, transaction_id=tx_id or None)
    ok = False
    exc_text = ""
    try:
        from display_key_sidebar_save_pipeline import run_explicit_display_key_cloud_save

        ok = bool(run_explicit_display_key_cloud_save(st, transaction_id=tx_id, caller="queued_display_key_flush"))
    except Exception as exc:
        exc_text = str(exc)
        ok = False
    try:
        from display_key_sidebar_cloud_confirmation import enrich_display_key_save_transaction

        tx = enrich_display_key_save_transaction(ss)
        record_queued_flush_diag(
            ss,
            reserved_revision=tx.get("reserved_write_revision"),
            payload_core_display_key=tx.get("payload_core_display_key"),
            upsert_attempted=bool(tx.get("cloud_write_attempted")),
            upsert_succeeded=bool(tx.get("cloud_upsert_succeeded") or tx.get("cloud_write_succeeded")),
            network_confirmed=bool(tx.get("cloud_confirmed")),
        )
        trace = ss.get(DISPLAY_KEY_SIDEBAR_TRACE_KEY)
        forensic = trace.get("confirmation_forensic") if isinstance(trace, dict) else {}
        if isinstance(forensic, dict):
            record_queued_flush_diag(
                ss,
                fetched_display_key=forensic.get("fetched_display_key"),
                network_confirmed=bool(forensic.get("confirmed")),
            )
    except ImportError:
        pass
    if ok:
        clear_queued_display_key_change(ss, clear_reason="confirmed_flush")
        record_queued_flush_diag(ss, clear_reason="confirmed_flush")
    else:
        record_queued_flush_diag(ss, flush_error=exc_text or ss.get("_music_force_save_blocked_reason"))
        if has_queued_display_key_change(ss):
            record_display_key_user_change_violation(
                ss,
                str(exc_text or ss.get("_music_force_save_blocked_reason") or "queued_flush_failed"),
                violation_code=DISPLAY_KEY_QUEUED_USER_CHANGE_NOT_FLUSHED,
            )
    return ok


def maybe_queue_display_key_save_blocked_by_startup(
    session: dict[str, Any],
    *,
    block_reason: str,
    transaction_id: str = "",
) -> bool:
    if not _startup_block_reason(block_reason):
        return False
    if str(session.get("display_key_change_source") or "").strip() != "sidebar_on_change":
        return False
    queue_explicit_display_key_change(
        session,
        transaction_id=transaction_id,
        queued_stage="cloud_save_blocked",
        block_reason=block_reason,
    )
    return True


__all__ = [
    "DISPLAY_KEY_QUEUED_USER_CHANGE_NOT_FLUSHED",
    "QUEUED_DISPLAY_KEY_CHANGE_KEY",
    "attempt_release_stale_startup_suppression_for_display_key",
    "attempt_release_startup_for_queued_display_key_change",
    "clear_queued_display_key_change",
    "flush_queued_display_key_change_once",
    "has_queued_display_key_change",
    "hydration_complete_for_explicit_user_save",
    "is_genuine_queued_display_key_change",
    "maybe_queue_display_key_save_blocked_by_startup",
    "queue_explicit_display_key_change",
    "record_queued_flush_diag",
    "record_startup_release_diag",
]

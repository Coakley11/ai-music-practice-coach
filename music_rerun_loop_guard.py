"""Detect and stop identical Streamlit rerun loops (live availability guard)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

RERUN_LOOP_DIAG_KEY = "_music_rerun_loop_diag"
RERUN_LOOP_BLOCKED_KEY = "_music_rerun_loop_blocked"
RERUN_LOOP_BLOCKED_FINGERPRINT_KEY = "_music_rerun_loop_blocked_fingerprint"
RERUN_LOOP_FINGERPRINT_KEY = "_music_rerun_loop_last_fingerprint"
RERUN_LOOP_REPEAT_COUNT_KEY = "_music_rerun_loop_repeat_count"
RERUN_LOOP_MAX_REPEATS = 3


def _run_seq(session: dict[str, Any]) -> int:
    try:
        return int(session.get("_script_run_seq") or 0)
    except (TypeError, ValueError):
        return 0


def _diag(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(RERUN_LOOP_DIAG_KEY)
    if not isinstance(raw, dict):
        raw = {}
        session[RERUN_LOOP_DIAG_KEY] = raw
    return raw


def build_route_restore_fingerprint(
    session: dict[str, Any],
    *,
    reason: str = "",
    stage: str = "",
) -> str:
    """Transition identity for loop detection — changes when restore/route makes progress."""
    try:
        from mission_pending_upload_analysis import envelope_from_session_or_canonical

        env = envelope_from_session_or_canonical(session) or {}
        take_id = str(env.get("take_id") or "")
        handoff_rev = env.get("handoff_revision")
    except ImportError:
        take_id = ""
        handoff_rev = None
    nav = env.get("navigation") if isinstance(env.get("navigation"), dict) else {}
    parts = {
        "reason": str(reason or ""),
        "stage": str(stage or ""),
        "studio_page": str(session.get("studio_page") or ""),
        "take_id": take_id,
        "handoff_revision": handoff_rev,
        "route_lock": bool(session.get("_pending_upload_route_lock")),
        "ws_rev": session.get("_suite_applied_workspace_revision"),
        "hydrated_take": session.get("_pending_upload_hydrated_take_id"),
        "route_applied_take": session.get("_pending_upload_route_applied_take_id"),
        "suite_sid": str(session.get("_suite_browser_session_id") or "")[:12],
        "workflow_owner": str(
            session.get("music_workflow_owner")
            or session.get("_music_workflow_owner")
            or nav.get("workflow_owner")
            or ""
        ),
        "persist_restore_applied": bool(session.get("_suite_persist_restore_applied")),
        "blob_hydrated": bool(session.get("_music_workspace_blob_hydrated")),
        "navigate_page": str(session.get("_navigate_to_studio_page") or ""),
    }
    blob = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def note_rerun_request(session: dict[str, Any], *, reason: str, fingerprint: str = "") -> dict[str, Any]:
    fp = fingerprint or build_route_restore_fingerprint(session, reason=reason)
    prev = str(session.get(RERUN_LOOP_FINGERPRINT_KEY) or "")
    count = int(session.get(RERUN_LOOP_REPEAT_COUNT_KEY) or 0)
    if fp == prev:
        count += 1
    else:
        count = 1
        session.pop(RERUN_LOOP_BLOCKED_FINGERPRINT_KEY, None)
        session.pop(RERUN_LOOP_BLOCKED_KEY, None)
    session[RERUN_LOOP_FINGERPRINT_KEY] = fp
    session[RERUN_LOOP_REPEAT_COUNT_KEY] = count
    entry = {
        "run_seq": _run_seq(session),
        "reason": reason,
        "fingerprint": fp,
        "repeat_count": count,
    }
    hist = _diag(session).setdefault("requests", [])
    if isinstance(hist, list):
        hist.append(entry)
        _diag(session)["requests"] = hist[-30:]
    _diag(session)["last"] = entry
    return entry


def should_block_rerun(session: dict[str, Any], *, reason: str, fingerprint: str = "") -> bool:
    fp = fingerprint or build_route_restore_fingerprint(session, reason=reason)
    blocked_fp = str(session.get(RERUN_LOOP_BLOCKED_FINGERPRINT_KEY) or "")
    if blocked_fp and blocked_fp == fp:
        return True
    entry = note_rerun_request(session, reason=reason, fingerprint=fp)
    if int(entry.get("repeat_count") or 0) >= RERUN_LOOP_MAX_REPEATS:
        session[RERUN_LOOP_BLOCKED_KEY] = True
        session[RERUN_LOOP_BLOCKED_FINGERPRINT_KEY] = fp
        _diag(session)["blocked_reason"] = reason
        _diag(session)["blocked_fingerprint"] = fp
        _diag(session)["blocked_at_run_seq"] = _run_seq(session)
        return True
    return False


def clear_rerun_loop_block(session: dict[str, Any], *, reason: str = "") -> None:
    session.pop(RERUN_LOOP_BLOCKED_KEY, None)
    session.pop(RERUN_LOOP_BLOCKED_FINGERPRINT_KEY, None)
    session.pop(RERUN_LOOP_FINGERPRINT_KEY, None)
    session.pop(RERUN_LOOP_REPEAT_COUNT_KEY, None)
    if reason:
        _diag(session)["cleared_reason"] = reason


def safe_rerun(st_module: Any, session: dict[str, Any], *, reason: str, fingerprint: str = "") -> bool:
    """Request rerun unless an identical loop was detected. Returns True if rerun was invoked."""
    if should_block_rerun(session, reason=reason, fingerprint=fingerprint):
        return False
    st_module.rerun()
    return True


def render_rerun_loop_blocked_notice(st_module: Any, session: dict[str, Any]) -> None:
    """User-visible fail-safe when an identical rerun loop was blocked."""
    if not session.get(RERUN_LOOP_BLOCKED_KEY):
        return
    reason = str((_diag(session).get("blocked_reason") or "route_restore")).strip()
    st_module.warning(
        "Session restore paused after repeating the same navigation step. "
        "Your saved data is unchanged. Refresh the page or continue — "
        f"if this persists, open Support with dev diagnostics. (reason: {reason})"
    )


def render_rerun_loop_dev_notice(st_module: Any, session: dict[str, Any]) -> None:
    try:
        dev = bool(st_module.query_params.get("dev"))
    except Exception:
        dev = bool(session.get("developer_mode"))
    if not dev:
        return
    if not session.get(RERUN_LOOP_BLOCKED_KEY) and not _diag(session).get("last"):
        return
    st_module.sidebar.warning(
        "Rerun loop guard: "
        f"blocked={bool(session.get(RERUN_LOOP_BLOCKED_KEY))} · "
        f"blocked_fp={session.get(RERUN_LOOP_BLOCKED_FINGERPRINT_KEY, '—')} · "
        f"repeats={session.get(RERUN_LOOP_REPEAT_COUNT_KEY)} · "
        f"last={(_diag(session).get('last') or {})}"
    )


__all__ = [
    "RERUN_LOOP_BLOCKED_FINGERPRINT_KEY",
    "RERUN_LOOP_BLOCKED_KEY",
    "RERUN_LOOP_DIAG_KEY",
    "RERUN_LOOP_MAX_REPEATS",
    "build_route_restore_fingerprint",
    "clear_rerun_loop_block",
    "note_rerun_request",
    "render_rerun_loop_blocked_notice",
    "render_rerun_loop_dev_notice",
    "safe_rerun",
    "should_block_rerun",
]

"""Run-scoped block on legacy/CWS projection overwriting authoritatively restored workflow fields."""

from __future__ import annotations

import time
import uuid
from typing import Any

WORKFLOW_RESTORE_GUARD_KEY = "_music_workflow_authoritative_restore_guard"
MUSIC_SCRIPT_RUN_ID_KEY = "_music_script_run_id"

PROTECTED_WORKFLOW_SESSION_KEYS: frozenset[str] = frozenset(
    {
        "_music_active_workflow",
        "_music_workflow_state_store",
        "display_key",
        "concert_key",
        "_pending_display_key",
        "improv_song_concert_sections",
        "improv_generated_sections",
        "improv_jam_session",
        "improv_style_key",
        "improv_jam_key",
        "ii_selected_chord",
        "II_SELECTED_CHORD",
        "ii_selected_section",
        "ii_selected_chord_index",
        "improv_active_mission",
        "improv_mission_recording_seal",
    }
)


def _current_script_run_id(session: dict[str, Any], *, st: Any | None = None) -> str:
    existing = str(session.get(MUSIC_SCRIPT_RUN_ID_KEY) or "").strip()
    if existing:
        return existing
    run_id = ""
    if st is not None:
        try:
            from music_workspace_save_transaction_debug import _streamlit_script_run_id

            run_id = str(_streamlit_script_run_id(st) or "").strip()
        except ImportError:
            pass
    if not run_id:
        run_id = str(uuid.uuid4())
    session[MUSIC_SCRIPT_RUN_ID_KEY] = run_id
    return run_id


def ensure_script_run_scope(session: dict[str, Any], *, st: Any | None = None) -> str:
    """Bind restore guards to the active Streamlit script run."""
    return _current_script_run_id(session, st=st)


def expire_stale_workflow_restore_guards(session: dict[str, Any], *, st: Any | None = None) -> bool:
    """Drop restore guards from a prior script run so they cannot suppress later legitimate changes."""
    g = session.get(WORKFLOW_RESTORE_GUARD_KEY)
    if not isinstance(g, dict) or not g.get("authoritative_restore_guard_active"):
        return False
    guard_run = str(g.get("guard_run_id") or "").strip()
    current = _current_script_run_id(session, st=st)
    if guard_run and guard_run != current:
        session.pop(WORKFLOW_RESTORE_GUARD_KEY, None)
        return True
    return False


def activate_workflow_restore_guard(
    session: dict[str, Any],
    *,
    source: str = "canonical_restore",
    run_id: str = "",
    request_seq: int | None = None,
    st: Any | None = None,
) -> None:
    rid = str(run_id or "").strip() or _current_script_run_id(session, st=st)
    session[WORKFLOW_RESTORE_GUARD_KEY] = {
        "authoritative_restore_guard_active": True,
        "canonical_restore_source": str(source or ""),
        "guard_run_id": rid,
        "guard_request_seq": request_seq,
        "activated_at": time.time(),
        "fields_protected": sorted(PROTECTED_WORKFLOW_SESSION_KEYS),
        "legacy_overwrite_attempts_blocked": [],
        "expires_after_run": True,
    }


def deactivate_workflow_restore_guard(session: dict[str, Any], *, reason: str = "") -> None:
    g = session.get(WORKFLOW_RESTORE_GUARD_KEY)
    if isinstance(g, dict):
        g["deactivated_reason"] = str(reason or "manual")
        g["authoritative_restore_guard_active"] = False
    session.pop(WORKFLOW_RESTORE_GUARD_KEY, None)


def complete_workflow_restore_guard(session: dict[str, Any], *, reason: str = "restore_complete") -> None:
    """End run-scoped protection after canonical restore + projection succeeded."""
    deactivate_workflow_restore_guard(session, reason=reason)


def restore_guard_active(session: dict[str, Any], *, st: Any | None = None) -> bool:
    expire_stale_workflow_restore_guards(session, st=st)
    g = session.get(WORKFLOW_RESTORE_GUARD_KEY)
    return isinstance(g, dict) and bool(g.get("authoritative_restore_guard_active"))


def block_legacy_overwrite(session: dict[str, Any], key: str, *, caller: str, st: Any | None = None) -> bool:
    if not restore_guard_active(session, st=st):
        return False
    if key not in PROTECTED_WORKFLOW_SESSION_KEYS:
        return False
    g = session.get(WORKFLOW_RESTORE_GUARD_KEY)
    if isinstance(g, dict):
        bucket = g.setdefault("legacy_overwrite_attempts_blocked", [])
        if isinstance(bucket, list):
            bucket.append({"key": key, "caller": caller})
    return True


__all__ = [
    "MUSIC_SCRIPT_RUN_ID_KEY",
    "PROTECTED_WORKFLOW_SESSION_KEYS",
    "WORKFLOW_RESTORE_GUARD_KEY",
    "activate_workflow_restore_guard",
    "block_legacy_overwrite",
    "complete_workflow_restore_guard",
    "deactivate_workflow_restore_guard",
    "ensure_script_run_scope",
    "expire_stale_workflow_restore_guards",
    "restore_guard_active",
]

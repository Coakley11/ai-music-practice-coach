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


def authoritative_legacy_value_for_key(session: dict[str, Any], key: str) -> Any | None:
    """Practice-key and mission fields derived from the active workflow blob (forward authority)."""
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob
    except ImportError:
        return None
    ptr = get_active_workflow_pointer(session)
    if ptr is None or not ptr.workflow_owner:
        return None
    blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
    if blob is None:
        return None
    tonic = str(blob.keys.practice_tonic or "C").strip() or "C"
    mode = str(blob.keys.practice_mode or "major").strip().lower()
    key_token = f"{tonic}m" if mode == "minor" and not tonic.endswith("m") else tonic
    if key in {"display_key", "concert_key", "_pending_display_key"}:
        return key_token
    if key == "improv_style_key" and blob.workflow_owner == "style_jam":
        return key_token
    if key == "improv_jam_key" and blob.workflow_owner == "jam_session_generator":
        return key_token
    if key == "ii_selected_chord" and blob.selected_chord_symbol:
        return blob.selected_chord_symbol
    if key == "ii_selected_section" and blob.selected_section:
        return blob.selected_section
    if key == "ii_selected_chord_index":
        return int(blob.selected_chord_index or 0)
    if key in {"improv_active_mission", "improv_mission_pick"} and blob.mission_type:
        return blob.mission_type
    return None


def block_legacy_overwrite(
    session: dict[str, Any],
    key: str,
    *,
    caller: str,
    value: Any = None,
    authoritative_projection: bool = False,
    st: Any | None = None,
) -> bool:
    """Return True when a stale legacy write must be blocked (not authoritative blob→legacy projection).

    Authoritative projection (blob → compatibility/renderer fields) is always allowed.
    Stale session→legacy writes that disagree with the active blob are blocked.
    Pointer/store keys are never writable from legacy paths while the guard is active.
    """
    if not restore_guard_active(session, st=st):
        return False
    if key in {"_music_active_workflow", "_music_workflow_state_store"}:
        if authoritative_projection:
            return False
        _log_blocked(session, key, caller)
        return True
    if authoritative_projection:
        return False
    if key not in PROTECTED_WORKFLOW_SESSION_KEYS:
        return False
    auth = authoritative_legacy_value_for_key(session, key)
    if auth is not None and value is not None:
        if str(value).strip() == str(auth).strip():
            return False
        _log_blocked(session, key, caller, detail=f"stale:{value}!={auth}")
        return True
    _log_blocked(session, key, caller)
    return True


def _log_blocked(session: dict[str, Any], key: str, caller: str, *, detail: str = "") -> None:
    g = session.get(WORKFLOW_RESTORE_GUARD_KEY)
    if isinstance(g, dict):
        bucket = g.setdefault("legacy_overwrite_attempts_blocked", [])
        if isinstance(bucket, list):
            entry: dict[str, Any] = {"key": key, "caller": caller}
            if detail:
                entry["detail"] = detail
            bucket.append(entry)


__all__ = [
    "MUSIC_SCRIPT_RUN_ID_KEY",
    "PROTECTED_WORKFLOW_SESSION_KEYS",
    "WORKFLOW_RESTORE_GUARD_KEY",
    "activate_workflow_restore_guard",
    "authoritative_legacy_value_for_key",
    "block_legacy_overwrite",
    "complete_workflow_restore_guard",
    "deactivate_workflow_restore_guard",
    "ensure_script_run_scope",
    "expire_stale_workflow_restore_guards",
    "restore_guard_active",
]

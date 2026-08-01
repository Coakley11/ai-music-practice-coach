"""Single restore-phase gate for Music — restore once, user wins afterward.

Multiple persistence layers (cloud full-session, page snapshots, canonical
prepare_*, widget priming, defaults) previously ran on every script rerun and
fought each other. This module marks when authoritative restore is complete so
later layers do not re-apply stale blobs over live user edits.
"""

from __future__ import annotations

from typing import Any

MUSIC_RESTORE_PHASE_COMPLETE_KEY = "_music_restore_phase_complete"
MUSIC_STARTUP_RESTORE_FINALIZED_KEY = "_music_startup_restore_finalized"
MUSIC_ACTIVE_PICK_KEY_RECONCILED_KEY = "_music_active_pick_key_reconciled"
MUSIC_PAGE_SNAPSHOT_HYDRATED_PREFIX = "_music_page_snapshot_hydrated::"
MUSIC_SCRIPT_SESSION_KEY = "_music_script_browser_session_id"
STREAMLIT_WIDGETS_LOCKED_KEY = "_streamlit_widgets_locked_this_run"


def begin_music_script_run(session_state: dict[str, Any]) -> None:
    """Start-of-script hook — reset page tracker only on true new browser session."""
    session_state.pop(STREAMLIT_WIDGETS_LOCKED_KEY, None)
    try:
        from multitrack_session_persistence import reset_mt_workspace_run_diag

        reset_mt_workspace_run_diag(session_state)
    except ImportError:
        pass
    run_seq = int(session_state.get("_script_run_seq") or 0)
    last_seq = session_state.get(MUSIC_SCRIPT_SESSION_KEY)
    if last_seq is None:
        session_state[MUSIC_SCRIPT_SESSION_KEY] = run_seq
        session_state.pop("_studio_active_page_id", None)
        session_state.pop(MUSIC_RESTORE_PHASE_COMPLETE_KEY, None)
        session_state.pop("_improv_tab_user_touched", None)
        session_state.pop("_creative_mode_user_touched", None)
        for key in list(session_state.keys()):
            if str(key).startswith(MUSIC_PAGE_SNAPSHOT_HYDRATED_PREFIX):
                session_state.pop(key, None)
        return
    session_state[MUSIC_SCRIPT_SESSION_KEY] = run_seq


def mark_music_workspace_restore_applied(session_state: dict[str, Any]) -> None:
    """Call when sync_workspace_protocol applies cloud/disk blob this run."""
    session_state.pop(MUSIC_RESTORE_PHASE_COMPLETE_KEY, None)
    for key in list(session_state.keys()):
        if str(key).startswith(MUSIC_PAGE_SNAPSHOT_HYDRATED_PREFIX):
            session_state.pop(key, None)


def complete_music_restore_phase(session_state: dict[str, Any]) -> None:
    """Call once after all startup restore/reconcile paths finish."""
    session_state[MUSIC_RESTORE_PHASE_COMPLETE_KEY] = True


def music_restore_phase_complete(session_state: dict[str, Any]) -> bool:
    return bool(session_state.get(MUSIC_RESTORE_PHASE_COMPLETE_KEY))


def authoritative_restore_in_progress(session_state: dict[str, Any]) -> bool:
    """True only while startup restore is still stamping widgets — not forever after."""
    if music_restore_phase_complete(session_state):
        return False
    return bool(
        session_state.get("_cloud_workspace_restored_this_run")
        or session_state.get("_suite_persist_restore_applied")
    )


def page_snapshot_hydrated(session_state: dict[str, Any], page_id: str) -> bool:
    return bool(session_state.get(f"{MUSIC_PAGE_SNAPSHOT_HYDRATED_PREFIX}{page_id}"))


def mark_page_snapshot_hydrated(session_state: dict[str, Any], page_id: str) -> None:
    session_state[f"{MUSIC_PAGE_SNAPSHOT_HYDRATED_PREFIX}{page_id}"] = True


def should_hydrate_page_snapshot(
    session_state: dict[str, Any],
    *,
    page_id: str,
    page_changed: bool,
) -> bool:
    """True when page-local snapshot may be applied (once per page, or on nav)."""
    if page_changed:
        return True
    if not music_restore_phase_complete(session_state):
        return True
    return not page_snapshot_hydrated(session_state, page_id)


def workspace_is_truly_empty(session_state: dict[str, Any]) -> bool:
    """True when cold-start default song seeding is allowed (never after failed restore)."""
    if session_state.get("_suite_persist_restore_applied"):
        return False
    if session_state.get("_music_workspace_blob_hydrated"):
        return False
    if session_state.get("_cloud_workspace_restored_this_run"):
        return False
    if session_state.get("_music_restore_error"):
        return False
    if session_state.get("_suite_workspace_sync_attempted") and not session_state.get(
        "_suite_persist_restore_applied"
    ):
        # Cloud/disk fetch ran but nothing durable restored — do not force Stay.
        return False
    payload = session_state.get("_suite_last_cloud_fetch_payload")
    if isinstance(payload, dict) and payload:
        return False
    try:
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

        sel = session_state.get(SELECTED_SONG_STATE_KEY)
        if isinstance(sel, dict) and str(sel.get("pick_key") or "").strip():
            if not session_state.get("_music_default_song_ephemeral"):
                return False
        live_pk = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
        if live_pk and not session_state.get("_music_default_song_ephemeral"):
            return False
    except ImportError:
        pass
    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY

        blob = session_state.get(ACTIVE_SONG_STATE_KEY)
        if isinstance(blob, dict) and str(blob.get("pick_key") or "").strip():
            if not session_state.get("_music_default_song_ephemeral"):
                return False
    except ImportError:
        pass
    if session_state.get("cpl_saved_progressions") or session_state.get("cpl_active_progression"):
        return False
    if session_state.get("music_workspace_state"):
        return False
    page = str(session_state.get("studio_page") or "").strip()
    if page and page != "practice":
        return False
    return True

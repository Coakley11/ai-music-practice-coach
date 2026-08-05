"""Workspace hydration state — distinct from restore-phase completion."""

from __future__ import annotations

from typing import Any

WORKSPACE_HYDRATION_STARTED_KEY = "_music_workspace_hydration_started"
WORKSPACE_HYDRATION_ATTEMPTED_KEY = "_music_workspace_hydration_attempted"
WORKSPACE_BLOB_HYDRATED_KEY = "_music_workspace_blob_hydrated"
WORKSPACE_EMPTY_CONFIRMED_KEY = "_music_workspace_empty_confirmed"
WORKSPACE_HYDRATION_FAILED_KEY = "_music_workspace_hydration_failed"
WORKSPACE_HYDRATION_FAILURE_REASON_KEY = "_music_workspace_hydration_failure_reason"


def workspace_blob_hydrated(session_state: dict[str, Any]) -> bool:
    return bool(session_state.get(WORKSPACE_BLOB_HYDRATED_KEY))


def workspace_empty_confirmed(session_state: dict[str, Any]) -> bool:
    return bool(session_state.get(WORKSPACE_EMPTY_CONFIRMED_KEY))


def can_finalize_music_restore(session_state: dict[str, Any]) -> bool:
    """True only after Case A (hydrated) or Case B (authoritatively empty workspace)."""
    return workspace_blob_hydrated(session_state) or workspace_empty_confirmed(session_state)


def mark_workspace_hydration_started(session_state: dict[str, Any]) -> None:
    session_state[WORKSPACE_HYDRATION_STARTED_KEY] = True


def mark_workspace_hydration_attempted(session_state: dict[str, Any]) -> None:
    session_state[WORKSPACE_HYDRATION_ATTEMPTED_KEY] = True


def mark_workspace_blob_hydrated(session_state: dict[str, Any]) -> None:
    session_state[WORKSPACE_BLOB_HYDRATED_KEY] = True
    session_state.pop(WORKSPACE_HYDRATION_FAILED_KEY, None)
    session_state.pop(WORKSPACE_HYDRATION_FAILURE_REASON_KEY, None)
    session_state.pop(WORKSPACE_EMPTY_CONFIRMED_KEY, None)


def mark_workspace_empty_confirmed(session_state: dict[str, Any], reason: str = "") -> None:
    session_state[WORKSPACE_EMPTY_CONFIRMED_KEY] = True
    session_state.pop(WORKSPACE_HYDRATION_FAILED_KEY, None)
    session_state.pop(WORKSPACE_HYDRATION_FAILURE_REASON_KEY, None)
    if reason:
        session_state["_music_workspace_empty_confirmed_reason"] = reason


def mark_workspace_hydration_failed(session_state: dict[str, Any], reason: str) -> None:
    session_state[WORKSPACE_HYDRATION_FAILED_KEY] = True
    session_state[WORKSPACE_HYDRATION_FAILURE_REASON_KEY] = str(reason or "unknown").strip() or "unknown"
    session_state.pop(WORKSPACE_EMPTY_CONFIRMED_KEY, None)


def clear_stale_restore_completion_flags(session_state: dict[str, Any]) -> None:
    """Drop finalized/complete flags when hydration outcome is still unknown."""
    if can_finalize_music_restore(session_state):
        return
    try:
        from music_restore_phase import (
            MUSIC_RESTORE_PHASE_COMPLETE_KEY,
            MUSIC_STARTUP_RESTORE_FINALIZED_KEY,
        )
    except ImportError:
        MUSIC_RESTORE_PHASE_COMPLETE_KEY = "_music_restore_phase_complete"
        MUSIC_STARTUP_RESTORE_FINALIZED_KEY = "_music_startup_restore_finalized"
    session_state.pop(MUSIC_STARTUP_RESTORE_FINALIZED_KEY, None)
    session_state.pop(MUSIC_RESTORE_PHASE_COMPLETE_KEY, None)


def record_sync_outcome_after_attempt(session_state: dict[str, Any], *, sync_applied: bool) -> None:
    """Classify workspace sync result when apply did not hydrate the blob."""
    if workspace_blob_hydrated(session_state):
        return
    if sync_applied:
        mark_workspace_hydration_failed(session_state, "sync_applied_without_hydrate_flag")
        return
    skip = str(session_state.get("_suite_persist_restore_skip_reason") or "").strip()
    if skip == "no workspace blob":
        mark_workspace_empty_confirmed(session_state, skip)
        return
    if skip.startswith("workspace already synced"):
        mark_workspace_hydration_failed(session_state, skip)
        return
    if skip in (
        "cloud module missing",
        "resume query params — workspace sync skipped",
    ):
        mark_workspace_hydration_failed(session_state, skip)
        return
    if session_state.get("_suite_persist_restore_applied"):
        mark_workspace_blob_hydrated(session_state)
        return
    payload = session_state.get("_suite_last_cloud_fetch_payload")
    if isinstance(payload, dict) and payload:
        mark_workspace_hydration_failed(
            session_state,
            skip or "payload_present_but_sync_not_applied",
        )
        return
    if session_state.get("_suite_workspace_sync_attempted"):
        if skip:
            mark_workspace_hydration_failed(session_state, skip)
        else:
            mark_workspace_hydration_failed(
                session_state,
                str(
                    session_state.get("_suite_persist_restore_skip_reason")
                    or "sync_incomplete_no_authoritative_empty"
                ),
            )


def workspace_hydration_failed(session_state: dict[str, Any]) -> bool:
    return bool(session_state.get(WORKSPACE_HYDRATION_FAILED_KEY))


HYDRATION_UI_WAIT_ATTEMPTS_KEY = "_music_hydration_ui_wait_attempts"
HYDRATION_UI_WAIT_MAX = 3


def render_workspace_hydration_wait_or_stop(
    st_module: Any,
    *,
    song_picker_catalog: dict,
    song_library: dict | None,
) -> bool:
    """
    While hydration outcome is unknown, show a restoring state (bounded reruns).
    Returns True if caller should stop the script (no chart / choose-song / key warnings).
    """
    if can_finalize_music_restore(st_module.session_state):
        st_module.session_state.pop(HYDRATION_UI_WAIT_ATTEMPTS_KEY, None)
        return False
    ss = st_module.session_state
    if ss.get("_suite_persist_restore_applied") or ss.get("_music_workspace_blob_hydrated"):
        try:
            from music_workspace_hydration import mark_workspace_blob_hydrated

            mark_workspace_blob_hydrated(ss)
        except ImportError:
            ss["_music_workspace_blob_hydrated"] = True
        ss.pop(HYDRATION_UI_WAIT_ATTEMPTS_KEY, None)
        return False
    if workspace_hydration_failed(ss):
        reason = str(ss.get(WORKSPACE_HYDRATION_FAILURE_REASON_KEY) or "unknown").strip()
        st_module.warning(
            "Your saved workspace could not be restored yet. "
            f"({reason}) Refresh the page or try again in a moment."
        )
        return True
    attempts = int(ss.get(HYDRATION_UI_WAIT_ATTEMPTS_KEY) or 0)
    if attempts < HYDRATION_UI_WAIT_MAX:
        ss[HYDRATION_UI_WAIT_ATTEMPTS_KEY] = attempts + 1
        if attempts == 0:
            try:
                from music_persistent_state import prepare_music_workspace

                prepare_music_workspace(
                    st_module,
                    song_picker_catalog=song_picker_catalog,
                    song_library=song_library,
                )
            except Exception:
                pass
        st_module.info("Restoring your saved workspace…")
        try:
            from music_rerun_loop_guard import build_route_restore_fingerprint, safe_rerun

            if not safe_rerun(
                st_module,
                ss,
                reason="workspace_hydration_wait",
                fingerprint=build_route_restore_fingerprint(ss, reason="hydration_wait"),
            ):
                ss.pop(HYDRATION_UI_WAIT_ATTEMPTS_KEY, None)
                st_module.warning(
                    "Workspace restore stopped repeating the same step. "
                    "The app stays interactive — refresh once if something looks missing."
                )
                return False
        except ImportError:
            st_module.rerun()
    st_module.warning(
        "Workspace restore is taking longer than expected. The app will stay interactive; "
        "refresh once if charts or song data look incomplete."
    )
    try:
        from music_rerun_loop_guard import clear_rerun_loop_block

        clear_rerun_loop_block(ss, reason="hydration_wait_exhausted")
    except ImportError:
        pass
    ss.pop(HYDRATION_UI_WAIT_ATTEMPTS_KEY, None)
    return False


def collect_workspace_hydration_diagnostics(session_state: dict[str, Any]) -> dict[str, Any]:
    return {
        "workspace_hydration_started": bool(session_state.get(WORKSPACE_HYDRATION_STARTED_KEY)),
        "workspace_hydration_attempted": bool(session_state.get(WORKSPACE_HYDRATION_ATTEMPTED_KEY)),
        "workspace_blob_hydrated": workspace_blob_hydrated(session_state),
        "workspace_empty_confirmed": workspace_empty_confirmed(session_state),
        "workspace_hydration_failed": bool(session_state.get(WORKSPACE_HYDRATION_FAILED_KEY)),
        "workspace_hydration_failure_reason": session_state.get(WORKSPACE_HYDRATION_FAILURE_REASON_KEY),
        "can_finalize_music_restore": can_finalize_music_restore(session_state),
        "workspace_sync_attempted": bool(session_state.get("_suite_workspace_sync_attempted")),
        "suite_persist_restore_applied": bool(session_state.get("_suite_persist_restore_applied")),
        "suite_restore_skip_reason": session_state.get("_suite_persist_restore_skip_reason"),
    }

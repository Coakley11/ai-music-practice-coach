"""Suppress false-positive workspace saves during cloud hydration and restore."""

from __future__ import annotations

from typing import Any

STARTUP_RESTORE_IN_PROGRESS_KEY = "startup_restore_in_progress"
STARTUP_SAVE_SUPPRESSED_KEY = "startup_save_suppressed"
STARTUP_SAVE_SUPPRESSION_REASON_KEY = "startup_save_suppression_reason"
HYDRATED_CANONICAL_FP_KEY = "hydrated_canonical_fingerprint"
POST_RESTORE_CANONICAL_FP_KEY = "post_restore_canonical_fingerprint"
STARTUP_FINGERPRINT_MATCHES_KEY = "startup_fingerprint_matches"
STARTUP_REVISION_LOADED_KEY = "startup_revision_loaded"
STARTUP_REVISION_FINAL_KEY = "startup_revision_final"

_RESTORE_BLOCKED_SAVE_REASONS: frozenset[str] = frozenset(
    {
        "song_edit",
        "display_key_change",
        "capo_widget",
        "autosave",
        "force_autosave",
    }
)

_EXPLICIT_STARTUP_SAVE_REASONS: frozenset[str] = frozenset(
    {
        "startup_migration",
        "canonical_repair",
    }
)


def _canonical_fp(state: dict[str, Any] | None) -> str:
    from music_workspace_canonical_fingerprint import workspace_canonical_content_fingerprint

    return workspace_canonical_content_fingerprint(state if isinstance(state, dict) else {})


def record_hydrated_canonical_fingerprint(session: dict[str, Any], payload: dict[str, Any] | None) -> str:
    """Capture cloud payload fingerprint at hydration (read-only)."""
    session[STARTUP_RESTORE_IN_PROGRESS_KEY] = True
    fp = _canonical_fp(payload if isinstance(payload, dict) else {})
    session[HYDRATED_CANONICAL_FP_KEY] = fp or "(none)"
    try:
        from workspace_revision import workspace_revision_from_blob

        session[STARTUP_REVISION_LOADED_KEY] = workspace_revision_from_blob(payload if isinstance(payload, dict) else {})
    except ImportError:
        session[STARTUP_REVISION_LOADED_KEY] = 0
    return fp


def _record_alignment_diagnostics(
    session: dict[str, Any],
    *,
    hydrated_fp: str,
    post_fp: str,
    matches: bool,
    revision_final: int,
) -> None:
    session[HYDRATED_CANONICAL_FP_KEY] = hydrated_fp or session.get(HYDRATED_CANONICAL_FP_KEY) or "(none)"
    session[POST_RESTORE_CANONICAL_FP_KEY] = post_fp or "(none)"
    session[STARTUP_FINGERPRINT_MATCHES_KEY] = bool(matches)
    session[STARTUP_REVISION_FINAL_KEY] = int(revision_final or 0)


def finalize_startup_canonical_alignment(st: Any) -> bool:
    """After restore normalization, align confirmed fingerprint/revision or record mismatch."""
    ss = st.session_state
    payload = ss.get("_suite_last_cloud_fetch_payload")
    hydrated_fp = str(ss.get(HYDRATED_CANONICAL_FP_KEY) or "").strip()
    if not hydrated_fp or hydrated_fp == "(none)":
        hydrated_fp = _canonical_fp(payload if isinstance(payload, dict) else {})
        ss[HYDRATED_CANONICAL_FP_KEY] = hydrated_fp or "(none)"

    post_state: dict[str, Any] | None = None
    try:
        from music_persistent_state import build_music_disk_state

        post_state = build_music_disk_state(st)
    except Exception:
        post_state = None

    post_fp = _canonical_fp(post_state)
    matches = bool(hydrated_fp and post_fp and hydrated_fp == post_fp)

    rev_final = 0
    try:
        from workspace_revision import (
            CLOUD_REVISION_KEY,
            LAST_CONFIRMED_REVISION_KEY,
            workspace_revision_from_blob,
        )

        if isinstance(payload, dict):
            rev_loaded = workspace_revision_from_blob(payload)
        else:
            rev_loaded = int(ss.get(STARTUP_REVISION_LOADED_KEY) or 0)
        rev_final = workspace_revision_from_blob(post_state if isinstance(post_state, dict) else payload)
        ss[STARTUP_REVISION_LOADED_KEY] = rev_loaded
        _record_alignment_diagnostics(
            ss,
            hydrated_fp=hydrated_fp,
            post_fp=post_fp,
            matches=matches,
            revision_final=rev_final,
        )
        if matches:
            try:
                from music_egress_strict_save import note_confirmed_cloud_fingerprint

                note_confirmed_cloud_fingerprint(ss, post_fp)
            except ImportError:
                ss["_music_last_confirmed_cloud_fp"] = post_fp
            ss[LAST_CONFIRMED_REVISION_KEY] = rev_loaded
            ss[CLOUD_REVISION_KEY] = rev_loaded
            try:
                from active_song_state import (
                    ACTIVE_SONG_DIRTY_KEY,
                    ACTIVE_SONG_LOCAL_EDIT_TS_KEY,
                    ACTIVE_SONG_PENDING_SYNC_KEY,
                    clear_active_song_local_edit,
                )

                clear_active_song_local_edit(ss)
                ss.pop(ACTIVE_SONG_PENDING_SYNC_KEY, None)
                ss.pop(ACTIVE_SONG_DIRTY_KEY, None)
                ss.pop(ACTIVE_SONG_LOCAL_EDIT_TS_KEY, None)
            except ImportError:
                pass
            try:
                from suite_user_persistence import _local_dirty_key

                ss[_local_dirty_key("music")] = False
            except ImportError:
                pass
            ss.pop("_music_pending_canonical_content_fp", None)
            ss.pop("_music_reserved_write_revision", None)
    except ImportError:
        _record_alignment_diagnostics(
            ss,
            hydrated_fp=hydrated_fp,
            post_fp=post_fp,
            matches=matches,
            revision_final=rev_final,
        )

    ss[STARTUP_RESTORE_IN_PROGRESS_KEY] = False
    return matches


def record_startup_save_suppressed(session: dict[str, Any], reason: str) -> None:
    session[STARTUP_SAVE_SUPPRESSED_KEY] = True
    session[STARTUP_SAVE_SUPPRESSION_REASON_KEY] = reason


def should_suppress_music_workspace_save(session: dict[str, Any], save_reason: str) -> tuple[bool, str]:
    """Return (suppress, diagnostic_reason). Does not mutate save/confirm logic."""
    reason = str(save_reason or "").strip() or "autosave"
    if reason in _EXPLICIT_STARTUP_SAVE_REASONS:
        return False, ""

    if session.get(STARTUP_RESTORE_IN_PROGRESS_KEY):
        if reason in _RESTORE_BLOCKED_SAVE_REASONS or reason == "song_edit":
            return True, "startup_restore_in_progress"

    if session.get(STARTUP_FINGERPRINT_MATCHES_KEY) and reason in _RESTORE_BLOCKED_SAVE_REASONS:
        return True, "startup_canonical_unchanged"

    return False, ""


def gate_music_workspace_save_at_startup(session: dict[str, Any], save_reason: str) -> tuple[bool, str]:
    """If True, caller must not run force_music_workspace_save (no transaction)."""
    suppress, why = should_suppress_music_workspace_save(session, save_reason)
    if suppress:
        record_startup_save_suppressed(session, why)
    return suppress, why


def collect_startup_save_suppression_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "startup_restore_in_progress": session.get(STARTUP_RESTORE_IN_PROGRESS_KEY),
        "startup_save_suppressed": session.get(STARTUP_SAVE_SUPPRESSED_KEY),
        "startup_save_suppression_reason": session.get(STARTUP_SAVE_SUPPRESSION_REASON_KEY),
        "hydrated_canonical_fingerprint": session.get(HYDRATED_CANONICAL_FP_KEY),
        "post_restore_canonical_fingerprint": session.get(POST_RESTORE_CANONICAL_FP_KEY),
        "startup_fingerprint_matches": session.get(STARTUP_FINGERPRINT_MATCHES_KEY),
        "startup_revision_loaded": session.get(STARTUP_REVISION_LOADED_KEY),
        "startup_revision_final": session.get(STARTUP_REVISION_FINAL_KEY),
    }


__all__ = [
    "STARTUP_RESTORE_IN_PROGRESS_KEY",
    "finalize_startup_canonical_alignment",
    "gate_music_workspace_save_at_startup",
    "collect_startup_save_suppression_diagnostics",
    "record_hydrated_canonical_fingerprint",
    "record_startup_save_suppressed",
    "should_suppress_music_workspace_save",
]

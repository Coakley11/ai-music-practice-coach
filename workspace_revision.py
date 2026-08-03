"""Monotonic workspace revision for cross-device sync."""

from __future__ import annotations

import copy
from typing import Any

LOCAL_REVISION_KEY = "_suite_workspace_revision"
APPLIED_REVISION_KEY = "_suite_applied_workspace_revision"
CLOUD_REVISION_KEY = "_suite_cloud_workspace_revision"
LAST_CONFIRMED_REVISION_KEY = "_music_last_confirmed_cloud_revision"
PENDING_CANONICAL_FP_KEY = "_music_pending_canonical_content_fp"
RESERVED_WRITE_REVISION_KEY = "_music_reserved_write_revision"


def workspace_revision_from_blob(state: dict[str, Any] | None) -> int:
    if not isinstance(state, dict):
        return 0
    ws = state.get("music_workspace_state")
    if isinstance(ws, dict):
        try:
            return int(ws.get("workspace_revision") or 0)
        except (TypeError, ValueError):
            pass
    try:
        return int(state.get("workspace_revision") or 0)
    except (TypeError, ValueError):
        return 0


def _revision_candidates(session: dict[str, Any], state: dict[str, Any] | None) -> list[int]:
    candidates: list[int] = []
    if state is not None:
        candidates.append(workspace_revision_from_blob(state))
    for key in (
        LOCAL_REVISION_KEY,
        APPLIED_REVISION_KEY,
        CLOUD_REVISION_KEY,
        LAST_CONFIRMED_REVISION_KEY,
        "_music_pending_save_revision",
        "_music_loaded_workspace_revision",
        "_music_selected_payload_revision",
        RESERVED_WRITE_REVISION_KEY,
    ):
        try:
            candidates.append(int(session.get(key) or 0))
        except (TypeError, ValueError):
            pass
    return candidates


def compute_monotonic_next_revision(session: dict[str, Any], state: dict[str, Any] | None = None) -> int:
    base = max(_revision_candidates(session, state) or [0])
    return base + 1


def bump_workspace_revision(session: dict[str, Any]) -> int:
    rev = compute_monotonic_next_revision(session, None)
    session[LOCAL_REVISION_KEY] = rev
    return rev


def reserve_workspace_revision_for_canonical_fp(
    session: dict[str, Any],
    state: dict[str, Any],
    canonical_fp: str,
) -> int:
    """Reserve one revision per canonical content fingerprint; reuse on retry."""
    fp = str(canonical_fp or "").strip()
    pending_fp = str(session.get(PENDING_CANONICAL_FP_KEY) or "").strip()
    reserved = session.get(RESERVED_WRITE_REVISION_KEY)
    if fp and pending_fp == fp and reserved is not None:
        rev = int(reserved)
    else:
        rev = compute_monotonic_next_revision(session, state)
        try:
            applied = int(session.get(APPLIED_REVISION_KEY) or 0)
            cloud = int(session.get(CLOUD_REVISION_KEY) or 0)
            rev = max(rev, applied + 1, cloud + 1)
        except (TypeError, ValueError):
            pass
        if fp:
            session[PENDING_CANONICAL_FP_KEY] = fp
        session[RESERVED_WRITE_REVISION_KEY] = rev
    session["_music_pending_save_revision"] = rev
    session[LOCAL_REVISION_KEY] = max(int(session.get(LOCAL_REVISION_KEY) or 0), rev)
    return rev


def stamp_workspace_revision_into_state(state: dict[str, Any], revision: int) -> dict[str, Any]:
    rev = int(revision)
    state["workspace_revision"] = rev
    ws = state.get("music_workspace_state")
    if isinstance(ws, dict):
        ws_copy = copy.deepcopy(ws)
        ws_copy["workspace_revision"] = rev
        state["music_workspace_state"] = ws_copy
    else:
        state["music_workspace_state"] = {"workspace_revision": rev}
    return state


def note_confirmed_workspace_revision(session: dict[str, Any], state: dict[str, Any]) -> None:
    rev = workspace_revision_from_blob(state)
    session[LAST_CONFIRMED_REVISION_KEY] = rev
    session[LOCAL_REVISION_KEY] = max(int(session.get(LOCAL_REVISION_KEY) or 0), rev)
    session.pop(RESERVED_WRITE_REVISION_KEY, None)
    session.pop(PENDING_CANONICAL_FP_KEY, None)
    session.pop("_music_pending_save_revision", None)
    session.pop("_music_workspace_save_pending_retry", None)
    session.pop("_music_retry_required", None)


def stamp_applied_workspace_revision(session: dict[str, Any], state: dict[str, Any]) -> None:
    rev = workspace_revision_from_blob(state)
    session[APPLIED_REVISION_KEY] = rev
    session[LOCAL_REVISION_KEY] = max(int(session.get(LOCAL_REVISION_KEY) or 0), rev)


def cloud_revision_newer_than_applied(session: dict[str, Any], cloud_state: dict[str, Any]) -> bool:
    cloud_rev = workspace_revision_from_blob(cloud_state)
    try:
        applied = int(session.get(APPLIED_REVISION_KEY) or 0)
    except (TypeError, ValueError):
        applied = 0
    session[CLOUD_REVISION_KEY] = cloud_rev
    return cloud_rev > applied


def collect_workspace_revision_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "local_workspace_revision": session.get(LOCAL_REVISION_KEY),
        "cloud_workspace_revision": session.get(CLOUD_REVISION_KEY),
        "applied_workspace_revision": session.get(APPLIED_REVISION_KEY),
        "last_cloud_save_timestamp": session.get("_suite_persist_last_save_at"),
        "last_cloud_hydrate_timestamp": session.get("_suite_persist_last_restore_at"),
        "save_source_session": session.get("_suite_persist_last_save_source"),
        "cloud_state_newer_than_local": session.get("_suite_persist_content_resync_needed"),
        "cloud_state_applied": bool(
            session.get("_music_authoritative_payload_applied")
            or (
                session.get("_suite_persist_restore_applied")
                and session.get("_music_selected_payload_revision") is not None
            )
        ),
        "conflict_detected": bool(session.get("_suite_workspace_conflict_detected")),
        "conflict_resolution_result": session.get("_suite_workspace_conflict_resolution"),
    }

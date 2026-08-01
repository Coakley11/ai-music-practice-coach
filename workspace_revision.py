"""Monotonic workspace revision for cross-device sync."""

from __future__ import annotations

from typing import Any

LOCAL_REVISION_KEY = "_suite_workspace_revision"
APPLIED_REVISION_KEY = "_suite_applied_workspace_revision"
CLOUD_REVISION_KEY = "_suite_cloud_workspace_revision"


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


def bump_workspace_revision(session: dict[str, Any]) -> int:
    try:
        current = int(session.get(LOCAL_REVISION_KEY) or 0)
    except (TypeError, ValueError):
        current = 0
    rev = current + 1
    session[LOCAL_REVISION_KEY] = rev
    return rev


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
        "cloud_state_applied": bool(session.get("_suite_persist_restore_applied")),
        "conflict_detected": bool(session.get("_suite_workspace_conflict_detected")),
        "conflict_resolution_result": session.get("_suite_workspace_conflict_resolution"),
    }

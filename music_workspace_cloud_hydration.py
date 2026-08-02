"""Cold-start cloud fetch diagnostics for music workspace."""

from __future__ import annotations

from typing import Any

HYDRATION_DIAG_KEY = "_music_cloud_hydration_diag"


def record_cloud_fetch_result(
    session: dict[str, Any],
    *,
    app_id: str,
    cloud_state: dict[str, Any] | None,
    cloud_ts: str | None,
    disk_state: dict[str, Any] | None,
    disk_ts: str | None,
    error: str = "",
    attempted: bool = True,
) -> None:
    try:
        from workspace_revision import workspace_revision_from_blob
    except ImportError:
        workspace_revision_from_blob = lambda _s: 0  # type: ignore[assignment,misc]

    cloud = cloud_state if isinstance(cloud_state, dict) else {}
    disk = disk_state if isinstance(disk_state, dict) else {}
    session[HYDRATION_DIAG_KEY] = {
        "cloud_fetch_attempted": attempted,
        "cloud_fetch_succeeded": bool(cloud) and not error,
        "cloud_fetch_error": error or "(none)",
        "cloud_document_found": bool(cloud),
        "cloud_workspace_id": str(session.get("_suite_persist_app_id") or app_id),
        "account_workspace_key": str(app_id),
        "cloud_loaded_revision": workspace_revision_from_blob(cloud),
        "disk_payload_found": bool(disk),
        "cloud_fetch_updated_at": cloud_ts,
        "disk_fetch_updated_at": disk_ts,
    }
    if cloud:
        session["_suite_last_cloud_fetch_payload"] = cloud
        session["_suite_cloud_fetch_updated_at"] = cloud_ts
        session["_music_loaded_workspace_revision"] = workspace_revision_from_blob(cloud)


def record_selected_payload_source(
    session: dict[str, Any],
    *,
    source: str,
    reason: str = "",
) -> None:
    diag = session.get(HYDRATION_DIAG_KEY)
    if not isinstance(diag, dict):
        diag = {}
    diag["selected_payload_source"] = source
    diag["no_payload_reason"] = reason or "(none)"
    session[HYDRATION_DIAG_KEY] = diag
    if source == "cloud":
        session["_music_cloud_payload_source"] = "cloud"
        session["_backing_cloud_payload_source"] = "fetch"
    elif source == "disk":
        session["_music_cloud_payload_source"] = "disk"
        session["_backing_cloud_payload_source"] = "disk"
    elif source != "none":
        session["_music_cloud_payload_source"] = source
    else:
        session["_music_cloud_payload_source"] = "none"
        if not session.get("_backing_cloud_payload_source"):
            session["_backing_cloud_payload_source"] = "none"


def collect_hydration_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    diag = session.get(HYDRATION_DIAG_KEY)
    return dict(diag) if isinstance(diag, dict) else {}


__all__ = [
    "HYDRATION_DIAG_KEY",
    "collect_hydration_diagnostics",
    "record_cloud_fetch_result",
    "record_selected_payload_source",
]

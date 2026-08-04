"""Unified logical workspace revision from Supabase metrics row (blob + top-level)."""

from __future__ import annotations

import copy
from typing import Any

FULL_SESSION_KEY = "full_session"

LOGICAL_SOURCE_TOP_LEVEL = "top_level"
LOGICAL_SOURCE_MUSIC_WORKSPACE_STATE = "music_workspace_state"
LOGICAL_SOURCE_FULL_SESSION_ROOT = "full_session_root"
LOGICAL_SOURCE_NONE = "none"

FILTER_TOP_LEVEL = "metrics->>workspace_revision"
FILTER_MUSIC_WORKSPACE_STATE = (
    "metrics->full_session->music_workspace_state->>workspace_revision"
)
FILTER_FULL_SESSION_ROOT = "metrics->full_session->>workspace_revision"

SESSION_CLOUD_METRICS_LOGICAL_KEY = "_music_cloud_metrics_logical_revision"


def _blob_revision_and_source(full: dict[str, Any] | None) -> tuple[int, str]:
    if not isinstance(full, dict):
        return 0, LOGICAL_SOURCE_NONE
    try:
        from workspace_revision import workspace_revision_from_blob

        rev = int(workspace_revision_from_blob(full))
    except ImportError:
        rev = 0
    if rev <= 0:
        return 0, LOGICAL_SOURCE_NONE
    ws = full.get("music_workspace_state")
    if isinstance(ws, dict):
        try:
            ws_rev = int(ws.get("workspace_revision") or 0)
        except (TypeError, ValueError):
            ws_rev = 0
        if ws_rev > 0:
            return rev, LOGICAL_SOURCE_MUSIC_WORKSPACE_STATE
    try:
        root_rev = int(full.get("workspace_revision") or 0)
    except (TypeError, ValueError):
        root_rev = 0
    if root_rev > 0:
        return rev, LOGICAL_SOURCE_FULL_SESSION_ROOT
    return rev, LOGICAL_SOURCE_MUSIC_WORKSPACE_STATE


def _filter_path_for_source(source: str) -> str:
    if source == LOGICAL_SOURCE_TOP_LEVEL:
        return FILTER_TOP_LEVEL
    if source == LOGICAL_SOURCE_MUSIC_WORKSPACE_STATE:
        return FILTER_MUSIC_WORKSPACE_STATE
    if source == LOGICAL_SOURCE_FULL_SESSION_ROOT:
        return FILTER_FULL_SESSION_ROOT
    return FILTER_TOP_LEVEL


def resolve_logical_stored_revision(metrics: dict[str, Any] | None) -> dict[str, Any]:
    """
    One logical revision for hydration, CAS preflight, row probe, and PATCH compare.

    Precedence:
    - Blob revision is canonical for workspace content (Items 1–7).
    - Top-level metrics.workspace_revision is used only when present, positive, and
      equal to the canonical blob revision.
    - Otherwise logical revision and CAS filter use the blob path (music_workspace_state
      preferred over full_session root).
    """
    stored = dict(metrics) if isinstance(metrics, dict) else {}
    full = stored.get(FULL_SESSION_KEY)
    blob_rev, blob_source = _blob_revision_and_source(full if isinstance(full, dict) else {})

    top_present = "workspace_revision" in stored
    top_raw = stored.get("workspace_revision") if top_present else None
    try:
        top_int = int(top_raw) if top_raw is not None else 0
    except (TypeError, ValueError):
        top_int = 0

    top_consistent: bool | None = None
    if blob_rev > 0 and top_present:
        top_consistent = top_int > 0 and top_int == blob_rev

    if blob_rev > 0:
        if top_consistent:
            logical = blob_rev
            source = LOGICAL_SOURCE_TOP_LEVEL
        else:
            logical = blob_rev
            source = blob_source
    elif top_int > 0:
        logical = top_int
        source = LOGICAL_SOURCE_TOP_LEVEL
    else:
        logical = 0
        source = LOGICAL_SOURCE_NONE

    filter_path = _filter_path_for_source(source)
    return {
        "logical_revision": logical,
        "stored_logical_workspace_revision": logical,
        "logical_revision_source": source,
        "selected_cas_filter_path": filter_path,
        "stored_top_level_present": top_present,
        "stored_top_level_workspace_revision": top_raw,
        "stored_blob_workspace_revision": blob_rev,
        "top_level_consistent_with_blob": top_consistent,
    }


def metrics_logical_workspace_revision(metrics: dict[str, Any] | None) -> int:
    return int(resolve_logical_stored_revision(metrics).get("logical_revision") or 0)


def build_cas_patch_filter_params(
    stored_metrics: dict[str, Any] | None,
    expected_workspace_revision: int,
) -> tuple[dict[str, str], str, dict[str, Any]]:
    resolved = resolve_logical_stored_revision(stored_metrics)
    key = str(resolved.get("selected_cas_filter_path") or FILTER_TOP_LEVEL)
    expected_s = str(int(expected_workspace_revision))
    return {key: f"eq.{expected_s}"}, key, resolved


def describe_cas_patch_filter(
    stored_metrics: dict[str, Any] | None,
    expected_workspace_revision: int,
) -> str:
    params, field, _resolved = build_cas_patch_filter_params(stored_metrics, expected_workspace_revision)
    op = params.get(field, f"eq.{int(expected_workspace_revision)}")
    return f"{field}={op}"


def sync_metrics_revision_surfaces(metrics: dict[str, Any], candidate_revision: int) -> dict[str, Any]:
    """Write the same candidate revision to all metrics/full_session revision surfaces."""
    rev = int(candidate_revision)
    out = dict(metrics)
    out["workspace_revision"] = rev
    full = out.get(FULL_SESSION_KEY)
    if isinstance(full, dict):
        try:
            from workspace_revision import stamp_workspace_revision_into_state

            out[FULL_SESSION_KEY] = stamp_workspace_revision_into_state(copy.deepcopy(full), rev)
        except ImportError:
            stamped = copy.deepcopy(full)
            stamped["workspace_revision"] = rev
            ws = stamped.get("music_workspace_state")
            if isinstance(ws, dict):
                ws = copy.deepcopy(ws)
                ws["workspace_revision"] = rev
                stamped["music_workspace_state"] = ws
            else:
                stamped["music_workspace_state"] = {"workspace_revision": rev}
            out[FULL_SESSION_KEY] = stamped
    return out


def revision_for_authoritative_hydrate(
    session: dict[str, Any] | None,
    payload: dict[str, Any] | None,
) -> int:
    """Same logical rule as cloud metrics row when session holds a recent resolve snapshot."""
    ss = session if isinstance(session, dict) else {}
    cached = ss.get(SESSION_CLOUD_METRICS_LOGICAL_KEY)
    if isinstance(cached, dict):
        try:
            lr = int(cached.get("logical_revision") or 0)
        except (TypeError, ValueError):
            lr = 0
        if lr > 0:
            return lr
    try:
        from workspace_revision import workspace_revision_from_blob

        return int(workspace_revision_from_blob(payload if isinstance(payload, dict) else {}))
    except ImportError:
        return 0


def cache_cloud_metrics_logical_revision(session: dict[str, Any], metrics: dict[str, Any] | None) -> dict[str, Any]:
    resolved = resolve_logical_stored_revision(metrics)
    session[SESSION_CLOUD_METRICS_LOGICAL_KEY] = dict(resolved)
    return resolved


__all__ = [
    "FILTER_FULL_SESSION_ROOT",
    "FILTER_MUSIC_WORKSPACE_STATE",
    "FILTER_TOP_LEVEL",
    "FULL_SESSION_KEY",
    "LOGICAL_SOURCE_FULL_SESSION_ROOT",
    "LOGICAL_SOURCE_MUSIC_WORKSPACE_STATE",
    "LOGICAL_SOURCE_NONE",
    "LOGICAL_SOURCE_TOP_LEVEL",
    "SESSION_CLOUD_METRICS_LOGICAL_KEY",
    "build_cas_patch_filter_params",
    "cache_cloud_metrics_logical_revision",
    "describe_cas_patch_filter",
    "metrics_logical_workspace_revision",
    "resolve_logical_stored_revision",
    "revision_for_authoritative_hydrate",
    "sync_metrics_revision_surfaces",
]

"""Hydrate durable workspace data before a URL entry may persist a new context.

URL intent owns navigation/active context, not the existence of saved resources.
Use the ordinary full-state reader/applicator rather than a second library schema.
"""
from __future__ import annotations

from typing import Any, Callable

REQUIRED = "_music_entry_workspace_required"
READY = "_music_entry_workspace_ready"
LOADING = "_music_entry_workspace_loading"


def require_entry_workspace(session: dict[str, Any]) -> None:
    session[REQUIRED] = True


def assert_entry_workspace_ready(session: dict[str, Any]) -> None:
    if session.get(REQUIRED) and (session.get(LOADING) or not session.get(READY)):
        raise RuntimeError("Music entry workspace hydration is incomplete; persistence deferred")


def hydrate_entry_workspace(
    st: Any, *, apply_state: Callable[[Any, dict[str, Any]], None], cloud_first: bool = True,
) -> bool:
    """Once per cold URL entry, restore resources, then reassert URL context intent.

    An unsuccessful read/apply never grants write authority. The guard also stops
    nested activation saves while the full workspace is only partially applied.
    """
    ss = st.session_state
    require_entry_workspace(ss)
    if ss.get(READY):
        return True
    if ss.get("_music_workspace_blob_hydrated") and not ss.get("_music_entry_workspace_error"):
        ss[READY] = True  # already loaded by ordinary startup in this browser
        return True
    from suite_cloud_state import load_cloud_full_session, pick_restore_session
    from suite_user_persistence import _load_raw

    ss[LOADING] = True
    try:
        cloud, cloud_ts = load_cloud_full_session("music")
        disk, warning, disk_ts = _load_raw("music")
        error = str(ss.get("_cloud_fetch_error") or "")
        if not cloud and (warning or (not disk and error not in ("", "cloud_storage_disabled"))):
            raise RuntimeError(warning or error)
        picked = pick_restore_session(cloud, cloud_ts, disk, disk_ts,
                                      local_dirty=False, cloud_first=cloud_first)
        if picked.state:
            if picked.source == "cloud":
                ss["_music_authoritative_cloud_apply"] = True
            apply_state(st, picked.state)
        # Full hydration can restore the old active source/page. Reapply only the
        # existing URL launch intent; finalization still uses its normal owner API.
        from suite_resume_launch import _apply_music, _qp_get
        _apply_music(st, _qp_get(st, "suite_resume"), _qp_get(st, "suite_page"))
        ss.pop("_suite_resume_finalized_music", None)
        ss["_suite_resume_launch_music"] = True
        ss["_music_entry_workspace_source"] = picked.source
        ss[READY] = True
        ss.pop("_music_entry_workspace_error", None)
        return True
    except Exception as exc:
        ss["_music_entry_workspace_error"] = str(exc)
        return False
    finally:
        ss.pop(LOADING, None)

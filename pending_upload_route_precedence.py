"""Startup route precedence: prepared Upload Analysis wins over stale Mission Jam backing."""

from __future__ import annotations

import copy
from typing import Any

PENDING_UPLOAD_ROUTE_DIAG_KEY = "_pending_upload_route_restore_diag"
PENDING_UPLOAD_ROUTE_LOCK_KEY = "_pending_upload_route_lock"
PENDING_UPLOAD_ROUTE_TRACE_KEY = "_pending_upload_route_trace"

_USER_NAV_REASONS = frozenset(
    {
        "user_nav_this_run",
        "user_navigation",
        "user_navigation_preserve",
        "user_page_preserved",
        "pending_upload_cleared",
        "explicit_user_navigation",
    }
)


def record_pending_upload_route_trace(
    session: dict[str, Any],
    *,
    stage: str,
    old_page: str = "",
    new_page: str = "",
    source: str = "",
    reason: str = "",
) -> None:
    trace = session.get(PENDING_UPLOAD_ROUTE_TRACE_KEY)
    if not isinstance(trace, list):
        trace = []
    run_seq = int(session.get("_script_run_seq") or 0)
    trace.append(
        {
            "run_seq": run_seq,
            "stage": stage,
            "old_page": old_page or None,
            "new_page": new_page or None,
            "source": source or None,
            "reason": reason or None,
        }
    )
    session[PENDING_UPLOAD_ROUTE_TRACE_KEY] = trace[-40:]


def pending_upload_owns_active_destination(session: dict[str, Any], blob: dict[str, Any] | None = None) -> bool:
    return pending_upload_should_restore_analysis_page(session, blob)


def _route_from_blob(blob: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(blob, dict):
        return None
    mws = blob.get("music_workspace_state")
    if isinstance(mws, dict):
        route = mws.get("pending_upload_route")
        if isinstance(route, dict):
            return route
    return None


def durable_pending_upload_route_active(
    session: dict[str, Any],
    blob: dict[str, Any] | None = None,
) -> bool:
    """Route lock must come from cloud envelope or music_workspace_state — not session-only."""
    route = _route_from_blob(blob)
    if isinstance(route, dict):
        if route.get("route_lock") and str(route.get("destination_page") or "") == "analysis":
            return True
    env = _envelope(session, blob)
    if not env:
        return False
    nav = env.get("navigation") if isinstance(env.get("navigation"), dict) else {}
    if nav.get("route_lock") and nav.get("resume_upload_analysis") is not False:
        return True
    if str(env.get("active_destination_page") or "").strip().lower() == "analysis" and nav.get(
        "resume_upload_analysis"
    ):
        return bool(nav.get("route_lock"))
    return False


def pending_upload_blocks_passive_creative_sync(session: dict[str, Any], *, reason: str = "") -> bool:
    if not durable_pending_upload_route_active(session, session.get("_suite_last_cloud_fetch_payload")):
        if not session.get(PENDING_UPLOAD_ROUTE_LOCK_KEY):
            return False
    try:
        from mission_pending_upload_analysis import SAVE_REASON_MISSION_PENDING_UPLOAD
    except ImportError:
        SAVE_REASON_MISSION_PENDING_UPLOAD = "mission_pending_upload_handoff"
    allowed = {
        SAVE_REASON_MISSION_PENDING_UPLOAD,
        "pending_upload_navigation_handoff",
        "mission_pending_upload_cleared",
        "mission_pending_upload_handoff",
    }
    r = str(reason or "").strip()
    if r in allowed:
        return False
    if str(session.get("studio_page") or "").strip().lower() == "analysis":
        return True
    return bool(session.get(PENDING_UPLOAD_ROUTE_LOCK_KEY))


def pending_upload_owns_active_destination(session: dict[str, Any], blob: dict[str, Any] | None = None) -> bool:
    return pending_upload_should_restore_analysis_page(session, blob)


def guard_studio_page_write_for_pending_upload(
    session: dict[str, Any],
    page: str,
    *,
    reason: str = "",
) -> str:
    """Block passive overwrites of analysis while prepared upload resume is active."""
    proposed = str(page or "").strip().lower()
    blob = session.get("_suite_last_cloud_fetch_payload")
    blob_dict = blob if isinstance(blob, dict) else None
    if not pending_upload_owns_active_destination(session, blob_dict):
        return proposed or str(page or "")
    if proposed == "analysis":
        return "analysis"
    r = str(reason or "").strip()
    if r in _USER_NAV_REASONS or session.get("_music_user_navigated_page_this_run"):
        record_pending_upload_route_trace(
            session,
            stage="guard_allow_user_nav",
            old_page=str(session.get("studio_page") or ""),
            new_page=proposed,
            source="pending_upload_route_precedence",
            reason=r or "user_nav",
        )
        return proposed
    if session.get(PENDING_UPLOAD_ROUTE_LOCK_KEY) or durable_pending_upload_route_active(
        session, blob_dict
    ):
        old = str(session.get("studio_page") or "")
        record_pending_upload_route_trace(
            session,
            stage="guard_block_overwrite",
            old_page=old,
            new_page=proposed,
            source="pending_upload_route_precedence",
            reason=r or "blocked",
        )
        return "analysis"
    return proposed or str(page or "")


def apply_pending_upload_startup_page_if_needed(session: dict[str, Any]) -> str | None:
    """Early startup: pending prepared take owns Upload Analysis destination."""
    blob = session.get("_suite_last_cloud_fetch_payload")
    blob_dict = blob if isinstance(blob, dict) else None
    if not pending_upload_should_restore_analysis_page(session, blob_dict):
        return None
    old = str(session.get("studio_page") or "")
    session[PENDING_UPLOAD_ROUTE_LOCK_KEY] = True
    session["_pending_upload_suppresses_mission_backing"] = True
    try:
        from studio_nav_state import write_canonical_studio_nav_state

        write_canonical_studio_nav_state(session, "analysis", reason="pending_upload_startup_owner")
    except ImportError:
        session["studio_page"] = "analysis"
    try:
        from music_persistent_state import synchronize_page_bearing_state_for_save

        synchronize_page_bearing_state_for_save(session, "analysis")
    except ImportError:
        pass
    record_pending_upload_route_trace(
        session,
        stage="startup_page_owner",
        old_page=old,
        new_page="analysis",
        source="apply_pending_upload_startup_page_if_needed",
        reason="pending_upload_analysis",
    )
    return "analysis"


def _envelope(session: dict[str, Any], blob: dict[str, Any] | None = None) -> dict[str, Any] | None:
    try:
        from mission_pending_upload_analysis import (
            PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY,
            envelope_from_session_or_canonical,
        )

        env = envelope_from_session_or_canonical(session)
        if env:
            return env
        if isinstance(blob, dict):
            cws = blob.get("creative_workspace_state")
            if isinstance(cws, dict):
                raw = cws.get(PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY)
                if isinstance(raw, dict) and raw.get("take_id"):
                    return raw
    except ImportError:
        pass
    return None


def pending_upload_should_restore_analysis_page(
    session: dict[str, Any],
    blob: dict[str, Any] | None = None,
) -> bool:
    env = _envelope(session, blob)
    if not env or str(env.get("analysis_status") or "") != "prepared":
        return False
    nav = env.get("navigation") if isinstance(env.get("navigation"), dict) else {}
    if nav.get("resume_upload_analysis") is False:
        return False
    if session.get("_pending_upload_user_left_analysis"):
        return False
    if not durable_pending_upload_route_active(session, blob):
        return False
    if nav.get("resume_upload_analysis") is True:
        return True
    return str(env.get("active_destination_page") or "").strip().lower() == "analysis"


def resolve_pending_upload_studio_page(
    session: dict[str, Any],
    blob: dict[str, Any] | None = None,
) -> tuple[str, str] | None:
    if pending_upload_should_restore_analysis_page(session, blob):
        return "analysis", "pending_upload_analysis"
    return None


def deactivate_mission_jam_route_for_upload_handoff(session: dict[str, Any]) -> None:
    session["_pending_upload_suppresses_mission_backing"] = True
    try:
        from backing_session_route import deactivate_mission_backing_ui_state

        deactivate_mission_backing_ui_state(session)
    except ImportError:
        pass
    try:
        from mission_backing_handoff_persistence import (
            MISSION_BACKING_HANDOFF_ACTIVE_KEY,
            MISSION_BACKING_HANDOFF_SEALED_FOR_PAGE_CHANGE_KEY,
        )

        session.pop(MISSION_BACKING_HANDOFF_ACTIVE_KEY, None)
        session.pop(MISSION_BACKING_HANDOFF_SEALED_FOR_PAGE_CHANGE_KEY, None)
    except ImportError:
        session.pop("_mission_backing_handoff_active", None)


def apply_pending_upload_to_save_payload(session: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """Pin Upload Analysis destination into cloud payload when pending handoff owns the route."""
    blob = session.get("_suite_last_cloud_fetch_payload")
    blob_dict = blob if isinstance(blob, dict) else None
    owns = bool(session.get(PENDING_UPLOAD_ROUTE_LOCK_KEY)) or pending_upload_should_restore_analysis_page(
        session, blob_dict
    ) or durable_pending_upload_route_active(session, blob_dict)
    if not owns:
        return state
    page = "analysis"
    try:
        from mission_pending_upload_analysis import envelope_from_session_or_canonical

        env = envelope_from_session_or_canonical(session) or {}
    except ImportError:
        env = {}
    nav = env.get("navigation") if isinstance(env.get("navigation"), dict) else {}
    route_blob = {
        "destination_page": page,
        "studio_page": page,
        "resume_upload_analysis": nav.get("resume_upload_analysis", True),
        "route_lock": True,
        "take_id": env.get("take_id"),
        "destination_workflow": nav.get("workflow_owner") or "pending_mission_upload_analysis",
    }
    mws = state.get("music_workspace_state")
    if not isinstance(mws, dict):
        mws = {}
        state["music_workspace_state"] = mws
    mws["studio_page"] = page
    mws["page"] = page
    mws["pending_upload_route"] = copy.deepcopy(route_blob)
    core = state.get("core")
    if isinstance(core, dict):
        core["studio_page"] = page
    sns = state.get("studio_nav_state")
    if isinstance(sns, dict):
        sns["studio_page"] = page
        sns["page"] = page
    cws = state.get("creative_workspace_state")
    if isinstance(cws, dict) and env:
        cws.setdefault("pending_upload_analysis_envelope", copy.deepcopy(env))
    record_pending_upload_route_trace(
        session,
        stage="payload_pin_analysis",
        old_page=str(session.get("studio_page") or ""),
        new_page=page,
        source="apply_pending_upload_to_save_payload",
        reason="cloud_save",
    )
    return state


def hydrate_pending_upload_route_from_payload(session: dict[str, Any], payload: dict[str, Any]) -> None:
    """Restore route lock from durable music_workspace_state.pending_upload_route."""
    mws = payload.get("music_workspace_state") if isinstance(payload.get("music_workspace_state"), dict) else {}
    route = mws.get("pending_upload_route") if isinstance(mws, dict) else None
    if not isinstance(route, dict):
        return
    if not route.get("route_lock") and not route.get("resume_upload_analysis"):
        return
    if str(route.get("destination_page") or "") != "analysis":
        return
    session[PENDING_UPLOAD_ROUTE_LOCK_KEY] = True
    session["_pending_upload_suppresses_mission_backing"] = True
    record_pending_upload_route_trace(
        session,
        stage="hydrate_route_from_payload",
        old_page=str(session.get("studio_page") or ""),
        new_page="analysis",
        source="music_workspace_state.pending_upload_route",
        reason="cloud_hydrate",
    )


def attach_navigation_to_envelope(env: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(env)
    out["active_destination_page"] = "analysis"
    out["navigation"] = {
        "studio_page": "analysis",
        "workflow_owner": "pending_mission_upload_analysis",
        "resume_upload_analysis": True,
        "mission_jam_route_suppressed": True,
        "route_lock": True,
        "destination_workflow": "pending_mission_upload_analysis",
    }
    return out


def commit_pending_upload_navigation_handoff(
    session: dict[str, Any],
    *,
    st: Any | None = None,
    persist_save: bool = True,
) -> None:
    """Pin durable destination to Upload Analysis and drop transient mission backing route."""
    try:
        from mission_pending_upload_analysis import (
            PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY,
            envelope_from_session_or_canonical,
        )
    except ImportError:
        return
    env = envelope_from_session_or_canonical(session)
    if not env:
        return
    merged = attach_navigation_to_envelope(env)
    session[PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY] = merged
    try:
        from creative_workspace_state_persistence import (
            gather_creative_workspace_from_session,
            write_canonical_creative_workspace,
        )
        from mission_pending_upload_analysis import SAVE_REASON_MISSION_PENDING_UPLOAD

        blob = gather_creative_workspace_from_session(session)
        blob[PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY] = copy.deepcopy(merged)
        write_canonical_creative_workspace(session, blob, reason=SAVE_REASON_MISSION_PENDING_UPLOAD)
    except ImportError:
        pass
    deactivate_mission_jam_route_for_upload_handoff(session)
    session[PENDING_UPLOAD_ROUTE_LOCK_KEY] = True
    record_pending_upload_route_trace(
        session,
        stage="handoff_commit",
        old_page=str(session.get("studio_page") or ""),
        new_page="analysis",
        source="commit_pending_upload_navigation_handoff",
        reason="pending_upload_handoff",
    )
    try:
        from studio_nav_state import write_canonical_studio_nav_state

        write_canonical_studio_nav_state(session, "analysis", reason="pending_upload_handoff")
    except ImportError:
        session["studio_page"] = "analysis"
    session["_navigate_to_studio_page"] = "analysis"
    try:
        from music_persistent_state import synchronize_page_bearing_state_for_save

        synchronize_page_bearing_state_for_save(session, "analysis")
    except ImportError:
        pass
    if persist_save and st is not None:
        try:
            from music_persistent_state import force_save_music_state

            force_save_music_state(st, reason="pending_upload_navigation_handoff")
        except Exception:
            pass


def release_pending_upload_resume_route(session: dict[str, Any], *, new_page: str) -> None:
    """User navigated away from Upload Analysis — keep take, stop forcing analysis on refresh."""
    page = str(new_page or "").strip().lower()
    if page == "analysis":
        return
    try:
        from mission_pending_upload_analysis import (
            PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY,
            envelope_from_session_or_canonical,
        )
    except ImportError:
        return
    env = envelope_from_session_or_canonical(session)
    if not env or str(env.get("analysis_status") or "") != "prepared":
        return
    nav = dict(env.get("navigation") or {})
    nav["resume_upload_analysis"] = False
    updated = copy.deepcopy(env)
    updated["navigation"] = nav
    session[PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY] = updated
    session["_pending_upload_user_left_analysis"] = True
    session.pop(PENDING_UPLOAD_ROUTE_LOCK_KEY, None)
    record_pending_upload_route_trace(
        session,
        stage="release_resume_route",
        old_page="analysis",
        new_page=page,
        source="release_pending_upload_resume_route",
        reason="user_left_analysis",
    )


def enforce_pending_upload_startup_route(session: dict[str, Any], *, st: Any | None = None) -> dict[str, Any]:
    """Run after page snapshot hydration — pending analysis must win over backing restore."""
    blob = session.get("_suite_last_cloud_fetch_payload")
    blob_dict = blob if isinstance(blob, dict) else None
    candidates: list[tuple[str, str]] = []
    cur = str(session.get("studio_page") or "").strip().lower()
    if cur:
        candidates.append((cur, "session_studio_page"))
    try:
        from mission_pending_upload_analysis import envelope_from_session_or_canonical

        env = envelope_from_session_or_canonical(session)
    except ImportError:
        env = None
    pending_win = pending_upload_should_restore_analysis_page(session, blob_dict)
    diag: dict[str, Any] = {
        "hydrated_take_id": (env or {}).get("take_id"),
        "pending_analysis_status": (env or {}).get("analysis_status"),
        "persisted_active_destination": ((env or {}).get("navigation") or {}).get("studio_page")
        or (env or {}).get("active_destination_page"),
        "persisted_backing_session_type": (session.get("backing_session_route") or {}).get(
            "backing_session_type"
        ),
        "route_candidates": candidates,
        "winning_route": cur,
        "winning_route_reason": "unchanged",
        "stale_mission_jam_suppressed": bool(session.get("_pending_upload_suppresses_mission_backing")),
        "audio_hydrate": (session.get("_pending_upload_analysis_diag") or {}).get("hydrate"),
    }
    if pending_win:
        try:
            from mission_pending_upload_persistence import apply_pending_upload_envelope_to_session

            apply_pending_upload_envelope_to_session(session, st=st, source="startup_route_precedence")
        except ImportError:
            session["studio_page"] = "analysis"
        try:
            from studio_nav_state import write_canonical_studio_nav_state

            write_canonical_studio_nav_state(session, "analysis", reason="pending_upload_route_precedence")
        except ImportError:
            session["studio_page"] = "analysis"
        diag["winning_route"] = "analysis"
        diag["winning_route_reason"] = "pending_upload_analysis"
        diag["stale_mission_jam_suppressed"] = True
    session[PENDING_UPLOAD_ROUTE_DIAG_KEY] = diag
    return diag


def render_pending_upload_route_dev_diagnostics(st_module: Any, session: dict[str, Any]) -> None:
    try:
        from suite_workspace import is_developer_mode_enabled

        if not is_developer_mode_enabled(st=st_module):
            return
    except ImportError:
        if not session.get("dev_mode"):
            return
    diag = dict(session.get(PENDING_UPLOAD_ROUTE_DIAG_KEY) or {})
    deploy = str(session.get("_studio_ui_release_sha") or "—")
    trace_tail = (session.get(PENDING_UPLOAD_ROUTE_TRACE_KEY) or [])[-3:]
    st_module.caption(
        "DEV route restore · "
        f"take `{diag.get('hydrated_take_id', '—')}` · "
        f"status `{diag.get('pending_analysis_status', '—')}` · "
        f"dest `{diag.get('persisted_active_destination', '—')}` · "
        f"win `{diag.get('winning_route', '—')}` ({diag.get('winning_route_reason', '—')}) · "
        f"lock `{session.get(PENDING_UPLOAD_ROUTE_LOCK_KEY)}` · "
        f"trace `{trace_tail}` · "
        f"sha `{deploy[:7] if deploy else '—'}`"
    )


__all__ = [
    "apply_pending_upload_to_save_payload",
    "durable_pending_upload_route_active",
    "pending_upload_blocks_passive_creative_sync",
    "commit_pending_upload_navigation_handoff",
    "enforce_pending_upload_startup_route",
    "hydrate_pending_upload_route_from_payload",
    "pending_upload_should_restore_analysis_page",
    "release_pending_upload_resume_route",
    "render_pending_upload_route_dev_diagnostics",
    "resolve_pending_upload_studio_page",
]

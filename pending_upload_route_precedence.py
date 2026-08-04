"""Startup route precedence: prepared Upload Analysis wins over stale Mission Jam backing."""

from __future__ import annotations

import copy
from typing import Any

PENDING_UPLOAD_ROUTE_DIAG_KEY = "_pending_upload_route_restore_diag"


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


def attach_navigation_to_envelope(env: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(env)
    out["active_destination_page"] = "analysis"
    out["navigation"] = {
        "studio_page": "analysis",
        "workflow_owner": "pending_mission_upload_analysis",
        "resume_upload_analysis": True,
        "mission_jam_route_suppressed": True,
    }
    return out


def commit_pending_upload_navigation_handoff(session: dict[str, Any], *, st: Any | None = None) -> None:
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
    try:
        from studio_nav_state import write_canonical_studio_nav_state

        write_canonical_studio_nav_state(session, "analysis", reason="pending_upload_handoff")
    except ImportError:
        session["studio_page"] = "analysis"
    session["_navigate_to_studio_page"] = "analysis"
    if st is not None:
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
    st_module.caption(
        "DEV route restore · "
        f"take `{diag.get('hydrated_take_id', '—')}` · "
        f"status `{diag.get('pending_analysis_status', '—')}` · "
        f"dest `{diag.get('persisted_active_destination', '—')}` · "
        f"win `{diag.get('winning_route', '—')}` ({diag.get('winning_route_reason', '—')}) · "
        f"mission_jam_suppressed `{diag.get('stale_mission_jam_suppressed')}` · "
        f"sha `{deploy[:7] if deploy else '—'}`"
    )


__all__ = [
    "commit_pending_upload_navigation_handoff",
    "enforce_pending_upload_startup_route",
    "pending_upload_should_restore_analysis_page",
    "release_pending_upload_resume_route",
    "render_pending_upload_route_dev_diagnostics",
    "resolve_pending_upload_studio_page",
]

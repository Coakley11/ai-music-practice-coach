"""Mission Backing navigation handoff — defer artifact cloud save until page_change."""

from __future__ import annotations

import copy
from typing import Any

from improvisation_missions import MISSION_PRACTICE_LICK_KEY

MISSION_BACKING_HANDOFF_DIAG_KEY = "_mission_backing_handoff_diag"
MISSION_BACKING_HANDOFF_ACTIVE_KEY = "_mission_backing_handoff_active"


def _normalize_page(session: dict[str, Any]) -> str:
    return str(session.get("studio_page") or "").strip().lower()


def _backing_subview_label(session: dict[str, Any]) -> str:
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            return str(ctx.source or "").strip() or "unknown"
    except ImportError:
        pass
    return ""


def _studio_nav_snapshot(session: dict[str, Any]) -> dict[str, Any]:
    nav = session.get("studio_nav_state")
    if isinstance(nav, dict):
        return copy.deepcopy(nav)
    return {}


def _backing_state_snapshot(session: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"backing_subview": _backing_subview_label(session)}
    try:
        from backing_track_state import BACKING_STATE_KEY

        blob = session.get(BACKING_STATE_KEY)
        if isinstance(blob, dict):
            out["backing_track_state"] = copy.deepcopy(blob)
    except ImportError:
        pass
    try:
        from backing_context import BACKING_CONTEXT_KEY

        ctx = session.get(BACKING_CONTEXT_KEY)
        if isinstance(ctx, dict):
            out["backing_context_source"] = ctx.get("source")
    except ImportError:
        pass
    return out


def _payload_page_fields(session: dict[str, Any]) -> dict[str, str]:
    stamp = session.get("_music_save_payload_stamp_trace")
    if isinstance(stamp, dict):
        pages = {
            k: str(stamp.get(k) or "").strip()
            for k in (
                "core_studio_page",
                "session_studio_page",
                "workspace_studio_page",
                "studio_nav_studio_page",
                "page_change_write_pending",
                "build_page_change_target",
            )
        }
        if any(pages.values()):
            return pages
    try:
        from music_page_save_pipeline_trace import payload_pages_from_state
        from music_persistent_state import build_music_disk_state

        import streamlit as st

        st_like = type("_St", (), {"session_state": session})()
        payload = build_music_disk_state(st_like)
        pages = payload_pages_from_state(payload)
        env = payload.get("music_workspace_state")
        if isinstance(env, dict):
            pages["envelope"] = str(env.get("studio_page") or env.get("page") or "").strip()
        return {k: str(v or "") for k, v in pages.items()}
    except Exception:
        return {}


def _diag(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(MISSION_BACKING_HANDOFF_DIAG_KEY)
    if isinstance(raw, dict):
        return raw
    d: dict[str, Any] = {"violations": []}
    session[MISSION_BACKING_HANDOFF_DIAG_KEY] = d
    return d


def begin_mission_backing_handoff(
    session: dict[str, Any],
    *,
    navigation_callback: str,
    with_practice_lick: bool,
) -> None:
    session[MISSION_BACKING_HANDOFF_ACTIVE_KEY] = True
    d = _diag(session)
    d.clear()
    d.update(
        {
            "navigation_callback": navigation_callback,
            "with_practice_lick": with_practice_lick,
            "page_before": _normalize_page(session),
            "backing_subview_before": _backing_subview_label(session),
            "studio_nav_state_before": _studio_nav_snapshot(session),
            "backing_view_state_before": _backing_state_snapshot(session),
            "practice_lick_present_before": bool(session.get(MISSION_PRACTICE_LICK_KEY)),
            "violations": [],
        }
    )


def complete_mission_backing_handoff_after_navigation(
    session: dict[str, Any],
    *,
    navigation_callback: str,
    backing_source: str,
) -> None:
    d_raw = session.get(MISSION_BACKING_HANDOFF_DIAG_KEY)
    if not isinstance(d_raw, dict) or not d_raw.get("with_practice_lick"):
        session.pop(MISSION_BACKING_HANDOFF_ACTIVE_KEY, None)
        return
    session.pop(MISSION_BACKING_HANDOFF_ACTIVE_KEY, None)
    d = _diag(session)
    d["navigation_callback"] = navigation_callback
    d["page_after"] = _normalize_page(session)
    d["backing_subview_after"] = _backing_subview_label(session) or str(backing_source or "").strip()
    d["studio_nav_state_after"] = _studio_nav_snapshot(session)
    d["backing_view_state_after"] = _backing_state_snapshot(session)
    d["canonical_studio_nav_page_after"] = str(
        (d.get("studio_nav_state_after") or {}).get("studio_page")
        or (d.get("studio_nav_state_after") or {}).get("page")
        or ""
    ).strip()
    d["practice_lick_present_in_payload"] = _practice_lick_in_last_payload(session)
    d["practice_lick_present_after"] = bool(session.get(MISSION_PRACTICE_LICK_KEY))
    d["save_reason"] = str(
        session.get("_suite_persist_last_save_reason")
        or session.get("_music_build_save_reason")
        or ""
    ).strip()
    d["reserved_revision"] = session.get("_music_last_reserved_workspace_revision")
    d["confirmed_revision"] = session.get("_music_last_confirmed_cloud_revision")
    d["upsert_result"] = bool(session.get("_suite_persist_last_save_cloud"))
    d["payload_page_fields"] = _payload_page_fields(session)
    d["authoritative_refetched_page"] = d.get("payload_page_fields", {}).get("workspace") or d.get(
        "payload_page_fields", {}
    ).get("envelope")
    d["authoritative_refetched_backing_subview"] = d.get("backing_subview_after")
    d["overwrite_source"] = session.get("page_restore_overwrite_source") or session.get(
        "_music_page_restore_overwrite_source"
    )
    if d.get("save_reason") == "creative_mission_practice_lick_change":
        violations = list(d.get("violations") or [])
        violations.append("HANDOFF_ARTIFACT_SAVE_BEFORE_PAGE_CHANGE")
        d["violations"] = violations
    if _normalize_page(session) != "backing":
        violations = list(d.get("violations") or [])
        violations.append("HANDOFF_PAGE_NOT_BACKING_AFTER_NAV")
        d["violations"] = violations
    if d.get("backing_subview_after") not in ("mission", ""):
        if str(backing_source or "") != "mission":
            violations = list(d.get("violations") or [])
            violations.append("HANDOFF_BACKING_SUBVIEW_NOT_MISSION")
            d["violations"] = violations
    session.pop(MISSION_BACKING_HANDOFF_ACTIVE_KEY, None)


def _practice_lick_in_last_payload(session: dict[str, Any]) -> bool:
    try:
        from creative_mission_artifact_persistence import canonical_mission_artifact_value

        if canonical_mission_artifact_value(session, MISSION_PRACTICE_LICK_KEY):
            return True
    except ImportError:
        pass
    fetch = session.get("_suite_last_cloud_fetch_payload")
    if isinstance(fetch, dict):
        cws = fetch.get("creative_workspace_state")
        if isinstance(cws, dict) and cws.get(MISSION_PRACTICE_LICK_KEY):
            return True
        sess = fetch.get("session")
        if isinstance(sess, dict) and sess.get(MISSION_PRACTICE_LICK_KEY):
            return True
    return bool(session.get(MISSION_PRACTICE_LICK_KEY))


def collect_mission_backing_handoff_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    d = session.get(MISSION_BACKING_HANDOFF_DIAG_KEY)
    if isinstance(d, dict):
        return copy.deepcopy(d)
    return {}


__all__ = [
    "MISSION_BACKING_HANDOFF_DIAG_KEY",
    "begin_mission_backing_handoff",
    "collect_mission_backing_handoff_diagnostics",
    "complete_mission_backing_handoff_after_navigation",
]

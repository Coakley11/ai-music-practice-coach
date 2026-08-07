"""Runtime diagnostics for Return-to-Creative — prefix [creative_return_trace]."""

from __future__ import annotations

import json
import logging
from typing import Any

_LOG = logging.getLogger("music.creative_return_trace")
TRACE_PREFIX = "[creative_return_trace]"
SESSION_TRACE_LOG_KEY = "_creative_return_trace_log"
SESSION_TRACE_LAST_KEY = "_creative_return_trace_last"
MAX_TRACE_ENTRIES = 48


def _run_seq(session: dict[str, Any]) -> int:
    try:
        return int(session.get("_script_run_seq") or 0)
    except (TypeError, ValueError):
        return 0


def _safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, sort_keys=True, default=str)
    except Exception:
        return repr(obj)


def snapshot_return_surface(session: dict[str, Any]) -> dict[str, Any]:
    """Live session fields relevant to Creative return (not widget Streamlit keys)."""
    try:
        from studio_page_state import CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY
    except ImportError:
        CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY = "creative_improv_intelligence_tab"
    try:
        from backing_creative_return_route import get_creative_return_route
    except ImportError:
        get_creative_return_route = None  # type: ignore[assignment,misc]
    try:
        from backing_context import BACKING_CONTEXT_KEY, get_backing_context

        ctx = get_backing_context(session)
        raw = session.get(BACKING_CONTEXT_KEY)
    except ImportError:
        ctx = None
        raw = session.get("backing_context")
    route = get_creative_return_route(session) if get_creative_return_route else None
    raw_route = raw.get("creative_return_route") if isinstance(raw, dict) else None
    creative_sess = session.get("creative_session")
    tool_type = ""
    if isinstance(creative_sess, dict):
        tool_type = str(creative_sess.get("tool_type") or "")
    return {
        "studio_page": str(session.get("studio_page") or ""),
        "improv_intelligence_tab": str(session.get("improv_intelligence_tab") or ""),
        "creative_improv_intelligence_tab": str(session.get(CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY) or ""),
        "improv_entry_mode": str(session.get("improv_entry_mode") or ""),
        "improv_active_mission": str(session.get("improv_active_mission") or ""),
        "improv_mission_pick": str(session.get("improv_mission_pick") or ""),
        "ii_selected_section": str(session.get("ii_selected_section") or session.get("II_SELECTED_SECTION") or ""),
        "ii_selected_chord": str(session.get("ii_selected_chord") or session.get("II_SELECTED_CHORD") or ""),
        "backing_source": str(getattr(ctx, "source", "") or ""),
        "backing_entry_mode": str(getattr(ctx, "entry_mode", "") or ""),
        "backing_source_signature": str(getattr(ctx, "source_signature", "") or ""),
        "backing_created_at": str(getattr(ctx, "created_at", "") or ""),
        "backing_updated_at": str(getattr(ctx, "updated_at", "") or ""),
        "creative_return_route_in_blob": raw_route,
        "creative_return_route_resolved": route,
        "creative_session_tool_type": tool_type,
        "creative_restore_from_backing": bool(session.get("_creative_restore_from_backing")),
        "_creative_restore_flag": bool(session.get("_creative_restore_from_backing")),
        "_backing_launch_workflow": str(session.get("_backing_launch_workflow") or ""),
        "_improv_tab_user_touched": bool(session.get("_improv_tab_user_touched")),
    }


def _append_session_log(session: dict[str, Any], record: dict[str, Any]) -> None:
    log = session.get(SESSION_TRACE_LOG_KEY)
    if not isinstance(log, list):
        log = []
    log.append(record)
    if len(log) > MAX_TRACE_ENTRIES:
        log = log[-MAX_TRACE_ENTRIES:]
    session[SESSION_TRACE_LOG_KEY] = log
    session[SESSION_TRACE_LAST_KEY] = record


def emit_creative_return_trace(
    session: dict[str, Any],
    phase: str,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One diagnostic record — logged and stored on session for sidebar/dev copy."""
    surface = snapshot_return_surface(session)
    record: dict[str, Any] = {
        "phase": str(phase or "").strip(),
        "run_seq": _run_seq(session),
        **surface,
    }
    if extra:
        record["extra"] = extra
    line = f"{TRACE_PREFIX} phase={record['phase']} run_seq={record['run_seq']} {_safe_json({k: v for k, v in record.items() if k not in ('phase', 'run_seq')})}"
    _LOG.info(line)
    _append_session_log(session, record)
    return record


def trace_backing_launch(
    session: dict[str, Any],
    *,
    launch_tab: str,
    launch_entry: str,
    sealed_route: dict[str, Any] | None,
    backing_source: str,
) -> None:
    emit_creative_return_trace(
        session,
        "AT_BACKING_LAUNCH",
        extra={
            "launch_tab_read": launch_tab,
            "launch_entry_read": launch_entry,
            "sealed_creative_return_route": sealed_route,
            "declared_backing_source": backing_source,
        },
    )


def trace_set_backing_context(
    session: dict[str, Any],
    *,
    caller: str,
    prev_route: Any,
    new_route: Any,
    ctx_source: str,
    ctx_signature: str,
) -> None:
    dropped = bool(prev_route) and not new_route
    replaced = (
        isinstance(prev_route, dict)
        and isinstance(new_route, dict)
        and prev_route != new_route
    )
    emit_creative_return_trace(
        session,
        "SET_BACKING_CONTEXT",
        extra={
            "caller": caller,
            "route_dropped": dropped,
            "route_replaced": replaced,
            "prev_route": prev_route,
            "new_route": new_route,
            "ctx_source": ctx_source,
            "ctx_source_signature": ctx_signature,
        },
    )


def trace_return_click_before(session: dict[str, Any]) -> None:
    emit_creative_return_trace(session, "ON_RETURN_BUTTON_CLICK_BEFORE")


def trace_return_route_read(
    session: dict[str, Any],
    *,
    route: dict[str, Any] | None,
    route_source: str,
    rebuilt_route: dict[str, Any] | None = None,
) -> None:
    emit_creative_return_trace(
        session,
        "ON_RETURN_ROUTE_READ",
        extra={
            "route_source": route_source,
            "route_applied": route,
            "rebuilt_route_if_any": rebuilt_route,
        },
    )


def trace_return_after_apply(
    session: dict[str, Any],
    *,
    requested: dict[str, Any],
    written: dict[str, Any],
) -> None:
    emit_creative_return_trace(
        session,
        "AFTER_APPLYING_RETURN_ROUTE",
        extra={
            "requested": requested,
            "written_to_session": written,
        },
    )


def trace_creative_run_start(session: dict[str, Any], *, label: str) -> None:
    emit_creative_return_trace(session, f"CREATIVE_SCRIPT_RUN_{label}")


def trace_hydration_step(
    session: dict[str, Any],
    step: str,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    emit_creative_return_trace(
        session,
        "CREATIVE_HYDRATION_STEP",
        extra={
            "step": step,
            "before": before or snapshot_return_surface(session),
            "after": after,
        },
    )


def trace_page_transition(session: dict[str, Any], *, from_page: str, to_page: str) -> None:
    emit_creative_return_trace(
        session,
        "STUDIO_PAGE_TRANSITION",
        extra={"from_page": from_page, "to_page": to_page},
    )


def should_show_trace_ui(session: dict[str, Any], st_module: Any | None = None) -> bool:
    if session.get("developer_mode"):
        return True
    if st_module is not None:
        try:
            if str(st_module.query_params.get("creative_return_trace") or "").strip() in ("1", "true", "yes"):
                return True
        except Exception:
            pass
    try:
        from music_deploy_verification import CREATIVE_OWNER_PREVIEW_BRANCH, matches_creative_owner_preview_deploy

        if matches_creative_owner_preview_deploy():
            return True
    except ImportError:
        pass
    return False


def render_creative_return_trace_panel(st_module: Any, session: dict[str, Any]) -> None:
    if not should_show_trace_ui(session, st_module):
        return
    last = session.get(SESSION_TRACE_LAST_KEY)
    log = session.get(SESSION_TRACE_LOG_KEY)
    count = len(log) if isinstance(log, list) else 0
    with st_module.sidebar.expander(f"{TRACE_PREFIX} ({count} events)", expanded=False):
        st_module.caption("Copy logs from Streamlit Cloud or expand last event below.")
        if isinstance(last, dict):
            st_module.json(last)
        if isinstance(log, list) and log:
            st_module.download_button(
                "Download trace JSON",
                data=_safe_json(log),
                file_name="creative_return_trace.json",
                mime="application/json",
                key="creative_return_trace_download",
            )


__all__ = [
    "SESSION_TRACE_LOG_KEY",
    "TRACE_PREFIX",
    "emit_creative_return_trace",
    "render_creative_return_trace_panel",
    "should_show_trace_ui",
    "snapshot_return_surface",
    "trace_backing_launch",
    "trace_creative_run_start",
    "trace_hydration_step",
    "trace_page_transition",
    "trace_return_after_apply",
    "trace_return_click_before",
    "trace_return_route_read",
    "trace_set_backing_context",
]

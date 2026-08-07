"""Post–Return-to-Creative page routing diagnostics — prefix [studio_page_route_trace]."""

from __future__ import annotations

import json
import logging
from typing import Any

_LOG = logging.getLogger("music.studio_page_route_trace")
TRACE_PREFIX = "[studio_page_route_trace]"
SESSION_LOG_KEY = "_studio_page_route_trace_log"
SESSION_LAST_KEY = "_studio_page_route_trace_last"
MAX_ENTRIES = 64


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


def snapshot_route_authorities(session: dict[str, Any], *, dispatch_local: str = "") -> dict[str, Any]:
    nav = session.get("studio_nav_state")
    nav_page = ""
    nav_reason = ""
    if isinstance(nav, dict):
        nav_page = str(nav.get("studio_page") or nav.get("page") or "").strip()
        nav_reason = str(nav.get("last_write_reason") or "").strip()
    ws = session.get("music_workspace_state")
    ws_page = ""
    if isinstance(ws, dict):
        ws_page = str(ws.get("studio_page") or ws.get("page") or "").strip()
    try:
        from studio_page_persistence import _ACTIVE_PAGE_TRACKER  # type: ignore[attr-defined]
    except ImportError:
        _ACTIVE_PAGE_TRACKER = "_studio_active_page_id"
    try:
        from music_rerun_loop_guard import RERUN_LOOP_BLOCKED_KEY
    except ImportError:
        RERUN_LOOP_BLOCKED_KEY = "_music_rerun_loop_blocked"
    try:
        from music_persistent_state import current_run_user_navigated_page

        scoped_user_nav = current_run_user_navigated_page(session)
    except ImportError:
        scoped_user_nav = ""
    return {
        "studio_page": str(session.get("studio_page") or "").strip(),
        "dispatch_local_studio_page": str(dispatch_local or "").strip(),
        "canonical_studio_nav_state": nav_page,
        "studio_nav_last_write_reason": nav_reason,
        "music_workspace_state_page": ws_page,
        "active_page_tracker": str(session.get(_ACTIVE_PAGE_TRACKER) or "").strip(),
        "navigate_to_studio_page_popped": str(session.get("_navigate_to_studio_page") or "").strip(),
        "nav_target_page": str(session.get("nav_target_page") or "").strip(),
        "user_nav_page_this_run": str(session.get("_music_user_navigated_page_this_run") or "").strip(),
        "user_nav_page_run_seq": session.get("_music_user_navigated_page_run_seq"),
        "user_nav_page_this_run_scoped": scoped_user_nav,
        "suite_page_user_nav": bool(session.get("_suite_page_user_nav")),
        "studio_nav_dirty": bool(session.get("studio_nav_state_dirty")),
        "creative_restore_from_backing": bool(session.get("_creative_restore_from_backing")),
        "rerun_loop_blocked": bool(session.get(RERUN_LOOP_BLOCKED_KEY)),
        "page_restore_overwrite_source": str(session.get("_suite_page_overwrite_source") or "").strip(),
    }


def emit_route_trace(
    session: dict[str, Any],
    phase: str,
    *,
    dispatch_local: str = "",
    render_target: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "phase": str(phase or "").strip(),
        "run_seq": _run_seq(session),
        **snapshot_route_authorities(session, dispatch_local=dispatch_local),
    }
    if render_target:
        record["render_target"] = str(render_target)
    if extra:
        record["extra"] = extra
    line = (
        f"{TRACE_PREFIX} phase={record['phase']} run_seq={record['run_seq']} "
        f"{_safe_json({k: v for k, v in record.items() if k not in ('phase', 'run_seq')})}"
    )
    _LOG.info(line)
    log = session.get(SESSION_LOG_KEY)
    if not isinstance(log, list):
        log = []
    log.append(record)
    if len(log) > MAX_ENTRIES:
        log = log[-MAX_ENTRIES:]
    session[SESSION_LOG_KEY] = log
    session[SESSION_LAST_KEY] = record
    return record


def trace_run_start_after_ensure(
    session: dict[str, Any],
    *,
    dispatch_local: str,
    ensure_result: str,
) -> None:
    emit_route_trace(
        session,
        "RUN_START_AFTER_ENSURE_STUDIO_PAGE",
        dispatch_local=dispatch_local,
        extra={"ensure_studio_page_result": ensure_result},
    )


def trace_after_page_transition(session: dict[str, Any], *, dispatch_local: str) -> None:
    emit_route_trace(
        session,
        "AFTER_HANDLE_STUDIO_PAGE_TRANSITION",
        dispatch_local=dispatch_local,
    )


def trace_post_quick_nav(session: dict[str, Any], *, before: str, after: str) -> None:
    mismatch = before != after
    emit_route_trace(
        session,
        "POST_QUICK_NAV_DISPATCH",
        dispatch_local=after,
        extra={"dispatch_before_quick_nav": before, "dispatch_changed": mismatch},
    )


def trace_page_dispatch_branch(
    session: dict[str, Any],
    *,
    dispatch_local: str,
    branch: str,
) -> None:
    live = str(session.get("studio_page") or "").strip()
    disagree = live and dispatch_local and live != dispatch_local
    emit_route_trace(
        session,
        "PAGE_DISPATCH_BRANCH",
        dispatch_local=dispatch_local,
        render_target=branch,
        extra={
            "session_vs_dispatch_disagree": disagree,
            "chosen_render_branch": branch,
        },
    )


def trace_before_render_backing(session: dict[str, Any], *, dispatch_local: str) -> None:
    trace_page_dispatch_branch(session, dispatch_local=dispatch_local, branch="backing")


def trace_before_render_creative(session: dict[str, Any], *, dispatch_local: str) -> None:
    trace_page_dispatch_branch(session, dispatch_local=dispatch_local, branch="creative")


def trace_return_before_rerun(session: dict[str, Any], *, dispatch_local: str = "backing") -> None:
    emit_route_trace(
        session,
        "RETURN_CLICK_BEFORE_RERUN",
        dispatch_local=dispatch_local,
    )


def trace_return_rerun_outcome(
    session: dict[str, Any],
    *,
    rerun_requested: bool,
    rerun_invoked: bool,
    fallback_rerun: bool = False,
) -> None:
    emit_route_trace(
        session,
        "RETURN_CLICK_RERUN_OUTCOME",
        extra={
            "rerun_requested": rerun_requested,
            "rerun_invoked": rerun_invoked,
            "fallback_st_rerun": fallback_rerun,
        },
    )


def trace_dispatch_resync(
    session: dict[str, Any],
    *,
    old_dispatch: str,
    new_dispatch: str,
    reason: str,
) -> None:
    emit_route_trace(
        session,
        "DISPATCH_RESYNC_FROM_SESSION",
        dispatch_local=new_dispatch,
        extra={
            "old_dispatch_local": old_dispatch,
            "new_dispatch_local": new_dispatch,
            "reason": reason,
        },
    )


def trace_post_return_stop_guard(session: dict[str, Any]) -> None:
    emit_route_trace(session, "RETURN_POST_RERUN_STOP_GUARD")


def should_show_route_trace_ui(session: dict[str, Any], st_module: Any | None = None) -> bool:
    """Same visibility gate as creative_return_trace (safety preview + ?dev=1)."""
    try:
        from creative_return_trace import should_show_trace_ui

        return bool(should_show_trace_ui(session, st_module))
    except ImportError:
        pass
    if session.get("developer_mode"):
        return True
    if st_module is not None:
        try:
            qp = str(st_module.query_params.get("studio_page_route_trace") or "").strip().lower()
            if qp in ("1", "true", "yes"):
                return True
        except Exception:
            pass
    try:
        from music_deploy_verification import matches_creative_owner_preview_deploy

        return bool(matches_creative_owner_preview_deploy())
    except ImportError:
        return False


def build_route_trace_journal_payload(session: dict[str, Any]) -> dict[str, Any]:
    log = session.get(SESSION_LOG_KEY)
    if not isinstance(log, list):
        log = []
    last = session.get(SESSION_LAST_KEY)
    return {
        "trace_prefix": TRACE_PREFIX,
        "event_count": len(log),
        "last_event": last if isinstance(last, dict) else None,
        "events": list(log),
        "authorities_now": snapshot_route_authorities(session),
    }


def _phase_summary_row(record: dict[str, Any]) -> str:
    phase = str(record.get("phase") or "")
    run_seq = record.get("run_seq")
    page = str(record.get("studio_page") or "")
    dispatch = str(record.get("dispatch_local_studio_page") or "")
    target = str(record.get("render_target") or "")
    parts = [f"run={run_seq}", f"phase={phase}"]
    if page:
        parts.append(f"session={page}")
    if dispatch:
        parts.append(f"dispatch={dispatch}")
    if target:
        parts.append(f"render={target}")
    return " · ".join(parts)


def render_studio_page_route_trace_panel(st_module: Any, session: dict[str, Any]) -> None:
    if not should_show_route_trace_ui(session, st_module):
        return
    log = session.get(SESSION_LOG_KEY)
    if not isinstance(log, list):
        log = []
    last = session.get(SESSION_LAST_KEY)
    count = len(log)
    expanded = True
    try:
        from music_deploy_verification import matches_creative_owner_preview_deploy

        expanded = bool(matches_creative_owner_preview_deploy()) or bool(session.get("developer_mode"))
    except ImportError:
        expanded = bool(session.get("developer_mode"))
    with st_module.sidebar.expander(f"{TRACE_PREFIX} ({count} events)", expanded=expanded):
        st_module.caption(
            "Page dispatch vs session after Return — click run + next run. "
            "Phases include PREPARE_STUDIO_NAV_EXIT, DISPATCH_RESYNC, render branch."
        )
        if not log:
            st_module.info("No route events yet. Open Backing, click Return to Creative, then refresh this panel.")
        else:
            st_module.markdown("**Recent phases (newest last)**")
            for row in log[-16:]:
                if isinstance(row, dict):
                    st_module.text(_phase_summary_row(row))
        if isinstance(last, dict):
            st_module.markdown("**Last event**")
            st_module.json(last)
        payload = build_route_trace_journal_payload(session)
        st_module.download_button(
            "Download route trace JSON",
            data=_safe_json(payload),
            file_name="studio_page_route_trace.json",
            mime="application/json",
            key="studio_page_route_trace_download",
        )


__all__ = [
    "SESSION_LAST_KEY",
    "SESSION_LOG_KEY",
    "TRACE_PREFIX",
    "build_route_trace_journal_payload",
    "emit_route_trace",
    "render_studio_page_route_trace_panel",
    "should_show_route_trace_ui",
    "snapshot_route_authorities",
    "trace_after_page_transition",
    "trace_before_render_backing",
    "trace_before_render_creative",
    "trace_dispatch_resync",
    "trace_page_dispatch_branch",
    "trace_post_quick_nav",
    "trace_post_return_stop_guard",
    "trace_return_before_rerun",
    "trace_return_rerun_outcome",
    "trace_run_start_after_ensure",
]

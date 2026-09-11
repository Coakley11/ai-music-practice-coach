"""Runtime diagnostics for Return-to-Creative — prefix [creative_return_trace]."""

from __future__ import annotations

import json
import logging
from typing import Any

_LOG = logging.getLogger("music.creative_return_trace")
TRACE_PREFIX = "[creative_return_trace]"
SESSION_TRACE_LOG_KEY = "_creative_return_trace_log"
SESSION_TRACE_LAST_KEY = "_creative_return_trace_last"
BACKING_CONTEXT_MUTATION_JOURNAL_KEY = "_backing_context_mutation_journal"
BACKING_CONTEXT_PRESERVE_FIX_ID = "launch_id_v1"
MAX_TRACE_ENTRIES = 48
MAX_MUTATION_JOURNAL_ENTRIES = 64


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
            "preserve_fix_id": BACKING_CONTEXT_PRESERVE_FIX_ID,
        },
    )


def _append_mutation_journal(session: dict[str, Any], record: dict[str, Any]) -> None:
    journal = session.get(BACKING_CONTEXT_MUTATION_JOURNAL_KEY)
    if not isinstance(journal, list):
        journal = []
    journal.append(record)
    if len(journal) > MAX_MUTATION_JOURNAL_ENTRIES:
        journal = journal[-MAX_MUTATION_JOURNAL_ENTRIES:]
    session[BACKING_CONTEXT_MUTATION_JOURNAL_KEY] = journal


def _blob_route_present(blob: Any) -> bool:
    if not isinstance(blob, dict):
        return False
    route = blob.get("creative_return_route")
    return isinstance(route, dict) and bool(route)


def _blob_signature(blob: Any) -> str:
    if not isinstance(blob, dict):
        return ""
    return str(blob.get("source_signature") or "").strip()


def record_backing_context_mutation(
    session: dict[str, Any],
    *,
    phase: str,
    write_path: str,
    uses_set_backing_context: bool,
    blob_key: str = "backing_context",
    caller: str = "",
    prev_blob: Any = None,
    new_blob: Any = None,
    prev_source_signature: str = "",
    new_source_signature: str = "",
    prev_route_present: bool | None = None,
    explicit_route_arg_present: bool | None = None,
    new_route_present: bool | None = None,
    preservation_reason: str = "",
    route_dropped: bool | None = None,
) -> None:
    """Forensic journal row for backing_context blob mutations (filter by source_signature)."""
    if prev_route_present is None:
        prev_route_present = _blob_route_present(prev_blob)
    if new_route_present is None:
        new_route_present = _blob_route_present(new_blob)
    if route_dropped is None:
        route_dropped = bool(prev_route_present) and not bool(new_route_present)
    if not prev_source_signature:
        prev_source_signature = _blob_signature(prev_blob)
    if not new_source_signature:
        new_source_signature = _blob_signature(new_blob)
    row = {
        "phase": str(phase or "").strip(),
        "run_seq": _run_seq(session),
        "caller": str(caller or write_path or "").strip(),
        "write_path": str(write_path or "").strip(),
        "uses_set_backing_context": bool(uses_set_backing_context),
        "blob_key": str(blob_key or "backing_context"),
        "prev_source_signature": prev_source_signature,
        "new_source_signature": new_source_signature,
        "prev_route_present": prev_route_present,
        "explicit_route_arg_present": explicit_route_arg_present,
        "new_route_present": new_route_present,
        "preservation_reason": str(preservation_reason or "").strip(),
        "route_dropped": route_dropped,
        "preserve_fix_id": BACKING_CONTEXT_PRESERVE_FIX_ID,
    }
    _append_mutation_journal(session, row)
    line = f"{TRACE_PREFIX} mutation phase={row['phase']} sig={new_source_signature or prev_source_signature} {_safe_json(row)}"
    _LOG.info(line)


def trace_direct_backing_context_write(
    session: dict[str, Any],
    *,
    source: str,
    prev_blob: Any,
    new_blob: Any,
) -> None:
    """Direct session[backing_context] assignment bypassing set_backing_context()."""
    record_backing_context_mutation(
        session,
        phase="DIRECT_BACKING_CONTEXT_WRITE",
        write_path=str(source or "direct"),
        uses_set_backing_context=False,
        caller=str(source or "direct"),
        prev_blob=prev_blob,
        new_blob=new_blob,
        explicit_route_arg_present=False,
        preservation_reason="bypass_set_backing_context",
    )
    emit_creative_return_trace(
        session,
        "DIRECT_BACKING_CONTEXT_WRITE",
        extra={
            "source": source,
            "prev_route_present": _blob_route_present(prev_blob),
            "new_route_present": _blob_route_present(new_blob),
            "prev_source_signature": _blob_signature(prev_blob),
            "new_source_signature": _blob_signature(new_blob),
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
    prev_blob: Any = None,
    new_blob: Any = None,
    preservation_reason: str = "",
    explicit_route_arg_present: bool = False,
    extra: dict[str, Any] | None = None,
) -> None:
    dropped = bool(prev_route) and not new_route
    replaced = (
        isinstance(prev_route, dict)
        and isinstance(new_route, dict)
        and prev_route != new_route
    )
    trace_extra: dict[str, Any] = {
        "caller": caller,
        "route_dropped": dropped,
        "route_replaced": replaced,
        "prev_route": prev_route,
        "new_route": new_route,
        "ctx_source": ctx_source,
        "ctx_source_signature": ctx_signature,
        "prev_source_signature": _blob_signature(prev_blob),
        "preservation_reason": preservation_reason,
        "explicit_route_arg_present": explicit_route_arg_present,
        "preserve_fix_id": BACKING_CONTEXT_PRESERVE_FIX_ID,
    }
    if isinstance(extra, dict):
        trace_extra.update(extra)
    record_backing_context_mutation(
        session,
        phase="SET_BACKING_CONTEXT",
        write_path="set_backing_context",
        uses_set_backing_context=True,
        caller=caller,
        prev_blob=prev_blob,
        new_blob=new_blob,
        prev_source_signature=str(trace_extra.get("prev_source_signature") or _blob_signature(prev_blob)),
        new_source_signature=str(trace_extra.get("new_source_signature") or ctx_signature or _blob_signature(new_blob)),
        prev_route_present=_blob_route_present(prev_blob) or bool(prev_route),
        explicit_route_arg_present=explicit_route_arg_present,
        new_route_present=isinstance(new_route, dict),
        preservation_reason=preservation_reason,
        route_dropped=dropped,
    )
    emit_creative_return_trace(
        session,
        "SET_BACKING_CONTEXT",
        extra=trace_extra,
    )


def trace_return_click_before(session: dict[str, Any]) -> None:
    emit_creative_return_trace(session, "ON_RETURN_BUTTON_CLICK_RECEIVED")


def trace_return_handoff_queued(session: dict[str, Any], req: dict[str, Any]) -> None:
    sealed = req.get("sealed_context") if isinstance(req.get("sealed_context"), dict) else {}
    emit_creative_return_trace(
        session,
        "ON_RETURN_HANDOFF_QUEUED",
        extra={
            "request_seq": req.get("request_seq"),
            "consume_token": req.get("consume_token"),
            "sealed_source": str(sealed.get("source") or ""),
            "sealed_entry_mode": str(sealed.get("entry_mode") or ""),
            "sealed_creative_tab": str(
                sealed.get("creative_tab")
                or sealed.get("improv_intelligence_tab")
                or sealed.get("creative_improv_intelligence_tab")
                or ""
            ),
            "sealed_song_pick": str(sealed.get("song_pick") or ""),
            "sealed_display_key": str(sealed.get("display_key") or ""),
            "sealed_concert_key": str(sealed.get("concert_key") or ""),
        },
    )


def trace_return_consume_phase(
    session: dict[str, Any],
    phase: str,
    *,
    sealed: dict[str, Any] | None = None,
) -> None:
    try:
        from music_persistent_state import (
            MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY,
            current_run_user_navigated_page,
        )

        user_nav_scoped = current_run_user_navigated_page(session)
        user_nav_raw = str(session.get(MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY) or "")
    except ImportError:
        user_nav_scoped = ""
        user_nav_raw = ""
    extra: dict[str, Any] = {
        "consume_phase": str(phase or ""),
        "studio_page_after_consume": str(session.get("studio_page") or ""),
        "user_nav_marker_this_run_scoped": user_nav_scoped,
        "user_nav_marker_raw": user_nav_raw,
    }
    if isinstance(sealed, dict):
        extra["sealed_creative_tab"] = str(
            sealed.get("creative_tab")
            or sealed.get("improv_intelligence_tab")
            or sealed.get("creative_improv_intelligence_tab")
            or ""
        )
        extra["sealed_source"] = str(sealed.get("source") or "")
        extra["sealed_entry_mode"] = str(sealed.get("entry_mode") or "")
    emit_creative_return_trace(session, "ON_RETURN_CONSUME_PHASE", extra=extra)


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


def snapshot_improv_selector_render_state(session: dict[str, Any]) -> dict[str, Any]:
    """Session + canonical selector fields at Creative II radio render boundary."""
    try:
        from studio_page_state import CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY
    except ImportError:
        CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY = "creative_improv_intelligence_tab"
    try:
        from creative_tab_tool_persistence import (
            CREATIVE_WORKSPACE_STATE_KEY,
            canonical_creative_selector_value,
            selector_hydration_complete,
        )
    except ImportError:
        CREATIVE_WORKSPACE_STATE_KEY = "creative_workspace_state"
        canonical_creative_selector_value = None  # type: ignore[assignment,misc]
        selector_hydration_complete = lambda _s: False  # type: ignore[assignment,misc]
    try:
        from creative_session_state import get_creative_session

        sess = get_creative_session(session)
        tool_type = str(getattr(sess, "tool_type", "") or "") if sess is not None else ""
    except ImportError:
        tool_type = ""
    cws = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    cws_entry = cws.get("improv_entry_mode") if isinstance(cws, dict) else None
    canon_entry = (
        canonical_creative_selector_value(session, "improv_entry_mode")
        if canonical_creative_selector_value
        else ""
    )
    return {
        "improv_entry_mode": str(session.get("improv_entry_mode") or ""),
        "improv_intelligence_tab": str(session.get("improv_intelligence_tab") or ""),
        "creative_improv_intelligence_tab": str(session.get(CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY) or ""),
        "creative_session_tool_type": tool_type,
        "creative_workspace_improv_entry_mode": cws_entry,
        "canonical_improv_entry_mode": str(canon_entry or ""),
        "_creative_restore_from_backing": bool(session.get("_creative_restore_from_backing")),
        "_creative_selector_hydration_complete": bool(selector_hydration_complete(session)),
    }


def trace_improv_selector_restore(
    session: dict[str, Any],
    phase: str,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    returned: str = "",
) -> None:
    extra: dict[str, Any] = {}
    if before is not None:
        extra["before"] = before
    if after is not None:
        extra["after"] = after
    if returned:
        extra["returned"] = returned
    emit_creative_return_trace(session, phase, extra=extra)


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
        journal = session.get(BACKING_CONTEXT_MUTATION_JOURNAL_KEY)
        if isinstance(journal, list) and journal:
            filter_sig = st_module.text_input(
                "Filter mutation journal by source_signature",
                value="",
                key="creative_return_trace_sig_filter",
            ).strip()
            rows = journal
            if filter_sig:
                rows = [
                    r
                    for r in journal
                    if isinstance(r, dict)
                    and (
                        str(r.get("new_source_signature") or "") == filter_sig
                        or str(r.get("prev_source_signature") or "") == filter_sig
                    )
                ]
            st_module.caption(f"Backing-context mutation journal ({len(rows)} rows)")
            if rows:
                st_module.json(rows[-12:])
            st_module.download_button(
                "Download mutation journal JSON",
                data=_safe_json(journal),
                file_name="backing_context_mutation_journal.json",
                mime="application/json",
                key="creative_return_mutation_download",
            )


__all__ = [
    "BACKING_CONTEXT_MUTATION_JOURNAL_KEY",
    "BACKING_CONTEXT_PRESERVE_FIX_ID",
    "SESSION_TRACE_LOG_KEY",
    "TRACE_PREFIX",
    "emit_creative_return_trace",
    "record_backing_context_mutation",
    "render_creative_return_trace_panel",
    "should_show_trace_ui",
    "snapshot_improv_selector_render_state",
    "snapshot_return_surface",
    "trace_backing_launch",
    "trace_creative_run_start",
    "trace_direct_backing_context_write",
    "trace_hydration_step",
    "trace_improv_selector_restore",
    "trace_page_transition",
    "trace_return_after_apply",
    "trace_return_click_before",
    "trace_return_consume_phase",
    "trace_return_handoff_queued",
    "trace_return_route_read",
    "trace_set_backing_context",
]

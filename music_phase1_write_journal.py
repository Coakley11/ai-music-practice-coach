"""Ordered runtime write journal for Phase 1 global controls + studio page (?dev=1)."""

from __future__ import annotations

import inspect
import json
import traceback
from pathlib import Path
from typing import Any

PHASE1_WRITE_JOURNAL_KEY = "_phase1_write_journal"
PHASE1_PREV_RUN_SUMMARY_KEY = "_phase1_prev_run_summary"

GLOBAL_JOURNAL_KEYS: frozenset[str] = frozenset(
    {
        "instrument",
        "level",
        "focus",
        "selected_transposing_instrument",
        "instrument_subtype",
    }
)

ACTIVE_SONG_GLOBAL_FIELDS: frozenset[str] = frozenset({"instrument", "level", "focus"})

PAGE_JOURNAL_KEYS: frozenset[str] = frozenset(
    {
        "studio_page",
        "studio_nav_state.page",
        "studio_nav_state.studio_page",
        "_music_hydrated_studio_page",
        "_suite_last_persisted_page",
        "navigation_widget",
    }
)

USER_ORIGINS: frozenset[str] = frozenset(
    {
        "user",
        "user_navigation",
        "sidebar_on_change",
        "widget_callback",
        "setter",
        "local_nav_preserve",
        "session_page_wins",
    }
)


def phase1_journal_enabled(session: dict[str, Any]) -> bool:
    if session.get("_phase1_write_journal_force"):
        return True
    if session.get("developer_mode"):
        return True
    try:
        from suite_workspace import is_developer_mode_enabled

        return bool(is_developer_mode_enabled())
    except ImportError:
        return False


def _caller_summary(*, depth: int = 3) -> str:
    parts: list[str] = []
    for frame in inspect.stack()[2 : 2 + depth]:
        path = Path(frame.filename)
        parts.append(f"{frame.function}({path.name}:{frame.lineno})")
    return " <- ".join(parts)


def _journal(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(PHASE1_WRITE_JOURNAL_KEY)
    if isinstance(raw, dict):
        return raw
    fresh: dict[str, Any] = {
        "run_seq": int(session.get("_script_run_seq") or 0),
        "global_writes": [],
        "page_writes": [],
        "user_widget_events": {},
        "user_selection_at_run_start": {},
        "widget_value_at_run_start": {},
        "violations": [],
        "write_seq": 0,
    }
    session[PHASE1_WRITE_JOURNAL_KEY] = fresh
    return fresh


def _context_snapshot(session: dict[str, Any]) -> dict[str, Any]:
    ctx: dict[str, Any] = {}
    try:
        from music_restore_phase import (
            global_controls_restore_projection_complete,
            music_restore_phase_complete,
            studio_page_restore_projection_complete,
        )

        ctx["restore_phase_complete"] = music_restore_phase_complete(session)
        ctx["global_restore_projection_complete"] = global_controls_restore_projection_complete(
            session
        )
        ctx["page_restore_projection_complete"] = studio_page_restore_projection_complete(session)
    except ImportError:
        pass
    try:
        from music_startup_save_suppression import (
            collect_startup_save_suppression_diagnostics,
            get_page_change_origin,
        )

        sup = collect_startup_save_suppression_diagnostics(session)
        ctx["startup_suppression"] = sup
        ctx["page_change_origin"] = get_page_change_origin(session)
    except ImportError:
        ctx["startup_suppression"] = None
        ctx["page_change_origin"] = None
    ctx["creative_projection_active"] = bool(session.get("_creative_workspace_restored_applied"))
    ctx["user_widget_event_present"] = bool(_journal(session).get("user_widget_events"))
    return ctx


def begin_phase1_write_journal_run(session: dict[str, Any]) -> None:
    if not phase1_journal_enabled(session):
        return
    run_seq = int(session.get("_script_run_seq") or 0)
    prior = session.get(PHASE1_WRITE_JOURNAL_KEY)
    if isinstance(prior, dict):
        session[PHASE1_PREV_RUN_SUMMARY_KEY] = summarize_run(prior, session)
    journal: dict[str, Any] = {
        "run_seq": run_seq,
        "global_writes": [],
        "page_writes": [],
        "user_widget_events": {},
        "user_selection_at_run_start": {},
        "widget_value_at_run_start": {},
        "violations": [],
        "write_seq": 0,
        "prev_run_summary": session.get(PHASE1_PREV_RUN_SUMMARY_KEY),
    }
    session[PHASE1_WRITE_JOURNAL_KEY] = journal

    prev = journal.get("prev_run_summary") or {}
    prev_globals = prev.get("final_globals") or {}
    for key in ("instrument", "level", "focus", "selected_transposing_instrument"):
        cur = session.get(key)
        journal["widget_value_at_run_start"][key] = _short_val(cur)
        if cur is not None and str(cur).strip() and str(cur) != str(prev_globals.get(key, "")):
            journal["user_selection_at_run_start"][key] = _short_val(cur)
            journal["user_widget_events"][key] = _short_val(cur)

    prev_page = str(prev.get("final_page") or "").strip()
    cur_page = str(session.get("studio_page") or "").strip()
    journal["widget_value_at_run_start"]["studio_page"] = cur_page or None
    if cur_page and cur_page != prev_page:
        journal["user_selection_at_run_start"]["studio_page"] = cur_page
        journal["user_widget_events"]["navigation_widget"] = cur_page

    try:
        from studio_nav_state import canonical_studio_page

        journal["canonical_page_at_run_start"] = canonical_studio_page(session)
    except ImportError:
        journal["canonical_page_at_run_start"] = None
    journal["hydrated_page_at_run_start"] = session.get("_music_hydrated_studio_page")


def note_phase1_user_widget_event(
    session: dict[str, Any],
    *,
    field: str,
    value: Any,
    source: str = "widget_callback",
) -> None:
    if not phase1_journal_enabled(session):
        return
    j = _journal(session)
    j["user_widget_events"][field] = _short_val(value)
    record_phase1_global_write(
        session,
        key=field,
        old_value=session.get(field),
        new_value=value,
        module="streamlit",
        function=source,
        reason=source,
        origin="user",
        target="widget_event",
    )


def record_phase1_global_write(
    session: dict[str, Any],
    *,
    key: str,
    old_value: Any,
    new_value: Any,
    module: str = "",
    function: str = "",
    reason: str = "",
    origin: str = "",
    target: str = "session",
    blocked: bool = False,
) -> None:
    if not phase1_journal_enabled(session):
        return
    norm_key = str(key or "").strip()
    allowed = (
        norm_key in GLOBAL_JOURNAL_KEYS
        or norm_key.startswith("active_song_state.")
        or norm_key.startswith("music_workspace_envelope.")
    )
    if not allowed:
        return
    if str(old_value) == str(new_value) and not blocked:
        return
    j = _journal(session)
    j["write_seq"] = int(j.get("write_seq") or 0) + 1
    entry: dict[str, Any] = {
        "write_seq": j["write_seq"],
        "run_seq": j.get("run_seq"),
        "key": norm_key,
        "target": target,
        "old_value": _short_val(old_value),
        "new_value": _short_val(new_value),
        "module": module or "?",
        "function": function or "?",
        "reason": reason or origin or "?",
        "origin": origin or reason or "?",
        "blocked": bool(blocked),
        "caller": _caller_summary(),
        **_context_snapshot(session),
    }
    j["global_writes"].append(entry)


def record_phase1_active_song_blob_globals(
    session: dict[str, Any],
    ctx: dict[str, Any],
    *,
    module: str,
    function: str,
    reason: str,
    origin: str = "canonical",
) -> None:
    if not phase1_journal_enabled(session):
        return
    meta = session.get("active_song_state")
    old_meta = dict(meta) if isinstance(meta, dict) else {}
    for field in ACTIVE_SONG_GLOBAL_FIELDS:
        new_val = ctx.get(field)
        if new_val is None:
            continue
        record_phase1_global_write(
            session,
            key=f"active_song_state.{field}",
            old_value=old_meta.get(field),
            new_value=new_val,
            module=module,
            function=function,
            reason=reason,
            origin=origin,
            target="active_song_state",
        )


def record_phase1_page_write(
    session: dict[str, Any],
    *,
    key: str,
    old_page: Any,
    new_page: Any,
    module: str = "",
    function: str = "",
    reason: str = "",
    origin: str = "",
    blocked: bool = False,
) -> None:
    if not phase1_journal_enabled(session):
        return
    if str(old_page) == str(new_page) and not blocked:
        return
    j = _journal(session)
    j["write_seq"] = int(j.get("write_seq") or 0) + 1
    try:
        from studio_nav_state import canonical_studio_page

        canonical = canonical_studio_page(session)
    except ImportError:
        canonical = None
    entry: dict[str, Any] = {
        "write_seq": j["write_seq"],
        "run_seq": j.get("run_seq"),
        "key": key,
        "old_page": _short_val(old_page),
        "new_page": _short_val(new_page),
        "module": module or "?",
        "function": function or "?",
        "reason": reason or "?",
        "origin": origin or reason or "?",
        "canonical_page": canonical,
        "hydrated_page": session.get("_music_hydrated_studio_page"),
        "blocked": bool(blocked),
        "caller": _caller_summary(),
        **_context_snapshot(session),
    }
    j["page_writes"].append(entry)


def record_phase1_session_key_write(
    session: dict[str, Any],
    key: str,
    value: Any,
    *,
    module: str,
    function: str,
    reason: str = "",
    origin: str = "",
) -> None:
    """Route session key writes to global or page journal."""
    old = session.get(key)
    if key in GLOBAL_JOURNAL_KEYS:
        record_phase1_global_write(
            session,
            key=key,
            old_value=old,
            new_value=value,
            module=module,
            function=function,
            reason=reason,
            origin=origin,
            target="session",
        )
    elif key == "studio_page" or key == "_music_hydrated_studio_page":
        record_phase1_page_write(
            session,
            key=key,
            old_page=old,
            new_page=value,
            module=module,
            function=function,
            reason=reason,
            origin=origin,
        )


def finalize_phase1_write_journal(session: dict[str, Any]) -> dict[str, Any]:
    if not phase1_journal_enabled(session):
        return {}
    j = _journal(session)
    summary = summarize_run(j, session)
    j["final_summary"] = summary

    _detect_global_overwrites(session, j)
    _detect_page_overwrite(session, j)

    session[PHASE1_PREV_RUN_SUMMARY_KEY] = summary
    return summary


def _detect_global_overwrites(session: dict[str, Any], journal: dict[str, Any]) -> None:
    user_targets = journal.get("user_selection_at_run_start") or {}
    if not user_targets:
        return
    try:
        from music_restore_phase import global_controls_restore_projection_complete

        if not global_controls_restore_projection_complete(session):
            return
    except ImportError:
        pass
    for field, expected in user_targets.items():
        if field not in ("instrument", "level", "focus", "selected_transposing_instrument"):
            continue
        expected_s = str(expected)
        last_user_seq = 0
        overwrite_entry = None
        for entry in journal.get("global_writes") or []:
            if entry.get("key") != field and entry.get("key") != f"active_song_state.{field}":
                continue
            origin = str(entry.get("origin") or "")
            if origin in USER_ORIGINS or "sidebar_on_change" in str(entry.get("reason") or ""):
                last_user_seq = int(entry.get("write_seq") or 0)
                continue
            if entry.get("blocked"):
                continue
            seq = int(entry.get("write_seq") or 0)
            if seq <= last_user_seq:
                continue
            new_v = str(entry.get("new_value") or "")
            if new_v and new_v != expected_s:
                overwrite_entry = entry
        final_v = _short_val(session.get(field))
        if overwrite_entry or (final_v and final_v != expected_s):
            viol = {
                "code": "PHASE1_GLOBAL_OVERWRITE",
                "field": field,
                "user_selected": expected_s,
                "final_value": final_v,
                "overwrite_writer": (
                    f"{overwrite_entry.get('module')}.{overwrite_entry.get('function')}"
                    if overwrite_entry
                    else "unknown"
                ),
                "overwrite_reason": overwrite_entry.get("reason") if overwrite_entry else None,
                "overwrite_seq": overwrite_entry.get("write_seq") if overwrite_entry else None,
            }
            journal.setdefault("violations", []).append(viol)
            _log_violation(session, viol)


def _detect_page_overwrite(session: dict[str, Any], journal: dict[str, Any]) -> None:
    hydrated = str(session.get("_music_hydrated_studio_page") or "").strip()
    final = str(session.get("studio_page") or "").strip()
    user_wanted = str((journal.get("user_selection_at_run_start") or {}).get("studio_page") or "").strip()
    if user_wanted == "creative" and final and final != "creative":
        hydrated = hydrated or user_wanted
    if hydrated == "creative" and final and final != "creative":
        overwrite_entry = None
        for entry in journal.get("page_writes") or []:
            if str(entry.get("new_page") or "") == final and str(entry.get("old_page") or "") == "creative":
                overwrite_entry = entry
            elif str(entry.get("new_page") or "") == final and entry.get("origin") not in USER_ORIGINS:
                overwrite_entry = entry
        viol = {
            "code": "PHASE1_PAGE_OVERWRITE",
            "hydrated_page": hydrated,
            "final_rendered_page": final,
            "overwrite_writer": (
                f"{overwrite_entry.get('module')}.{overwrite_entry.get('function')}"
                if overwrite_entry
                else "unknown"
            ),
            "overwrite_reason": overwrite_entry.get("reason") if overwrite_entry else None,
            "overwrite_seq": overwrite_entry.get("write_seq") if overwrite_entry else None,
        }
        journal.setdefault("violations", []).append(viol)
        _log_violation(session, viol)


def _log_violation(session: dict[str, Any], viol: dict[str, Any]) -> None:
    trace = session.setdefault("_phase1_violation_trace", [])
    if isinstance(trace, list):
        trace.append(viol)
        if len(trace) > 20:
            del trace[:-20]
    try:
        import streamlit as st

        st.session_state["_phase1_last_violation"] = viol
    except Exception:
        pass


def summarize_run(journal: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY, canonical_active_song_context
        from studio_nav_state import canonical_studio_page

        meta = canonical_active_song_context(session) or {}
        canon_page = canonical_studio_page(session)
    except ImportError:
        meta = session.get("active_song_state") if isinstance(session.get("active_song_state"), dict) else {}
        canon_page = None
    return {
        "run_seq": journal.get("run_seq"),
        "final_globals": {
            "instrument": _short_val(session.get("instrument")),
            "level": _short_val(session.get("level")),
            "focus": _short_val(session.get("focus")),
            "selected_transposing_instrument": _short_val(session.get("selected_transposing_instrument")),
        },
        "final_canonical_globals": {
            "instrument": _short_val(meta.get("instrument")),
            "level": _short_val(meta.get("level")),
            "focus": _short_val(meta.get("focus")),
        },
        "final_page": _short_val(session.get("studio_page")),
        "final_canonical_page": _short_val(canon_page),
        "hydrated_page": _short_val(session.get("_music_hydrated_studio_page")),
        "page_change_origin": journal.get("page_change_origin"),
        "last_page_write": (journal.get("page_writes") or [])[-1] if journal.get("page_writes") else None,
        "last_global_write": (journal.get("global_writes") or [])[-1] if journal.get("global_writes") else None,
    }


def _short_val(value: Any, *, max_len: int = 160) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        text = json.dumps(value, default=str)[:max_len]
    else:
        text = str(value)[:max_len]
    return text or None


def _page_change_cloud_confirmed_for_journal(session: dict[str, Any]) -> bool:
    try:
        from music_page_cloud_durability_trace import authoritative_page_change_cloud_confirmed

        if session.get("_music_page_change_authoritative_confirmation") is not None:
            return authoritative_page_change_cloud_confirmed(session)
    except ImportError:
        pass
    return bool(session.get("_suite_persist_last_save_cloud"))


def format_journal_copy_block(session: dict[str, Any]) -> str:
    j = session.get(PHASE1_WRITE_JOURNAL_KEY)
    if not isinstance(j, dict):
        payload = {
            "error": "no journal — enable ?dev=1",
            "page_cloud_durability_trace_json": _durability_trace_json_for_journal(session),
        }
        return json.dumps(payload, indent=2, default=str)
    payload = {
        "run_seq": j.get("run_seq"),
        "user_widget_events": j.get("user_widget_events"),
        "user_selection_at_run_start": j.get("user_selection_at_run_start"),
        "widget_value_at_run_start": j.get("widget_value_at_run_start"),
        "global_writes": j.get("global_writes"),
        "page_writes": j.get("page_writes"),
        "violations": j.get("violations"),
        "final_summary": j.get("final_summary"),
        "prev_run_summary": j.get("prev_run_summary"),
        "save_trace": session.get("_music_save_payload_stamp_trace"),
        "page_change_cloud_confirmed": _page_change_cloud_confirmed_for_journal(session),
        "page_change_cloud_confirmed_legacy": session.get("_suite_persist_last_save_cloud"),
        "authoritative_page_change_cloud_confirmed": _page_change_cloud_confirmed_for_journal(session),
        "last_cloud_payload_page": _page_from_cloud_payload(session.get("_suite_last_cloud_fetch_payload")),
    }
    try:
        from music_page_save_pipeline_trace import build_pipeline_trace_copy_block

        payload["page_save_pipeline_trace_json"] = json.loads(build_pipeline_trace_copy_block(session))
    except Exception:
        payload["page_save_pipeline_trace_json"] = {"status": "pipeline_trace_unavailable"}
    payload["page_cloud_durability_trace_json"] = _durability_trace_json_for_journal(session)
    return json.dumps(payload, indent=2, default=str)


def _durability_trace_json_for_journal(session: dict[str, Any]) -> dict[str, Any]:
    try:
        from music_page_cloud_durability_trace import durability_journal_payload

        return durability_journal_payload(session)
    except Exception as exc:
        return {
            "ui_marker": "PAGE_CLOUD_DURABILITY_TRACE_IMPL: 3ff4251-v1",
            "status": "durability_module_import_failed",
            "error": str(exc),
        }


def _page_from_cloud_payload(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    try:
        from studio_nav_state import _studio_page_from_blob

        page = _studio_page_from_blob(payload)
        return page or None
    except ImportError:
        return None


def render_phase1_write_journal_expander(st: Any, session: dict[str, Any]) -> None:
    if not phase1_journal_enabled(session):
        return
    summary = finalize_phase1_write_journal(session)
    j = session.get(PHASE1_WRITE_JOURNAL_KEY) or {}
    with st.sidebar.expander("Phase 1 runtime write journal", expanded=True):
        try:
            from music_page_cloud_durability_trace import (
                PAGE_CLOUD_DURABILITY_UI_MARKER,
                render_page_cloud_durability_trace_section,
            )

            st.markdown(f"`{PAGE_CLOUD_DURABILITY_UI_MARKER}`")
        except Exception as exc:
            st.markdown("`PAGE_CLOUD_DURABILITY_TRACE_IMPL: 3ff4251-v1 (import failed)`")
            st.caption(str(exc))
        if j.get("violations"):
            for viol in j["violations"]:
                st.error(
                    f"{viol.get('code')}: {viol.get('field') or viol.get('hydrated_page')} "
                    f"→ {viol.get('overwrite_writer')} ({viol.get('overwrite_reason')})"
                )
        page_viol = session.get("_phase1_last_page_payload_violation")
        if isinstance(page_viol, dict):
            st.error(
                f"{page_viol.get('code')}: clicked={page_viol.get('clicked_page')} "
                f"target={page_viol.get('target')} stale={page_viol.get('stale_fields')}"
            )
        st.markdown("**Final owner / value summary**")
        st.json(summary or j.get("final_summary") or {})
        st.markdown("**Global control writes this rerun**")
        st.json(j.get("global_writes") or [])
        st.markdown("**Page writes this rerun**")
        st.json(j.get("page_writes") or [])
        try:
            from music_page_save_history import PAGE_SAVE_HISTORY_KEY

            st.markdown("**Page-bearing save history**")
            st.json(session.get(PAGE_SAVE_HISTORY_KEY) or [])
        except ImportError:
            pass
        try:
            from music_page_save_pipeline_trace import build_pipeline_trace_copy_block, infer_failure_class

            st.markdown("**Page save pipeline trace**")
            infer_failure_class(session)
            hints = (session.get("_music_page_save_pipeline_trace") or {}).get("failure_class_hints") or []
            if hints:
                st.warning("Likely failure classes: " + ", ".join(hints))
            st.code(build_pipeline_trace_copy_block(session), language="json")
        except ImportError:
            pass
        try:
            from music_page_cloud_durability_trace import render_page_cloud_durability_trace_section

            render_page_cloud_durability_trace_section(st, session)
        except Exception as exc:
            st.markdown("**Page cloud durability trace**")
            st.error(f"Durability trace render failed: {exc}")
            st.json({"status": "durability_trace_render_failed", "error": str(exc)})
        st.markdown("**Copyable journal**")
        st.code(format_journal_copy_block(session), language="json")


__all__ = [
    "begin_phase1_write_journal_run",
    "finalize_phase1_write_journal",
    "format_journal_copy_block",
    "note_phase1_user_widget_event",
    "phase1_journal_enabled",
    "record_phase1_active_song_blob_globals",
    "record_phase1_global_write",
    "record_phase1_page_write",
    "record_phase1_session_key_write",
    "render_phase1_write_journal_expander",
]

"""Streamlit script-run lifecycle trace (availability / RUN_COMPLETED diagnostics)."""

from __future__ import annotations

import time
from typing import Any

from music_run_log import emit_music_run, run_summary_fields

LIFECYCLE_KEY = "_music_run_lifecycle"
PHASE_STACK_KEY = "_music_run_phase_stack"


def _lifecycle(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(LIFECYCLE_KEY)
    if not isinstance(raw, dict):
        raw = {}
        session[LIFECYCLE_KEY] = raw
    return raw


def _run_seq(session: dict[str, Any]) -> int:
    try:
        return int(session.get("_script_run_seq") or 0)
    except (TypeError, ValueError):
        return 0


def _snapshot_context(session: dict[str, Any], st: Any | None = None) -> dict[str, Any]:
    qp: dict[str, str] = {}
    if st is not None:
        try:
            for k in st.query_params:
                v = st.query_params.get(k)
                if isinstance(v, list):
                    v = v[0] if v else ""
                qp[str(k)] = str(v or "")[:80]
        except Exception:
            pass
    try:
        from music_workspace_hydration import collect_workspace_hydration_diagnostics

        hydration = collect_workspace_hydration_diagnostics(session)
    except ImportError:
        hydration = {}
    return {
        "run_seq": _run_seq(session),
        "studio_page": str(session.get("studio_page") or ""),
        "workflow_owner": str(
            session.get("music_workflow_owner")
            or session.get("_music_workflow_owner")
            or ""
        ),
        "query_params": qp,
        "hydration": hydration,
        "pending_upload_lock": bool(session.get("_pending_upload_route_lock")),
        "pending_hydrated_take": session.get("_pending_upload_hydrated_take_id"),
        "pending_applied_take": session.get("_pending_upload_route_applied_take_id"),
        "chart_recovery_attempts": session.get("_chart_bundle_recovery_attempts"),
        "strict_save_pending": session.get("_music_strict_save_pending"),
    }


def begin_script_run_lifecycle(session: dict[str, Any], *, st: Any | None = None) -> None:
    lc = _lifecycle(session)
    lc["started_at"] = time.time()
    lc["run_seq_started"] = _run_seq(session)
    lc.pop("completed_at", None)
    lc.pop("elapsed_ms", None)
    lc["started_context"] = _snapshot_context(session, st=st)
    session[PHASE_STACK_KEY] = []


def enter_run_phase(session: dict[str, Any], phase: str) -> None:
    stack = session.get(PHASE_STACK_KEY)
    if not isinstance(stack, list):
        stack = []
    entry = {"phase": phase, "run_seq": _run_seq(session), "entered_at": time.time()}
    stack.append(entry)
    session[PHASE_STACK_KEY] = stack[-24:]
    _lifecycle(session)["last_phase_entered"] = phase
    _lifecycle(session)["last_phase_entered_run"] = _run_seq(session)
    emit_music_run("PHASE_ENTER", session, phase=phase, **run_summary_fields(session))


def exit_run_phase(session: dict[str, Any], phase: str) -> None:
    stack = session.get(PHASE_STACK_KEY)
    if isinstance(stack, list) and stack:
        top = stack[-1]
        if isinstance(top, dict) and top.get("phase") == phase:
            top["exited_at"] = time.time()
            top["run_seq_exit"] = _run_seq(session)
            _lifecycle(session)["last_phase_exited"] = phase
    _lifecycle(session)["last_phase_completed"] = phase
    emit_music_run("PHASE_EXIT", session, phase=phase, **run_summary_fields(session))


def note_rerun_requested(
    session: dict[str, Any],
    *,
    reason: str,
    fingerprint: str = "",
    repeat_count: int | None = None,
    state_delta: dict[str, Any] | None = None,
) -> None:
    entry = {
        "run_seq": _run_seq(session),
        "reason": reason,
        "fingerprint": fingerprint,
        "repeat_count": repeat_count,
        "state_delta": state_delta or {},
        "at": time.time(),
    }
    lc = _lifecycle(session)
    lc["last_rerun_request"] = entry
    hist = lc.setdefault("rerun_requests", [])
    if isinstance(hist, list):
        hist.append(entry)
        lc["rerun_requests"] = hist[-40:]


def note_stop_requested(
    session: dict[str, Any],
    *,
    reason: str,
    expect_interactive: bool = True,
    resumable: bool = False,
) -> None:
    lc = _lifecycle(session)
    lc["last_stop"] = {
        "run_seq": _run_seq(session),
        "reason": reason,
        "expect_interactive": expect_interactive,
        "resumable": resumable,
        "at": time.time(),
        "phase_entered": lc.get("last_phase_entered"),
    }


def complete_script_run_lifecycle(session: dict[str, Any], *, st: Any | None = None) -> None:
    lc = _lifecycle(session)
    started = float(lc.get("started_at") or time.time())
    lc["completed_at"] = time.time()
    lc["elapsed_ms"] = int((lc["completed_at"] - started) * 1000)
    lc["run_seq_completed"] = _run_seq(session)
    lc["completed_context"] = {
        "route_lock": bool(session.get("_pending_upload_route_lock")),
        "pending_hydrated_take": session.get("_pending_upload_hydrated_take_id"),
        "workflow_owner": str(session.get("music_workflow_owner") or ""),
        "rerun_blocked": bool(session.get("_music_rerun_loop_blocked")),
    }
    try:
        from music_run_boundary import log_run_completed

        log_run_completed(session)
    except ImportError:
        emit_music_run(
            "RUN_COMPLETED",
            session,
            elapsed_ms=lc["elapsed_ms"],
            **run_summary_fields(session),
        )


def render_run_lifecycle_dev_caption(st_module: Any, session: dict[str, Any]) -> None:
    try:
        dev = bool(st_module.query_params.get("dev"))
    except Exception:
        dev = bool(session.get("developer_mode"))
    if not dev:
        return
    lc = _lifecycle(session)
    last_rr = lc.get("last_rerun_request") or {}
    st_module.sidebar.caption(
        "Run lifecycle · "
        f"seq `{_run_seq(session)}` · "
        f"status `{lc.get('status', lc.get('terminal_outcome', 'RUNNING'))}` · "
        f"phase `{lc.get('last_phase_entered', '—')}` · "
        f"rerun `{last_rr.get('reason', '—')}` · "
        f"fp `{last_rr.get('fingerprint', '—')}` · "
        f"rep `{last_rr.get('repeat_count', '—')}` · "
        f"stop `{ (lc.get('last_stop') or {}).get('reason', '—')}`"
    )


__all__ = [
    "LIFECYCLE_KEY",
    "begin_script_run_lifecycle",
    "complete_script_run_lifecycle",
    "enter_run_phase",
    "exit_run_phase",
    "note_rerun_requested",
    "note_stop_requested",
    "render_run_lifecycle_dev_caption",
]

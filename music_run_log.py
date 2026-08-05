"""Unconditional process logging for Streamlit script runs (Cloud-visible)."""

from __future__ import annotations

import sys
from typing import Any

PENDING_RERUN_REASON_KEY = "_music_run_pending_rerun_reason"
PENDING_RERUN_FP_KEY = "_music_run_pending_rerun_fingerprint"
PENDING_STOP_REASON_KEY = "_music_run_pending_stop_reason"
TERMINAL_LOGGED_KEY = "_music_run_terminal_logged"


def _run_seq(session: dict[str, Any] | None) -> int:
    if not session:
        return 0
    try:
        return int(session.get("_script_run_seq") or 0)
    except (TypeError, ValueError):
        return 0


def _format_line(event: str, fields: dict[str, Any]) -> str:
    parts = [f"event={event}"]
    for key in sorted(fields.keys()):
        val = fields[key]
        if val is None:
            continue
        text = str(val).replace("\n", " ").replace("\r", " ")
        if len(text) > 240:
            text = text[:237] + "..."
        parts.append(f"{key}={text}")
    return "[music_run] " + " ".join(parts)


def emit_music_run(event: str, session: dict[str, Any] | None = None, **fields: Any) -> None:
    """Print to stdout and stderr with immediate flush (always, no dev gate)."""
    if session is not None and "run_seq" not in fields:
        fields = {"run_seq": _run_seq(session), **fields}
    line = _format_line(event, fields)
    try:
        print(line, flush=True)
        print(line, flush=True, file=sys.stderr)
    except Exception:
        pass


def run_summary_fields(session: dict[str, Any]) -> dict[str, Any]:
    lc = session.get("_music_run_lifecycle")
    lc = lc if isinstance(lc, dict) else {}
    last_rr = lc.get("last_rerun_request") if isinstance(lc.get("last_rerun_request"), dict) else {}
    return {
        "page": str(session.get("studio_page") or ""),
        "phase_entered": lc.get("last_phase_entered"),
        "phase_exited": lc.get("last_phase_exited"),
        "route_lock": bool(session.get("_pending_upload_route_lock")),
        "pending_hydrated_take": session.get("_pending_upload_hydrated_take_id"),
        "workflow_owner": str(session.get("music_workflow_owner") or session.get("_music_workflow_owner") or ""),
        "rerun_fingerprint": last_rr.get("fingerprint"),
        "rerun_repeat": last_rr.get("repeat_count"),
        "strict_save_pending": bool(session.get("_music_strict_save_pending")),
    }


__all__ = [
    "PENDING_RERUN_FP_KEY",
    "PENDING_RERUN_REASON_KEY",
    "PENDING_STOP_REASON_KEY",
    "TERMINAL_LOGGED_KEY",
    "emit_music_run",
    "run_summary_fields",
]

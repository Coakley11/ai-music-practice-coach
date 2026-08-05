"""Startup availability watchdog — bounded transitions, lock release, recovery notice."""

from __future__ import annotations

from typing import Any

WATCHDOG_KEY = "_music_availability_watchdog"
STARTUP_MAX_ELAPSED_SEC = 45.0


def _watchdog(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(WATCHDOG_KEY)
    if not isinstance(raw, dict):
        raw = {}
        session[WATCHDOG_KEY] = raw
    return raw


def check_startup_watchdog(session: dict[str, Any], *, st: Any | None = None) -> dict[str, Any]:
    """
    After bounded hydration/chart reruns, release transient locks and allow interaction.
    Does not clear durable pending upload envelope.
    """
    import time

    wd = _watchdog(session)
    lc = session.get("_music_run_lifecycle")
    started = float(lc.get("started_at") or 0) if isinstance(lc, dict) else 0.0
    elapsed = (time.time() - started) if started else 0.0
    blocked = bool(session.get("_music_rerun_loop_blocked"))
    out = {"elapsed_sec": round(elapsed, 2), "blocked": blocked, "action": "none"}

    if blocked or elapsed > STARTUP_MAX_ELAPSED_SEC:
        try:
            from pending_upload_route_precedence import (
                PENDING_UPLOAD_ROUTE_LOCK_KEY,
                finalize_pending_upload_session_route_lock,
            )

            finalize_pending_upload_session_route_lock(session)
            if session.get(PENDING_UPLOAD_ROUTE_LOCK_KEY) and blocked:
                session.pop(PENDING_UPLOAD_ROUTE_LOCK_KEY, None)
                out["released_session_route_lock"] = True
        except ImportError:
            pass
        try:
            from music_rerun_loop_guard import clear_rerun_loop_block

            clear_rerun_loop_block(session, reason="watchdog_terminal")
        except ImportError:
            pass
        session.pop("_music_hydration_ui_wait_attempts", None)
        wd["terminal_recovery"] = True
        wd["terminal_reason"] = "rerun_loop_blocked" if blocked else "startup_elapsed_cap"
        out["action"] = "terminal_recovery"
        try:
            from music_run_log import emit_music_run, run_summary_fields

            emit_music_run(
                "WATCHDOG_RECOVERY",
                session,
                reason=wd.get("terminal_reason"),
                **run_summary_fields(session),
            )
        except ImportError:
            pass
        if st is not None and (blocked or elapsed > STARTUP_MAX_ELAPSED_SEC):
            try:
                st.warning(
                    "Startup restore hit a safety limit. Your saved data is intact — "
                    "you can navigate normally; refresh once if a page looks incomplete."
                )
            except Exception:
                pass
    return out


__all__ = ["STARTUP_MAX_ELAPSED_SEC", "WATCHDOG_KEY", "check_startup_watchdog"]

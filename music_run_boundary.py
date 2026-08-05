"""Top-level run boundary: hooks rerun/stop and records terminal outcomes."""

from __future__ import annotations

import sys
import time
from typing import Any

from music_run_log import (
    PENDING_RERUN_FP_KEY,
    PENDING_RERUN_REASON_KEY,
    PENDING_STOP_REASON_KEY,
    TERMINAL_LOGGED_KEY,
    emit_music_run,
    run_summary_fields,
)

_HOOKS_INSTALLED = False
_ST_MODULE: Any = None
_ORIG_RERUN: Any = None
_ORIG_STOP: Any = None


def _lifecycle(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get("_music_run_lifecycle")
    if not isinstance(raw, dict):
        raw = {}
        session["_music_run_lifecycle"] = raw
    return raw


def _elapsed_ms(session: dict[str, Any]) -> int:
    lc = _lifecycle(session)
    started = float(lc.get("started_at") or 0)
    if started <= 0:
        return 0
    return int((time.time() - started) * 1000)


def _session() -> dict[str, Any]:
    if _ST_MODULE is None:
        return {}
    ss = _ST_MODULE.session_state
    return ss if isinstance(ss, dict) else {}


def record_run_terminal(session: dict[str, Any], outcome: str, **extra: Any) -> None:
    if session.get(TERMINAL_LOGGED_KEY):
        return
    session[TERMINAL_LOGGED_KEY] = True
    lc = _lifecycle(session)
    lc["terminal_outcome"] = outcome
    fields = {
        **run_summary_fields(session),
        "outcome": outcome,
        "elapsed_ms": _elapsed_ms(session),
        **extra,
    }
    emit_music_run("RUN_END", session, **fields)


def log_run_completed(session: dict[str, Any]) -> None:
    if session.get(TERMINAL_LOGGED_KEY):
        return
    session[TERMINAL_LOGGED_KEY] = True
    lc = _lifecycle(session)
    lc["status"] = "RUN_COMPLETED"
    lc["terminal_outcome"] = "completed"
    emit_music_run(
        "RUN_COMPLETED",
        session,
        elapsed_ms=_elapsed_ms(session),
        **run_summary_fields(session),
    )


def _patched_rerun(*args: Any, **kwargs: Any) -> None:
    session = _session()
    reason = str(session.pop(PENDING_RERUN_REASON_KEY, None) or "direct_st_rerun")
    fp = str(session.pop(PENDING_RERUN_FP_KEY, None) or "")
    repeat = session.get("_music_rerun_loop_repeat_count")
    emit_music_run(
        "BEFORE_RERUN",
        session,
        reason=reason,
        fingerprint=fp,
        repeat_count=repeat,
        **run_summary_fields(session),
    )
    record_run_terminal(session, "rerun_requested", reason=reason, fingerprint=fp)
    assert _ORIG_RERUN is not None
    _ORIG_RERUN(*args, **kwargs)


def _patched_stop(*args: Any, **kwargs: Any) -> None:
    session = _session()
    reason = str(session.pop(PENDING_STOP_REASON_KEY, None) or "direct_st_stop")
    emit_music_run(
        "BEFORE_STOP",
        session,
        reason=reason,
        expect_interactive=True,
        **run_summary_fields(session),
    )
    record_run_terminal(session, "stopped", reason=reason)
    assert _ORIG_STOP is not None
    _ORIG_STOP(*args, **kwargs)


def _music_run_excepthook(exc_type: type[BaseException], exc: BaseException, tb: Any) -> None:
    try:
        session = _session()
        if session:
            from streamlit.runtime.scriptrunner_utils.exceptions import RerunException, StopException

            if exc_type not in (RerunException, StopException) and not session.get(TERMINAL_LOGGED_KEY):
                emit_music_run(
                    "RUN_EXCEPTION",
                    session,
                    exc_type=exc_type.__name__,
                    exc=str(exc)[:200],
                    **run_summary_fields(session),
                )
                record_run_terminal(session, "exception", exc_type=exc_type.__name__)
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc, tb)


def install_music_run_instrumentation(st_module: Any) -> None:
    """Call immediately after page config and run_seq increment."""
    global _HOOKS_INSTALLED, _ORIG_RERUN, _ORIG_STOP, _ST_MODULE
    _ST_MODULE = st_module
    session = st_module.session_state
    session[TERMINAL_LOGGED_KEY] = False

    try:
        from music_run_lifecycle import begin_script_run_lifecycle

        begin_script_run_lifecycle(session, st=st_module)
    except ImportError:
        pass

    emit_music_run("RUN_STARTED", session, **run_summary_fields(session))

    if not _HOOKS_INSTALLED:
        _ORIG_RERUN = st_module.rerun
        _ORIG_STOP = st_module.stop
        st_module.rerun = _patched_rerun  # type: ignore[method-assign]
        st_module.stop = _patched_stop  # type: ignore[method-assign]
        sys.excepthook = _music_run_excepthook
        _HOOKS_INSTALLED = True


def schedule_rerun_log(session: dict[str, Any], *, reason: str, fingerprint: str = "") -> None:
    session[PENDING_RERUN_REASON_KEY] = reason
    session[PENDING_RERUN_FP_KEY] = fingerprint


def schedule_stop_log(session: dict[str, Any], *, reason: str) -> None:
    session[PENDING_STOP_REASON_KEY] = reason


__all__ = [
    "install_music_run_instrumentation",
    "log_run_completed",
    "record_run_terminal",
    "schedule_rerun_log",
    "schedule_stop_log",
]

"""Central guarded rerun requests for availability-sensitive startup paths."""

from __future__ import annotations

from typing import Any


def request_app_rerun(
    st_module: Any,
    session: dict[str, Any],
    *,
    reason: str,
    stage: str = "",
) -> bool:
    """Log + scoped loop guard + rerun. Returns True if rerun was invoked."""
    try:
        from music_rerun_loop_guard import build_route_restore_fingerprint, safe_rerun

        fp = build_route_restore_fingerprint(session, reason=reason, stage=stage)
        repeat = int(session.get("_music_rerun_loop_repeat_count") or 0)
    except ImportError:
        try:
            from music_run_boundary import schedule_rerun_log

            schedule_rerun_log(session, reason=reason, fingerprint="")
        except ImportError:
            pass
        st_module.rerun()
        return True

    try:
        from music_run_lifecycle import note_rerun_requested

        note_rerun_requested(session, reason=reason, fingerprint=fp, repeat_count=repeat)
    except ImportError:
        pass

    try:
        from music_run_boundary import schedule_rerun_log

        schedule_rerun_log(session, reason=reason, fingerprint=fp)
    except ImportError:
        pass

    return safe_rerun(st_module, session, reason=reason, fingerprint=fp)


def request_app_stop(
    st_module: Any,
    session: dict[str, Any],
    *,
    reason: str,
    expect_interactive: bool = True,
    resumable: bool = False,
) -> None:
    try:
        from music_run_lifecycle import note_stop_requested

        note_stop_requested(
            session,
            reason=reason,
            expect_interactive=expect_interactive,
            resumable=resumable,
        )
    except ImportError:
        pass
    try:
        from music_run_boundary import schedule_stop_log

        schedule_stop_log(session, reason=reason)
    except ImportError:
        pass
    st_module.stop()


__all__ = ["request_app_rerun", "request_app_stop"]

"""Streamlit wake-up for deferred strict-egress cloud saves."""

from __future__ import annotations

from typing import Any

try:
    from music_egress_strict_save import _record_strict_pending_diag
except ImportError:
    _record_strict_pending_diag = None  # type: ignore[assignment,misc]

_FRAGMENT_KEY = "_music_strict_save_flusher_mounted"
_FRAGMENT_TICKS_KEY = "_music_strict_save_flusher_ticks"
_FRAGMENT_TICKS_MAX = 45


def mount_strict_save_wakeup_flusher(st: Any, *, build_state: Any) -> None:
    """
    While a debounced strict save is pending, run a bounded 1s fragment timer so the
    flush completes without another user interaction.
    """
    try:
        from music_egress_strict_save import (
            collect_strict_pending_diagnostics,
            music_egress_strict_enabled,
            strict_save_pending,
            strict_save_wakeup_tick,
        )
    except ImportError:
        return

    if not music_egress_strict_enabled():
        return
    ss = st.session_state
    if not strict_save_pending(ss):
        ss.pop(_FRAGMENT_KEY, None)
        ss.pop(_FRAGMENT_TICKS_KEY, None)
        return

    ticks = int(ss.get(_FRAGMENT_TICKS_KEY) or 0)
    if ticks >= _FRAGMENT_TICKS_MAX:
        try:
            from music_egress_strict_save import flush_strict_pending_save_if_due

            flush_strict_pending_save_if_due(st, build_state=build_state)
        except ImportError:
            pass
        ss.pop(_FRAGMENT_KEY, None)
        ss[_FRAGMENT_TICKS_KEY] = ticks
        return

    if _record_strict_pending_diag is not None:
        _record_strict_pending_diag(ss, **collect_strict_pending_diagnostics(ss))

    if not ss.get(_FRAGMENT_KEY):
        ss[_FRAGMENT_KEY] = True

    try:
        from music_workspace_cloud_save import record_save_transaction

        record_save_transaction(ss, **collect_strict_pending_diagnostics(ss))
    except ImportError:
        pass

    @st.fragment(run_every=1)
    def _music_strict_save_wakeup_fragment() -> None:
        ss[_FRAGMENT_TICKS_KEY] = int(ss.get(_FRAGMENT_TICKS_KEY) or 0) + 1
        strict_save_wakeup_tick(st, build_state=build_state)
        if not strict_save_pending(ss) or int(ss.get(_FRAGMENT_TICKS_KEY) or 0) >= _FRAGMENT_TICKS_MAX:
            ss.pop(_FRAGMENT_KEY, None)

    _music_strict_save_wakeup_fragment()


__all__ = ["_FRAGMENT_TICKS_MAX", "mount_strict_save_wakeup_flusher"]

"""Streamlit wake-up for deferred strict-egress cloud saves."""

from __future__ import annotations

from typing import Any

_FRAGMENT_KEY = "_music_strict_save_flusher_mounted"


def mount_strict_save_wakeup_flusher(st: Any, *, build_state: Any) -> None:
    """
    While a debounced strict save is pending, run a 1s fragment timer so the
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
        strict_save_wakeup_tick(st, build_state=build_state)

    _music_strict_save_wakeup_fragment()


__all__ = ["mount_strict_save_wakeup_flusher"]

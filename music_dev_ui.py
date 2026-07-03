"""Central developer-mode gate for Music UI surfaces."""

from __future__ import annotations

from typing import Any


def music_dev_mode_enabled(*, st: Any | None = None) -> bool:
    """
    True when explicit developer mode is on.

    Enabled via ``?dev=1`` or session dev flags (``developer_mode``, etc.).
    Normal users without dev mode see a clean product UI.
    """
    try:
        from suite_workspace import is_developer_mode_enabled

        return is_developer_mode_enabled(st=st)
    except ImportError:
        if st is not None:
            try:
                return bool(st.session_state.get("developer_mode"))
            except Exception:
                pass
        return False

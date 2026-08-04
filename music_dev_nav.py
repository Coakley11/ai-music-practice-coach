"""?dev=1 navigation and hydration counters (session-local)."""

from __future__ import annotations

from typing import Any

_COUNTERS_KEY = "_music_dev_perf_counters"


def dev_count(session: dict[str, Any], name: str, *, n: int = 1) -> None:
    if not session.get("_dev_mode") and not session.get("dev_mode"):
        try:
            from suite_workspace import is_developer_mode_enabled

            if not is_developer_mode_enabled(st=None):
                return
        except ImportError:
            return
    c = session.setdefault(_COUNTERS_KEY, {})
    if isinstance(c, dict):
        c[name] = int(c.get(name) or 0) + int(n)


def render_dev_counters_caption(st_module: Any, session: dict[str, Any], *, route: str) -> None:
    c = session.get(_COUNTERS_KEY)
    if not isinstance(c, dict) or not c:
        return
    bits = ", ".join(f"{k}={v}" for k, v in sorted(c.items()))
    st_module.caption(f"DEV counters · {route} · {bits}")

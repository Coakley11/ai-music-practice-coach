"""?dev=1 render timing — no overhead when developer mode is off."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator

_PERF_KEY = "_music_dev_perf_spans"


def _enabled(session: dict[str, Any] | None, st_module: Any | None) -> bool:
    if session is not None and (session.get("_dev_mode") or session.get("dev_mode")):
        return True
    try:
        from suite_workspace import is_developer_mode_enabled

        return bool(is_developer_mode_enabled(st=st_module))
    except ImportError:
        return False


@contextmanager
def dev_perf_span(
    session: dict[str, Any],
    label: str,
    *,
    st_module: Any | None = None,
) -> Iterator[None]:
    if not _enabled(session, st_module):
        yield
        return
    t0 = time.perf_counter()
    try:
        yield
    finally:
        ms = (time.perf_counter() - t0) * 1000.0
        spans = session.setdefault(_PERF_KEY, [])
        if isinstance(spans, list):
            spans.append({"label": label, "ms": round(ms, 2)})


def dev_perf_note(session: dict[str, Any], label: str, **fields: Any) -> None:
    if not _enabled(session, None):
        return
    spans = session.setdefault(_PERF_KEY, [])
    if isinstance(spans, list):
        spans.append({"label": label, **fields})


def render_dev_perf_caption(st_module: Any, session: dict[str, Any], *, route: str) -> None:
    if not _enabled(session, st_module):
        return
    spans = session.pop(_PERF_KEY, [])
    if not isinstance(spans, list) or not spans:
        return
    total = sum(float(s.get("ms") or 0) for s in spans if "ms" in s)
    bits = ", ".join(
        f"{s.get('label')} {s.get('ms')}ms" for s in spans[-8:] if s.get("ms") is not None
    )
    st_module.caption(f"DEV perf · {route} · ~{total:.0f}ms · {bits}")

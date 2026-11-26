"""Whether a melody panel on Backing is open: the musician's choice, kept per song.

Dev review 2026-11-25: a melody closed during Key Cycling opened again when the music changed key. The panels were
expanders that start open and had no identity of their own: the browser rebuilt them (open) whenever anything above
them appeared or went -- a key step, a settings rebuild -- or a run did not draw them. The choice now lives here,
keyed by panel and song: a cycling key, a setting, an instrument or a rerun never changes it. Only the musician
does, or an explicit request to see a melody (``show``).
"""

from __future__ import annotations

import hashlib
from typing import Any

STATE_KEY = "_backing_melody_panels_open"
_MAX = 60

PRACTICE = "practice"
ORIGINAL = "original"


def _slot(panel: str, identity: str) -> str:
    return f"{panel}::{hashlib.sha256(str(identity or '').encode()).hexdigest()[:12]}"


def widget_key(panel: str, identity: str) -> str:
    return f"bk_melody_panel::{_slot(panel, identity)}"


def is_open(session: Any, panel: str, identity: str, *, default: bool = True) -> bool:
    saved = session.get(STATE_KEY)
    value = saved.get(_slot(panel, identity)) if isinstance(saved, dict) else None
    return value if isinstance(value, bool) else default


def set_open(session: Any, panel: str, identity: str, value: bool) -> None:
    saved = session.get(STATE_KEY)
    saved = dict(saved) if isinstance(saved, dict) else {}
    slot = _slot(panel, identity)
    saved.pop(slot, None)
    saved[slot] = bool(value)
    while len(saved) > _MAX:
        saved.pop(next(iter(saved)))
    session[STATE_KEY] = saved


def show(session: Any, panel: str, identity: str) -> None:
    """The musician asked for this melody (created it, or opened it from Practice): show it."""
    set_open(session, panel, identity, True)
    session.pop(widget_key(panel, identity), None)


def _remember(panel: str, identity: str, key: str) -> None:
    import streamlit as st

    set_open(st.session_state, panel, identity, bool(st.session_state.get(key)))


def melody_expander(st: Any, label: str, panel: str, identity: str) -> Any:
    """The panel, open or closed as the musician last left it for this song."""
    session = st.session_state
    key = widget_key(panel, identity)
    if key not in session:
        session[key] = is_open(session, panel, identity)
    return st.expander(label, key=key, on_change=_remember, args=(panel, identity, key))


__all__ = ("ORIGINAL", "PRACTICE", "STATE_KEY", "is_open", "melody_expander", "set_open", "show", "widget_key")

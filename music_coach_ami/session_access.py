"""Accept Streamlit SessionStateProxy (Mapping) — never coerce live session to ``{}``."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any


def as_session_mapping(session_state: Any | None) -> Mapping[str, Any]:
    """Return a Mapping suitable for ``.get`` reads.

    Streamlit's ``st.session_state`` is a ``SessionStateProxy`` (MutableMapping),
    **not** a ``dict``. Treating non-dict as ``{}`` empties Practice Key, chart
    improv sections, and instrument on the live submit path.
    """
    if session_state is None:
        return {}
    if isinstance(session_state, Mapping):
        return session_state
    return {}


def as_mutable_session(session_state: Any | None) -> MutableMapping[str, Any] | dict[str, Any]:
    """Prefer the live mutable session when available (capo / key writes)."""
    if isinstance(session_state, MutableMapping):
        return session_state
    if isinstance(session_state, Mapping):
        return dict(session_state)
    return {}

"""Treat Streamlit's session state as a real mapping.

``st.session_state`` is a ``MutableMapping`` but NOT a ``dict`` subclass. Code that guards with
``isinstance(session, dict)`` silently reads an empty session on the real app (tests pass plain
dicts, so they never noticed). Cloud-write pre-flight used that guard, so a signed-in device
always looked "never hydrated" and every save to an existing workspace was refused as a conflict.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def as_session_mapping(session: Any) -> Any:
    """Return ``session`` unchanged when it is any mapping (dict or Streamlit proxy), else ``{}``."""
    if isinstance(session, Mapping):
        return session
    if session is not None and hasattr(session, "get") and hasattr(session, "keys"):
        return session
    return {}

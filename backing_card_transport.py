"""Backing card transport: the one Play / Stop control on the active Backing card.

The control's label is read in the browser from the real audio elements, so it
cannot drift from playback. Clicks reach Python as intents ("play", "stop",
"ended") that the Backing page hands to its existing Play / Stop handlers, so
musical state (song, source, key, BPM) is never written here.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

BACKING_CARD_TRANSPORT_KEY = "backing_card_transport"
BACKING_CARD_TRANSPORT_CONSUMED_KEY = "_backing_card_transport_consumed"
TRANSPORT_ACTIONS = frozenset({"play", "stop", "ended"})

_COMPONENT_DIR = Path(__file__).resolve().parent / "backing_transport_component"
_backing_transport_component = components.declare_component(
    "backing_card_transport",
    path=str(_COMPONENT_DIR),
)


def consume_backing_card_transport_action(session: dict[str, Any]) -> str:
    """The card's newest click intent, returned once; "" when there is none."""
    raw = session.get(BACKING_CARD_TRANSPORT_KEY)
    if not isinstance(raw, dict):
        return ""
    action = str(raw.get("action") or "").strip()
    if action not in TRANSPORT_ACTIONS:
        return ""
    token = f"{raw.get('session') or ''}:{raw.get('nonce') or ''}"
    if session.get(BACKING_CARD_TRANSPORT_CONSUMED_KEY) == token:
        return ""
    session[BACKING_CARD_TRANSPORT_CONSUMED_KEY] = token
    return action


def render_backing_card_transport(
    session: dict[str, Any],
    *,
    enabled: bool,
    server_playing: bool,
    report_ended: bool = True,
    now_singing: str = "",
) -> None:
    """Mount the Play / Stop control (inside the active Backing card).

    ``consumed`` echoes the last click Python handled, so the control can end
    its "Starting…" state for exactly that Play instead of any later rerun.
    ``now_singing`` is the Karaoke entry this render is for: the destination
    shown on Next / Previous stays up until the render for that entry arrives.
    """
    _backing_transport_component(
        key=BACKING_CARD_TRANSPORT_KEY,
        enabled=bool(enabled),
        server_playing=bool(server_playing),
        report_ended=bool(report_ended),
        now_singing=str(now_singing or ""),
        consumed=str(session.get(BACKING_CARD_TRANSPORT_CONSUMED_KEY) or ""),
        render_id=uuid.uuid4().hex[:10],
        default=None,
    )

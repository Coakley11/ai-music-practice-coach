"""Backing card transport: Play / Stop and Pause / Resume on the active Backing card.

The buttons follow the explicit transport intent (backing_transport_intent):
STOPPED offers Play; PLAYING offers Stop and Pause; PAUSED offers Stop and
Resume. The browser still reads the real audio elements for "Starting…" (Play
pressed, nothing audible yet) and for a natural end. Clicks reach Python as
intents ("play", "stop", "pause", "resume", "ended") that the Backing page
hands to its transport handlers, so musical state (song, source, key, BPM) is
never written here.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

BACKING_CARD_TRANSPORT_KEY = "backing_card_transport"
BACKING_CARD_TRANSPORT_CONSUMED_KEY = "_backing_card_transport_consumed"
TRANSPORT_ACTIONS = frozenset({"play", "stop", "pause", "resume", "ended"})

_COMPONENT_DIR = Path(__file__).resolve().parent / "backing_transport_component"
_backing_transport_component = components.declare_component(
    "backing_card_transport",
    path=str(_COMPONENT_DIR),
)


def consume_backing_card_transport_action(session: dict[str, Any]) -> str:
    """The card's newest intent, consumed on receipt (at most once).

    The Backing page applies Play / Stop / Pause / Resume through
    backing_card_commands instead, which commits a command only after it was
    applied, so a run cut off in between handles it again.
    """
    from backing_card_commands import commit_card_command, pending_card_command

    action, token = pending_card_command(session)
    commit_card_command(session, token)
    return action


def _echo_token(session: dict[str, Any]) -> str:
    from backing_card_commands import card_echo_token

    return card_echo_token(session)


def render_backing_card_transport(
    session: dict[str, Any],
    *,
    enabled: bool,
    server_playing: bool,
    report_ended: bool = True,
    now_singing: str = "",
    transport: str = "",
    restart_on_resume: bool = False,
    cycle_active: bool = False,
) -> None:
    """Mount the transport control (inside the active Backing card).

    ``transport`` is the intent (stopped / playing / paused). With
    ``restart_on_resume`` a setting changed while paused, so Resume leaves the
    paused take alone and the server starts the new selection. Key cycling has
    its own Pause / Resume on the cycle bar, so ``cycle_active`` hides the
    card's.

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
        transport=str(transport or ""),
        restart_on_resume=bool(restart_on_resume),
        cycle_active=bool(cycle_active),
        # The newest command the server applied (it is committed a little later
        # for Play: once armed).
        consumed=_echo_token(session),
        render_id=uuid.uuid4().hex[:10],
        default=None,
    )

"""Which props the Lead Sheet's follow-along player is drawn with on a run.

Streamlit re-creates a ``components.html`` iframe whenever its HTML changes, and a re-created player starts again
from 0:00. So while one take stays mounted, the props that decide autoplay, countdown and the "sheet just opened
over a live take" hand-off are kept exactly as first drawn for that take (later runs would otherwise flip them).

A fresh open request is a new mount: the sheet was closed, so nothing is mounted to protect. Reusing the props of
the take's earlier mount there handed the reopened player that mount's hand-off flag (off), so it autoplayed from
0:00 beside the still-playing page player instead of taking over at its position.
"""
from __future__ import annotations

from typing import Any, MutableMapping

RENDERED_TAKE = "_ls_rendered_take"
AUTOPLAY_RENDERED = "_ls_autoplay_rendered"
COUNTDOWN_RENDERED = "_ls_countdown_rendered"
HANDOFF_RENDERED = "_ls_handoff_rendered"


def lead_sheet_mount_props(
    session: MutableMapping[str, Any],
    *,
    take: str,
    intent: str,
    autoplay: bool,
    countdown: bool,
    handoff: bool,
) -> tuple[bool, bool, bool]:
    """Return (autoplay, countdown, handoff) for this run and remember them for the take.

    ``handoff`` is this run's one-shot open request (True only on the run the sheet is opened over a take).
    """
    keep = (
        bool(take)
        and intent in ("playing", "paused")
        and session.get(RENDERED_TAKE) == take
        and not handoff
    )
    if keep:
        autoplay = bool(session.get(AUTOPLAY_RENDERED, autoplay))
        countdown = bool(session.get(COUNTDOWN_RENDERED, countdown))
        handoff = bool(session.get(HANDOFF_RENDERED, handoff))
    session[RENDERED_TAKE] = take
    session[AUTOPLAY_RENDERED] = bool(autoplay)
    session[COUNTDOWN_RENDERED] = bool(countdown)
    session[HANDOFF_RENDERED] = bool(handoff)
    return bool(autoplay), bool(countdown), bool(handoff)

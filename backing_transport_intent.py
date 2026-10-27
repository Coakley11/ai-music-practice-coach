"""Explicit Backing transport intent: STOPPED, PLAYING or PAUSED.

Whether audio should play used to be inferred on every run from autoplay
flags, prepared takes, the key-cycle status and resume markers. A settings
change or a background render finishing could therefore start playback on
its own, and Stop was a hold that a later setting change undid.

Only an explicit transport command writes the intent:

* Play (card)                                    -> PLAYING, new session
* Pause (card, Lead Sheet, key-cycle bar)        -> PAUSED
* Resume / Continue                              -> PLAYING, same session
* Stop (card)                                    -> STOPPED, session over
* Karaoke Start / Next / Previous / auto-advance -> PLAYING
* Key cycling Previous / Next                    -> PLAYING
* a non-Karaoke take finishing on its own        -> STOPPED

Settings never write it. Every player mount asks :func:`playback_allowed`,
so a take generated while STOPPED or PAUSED is installed silently and waits
for an explicit command. The intent lives in this browser session only and
is never persisted: a refresh starts STOPPED.

A structural edit while PAUSED (scope, sections, loops, BPM, feel, meter,
strings) sets ``restart_on_resume``: Resume then starts the new selection
from its first chord instead of un-pausing the obsolete take.

``generation`` counts playback sessions (Play and Stop each start a new
one), so work queued for an older session can tell it is stale.
"""

from __future__ import annotations

import time
from typing import Any

STOPPED = "stopped"
PLAYING = "playing"
PAUSED = "paused"
TRANSPORT_STATES = (STOPPED, PLAYING, PAUSED)

TRANSPORT_INTENT_KEY = "_backing_transport_intent"
TRANSPORT_GENERATION_KEY = "_backing_transport_generation"
RESTART_ON_RESUME_KEY = "_backing_transport_restart_on_resume"
TRANSPORT_LOG_KEY = "_backing_transport_log"
# The card command that started the current session (see backing_card_commands).
TRANSPORT_COMMAND_KEY = "_backing_transport_command"
_LOG_LIMIT = 24


def transport_intent(session: Any) -> str:
    value = str((session or {}).get(TRANSPORT_INTENT_KEY) or "").strip().lower()
    return value if value in TRANSPORT_STATES else STOPPED


def transport_generation(session: Any) -> int:
    try:
        return int((session or {}).get(TRANSPORT_GENERATION_KEY) or 0)
    except (TypeError, ValueError):
        return 0


def playback_allowed(session: Any) -> bool:
    """True only while the musician's last transport command was Play / Resume."""
    return transport_intent(session) == PLAYING


def transport_session_active(session: Any) -> bool:
    """A playback session exists (playing or paused); Stop ends it."""
    return transport_intent(session) in (PLAYING, PAUSED)


def restart_on_resume(session: Any) -> bool:
    return bool((session or {}).get(RESTART_ON_RESUME_KEY))


def _set(
    session: Any,
    intent: str,
    *,
    reason: str,
    new_session: bool,
    generation: int | None = None,
) -> str:
    before = transport_intent(session)
    session[TRANSPORT_INTENT_KEY] = intent
    if generation is not None:
        session[TRANSPORT_GENERATION_KEY] = int(generation)
    elif new_session:
        session[TRANSPORT_GENERATION_KEY] = transport_generation(session) + 1
    log = session.get(TRANSPORT_LOG_KEY)
    log = list(log) if isinstance(log, list) else []
    log.append(
        {
            "t": round(time.time(), 3),
            "from": before,
            "to": intent,
            "reason": str(reason or ""),
            "gen": transport_generation(session),
        }
    )
    session[TRANSPORT_LOG_KEY] = log[-_LOG_LIMIT:]
    return intent


def transport_command(session: Any) -> str:
    """The card command whose Play started the newest session ("" if none)."""
    rec = (session or {}).get(TRANSPORT_COMMAND_KEY)
    return str(rec.get("token") or "") if isinstance(rec, dict) else ""


def begin_playback(session: Any, *, reason: str = "play", command: str = "") -> str:
    """Play: a new playback session from the beginning of the selection.

    With ``command`` (a card command token) this is idempotent: the session the
    command starts is decided in one write before anything changes, and handling
    the same command again (its run was cut off part-way) completes that same
    session instead of starting another.
    """
    if command:
        rec = session.get(TRANSPORT_COMMAND_KEY)
        if isinstance(rec, dict) and rec.get("token") == command:
            target = int(rec.get("generation") or 0)
        else:
            target = transport_generation(session) + 1
            session[TRANSPORT_COMMAND_KEY] = {"token": str(command), "generation": target}
        session.pop(RESTART_ON_RESUME_KEY, None)
        return _set(session, PLAYING, reason=reason, new_session=True, generation=target)
    session.pop(RESTART_ON_RESUME_KEY, None)
    return _set(session, PLAYING, reason=reason, new_session=True)


def continue_playback(session: Any, *, reason: str = "resume") -> str:
    """Resume / Next / Previous: the current session keeps (or starts) playing."""
    if transport_intent(session) == STOPPED:
        return begin_playback(session, reason=reason)
    session.pop(RESTART_ON_RESUME_KEY, None)
    return _set(session, PLAYING, reason=reason, new_session=False)


def pause_playback(session: Any, *, reason: str = "pause") -> str:
    """Pause: the session and its position stay; nothing sounds."""
    if transport_intent(session) == STOPPED:
        return STOPPED
    return _set(session, PAUSED, reason=reason, new_session=False)


def restore_paused_session(session: Any, *, reason: str = "restore") -> str:
    """A refreshed page restored a held key cycle: a paused session at that key.

    Resume restarts that key's pass; Stop ends it. Nothing sounds on its own.
    """
    session.pop(RESTART_ON_RESUME_KEY, None)
    return _set(session, PAUSED, reason=reason, new_session=True)


def stop_playback(session: Any, *, reason: str = "stop") -> str:
    """Stop: the playback session is over; the next Play starts from the top."""
    session.pop(RESTART_ON_RESUME_KEY, None)
    return _set(session, STOPPED, reason=reason, new_session=True)


def note_playback_settings_changed(session: Any, *, reason: str = "settings") -> str:
    """A structural setting changed. Never starts audio.

    While paused, the paused take no longer matches the selection, so Resume
    must start the new selection from its first chord.
    """
    intent = transport_intent(session)
    if intent == PAUSED:
        session[RESTART_ON_RESUME_KEY] = True
    return intent


def consume_restart_on_resume(session: Any) -> bool:
    return bool(session.pop(RESTART_ON_RESUME_KEY, False))


__all__ = [
    "PAUSED",
    "PLAYING",
    "RESTART_ON_RESUME_KEY",
    "STOPPED",
    "TRANSPORT_COMMAND_KEY",
    "TRANSPORT_GENERATION_KEY",
    "TRANSPORT_INTENT_KEY",
    "TRANSPORT_LOG_KEY",
    "TRANSPORT_STATES",
    "begin_playback",
    "consume_restart_on_resume",
    "continue_playback",
    "note_playback_settings_changed",
    "pause_playback",
    "playback_allowed",
    "restart_on_resume",
    "restore_paused_session",
    "stop_playback",
    "transport_command",
    "transport_generation",
    "transport_intent",
    "transport_session_active",
]

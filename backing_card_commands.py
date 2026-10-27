"""Backing card commands (Play / Stop / Pause / Resume): applied, then acknowledged.

Every ``st.session_state`` access can end a Streamlit run: with fastReruns a
click (or any component update) during a run stops it at its next session
access with a ``StopException``, a ``BaseException`` no handler catches. The
card's command used to be marked consumed before it was handled, so a run cut
off in between lost it for good -- a Play left the card on Stop with nothing
armed and no audio, a Stop could leave the session playing.

Here a command stays *pending* until :func:`commit_card_command`, which the
Backing page calls once the command's authoritative mutation is complete. A
run cut off earlier handles the same command again on the next run, and
applying it again changes nothing:

* Play starts its playback session once per command: the session is
  decided in one write before anything changes, and a retry completes it.
* Stop and Pause are idempotent.
* Resume and Stop record their decisions per command (``_plan``) before they
  mutate anything, so a retry decides exactly as the first attempt did even
  though that attempt already cleared the flags it read.

A newer click replaces the pending command (each click carries its own
nonce), so a superseded command is never applied later. ``ended`` (a take
finishing) stays consumed on receipt: it advances a Karaoke set, which must
happen at most once.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from backing_card_transport import (
    BACKING_CARD_TRANSPORT_CONSUMED_KEY,
    BACKING_CARD_TRANSPORT_KEY,
    TRANSPORT_ACTIONS,
)
from backing_transport_intent import (
    begin_playback,
    continue_playback,
    pause_playback,
    restart_on_resume,
)

# The command whose authoritative mutation the server has applied: echoed to
# the card (ends its "Starting…" state) before the command is committed.
CARD_HANDLED_KEY = "_backing_card_transport_handled"
CARD_PLAN_KEY = "_backing_card_command_plan"
BACKING_AUTOPLAY_KEY = "_backing_autoplay"
BACKING_PLAY_FEEDBACK_KEY = "_backing_play_feedback"


@dataclass(frozen=True)
class CardCommandOutcome:
    """What the Backing page does next for one handled command.

    ``play``: run the Play path (arm the follow-along, build or mount the take)
    and commit once it is armed. ``commit``: the command is complete; commit it
    now. ``rerun``: rerun after committing.
    """

    play: bool = False
    commit: bool = False
    rerun: bool = False


def pending_card_command(session: Any) -> tuple[str, str]:
    """The card's newest command and its token, until it is committed."""
    raw = session.get(BACKING_CARD_TRANSPORT_KEY)
    if not isinstance(raw, dict):
        return "", ""
    action = str(raw.get("action") or "").strip()
    if action not in TRANSPORT_ACTIONS:
        return "", ""
    token = f"{raw.get('session') or ''}:{raw.get('nonce') or ''}"
    if session.get(BACKING_CARD_TRANSPORT_CONSUMED_KEY) == token:
        return "", ""
    return action, token


def commit_card_command(session: Any, token: str) -> None:
    """The command is fully applied: never handle it again."""
    if token and session.get(BACKING_CARD_TRANSPORT_CONSUMED_KEY) != token:
        session[BACKING_CARD_TRANSPORT_CONSUMED_KEY] = token
    _mark_handled(session, token)


def commit_handled_card_command(session: Any) -> None:
    """Commit the pending command if its mutation was applied (Play once armed).

    The component value cannot change during a run, so this is the command
    this run handled.
    """
    _action, token = pending_card_command(session)
    if token and session.get(CARD_HANDLED_KEY) == token:
        commit_card_command(session, token)


def card_echo_token(session: Any) -> str:
    """The newest command the server applied, for the card's state machine."""
    return str(
        session.get(CARD_HANDLED_KEY) or session.get(BACKING_CARD_TRANSPORT_CONSUMED_KEY) or ""
    )


def _plan(session: Any, token: str, decide: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """This command's decisions, made on its first attempt (one atomic write)."""
    plan = session.get(CARD_PLAN_KEY)
    if isinstance(plan, dict) and plan.get("token") == token:
        return plan
    plan = dict(decide(), token=token)
    session[CARD_PLAN_KEY] = plan
    return plan


def _mark_handled(session: Any, token: str) -> None:
    if session.get(CARD_HANDLED_KEY) != token:
        session[CARD_HANDLED_KEY] = token


def apply_card_command(
    session: Any,
    action: str,
    token: str,
    *,
    has_chords: bool,
    stop_backing: Callable[[int], bool],
    karaoke_index: Callable[[], int] = lambda: 0,
) -> CardCommandOutcome:
    """Apply one card command; safe to call again for the same command.

    ``stop_backing(karaoke_index_before)`` is the Backing page's Stop (it ends
    key cycling and a Karaoke set too) and returns True when the page must
    rerun. ``karaoke_index`` reads Now Singing's index before Stop moves it.
    """
    if action == "play":
        if not has_chords:
            return CardCommandOutcome(commit=True)
        # Idempotent per command: a retry completes the same session.
        begin_playback(session, reason="card_play", command=token)
        _mark_handled(session, token)
        return CardCommandOutcome(play=True)
    if action == "stop":
        plan = _plan(session, token, lambda: {"karaoke_index": int(karaoke_index() or 0)})
        rerun = bool(stop_backing(int(plan.get("karaoke_index") or 0)))
        _mark_handled(session, token)
        return CardCommandOutcome(commit=True, rerun=rerun)
    if action == "pause":
        # The browser already paused the take where it was; the session stays.
        pause_playback(session, reason="card_pause")
        session[BACKING_AUTOPLAY_KEY] = False
        session.pop("_backing_play_request", None)
        session[BACKING_PLAY_FEEDBACK_KEY] = "Paused"
        try:
            from backing_key_cycle import is_cycle_active, pause_key_cycle

            if is_cycle_active(session):
                pause_key_cycle(session)
        except Exception:
            pass
        _mark_handled(session, token)
        return CardCommandOutcome(commit=True)
    if action == "resume":
        # A setting changed while paused: the paused take is obsolete, so the
        # new selection starts from its first chord. Otherwise the browser has
        # already resumed the paused take from where it stopped.
        plan = _plan(session, token, lambda: {"restart": restart_on_resume(session)})
        continue_playback(session, reason="card_resume")
        session.pop("_backing_transport_user_stopped", None)
        session[BACKING_PLAY_FEEDBACK_KEY] = "Resumed"
        _cycle = False
        try:
            from backing_key_cycle import is_cycle_active, resume_key_cycle

            if is_cycle_active(session):
                _cycle = True
                resume_key_cycle(session)
        except Exception:
            pass
        if _cycle:
            _mark_handled(session, token)
            return CardCommandOutcome(commit=True)
        _mark_handled(session, token)
        if plan.get("restart") and has_chords:
            return CardCommandOutcome(play=True)
        session[BACKING_AUTOPLAY_KEY] = True
        return CardCommandOutcome(commit=True)
    return CardCommandOutcome(commit=True)


__all__ = [
    "CARD_HANDLED_KEY",
    "CARD_PLAN_KEY",
    "CardCommandOutcome",
    "apply_card_command",
    "card_echo_token",
    "commit_card_command",
    "pending_card_command",
]

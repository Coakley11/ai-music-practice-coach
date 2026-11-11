"""Issue 64 slice 4: which song commits are navigation, and which are the app breathing.

`commit_catalog_active_song` is called for two completely different things. One is a
musician choosing a song. The other is the app re-establishing the song it already had -
on a refresh, a page change, a restore from the canonical blob, a Creative visit coming
back. Both arrive at the same function.

Guarding all of them would be wrong twice over. A restore is not a navigation, so asking
about it interrupts someone who went nowhere; and a restore that gets held would leave
the app with no active song at all. Guarding none of them is the bug.

So the test here is narrow and has to be *all* of these at once:

* the reason is a deliberate selection, not a restore;
* the pick really differs from the one already active;
* and there is unsaved Multitrack work to lose.

Anything else proceeds untouched. ``reason`` alone is not trusted to mean a change -
the same selection reason arrives on remounts, which is why the pick is compared too.

**Letting the approved move through.** After the musician saves or discards, the move has
to actually happen. Rather than reconstruct it, the whole call is kept - arguments and
all, including the ``invalidate_backing`` callable the app passes - and replayed with a
one-shot token that this guard consumes. One token, one commit: it cannot authorize a
second.
"""

from __future__ import annotations

from typing import Any, Mapping

__all__ = [
    "APPROVED_PICK_KEY",
    "RESTORE_REASONS",
    "USER_SELECTION_REASONS",
    "approve_song_commit",
    "hold_song_commit_if_needed",
    "song_commit_is_user_selection",
]

#: Reasons that mean "a musician picked this song".
USER_SELECTION_REASONS = frozenset({
    "song_pick",
    "catalog_pick",
    "karaoke_selection",
    "creative_to_catalog",
    "switch_to_catalog_backing",
    "catalog_source_switch",
    "music_source_switch",
})

#: Reasons that mean "the app is putting back the song it already had". Never guarded:
#: holding one of these would leave the session with no active song.
RESTORE_REASONS = frozenset({
    "catalog_restore",
    "last_catalog_restore",
    "previous_catalog_restore",
})

#: One-shot permission, consumed by the commit it names.
APPROVED_PICK_KEY = "_mt_switch_approved_pick"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _active_pick(session_state: Mapping[str, Any]) -> str:
    try:
        from songs.state import ACTIVE_CATALOG_PICK_KEY
    except Exception:
        ACTIVE_CATALOG_PICK_KEY = "active_catalog_pick_key"
    return _text(session_state.get(ACTIVE_CATALOG_PICK_KEY))


def song_commit_is_user_selection(
    session_state: Mapping[str, Any],
    *,
    pick_key: str,
    reason: str,
) -> bool:
    """True only for a deliberate move to a *different* song."""
    reason = _text(reason)
    if not reason or reason in RESTORE_REASONS:
        return False
    if reason not in USER_SELECTION_REASONS:
        return False
    pick = _text(pick_key)
    if not pick:
        return False
    current = _active_pick(session_state)
    # A remount re-commits the same pick under a selection reason. Same song, no move.
    return bool(current) and current != pick


def approve_song_commit(session_state: Any, pick_key: str) -> None:
    """Let the next commit of this pick through once, without asking again."""
    try:
        session_state[APPROVED_PICK_KEY] = _text(pick_key)
    except Exception:
        pass


def _consume_approval(session_state: Any, pick_key: str) -> bool:
    try:
        approved = _text(session_state.get(APPROVED_PICK_KEY))
    except Exception:
        return False
    if not approved or approved != _text(pick_key):
        return False
    try:
        session_state.pop(APPROVED_PICK_KEY, None)
    except Exception:
        pass
    return True


def hold_song_commit_if_needed(
    session_state: Any,
    *,
    pick_key: str,
    reason: str,
    song_title: str = "",
    replay: Mapping[str, Any] | None = None,
) -> bool:
    """Decide whether this song commit may proceed.

    Returns ``True`` when the caller must **return without committing** - the request is
    now held and the prompt will render on the next rerun. ``False`` means carry on, and
    is what every restore, remount and clean-workspace selection gets.
    """
    if not song_commit_is_user_selection(session_state, pick_key=pick_key, reason=reason):
        return False
    if _consume_approval(session_state, pick_key):
        return False
    try:
        from multitrack_switch_intent import KIND_SONG, request_switch, switch_is_pending
    except Exception:
        return False                      # never break navigation over a missing guard
    if switch_is_pending(session_state):
        # A prompt is already open. Do not stack a second destination behind it, and do
        # not commit this one either.
        return True
    asked = request_switch(
        session_state,
        kind=KIND_SONG,
        target=_text(song_title) or _text(pick_key),
        reason=_text(reason),
        payload={"pick_key": _text(pick_key), "replay": dict(replay or {})},
    )
    return not asked.get("allowed", True)

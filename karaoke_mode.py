"""Karaoke / Vocal Performance Mode for the AI Music Practice Coach.

When the active instrument is ``Voice`` (or one of its aliases), the app
shifts into a karaoke-oriented experience: voice-aware wording on the
Backing Track page, a lightweight Performance Setlist on Song Selection,
and automatic transitions between queued songs.

Design notes:

* All state lives in :mod:`streamlit.session_state` under stable string
  keys defined here. **No** module in this package may import the main
  ``streamlit_music_practice_app`` module - this file is pure state +
  helpers so it can be imported by any page.
* Queue ordering uses the existing catalog ``pick_key`` (see
  ``song_catalog.catalog.format_pick_key``) so the queue survives catalog
  rebuilds and identifies songs uniquely across genres.
* The pending / advance pattern mirrors the other ``_pending_*`` keys in
  the app (e.g. ``_pending_backing_single_section``). Anything that needs
  to mutate a widget key is queued here and applied **before** widgets
  rebuild on the next rerun.
* Future-facing hooks (``record_vocal_score``, ``set_vocal_focus_target``
  etc.) are intentional stubs so pitch tracking / scoring can be added
  later without rewiring the queue or wording layer.
"""

from __future__ import annotations

from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Voice instrument aliases
# ---------------------------------------------------------------------------

#: Set of instrument values that should activate Vocal Performance Mode.
#: ``"Voice"`` is the canonical value used by ``practice_setup_controls.py``;
#: the others are accepted as aliases in case the instrument list is
#: extended later.
VOICE_INSTRUMENT_ALIASES: frozenset[str] = frozenset(
    {"voice", "vocals", "vocal", "singer", "vocalist", "karaoke"}
)


def is_voice_mode(session_state: Any) -> bool:
    """Return ``True`` when the active instrument is Voice (or an alias)."""
    instrument = str((session_state or {}).get("instrument") or "").strip().lower()
    if not instrument:
        return False
    return instrument in VOICE_INSTRUMENT_ALIASES


# ---------------------------------------------------------------------------
# Session-state keys
# ---------------------------------------------------------------------------

KARAOKE_QUEUE_KEY = "karaoke_queue"
"""``list[str]`` of catalog ``pick_key`` values queued for the setlist."""

KARAOKE_SESSION_ACTIVE_KEY = "karaoke_session_active"
"""``bool`` - whether a karaoke performance is currently running."""

KARAOKE_SESSION_INDEX_KEY = "karaoke_session_index"
"""``int`` - 0-based index into ``KARAOKE_QUEUE_KEY`` of the currently
performing song. Only meaningful when the session is active."""

KARAOKE_AUTO_ADVANCE_KEY = "karaoke_auto_advance"
"""``bool`` - user preference for automatic transitions after a song
finishes (default ``True``)."""

PENDING_KARAOKE_ADVANCE_KEY = "_pending_karaoke_advance"
"""When set, the next rerun should advance the active song to the next
queued entry **before** rebuilding any backing-track widgets."""

KARAOKE_SONG_ENDED_KEY = "_karaoke_song_ended"
"""Sticky flag set by the JS bridge when the backing audio finishes; the
transition card consumes this to show the next-song prompt."""

KARAOKE_TRANSITION_LABEL_KEY = "_karaoke_transition_label"
"""Short status string ("Next: <title>", "Setlist complete", ...) the
Backing Track page shows during a transition."""


# ---------------------------------------------------------------------------
# Queue operations
# ---------------------------------------------------------------------------


def get_queue(session_state: Any) -> list[str]:
    """Return a copy of the current karaoke queue."""
    return list((session_state or {}).get(KARAOKE_QUEUE_KEY) or [])


def queue_length(session_state: Any) -> int:
    return len(get_queue(session_state))


def is_in_queue(session_state: Any, pick_key: str) -> bool:
    return bool(pick_key) and pick_key in get_queue(session_state)


def add_to_queue(session_state: Any, pick_key: str) -> bool:
    """Append ``pick_key`` to the queue (no duplicates). Returns True if added."""
    if not pick_key:
        return False
    queue = get_queue(session_state)
    if pick_key in queue:
        return False
    queue.append(pick_key)
    session_state[KARAOKE_QUEUE_KEY] = queue
    return True


def add_many_to_queue(session_state: Any, pick_keys: Iterable[str]) -> int:
    """Append a batch of pick_keys. Returns the count actually added."""
    added = 0
    for pk in pick_keys:
        if add_to_queue(session_state, pk):
            added += 1
    return added


def remove_from_queue(session_state: Any, pick_key: str) -> bool:
    """Remove ``pick_key`` from the queue. Returns True if removed."""
    queue = get_queue(session_state)
    if pick_key not in queue:
        return False
    queue.remove(pick_key)
    session_state[KARAOKE_QUEUE_KEY] = queue
    # If we removed the currently performing song, clamp the index.
    if session_state.get(KARAOKE_SESSION_ACTIVE_KEY):
        idx = int(session_state.get(KARAOKE_SESSION_INDEX_KEY, 0) or 0)
        idx = min(idx, max(0, len(queue) - 1))
        session_state[KARAOKE_SESSION_INDEX_KEY] = idx
        if not queue:
            stop_session(session_state)
    return True


def move_in_queue(session_state: Any, pick_key: str, direction: int) -> bool:
    """Swap ``pick_key`` with its neighbour in the queue.

    ``direction`` is ``-1`` (move up / earlier) or ``+1`` (move down /
    later). Returns ``True`` if the queue actually changed.
    """
    if direction not in (-1, 1):
        return False
    queue = get_queue(session_state)
    if pick_key not in queue:
        return False
    idx = queue.index(pick_key)
    new_idx = idx + direction
    if new_idx < 0 or new_idx >= len(queue):
        return False
    queue[idx], queue[new_idx] = queue[new_idx], queue[idx]
    session_state[KARAOKE_QUEUE_KEY] = queue
    # Re-anchor the active index if we moved the currently performing song.
    if session_state.get(KARAOKE_SESSION_ACTIVE_KEY):
        active_pk = session_state.get("_karaoke_active_pick_key")
        if active_pk and active_pk in queue:
            session_state[KARAOKE_SESSION_INDEX_KEY] = queue.index(active_pk)
    return True


def clear_queue(session_state: Any) -> None:
    """Empty the karaoke queue (also ends any active session)."""
    session_state[KARAOKE_QUEUE_KEY] = []
    stop_session(session_state)


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


def is_karaoke_session_active(session_state: Any) -> bool:
    """``True`` when a karaoke performance is currently running."""
    return bool((session_state or {}).get(KARAOKE_SESSION_ACTIVE_KEY))


def session_position(session_state: Any) -> tuple[int, int]:
    """Return ``(current_position_1_indexed, total)``.

    ``current_position`` is ``0`` when no session is active.
    """
    total = queue_length(session_state)
    if not is_karaoke_session_active(session_state):
        return (0, total)
    idx = int(session_state.get(KARAOKE_SESSION_INDEX_KEY, 0) or 0)
    return (max(0, min(idx, max(total - 1, 0))) + 1, total)


def current_session_pick_key(session_state: Any) -> str | None:
    if not is_karaoke_session_active(session_state):
        return None
    queue = get_queue(session_state)
    if not queue:
        return None
    idx = int(session_state.get(KARAOKE_SESSION_INDEX_KEY, 0) or 0)
    if 0 <= idx < len(queue):
        return queue[idx]
    return None


def next_session_pick_key(session_state: Any) -> str | None:
    """The pick_key the session would advance to next, or ``None`` at end."""
    if not is_karaoke_session_active(session_state):
        return None
    queue = get_queue(session_state)
    if not queue:
        return None
    idx = int(session_state.get(KARAOKE_SESSION_INDEX_KEY, 0) or 0)
    nxt = idx + 1
    if 0 <= nxt < len(queue):
        return queue[nxt]
    return None


def start_session(
    session_state: Any,
    *,
    starting_pick_key: str | None = None,
) -> str | None:
    """Begin a karaoke performance.

    If ``starting_pick_key`` is provided and already in the queue, the
    session starts at that song; otherwise it starts at the head of the
    queue. Returns the pick_key that should now become the active song,
    or ``None`` when the queue is empty.
    """
    queue = get_queue(session_state)
    if not queue:
        return None
    start_idx = 0
    if starting_pick_key and starting_pick_key in queue:
        start_idx = queue.index(starting_pick_key)
    session_state[KARAOKE_SESSION_ACTIVE_KEY] = True
    session_state[KARAOKE_SESSION_INDEX_KEY] = start_idx
    session_state["_karaoke_active_pick_key"] = queue[start_idx]
    session_state.pop(KARAOKE_SONG_ENDED_KEY, None)
    session_state.pop(PENDING_KARAOKE_ADVANCE_KEY, None)
    session_state.setdefault(KARAOKE_AUTO_ADVANCE_KEY, True)
    return queue[start_idx]


def stop_session(session_state: Any) -> None:
    """End the karaoke performance (queue is left intact)."""
    session_state[KARAOKE_SESSION_ACTIVE_KEY] = False
    session_state.pop("_karaoke_active_pick_key", None)
    session_state.pop(KARAOKE_SONG_ENDED_KEY, None)
    session_state.pop(PENDING_KARAOKE_ADVANCE_KEY, None)
    session_state.pop(KARAOKE_TRANSITION_LABEL_KEY, None)


def advance_session(session_state: Any) -> str | None:
    """Advance the session to the next queued song.

    Returns the new active ``pick_key``, or ``None`` if the setlist is
    finished (in which case the session is automatically stopped).
    """
    queue = get_queue(session_state)
    if not queue or not is_karaoke_session_active(session_state):
        return None
    idx = int(session_state.get(KARAOKE_SESSION_INDEX_KEY, 0) or 0)
    nxt = idx + 1
    if nxt >= len(queue):
        session_state[KARAOKE_TRANSITION_LABEL_KEY] = "Setlist complete"
        stop_session(session_state)
        return None
    session_state[KARAOKE_SESSION_INDEX_KEY] = nxt
    session_state["_karaoke_active_pick_key"] = queue[nxt]
    session_state.pop(KARAOKE_SONG_ENDED_KEY, None)
    session_state.pop(PENDING_KARAOKE_ADVANCE_KEY, None)
    return queue[nxt]


def auto_advance_enabled(session_state: Any) -> bool:
    """User preference: auto-advance after each song? Defaults to ``True``."""
    raw = (session_state or {}).get(KARAOKE_AUTO_ADVANCE_KEY)
    if raw is None:
        return True
    return bool(raw)


# ---------------------------------------------------------------------------
# Pending-advance flag (consumed at the top of the Backing page)
# ---------------------------------------------------------------------------


def request_advance(session_state: Any, *, reason: str = "user") -> None:
    """Queue a karaoke advance to be applied **before** the next rerun's widgets.

    ``reason`` is recorded in ``KARAOKE_TRANSITION_LABEL_KEY`` for the UI
    (e.g. ``"audio_ended"`` -> "Next song", ``"user"`` -> "Continue").
    """
    if not is_karaoke_session_active(session_state):
        return
    session_state[PENDING_KARAOKE_ADVANCE_KEY] = True
    if reason == "audio_ended":
        session_state[KARAOKE_TRANSITION_LABEL_KEY] = "Next song"
    elif reason == "skip":
        session_state[KARAOKE_TRANSITION_LABEL_KEY] = "Skipping ahead"
    else:
        session_state[KARAOKE_TRANSITION_LABEL_KEY] = "Continue"


def consume_pending_advance(session_state: Any) -> str | None:
    """Apply a queued advance if one is pending.

    Returns the new active ``pick_key`` (or ``None`` if no advance was
    pending or the setlist just finished). Callers should run this at the
    very top of the Backing Track / page-entry block, before any widget
    rebuilds.
    """
    if not session_state.pop(PENDING_KARAOKE_ADVANCE_KEY, False):
        return None
    return advance_session(session_state)


def note_song_ended(session_state: Any) -> None:
    """Mark the currently performing song as finished (audio ``ended``)."""
    if not is_karaoke_session_active(session_state):
        return
    session_state[KARAOKE_SONG_ENDED_KEY] = True
    if auto_advance_enabled(session_state):
        request_advance(session_state, reason="audio_ended")


# ---------------------------------------------------------------------------
# Voice-mode wording
# ---------------------------------------------------------------------------

_VOICE_WORDING: dict[str, dict[str, str]] = {
    # key -> {default, voice}
    "backing_page_title":    {"default": "Backing Track",                     "voice": "Vocal Performance Mode"},
    "backing_page_subtitle": {
        "default": "Generate accompaniment matched to your active song - then play along.",
        "voice":   "Sing along to a backing track shaped for your voice - phrasing, breath, and emotional delivery first.",
    },
    "backing_kicker":        {"default": "Active song · Backing Track",      "voice": "Now Singing · Vocal Performance"},
    "active_song_kicker":    {"default": "Active Song",                       "voice": "Now Singing"},
    "queue_section_title":   {"default": "Performance Setlist",               "voice": "Karaoke Performance Setlist"},
    "queue_empty_caption":   {
        "default": "Add songs from the catalog below to build your setlist.",
        "voice":   "Build your karaoke setlist - add songs from the catalog and they'll play in order.",
    },
    "add_to_queue_button":   {"default": "Add to Setlist",                    "voice": "Add to Karaoke Queue"},
    "remove_from_queue":     {"default": "Remove",                            "voice": "Remove from Setlist"},
    "start_session_button":  {"default": "Start Performance",                 "voice": "Start Karaoke Set"},
    "stop_session_button":   {"default": "End Performance",                   "voice": "End Karaoke Set"},
    "continue_button":       {"default": "Continue to next song",             "voice": "Continue to next song"},
    "next_up_label":         {"default": "Up next",                           "voice": "Next on the setlist"},
}


def voice_wording(key: str, *, voice: bool) -> str:
    """Return the voice-aware label for ``key``, or the default."""
    entry = _VOICE_WORDING.get(key)
    if not entry:
        return key
    return entry["voice"] if voice else entry["default"]


def voice_mode_modifier_classes(
    session_state: Any,
    *,
    base: str = "",
) -> str:
    """Return CSS modifier classes to layer on top of the base class string.

    Adds ``" inst-voice"`` (so the existing ``studio_card_modifier_classes``
    cascade still applies) and, when a karaoke session is active, also
    ``" mode-karaoke"``.
    """
    bits: list[str] = []
    if is_voice_mode(session_state):
        bits.append("inst-voice")
    if is_karaoke_session_active(session_state):
        bits.append("mode-karaoke")
    if not bits:
        return ""
    joined = " ".join(bits)
    if base and not base.endswith(" "):
        return " " + joined
    return joined


# ---------------------------------------------------------------------------
# Extension hooks for future features (intentional stubs)
# ---------------------------------------------------------------------------


def record_vocal_score(
    session_state: Any,
    pick_key: str,
    *,
    accuracy: float,
    breath_score: float | None = None,
    phrasing_score: float | None = None,
) -> None:  # pragma: no cover - stub for future pitch-tracking feature
    """Reserved hook for vocal scoring / pitch tracking.

    Once a pitch-tracking front-end is wired in, this can persist scores
    keyed by ``pick_key`` so the Practice Log can show per-song karaoke
    history. Currently a no-op.
    """
    return None


def set_vocal_focus_target(
    session_state: Any,
    *,
    target: str | None,
) -> None:  # pragma: no cover - stub for future vocal-focus feature
    """Reserved hook for setting a vocal practice focus (breath / phrasing / range).

    Currently a no-op - the focus list already lives in
    ``practice_setup_controls.py``.
    """
    return None


__all__ = (
    "VOICE_INSTRUMENT_ALIASES",
    "KARAOKE_QUEUE_KEY",
    "KARAOKE_SESSION_ACTIVE_KEY",
    "KARAOKE_SESSION_INDEX_KEY",
    "KARAOKE_AUTO_ADVANCE_KEY",
    "PENDING_KARAOKE_ADVANCE_KEY",
    "KARAOKE_SONG_ENDED_KEY",
    "KARAOKE_TRANSITION_LABEL_KEY",
    "is_voice_mode",
    "is_karaoke_session_active",
    "auto_advance_enabled",
    "session_position",
    "current_session_pick_key",
    "next_session_pick_key",
    "get_queue",
    "queue_length",
    "is_in_queue",
    "add_to_queue",
    "add_many_to_queue",
    "remove_from_queue",
    "move_in_queue",
    "clear_queue",
    "start_session",
    "stop_session",
    "advance_session",
    "request_advance",
    "consume_pending_advance",
    "note_song_ended",
    "voice_wording",
    "voice_mode_modifier_classes",
    "record_vocal_score",
    "set_vocal_focus_target",
)

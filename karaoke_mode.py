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
* Queue entries are structured dicts with a unique ``entry_id``. The same
  song (``pick_key``) may appear multiple times; each row owns its own
  Practice Key snapshot and optional play count.
* Legacy persisted queues of bare ``pick_key`` strings are normalized on
  read so older sessions still load.
* The pending / advance pattern mirrors the other ``_pending_*`` keys in
  the app (e.g. ``_pending_backing_single_section``).
"""

from __future__ import annotations

import copy
import uuid
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Voice instrument aliases
# ---------------------------------------------------------------------------

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
"""``list[dict]`` of karaoke entries (legacy ``list[str]`` still accepted)."""

KARAOKE_SESSION_ACTIVE_KEY = "karaoke_session_active"
KARAOKE_SESSION_INDEX_KEY = "karaoke_session_index"
KARAOKE_AUTO_ADVANCE_KEY = "karaoke_auto_advance"
PENDING_KARAOKE_ADVANCE_KEY = "_pending_karaoke_advance"
KARAOKE_SONG_ENDED_KEY = "_karaoke_song_ended"
KARAOKE_TRANSITION_LABEL_KEY = "_karaoke_transition_label"
KARAOKE_COUNTDOWN_KEY = "karaoke_countdown_enabled"
KARAOKE_COUNTDOWN_SECONDS_KEY = "karaoke_countdown_seconds"
KARAOKE_SHOW_CHORDS_KEY = "karaoke_show_chords"
KARAOKE_LYRIC_COLOR_KEY = "karaoke_lyric_color"
PENDING_KARAOKE_AUTO_GENERATE_KEY = "_pending_karaoke_auto_generate"
KARAOKE_ENTRY_PLAYS_LEFT_KEY = "_karaoke_entry_plays_left"
"""Remaining playthroughs for the current entry (includes the current play)."""

KARAOKE_ACTIVE_ENTRY_ID_KEY = "_karaoke_active_entry_id"

# After a cold reboot / refresh, an active karaoke session may restore its
# queue index and entry identity, but audio always restarts from the start
# of that entry (no mid-song resume). Prefer safe restart over fragile
# playback-state restoration.
KARAOKE_SESSION_RESUME_POLICY = "restart_entry_from_start"


# ---------------------------------------------------------------------------
# Entry model
# ---------------------------------------------------------------------------


def _new_entry_id() -> str:
    return str(uuid.uuid4())


def _infer_source(pick_key: str) -> str:
    pk = str(pick_key or "")
    if pk.startswith("custom::"):
        return "custom_progression"
    if pk.startswith("composition::"):
        return "composition_song"
    return "catalog_song"


def normalize_karaoke_entry(
    raw: Any,
    *,
    practice_key: str = "",
    play_count: int = 1,
    title: str = "",
    artist: str = "",
) -> dict[str, Any] | None:
    """Normalize a legacy pick_key string or entry dict into a karaoke entry."""
    if isinstance(raw, str):
        pick_key = raw.strip()
        if not pick_key:
            return None
        return {
            "entry_id": _new_entry_id(),
            "pick_key": pick_key,
            "source": _infer_source(pick_key),
            "practice_key": str(practice_key or "").strip(),
            "play_count": max(1, int(play_count or 1)),
            "title": str(title or "").strip(),
            "artist": str(artist or "").strip(),
        }
    if not isinstance(raw, dict):
        return None
    pick_key = str(raw.get("pick_key") or "").strip()
    if not pick_key:
        return None
    try:
        plays = max(1, int(raw.get("play_count") or play_count or 1))
    except (TypeError, ValueError):
        plays = 1
    entry_id = str(raw.get("entry_id") or "").strip() or _new_entry_id()
    source = str(raw.get("source") or "").strip() or _infer_source(pick_key)
    return {
        "entry_id": entry_id,
        "pick_key": pick_key,
        "source": source,
        "practice_key": str(raw.get("practice_key") or practice_key or "").strip(),
        "play_count": plays,
        "title": str(raw.get("title") or title or "").strip(),
        "artist": str(raw.get("artist") or artist or "").strip(),
    }


def normalize_karaoke_queue(raw: Any) -> list[dict[str, Any]]:
    """Upgrade legacy ``list[str]`` queues and drop invalid rows."""
    out: list[dict[str, Any]] = []
    for item in list(raw or []):
        entry = normalize_karaoke_entry(item)
        if entry:
            out.append(entry)
    return out


def _write_queue(session_state: Any, queue: list[dict[str, Any]]) -> None:
    session_state[KARAOKE_QUEUE_KEY] = [copy.deepcopy(e) for e in queue]


def get_queue(session_state: Any) -> list[dict[str, Any]]:
    """Return a normalized copy of the karaoke queue (structured entries)."""
    raw = (session_state or {}).get(KARAOKE_QUEUE_KEY)
    normalized = normalize_karaoke_queue(raw)
    # Persist upgrade in-place so later code and disk see entry dicts.
    if isinstance(raw, list) and (
        len(raw) != len(normalized)
        or any(not isinstance(x, dict) for x in raw)
        or any(not str((x or {}).get("entry_id") or "").strip() for x in raw if isinstance(x, dict))
    ):
        _write_queue(session_state, normalized)
    reconcile_karaoke_session_after_restore(session_state)
    return [copy.deepcopy(e) for e in normalized]


def reconcile_karaoke_session_after_restore(session_state: Any) -> None:
    """Keep restored session index safe; never invent mid-song audio resume.

    Queue + entry Practice Keys survive refresh. If a session was active,
    we keep the entry index when valid so Start/Voice can continue the
    setlist from that row — audio always restarts from the entry start
    (``KARAOKE_SESSION_RESUME_POLICY``).
    """
    if not session_state:
        return
    queue = normalize_karaoke_queue(session_state.get(KARAOKE_QUEUE_KEY))
    if not queue:
        if session_state.get(KARAOKE_SESSION_ACTIVE_KEY):
            stop_session(session_state)
        return
    if not session_state.get(KARAOKE_SESSION_ACTIVE_KEY):
        return
    idx = int(session_state.get(KARAOKE_SESSION_INDEX_KEY, 0) or 0)
    if idx < 0 or idx >= len(queue):
        session_state[KARAOKE_SESSION_INDEX_KEY] = 0
        idx = 0
    entry = queue[idx]
    session_state[KARAOKE_ACTIVE_ENTRY_ID_KEY] = str(entry.get("entry_id") or "")
    session_state["_karaoke_active_pick_key"] = str(entry.get("pick_key") or "")
    if KARAOKE_ENTRY_PLAYS_LEFT_KEY not in session_state:
        try:
            plays = max(1, int(entry.get("play_count") or 1))
        except (TypeError, ValueError):
            plays = 1
        session_state[KARAOKE_ENTRY_PLAYS_LEFT_KEY] = plays


def get_queue_pick_keys(session_state: Any) -> list[str]:
    return [str(e.get("pick_key") or "") for e in get_queue(session_state)]


def queue_length(session_state: Any) -> int:
    return len(get_queue(session_state))


def entry_by_id(session_state: Any, entry_id: str) -> dict[str, Any] | None:
    eid = str(entry_id or "").strip()
    if not eid:
        return None
    for entry in get_queue(session_state):
        if str(entry.get("entry_id") or "") == eid:
            return copy.deepcopy(entry)
    return None


def is_in_queue(session_state: Any, pick_key: str) -> bool:
    """True if *any* entry uses this pick_key (duplicates still count as in-queue)."""
    return bool(pick_key) and pick_key in get_queue_pick_keys(session_state)


def count_pick_key_in_queue(session_state: Any, pick_key: str) -> int:
    pk = str(pick_key or "")
    return sum(1 for e in get_queue(session_state) if str(e.get("pick_key") or "") == pk)


def _snapshot_practice_key(session_state: Any, pick_key: str) -> str:
    """Capture the live Practice Concert Key for a new karaoke entry."""
    try:
        from songs.practice_key_state import get_practice_concert_key

        saved = get_practice_concert_key(session_state, pick_key, default="")
        if saved:
            return str(saved).strip()
    except Exception:
        pass
    # Fallbacks: live sidebar / display key / original song key fields
    for key in (
        "practice_concert_key",
        "display_key",
        "practice_key",
        "song_key",
    ):
        val = str((session_state or {}).get(key) or "").strip()
        if val:
            return val
    sel = (session_state or {}).get("selected_song")
    if isinstance(sel, dict):
        for key in ("practice_key", "key", "original_key"):
            val = str(sel.get(key) or "").strip()
            if val:
                return val
    return ""


def add_to_queue(
    session_state: Any,
    pick_key: str,
    *,
    practice_key: str | None = None,
    play_count: int = 1,
    title: str = "",
    artist: str = "",
    source: str = "",
) -> dict[str, Any] | None:
    """Append a new karaoke entry (duplicates allowed).

    Snapshots ``practice_key`` at add time. Later global Practice Key
    changes do not rewrite this entry.
    """
    pk = str(pick_key or "").strip()
    if not pk:
        return None
    snap = str(practice_key).strip() if practice_key is not None else _snapshot_practice_key(session_state, pk)
    try:
        plays = max(1, int(play_count or 1))
    except (TypeError, ValueError):
        plays = 1
    entry = normalize_karaoke_entry(
        {
            "entry_id": _new_entry_id(),
            "pick_key": pk,
            "source": source or _infer_source(pk),
            "practice_key": snap,
            "play_count": plays,
            "title": title,
            "artist": artist,
        }
    )
    if not entry:
        return None
    queue = get_queue(session_state)
    queue.append(entry)
    _write_queue(session_state, queue)
    return copy.deepcopy(entry)


def add_many_to_queue(session_state: Any, pick_keys: Iterable[str]) -> int:
    """Append a batch of pick_keys as separate entries. Returns count added."""
    added = 0
    for pk in pick_keys:
        if add_to_queue(session_state, pk):
            added += 1
    return added


def remove_from_queue(session_state: Any, pick_key_or_entry_id: str) -> bool:
    """Remove by ``entry_id``, or the first matching ``pick_key`` (legacy)."""
    token = str(pick_key_or_entry_id or "").strip()
    if not token:
        return False
    queue = get_queue(session_state)
    remove_idx = -1
    for i, entry in enumerate(queue):
        if str(entry.get("entry_id") or "") == token or str(entry.get("pick_key") or "") == token:
            remove_idx = i
            break
    if remove_idx < 0:
        return False
    removed = queue.pop(remove_idx)
    _write_queue(session_state, queue)
    if session_state.get(KARAOKE_SESSION_ACTIVE_KEY):
        idx = int(session_state.get(KARAOKE_SESSION_INDEX_KEY, 0) or 0)
        if remove_idx < idx:
            session_state[KARAOKE_SESSION_INDEX_KEY] = max(0, idx - 1)
        elif remove_idx == idx:
            session_state[KARAOKE_SESSION_INDEX_KEY] = min(idx, max(0, len(queue) - 1))
            if queue:
                _activate_entry_at(session_state, int(session_state[KARAOKE_SESSION_INDEX_KEY]))
        if not queue:
            stop_session(session_state)
        # If we removed the active entry id, refresh pointer
        if str(session_state.get(KARAOKE_ACTIVE_ENTRY_ID_KEY) or "") == str(removed.get("entry_id") or ""):
            if queue and is_karaoke_session_active(session_state):
                _activate_entry_at(session_state, int(session_state.get(KARAOKE_SESSION_INDEX_KEY, 0) or 0))
    return True


def remove_entry_at(session_state: Any, index: int) -> bool:
    queue = get_queue(session_state)
    if index < 0 or index >= len(queue):
        return False
    return remove_from_queue(session_state, str(queue[index].get("entry_id") or ""))


def move_in_queue(session_state: Any, pick_key_or_entry_id: str, direction: int) -> bool:
    """Swap an entry with its neighbour. Prefers ``entry_id`` match."""
    if direction not in (-1, 1):
        return False
    token = str(pick_key_or_entry_id or "").strip()
    queue = get_queue(session_state)
    idx = -1
    for i, entry in enumerate(queue):
        if str(entry.get("entry_id") or "") == token:
            idx = i
            break
    if idx < 0:
        for i, entry in enumerate(queue):
            if str(entry.get("pick_key") or "") == token:
                idx = i
                break
    if idx < 0:
        return False
    new_idx = idx + direction
    if new_idx < 0 or new_idx >= len(queue):
        return False
    queue[idx], queue[new_idx] = queue[new_idx], queue[idx]
    _write_queue(session_state, queue)
    if session_state.get(KARAOKE_SESSION_ACTIVE_KEY):
        active_id = str(session_state.get(KARAOKE_ACTIVE_ENTRY_ID_KEY) or "")
        if active_id:
            for i, entry in enumerate(queue):
                if str(entry.get("entry_id") or "") == active_id:
                    session_state[KARAOKE_SESSION_INDEX_KEY] = i
                    break
    return True


def move_entry_at(session_state: Any, index: int, direction: int) -> bool:
    queue = get_queue(session_state)
    if index < 0 or index >= len(queue):
        return False
    return move_in_queue(session_state, str(queue[index].get("entry_id") or ""), direction)


def clear_queue(session_state: Any) -> None:
    """Empty the karaoke queue (also ends any active session)."""
    session_state[KARAOKE_QUEUE_KEY] = []
    stop_session(session_state)


def set_entry_play_count(session_state: Any, entry_id: str, play_count: int) -> bool:
    queue = get_queue(session_state)
    eid = str(entry_id or "").strip()
    try:
        plays = max(1, int(play_count))
    except (TypeError, ValueError):
        return False
    for entry in queue:
        if str(entry.get("entry_id") or "") == eid:
            entry["play_count"] = plays
            _write_queue(session_state, queue)
            return True
    return False


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


def is_karaoke_session_active(session_state: Any) -> bool:
    return bool((session_state or {}).get(KARAOKE_SESSION_ACTIVE_KEY))


def session_position(session_state: Any) -> tuple[int, int]:
    total = queue_length(session_state)
    if not is_karaoke_session_active(session_state):
        return (0, total)
    idx = int(session_state.get(KARAOKE_SESSION_INDEX_KEY, 0) or 0)
    return (max(0, min(idx, max(total - 1, 0))) + 1, total)


def current_session_entry(session_state: Any) -> dict[str, Any] | None:
    if not is_karaoke_session_active(session_state):
        return None
    queue = get_queue(session_state)
    if not queue:
        return None
    idx = int(session_state.get(KARAOKE_SESSION_INDEX_KEY, 0) or 0)
    if 0 <= idx < len(queue):
        return copy.deepcopy(queue[idx])
    return None


def current_session_pick_key(session_state: Any) -> str | None:
    entry = current_session_entry(session_state)
    if not entry:
        return None
    pk = str(entry.get("pick_key") or "").strip()
    return pk or None


def current_session_practice_key(session_state: Any) -> str:
    entry = current_session_entry(session_state)
    if not entry:
        return ""
    return str(entry.get("practice_key") or "").strip()


def next_session_entry(session_state: Any) -> dict[str, Any] | None:
    if not is_karaoke_session_active(session_state):
        return None
    queue = get_queue(session_state)
    if not queue:
        return None
    idx = int(session_state.get(KARAOKE_SESSION_INDEX_KEY, 0) or 0)
    nxt = idx + 1
    if 0 <= nxt < len(queue):
        return copy.deepcopy(queue[nxt])
    return None


def next_session_pick_key(session_state: Any) -> str | None:
    entry = next_session_entry(session_state)
    if not entry:
        return None
    pk = str(entry.get("pick_key") or "").strip()
    return pk or None


def apply_entry_practice_key(session_state: Any, entry: dict[str, Any] | None = None) -> str:
    """Apply a karaoke entry's Practice Key snapshot to live practice state.

    Writes the snapshot into ``practice_key_by_source`` for the entry's
    pick_key so backing/charts resolve to that key for this playthrough.
    Does not mutate other karaoke entries.
    """
    row = entry if isinstance(entry, dict) else current_session_entry(session_state)
    if not row:
        return ""
    pick_key = str(row.get("pick_key") or "").strip()
    key = str(row.get("practice_key") or "").strip()
    if not pick_key or not key:
        return key
    try:
        from songs.practice_key_state import set_practice_concert_key

        set_practice_concert_key(session_state, key, pick_key=pick_key)
    except Exception:
        session_state["practice_concert_key"] = key
    session_state["practice_concert_key"] = key
    return key


def _activate_entry_at(session_state: Any, index: int) -> str | None:
    queue = get_queue(session_state)
    if not queue or index < 0 or index >= len(queue):
        return None
    entry = queue[index]
    session_state[KARAOKE_SESSION_INDEX_KEY] = index
    session_state["_karaoke_active_pick_key"] = str(entry.get("pick_key") or "")
    session_state[KARAOKE_ACTIVE_ENTRY_ID_KEY] = str(entry.get("entry_id") or "")
    try:
        plays = max(1, int(entry.get("play_count") or 1))
    except (TypeError, ValueError):
        plays = 1
    session_state[KARAOKE_ENTRY_PLAYS_LEFT_KEY] = plays
    apply_entry_practice_key(session_state, entry)
    return str(entry.get("pick_key") or "") or None


def start_session(
    session_state: Any,
    *,
    starting_pick_key: str | None = None,
    starting_entry_id: str | None = None,
) -> str | None:
    """Begin a karaoke performance. Returns the active pick_key."""
    queue = get_queue(session_state)
    if not queue:
        return None
    start_idx = 0
    if starting_entry_id:
        for i, entry in enumerate(queue):
            if str(entry.get("entry_id") or "") == str(starting_entry_id):
                start_idx = i
                break
    elif starting_pick_key:
        for i, entry in enumerate(queue):
            if str(entry.get("pick_key") or "") == str(starting_pick_key):
                start_idx = i
                break
    session_state[KARAOKE_SESSION_ACTIVE_KEY] = True
    session_state.pop(KARAOKE_SONG_ENDED_KEY, None)
    session_state.pop(PENDING_KARAOKE_ADVANCE_KEY, None)
    session_state.setdefault(KARAOKE_AUTO_ADVANCE_KEY, True)
    return _activate_entry_at(session_state, start_idx)


def stop_session(session_state: Any) -> None:
    """End the karaoke performance (queue is left intact)."""
    session_state[KARAOKE_SESSION_ACTIVE_KEY] = False
    session_state.pop("_karaoke_active_pick_key", None)
    session_state.pop(KARAOKE_ACTIVE_ENTRY_ID_KEY, None)
    session_state.pop(KARAOKE_ENTRY_PLAYS_LEFT_KEY, None)
    session_state.pop(KARAOKE_SONG_ENDED_KEY, None)
    session_state.pop(PENDING_KARAOKE_ADVANCE_KEY, None)
    session_state.pop(KARAOKE_TRANSITION_LABEL_KEY, None)


def advance_session(session_state: Any) -> str | None:
    """Advance within play_count, then to the next queued entry."""
    queue = get_queue(session_state)
    if not queue or not is_karaoke_session_active(session_state):
        return None
    left = int(session_state.get(KARAOKE_ENTRY_PLAYS_LEFT_KEY) or 1)
    if left > 1:
        session_state[KARAOKE_ENTRY_PLAYS_LEFT_KEY] = left - 1
        session_state.pop(KARAOKE_SONG_ENDED_KEY, None)
        session_state.pop(PENDING_KARAOKE_ADVANCE_KEY, None)
        session_state[PENDING_KARAOKE_AUTO_GENERATE_KEY] = True
        # Re-apply the same entry's key for the next playthrough.
        apply_entry_practice_key(session_state, current_session_entry(session_state))
        return current_session_pick_key(session_state)

    idx = int(session_state.get(KARAOKE_SESSION_INDEX_KEY, 0) or 0)
    nxt = idx + 1
    if nxt >= len(queue):
        session_state[KARAOKE_TRANSITION_LABEL_KEY] = "Setlist complete"
        stop_session(session_state)
        return None
    session_state.pop(KARAOKE_SONG_ENDED_KEY, None)
    session_state.pop(PENDING_KARAOKE_ADVANCE_KEY, None)
    session_state[PENDING_KARAOKE_AUTO_GENERATE_KEY] = True
    return _activate_entry_at(session_state, nxt)


def regress_session(session_state: Any) -> str | None:
    """Step back to the previous queued entry."""
    queue = get_queue(session_state)
    if not queue or not is_karaoke_session_active(session_state):
        return None
    idx = int(session_state.get(KARAOKE_SESSION_INDEX_KEY, 0) or 0)
    prev_idx = idx - 1
    if prev_idx < 0:
        return None
    session_state.pop(KARAOKE_SONG_ENDED_KEY, None)
    session_state.pop(PENDING_KARAOKE_ADVANCE_KEY, None)
    session_state[PENDING_KARAOKE_AUTO_GENERATE_KEY] = True
    return _activate_entry_at(session_state, prev_idx)


def previous_session_pick_key(session_state: Any) -> str | None:
    if not is_karaoke_session_active(session_state):
        return None
    queue = get_queue(session_state)
    if not queue:
        return None
    idx = int(session_state.get(KARAOKE_SESSION_INDEX_KEY, 0) or 0)
    if idx - 1 < 0:
        return None
    return str(queue[idx - 1].get("pick_key") or "") or None


def upcoming_session_pick_keys(session_state: Any, *, limit: int = 3) -> list[str]:
    if not is_karaoke_session_active(session_state):
        return []
    queue = get_queue(session_state)
    idx = int(session_state.get(KARAOKE_SESSION_INDEX_KEY, 0) or 0)
    return [str(e.get("pick_key") or "") for e in queue[idx + 1 : idx + 1 + max(0, int(limit))]]


def upcoming_session_entries(session_state: Any, *, limit: int = 3) -> list[dict[str, Any]]:
    if not is_karaoke_session_active(session_state):
        return []
    queue = get_queue(session_state)
    idx = int(session_state.get(KARAOKE_SESSION_INDEX_KEY, 0) or 0)
    return [copy.deepcopy(e) for e in queue[idx + 1 : idx + 1 + max(0, int(limit))]]


# ---------------------------------------------------------------------------
# Countdown / prefs
# ---------------------------------------------------------------------------


def countdown_enabled(session_state: Any) -> bool:
    raw = (session_state or {}).get(KARAOKE_COUNTDOWN_KEY)
    if raw is None:
        return True
    return bool(raw)


def countdown_seconds(session_state: Any) -> int:
    raw = (session_state or {}).get(KARAOKE_COUNTDOWN_SECONDS_KEY)
    try:
        if raw is None:
            return 5
        n = int(raw)
    except (TypeError, ValueError):
        return 5
    return max(1, min(10, n))


def consume_pending_auto_generate(session_state: Any) -> bool:
    return bool(session_state.pop(PENDING_KARAOKE_AUTO_GENERATE_KEY, False))


def auto_advance_enabled(session_state: Any) -> bool:
    raw = (session_state or {}).get(KARAOKE_AUTO_ADVANCE_KEY)
    if raw is None:
        return True
    return bool(raw)


def show_chords_enabled(session_state: Any) -> bool:
    raw = (session_state or {}).get(KARAOKE_SHOW_CHORDS_KEY)
    if raw is None:
        return True
    return bool(raw)


_LYRIC_COLOR_OPTIONS = ("white", "gold", "cyan", "cream")


def lyric_color(session_state: Any) -> str:
    raw = (session_state or {}).get(KARAOKE_LYRIC_COLOR_KEY)
    token = str(raw or "").strip().lower()
    if token in _LYRIC_COLOR_OPTIONS:
        return token
    return "white"


def request_advance(session_state: Any, *, reason: str = "user") -> None:
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
    if not session_state.pop(PENDING_KARAOKE_ADVANCE_KEY, False):
        return None
    return advance_session(session_state)


def note_song_ended(session_state: Any) -> None:
    """JS bridge / player marks the current track finished."""
    if not is_karaoke_session_active(session_state):
        return
    session_state[KARAOKE_SONG_ENDED_KEY] = True
    if auto_advance_enabled(session_state):
        request_advance(session_state, reason="audio_ended")


_VOICE_WORDING: dict[str, dict[str, str]] = {
    "backing_page_title": {"default": "Backing Track", "voice": "Vocal Performance Mode"},
    "backing_page_subtitle": {
        "default": "Generate accompaniment matched to your active song - then play along.",
        "voice": (
            "Sing along to a backing track shaped for your voice - "
            "phrasing, breath, and emotional delivery first."
        ),
    },
    "backing_kicker": {
        "default": "Active song · Backing Track",
        "voice": "Now Singing · Vocal Performance",
    },
    "active_song_kicker": {"default": "Active Song", "voice": "Now Singing"},
    "queue_section_title": {
        "default": "Performance Setlist",
        "voice": "Karaoke Performance Setlist",
    },
    "queue_empty_caption": {
        "default": "Add songs from the catalog below to build your setlist.",
        "voice": (
            "Build your karaoke setlist — each entry keeps the Practice Key "
            "from the sidebar at the moment you add it."
        ),
    },
    "add_to_queue_button": {"default": "Add to Setlist", "voice": "Add to Karaoke Queue"},
    "remove_from_queue": {"default": "Remove", "voice": "Remove from Setlist"},
    "start_session_button": {"default": "Start Performance", "voice": "Start Karaoke Set"},
    "stop_session_button": {"default": "End Performance", "voice": "End Karaoke Set"},
    "continue_button": {"default": "Continue to next song", "voice": "Continue to next song"},
    "next_up_label": {"default": "Up next", "voice": "Next on the setlist"},
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
    """Return CSS modifier classes to layer on top of the base class string."""
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


def record_vocal_score(
    session_state: Any,
    pick_key: str = "",
    *,
    accuracy: float = 0.0,
    breath_score: float | None = None,
    phrasing_score: float | None = None,
    **kwargs: Any,
) -> None:
    """Reserved hook for vocal scoring / pitch tracking (no-op)."""
    return None


def set_vocal_focus_target(
    session_state: Any,
    *,
    target: str | None = None,
    **kwargs: Any,
) -> None:
    """Reserved hook for vocal practice focus (no-op)."""
    return None


def entry_display_line(entry: dict[str, Any] | None) -> str:
    """Compact setlist label: Title — Practice Key (×N)."""
    if not isinstance(entry, dict):
        return ""
    title = str(entry.get("title") or "").strip()
    if not title:
        pk = str(entry.get("pick_key") or "")
        title = pk.split("\x1f", 1)[-1] if "\x1f" in pk else pk
        if title.startswith("custom::"):
            title = title.removeprefix("custom::").replace("_", " ")
        if " — " in title:
            title = title.split(" — ", 1)[0].strip()
    key = str(entry.get("practice_key") or "").strip() or "?"
    try:
        plays = max(1, int(entry.get("play_count") or 1))
    except (TypeError, ValueError):
        plays = 1
    base = f"{title} — Practice Key: {key}"
    if plays > 1:
        base = f"{base} — Play {plays}×"
    return base

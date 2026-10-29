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


def _state(session_state: Any) -> Any:
    """``session_state``, or ``{}`` for None.

    Not ``session_state or {}``: the truth test of st.session_state calls its
    ``__len__``, which builds a filtered copy of the whole session. These
    helpers run many times per Karaoke rerun, and that copying measured about a
    third of every Karaoke Backing run (the old song stayed on screen while it
    ran).
    """
    return {} if session_state is None else session_state


def is_voice_mode(session_state: Any) -> bool:
    """Return ``True`` when the active instrument is Voice (or an alias)."""
    instrument = str(_state(session_state).get("instrument") or "").strip().lower()
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
# One-shot: the next Backing render starts the Now Singing song at its own tempo.
KARAOKE_TEMPO_RESET_PENDING_KEY = "_karaoke_tempo_reset_pending"
# Bumped on every singing transition so a late outgoing WAV cannot install.
KARAOKE_PLAYBACK_GENERATION_KEY = "_karaoke_playback_generation"
# Carries an open Lead Sheet across a singing transition (a new Backing source).
KARAOKE_SHEET_FOLLOW_KEY = "_karaoke_sheet_follow"
KARAOKE_ENTRY_PLAYS_LEFT_KEY = "_karaoke_entry_plays_left"
"""Remaining playthroughs for the current entry (includes the current play)."""

KARAOKE_ACTIVE_ENTRY_ID_KEY = "_karaoke_active_entry_id"
KARAOKE_EDITING_ENTRY_ID_KEY = "_karaoke_editing_entry_id"
KARAOKE_EDITING_PICK_KEY = "_karaoke_editing_pick_key"
"""Pick key the user was editing on the Songs page before karaoke overrode the active song."""

PENDING_KARAOKE_LYRICS_NAV_KEY = "_pending_karaoke_lyrics_nav"
"""Deferred navigation flag: dict with pick_key, entry_id, target_page. Consumed pre-render."""

PENDING_KARAOKE_ENTRY_ACTIVATION_KEY = "_pending_karaoke_entry_activation"
"""Setlist row click: the entry to make Now Editing. Consumed pre-render, before widgets."""

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
            "bpm": 0,
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
    try:
        bpm = int(raw.get("bpm") or 0)
    except (TypeError, ValueError):
        bpm = 0
    return {
        "entry_id": entry_id,
        "pick_key": pick_key,
        "source": source,
        "practice_key": str(raw.get("practice_key") or practice_key or "").strip(),
        "play_count": plays,
        "title": str(raw.get("title") or title or "").strip(),
        "artist": str(raw.get("artist") or artist or "").strip(),
        "bpm": bpm if bpm > 0 else 0,
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
    raw = _state(session_state).get(KARAOKE_QUEUE_KEY)
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
    if session_state is None or (isinstance(session_state, dict) and not session_state):
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
        val = str(_state(session_state).get(key) or "").strip()
        if val:
            return val
    sel = _state(session_state).get("selected_song")
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
    bpm: int | None = None,
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
            "bpm": int(bpm) if bpm else 0,
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
    if str(session_state.get(KARAOKE_EDITING_ENTRY_ID_KEY) or "") == str(removed.get("entry_id") or ""):
        session_state.pop(KARAOKE_EDITING_ENTRY_ID_KEY, None)
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
    session_state.pop(KARAOKE_EDITING_ENTRY_ID_KEY, None)
    session_state.pop(KARAOKE_EDITING_PICK_KEY, None)
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
    return bool(_state(session_state).get(KARAOKE_SESSION_ACTIVE_KEY))


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


KARAOKE_GENERATION_ATTEMPT_KEY = "_karaoke_generation_attempt_sig"


def karaoke_take_requires_generation(
    session_state: Any,
    signature: Any,
    *,
    has_chords: bool,
    has_exact_wav: bool,
    has_exact_build: bool,
) -> bool:
    """Whether the Now Singing take must be generated now.

    A destination without its exact WAV either has a build for that exact
    signature in flight or needs generation; it must never settle at "no WAV,
    no build, no regeneration". True once per signature, so a build that fails
    does not retry forever.
    """
    if not has_chords or has_exact_wav or has_exact_build or signature is None:
        return False
    if session_state.get(KARAOKE_GENERATION_ATTEMPT_KEY) == signature:
        return False
    session_state[KARAOKE_GENERATION_ATTEMPT_KEY] = signature
    return True


def bump_karaoke_playback_generation(session_state: Any) -> int:
    """Retire the outgoing take. A later install must carry this generation."""
    try:
        n = int(_state(session_state).get(KARAOKE_PLAYBACK_GENERATION_KEY) or 0) + 1
    except (TypeError, ValueError):
        n = 1
    session_state[KARAOKE_PLAYBACK_GENERATION_KEY] = n
    return n


def karaoke_take_install_allowed(session_state: Any, started_entry_id: str) -> bool:
    """False when a render started for a singing entry that is no longer current."""
    if not is_karaoke_session_active(session_state) or not is_voice_mode(session_state):
        return True
    started = str(started_entry_id or "").strip()
    if not started:
        return True
    return started == str(session_state.get(KARAOKE_ACTIVE_ENTRY_ID_KEY) or "")


def resolve_karaoke_entry_bpm(session_state: Any, entry: dict[str, Any] | None = None) -> int:
    """BPM owned by one Karaoke entry. Never the live slider or another source.

    Stored entry BPM wins. Otherwise the destination's own Catalog row, Custom
    progression, or Composition document. Global ``backing_track_bpm``, the
    outgoing play session, and a title lookup are not consulted.
    """
    row = entry if isinstance(entry, dict) else current_session_entry(session_state)
    if not isinstance(row, dict):
        return 0
    try:
        stored = int(row.get("bpm") or 0)
    except (TypeError, ValueError):
        stored = 0
    if stored > 0:
        return stored
    pick = str(row.get("pick_key") or "").strip()
    if not pick:
        return 0
    if pick.startswith("custom::"):
        try:
            from songs.music_source import custom_progression_for_pick_key

            prog = custom_progression_for_pick_key(session_state, pick) or {}
            bpm = int(prog.get("bpm") or 0)
        except Exception:
            bpm = 0
        return bpm if bpm > 0 else 0
    if pick.startswith("composition::"):
        try:
            from composition_songs_bridge import find_composition_document, playback_globals

            doc = find_composition_document(session_state, pick)
            bpm = int((playback_globals(doc) or {}).get("bpm") or 0) if isinstance(doc, dict) else 0
        except Exception:
            bpm = 0
        return bpm if bpm > 0 else 0
    try:
        from songs.music_source import catalog_transport_bpm_for_pick

        return int(catalog_transport_bpm_for_pick(session_state, pick) or 0)
    except Exception:
        return 0


def karaoke_display_lyrics(
    session_state: Any,
    *,
    song_library: dict | None = None,
    song_picker_catalog: dict | None = None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Lyrics for Now Singing, or None when Karaoke is not performing.

    Empty dicts mean the destination has no lyrics. Callers must not keep the
    outgoing song's lines, and must not read Now Editing's lyrics instead.
    """
    if not is_karaoke_session_active(session_state) or not is_voice_mode(session_state):
        return None
    if str(_state(session_state).get("studio_page") or "").strip().lower() == "picker":
        return None
    entry = current_session_entry(session_state) or {}
    pick = str(entry.get("pick_key") or "").strip()
    if not pick:
        return {}, {}
    if pick.startswith("composition::"):
        doc: dict | None = None
        try:
            from composition_songs_bridge import (
                composition_section_lyrics,
                composition_section_lyrics_alignment,
                find_composition_document,
            )

            doc = find_composition_document(session_state, pick)
            lyrics = composition_section_lyrics(doc) if isinstance(doc, dict) else {}
        except Exception:
            lyrics = {}
        cues: dict[str, list[str]] = {}
        if isinstance(doc, dict) and lyrics:
            try:
                alignments = composition_section_lyrics_alignment(doc)
                for sec_key, alignment in alignments.items():
                    syllables = alignment.get("syllables") or []
                    if not syllables:
                        continue
                    lines: list[str] = []
                    current: list[str] = []
                    for syl in syllables:
                        current.append(str(syl.get("text") or ""))
                        if syl.get("is_line_end"):
                            line = " ".join(
                                t for t in current if t
                            ).replace(" -", "-").replace("- ", "-")
                            if line.strip():
                                lines.append(line.strip())
                            current = []
                    if current:
                        line = " ".join(
                            t for t in current if t
                        ).replace(" -", "-").replace("- ", "-")
                        if line.strip():
                            lines.append(line.strip())
                    if lines:
                        cues[sec_key] = lines
            except Exception:
                pass
        if not cues and lyrics:
            for sec_key, text in lyrics.items():
                lines = [ln.strip() for ln in str(text).splitlines() if ln.strip()]
                if lines:
                    cues[sec_key] = lines
        return dict(lyrics or {}), cues
    if pick.startswith("custom::"):
        return {}, {}
    title = str(entry.get("title") or "").strip()
    artist = str(entry.get("artist") or "").strip()
    song_data: dict[str, Any] = {}
    ctx = karaoke_song_context(
        session_state,
        song_library or {},
        song_picker_catalog or {},
    )
    if ctx:
        _genre, ctx_title, ctx_data = ctx
        song_data = dict(ctx_data or {})
        title = str(song_data.get("title") or ctx_title or title).strip()
        artist = str(song_data.get("artist") or artist).strip()
    try:
        from songs.user_lyrics_runtime import resolve_user_lyrics_and_cues

        section_lyrics, cues, _notes = resolve_user_lyrics_and_cues(
            session_state,
            title=title,
            artist=artist,
            song_data=song_data or {"title": title, "artist": artist, "pick_key": pick},
            include_catalog_cues=bool((song_data or {}).get("trusted_core")),
        )
        return dict(section_lyrics or {}), dict(cues or {})
    except Exception:
        return {}, {}


def now_singing_entry_id(session_state: Any) -> str:
    """Entry ID for the Now Singing marker, valid even when session is stopped."""
    return str(session_state.get(KARAOKE_ACTIVE_ENTRY_ID_KEY) or "")


def now_singing_pick_key(session_state: Any) -> str:
    """Pick key of the Now Singing entry, valid even when session is stopped."""
    return str(session_state.get("_karaoke_active_pick_key") or "")


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
        from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY

        store = session_state.setdefault(PRACTICE_KEY_BY_SOURCE_KEY, {})
        store[pick_key] = key
    except Exception:
        pass
    return key


def karaoke_key_identity(key: Any) -> str:
    """Normalized Practice Key identity: tonic + mode (A != Am, Gb == F#)."""
    raw = str(key or "").strip()
    if not raw:
        return ""
    try:
        from music_theory import normalize_root, split_key_center

        tonic, mode = split_key_center(raw)
        return f"{normalize_root(tonic)}|{mode}"
    except Exception:
        return raw


def entry_selection_identity(entry: dict[str, Any] | None) -> str:
    """``song pick | key identity`` for one setlist entry."""
    row = entry if isinstance(entry, dict) else {}
    pick = str(row.get("pick_key") or "").strip()
    return f"{pick}||{karaoke_key_identity(row.get('practice_key'))}" if pick else ""


def global_selection_identity(session_state: Any) -> str:
    """``song pick | key identity`` of the global active song at its Practice Key."""
    pick = str(_state(session_state).get("active_catalog_pick_key") or "").strip()
    if not pick:
        return ""
    key = ""
    try:
        from songs.practice_key_state import get_practice_concert_key

        key = str(get_practice_concert_key(session_state, pick, default="") or "").strip()
    except Exception:
        key = ""
    if not key:
        key = str(session_state.get("display_key") or "").strip()
    return f"{pick}||{karaoke_key_identity(key)}"


def now_editing_entry_ids(session_state: Any) -> set[str]:
    """Setlist entries that ARE the global song at the global Practice Key.

    Normally one row; identical duplicates (same song, same key) all match.
    Same song in a different key does not.
    """
    target = global_selection_identity(session_state)
    if not target:
        return set()
    return {
        str(e.get("entry_id") or "")
        for e in get_queue(session_state)
        if entry_selection_identity(e) == target
    }


def commit_entry_practice_key(session_state: Any, entry: dict[str, Any] | None) -> str:
    """Make the entry's Practice Key the active song's own Practice Key.

    Same commit a sidebar Practice Key change makes for a Catalog song: the
    per-song store (durable), the user-override mark, the commit token for this
    pick, and the queued display key for the next widget render.
    """
    row = entry if isinstance(entry, dict) else {}
    pick = str(row.get("pick_key") or "").strip()
    key = str(row.get("practice_key") or "").strip()
    if not pick or not key:
        return ""
    try:
        from songs.practice_key_state import mark_practice_key_user_override, set_practice_concert_key

        mark_practice_key_user_override(session_state, pick)
        set_practice_concert_key(
            session_state,
            key,
            pick_key=pick,
            allow_restore_original=True,
            commit_catalog_practice_key=True,
        )
    except Exception:
        apply_entry_practice_key(session_state, row)
    session_state["_pk_user_commit_token"] = key
    session_state["_pk_user_commit_pick"] = pick
    session_state["concert_key"] = key
    try:
        # An explicit song + key selection makes the shared Catalog Backing
        # widget's leftover value foreign even for the same song (Perfect G ->
        # Perfect A): forget whose value it holds, so Backing seeds from this key.
        from backing_practice_key_control import CATALOG_BACKING_PK_WIDGET_PICK_KEY

        session_state.pop(CATALOG_BACKING_PK_WIDGET_PICK_KEY, None)
    except Exception:
        pass
    try:
        from songs.key_state import request_display_key

        request_display_key(session_state, key)
    except Exception:
        pass
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
    # Now Singing only: Karaoke Backing reads this entry's own key through
    # current_session_practice_key. Writing it into the song's shared Practice
    # Key store would rewrite Now Editing when the same song is being edited in
    # another key (Perfect G edited while Perfect A sings).
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
    session_state[PENDING_KARAOKE_AUTO_GENERATE_KEY] = True
    session_state.pop("_pending_matching_song_dropdown", None)
    session_state.pop("_pending_catalog_pick_key", None)
    session_state.pop("_pending_catalog_from_picker", None)
    return _activate_entry_at(session_state, start_idx)


def stop_session(session_state: Any) -> None:
    """End the karaoke performance (queue is left intact).

    Resets Now Singing to the first queued entry so the setlist panel
    shows where the next performance would start from.
    """
    session_state[KARAOKE_SESSION_ACTIVE_KEY] = False
    session_state.pop(KARAOKE_ENTRY_PLAYS_LEFT_KEY, None)
    session_state.pop(KARAOKE_SONG_ENDED_KEY, None)
    session_state.pop(PENDING_KARAOKE_ADVANCE_KEY, None)
    session_state.pop(KARAOKE_TRANSITION_LABEL_KEY, None)
    session_state.pop(KARAOKE_SHEET_FOLLOW_KEY, None)
    queue = get_queue(session_state)
    if queue:
        first = queue[0]
        session_state[KARAOKE_SESSION_INDEX_KEY] = 0
        session_state["_karaoke_active_pick_key"] = str(first.get("pick_key") or "")
        session_state[KARAOKE_ACTIVE_ENTRY_ID_KEY] = str(first.get("entry_id") or "")
    else:
        session_state.pop("_karaoke_active_pick_key", None)
        session_state.pop(KARAOKE_ACTIVE_ENTRY_ID_KEY, None)
        session_state.pop(KARAOKE_SESSION_INDEX_KEY, None)


def rewind_session_to_first_entry(session_state: Any) -> str | None:
    """Stop Backing Track in Karaoke: Now Singing returns to the first entry.

    The set stays open (Karaoke Backing keeps showing it) but nothing is armed:
    the next Play starts the setlist again from that entry.
    """
    if not is_karaoke_session_active(session_state):
        return None
    session_state.pop(PENDING_KARAOKE_AUTO_GENERATE_KEY, None)
    session_state.pop(KARAOKE_SONG_ENDED_KEY, None)
    session_state.pop(PENDING_KARAOKE_ADVANCE_KEY, None)
    session_state.pop(KARAOKE_TRANSITION_LABEL_KEY, None)
    return _activate_entry_at(session_state, 0)


def advance_session(session_state: Any, *, skip_repeats: bool = False) -> str | None:
    """Advance within play_count, then to the next queued entry.

    ``skip_repeats`` is the explicit "Skip to next song": it moves to the next
    setlist entry even when this entry still has plays left. Natural end of a
    song keeps playing the entry's remaining repeats.
    """
    queue = get_queue(session_state)
    if not queue or not is_karaoke_session_active(session_state):
        return None
    left = int(session_state.get(KARAOKE_ENTRY_PLAYS_LEFT_KEY) or 1)
    if left > 1 and not skip_repeats:
        session_state[KARAOKE_ENTRY_PLAYS_LEFT_KEY] = left - 1
        session_state.pop(KARAOKE_SONG_ENDED_KEY, None)
        session_state.pop(PENDING_KARAOKE_ADVANCE_KEY, None)
        session_state[PENDING_KARAOKE_AUTO_GENERATE_KEY] = True
        # Same entry plays again; its key comes from the entry (Now Singing),
        # not the song's shared Practice Key store.
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
    raw = _state(session_state).get(KARAOKE_COUNTDOWN_KEY)
    if raw is None:
        return True
    return bool(raw)


def countdown_seconds(session_state: Any) -> int:
    raw = _state(session_state).get(KARAOKE_COUNTDOWN_SECONDS_KEY)
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
    raw = _state(session_state).get(KARAOKE_AUTO_ADVANCE_KEY)
    if raw is None:
        return True
    return bool(raw)


def show_chords_enabled(session_state: Any) -> bool:
    raw = _state(session_state).get(KARAOKE_SHOW_CHORDS_KEY)
    if raw is None:
        return True
    return bool(raw)


_LYRIC_COLOR_OPTIONS = ("white", "gold", "cyan", "cream")


def lyric_color(session_state: Any) -> str:
    raw = _state(session_state).get(KARAOKE_LYRIC_COLOR_KEY)
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


def entry_display_line(entry: dict[str, Any] | None, *, title_override: str | None = None) -> str:
    """Compact managed-setlist label: Title · Key [· Play N×].

    Uses the Practice Key **snapshot on the entry**, never the live sidebar key.
    """
    if not isinstance(entry, dict):
        return ""
    title = str(title_override if title_override is not None else entry.get("title") or "").strip()
    if not title:
        pk = str(entry.get("pick_key") or "")
        title = pk.split("\x1f", 1)[-1] if "\x1f" in pk else pk
        if title.startswith("custom::"):
            title = title.removeprefix("custom::").replace("_", " ")
        if title.startswith("composition::"):
            title = title.removeprefix("composition::").replace("_", " ")
        if " — " in title:
            title = title.split(" — ", 1)[0].strip()
    key = str(entry.get("practice_key") or "").strip() or "?"
    try:
        plays = max(1, int(entry.get("play_count") or 1))
    except (TypeError, ValueError):
        plays = 1
    base = f"{title} · {key}"
    if plays > 1:
        base = f"{base} · Play {plays}×"
    return base


def managed_setlist_display_rows(session_state: Any) -> list[dict[str, Any]]:
    """Stable view of queue rows for manage UI / tests (order, keys, labels)."""
    rows: list[dict[str, Any]] = []
    for idx, entry in enumerate(get_queue(session_state)):
        if not isinstance(entry, dict):
            continue
        try:
            plays = max(1, int(entry.get("play_count") or 1))
        except (TypeError, ValueError):
            plays = 1
        rows.append(
            {
                "index": idx,
                "entry_id": str(entry.get("entry_id") or ""),
                "pick_key": str(entry.get("pick_key") or ""),
                "practice_key": str(entry.get("practice_key") or "").strip(),
                "play_count": plays,
                "label": entry_display_line(entry),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Karaoke isolation helpers — Backing page reads these instead of global state
# ---------------------------------------------------------------------------


def effective_catalog_pick_key(session_state: Any) -> str:
    """Return the karaoke singing pick when active, else the global catalog pick.

    Backing infrastructure should call this instead of reading
    ``active_catalog_pick_key`` directly so the Backing page renders the
    karaoke song without overwriting the global Active Song.
    """
    if is_karaoke_session_active(session_state) and is_voice_mode(session_state):
        pk = current_session_pick_key(session_state)
        if pk:
            return pk
    return str(_state(session_state).get("active_catalog_pick_key") or "").strip()


def karaoke_song_context(
    session_state: Any,
    song_library: dict,
    song_picker_catalog: dict,
) -> tuple[str, str, dict] | None:
    """Resolve the current karaoke song's (genre, title, song_data) from the catalog.

    Returns ``None`` when karaoke is inactive or the pick cannot be resolved.
    """
    if not is_karaoke_session_active(session_state) or not is_voice_mode(session_state):
        return None
    pk = current_session_pick_key(session_state)
    if not pk:
        return None
    if pk.startswith("custom::"):
        # Custom and Composition entries have no catalog row; describe them
        # from their own saved progression / document (title and home key).
        try:
            from songs.music_source import custom_original_key, custom_progression_for_pick_key

            prog = custom_progression_for_pick_key(session_state, pk)
        except ImportError:
            prog = None
        if prog:
            title = str(prog.get("name") or "").strip() or "Custom Progression"
            return (
                "Custom",
                title,
                {
                    "title": title,
                    "artist": "Your progression",
                    "genre": "Custom",
                    "key": custom_original_key(prog),
                    "pick_key": pk,
                },
            )
    if pk.startswith("composition::"):
        try:
            from composition_songs_bridge import (
                composition_home_key,
                composition_title,
                find_composition_document,
            )

            doc = find_composition_document(session_state, pk)
        except ImportError:
            doc = None
        if doc:
            title = composition_title(doc)
            return (
                "Composition",
                title,
                {
                    "title": title,
                    "artist": "Composition",
                    "genre": "Composition",
                    "key": composition_home_key(doc),
                    "pick_key": pk,
                },
            )
    sep = "\x1f"
    if sep in pk:
        genre_part, title_part = pk.split(sep, 1)
        genre_songs = song_picker_catalog.get(genre_part)
        if isinstance(genre_songs, dict):
            for title, data in genre_songs.items():
                if title == title_part or str(data.get("pick_key") or "") == pk:
                    return (genre_part, title, data)
    for genre, songs in song_picker_catalog.items():
        if not isinstance(songs, dict):
            continue
        for title, data in songs.items():
            if str(data.get("pick_key") or "") == pk:
                return (genre, title, data)
    entry = current_session_entry(session_state)
    if entry:
        return (
            str(entry.get("genre") or ""),
            str(entry.get("title") or ""),
            dict(entry),
        )
    return None


# --- ownership diagnostics ---------------------------------------------------

GLOBAL_IDENTITY_KEYS = (
    "active_catalog_pick_key",
    "selected_song",
    "active_song_state",
    "practice_concert_key",
)

EXPLICIT_GLOBAL_CHANGE_KEY = "_karaoke_explicit_global_change"


def snapshot_global_identity(session_state: Any) -> dict[str, Any]:
    """Copy the global identity keys so a later check can detect a karaoke write."""
    return {k: copy.deepcopy(session_state.get(k)) for k in GLOBAL_IDENTITY_KEYS}


def audit_global_identity(
    session_state: Any,
    before: dict[str, Any],
    *,
    where: str = "",
) -> list[dict[str, Any]]:
    """Report global identity keys a karaoke run changed toward Now Singing.

    Karaoke owns no global identity. A difference here is an ownership
    violation unless an explicit editing action authorised it (setlist click or
    Add Lyrics, which set EXPLICIT_GLOBAL_CHANGE_KEY). Returns one record per
    offending key; empty means the boundary held.
    """
    if not is_karaoke_session_active(session_state) or not is_voice_mode(session_state):
        return []
    if session_state.get(EXPLICIT_GLOBAL_CHANGE_KEY):
        return []
    singing = str(current_session_pick_key(session_state) or "").strip()
    out: list[dict[str, Any]] = []
    def _identity(v: Any) -> str:
        """The song identity a value denotes, ignoring incidental fields."""
        if isinstance(v, dict):
            return str(v.get("pick_key") or v.get("title") or "")
        return str(v or "")

    for key in GLOBAL_IDENTITY_KEYS:
        now = session_state.get(key)
        was = before.get(key)
        # Compare song IDENTITY, not dict equality. Comparing whole dicts
        # reported every incidental field update (bpm, title spelling, groove)
        # as an ownership violation, which buried the real signal: a run of 52
        # alerts that all read "PopGravity -> PopGravity". Only a change of the
        # song a key denotes, or of the practice key itself, is a violation.
        if _identity(now) == _identity(was):
            continue
        record = {
            "where": str(where or ""),
            "key": key,
            "was": _identity(was)[-30:],
            "now": _identity(now)[-30:],
            "matches_now_singing": bool(singing and _identity(now) == singing),
        }
        out.append(record)
    return out


LYRICS_TARGET_REQUEST_KEY = "_karaoke_lyrics_target_request"


def record_lyrics_target_request(session_state: Any, pick_key: str, entry_id: str = "") -> None:
    """Remember which entry an explicit Add Lyrics action asked to edit.

    Survives the rerun that performs the navigation so the editor actually
    opened can be compared against what was requested. Cleared once verified.
    """
    pk = str(pick_key or "").strip()
    if not pk:
        return
    session_state[LYRICS_TARGET_REQUEST_KEY] = {
        "pick_key": pk,
        "entry_id": str(entry_id or ""),
    }


def audit_lyrics_target(session_state: Any, opened_pick_key: str) -> dict[str, Any] | None:
    """Compare the editor that opened against the Add Lyrics request.

    Returns a record when they disagree -- the "Add lyrics for Perfect opened
    Gravity" failure -- and None when they agree or nothing was requested. This
    catches the mismatch even though no global-state mutation is involved, so a
    silently retargeted editor cannot pass unnoticed. Consumes the request.
    """
    req = session_state.get(LYRICS_TARGET_REQUEST_KEY)
    if not isinstance(req, dict):
        return None
    want = str(req.get("pick_key") or "").strip()
    got = str(opened_pick_key or "").strip()
    if not want:
        session_state.pop(LYRICS_TARGET_REQUEST_KEY, None)
        return None
    if not got:
        return None                      # editor not resolved yet this run
    session_state.pop(LYRICS_TARGET_REQUEST_KEY, None)
    if want == got:
        return None
    return {
        "requested": want,
        "opened": got,
        "entry_id": str(req.get("entry_id") or ""),
    }


LAST_EXPLICIT_GLOBAL_KEY = "_karaoke_last_explicit_global"


def remember_explicit_global_selection(session_state: Any) -> None:
    """Record the global identity an explicit editing action just established.

    Lets a later run detect that the explicit selection was reverted, which a
    single-run baseline cannot see: returning to the Backing page appeared to
    snap the sidebar back to the current playlist entry.
    """
    sel = session_state.get("selected_song")
    pick = ""
    if isinstance(sel, dict):
        pick = str(sel.get("pick_key") or "")
    pick = pick or str(session_state.get("active_catalog_pick_key") or "")
    if not pick:
        return
    session_state[LAST_EXPLICIT_GLOBAL_KEY] = {
        "pick_key": pick,
        "practice_key": str(session_state.get("practice_concert_key") or ""),
    }


def audit_explicit_global_reverted(session_state: Any) -> dict[str, Any] | None:
    """Report that a remembered explicit global selection no longer holds.

    Returns None when nothing was remembered, when it still holds, or when a
    fresh explicit action is in flight. A hit means some non-explicit path
    rewrote the user's global editing selection.
    """
    remembered = session_state.get(LAST_EXPLICIT_GLOBAL_KEY)
    if not isinstance(remembered, dict):
        return None
    if session_state.get(EXPLICIT_GLOBAL_CHANGE_KEY):
        return None
    want = str(remembered.get("pick_key") or "").strip()
    if not want:
        return None
    sel = session_state.get("selected_song")
    live_sel = str(sel.get("pick_key") or "") if isinstance(sel, dict) else ""
    live_pick = str(session_state.get("active_catalog_pick_key") or "").strip()
    now_pick = live_sel or live_pick
    if not now_pick or now_pick == want:
        return None
    singing = str(current_session_pick_key(session_state) or "").strip()
    return {
        "expected": want[-30:],
        "actual": now_pick[-30:],
        "reverted_to_now_singing": bool(singing and now_pick == singing),
    }


KARAOKE_RENDER_GENERATION_KEY = "_karaoke_render_generation"


def render_generation(session_state: Any) -> str:
    """Identity of the current performance render: entry id + saved key + index.

    Components keyed by this remount when the entry changes, so the previous
    entry's mounted chart, chord grid or player cannot survive underneath the
    new entry's title. Derived only from the karaoke entry -- never from the
    global Active Song, so refreshing a performance surface never requires
    touching global identity.
    """
    stored = str(session_state.get(KARAOKE_RENDER_GENERATION_KEY) or "").strip()
    if stored:
        return stored
    entry = current_session_entry(session_state) or {}
    return "{}::{}::{}".format(
        str(entry.get("entry_id") or ""),
        str(entry.get("practice_key") or ""),
        int(session_state.get(KARAOKE_SESSION_INDEX_KEY) or 0),
    )

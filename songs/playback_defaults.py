"""Sync backing-track BPM and groove with the active song (catalog or CPL)."""

from __future__ import annotations

from typing import Any

from .bpm_state import BPM_WIDGET_KEY, LAST_BPM_SONG, PENDING_BACKING_TRACK_BPM, sync_backing_bpm_before_widget

BACKING_GROOVE_KEY = "backing_groove_style"
LAST_PLAYBACK_GROOVE_SONG = "_last_playback_groove_song"
PENDING_BACKING_GROOVE = "_pending_backing_groove"
PRACTICE_GROOVE_KEY = "practice_groove_style"


def default_groove_for_song(song_data: dict[str, Any] | None, *, infer_fn) -> str:
    """Resolve groove label from song metadata (extensions + genre)."""
    song_data = song_data or {}
    ext = song_data.get("extensions") or {}
    if ext.get("default_groove"):
        return str(ext["default_groove"])
    genre = str(song_data.get("genre") or "")
    if genre == "Pop":
        return "Pop groove"
    if genre == "Rock":
        return "Rock groove"
    if genre == "Jazz":
        return "Jazz swing"
    if genre in ("Funk", "Soul"):
        return "Funk groove"
    return infer_fn(song_data, "Auto")


def sync_backing_groove_before_widget(
    st: Any,
    song_id: str,
    default_groove: str,
) -> str:
    """Apply pending groove or song-change defaults before the groove widget exists."""
    pending = st.session_state.pop(PENDING_BACKING_GROOVE, None)
    song_changed = st.session_state.get(LAST_PLAYBACK_GROOVE_SONG) != song_id

    if song_changed:
        st.session_state[LAST_PLAYBACK_GROOVE_SONG] = song_id
        st.session_state[BACKING_GROOVE_KEY] = (
            pending if pending is not None else default_groove
        )
    elif pending is not None:
        st.session_state[BACKING_GROOVE_KEY] = pending
    elif BACKING_GROOVE_KEY not in st.session_state:
        st.session_state[BACKING_GROOVE_KEY] = default_groove

    return str(st.session_state[BACKING_GROOVE_KEY])


def request_backing_groove(st: Any, groove: str) -> None:
    st.session_state[PENDING_BACKING_GROOVE] = str(groove)


def playback_song_id(
    *,
    is_custom: bool,
    song_title: str,
    song_artist: str,
    custom_name: str = "",
    custom_revision: str = "",
) -> str:
    if is_custom:
        rev = custom_revision or custom_name or "custom"
        return f"cpl::{rev}"
    return f"cat::{song_title}::{song_artist}"


def sync_playback_defaults_for_active_song(
    st: Any,
    *,
    song_id: str,
    default_bpm: int,
    default_groove: str,
) -> tuple[int, str]:
    """Sync BPM + groove when the active song changes; preserve manual tweaks otherwise."""
    bpm = sync_backing_bpm_before_widget(st, song_id, int(default_bpm))
    groove = sync_backing_groove_before_widget(st, song_id, default_groove)
    if st.session_state.get(LAST_PLAYBACK_GROOVE_SONG) == song_id:
        st.session_state[PRACTICE_GROOVE_KEY] = groove
    return bpm, groove

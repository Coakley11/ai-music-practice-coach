"""Backing-track BPM session state — apply changes only before the BPM widget is built."""

from __future__ import annotations

from typing import Any

PENDING_BACKING_TRACK_BPM = "_pending_backing_track_bpm"
LAST_BPM_SONG = "_last_bpm_song"
BPM_WIDGET_KEY = "backing_track_bpm"


def sync_backing_bpm_before_widget(st: Any, song_title: str, default_bpm: int) -> int:
    """Apply pending BPM or song-change defaults before ``backing_track_bpm`` widget exists."""
    pending = st.session_state.pop(PENDING_BACKING_TRACK_BPM, None)
    song_changed = st.session_state.get(LAST_BPM_SONG) != song_title

    if song_changed:
        st.session_state[LAST_BPM_SONG] = song_title
        st.session_state[BPM_WIDGET_KEY] = pending if pending is not None else default_bpm
    elif pending is not None:
        st.session_state[BPM_WIDGET_KEY] = pending
    elif BPM_WIDGET_KEY not in st.session_state:
        st.session_state[BPM_WIDGET_KEY] = default_bpm

    return int(st.session_state[BPM_WIDGET_KEY])


def request_backing_bpm(st: Any, bpm: int) -> None:
    """Queue a BPM change for the next run (safe after the widget exists)."""
    st.session_state[PENDING_BACKING_TRACK_BPM] = int(bpm)

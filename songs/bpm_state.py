"""Backing-track BPM session state — apply changes only before the BPM widget is built."""

from __future__ import annotations

from typing import Any

PENDING_BACKING_TRACK_BPM = "_pending_backing_track_bpm"
LAST_BPM_SONG = "_last_bpm_song"
BPM_WIDGET_KEY = "backing_track_bpm"

BACKING_BPM_MIN = 20
BACKING_BPM_MAX = 180


def normalize_backing_bpm(bpm: int | float) -> int:
    """Clamp tempo to the backing-track slider range without resetting to song default."""
    try:
        val = int(round(float(bpm)))
    except (TypeError, ValueError):
        return 100
    return max(BACKING_BPM_MIN, min(BACKING_BPM_MAX, val))


def sync_backing_bpm_before_widget(st: Any, song_title: str, default_bpm: int) -> int:
    """Apply pending BPM or song-change defaults before ``backing_track_bpm`` widget exists."""
    pending = st.session_state.pop(PENDING_BACKING_TRACK_BPM, None)
    song_changed = st.session_state.get(LAST_BPM_SONG) != song_title

    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(st.session_state)
        if ctx is not None and str(getattr(ctx, "source", "") or "").strip() == "regular_song":
            ctx_bpm = int(getattr(ctx, "bpm", 0) or 0)
            if ctx_bpm > 0:
                default_bpm = ctx_bpm
                if int(st.session_state.get(BPM_WIDGET_KEY) or 0) != ctx_bpm:
                    pending = ctx_bpm
                    song_changed = True
    except ImportError:
        pass

    if song_changed and st.session_state.get(LAST_BPM_SONG) is None:
        try:
            from backing_track_state import backing_canonical_playback_seed

            canon_bpm, _ = backing_canonical_playback_seed(st.session_state)
            if canon_bpm is not None:
                st.session_state[LAST_BPM_SONG] = song_title
                st.session_state[BPM_WIDGET_KEY] = int(canon_bpm)
                return int(canon_bpm)
        except ImportError:
            pass

    if song_changed:
        st.session_state[LAST_BPM_SONG] = song_title
        st.session_state[BPM_WIDGET_KEY] = int(default_bpm)
    elif pending is not None:
        st.session_state[BPM_WIDGET_KEY] = pending
    elif BPM_WIDGET_KEY not in st.session_state:
        st.session_state[BPM_WIDGET_KEY] = default_bpm

    return int(st.session_state[BPM_WIDGET_KEY])


def request_backing_bpm(st: Any, bpm: int) -> None:
    """Queue a BPM change for the next run (safe after the widget exists)."""
    st.session_state[PENDING_BACKING_TRACK_BPM] = normalize_backing_bpm(bpm)

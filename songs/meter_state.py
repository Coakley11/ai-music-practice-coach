"""Backing-track time signature session state (song default + user override)."""

from __future__ import annotations

from typing import Any

from .meter import BACKING_TIME_SIGNATURES, normalize_time_signature

BACKING_METER_KEY = "backing_time_signature"
BACKING_METER_OVERRIDE_KEY = "backing_time_signature_override"
LAST_BACKING_METER_SONG = "_last_backing_meter_song"


def reset_backing_meter_tracking(st: Any) -> None:
    st.session_state.pop(LAST_BACKING_METER_SONG, None)
    st.session_state.pop(BACKING_METER_KEY, None)
    st.session_state.pop(BACKING_METER_OVERRIDE_KEY, None)


def apply_backing_meter_for_song(
    st: Any,
    *,
    song_id: str,
    default_time_signature: str,
) -> tuple[str, bool, str]:
    """
    Sync meter with active song; preserve user override until the song changes.

    Returns (applied_meter, user_override, song_default_meter).
    """
    song_default = normalize_time_signature(default_time_signature)
    song_changed = st.session_state.get(LAST_BACKING_METER_SONG) != song_id

    if song_changed:
        from .key_state import invalidate_backing_cache

        invalidate_backing_cache(st)
        st.session_state[LAST_BACKING_METER_SONG] = song_id
        st.session_state[BACKING_METER_KEY] = song_default
        st.session_state[BACKING_METER_OVERRIDE_KEY] = False
    elif BACKING_METER_KEY not in st.session_state:
        st.session_state[BACKING_METER_KEY] = song_default

    applied = normalize_time_signature(st.session_state.get(BACKING_METER_KEY, song_default))
    if applied not in BACKING_TIME_SIGNATURES:
        applied = song_default
        st.session_state[BACKING_METER_KEY] = applied

    override = bool(st.session_state.get(BACKING_METER_OVERRIDE_KEY, False))
    return applied, override, song_default


def note_backing_meter_override(st: Any, time_signature: str) -> None:
    from .key_state import BACKING_NEEDS_REGEN, invalidate_backing_cache

    st.session_state[BACKING_METER_KEY] = normalize_time_signature(time_signature)
    st.session_state[BACKING_METER_OVERRIDE_KEY] = True
    invalidate_backing_cache(st)
    st.session_state[BACKING_NEEDS_REGEN] = True

"""Global display-key session state (sidebar transpose for the active song)."""

from __future__ import annotations

from typing import Any

from music_theory import display_key_options

IDENTITY_KEY = "_display_key_song_identity"
LAST_DISPLAY_KEY = "_last_app_display_key"
PENDING_DISPLAY_KEY = "_pending_display_key"
BACKING_NEEDS_REGEN = "_backing_needs_regen"

_BACKING_CACHE_KEYS = (
    "_last_backing_wav",
    "_last_backing_signature",
    "_last_backing_timeline",
    "current_chord_timeline",
    "playback_start_time",
)


def invalidate_backing_cache(st: Any) -> None:
    for key in _BACKING_CACHE_KEYS:
        st.session_state.pop(key, None)


def clear_backing_needs_regen(st: Any) -> None:
    st.session_state[BACKING_NEEDS_REGEN] = False


def mark_display_key_changed(st: Any) -> None:
    """Sidebar widget callback — invalidate derived audio/analysis."""
    invalidate_backing_cache(st)
    st.session_state[BACKING_NEEDS_REGEN] = True
    from custom_progression_lab import on_global_display_key_change

    dk = st.session_state.get("display_key")
    if dk:
        on_global_display_key_change(st.session_state, dk)


def sync_display_key_before_widget(
    st: Any,
    original_key: str,
    song_identity: tuple,
) -> list[str]:
    """Apply pending key / song-change resets before the display_key widget is built."""
    pending = st.session_state.pop(PENDING_DISPLAY_KEY, None)
    if pending is not None:
        st.session_state["display_key"] = pending

    options = display_key_options(original_key)

    if st.session_state.get(IDENTITY_KEY) != song_identity:
        st.session_state[IDENTITY_KEY] = song_identity
        st.session_state["display_key"] = original_key
        st.session_state[LAST_DISPLAY_KEY] = original_key
        invalidate_backing_cache(st)
        st.session_state[BACKING_NEEDS_REGEN] = False
    elif "display_key" not in st.session_state:
        st.session_state["display_key"] = original_key

    current = st.session_state.get("display_key", original_key)
    if current not in options:
        st.session_state["display_key"] = (
            original_key if original_key in options else options[0]
        )

    return options


def request_display_key(st: Any, key: str) -> None:
    """Set display key on the next run without touching the widget after creation."""
    st.session_state[PENDING_DISPLAY_KEY] = key


def note_display_key_change(st: Any, display_key: str) -> bool:
    """Detect programmatic or widget-driven display-key changes after the sidebar."""
    last = st.session_state.get(LAST_DISPLAY_KEY)
    if last is None:
        st.session_state[LAST_DISPLAY_KEY] = display_key
        return False
    if last == display_key:
        return False

    st.session_state[LAST_DISPLAY_KEY] = display_key
    invalidate_backing_cache(st)
    st.session_state[BACKING_NEEDS_REGEN] = True
    from custom_progression_lab import on_global_display_key_change

    on_global_display_key_change(st.session_state, display_key)
    return True

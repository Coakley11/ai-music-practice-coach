"""Global display-key session state (sidebar transpose for the active song)."""

from __future__ import annotations

from typing import Any

from music_theory import display_key_options

IDENTITY_KEY = "_display_key_song_identity"
LAST_DISPLAY_KEY = "_last_app_display_key"
PENDING_DISPLAY_KEY = "_pending_display_key"
CPL_JUMP_HOME_TARGET = "_cpl_jump_home_target"
BACKING_NEEDS_REGEN = "_backing_needs_regen"

_BACKING_CACHE_KEYS = (
    "_last_backing_wav",
    "_last_backing_wav_b64",
    "_last_backing_signature",
    "_last_backing_timeline",
    "current_chord_timeline",
    "playback_start_time",
)


def invalidate_backing_cache(st: Any) -> None:
    for key in _BACKING_CACHE_KEYS:
        st.session_state.pop(key, None)
    try:
        from studio_cache import invalidate_session_cache

        invalidate_session_cache(st.session_state, "backing_wav_b64")
        invalidate_session_cache(st.session_state, "chart_bundle")
        invalidate_session_cache(st.session_state, "backing_chart_html")
    except Exception:
        pass


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
    try:
        from songs.state import persist_music_local_state

        persist_music_local_state(st)
    except Exception:
        pass


def _apply_display_key_before_widget(st: Any, key: str) -> None:
    """Mutate display_key only before the sidebar selectbox is instantiated."""
    st.session_state["display_key"] = key


def sync_display_key_before_widget(
    st: Any,
    original_key: str,
    song_identity: tuple,
) -> list[str]:
    """Apply pending key / song-change resets before the display_key widget is built."""
    pending = st.session_state.pop(PENDING_DISPLAY_KEY, None)
    options = display_key_options(original_key)
    identity_changed = st.session_state.get(IDENTITY_KEY) != song_identity

    if identity_changed:
        st.session_state[IDENTITY_KEY] = song_identity
        _apply_display_key_before_widget(
            st,
            pending if pending is not None else original_key,
        )
        st.session_state[LAST_DISPLAY_KEY] = st.session_state["display_key"]
        invalidate_backing_cache(st)
        st.session_state[BACKING_NEEDS_REGEN] = False
    elif pending is not None:
        _apply_display_key_before_widget(st, pending)
    elif "display_key" not in st.session_state:
        _apply_display_key_before_widget(st, original_key)

    current = st.session_state.get("display_key", original_key)
    if current not in options:
        _apply_display_key_before_widget(
            st,
            original_key if original_key in options else options[0],
        )

    return options


def request_display_key(st: Any, key: str) -> None:
    """Set display key on the next run without touching the widget after creation."""
    st.session_state[PENDING_DISPLAY_KEY] = key


def prepare_cpl_jump_home(st: Any, home_key: str) -> None:
    """Store CPL home-key target for the sidebar jump button callback."""
    st.session_state[CPL_JUMP_HOME_TARGET] = home_key


def on_cpl_jump_home_key() -> None:
    """Button callback: queue display-key change before the widget is built on rerun."""
    import streamlit as st

    target = st.session_state.pop(CPL_JUMP_HOME_TARGET, None)
    if not target:
        return
    request_display_key(st, target)
    invalidate_backing_cache(st)
    st.session_state[BACKING_NEEDS_REGEN] = True


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

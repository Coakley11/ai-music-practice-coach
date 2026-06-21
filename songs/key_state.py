"""Global display-key session state (sidebar transpose for the active song)."""

from __future__ import annotations

from typing import Any

from music_theory import coerce_key_to_mode, display_key_options, key_mode

IDENTITY_KEY = "_display_key_song_identity"
LAST_DISPLAY_KEY = "_last_app_display_key"
PENDING_DISPLAY_KEY = "_pending_display_key"
DISPLAY_KEY_OWNER_IDENTITY_KEY = "_display_key_owner_identity"
LAST_DISPLAY_KEY_SAVE_OK_KEY = "_last_display_key_save_ok"
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
    try:
        from practice_setup_globals import record_global_control_change

        record_global_control_change(
            st.session_state,
            "display_key",
            "sidebar_on_change",
        )
    except Exception:
        pass
    try:
        from instrument_transposition import preserve_written_key_on_display_key_change

        preserve_written_key_on_display_key_change(st.session_state)
    except Exception:
        pass
    invalidate_backing_cache(st)
    st.session_state[BACKING_NEEDS_REGEN] = True
    from custom_progression_lab import on_global_display_key_change

    dk = st.session_state.get("display_key")
    if dk:
        on_global_display_key_change(st.session_state, dk)
    try:
        from music_activity import log_display_key_changed

        log_display_key_changed(
            st,
            display_key=str(dk or ""),
            previous_key=str(st.session_state.get(LAST_DISPLAY_KEY) or ""),
        )
    except Exception:
        pass
    try:
        from songs.state import persist_music_local_state

        persist_music_local_state(st)
    except Exception:
        pass
    try:
        from active_song_state import mark_active_song_local_edit
        from music_persistent_state import flush_active_song_edits_and_save

        mark_active_song_local_edit(st.session_state)
        ok = flush_active_song_edits_and_save(st, reason="display_key_change")
        st.session_state[LAST_DISPLAY_KEY_SAVE_OK_KEY] = bool(ok)
        if ok:
            try:
                from songs.music_source import (
                    ACTIVE_SONG_IDENTITY_KEY,
                    compute_active_song_identity,
                    cpl_session_is_active,
                )
                from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

                owner = str(st.session_state.get(ACTIVE_SONG_IDENTITY_KEY) or "").strip()
                if not owner:
                    selected = st.session_state.get(SELECTED_SONG_STATE_KEY) or {}
                    owner = compute_active_song_identity(
                        pick_key=str(
                            st.session_state.get(ACTIVE_CATALOG_PICK_KEY)
                            or selected.get("pick_key")
                            or ""
                        ).strip(),
                        title=str(selected.get("title") or ""),
                        artist=str(selected.get("artist") or ""),
                        original_key=str(selected.get("key") or "C"),
                        is_custom=cpl_session_is_active(st.session_state),
                        custom_revision=str(
                            (st.session_state.get("cpl_active_progression") or {}).get("id") or ""
                        ).strip(),
                    )
                st.session_state[DISPLAY_KEY_OWNER_IDENTITY_KEY] = owner
            except Exception:
                pass
    except Exception:
        st.session_state[LAST_DISPLAY_KEY_SAVE_OK_KEY] = False


def _apply_display_key_before_widget(st: Any, key: str, *, source: str = "sync_display_key") -> None:
    """Mutate display_key only before the sidebar selectbox is instantiated."""
    try:
        from practice_setup_globals import record_global_control_change

        record_global_control_change(st.session_state, "display_key", source)
    except Exception:
        pass
    st.session_state["display_key"] = key


def song_display_identity(title: str, artist: str, original_key: str) -> tuple[str, str, str]:
    """Stable identity tuple for display-key reset when the active song changes."""
    return (str(title or "").strip(), str(artist or "").strip(), str(original_key or "").strip())


def apply_display_key_for_active_song(
    st: Any,
    original_key: str,
    song_identity: tuple,
    *,
    pending_key: str | None = None,
) -> list[str]:
    """Reset or sync practice display key before the display_key widget renders."""
    options = display_key_options(original_key)
    identity_changed = st.session_state.get(IDENTITY_KEY) != song_identity

    if identity_changed:
        st.session_state[IDENTITY_KEY] = song_identity
        st.session_state.pop(PENDING_DISPLAY_KEY, None)
        if pending_key is not None:
            target = pending_key
        else:
            target = original_key
        _apply_display_key_before_widget(st, target, source="active_song_change")
        st.session_state[LAST_DISPLAY_KEY] = st.session_state["display_key"]
        invalidate_backing_cache(st)
        st.session_state[BACKING_NEEDS_REGEN] = False
        return options

    pending = st.session_state.pop(PENDING_DISPLAY_KEY, None)
    if pending is not None:
        _apply_display_key_before_widget(st, pending, source="pending_display_key")
    elif "display_key" not in st.session_state:
        _apply_display_key_before_widget(st, original_key, source="initial_display_key")

    current = st.session_state.get("display_key", original_key)
    if current not in options:
        mode = key_mode(original_key)
        fallback = (
            coerce_key_to_mode(original_key, mode)
            if coerce_key_to_mode(original_key, mode) in options
            else options[0]
        )
        _apply_display_key_before_widget(st, fallback)

    return options


def sync_display_key_before_widget(
    st: Any,
    original_key: str,
    song_identity: tuple,
) -> list[str]:
    """Apply pending key / song-change resets before the display_key widget is built."""
    return apply_display_key_for_active_song(st, original_key, song_identity)


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

    previous = str(last or "")
    st.session_state[LAST_DISPLAY_KEY] = display_key
    try:
        from instrument_transposition import preserve_written_key_on_display_key_change

        preserve_written_key_on_display_key_change(st.session_state)
    except Exception:
        pass
    invalidate_backing_cache(st)
    st.session_state[BACKING_NEEDS_REGEN] = True
    from custom_progression_lab import on_global_display_key_change

    on_global_display_key_change(st.session_state, display_key)
    try:
        from music_activity import log_display_key_changed

        log_display_key_changed(st, display_key=display_key, previous_key=previous)
    except Exception:
        pass
    return True

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
    record_display_key_write(st.session_state, key, source=source)
    trace_display_key_surface(
        st.session_state,
        "sidebar",
        key,
        source=source,
    )


def song_display_identity(
    title: str,
    artist: str,
    original_key: str,
    *,
    pick_key: str = "",
) -> tuple[str, str, str]:
    """Stable identity tuple for display-key reset when the active song changes."""
    pk = str(pick_key or "").strip()
    if pk:
        return (pk, str(artist or "").strip(), str(original_key or "").strip())
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


DISPLAY_KEY_TRACE_KEY = "_display_key_surface_trace"
DISPLAY_KEY_LAST_WRITE_KEY = "_display_key_last_write_source"
ACTIVE_SONG_PICK_TRACE_KEY = "_display_key_active_song_pick_key"


def _active_catalog_pick_key(session: dict[str, Any]) -> str:
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    return str(
        session.get(ACTIVE_CATALOG_PICK_KEY)
        or (session.get(SELECTED_SONG_STATE_KEY) or {}).get("pick_key")
        or ""
    ).strip()


def trace_display_key_surface(
    session: dict[str, Any],
    surface: str,
    value: str,
    *,
    pick_key: str = "",
    source: str = "",
) -> None:
    """Record which surface read/wrote a display key (dev trace + split detection)."""
    pk = str(pick_key or _active_catalog_pick_key(session) or "").strip()
    if pk:
        session[ACTIVE_SONG_PICK_TRACE_KEY] = pk
    trace = session.get(DISPLAY_KEY_TRACE_KEY)
    if not isinstance(trace, dict):
        trace = {}
    trace[str(surface or "unknown")] = {
        "value": str(value or "").strip(),
        "pick_key": pk,
        "source": str(source or "").strip(),
    }
    session[DISPLAY_KEY_TRACE_KEY] = trace
    if source:
        session[DISPLAY_KEY_LAST_WRITE_KEY] = str(source)


def _display_key_split_surfaces(trace: dict[str, Any]) -> str | None:
    """Return a short disagreement summary when surfaces diverge."""
    refs = (
        ("sidebar", trace.get("sidebar", {})),
        ("song_card", trace.get("song_card", {})),
        ("backing_card", trace.get("backing_card", {})),
        ("practice", trace.get("practice", {})),
    )
    values: dict[str, str] = {}
    for name, row in refs:
        if isinstance(row, dict):
            val = str(row.get("value") or "").strip()
            if val:
                values[name] = val
    if len(set(values.values())) <= 1:
        return None
    parts = [f"{name}={val}" for name, val in values.items()]
    return " | ".join(parts)


def record_display_key_write(session: dict[str, Any], value: str, *, source: str) -> None:
    trace_display_key_surface(session, "write", value, source=source)
    session[DISPLAY_KEY_LAST_WRITE_KEY] = str(source or "")


def get_authoritative_display_key(
    session: dict[str, Any],
    *,
    original_key: str = "",
    surface: str = "",
) -> str:
    """Single authoritative practice/display key for cards, charts, cloud, and restore."""
    from songs.music_source import SOURCE_CUSTOM, cpl_session_is_active, custom_progression_is_active
    from active_song_state import _resolve_custom_display_key_for_session

    pick_key = _active_catalog_pick_key(session)
    home = str(original_key or "").strip()
    if not home:
        selected = session.get("selected_song") or {}
        if pick_key and str(selected.get("pick_key") or "").strip() == pick_key:
            home = str(selected.get("key") or "C").strip() or "C"
        else:
            home = "C"

    if custom_progression_is_active(session) or cpl_session_is_active(session):
        resolved = _resolve_custom_display_key_for_session(session, home)
        source = "authoritative_custom"
    else:
        live = str(session.get("display_key") or "").strip()
        meta = session.get("active_song_state")
        canonical = ""
        if isinstance(meta, dict):
            meta_pick = str(meta.get("pick_key") or "").strip()
            if not meta_pick or not pick_key or meta_pick == pick_key:
                canonical = str(meta.get("display_key") or "").strip()
        try:
            from active_song_state import _display_key_override_valid_for_identity

            if _display_key_override_valid_for_identity(session) and live:
                resolved = live
                source = "authoritative_live_override"
            elif live:
                resolved = live
                source = "authoritative_live"
            elif canonical:
                resolved = canonical
                source = "authoritative_canonical"
            else:
                resolved = home or "C"
                source = "authoritative_home"
        except ImportError:
            resolved = live or canonical or home or "C"
            source = "authoritative_fallback"

    trace_display_key_surface(
        session,
        surface or "authoritative",
        resolved,
        pick_key=pick_key,
        source=source,
    )
    try:
        from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY

        if (
            str(session.get("instrument") or "").strip() == "Guitar"
            and session.get(CAPO_ENABLED_KEY)
        ):
            shape = str(session.get(CAPO_SHAPE_KEY) or "").strip()
            if shape:
                trace_display_key_surface(
                    session,
                    surface or "authoritative_capo",
                    shape,
                    pick_key=pick_key,
                    source="authoritative_capo_shape",
                )
                return shape
    except ImportError:
        pass
    return resolved


def detect_display_key_split(session: dict[str, Any]) -> str | None:
    """Compare traced surface keys; return disagreement summary or None."""
    trace = session.get(DISPLAY_KEY_TRACE_KEY)
    if not isinstance(trace, dict):
        return None
    return _display_key_split_surfaces(trace)

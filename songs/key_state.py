"""Global display-key session state (sidebar transpose for the active song)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from music_theory import coerce_key_to_mode, display_key_options, key_mode

IDENTITY_KEY = "_display_key_song_identity"
LAST_DISPLAY_KEY = "_last_app_display_key"
PENDING_DISPLAY_KEY = "_pending_display_key"
DISPLAY_KEY_OWNER_IDENTITY_KEY = "_display_key_owner_identity"
LAST_DISPLAY_KEY_SAVE_OK_KEY = "_last_display_key_save_ok"
CPL_JUMP_HOME_TARGET = "_cpl_jump_home_target"
BACKING_NEEDS_REGEN = "_backing_needs_regen"


def resolve_restore_display_key(
    session: dict[str, Any],
    *,
    override: str = "",
    core_display_key: str = "",
    workspace_payload: dict[str, Any] | None = None,
) -> str:
    """Best saved practice/display key for catalog restore (not catalog original)."""
    dk = str(override or "").strip()
    if dk:
        return dk
    dk = str(core_display_key or "").strip()
    if dk:
        return dk
    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY

        meta = session.get(ACTIVE_SONG_STATE_KEY)
        if isinstance(meta, dict):
            dk = str(meta.get("display_key") or "").strip()
            if dk:
                return dk
    except ImportError:
        pass
    dk = str(session.get(PENDING_DISPLAY_KEY) or "").strip()
    if dk:
        return dk
    if isinstance(workspace_payload, dict) and workspace_payload:
        try:
            from active_song_state import _resolve_display_key_from_music_blob

            dk = _resolve_display_key_from_music_blob(workspace_payload)
            if dk:
                return dk
        except ImportError:
            pass
    return ""


def canonical_display_key_for_pick(session: dict[str, Any], pick_key: str) -> str:
    """Saved practice display key for one pick_key only (ignores other songs' canonical)."""
    pk = str(pick_key or "").strip()
    if not pk:
        return ""
    try:
        from practice_key_mode import is_fixed_practice_key_mode

        if is_fixed_practice_key_mode(session):
            return ""
    except ImportError:
        pass
    try:
        from songs.practice_key_state import get_practice_concert_key

        saved = get_practice_concert_key(session, pk)
        if saved:
            return saved
    except ImportError:
        pass
    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY

        meta = session.get(ACTIVE_SONG_STATE_KEY)
        if isinstance(meta, dict) and str(meta.get("pick_key") or "").strip() == pk:
            return str(meta.get("display_key") or "").strip()
    except ImportError:
        pass
    return ""


_BACKING_CACHE_KEYS = (
    "_last_backing_wav",
    "_last_backing_wav_b64",
    "_last_backing_signature",
    "_last_backing_timeline",
    "current_chord_timeline",
    "playback_start_time",
)


def _is_session_mapping(obj: Any) -> bool:
    return obj is not None and hasattr(obj, "__getitem__") and hasattr(obj, "__setitem__")


def _session_from_st_like(session_or_st: Any) -> Any:
    """Accept a session dict, mapping-like session_state, or Streamlit module/context."""
    if isinstance(session_or_st, dict):
        return session_or_st
    if _is_session_mapping(session_or_st) and not hasattr(session_or_st, "session_state"):
        return session_or_st
    ss = getattr(session_or_st, "session_state", None)
    if _is_session_mapping(ss):
        return ss
    raise TypeError(
        f"Expected session dict or st-like object, got {type(session_or_st)!r}"
    )


def invalidate_backing_cache(session_or_st: Any) -> None:
    session = _session_from_st_like(session_or_st)
    for key in _BACKING_CACHE_KEYS:
        session.pop(key, None)
    try:
        from studio_cache import invalidate_session_cache

        invalidate_session_cache(session, "backing_wav_b64")
        invalidate_session_cache(session, "chart_bundle")
        invalidate_session_cache(session, "backing_chart_html")
    except Exception:
        pass


def clear_backing_needs_regen(session_or_st: Any) -> None:
    _session_from_st_like(session_or_st)[BACKING_NEEDS_REGEN] = False


def sync_display_key_owner_identity(session: dict[str, Any]) -> None:
    """Attach display-key override ownership to the current active song identity."""
    try:
        from songs.music_source import ACTIVE_SONG_IDENTITY_KEY, resolve_active_song_identity

        owner = resolve_active_song_identity(session)
        if owner:
            session[DISPLAY_KEY_OWNER_IDENTITY_KEY] = owner
            session[ACTIVE_SONG_IDENTITY_KEY] = owner
    except Exception:
        pass


def normalize_sidebar_display_key(session: dict[str, Any], raw: str) -> str:
    """Normalize widget spelling to the active song mode (Cm vs C minor, etc.)."""
    selected = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
    original = str(selected.get("key") or session.get("original_key") or "C").strip() or "C"
    text = str(raw or "C").strip() or "C"
    return coerce_key_to_mode(text, key_mode(original))


def commit_explicit_sidebar_display_key_transaction(st: Any, *, caller: str = "mark_display_key_changed") -> bool:
    """Canonical + cloud save for an explicit sidebar Display key selection."""
    session = st.session_state
    tx_id = ""
    try:
        from display_key_sidebar_persistence_trace import (
            begin_display_key_sidebar_transaction,
            record_display_key_sidebar_stage,
        )

        tx_id = begin_display_key_sidebar_transaction(session, caller=caller)
        record_display_key_sidebar_stage(
            session,
            "canonical_commit_start",
            caller=caller,
            transaction_id=tx_id or None,
            reason="display_key_change",
        )
    except ImportError:
        pass
    try:
        from active_song_state import flush_global_control_edits, mark_active_song_local_edit

        mark_active_song_local_edit(session)
        flush_global_control_edits(session, reason="display_key_change")
    except ImportError:
        pass
    try:
        from display_key_sidebar_persistence_trace import record_display_key_sidebar_stage

        record_display_key_sidebar_stage(
            session,
            "canonical_commit_end",
            caller=caller,
            transaction_id=tx_id or None,
            reason="display_key_change",
        )
    except ImportError:
        pass
    ok = False
    try:
        from display_key_sidebar_persistence_trace import record_display_key_sidebar_stage

        record_display_key_sidebar_stage(
            session,
            "cloud_save_start",
            caller=caller,
            transaction_id=tx_id or None,
            reason="display_key_change",
        )
    except ImportError:
        pass
    try:
        from music_persistent_state import flush_global_control_edits_and_save

        ok = bool(flush_global_control_edits_and_save(st, reason="display_key_change"))
    except Exception:
        ok = False
    session[LAST_DISPLAY_KEY_SAVE_OK_KEY] = ok
    try:
        from display_key_sidebar_persistence_trace import record_display_key_sidebar_stage

        record_display_key_sidebar_stage(
            session,
            "cloud_save_end",
            caller=caller,
            transaction_id=tx_id or None,
            reason="display_key_change",
            cloud_save_requested=True,
            cloud_save_ok=ok,
        )
    except ImportError:
        pass
    if ok:
        try:
            from active_song_state import clear_active_song_local_edit

            clear_active_song_local_edit(session)
        except ImportError:
            pass
    return ok


def mark_display_key_changed(st: Any) -> None:
    """Sidebar widget callback — invalidate derived audio/analysis."""
    caller = "mark_display_key_changed"
    tx_id = ""
    try:
        from display_key_sidebar_persistence_trace import (
            begin_display_key_sidebar_transaction,
            record_display_key_sidebar_stage,
        )

        tx_id = begin_display_key_sidebar_transaction(st.session_state, caller=caller)
        record_display_key_sidebar_stage(st.session_state, "callback_enter", caller=caller, transaction_id=tx_id or None)
    except ImportError:
        pass
    widget_before = str(st.session_state.get("display_key") or "").strip()
    raw_widget = widget_before
    try:
        from display_key_sidebar_persistence_trace import record_display_key_sidebar_stage

        record_display_key_sidebar_stage(
            st.session_state,
            "widget_value_read",
            caller=caller,
            transaction_id=tx_id or None,
            widget_value=raw_widget or None,
        )
    except ImportError:
        pass
    dk = normalize_sidebar_display_key(st.session_state, raw_widget)
    if dk:
        st.session_state["display_key"] = dk
    sync_display_key_owner_identity(st.session_state)
    try:
        from practice_setup_globals import record_global_control_change

        record_global_control_change(
            st.session_state,
            "display_key",
            "sidebar_on_change",
        )
    except Exception:
        pass
    if dk:
        try:
            from practice_key_mode import is_fixed_practice_key_mode
            from songs.practice_key_state import (
                creative_jam_owns_practice_settings,
                resolve_practice_source_pick,
                set_practice_concert_key,
                should_write_song_source_settings,
            )

            if not is_fixed_practice_key_mode(st.session_state):
                pick = resolve_practice_source_pick(st.session_state)
                set_practice_concert_key(
                    st.session_state,
                    dk,
                    pick_key=pick,
                )
                if should_write_song_source_settings(st.session_state, pick):
                    try:
                        from source_session_state import sync_catalog_session

                        sync_catalog_session(st.session_state)
                    except ImportError:
                        pass
            if creative_jam_owns_practice_settings(st.session_state):
                try:
                    from creative_session_state import sync_creative_session_from_session

                    sync_creative_session_from_session(st.session_state)
                except ImportError:
                    pass
        except ImportError:
            pass
    try:
        from instrument_transposition import preserve_written_key_on_display_key_change

        preserve_written_key_on_display_key_change(st.session_state)
    except Exception:
        pass
    invalidate_backing_cache(st)
    st.session_state[BACKING_NEEDS_REGEN] = True
    try:
        from backing_context import sync_regular_song_backing_context_keys

        sync_regular_song_backing_context_keys(st.session_state)
    except ImportError:
        pass
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
    save_ok = False
    try:
        save_ok = commit_explicit_sidebar_display_key_transaction(st, caller=caller)
    except Exception:
        st.session_state[LAST_DISPLAY_KEY_SAVE_OK_KEY] = False
        save_ok = False
    try:
        from display_key_sidebar_persistence_trace import (
            audit_display_key_user_change_committed,
            record_display_key_sidebar_event,
        )

        record_display_key_sidebar_event(
            st.session_state,
            "mark_display_key_changed",
            widget_before=widget_before,
            widget_after=str(st.session_state.get("display_key") or "").strip() or None,
            callback_invoked=True,
            save_reason="display_key_change",
            cloud_save_requested=bool(save_ok),
            cloud_save_ok=bool(save_ok),
            transaction_id=tx_id or None,
        )
        audit_display_key_user_change_committed(
            st.session_state,
            callback_invoked=True,
            cloud_save_requested=bool(save_ok),
        )
    except ImportError:
        pass


def _apply_display_key_before_widget(st: Any, key: str, *, source: str = "sync_display_key") -> None:
    """Mutate display_key via widget-safe path when sidebar may already exist."""
    concert = str(key or "C").strip() or "C"
    try:
        from practice_setup_globals import record_global_control_change

        record_global_control_change(st.session_state, "display_key", source)
    except Exception:
        pass
    try:
        from session_widget_safe import safe_assign_display_key

        safe_assign_display_key(st.session_state, concert, widget_safe=True, st_like=st)
    except ImportError:
        st.session_state["display_key"] = concert
        st.session_state[PENDING_DISPLAY_KEY] = concert
    record_display_key_write(st.session_state, concert, source=source)
    trace_display_key_surface(
        st.session_state,
        "sidebar",
        concert,
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
        pending = st.session_state.pop(PENDING_DISPLAY_KEY, None)
        identity_pk = str(song_identity[0] or "").strip() if song_identity else ""
        if pending_key is not None:
            target = pending_key
        else:
            canonical = canonical_display_key_for_pick(st.session_state, identity_pk)
            target = canonical or original_key
        try:
            from practice_key_mode import apply_fixed_mode_target

            target = apply_fixed_mode_target(st.session_state, target, original_key)
        except ImportError:
            pass
        try:
            from practice_setup_globals import DISPLAY_KEY_CHANGE_SOURCE_KEY

            st.session_state.pop(DISPLAY_KEY_CHANGE_SOURCE_KEY, None)
            st.session_state.pop(DISPLAY_KEY_OWNER_IDENTITY_KEY, None)
        except ImportError:
            pass
        _apply_display_key_before_widget(st, target, source="active_song_change")
        st.session_state[LAST_DISPLAY_KEY] = target
        invalidate_backing_cache(st)
        st.session_state[BACKING_NEEDS_REGEN] = False
        try:
            from practice_key_mode import is_fixed_practice_key_mode

            if is_fixed_practice_key_mode(st.session_state):
                return [str(target)]
        except ImportError:
            pass
        if target not in options:
            options = [str(target)] + [opt for opt in options if opt != str(target)]
        return options

    identity_pk = str(song_identity[0] or "").strip() if song_identity else ""
    pending = st.session_state.pop(PENDING_DISPLAY_KEY, None)
    if pending is not None:
        _apply_display_key_before_widget(st, pending, source="pending_display_key")
    else:
        saved = canonical_display_key_for_pick(st.session_state, identity_pk)
        if saved and saved != str(st.session_state.get("display_key") or "").strip():
            target_saved = saved
            try:
                from practice_key_mode import apply_fixed_mode_target

                target_saved = apply_fixed_mode_target(st.session_state, saved, original_key)
            except ImportError:
                pass
            _apply_display_key_before_widget(st, target_saved, source="practice_key_restore")
            st.session_state[LAST_DISPLAY_KEY] = target_saved
        elif "display_key" not in st.session_state:
            target_initial = original_key
            try:
                from practice_key_mode import apply_fixed_mode_target

                target_initial = apply_fixed_mode_target(
                    st.session_state,
                    original_key,
                    original_key,
                )
            except ImportError:
                pass
            _apply_display_key_before_widget(st, target_initial, source="initial_display_key")

    current = st.session_state.get("display_key", original_key)
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

        if is_fixed_practice_key_mode(st.session_state):
            target = resolve_practice_concert_key_for_song(
                st.session_state,
                original_key or "C",
                fallback=original_key or "C",
            )
            if str(current or "").strip() != str(target).strip():
                _apply_display_key_before_widget(
                    st,
                    target,
                    source="fixed_key_family_sync",
                )
                st.session_state[LAST_DISPLAY_KEY] = target
                st.session_state["last_key_writer_function"] = "apply_display_key_for_active_song:fixed_key_family_sync"
            return [str(target)]
    except ImportError:
        pass
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


def request_display_key(session_or_st: Any, key: str) -> None:
    """Set display key on the next run without touching the widget after creation."""
    _session_from_st_like(session_or_st)[PENDING_DISPLAY_KEY] = key


def prepare_cpl_jump_home(session_or_st: Any, home_key: str) -> None:
    """Store CPL home-key target for the sidebar jump button callback."""
    _session_from_st_like(session_or_st)[CPL_JUMP_HOME_TARGET] = home_key


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
    sync_display_key_owner_identity(st.session_state)
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

    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

        if is_fixed_practice_key_mode(session):
            resolved = resolve_practice_concert_key_for_song(
                session,
                home,
                pick_key=pick_key,
                fallback=home,
            )
            trace_display_key_surface(
                session,
                surface or "authoritative",
                resolved,
                pick_key=pick_key,
                source="fixed_key_family",
            )
            session["last_key_writer_function"] = "get_authoritative_display_key:fixed_key_family"
            return resolved
    except ImportError:
        pass

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
    return resolved


def detect_display_key_split(session: dict[str, Any]) -> str | None:
    """Compare traced surface keys; return disagreement summary or None."""
    trace = session.get(DISPLAY_KEY_TRACE_KEY)
    if not isinstance(trace, dict):
        return None
    return _display_key_split_surfaces(trace)


@dataclass(frozen=True)
class ActiveMusicalKeyContext:
    """Resolved keys — practice/concert, written, shape, and chart are kept separate."""

    original_key: str
    practice_concert_key: str
    written_key: str
    shape_key: str
    chart_key: str
    chart_key_mode: str
    instrument: str
    transposing_type: str = ""

    @property
    def concert_key(self) -> str:
        """Alias for practice_concert_key (sounding / user-selected key)."""
        return self.practice_concert_key

    @property
    def musical_key(self) -> str:
        """Deprecated alias — use ``chart_key`` for charts, ``practice_concert_key`` for display."""
        return self.chart_key


def resolve_active_musical_key(
    session: dict[str, Any],
    *,
    rec: dict[str, Any] | None = None,
    instrument: str | None = None,
    surface: str = "",
) -> ActiveMusicalKeyContext:
    """Resolve all key roles without collapsing display and chart keys.

    - **practice_concert_key** — user Practice / Concert Key (always sounding pitch).
    - **written_key** — transposing-instrument written spelling (may differ from concert).
    - **shape_key** — guitar capo fingering key when capo shape mode is on.
    - **chart_key** — key charts/coaching/scales should use (concert, written, or shape).
    """
    from instrument_transposition import (
        chart_in_instrument_key,
        effective_chart_key,
        is_transposing_instrument,
        resolve_practice_keys,
        selected_transposing_type,
    )
    from songs.music_source import resolve_active_song_keys

    inst = str(instrument or session.get("instrument") or "Piano").strip() or "Piano"
    original, concert, _written_opt = resolve_active_song_keys(session, rec)
    key_ctx = resolve_practice_keys(session, concert, inst)
    practice_concert_key = str(key_ctx.get("concert_key") or concert or "C").strip() or "C"

    written_key = ""
    if is_transposing_instrument(inst):
        written_key = str(key_ctx.get("written_key") or "").strip()

    shape_key = ""
    try:
        from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY

        if inst == "Guitar" and session.get(CAPO_ENABLED_KEY):
            shape_key = str(session.get(CAPO_SHAPE_KEY) or "").strip()
    except ImportError:
        shape_key = ""

    if shape_key:
        chart_key = shape_key
        mode = "shape"
    elif is_transposing_instrument(inst) and chart_in_instrument_key(session):
        chart_key, mode = effective_chart_key(practice_concert_key, inst, session)
    else:
        chart_key = practice_concert_key
        mode = "concert"

    trace_display_key_surface(
        session,
        surface or "practice_concert",
        practice_concert_key,
        source="resolve_active_musical_key",
    )
    trace_display_key_surface(
        session,
        "chart",
        chart_key,
        source="resolve_active_musical_key",
    )
    return ActiveMusicalKeyContext(
        original_key=str(original or "C").strip() or "C",
        practice_concert_key=practice_concert_key,
        written_key=written_key,
        shape_key=shape_key,
        chart_key=str(chart_key or practice_concert_key or "C").strip() or "C",
        chart_key_mode=mode,
        instrument=inst,
        transposing_type=(
            selected_transposing_type(session, inst)
            if is_transposing_instrument(inst)
            else ""
        ),
    )

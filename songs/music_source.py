"""Active music source: catalog song vs custom progression (shared session contract)."""

from __future__ import annotations

from typing import Any, Callable

ACTIVE_MUSIC_SOURCE_KEY = "active_music_source"
SOURCE_CATALOG = "catalog_song"
SOURCE_CUSTOM = "custom_progression"
_LAST_SOURCE_KEY = "_last_active_music_source"
_LAST_ACTIVE_PICK_KEY = "_last_active_pick_key_for_reset"
PENDING_CUSTOM_ACTIVE_SONG_KEY = "_pending_custom_active_song_activation"
PENDING_CUSTOM_LIBRARY_ACTION_KEY = "_pending_custom_library_action"
SONG_PICKER_SOURCE_CATALOG = "Song Selection (catalog song)"
SONG_PICKER_SOURCE_CUSTOM = "Use Custom Progression / Create Your Own Song"
SONG_PICKER_ACTIVE_SOURCE_KEY = "song_picker_active_source"
LAST_CATALOG_STATE_KEY = "_last_catalog_song_state"
CATALOG_BEFORE_CUSTOM_KEY = "_catalog_before_custom_state"
PENDING_PREVIOUS_CATALOG_RESTORE_KEY = "_pending_previous_catalog_restore"
USER_CATALOG_SOURCE_CHOICE_KEY = "_user_chose_catalog_music_source"
CATALOG_RECENT_PICK_KEYS = "catalog_recent_pick_keys"
CUSTOM_RECENT_ACTIVE_NAMES_KEY = "custom_recent_active_names"


def ensure_active_music_source(session_state: dict[str, Any]) -> None:
    session_state.setdefault(ACTIVE_MUSIC_SOURCE_KEY, SOURCE_CATALOG)


def is_custom_progression(session_state: dict[str, Any]) -> bool:
    return session_state.get(ACTIVE_MUSIC_SOURCE_KEY) == SOURCE_CUSTOM


def custom_progression_is_active(session_state: dict[str, Any]) -> bool:
    """True when Custom Progression is the active song (session or canonical blob)."""
    if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        return False
    if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) == SOURCE_CATALOG:
        return False
    if is_custom_progression(session_state):
        return True
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    pick_key = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if pick_key.startswith("custom::"):
        return True
    meta = session_state.get("active_song_state")
    if isinstance(meta, dict):
        if str(meta.get("music_source") or "") == SOURCE_CUSTOM:
            return True
        if str(meta.get("pick_key") or "").strip().startswith("custom::"):
            return True
    return False


def picker_custom_progression_mode(session_state: dict[str, Any]) -> bool:
    """True when the Songs page radio is on Custom Progression."""
    if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        return False
    choice = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    return choice == SONG_PICKER_SOURCE_CUSTOM or choice.startswith("Use Custom")


def cpl_session_is_active(session_state: dict[str, Any]) -> bool:
    """True when the loaded song is a Custom Progression (for key display/sync)."""
    if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        return False
    if is_custom_progression(session_state):
        return True
    if picker_custom_progression_mode(session_state):
        return True
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    pick_key = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if pick_key.startswith("custom::"):
        return True
    meta = session_state.get("active_song_state")
    if isinstance(meta, dict) and str(meta.get("music_source") or "") == SOURCE_CUSTOM:
        return True
    if isinstance(meta, dict):
        meta_pick = str(meta.get("pick_key") or "").strip()
        if meta_pick.startswith("custom::"):
            return True
    return False


def reconcile_music_picker_source_widget(session_state: dict[str, Any]) -> bool:
    """Align Songs page source radio with active song + active_music_source."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    try:
        from music_restore_phase import music_restore_phase_complete

        phase_done = music_restore_phase_complete(session_state)
    except ImportError:
        phase_done = False

    if phase_done and session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        expected = SONG_PICKER_SOURCE_CATALOG
        current = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
        changed = False
        if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) != SOURCE_CATALOG:
            set_catalog_source(session_state)
            changed = True
        if current != expected:
            session_state[SONG_PICKER_ACTIVE_SOURCE_KEY] = expected
            changed = True
        return changed

    pick_key = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    custom_active = custom_progression_is_active(session_state)
    expected = SONG_PICKER_SOURCE_CUSTOM if custom_active else SONG_PICKER_SOURCE_CATALOG
    current = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    changed = False

    if custom_active:
        if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) != SOURCE_CUSTOM:
            session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CUSTOM
            changed = True
    elif pick_key and not pick_key.startswith("custom::"):
        if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) != SOURCE_CATALOG:
            set_catalog_source(session_state)
            changed = True

    if current != expected:
        session_state[SONG_PICKER_ACTIVE_SOURCE_KEY] = expected
        changed = True
    return changed


def ensure_active_music_source_from_canonical(session_state: dict[str, Any]) -> None:
    """After cloud/local restore, align session source flag with canonical custom songs."""
    if is_custom_progression(session_state):
        return
    if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        return
    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY
        from music_restore_phase import authoritative_restore_in_progress
    except ImportError:
        return
    if not authoritative_restore_in_progress(session_state):
        return
    meta = session_state.get(ACTIVE_SONG_STATE_KEY)
    if isinstance(meta, dict) and str(meta.get("music_source") or "") == SOURCE_CUSTOM:
        session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CUSTOM


def set_catalog_source(session_state: dict[str, Any]) -> None:
    session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CATALOG


def _catalog_snapshot_from_session(session_state: dict[str, Any]) -> dict[str, Any] | None:
    """Build a catalog song snapshot from the current session selection."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    sel = session_state.get(SELECTED_SONG_STATE_KEY)
    if not isinstance(sel, dict):
        return None
    pick_key = str(
        session_state.get(ACTIVE_CATALOG_PICK_KEY) or sel.get("pick_key") or ""
    ).strip()
    if not pick_key or pick_key.startswith("custom::"):
        return None
    original_key = str(sel.get("key") or "C").strip() or "C"
    display_key = str(session_state.get("display_key") or original_key).strip() or original_key
    return {
        "pick_key": pick_key,
        "selected_song": dict(sel),
        "original_key": original_key,
        "display_key": display_key,
    }


def snapshot_catalog_before_custom(session_state: dict[str, Any]) -> None:
    """Remember the active catalog song before entering Custom Progression."""
    if is_custom_progression(session_state):
        return
    snap = _catalog_snapshot_from_session(session_state)
    if snap:
        session_state[CATALOG_BEFORE_CUSTOM_KEY] = snap


def set_custom_source(session_state: dict[str, Any]) -> None:
    snapshot_catalog_before_custom(session_state)
    session_state.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)
    session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CUSTOM


def sync_song_picker_source_widget(session_state: dict[str, Any], *, force: bool = False) -> None:
    """Align Song Selection source radio with active_music_source (init or forced promotion only)."""
    if not force and SONG_PICKER_ACTIVE_SOURCE_KEY in session_state:
        return
    session_state[SONG_PICKER_ACTIVE_SOURCE_KEY] = (
        SONG_PICKER_SOURCE_CUSTOM
        if is_custom_progression(session_state)
        else SONG_PICKER_SOURCE_CATALOG
    )


def snapshot_current_catalog_state(session_state: dict[str, Any]) -> None:
    """Remember the active catalog song before switching to another catalog song."""
    if is_custom_progression(session_state):
        return
    snap = _catalog_snapshot_from_session(session_state)
    if snap:
        session_state[LAST_CATALOG_STATE_KEY] = snap


def save_last_catalog_snapshot(session_state: dict[str, Any]) -> None:
    """Backward-compatible alias for snapshot_current_catalog_state."""
    snapshot_current_catalog_state(session_state)


def previous_catalog_snapshot(session_state: dict[str, Any]) -> dict[str, Any] | None:
    """Previous catalog song snapshot when it differs from the active catalog pick."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    snap = session_state.get(LAST_CATALOG_STATE_KEY)
    if not isinstance(snap, dict):
        return None
    prev_pick = str(snap.get("pick_key") or "").strip()
    if not prev_pick or prev_pick.startswith("custom::"):
        return None
    current_pick = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if prev_pick == current_pick:
        return None
    return snap


def queue_previous_catalog_restore(st: Any) -> None:
    """Queue previous-catalog restore for before-widget application on the next rerun."""
    st.session_state[PENDING_PREVIOUS_CATALOG_RESTORE_KEY] = True


def apply_pending_previous_catalog_restore_before_widgets(
    st: Any,
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]] | None = None,
    invalidate_backing,
) -> bool:
    """Apply queued previous-catalog restore before sidebar/global widgets render."""
    if not st.session_state.pop(PENDING_PREVIOUS_CATALOG_RESTORE_KEY, None):
        return False
    return restore_previous_catalog_song(
        st,
        song_picker_catalog=song_picker_catalog,
        song_library=song_library,
        invalidate_backing=invalidate_backing,
    )


def restore_previous_catalog_song(
    st: Any,
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]] | None = None,
    invalidate_backing,
) -> bool:
    """Restore the previous catalog song (browser-back style shortcut)."""
    snap = previous_catalog_snapshot(st.session_state)
    if not snap:
        return False
    pick_key = str(snap.get("pick_key") or "").strip()
    selected = dict(snap.get("selected_song") or {})
    original_key = str(snap.get("original_key") or selected.get("key") or "C").strip() or "C"
    display_key = str(snap.get("display_key") or original_key).strip() or original_key
    from songs.state import apply_pick_key

    data = apply_pick_key(
        st,
        pick_key,
        song_picker_catalog,
        song_library=song_library,
        skip_activity_log=True,
    )
    if not data:
        return False
    selected.setdefault("title", str(data.get("title") or ""))
    selected.setdefault("artist", str(data.get("artist") or ""))
    selected.setdefault("key", str(data.get("key") or original_key))
    selected["pick_key"] = pick_key
    commit_catalog_active_song(
        st,
        pick_key=pick_key,
        selected_song=selected,
        original_key=original_key,
        display_key=display_key,
        invalidate_backing=invalidate_backing,
        reason="previous_catalog_restore",
    )
    return True


def restore_last_catalog_active_song(
    st: Any,
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]] | None = None,
    invalidate_backing,
) -> bool:
    """Restore the catalog song active before Custom Progression mode."""
    from songs.key_state import apply_display_key_for_active_song, song_display_identity
    from songs.state import apply_pick_key

    session = st.session_state
    snap = session.get(CATALOG_BEFORE_CUSTOM_KEY) or session.get(LAST_CATALOG_STATE_KEY)
    if not isinstance(snap, dict) or not snap.get("pick_key"):
        return False
    pick_key = str(snap.get("pick_key") or "").strip()
    if not pick_key or pick_key.startswith("custom::"):
        return False
    data = apply_pick_key(
        st,
        pick_key,
        song_picker_catalog,
        song_library=song_library,
        skip_activity_log=True,
    )
    if not data:
        return False
    original_key = str(snap.get("original_key") or data.get("key") or "C").strip() or "C"
    display_key = str(snap.get("display_key") or original_key).strip() or original_key
    identity = song_display_identity(
        str(data.get("title") or ""),
        str(data.get("artist") or ""),
        original_key,
    )
    apply_display_key_for_active_song(st, original_key, identity, pending_key=display_key)
    note_active_source_change(st, invalidate_backing=invalidate_backing)
    return True


def commit_catalog_active_song(
    st: Any,
    *,
    pick_key: str,
    selected_song: dict[str, Any],
    original_key: str,
    display_key: str,
    invalidate_backing,
    reason: str = "catalog_restore",
) -> None:
    """Promote a catalog song to the global active song and canonical blob."""
    from active_song_state import write_canonical_active_song_state
    from songs.playback_defaults import (
        active_song_sync_id,
        canonical_active_song_bpm,
        default_groove_for_song,
        get_song_default_meter,
        playback_song_id,
    )
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    session = st.session_state
    session[USER_CATALOG_SOURCE_CHOICE_KEY] = True
    set_catalog_source(session)
    session[SELECTED_SONG_STATE_KEY] = dict(selected_song)
    session[ACTIVE_CATALOG_PICK_KEY] = str(pick_key or "").strip()
    original_key = str(original_key or selected_song.get("key") or "C").strip() or "C"
    display_key = str(display_key or original_key).strip() or original_key
    if reason == "catalog_source_switch":
        display_key = original_key
    lib_record = dict(selected_song)
    default_bpm = canonical_active_song_bpm(lib_record)
    default_groove = default_groove_for_song(lib_record, infer_fn=lambda _rec, _fb: "Auto")
    default_meter = get_song_default_meter(lib_record)
    _pid = playback_song_id(
        is_custom=False,
        song_title=str(selected_song.get("title") or ""),
        song_artist=str(selected_song.get("artist") or ""),
    )
    sync_id = active_song_sync_id(pick_key=str(pick_key or "").strip(), playback_song_id=_pid, is_custom=False)
    on_active_song_identity_changed(
        st,
        pick_key=str(pick_key or "").strip(),
        title=str(selected_song.get("title") or ""),
        artist=str(selected_song.get("artist") or ""),
        original_key=original_key,
        is_custom=False,
        sync_id=sync_id,
        default_bpm=default_bpm,
        default_groove=default_groove,
        default_meter=default_meter,
        display_key=display_key,
        song_data=lib_record,
        invalidate_backing=invalidate_backing,
        force_reset=reason in ("catalog_source_switch", "last_catalog_restore", "previous_catalog_restore"),
    )
    sync_song_picker_source_widget(session, force=True)
    note_active_source_change(st, invalidate_backing=invalidate_backing)
    ctx = {
        "pick_key": str(pick_key or "").strip(),
        "display_key": str(display_key or original_key).strip() or original_key,
        "instrument": str(session.get("instrument") or "").strip(),
        "level": str(session.get("level") or "").strip(),
        "focus": str(session.get("focus") or "").strip(),
        "selected_song": dict(selected_song),
        "music_source": SOURCE_CATALOG,
    }
    write_canonical_active_song_state(session, ctx, reason=reason, local_edit=True)
    try:
        from songs.state import persist_music_local_state

        persist_music_local_state(st)
    except ImportError:
        pass


def switch_to_catalog_from_custom(
    st: Any,
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]] | None = None,
    invalidate_backing,
) -> bool:
    """Leave Custom Progression for the last catalog song (or current catalog pick)."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY, apply_pick_key, first_valid_pick_key

    session = st.session_state
    if not is_custom_progression(session):
        return False
    session[USER_CATALOG_SOURCE_CHOICE_KEY] = True

    def _try_restore_from_snap(snap: dict[str, Any]) -> bool:
        pick_key = str(snap.get("pick_key") or "").strip()
        if not pick_key or pick_key.startswith("custom::"):
            return False
        selected = dict(snap.get("selected_song") or {})
        original_key = str(snap.get("original_key") or selected.get("key") or "C").strip() or "C"
        display_key = str(snap.get("display_key") or original_key).strip() or original_key
        data = apply_pick_key(
            st,
            pick_key,
            song_picker_catalog,
            song_library=song_library,
            skip_activity_log=True,
        )
        if not data:
            return False
        selected.setdefault("title", str(data.get("title") or ""))
        selected.setdefault("artist", str(data.get("artist") or ""))
        selected.setdefault("key", str(data.get("key") or original_key))
        selected["pick_key"] = pick_key
        commit_catalog_active_song(
            st,
            pick_key=pick_key,
            selected_song=selected,
            original_key=original_key,
            display_key=display_key,
            invalidate_backing=invalidate_backing,
            reason="last_catalog_restore",
        )
        return True

    snap = session.get(CATALOG_BEFORE_CUSTOM_KEY)
    if isinstance(snap, dict) and _try_restore_from_snap(snap):
        return True
    snap = session.get(LAST_CATALOG_STATE_KEY)
    if isinstance(snap, dict) and _try_restore_from_snap(snap):
        return True

    for pick_key in session.get(CATALOG_RECENT_PICK_KEYS) or []:
        pk = str(pick_key or "").strip()
        if not pk or pk.startswith("custom::"):
            continue
        if _try_restore_from_snap({"pick_key": pk, "selected_song": {}, "original_key": "C", "display_key": "C"}):
            return True

    pick_key = str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if pick_key and not pick_key.startswith("custom::"):
        data = apply_pick_key(
            st,
            pick_key,
            song_picker_catalog,
            song_library=song_library,
            skip_activity_log=True,
        )
        if data:
            original_key = str(data.get("key") or "C").strip() or "C"
            display_key = original_key
            commit_catalog_active_song(
                st,
                pick_key=pick_key,
                selected_song={
                    "pick_key": pick_key,
                    "title": str(data.get("title") or ""),
                    "artist": str(data.get("artist") or ""),
                    "key": original_key,
                },
                original_key=original_key,
                display_key=display_key,
                invalidate_backing=invalidate_backing,
                reason="catalog_source_switch",
            )
            return True

    fallback = first_valid_pick_key(song_picker_catalog)
    if fallback and _try_restore_from_snap(
        {"pick_key": fallback, "selected_song": {}, "original_key": "C", "display_key": "C"}
    ):
        return True

    set_catalog_source(session)
    sync_song_picker_source_widget(session, force=True)
    note_active_source_change(st, invalidate_backing=invalidate_backing)
    return True


def on_song_picker_source_change(
    st: Any,
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]] | None = None,
    invalidate_backing,
) -> None:
    """Radio callback: switch catalog ↔ custom without post-render rerun loops."""
    choice = str(st.session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    if choice.startswith("Use Custom"):
        st.session_state.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)
        if not is_custom_progression(st.session_state):
            set_custom_source(st.session_state)
            note_active_source_change(st, invalidate_backing=invalidate_backing)
        try:
            from custom_progression_lab import cpl_active_from_session

            queue_custom_active_song_activation(st, cpl_active_from_session(st.session_state))
        except Exception:
            pass
        st.rerun()
        return
    st.session_state[USER_CATALOG_SOURCE_CHOICE_KEY] = True
    if is_custom_progression(st.session_state):
        switch_to_catalog_from_custom(
            st,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
            invalidate_backing=invalidate_backing,
        )
        st.rerun()


def reconcile_picker_music_source(session_state: dict[str, Any]) -> bool:
    """Align active source with Songs page picker widget before widgets render."""
    page = str(
        session_state.get("studio_page") or session_state.get("page") or ""
    ).strip()
    if page != "picker":
        return reconcile_music_picker_source_widget(session_state)
    choice = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    if choice.startswith("Use Custom") and not is_custom_progression(session_state):
        session_state.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)
        set_custom_source(session_state)
        session_state[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CUSTOM
        return True
    return reconcile_music_picker_source_widget(session_state)


def custom_original_key(active: dict[str, Any]) -> str:
    """User-chosen CPL original key (never inferred from chord analysis)."""
    from custom_progression_lab import cpl_draft_written_key, ensure_original_structure

    return cpl_draft_written_key(ensure_original_structure(active))


def _catalog_original_key_for_session(
    session_state: dict[str, Any],
    rec: dict[str, Any] | None = None,
) -> str:
    """Original/home key from active pick identity — not a stale card record."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    selected = session_state.get(SELECTED_SONG_STATE_KEY) or {}
    pick_key = str(
        session_state.get(ACTIVE_CATALOG_PICK_KEY)
        or selected.get("pick_key")
        or ""
    ).strip()
    selected_pick = str(selected.get("pick_key") or "").strip()
    if pick_key and selected_pick == pick_key and selected.get("key"):
        return str(selected.get("key") or "C").strip() or "C"
    record = rec or {}
    if record.get("key"):
        return str(record.get("key") or "C").strip() or "C"
    return str(selected.get("key") or "C").strip() or "C"


def resolve_active_song_keys(
    session_state: dict[str, Any],
    rec: dict[str, Any] | None = None,
) -> tuple[str, str, str | None]:
    """Single source of truth: original, display/practice, optional written chart key."""
    from songs.key_state import get_authoritative_display_key, trace_display_key_surface

    if cpl_session_is_active(session_state):
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
            default_active_progression,
            ensure_original_structure,
        )

        active = ensure_original_structure(
            session_state.get(CPL_ACTIVE_KEY) or default_active_progression()
        )
        original = custom_original_key(active)
        display = get_authoritative_display_key(
            session_state,
            original_key=original,
            surface="song_card",
        )
    else:
        original = _catalog_original_key_for_session(session_state, rec)
        display = get_authoritative_display_key(
            session_state,
            original_key=original,
            surface="song_card",
        )
    trace_display_key_surface(
        session_state,
        "song_card",
        display,
        source="resolve_active_song_keys",
    )
    from instrument_transposition import (
        chart_in_instrument_key,
        effective_chart_key,
        is_transposing_instrument,
    )

    written: str | None = None
    inst = str(session_state.get("instrument") or "Piano")
    if is_transposing_instrument(inst) and chart_in_instrument_key(session_state):
        chart_k, _ = effective_chart_key(display, inst, session_state)
        written = chart_k
    return original, display, written


def active_song_key_pair(
    session_state: dict[str, Any],
    rec: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Original key and Practice / Concert key for Active Song cards.

    For chart/coach/analysis surfaces use ``resolve_active_musical_key()`` instead
    (written or guitar shape key when those modes are active).
    """
    original, display, _written = resolve_active_song_keys(session_state, rec)
    return original, display


def active_song_musical_key(
    session_state: dict[str, Any],
    rec: dict[str, Any] | None = None,
    *,
    instrument: str | None = None,
    surface: str = "song_card",
) -> str:
    """Chart/analysis key honoring written-instrument and guitar capo shape modes."""
    from songs.key_state import resolve_active_musical_key

    return resolve_active_musical_key(
        session_state,
        rec=rec,
        instrument=instrument,
        surface=surface,
    ).chart_key


def active_song_written_chart_key(
    session_state: dict[str, Any],
    *,
    display_key: str | None = None,
) -> str | None:
    """Written/shape chart key for cards — transposing instrument or guitar capo shape."""
    from instrument_transposition import (
        chart_in_instrument_key,
        effective_chart_key,
        is_transposing_instrument,
    )

    _, display = active_song_key_pair(session_state)
    concert = str(display_key or display or "C").strip() or "C"
    inst = str(session_state.get("instrument") or "Piano")
    if is_transposing_instrument(inst) and chart_in_instrument_key(session_state):
        chart_k, _ = effective_chart_key(concert, inst, session_state)
        return chart_k
    try:
        from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY

        if inst == "Guitar" and session_state.get(CAPO_ENABLED_KEY):
            shape = str(session_state.get(CAPO_SHAPE_KEY) or "").strip()
            if shape:
                return shape
    except ImportError:
        pass
    return None


def note_active_source_change(st: Any, *, invalidate_backing) -> bool:
    """Invalidate backing/chart caches when active song source or pick changes."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    from .playback_defaults import reset_playback_song_tracking

    session_state = st.session_state
    current_source = session_state.get(ACTIVE_MUSIC_SOURCE_KEY, SOURCE_CATALOG)
    previous_source = session_state.get(_LAST_SOURCE_KEY)
    current_pick = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    previous_pick = session_state.get(_LAST_ACTIVE_PICK_KEY)

    session_state[_LAST_SOURCE_KEY] = current_source
    session_state[_LAST_ACTIVE_PICK_KEY] = current_pick

    source_changed = previous_source is not None and previous_source != current_source
    pick_changed = previous_pick is not None and previous_pick != current_pick
    if source_changed or pick_changed:
        reset_playback_song_tracking(st)
        invalidate_backing(st)
        try:
            from studio_cache import invalidate_session_cache

            invalidate_session_cache(session_state, "chart_bundle")
        except Exception:
            pass
        return True
    return False


ACTIVE_SONG_IDENTITY_KEY = "_active_song_identity"
PREVIOUS_ACTIVE_SONG_IDENTITY_KEY = "_previous_active_song_identity"
SONG_IDENTITY_DIAG_KEY = "_song_identity_diag"


def compute_active_song_identity(
    *,
    pick_key: str = "",
    title: str = "",
    artist: str = "",
    original_key: str = "",
    is_custom: bool = False,
    custom_revision: str = "",
) -> str:
    """Stable identity string for catalog pick_key or custom progression revision."""
    pk = str(pick_key or "").strip()
    if is_custom or pk.startswith("custom::"):
        rev = str(custom_revision or "").strip()
        if rev:
            return f"cpl::{rev}"
        if pk:
            return f"cpl::{pk}"
        return f"cpl::{title}|{artist}|{original_key}"
    if pk:
        return f"pk::{pk}"
    return f"cat::{title}|{artist}|{original_key}"


def on_active_song_identity_changed(
    st: Any,
    *,
    pick_key: str,
    title: str,
    artist: str,
    original_key: str,
    is_custom: bool,
    sync_id: str,
    default_bpm: int,
    default_groove: str,
    default_meter: str,
    display_key: str | None = None,
    custom_revision: str = "",
    song_data: dict[str, Any] | None = None,
    invalidate_backing,
    force_reset: bool = False,
) -> bool:
    """Reset display key and backing defaults when the active song identity changes.

    Must run before widget-bound session keys (``display_key``, BPM slider, etc.)
    are instantiated for the rerun.
    """
    from songs.key_state import apply_display_key_for_active_song, song_display_identity
    from songs.playback_defaults import (
        canonicalize_backing_defaults_for_song,
        prime_active_song_bpm,
        reset_playback_song_tracking,
    )

    session = st.session_state
    new_identity = compute_active_song_identity(
        pick_key=pick_key,
        title=title,
        artist=artist,
        original_key=original_key,
        is_custom=is_custom,
        custom_revision=custom_revision,
    )
    prev_identity = session.get(ACTIVE_SONG_IDENTITY_KEY)
    session[PREVIOUS_ACTIVE_SONG_IDENTITY_KEY] = prev_identity
    identity_changed = force_reset or (
        prev_identity is not None and prev_identity != new_identity
    )

    if identity_changed:
        try:
            from songs.key_state import PENDING_DISPLAY_KEY

            session.pop(PENDING_DISPLAY_KEY, None)
        except ImportError:
            pass
        try:
            from practice_setup_globals import DISPLAY_KEY_CHANGE_SOURCE_KEY

            session.pop(DISPLAY_KEY_CHANGE_SOURCE_KEY, None)
        except ImportError:
            pass
        target_display = str(display_key if display_key is not None else original_key).strip() or original_key
        song_identity = song_display_identity(title, artist, original_key, pick_key=pick_key)
        apply_display_key_for_active_song(
            st,
            original_key,
            song_identity,
            pending_key=target_display,
        )
        try:
            from backing_source_navigation import PRACTICE_SOURCE_DISPLAY_KEY

            session[PRACTICE_SOURCE_DISPLAY_KEY] = target_display
        except ImportError:
            pass
        reset_playback_song_tracking(st)
        invalidate_backing(st)
        try:
            from studio_cache import invalidate_session_cache

            invalidate_session_cache(session, "chart_bundle")
        except Exception:
            pass
        prime_active_song_bpm(st, sync_id=sync_id, active_song_bpm=int(default_bpm))
        canonicalize_backing_defaults_for_song(
            st,
            sync_id=sync_id,
            active_song_bpm=int(default_bpm),
            active_song_groove=str(default_groove),
            active_song_meter=str(default_meter),
        )

    if identity_changed:
        try:
            from songs.key_state import DISPLAY_KEY_OWNER_IDENTITY_KEY

            session.pop(DISPLAY_KEY_OWNER_IDENTITY_KEY, None)
        except ImportError:
            pass

    session[ACTIVE_SONG_IDENTITY_KEY] = new_identity
    try:
        from practice_setup_globals import DISPLAY_KEY_CHANGE_SOURCE_KEY

        last_change_source = session.get(DISPLAY_KEY_CHANGE_SOURCE_KEY)
    except ImportError:
        last_change_source = None
    session[SONG_IDENTITY_DIAG_KEY] = {
        "active_song_id": new_identity,
        "active_song_identity": new_identity,
        "previous_active_song_identity": prev_identity,
        "active_music_source": SOURCE_CUSTOM if is_custom else SOURCE_CATALOG,
        "song_source": SOURCE_CUSTOM if is_custom else SOURCE_CATALOG,
        "pick_key": pick_key,
        "original_key": original_key,
        "practice_display_key": session.get("display_key"),
        "display_key": session.get("display_key"),
        "last_song_change_source": last_change_source,
        "default_bpm": default_bpm,
        "backing_bpm": session.get("backing_track_bpm"),
        "default_style": default_groove,
        "backing_groove": session.get("backing_groove_style"),
        "default_meter": default_meter,
        "backing_meter": session.get("backing_time_signature"),
        "identity_changed": identity_changed,
    }
    return identity_changed


def active_source_labels(
    session_state: dict[str, Any],
    *,
    catalog_title: str,
    catalog_artist: str,
    custom_name: str,
) -> tuple[str, str]:
    """Return ``(source_kind, source_detail)`` for the sidebar active-source banner."""
    if is_custom_progression(session_state):
        return "Custom Progression", str(custom_name or "Custom Progression")
    title = str(catalog_title or "").strip()
    artist = str(catalog_artist or "").strip()
    detail = f"{title} — {artist}".strip(" —") if title or artist else ""
    return "Song", detail


def _parse_legacy_active_source_markdown(text: str) -> tuple[str, str]:
    """Older builds returned one markdown string (``Song Picker — title — artist``)."""
    raw = str(text or "").replace("**", "").strip()
    if raw.lower().startswith("active source:"):
        raw = raw.split(":", 1)[1].strip()
    parts = [p.strip() for p in raw.split("—") if p.strip()]
    if not parts:
        return "Song", ""
    kind = parts[0].replace("Song Picker", "Song").strip() or "Song"
    detail = " — ".join(parts[1:]) if len(parts) > 1 else ""
    return kind, detail


def unpack_active_source_banner(result: Any) -> tuple[str, str]:
    """Normalize banner return value to exactly ``(kind, detail)``."""
    if isinstance(result, tuple):
        if len(result) >= 2:
            return str(result[0]), str(result[1])
        if len(result) == 1:
            return str(result[0]), ""
        return "Song", ""
    if isinstance(result, str):
        return _parse_legacy_active_source_markdown(result)
    if result is None:
        return "Song", ""
    return "Song", str(result)


def active_source_banner(
    session_state: dict[str, Any],
    *,
    catalog_title: str,
    catalog_artist: str,
    custom_name: str,
) -> tuple[str, str]:
    """Return ``(source_kind, source_detail)`` — always a 2-tuple (never markdown)."""
    kind, detail = active_source_labels(
        session_state,
        catalog_title=catalog_title,
        catalog_artist=catalog_artist,
        custom_name=custom_name,
    )
    return (str(kind), str(detail))


def display_key_context(
    session_state: dict[str, Any],
    *,
    catalog_song_data: dict[str, Any],
    cpl_active_key: str,
) -> tuple[str, tuple]:
    """Original/home key and identity tuple for the global display-key widget."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    if custom_progression_is_active(session_state) or cpl_session_is_active(session_state):
        from custom_progression_lab import (
            default_active_progression,
            ensure_original_structure,
        )

        ensure_custom_active_song_identity(session_state, cpl_active_key=cpl_active_key)
        active = ensure_original_structure(
            session_state.get(cpl_active_key) or default_active_progression()
        )
        home = custom_original_key(active)
        title = active.get("name", "Custom Progression")
        pick_key = str(
            session_state.get(ACTIVE_CATALOG_PICK_KEY)
            or (session_state.get(SELECTED_SONG_STATE_KEY) or {}).get("pick_key")
            or ""
        ).strip()
        from songs.key_state import song_display_identity

        return home, song_display_identity(
            str(title),
            "Custom progression",
            home,
            pick_key=pick_key,
        )

    original = catalog_song_data.get("key", "C")
    pick_key = str(
        session_state.get(ACTIVE_CATALOG_PICK_KEY)
        or (session_state.get(SELECTED_SONG_STATE_KEY) or {}).get("pick_key")
        or ""
    ).strip()
    from songs.key_state import song_display_identity

    return original, song_display_identity(
        str(catalog_song_data.get("title") or ""),
        str(catalog_song_data.get("artist") or ""),
        str(original),
        pick_key=pick_key,
    )


def custom_pick_key_for(active: dict[str, Any]) -> str:
    """Stable session pick_key for a custom progression (not a catalog pk:: id)."""
    title = str(active.get("name") or "My Progression").strip() or "My Progression"
    rev = str(active.get("id") or "").strip()
    if rev:
        return f"custom::{rev}"
    safe = title.replace(":", "_").replace("/", "_")[:80]
    return f"custom::{safe}"


def _custom_pick_key_suffix(pick_key: str) -> str:
    return str(pick_key or "").strip().removeprefix("custom::").strip()


def _title_from_custom_blob(blob: dict[str, Any], store_name: str = "") -> tuple[str, str]:
    title = str(blob.get("name") or store_name or "").strip()
    artist = str(blob.get("artist") or "Your progression").strip() or "Your progression"
    return title, artist


def custom_display_title_for_pick_key(
    session_state: dict[str, Any],
    pick_key: str,
    *,
    fallback_title: str = "",
    cpl_active_key: str = "cpl_active_progression",
    cpl_saved_key: str = "cpl_saved_progressions",
) -> str:
    """User-facing title for a custom song (never an internal id/code)."""
    from custom_progression_lab import default_active_progression, ensure_original_structure
    from songs.state import SELECTED_SONG_STATE_KEY

    pk = str(pick_key or "").strip()
    fb = str(fallback_title or "").strip()
    if not pk.startswith("custom::"):
        return fb
    suffix = _custom_pick_key_suffix(pk)
    if fb and not fb.startswith("custom::") and fb != suffix:
        return fb

    sel = session_state.get(SELECTED_SONG_STATE_KEY)
    if isinstance(sel, dict) and str(sel.get("pick_key") or "").strip() == pk:
        title = str(sel.get("title") or "").strip()
        if title and title != suffix:
            return title

    active = ensure_original_structure(
        session_state.get(cpl_active_key) or default_active_progression()
    )
    active_id = str(active.get("id") or "").strip()
    active_name = str(active.get("name") or "").strip()
    if active_id and suffix == active_id and active_name:
        return active_name
    if active_name and suffix == active_name.replace(":", "_").replace("/", "_")[:80]:
        return active_name

    saved = session_state.get(cpl_saved_key) or {}
    if isinstance(saved, dict):
        for store_name, blob in saved.items():
            if not isinstance(blob, dict):
                continue
            blob_id = str(blob.get("id") or "").strip()
            blob_name = str(blob.get("name") or store_name).strip()
            if suffix and (suffix == blob_id or suffix == blob_name or suffix == store_name):
                return blob_name or store_name

    meta = session_state.get("active_song_state")
    if isinstance(meta, dict) and str(meta.get("pick_key") or "").strip() == pk:
        title = str(meta.get("custom_progression_name") or meta.get("title") or "").strip()
        if title and title != suffix:
            return title

    if suffix and " " in suffix.replace("_", " "):
        return suffix.replace("_", " ")
    return active_name or fb or "My Progression"


def custom_display_artist_for_pick_key(
    session_state: dict[str, Any],
    pick_key: str,
    *,
    fallback_artist: str = "",
    cpl_active_key: str = "cpl_active_progression",
    cpl_saved_key: str = "cpl_saved_progressions",
) -> str:
    """User-facing artist for a custom song pick_key."""
    from custom_progression_lab import default_active_progression, ensure_original_structure

    pk = str(pick_key or "").strip()
    fb = str(fallback_artist or "").strip() or "Your progression"
    if not pk.startswith("custom::"):
        return fb
    suffix = _custom_pick_key_suffix(pk)

    active = ensure_original_structure(
        session_state.get(cpl_active_key) or default_active_progression()
    )
    active_id = str(active.get("id") or "").strip()
    if active_id and suffix == active_id:
        return str(active.get("artist") or fb).strip() or fb

    saved = session_state.get(cpl_saved_key) or {}
    if isinstance(saved, dict):
        for store_name, blob in saved.items():
            if not isinstance(blob, dict):
                continue
            blob_id = str(blob.get("id") or "").strip()
            blob_name = str(blob.get("name") or store_name).strip()
            if suffix and (suffix == blob_id or suffix == blob_name or suffix == store_name):
                return _title_from_custom_blob(blob, store_name)[1]

    return fb


def _push_recent_custom_name(session_state: dict[str, Any], name: str) -> None:
    label = str(name or "").strip()
    if not label:
        return
    recent = [
        str(n).strip()
        for n in (session_state.get(CUSTOM_RECENT_ACTIVE_NAMES_KEY) or [])
        if str(n).strip()
    ]
    if label in recent:
        recent.remove(label)
    recent.insert(0, label)
    session_state[CUSTOM_RECENT_ACTIVE_NAMES_KEY] = recent[:8]


def custom_song_data_from_active(active: dict[str, Any]) -> dict[str, Any]:
    """Catalog-shaped song row for charts/backing when Custom Progression is active."""
    from custom_progression_lab import (
        cpl_draft_written_key,
        ensure_original_structure,
        sections_to_chord_lists,
    )

    active = ensure_original_structure(active)
    title = str(active.get("name") or "My Progression")
    home_key = cpl_draft_written_key(active)
    artist = str(active.get("artist") or "").strip()
    sections = sections_to_chord_lists(active.get("original_sections") or {})
    style = str(active.get("progression_style") or "Custom")
    bpm = int(active.get("bpm") or 100)
    groove = str(active.get("groove_style") or "Auto")
    meter = str(active.get("time_signature") or "4/4")
    return {
        "title": title,
        "artist": artist or "Your progression",
        "genre": "Custom",
        "key": home_key,
        "sections": sections,
        "chart_versions": {
            "Beginner": sections,
            "Intermediate": sections,
            "Advanced": sections,
        },
        "chart_status": "custom",
        "extensions": {
            "default_bpm": bpm,
            "default_groove": groove,
            "time_signature": meter,
            "arrangement_notes": f"Custom progression — {style} feel",
        },
    }


def custom_song_context_from_session(
    session_state: dict[str, Any],
    *,
    cpl_active_key: str = "cpl_active_progression",
) -> tuple[str, str, dict[str, Any]]:
    """Return (genre, title, song_data) for an active Custom Progression song."""
    from custom_progression_lab import default_active_progression, ensure_original_structure

    active = ensure_original_structure(
        session_state.get(cpl_active_key) or default_active_progression()
    )
    song_data = custom_song_data_from_active(active)
    return "Custom", str(song_data.get("title") or "My Progression"), song_data


def custom_selected_song_record(active: dict[str, Any]) -> dict[str, Any]:
    """Sidebar/global ``selected_song`` shape for an active custom progression."""
    from custom_progression_lab import ensure_original_structure

    active = ensure_original_structure(active)
    home_key = custom_original_key(active)
    title = str(active.get("name") or "My Progression").strip() or "My Progression"
    artist = str(active.get("artist") or "Your progression").strip() or "Your progression"
    pick_key = custom_pick_key_for(active)
    return {
        "pick_key": pick_key,
        "title": title,
        "artist": artist,
        "key": home_key,
        "source": SOURCE_CUSTOM,
        "is_custom": True,
    }


def ensure_custom_active_song_identity(
    session_state: dict[str, Any],
    *,
    cpl_active_key: str = "cpl_active_progression",
) -> dict[str, Any] | None:
    """Sync CPL pick_key, selected_song, and active identity before key widgets resolve."""
    if not cpl_session_is_active(session_state):
        return None
    try:
        from custom_progression_lab import default_active_progression, ensure_original_structure
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY
    except ImportError:
        return None

    active_raw = session_state.get(cpl_active_key)
    if active_raw is None:
        selected = session_state.get(SELECTED_SONG_STATE_KEY)
        if isinstance(selected, dict) and str(selected.get("pick_key") or "").strip():
            return selected
        return None

    active = ensure_original_structure(active_raw or default_active_progression())
    selected = custom_selected_song_record(active)
    pick_key = str(selected.get("pick_key") or "").strip()
    existing_pick = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if not existing_pick.startswith("custom::"):
        selected_state = session_state.get(SELECTED_SONG_STATE_KEY) or {}
        existing_pick = str(selected_state.get("pick_key") or "").strip()
    if not existing_pick.startswith("custom::"):
        try:
            from active_song_state import ACTIVE_SONG_STATE_KEY

            meta = session_state.get(ACTIVE_SONG_STATE_KEY)
            if isinstance(meta, dict):
                existing_pick = str(meta.get("pick_key") or "").strip()
        except ImportError:
            pass
    if existing_pick.startswith("custom::"):
        pick_key = existing_pick
        selected = {**selected, "pick_key": pick_key}
    if pick_key:
        session_state[ACTIVE_CATALOG_PICK_KEY] = pick_key
    session_state[SELECTED_SONG_STATE_KEY] = selected
    identity = compute_active_song_identity(
        pick_key=pick_key,
        title=str(selected.get("title") or ""),
        artist=str(selected.get("artist") or ""),
        original_key=str(selected.get("key") or "C"),
        is_custom=True,
        custom_revision=str(active.get("id") or ""),
    )
    session_state[ACTIVE_SONG_IDENTITY_KEY] = identity
    return selected


def resolve_active_song_identity(
    session_state: dict[str, Any],
    *,
    cpl_active_key: str = "cpl_active_progression",
) -> str:
    """Recompute stable identity for display-key ownership (CPL-aware)."""
    try:
        from songs.key_state import DISPLAY_KEY_OWNER_IDENTITY_KEY
    except ImportError:
        DISPLAY_KEY_OWNER_IDENTITY_KEY = "_display_key_owner_identity"

    owner = str(session_state.get(DISPLAY_KEY_OWNER_IDENTITY_KEY) or "").strip()
    cached = str(session_state.get(ACTIVE_SONG_IDENTITY_KEY) or "").strip()
    if owner and cached and owner == cached:
        return cached

    if cpl_session_is_active(session_state):
        ensure_custom_active_song_identity(session_state, cpl_active_key=cpl_active_key)
        identity = str(session_state.get(ACTIVE_SONG_IDENTITY_KEY) or "").strip()
        if identity:
            return identity
        try:
            from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY
        except ImportError:
            return cached
        selected = session_state.get(SELECTED_SONG_STATE_KEY) or {}
        pick_key = str(
            session_state.get(ACTIVE_CATALOG_PICK_KEY) or selected.get("pick_key") or ""
        ).strip()
        return compute_active_song_identity(
            pick_key=pick_key,
            title=str(selected.get("title") or ""),
            artist=str(selected.get("artist") or ""),
            original_key=str(selected.get("key") or "C"),
            is_custom=True,
            custom_revision="",
        )

    try:
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY
    except ImportError:
        return cached

    selected = session_state.get(SELECTED_SONG_STATE_KEY) or {}
    pick_key = str(
        session_state.get(ACTIVE_CATALOG_PICK_KEY) or selected.get("pick_key") or ""
    ).strip()
    return compute_active_song_identity(
        pick_key=pick_key,
        title=str(selected.get("title") or ""),
        artist=str(selected.get("artist") or ""),
        original_key=str(selected.get("key") or "C"),
        is_custom=False,
    )


def queue_custom_active_song_activation(
    st: Any,
    active: dict[str, Any],
    *,
    cpl_active_key: str = "cpl_active_progression",
    toast_title: str | None = None,
) -> None:
    """Queue CPL activation for the next run (before sidebar/global widgets render)."""
    from custom_progression_lab import ensure_all_cpl_sections, ensure_original_structure

    session = st.session_state
    active = ensure_original_structure(active)
    active["original_sections"] = ensure_all_cpl_sections(active.get("original_sections"))
    active["user_locked_home_key"] = True
    session[cpl_active_key] = active
    payload: dict[str, Any] = {"cpl_active_key": cpl_active_key}
    if toast_title:
        payload["toast_title"] = str(toast_title).strip()
    session[PENDING_CUSTOM_ACTIVE_SONG_KEY] = payload


def queue_custom_library_action(
    st: Any,
    *,
    name: str = "",
    action: str = "activate",
) -> None:
    """Queue saved custom song load/activate/edit for before-widget application."""
    payload: dict[str, Any] = {"action": str(action or "activate").strip()}
    label = str(name or "").strip()
    if label:
        payload["name"] = label
    st.session_state[PENDING_CUSTOM_LIBRARY_ACTION_KEY] = payload


def apply_pending_custom_library_action_before_widgets(
    st: Any,
    *,
    invalidate_backing,
) -> bool:
    """Load a saved custom song (or reseed active) before sidebar/global widgets render."""
    session = st.session_state
    pending = session.pop(PENDING_CUSTOM_LIBRARY_ACTION_KEY, None)
    if not isinstance(pending, dict):
        return False
    action = str(pending.get("action") or "activate").strip()
    from custom_progression_lab import (
        CPL_SAVED_KEY,
        apply_cpl_session_progression,
        cpl_active_from_session,
        load_saved_progression,
        start_new_progression,
    )

    if action == "edit_active":
        active = cpl_active_from_session(session)
    elif action == "new_song":
        active = start_new_progression()
    else:
        name = str(pending.get("name") or "").strip()
        if not name:
            return False
        saved = session.get(CPL_SAVED_KEY) or {}
        active = load_saved_progression(saved, name)

    apply_cpl_session_progression(session, active, reset_display_key=True)

    if action == "activate":
        song_name = str(pending.get("name") or active.get("name") or "").strip()
        commit_custom_active_song(st, active, invalidate_backing=invalidate_backing)
        if song_name:
            session["_cpl_activation_toast"] = song_name
        session["_custom_active_song_applied_this_run"] = True
    elif action in ("edit", "edit_active", "new_song"):
        try:
            from studio_nav_history import navigate_studio_page

            navigate_studio_page(session, "custom")
        except ImportError:
            session["studio_page"] = "custom"

    session["_custom_library_action_applied_this_run"] = True
    return True


def apply_pending_custom_active_song_activation_before_widgets(
    st: Any,
    *,
    invalidate_backing,
) -> bool:
    """Apply queued CPL activation before any widget-bound session keys are touched."""
    session = st.session_state
    pending = session.pop(PENDING_CUSTOM_ACTIVE_SONG_KEY, None)
    if not isinstance(pending, dict):
        return False
    cpl_active_key = str(pending.get("cpl_active_key") or "cpl_active_progression").strip()
    active = session.get(cpl_active_key)
    if not isinstance(active, dict):
        return False
    commit_custom_active_song(
        st,
        active,
        cpl_active_key=cpl_active_key,
        invalidate_backing=invalidate_backing,
    )
    toast_title = str(pending.get("toast_title") or "").strip()
    if toast_title:
        session["_cpl_activation_toast"] = toast_title
    session["_custom_active_song_applied_this_run"] = True
    return True


def commit_custom_active_song(
    st: Any,
    active: dict[str, Any],
    *,
    cpl_active_key: str = "cpl_active_progression",
    invalidate_backing,
) -> dict[str, Any]:
    """Promote CPL draft to the global active song (source, title, key, playback, cloud).

    Must run before sidebar/global widgets render. Use ``queue_custom_active_song_activation``
    from page callbacks, then ``apply_pending_custom_active_song_activation_before_widgets``
    at app startup.
    """
    from custom_progression_lab import (
        ensure_all_cpl_sections,
        ensure_original_structure,
        prepare_cpl_backing_handoff,
        cpl_draft_written_key,
        cpl_default_groove_for_active,
    )
    from songs.playback_defaults import (
        active_song_sync_id,
        canonical_active_song_bpm,
        get_song_default_meter,
        normalize_groove_label,
        playback_song_id,
    )
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    session = st.session_state
    active = ensure_original_structure(active)
    active["original_sections"] = ensure_all_cpl_sections(active.get("original_sections"))
    active["user_locked_home_key"] = True
    session[cpl_active_key] = active
    _push_recent_custom_name(session, str(active.get("name") or "My Progression"))

    home_key = cpl_draft_written_key(active)
    selected = custom_selected_song_record(active)
    pick_key = str(selected.get("pick_key") or "").strip()
    practice_key = home_key
    try:
        from songs.key_state import canonical_display_key_for_pick

        saved = canonical_display_key_for_pick(session, pick_key)
        if saved:
            practice_key = saved
    except ImportError:
        pass

    set_custom_source(session)
    sync_song_picker_source_widget(session, force=True)

    default_bpm = int(active.get("bpm") or canonical_active_song_bpm(active) or 100)
    default_groove = normalize_groove_label(cpl_default_groove_for_active(active), song_data=active)
    default_meter = str(active.get("time_signature") or get_song_default_meter(active) or "4/4")
    song_id = playback_song_id(
        is_custom=True,
        song_title=str(active.get("name", "") or ""),
        song_artist="",
        custom_name=str(active.get("name", "") or ""),
        custom_revision=str(active.get("id", "") or ""),
    )
    sync_id = active_song_sync_id(pick_key=pick_key, playback_song_id=song_id, is_custom=True)
    on_active_song_identity_changed(
        st,
        pick_key=pick_key,
        title=str(selected.get("title") or ""),
        artist=str(selected.get("artist") or ""),
        original_key=home_key,
        is_custom=True,
        sync_id=sync_id,
        default_bpm=default_bpm,
        default_groove=default_groove,
        default_meter=default_meter,
        display_key=practice_key,
        custom_revision=str(active.get("id") or ""),
        song_data=active,
        invalidate_backing=invalidate_backing,
        force_reset=True,
    )
    note_active_source_change(st, invalidate_backing=invalidate_backing)

    session[SELECTED_SONG_STATE_KEY] = selected
    if pick_key:
        session[ACTIVE_CATALOG_PICK_KEY] = pick_key

    prepare_cpl_backing_handoff(session, active)

    try:
        from active_song_state import write_canonical_active_song_state
        from global_active_song_state import sync_active_song_to_canonical

        ctx = {
            "pick_key": pick_key,
            "display_key": practice_key,
            "instrument": str(session.get("instrument") or "").strip(),
            "level": str(session.get("level") or "").strip(),
            "focus": str(session.get("focus") or "").strip(),
            "selected_song": selected,
            "music_source": SOURCE_CUSTOM,
            "custom_progression_name": selected.get("title", ""),
            "custom_home_key": home_key,
        }
        write_canonical_active_song_state(
            session,
            ctx,
            reason="custom_active_song",
            local_edit=True,
        )
        sync_active_song_to_canonical(session)
    except ImportError:
        pass

    try:
        from songs.state import persist_music_local_state

        persist_music_local_state(st)
    except ImportError:
        pass

    try:
        from music_persistent_state import clear_music_ephemeral_default_song

        clear_music_ephemeral_default_song(session)
    except ImportError:
        pass

    return active


def build_active_chart_bundle(
    session_state: dict[str, Any],
    *,
    catalog_genre: str,
    catalog_song: str,
    catalog_song_data: dict[str, Any],
    level: str,
    display_key: str,
    cpl_active_key: str,
    sections_for_level: Callable[[dict, str], dict],
    transpose_sections: Callable[[dict, str], dict],
) -> dict[str, Any]:
    """Resolve genre, song, song_data, and chord sections for the active source."""
    if custom_progression_is_active(session_state):
        from custom_progression_lab import (
            cpl_default_groove_for_active,
            default_active_progression,
            ensure_all_cpl_sections,
            ensure_original_structure,
            sections_to_chord_lists,
        )

        active = ensure_original_structure(
            session_state.get(cpl_active_key) or default_active_progression()
        )
        active["original_sections"] = ensure_all_cpl_sections(active.get("original_sections"))
        session_state[cpl_active_key] = active
        home_key = custom_original_key(active)
        home_sections = active.get("original_sections") or {}
        level_source_sections = sections_to_chord_lists(home_sections)
        level_song_data = {
            "key": home_key,
            "sections": level_source_sections,
        }
        sections = transpose_sections(level_song_data, display_key)
        title = active.get("name", "Custom Progression")
        return {
            "source": SOURCE_CUSTOM,
            "genre": "Custom",
            "song": title,
            "song_data": {
                "title": title,
                "artist": "Your progression",
                "genre": "Custom",
                "key": home_key,
                "sections": level_source_sections,
                "chart_status": "custom",
                "trusted_core": False,
            },
            "original_key": home_key,
            "level_source_sections": level_source_sections,
            "sections": sections,
            "cpl_active": active,
            "default_bpm": int(active.get("bpm", 100) or 100),
            "default_loops": int(active.get("loops", 2) or 2),
            "default_groove": cpl_default_groove_for_active(active),
            "time_signature": active.get("time_signature", "4/4") or "4/4",
        }

    from backing_audio import infer_groove_style
    from .playback_defaults import default_bpm_for_song_data, default_groove_for_song

    level_source_sections = sections_for_level(catalog_song_data, level)
    level_song_data = {
        **catalog_song_data,
        "sections": level_source_sections,
    }
    sections = transpose_sections(level_song_data, display_key)
    ext = catalog_song_data.get("extensions") or {}
    return {
        "source": SOURCE_CATALOG,
        "genre": catalog_genre,
        "song": catalog_song,
        "song_data": catalog_song_data,
        "original_key": catalog_song_data.get("key", "C"),
        "level_source_sections": level_source_sections,
        "sections": sections,
        "cpl_active": None,
        "default_bpm": default_bpm_for_song_data(catalog_song_data),
        "default_loops": int(ext.get("default_loops", 2) or 2),
        "default_groove": default_groove_for_song(
            catalog_song_data,
            infer_fn=infer_groove_style,
        ),
        "time_signature": ext.get("time_signature", "4/4") or "4/4",
    }

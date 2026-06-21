"""Active music source: catalog song vs custom progression (shared session contract)."""

from __future__ import annotations

from typing import Any, Callable

ACTIVE_MUSIC_SOURCE_KEY = "active_music_source"
SOURCE_CATALOG = "catalog_song"
SOURCE_CUSTOM = "custom_progression"
_LAST_SOURCE_KEY = "_last_active_music_source"
PENDING_CUSTOM_ACTIVE_SONG_KEY = "_pending_custom_active_song_activation"
SONG_PICKER_SOURCE_CATALOG = "Song Selection (catalog song)"
SONG_PICKER_SOURCE_CUSTOM = "Use Custom Progression / Create Your Own Song"
SONG_PICKER_ACTIVE_SOURCE_KEY = "song_picker_active_source"
LAST_CATALOG_STATE_KEY = "_last_catalog_song_state"
USER_CATALOG_SOURCE_CHOICE_KEY = "_user_chose_catalog_music_source"
CATALOG_RECENT_PICK_KEYS = "catalog_recent_pick_keys"


def ensure_active_music_source(session_state: dict[str, Any]) -> None:
    session_state.setdefault(ACTIVE_MUSIC_SOURCE_KEY, SOURCE_CATALOG)


def is_custom_progression(session_state: dict[str, Any]) -> bool:
    return session_state.get(ACTIVE_MUSIC_SOURCE_KEY) == SOURCE_CUSTOM


def custom_progression_is_active(session_state: dict[str, Any]) -> bool:
    """True when Custom Progression is the active song (session or canonical blob)."""
    if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        return False
    if is_custom_progression(session_state):
        return True
    if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) == SOURCE_CATALOG:
        return False
    meta = session_state.get("active_song_state")
    if isinstance(meta, dict) and str(meta.get("music_source") or "") == SOURCE_CUSTOM:
        return True
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    pick_key = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if pick_key.startswith("custom::"):
        return True
    if isinstance(meta, dict):
        meta_pick = str(meta.get("pick_key") or "").strip()
        if meta_pick.startswith("custom::"):
            return True
    return False


def cpl_session_is_active(session_state: dict[str, Any]) -> bool:
    """True when the loaded song is a Custom Progression (for key display/sync)."""
    if is_custom_progression(session_state):
        return True
    if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        return False
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


def ensure_active_music_source_from_canonical(session_state: dict[str, Any]) -> None:
    """After cloud/local restore, align session source flag with canonical custom songs."""
    if is_custom_progression(session_state):
        return
    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY, SUITE_LOCAL_STATE_RESTORED_KEY
    except ImportError:
        return
    restored = bool(
        session_state.get("_cloud_workspace_restored_this_run")
        or session_state.get(SUITE_LOCAL_STATE_RESTORED_KEY)
    )
    if not restored:
        return
    meta = session_state.get(ACTIVE_SONG_STATE_KEY)
    if isinstance(meta, dict) and str(meta.get("music_source") or "") == SOURCE_CUSTOM:
        session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CUSTOM


def set_catalog_source(session_state: dict[str, Any]) -> None:
    session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CATALOG


def set_custom_source(session_state: dict[str, Any]) -> None:
    save_last_catalog_snapshot(session_state)
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
    """Remember the active catalog song before switching to another song or Custom Progression."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    if is_custom_progression(session_state):
        return
    sel = session_state.get(SELECTED_SONG_STATE_KEY)
    if not isinstance(sel, dict):
        return
    pick_key = str(
        session_state.get(ACTIVE_CATALOG_PICK_KEY) or sel.get("pick_key") or ""
    ).strip()
    if not pick_key or pick_key.startswith("custom::"):
        return
    original_key = str(sel.get("key") or "C").strip() or "C"
    display_key = str(session_state.get("display_key") or original_key).strip() or original_key
    session_state[LAST_CATALOG_STATE_KEY] = {
        "pick_key": pick_key,
        "selected_song": dict(sel),
        "original_key": original_key,
        "display_key": display_key,
    }


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
    snap = session.get(LAST_CATALOG_STATE_KEY)
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
    from songs.key_state import apply_display_key_for_active_song, song_display_identity
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    session = st.session_state
    session[USER_CATALOG_SOURCE_CHOICE_KEY] = True
    set_catalog_source(session)
    session[SELECTED_SONG_STATE_KEY] = dict(selected_song)
    session[ACTIVE_CATALOG_PICK_KEY] = str(pick_key or "").strip()
    identity = song_display_identity(
        str(selected_song.get("title") or ""),
        str(selected_song.get("artist") or ""),
        original_key,
    )
    apply_display_key_for_active_song(
        st,
        original_key,
        identity,
        pending_key=display_key,
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
        from active_song_state import clear_active_song_local_edit

        clear_active_song_local_edit(session)
    except ImportError:
        pass
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
            display_key = str(session.get("display_key") or original_key).strip() or original_key
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


def custom_original_key(active: dict[str, Any]) -> str:
    """User-chosen CPL original key (never inferred from chord analysis)."""
    from custom_progression_lab import cpl_draft_written_key, ensure_original_structure

    return cpl_draft_written_key(ensure_original_structure(active))


def resolve_active_song_keys(
    session_state: dict[str, Any],
    rec: dict[str, Any] | None = None,
) -> tuple[str, str, str | None]:
    """Single source of truth: original, display/practice, optional written chart key."""
    from songs.state import SELECTED_SONG_STATE_KEY

    if cpl_session_is_active(session_state):
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
            default_active_progression,
            ensure_original_structure,
        )
        from active_song_state import _resolve_custom_display_key_for_session

        active = ensure_original_structure(
            session_state.get(CPL_ACTIVE_KEY) or default_active_progression()
        )
        original = custom_original_key(active)
        display = _resolve_custom_display_key_for_session(session_state, original)
    else:
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        record = rec or {}
        selected = session_state.get(SELECTED_SONG_STATE_KEY) or {}
        original = str(record.get("key") or selected.get("key") or "C").strip() or "C"
        meta = session_state.get("active_song_state")
        live_pick = str(
            session_state.get(ACTIVE_CATALOG_PICK_KEY)
            or selected.get("pick_key")
            or ""
        ).strip()
        canonical = ""
        if isinstance(meta, dict):
            meta_pick = str(meta.get("pick_key") or "").strip()
            if not meta_pick or not live_pick or meta_pick == live_pick:
                canonical = str(meta.get("display_key") or "").strip()
        live = str(session_state.get("display_key") or "").strip()
        display = canonical or live or original
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
    """Original key and display/practice (concert) key for Active Song cards."""
    original, display, _written = resolve_active_song_keys(session_state, rec)
    return original, display


def active_song_written_chart_key(
    session_state: dict[str, Any],
    *,
    display_key: str | None = None,
) -> str | None:
    """Written instrument key when transposing + chart-in-written-key mode is on."""
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
    return None


def note_active_source_change(st: Any, *, invalidate_backing) -> bool:
    """Invalidate backing cache when the user switches catalog ↔ custom."""
    from .playback_defaults import reset_playback_song_tracking

    session_state = st.session_state
    current = session_state.get(ACTIVE_MUSIC_SOURCE_KEY, SOURCE_CATALOG)
    previous = session_state.get(_LAST_SOURCE_KEY)
    session_state[_LAST_SOURCE_KEY] = current
    if previous is not None and previous != current:
        reset_playback_song_tracking(st)
        invalidate_backing(st)
        return True
    return False


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
    if cpl_session_is_active(session_state):
        from custom_progression_lab import (
            default_active_progression,
            ensure_original_structure,
        )

        active = ensure_original_structure(
            session_state.get(cpl_active_key) or default_active_progression()
        )
        home = custom_original_key(active)
        title = active.get("name", "Custom Progression")
        return home, (title, "Custom progression", home)

    original = catalog_song_data.get("key", "C")
    return original, (
        catalog_song_data.get("title"),
        catalog_song_data.get("artist"),
        original,
    )


def custom_pick_key_for(active: dict[str, Any]) -> str:
    """Stable session pick_key for a custom progression (not a catalog pk:: id)."""
    title = str(active.get("name") or "My Progression").strip() or "My Progression"
    rev = str(active.get("id") or "").strip()
    if rev:
        return f"custom::{rev}"
    safe = title.replace(":", "_").replace("/", "_")[:80]
    return f"custom::{safe}"


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
    )
    from songs.key_state import (
        apply_display_key_for_active_song,
        song_display_identity,
    )
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    session = st.session_state
    active = ensure_original_structure(active)
    active["original_sections"] = ensure_all_cpl_sections(active.get("original_sections"))
    active["user_locked_home_key"] = True
    session[cpl_active_key] = active

    home_key = cpl_draft_written_key(active)
    selected = custom_selected_song_record(active)
    pick_key = str(selected.get("pick_key") or "").strip()
    existing_pick = str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    live_display = str(session.get("display_key") or "").strip()
    if pick_key and existing_pick == pick_key and live_display:
        practice_key = live_display
    else:
        practice_key = home_key

    set_custom_source(session)
    sync_song_picker_source_widget(session, force=True)
    note_active_source_change(st, invalidate_backing=invalidate_backing)

    session[SELECTED_SONG_STATE_KEY] = selected
    if pick_key:
        session[ACTIVE_CATALOG_PICK_KEY] = pick_key

    identity = song_display_identity(
        selected.get("title", ""),
        selected.get("artist", ""),
        home_key,
    )
    apply_display_key_for_active_song(st, home_key, identity, pending_key=practice_key)

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

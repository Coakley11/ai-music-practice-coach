"""Single master selected song for the whole Streamlit app."""

from __future__ import annotations

from typing import Any

from song_catalog import (
    first_valid_pick_key,
    format_pick_key,
    parse_pick_key,
    resolve_pick_key,
)

from .key_state import (
    BACKING_NEEDS_REGEN,
    IDENTITY_KEY,
    LAST_DISPLAY_KEY,
    PENDING_DISPLAY_KEY,
    invalidate_backing_cache,
)
from .playback_defaults import (
    active_song_sync_id,
    canonical_active_song_bpm,
    playback_song_id,
    prime_active_song_bpm,
    reset_playback_song_tracking,
)

SELECTED_SONG_STATE_KEY = "selected_song"
ACTIVE_CATALOG_PICK_KEY = "active_catalog_pick_key"
PENDING_MATCHING_SONG_DROPDOWN = "_pending_matching_song_dropdown"
PICK_KEY_RECOVERY_NOTICE_KEY = "_pick_key_recovery_notice"
_LAST_PICK_KEY = "_master_song_pick_key"
SUITE_LOCAL_STATE_RESTORED_KEY = "_suite_local_state_restored"


def build_music_local_state(st: Any) -> dict[str, str]:
    """Snapshot musician context for reload persistence."""
    ss = st.session_state
    sel = ss.get(SELECTED_SONG_STATE_KEY) or {}
    page = str(ss.get("studio_page") or ss.get("page") or "")
    return {
        "song": str(sel.get("title") or ss.get("active_song_title") or ""),
        "artist": str(sel.get("artist") or ""),
        "pick_key": str(ss.get(ACTIVE_CATALOG_PICK_KEY) or sel.get("pick_key") or ""),
        "page": page,
        "studio_page": page,
        "focus": str(ss.get("focus") or ""),
        "instrument": str(ss.get("instrument") or ""),
        "display_key": str(ss.get("display_key") or ""),
        "practice_focus_section": str(ss.get("practice_focus_section") or ""),
        "level": str(ss.get("level") or ""),
        "mode": str(ss.get("last_practice_mode") or ""),
    }


def persist_music_local_state(st: Any, **extra: Any) -> None:
    """Write disk + cloud session snapshot (Streamlit Cloud survives reboot via cloud)."""
    if extra:
        for key, value in extra.items():
            if value:
                st.session_state[key] = str(value)
    try:
        from music_persistent_state import flush_active_song_edits_and_save

        flush_active_song_edits_and_save(st, reason="song_edit")
        return
    except ImportError:
        pass
    try:
        from music_persistent_state import autosave_music_state

        autosave_music_state(st)
    except Exception:
        try:
            from music_persistent_state import build_music_disk_state, persist_music_disk_state

            if extra:
                for key, value in extra.items():
                    if value:
                        st.session_state[key] = str(value)
            persist_music_disk_state(st)
        except Exception:
            try:
                from suite_activity_client import save_local_app_state

                payload = build_music_local_state(st)
                for key, value in extra.items():
                    if value:
                        payload[key] = str(value)
                save_local_app_state("music", payload)
            except Exception:
                pass


def apply_saved_music_context(
    st: Any,
    saved: dict[str, Any],
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]] | None = None,
    apply_studio_page: bool = True,
) -> bool:
    """Apply pick_key, instrument, studio page, and related fields from a snapshot dict."""
    if not isinstance(saved, dict) or not saved:
        return False

    saved_display_key = str(saved.get("display_key") or "").strip()
    try:
        from practice_setup_globals import (
            get_active_instrument,
            set_active_focus,
            set_active_instrument,
            set_active_level,
            valid_focus_for,
        )
        from studio_nav_history import STUDIO_PAGE_IDS

        instrument = str(saved.get("instrument") or "").strip()
        if instrument:
            set_active_instrument(st.session_state, instrument)

        level = str(saved.get("level") or "").strip()
        if level:
            set_active_level(st.session_state, level)

        focus = str(saved.get("focus") or "").strip()
        if focus:
            set_active_focus(
                st.session_state,
                valid_focus_for(get_active_instrument(st.session_state), focus),
            )

        if apply_studio_page:
            page = str(saved.get("studio_page") or saved.get("page") or "").strip()
            if page in STUDIO_PAGE_IDS:
                st.session_state["studio_page"] = page

        section = str(saved.get("practice_focus_section") or "").strip()
        if section:
            st.session_state["practice_focus_section"] = section

        mode = str(saved.get("mode") or "").strip()
        if mode:
            st.session_state["last_practice_mode"] = mode
    except Exception:
        pass

    pick_key = str(saved.get("pick_key") or "").strip()
    if not pick_key:
        title = str(saved.get("song") or "").strip()
        if title:
            pick_key = _recover_pick_key_by_title(
                {"title": title, "artist": str(saved.get("artist") or "")},
                song_picker_catalog,
            ) or ""

    if not pick_key:
        return False

    resolved = resolve_pick_key(pick_key, song_picker_catalog=song_picker_catalog)
    target = resolved or pick_key
    genre, label = parse_pick_key(target)
    in_catalog = (
        genre in song_picker_catalog
        and label in song_picker_catalog[genre]
    )

    if resolved or in_catalog:
        try:
            apply_pick_key(
                st,
                target,
                song_picker_catalog,
                song_library=song_library,
                skip_activity_log=True,
            )
        except Exception:
            return False
        if saved_display_key:
            st.session_state[PENDING_DISPLAY_KEY] = saved_display_key
        return True

    by_title = _recover_pick_key_by_title(
        {
            "title": str(saved.get("song") or ""),
            "artist": str(saved.get("artist") or ""),
        },
        song_picker_catalog,
    )
    if by_title:
        try:
            apply_pick_key(
                st,
                by_title,
                song_picker_catalog,
                song_library=song_library,
                skip_activity_log=True,
            )
        except Exception:
            return False
        if saved_display_key:
            st.session_state[PENDING_DISPLAY_KEY] = saved_display_key
        return True

    label = str(saved.get("song") or pick_key).strip() or "your last song"
    st.session_state[PICK_KEY_RECOVERY_NOTICE_KEY] = (
        f'Your last session song (“{label}”) is no longer available; showing the default catalog song.'
    )
    return False


def restore_saved_app_state_once(
    st: Any,
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]] | None = None,
) -> None:
    """Restore last saved musician context once per browser session."""
    if st.session_state.get(SUITE_LOCAL_STATE_RESTORED_KEY):
        return
    st.session_state[SUITE_LOCAL_STATE_RESTORED_KEY] = True

    try:
        from suite_activity_client import load_local_app_state

        saved = load_local_app_state("music")
    except Exception:
        return

    apply_saved_music_context(
        st,
        saved,
        song_picker_catalog=song_picker_catalog,
        song_library=song_library,
    )


def sync_matching_song_dropdown_before_widget(
    st: Any,
    pick_options: list[str],
    fallback_pk: str,
) -> str:
    """Align the dropdown widget with ``ACTIVE_CATALOG_PICK_KEY`` before it is drawn.

    Never assign ``matching_song_dropdown`` after the selectbox exists — use pending
    values applied on the next run only.
    """
    if not pick_options:
        return fallback_pk

    fallback = fallback_pk if fallback_pk in pick_options else pick_options[0]
    active = st.session_state.get(ACTIVE_CATALOG_PICK_KEY) or fallback
    if active not in pick_options:
        active = fallback
        st.session_state[ACTIVE_CATALOG_PICK_KEY] = active

    pending = st.session_state.pop(PENDING_MATCHING_SONG_DROPDOWN, None)
    if pending in pick_options:
        st.session_state["matching_song_dropdown"] = pending
    elif st.session_state.get("matching_song_dropdown") not in pick_options:
        st.session_state["matching_song_dropdown"] = active

    return active


def _label_for_library_entry(genre: str, title: str, song_library: dict) -> str:
    artist = song_library[genre][title]["artist"]
    return f"{title} — {artist}"


def resolve_library_song_data(
    song_library: dict[str, dict[str, dict]],
    *,
    genre: str,
    title: str,
    artist: str,
    fallback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve a catalog row from SONG_LIBRARY without title-only collisions.

    SONG_LIBRARY is keyed by title per genre; duplicate titles (e.g. two
    "Autumn Leaves" rows) must match artist or fall back to the picker row.
    """
    lib_row = (song_library.get(genre) or {}).get(title)
    if lib_row is not None and str(lib_row.get("artist") or "") == str(artist or ""):
        return lib_row
    if fallback is not None:
        return fallback
    return lib_row if lib_row is not None else {}


def _build_library_from_picker(
    genre: str,
    label: str,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]],
) -> tuple[str, dict] | None:
    """Resolve (title, song_data) from picker keys, with library fallback."""
    picker = (song_picker_catalog.get(genre) or {}).get(label)
    if not picker:
        return None
    title = picker["title"]
    artist = str(picker.get("artist") or "")
    song_data = resolve_library_song_data(
        song_library,
        genre=genre,
        title=title,
        artist=artist,
        fallback=picker,
    )
    return title, song_data


def _recover_pick_key_by_title(
    sel: dict[str, Any],
    song_picker_catalog: dict[str, dict[str, dict]],
) -> str | None:
    """Match a stale session row by stored title (and artist when unique)."""
    title = str(sel.get("title") or "").strip()
    artist = str(sel.get("artist") or "").strip()
    if not title:
        return None

    if artist:
        for g, labels in song_picker_catalog.items():
            for lab, data in labels.items():
                if data.get("title") == title and str(data.get("artist") or "") == artist:
                    return format_pick_key(g, lab)

    matches: list[str] = []
    for g, labels in song_picker_catalog.items():
        for lab, data in labels.items():
            if data.get("title") == title:
                matches.append(format_pick_key(g, lab))
    if len(matches) == 1:
        return matches[0]
    return None


def ensure_master_song_initialized(
    st: Any,
    *,
    all_records: list[dict[str, Any]],
    song_library: dict[str, dict[str, dict]],
    song_picker_catalog: dict[str, dict[str, dict]],
) -> None:
    """Pick a default song once; migrate legacy sidebar session keys if present."""
    sel = st.session_state.get(SELECTED_SONG_STATE_KEY) or {}
    if isinstance(sel, dict) and sel.get("pick_key"):
        return

    pending_pk = str(st.session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if pending_pk and resolve_pick_key(pending_pk, song_picker_catalog=song_picker_catalog):
        apply_pick_key(
            st,
            pending_pk,
            song_picker_catalog,
            song_library=song_library,
            skip_activity_log=True,
        )
        return

    if (
        SELECTED_SONG_STATE_KEY in st.session_state
        and st.session_state[SELECTED_SONG_STATE_KEY]
        and st.session_state[SELECTED_SONG_STATE_KEY].get("pick_key")
    ):
        return

    # Migrate from pre-refactor keys
    legacy_g = st.session_state.get("active_genre")
    legacy_t = st.session_state.get("active_song_title")
    if (
        legacy_g
        and legacy_t
        and legacy_g in song_library
        and legacy_t in song_library[legacy_g]
    ):
        label = _label_for_library_entry(legacy_g, legacy_t, song_library)
        if legacy_g in song_picker_catalog and label in song_picker_catalog[legacy_g]:
            apply_pick_key(st, format_pick_key(legacy_g, label), song_picker_catalog)
            return

    r0 = all_records[0]
    label0 = f"{r0['title']} — {r0['artist']}"
    pk = format_pick_key(r0["genre"], label0)
    apply_pick_key(st, pk, song_picker_catalog)


def apply_pick_key(
    st: Any,
    pick_key: str,
    song_picker_catalog: dict[str, dict[str, dict]],
    *,
    song_library: dict[str, dict[str, dict]] | None = None,
    skip_activity_log: bool = False,
) -> dict[str, Any]:
    resolved = resolve_pick_key(pick_key, song_picker_catalog=song_picker_catalog)
    if not resolved:
        existing = st.session_state.get(SELECTED_SONG_STATE_KEY)
        if isinstance(existing, dict) and existing.get("title"):
            return existing
        fallback = first_valid_pick_key(song_picker_catalog)
        if fallback:
            resolved = fallback
        else:
            return {}
    pick_key = resolved
    prev = st.session_state.get(_LAST_PICK_KEY)
    if (
        prev
        and prev != pick_key
        and not str(prev).startswith("custom::")
        and not str(pick_key).startswith("custom::")
    ):
        try:
            from songs.music_source import snapshot_current_catalog_state

            snapshot_current_catalog_state(st.session_state)
        except ImportError:
            pass
    genre, label = parse_pick_key(pick_key)
    if genre not in song_picker_catalog or label not in song_picker_catalog[genre]:
        existing = st.session_state.get(SELECTED_SONG_STATE_KEY)
        return existing if isinstance(existing, dict) else {}
    data = song_picker_catalog[genre][label]
    st.session_state[SELECTED_SONG_STATE_KEY] = {
        "pick_key": pick_key,
        "title": data["title"],
        "artist": data["artist"],
        "genre": genre,
        "label": label,
        "key": data.get("key") or "",
    }
    prev = st.session_state.get(_LAST_PICK_KEY)
    st.session_state[_LAST_PICK_KEY] = pick_key
    st.session_state["active_genre"] = genre
    st.session_state["active_song_title"] = data["title"]
    if prev is not None and prev != pick_key:
        try:
            from picker_song_editor import PICKER_EDITOR_OPEN_KEY, PICKER_EDITOR_NOTICE_KEY

            st.session_state[PICKER_EDITOR_OPEN_KEY] = False
            st.session_state.pop(PICKER_EDITOR_NOTICE_KEY, None)
            st.session_state["chart_edit_mode"] = False
        except Exception:
            pass
        from songs.key_state import apply_display_key_for_active_song, song_display_identity

        song_identity = song_display_identity(
            str(data.get("title") or ""),
            str(data.get("artist") or ""),
            str(data.get("key") or ""),
        )
        apply_display_key_for_active_song(
            st,
            str(data.get("key") or "C"),
            song_identity,
            pending_key=str(data.get("key") or "C"),
        )
        reset_playback_song_tracking(st)
        invalidate_backing_cache(st)
        st.session_state[BACKING_NEEDS_REGEN] = False
        st.session_state.pop("multitrack_backing_wav", None)
        st.session_state.pop("multitrack_backing_music_wav", None)
        st.session_state.pop("mixed_track_wav", None)
        lib_record = data
        if song_library is not None:
            lib_record = resolve_library_song_data(
                song_library,
                genre=genre,
                title=str(data.get("title") or ""),
                artist=str(data.get("artist") or ""),
                fallback=data,
            )
        _pid = playback_song_id(
            is_custom=False,
            song_title=data["title"],
            song_artist=data.get("artist", ""),
        )
        _sync_id = active_song_sync_id(pick_key=pick_key, playback_song_id=_pid, is_custom=False)
        prime_active_song_bpm(
            st,
            sync_id=_sync_id,
            active_song_bpm=canonical_active_song_bpm(lib_record),
        )
    elif "display_key" not in st.session_state:
        st.session_state[PENDING_DISPLAY_KEY] = data["key"]
    st.session_state[ACTIVE_CATALOG_PICK_KEY] = pick_key
    st.session_state[PENDING_MATCHING_SONG_DROPDOWN] = pick_key
    try:
        from songs.user_lyrics_runtime import hydrate_user_lyrics_session

        hydrate_user_lyrics_session(
            st.session_state,
            title=str(data.get("title", "")),
            artist=str(data.get("artist", "")),
            force=bool(prev is not None and prev != pick_key),
        )
    except Exception:
        pass
    if not skip_activity_log:
        try:
            from suite_activity_client import record_activity

            song_label = f"{data.get('title', '')} — {data.get('artist', '')}".strip(" —")
            local_state = build_music_local_state(st)
            record_activity(
                "music",
                "song_selected",
                page=str(st.session_state.get("studio_page") or "Song Picker"),
                metrics={
                    "song": str(data.get("title") or ""),
                    "artist": str(data.get("artist") or ""),
                    "genre": genre,
                    "pick_key": pick_key,
                    "focus": str(st.session_state.get("focus") or ""),
                    "instrument": local_state.get("instrument", ""),
                    "display_key": local_state.get("display_key", ""),
                },
                summary=f"Practice {song_label}" if song_label else "Music practice",
                resume_key=f"song:{pick_key}",
                resume_title=f"Continue: {data.get('title', 'song')}",
                resume_subtitle=str(data.get("artist") or ""),
                local_state=local_state,
            )
        except Exception:
            pass
    persist_music_local_state(st)
    return data


def get_song_context(
    st: Any,
    *,
    song_library: dict[str, dict[str, dict]],
    song_picker_catalog: dict[str, dict[str, dict]],
) -> tuple[str, str, dict]:
    """Return (genre, title, song_data) for the master selection.

    Never raises for stale/renamed/missing pick keys — falls back to title match,
    then the first catalog song, and stores a one-run recovery notice.
    """
    sel = st.session_state.get(SELECTED_SONG_STATE_KEY) or {}
    pk = str(sel.get("pick_key") or "").strip()

    def _commit(resolved_pk: str, *, notice: str | None = None) -> tuple[str, str, dict]:
        if notice:
            st.session_state[PICK_KEY_RECOVERY_NOTICE_KEY] = notice
        if resolved_pk != pk or not sel.get("title"):
            apply_pick_key(
                st,
                resolved_pk,
                song_picker_catalog,
                song_library=song_library,
            )
        genre, label = parse_pick_key(resolved_pk)
        resolved = _build_library_from_picker(genre, label, song_picker_catalog, song_library)
        if resolved is None:
            fallback = first_valid_pick_key(song_picker_catalog)
            if not fallback:
                raise RuntimeError("Song catalog is empty — cannot select a default song.")
            return _commit(
                fallback,
                notice=notice or "Restored default song selection.",
            )
        title, song_data = resolved
        return genre, title, song_data

    if not pk:
        fallback = first_valid_pick_key(song_picker_catalog)
        if not fallback:
            raise RuntimeError("Master song not initialized — call ensure_master_song_initialized first.")
        return _commit(fallback, notice="No saved song selection; restored default catalog song.")

    resolved_pk = resolve_pick_key(pk, song_picker_catalog=song_picker_catalog)
    if resolved_pk:
        genre, label = parse_pick_key(resolved_pk)
        if genre in song_picker_catalog and label in song_picker_catalog[genre]:
            if resolved_pk != pk:
                old = sel.get("title") or pk
                return _commit(
                    resolved_pk,
                    notice=f'Updated song selection for "{old}" after a catalog change.',
                )
            return _commit(resolved_pk)

    by_title = _recover_pick_key_by_title(sel, song_picker_catalog)
    if by_title:
        old = sel.get("title") or pk
        return _commit(
            by_title,
            notice=f'"{old}" was moved or renamed in the catalog; selection updated.',
        )

    fallback = first_valid_pick_key(song_picker_catalog)
    if not fallback:
        raise RuntimeError("Song catalog is empty — cannot recover from stale pick key.")
    old = sel.get("title") or sel.get("label") or pk
    return _commit(
        fallback,
        notice=f'Previous song "{old}" is no longer in the catalog; switched to a default song.',
    )

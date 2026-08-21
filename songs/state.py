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
)

SELECTED_SONG_STATE_KEY = "selected_song"
ACTIVE_CATALOG_PICK_KEY = "active_catalog_pick_key"
PENDING_MATCHING_SONG_DROPDOWN = "_pending_matching_song_dropdown"
PENDING_CATALOG_PICK_KEY = "_pending_catalog_pick_key"
PICK_KEY_RECOVERY_NOTICE_KEY = "_pick_key_recovery_notice"
_LAST_PICK_KEY = "_master_song_pick_key"
SUITE_LOCAL_STATE_RESTORED_KEY = "_suite_local_state_restored"


def queue_pending_catalog_pick(st: Any, pick_key: str) -> None:
    """Queue a catalog pick for before-widget application on the next rerun."""
    pk = str(pick_key or "").strip()
    if pk:
        st.session_state[PENDING_CATALOG_PICK_KEY] = pk


def sync_catalog_pick_identity(
    session: dict[str, Any],
    pick_key: str,
    song_picker_catalog: dict[str, dict[str, dict]],
) -> bool:
    """Mirror one catalog pick_key into all session identity keys (no backing reset)."""
    resolved = resolve_pick_key(pick_key, song_picker_catalog=song_picker_catalog)
    if not resolved:
        return False
    genre, label = parse_pick_key(resolved)
    if genre not in song_picker_catalog or label not in song_picker_catalog[genre]:
        return False
    data = song_picker_catalog[genre][label]
    session[ACTIVE_CATALOG_PICK_KEY] = resolved
    session[SELECTED_SONG_STATE_KEY] = {
        "pick_key": resolved,
        "title": data["title"],
        "artist": str(data.get("artist") or ""),
        "genre": genre,
        "label": label,
        "key": str(data.get("key") or "C").strip() or "C",
    }
    session["active_genre"] = genre
    session["active_song_title"] = data["title"]
    session["song"] = data["title"]
    session[PENDING_MATCHING_SONG_DROPDOWN] = resolved
    session[_LAST_PICK_KEY] = resolved
    try:
        from music_state_writes import WriteOrigin, record_state_write_trace

        record_state_write_trace(
            session,
            key=ACTIVE_CATALOG_PICK_KEY,
            origin=WriteOrigin.RECONCILE,
            writer="sync_catalog_pick_identity",
            value=resolved,
        )
    except ImportError:
        pass
    return True


def reconcile_active_song_identity(
    session: dict[str, Any],
    song_picker_catalog: dict[str, dict[str, dict]] | None = None,
) -> str:
    """Ensure ACTIVE, selected_song, and dropdown agree on one pick_key."""
    if not song_picker_catalog:
        return str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()

    try:
        from creative_key_sync import is_creative_catalog_pick_frozen
    except ImportError:
        is_creative_catalog_pick_frozen = lambda _s: False  # type: ignore[assignment,misc]

    try:
        from songs.music_source import USER_CATALOG_SOURCE_CHOICE_KEY, is_custom_progression

        if is_custom_progression(session) and not session.get(USER_CATALOG_SOURCE_CHOICE_KEY):
            return str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    except ImportError:
        pass

    active = str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    sel = session.get(SELECTED_SONG_STATE_KEY)
    sel_pk = str(sel.get("pick_key") or "").strip() if isinstance(sel, dict) else ""
    dropdown = str(session.get("matching_song_dropdown") or "").strip()
    pending = str(session.get(PENDING_CATALOG_PICK_KEY) or "").strip()

    try:
        from songs.music_source import peek_catalog_restore_pin

        restore_pin = peek_catalog_restore_pin(session)
        if restore_pin and resolve_pick_key(restore_pin, song_picker_catalog=song_picker_catalog):
            if restore_pin != active or restore_pin != sel_pk:
                sync_catalog_pick_identity(session, restore_pin, song_picker_catalog)
            elif dropdown and dropdown != restore_pin:
                session[PENDING_MATCHING_SONG_DROPDOWN] = restore_pin
                session["matching_song_dropdown"] = restore_pin
            return restore_pin
    except ImportError:
        pass

    if is_creative_catalog_pick_frozen(session):
        master = active or sel_pk
        if master and resolve_pick_key(master, song_picker_catalog=song_picker_catalog):
            if master != active or master != sel_pk:
                sync_catalog_pick_identity(session, master, song_picker_catalog)
            elif dropdown and dropdown != master:
                session[PENDING_MATCHING_SONG_DROPDOWN] = master
                session["matching_song_dropdown"] = master
            return master
        return active or sel_pk

    master = active or sel_pk
    if pending and resolve_pick_key(pending, song_picker_catalog=song_picker_catalog):
        master = pending
    elif dropdown:
        resolved_dd = resolve_pick_key(dropdown, song_picker_catalog=song_picker_catalog)
        if resolved_dd and resolved_dd != master:
            try:
                from active_song_state import is_active_song_locally_dirty

                dirty = is_active_song_locally_dirty(session)
            except ImportError:
                dirty = False
            if dirty or resolved_dd == sel_pk or not master:
                master = resolved_dd

    if not master:
        return ""

    if master != active or master != sel_pk:
        sync_catalog_pick_identity(session, master, song_picker_catalog)
    elif dropdown and dropdown != master:
        session[PENDING_MATCHING_SONG_DROPDOWN] = master
    return master


def apply_pending_catalog_pick_before_widgets(
    st: Any,
    song_picker_catalog: dict[str, dict[str, dict]],
    *,
    song_library: dict[str, dict[str, dict]] | None = None,
    invalidate_backing,
) -> bool:
    """Apply queued catalog pick before sidebar/global widgets render."""
    try:
        from songs.music_source import (
            PENDING_CUSTOM_ACTIVE_SONG_KEY,
            PENDING_CUSTOM_LIBRARY_ACTION_KEY,
            is_custom_progression,
        )
    except ImportError:
        PENDING_CUSTOM_ACTIVE_SONG_KEY = "_pending_custom_active_song_activation"  # noqa: N806
        PENDING_CUSTOM_LIBRARY_ACTION_KEY = "_pending_custom_library_action"  # noqa: N806
        is_custom_progression = lambda _s: False  # type: ignore[assignment,misc]

    if st.session_state.get(PENDING_CUSTOM_ACTIVE_SONG_KEY):
        return False
    if st.session_state.get(PENDING_CUSTOM_LIBRARY_ACTION_KEY):
        return False
    if is_custom_progression(st.session_state) or st.session_state.get(
        "_custom_active_song_applied_this_run"
    ):
        st.session_state.pop(PENDING_CATALOG_PICK_KEY, None)
        return False

    pending = st.session_state.pop(PENDING_CATALOG_PICK_KEY, None)
    if not pending:
        return False
    apply_pick_key(
        st,
        str(pending),
        song_picker_catalog,
        song_library=song_library,
        skip_activity_log=True,
    )
    try:
        reconcile_active_song_identity(st.session_state, song_picker_catalog)
    except Exception:
        pass
    try:
        from songs.music_source import note_active_source_change

        note_active_source_change(st, invalidate_backing=invalidate_backing)
    except ImportError:
        pass
    return True


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
    save_reason = str(extra.pop("_persist_reason", None) or "song_edit").strip() or "song_edit"
    try:
        from music_startup_save_suppression import should_suppress_music_workspace_save, record_startup_save_suppressed

        suppress, why = should_suppress_music_workspace_save(st.session_state, save_reason)
        if suppress:
            record_startup_save_suppressed(st.session_state, why)
            return
    except ImportError:
        pass
    if extra:
        for key, value in extra.items():
            if value:
                st.session_state[key] = str(value)
    try:
        from music_persistent_state import flush_active_song_edits_and_save

        flush_active_song_edits_and_save(st, reason=save_reason)
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


def apply_saved_custom_pick_key_context(
    st: Any,
    pick_key: str,
    saved: dict[str, Any],
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]] | None = None,
    saved_display_key: str = "",
) -> bool:
    """Restore a custom:: pick_key from CPL active/saved library after cloud restore."""
    from custom_progression_lab import (
        CPL_ACTIVE_KEY,
        default_active_progression,
        ensure_original_structure,
    )
    from songs.music_source import (
        custom_pick_key_for,
        custom_selected_song_record,
        set_custom_source,
    )

    suffix = str(pick_key or "").strip().removeprefix("custom::").strip()
    if not suffix:
        return False

    active: dict[str, Any] | None = None
    cpl_active = st.session_state.get(CPL_ACTIVE_KEY)
    if isinstance(cpl_active, dict):
        cand = ensure_original_structure(cpl_active)
        if (
            custom_pick_key_for(cand) == pick_key
            or str(cand.get("id") or "").strip() == suffix
            or str(cand.get("name") or "").strip() == suffix
        ):
            active = cand

    if active is None:
        saved_lib = st.session_state.get("cpl_saved_progressions") or {}
        if isinstance(saved_lib, dict):
            for name, prog in saved_lib.items():
                if not isinstance(prog, dict):
                    continue
                cand = ensure_original_structure(prog)
                if (
                    custom_pick_key_for(cand) == pick_key
                    or str(name).strip() == suffix
                    or str(cand.get("id") or "").strip() == suffix
                    or str(cand.get("name") or "").strip() == suffix
                ):
                    active = cand
                    break

    if active is None:
        return False

    st.session_state[CPL_ACTIVE_KEY] = active
    set_custom_source(st.session_state)
    selected = custom_selected_song_record(active)
    st.session_state[SELECTED_SONG_STATE_KEY] = selected
    st.session_state[ACTIVE_CATALOG_PICK_KEY] = pick_key

    try:
        from active_song_state import write_canonical_active_song_state, gather_active_song_context

        ctx = gather_active_song_context(st.session_state)
        write_canonical_active_song_state(st.session_state, ctx, reason="custom_pick_restore")
    except ImportError:
        pass

    display_key = saved_display_key or str(saved.get("display_key") or "").strip()
    from songs.key_state import PENDING_DISPLAY_KEY

    try:
        from custom_progression_lab import cpl_draft_written_key
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

        home_key_for_fixed = cpl_draft_written_key(active)
        if is_fixed_practice_key_mode(st.session_state):
            display_key = resolve_practice_concert_key_for_song(
                st.session_state,
                home_key_for_fixed,
                pick_key=pick_key,
                fallback=display_key or home_key_for_fixed,
            )
    except ImportError:
        pass

    if display_key:
        st.session_state[PENDING_DISPLAY_KEY] = display_key
    else:
        try:
            from custom_progression_lab import cpl_draft_written_key

            st.session_state[PENDING_DISPLAY_KEY] = cpl_draft_written_key(active)
        except ImportError:
            pass

    try:
        from custom_progression_lab import cpl_draft_written_key
        from songs.music_source import on_active_song_identity_changed
        from songs.key_state import invalidate_backing_cache
        from songs.playback_defaults import (
            active_song_sync_id,
            canonical_active_song_bpm,
            default_groove_for_song,
            get_song_default_meter,
            playback_song_id,
        )

        home_key = cpl_draft_written_key(active)
        title = str(selected.get("title") or active.get("name") or "Custom")
        artist = str(selected.get("artist") or "Custom progression")
        _pid = playback_song_id(is_custom=True, song_title=title, song_artist=artist)
        _sync_id = active_song_sync_id(pick_key=pick_key, playback_song_id=_pid, is_custom=True)
        on_active_song_identity_changed(
            st,
            pick_key=pick_key,
            title=title,
            artist=artist,
            original_key=home_key,
            is_custom=True,
            sync_id=_sync_id,
            default_bpm=canonical_active_song_bpm(active),
            default_groove=default_groove_for_song(active, infer_fn=lambda _rec, _fb: "Auto"),
            default_meter=get_song_default_meter(active),
            display_key=display_key or home_key,
            custom_revision=str(active.get("id") or "").strip(),
            invalidate_backing=invalidate_backing_cache,
            force_reset=True,
        )
    except Exception:
        pass

    st.session_state[SUITE_LOCAL_STATE_RESTORED_KEY] = True
    try:
        from music_persistent_state import clear_music_ephemeral_default_song

        clear_music_ephemeral_default_song(st.session_state)
    except ImportError:
        pass
    return True


def apply_saved_music_context(
    st: Any,
    saved: dict[str, Any],
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]] | None = None,
    apply_studio_page: bool = True,
    skip_catalog_pick_key: bool = False,
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

    if pick_key.startswith("custom::"):
        return apply_saved_custom_pick_key_context(
            st,
            pick_key,
            saved,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
            saved_display_key=saved_display_key,
        )

    if skip_catalog_pick_key:
        return True

    # Explicit Custom Set-as-Active outranks a stale catalog snapshot on disk/cloud.
    try:
        from songs.music_source import explicit_custom_activation_is_authoritative

        if explicit_custom_activation_is_authoritative(st.session_state):
            try:
                from e5_reclaim_trace import note_e5_reclaim_writer

                note_e5_reclaim_writer(
                    st.session_state,
                    writer="apply_saved_music_context_blocked",
                    reason="stale_catalog_snapshot",
                    new_pick=pick_key,
                )
            except ImportError:
                pass
            return False
    except ImportError:
        pass

    resolved = resolve_pick_key(pick_key, song_picker_catalog=song_picker_catalog)
    target = resolved or pick_key
    genre, label = parse_pick_key(target)
    in_catalog = (
        genre in song_picker_catalog
        and label in song_picker_catalog[genre]
    )

    if resolved or in_catalog:
        try:
            from songs.key_state import resolve_restore_display_key

            restore_dk = resolve_restore_display_key(
                st.session_state,
                override=saved_display_key,
            )
            apply_pick_key(
                st,
                target,
                song_picker_catalog,
                song_library=song_library,
                skip_activity_log=True,
                origin="recovery",
                display_key_override=restore_dk or None,
            )
        except Exception:
            return False
        if instrument:
            set_active_instrument(st.session_state, instrument)
        if level:
            set_active_level(st.session_state, level)
        if focus:
            set_active_focus(
                st.session_state,
                valid_focus_for(get_active_instrument(st.session_state), focus),
            )
        if saved_display_key:
            st.session_state[PENDING_DISPLAY_KEY] = saved_display_key
        elif restore_dk:
            st.session_state[PENDING_DISPLAY_KEY] = restore_dk
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
            from songs.key_state import resolve_restore_display_key

            restore_dk = resolve_restore_display_key(
                st.session_state,
                override=saved_display_key,
            )
            apply_pick_key(
                st,
                by_title,
                song_picker_catalog,
                song_library=song_library,
                skip_activity_log=True,
                origin="recovery",
                display_key_override=restore_dk or None,
            )
        except Exception:
            return False
        if instrument:
            set_active_instrument(st.session_state, instrument)
        if level:
            set_active_level(st.session_state, level)
        if focus:
            set_active_focus(
                st.session_state,
                valid_focus_for(get_active_instrument(st.session_state), focus),
            )
        if saved_display_key:
            st.session_state[PENDING_DISPLAY_KEY] = saved_display_key
        elif restore_dk:
            st.session_state[PENDING_DISPLAY_KEY] = restore_dk
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
    *,
    song_picker_catalog: dict[str, dict[str, dict]] | None = None,
) -> str:
    """Align the dropdown widget with ``ACTIVE_CATALOG_PICK_KEY`` before it is drawn.

    Never assign ``matching_song_dropdown`` after the selectbox exists — use pending
    values applied on the next run only.
    """
    if not pick_options:
        return fallback_pk

    live_pk = str(st.session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    dropdown = str(st.session_state.get("matching_song_dropdown") or "").strip()
    try:
        from creative_key_sync import is_creative_catalog_pick_frozen

        if is_creative_catalog_pick_frozen(st.session_state) and live_pk:
            if (
                live_pk not in pick_options
                and song_picker_catalog
                and resolve_pick_key(live_pk, song_picker_catalog=song_picker_catalog)
            ):
                pick_options.insert(0, live_pk)
            st.session_state["matching_song_dropdown"] = live_pk
            return live_pk if live_pk in pick_options else live_pk
    except ImportError:
        pass
    if (
        song_picker_catalog
        and dropdown
        and dropdown in pick_options
        and dropdown != live_pk
        and resolve_pick_key(dropdown, song_picker_catalog=song_picker_catalog)
    ):
        try:
            from active_song_state import is_active_song_locally_dirty

            if is_active_song_locally_dirty(st.session_state) or not live_pk:
                sync_catalog_pick_identity(st.session_state, dropdown, song_picker_catalog)
                live_pk = dropdown
        except ImportError:
            sync_catalog_pick_identity(st.session_state, dropdown, song_picker_catalog)
            live_pk = dropdown

    if live_pk and live_pk not in pick_options and song_picker_catalog:
        if resolve_pick_key(live_pk, song_picker_catalog=song_picker_catalog):
            pick_options.insert(0, live_pk)

    fallback = fallback_pk if fallback_pk in pick_options else pick_options[0]
    active = live_pk or fallback
    if active not in pick_options:
        active = fallback
        try:
            from music_state_writes import WriteOrigin, guarded_session_set

            guarded_session_set(
                st.session_state,
                ACTIVE_CATALOG_PICK_KEY,
                active,
                origin=WriteOrigin.WIDGET_SYNC,
                writer="sync_matching_song_dropdown_before_widget",
            )
        except ImportError:
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


def load_catalog_song_record_by_pick_key(
    pick_key: str,
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]],
) -> tuple[str, str, dict] | None:
    """Load complete catalog song_data for a pick key (genre, title, record)."""
    resolved = resolve_pick_key(pick_key, song_picker_catalog=song_picker_catalog)
    if not resolved:
        return None
    genre, label = parse_pick_key(resolved)
    built = _build_library_from_picker(genre, label, song_picker_catalog, song_library)
    if not built:
        return None
    title, song_data = built
    return genre, title, song_data


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
    origin: str = "default",
) -> None:
    """Pick a default song once; migrate legacy sidebar session keys if present."""
    ss = st.session_state
    try:
        from active_song_workspace_restore import should_defer_default_master_song_init

        if should_defer_default_master_song_init(ss):
            ss["_music_skip_master_song_init_reason"] = "cloud_song_pending_apply"
            return
    except ImportError:
        pass
    sel = ss.get(SELECTED_SONG_STATE_KEY) or {}
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
            persist=False,
            origin=origin,
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
            apply_pick_key(st, format_pick_key(legacy_g, label), song_picker_catalog, persist=False, origin=origin)
            return

    r0 = all_records[0]
    label0 = f"{r0['title']} — {r0['artist']}"
    pk = format_pick_key(r0["genre"], label0)
    apply_pick_key(st, pk, song_picker_catalog, persist=False, origin=origin)
    st.session_state["_music_default_song_ephemeral"] = True


def apply_pick_key(
    st: Any,
    pick_key: str,
    song_picker_catalog: dict[str, dict[str, dict]],
    *,
    song_library: dict[str, dict[str, dict]] | None = None,
    skip_activity_log: bool = False,
    persist: bool = True,
    origin: str = "user",
    display_key_override: str | None = None,
) -> dict[str, Any]:
    try:
        from music_state_writes import WriteOrigin, may_write_contested, record_state_write_trace

        origin_enum = WriteOrigin(origin)
    except ImportError:
        origin_enum = None
        may_write_contested = None  # type: ignore[assignment,misc]
        record_state_write_trace = None  # type: ignore[assignment,misc]

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
    # Explicit Custom Set-as-Active outranks stale catalog restore/recovery picks.
    try:
        from songs.music_source import explicit_custom_activation_is_authoritative

        if (
            explicit_custom_activation_is_authoritative(st.session_state)
            and origin in ("restore", "recovery")
            and not str(pick_key).startswith("custom::")
        ):
            try:
                from e5_reclaim_trace import note_e5_reclaim_writer

                note_e5_reclaim_writer(
                    st.session_state,
                    writer="apply_pick_key_blocked",
                    reason=f"origin={origin}",
                    new_pick=str(pick_key or ""),
                )
            except ImportError:
                pass
            existing = st.session_state.get(SELECTED_SONG_STATE_KEY)
            return existing if isinstance(existing, dict) else {}
    except ImportError:
        pass
    prev = st.session_state.get(_LAST_PICK_KEY)
    if origin_enum is not None and may_write_contested is not None:
        if prev and prev != pick_key and not may_write_contested(
            st.session_state, origin_enum, ACTIVE_CATALOG_PICK_KEY
        ):
            if record_state_write_trace is not None:
                record_state_write_trace(
                    st.session_state,
                    key=ACTIVE_CATALOG_PICK_KEY,
                    origin=origin_enum,
                    writer="apply_pick_key",
                    value=pick_key,
                    blocked=True,
                )
            existing = st.session_state.get(SELECTED_SONG_STATE_KEY)
            return existing if isinstance(existing, dict) else {}
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
    selected_payload = {
        "pick_key": pick_key,
        "title": data["title"],
        "artist": data["artist"],
        "genre": genre,
        "label": label,
        "key": data.get("key") or "",
    }
    data_sections = data.get("sections")
    if isinstance(data_sections, dict) and data_sections:
        selected_payload["sections"] = {
            str(name): [str(c) for c in chords if str(c).strip()]
            for name, chords in data_sections.items()
            if isinstance(chords, list)
        }
    st.session_state[SELECTED_SONG_STATE_KEY] = selected_payload
    prev = st.session_state.get(_LAST_PICK_KEY)
    st.session_state[_LAST_PICK_KEY] = pick_key
    st.session_state["active_genre"] = genre
    st.session_state["active_song_title"] = data["title"]
    is_restore = origin in ("recovery", "restore")
    pick_changed = prev is not None and prev != pick_key
    if prev != pick_key:
        try:
            from picker_song_editor import PICKER_EDITOR_OPEN_KEY, PICKER_EDITOR_NOTICE_KEY

            st.session_state[PICKER_EDITOR_OPEN_KEY] = False
            st.session_state.pop(PICKER_EDITOR_NOTICE_KEY, None)
            st.session_state["chart_edit_mode"] = False
        except Exception:
            pass
        if str(pick_key).startswith("custom::"):
            from songs.music_source import USER_CATALOG_SOURCE_CHOICE_KEY, set_custom_source

            st.session_state.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)
            set_custom_source(st.session_state)
        else:
            from songs.music_source import (
                EXPLICIT_CATALOG_SELECTION_EPOCH_KEY,
                USER_CATALOG_SOURCE_CHOICE_KEY,
                set_catalog_source,
            )

            try:
                from e5_reclaim_trace import note_e5_reclaim_writer

                note_e5_reclaim_writer(
                    st.session_state,
                    writer="apply_pick_key",
                    reason=str(origin or ""),
                    new_pick=str(pick_key or ""),
                )
            except ImportError:
                pass
            if not is_restore:
                st.session_state[USER_CATALOG_SOURCE_CHOICE_KEY] = True
                # Intentional catalog pick outranks prior Custom Set-as-Active epoch.
                try:
                    import time as _time

                    st.session_state[EXPLICIT_CATALOG_SELECTION_EPOCH_KEY] = float(_time.time())
                except Exception:
                    st.session_state[EXPLICIT_CATALOG_SELECTION_EPOCH_KEY] = 1.0
            set_catalog_source(st.session_state)
        lib_record = data
        if song_library is not None:
            lib_record = resolve_library_song_data(
                song_library,
                genre=genre,
                title=str(data.get("title") or ""),
                artist=str(data.get("artist") or ""),
                fallback=data,
            )
        lib_sections = lib_record.get("sections") if isinstance(lib_record, dict) else None
        if isinstance(lib_sections, dict) and lib_sections:
            live_sel = dict(st.session_state.get(SELECTED_SONG_STATE_KEY) or selected_payload)
            live_sel["sections"] = {
                str(name): [str(c) for c in chords if str(c).strip()]
                for name, chords in lib_sections.items()
                if isinstance(chords, list)
            }
            if lib_record.get("key"):
                live_sel["key"] = str(lib_record.get("key") or live_sel.get("key") or "")
            st.session_state[SELECTED_SONG_STATE_KEY] = live_sel
        original_key = str(lib_record.get("key") or data.get("key") or "C").strip() or "C"
        default_bpm = canonical_active_song_bpm(lib_record)
        from songs.playback_defaults import default_groove_for_song, get_song_default_meter

        default_groove = default_groove_for_song(lib_record, infer_fn=lambda _rec, _fb: "Auto")
        default_meter = get_song_default_meter(lib_record)
        _pid = playback_song_id(
            is_custom=False,
            song_title=data["title"],
            song_artist=data.get("artist", ""),
        )
        _sync_id = active_song_sync_id(pick_key=pick_key, playback_song_id=_pid, is_custom=False)
        from songs.key_state import PENDING_DISPLAY_KEY, resolve_restore_display_key
        from songs.music_source import on_active_song_identity_changed

        restore_display_key = ""
        if is_restore:
            restore_display_key = resolve_restore_display_key(
                st.session_state,
                override=str(display_key_override or "").strip(),
            )
        effective_display_key = (
            restore_display_key if (is_restore and restore_display_key) else original_key
        )
        user_song_change = pick_changed and not is_restore
        try:
            from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

            if is_fixed_practice_key_mode(st.session_state) or user_song_change:
                effective_display_key = resolve_practice_concert_key_for_song(
                    st.session_state,
                    original_key,
                    pick_key=pick_key,
                    fallback=effective_display_key,
                )
        except ImportError:
            pass
        on_active_song_identity_changed(
            st,
            pick_key=pick_key,
            title=str(data.get("title") or ""),
            artist=str(data.get("artist") or ""),
            original_key=original_key,
            is_custom=False,
            sync_id=_sync_id,
            default_bpm=default_bpm,
            default_groove=default_groove,
            default_meter=default_meter,
            display_key=effective_display_key,
            song_data=lib_record,
            invalidate_backing=invalidate_backing_cache,
            force_reset=user_song_change,
        )
        if is_restore and restore_display_key:
            from session_widget_safe import safe_assign_display_key

            safe_assign_display_key(
                st.session_state,
                restore_display_key,
                widget_safe=True,
                st_like=st,
            )
        st.session_state[BACKING_NEEDS_REGEN] = False
        st.session_state.pop("multitrack_backing_wav", None)
        st.session_state.pop("multitrack_backing_music_wav", None)
        st.session_state.pop("mixed_track_wav", None)
    elif "display_key" not in st.session_state:
        st.session_state[PENDING_DISPLAY_KEY] = data["key"]
    st.session_state[ACTIVE_CATALOG_PICK_KEY] = pick_key
    st.session_state[PENDING_MATCHING_SONG_DROPDOWN] = pick_key
    if origin_enum is not None and record_state_write_trace is not None:
        record_state_write_trace(
            st.session_state,
            key=ACTIVE_CATALOG_PICK_KEY,
            origin=origin_enum,
            writer="apply_pick_key",
            value=pick_key,
            blocked=False,
        )
    if origin == "user" or (origin_enum is not None and origin_enum == WriteOrigin.USER):
        try:
            from active_song_state import mark_active_song_local_edit

            mark_active_song_local_edit(st.session_state)
        except ImportError:
            pass
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
    if persist:
        try:
            from music_workspace_restore_mode import (
                queue_pending_user_edit,
                user_edit_tracking_enabled,
            )

            if not user_edit_tracking_enabled(st.session_state):
                queue_pending_user_edit(st.session_state, "active_catalog_pick_key", reason="song_pick")
        except ImportError:
            pass
        try:
            from music_persistent_state import clear_music_ephemeral_default_song

            clear_music_ephemeral_default_song(st.session_state)
        except ImportError:
            pass
        persist_music_local_state(st)
    return data


def _pick_key_from_cloud_payload(session_state: dict[str, Any]) -> str:
    """Best-effort pick_key from last cloud/disk workspace blob (restore guard)."""
    payload = session_state.get("_suite_last_cloud_fetch_payload")
    if not isinstance(payload, dict) or not payload:
        return ""
    core = payload.get("core") if isinstance(payload.get("core"), dict) else {}
    pk = str(core.get("pick_key") or core.get("active_catalog_pick_key") or "").strip()
    if pk:
        return pk
    ws = payload.get("music_workspace_state")
    if isinstance(ws, dict):
        pk = str(ws.get("pick_key") or "").strip()
        if pk:
            return pk
        active = ws.get("active_song")
        if isinstance(active, dict):
            pk = str(active.get("pick_key") or "").strip()
            if pk:
                return pk
    extra = payload.get("session") if isinstance(payload.get("session"), dict) else {}
    pk = str(extra.get("active_catalog_pick_key") or "").strip()
    if pk:
        return pk
    sel = extra.get("selected_song")
    if isinstance(sel, dict):
        pk = str(sel.get("pick_key") or "").strip()
        if pk:
            return pk
    meta = payload.get("active_song_state")
    if isinstance(meta, dict):
        pk = str(meta.get("pick_key") or meta.get("active_catalog_pick_key") or "").strip()
        if pk:
            return pk
    ws = payload.get("music_workspace_state")
    if isinstance(ws, dict):
        active = ws.get("active_song")
        if isinstance(active, dict):
            pk = str(active.get("pick_key") or "").strip()
            if pk:
                return pk
    return ""


def _pick_key_from_canonical_session(session_state: dict[str, Any]) -> str:
    """Pick key from hydrated canonical/session restore before catalog default."""
    pk = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if pk:
        return pk
    sel = session_state.get(SELECTED_SONG_STATE_KEY) or {}
    pk = str(sel.get("pick_key") or "").strip()
    if pk:
        return pk
    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY

        meta = session_state.get(ACTIVE_SONG_STATE_KEY)
        if isinstance(meta, dict):
            pk = str(meta.get("pick_key") or meta.get("active_catalog_pick_key") or "").strip()
            if pk:
                return pk
    except ImportError:
        pass
    return ""


def reconcile_active_pick_key(
    session_state: dict[str, Any],
    *,
    song_picker_catalog: dict[str, dict[str, dict]] | None = None,
) -> str:
    """Best pick_key from workspace sources — never the catalog default."""
    pk = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if pk:
        return pk
    sel = session_state.get(SELECTED_SONG_STATE_KEY) or {}
    pk = str(sel.get("pick_key") or "").strip()
    if pk:
        return pk
    pk = _pick_key_from_canonical_session(session_state)
    if pk:
        return pk
    pk = _pick_key_from_cloud_payload(session_state)
    if not pk:
        return ""
    if song_picker_catalog is not None:
        resolved = resolve_pick_key(pk, song_picker_catalog=song_picker_catalog)
        return resolved or pk
    return pk


def _catalog_default_pick_key(
    song_picker_catalog: dict[str, dict[str, dict]] | None,
) -> str | None:
    return first_valid_pick_key(song_picker_catalog)


def _may_persist_pick_key_recovery(
    session_state: dict[str, Any],
    resolved_pk: str,
    *,
    song_picker_catalog: dict[str, dict[str, dict]] | None,
) -> bool:
    """True when a recovery commit may be written to disk/cloud."""
    try:
        from music_restore_phase import (
            authoritative_restore_in_progress,
            music_restore_phase_complete,
            workspace_is_truly_empty,
        )
    except ImportError:
        return True

    if authoritative_restore_in_progress(session_state):
        return False
    default_pk = _catalog_default_pick_key(song_picker_catalog)
    if default_pk and resolved_pk == default_pk:
        if not music_restore_phase_complete(session_state):
            return False
        return workspace_is_truly_empty(session_state)
    return True


def apply_active_pick_key_reconciliation(
    st: Any,
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]] | None = None,
) -> str:
    """Stamp session pick_key from cloud/canonical sources during startup restore."""
    ss = st.session_state
    try:
        from e5_reclaim_trace import note_e5_reclaim_sample

        note_e5_reclaim_sample(ss, phase="apply_active_pick_key_reconciliation")
    except ImportError:
        pass
    live = str(ss.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    try:
        from songs.music_source import explicit_custom_activation_is_authoritative

        if explicit_custom_activation_is_authoritative(ss) and (
            live.startswith("custom::")
            or str(ss.get("active_music_source") or "") == "custom_progression"
        ):
            try:
                from e5_reclaim_trace import note_e5_reclaim_writer

                note_e5_reclaim_writer(
                    ss,
                    writer="apply_active_pick_key_reconciliation_skipped",
                    reason="explicit_custom_epoch",
                )
            except ImportError:
                pass
            ss["_music_active_pick_key_reconciled"] = True
            return live
    except ImportError:
        pass
    candidate = reconcile_active_pick_key(ss, song_picker_catalog=song_picker_catalog)
    if not candidate:
        ss["_music_active_pick_key_reconciled"] = False
        return ""
    resolved = resolve_pick_key(candidate, song_picker_catalog=song_picker_catalog) or candidate
    live = str(ss.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    sel = ss.get(SELECTED_SONG_STATE_KEY) or {}
    sel_missing_key = isinstance(sel, dict) and not str(sel.get("key") or "").strip()
    if live == resolved:
        if sel_missing_key and resolved:
            apply_pick_key(
                st,
                resolved,
                song_picker_catalog,
                song_library=song_library,
                origin="restore",
                persist=False,
                skip_activity_log=True,
            )
        try:
            from studio_cache import invalidate_session_cache

            if sel_missing_key:
                invalidate_session_cache(ss, "chart_bundle")
        except ImportError:
            pass
        ss["_music_active_pick_key_reconciled"] = True
        return resolved
    persist = _may_persist_pick_key_recovery(
        ss,
        resolved,
        song_picker_catalog=song_picker_catalog,
    )
    apply_pick_key(
        st,
        resolved,
        song_picker_catalog,
        song_library=song_library,
        origin="restore",
        persist=persist,
    )
    try:
        from studio_cache import invalidate_session_cache

        invalidate_session_cache(ss, "chart_bundle")
    except ImportError:
        pass
    ss["_music_active_pick_key_reconciled"] = True
    return resolved


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
    try:
        from songs.music_source import custom_song_context_from_session, is_custom_progression
    except ImportError:
        is_custom_progression = lambda _s: False  # type: ignore[assignment,misc]
        custom_song_context_from_session = None  # type: ignore[assignment,misc]

    sel = st.session_state.get(SELECTED_SONG_STATE_KEY) or {}
    pk_early = str(st.session_state.get(ACTIVE_CATALOG_PICK_KEY) or sel.get("pick_key") or "").strip()
    if is_custom_progression(st.session_state) or pk_early.startswith("custom::"):
        if custom_song_context_from_session is not None:
            return custom_song_context_from_session(st.session_state)

    pk = reconcile_active_pick_key(
        st.session_state,
        song_picker_catalog=song_picker_catalog,
    )

    def _restore_still_in_progress() -> bool:
        try:
            from music_restore_phase import (
                authoritative_restore_in_progress,
                music_restore_phase_complete,
            )

            if authoritative_restore_in_progress(st.session_state):
                return True
            if not music_restore_phase_complete(st.session_state):
                return True
        except ImportError:
            pass
        return False

    def _recovery_may_persist(resolved_pk: str) -> bool:
        return _may_persist_pick_key_recovery(
            st.session_state,
            resolved_pk,
            song_picker_catalog=song_picker_catalog,
        )

    def _may_apply_catalog_default() -> bool:
        try:
            from music_restore_phase import music_restore_phase_complete, workspace_is_truly_empty

            if not music_restore_phase_complete(st.session_state):
                return False
            return workspace_is_truly_empty(st.session_state)
        except ImportError:
            return True

    def _merge_sel_onto_canonical(canon: dict, overlay: dict) -> dict:
        merged = dict(canon)
        for key, val in overlay.items():
            if key == "key" and (val is None or not str(val).strip()):
                continue
            if val is None:
                continue
            if key == "sections" and not val and merged.get("sections"):
                continue
            merged[key] = val
        return merged

    def _context_from_sel_only() -> tuple[str, str, dict] | None:
        title = str(sel.get("title") or "").strip()
        if not title:
            return None
        genre = str(sel.get("genre") or "").strip()
        pk = str(
            sel.get("pick_key")
            or st.session_state.get(ACTIVE_CATALOG_PICK_KEY)
            or ""
        ).strip()
        if not pk:
            try:
                from active_song_state import ACTIVE_SONG_STATE_KEY

                meta = st.session_state.get(ACTIVE_SONG_STATE_KEY)
                if isinstance(meta, dict):
                    pk = str(
                        meta.get("pick_key") or meta.get("active_catalog_pick_key") or ""
                    ).strip()
            except ImportError:
                pass
        if pk and not pk.startswith("custom::"):
            loaded = load_catalog_song_record_by_pick_key(
                pk,
                song_picker_catalog=song_picker_catalog,
                song_library=song_library,
            )
            if loaded is not None:
                g, canon_title, canon_data = loaded
                merged = _merge_sel_onto_canonical(canon_data, dict(sel))
                return g or genre, canon_title or title, merged
        song_data = dict(sel)
        if song_data.get("key"):
            return genre, title, song_data
        if song_library and genre and title in (song_library.get(genre) or {}):
            return genre, title, dict(song_library[genre][title])
        if song_data.get("sections"):
            return None
        return genre, title, song_data

    def _commit(resolved_pk: str, *, notice: str | None = None) -> tuple[str, str, dict]:
        if notice:
            st.session_state[PICK_KEY_RECOVERY_NOTICE_KEY] = notice
        if resolved_pk != pk or not sel.get("title"):
            try:
                from songs.key_state import resolve_restore_display_key

                restore_dk = resolve_restore_display_key(st.session_state)
            except ImportError:
                restore_dk = ""
            apply_pick_key(
                st,
                resolved_pk,
                song_picker_catalog,
                song_library=song_library,
                origin="recovery",
                persist=_recovery_may_persist(resolved_pk),
                display_key_override=restore_dk or None,
            )
        genre, label = parse_pick_key(resolved_pk)
        resolved = _build_library_from_picker(genre, label, song_picker_catalog, song_library)
        if resolved is None:
            cloud_pk = _pick_key_from_cloud_payload(st.session_state)
            if cloud_pk and resolve_pick_key(cloud_pk, song_picker_catalog=song_picker_catalog):
                return _commit(
                    resolve_pick_key(cloud_pk, song_picker_catalog=song_picker_catalog) or cloud_pk,
                    notice=notice or "Restored song selection from saved workspace.",
                )
            fallback = first_valid_pick_key(song_picker_catalog)
            if not fallback:
                raise RuntimeError("Song catalog is empty — cannot select a default song.")
            if not _may_apply_catalog_default():
                deferred = _context_from_sel_only()
                if deferred is not None:
                    return deferred
                raise RuntimeError("Song catalog default blocked — workspace is not empty.")
            return _commit(
                fallback,
                notice=notice or "Restored default song selection.",
            )
        title, song_data = resolved
        return genre, title, song_data

    if not pk:
        cloud_pk = _pick_key_from_cloud_payload(st.session_state)
        if cloud_pk and resolve_pick_key(cloud_pk, song_picker_catalog=song_picker_catalog):
            resolved_cloud = resolve_pick_key(cloud_pk, song_picker_catalog=song_picker_catalog) or cloud_pk
            if _restore_still_in_progress():
                deferred = _context_from_sel_only()
                if deferred is not None:
                    st.session_state["_pick_key_recovery_deferred"] = cloud_pk
                    return deferred
            return _commit(resolved_cloud)
        if _restore_still_in_progress():
            deferred = _context_from_sel_only()
            if deferred is not None:
                st.session_state["_pick_key_recovery_deferred"] = cloud_pk or pk
                return deferred
        fallback = first_valid_pick_key(song_picker_catalog)
        if not fallback:
            raise RuntimeError("Master song not initialized — call ensure_master_song_initialized first.")
        if not _may_apply_catalog_default():
            deferred = _context_from_sel_only()
            if deferred is not None:
                return deferred
            raise RuntimeError("Master song not initialized — workspace restore pending.")
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

    if _restore_still_in_progress():
        deferred = _context_from_sel_only()
        if deferred is not None:
            st.session_state["_pick_key_recovery_deferred"] = pk
            return deferred
        cloud_pk = _pick_key_from_cloud_payload(st.session_state)
        resolved_cloud = (
            resolve_pick_key(cloud_pk, song_picker_catalog=song_picker_catalog) if cloud_pk else None
        )
        if resolved_cloud:
            genre, label = parse_pick_key(resolved_cloud)
            built = _build_library_from_picker(genre, label, song_picker_catalog, song_library)
            if built is not None:
                title, song_data = built
                st.session_state["_pick_key_recovery_deferred"] = pk or cloud_pk
                return genre, title, song_data
    fallback = first_valid_pick_key(song_picker_catalog)
    if not fallback:
        raise RuntimeError("Song catalog is empty — cannot recover from stale pick key.")
    if not _may_apply_catalog_default():
        deferred = _context_from_sel_only()
        if deferred is not None:
            return deferred
        raise RuntimeError(f'Previous song "{sel.get("title") or pk}" is no longer in the catalog.')
    old = sel.get("title") or sel.get("label") or pk
    return _commit(
        fallback,
        notice=f'Previous song "{old}" is no longer in the catalog; switched to a default song.',
    )

"""Canonical music source ownership transitions — full clear, full rebuild.

When ownership changes the previous owner loses completely; the new owner
rebuilds backing_context, key, BPM, style, sections, and preference together.
"""

from __future__ import annotations

from typing import Any, Literal

PracticeOwner = Literal["catalog", "custom"]
BackingOwner = Literal["catalog", "custom", "entry_jam", "song_improv", "mission"]

CATALOG_REBUILD_NEEDED_KEY = "catalog_rebuild_needed"
CATALOG_REBUILD_RAN_KEY = "catalog_rebuild_ran"
CATALOG_REBUILD_PICK_KEY = "catalog_rebuild_pick_key"
CATALOG_REBUILD_RESULT_BOUND_PICK_KEY = "catalog_rebuild_result_bound_pick"
CATALOG_REBUILD_RESULT_KEY_KEY = "catalog_rebuild_result_key"
CATALOG_REBUILD_RESULT_BPM_KEY = "catalog_rebuild_result_bpm"
LAST_RECONCILE_REASON_KEY = "last_reconcile_reason"
CATALOG_BACKING_RESTORE_DIAG_KEY = "_catalog_backing_restore_diag"


def write_catalog_backing_restore_diag(session: dict[str, Any], **fields: Any) -> None:
    """Trace for Use Catalog Song Backing / catalog restore actions."""
    blob = dict(session.get(CATALOG_BACKING_RESTORE_DIAG_KEY) or {})
    blob.update(fields)
    session[CATALOG_BACKING_RESTORE_DIAG_KEY] = blob


def write_catalog_restore_diag(session: dict[str, Any], **fields: Any) -> None:
    """Dev trace for catalog restore / Use Catalog Song Backing."""
    blob = dict(session.get("_catalog_restore_diag") or {})
    blob.update(fields)
    session["_catalog_restore_diag"] = blob
    write_catalog_backing_restore_diag(session, **blob)


def write_key_transition_diag(session: dict[str, Any], **fields: Any) -> None:
    """Dev trace for catalog/custom key ownership transitions."""
    try:
        from songs.key_state import PENDING_DISPLAY_KEY
    except ImportError:
        PENDING_DISPLAY_KEY = "_pending_display_key"  # type: ignore[misc,assignment]
    try:
        from creative_key_sync import CREATIVE_CONCERT_KEY_SOURCE
    except ImportError:
        CREATIVE_CONCERT_KEY_SOURCE = "_creative_concert_key_source"  # type: ignore[misc,assignment]
    blob = dict(session.get("_key_transition_diag") or {})
    blob.update(dict(session.get(CATALOG_BACKING_RESTORE_DIAG_KEY) or {}))
    blob.update(fields)
    blob["display_key"] = str(session.get("display_key") or blob.get("display_key") or "").strip()
    blob["concert_key"] = str(session.get("concert_key") or blob.get("concert_key") or "").strip()
    blob["pending_display_key"] = str(session.get(PENDING_DISPLAY_KEY) or blob.get("pending_display_key") or "").strip()
    blob["creative_concert_key_source"] = str(
        session.get(CREATIVE_CONCERT_KEY_SOURCE) or blob.get("creative_concert_key_source") or ""
    ).strip()
    session["_key_transition_diag"] = blob
    write_catalog_backing_restore_diag(session, **blob)


def _write_catalog_rebuild_trace(
    session: dict[str, Any],
    *,
    needed: bool | None = None,
    ran: bool | None = None,
    pick_key: str | None = None,
    result_bound_pick: str | None = None,
    result_key: str | None = None,
    result_bpm: int | None = None,
    reason: str | None = None,
) -> None:
    if needed is not None:
        session[CATALOG_REBUILD_NEEDED_KEY] = bool(needed)
    if ran is not None:
        session[CATALOG_REBUILD_RAN_KEY] = bool(ran)
    if pick_key is not None:
        session[CATALOG_REBUILD_PICK_KEY] = str(pick_key or "").strip()
    if result_bound_pick is not None:
        session[CATALOG_REBUILD_RESULT_BOUND_PICK_KEY] = str(result_bound_pick or "").strip()
    if result_key is not None:
        session[CATALOG_REBUILD_RESULT_KEY_KEY] = str(result_key or "").strip()
    if result_bpm is not None:
        session[CATALOG_REBUILD_RESULT_BPM_KEY] = int(result_bpm or 0)
    if reason is not None:
        session[LAST_RECONCILE_REASON_KEY] = str(reason or "").strip()


def _write_catalog_bpm_diagnostics(
    session: dict[str, Any],
    *,
    pick_key: str,
    selected: dict[str, Any] | None,
    ctx_bpm: int | None = None,
) -> None:
    """Dev trace for catalog BPM resolution during rebuild."""
    try:
        from backing_context import _canonical_active_song_bpm, get_backing_context
        from songs.music_source import (
            _catalog_bpm_from_row,
            _catalog_picker_from_session,
            _catalog_row_for_pick,
        )
    except ImportError:
        return
    catalog = _catalog_picker_from_session(session)
    row = _catalog_row_for_pick(pick_key, catalog) if isinstance(catalog, dict) else None
    ext = row.get("extensions") if isinstance(row, dict) and isinstance(row.get("extensions"), dict) else {}
    session["catalog_rebuild_catalog_present"] = bool(catalog)
    session["catalog_rebuild_row_bpm"] = int(row.get("bpm") or 0) if isinstance(row, dict) else 0
    session["catalog_rebuild_row_default_bpm"] = int(ext.get("default_bpm") or 0) if ext else 0
    session["catalog_rebuild_selected_bpm_after_merge"] = (
        int(selected.get("bpm") or 0) if isinstance(selected, dict) else 0
    )
    session["catalog_rebuild_canonical_bpm"] = int(_canonical_active_song_bpm(session) or 0)
    try:
        from songs.bpm_state import LAST_BPM_SONG
        from songs.playback_defaults import LAST_BACKING_DEFAULTS_SONG_ID

        session["catalog_rebuild_last_bpm_song"] = str(session.get(LAST_BPM_SONG) or "")
        session["catalog_rebuild_last_backing_defaults_song_id"] = str(
            session.get(LAST_BACKING_DEFAULTS_SONG_ID) or session.get("last_backing_defaults_song_id") or ""
        )
    except ImportError:
        session["catalog_rebuild_last_bpm_song"] = str(session.get("_last_bpm_song") or "")
        session["catalog_rebuild_last_backing_defaults_song_id"] = str(
            session.get("last_backing_defaults_song_id") or ""
        )
    if ctx_bpm is not None:
        session["catalog_rebuild_ctx_bpm"] = int(ctx_bpm or 0)
    else:
        ctx = get_backing_context(session)
        session["catalog_rebuild_ctx_bpm"] = int(ctx.bpm or 0) if ctx else 0


def _creative_session_blob_is_active(session: dict[str, Any]) -> bool:
    """Creative session blob present without catalog/custom authority circular checks."""
    try:
        from creative_session_state import get_creative_session

        sess = get_creative_session(session, allow_migrate=True)
        if sess is None:
            return False
        if sess.tool_type in {"entry_style_jam", "jam_session_generator"}:
            return bool(sess.sections) or bool(sess.style)
        if sess.tool_type == "song_based_improvisation":
            return bool(sess.sections)
        if sess.tool_type == "mission":
            return bool(sess.mission_id)
        return False
    except ImportError:
        return False


def intentional_creative_backing_active(session: dict[str, Any]) -> bool:
    """True when user explicitly opened Backing from Creative (not stale catalog ctx)."""
    if session.get("_backing_released_specialized_context"):
        return False
    try:
        from backing_context import (
            BACKING_PREF_CATALOG,
            BACKING_PREF_CREATIVE,
            BACKING_PREF_CUSTOM,
            get_backing_context,
            get_backing_source_preference,
        )

        pref = get_backing_source_preference(session)
        ctx = get_backing_context(session)
    except ImportError:
        return False
    if ctx is None:
        return False
    src = str(ctx.source or "").strip()
    if src not in {"entry_jam", "song_improv", "mission", "custom_progression"}:
        return False
    try:
        from backing_source_navigation import BACKING_INTENT_FROM_CREATIVE, BACKING_OPEN_INTENT_KEY

        if str(session.get(BACKING_OPEN_INTENT_KEY) or "") == BACKING_INTENT_FROM_CREATIVE:
            return True
    except ImportError:
        pass
    blob_active = _creative_session_blob_is_active(session)
    if pref == BACKING_PREF_CREATIVE and blob_active:
        return True
    if blob_active and pref not in {BACKING_PREF_CATALOG, BACKING_PREF_CUSTOM}:
        return True
    return False


def intended_practice_owner(session: dict[str, Any]) -> PracticeOwner | None:
    """Live practice owner from active_music_source (not backing_pref or backing_context).

    Returns None when an intentional Creative backing workflow owns the session
    (Entry Jam / SBI / Mission opened from Creative) so practice catalog pick
    does not clobber active creative backing.
    """
    if intentional_creative_backing_active(session):
        return None
    try:
        from songs.music_source import (
            SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            cpl_session_is_active,
            custom_progression_is_active,
            is_custom_progression,
        )

        if (
            cpl_session_is_active(session)
            or is_custom_progression(session)
            or custom_progression_is_active(session)
        ):
            return "custom"
        if session.get(USER_CATALOG_SOURCE_CHOICE_KEY):
            return "catalog"
        if str(session.get("active_music_source") or "").strip() == SOURCE_CATALOG:
            return "catalog"
        pick = str(session.get("active_catalog_pick_key") or "").strip()
        if pick and not pick.startswith("custom::"):
            return "catalog"
    except ImportError:
        pass
    return None


def current_backing_owner(session: dict[str, Any]) -> BackingOwner | None:
    """Owner implied by the active backing_context snapshot."""
    try:
        from backing_context import get_backing_context
    except ImportError:
        return None
    ctx = get_backing_context(session)
    if ctx is None:
        return None
    src = str(ctx.source or "").strip()
    if src == "regular_song":
        return "catalog"
    if src == "custom_progression":
        return "custom"
    if src in {"entry_jam", "song_improv", "mission"}:
        return src  # type: ignore[return-value]
    return None


def backing_preference_owner(session: dict[str, Any]) -> PracticeOwner | None:
    try:
        from backing_context import (
            BACKING_PREF_CATALOG,
            BACKING_PREF_CUSTOM,
            get_backing_source_preference,
        )

        pref = get_backing_source_preference(session)
        if pref == BACKING_PREF_CATALOG:
            return "catalog"
        if pref == BACKING_PREF_CUSTOM:
            return "custom"
    except ImportError:
        pass
    return None


def active_catalog_pick_key(session: dict[str, Any]) -> str:
    """Authoritative catalog pick_key from session identity keys."""
    try:
        from songs.music_source import normalize_catalog_pick_key
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY
    except ImportError:
        return str(session.get("active_catalog_pick_key") or "").strip()
    pick = str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    sel = session.get(SELECTED_SONG_STATE_KEY)
    if isinstance(sel, dict):
        sel_pick = str(sel.get("pick_key") or "").strip()
        if sel_pick and not pick:
            pick = sel_pick
    return normalize_catalog_pick_key(pick, session_state=session)


def catalog_identity_aligns(session: dict[str, Any]) -> bool:
    """True when catalog pick_key, title, keys, BPM, and backing_context describe one song."""
    if intended_practice_owner(session) != "catalog":
        return True
    pick = active_catalog_pick_key(session)
    if not pick or pick.startswith("custom::"):
        return False
    try:
        from songs.music_source import _pick_keys_match
        from songs.state import SELECTED_SONG_STATE_KEY
    except ImportError:
        return True
    sel = session.get(SELECTED_SONG_STATE_KEY)
    if isinstance(sel, dict):
        sel_pick = str(sel.get("pick_key") or "").strip()
        if sel_pick and not _pick_keys_match(sel_pick, pick, session_state=session):
            return False
        title_sel = str(sel.get("title") or "").strip()
    else:
        title_sel = ""
    title_live = str(session.get("song") or session.get("active_song_title") or "").strip()
    if title_sel and title_live and title_sel != title_live:
        return False
    try:
        from backing_context import _canonical_active_song_bpm, get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and ctx.source == "regular_song":
            bound = str(ctx.bound_pick_key or ctx.active_song_id or "").strip()
            if bound and not _pick_keys_match(bound, pick, session_state=session):
                return False
            ctx_title = str(ctx.song_title or "").strip()
            expected_title = title_sel or title_live
            if ctx_title and expected_title and ctx_title != expected_title:
                return False
            if bound and _pick_keys_match(bound, pick, session_state=session):
                # BPM is a play-session / transport knob, not catalog identity.
                # Never force-reset Backing because Current BPM differs from catalog default.
                pass
    except ImportError:
        pass
    return True


def practice_backing_owners_align(session: dict[str, Any]) -> bool:
    """True when practice source, backing owner, pref, and song identity all agree."""
    practice = intended_practice_owner(session)
    if practice is None:
        return True
    backing = current_backing_owner(session)
    pref = backing_preference_owner(session)
    if practice == "catalog":
        if backing != "catalog" or pref != "catalog":
            return False
        return catalog_identity_aligns(session)
    if backing != "custom" or pref != "custom":
        return False
    return True


def _clear_cross_owner_transport(session: dict[str, Any]) -> None:
    """Drop transport keys that leak BPM/style/meter across owners."""
    for key in (
        "last_backing_defaults_song_id",
        "last_backing_bpm_song_id",
        "_canonical_backing_id",
        "_canonical_active_backing_song_id",
        "_backing_trace_sync_id",
    ):
        session.pop(key, None)
    try:
        from songs.bpm_state import LAST_BPM_SONG, PENDING_BACKING_TRACK_BPM
        from songs.playback_defaults import LAST_BACKING_DEFAULTS_SONG_ID, LAST_PLAYBACK_GROOVE_SONG

        session.pop(LAST_BPM_SONG, None)
        session.pop(PENDING_BACKING_TRACK_BPM, None)
        session.pop(LAST_BACKING_DEFAULTS_SONG_ID, None)
        session.pop(LAST_PLAYBACK_GROOVE_SONG, None)
    except ImportError:
        session.pop("_last_bpm_song", None)
        session.pop("_pending_backing_track_bpm", None)
    try:
        from songs.playback_defaults import _CANONICAL_BACKING_ID_KEY

        session.pop(_CANONICAL_BACKING_ID_KEY, None)
    except ImportError:
        pass
    try:
        from songs.meter_state import LAST_BACKING_METER_SONG

        session.pop(LAST_BACKING_METER_SONG, None)
    except ImportError:
        session.pop("_last_backing_meter_song", None)
    session.pop("backing_groove_style", None)
    session.pop("backing_track_bpm", None)
    try:
        from backing_track_state import clear_backing_local_edit

        clear_backing_local_edit(session)
    except ImportError:
        pass


def _release_creative_transport_authority(session: dict[str, Any]) -> None:
    """Clear Creative/Jam transport keys that can block catalog/custom key restore."""
    try:
        from backing_context import _detach_creative_backing_from_session, _release_creative_backing_ownership

        _release_creative_backing_ownership(session)
    except ImportError:
        try:
            from backing_context import _detach_creative_backing_from_session

            _detach_creative_backing_from_session(session)
        except ImportError:
            pass
    try:
        from creative_key_sync import CREATIVE_CONCERT_KEY_SOURCE

        session.pop(CREATIVE_CONCERT_KEY_SOURCE, None)
    except ImportError:
        session.pop("_creative_concert_key_source", None)
    try:
        from creative_session_state import JAM_CAPTURE_STAGING_KEY, JAM_SESSION_GENERATE_GUARD_KEY

        session.pop(JAM_CAPTURE_STAGING_KEY, None)
        session.pop(JAM_SESSION_GENERATE_GUARD_KEY, None)
    except ImportError:
        session.pop("_jam_capture_staging", None)
        session.pop("_jam_session_generate_guard", None)
    try:
        from session_widget_safe import (
            PENDING_IMPROV_ENSEMBLE_KEY,
            PENDING_IMPROV_ENTRY_MODE_KEY,
            PENDING_IMPROV_JAM_BPM_KEY,
            PENDING_IMPROV_JAM_KEY,
            PENDING_IMPROV_JAM_MOOD_KEY,
            PENDING_IMPROV_JAM_STYLE_KEY,
        )

        for pending_key in (
            PENDING_IMPROV_JAM_KEY,
            PENDING_IMPROV_JAM_BPM_KEY,
            PENDING_IMPROV_JAM_MOOD_KEY,
            PENDING_IMPROV_JAM_STYLE_KEY,
            PENDING_IMPROV_ENSEMBLE_KEY,
            PENDING_IMPROV_ENTRY_MODE_KEY,
        ):
            session.pop(pending_key, None)
        try:
            from session_widget_safe import PENDING_IMPROV_STYLE_BPM_KEY

            session.pop(PENDING_IMPROV_STYLE_BPM_KEY, None)
        except ImportError:
            session.pop("_pending_improv_style_bpm", None)
    except ImportError:
        for pending_key in (
            "_pending_improv_jam_key",
            "_pending_improv_jam_bpm",
            "_pending_improv_jam_mood",
            "_pending_improv_jam_style",
            "_pending_improv_ensemble",
            "_pending_improv_entry_mode",
            "_pending_improv_style_bpm",
        ):
            session.pop(pending_key, None)
    for key in (
        "improv_jam_bpm",
        "improv_style_bpm",
        "improv_jam_key",
        "improv_style_key",
    ):
        session.pop(key, None)


def _force_practice_display_key(
    session: dict[str, Any],
    concert_key: str,
    *,
    st_like: Any | None = None,
    writer: str = "catalog_ownership_reset",
) -> str:
    """Authoritatively set practice/display key — used on ownership switches."""
    concert = str(concert_key or "C").strip() or "C"
    try:
        from session_widget_safe import safe_assign_display_key

        safe_assign_display_key(session, concert, widget_safe=True, st_like=st_like)
    except ImportError:
        try:
            from songs.key_state import LAST_DISPLAY_KEY, PENDING_DISPLAY_KEY

            session["concert_key"] = concert
            session["display_key"] = concert
            session[LAST_DISPLAY_KEY] = concert
            session.pop(PENDING_DISPLAY_KEY, None)
        except ImportError:
            session["concert_key"] = concert
            session["display_key"] = concert
    try:
        from songs.key_state import LAST_DISPLAY_KEY

        if not session.get("_streamlit_widgets_locked_this_run"):
            session[LAST_DISPLAY_KEY] = concert
    except ImportError:
        pass
    pending = str(session.get("_pending_display_key") or "").strip()
    write_key_transition_diag(
        session,
        catalog_target_key=concert,
        display_key=str(session.get("display_key") or "").strip(),
        concert_key=concert,
        pending_display_key=pending,
        last_key_writer=writer,
    )
    return concert


def _apply_catalog_transport_from_record(
    session: dict[str, Any],
    *,
    st_like: Any,
    pick_key: str,
    selected: dict[str, Any],
    original_key: str,
    concert_key: str = "",
    force_display_key: bool = False,
    force_bpm_reset: bool = False,
) -> tuple[int, str, str]:
    """Force display key and BPM/groove/meter from canonical catalog record."""
    concert = str(concert_key or original_key or selected.get("key") or "C").strip() or "C"
    if force_display_key:
        live_display = str(session.get("display_key") or "").strip()
        try:
            from session_widget_safe import safe_assign_display_key, widgets_likely_instantiated

            locked = widgets_likely_instantiated(session)
            if locked or (live_display and live_display != concert):
                safe_assign_display_key(session, concert, widget_safe=True, st_like=st_like)
                session["concert_key"] = concert
            else:
                _force_practice_display_key(
                    session,
                    concert,
                    st_like=st_like,
                    writer="catalog_transport_force",
                )
        except ImportError:
            _force_practice_display_key(
                session,
                concert,
                st_like=st_like,
                writer="catalog_transport_force",
            )
    else:
        try:
            from session_widget_safe import reconcile_practice_key_fields, safe_assign_display_key

            safe_assign_display_key(session, concert, widget_safe=True, st_like=st_like)
            reconcile_practice_key_fields(session, authoritative=concert)
        except ImportError:
            session["display_key"] = concert
            session["concert_key"] = concert
            session.pop("_pending_display_key", None)

    lib_record = dict(selected)
    bpm = 0
    groove = "Pop groove"
    meter = "4/4"
    try:
        bpm = int(selected.get("bpm") or 0)
    except (TypeError, ValueError):
        bpm = 0
    if bpm <= 0:
        try:
            from songs.playback_defaults import canonical_active_song_bpm

            bpm = int(canonical_active_song_bpm(lib_record) or 0)
        except (ImportError, TypeError, ValueError):
            bpm = 0
    try:
        from songs.practice_key_state import resolve_source_bpm_for_pick

        bpm = resolve_source_bpm_for_pick(session, pick_key, default_bpm=bpm or 100)
    except ImportError:
        pass
    try:
        from songs.music_source import catalog_transport_bpm_for_pick

        row_bpm = catalog_transport_bpm_for_pick(session, pick_key)
        if row_bpm > 0 and bpm <= 0:
            bpm = row_bpm
    except ImportError:
        pass
    try:
        from backing_context import _canonical_active_song_bpm, _canonical_active_song_groove
        from songs.playback_defaults import (
            active_song_sync_id,
            canonicalize_backing_defaults_for_song,
            get_song_default_meter,
            playback_song_id,
            prime_active_song_bpm,
        )

        if bpm <= 0:
            bpm = int(_canonical_active_song_bpm(session) or 100)
        groove = str(_canonical_active_song_groove(session) or "Pop groove").strip() or "Pop groove"
        meter = str(get_song_default_meter(lib_record) or "4/4").strip() or "4/4"
        pid = playback_song_id(
            is_custom=False,
            song_title=str(selected.get("title") or ""),
            song_artist=str(selected.get("artist") or ""),
        )
        sync_id = active_song_sync_id(pick_key=pick_key, playback_song_id=pid, is_custom=False)
        if force_bpm_reset or force_display_key:
            try:
                from songs.playback_defaults import _CANONICAL_BACKING_ID_KEY

                session.pop(_CANONICAL_BACKING_ID_KEY, None)
            except ImportError:
                session.pop("_canonical_active_backing_song_id", None)
        effective_force = bool(force_bpm_reset or force_display_key)
        try:
            from songs.practice_key_state import get_source_bpm

            if get_source_bpm(session, pick_key, default=0) > 0:
                effective_force = False
        except ImportError:
            pass
        playback_target = session if st_like is None else st_like
        prime_active_song_bpm(playback_target, sync_id=sync_id, active_song_bpm=bpm)
        try:
            from songs.practice_key_state import mark_force_bpm_sync

            mark_force_bpm_sync(session, sync_id)
        except ImportError:
            pass
        canon_result = canonicalize_backing_defaults_for_song(
            playback_target,
            sync_id=sync_id,
            active_song_bpm=bpm,
            active_song_groove=groove,
            active_song_meter=meter,
            force_reset=effective_force,
        )
        if isinstance(canon_result, dict) and canon_result.get("did_reset"):
            bpm = int(canon_result.get("applied_bpm") or bpm)
    except ImportError:
        pass
    return bpm, groove, meter


def _finalize_catalog_backing_context(
    ctx: Any,
    *,
    pick_key: str,
    selected: dict[str, Any],
    original_key: str,
    bpm: int,
    groove: str,
) -> Any:
    """Bind backing_context identity fields to the canonical catalog record."""
    title = str(selected.get("title") or "").strip()
    concert = str(original_key or selected.get("key") or "C").strip() or "C"
    ctx.bound_pick_key = pick_key
    ctx.active_song_id = pick_key
    if title:
        ctx.song_title = title
    ctx.key = concert
    ctx.concert_key = concert
    ctx.display_key = concert
    ctx.bpm = int(bpm or ctx.bpm or 100)
    if groove:
        ctx.groove = groove
    ctx.source = "regular_song"
    return ctx


def rebuild_catalog_backing_from_canonical_pick(
    session: dict[str, Any],
    *,
    st_like: Any | None = None,
    pick_key: str = "",
    practice_concert_key: str = "",
    reset_to_original: bool = True,
    force_bpm_reset: bool = True,
) -> Any:
    """Full backing_context rebuild from canonical_active_pick_key and catalog record."""
    from types import SimpleNamespace

    from songs.music_source import (
        USER_CATALOG_SOURCE_CHOICE_KEY,
        resolve_catalog_song_for_pick,
        set_catalog_source,
        _sync_catalog_session_surface_keys,
    )

    pick = str(pick_key or "").strip() or active_catalog_pick_key(session)
    _write_catalog_rebuild_trace(session, pick_key=pick)
    if not pick or pick.startswith("custom::"):
        _write_catalog_rebuild_trace(
            session,
            ran=False,
            result_bound_pick="",
            result_key="",
            result_bpm=0,
        )
        return None

    selected, original_key = resolve_catalog_song_for_pick(
        session,
        pick,
        authoritative_transport=True,
    )
    _write_catalog_bpm_diagnostics(session, pick_key=pick, selected=selected)
    if not selected:
        _write_catalog_rebuild_trace(
            session,
            ran=False,
            result_bound_pick="",
            result_key="",
            result_bpm=0,
        )
        return None

    catalog_original = str(original_key or selected.get("key") or "C").strip() or "C"
    try:
        from songs.practice_key_state import (
            get_practice_concert_key,
            resolve_practice_concert_key_for_pick,
        )

        try:
            from practice_key_mode import is_fixed_practice_key_mode
        except ImportError:
            is_fixed_practice_key_mode = lambda _session: False  # type: ignore[misc,assignment]
        saved_key = get_practice_concert_key(session, pick)
        try:
            from backing_source_navigation import peek_key_transition_intent

            _transition = peek_key_transition_intent(session)
        except ImportError:
            _transition = ""
        if reset_to_original or _transition in {
            "switch_to_catalog_backing",
            "catalog_source_switch",
            "creative_to_catalog",
        }:
            try:
                from music_workflow_song_practice import reconcile_practice_key_after_active_source_change
                from songs.music_source import CATALOG_BEFORE_CREATIVE_KEY, LAST_CATALOG_STATE_KEY

                prev_pick = ""
                for snap_key in (CATALOG_BEFORE_CREATIVE_KEY, LAST_CATALOG_STATE_KEY):
                    raw = session.get(snap_key)
                    if isinstance(raw, dict):
                        cand = str(raw.get("pick_key") or "").strip()
                        if cand and cand != pick:
                            prev_pick = cand
                            break
                if not prev_pick:
                    invalidated = str(session.get("_backing_restore_invalidated_from") or "").strip()
                    if invalidated.startswith("pk::"):
                        prev_pick = invalidated[4:]
                healed = reconcile_practice_key_after_active_source_change(
                    session,
                    pick_key=pick,
                    original_key=catalog_original,
                    previous_pick_key=prev_pick,
                    source=f"rebuild_catalog:{_transition or 'reset_to_original'}",
                    force_source_change=True,
                )
                if healed:
                    saved_key = get_practice_concert_key(session, pick)
                    practice_concert_key = healed
            except ImportError:
                pass
        if saved_key and not is_fixed_practice_key_mode(session):
            target_key = saved_key
        elif reset_to_original:
            target_key = resolve_practice_concert_key_for_pick(
                session,
                pick,
                original_key=catalog_original,
            )
        else:
            target_key = (
                str(practice_concert_key or "").strip()
                or resolve_practice_concert_key_for_pick(session, pick, original_key=catalog_original)
            )
    except ImportError:
        saved_key = ""
        if reset_to_original:
            target_key = catalog_original
        else:
            target_key = str(practice_concert_key or "").strip() or catalog_original
    # Capo is player context — Creative→Backing must not apply a sealed Roads PK (A)
    # while the live song Practice Key still matches the catalog original (Love Story C).
    try:
        from guitar_capo import CAPO_ENABLED_KEY

        if session.get(CAPO_ENABLED_KEY):
            live_dk = str(session.get("display_key") or session.get("concert_key") or "").strip()
            if live_dk and catalog_original:
                try:
                    from music_theory import split_key_center

                    live_t, _ = split_key_center(live_dk)
                    orig_t, _ = split_key_center(catalog_original)
                    if live_t and orig_t and live_t == orig_t:
                        target_key = live_dk
                except ImportError:
                    if live_dk == catalog_original:
                        target_key = live_dk
    except ImportError:
        pass
    try:
        from backing_source_navigation import peek_key_transition_intent

        transition = peek_key_transition_intent(session)
    except ImportError:
        transition = ""
    write_key_transition_diag(
        session,
        catalog_original_key=catalog_original,
        catalog_target_key=target_key,
        key_transition_intent=transition,
        active_transport_owner="catalog" if reset_to_original else "catalog_preserve_practice",
        last_key_writer="rebuild_catalog_backing_from_canonical_pick",
    )

    _clear_cross_owner_transport(session)
    _release_creative_transport_authority(session)
    try:
        from backing_context import (
            BACKING_PREF_CATALOG,
            apply_backing_context_to_session,
            build_regular_song_context,
            clear_backing_context,
            set_backing_context,
            set_backing_source_preference,
        )
    except ImportError:
        return None

    clear_backing_context(session)
    for key in ("_creative_concert_key_source",):
        session.pop(key, None)
    try:
        from creative_key_sync import CREATIVE_CONCERT_KEY_SOURCE

        session.pop(CREATIVE_CONCERT_KEY_SOURCE, None)
    except ImportError:
        pass

    session[USER_CATALOG_SOURCE_CHOICE_KEY] = True
    set_catalog_source(session)
    _sync_catalog_session_surface_keys(session, pick_key=pick, selected_song=selected)

    st = st_like or SimpleNamespace(session_state=session)
    capo_keeps_live_pk = False
    try:
        from guitar_capo import CAPO_ENABLED_KEY
        from music_theory import split_key_center

        if session.get(CAPO_ENABLED_KEY) and target_key and catalog_original:
            tt, _ = split_key_center(str(target_key))
            ot, _ = split_key_center(str(catalog_original))
            capo_keeps_live_pk = bool(tt and ot and tt == ot)
    except ImportError:
        capo_keeps_live_pk = False
    bpm, groove, _meter = _apply_catalog_transport_from_record(
        session,
        st_like=st,
        pick_key=pick,
        selected=selected,
        original_key=original_key,
        concert_key=target_key,
        force_display_key=bool(reset_to_original and not saved_key) or capo_keeps_live_pk,
        force_bpm_reset=force_bpm_reset,
    )

    set_backing_source_preference(session, BACKING_PREF_CATALOG)
    ctx = build_regular_song_context(session)
    ctx = _finalize_catalog_backing_context(
        ctx,
        pick_key=pick,
        selected=selected,
        original_key=target_key,
        bpm=bpm,
        groove=groove,
    )
    set_backing_context(session, ctx)
    apply_backing_context_to_session(session, ctx, st_like=st, widget_safe=True)
    _write_catalog_bpm_diagnostics(session, pick_key=pick, selected=selected, ctx_bpm=int(ctx.bpm or 0))
    _write_catalog_rebuild_trace(
        session,
        ran=True,
        result_bound_pick=str(ctx.bound_pick_key or ctx.active_song_id or ""),
        result_key=str(ctx.concert_key or ctx.display_key or ctx.key or ""),
        result_bpm=int(ctx.bpm or 0),
    )
    try:
        from songs.key_state import BACKING_NEEDS_REGEN

        session[BACKING_NEEDS_REGEN] = True
    except ImportError:
        pass
    return ctx


def activate_catalog_ownership(
    session: dict[str, Any],
    *,
    st_like: Any | None = None,
    preserve_practice_key: bool = False,
) -> Any:
    """Catalog song owns everything — release prior owner, rebuild from active catalog pick."""
    pick = active_catalog_pick_key(session)
    practice_key = ""
    if preserve_practice_key:
        try:
            from backing_source_navigation import _resolved_practice_display_key

            practice_key = _resolved_practice_display_key(session)
        except ImportError:
            practice_key = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if pick and not pick.startswith("custom::"):
        return rebuild_catalog_backing_from_canonical_pick(
            session,
            st_like=st_like,
            pick_key=pick,
            practice_concert_key=practice_key,
            reset_to_original=not preserve_practice_key,
            force_bpm_reset=True,
        )
    _clear_cross_owner_transport(session)
    from backing_context import restore_regular_song_backing

    return restore_regular_song_backing(session, st_like=st_like)


def activate_custom_ownership(
    session: dict[str, Any],
    *,
    st_like: Any | None = None,
    preserve_practice_key: bool = False,
) -> Any:
    """Custom progression owns everything — release prior owner, rebuild from CPL active song."""
    _clear_cross_owner_transport(session)
    if not preserve_practice_key:
        _release_creative_transport_authority(session)
    from backing_context import restore_custom_song_backing

    return restore_custom_song_backing(session, st_like=st_like)


def activate_entry_jam_ownership(session: dict[str, Any], *, st_like: Any | None = None) -> Any:
    """Entry Jam / Style Jam owns backing — rebuild creative entry_jam context."""
    from backing_context import open_backing_from_creative

    return open_backing_from_creative(session, source="entry_jam", st_like=st_like)


def activate_sbi_ownership(session: dict[str, Any], *, st_like: Any | None = None) -> Any:
    """Song-Based Improvisation owns backing — rebuild song_improv context."""
    from backing_context import open_backing_from_creative

    return open_backing_from_creative(session, source="song_improv", st_like=st_like)


def activate_mission_ownership(session: dict[str, Any], *, st_like: Any | None = None) -> Any:
    from backing_context import open_backing_from_creative

    return open_backing_from_creative(session, source="mission", st_like=st_like)


def reconcile_source_ownership(
    session: dict[str, Any],
    *,
    st_like: Any | None = None,
    reason: str = "",
) -> bool:
    """Transition backing to match practice owner when practice owns and backing is stale."""
    if reason:
        _write_catalog_rebuild_trace(session, reason=reason)
    try:
        from songs.music_source import peek_catalog_restore_pin

        restore_pin = peek_catalog_restore_pin(session)
        if restore_pin:
            try:
                from backing_context import get_backing_context
                from songs.music_source import _pick_keys_match

                ctx = get_backing_context(session)
                if ctx is not None and ctx.source == "regular_song":
                    bound = str(ctx.bound_pick_key or ctx.active_song_id or "").strip()
                    if bound and _pick_keys_match(bound, restore_pin, session_state=session):
                        _write_catalog_rebuild_trace(session, ran=False, reason="catalog_restore_pin")
                        return False
            except ImportError:
                pass
    except ImportError:
        pass
    practice = intended_practice_owner(session)
    identity_stale = practice == "catalog" and not catalog_identity_aligns(session)
    _write_catalog_rebuild_trace(session, needed=identity_stale)
    if practice is None:
        _write_catalog_rebuild_trace(session, ran=False)
        return False
    if identity_stale:
        rebuild_catalog_backing_from_canonical_pick(session, st_like=st_like)
        return True
    if practice_backing_owners_align(session):
        _write_catalog_rebuild_trace(session, ran=False)
        return False
    if practice == "catalog":
        activate_catalog_ownership(session, st_like=st_like)
        _write_catalog_rebuild_trace(session, ran=True)
        return True
    activate_custom_ownership(session, st_like=st_like)
    _write_catalog_rebuild_trace(session, ran=False)
    return True


def _raw_practice_owner(session: dict[str, Any]) -> PracticeOwner | None:
    """Catalog/custom practice owner without creative-backing suppression."""
    try:
        from songs.music_source import (
            SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            cpl_session_is_active,
            custom_progression_is_active,
            is_custom_progression,
        )

        if (
            cpl_session_is_active(session)
            or is_custom_progression(session)
            or custom_progression_is_active(session)
        ):
            return "custom"
        if session.get(USER_CATALOG_SOURCE_CHOICE_KEY):
            return "catalog"
        if str(session.get("active_music_source") or "").strip() == SOURCE_CATALOG:
            return "catalog"
        pick = str(session.get("active_catalog_pick_key") or "").strip()
        if pick and not pick.startswith("custom::"):
            return "catalog"
    except ImportError:
        pass
    return None


def _creative_transport_authoritative(session: dict[str, Any]) -> bool:
    """True when Creative/Jam transport still owns the live practice key."""
    try:
        from creative_key_sync import CREATIVE_CONCERT_KEY_SOURCE

        if str(session.get(CREATIVE_CONCERT_KEY_SOURCE) or "").strip():
            return True
    except ImportError:
        if str(session.get("_creative_concert_key_source") or "").strip():
            return True
    try:
        from backing_context import active_creative_backing_context

        if active_creative_backing_context(session) is not None:
            return True
    except ImportError:
        pass
    try:
        from creative_session_state import creative_session_is_active

        if creative_session_is_active(session):
            return True
    except ImportError:
        pass
    if str(session.get("improv_jam_key") or session.get("improv_style_key") or "").strip():
        return True
    return False


def _resolve_source_original_key(session: dict[str, Any], owner: PracticeOwner) -> str:
    """Original/home key for the active catalog or custom practice source."""
    if owner == "custom":
        try:
            from custom_progression_lab import CPL_ACTIVE_KEY, default_active_progression, ensure_original_structure
            from songs.music_source import custom_original_key

            active = ensure_original_structure(session.get(CPL_ACTIVE_KEY) or default_active_progression())
            return str(custom_original_key(active) or "C").strip() or "C"
        except ImportError:
            pass
        sel = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
        return str(sel.get("key") or "C").strip() or "C"
    pick = active_catalog_pick_key(session)
    sel = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
    original = str(sel.get("key") or "").strip()
    if original:
        return original
    try:
        from songs.music_source import resolve_catalog_song_for_pick

        selected, original_key = resolve_catalog_song_for_pick(session, pick)
        if selected:
            return str(original_key or selected.get("key") or "C").strip() or "C"
    except ImportError:
        pass
    return "C"


def maybe_reset_practice_key_on_source_activation(
    session: dict[str, Any],
    *,
    st_like: Any | None = None,
    surface: str = "",
) -> bool:
    """Reset practice key to source original when leaving Creative/custom transport."""
    try:
        from backing_source_navigation import _backing_intent_preserves_practice_key, peek_key_transition_intent

        if _backing_intent_preserves_practice_key(peek_key_transition_intent(session)):
            return False
    except ImportError:
        pass
    owner = _raw_practice_owner(session)
    if owner is None:
        return False
    original = _resolve_source_original_key(session, owner)
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    needs_reset = _creative_transport_authoritative(session)
    if not needs_reset and live and original and live != original:
        try:
            from backing_context import get_backing_source_preference, BACKING_PREF_CREATIVE

            if get_backing_source_preference(session) == BACKING_PREF_CREATIVE:
                needs_reset = True
        except ImportError:
            pass
    if not needs_reset and owner == "custom" and live and original and live != original:
        try:
            from songs.practice_key_state import get_practice_concert_key, resolve_practice_source_pick

            saved = get_practice_concert_key(
                session,
                resolve_practice_source_pick(session),
                default=live,
            )
            if saved and saved == live:
                return False
        except ImportError:
            pass
        try:
            from custom_progression_lab import CPL_LAST_DISPLAY_KEY

            cpl_last = str(session.get(CPL_LAST_DISPLAY_KEY) or "").strip()
        except ImportError:
            cpl_last = str(session.get("cpl_last_display_key") or "").strip()
        intentional_transpose = cpl_last == live and live != original
        if not intentional_transpose:
            needs_reset = True
    if not needs_reset and owner == "catalog" and live and original and live != original:
        try:
            from songs.practice_key_state import get_practice_concert_key, resolve_practice_source_pick

            pick = resolve_practice_source_pick(session)
            saved = get_practice_concert_key(session, pick)
            if saved:
                return False
            saved = get_practice_concert_key(
                session,
                resolve_practice_source_pick(session),
                default=live,
            )
            if saved and saved == live:
                return False
        except ImportError:
            pass
    if not needs_reset:
        return False
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song
        from songs.practice_key_state import resolve_practice_source_pick

        if is_fixed_practice_key_mode(session):
            original = resolve_practice_concert_key_for_song(
                session,
                original,
                pick_key=resolve_practice_source_pick(session),
                fallback=original,
            )
    except ImportError:
        pass
    _release_creative_transport_authority(session)
    try:
        from backing_context import BACKING_PREF_CATALOG, BACKING_PREF_CUSTOM, set_backing_source_preference

        if owner == "catalog":
            set_backing_source_preference(session, BACKING_PREF_CATALOG)
        else:
            set_backing_source_preference(session, BACKING_PREF_CUSTOM)
    except ImportError:
        pass
    _force_practice_display_key(
        session,
        original,
        st_like=st_like,
        writer=f"source_activation_{surface or 'unknown'}",
    )
    write_key_transition_diag(
        session,
        catalog_original_key=original,
        catalog_target_key=original,
        key_transition_intent=f"source_activation_{surface}",
        active_transport_owner=owner,
        last_key_writer=f"maybe_reset_practice_key_on_source_activation:{surface}",
    )
    return True


def trace_practice_key_owner(
    session: dict[str, Any],
    *,
    phase: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record source-scoped Practice Key ownership for Pass 8 isolation debugging."""
    ctx_source = ""
    ctx_id = ""
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            ctx_source = str(ctx.source or "")
            ctx_id = str(ctx.bound_pick_key or ctx.active_song_id or ctx.mission_id or "")
    except ImportError:
        pass
    pick = str(session.get("active_catalog_pick_key") or "").strip()
    store_val = ""
    try:
        from songs.practice_key_state import get_practice_concert_key

        if pick:
            store_val = str(get_practice_concert_key(session, pick) or "").strip()
    except ImportError:
        store_val = ""
    owner = ""
    try:
        from generated_jam_key_context import generated_jam_owns_practice_key

        if generated_jam_owns_practice_key(session):
            owner = "generated_jam"
    except ImportError:
        owner = ""
    if not owner:
        owner = str(intended_practice_owner(session) or "catalog")
    snap = {
        "phase": str(phase or ""),
        "studio_page": str(session.get("studio_page") or ""),
        "source_kind": ctx_source or str(session.get("improv_entry_mode") or ""),
        "source_identity": ctx_id or pick,
        "practice_key_owner": owner,
        "practice_key_value": str(session.get("display_key") or session.get("concert_key") or ""),
        "workspace_field": "practice_key_by_source" if store_val else "display_key",
        "practice_key_by_source": store_val,
        "improv_jam_key": str(session.get("improv_jam_key") or session.get("improv_style_key") or ""),
    }
    if extra:
        snap.update(extra)
    buf = list(session.get("_pk_owner_trace") or [])
    buf.append(snap)
    session["_pk_owner_trace"] = buf[-24:]
    return snap


__all__ = [
    "PracticeOwner",
    "BackingOwner",
    "CATALOG_REBUILD_NEEDED_KEY",
    "CATALOG_REBUILD_PICK_KEY",
    "CATALOG_REBUILD_RAN_KEY",
    "CATALOG_REBUILD_RESULT_BPM_KEY",
    "CATALOG_REBUILD_RESULT_BOUND_PICK_KEY",
    "CATALOG_REBUILD_RESULT_KEY_KEY",
    "CATALOG_BACKING_RESTORE_DIAG_KEY",
    "LAST_RECONCILE_REASON_KEY",
    "activate_catalog_ownership",
    "activate_custom_ownership",
    "activate_entry_jam_ownership",
    "activate_mission_ownership",
    "activate_sbi_ownership",
    "active_catalog_pick_key",
    "backing_preference_owner",
    "catalog_identity_aligns",
    "current_backing_owner",
    "intentional_creative_backing_active",
    "intended_practice_owner",
    "maybe_reset_practice_key_on_source_activation",
    "practice_backing_owners_align",
    "rebuild_catalog_backing_from_canonical_pick",
    "reconcile_source_ownership",
    "trace_practice_key_owner",
    "write_catalog_backing_restore_diag",
]

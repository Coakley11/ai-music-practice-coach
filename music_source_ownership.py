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
                expected_bpm = _canonical_active_song_bpm(session)
                if expected_bpm and int(ctx.bpm or 0) != int(expected_bpm):
                    return False
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
        "_canonical_backing_id",
        "_backing_trace_sync_id",
    ):
        session.pop(key, None)
    try:
        from songs.bpm_state import LAST_BPM_SONG

        session.pop(LAST_BPM_SONG, None)
    except ImportError:
        session.pop("_last_bpm_song", None)
    try:
        from songs.playback_defaults import _CANONICAL_BACKING_ID_KEY

        session.pop(_CANONICAL_BACKING_ID_KEY, None)
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
    except ImportError:
        for pending_key in (
            "_pending_improv_jam_key",
            "_pending_improv_jam_bpm",
            "_pending_improv_jam_mood",
            "_pending_improv_jam_style",
            "_pending_improv_ensemble",
            "_pending_improv_entry_mode",
        ):
            session.pop(pending_key, None)


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
        from songs.key_state import LAST_DISPLAY_KEY, PENDING_DISPLAY_KEY, request_display_key
    except ImportError:
        LAST_DISPLAY_KEY = "_last_app_display_key"  # type: ignore[misc,assignment]
        PENDING_DISPLAY_KEY = "_pending_display_key"  # type: ignore[misc,assignment]
        request_display_key = None  # type: ignore[assignment,misc]
    session.pop(PENDING_DISPLAY_KEY, None)
    session["concert_key"] = concert
    session["display_key"] = concert
    session[LAST_DISPLAY_KEY] = concert
    if st_like is not None and request_display_key is not None:
        try:
            request_display_key(st_like, concert)
        except Exception:
            pass
    write_key_transition_diag(
        session,
        catalog_target_key=concert,
        display_key=concert,
        concert_key=concert,
        pending_display_key="",
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
) -> tuple[int, str, str]:
    """Force display key and BPM/groove/meter from canonical catalog record."""
    concert = str(concert_key or original_key or selected.get("key") or "C").strip() or "C"
    if force_display_key:
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
        from songs.music_source import catalog_transport_bpm_for_pick

        row_bpm = catalog_transport_bpm_for_pick(session, pick_key)
        if row_bpm > 0:
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
        prime_active_song_bpm(st_like, sync_id=sync_id, active_song_bpm=bpm)
        canonicalize_backing_defaults_for_song(
            st_like,
            sync_id=sync_id,
            active_song_bpm=bpm,
            active_song_groove=groove,
            active_song_meter=meter,
        )
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
    if reset_to_original:
        target_key = catalog_original
    else:
        target_key = str(practice_concert_key or "").strip() or catalog_original
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
    bpm, groove, _meter = _apply_catalog_transport_from_record(
        session,
        st_like=st,
        pick_key=pick,
        selected=selected,
        original_key=original_key,
        concert_key=target_key,
        force_display_key=reset_to_original,
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
    "practice_backing_owners_align",
    "rebuild_catalog_backing_from_canonical_pick",
    "reconcile_source_ownership",
    "write_catalog_backing_restore_diag",
]

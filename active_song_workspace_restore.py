"""Canonical active-song identity from hydrated workspace envelopes."""

from __future__ import annotations

from typing import Any

ACTIVE_SONG_WORKSPACE_DIAG_KEY = "_active_song_workspace_restore_diag"
ACTIVE_SONG_RESTORE_INCOMPLETE_KEY = "_music_active_song_restore_incomplete"
CHOOSE_SONG_RESTORE_STATE_KEY = "_music_choose_song_restore_state"


def _first_str(*values: Any) -> str:
    for val in values:
        s = str(val or "").strip()
        if s:
            return s
    return ""


def _session_pick_key(session: dict[str, Any]) -> str:
    try:
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY
    except ImportError:
        return ""
    pk = str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if pk:
        return pk
    sel = session.get(SELECTED_SONG_STATE_KEY)
    if isinstance(sel, dict):
        pk = str(sel.get("pick_key") or "").strip()
        if pk:
            return pk
    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY

        meta = session.get(ACTIVE_SONG_STATE_KEY)
        if isinstance(meta, dict):
            return str(meta.get("pick_key") or meta.get("active_catalog_pick_key") or "").strip()
    except ImportError:
        pass
    return ""


def inspect_workspace_envelope_identity(payload: dict[str, Any]) -> dict[str, Any]:
    """Safe read-only inspection of saved workspace song identity fields."""
    core = payload.get("core") if isinstance(payload.get("core"), dict) else {}
    session_extra = payload.get("session") if isinstance(payload.get("session"), dict) else {}
    meta = payload.get("active_song_state") if isinstance(payload.get("active_song_state"), dict) else {}
    ws = payload.get("music_workspace_state") if isinstance(payload.get("music_workspace_state"), dict) else {}
    ws_active = ws.get("active_song") if isinstance(ws.get("active_song"), dict) else {}
    sel_blob = session_extra.get("selected_song") if isinstance(session_extra.get("selected_song"), dict) else {}
    meta_sel = meta.get("selected_song") if isinstance(meta.get("selected_song"), dict) else {}

    core_pk = _first_str(core.get("pick_key"), core.get("active_catalog_pick_key"))
    active_song_pk = _first_str(
        meta.get("pick_key"),
        meta.get("active_catalog_pick_key"),
        ws.get("pick_key"),
        ws_active.get("pick_key"),
        session_extra.get("active_catalog_pick_key"),
        sel_blob.get("pick_key"),
        meta_sel.get("pick_key"),
    )
    title = _first_str(
        ws_active.get("title"),
        meta_sel.get("title"),
        sel_blob.get("title"),
        core.get("song"),
        meta.get("title"),
    )
    genre = _first_str(
        ws_active.get("genre"),
        meta_sel.get("genre"),
        sel_blob.get("genre"),
        meta.get("genre"),
    )
    return {
        "workspace_has_core_pick_key": bool(core_pk),
        "workspace_has_active_song_pick_key": bool(active_song_pk),
        "workspace_active_song_title": title or None,
        "workspace_active_song_genre": genre or None,
        "workspace_core_pick_key_preview": core_pk[:48] if core_pk else None,
        "workspace_active_song_pick_key_preview": active_song_pk[:48] if active_song_pk else None,
    }


def extract_canonical_active_song_identity(payload: dict[str, Any]) -> dict[str, Any]:
    """Best canonical active-song object from a hydrated workspace envelope."""
    if not isinstance(payload, dict) or not payload:
        return {}
    core = payload.get("core") if isinstance(payload.get("core"), dict) else {}
    session_extra = payload.get("session") if isinstance(payload.get("session"), dict) else {}
    meta = payload.get("active_song_state") if isinstance(payload.get("active_song_state"), dict) else {}
    ws = payload.get("music_workspace_state") if isinstance(payload.get("music_workspace_state"), dict) else {}
    ws_active = ws.get("active_song") if isinstance(ws.get("active_song"), dict) else {}
    sel_blob = session_extra.get("selected_song") if isinstance(session_extra.get("selected_song"), dict) else {}
    meta_sel = meta.get("selected_song") if isinstance(meta.get("selected_song"), dict) else {}

    pick_key = _first_str(
        core.get("pick_key"),
        core.get("active_catalog_pick_key"),
        session_extra.get("active_catalog_pick_key"),
        sel_blob.get("pick_key"),
        meta.get("pick_key"),
        meta.get("active_catalog_pick_key"),
        meta_sel.get("pick_key"),
        ws.get("pick_key"),
        ws_active.get("pick_key"),
    )
    title = _first_str(
        ws_active.get("title"),
        meta_sel.get("title"),
        sel_blob.get("title"),
        core.get("song"),
    )
    artist = _first_str(
        ws_active.get("artist"),
        meta_sel.get("artist"),
        sel_blob.get("artist"),
        core.get("artist"),
    )
    genre = _first_str(
        ws_active.get("genre"),
        meta_sel.get("genre"),
        sel_blob.get("genre"),
        meta.get("genre"),
    )
    original_key = _first_str(
        ws_active.get("original_key"),
        meta_sel.get("key"),
        sel_blob.get("key"),
        meta.get("original_key"),
    )
    source_type = _first_str(
        ws_active.get("source_type"),
        ws_active.get("music_source"),
        meta.get("music_source"),
        session_extra.get("active_music_source"),
        core.get("music_source"),
    )
    if not source_type and pick_key.startswith("custom::"):
        source_type = "custom_progression"
    if not source_type and pick_key:
        source_type = "catalog"

    identity: dict[str, Any] = {
        "pick_key": pick_key,
        "title": title,
        "artist": artist,
        "genre": genre,
        "original_key": original_key,
        "source_type": source_type,
        "display_key": _first_str(
            ws_active.get("display_key"),
            meta.get("display_key"),
            core.get("display_key"),
        ),
        "instrument": _first_str(
            ws_active.get("instrument"),
            meta.get("instrument"),
            core.get("instrument"),
        ),
    }
    return {k: v for k, v in identity.items() if v not in ("", None)}


def workspace_envelope_expects_catalog_song(payload: dict[str, Any]) -> bool:
    """True when saved workspace clearly intended a catalog song (not empty cold start)."""
    if not isinstance(payload, dict) or not payload:
        return False
    identity = extract_canonical_active_song_identity(payload)
    pk = str(identity.get("pick_key") or "").strip()
    if pk.startswith("custom::"):
        return False
    if pk and not pk.startswith("custom::"):
        return True
    source = str(identity.get("source_type") or "").strip()
    if source == "custom_progression":
        return False
    if identity.get("title") and source != "custom_progression":
        return True
    return False


def should_defer_default_master_song_init(session: dict[str, Any]) -> bool:
    """Avoid pinning the first catalog song while a saved workspace song is not yet applied."""
    if _session_pick_key(session):
        return False
    payload = session.get("_suite_last_cloud_fetch_payload")
    if not isinstance(payload, dict) or not payload:
        return False
    ident = inspect_workspace_envelope_identity(payload)
    expects_song = bool(
        ident.get("workspace_has_active_song_pick_key") or ident.get("workspace_has_core_pick_key")
    )
    if not expects_song:
        expects_song = workspace_envelope_expects_catalog_song(payload)
    if expects_song:
        session[ACTIVE_SONG_RESTORE_INCOMPLETE_KEY] = True
        return True
    return False


def _record_pick_key_checkpoint(
    session: dict[str, Any],
    diag: dict[str, Any],
    *,
    stage: str,
) -> None:
    pk = _session_pick_key(session)
    before = str(diag.get("_last_pick_key_checkpoint") or "").strip()
    if before and not pk:
        diag["pick_key_cleared_by_stage"] = stage
    diag["_last_pick_key_checkpoint"] = pk or ""
    if stage == "before_apply":
        diag["pick_key_present_before_apply"] = bool(pk)
    elif stage == "after_apply":
        diag["pick_key_present_after_apply"] = bool(pk)


def migrate_legacy_active_song_pick_key(
    session: dict[str, Any],
    payload: dict[str, Any],
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
) -> tuple[str, str]:
    """One-time pick_key recovery from title/genre metadata. Returns (pick_key, result)."""
    from songs.state import _recover_pick_key_by_title

    identity = extract_canonical_active_song_identity(payload)
    if str(identity.get("pick_key") or "").strip():
        return str(identity["pick_key"]).strip(), "already_had_pick_key"

    title = str(identity.get("title") or "").strip()
    artist = str(identity.get("artist") or "").strip()
    genre = str(identity.get("genre") or "").strip()

    if title and genre:
        label_matches: list[str] = []
        try:
            from song_catalog.catalog import format_pick_key

            labels = song_picker_catalog.get(genre) or {}
            for lab, data in labels.items():
                if str(data.get("title") or "").strip() == title:
                    if not artist or str(data.get("artist") or "") == artist:
                        label_matches.append(format_pick_key(genre, lab))
        except ImportError:
            pass
        if len(label_matches) == 1:
            return label_matches[0], "migrated_title_genre_unique"
        if len(label_matches) > 1:
            return "", "ambiguous_title_in_genre"

    if title:
        recovered = _recover_pick_key_by_title(
            {"title": title, "artist": artist},
            song_picker_catalog,
        )
        if recovered:
            return recovered, "migrated_title_unique"
        return "", "ambiguous_or_missing_title_match"

    return "", "no_migration_candidates"


def apply_canonical_active_song_from_workspace(
    st: Any,
    payload: dict[str, Any],
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]] | None,
    allow_migration: bool = True,
    persist_migration: bool = True,
) -> bool:
    """Stamp catalog pick_key and load canonical record from workspace envelope."""
    ss = st.session_state
    diag = ss.get(ACTIVE_SONG_WORKSPACE_DIAG_KEY)
    if not isinstance(diag, dict):
        diag = {}
    diag.update(inspect_workspace_envelope_identity(payload))
    _record_pick_key_checkpoint(ss, diag, stage="before_apply")

    identity = extract_canonical_active_song_identity(payload)
    pick_key = str(identity.get("pick_key") or "").strip()
    migration_result = "not_needed"

    if not pick_key and allow_migration and workspace_envelope_expects_catalog_song(payload):
        diag["active_song_migration_attempted"] = True
        pick_key, migration_result = migrate_legacy_active_song_pick_key(
            ss,
            payload,
            song_picker_catalog=song_picker_catalog,
        )
        if pick_key:
            identity = {**identity, "pick_key": pick_key}
    else:
        diag["active_song_migration_attempted"] = bool(
            not str(extract_canonical_active_song_identity(payload).get("pick_key") or "").strip()
            and workspace_envelope_expects_catalog_song(payload)
        )

    diag["active_song_migration_result"] = migration_result
    ss[ACTIVE_SONG_WORKSPACE_DIAG_KEY] = diag

    if not pick_key or pick_key.startswith("custom::"):
        _record_pick_key_checkpoint(ss, diag, stage="after_apply")
        ss[ACTIVE_SONG_WORKSPACE_DIAG_KEY] = diag
        return False

    try:
        from active_song_state import write_canonical_active_song_state

        sel: dict[str, Any] = {}
        if identity.get("title"):
            sel["title"] = identity["title"]
        if identity.get("artist"):
            sel["artist"] = identity["artist"]
        if identity.get("genre"):
            sel["genre"] = identity["genre"]
        if identity.get("original_key"):
            sel["key"] = identity["original_key"]
        sel["pick_key"] = pick_key
        ctx = {
            "pick_key": pick_key,
            "music_source": "catalog",
            "selected_song": sel,
        }
        for key in ("display_key", "instrument", "level", "focus"):
            if identity.get(key):
                ctx[key] = identity[key]
        try:
            from music_restore_phase import should_project_global_controls_from_canonical

            apply_globals = should_project_global_controls_from_canonical(ss)
        except ImportError:
            apply_globals = True
        write_canonical_active_song_state(
            ss,
            ctx,
            reason="workspace_envelope_identity",
            apply_global_controls_to_session=apply_globals,
        )
        if apply_globals:
            try:
                from music_restore_phase import mark_global_controls_restore_projection_complete

                mark_global_controls_restore_projection_complete(ss)
            except ImportError:
                pass
    except ImportError:
        pass

    try:
        from songs.state import apply_pick_key, resolve_pick_key

        target = resolve_pick_key(pick_key, song_picker_catalog=song_picker_catalog) or pick_key
        apply_pick_key(
            st,
            target,
            song_picker_catalog,
            song_library=song_library,
            skip_activity_log=True,
            origin="restore",
            persist=False,
        )
    except Exception:
        _record_pick_key_checkpoint(ss, diag, stage="after_apply")
        ss[ACTIVE_SONG_WORKSPACE_DIAG_KEY] = diag
        return False

    if migration_result.startswith("migrated") and persist_migration:
        try:
            from music_persistent_state import force_save_music_state

            force_save_music_state(st, reason="startup_migration")
            diag["active_song_migration_persisted"] = True
        except ImportError:
            pass

    _record_pick_key_checkpoint(ss, diag, stage="after_apply")
    ss[ACTIVE_SONG_WORKSPACE_DIAG_KEY] = diag
    ss.pop(ACTIVE_SONG_RESTORE_INCOMPLETE_KEY, None)
    ss.pop(CHOOSE_SONG_RESTORE_STATE_KEY, None)
    return True


def merge_active_song_workspace_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    """Diagnostics fields for chart bundle / dev sidebar."""
    payload = session.get("_suite_last_cloud_fetch_payload")
    base = inspect_workspace_envelope_identity(payload if isinstance(payload, dict) else {})
    hydrated = bool(session.get("_music_workspace_blob_hydrated"))
    base["workspace_inspection_authoritative"] = hydrated
    if not hydrated:
        base["workspace_expects_catalog_song"] = None
    else:
        base["workspace_expects_catalog_song"] = workspace_envelope_expects_catalog_song(
            payload if isinstance(payload, dict) else {}
        )
    extra = session.get(ACTIVE_SONG_WORKSPACE_DIAG_KEY)
    if isinstance(extra, dict):
        base.update(
            {
                k: extra.get(k)
                for k in (
                    "pick_key_present_before_apply",
                    "pick_key_present_after_apply",
                    "pick_key_cleared_by_stage",
                    "active_song_migration_attempted",
                    "active_song_migration_result",
                    "active_song_migration_persisted",
                )
                if k in extra
            }
        )
    base["active_song_restore_incomplete"] = bool(session.get(ACTIVE_SONG_RESTORE_INCOMPLETE_KEY))
    try:
        from music_workspace_hydration import collect_workspace_hydration_diagnostics

        base.update(collect_workspace_hydration_diagnostics(session))
    except ImportError:
        pass
    return base


def should_block_chart_recovery_no_pick_key(session: dict[str, Any]) -> bool:
    """Block chart recovery while workspace hydration is unknown or pick_key missing after hydrate."""
    try:
        from music_workspace_hydration import can_finalize_music_restore, workspace_blob_hydrated

        if not can_finalize_music_restore(session):
            return True
        if not workspace_blob_hydrated(session):
            return False
    except ImportError:
        if not session.get("_music_workspace_blob_hydrated"):
            return True
    payload = session.get("_suite_last_cloud_fetch_payload")
    if not isinstance(payload, dict) or not workspace_envelope_expects_catalog_song(payload):
        return False
    try:
        from songs.state import reconcile_active_pick_key

        pk = reconcile_active_pick_key(session, song_picker_catalog=None)
    except ImportError:
        pk = _session_pick_key(session)
    return not str(pk or "").strip()

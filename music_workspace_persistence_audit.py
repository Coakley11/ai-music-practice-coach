"""Dev-only workspace persistence audit — saved vs applied vs final."""

from __future__ import annotations

from typing import Any

from music_persistent_state import APP_ID


def _saved_from_envelope(session: dict[str, Any], *paths: str) -> Any:
    payload = session.get("_suite_last_cloud_fetch_payload")
    if not isinstance(payload, dict):
        return None
    cur: Any = payload
    for part in paths:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _triple_when_authoritative(
    saved: Any,
    applied: Any,
    final: Any,
    *,
    authoritative: bool,
) -> dict[str, Any]:
    block = _triple(saved, applied if authoritative else "(pending)", final)
    if not authoritative:
        block["mismatch"] = False
        block["hydration_pending"] = True
    return block


def _triple(
    saved: Any,
    applied: Any,
    final: Any,
) -> dict[str, Any]:
    saved_s = str(saved or "").strip() if saved is not None else ""
    applied_s = str(applied or "").strip() if applied is not None else ""
    final_s = str(final or "").strip() if final is not None else ""
    mismatch = saved_s and final_s and saved_s != final_s
    return {
        "saved": saved or "(none)",
        "applied": applied or "(none)",
        "final": final or "(none)",
        "mismatch": bool(mismatch),
    }


def collect_workspace_persistence_audit(session: dict[str, Any]) -> dict[str, Any]:
    """Safe diagnostics for ?dev=1 — no secrets."""
    try:
        from music_workspace_hydration import (
            can_finalize_music_restore,
            collect_workspace_hydration_diagnostics,
            workspace_blob_hydrated,
            workspace_empty_confirmed,
        )

        hydration = collect_workspace_hydration_diagnostics(session)
    except ImportError:
        hydration = {}
        can_finalize_music_restore = lambda _s: bool(session.get("_music_workspace_blob_hydrated"))  # noqa: E731

    try:
        from music_restore_phase import music_restore_phase_complete

        restore_complete = music_restore_phase_complete(session)
    except ImportError:
        restore_complete = bool(session.get("_music_restore_phase_complete"))

    core = _saved_from_envelope(session, "core") or {}
    ws_meta = _saved_from_envelope(session, "music_workspace_state") or {}
    if not isinstance(core, dict):
        core = {}
    if not isinstance(ws_meta, dict):
        ws_meta = {}

    saved_page = (
        str(ws_meta.get("studio_page") or core.get("studio_page") or core.get("page") or "").strip()
    )
    restore_trace = session.get("_music_workspace_restore_trace")
    if not isinstance(restore_trace, dict):
        restore_trace = {}
    applied_page = str(
        restore_trace.get("studio_page_applied")
        or session.get("_suite_page_overwrite_source")
        or ""
    ).strip()
    final_page = str(session.get("studio_page") or "").strip()

    saved_pk = str(core.get("pick_key") or "").strip()
    active_song_meta = ws_meta.get("active_song")
    if not saved_pk and isinstance(active_song_meta, dict):
        saved_pk = str(active_song_meta.get("pick_key") or "").strip()
    saved_title = str(
        (active_song_meta or {}).get("title")
        if isinstance(active_song_meta, dict)
        else core.get("song")
        or ""
    ).strip()
    if not saved_title:
        sel = _saved_from_envelope(session, "session", "selected_song")
        if isinstance(sel, dict):
            saved_title = str(sel.get("title") or "").strip()

    applied_pk = str(restore_trace.get("pick_key_applied") or session.get("_music_active_pick_key_reconciled") or "").strip()

    try:
        from songs.state import reconcile_active_pick_key

        final_pk = reconcile_active_pick_key(session, song_picker_catalog=None)
    except ImportError:
        final_pk = str(session.get("active_catalog_pick_key") or "").strip()

    final_title = ""
    try:
        from songs.state import SELECTED_SONG_STATE_KEY

        sel_live = session.get(SELECTED_SONG_STATE_KEY)
        if isinstance(sel_live, dict):
            final_title = str(sel_live.get("title") or "").strip()
    except ImportError:
        pass

    saved_section = str(
        core.get("practice_focus_section")
        or _saved_from_envelope(session, "session", "practice_focus_section")
        or ""
    ).strip()
    applied_section = str(restore_trace.get("practice_section_applied") or "").strip()
    final_section = str(session.get("practice_focus_section") or "").strip()

    saved_instrument = str(core.get("instrument") or "").strip()
    applied_instrument = str(restore_trace.get("instrument_applied") or "").strip()
    try:
        from practice_setup_globals import get_active_instrument

        final_instrument = str(get_active_instrument(session) or session.get("instrument") or "").strip()
    except ImportError:
        final_instrument = str(session.get("instrument") or "").strip()

    saved_level = str(core.get("level") or "").strip()
    applied_level = str(restore_trace.get("level_applied") or "").strip()
    final_level = str(session.get("level") or "").strip()

    saved_focus = str(core.get("focus") or "").strip()
    applied_focus = str(restore_trace.get("focus_applied") or "").strip()
    final_focus = str(session.get("focus") or "").strip()

    family_saved = _saved_from_envelope(session, "session", "fixed_practice_key_family_id")
    family_applied = restore_trace.get("key_family_applied") or session.get("fixed_practice_key_family_id")
    family_final = session.get("fixed_practice_key_family_id")

    fixed_mode_saved = _saved_from_envelope(session, "session", "practice_key_mode")
    fixed_mode_applied = restore_trace.get("practice_key_mode_applied")
    fixed_mode_final = session.get("practice_key_mode")

    concert_saved = _saved_from_envelope(session, "session", "concert_key") or core.get("concert_key")
    concert_final = session.get("concert_key") or session.get("original_key")

    practice_key_saved = _saved_from_envelope(session, "session", "practice_key") or core.get("practice_key")
    practice_key_final = session.get("practice_key") or session.get("display_key")

    display_saved = str(core.get("display_key") or "").strip()
    display_applied = str(restore_trace.get("display_key_applied") or "").strip()
    display_final = str(session.get("display_key") or "").strip()

    audit_authoritative = bool(session.get("_music_workspace_blob_hydrated"))
    creative_mode_saved = _saved_from_envelope(session, "session", "creative_lab_analysis_mode")
    creative_mode_final = session.get("creative_lab_analysis_mode")

    mission_saved = _saved_from_envelope(session, "session", "improv_active_mission")
    mission_final = session.get("improv_active_mission")

    motif_saved = _saved_from_envelope(session, "session", "improv_motif")
    motif_final = session.get("improv_motif")
    motif_hash_saved = ""
    motif_hash_final = ""
    if isinstance(motif_saved, dict) and motif_saved.get("notes"):
        motif_hash_saved = str(hash(tuple(motif_saved.get("notes") or [])))
    if isinstance(motif_final, dict) and motif_final.get("notes"):
        motif_hash_final = str(hash(tuple(motif_final.get("notes") or [])))

    capo_saved = _saved_from_envelope(session, "session", "guitar_capo_enabled")
    capo_final = session.get("guitar_capo_enabled")
    shape_saved = _saved_from_envelope(session, "session", "guitar_capo_shape_key")
    shape_final = session.get("guitar_capo_shape_key")

    practice_tool_saved = None
    practice_audit: dict[str, Any] = {}
    try:
        from practice_workspace_persistence import collect_practice_workspace_audit

        payload = session.get("_suite_last_cloud_fetch_payload")
        practice_audit = collect_practice_workspace_audit(
            session,
            payload if isinstance(payload, dict) else None,
        )
        practice_tool_saved = practice_audit.get("practice_tool_saved")
    except ImportError:
        snaps = _saved_from_envelope(session, "session", "_studio_page_snapshots")
        if isinstance(snaps, dict) and isinstance(snaps.get("practice"), dict):
            practice_tool_saved = snaps["practice"].get("practice_active_tool")
    practice_tool_final = session.get("practice_active_tool")

    resolved_session_key = ""
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_session_key_from_family

        if is_fixed_practice_key_mode(session):
            from music_theory import key_mode

            orig = str(session.get("concert_key") or session.get("original_key") or "C")
            resolved_session_key = resolve_session_key_from_family(
                str(session.get("fixed_practice_key_family_id") or ""),
                key_mode(orig),
            )
    except ImportError:
        pass

    workspace_id = ""
    account_hint = ""
    try:
        from music_persistent_state import _active_workspace_id

        workspace_id = _active_workspace_id(type("St", (), {"session_state": session})())
    except Exception:
        workspace_id = str(session.get("_suite_persist_app_id") or APP_ID)
    account_hint = str(session.get("_suite_cloud_user_hint") or session.get("user_email") or "(unknown)")

    autosave_blocked = bool(session.get("_suite_autosave_block_reason"))
    return {
        "app_id": APP_ID,
        "account_hint": account_hint,
        "workspace_id": workspace_id,
        "cloud_fetch_updated_at": session.get("_suite_cloud_fetch_updated_at"),
        "applied_cloud_ts": session.get("_suite_applied_cloud_ts_music") or session.get("_suite_persist_debug_cloud_ts"),
        "last_save_at": session.get("_suite_persist_last_save_at"),
        "last_hydrate_at": session.get("_music_workspace_hydration_attempted"),
        "last_save_source": session.get("_suite_persist_last_save_source"),
        "device_session": session.get("_music_device_id"),
        "restore_complete": restore_complete,
        "can_finalize_restore": can_finalize_music_restore(session) if hydration else bool(session.get("_music_workspace_blob_hydrated")),
        "workspace_blob_hydrated": bool(session.get("_music_workspace_blob_hydrated")),
        "workspace_empty_confirmed": bool(session.get("_music_workspace_empty_confirmed")),
        "autosave_enabled": not autosave_blocked,
        "autosave_block_reason": session.get("_suite_autosave_block_reason"),
        "local_dirty_flags": {
            "active_song": bool(session.get("_active_song_local_dirty")),
            "practice": bool(session.get("_practice_local_dirty")),
            "studio_nav": bool(session.get("_studio_nav_local_dirty")),
            "mission": bool(session.get("_mission_workspace_local_dirty")),
        },
        "last_save_reason": session.get("_music_build_save_reason"),
        "last_save_skipped_reason": session.get("_suite_persist_restore_skip_reason"),
        "last_persistence_error": session.get("_music_commit_error") or session.get("_music_restore_error"),
        "newer_cloud_ignored": session.get("_suite_workspace_sync_skipped_no_apply"),
        "hydration": hydration,
        **practice_audit,
        "audit_authoritative": audit_authoritative,
        "studio_page_saved": saved_page or "(none)",
        "studio_page_applied": applied_page or "(none)",
        "studio_page_final": final_page or "(none)",
        "active_pick_saved": saved_pk or "(none)",
        "active_pick_applied": applied_pk or "(none)",
        "active_pick_final": final_pk or "(none)",
        "song_title_saved": saved_title or "(none)",
        "song_title_final": final_title or "(none)",
        "selected_section_saved": saved_section or "(none)",
        "selected_section_applied": applied_section or "(none)",
        "selected_section_final": final_section or "(none)",
        "instrument_saved": saved_instrument or "(none)",
        "instrument_applied": applied_instrument or "(none)",
        "instrument_final": final_instrument or "(none)",
        "level_saved": saved_level or "(none)",
        "level_applied": applied_level or "(none)",
        "level_final": final_level or "(none)",
        "focus_saved": saved_focus or "(none)",
        "focus_applied": applied_focus or "(none)",
        "focus_final": final_focus or "(none)",
        "practice_section_saved": saved_section or "(none)",
        "practice_section_applied": applied_section or "(none)",
        "practice_section_final": final_section or "(none)",
        "key_family_saved": family_saved or "(none)",
        "key_family_applied": family_applied or "(none)",
        "key_family_final": family_final or "(none)",
        "fixed_key_saved": fixed_mode_saved or "(none)",
        "fixed_key_applied": fixed_mode_applied or "(none)",
        "fixed_key_final": fixed_mode_final or "(none)",
        "concert_key_saved": concert_saved or "(none)",
        "concert_key_final": concert_final or "(none)",
        "practice_key_saved": practice_key_saved or "(none)",
        "practice_key_final": practice_key_final or "(none)",
        "display_key_saved": display_saved or "(none)",
        "display_key_applied": display_applied or "(none)",
        "display_key_final": display_final or "(none)",
        "active_page": _triple_when_authoritative(saved_page, applied_page, final_page, authoritative=audit_authoritative),
        "active_song_pick_key": _triple_when_authoritative(saved_pk, applied_pk, final_pk, authoritative=audit_authoritative),
        "song_title": _triple_when_authoritative(saved_title, applied_pk and saved_title, final_title, authoritative=audit_authoritative),
        "selected_section": _triple_when_authoritative(saved_section, applied_section, final_section, authoritative=audit_authoritative),
        "instrument": _triple_when_authoritative(saved_instrument, applied_instrument, final_instrument, authoritative=audit_authoritative),
        "level": _triple_when_authoritative(saved_level, applied_level, final_level, authoritative=audit_authoritative),
        "focus": _triple_when_authoritative(saved_focus, applied_focus, final_focus, authoritative=audit_authoritative),
        "creative_mode": _triple(creative_mode_saved, "(session_extra)", creative_mode_final),
        "mission_id": _triple(
            mission_saved if isinstance(mission_saved, str) else (mission_saved or {}).get("id") if isinstance(mission_saved, dict) else mission_saved,
            "(session_extra)",
            mission_final if isinstance(mission_final, str) else (mission_final or {}).get("id") if isinstance(mission_final, dict) else mission_final,
        ),
        "active_motif_hash": _triple(motif_hash_saved or "(none)", "(session_extra)", motif_hash_final or "(none)"),
        "key_family": _triple_when_authoritative(family_saved, family_applied, family_final, authoritative=audit_authoritative),
        "fixed_practice_key_mode": _triple_when_authoritative(
            fixed_mode_saved, fixed_mode_applied, fixed_mode_final, authoritative=audit_authoritative
        ),
        "display_key": _triple_when_authoritative(display_saved, display_applied, display_final, authoritative=audit_authoritative),
        "resolved_session_key": resolved_session_key or "(n/a)",
        "capo_mode": _triple(capo_saved, "(session_extra)", capo_final),
        "shape_key": _triple(shape_saved, "(session_extra)", shape_final),
        "practice_tool": _triple(practice_tool_saved, practice_audit.get("practice_tool_applied"), practice_tool_final),
        "overwrite_stages": {
            "skip_master_song_init": session.get("_music_skip_master_song_init_reason"),
            "active_song_restore_skipped": session.get("_active_song_restore_skipped_reason"),
            "practice_restore_skipped": session.get("_practice_restore_skipped_reason"),
            "creative_restore_skipped": session.get("_creative_restore_skipped_reason"),
            "studio_nav_restore_skipped": session.get("_studio_nav_restore_skipped_reason"),
            "page_overwrite_source": session.get("_suite_page_overwrite_source"),
            "restore_trace": session.get("_music_workspace_restore_trace"),
        },
    }


def render_workspace_persistence_audit_sidebar(st_module: Any) -> None:
    audit = collect_workspace_persistence_audit(st_module.session_state)
    with st_module.sidebar.expander("Workspace persistence audit", expanded=False):
        st_module.caption("saved → applied → final (mismatch flagged)")
        for key in (
            "app_id",
            "account_hint",
            "workspace_id",
            "cloud_fetch_updated_at",
            "applied_cloud_ts",
            "last_save_at",
            "restore_complete",
            "can_finalize_restore",
            "autosave_enabled",
            "autosave_block_reason",
            "resolved_session_key",
            "last_save_reason",
            "last_save_skipped_reason",
            "last_persistence_error",
        ):
            st_module.text(f"{key}: {audit.get(key)!r}")
        for block_key in (
            "active_page",
            "active_song_pick_key",
            "song_title",
            "selected_section",
            "instrument",
            "level",
            "focus",
            "key_family",
            "fixed_practice_key_mode",
            "display_key",
            "creative_mode",
            "mission_id",
            "active_motif_hash",
            "capo_mode",
            "shape_key",
            "practice_tool",
        ):
            block = audit.get(block_key)
            if isinstance(block, dict):
                flag = " ⚠" if block.get("mismatch") else ""
                st_module.text(
                    f"{block_key}{flag}: saved={block.get('saved')} → "
                    f"applied={block.get('applied')} → final={block.get('final')}"
                )
        st_module.markdown("**Practice workspace**")
        for pk, pv in sorted(audit.items()):
            if pk.startswith("practice_") and pk != "practice_tool":
                st_module.text(f"{pk}: {pv!r}")
        try:
            from workspace_revision import collect_workspace_revision_diagnostics

            st_module.markdown("**Workspace revision / sync**")
            for rk, rv in collect_workspace_revision_diagnostics(st_module.session_state).items():
                st_module.text(f"{rk}: {rv!r}")
        except ImportError:
            pass
        st_module.markdown("**Overwrite stages**")
        stages = audit.get("overwrite_stages") or {}
        if isinstance(stages, dict):
            for sk, sv in stages.items():
                if sv:
                    st_module.text(f"{sk}: {sv!r}")
        dirty = audit.get("local_dirty_flags") or {}
        if isinstance(dirty, dict) and any(dirty.values()):
            st_module.text(f"local_dirty_flags: {dirty!r}")

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
    applied_page = str(session.get("_suite_page_overwrite_source") or "").strip()
    final_page = str(session.get("studio_page") or "").strip()

    saved_pk = str(core.get("pick_key") or "").strip()
    active_song_meta = ws_meta.get("active_song")
    if not saved_pk and isinstance(active_song_meta, dict):
        saved_pk = str(active_song_meta.get("pick_key") or "").strip()

    try:
        from songs.state import reconcile_active_pick_key

        final_pk = reconcile_active_pick_key(session, song_picker_catalog=None)
    except ImportError:
        final_pk = str(session.get("active_catalog_pick_key") or "").strip()

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

    family_saved = _saved_from_envelope(session, "session", "fixed_practice_key_family_id")
    family_final = session.get("fixed_practice_key_family_id")

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
        "active_page": _triple(saved_page, applied_page or "(source)", final_page),
        "active_song_pick_key": _triple(saved_pk, session.get("_music_active_pick_key_reconciled"), final_pk),
        "creative_mode": _triple(creative_mode_saved, "(session_extra)", creative_mode_final),
        "mission_id": _triple(
            mission_saved if isinstance(mission_saved, str) else (mission_saved or {}).get("id") if isinstance(mission_saved, dict) else mission_saved,
            "(session_extra)",
            mission_final if isinstance(mission_final, str) else (mission_final or {}).get("id") if isinstance(mission_final, dict) else mission_final,
        ),
        "active_motif_hash": _triple(motif_hash_saved or "(none)", "(session_extra)", motif_hash_final or "(none)"),
        "key_family": _triple(family_saved, "(session_extra)", family_final),
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
            "creative_mode",
            "mission_id",
            "active_motif_hash",
            "key_family",
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
        st_module.markdown("**Overwrite stages**")
        stages = audit.get("overwrite_stages") or {}
        if isinstance(stages, dict):
            for sk, sv in stages.items():
                if sv:
                    st_module.text(f"{sk}: {sv!r}")
        dirty = audit.get("local_dirty_flags") or {}
        if isinstance(dirty, dict) and any(dirty.values()):
            st_module.text(f"local_dirty_flags: {dirty!r}")

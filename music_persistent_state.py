"""Disk persistence for the Music Practice Coach app."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from songs.state import (
    ACTIVE_CATALOG_PICK_KEY,
    SELECTED_SONG_STATE_KEY,
    SUITE_LOCAL_STATE_RESTORED_KEY,
    apply_saved_music_context,
    build_music_local_state,
    restore_saved_app_state_once,
)
from suite_user_persistence import (
    autosave_if_changed,
    clear_workspace_autosave_block,
    finalize_suite_reset,
    force_autosave,
    load_user_state,
    reset_user_state,
    restore_once,
    save_user_state,
    sync_workspace_protocol,
)

APP_ID = "music"
WORKSPACE_SCHEMA_VERSION = 1
MUSIC_STARTUP_RESTORE_DIAG_KEY = "_music_startup_restore_diag"


def _payload_has_custom_active_signals(payload: dict[str, Any]) -> bool:
    """True when cloud/disk blob indicates custom progression is the active song."""
    if not isinstance(payload, dict):
        return False
    try:
        from songs.music_source import SOURCE_CUSTOM
    except ImportError:
        SOURCE_CUSTOM = "custom_progression"  # type: ignore[misc]

    core = payload.get("core") if isinstance(payload.get("core"), dict) else {}
    core_pk = str(core.get("pick_key") or "").strip()
    if core_pk.startswith("custom::"):
        return True

    meta = payload.get("active_song_state")
    if isinstance(meta, dict) and str(meta.get("music_source") or "") == SOURCE_CUSTOM:
        return True
    if isinstance(meta, dict) and str(meta.get("pick_key") or "").strip().startswith("custom::"):
        return True

    session_extra = payload.get("session") if isinstance(payload.get("session"), dict) else {}
    if str(session_extra.get("active_music_source") or "") == SOURCE_CUSTOM:
        cpl = session_extra.get("cpl_active_progression")
        if isinstance(cpl, dict) and str(cpl.get("name") or cpl.get("id") or "").strip():
            return True
    return False


def _session_has_restored_song_context(session_state: dict[str, Any]) -> bool:
    """True when session has a real active song (not ephemeral cold-start default)."""
    if session_state.get("_music_default_song_ephemeral"):
        return False
    sel = session_state.get(SELECTED_SONG_STATE_KEY)
    if isinstance(sel, dict) and str(sel.get("pick_key") or "").strip():
        return True
    if str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip():
        return True
    if str(session_state.get("active_music_source") or "") == "custom_progression":
        return True
    return False


def clear_music_ephemeral_default_song(session_state: dict[str, Any]) -> None:
    """Allow persistence after user promotes a real song (not cold-start default)."""
    session_state.pop("_music_default_song_ephemeral", None)
    session_state.pop("_music_default_init_this_run", None)


def _reapply_core_practice_globals_from_payload(
    session_state: dict[str, Any],
    core: dict[str, Any],
) -> None:
    """Core musician globals from the workspace blob win over catalog/cloud side effects."""
    if not isinstance(core, dict) or not core:
        return
    try:
        from practice_setup_globals import (
            get_active_instrument,
            set_active_focus,
            set_active_instrument,
            set_active_level,
            valid_focus_for,
        )
    except ImportError:
        return
    inst = str(core.get("instrument") or "").strip()
    if inst:
        set_active_instrument(session_state, inst)
    lvl = str(core.get("level") or "").strip()
    if lvl:
        set_active_level(session_state, lvl)
    foc = str(core.get("focus") or "").strip()
    if foc:
        set_active_focus(
            session_state,
            valid_focus_for(get_active_instrument(session_state), foc),
        )
    section = str(core.get("practice_focus_section") or "").strip()
    if section:
        session_state["practice_focus_section"] = section
    display_key = str(core.get("display_key") or "").strip()
    if display_key:
        try:
            from songs.key_state import PENDING_DISPLAY_KEY

            session_state[PENDING_DISPLAY_KEY] = display_key
        except ImportError:
            pass


def music_skip_master_song_init_reason(session_state: dict[str, Any]) -> str:
    """Human-readable reason when trusted-core default init must be skipped."""
    if session_state.get(SUITE_LOCAL_STATE_RESTORED_KEY):
        return "suite_local_state_restored"
    if session_state.get("_music_restore_error"):
        return "music_restore_error"
    if session_state.get("_suite_persist_restore_applied"):
        return "suite_persist_restore_applied"
    if session_state.get("_suite_cloud_workspace_applied"):
        return "suite_cloud_workspace_applied"
    if session_state.get("_music_workspace_blob_hydrated") and _session_has_restored_song_context(session_state):
        return "music_workspace_song_restored"

    sel = session_state.get(SELECTED_SONG_STATE_KEY)
    if isinstance(sel, dict) and str(sel.get("pick_key") or "").strip():
        if not session_state.get("_music_default_song_ephemeral"):
            return "selected_song_pick_key"
    if str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip():
        if not session_state.get("_music_default_song_ephemeral"):
            return "active_catalog_pick_key"
    if str(session_state.get("active_music_source") or "").strip() == "custom_progression":
        return "active_music_source_custom"

    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY

        blob = session_state.get(ACTIVE_SONG_STATE_KEY)
        if isinstance(blob, dict):
            if str(blob.get("pick_key") or blob.get("active_catalog_pick_key") or "").strip():
                return "active_song_state_pick_key"
            if str(blob.get("music_source") or "") == "custom_progression":
                return "active_song_state_custom"
            if str(blob.get("custom_progression_name") or "").strip():
                return "active_song_state_custom_name"
    except ImportError:
        pass

    if session_state.get("cpl_saved_progressions") or session_state.get("cpl_active_progression"):
        return "cpl_library_present"

    ws = session_state.get("music_workspace_state")
    if isinstance(ws, dict) and str(ws.get("studio_page") or ws.get("page") or "").strip():
        return "music_workspace_state_page"

    payload = session_state.get("_suite_last_cloud_fetch_payload")
    if isinstance(payload, dict) and payload:
        if _payload_has_custom_active_signals(payload):
            return "cloud_payload_custom_active"
        core = payload.get("core") if isinstance(payload.get("core"), dict) else {}
        extra = payload.get("session") if isinstance(payload.get("session"), dict) else {}
        cloud_pk = str(core.get("pick_key") or core.get("active_catalog_pick_key") or "").strip()
        if cloud_pk and not session_state.get("_music_default_song_ephemeral"):
            return "cloud_payload_pick_key"
        if str(extra.get("active_music_source") or "") == "custom_progression":
            return "cloud_payload_custom_source"
        if extra.get("cpl_saved_progressions") or extra.get("cpl_active_progression"):
            return "cloud_payload_cpl"
        blob_page = str(extra.get("studio_page") or "").strip()
        if not blob_page:
            meta = payload.get("music_workspace_state")
            if isinstance(meta, dict):
                blob_page = str(meta.get("studio_page") or "").strip()
        if blob_page:
            return "cloud_payload_studio_page"

    return ""


def run_post_nav_music_startup_init(
    st: Any,
    *,
    song_picker_catalog: dict,
    song_library: dict | None,
    default_song_records: list | None = None,
) -> bool:
    """Trusted-core default + startup diag after AMI hydrate and second workspace sync."""
    from songs.state import ensure_master_song_initialized

    ss = st.session_state

    payload = ss.get("_suite_last_cloud_fetch_payload")
    if isinstance(payload, dict) and payload:
        try:
            _finalize_music_workspace_restore(
                st,
                payload,
                song_picker_catalog=song_picker_catalog,
                song_library=song_library,
            )
        except Exception:
            pass

    skip = music_should_skip_master_song_init(ss)
    try:
        from music_restore_phase import workspace_is_truly_empty

        if not skip and not workspace_is_truly_empty(ss):
            skip = True
            ss["_music_skip_master_song_init_reason"] = "workspace_not_truly_empty"
    except ImportError:
        pass

    if not skip and default_song_records:
        ensure_master_song_initialized(
            st,
            all_records=default_song_records,
            song_library=song_library,
            song_picker_catalog=song_picker_catalog,
            origin="default",
        )
        ss["_music_default_init_this_run"] = True
        try:
            from music_persistence_trace import update_trace

            update_trace(st, trusted_core_init_ran=True, default_init_called=True)
        except Exception:
            pass
    else:
        try:
            from music_persistence_trace import update_trace

            update_trace(st, trusted_core_init_ran=False, default_init_called=False)
        except Exception:
            pass

    if isinstance(payload, dict) and payload:
        diag = ss.get(MUSIC_STARTUP_RESTORE_DIAG_KEY)
        if not isinstance(diag, dict):
            _record_music_startup_restore_diag(
                ss,
                payload,
                restored_studio_page=str(ss.get("studio_page") or ""),
                blob_studio_page=str(ss.get("studio_page") or ""),
                default_init_called=bool(ss.get("_music_default_init_this_run")),
            )
        else:
            diag["default_init_called"] = bool(ss.get("_music_default_init_this_run"))
            diag["skip_master_song_init_reason"] = ss.get("_music_skip_master_song_init_reason")
        try:
            from music_persistence_trace import update_trace

            update_trace(st, **(ss.get(MUSIC_STARTUP_RESTORE_DIAG_KEY) or {}))
        except Exception:
            pass
    return skip


def finalize_music_startup_restore(
    st: Any,
    *,
    song_picker_catalog: dict,
    song_library: dict | None,
) -> None:
    """Finish startup restore: page snapshot, active pick key, then restore-phase gate."""
    ss = st.session_state
    try:
        from music_restore_phase import (
            MUSIC_STARTUP_RESTORE_FINALIZED_KEY,
            complete_music_restore_phase,
            music_restore_phase_complete,
        )
    except ImportError:
        complete_music_restore_phase = None  # type: ignore[assignment,misc]
        music_restore_phase_complete = lambda _s: False  # type: ignore[assignment,misc]
        MUSIC_STARTUP_RESTORE_FINALIZED_KEY = "_music_startup_restore_finalized"  # type: ignore[misc]

    if ss.get(MUSIC_STARTUP_RESTORE_FINALIZED_KEY):
        return

    try:
        from music_workspace_hydration import can_finalize_music_restore

        if not can_finalize_music_restore(ss):
            return
    except ImportError:
        if not ss.get("_music_workspace_blob_hydrated") and not ss.get(
            "_music_workspace_empty_confirmed"
        ):
            return

    try:
        from studio_page_persistence import restore_current_page_snapshot_if_needed

        restore_current_page_snapshot_if_needed(ss)
    except ImportError:
        pass

    payload = ss.get("_suite_last_cloud_fetch_payload")
    if isinstance(payload, dict) and payload:
        try:
            from active_song_workspace_restore import (
                ACTIVE_SONG_RESTORE_INCOMPLETE_KEY,
                CHOOSE_SONG_RESTORE_STATE_KEY,
                apply_canonical_active_song_from_workspace,
                workspace_envelope_expects_catalog_song,
            )

            apply_canonical_active_song_from_workspace(
                st,
                payload,
                song_picker_catalog=song_picker_catalog,
                song_library=song_library,
                allow_migration=True,
                persist_migration=True,
            )
        except ImportError:
            pass

    try:
        from active_song_workspace_restore import (
            ACTIVE_SONG_RESTORE_INCOMPLETE_KEY,
            CHOOSE_SONG_RESTORE_STATE_KEY,
            workspace_envelope_expects_catalog_song,
        )
    except ImportError:
        ACTIVE_SONG_RESTORE_INCOMPLETE_KEY = "_music_active_song_restore_incomplete"  # type: ignore[misc]
        CHOOSE_SONG_RESTORE_STATE_KEY = "_music_choose_song_restore_state"  # type: ignore[misc]

        def workspace_envelope_expects_catalog_song(_payload: dict) -> bool:  # type: ignore[misc]
            return False

    try:
        from songs.state import apply_active_pick_key_reconciliation, reconcile_active_pick_key

        apply_active_pick_key_reconciliation(
            st,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
        )
        reconciled = reconcile_active_pick_key(
            ss,
            song_picker_catalog=song_picker_catalog,
        )
        if (
            isinstance(payload, dict)
            and payload
            and workspace_envelope_expects_catalog_song(payload)
            and not str(reconciled or "").strip()
        ):
            ss[ACTIVE_SONG_RESTORE_INCOMPLETE_KEY] = True
            ss[CHOOSE_SONG_RESTORE_STATE_KEY] = True
        elif str(reconciled or "").strip():
            ss.pop(ACTIVE_SONG_RESTORE_INCOMPLETE_KEY, None)
            ss.pop(CHOOSE_SONG_RESTORE_STATE_KEY, None)
    except ImportError:
        try:
            from songs.state import apply_active_pick_key_reconciliation

            apply_active_pick_key_reconciliation(
                st,
                song_picker_catalog=song_picker_catalog,
                song_library=song_library,
            )
        except ImportError:
            pass

    try:
        from studio_cache import invalidate_session_cache

        invalidate_session_cache(ss, "chart_bundle")
    except ImportError:
        pass

    ss[MUSIC_STARTUP_RESTORE_FINALIZED_KEY] = True
    try:
        from music_startup_save_suppression import finalize_startup_canonical_alignment

        finalize_startup_canonical_alignment(st, stage="early_finalize")
    except ImportError:
        pass
    if (
        complete_music_restore_phase is not None
        and not music_restore_phase_complete(ss)
        and not ss.get(ACTIVE_SONG_RESTORE_INCOMPLETE_KEY)
    ):
        complete_music_restore_phase(ss)


def music_should_skip_master_song_init(session_state: dict[str, Any]) -> bool:
    """True when cold-start trusted-core pin would clobber restored workspace state."""
    reason = music_skip_master_song_init_reason(session_state)
    if reason:
        session_state["_music_skip_master_song_init_reason"] = reason
        return True
    session_state["_music_skip_master_song_init_reason"] = "cold_start"
    return False


def _record_music_startup_restore_diag(
    ss: dict[str, Any],
    payload: dict[str, Any],
    *,
    restored_studio_page: str,
    blob_studio_page: str,
    default_init_called: bool,
) -> None:
    """Capture reboot-restore diagnostics for ?dev=1 and Sprint D validation."""
    sel = ss.get(SELECTED_SONG_STATE_KEY) if isinstance(ss.get(SELECTED_SONG_STATE_KEY), dict) else {}
    restored_active = ""
    try:
        core = payload.get("core") if isinstance(payload.get("core"), dict) else {}
        extra = payload.get("session") if isinstance(payload.get("session"), dict) else {}
        restored_active = str(
            core.get("pick_key")
            or extra.get("active_catalog_pick_key")
            or ""
        ).strip()
        if not restored_active:
            meta = payload.get("active_song_state")
            if isinstance(meta, dict):
                restored_active = str(meta.get("pick_key") or "").strip()
    except Exception:
        pass

    custom_count = 0
    saved = ss.get("cpl_saved_progressions")
    if isinstance(saved, dict):
        custom_count = len(saved)

    mt_diag = ss.get("_multitrack_persist_diag") if isinstance(ss.get("_multitrack_persist_diag"), dict) else {}

    workspace_diag: dict[str, Any] = {}
    try:
        from active_song_workspace_restore import merge_active_song_workspace_diagnostics

        workspace_diag = merge_active_song_workspace_diagnostics(ss)
    except ImportError:
        pass

    startup_suppress: dict[str, Any] = {}
    try:
        from music_startup_save_suppression import collect_startup_save_suppression_diagnostics

        startup_suppress = collect_startup_save_suppression_diagnostics(ss)
    except ImportError:
        pass

    ss[MUSIC_STARTUP_RESTORE_DIAG_KEY] = {
        "restored_studio_page": restored_studio_page or blob_studio_page or None,
        "final_studio_page": str(ss.get("studio_page") or "").strip() or None,
        "restored_active_song": restored_active or None,
        "final_active_song": str(sel.get("pick_key") or ss.get(ACTIVE_CATALOG_PICK_KEY) or "").strip() or None,
        "custom_song_count_after_restore": custom_count,
        "default_init_called": bool(default_init_called),
        "skip_master_song_init_reason": ss.get("_music_skip_master_song_init_reason"),
        "first_autosave_reason": ss.get("_suite_persist_last_save_reason"),
        "mt_tracks_count_after_restore": mt_diag.get("mt_tracks_count_after_restore"),
        "audio_persisted": mt_diag.get("audio_persisted"),
        "skipped_due_to_size": mt_diag.get("skipped_due_to_size"),
        "restore_source": mt_diag.get("restore_source"),
        **workspace_diag,
        **startup_suppress,
    }


def _finalize_music_workspace_restore(
    st: Any,
    payload: dict[str, Any],
    *,
    song_picker_catalog: dict,
    song_library: dict | None,
) -> None:
    """Reconcile custom song + multitrack blobs after session_extra hydration."""
    ss = st.session_state
    try:
        from active_song_state import apply_cloud_active_song_state_if_allowed

        apply_cloud_active_song_state_if_allowed(ss, payload)
        if _session_has_restored_song_context(ss):
            clear_music_ephemeral_default_song(ss)
    except ImportError:
        pass

    core = payload.get("core") if isinstance(payload.get("core"), dict) else {}
    custom_pk = str(core.get("pick_key") or "").strip()
    if custom_pk.startswith("custom::"):
        try:
            from songs.state import apply_saved_custom_pick_key_context

            apply_saved_custom_pick_key_context(
                st,
                custom_pk,
                core if isinstance(core, dict) else {},
                song_picker_catalog=song_picker_catalog,
                song_library=song_library,
            )
        except Exception:
            pass
    elif _payload_has_custom_active_signals(payload):
        core_pk_guard = str((core if isinstance(core, dict) else {}).get("pick_key") or "").strip()
        if not (core_pk_guard and not core_pk_guard.startswith("custom::")):
            session_extra = payload.get("session") if isinstance(payload.get("session"), dict) else {}
            cpl = session_extra.get("cpl_active_progression")
            if not isinstance(cpl, dict):
                cpl = ss.get("cpl_active_progression")
            if isinstance(cpl, dict):
                cid = str(cpl.get("id") or "").strip()
                if cid:
                    try:
                        from songs.state import apply_saved_custom_pick_key_context

                        apply_saved_custom_pick_key_context(
                            st,
                            f"custom::{cid}",
                            core if isinstance(core, dict) else {},
                            song_picker_catalog=song_picker_catalog,
                            song_library=song_library,
                        )
                    except Exception:
                        pass

    try:
        from multitrack_session_persistence import restore_multitrack_layers_from_workspace

        restore_multitrack_layers_from_workspace(ss)
    except ImportError:
        try:
            from multitrack_session_persistence import restore_multitrack_session_if_needed

            restore_multitrack_session_if_needed(ss)
        except ImportError:
            pass

    try:
        from studio_page_persistence import restore_current_page_snapshot_if_needed

        restore_current_page_snapshot_if_needed(ss)
    except ImportError:
        pass

    try:
        from custom_song_library import merge_custom_songs_from_cloud

        merge_custom_songs_from_cloud(ss, st=st)
    except Exception:
        pass

# Content-edit saves must not clobber the last page_change-persisted studio_page.
_PRESERVE_USER_NAV_SAVE_REASONS: frozenset[str] = frozenset(
    {
        "song_edit",
        "cpl_draft_edit",
        "practice_edit",
        "backing_edit",
        "autosave",
        "force_autosave",
    }
)

# JSON-serializable session keys (never large blobs / widget-only keys).
_PERSIST_KEYS: tuple[str, ...] = (
    "studio_page",
    "chart_library_mode",
    "song_picker_chart_status",
    "song_search_text",
    "song_search_scope",
    "song_picker_level_filter",
    "workspace_genre_filter",
    "backing_track_scope",
    "backing_track_loops",
    "backing_track_single_section",
    "backing_groove_style",
    "backing_lead_sheet_open",
    "backing_track_bpm",
    "backing_time_signature",
    "backing_time_signature_override",
    "backing_quick_section",
    "karaoke_countdown_enabled",
    "karaoke_auto_advance",
    "active_music_source",
    "chart_edit_mode",
    "picker_editor_tab",
    "picker_song_editor_open",
    "last_practice_mode",
    "improv_song_source",
    "creative_lab_analysis_mode",
    "improv_intelligence_tab",
    "creative_improv_intelligence_tab",
    "last_analysis_result",
    "last_analysis_audio",
    "last_analysis_source_label",
    "song_picker_favorites_only",
    "cpl_active_progression",
    "cpl_saved_progressions",
    "cpl_builder_version",
    "cpl_edit_section",
    "cpl_finished",
    "_cpl_editing_display_key",
    "cpl_last_display_key",
    "mt_track_filenames",
    "mt_tracks",
    "mixed_track_wav",
    "guitar_capo_enabled",
    "guitar_capo_sounding_key",
    "guitar_capo_shape_key",
    "guitar_capo_last_concert_key",
    "latest_practice_analysis_summary",
    "latest_practice_analysis_created_at",
    "latest_practice_analysis_evidence_counts",
    "latest_practice_analysis_full_report",
    "latest_practice_analysis_handoff_status",
    "backing_context",
    "creative_session",
    "improv_entry_mode",
    "improv_generated_sections",
    "improv_style_meta",
    "improv_jam_session",
    "improv_style_key",
    "improv_style",
    "improv_style_bpm",
    "improv_mood",
    "improv_groove",
    "improv_difficulty",
    "improv_style_meter",
    "improv_jam_key",
    "improv_jam_bpm",
    "improv_jam_style",
    "improv_jam_mood",
    "improv_song_concert_sections",
    "improv_song_chart_sections",
    "improv_active_mission",
    "improv_mission_pick",
    "improv_mission_example",
    "improv_mission_variant",
    "improv_mission_new_nonce",
    "improv_mission_practice_lick",
    "improv_mission_chord_options",
    "improv_mission_progression",
    "ii_selected_chord",
    "ii_selected_section",
    "ii_selected_chord_index",
    "ii_selected_chord_label",
    "improv_mission_workspace_updated_at",
    "harmony_map_section",
    "harmony_map_chord",
    "improv_motif",
    "improv_motif_output_mode",
    "improv_motif_abc",
    "improv_motif_tab",
    "deep_harmony_lesson_step",
    "improv_deep_harmony_dha_section_idx",
    "creative_lab_last_mode",
    "improv_ai_metric_ids",
    "analysis_criteria_locked",
    "practice_key_by_source",
    "bpm_by_source",
    "practice_key_mode",
    "fixed_practice_key",
    "fixed_practice_key_family_id",
    "fixed_practice_key_family_spelling",
    "sbi_preview_source",
    "catalog_session",
    "custom_session",
    "_last_catalog_song_state",
    "_catalog_before_custom_state",
)

_LIST_KEYS = (
    "backing_track_multi_sections",
    "karaoke_queue",
    "catalog_favorite_pick_keys",
    "catalog_recent_pick_keys",
)

_INSIGHT_KEYS = (
    "_ami_pending_insight",
    "_ami_return_page",
    "_ami_return_context",
    "_ami_dismissed_insight_ids",
    "_ami_dismissed_insight_at",
)

# Phase C canonical modules (grow as migration proceeds).
_WORKSPACE_KEYS: tuple[str, ...] = (
    "active_song_state",
    "studio_nav_state",
    "practice_state",
    "practice_workspace_state",
    "creative_workspace_state",
    "backing_track_state",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _active_workspace_id(st: Any) -> str:
    try:
        from suite_workspace import get_active_workspace_id

        return get_active_workspace_id(st)
    except Exception:
        return "daniel"


def get_music_device_id(st: Any) -> str:
    """Stable per-install device id (persisted under data/music_device_id.txt)."""
    return _get_device_id(st)


def _get_device_id(st: Any) -> str:
    try:
        from pathlib import Path

        path = Path("data") / "music_device_id.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            return path.read_text(encoding="utf-8").strip() or "unknown"
        import uuid

        device_id = str(uuid.uuid4())
        path.write_text(device_id, encoding="utf-8")
        return device_id
    except Exception:
        return "unknown"


def _normalize_studio_page_for_save(page: Any) -> str:
    val = str(page or "").strip()
    if not val:
        return ""
    try:
        from studio_nav_history import STUDIO_PAGE_IDS

        return val if val in STUDIO_PAGE_IDS else ""
    except ImportError:
        return val


def _studio_nav_page_from_session(ss: dict[str, Any]) -> str:
    nav = ss.get("studio_nav_state")
    if isinstance(nav, dict):
        return _normalize_studio_page_for_save(nav.get("studio_page") or nav.get("page"))
    return ""


_PAGE_CHANGE_STAMP_TARGET_KEY = "_suite_page_change_stamp_target"
_PAGE_CHANGE_WRITE_PENDING_KEY = "_suite_page_change_write_pending"
MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY = "_music_user_navigated_page_this_run"


def mark_user_navigated_page_this_run(session: dict[str, Any], page: str) -> str:
    """Record genuine user navigation for this script run (wins over stale workspace blob)."""
    normalized = _normalize_studio_page_for_save(page)
    if not normalized:
        return ""
    session[MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY] = normalized
    _mark_page_change_write_pending(session, normalized)
    return normalized


def clear_user_navigated_page_this_run(session: dict[str, Any], *, page: str = "") -> None:
    cur = _normalize_studio_page_for_save(session.get(MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY))
    want = _normalize_studio_page_for_save(page)
    if not cur:
        return
    if not want or cur == want:
        session.pop(MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY, None)


def synchronize_page_bearing_state_for_save(session: dict[str, Any], page: str) -> None:
    """Stamp authoritative page into session + workspace blobs before payload build."""
    try:
        from music_page_save_pipeline_trace import (
            page_sync_impl_marker,
            record_checkpoint,
            record_pipeline_event,
        )

        record_pipeline_event(
            session,
            function="synchronize_page_bearing_state_for_save",
            phase="entry",
            selected_target=_normalize_studio_page_for_save(page),
            extra={"page_sync_impl_marker": page_sync_impl_marker},
        )
        record_checkpoint(session, "B_sync_page_bearing_entry")
    except ImportError:
        pass
    normalized = _normalize_studio_page_for_save(page)
    if not normalized:
        return
    _apply_page_change_stamp_to_session(session, normalized)
    pws = session.get("practice_workspace_state")
    if isinstance(pws, dict):
        pws = copy.deepcopy(pws)
        pws["studio_page"] = normalized
        pws["page"] = normalized
        session["practice_workspace_state"] = pws
    try:
        from music_page_save_pipeline_trace import (
            page_sync_impl_marker,
            record_checkpoint,
            record_pipeline_event,
        )

        record_pipeline_event(
            session,
            function="synchronize_page_bearing_state_for_save",
            phase="exit",
            selected_target=normalized,
            extra={"page_sync_impl_marker": page_sync_impl_marker},
        )
        record_checkpoint(session, "B_sync_page_bearing_exit")
    except ImportError:
        pass


def _assert_page_change_payload_not_stale(
    session: dict[str, Any],
    *,
    target: str,
    trace: dict[str, Any],
) -> None:
    try:
        from music_startup_save_suppression import get_page_change_origin
    except ImportError:
        return
    if get_page_change_origin(session) != "user_navigation":
        return
    clicked = _normalize_studio_page_for_save(
        session.get(MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY)
        or session.get("requested_page")
    )
    if not clicked:
        return
    fields = (
        trace.get("save_payload_core_page"),
        trace.get("save_payload_session_page"),
        trace.get("save_payload_workspace_page"),
        trace.get("save_payload_studio_nav_page"),
        trace.get("post_stamp_core_page"),
        trace.get("post_stamp_session_page"),
        trace.get("post_stamp_workspace_page"),
        trace.get("post_stamp_studio_nav_page"),
    )
    stale = [f for f in fields if f and _normalize_studio_page_for_save(f) != clicked]
    if not stale and _normalize_studio_page_for_save(target) == clicked:
        return
    viol = {
        "code": "PHASE1_PAGE_PAYLOAD_STALE",
        "clicked_page": clicked,
        "target": target,
        "stale_fields": stale,
        "trace": {k: trace.get(k) for k in fields if trace.get(k)},
    }
    session.setdefault("_phase1_page_payload_violations", []).append(viol)
    try:
        import streamlit as st

        st.session_state["_phase1_last_page_payload_violation"] = viol
    except Exception:
        pass


def _normalized_session_studio_page_for_save(ss: dict[str, Any]) -> tuple[str, str]:
    """Single source of truth: current normalized ``studio_page`` in session."""
    live = _normalize_studio_page_for_save(ss.get("studio_page"))
    if live:
        return live, "normalized_studio_page"
    ws = ss.get("music_workspace_state")
    ws_page = (
        _normalize_studio_page_for_save(ws.get("studio_page"))
        if isinstance(ws, dict)
        else ""
    )
    if ws_page:
        return ws_page, "music_workspace_state.studio_page"
    nav = _studio_nav_page_from_session(ss)
    if nav:
        return nav, "studio_nav_state"
    hinted = _normalize_studio_page_for_save(ss.get("_suite_page_change_save_page"))
    if hinted:
        return hinted, "_suite_page_change_save_page"
    return "", "missing"


def _pending_page_change_write_target(ss: dict[str, Any]) -> str:
    """Page id that must still be written before page_change is considered complete."""
    for key in (
        _PAGE_CHANGE_WRITE_PENDING_KEY,
        _PAGE_CHANGE_STAMP_TARGET_KEY,
        "_suite_page_change_save_page",
    ):
        page = _normalize_studio_page_for_save(ss.get(key))
        if page:
            return page
    return ""


def _mark_page_change_write_pending(session: dict[str, Any], page_id: str) -> str:
    page = _normalize_studio_page_for_save(page_id)
    if not page:
        return ""
    session[_PAGE_CHANGE_WRITE_PENDING_KEY] = page
    session[_PAGE_CHANGE_STAMP_TARGET_KEY] = page
    session["_suite_page_change_save_page"] = page
    return page


def _clear_page_change_write_pending(session: dict[str, Any]) -> None:
    session.pop(_PAGE_CHANGE_WRITE_PENDING_KEY, None)
    session.pop(_PAGE_CHANGE_STAMP_TARGET_KEY, None)
    session.pop("_suite_page_change_save_page", None)


def _maybe_clear_page_change_write_pending(
    st: Any,
    state: dict[str, Any],
    *,
    saved_cloud: bool,
) -> None:
    if not saved_cloud:
        return
    ss = st.session_state
    pending = _pending_page_change_write_target(ss)
    if not pending:
        return
    written = _normalize_studio_page_for_save(
        ss.get("_music_cloud_write_studio_page")
        or ss.get("_music_final_payload_studio_page")
        or _studio_page_from_save_state(state)
    )
    if written == pending:
        _clear_page_change_write_pending(ss)
        clear_user_navigated_page_this_run(ss, page=pending)


def _page_change_write_target(ss: dict[str, Any]) -> tuple[str, str]:
    """Resolve the page id that must be written for page_change (session/workspace/nav)."""
    try:
        from music_page_save_pipeline_trace import page_target_impl_marker, record_pipeline_event

        record_pipeline_event(
            ss,
            function="_page_change_write_target",
            phase="entry",
            extra={"page_target_impl_marker": page_target_impl_marker},
        )
    except ImportError:
        pass
    candidates: list[dict[str, Any]] = []

    def _cand(key: str, page: str, *, eligible: bool, note: str = "") -> None:
        candidates.append(
            {
                "key": key,
                "page": _normalize_studio_page_for_save(page),
                "eligible": eligible,
                "note": note or None,
            }
        )

    user_run = _normalize_studio_page_for_save(ss.get(MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY))
    _cand(MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY, user_run, eligible=bool(user_run), note="highest_precedence")
    if user_run:
        try:
            from music_page_save_pipeline_trace import record_page_target_resolution

            record_page_target_resolution(
                ss,
                candidates=candidates,
                selected_page=user_run,
                selected_source=MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY,
                branch="user_run_wins",
            )
        except ImportError:
            pass
        return user_run, MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY

    live, live_source = _normalized_session_studio_page_for_save(ss)
    user_nav = bool(ss.get("_suite_page_user_nav"))
    _cand("normalized_session", live, eligible=bool(user_nav and live), note=f"source={live_source}")

    if user_nav and live:
        try:
            from music_page_save_pipeline_trace import record_page_target_resolution

            record_page_target_resolution(
                ss,
                candidates=candidates,
                selected_page=live,
                selected_source=live_source,
                branch="user_nav_and_live_session",
            )
        except ImportError:
            pass
        return live, live_source

    write_pending = _normalize_studio_page_for_save(ss.get(_PAGE_CHANGE_WRITE_PENDING_KEY))
    _cand(_PAGE_CHANGE_WRITE_PENDING_KEY, write_pending, eligible=bool(write_pending))
    if write_pending:
        if live and live != write_pending:
            _cand("live_over_pending", live, eligible=True, note="live != pending")
            try:
                from music_page_save_pipeline_trace import record_page_target_resolution

                record_page_target_resolution(
                    ss,
                    candidates=candidates,
                    selected_page=live,
                    selected_source=live_source,
                    branch="live_session_over_stale_pending",
                )
            except ImportError:
                pass
            return live, live_source
        try:
            from music_page_save_pipeline_trace import record_page_target_resolution

            record_page_target_resolution(
                ss,
                candidates=candidates,
                selected_page=write_pending,
                selected_source=_PAGE_CHANGE_WRITE_PENDING_KEY,
                branch="write_pending",
            )
        except ImportError:
            pass
        return write_pending, _PAGE_CHANGE_WRITE_PENDING_KEY

    _cand("normalized_session_fallback", live, eligible=bool(live))
    if live:
        try:
            from music_page_save_pipeline_trace import record_page_target_resolution

            record_page_target_resolution(
                ss,
                candidates=candidates,
                selected_page=live,
                selected_source=live_source,
                branch="live_session_fallback",
            )
        except ImportError:
            pass
        return live, live_source

    nav = _studio_nav_page_from_session(ss)
    _cand("studio_nav_state", nav, eligible=bool(nav))
    if nav:
        try:
            from music_page_save_pipeline_trace import record_page_target_resolution

            record_page_target_resolution(
                ss,
                candidates=candidates,
                selected_page=nav,
                selected_source="studio_nav_state",
                branch="studio_nav_state",
            )
        except ImportError:
            pass
        return nav, "studio_nav_state"

    stamp = _normalize_studio_page_for_save(ss.get(_PAGE_CHANGE_STAMP_TARGET_KEY))
    _cand(_PAGE_CHANGE_STAMP_TARGET_KEY, stamp, eligible=bool(stamp))
    if stamp:
        try:
            from music_page_save_pipeline_trace import record_page_target_resolution

            record_page_target_resolution(
                ss,
                candidates=candidates,
                selected_page=stamp,
                selected_source=_PAGE_CHANGE_STAMP_TARGET_KEY,
                branch="stamp_target",
            )
        except ImportError:
            pass
        return stamp, _PAGE_CHANGE_STAMP_TARGET_KEY

    resolved, resolved_source = _resolve_page_change_stamp_target(ss)
    _cand("resolve_stamp_target", resolved, eligible=bool(resolved))
    try:
        from music_page_save_pipeline_trace import record_page_target_resolution

        record_page_target_resolution(
            ss,
            candidates=candidates,
            selected_page=resolved,
            selected_source=resolved_source,
            branch="resolve_page_change_stamp_target",
        )
    except ImportError:
        pass
    return resolved, resolved_source


def _resolve_page_change_stamp_target(ss: dict[str, Any]) -> tuple[str, str]:
    """Authoritative page_change save target — live normalized session page wins."""
    normalized, source = _normalized_session_studio_page_for_save(ss)
    if normalized:
        return normalized, source

    explicit = _normalize_studio_page_for_save(ss.get(_PAGE_CHANGE_STAMP_TARGET_KEY))
    if explicit:
        return explicit, _PAGE_CHANGE_STAMP_TARGET_KEY

    for key, source in (
        ("_suite_page_change_save_page", "_suite_page_change_save_page"),
        ("_suite_deferred_page_change_save", "_suite_deferred_page_change_save"),
    ):
        page = _normalize_studio_page_for_save(ss.get(key))
        if page:
            return page, source
    return "", "missing"


def _payload_page_snapshot(state: dict[str, Any]) -> dict[str, str]:
    core = state.get("core") if isinstance(state.get("core"), dict) else {}
    sess = state.get("session") if isinstance(state.get("session"), dict) else {}
    ws = state.get("music_workspace_state") if isinstance(state.get("music_workspace_state"), dict) else {}
    nav = state.get("studio_nav_state") if isinstance(state.get("studio_nav_state"), dict) else {}
    return {
        "core": str(core.get("studio_page") or "").strip(),
        "session": str(sess.get("studio_page") or "").strip(),
        "workspace": str(ws.get("studio_page") or "").strip(),
        "studio_nav": str(nav.get("studio_page") or nav.get("page") or "").strip(),
    }


def _studio_page_from_save_state(state: dict[str, Any]) -> str:
    snap = _payload_page_snapshot(state)
    for key in ("workspace", "core", "session", "studio_nav"):
        page = _normalize_studio_page_for_save(snap.get(key))
        if page:
            return page
    return ""


def _sync_save_payload_trace_fields(trace: dict[str, Any]) -> dict[str, Any]:
    """Ensure save_payload_* and final_payload_* reflect post-stamp values for diagnostics."""
    out = dict(trace)
    final_page = str(
        out.get("final_payload_studio_page")
        or out.get("cloud_write_studio_page")
        or out.get("post_stamp_workspace_page")
        or out.get("post_stamp_core_page")
        or ""
    ).strip()
    mapping = (
        ("post_stamp_core_page", "save_payload_core_page"),
        ("post_stamp_session_page", "save_payload_session_page"),
        ("post_stamp_workspace_page", "save_payload_workspace_page"),
        ("post_stamp_studio_nav_page", "save_payload_studio_nav_page"),
    )
    for src, dst in mapping:
        val = str(out.get(src) or "").strip()
        if val:
            out[dst] = val
    if final_page:
        out["final_payload_studio_page"] = final_page
        if not str(out.get("save_payload_workspace_page") or "").strip():
            out["save_payload_workspace_page"] = final_page
        if not str(out.get("save_payload_core_page") or "").strip():
            out["save_payload_core_page"] = final_page
    return out


def _finalize_trace_shell(
    *,
    save_reason: str = "",
    target: str = "",
    source: str = "",
    error: str = "",
    ran: bool = False,
) -> dict[str, Any]:
    return {
        "page_change_finalize_ran": ran,
        "page_change_finalize_target": target or None,
        "page_change_finalize_source": source or None,
        "page_change_finalize_error": error or None,
        "save_reason_at_write": save_reason or None,
        "cloud_write_studio_page": None,
        "final_payload_studio_page": None,
    }


def finalize_music_page_change_cloud_payload(
    st: Any,
    state: dict[str, Any],
    *,
    save_reason: str = "page_change",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Last-chance stamp immediately before disk/cloud write (phone page_change)."""
    ss = st.session_state
    try:
        from music_page_save_pipeline_trace import finalize_impl_marker, record_pipeline_event

        record_pipeline_event(
            ss,
            function="finalize_music_page_change_cloud_payload",
            phase="entry",
            extra={"finalize_impl_marker": finalize_impl_marker, "save_reason": save_reason},
            payload=state,
        )
    except ImportError:
        pass
    target, source = _page_change_write_target(ss)
    if not target:
        return state, _finalize_trace_shell(
            save_reason=save_reason,
            error="no_page_change_write_target",
            ran=False,
        )

    synchronize_page_bearing_state_for_save(ss, target)
    try:
        pre = _payload_page_snapshot(state)
        post_trace = _stamp_live_studio_page_into_save_payload(
            state,
            target,
            source=source or "normalized_studio_page",
            coach_page=target,
        )
        post = _payload_page_snapshot(state)
        final_page = _studio_page_from_save_state(state) or target
        trace: dict[str, Any] = _sync_save_payload_trace_fields(
            {
                **post_trace,
                **_finalize_trace_shell(
                    save_reason=save_reason,
                    target=target,
                    source=source,
                    ran=True,
                ),
                "pre_stamp_core_page": pre.get("core") or None,
                "pre_stamp_session_page": pre.get("session") or None,
                "pre_stamp_workspace_page": pre.get("workspace") or None,
                "pre_stamp_studio_nav_page": pre.get("studio_nav") or None,
                "post_stamp_core_page": post.get("core") or None,
                "post_stamp_session_page": post.get("session") or None,
                "post_stamp_workspace_page": post.get("workspace") or None,
                "post_stamp_studio_nav_page": post.get("studio_nav") or None,
                "cloud_write_studio_page": final_page or None,
                "final_payload_studio_page": final_page or None,
                "final_payload_source": source or "normalized_studio_page",
            }
        )
        _assert_page_change_payload_not_stale(ss, target=target, trace=trace)
        try:
            from music_page_save_pipeline_trace import payload_pages_from_state, record_pipeline_event

            record_pipeline_event(
                ss,
                function="finalize_music_page_change_cloud_payload",
                phase="exit",
                selected_target=target,
                target_source=source,
                extra={"payload_pages": payload_pages_from_state(state)},
            )
        except ImportError:
            pass
        return state, trace
    except Exception as exc:
        return state, _finalize_trace_shell(
            save_reason=save_reason,
            target=target,
            source=source,
            error=str(exc),
            ran=False,
        )


def sync_page_change_write_pending_for_music_save(st: Any) -> str:
    """Promote any in-flight page_change target onto the write ``session_state``."""
    ss = st.session_state
    existing = _pending_page_change_write_target(ss)
    if existing:
        _mark_page_change_write_pending(ss, existing)
        return existing
    try:
        from music_persistence_trace import get_trace

        trace = get_trace(st)
        if isinstance(trace, dict):
            for key in ("page_change_write_pending", "build_page_change_target"):
                page = _normalize_studio_page_for_save(trace.get(key))
                if page:
                    _mark_page_change_write_pending(ss, page)
                    return page
    except Exception:
        pass
    stamp_trace = ss.get("_music_save_payload_stamp_trace")
    if isinstance(stamp_trace, dict):
        for key in ("page_change_write_pending", "build_page_change_target"):
            page = _normalize_studio_page_for_save(stamp_trace.get(key))
            if page:
                _mark_page_change_write_pending(ss, page)
                return page
    build_target = _normalize_studio_page_for_save(ss.get("_music_build_page_change_target"))
    if build_target and str(ss.get("_music_build_save_reason") or "") == "page_change":
        _mark_page_change_write_pending(ss, build_target)
        return build_target
    return ""


def resolve_music_save_reason_at_write(st: Any, explicit: str = "") -> str:
    """Resolve the save reason that must drive the pre-write stamp on this persist."""
    sync_page_change_write_pending_for_music_save(st)
    ss = st.session_state
    if _pending_page_change_write_target(ss):
        return "page_change"
    explicit_reason = str(explicit or "").strip()
    if explicit_reason and explicit_reason != "autosave":
        return explicit_reason
    pending = str(ss.get("_suite_pending_save_reason") or "").strip()
    if pending:
        return pending
    at_write = str(ss.get("_music_save_reason_at_write") or "").strip()
    if at_write:
        return at_write
    if ss.get("_suite_page_user_nav") and ss.get("_music_build_page_change_target"):
        return "page_change"
    last_force = str(ss.get("_suite_persist_last_save_reason") or "").strip()
    if last_force == "page_change":
        return "page_change"
    return explicit_reason or "autosave"


def apply_music_pre_write_stamp(
    st: Any,
    state: dict[str, Any],
    *,
    save_reason: str = "",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Stamp persist payload from session immediately before disk/cloud write."""
    pending = sync_page_change_write_pending_for_music_save(st)
    reason = "page_change" if pending else resolve_music_save_reason_at_write(st, save_reason)
    if reason == "page_change":
        state, trace = finalize_music_page_change_cloud_payload(st, state, save_reason=reason)
    else:
        state, trace = ensure_music_payload_stamped_for_session(st, state)
        if not trace:
            trace = _finalize_trace_shell(save_reason=reason, ran=False)
        else:
            trace = {
                **trace,
                **_finalize_trace_shell(
                    save_reason=reason,
                    target=trace.get("page_change_finalize_target"),
                    source=trace.get("page_change_finalize_source"),
                    ran=True,
                ),
            }
    meta = {
        "page_change_finalize_ran": bool(trace.get("page_change_finalize_ran")),
        "page_change_finalize_target": trace.get("page_change_finalize_target"),
        "page_change_finalize_source": trace.get("page_change_finalize_source"),
        "page_change_finalize_error": trace.get("page_change_finalize_error"),
        "page_change_write_pending": _pending_page_change_write_target(st.session_state) or None,
        "page_change_write_coerced": bool(pending and str(save_reason or "").strip() not in ("", "page_change")),
        "_music_save_reason_at_write": reason,
        "_music_cloud_write_studio_page": trace.get("cloud_write_studio_page"),
        "_music_final_payload_studio_page": trace.get("final_payload_studio_page"),
    }
    return state, trace, meta


def record_music_pre_write_diagnostics(
    st: Any,
    trace: dict[str, Any],
    meta: dict[str, Any],
    *,
    write_path: str,
) -> None:
    """Mirror pre-write stamp diagnostics onto session + stamp trace."""
    ss = st.session_state
    ss["music_pre_write_path"] = write_path
    ss["music_pre_write_stamp_ran"] = bool(
        trace.get("page_change_finalize_ran")
        or trace.get("cloud_write_studio_page")
    )
    for key, val in meta.items():
        ss[key] = val
    for key in (
        "page_change_finalize_ran",
        "page_change_finalize_target",
        "page_change_finalize_source",
        "page_change_finalize_error",
    ):
        val = meta.get(key)
        if val is None:
            val = trace.get(key)
        if val is not None:
            ss[key] = val
    if trace:
        stamped = _sync_save_payload_trace_fields(
            {
                **trace,
                "music_pre_write_path": write_path,
                "music_pre_write_stamp_ran": bool(trace.get("page_change_finalize_ran")),
                "save_reason_at_write": meta.get("_music_save_reason_at_write"),
            }
        )
        ss["_music_save_payload_stamp_trace"] = stamped


def build_music_fallback_page_change_state(st: Any) -> dict[str, Any]:
    """Minimal persist blob when full disk build throws during page_change."""
    ss = st.session_state
    target = (
        sync_page_change_write_pending_for_music_save(st)
        or _normalize_studio_page_for_save(ss.get("_music_build_page_change_target"))
        or _page_change_write_target(ss)[0]
    )
    if not target:
        raise ValueError("no page_change target for fallback build")
    core = build_music_local_state(st)
    core["studio_page"] = target
    core["page"] = target
    extra: dict[str, Any] = {"studio_page": target}
    state: dict[str, Any] = {"core": core, "session": extra}
    nav = ss.get("studio_nav_state")
    if isinstance(nav, dict):
        nav_copy = copy.deepcopy(nav)
        nav_copy["studio_page"] = target
        nav_copy["page"] = target
        state["studio_nav_state"] = nav_copy
    ws = ss.get("music_workspace_state")
    if isinstance(ws, dict):
        ws_copy = copy.deepcopy(ws)
        ws_copy["studio_page"] = target
        ws_copy["page"] = target
        state["music_workspace_state"] = ws_copy
    else:
        state["music_workspace_state"] = {"studio_page": target, "page": target}
    ss["_music_build_save_reason"] = "page_change"
    ss["_music_build_page_change_target"] = target
    ss["_music_fallback_page_change_build"] = True
    return state


def build_music_state_for_save(
    st: Any,
    build_state: Any,
    *,
    save_reason: str = "",
) -> dict[str, Any]:
    """Build disk state; on page_change failures use a minimal backing-safe blob."""
    try:
        return build_state(st)
    except Exception as exc:
        ss = st.session_state
        ss["_music_disk_build_error"] = str(exc)
        if save_reason == "page_change" or _pending_page_change_write_target(ss):
            return build_music_fallback_page_change_state(st)
        raise


def record_transposing_save_diagnostics(
    st: Any,
    payload: dict[str, Any] | None,
    *,
    phase: str,
    write_path: str = "",
    readback_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record canonical/payload/cloud-readback transposing fields for save-path debugging."""
    ss = st.session_state
    try:
        from active_song_state import collect_transposing_save_trace_fields
    except ImportError:
        return {}
    rows = collect_transposing_save_trace_fields(ss, payload, phase=phase)
    if write_path:
        rows["save_write_path"] = write_path
    if isinstance(readback_payload, dict):
        rb_written, rb_subtype = None, None
        try:
            from active_song_state import _transposing_values_from_payload_sources

            rb_written, rb_subtype = _transposing_values_from_payload_sources(readback_payload)
        except ImportError:
            pass
        rows["save_written_key_cloud_readback"] = rb_written
        rows["save_transposing_subtype_cloud_readback"] = rb_subtype
    if phase == "cloud_readback":
        last = ss.get("_music_last_transposing_save_trace")
        if isinstance(last, dict):
            rows = {**last, **rows}
    seq = int(ss.get("_music_transposing_save_seq") or 0) + 1
    if phase == "payload_write":
        rows["save_sequence"] = seq
        ss["_music_transposing_save_seq"] = seq
    prev = ss.get("_music_prev_transposing_save_trace")
    if isinstance(prev, dict) and phase == "payload_write":
        if (
            prev.get("save_written_key_payload") is not None
            and rows.get("save_written_key_payload") is not None
            and prev.get("save_written_key_payload") != rows.get("save_written_key_payload")
        ) or (
            prev.get("save_transposing_subtype_payload") is not None
            and rows.get("save_transposing_subtype_payload") is not None
            and prev.get("save_transposing_subtype_payload") != rows.get("save_transposing_subtype_payload")
        ):
            ss["_music_transposing_save_overwrite_detected"] = True
            ss["_music_transposing_save_overwrite_detail"] = {
                "previous_written": prev.get("save_written_key_payload"),
                "current_written": rows.get("save_written_key_payload"),
                "previous_subtype": prev.get("save_transposing_subtype_payload"),
                "current_subtype": rows.get("save_transposing_subtype_payload"),
                "previous_seq": prev.get("save_sequence"),
                "current_seq": seq,
                "previous_path": prev.get("save_write_path"),
                "current_path": write_path,
            }
    ss["_music_prev_transposing_save_trace"] = dict(rows)
    ss["_music_last_transposing_save_trace"] = dict(rows)
    try:
        from music_persistence_trace import update_trace

        update_trace(st, **{k: v for k, v in rows.items() if v is not None})
    except Exception:
        pass
    return rows


def record_music_cloud_write_result(
    st: Any,
    state: dict[str, Any],
    *,
    write_path: str,
    saved_cloud: bool,
    cloud_error: str = "",
) -> None:
    ss = st.session_state
    ss["_music_cloud_write_path"] = write_path
    ss["_music_last_cloud_write_ok"] = saved_cloud
    ss["_music_stamp_before_cloud_write_ran"] = bool(
        ss.get("music_pre_write_stamp_ran") or ss.get("page_change_finalize_ran")
    )
    record_transposing_save_diagnostics(
        st,
        state,
        phase="payload_write",
        write_path=write_path,
    )
    if saved_cloud:
        import copy as _copy

        ss["_suite_last_cloud_save_payload"] = _copy.deepcopy(state)
        try:
            from backing_track_state import record_backing_disk_payload_trace

            record_backing_disk_payload_trace(ss, state)
        except ImportError:
            pass
        written = (
            ss.get("_music_final_payload_studio_page")
            or ss.get("_music_cloud_write_studio_page")
            or _studio_page_from_save_state(state)
        )
        if written:
            ss["_music_cloud_payload_studio_page"] = written
            ss["_music_cloud_payload_source"] = "last_write"
        _maybe_clear_page_change_write_pending(st, state, saved_cloud=True)
        ss.pop("_music_last_cloud_write_error", None)
    elif cloud_error:
        ss["_music_last_cloud_write_error"] = cloud_error


def save_music_cloud_session(
    st: Any,
    state: dict[str, Any],
    *,
    write_path: str,
    page: str = "",
    summary: str = "",
    strict_egress_approval: dict[str, Any] | None = None,
) -> bool:
    """Write stamped music state to cloud and record v13 write-path diagnostics."""
    from suite_cloud_state import save_cloud_full_session

    ss = st.session_state
    ss["_music_cloud_write_path"] = write_path
    approval = strict_egress_approval
    if approval is None:
        try:
            from music_strict_egress_transaction import STRICT_EGRESS_APPROVAL_KEY

            cached = ss.get(STRICT_EGRESS_APPROVAL_KEY)
            if isinstance(cached, dict):
                approval = cached
        except ImportError:
            approval = None

    try:
        from music_egress_config import music_cloud_write_allowed, music_egress_strict_enabled

        allowed_inside = True
        if music_egress_strict_enabled():
            allowed_inside = music_cloud_write_allowed(
                save_reason=str((approval or {}).get("reason") or (approval or {}).get("raw_reason") or ""),
                st=st,
                strict_egress_approval=approval,
            )
        ss["_music_cloud_write_allowed_inside_save"] = allowed_inside
        if not allowed_inside:
            ss["_music_last_cloud_write_error"] = "music_egress_strict"
            return False
    except ImportError:
        pass

    cloud_error = ""
    saved_cloud = False
    cloud_result = None
    try:
        from music_page_save_pipeline_trace import (
            payload_pages_from_state,
            record_checkpoint,
            upsert_impl_marker,
        )

        record_checkpoint(
            ss,
            "E_pre_supabase_upsert",
            payload=state,
            extra={
                "upsert_impl_marker": upsert_impl_marker,
                "write_path": write_path,
                "payload_pages": payload_pages_from_state(state),
                "page_arg": page,
            },
        )
    except ImportError:
        pass
    try:
        cloud_result = save_cloud_full_session(
            APP_ID,
            state,
            page=page,
            summary=summary,
            strict_egress_approval=approval,
        )
        saved_cloud = bool(cloud_result.success)
        if not saved_cloud:
            stage = str(getattr(cloud_result, "failure_stage", "") or "unknown")
            exc = str(getattr(cloud_result, "exception", "") or "").strip()
            cloud_error = f"save_cloud_full_session:{stage}" + (f":{exc}" if exc else "")
            ss["_music_last_cloud_save_diag"] = cloud_result.to_diag()
    except Exception as exc:
        cloud_error = str(exc)
    record_music_cloud_write_result(
        st,
        state,
        write_path=write_path,
        saved_cloud=saved_cloud,
        cloud_error=cloud_error,
    )
    if saved_cloud:
        readback: dict[str, Any] = {}
        try:
            from music_egress_config import skip_cloud_readback_after_write

            do_readback = not skip_cloud_readback_after_write(APP_ID, st=st)
        except ImportError:
            do_readback = True
        if do_readback:
            try:
                from suite_cloud_state import load_cloud_full_session

                readback, _ = load_cloud_full_session(APP_ID)
            except Exception:
                readback = {}
        if isinstance(readback, dict) and readback:
            record_transposing_save_diagnostics(
                st,
                state,
                phase="cloud_readback",
                write_path=write_path,
                readback_payload=readback,
            )
    return saved_cloud


def stamp_music_payload_for_write(
    st: Any,
    state: dict[str, Any],
    *,
    explicit_reason: str = "",
    write_path: str = "",
) -> dict[str, Any]:
    """Authoritative pre-write stamp used by every music disk/cloud persist path."""
    if not isinstance(state, dict):
        return state
    try:
        pending = sync_page_change_write_pending_for_music_save(st)
        write_reason = "page_change" if pending else resolve_music_save_reason_at_write(st, explicit_reason)
        state, trace, meta = apply_music_pre_write_stamp(st, state, save_reason=write_reason)
        record_music_pre_write_diagnostics(st, trace, meta, write_path=write_path or "unknown")
    except Exception as exc:
        ss = st.session_state
        ss["music_pre_write_path"] = write_path or "unknown"
        ss["music_pre_write_stamp_ran"] = False
        ss["page_change_finalize_ran"] = False
        ss["page_change_finalize_error"] = str(exc)
        ss["_music_save_reason_at_write"] = resolve_music_save_reason_at_write(st, explicit_reason)
    return state


def ensure_music_payload_stamped_for_session(
    st: Any,
    state: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Re-stamp persist blob when session normalized page drifted from payload (any save path)."""
    ss = st.session_state
    target, source = _page_change_write_target(ss)
    if not target:
        target, source = _normalized_session_studio_page_for_save(ss)
    if not target:
        return state, {}
    snap = _payload_page_snapshot(state)
    core_page = _normalize_studio_page_for_save(snap.get("core"))
    ws_page = _normalize_studio_page_for_save(snap.get("workspace"))
    nav_page = _normalize_studio_page_for_save(snap.get("studio_nav"))
    if core_page == target and ws_page == target and nav_page == target:
        return state, {}
    pre = _payload_page_snapshot(state)
    post_trace = _stamp_live_studio_page_into_save_payload(
        state,
        target,
        source=source or "normalized_studio_page",
        coach_page=target,
    )
    post = _payload_page_snapshot(state)
    final_page = _studio_page_from_save_state(state) or target
    trace = _sync_save_payload_trace_fields(
        {
            **post_trace,
            "page_change_finalize_target": target,
            "page_change_finalize_source": source,
            "pre_stamp_core_page": pre.get("core") or None,
            "pre_stamp_session_page": pre.get("session") or None,
            "pre_stamp_workspace_page": pre.get("workspace") or None,
            "pre_stamp_studio_nav_page": pre.get("studio_nav") or None,
            "post_stamp_core_page": post.get("core") or None,
            "post_stamp_session_page": post.get("session") or None,
            "post_stamp_workspace_page": post.get("workspace") or None,
            "post_stamp_studio_nav_page": post.get("studio_nav") or None,
            "cloud_write_studio_page": final_page or None,
            "final_payload_studio_page": final_page or None,
            "final_payload_source": source or "normalized_studio_page",
            "page_change_finalize_ran": True,
        }
    )
    return state, trace


def _apply_page_change_stamp_to_session(session: dict[str, Any], target: str) -> None:
    """Force live session + workspace blobs to the page_change target before payload build."""
    page = _normalize_studio_page_for_save(target)
    if not page:
        return
    session["studio_page"] = page
    nav = session.get("studio_nav_state")
    if isinstance(nav, dict):
        nav = copy.deepcopy(nav)
        nav["studio_page"] = page
        nav["page"] = page
        nav["last_write_reason"] = nav.get("last_write_reason") or "page_change_save_stamp"
        session["studio_nav_state"] = nav
    else:
        session["studio_nav_state"] = {
            "studio_page": page,
            "page": page,
            "last_write_reason": "page_change_save_stamp",
        }
    ws = session.get("music_workspace_state")
    if isinstance(ws, dict):
        ws = copy.deepcopy(ws)
        ws["studio_page"] = page
        ws["page"] = page
        session["music_workspace_state"] = ws
    else:
        session["music_workspace_state"] = {"studio_page": page, "page": page}
    try:
        from music_coach_context import sync_music_coach_workspace_page

        sync_music_coach_workspace_page(session)
    except Exception:
        pass


def _mirror_page_change_save_session(st: Any, ss: dict[str, Any], page_id: str) -> None:
    """When ``session_state`` arg differs from ``st.session_state``, mirror stamped nav into build target."""
    build_ss = getattr(st, "session_state", None)
    if build_ss is None or build_ss is ss:
        return
    target = _normalize_studio_page_for_save(page_id)
    if not target:
        return
    _apply_page_change_stamp_to_session(ss, target)
    _apply_page_change_stamp_to_session(build_ss, target)
    for key in (
        "_suite_page_user_nav",
        "active_page_source",
        "requested_page",
        _PAGE_CHANGE_STAMP_TARGET_KEY,
        _PAGE_CHANGE_WRITE_PENDING_KEY,
        "_suite_page_change_save_page",
    ):
        if key in ss:
            build_ss[key] = ss[key]
        elif key in (
            _PAGE_CHANGE_STAMP_TARGET_KEY,
            _PAGE_CHANGE_WRITE_PENDING_KEY,
            "_suite_page_change_save_page",
        ):
            build_ss[key] = target


def _clear_page_change_save_hints(session: dict[str, Any]) -> None:
    _clear_page_change_write_pending(session)


def _page_change_save_ready(session: dict[str, Any], target_page: str) -> bool:
    """True when live session/nav/ownership/workspace all match the nav target."""
    target = _normalize_studio_page_for_save(target_page)
    if not target:
        return False
    if _normalize_studio_page_for_save(session.get("studio_page")) != target:
        return False
    if _studio_nav_page_from_session(session) != target:
        return False
    if not bool(session.get("_suite_page_user_nav")):
        return False
    ws = session.get("music_workspace_state")
    if isinstance(ws, dict):
        ws_page = _normalize_studio_page_for_save(ws.get("studio_page"))
        if ws_page and ws_page != target:
            return False
    return True


def prepare_page_change_save_state(
    session: dict[str, Any],
    target_page: str,
    *,
    st: Any | None = None,
    origin: str | None = None,
) -> str:
    """Stamp live nav/workspace/ownership before page_change cloud save."""
    try:
        from music_page_save_pipeline_trace import prepare_save_impl_marker, record_pipeline_event

        record_pipeline_event(
            session,
            function="prepare_page_change_save_state",
            phase="entry",
            selected_target=_normalize_studio_page_for_save(target_page),
            extra={"prepare_save_impl_marker": prepare_save_impl_marker, "origin_arg": origin},
        )
    except ImportError:
        pass
    try:
        from music_startup_save_suppression import get_page_change_origin, set_page_change_origin

        nav_origin = str(origin or get_page_change_origin(session) or "unknown").strip()
        if origin:
            set_page_change_origin(session, nav_origin)
        elif session.get("startup_suppression_armed") and not session.get("startup_suppression_released"):
            nav_origin = "reconciliation"
            set_page_change_origin(session, nav_origin)
        elif nav_origin == "unknown" and not session.get("startup_suppression_released"):
            nav_origin = "reconciliation"
            set_page_change_origin(session, nav_origin)
    except ImportError:
        nav_origin = str(origin or "user_navigation")
    user_nav = nav_origin == "user_navigation"
    page = _normalize_studio_page_for_save(target_page) or _normalize_studio_page_for_save(
        session.get("studio_page")
    )
    if not page:
        return ""
    session["studio_page"] = page
    synchronize_page_bearing_state_for_save(session, page)
    try:
        from studio_nav_state import write_canonical_studio_nav_state

        write_canonical_studio_nav_state(
            session,
            page,
            reason="page_change" if user_nav else "workspace_restore",
            local_edit=user_nav,
        )
    except ImportError:
        session["studio_nav_state"] = {
            "studio_page": page,
            "page": page,
            "last_write_reason": "page_change" if user_nav else "workspace_restore",
        }
        if user_nav:
            session["_suite_page_user_nav"] = True

    if user_nav:
        session["_suite_page_user_nav"] = True
        session["active_page_source"] = "user_sidebar"
    else:
        session.pop("_suite_page_user_nav", None)
        session["active_page_source"] = nav_origin if nav_origin != "unknown" else "cloud_restore"
    session["requested_page"] = page
    if user_nav:
        try:
            from suite_user_persistence import SESSION_USER_OWNED_PAGE_KEY

            session[SESSION_USER_OWNED_PAGE_KEY] = page
        except ImportError:
            session["_suite_user_owned_page"] = page

        if st is not None:
            try:
                from suite_user_persistence import claim_user_page_ownership

                claim_user_page_ownership(st, APP_ID, page)
            except Exception:
                pass

    ws = session.get("music_workspace_state")
    if isinstance(ws, dict):
        ws = copy.deepcopy(ws)
    else:
        ws = {}
    ws["studio_page"] = page
    try:
        from music_coach_context import resolve_coach_source_page

        ws["page"] = resolve_coach_source_page({**session, **ws})
    except Exception:
        ws["page"] = page
    session["music_workspace_state"] = ws
    try:
        from music_coach_context import sync_music_coach_workspace_page

        sync_music_coach_workspace_page(session)
    except Exception:
        pass
    try:
        from music_page_save_pipeline_trace import record_pipeline_event

        record_pipeline_event(
            session,
            function="prepare_page_change_save_state",
            phase="exit",
            selected_target=page,
            branch="user_nav" if user_nav else nav_origin,
        )
    except ImportError:
        pass
    return page


def maybe_flush_deferred_page_change_save(st: Any) -> bool:
    """Run a deferred page_change save after canonical nav catches up (next rerun)."""
    ss = st.session_state
    try:
        from music_startup_save_suppression import (
            clear_startup_deferred_page_change_saves,
            record_startup_save_suppressed,
            should_suppress_music_workspace_save,
        )

        suppress, why = should_suppress_music_workspace_save(ss, "page_change")
        if suppress:
            record_startup_save_suppressed(ss, why)
            clear_startup_deferred_page_change_saves(ss)
            _clear_page_change_write_pending(ss)
            return False
    except ImportError:
        pass
    deferred = _normalize_studio_page_for_save(ss.get("_suite_deferred_page_change_save"))
    if not deferred:
        return False
    try:
        from music_startup_save_suppression import set_page_change_origin

        set_page_change_origin(ss, "reconciliation")
    except ImportError:
        pass
    prepare_page_change_save_state(ss, deferred, st=st, origin="reconciliation")
    if not _page_change_save_ready(ss, deferred):
        return False
    ss.pop("_suite_deferred_page_change_save", None)
    _mark_page_change_write_pending(ss, deferred)
    build_ss = getattr(st, "session_state", ss)
    _mirror_page_change_save_session(st, ss, deferred)
    if build_ss is not ss:
        _mark_page_change_write_pending(build_ss, deferred)
    ok = force_save_music_state(st, reason="page_change")
    if ok:
        try:
            from suite_user_persistence import _release_user_page_ownership_after_save

            _release_user_page_ownership_after_save(st, deferred)
        except ImportError:
            pass
        ss["_suite_last_persisted_page"] = deferred
    return ok


def _last_persisted_studio_page_for_save(session: dict[str, Any]) -> str:
    return _normalize_studio_page_for_save(session.get("_suite_last_persisted_page"))


def _resolve_live_studio_page_for_save(ss: dict[str, Any], *, save_reason: str) -> tuple[str, str]:
    """Authoritative studio page for save payload (page_change must not use restored blob)."""
    if save_reason == "page_change":
        return _resolve_page_change_stamp_target(ss)
    live = _normalize_studio_page_for_save(ss.get("studio_page"))
    reason = str(save_reason or "autosave").strip() or "autosave"
    if reason in _PRESERVE_USER_NAV_SAVE_REASONS:
        last = _last_persisted_studio_page_for_save(ss)
        user_nav = bool(ss.get("_suite_page_user_nav"))
        if last and not user_nav:
            if not live or live != last:
                return last, "_suite_last_persisted_page"
        if last and user_nav and live and live == last:
            return live, "session_state.studio_page"
    return live, "session_state.studio_page" if live else "missing"


def _stamp_live_studio_page_into_save_payload(
    state: dict[str, Any],
    page: str,
    *,
    source: str = "session_state.studio_page",
    coach_page: str = "",
) -> dict[str, str]:
    """Force raw ``studio_page`` id into every cross-device sync field (not coach aliases)."""
    normalized = str(page or "").strip()
    trace: dict[str, str] = {
        "save_payload_source": source,
        "save_payload_core_page": "",
        "save_payload_session_page": "",
        "save_payload_workspace_page": "",
        "save_payload_studio_nav_page": "",
    }
    if not normalized:
        return trace
    core = state.get("core")
    if isinstance(core, dict):
        core["studio_page"] = normalized
        core["page"] = normalized
        trace["save_payload_core_page"] = normalized
    session_extra = state.get("session")
    if isinstance(session_extra, dict):
        session_extra["studio_page"] = normalized
        trace["save_payload_session_page"] = normalized
    meta = state.get("music_workspace_state")
    if isinstance(meta, dict):
        meta["studio_page"] = normalized
        meta["page"] = coach_page or normalized
        trace["save_payload_workspace_page"] = normalized
    nav_meta = state.get("studio_nav_state")
    if isinstance(nav_meta, dict):
        nav_meta["studio_page"] = normalized
        nav_meta["page"] = normalized
        trace["save_payload_studio_nav_page"] = normalized
    else:
        state["studio_nav_state"] = {
            "studio_page": normalized,
            "page": normalized,
            "last_write_reason": "page_change_save_stamp",
        }
        trace["save_payload_studio_nav_page"] = normalized
    state["studio_page"] = normalized
    return trace


def _sync_studio_page_into_music_blob(
    st: Any,
    state: dict[str, Any],
    *,
    save_reason: str = "autosave",
) -> dict[str, str]:
    if not hasattr(st, "session_state"):
        return {}
    ss = st.session_state
    page, source = _resolve_live_studio_page_for_save(ss, save_reason=save_reason)
    coach_page = ""
    if page and save_reason != "page_change":
        try:
            from music_coach_context import resolve_coach_source_page

            merged = {**ss}
            core = state.get("core")
            session_extra = state.get("session")
            if isinstance(core, dict):
                merged.update(core)
            if isinstance(session_extra, dict):
                merged.update(session_extra)
            coach_page = resolve_coach_source_page(merged)
        except Exception:
            coach_page = page
    elif page:
        coach_page = page
    return _stamp_live_studio_page_into_save_payload(
        state,
        page,
        source=source,
        coach_page=coach_page,
    )


def _build_workspace_envelope(st: Any, state: dict[str, Any], *, save_reason: str) -> dict[str, Any]:
    core = state.get("core") if isinstance(state.get("core"), dict) else {}
    session_extra = state.get("session") if isinstance(state.get("session"), dict) else {}
    coach_page = ""
    try:
        from music_coach_context import resolve_coach_source_page, sync_music_coach_workspace_page

        merged = {**core, **session_extra}
        if hasattr(st, "session_state"):
            merged = {**dict(st.session_state), **merged}
        sync_music_coach_workspace_page(merged)
        coach_page = resolve_coach_source_page(merged)
    except Exception:
        coach_page = str((core or {}).get("studio_page") or session_extra.get("studio_page") or "")
    active_song_meta = state.get("active_song_state") if isinstance(state.get("active_song_state"), dict) else {}
    active_sel = (
        active_song_meta.get("selected_song")
        if isinstance(active_song_meta.get("selected_song"), dict)
        else {}
    )
    active_pk = str(active_song_meta.get("pick_key") or (core or {}).get("pick_key") or "").strip()
    active_title = str(active_sel.get("title") or (core or {}).get("song") or "").strip()
    active_artist = str(active_sel.get("artist") or (core or {}).get("artist") or "").strip()
    active_genre = str(active_sel.get("genre") or "").strip()
    if not active_genre and active_pk and "::" in active_pk:
        active_genre = active_pk.split("::", 1)[0]
    active_original_key = str(active_sel.get("key") or active_song_meta.get("original_key") or "").strip()
    active_source = (
        active_song_meta.get("music_source")
        or session_extra.get("active_music_source")
        or (core or {}).get("music_source")
        or ("custom_progression" if active_pk.startswith("custom::") else "catalog" if active_pk else "")
    )
    studio_nav_meta = state.get("studio_nav_state") if isinstance(state.get("studio_nav_state"), dict) else {}
    practice_meta = state.get("practice_state") if isinstance(state.get("practice_state"), dict) else {}
    live_studio = ""
    if hasattr(st, "session_state"):
        ss_ref = st.session_state
        live_studio, _ = _resolve_live_studio_page_for_save(ss_ref, save_reason=save_reason)
    if save_reason == "page_change" and live_studio:
        coach_page = live_studio
    if save_reason == "page_change" and live_studio:
        studio_page = live_studio
    else:
        studio_page = (
            live_studio
            or studio_nav_meta.get("studio_page")
            or (core or {}).get("studio_page")
            or session_extra.get("studio_page")
        )
    try:
        from workspace_revision import bump_workspace_revision

        workspace_revision = bump_workspace_revision(st.session_state) if hasattr(st, "session_state") else 0
    except ImportError:
        workspace_revision = 0
    return {
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "workspace_revision": workspace_revision,
        "updated_at": _utc_now_iso(),
        "device_id": _get_device_id(st),
        "save_reason": save_reason or "autosave",
        "workspace_id": _active_workspace_id(st),
        "page": coach_page or studio_page,
        "studio_page": studio_page,
        "pick_key": active_song_meta.get("pick_key") or (core or {}).get("pick_key"),
        "instrument": active_song_meta.get("instrument") or (core or {}).get("instrument"),
        "display_key": active_song_meta.get("display_key") or (core or {}).get("display_key"),
        "active_song": {
            "pick_key": active_pk or None,
            "title": active_title or None,
            "artist": active_artist or None,
            "genre": active_genre or None,
            "original_key": active_original_key or None,
            "source_type": active_source or None,
            "display_key": active_song_meta.get("display_key") or (core or {}).get("display_key"),
            "instrument": active_song_meta.get("instrument") or (core or {}).get("instrument"),
            "level": active_song_meta.get("level") or (core or {}).get("level"),
            "focus": active_song_meta.get("focus") or (core or {}).get("focus"),
            "music_source": active_source,
            "custom_progression_name": active_song_meta.get("custom_progression_name"),
            "custom_home_key": active_song_meta.get("custom_home_key"),
            "show_chart_in_instrument_key": bool(
                active_song_meta.get("show_chart_in_instrument_key", False)
            ),
            **(
                {"_chart_written_key_instrument_anchor": active_song_meta["_chart_written_key_instrument_anchor"]}
                if active_song_meta.get("_chart_written_key_instrument_anchor")
                else {}
            ),
            **(
                {
                    "selected_transposing_instrument": str(
                        active_song_meta["selected_transposing_instrument"]
                    ).strip()
                }
                if str(active_song_meta.get("selected_transposing_instrument") or "").strip()
                else {}
            ),
            "practice_focus_section": active_song_meta.get("practice_focus_section")
            or practice_meta.get("practice_focus_section")
            or (core or {}).get("practice_focus_section"),
        },
        "practice_filters": {
            "practice_focus_section": practice_meta.get("practice_focus_section")
            or active_song_meta.get("practice_focus_section"),
            "practice_groove_style": practice_meta.get("practice_groove_style"),
            "practice_minutes": practice_meta.get("practice_minutes"),
            "practice_notation_lines": practice_meta.get("practice_notation_lines"),
            "practice_notation_difficulty": practice_meta.get("practice_notation_difficulty"),
            "last_practice_mode": practice_meta.get("last_practice_mode"),
        },
        "backing_filters": _backing_filters_for_envelope(st, state, save_reason=save_reason),
        "practice_workspace_state": (
            state.get("practice_workspace_state")
            if isinstance(state.get("practice_workspace_state"), dict)
            else {}
        ),
        "creative_workspace_state": (
            state.get("creative_workspace_state")
            if isinstance(state.get("creative_workspace_state"), dict)
            else {}
        ),
    }


def _backing_filters_for_envelope(st: Any, state: dict[str, Any], *, save_reason: str = "autosave") -> dict[str, Any]:
    try:
        from backing_track_state import backing_filters_for_workspace_envelope

        session_ref = st.session_state if hasattr(st, "session_state") else {}
        return backing_filters_for_workspace_envelope(session_ref, state_blob=state)
    except ImportError:
        backing_meta = state.get("backing_track_state") if isinstance(state.get("backing_track_state"), dict) else {}
        return {
            "backing_track_scope": backing_meta.get("backing_track_scope"),
            "backing_track_single_section": backing_meta.get("backing_track_single_section"),
            "backing_track_multi_sections": backing_meta.get("backing_track_multi_sections"),
            "backing_track_loops": backing_meta.get("backing_track_loops"),
            "backing_track_bpm": backing_meta.get("backing_track_bpm"),
            "backing_groove_style": backing_meta.get("backing_groove_style"),
            "backing_volume": backing_meta.get("backing_volume"),
            "backing_time_signature": backing_meta.get("backing_time_signature"),
            "backing_time_signature_override": backing_meta.get("backing_time_signature_override"),
            "backing_quick_section": backing_meta.get("backing_quick_section"),
        }


def build_music_disk_state(st: Any) -> dict[str, Any]:
    ss = st.session_state
    try:
        from music_page_save_pipeline_trace import build_disk_impl_marker, record_pipeline_event

        record_pipeline_event(
            ss,
            function="build_music_disk_state",
            phase="entry",
            extra={"build_disk_impl_marker": build_disk_impl_marker},
        )
    except ImportError:
        pass
    try:
        from studio_page_persistence import flush_current_page_snapshot

        flush_current_page_snapshot(ss)
    except ImportError:
        pass
    save_reason = str(ss.get("_suite_pending_save_reason") or "autosave")
    ss["_music_build_save_reason"] = save_reason
    page_change_target = ""
    page_change_source = ""
    if save_reason == "page_change":
        explicit = _normalize_studio_page_for_save(ss.get(_PAGE_CHANGE_STAMP_TARGET_KEY))
        if explicit:
            _apply_page_change_stamp_to_session(ss, explicit)
        page_change_target, page_change_source = _page_change_write_target(ss)
        if page_change_target:
            synchronize_page_bearing_state_for_save(ss, page_change_target)
            ss[_PAGE_CHANGE_STAMP_TARGET_KEY] = page_change_target
            ss["_music_build_page_change_target"] = page_change_target
    try:
        from active_song_state import commit_active_song_state_from_session
        from backing_track_state import commit_backing_state_from_session
        from practice_state import commit_practice_state_from_session
        from studio_nav_state import commit_studio_nav_from_session

        commit_active_song_state_from_session(ss, reason=save_reason)
        if save_reason not in (
            "song_edit",
            "cpl_draft_edit",
            "practice_edit",
            "backing_edit",
            "page_change",
        ):
            commit_studio_nav_from_session(ss, reason=save_reason)
        commit_practice_state_from_session(ss, reason=save_reason)
        commit_backing_state_from_session(ss, reason=save_reason)
    except ImportError:
        pass
    except Exception as exc:
        ss["_music_commit_error"] = str(exc)
    try:
        from practice_workspace_persistence import (
            practice_workspace_for_envelope,
            sync_practice_workspace_before_persist,
        )

        sync_practice_workspace_before_persist(ss, reason=save_reason)
    except ImportError:
        pass
    try:
        from creative_workspace_state_persistence import sync_creative_workspace_state_before_persist

        sync_creative_workspace_state_before_persist(ss, reason=save_reason)
    except ImportError:
        pass
    core = build_music_local_state(st)
    if ss.get("_music_default_song_ephemeral"):
        for drop_key in ("pick_key", "song", "artist"):
            core.pop(drop_key, None)
    extra: dict[str, Any] = {}
    try:
        from creative_session_state import sync_creative_session_before_persist

        sync_creative_session_before_persist(ss)
    except ImportError:
        pass
    try:
        from improvisation_mission_persistence import sync_mission_workspace_before_persist

        sync_mission_workspace_before_persist(ss)
    except ImportError:
        pass
    for key in _PERSIST_KEYS:
        if key in ss:
            val = copy.deepcopy(ss[key])
            if key == "last_analysis_result":
                try:
                    from analysis_session_persistence import sanitize_analysis_result_for_persist

                    val = sanitize_analysis_result_for_persist(val)
                except ImportError:
                    pass
            if key == "last_analysis_audio" and isinstance(val, bytes):
                try:
                    from studio_page_persistence import _encode_snapshot_value

                    val = _encode_snapshot_value(val)
                except ImportError:
                    pass
            if key == "mt_tracks" and isinstance(val, dict):
                try:
                    from multitrack_session_persistence import (
                        count_mt_layers,
                        encode_mt_tracks_for_persist,
                        record_multitrack_persist_diag,
                    )

                    if count_mt_layers(val) == 0:
                        continue
                    encoded, diag = encode_mt_tracks_for_persist(val)
                    val = encoded
                    record_multitrack_persist_diag(ss, {"save_diag": diag})
                    ss["_mt_tracks_persist_blob"] = copy.deepcopy(encoded)
                except ImportError:
                    pass
            if key == "mixed_track_wav" and isinstance(val, bytes):
                try:
                    from multitrack_session_persistence import (
                        encode_mixed_track_for_persist,
                        record_multitrack_persist_diag,
                    )

                    encoded, mix_diag = encode_mixed_track_for_persist(val)
                    val = encoded
                    record_multitrack_persist_diag(ss, {"mixed_save_diag": mix_diag})
                except ImportError:
                    try:
                        from studio_page_persistence import _encode_snapshot_value

                        val = _encode_snapshot_value(val)
                    except ImportError:
                        pass
            extra[key] = val
    for key in _LIST_KEYS:
        if key in ss:
            val = ss[key]
            if isinstance(val, list):
                extra[key] = copy.deepcopy(val)
    snapshots = ss.get("_studio_page_snapshots")
    if isinstance(snapshots, dict) and snapshots:
        snap_copy = copy.deepcopy(snapshots)
        try:
            from music_egress_config import sanitize_studio_page_snapshots_for_persist

            snap_copy = sanitize_studio_page_snapshots_for_persist(snap_copy)
        except ImportError:
            pass
        extra["_studio_page_snapshots"] = snap_copy
    try:
        from multitrack_session_persistence import count_mt_layers
        from studio_page_persistence import save_page_snapshot

        if count_mt_layers(ss.get("mt_tracks") or {}) > 0:
            save_page_snapshot(ss, "multitrack")
            snap = copy.deepcopy(ss.get("_studio_page_snapshots") or {})
            mt_snap = snap.get("multitrack")
            if isinstance(mt_snap, dict):
                mt_snap.pop("mt_tracks", None)
                mt_snap.pop("mixed_track_wav", None)
                mt_snap.pop("mt_track_filenames", None)
            extra["_studio_page_snapshots"] = snap
    except ImportError:
        pass
    try:
        from custom_progression_lab import export_cpl_widget_state

        cpl_widgets = export_cpl_widget_state(ss)
        if cpl_widgets:
            extra["_cpl_widget_state"] = cpl_widgets
    except Exception:
        pass
    for key in _INSIGHT_KEYS:
        if key in ss:
            extra[key] = copy.deepcopy(ss[key])
    try:
        from active_song_state import TRANSPOSING_WIDGET_SESSION_KEYS

        for key in TRANSPOSING_WIDGET_SESSION_KEYS:
            if key in ss:
                extra[key] = copy.deepcopy(ss[key])
    except ImportError:
        pass
    state: dict[str, Any] = {"core": core, "session": extra}
    for key in _WORKSPACE_KEYS:
        if key in ss:
            try:
                state[key] = copy.deepcopy(ss[key])
            except Exception:
                state[key] = ss[key]
    try:
        from practice_workspace_persistence import practice_workspace_for_envelope

        state["practice_workspace_state"] = practice_workspace_for_envelope(ss)
    except ImportError:
        pass
    try:
        from creative_workspace_state_persistence import creative_workspace_for_envelope

        state["creative_workspace_state"] = creative_workspace_for_envelope(ss)
    except ImportError:
        pass
    save_reason = str(ss.pop("_suite_pending_save_reason", None) or save_reason)
    if save_reason == "page_change" and not page_change_target:
        page_change_target, page_change_source = _resolve_page_change_stamp_target(ss)
    if save_reason == "page_change" and page_change_target:
        core["studio_page"] = page_change_target
        core["page"] = page_change_target
        extra["studio_page"] = page_change_target
        nav_meta = state.get("studio_nav_state")
        if isinstance(nav_meta, dict):
            nav_meta["studio_page"] = page_change_target
            nav_meta["page"] = page_change_target
    envelope = _build_workspace_envelope(st, state, save_reason=save_reason)
    try:
        from backing_track_state import backing_filters_for_workspace_envelope

        envelope["backing_filters"] = backing_filters_for_workspace_envelope(ss, state_blob=state)
    except ImportError:
        pass
    state["music_workspace_state"] = envelope
    try:
        from backing_track_state import record_backing_disk_payload_trace

        record_backing_disk_payload_trace(ss, state)
    except ImportError:
        pass
    pre_stamp = _payload_page_snapshot(state) if save_reason == "page_change" else {}
    if save_reason == "page_change" and page_change_target:
        stamp_trace = _stamp_live_studio_page_into_save_payload(
            state,
            page_change_target,
            source=page_change_source or _PAGE_CHANGE_STAMP_TARGET_KEY,
            coach_page=page_change_target,
        )
    else:
        stamp_trace = _sync_studio_page_into_music_blob(st, state, save_reason=save_reason)
    if save_reason == "page_change" and page_change_target:
        post_stamp = _payload_page_snapshot(state)
        final_page = _studio_page_from_save_state(state) or page_change_target
        stamp_trace = _sync_save_payload_trace_fields(
            {
                **stamp_trace,
                "pre_stamp_core_page": pre_stamp.get("core") or None,
                "pre_stamp_session_page": pre_stamp.get("session") or None,
                "pre_stamp_workspace_page": pre_stamp.get("workspace") or None,
                "pre_stamp_studio_nav_page": pre_stamp.get("studio_nav") or None,
                "post_stamp_core_page": post_stamp.get("core") or None,
                "post_stamp_session_page": post_stamp.get("session") or None,
                "post_stamp_workspace_page": post_stamp.get("workspace") or None,
                "post_stamp_studio_nav_page": post_stamp.get("studio_nav") or None,
                "cloud_write_studio_page": final_page or None,
                "final_payload_studio_page": final_page or None,
                "final_payload_source": page_change_source or "normalized_studio_page",
            }
        )
    if hasattr(st, "session_state"):
        if stamp_trace:
            ss["_music_save_payload_stamp_trace"] = stamp_trace
        try:
            from music_page_save_history import record_page_bearing_save

            record_page_bearing_save(
                ss,
                reason=save_reason,
                pages={
                    "save_payload_core_page": (stamp_trace or {}).get("save_payload_core_page")
                    or (stamp_trace or {}).get("post_stamp_core_page"),
                    "save_payload_session_page": (stamp_trace or {}).get("save_payload_session_page")
                    or (stamp_trace or {}).get("post_stamp_session_page"),
                    "save_payload_workspace_page": (stamp_trace or {}).get("save_payload_workspace_page")
                    or (stamp_trace or {}).get("post_stamp_workspace_page"),
                    "save_payload_studio_nav_page": (stamp_trace or {}).get("save_payload_studio_nav_page")
                    or (stamp_trace or {}).get("post_stamp_studio_nav_page"),
                    "final_payload_studio_page": (stamp_trace or {}).get("final_payload_studio_page")
                    or (stamp_trace or {}).get("cloud_write_studio_page"),
                },
                cloud_confirmed=ss.get("_suite_persist_last_save_cloud"),
                confirmed_revision=ss.get("_music_last_confirmed_cloud_revision"),
                writer="build_music_disk_state",
            )
        except ImportError:
            pass
        ss["music_workspace_state"] = copy.deepcopy(state["music_workspace_state"])
        if isinstance(state.get("studio_nav_state"), dict):
            ss["studio_nav_state"] = copy.deepcopy(state["studio_nav_state"])
        if isinstance(state.get("backing_track_state"), dict):
            ss["backing_track_state"] = copy.deepcopy(state["backing_track_state"])
    try:
        from music_page_save_pipeline_trace import (
            build_disk_impl_marker,
            payload_pages_from_state,
            record_checkpoint,
        )

        record_checkpoint(
            ss,
            "D_build_music_disk_state_return",
            payload=state,
            extra={
                "build_disk_impl_marker": build_disk_impl_marker,
                "save_reason": save_reason,
                "page_change_target": page_change_target or None,
                "page_change_source": page_change_source or None,
                "payload_pages": payload_pages_from_state(state),
            },
        )
    except ImportError:
        pass
    return state


def apply_music_disk_state(
    st: Any,
    payload: dict[str, Any],
    *,
    song_picker_catalog: dict,
    song_library: dict | None,
    authoritative_restore: bool = False,
) -> None:
    """Apply disk/cloud payload with studio_page ownership protection."""
    ss = st.session_state
    if not authoritative_restore and ss.pop("_music_authoritative_cloud_apply", False):
        authoritative_restore = True
    if authoritative_restore:
        try:
            from songs.music_source import USER_CATALOG_SOURCE_CHOICE_KEY
            from active_song_state import clear_active_song_local_edit

            if not ss.get(USER_CATALOG_SOURCE_CHOICE_KEY):
                clear_active_song_local_edit(ss)
            ss.pop("_active_song_restore_skipped_reason", None)
        except ImportError:
            pass
    try:
        ss["_suite_last_cloud_fetch_payload"] = copy.deepcopy(payload)
    except Exception:
        ss["_suite_last_cloud_fetch_payload"] = payload
    pre_restore_studio_page = str(ss.get("studio_page") or "").strip()
    pre_restore_user_nav = bool(ss.get("_suite_page_user_nav"))
    pre_restore_coach_page = str(ss.get("_music_coach_workspace_page") or "").strip()

    core = payload.get("core") if isinstance(payload.get("core"), dict) else payload
    session_extra = payload.get("session") if isinstance(payload.get("session"), dict) else {}

    preserve_insight = bool(ss.get("_ami_insight_return_preserve"))
    try:
        from applied_math_return_insight import local_ami_insight_should_preserve

        preserve_insight = preserve_insight or local_ami_insight_should_preserve(st)
    except ImportError:
        pass
    for key in _INSIGHT_KEYS:
        if key in session_extra and not preserve_insight:
            ss[key] = copy.deepcopy(session_extra[key])

    ss.pop(SUITE_LOCAL_STATE_RESTORED_KEY, None)
    for key in _WORKSPACE_KEYS:
        if key in payload:
            try:
                ss[key] = copy.deepcopy(payload[key])
            except Exception:
                ss[key] = payload[key]

    try:
        from active_song_workspace_restore import (
            ACTIVE_SONG_WORKSPACE_DIAG_KEY,
            inspect_workspace_envelope_identity,
        )

        ss[ACTIVE_SONG_WORKSPACE_DIAG_KEY] = {
            **inspect_workspace_envelope_identity(payload),
            **(ss.get(ACTIVE_SONG_WORKSPACE_DIAG_KEY) or {}),
        }
    except ImportError:
        pass

    blob_studio = ""
    try:
        from studio_nav_state import _studio_page_from_blob

        blob_studio = _studio_page_from_blob(payload)
    except ImportError:
        blob_studio = ""
    if not blob_studio:
        blob_studio = str((core or {}).get("studio_page") or session_extra.get("studio_page") or "").strip()
        meta = payload.get("music_workspace_state")
        if isinstance(meta, dict) and meta.get("studio_page"):
            blob_studio = str(meta.get("studio_page") or blob_studio).strip()

    applied = False
    defer_catalog_pick = _payload_has_custom_active_signals(payload)
    if isinstance(core, dict) and core:
        core_pk_for_defer = str(core.get("pick_key") or "").strip()
        if core_pk_for_defer and not core_pk_for_defer.startswith("custom::"):
            defer_catalog_pick = False
    if isinstance(core, dict) and core:
        core_for_apply = dict(core)
        if not str(core_for_apply.get("display_key") or "").strip():
            try:
                from active_song_state import _resolve_display_key_from_music_blob

                blob_dk = _resolve_display_key_from_music_blob(payload)
                if blob_dk:
                    core_for_apply["display_key"] = blob_dk
            except ImportError:
                pass
        applied = apply_saved_music_context(
            st,
            core_for_apply,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
            apply_studio_page=False,
            skip_catalog_pick_key=defer_catalog_pick,
        )
        if applied:
            ss[SUITE_LOCAL_STATE_RESTORED_KEY] = True

    if not applied and not (isinstance(core, dict) and core):
        restore_saved_app_state_once(
            st,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
        )

    restore_intermediate_studio_page = str(ss.get("studio_page") or "").strip()
    deferred_transposing_session: dict[str, Any] = {}

    for key, val in session_extra.items():
        if key in _INSIGHT_KEYS and preserve_insight:
            continue
        if key in ("studio_page", "page"):
            continue
        if key == "_studio_page_snapshots" and isinstance(val, dict):
            ss[key] = copy.deepcopy(val)
        elif key == "_cpl_widget_state" and isinstance(val, dict):
            try:
                from custom_progression_lab import (
                    CPL_WIDGETS_INITIALIZED_KEY,
                    import_cpl_widget_state,
                    purge_cpl_ephemeral_widget_keys,
                )

                if authoritative_restore or not ss.get(CPL_WIDGETS_INITIALIZED_KEY):
                    import_cpl_widget_state(ss, val)
                    purge_cpl_ephemeral_widget_keys(ss)
            except Exception:
                pass
        elif key in _LIST_KEYS and isinstance(val, list):
            ss[key] = copy.deepcopy(val)
        elif key in _PERSIST_KEYS:
            if key == "cpl_active_progression" and isinstance(val, dict):
                try:
                    from custom_progression_lab import (
                        CPL_DRAFT_DIRTY_KEY,
                        cpl_draft_chord_count,
                    )

                    if ss.get(CPL_DRAFT_DIRTY_KEY) and not authoritative_restore:
                        continue
                    local = ss.get(key)
                    if (
                        not authoritative_restore
                        and isinstance(local, dict)
                        and cpl_draft_chord_count(local) > cpl_draft_chord_count(val)
                    ):
                        continue
                except Exception:
                    pass
            if key == "last_analysis_result":
                try:
                    from analysis_session_persistence import analysis_result_ready

                    if not analysis_result_ready(val):
                        continue
                except ImportError:
                    pass
            if key == "practice_key_mode" and not authoritative_restore:
                try:
                    from practice_key_mode import MODE_FIXED as _MODE_FIXED

                    local_mode = str(ss.get("practice_key_mode") or "").strip()
                    incoming_mode = str(val or "").strip()
                    if local_mode == _MODE_FIXED and incoming_mode != _MODE_FIXED:
                        continue
                except ImportError:
                    pass
            if key == "fixed_practice_key" and not authoritative_restore:
                try:
                    from practice_key_mode import MODE_FIXED as _MODE_FIXED

                    if str(ss.get("practice_key_mode") or "").strip() == _MODE_FIXED:
                        local_family = str(ss.get("fixed_practice_key") or "").strip()
                        if local_family:
                            continue
                except ImportError:
                    pass
            if key == "fixed_practice_key_family_id" and not authoritative_restore:
                try:
                    from practice_key_mode import MODE_FIXED as _MODE_FIXED

                    if str(ss.get("practice_key_mode") or "").strip() == _MODE_FIXED:
                        local_family_id = str(ss.get("fixed_practice_key_family_id") or "").strip()
                        if local_family_id:
                            continue
                except ImportError:
                    pass
            ss[key] = copy.deepcopy(val)
            if key == "last_analysis_audio":
                try:
                    from studio_page_persistence import _decode_snapshot_value

                    ss[key] = _decode_snapshot_value(ss[key])
                except ImportError:
                    pass
            if key == "mt_tracks":
                try:
                    from multitrack_session_persistence import (
                        decode_mt_tracks_from_persist,
                        record_multitrack_restore_diag,
                    )

                    ss[key] = decode_mt_tracks_from_persist(ss[key])
                    ss["_mt_tracks_persist_blob"] = copy.deepcopy(val)
                    record_multitrack_restore_diag(ss, source="cloud_session_extra")
                except ImportError:
                    pass
            if key == "mixed_track_wav":
                try:
                    from multitrack_session_persistence import (
                        decode_mixed_track_from_persist,
                        record_multitrack_restore_diag,
                    )

                    ss[key] = decode_mixed_track_from_persist(ss[key])
                    record_multitrack_restore_diag(ss, source="cloud_session_extra")
                except ImportError:
                    try:
                        from studio_page_persistence import _decode_snapshot_value

                        ss[key] = _decode_snapshot_value(ss[key])
                    except ImportError:
                        pass
            if key == "cpl_active_progression" and authoritative_restore:
                try:
                    from custom_progression_lab import reset_cpl_widget_initialization

                    reset_cpl_widget_initialization(ss)
                except Exception:
                    pass
                ss["_cpl_reseed_widgets_from_active"] = True
        else:
            try:
                from active_song_state import (
                    ACTIVE_SONG_DIRTY_KEY,
                    ACTIVE_SONG_LOCAL_EDIT_TS_KEY,
                    ACTIVE_SONG_PENDING_SYNC_KEY,
                    TRANSPOSING_WIDGET_SESSION_KEYS,
                )

                if key in TRANSPOSING_WIDGET_SESSION_KEYS:
                    deferred_transposing_session[key] = copy.deepcopy(val)
                    continue
                if key in (
                    ACTIVE_SONG_DIRTY_KEY,
                    ACTIVE_SONG_LOCAL_EDIT_TS_KEY,
                    ACTIVE_SONG_PENDING_SYNC_KEY,
                ):
                    continue
            except ImportError:
                pass
            try:
                from songs.picker_session import WORKSPACE_GENRE_FILTERS_KEY

                if key == WORKSPACE_GENRE_FILTERS_KEY:
                    if ss.get("_genre_filters_user_touched") or ss.get(WORKSPACE_GENRE_FILTERS_KEY):
                        continue
            except ImportError:
                pass
            if not str(key).startswith("_ami_"):
                ss[key] = copy.deepcopy(val)

    if authoritative_restore:
        try:
            from songs.music_source import USER_CATALOG_SOURCE_CHOICE_KEY
            from active_song_state import clear_active_song_local_edit

            if not ss.get(USER_CATALOG_SOURCE_CHOICE_KEY):
                clear_active_song_local_edit(ss)
            ss.pop("_active_song_restore_skipped_reason", None)
        except ImportError:
            pass

    user_owns_page = bool(pre_restore_user_nav)
    active_studio, overwrite_source = blob_studio, "workspace_blob"
    try:
        from studio_nav_state import resolve_studio_page_for_restore

        active_studio, overwrite_source = resolve_studio_page_for_restore(
            ss,
            payload,
            pre_restore_page=pre_restore_studio_page,
            user_owns_page=user_owns_page,
            st=st,
        )
    except ImportError:
        last_persisted = str(ss.get("_suite_last_persisted_page") or "").strip()
        active_studio, overwrite_source = blob_studio or pre_restore_studio_page, "workspace_blob"
        try:
            from applied_math_return_insight import ami_return_navigation_active

            if (
                ami_return_navigation_active(st, APP_ID)
                and pre_restore_studio_page
                and (not blob_studio or pre_restore_studio_page != blob_studio)
            ):
                active_studio = pre_restore_studio_page
                overwrite_source = "ami_return_preserved"
                user_owns_page = True
        except ImportError:
            pass
        if user_owns_page and pre_restore_studio_page and blob_studio and pre_restore_studio_page != blob_studio:
            active_studio = pre_restore_studio_page
            overwrite_source = "user_page_preserved"
        elif pre_restore_studio_page and not blob_studio:
            active_studio = pre_restore_studio_page

    ss["_suite_page_overwrite_source"] = overwrite_source
    ss["_page_restore_overwrite_source"] = overwrite_source
    if active_studio:
        try:
            from music_startup_save_suppression import set_page_change_origin

            set_page_change_origin(ss, "cloud_restore")
        except ImportError:
            pass
        try:
            from music_studio_page_diagnostics import record_studio_page_diag

            record_studio_page_diag(
                ss,
                hydrated_studio_page=active_studio,
                page_restore_overwrite_source=overwrite_source,
            )
        except ImportError:
            pass
        old_hydrated = ss.get("_music_hydrated_studio_page")
        user_nav_page = _normalize_studio_page_for_save(ss.get(MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY))
        if user_nav_page and active_studio and active_studio != user_nav_page:
            active_studio = user_nav_page
            overwrite_source = "user_nav_this_run"
        try:
            from music_phase1_write_journal import record_phase1_page_write

            record_phase1_page_write(
                ss,
                key="_music_hydrated_studio_page",
                old_page=old_hydrated,
                new_page=active_studio,
                module="music_persistent_state",
                function="apply_music_disk_state",
                reason="workspace_restore",
                origin="cloud_restore",
            )
            record_phase1_page_write(
                ss,
                key="studio_page",
                old_page=pre_restore_studio_page,
                new_page=active_studio,
                module="music_persistent_state",
                function="apply_music_disk_state",
                reason=overwrite_source or "workspace_restore",
                origin="cloud_restore",
            )
        except ImportError:
            pass
        ss["studio_page"] = active_studio
        ss["_music_hydrated_studio_page"] = active_studio
        try:
            from studio_nav_state import write_canonical_studio_nav_state

            write_canonical_studio_nav_state(ss, active_studio, reason="workspace_restore")
        except ImportError:
            pass
        try:
            from music_restore_phase import mark_studio_page_restore_projection_complete

            mark_studio_page_restore_projection_complete(ss)
        except ImportError:
            pass

    try:
        from active_song_state import (
            apply_cloud_active_song_state_if_allowed,
            clear_active_song_local_edit,
            is_active_song_locally_dirty,
            sync_active_song_context_from_core,
        )

        if is_active_song_locally_dirty(ss):
            ss["_active_song_restore_skipped_reason"] = "local_dirty"
        elif apply_cloud_active_song_state_if_allowed(ss, payload):
            clear_active_song_local_edit(ss)
        elif isinstance(core, dict) and core:
            blob_custom = False
            try:
                from active_song_state import _custom_context_from_blob

                blob_custom = _custom_context_from_blob(payload) is not None
            except ImportError:
                pass
            if (
                str(ss.get("active_music_source") or "") != "custom_progression"
                and not blob_custom
                and (core.get("pick_key") or core.get("song"))
            ):
                sync_active_song_context_from_core(ss, core)
                clear_active_song_local_edit(ss)
        try:
            from active_song_state import finalize_transposing_receive_restore

            finalize_transposing_receive_restore(
                ss,
                payload,
                deferred_session=deferred_transposing_session,
                source="receive_finalize",
            )
        except ImportError:
            pass
    except ImportError:
        pass

    try:
        from practice_state import (
            apply_cloud_practice_state_if_allowed,
            clear_practice_local_edit,
            is_practice_locally_dirty,
        )
        from practice_workspace_persistence import (
            PRACTICE_WORKSPACE_DIRTY_KEY,
            apply_practice_workspace_from_payload,
        )

        if authoritative_restore:
            clear_practice_local_edit(ss)
            ss.pop(PRACTICE_WORKSPACE_DIRTY_KEY, None)

        if is_practice_locally_dirty(ss) and not authoritative_restore:
            ss["_practice_restore_skipped_reason"] = "local_dirty"
        elif apply_cloud_practice_state_if_allowed(ss, payload, authoritative=authoritative_restore):
            clear_practice_local_edit(ss)
        try:
            from practice_state import prepare_practice_page

            prepare_practice_page(ss)
        except ImportError:
            pass
        try:
            apply_practice_workspace_from_payload(
                ss,
                payload,
                authoritative=authoritative_restore,
            )
        except ImportError:
            pass
    except ImportError:
        pass

    try:
        from creative_workspace_state_persistence import apply_creative_workspace_from_payload
        from improvisation_mission_persistence import clear_mission_workspace_local_edit

        if authoritative_restore:
            clear_mission_workspace_local_edit(ss)
        apply_creative_workspace_from_payload(
            ss,
            payload,
            authoritative=authoritative_restore,
        )
    except ImportError:
        pass

    try:
        from backing_track_state import (
            apply_cloud_backing_state_if_allowed,
            clear_backing_local_edit,
            is_backing_user_dirty,
        )

        if is_backing_user_dirty(ss):
            ss["_backing_restore_skipped_reason"] = "local_dirty"
        elif apply_cloud_backing_state_if_allowed(ss, payload):
            clear_backing_local_edit(ss)
        try:
            from backing_track_state import prepare_backing_page

            prepare_backing_page(ss)
        except ImportError:
            pass
    except ImportError:
        pass

    try:
        from music_coach_context import sync_music_coach_workspace_page

        sync_music_coach_workspace_page(ss)
    except Exception:
        pass

    try:
        from improvisation_mission_persistence import (
            apply_cloud_mission_state_if_allowed,
            is_mission_workspace_locally_dirty,
        )

        if is_mission_workspace_locally_dirty(ss):
            ss["_mission_restore_skipped_reason"] = "local_dirty"
        else:
            apply_cloud_mission_state_if_allowed(ss, payload)
    except ImportError:
        pass

    ss["_suite_cloud_workspace_applied"] = True

    try:
        from custom_progression_lab import reconcile_cpl_restored_session

        reconcile_cpl_restored_session(ss)
    except Exception:
        pass

    try:
        from custom_song_library import merge_custom_songs_from_cloud

        merge_custom_songs_from_cloud(ss, st=st)
    except Exception:
        pass

    if not _session_has_restored_song_context(ss):
        try:
            from active_song_workspace_restore import apply_canonical_active_song_from_workspace

            apply_canonical_active_song_from_workspace(
                st,
                payload,
                song_picker_catalog=song_picker_catalog,
                song_library=song_library,
                allow_migration=False,
                persist_migration=False,
            )
        except ImportError:
            pass

    try:
        _finalize_music_workspace_restore(
            st,
            payload,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
        )
    except Exception:
        pass

    try:
        from creative_session_state import hydrate_creative_session_after_restore

        hydrate_creative_session_after_restore(ss)
    except ImportError:
        pass
    try:
        from improvisation_mission_persistence import hydrate_mission_workspace_after_restore

        hydrate_mission_workspace_after_restore(ss)
    except ImportError:
        pass
    try:
        from creative_workspace_persistence import hydrate_creative_workspace_after_restore

        hydrate_creative_workspace_after_restore(ss)
    except ImportError:
        pass

    try:
        from backing_context import hydrate_backing_context_after_restore

        hydrate_backing_context_after_restore(ss)
    except ImportError:
        pass

    if isinstance(core, dict) and core:
        _reapply_core_practice_globals_from_payload(ss, core)

    try:
        from practice_key_mode import prepare_practice_key_mode_widgets

        if authoritative_restore or ss.get("_music_workspace_blob_hydrated"):
            ss["_practice_key_mode_restored"] = bool(
                ss.get("practice_key_mode") or ss.get("fixed_practice_key_family_id")
            )
        prepare_practice_key_mode_widgets(ss)
        try:
            from practice_key_mode import (
                is_fixed_practice_key_mode,
                normalize_stored_family_option_id,
                set_fixed_practice_key_family,
            )

            if is_fixed_practice_key_mode(ss):
                raw_fam = str(ss.get("fixed_practice_key_family_id") or "").strip()
                norm = normalize_stored_family_option_id(raw_fam)
                if norm and norm != raw_fam:
                    set_fixed_practice_key_family(ss, norm)
                    ss["key_family_overwritten_by_stage"] = "apply_music_disk_state:normalize_family_id"
                elif norm and authoritative_restore:
                    set_fixed_practice_key_family(ss, norm)
        except ImportError:
            pass
    except ImportError:
        pass

    try:
        from key_family_persistence_trace import collect_key_family_persistence_trace

        key_trace = collect_key_family_persistence_trace(ss)
    except ImportError:
        key_trace = {}

    restore_trace = {
        "studio_page_applied": str(ss.get("studio_page") or "").strip(),
        "instrument_applied": str((core or {}).get("instrument") or ss.get("instrument") or "").strip(),
        "level_applied": str((core or {}).get("level") or ss.get("level") or "").strip(),
        "focus_applied": str((core or {}).get("focus") or ss.get("focus") or "").strip(),
        "practice_section_applied": str(
            (core or {}).get("practice_focus_section") or ss.get("practice_focus_section") or ""
        ).strip(),
        "pick_key_applied": str(ss.get("active_catalog_pick_key") or "").strip(),
        "practice_key_mode_applied": str(ss.get("practice_key_mode") or "").strip(),
        "key_family_applied": str(ss.get("fixed_practice_key_family_id") or "").strip(),
        "display_key_applied": str((core or {}).get("display_key") or ss.get("display_key") or "").strip(),
        "practice_tool_applied": str(ss.get("practice_active_tool") or "").strip(),
        "time_pitch_view_applied": str(ss.get("practice_time_pitch_view") or "").strip(),
        "family_spelling_applied": str(ss.get("fixed_practice_key_family_spelling") or "").strip(),
    }
    restore_trace.update(key_trace)
    ss["_music_workspace_restore_trace"] = restore_trace

    try:
        from music_workspace_hydration import mark_workspace_blob_hydrated

        mark_workspace_blob_hydrated(ss)
    except ImportError:
        ss["_music_workspace_blob_hydrated"] = True
    if authoritative_restore:
        try:
            from music_startup_save_suppression import record_hydrated_canonical_fingerprint

            record_hydrated_canonical_fingerprint(ss, payload, stage="apply_music_disk_state")
        except ImportError:
            pass
    try:
        from workspace_revision import stamp_applied_workspace_revision

        stamp_applied_workspace_revision(ss, payload)
    except ImportError:
        pass
    if _session_has_restored_song_context(ss):
        ss["_music_workspace_blob_applied"] = True
    _record_music_startup_restore_diag(
        ss,
        payload,
        restored_studio_page=active_studio or "",
        blob_studio_page=blob_studio or "",
        default_init_called=False,
    )

    try:
        from music_coach_context import resolve_coach_source_page
        from music_persistence_trace import update_trace

        coach_page = resolve_coach_source_page(ss)
        ws_meta = payload.get("music_workspace_state")
        ws_studio = (
            str(ws_meta.get("studio_page") or "").strip()
            if isinstance(ws_meta, dict)
            else ""
        )
        practice_trace: dict[str, Any] = {}
        backing_trace: dict[str, Any] = {}
        try:
            from practice_state import collect_practice_persistence_trace

            practice_trace = collect_practice_persistence_trace(ss, payload=payload)
        except ImportError:
            pass
        try:
            from backing_track_state import collect_backing_persistence_trace

            envelope_payload: dict[str, Any] = {}
            if isinstance(payload.get("music_workspace_state"), dict):
                envelope_payload["music_workspace_state"] = payload["music_workspace_state"]
            if isinstance(payload.get("backing_track_state"), dict):
                envelope_payload["backing_track_state"] = payload["backing_track_state"]
            backing_trace = collect_backing_persistence_trace(
                ss,
                envelope_payload=envelope_payload or None,
                cloud_payload=payload,
            )
        except ImportError:
            pass
        update_trace(
            st,
            studio_page_raw=pre_restore_studio_page or blob_studio,
            normalized_studio_page=coach_page,
            cloud_payload_studio_page=blob_studio or None,
            restored_studio_page=active_studio or blob_studio or None,
            restored_studio_page_source=overwrite_source,
            restore_intermediate_studio_page=restore_intermediate_studio_page or None,
            restore_decision=overwrite_source,
            restore_skip_reason=ss.get("_suite_persist_restore_skip_reason"),
            final_studio_page=ss.get("studio_page"),
            page_owner_flag=bool(ss.get("_suite_page_user_nav")),
            music_workspace_state_studio_page=ws_studio or blob_studio or None,
            **practice_trace,
            **backing_trace,
        )
    except Exception:
        pass

    try:
        from analysis_session_persistence import (
            analysis_result_ready,
            restore_analysis_session,
        )

        if str(ss.get("studio_page") or "") == "analysis" and not analysis_result_ready(
            ss.get("last_analysis_result")
        ):
            restore_analysis_session(ss, st=st)
    except Exception:
        pass


def after_studio_page_change(
    st: Any,
    session_state: dict | None = None,
    *,
    target_page: str | None = None,
) -> None:
    """Persist studio_page to disk/cloud immediately after manual navigation."""
    from suite_user_persistence import _release_user_page_ownership_after_save

    ss = session_state if session_state is not None else st.session_state
    page_id = (
        _normalize_studio_page_for_save(target_page)
        or _normalize_studio_page_for_save(ss.get("studio_page"))
        or "practice"
    )
    try:
        from applied_math_return_insight import ami_return_navigation_active, consume_ami_return_resume

        if ami_return_navigation_active(st, APP_ID):
            consume_ami_return_resume(st, APP_ID)
    except ImportError:
        pass
    try:
        from music_startup_save_suppression import set_page_change_origin

        set_page_change_origin(ss, "user_navigation")
    except ImportError:
        pass
    prepare_page_change_save_state(ss, page_id, st=st, origin="user_navigation")
    try:
        from music_persistence_trace import update_trace

        update_trace(
            st,
            pre_save_studio_page=ss.get("studio_page"),
            pre_save_nav_page=_studio_nav_page_from_session(ss),
            pre_save_page_owner=bool(ss.get("_suite_page_user_nav")),
        )
    except Exception:
        pass
    try:
        from local_nav_trace import record_local_nav_checkpoint

        record_local_nav_checkpoint(
            st,
            "post_navigate_before_save",
            session=ss,
            intent=page_id,
        )
    except ImportError:
        pass
    if not _page_change_save_ready(ss, page_id):
        ss["_suite_deferred_page_change_save"] = page_id
        return
    ss.pop("_suite_deferred_page_change_save", None)
    _mark_page_change_write_pending(ss, page_id)
    build_ss = getattr(st, "session_state", ss)
    _mirror_page_change_save_session(st, ss, page_id)
    if build_ss is not ss:
        _mark_page_change_write_pending(build_ss, page_id)
    force_save_music_state(st, reason="page_change")
    _release_user_page_ownership_after_save(st, page_id)
    ss["_suite_last_persisted_page"] = page_id
    ss.pop("_suite_page_user_nav", None)
    try:
        from music_page_save_history import record_page_click_save_diagnostics

        record_page_click_save_diagnostics(
            ss,
            clicked_page=page_id,
            page_change_origin="user_navigation",
            stamp_trace=ss.get("_music_save_payload_stamp_trace")
            if isinstance(ss.get("_music_save_payload_stamp_trace"), dict)
            else None,
            cloud_confirmed=ss.get("_suite_persist_last_save_cloud"),
            confirmed_revision=ss.get("_music_last_confirmed_cloud_revision"),
        )
    except ImportError:
        pass


def claim_studio_page_ownership(
    st: Any,
    page_id: str,
    session_state: dict | None = None,
) -> None:
    """Manual sidebar navigation wins over stale cloud studio_page restore."""
    ss = session_state if session_state is not None else st.session_state
    page = prepare_page_change_save_state(ss, page_id, st=st)
    if page:
        ss["_suite_last_persisted_page"] = page


def prepare_canonical_music_page_state(
    session: dict[str, Any],
    *,
    song_picker_catalog: dict | None = None,
    song_library: dict | None = None,
    force: bool = False,
) -> None:
    """Phase C: reconcile studio nav + active song + practice + backing canonical blobs."""
    run_seq = int(session.get("_script_run_seq") or 0)
    if not force and session.get("_music_canonical_prepared_for_run") == run_seq:
        return
    try:
        from active_song_state import prepare_active_song_context
        from backing_track_state import prepare_backing_page
        from practice_state import prepare_practice_page
        from studio_nav_state import prepare_studio_nav

        try:
            from songs.key_state import invalidate_backing_cache
            from songs.music_source import (
                apply_pending_catalog_from_picker_before_widgets,
                apply_pending_custom_active_song_activation_before_widgets,
                apply_pending_custom_library_action_before_widgets,
                apply_pending_previous_catalog_restore_before_widgets,
                reconcile_picker_music_source,
            )
            from songs.state import apply_pending_catalog_pick_before_widgets

            class _SessionProxy:
                session_state = session

            reconcile_picker_music_source(session)
            if song_picker_catalog:
                apply_pending_catalog_from_picker_before_widgets(
                    _SessionProxy(),
                    song_picker_catalog=song_picker_catalog,
                    song_library=song_library,
                    invalidate_backing=invalidate_backing_cache,
                )
            apply_pending_custom_active_song_activation_before_widgets(
                _SessionProxy(),
                invalidate_backing=invalidate_backing_cache,
            )
            apply_pending_custom_library_action_before_widgets(
                _SessionProxy(),
                invalidate_backing=invalidate_backing_cache,
            )
            if song_picker_catalog:
                apply_pending_previous_catalog_restore_before_widgets(
                    _SessionProxy(),
                    song_picker_catalog=song_picker_catalog,
                    song_library=song_library,
                    invalidate_backing=invalidate_backing_cache,
                )
                apply_pending_catalog_pick_before_widgets(
                    _SessionProxy(),
                    song_picker_catalog,
                    song_library=song_library,
                    invalidate_backing=invalidate_backing_cache,
                )
            reconcile_picker_music_source(session)
            try:
                from custom_song_library import merge_custom_songs_from_cloud

                page = str(session.get("studio_page") or "").strip()
                saved = session.get("cpl_saved_progressions")
                if page == "picker" and not (isinstance(saved, dict) and saved):
                    merge_custom_songs_from_cloud(session, st=_SessionProxy())
            except Exception:
                pass
        except ImportError:
            pass

        prepare_studio_nav(session)
        if song_picker_catalog:
            session["_reconcile_song_picker_catalog"] = song_picker_catalog
        prepare_active_song_context(session)
        prepare_practice_page(session)
        prepare_backing_page(session)
        try:
            from creative_workspace_state_persistence import prepare_creative_workspace_for_render

            prepare_creative_workspace_for_render(session)
        except ImportError:
            pass
        try:
            from creative_key_sync import is_creative_catalog_pick_frozen
            from music_source_ownership import reconcile_source_ownership

            class _ReconcileProxy:
                session_state = session

            if not is_creative_catalog_pick_frozen(session):
                reconcile_source_ownership(
                    session,
                    st_like=_ReconcileProxy(),
                    reason="prepare_canonical",
                )
            try:
                from songs.music_source import CATALOG_RESTORE_PIN_KEY

                session.pop(CATALOG_RESTORE_PIN_KEY, None)
            except ImportError:
                session.pop("_catalog_restore_pin_pick", None)
        except ImportError:
            pass
        session.pop("_reconcile_song_picker_catalog", None)
    except ImportError:
        pass
    session["_music_canonical_prepared_for_run"] = run_seq


def mark_active_song_edit_pending(session: dict[str, Any]) -> None:
    try:
        from active_song_state import mark_active_song_pending_sync

        mark_active_song_pending_sync(session)
    except ImportError:
        pass


def _clear_canonical_dirty_after_save(session: dict[str, Any], *, reason: str = "") -> None:
    """Clear page-local dirty flags after save; keep active-song dirty until user wins post-restore."""
    _active_song_preserve_reasons = frozenset(
        {
            "song_edit",
            "display_key_change",
            "active_song_edit",
            "last_catalog_restore",
            "catalog_source_switch",
        }
    )
    try:
        from active_song_state import clear_active_song_local_edit
        from backing_track_state import clear_backing_local_edit
        from practice_state import clear_practice_local_edit
        from studio_nav_state import clear_studio_nav_local_edit

        if reason not in _active_song_preserve_reasons:
            clear_active_song_local_edit(session)
        clear_practice_local_edit(session)
        clear_backing_local_edit(session)
        if reason == "page_change":
            clear_studio_nav_local_edit(session)
    except ImportError:
        pass


def flush_practice_edits_and_save(st: Any, *, reason: str = "practice_edit") -> bool:
    """Canonical Practice flush + cross-device force save (Phase C)."""
    try:
        from practice_state import (
            PRACTICE_PENDING_SYNC_KEY,
            flush_practice_edits,
            is_practice_locally_dirty,
        )

        ss = st.session_state
        if ss.get(PRACTICE_PENDING_SYNC_KEY) or is_practice_locally_dirty(ss) or reason == "practice_edit":
            flush_practice_edits(ss, reason=reason)
    except ImportError:
        pass
    ok = force_autosave(st, APP_ID, build_state=build_music_disk_state, reason=reason)
    if ok:
        _record_music_persist_trace(st, reason=reason)
    return ok


def maybe_flush_pending_practice_edits(st: Any) -> None:
    try:
        from practice_state import PRACTICE_PENDING_SYNC_KEY

        if st.session_state.get(PRACTICE_PENDING_SYNC_KEY):
            flush_practice_edits_and_save(st, reason="practice_edit")
    except ImportError:
        pass


def flush_active_song_edits_and_save(st: Any, *, reason: str = "song_edit") -> bool:
    """Canonical active-song flush + cross-device force save (Phase C)."""
    ss = st.session_state
    try:
        from music_startup_save_suppression import should_suppress_music_workspace_save, record_startup_save_suppressed

        suppress, why = should_suppress_music_workspace_save(ss, reason)
        if suppress:
            record_startup_save_suppressed(ss, why)
            return False
    except ImportError:
        pass
    try:
        from active_song_state import (
            ACTIVE_SONG_PENDING_SYNC_KEY,
            flush_active_song_edits,
            is_active_song_locally_dirty,
        )

        ss = st.session_state
        if reason in ("song_edit", "display_key_change", "capo_widget"):
            try:
                from music_persistent_state import clear_music_ephemeral_default_song

                pk = str(ss.get("active_catalog_pick_key") or "").strip()
                sel = ss.get("selected_song")
                if pk or (isinstance(sel, dict) and str(sel.get("pick_key") or "").strip()):
                    clear_music_ephemeral_default_song(ss)
            except ImportError:
                pass
        should_flush = reason not in ("cpl_draft_edit",) and (
            ss.get(ACTIVE_SONG_PENDING_SYNC_KEY)
            or is_active_song_locally_dirty(ss)
            or reason in ("display_key_change", "capo_widget")
        )
        if should_flush:
            flush_active_song_edits(ss, reason=reason)
    except ImportError:
        pass
    ok = force_autosave(st, APP_ID, build_state=build_music_disk_state, reason=reason)
    if ok:
        _record_music_persist_trace(st, reason=reason)
    return ok


def flush_global_control_edits_and_save(st: Any, *, reason: str = "instrument_change") -> bool:
    """Sidebar Instrument/Level/Focus → canonical blob + cloud save."""
    ss = st.session_state
    try:
        from music_startup_save_suppression import should_suppress_music_workspace_save, record_startup_save_suppressed

        suppress, why = should_suppress_music_workspace_save(ss, reason)
        if suppress:
            record_startup_save_suppressed(ss, why)
            return False
    except ImportError:
        pass
    try:
        from active_song_state import flush_global_control_edits

        flush_global_control_edits(ss, reason=reason)
    except ImportError:
        pass
    ok = force_autosave(st, APP_ID, build_state=build_music_disk_state, reason=reason)
    if ok:
        _record_music_persist_trace(st, reason=reason)
    return ok


def maybe_flush_pending_active_song_edits(st: Any) -> None:
    try:
        from active_song_state import ACTIVE_SONG_PENDING_SYNC_KEY
        from music_startup_save_suppression import should_suppress_music_workspace_save, record_startup_save_suppressed

        if should_suppress_music_workspace_save(st.session_state, "song_edit")[0]:
            record_startup_save_suppressed(st.session_state, "pending_active_song_flush_suppressed")
            return

        if st.session_state.get(ACTIVE_SONG_PENDING_SYNC_KEY):
            flush_active_song_edits_and_save(st, reason="song_edit")
    except ImportError:
        pass


def flush_backing_edits_and_save(st: Any, *, reason: str = "backing_edit") -> bool:
    """Canonical Backing flush + cross-device force save (Phase C)."""
    try:
        from backing_track_state import (
            BACKING_PENDING_SYNC_KEY,
            flush_backing_edits,
            is_backing_user_dirty,
        )

        ss = st.session_state
        if is_backing_user_dirty(ss) or (reason == "backing_edit" and ss.get(BACKING_PENDING_SYNC_KEY)):
            flush_backing_edits(ss, reason=reason)
    except ImportError:
        pass
    ok = force_autosave(st, APP_ID, build_state=build_music_disk_state, reason=reason)
    _record_music_persist_trace(st, reason=reason)
    try:
        from backing_track_state import snapshot_backing_path_trace

        snapshot_backing_path_trace(st)
    except ImportError:
        pass
    return ok


def maybe_flush_pending_backing_edits(st: Any) -> None:
    try:
        from backing_track_state import BACKING_PENDING_SYNC_KEY, is_backing_user_dirty

        ss = st.session_state
        if is_backing_user_dirty(ss) and ss.get(BACKING_PENDING_SYNC_KEY):
            flush_backing_edits_and_save(st, reason="backing_edit")
        elif ss.get(BACKING_PENDING_SYNC_KEY):
            ss.pop(BACKING_PENDING_SYNC_KEY, None)
    except ImportError:
        pass


def music_active_song_cloud_drift(
    st: Any,
    cloud_state: dict[str, Any],
    cloud_ts: str | None,
) -> tuple[bool, str]:
    """Detect cross-device drift in CPL draft, display key, capo, and written-key mode."""
    _ = cloud_ts
    if not isinstance(cloud_state, dict) or not cloud_state:
        return False, ""

    ss = st.session_state
    session_blob = cloud_state.get("session")
    cloud_meta = cloud_state.get("active_song_state")
    if not isinstance(cloud_meta, dict):
        try:
            from active_song_state import ACTIVE_SONG_STATE_KEY

            cloud_meta = cloud_state.get(ACTIVE_SONG_STATE_KEY)
        except ImportError:
            cloud_meta = cloud_state.get("active_song_state")

    try:
        from custom_progression_lab import cpl_draft_chord_count

        cloud_cpl = session_blob.get("cpl_active_progression") if isinstance(session_blob, dict) else None
        live_cpl = ss.get("cpl_active_progression")
        if isinstance(cloud_cpl, dict):
            cloud_count = cpl_draft_chord_count(cloud_cpl)
            live_count = cpl_draft_chord_count(live_cpl) if isinstance(live_cpl, dict) else 0
            if cloud_count != live_count:
                return True, f"cpl_chords:{cloud_count}!={live_count}"
            cloud_sections = cloud_cpl.get("original_sections") or {}
            live_sections = (live_cpl or {}).get("original_sections") if isinstance(live_cpl, dict) else {}
            if cloud_sections != live_sections:
                return True, "cpl_sections_drift"
    except ImportError:
        pass

    try:
        from active_song_state import (
            ACTIVE_SONG_STATE_KEY,
            _resolve_display_key_from_music_blob,
        )
        from guitar_capo import CAPO_PERSIST_KEYS
        from instrument_transposition import (
            CHART_IN_INSTRUMENT_KEY_KEY,
            SELECTED_TRANSPOSING_INSTRUMENT_KEY,
        )
    except ImportError:
        return False, ""

    try:
        from practice_key_mode import is_fixed_practice_key_mode

        fixed_mode_active = is_fixed_practice_key_mode(ss)
    except ImportError:
        fixed_mode_active = False

    if not fixed_mode_active:
        cloud_dk = _resolve_display_key_from_music_blob(cloud_state)
        live_dk = str(ss.get("display_key") or "").strip()
        canonical_dk = ""
        if isinstance(cloud_meta, dict):
            canonical_dk = str(cloud_meta.get("display_key") or "").strip()
        if cloud_dk and cloud_dk != live_dk:
            return True, f"display_key:{cloud_dk}!={live_dk or 'empty'}"
        if cloud_dk and canonical_dk and cloud_dk != canonical_dk:
            return True, f"display_key:canonical:{canonical_dk}!={cloud_dk}"
        if cloud_dk and not live_dk:
            return True, f"display_key:cloud_has:{cloud_dk}"

    if isinstance(cloud_meta, dict):
        for key in CAPO_PERSIST_KEYS:
            if key not in cloud_meta:
                continue
            if ss.get(key) != cloud_meta.get(key):
                return True, f"capo:{key}"
        if CHART_IN_INSTRUMENT_KEY_KEY in cloud_meta and CHART_IN_INSTRUMENT_KEY_KEY in ss:
            if bool(ss[CHART_IN_INSTRUMENT_KEY_KEY]) != bool(cloud_meta[CHART_IN_INSTRUMENT_KEY_KEY]):
                return True, "written_key_mode"
        cloud_subtype = str(cloud_meta.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or "").strip()
        live_subtype = str(ss.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or "").strip()
        if cloud_subtype and live_subtype and cloud_subtype != live_subtype:
            return True, "transposing_subtype"

    if isinstance(session_blob, dict):
        for key in CAPO_PERSIST_KEYS:
            if key not in session_blob:
                continue
            if ss.get(key) != session_blob.get(key):
                return True, f"session_capo:{key}"
    return False, ""


def music_content_cloud_drift(
    st: Any,
    cloud_state: dict[str, Any],
    cloud_ts: str | None,
) -> tuple[bool, str]:
    try:
        from practice_workspace_persistence import music_practice_workspace_cloud_drift

        drift, detail = music_practice_workspace_cloud_drift(st, cloud_state, cloud_ts)
        if drift:
            return True, detail
    except ImportError:
        pass
    drift, detail = music_active_song_cloud_drift(st, cloud_state, cloud_ts)
    if drift:
        return True, detail
    try:
        from improvisation_mission_persistence import music_mission_cloud_drift

        return music_mission_cloud_drift(st, cloud_state, cloud_ts)
    except ImportError:
        return False, ""


def prepare_music_workspace(
    st: Any,
    *,
    song_picker_catalog: dict,
    song_library: dict | None,
) -> bool:
    """Authoritative cloud/disk workspace sync before sidebar widgets."""
    ss = st.session_state
    run_seq = int(ss.get("_script_run_seq") or 0)
    try:
        from music_workspace_hydration import can_finalize_music_restore

        if ss.get("_music_workspace_prepared_for_run") == run_seq and can_finalize_music_restore(ss):
            return bool(ss.get("_music_workspace_last_result", False))
        if ss.get("_music_workspace_prepared_for_run") == run_seq:
            ss.pop("_music_workspace_prepared_for_run", None)
    except ImportError:
        if ss.get("_music_workspace_prepared_for_run") == run_seq:
            return bool(ss.get("_music_workspace_last_result", False))

    try:
        from suite_cloud_state import (
            list_active_resume_query_params,
            reconcile_stale_resume_session_flags,
            should_skip_workspace_restore_for_resume,
        )
        from music_persistence_trace import record_music_resume_restore_trace

        cleared = reconcile_stale_resume_session_flags(st, APP_ID)
        live_params = list_active_resume_query_params(st, APP_ID)
        skip = should_skip_workspace_restore_for_resume(st, APP_ID, reconcile_first=False)
        ami_active = False
        try:
            from applied_math_return_insight import ami_return_navigation_active

            ami_active = ami_return_navigation_active(st, APP_ID)
        except ImportError:
            pass
        record_music_resume_restore_trace(
            st,
            live_resume_url_params=live_params,
            stale_resume_flags_cleared=cleared,
            has_resume_query_params_result=bool(live_params),
            should_skip_workspace_restore_for_resume=skip,
            ami_return_navigation_active=ami_active,
        )
    except Exception:
        pass

    def _apply(st_obj: Any, state: dict[str, Any]) -> None:
        apply_music_disk_state(
            st_obj,
            state,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
        )

    import time

    t0 = time.perf_counter()
    result = sync_workspace_protocol(
        st,
        APP_ID,
        apply_state=_apply,
        cloud_first=True,
        content_resync_needed=music_content_cloud_drift,
    )
    try:
        from music_perf_diagnostics import record_span

        record_span(st, "workspace_sync", (time.perf_counter() - t0) * 1000.0)
    except Exception:
        pass
    ss["_music_workspace_prepared_for_run"] = run_seq
    ss["_music_workspace_last_result"] = bool(result)
    try:
        from music_workspace_hydration import (
            can_finalize_music_restore,
            mark_workspace_hydration_attempted,
            mark_workspace_hydration_started,
            record_sync_outcome_after_attempt,
        )

        mark_workspace_hydration_started(ss)
        mark_workspace_hydration_attempted(ss)
        record_sync_outcome_after_attempt(ss, sync_applied=bool(result))
    except ImportError:
        pass
    if result:
        try:
            from music_restore_phase import mark_music_workspace_restore_applied

            mark_music_workspace_restore_applied(ss)
        except ImportError:
            pass
    return result


def _record_music_persist_trace(st: Any, *, reason: str = "") -> None:
    """Update ?dev=1 trace after force/autosave (phone→Dell page sync diagnostics)."""
    try:
        from music_persistence_trace import get_trace, update_trace

        ss = st.session_state
        prior = get_trace(st)
        saved_studio = str(ss.get("studio_page") or "").strip()
        coach_page = ""
        try:
            from music_coach_context import resolve_coach_source_page

            coach_page = resolve_coach_source_page(ss)
        except Exception:
            coach_page = saved_studio
        ws_meta = ss.get("music_workspace_state")
        ws_studio = (
            str(ws_meta.get("studio_page") or "").strip()
            if isinstance(ws_meta, dict)
            else saved_studio
        )
        cloud_updated_at = None
        cloud_fetch_page = ""
        cloud_payload_page = saved_studio
        cloud_payload_source = "session"
        last_write = ss.get("_suite_last_cloud_save_payload")
        try:
            from suite_cloud_state import load_cloud_full_session

            cloud_state, cloud_ts = load_cloud_full_session(APP_ID)
            cloud_updated_at = cloud_ts
            if isinstance(last_write, dict) and ss.get("_suite_persist_last_save_cloud"):
                cloud_state = last_write
                ss["_backing_cloud_payload_source"] = "last_write"
            elif isinstance(cloud_state, dict) and cloud_state:
                ss["_backing_cloud_payload_source"] = "fetch"
            else:
                ss["_backing_cloud_payload_source"] = "none"
            if isinstance(cloud_state, dict) and cloud_state:
                cloud_meta = (
                    cloud_state.get("music_workspace_state")
                    if isinstance(cloud_state.get("music_workspace_state"), dict)
                    else {}
                )
                cloud_core = cloud_state.get("core") if isinstance(cloud_state.get("core"), dict) else {}
                cloud_fetch_page = str(
                    cloud_meta.get("studio_page")
                    or cloud_core.get("studio_page")
                    or ""
                ).strip()
                if cloud_fetch_page:
                    ss["_suite_cloud_fetch_studio_page"] = cloud_fetch_page
        except Exception:
            cloud_state = {}
        practice_trace: dict[str, Any] = {}
        backing_trace: dict[str, Any] = {}
        try:
            from practice_state import collect_practice_persistence_trace

            practice_trace = collect_practice_persistence_trace(
                ss, payload=cloud_state if isinstance(cloud_state, dict) else None
            )
        except ImportError:
            pass
        try:
            from backing_track_state import collect_backing_persistence_trace

            envelope_payload: dict[str, Any] = {}
            ws_local = ss.get("music_workspace_state")
            if isinstance(ws_local, dict):
                envelope_payload["music_workspace_state"] = ws_local
            if isinstance(ss.get("backing_track_state"), dict):
                envelope_payload["backing_track_state"] = ss["backing_track_state"]
            backing_trace = collect_backing_persistence_trace(
                ss,
                envelope_payload=envelope_payload or None,
                cloud_payload=cloud_state if isinstance(cloud_state, dict) else None,
            )
        except ImportError:
            pass
        local_updated_at = ss.get("_suite_persist_debug_disk_ts") or ss.get("_suite_persist_last_save_at")
        stamp_trace = ss.get("_music_save_payload_stamp_trace")
        save_payload_trace: dict[str, Any] = _sync_save_payload_trace_fields(
            dict(stamp_trace) if isinstance(stamp_trace, dict) else {}
        )
        cloud_payload_source = ss.get("_music_cloud_payload_source") or "session"
        if ss.get("_music_cloud_payload_studio_page"):
            cloud_payload_page = str(ss["_music_cloud_payload_studio_page"])
            cloud_payload_source = ss.get("_music_cloud_payload_source") or "last_write"
        elif isinstance(last_write, dict) and ss.get("_suite_persist_last_save_cloud"):
            cloud_payload_source = "last_write"
            cloud_payload_page = _studio_page_from_save_state(last_write) or cloud_payload_page
        elif reason == "page_change" and save_payload_trace.get("cloud_write_studio_page"):
            cloud_payload_source = "cloud_write_trace"
            cloud_payload_page = str(save_payload_trace["cloud_write_studio_page"])
        elif reason == "page_change" and save_payload_trace.get("post_stamp_workspace_page"):
            cloud_payload_source = "post_stamp_trace"
            cloud_payload_page = str(save_payload_trace["post_stamp_workspace_page"])
        elif reason == "page_change" and save_payload_trace.get("save_payload_workspace_page"):
            cloud_payload_source = "save_payload_trace"
            cloud_payload_page = str(save_payload_trace["save_payload_workspace_page"])
        elif reason == "page_change" and ss.get("_music_build_page_change_target"):
            cloud_payload_source = "build_target_inference"
            cloud_payload_page = str(ss["_music_build_page_change_target"])
        elif cloud_fetch_page and not ss.get(_PAGE_CHANGE_WRITE_PENDING_KEY):
            cloud_payload_page = cloud_fetch_page
            cloud_payload_source = "fetch"
        save_payload_trace = _sync_save_payload_trace_fields(save_payload_trace)
        diag_fields = {
            "page_change_finalize_ran": ss.get("page_change_finalize_ran"),
            "page_change_finalize_target": ss.get("page_change_finalize_target"),
            "page_change_finalize_source": ss.get("page_change_finalize_source"),
            "page_change_finalize_error": ss.get("page_change_finalize_error"),
            "save_reason_at_write": ss.get("_music_save_reason_at_write") or reason,
            "cloud_write_studio_page": ss.get("_music_cloud_write_studio_page"),
            "build_save_reason": ss.get("_music_build_save_reason"),
            "build_page_change_target": ss.get("_music_build_page_change_target"),
            "music_pre_write_path": ss.get("music_pre_write_path"),
            "music_pre_write_stamp_ran": ss.get("music_pre_write_stamp_ran"),
            "page_change_write_pending": ss.get(_PAGE_CHANGE_WRITE_PENDING_KEY),
            "page_change_write_coerced": ss.get("page_change_write_coerced"),
            "music_cloud_write_path": ss.get("_music_cloud_write_path"),
            "music_stamp_before_cloud_write_ran": ss.get("_music_stamp_before_cloud_write_ran"),
            "music_disk_build_error": ss.get("_music_disk_build_error"),
            "music_commit_error": ss.get("_music_commit_error"),
            "music_last_cloud_write_ok": ss.get("_music_last_cloud_write_ok"),
            "music_last_cloud_write_error": ss.get("_music_last_cloud_write_error"),
            "force_autosave_ok": ss.get("_music_force_save_ok"),
            "force_autosave_error": ss.get("_suite_force_autosave_error"),
            "music_fallback_page_change_build": ss.get("_music_fallback_page_change_build"),
        }
        for key, val in diag_fields.items():
            if val is not None and (val != "" or key == "page_change_finalize_ran"):
                save_payload_trace[key] = val
        if save_payload_trace.get("cloud_write_studio_page") is None:
            save_payload_trace["cloud_write_studio_page"] = ss.get("_music_cloud_write_studio_page")
        if save_payload_trace.get("final_payload_studio_page"):
            ss["_music_final_payload_studio_page"] = save_payload_trace["final_payload_studio_page"]
        if reason == "page_change":
            for src_key, dst_key in (
                ("post_stamp_core_page", "save_payload_core_page"),
                ("post_stamp_session_page", "save_payload_session_page"),
                ("post_stamp_workspace_page", "save_payload_workspace_page"),
                ("post_stamp_studio_nav_page", "save_payload_studio_nav_page"),
            ):
                post_val = save_payload_trace.get(src_key)
                if post_val:
                    save_payload_trace[dst_key] = post_val
        pre_save_studio = prior.get("pre_save_studio_page")
        pre_save_nav = prior.get("pre_save_nav_page")
        pre_save_owner = prior.get("pre_save_page_owner")
        save_tx: dict[str, Any] = {}
        hydration_diag: dict[str, Any] = {}
        restore_mode_diag: dict[str, Any] = {}
        try:
            from music_workspace_cloud_save import collect_save_transaction_diagnostics
            from music_workspace_cloud_hydration import collect_hydration_diagnostics
            from music_workspace_restore_mode import collect_restore_mode_diagnostics

            save_tx = collect_save_transaction_diagnostics(ss)
            hydration_diag = collect_hydration_diagnostics(ss)
            restore_mode_diag = collect_restore_mode_diagnostics(ss)
            if save_tx.get("force_save_block_reason"):
                backing_trace["force_save_block_reason"] = save_tx["force_save_block_reason"]
            if save_tx.get("cloud_write_error"):
                backing_trace["cloud_write_error"] = save_tx["cloud_write_error"]
        except ImportError:
            pass
        if hydration_diag.get("selected_payload_source"):
            cloud_payload_source = str(hydration_diag["selected_payload_source"])
        update_trace(
            st,
            studio_page_raw=saved_studio or None,
            normalized_studio_page=coach_page,
            cloud_payload_studio_page=cloud_payload_page or None,
            cloud_payload_source=cloud_payload_source,
            music_workspace_state_studio_page=ws_studio or saved_studio or None,
            last_save_cloud=bool(ss.get("_suite_persist_last_save_cloud")),
            force_save_reason=reason or ss.get("_suite_persist_last_save_reason"),
            page_owner_flag=(
                pre_save_owner
                if reason == "page_change" and pre_save_owner is not None
                else bool(ss.get("_suite_page_user_nav"))
            ),
            pre_save_studio_page=pre_save_studio if pre_save_studio is not None else ss.get("studio_page"),
            pre_save_nav_page=(
                pre_save_nav if pre_save_nav is not None else _studio_nav_page_from_session(ss)
            ),
            pre_save_page_owner=(
                pre_save_owner
                if pre_save_owner is not None
                else bool(ss.get("_suite_page_user_nav"))
            ),
            cloud_fetch_studio_page=cloud_fetch_page or ss.get("_suite_cloud_fetch_studio_page"),
            disk_write_studio_page=ss.get("_music_disk_write_studio_page"),
            cloud_updated_at=cloud_updated_at,
            local_updated_at=local_updated_at,
            final_studio_page=ss.get("studio_page"),
            **save_payload_trace,
            **practice_trace,
            **backing_trace,
            **save_tx,
            **hydration_diag,
            **restore_mode_diag,
        )
    except Exception:
        pass


def force_save_music_state(st: Any, *, reason: str = "") -> bool:
    ss = st.session_state
    if ss.get("_music_default_song_ephemeral") and reason in (
        "autosave",
        "force_autosave",
        "",
    ):
        ss["_music_force_save_ok"] = False
        ss["_music_force_save_blocked_reason"] = "ephemeral_default_song"
        try:
            from music_workspace_cloud_save import record_save_transaction

            record_save_transaction(ss, force_save_block_reason="ephemeral_default_song")
        except ImportError:
            pass
        return False
    ok = force_autosave(st, APP_ID, build_state=build_music_disk_state, reason=reason)
    cloud_ok = bool(st.session_state.get("_suite_persist_last_save_cloud"))
    if reason in ("multitrack_upload", "multitrack_layer_save") and not cloud_ok:
        ok = False
        st.session_state["_music_force_save_ok"] = False
        st.session_state["_music_force_save_blocked_reason"] = "multitrack_cloud_save_failed"
    else:
        st.session_state["_music_force_save_ok"] = ok
    if reason in ("multitrack_upload", "multitrack_layer_save"):
        try:
            from multitrack_session_persistence import record_multitrack_persist_diag

            record_multitrack_persist_diag(
                st.session_state,
                {
                    "cloud_save_ok": bool(st.session_state.get("_suite_persist_last_save_cloud")),
                    "save_reason": reason,
                },
            )
        except ImportError:
            pass
    return ok


def autosave_music_state(st: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "skipped": True,
        "disk_ok": False,
        "cloud_attempted": False,
        "cloud_ok": False,
        "cloud_error": None,
    }
    ss = st.session_state
    if ss.get("_music_default_init_this_run") or ss.get("_music_default_song_ephemeral"):
        result["skip_reason"] = "default_init_cooldown"
        try:
            from music_persistence_trace import update_trace

            update_trace(st, autosave_ran=False, autosave_skip_reason="default_init_cooldown")
        except Exception:
            pass
        return result
    try:
        from music_workspace_cloud_save import music_autosave_if_changed

        result = music_autosave_if_changed(st, build_state=build_music_disk_state)
    except ImportError:
        try:
            result = autosave_if_changed(st, APP_ID, build_state=build_music_disk_state)
            if result is None:
                result = {
                    "skipped": True,
                    "disk_ok": False,
                    "cloud_attempted": False,
                    "cloud_ok": False,
                    "cloud_error": None,
                }
        except Exception as exc:
            result = {"error": str(exc), "skipped": True}
    except Exception as exc:
        result["error"] = str(exc)
    try:
        from music_persistence_trace import get_trace, update_trace

        ss = st.session_state
        prior = get_trace(st)
        saved_studio = str(ss.get("studio_page") or "")
        coach_page = ""
        try:
            from music_coach_context import resolve_coach_source_page

            coach_page = resolve_coach_source_page(ss)
        except Exception:
            coach_page = saved_studio
        trace_fields: dict[str, Any] = {
            "autosave_ran": not result.get("skipped", True),
            "cloud_save_success": result.get("cloud_ok"),
            "cloud_save_attempted": result.get("cloud_attempted"),
            "cloud_save_error": result.get("cloud_error"),
            "last_save_source": result.get("last_save_source"),
            "persist_calls_autosave": True,
            "saved_studio_page": saved_studio,
            "studio_page_raw": ss.get("studio_page"),
            "normalized_studio_page": coach_page,
            "cloud_payload_studio_page": (
                ss.get("_music_cloud_payload_studio_page")
                or (
                    ss.get("_music_build_page_change_target")
                    if ss.get(_PAGE_CHANGE_WRITE_PENDING_KEY)
                    else None
                )
                or saved_studio
                or None
            ),
            "last_save_cloud": bool(result.get("cloud_ok")) or bool(ss.get("_suite_persist_last_save_cloud")),
            "force_save_reason": ss.get("_suite_persist_last_save_reason"),
            "passive_autosave_cloud_skip": ss.get("_music_passive_autosave_cloud_skip_reason"),
            "final_studio_page": ss.get("studio_page"),
        }
        if ss.get("_suite_page_user_nav"):
            trace_fields["page_owner_flag"] = True
        elif prior.get("force_save_reason") != "page_change":
            trace_fields["page_owner_flag"] = False
        stamp = ss.get("_music_save_payload_stamp_trace")
        if isinstance(stamp, dict):
            for key in (
                "page_change_finalize_ran",
                "page_change_finalize_target",
                "page_change_finalize_source",
                "page_change_finalize_error",
                "save_reason_at_write",
                "cloud_write_studio_page",
                "final_payload_studio_page",
                "post_stamp_core_page",
                "post_stamp_session_page",
                "post_stamp_workspace_page",
                "post_stamp_studio_nav_page",
                "save_payload_core_page",
                "save_payload_session_page",
                "save_payload_workspace_page",
                "save_payload_studio_nav_page",
                "page_change_write_pending",
                "page_change_write_coerced",
                "music_pre_write_path",
                "music_pre_write_stamp_ran",
                "music_cloud_write_path",
                "music_stamp_before_cloud_write_ran",
                "music_disk_build_error",
                "music_last_cloud_write_error",
            ):
                if stamp.get(key) not in (None, ""):
                    trace_fields[key] = stamp.get(key)
        for key in (
            "music_cloud_write_path",
            "music_stamp_before_cloud_write_ran",
            "music_disk_build_error",
            "music_commit_error",
            "music_last_cloud_write_ok",
            "music_last_cloud_write_error",
            "force_autosave_ok",
            "force_autosave_error",
            "_music_cloud_write_path",
        ):
            ss_key = key if key.startswith("_") or key.startswith("music") else key
            val = ss.get(ss_key) if ss_key != "force_autosave_error" else ss.get("_suite_force_autosave_error")
            if key == "force_autosave_ok":
                val = ss.get("_music_force_save_ok")
            if val is not None and val != "":
                trace_fields[key] = val
        prior_finalize = prior.get("page_change_finalize_ran")
        if prior.get("force_save_reason") == "page_change" and prior_finalize:
            for key in (
                "page_change_finalize_ran",
                "page_change_finalize_target",
                "post_stamp_workspace_page",
                "post_stamp_studio_nav_page",
                "final_payload_studio_page",
                "cloud_write_studio_page",
                "cloud_payload_studio_page",
                "cloud_payload_source",
            ):
                if prior.get(key) not in (None, ""):
                    trace_fields[key] = prior.get(key)
        try:
            from backing_track_state import collect_backing_persistence_trace, resolve_backing_trace_payloads

            envelope_payload, cloud_payload = resolve_backing_trace_payloads(st, ss)
            trace_fields.update(
                collect_backing_persistence_trace(
                    ss,
                    envelope_payload=envelope_payload,
                    cloud_payload=cloud_payload,
                )
            )
        except ImportError:
            pass
        try:
            from music_workspace_cloud_save import collect_save_transaction_diagnostics
            from music_workspace_cloud_hydration import collect_hydration_diagnostics

            trace_fields.update(collect_save_transaction_diagnostics(ss))
            trace_fields.update(collect_hydration_diagnostics(ss))
            tx = collect_save_transaction_diagnostics(ss)
            if tx.get("force_save_block_reason"):
                trace_fields["force_save_block_reason"] = tx["force_save_block_reason"]
            if tx.get("cloud_write_error"):
                trace_fields["cloud_write_error"] = tx["cloud_write_error"]
        except ImportError:
            pass
        update_trace(st, **trace_fields)
        if result.get("cloud_ok"):
            _clear_canonical_dirty_after_save(ss)
        try:
            from suite_cloud_state import load_cloud_full_session

            cloud_state, cloud_ts = load_cloud_full_session(APP_ID)
            if cloud_ts:
                update_trace(st, last_cloud_ts=cloud_ts)
            if isinstance(cloud_state, dict) and cloud_state:
                cloud_core = cloud_state.get("core") if isinstance(cloud_state.get("core"), dict) else {}
                cloud_sess = cloud_state.get("session") if isinstance(cloud_state.get("session"), dict) else {}
                cloud_meta = (
                    cloud_state.get("music_workspace_state")
                    if isinstance(cloud_state.get("music_workspace_state"), dict)
                    else {}
                )
                cloud_page = str(
                    cloud_meta.get("studio_page")
                    or cloud_core.get("studio_page")
                    or cloud_sess.get("studio_page")
                    or ""
                ).strip()
                if cloud_page:
                    st.session_state["_suite_cloud_fetch_studio_page"] = cloud_page
                    update_trace(st, cloud_fetch_studio_page=cloud_page)
        except Exception:
            pass
    except Exception:
        pass
    return result


def restore_music_disk_state_once(
    st: Any,
    *,
    song_picker_catalog: dict,
    song_library: dict | None,
) -> bool:
    """Deprecated — use prepare_music_workspace() instead."""
    return prepare_music_workspace(
        st,
        song_picker_catalog=song_picker_catalog,
        song_library=song_library,
    )


def persist_music_disk_state(st: Any) -> None:
    reason = resolve_music_save_reason_at_write(st)
    state = build_music_disk_state(st)
    state = stamp_music_payload_for_write(
        st,
        state,
        explicit_reason=reason,
        write_path="persist_music_disk_state",
    )
    save_user_state(APP_ID, state)


def reset_music_disk_state(st: Any) -> None:
    reset_user_state(APP_ID)
    st.session_state.pop(SUITE_LOCAL_STATE_RESTORED_KEY, None)
    for key in list(st.session_state.keys()):
        if str(key).startswith("_suite_") or str(key).startswith("_page_initialized"):
            st.session_state.pop(key, None)


def apply_music_session_defaults(st: Any) -> None:
    """Return music session to first-run defaults (not user chart override files)."""
    from picker_song_editor import PICKER_EDITOR_OPEN_KEY

    ss = st.session_state
    for key in (
        "studio_page",
        "instrument",
        "level",
        "focus",
        "display_key",
        "practice_focus_section",
        "backing_track_scope",
        "backing_lead_sheet_open",
        PICKER_EDITOR_OPEN_KEY,
        "chart_edit_mode",
        "_studio_page_snapshots",
        "chart_library_mode",
        "song_search_text",
        "song_search_scope",
        "song_picker_level_filter",
        "workspace_genre_filter",
        "backing_track_loops",
        "backing_track_single_section",
        "backing_groove_style",
        "backing_track_bpm",
        "karaoke_countdown_enabled",
        "karaoke_auto_advance",
        "active_music_source",
        "picker_editor_tab",
        "picker_song_editor_open",
        "last_practice_mode",
        "improv_song_source",
        "creative_lab_analysis_mode",
        "improv_intelligence_tab",
    "creative_improv_intelligence_tab",
        "workspace_genre_filters",
        "backing_track_multi_sections",
        "karaoke_queue",
        "catalog_favorite_pick_keys",
        "song_picker_favorites_only",
        "cpl_active_progression",
        "cpl_saved_progressions",
        "cpl_builder_version",
        "cpl_finished",
        "_cpl_editing_display_key",
        "cpl_last_display_key",
        "_music_coach_workspace_page",
    ):
        ss.pop(key, None)
    try:
        from custom_progression_lab import clear_cpl_widget_state

        clear_cpl_widget_state(ss)
    except Exception:
        pass
    ss.pop(ACTIVE_CATALOG_PICK_KEY, None)
    ss.pop(SELECTED_SONG_STATE_KEY, None)
    ss.pop(SUITE_LOCAL_STATE_RESTORED_KEY, None)
    for key in _WORKSPACE_KEYS:
        ss.pop(key, None)
    try:
        from active_song_state import ACTIVE_SONG_DIRTY_KEY, clear_active_song_local_edit
        from backing_track_state import clear_backing_local_edit
        from practice_state import clear_practice_local_edit
        from studio_nav_state import clear_studio_nav_local_edit

        clear_active_song_local_edit(ss)
        clear_practice_local_edit(ss)
        clear_backing_local_edit(ss)
        clear_studio_nav_local_edit(ss)
        ss.pop(ACTIVE_SONG_DIRTY_KEY, None)
    except ImportError:
        pass
    for key in list(ss.keys()):
        if str(key).startswith("_suite_") or str(key).startswith("_page_initialized"):
            ss.pop(key, None)


def default_reset_music_session(st: Any) -> None:
    """Full music reset: session, disk, and cloud ``full_session`` when available."""
    apply_music_session_defaults(st)
    reset_user_state(APP_ID)
    fresh = build_music_disk_state(st)
    finalize_suite_reset(st, APP_ID, fresh)
    st.session_state.pop(SUITE_LOCAL_STATE_RESTORED_KEY, None)
    st.session_state.pop(f"_suite_autosave_fp::{APP_ID}", None)


def clear_music_workspace_autosave_block(st: Any) -> None:
    clear_workspace_autosave_block(st, APP_ID)

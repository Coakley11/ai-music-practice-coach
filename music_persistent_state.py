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
    "song_picker_favorites_only",
    "cpl_active_progression",
    "cpl_saved_progressions",
    "cpl_builder_version",
    "cpl_edit_section",
    "cpl_finished",
    "_cpl_editing_display_key",
    "cpl_last_display_key",
)

_LIST_KEYS = (
    "workspace_genre_filters",
    "backing_track_multi_sections",
    "karaoke_queue",
    "catalog_favorite_pick_keys",
)

_INSIGHT_KEYS = (
    "_ami_pending_insight",
    "_ami_return_page",
    "_ami_return_context",
    "_ami_dismissed_insight_ids",
    "_ami_dismissed_insight_at",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    return {
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "updated_at": _utc_now_iso(),
        "device_id": _get_device_id(st),
        "save_reason": save_reason or "autosave",
        "page": coach_page or (core or {}).get("studio_page"),
        "studio_page": (core or {}).get("studio_page") or session_extra.get("studio_page"),
        "pick_key": (core or {}).get("pick_key"),
        "instrument": (core or {}).get("instrument"),
        "display_key": (core or {}).get("display_key"),
    }


def build_music_disk_state(st: Any) -> dict[str, Any]:
    ss = st.session_state
    core = build_music_local_state(st)
    extra: dict[str, Any] = {}
    for key in _PERSIST_KEYS:
        if key in ss:
            extra[key] = copy.deepcopy(ss[key])
    for key in _LIST_KEYS:
        if key in ss:
            val = ss[key]
            if isinstance(val, list):
                extra[key] = copy.deepcopy(val)
    snapshots = ss.get("_studio_page_snapshots")
    if isinstance(snapshots, dict) and snapshots:
        extra["_studio_page_snapshots"] = copy.deepcopy(snapshots)
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
    state = {"core": core, "session": extra}
    save_reason = str(ss.pop("_suite_pending_save_reason", None) or "autosave")
    state["music_workspace_state"] = _build_workspace_envelope(st, state, save_reason=save_reason)
    return state


def apply_music_disk_state(
    st: Any,
    payload: dict[str, Any],
    *,
    song_picker_catalog: dict,
    song_library: dict | None,
) -> None:
    """Apply disk/cloud payload with studio_page ownership protection."""
    ss = st.session_state
    pre_restore_studio_page = str(ss.get("studio_page") or "").strip()
    pre_restore_user_nav = bool(ss.get("_suite_page_user_nav"))
    pre_restore_coach_page = str(ss.get("_music_coach_workspace_page") or "").strip()

    core = payload.get("core") if isinstance(payload.get("core"), dict) else payload
    session_extra = payload.get("session") if isinstance(payload.get("session"), dict) else {}

    preserve_insight = bool(ss.get("_ami_insight_return_preserve"))
    for key in _INSIGHT_KEYS:
        if key in session_extra and not preserve_insight:
            ss[key] = copy.deepcopy(session_extra[key])

    ss.pop(SUITE_LOCAL_STATE_RESTORED_KEY, None)
    applied = False
    if isinstance(core, dict) and core:
        applied = apply_saved_music_context(
            st,
            core,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
        )
        if applied:
            ss[SUITE_LOCAL_STATE_RESTORED_KEY] = True

    if not applied and not (isinstance(core, dict) and core):
        restore_saved_app_state_once(
            st,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
        )

    for key, val in session_extra.items():
        if key in _INSIGHT_KEYS and preserve_insight:
            continue
        if key == "_studio_page_snapshots" and isinstance(val, dict):
            ss[key] = copy.deepcopy(val)
        elif key == "_cpl_widget_state" and isinstance(val, dict):
            try:
                from custom_progression_lab import import_cpl_widget_state

                import_cpl_widget_state(ss, val)
            except Exception:
                pass
        elif key in _LIST_KEYS and isinstance(val, list):
            ss[key] = copy.deepcopy(val)
        elif key in _PERSIST_KEYS:
            ss[key] = copy.deepcopy(val)
        elif not str(key).startswith("_ami_"):
            ss[key] = copy.deepcopy(val)

    blob_studio = str((core or {}).get("studio_page") or session_extra.get("studio_page") or "").strip()
    meta = payload.get("music_workspace_state")
    if isinstance(meta, dict) and meta.get("studio_page"):
        blob_studio = str(meta.get("studio_page") or blob_studio).strip()

    last_persisted = str(ss.get("_suite_last_persisted_page") or "").strip()
    user_owns_page = bool(pre_restore_user_nav)
    active_studio = blob_studio or pre_restore_studio_page
    overwrite_source = "workspace_blob"
    if user_owns_page and pre_restore_studio_page and blob_studio and pre_restore_studio_page != blob_studio:
        active_studio = pre_restore_studio_page
        overwrite_source = "user_page_preserved"
    elif pre_restore_studio_page and not blob_studio:
        active_studio = pre_restore_studio_page

    ss["_suite_page_overwrite_source"] = overwrite_source
    if active_studio:
        ss["studio_page"] = active_studio

    try:
        from music_coach_context import sync_music_coach_workspace_page

        sync_music_coach_workspace_page(ss)
    except Exception:
        pass

    ss["_suite_cloud_workspace_applied"] = True


def after_studio_page_change(st: Any, session_state: dict | None = None) -> None:
    """Persist studio_page to disk/cloud immediately after manual navigation."""
    from music_coach_context import resolve_coach_source_page, sync_music_coach_workspace_page
    from suite_user_persistence import _release_user_page_ownership_after_save

    ss = session_state if session_state is not None else st.session_state
    page_id = str(ss.get("studio_page") or "practice")
    claim_studio_page_ownership(st, page_id)
    sync_music_coach_workspace_page(ss)
    coach_page = resolve_coach_source_page(ss)
    force_save_music_state(st, reason="page_change")
    _release_user_page_ownership_after_save(st, coach_page)
    ss["_suite_last_persisted_page"] = coach_page
    ss.pop("_suite_page_user_nav", None)


def claim_studio_page_ownership(st: Any, page_id: str) -> None:
    """Manual sidebar navigation wins over stale cloud studio_page restore."""
    from music_coach_context import resolve_coach_source_page, sync_music_coach_workspace_page
    from suite_user_persistence import claim_user_page_ownership

    page = str(page_id or "").strip()
    if not page:
        return
    ss = st.session_state
    ss["studio_page"] = page
    sync_music_coach_workspace_page(ss)
    coach_page = resolve_coach_source_page(ss)
    claim_user_page_ownership(st, APP_ID, coach_page)
    ss["_suite_last_persisted_page"] = coach_page


def prepare_music_workspace(
    st: Any,
    *,
    song_picker_catalog: dict,
    song_library: dict | None,
) -> bool:
    """Authoritative cloud/disk workspace sync before sidebar widgets."""
    def _apply(st_obj: Any, state: dict[str, Any]) -> None:
        apply_music_disk_state(
            st_obj,
            state,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
        )

    return sync_workspace_protocol(
        st,
        APP_ID,
        apply_state=_apply,
        cloud_first=True,
    )


def force_save_music_state(st: Any, *, reason: str = "") -> bool:
    return force_autosave(st, APP_ID, build_state=build_music_disk_state, reason=reason)


def autosave_music_state(st: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "skipped": True,
        "disk_ok": False,
        "cloud_attempted": False,
        "cloud_ok": False,
        "cloud_error": None,
    }
    try:
        result = autosave_if_changed(st, APP_ID, build_state=build_music_disk_state)
    except Exception as exc:
        result["error"] = str(exc)
    try:
        from music_persistence_trace import update_trace

        core = build_music_disk_state(st).get("core", {})
        if not isinstance(core, dict):
            core = {}
        update_trace(
            st,
            autosave_ran=not result.get("skipped", True),
            cloud_save_success=result.get("cloud_ok"),
            cloud_save_attempted=result.get("cloud_attempted"),
            cloud_save_error=result.get("cloud_error"),
            last_save_source=result.get("last_save_source"),
            persist_calls_autosave=True,
            saved_pick_key=str(core.get("pick_key") or ""),
            saved_display_key=str(core.get("display_key") or ""),
            saved_instrument=str(core.get("instrument") or ""),
            saved_studio_page=str(core.get("studio_page") or core.get("page") or ""),
        )
        try:
            from suite_cloud_state import load_cloud_full_session

            _, cloud_ts = load_cloud_full_session(APP_ID)
            if cloud_ts:
                update_trace(st, last_cloud_ts=cloud_ts)
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
    save_user_state(APP_ID, build_music_disk_state(st))


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

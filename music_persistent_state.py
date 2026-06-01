"""Disk persistence for the Music Practice Coach app."""

from __future__ import annotations

import copy
from typing import Any

from songs.state import (
    ACTIVE_CATALOG_PICK_KEY,
    SELECTED_SONG_STATE_KEY,
    SUITE_LOCAL_STATE_RESTORED_KEY,
    build_music_local_state,
    restore_saved_app_state_once,
)
from suite_user_persistence import (
    autosave_if_changed,
    load_user_state,
    reset_user_state,
    restore_once,
    save_user_state,
)

APP_ID = "music"

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
)

_LIST_KEYS = ("workspace_genre_filters", "backing_track_multi_sections", "karaoke_queue")


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
    return {"core": core, "session": extra}


def apply_music_disk_state(
    st: Any,
    payload: dict[str, Any],
    *,
    song_picker_catalog: dict,
    song_library: dict | None,
) -> None:
    """Apply disk payload after legacy restore hook."""
    core = payload.get("core") if isinstance(payload.get("core"), dict) else payload
    session_extra = payload.get("session") if isinstance(payload.get("session"), dict) else {}

    # Seed session_state for restore_saved_app_state_once from core fields.
    if isinstance(core, dict):
        for k, v in core.items():
            if k in ("pick_key", "song", "artist", "instrument", "focus", "display_key", "level"):
                if v:
                    st.session_state[k] = v
            if k in ("studio_page", "page") and v:
                st.session_state["studio_page"] = v
            if k == "practice_focus_section" and v:
                st.session_state["practice_focus_section"] = v
            if k == "mode" and v:
                st.session_state["last_practice_mode"] = v

    st.session_state.pop(SUITE_LOCAL_STATE_RESTORED_KEY, None)
    restore_saved_app_state_once(
        st,
        song_picker_catalog=song_picker_catalog,
        song_library=song_library,
    )

    for key, val in session_extra.items():
        if key == "_studio_page_snapshots" and isinstance(val, dict):
            st.session_state[key] = copy.deepcopy(val)
        elif key in _LIST_KEYS and isinstance(val, list):
            st.session_state[key] = copy.deepcopy(val)
        else:
            st.session_state[key] = copy.deepcopy(val)


def restore_music_disk_state_once(
    st: Any,
    *,
    song_picker_catalog: dict,
    song_library: dict | None,
) -> bool:
    def _apply(st_obj: Any, state: dict[str, Any]) -> None:
        apply_music_disk_state(
            st_obj,
            state,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
        )

    return restore_once(st, APP_ID, apply_state=_apply)


def autosave_music_state(st: Any) -> None:
    autosave_if_changed(st, APP_ID, build_state=build_music_disk_state)


def persist_music_disk_state(st: Any) -> None:
    save_user_state(APP_ID, build_music_disk_state(st))


def reset_music_disk_state(st: Any) -> None:
    reset_user_state(APP_ID)
    st.session_state.pop(SUITE_LOCAL_STATE_RESTORED_KEY, None)
    for key in list(st.session_state.keys()):
        if str(key).startswith("_suite_") or str(key).startswith("_page_initialized"):
            st.session_state.pop(key, None)


def default_reset_music_session(st: Any) -> None:
    """Clear session keys that should return to app defaults (not user data files)."""
    from picker_song_editor import PICKER_EDITOR_OPEN_KEY

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
    ):
        st.session_state.pop(key, None)
    st.session_state.pop(ACTIVE_CATALOG_PICK_KEY, None)
    st.session_state.pop(SELECTED_SONG_STATE_KEY, None)

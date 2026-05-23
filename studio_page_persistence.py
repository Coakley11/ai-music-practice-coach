"""Per-page session_state snapshots and first-visit-only defaults."""

from __future__ import annotations

import copy
import re
from typing import Any

_LEGACY_IMPROV_CHORD_TILE_KEY = re.compile(r"^improv_(live|motif)_s\d+_c\d+$")

from studio_page_state import (
    init_analysis_page_state,
    init_backing_page_state,
    init_creative_lab_state,
    init_improvisation_state,
    init_practice_page_state,
)

# Keys restored when returning to a page (explicit + prefix rules).
_PAGE_EXPLICIT_KEYS: dict[str, tuple[str, ...]] = {
    "practice": (
        "practice_focus_section",
        "practice_minutes",
        "practice_groove_style",
        "practice_notation_lines",
        "practice_notation_difficulty",
        "practice_notation_sig",
        "practice_notation_result",
        "picker_open_chord_coach",
    ),
    "picker": (
        "chart_library_mode",
        "song_picker_chart_status",
        "song_search_scope",
        "song_picker_level_filter",
        "workspace_genre_filter",
        "global_quick_genre",
        "global_quick_song",
        "selected_song",
        "song_search_query",
        "picker_open_chord_coach",
    ),
    "backing": (
        "backing_track_bpm",
        "backing_groove_style",
        "backing_track_scope",
        "backing_track_loops",
        "backing_track_single_section",
        "backing_track_multi_sections",
        "backing_quick_section",
        "_last_backing_wav",
        "_last_backing_signature",
        "_last_backing_timeline",
        "playback_start_time",
        "current_chord_timeline",
        "selected_sections",
        "bpm",
        "beats_per_bar",
        "_backing_autoplay",
        "_backing_needs_regen",
    ),
    "custom": (
        "cpl_edit_section",
        "cpl_builder_version",
        "cpl_active_progression",
        "cpl_saved_progressions",
        "cpl_name",
        "cpl_original_key",
        "cpl_time_signature",
        "cpl_progression_style",
        "cpl_bpm",
        "cpl_groove_style",
    ),
    "creative": (
        "creative_lab_analysis_mode",
        "creative_lab_last_mode",
        "creative_arrangement_target_style",
        "creative_arrangement_section_focus",
    ),
    "multitrack": (
        "mt_tracks",
        "mt_track_filenames",
        "mt_track_controls",
        "mixed_track_wav",
        "multitrack_backing_music_wav",
    ),
    "analysis": (
        "analysis_mode",
        "analysis_recording_type",
        "analysis_audio_upload",
        "analysis_audio_record",
        "last_analysis_result",
        "last_analysis_audio",
    ),
    "log": (
        "ai_session_builder_minutes",
        "practice_log_insights",
        "_ai_practice_session_plan",
    ),
}

_PAGE_PREFIXES: dict[str, tuple[str, ...]] = {
    "practice": ("practice_", "practice::", "exercise_variation::"),
    "picker": ("picker_", "song_picker_", "chart_library_", "workspace_", "global_quick_"),
    "backing": ("backing_", "backing::", "_follow_", "follow_along::"),
    "custom": ("cpl_",),
    "creative": ("creative_", "improv_"),
    "multitrack": ("mt_", "multitrack_"),
    "analysis": ("analysis_",),
    "log": ("practice_log_", "practice_form"),
}

# Never copy these (shared across pages or too large / volatile).
_SNAPSHOT_BLOCKLIST = frozenset(
    {
        "studio_page",
        "studio_nav_back",
        "studio_nav_forward",
        "_studio_nav_from_history",
        "_studio_active_page_id",
        "_studio_page_snapshots",
        "instrument",
        "level",
        "focus",
        "display_key",
        "openai_api_key_box",
        "tutorial_open",
        "tutorial_step",
        "tutorial_dismissed",
        "tutorial_dismiss_checkbox",
        "tutorial_auto_prompted",
    }
)

_PAGE_INIT_FLAG = "_page_initialized::{page_id}"
_PAGE_SNAPSHOTS_KEY = "_studio_page_snapshots"
_ACTIVE_PAGE_TRACKER = "_studio_active_page_id"

# st.button / st.download_button keys — never snapshot or restore (Streamlit-owned).
_NON_RESTORABLE_WIDGET_KEYS = frozenset(
    {
        "practice_generate_notation",
        "practice_send_to_backing",
        "practice_full_abc_sketch",
        "practice_log_insights_btn",
        "build_session_from_logs",
        "session_go_practice",
        "improv_to_backing",
        "improv_to_practice",
        "cpl_to_backing_finish",
        "picker_card_practice",
        "picker_card_backing",
        "picker_card_creative",
        "picker_card_chord_coach",
        "analysis_run_btn",
        "analysis_mt_btn",
        "studio_nav_back_btn",
        "studio_nav_forward_btn",
        "tutorial_header_btn",
        "global_nav_picker",
        "global_nav_practice",
        "global_nav_backing",
    }
)


def _skip_snapshot_key(key: str) -> bool:
    """Exclude Streamlit button keys and cross-page link widgets from persistence."""
    if key in _NON_RESTORABLE_WIDGET_KEYS:
        return True
    if "_x_to_" in key:
        return True
    if key.startswith("ii_chord_tile_"):
        return True
    if _LEGACY_IMPROV_CHORD_TILE_KEY.match(key):
        return True
    if key.endswith("_btn"):
        return True
    return False


def _page_init_flag(page_id: str) -> str:
    return _PAGE_INIT_FLAG.format(page_id=page_id)


def _collect_keys_for_page(session_state: dict, page_id: str) -> set[str]:
    keys: set[str] = set()
    for key in _PAGE_EXPLICIT_KEYS.get(page_id, ()):
        if key in session_state:
            keys.add(key)
    prefixes = _PAGE_PREFIXES.get(page_id, ())
    for key in session_state.keys():
        if key in _SNAPSHOT_BLOCKLIST:
            continue
        if any(key.startswith(p) for p in prefixes):
            keys.add(key)
    return keys


def capture_page_snapshot(session_state: dict, page_id: str) -> dict[str, Any]:
    """Shallow copy of page-local session keys."""
    out: dict[str, Any] = {}
    for key in _collect_keys_for_page(session_state, page_id):
        if _skip_snapshot_key(key):
            continue
        val = session_state.get(key)
        try:
            copy.deepcopy(val)
            out[key] = copy.deepcopy(val)
        except Exception:
            out[key] = val
    return out


def apply_page_snapshot(session_state: dict, snapshot: dict[str, Any] | None) -> None:
    """Restore page-local keys without touching shared globals."""
    if not snapshot:
        return
    for key, val in snapshot.items():
        if key in _SNAPSHOT_BLOCKLIST or _skip_snapshot_key(key):
            continue
        session_state[key] = copy.deepcopy(val)


def save_page_snapshot(session_state: dict, page_id: str) -> None:
    store = session_state.setdefault(_PAGE_SNAPSHOTS_KEY, {})
    store[page_id] = capture_page_snapshot(session_state, page_id)


def restore_page_snapshot(session_state: dict, page_id: str) -> None:
    store = session_state.get(_PAGE_SNAPSHOTS_KEY) or {}
    apply_page_snapshot(session_state, store.get(page_id))


def ensure_page_initialized(
    session_state: dict,
    page_id: str,
    *,
    is_custom_active: bool = False,
) -> None:
    """Apply page defaults only the first time that page is opened."""
    flag = _page_init_flag(page_id)
    if session_state.get(flag):
        return
    session_state[flag] = True
    if page_id == "practice":
        init_practice_page_state(session_state)
    elif page_id == "backing":
        init_backing_page_state(session_state)
    elif page_id == "analysis":
        init_analysis_page_state(session_state)
    elif page_id == "creative":
        init_creative_lab_state(session_state)
    elif page_id == "custom":
        session_state.setdefault("cpl_edit_section", "Verse")
    if page_id == "creative" or page_id == "practice":
        session_state.setdefault("practice_minutes", 30)


def ensure_creative_improv_initialized(session_state: dict, *, is_custom_active: bool) -> None:
    flag = "_page_initialized::creative_improv"
    if session_state.get(flag):
        return
    session_state[flag] = True
    init_improvisation_state(session_state, is_custom_active=is_custom_active)


def handle_studio_page_transition(session_state: dict) -> None:
    """
    On ``studio_page`` change, snapshot the page being left and restore the target page.
    Called once per script run before page content renders.
    """
    current = str(session_state.get("studio_page", "practice"))
    last = session_state.get(_ACTIVE_PAGE_TRACKER)
    if last and last != current:
        save_page_snapshot(session_state, str(last))
        restore_page_snapshot(session_state, current)
    session_state[_ACTIVE_PAGE_TRACKER] = current


def make_history_entry(session_state: dict, page_id: str) -> dict[str, Any]:
    """History stack entry: page id + state snapshot at leave time."""
    return {
        "page": page_id,
        "snapshot": capture_page_snapshot(session_state, page_id),
    }


def restore_history_entry(session_state: dict, entry: dict[str, Any]) -> str:
    """Restore snapshot and return target page id."""
    page_id = str(entry.get("page") or "practice")
    apply_page_snapshot(session_state, entry.get("snapshot"))
    store = session_state.setdefault(_PAGE_SNAPSHOTS_KEY, {})
    store[page_id] = entry.get("snapshot") or {}
    session_state[_ACTIVE_PAGE_TRACKER] = page_id
    return page_id

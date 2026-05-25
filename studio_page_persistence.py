"""Per-page session_state snapshots and first-visit-only defaults.

Navigation (back / forward, quick nav, sidebar) stores **page-local** UI state only.
Musician-wide settings always use the **current** live session values.

Global (never snapshotted / never overwritten by restore):
  instrument, level, focus, selected song, display key, transposition, active source, …

Page-local (snapshotted per ``studio_page``):
  active tab, section focus, expanders, motif/chord picks, page-specific inputs, …
"""

from __future__ import annotations

import copy
import re
from typing import Any

_LEGACY_IMPROV_CHORD_TILE_KEY = re.compile(r"^improv_(live|motif)_s\d+_c\d+$")

# Widget key fragments synced from global instrument / level / focus / transpose.
_GLOBAL_WIDGET_KEY_MARKERS: tuple[str, ...] = (
    "::qc_instrument",
    "::qc_level",
    "::qc_focus",
    "::transposing_instrument",
)

from studio_page_state import (
    init_analysis_page_state,
    init_backing_page_state,
    init_creative_lab_state,
    init_improvisation_state,
    init_practice_page_state,
)

# Explicit page-local keys (whitelist). Do not use broad prefixes that capture globals.
_PAGE_LOCAL_KEYS: dict[str, frozenset[str]] = {
    "practice": frozenset(
        {
            "practice_focus_section",
            "practice_groove_style",
            "practice_notation_lines",
            "practice_notation_difficulty",
            "practice_notation_sig",
            "practice_notation_result",
            "picker_open_chord_coach",
        }
    ),
    "picker": frozenset(
        {
            "chart_library_mode",
            "song_picker_chart_status",
            "song_search_scope",
            "song_picker_level_filter",
            "workspace_genre_filter",
            "song_search_text",
            "picker_open_chord_coach",
            "song_picker_active_source",
        }
    ),
    "backing": frozenset(
        {
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
            "backing_volume",
        }
    ),
    "custom": frozenset(
        {
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
        }
    ),
    "creative": frozenset(
        {
            "creative_lab_analysis_mode",
            "creative_lab_last_mode",
            "creative_arrangement_target_style",
            "creative_arrangement_section_focus",
            "improv_intelligence_tab",
            "improv_entry_mode",
            "improv_generated_sections",
            "improv_style_meta",
            "improv_jam_session",
            "improv_motif",
            "improv_motif_output_mode",
            "improv_motif_abc",
            "improv_motif_tab",
            "improv_active_mission",
            "improv_mission_example",
            "improv_mission_variant",
            "improv_style",
            "improv_style_key",
            "improv_difficulty",
            "improv_mood",
            "improv_style_bpm",
            "improv_groove",
            "improv_style_prompt",
            "improv_ensemble",
            "improv_jam_style",
            "improv_jam_key",
            "improv_jam_bpm",
            "improv_jam_mood",
            "ii_selected_chord",
            "ii_selected_section",
            "ii_selected_chord_index",
            "ii_selected_chord_label",
            "harmony_map_section",
            "harmony_map_chord",
            "improv_ai_metric_ids",
            "analysis_criteria_locked",
            "analysis_return_to_improv_metrics",
        }
    ),
    "multitrack": frozenset(
        {
            "mt_tracks",
            "mt_track_filenames",
            "mt_track_controls",
            "mixed_track_wav",
            "multitrack_backing_music_wav",
        }
    ),
    "analysis": frozenset(
        {
            "analysis_mode",
            "analysis_recording_type",
            "analysis_audio_upload",
            "analysis_audio_record",
            "last_analysis_result",
            "last_analysis_audio",
            "analysis_mission_ids",
            "analysis_ai_metric_ids",
            "analysis_sync_creative_mission",
            "analysis_custom_goal_enabled",
            "analysis_custom_goal",
            "analysis_mission_trend_pick",
            "analysis_criteria_locked",
            "analysis_return_to_improv_metrics",
        }
    ),
    "log": frozenset(
        {
            "ai_session_builder_minutes",
            "practice_log_insights",
            "_ai_practice_session_plan",
        }
    ),
}

# Safe dynamic prefixes (scoped widget namespaces — never plain ``practice_`` / ``improv_``).
_PAGE_LOCAL_PREFIXES: dict[str, tuple[str, ...]] = {
    "practice": ("practice::", "exercise_variation::"),
    "backing": ("backing::", "_follow_", "follow_along::"),
    "multitrack": ("mt_name_", "mt_vol_", "mt_delay_"),
    "log": ("practice_form",),
}

# Navigation stacks and meta — never part of a page snapshot.
_NAV_META_KEYS = frozenset(
    {
        "studio_page",
        "studio_nav_back",
        "studio_nav_forward",
        "_studio_nav_from_history",
        "_studio_active_page_id",
        "_studio_page_snapshots",
        "tutorial_open",
        "tutorial_step",
        "tutorial_dismissed",
        "tutorial_dismiss_checkbox",
        "tutorial_auto_prompted",
    }
)

# App-wide musician / song settings — always use the live current value.
_GLOBAL_APP_STATE_KEYS = frozenset(
    {
        "instrument",
        "level",
        "focus",
        "display_key",
        "openai_api_key_box",
        "selected_song",
        "active_catalog_pick_key",
        "matching_song_dropdown",
        "_pending_matching_song_dropdown",
        "_master_song_pick_key",
        "global_quick_genre",
        "global_quick_song",
        "global_source_mode",
        "active_music_source",
        "_last_active_music_source",
        "active_genre",
        "active_song_title",
        "selected_transposing_instrument",
        "_pending_selected_transposing_instrument",
        "show_chart_in_instrument_key",
        "concert_practice_key",
        "saxophone_type",
        "_display_key_song_identity",
        "_last_app_display_key",
        "_pending_display_key",
        "_cpl_jump_home_target",
        "improv_song_source",
        "bpm",
        "backing_track_bpm",
        "backing_groove_style",
        "backing_time_signature",
        "backing_time_signature_override",
        "active_song_bpm",
        "active_playback_song_id",
        "last_backing_defaults_song_id",
        "last_backing_bpm_song_id",
        "_last_bpm_song",
        "_last_playback_groove_song",
        "practice_groove_style",
        "beats_per_bar",
        "_backing_needs_regen",
        "_backing_autoplay",
        "practice_minutes",
        # Karaoke / Vocal Performance Mode state — survives page switches.
        "karaoke_queue",
        "karaoke_session_active",
        "karaoke_session_index",
        "karaoke_auto_advance",
        "_karaoke_active_pick_key",
        "_karaoke_song_ended",
        "_karaoke_transition_label",
        "_pending_karaoke_advance",
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


def _is_global_app_state_key(key: str) -> bool:
    """True if this key must never be saved or restored as page-local state."""
    if key in _NAV_META_KEYS or key in _GLOBAL_APP_STATE_KEYS:
        return True
    return any(marker in key for marker in _GLOBAL_WIDGET_KEY_MARKERS)


def _skip_snapshot_key(key: str) -> bool:
    """Exclude globals and Streamlit-owned widget keys from persistence."""
    if _is_global_app_state_key(key):
        return True
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
    if key.startswith("practice_tuner"):
        return True
    if "::audio_in" in key or key.startswith("mt_record_"):
        return True
    if key in ("analysis_audio_upload", "analysis_audio_record"):
        return True
    return False


def _filter_page_local_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Drop global / widget keys from a stored snapshot (incl. legacy history entries)."""
    if not snapshot:
        return {}
    return {
        key: val
        for key, val in snapshot.items()
        if not _skip_snapshot_key(key)
    }


def _preserve_global_state(session_state: dict) -> dict[str, Any]:
    """Copy all current global keys so navigation cannot overwrite them."""
    preserved: dict[str, Any] = {}
    for key in list(session_state.keys()):
        if _is_global_app_state_key(key):
            try:
                preserved[key] = copy.deepcopy(session_state[key])
            except Exception:
                preserved[key] = session_state[key]
    return preserved


def _restore_preserved_globals(session_state: dict, preserved: dict[str, Any]) -> None:
    for key, val in preserved.items():
        session_state[key] = val


def _page_init_flag(page_id: str) -> str:
    return _PAGE_INIT_FLAG.format(page_id=page_id)


def _collect_keys_for_page(session_state: dict, page_id: str) -> set[str]:
    keys: set[str] = set()
    for key in _PAGE_LOCAL_KEYS.get(page_id, frozenset()):
        if key in session_state:
            keys.add(key)
    prefixes = _PAGE_LOCAL_PREFIXES.get(page_id, ())
    for key in session_state.keys():
        if _skip_snapshot_key(key):
            continue
        if any(key.startswith(p) for p in prefixes):
            keys.add(key)
    return keys


def capture_page_snapshot(session_state: dict, page_id: str) -> dict[str, Any]:
    """Shallow copy of page-local session keys only."""
    out: dict[str, Any] = {}
    for key in _collect_keys_for_page(session_state, page_id):
        if _skip_snapshot_key(key):
            continue
        val = session_state.get(key)
        try:
            out[key] = copy.deepcopy(val)
        except Exception:
            out[key] = val
    return out


def apply_page_snapshot(session_state: dict, snapshot: dict[str, Any] | None) -> None:
    """Restore page-local keys; global musician settings are always preserved."""
    preserved = _preserve_global_state(session_state)
    local = _filter_page_local_snapshot(snapshot)
    for key, val in local.items():
        session_state[key] = copy.deepcopy(val)
    _restore_preserved_globals(session_state, preserved)


def save_page_snapshot(session_state: dict, page_id: str) -> None:
    store = session_state.setdefault(_PAGE_SNAPSHOTS_KEY, {})
    store[page_id] = capture_page_snapshot(session_state, page_id)


def restore_page_snapshot(session_state: dict, page_id: str) -> None:
    store = session_state.get(_PAGE_SNAPSHOTS_KEY) or {}
    apply_page_snapshot(session_state, store.get(page_id))


def sanitize_persisted_snapshots(session_state: dict) -> None:
    """Strip globals from stored page snapshots and nav history (legacy sessions)."""
    store = session_state.get(_PAGE_SNAPSHOTS_KEY)
    if isinstance(store, dict):
        for page_id, snap in list(store.items()):
            store[page_id] = _filter_page_local_snapshot(snap if isinstance(snap, dict) else {})

    for stack_key in ("studio_nav_back", "studio_nav_forward"):
        stack = session_state.get(stack_key)
        if not isinstance(stack, list):
            continue
        for i, entry in enumerate(stack):
            if isinstance(entry, dict) and isinstance(entry.get("snapshot"), dict):
                stack[i] = {
                    **entry,
                    "snapshot": _filter_page_local_snapshot(entry["snapshot"]),
                }


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
    """On page change, snapshot the page left and restore page-local state only."""
    sanitize_persisted_snapshots(session_state)
    current = str(session_state.get("studio_page", "practice"))
    last = session_state.get(_ACTIVE_PAGE_TRACKER)
    if last and last != current:
        save_page_snapshot(session_state, str(last))
        restore_page_snapshot(session_state, current)
    session_state[_ACTIVE_PAGE_TRACKER] = current


def make_history_entry(session_state: dict, page_id: str) -> dict[str, Any]:
    """History stack entry: page id + page-local snapshot at leave time."""
    return {
        "page": page_id,
        "snapshot": capture_page_snapshot(session_state, page_id),
    }


def restore_history_entry(session_state: dict, entry: dict[str, Any]) -> str:
    """Restore page id + page-local snapshot; globals remain live."""
    page_id = str(entry.get("page") or "practice")
    local = _filter_page_local_snapshot(entry.get("snapshot"))
    apply_page_snapshot(session_state, local)
    store = session_state.setdefault(_PAGE_SNAPSHOTS_KEY, {})
    store[page_id] = local
    session_state[_ACTIVE_PAGE_TRACKER] = page_id
    return page_id

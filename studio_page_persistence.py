"""Per-page session_state snapshots and first-visit-only defaults.

Navigation (back / forward, quick nav, sidebar) stores **page-local** UI state only.
Musician-wide settings always use the **current** live session values.

Global (never snapshotted / never overwritten by restore):
  instrument, level, focus, selected song, display key, transposition, active source, …

Page-local (snapshotted per ``studio_page``):
  active tab, section focus, expanders, motif/chord picks, page-specific inputs, …
"""

from __future__ import annotations

import ast
import base64
import copy
import re
from typing import Any

_B64_MARKER = "__suite_b64__"

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
            "practice_active_tool",
            "practice_chart_panel_open",
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
            "workspace_genre_filters",
            "song_search_text",
            # song_picker_active_source is global ownership (also in music persist) —
            # must not be reclaimed by a stale Songs page snapshot after Custom→Catalog.
        }
    ),
    "backing": frozenset(
        {
            "_last_backing_wav",
            "_last_backing_signature",
            "_last_backing_timeline",
            "playback_start_time",
            "current_chord_timeline",
            "selected_sections",
            "backing_volume",
            "backing_context",
            "_music_mission_canonical_return_destination",
            "creative_session",
            "improv_mission_practice_lick",
            "improv_mission_example",
            "improv_mission_variant",
            "improv_active_mission",
            "improv_mission_pick",
            "ii_selected_chord",
            "ii_selected_section",
            "backing_track_bpm",
            "backing_track_loops",
            "backing_track_scope",
            "backing_track_single_section",
            "backing_track_multi_sections",
            "backing_groove_style",
            "backing_time_signature",
            "backing_time_signature_override",
        }
    ),
    "custom": frozenset(
        {
            "cpl_edit_section",
            "cpl_builder_version",
            "cpl_finished",
        }
    ),
    "composer": frozenset(
        {
            "composer_active_document",
            "composer_saved_compositions",
            "composer_needs_seed",
            "composer_active_section_id",
            "composer_focus_lane",
            "composer_snapshot_stamp",
            "composer_seed_type",
            "composer_play_scope",
            "composer_play_loops",
        }
    ),
    "creative": frozenset(
        {
            "creative_lab_analysis_mode",
            "creative_lab_last_mode",
            "creative_arrangement_target_style",
            "creative_arrangement_section_focus",
            "improv_intelligence_tab",
            "creative_improv_intelligence_tab",
            "improv_entry_mode",
            # Nested SBI source tab (Active vs Custom) — distinct from top-level Custom page.
            "improv_song_source",
            "sbi_preview_source",
            "creative_session",
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
            "improv_mission_practice_lick",
            "improv_mission_pick",
            "improv_mission_new_nonce",
            "improv_mission_chord_options",
            "improv_mission_progression",
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
            "deep_harmony_lesson_step",
            "improv_deep_harmony_dha_section_idx",
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
            "mt_backing_volume",
            "mt_playback_scope",
            "mt_single_section",
            "mt_multi_sections",
            "multitrack_bpm",
            "mt_section_loops",
            "mt_groove_style",
            "mt_time_signature",
            "mt_count_in_bars",
            "mt_metronome_playback",
            "mt_loop_backing",
            "mt_use_backing_monitor",
            "include_backing_mix",
            "mt_backing_scope",
            "mt_backing_duration",
            "mt_backing_prepared_at",
            "mt_history_save_name",
            "mt_history_save_notes",
            "multitrack_history_loaded_notes",
            "_last_catalog_multitrack_id",
            "multitrack_catalog_active_id",
            "mt_hist_active_item",
            "_mt_loaded_backing_project_id",
            "_mt_session_backing_storage_ref",
            "_mt_loaded_project_song",
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
            "last_analysis_source_label",
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
    "openai": frozenset(),
}

# Safe dynamic prefixes (scoped widget namespaces — never plain ``practice_`` / ``improv_``).
_PAGE_LOCAL_PREFIXES: dict[str, tuple[str, ...]] = {
    "practice": ("practice::", "exercise_variation::"),
    "backing": ("backing::", "_follow_", "follow_along::"),
    "multitrack": ("mt_name_", "mt_vol_", "mt_delay_", "mt_mute_", "mt_solo_"),
    "log": ("practice_form",),
}

# Navigation stacks and meta — never part of a page snapshot.
_NAV_META_KEYS = frozenset(
    {
        "studio_page",
        "studio_sidebar_nav_collapsed",
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
        "selected_song",
        "active_catalog_pick_key",
        "matching_song_dropdown",
        "_pending_matching_song_dropdown",
        "_master_song_pick_key",
        "global_quick_genre",
        "global_quick_song",
        "_ami_pending_insight",
        "_ami_return_page",
        "_ami_return_context",
        "_ami_dismissed_insight_ids",
        "_ami_dismissed_insight_at",
        "global_source_mode",
        "active_music_source",
        "_last_active_music_source",
        "song_picker_active_source",
        "active_genre",
        "active_song_title",
        "selected_transposing_instrument",
        "_pending_selected_transposing_instrument",
        "show_chart_in_instrument_key",
        "_chart_written_key_instrument_anchor",
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
        "backing_humanize_chord_timing",
        "backing_preserve_exact_timing",
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
        "_pending_karaoke_auto_generate",
        "karaoke_countdown_enabled",
        "karaoke_countdown_seconds",
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


def _encode_snapshot_value(val: Any) -> Any:
    """JSON-safe encoding for page snapshots (bytes → base64 wrapper)."""
    if isinstance(val, bytes):
        return {_B64_MARKER: base64.b64encode(val).decode("ascii")}
    if isinstance(val, dict):
        return {k: _encode_snapshot_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_encode_snapshot_value(v) for v in val]
    return val


def _decode_snapshot_value(val: Any) -> Any:
    """Reverse ``_encode_snapshot_value``; tolerate legacy ``default=str`` bytes."""
    if isinstance(val, dict):
        if set(val.keys()) == {_B64_MARKER}:
            raw = val.get(_B64_MARKER)
            if isinstance(raw, str):
                return base64.b64decode(raw.encode("ascii"))
            return val
        return {k: _decode_snapshot_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_decode_snapshot_value(v) for v in val]
    if isinstance(val, str) and len(val) >= 3 and val[0] == "b" and val[1] in ("'", '"'):
        try:
            decoded = ast.literal_eval(val)
            if isinstance(decoded, bytes):
                return decoded
        except (SyntaxError, ValueError):
            pass
    return val


def _encode_page_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {key: _encode_snapshot_value(val) for key, val in snapshot.items()}


def _decode_page_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not snapshot:
        return {}
    return {key: _decode_snapshot_value(val) for key, val in snapshot.items()}


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
    return _encode_page_snapshot(out)


_PAGE_SNAPSHOT_USER_TOUCH_GUARDS: dict[str, str] = {
    "workspace_genre_filters": "_genre_filters_user_touched",
    "creative_improv_intelligence_tab": "_improv_tab_user_touched",
    "improv_intelligence_tab": "_improv_tab_user_touched",
}

_VOLATILE_BACKING_SNAPSHOT_KEYS: frozenset[str] = frozenset(
    {
        "playback_start_time",
        "_backing_autoplay",
        "backing_lead_sheet_open",
    }
)


def apply_page_snapshot(session_state: dict, snapshot: dict[str, Any] | None) -> None:
    """Restore page-local keys; global musician settings are always preserved."""
    preserved = _preserve_global_state(session_state)
    local = _decode_page_snapshot(_filter_page_local_snapshot(snapshot))
    try:
        from backing_track_state import strip_durable_backing_snapshot_keys

        local = strip_durable_backing_snapshot_keys(local)
    except ImportError:
        pass
    restored_keys: list[str] = []
    try:
        from backing_source_navigation import (
            CREATIVE_BACKING_RETURN_WIDGET_KEYS,
            CREATIVE_RESTORE_FROM_BACKING_KEY,
        )

        skip_creative_widget_snapshot = bool(session_state.get(CREATIVE_RESTORE_FROM_BACKING_KEY))
    except ImportError:
        skip_creative_widget_snapshot = False
        CREATIVE_BACKING_RETURN_WIDGET_KEYS = frozenset()  # type: ignore[misc,assignment]
    for key, val in local.items():
        if key in _VOLATILE_BACKING_SNAPSHOT_KEYS:
            continue
        if skip_creative_widget_snapshot and key in CREATIVE_BACKING_RETURN_WIDGET_KEYS:
            continue
        touch_guard = _PAGE_SNAPSHOT_USER_TOUCH_GUARDS.get(key)
        if touch_guard and session_state.get(touch_guard):
            continue
        if key == "mt_tracks" and _multitrack_session_has_layers(session_state):
            if not _snapshot_has_multitrack_content({"mt_tracks": val}):
                continue
        if key in {"sbi_preview_source", "improv_song_source"}:
            live_preview = str(
                session_state.get("sbi_preview_source")
                or session_state.get("improv_song_source")
                or ""
            ).strip()
            snap_preview = str(val or "").strip()
            # Do not let a stale Creative page snapshot reclaim Active Source
            # when the live/persisted SBI source is already Custom.
            if live_preview == "Custom progression" and snap_preview != live_preview:
                continue
            if session_state.get("_sbi_follow_active_after_explicit_catalog"):
                if snap_preview != "Active song":
                    continue
                session_state[key] = "Active song"
                continue
        if key == "song_picker_active_source":
            # Global music-source ownership — never reclaim from page snapshots.
            continue
        if key == "multitrack_backing_music_wav":
            snap_project = str(
                local.get("_last_catalog_multitrack_id")
                or local.get("multitrack_catalog_active_id")
                or ""
            ).strip()
            live_project = str(
                session_state.get("_last_catalog_multitrack_id")
                or session_state.get("multitrack_catalog_active_id")
                or ""
            ).strip()
            loaded_project = str(session_state.get("_mt_loaded_backing_project_id") or "").strip()
            if loaded_project and snap_project and loaded_project != snap_project:
                continue
            if loaded_project and live_project and loaded_project != live_project:
                continue
            live = session_state.get(key)
            snap_has = bool(live) and isinstance(live, (bytes, bytearray)) and len(live) > 0
            val_has = bool(val) and isinstance(val, (bytes, bytearray)) and len(val) > 0
            if snap_has and not val_has:
                continue
        if key == "mt_track_controls":
            try:
                from multitrack_mixer_state import merge_mt_track_controls

                session_state[key] = merge_mt_track_controls(val, session_state.get(key))
            except ImportError:
                session_state[key] = copy.deepcopy(val)
            continue
        if key == "backing_context":
            prev_bc = session_state.get("backing_context")
            snap_bc = val if isinstance(val, dict) else None
            live_bc = prev_bc if isinstance(prev_bc, dict) else None
            if live_bc is not None and snap_bc is not None:
                live_src = str(live_bc.get("source") or "").strip()
                snap_src = str(snap_bc.get("source") or "").strip()
                specialized = {
                    "song_improv",
                    "mission",
                    "entry_jam",
                    "custom_progression",
                }
                # Specialized visit on disk/session must not be clobbered by a
                # stale Catalog Backing page snapshot on reboot/refresh.
                if live_src in specialized and snap_src == "regular_song":
                    continue
                try:
                    from backing_play_session import (
                        get_backing_play_session,
                        play_session_blocks_canonical_seed,
                    )

                    if play_session_blocks_canonical_seed(session_state):
                        continue
                    ps = get_backing_play_session(session_state)
                    if (
                        ps
                        and not ps.get("expired")
                        and live_src in specialized
                        and snap_src in specialized | {"regular_song", ""}
                    ):
                        # Same Backing visit — keep live sealed ctx; play session
                        # owns temporary BPM/style/loop over snapshot defaults.
                        continue
                except ImportError:
                    pass
            try:
                from creative_return_trace import trace_direct_backing_context_write

                trace_direct_backing_context_write(
                    session_state,
                    source="apply_page_snapshot",
                    prev_blob=prev_bc,
                    new_blob=val,
                )
            except ImportError:
                pass
        session_state[key] = copy.deepcopy(val)
    _restore_preserved_globals(session_state, preserved)


def save_page_snapshot(session_state: dict, page_id: str) -> None:
    if page_id in {"creative", "backing"}:
        try:
            from backing_source_navigation import CREATIVE_RESTORE_FROM_BACKING_KEY

            skip_sync = bool(session_state.get(CREATIVE_RESTORE_FROM_BACKING_KEY))
        except ImportError:
            skip_sync = False
        if not skip_sync:
            try:
                from creative_session_state import sync_creative_session_before_persist

                sync_creative_session_before_persist(session_state)
            except ImportError:
                pass
    store = session_state.setdefault(_PAGE_SNAPSHOTS_KEY, {})
    store[page_id] = capture_page_snapshot(session_state, page_id)


def flush_current_page_snapshot(session_state: dict) -> str:
    """Persist live page-local keys before disk/cloud autosave (same-page edits)."""
    page_id = str(session_state.get("studio_page") or "practice").strip() or "practice"
    save_page_snapshot(session_state, page_id)
    return page_id


def restore_page_snapshot(session_state: dict, page_id: str) -> None:
    store = session_state.get(_PAGE_SNAPSHOTS_KEY) or {}
    try:
        from multitrack_project_load_trace import record_restore_event

        record_restore_event(
            session_state,
            "restore_page_snapshot",
            page_id=page_id,
            has_snapshot=bool(store.get(page_id)),
        )
    except ImportError:
        pass
    apply_page_snapshot(session_state, store.get(page_id))


def reset_page_snapshot_tracker(session_state: dict) -> None:
    """Clear cross-run page tracker so refresh re-applies the active page snapshot."""
    session_state.pop(_ACTIVE_PAGE_TRACKER, None)


def _multitrack_session_has_layers(session_state: dict) -> bool:
    mt = session_state.get("mt_tracks")
    if not isinstance(mt, dict):
        return False
    return any(v for v in mt.values() if v)


def _snapshot_has_multitrack_content(snap: dict[str, Any]) -> bool:
    mt = snap.get("mt_tracks")
    if isinstance(mt, dict) and any(v for v in mt.values() if v):
        return True
    return bool(snap.get("mixed_track_wav"))


def _snapshot_has_multitrack_workspace(snap: dict[str, Any]) -> bool:
    if _snapshot_has_multitrack_content(snap):
        return True
    return bool(
        snap.get("mt_history_save_notes")
        or snap.get("mt_history_save_name")
        or snap.get("multitrack_catalog_active_id")
        or snap.get("_last_catalog_multitrack_id")
        or snap.get("mt_backing_prepared_at")
        or snap.get("multitrack_bpm") is not None
        or snap.get("mt_backing_volume") is not None
    )


def restore_current_page_snapshot_if_needed(session_state: dict) -> None:
    """After browser refresh / cloud restore — hydrate page-local UI for active page."""
    try:
        from music_restore_phase import mark_page_snapshot_hydrated, page_snapshot_hydrated
    except ImportError:
        mark_page_snapshot_hydrated = None  # type: ignore[assignment]
        page_snapshot_hydrated = lambda _ss, _pid: False  # type: ignore[assignment]

    skip_count = session_state.get("_mt_skip_snapshot_restore_count")
    if isinstance(skip_count, int) and skip_count > 0:
        session_state["_mt_skip_snapshot_restore_count"] = skip_count - 1
        try:
            from multitrack_project_load_trace import record_restore_event

            record_restore_event(
                session_state,
                "restore_current_page_snapshot_skipped",
                remaining=skip_count - 1,
            )
        except ImportError:
            pass
        return
    current = str(session_state.get("studio_page") or "practice").strip() or "practice"
    if page_snapshot_hydrated(session_state, current):
        return
    if current == "creative":
        try:
            from creative_session_state import (
                apply_creative_session_to_session,
                creative_session_is_active,
                get_creative_session,
            )

            sess = get_creative_session(session_state)
            if sess is not None and creative_session_is_active(session_state):
                apply_creative_session_to_session(session_state, sess, widget_safe=False)
                if mark_page_snapshot_hydrated is not None:
                    mark_page_snapshot_hydrated(session_state, current)
                return
        except ImportError:
            pass
    store = session_state.get(_PAGE_SNAPSHOTS_KEY) or {}
    snap = store.get(current) if isinstance(store, dict) else None
    if not snap:
        return
    multitrack_hydrated = current == "multitrack" and page_snapshot_hydrated(session_state, current)
    needs_restore = session_state.get(_ACTIVE_PAGE_TRACKER) is None
    if current == "analysis" and not session_state.get("last_analysis_result"):
        needs_restore = True
    if (
        current == "multitrack"
        and isinstance(snap, dict)
        and _snapshot_has_multitrack_workspace(snap)
        and not multitrack_hydrated
    ):
        if not _multitrack_session_has_layers(session_state) and not session_state.get("mixed_track_wav"):
            needs_restore = True
        elif not session_state.get("mt_history_save_notes") and snap.get("mt_history_save_notes"):
            needs_restore = True
        elif not session_state.get("multitrack_catalog_active_id") and snap.get("multitrack_catalog_active_id"):
            needs_restore = True
    if current == "creative" and not session_state.get("improv_motif_abc"):
        if any(
            k in snap
            for k in (
                "improv_motif_abc",
                "improv_generated_sections",
                "improv_jam_session",
                "improv_mission_example",
            )
        ):
            needs_restore = True
    if current == "backing":
        snap_ctx = snap.get("backing_context") if isinstance(snap, dict) else None
        snap_creative = snap.get("creative_session") if isinstance(snap, dict) else None
        live_ctx = session_state.get("backing_context")
        if snap_ctx and not live_ctx:
            needs_restore = True
        if snap_creative and not session_state.get("creative_session"):
            needs_restore = True
        try:
            from creative_session_state import creative_session_is_active

            if creative_session_is_active(session_state) and not live_ctx:
                needs_restore = True
        except ImportError:
            pass
        if isinstance(snap, dict) and snap.get("improv_mission_practice_lick") and not session_state.get(
            "improv_mission_practice_lick"
        ):
            needs_restore = True
        if isinstance(snap, dict) and snap.get("improv_mission_example") and not session_state.get(
            "improv_mission_example"
        ):
            needs_restore = True
    if needs_restore:
        try:
            from multitrack_project_load_trace import record_restore_event

            record_restore_event(
                session_state,
                "restore_current_page_snapshot_ran",
                page=current,
                reason="needs_restore",
            )
        except ImportError:
            pass
        restore_page_snapshot(session_state, current)
        if mark_page_snapshot_hydrated is not None:
            mark_page_snapshot_hydrated(session_state, current)
        if current == "multitrack":
            try:
                from multitrack_session_persistence import record_multitrack_workspace_restore

                record_multitrack_workspace_restore(session_state, source="restore_current_page_snapshot")
            except ImportError:
                pass


def sanitize_persisted_snapshots(session_state: dict) -> None:
    """Strip globals from stored page snapshots and nav history (legacy sessions)."""
    try:
        from backing_track_state import strip_durable_backing_snapshot_keys
    except ImportError:
        strip_durable_backing_snapshot_keys = None  # type: ignore[assignment]
    store = session_state.get(_PAGE_SNAPSHOTS_KEY)
    if isinstance(store, dict):
        for page_id, snap in list(store.items()):
            cleaned = _filter_page_local_snapshot(snap if isinstance(snap, dict) else {})
            if strip_durable_backing_snapshot_keys is not None:
                cleaned = strip_durable_backing_snapshot_keys(cleaned)
            store[page_id] = cleaned

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
    elif page_id == "composer":
        try:
            from composition_session_state import init_composer_page_state

            init_composer_page_state(session_state)
        except ImportError:
            pass


def ensure_creative_improv_initialized(session_state: dict, *, is_custom_active: bool) -> None:
    flag = "_page_initialized::creative_improv"
    if session_state.get(flag):
        return
    session_state[flag] = True
    init_improvisation_state(session_state, is_custom_active=is_custom_active)


def handle_studio_page_transition(session_state: dict) -> None:
    """On page change, snapshot the page left and restore page-local state only."""
    try:
        from music_restore_phase import (
            mark_page_snapshot_hydrated,
            should_hydrate_page_snapshot,
        )
    except ImportError:
        mark_page_snapshot_hydrated = None  # type: ignore[assignment]
        should_hydrate_page_snapshot = None  # type: ignore[assignment]

    if not session_state.get("_snapshots_sanitized_once"):
        sanitize_persisted_snapshots(session_state)
        session_state["_snapshots_sanitized_once"] = True
    current = str(session_state.get("studio_page", "practice"))
    last = session_state.get(_ACTIVE_PAGE_TRACKER)
    if last and last != current:
        try:
            from creative_return_trace import trace_page_transition

            trace_page_transition(session_state, from_page=str(last), to_page=current)
        except ImportError:
            pass
        try:
            from music_nav_dedupe import save_page_snapshot_deduped

            save_page_snapshot_deduped(session_state, str(last))
        except ImportError:
            save_page_snapshot(session_state, str(last))
        restore_page_snapshot(session_state, current)
        if mark_page_snapshot_hydrated is not None:
            mark_page_snapshot_hydrated(session_state, current)
        try:
            import streamlit as st

            from music_activity import log_studio_page_entered

            log_studio_page_entered(st, current)
        except Exception:
            pass
    elif last is None:
        hydrate = True
        if should_hydrate_page_snapshot is not None:
            hydrate = should_hydrate_page_snapshot(
                session_state,
                page_id=current,
                page_changed=False,
            )
        if hydrate:
            restore_current_page_snapshot_if_needed(session_state)
            if mark_page_snapshot_hydrated is not None:
                mark_page_snapshot_hydrated(session_state, current)
    session_state[_ACTIVE_PAGE_TRACKER] = current
    try:
        from studio_page_route_trace import trace_after_page_transition

        trace_after_page_transition(session_state, dispatch_local=current)
    except ImportError:
        pass


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

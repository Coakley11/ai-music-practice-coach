# VERSION: v49_global_transpose_key

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import io

try:
    import librosa
except Exception:
    librosa = None

import json
import wave
import tempfile
import html
import html as _html  # Alias so module-level helpers (lyric_guide_html,
# _chord_strip_html, _build_karaoke_lyrics_panel_html, etc.) can use the
# same ``_html.escape`` name that nested helpers already use.
import time
import base64
import traceback
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Any, Callable

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------

st.set_page_config(
    page_title="Daniel Cohen AI Music Practice Coach",
    page_icon="🎵",
    layout="wide"
)

st.session_state["_script_run_seq"] = int(st.session_state.get("_script_run_seq") or 0) + 1

try:
    from music_restore_phase import begin_music_script_run

    begin_music_script_run(st.session_state)
except Exception:
    pass

try:
    from app_ui import init_simple_music_nav_from_query
    from music_persistence_trace import init_developer_mode_from_query, render_persistence_trace_sidebar

    init_developer_mode_from_query(st)
    init_simple_music_nav_from_query(st)
    from app_ui import reset_quick_nav_render_diagnostics

    reset_quick_nav_render_diagnostics(st.session_state)
except Exception:
    pass

import portfolio_polish as pp
import portfolio_demo as pdemo

pp.inject_polish_css(st, app_slug="music")

try:
    from suite_resume_launch import apply_suite_resume_launch

    apply_suite_resume_launch(st, "music")
except Exception:
    pass

try:
    from suite_app_shell import apply_suite_auth_gate

    apply_suite_auth_gate(st)
except Exception:
    pass

try:
    from suite_app_shell import render_suite_sidebar_account_shell

    render_suite_sidebar_account_shell(st, command_center_divider=False)
except Exception:
    pass
# -------------------------------------------------
# GLOBAL CONSTANTS + SONG CATALOG
# -------------------------------------------------

DATA_FILE = Path("practice_history.json")

import importlib.util
import sys

_MUSIC_THEORY_PATH = Path(__file__).resolve().parent / "music_theory.py"
if not _MUSIC_THEORY_PATH.is_file():
    raise ImportError(
        f"music_theory.py must sit next to this app (expected {_MUSIC_THEORY_PATH}). "
        "Add that file to the repository root and redeploy."
    )
_spec = importlib.util.spec_from_file_location(
    "music_theory",
    str(_MUSIC_THEORY_PATH),
)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Could not load music_theory from {_MUSIC_THEORY_PATH}")
_music_theory = importlib.util.module_from_spec(_spec)
sys.modules["music_theory"] = _music_theory
_spec.loader.exec_module(_music_theory)

COMMON_KEYS = _music_theory.COMMON_KEYS
CHROMATIC = _music_theory.CHROMATIC
FLAT_TO_SHARP = _music_theory.FLAT_TO_SHARP
NOTE_TO_MIDI = _music_theory.NOTE_TO_MIDI
normalize_root = _music_theory.normalize_root
split_chord = _music_theory.split_chord
is_no_chord_token = _music_theory.is_no_chord_token
semitone_distance = _music_theory.semitone_distance
transpose_chord = _music_theory.transpose_chord
transpose_sections = _music_theory.transpose_sections
transpose_sections_dict = _music_theory.transpose_sections_dict
transpose_guitar_tabs = _music_theory.transpose_guitar_tabs
display_key_options = _music_theory.display_key_options

from song_catalog import (
    load_song_catalog,
    search_records,
    format_pick_key,
    parse_pick_key,
    resolve_pick_key,
    record_for_pick_key,
)
from songs.bpm_state import request_backing_bpm, sync_backing_bpm_before_widget
from songs.form import (
    chord_blocks_for_backing,
    form_timeline_rows,
    section_names_from_song,
    section_order,
)
from songs.key_state import (
    BACKING_NEEDS_REGEN,
    clear_backing_needs_regen,
    invalidate_backing_cache,
    mark_display_key_changed,
    note_display_key_change,
    on_cpl_jump_home_key,
    prepare_cpl_jump_home,
    request_display_key,
    resolve_active_musical_key,
    sync_display_key_before_widget,
)
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    LAST_CATALOG_STATE_KEY,
    SOURCE_CATALOG,
    SOURCE_CUSTOM,
    active_source_banner,
    build_active_chart_bundle,
    cpl_session_is_active,
    display_key_context,
    ensure_active_music_source,
    is_custom_progression,
    custom_progression_is_active,
    note_active_source_change,
    set_catalog_source,
    set_custom_source,
    unpack_active_source_banner,
)
from songs.picker_session import (
    CATALOG_FAVORITES_KEY,
    SONG_PICKER_FAVORITES_ONLY_KEY,
    WORKSPACE_GENRE_FILTERS_KEY,
    apply_picker_session_resets,
    prune_catalog_pick_keys,
    request_clear_browse_filters,
    toggle_catalog_favorite,
    toggle_favorites_filter,
    toggle_genre_filter,
)
from songs.state import (
    ACTIVE_CATALOG_PICK_KEY,
    PENDING_MATCHING_SONG_DROPDOWN,
    PICK_KEY_RECOVERY_NOTICE_KEY,
    SELECTED_SONG_STATE_KEY,
    SUITE_LOCAL_STATE_RESTORED_KEY,
    apply_pick_key,
    build_music_local_state,
    ensure_master_song_initialized,
    get_song_context,
    persist_music_local_state,
    restore_saved_app_state_once,
    sync_matching_song_dropdown_before_widget,
)
from songs.playback_defaults import (
    BACKING_BPM_MAX,
    BACKING_BPM_MIN,
    GROOVE_STYLE_CHOICES,
    active_song_sync_id,
    apply_backing_defaults_for_song,
    backing_bpm_slider_widget_key,
    canonical_active_song_bpm,
    canonicalize_backing_defaults_for_song,
    default_bpm_for_song_data,
    default_groove_for_song,
    normalize_groove_label,
    playback_song_id,
    request_backing_groove,
    resolve_active_bpm_sync_id,
    resolve_backing_bpm_for_slider,
    sync_backing_bpm_from_slider,
    sync_playback_defaults_for_active_song,
)
from backing_generation import (
    BackingGenProfile,
    prepare_wav_b64,
    profile_elapsed_ms,
    record_backing_timing_event,
    render_backing_generation_debug,
)
from backing_display import (
    render_backing_active_song_card,
    render_backing_defaults_debug,
    render_backing_meter_selector,
)
from harmonic_rhythm_intelligence import (
    BACKING_HUMANIZE_LEVEL_KEY,
    BACKING_PRESERVE_EXACT_KEY,
    annotations_lookup,
    apply_harmonic_rhythm_intelligence,
)
import karaoke_mode as km
from chart_level_arrangement import level_view_of_sections, resolve_level_chart
from youtube_ui import (
    render_original_song_video_card,
    render_practice_learning_video_panel,
)
from karaoke_ui import (
    build_karaoke_audio_bridge_script,
    build_karaoke_countdown_script,
    render_add_to_queue_button,
    render_karaoke_missing_lyrics_cta,
    render_karaoke_now_singing_banner,
    render_karaoke_queue_preview,
    render_karaoke_setlist_panel,
    render_karaoke_skip_controls,
    render_karaoke_status_pill,
    render_karaoke_transition_card,
)
from songs.meter import (
    beats_per_bar_from_signature,
    default_time_signature_for_record,
    meter_timing,
    metronome_accents,
)
from songs.meter_state import (
    BACKING_METER_KEY,
    BACKING_METER_OVERRIDE_KEY,
    apply_backing_meter_for_song,
)
from tuner_tone_ui import render_tuner_tone_section, tuner_key_prefix_for_song
from practice_metronome import render_metronome_widget
from practice_setup_controls import (
    DEFAULT_INSTRUMENT_OPTIONS,
    focus_options_for_instrument,
    render_setup_quick_controls,
)
from guitar_capo import (
    CAPO_ENABLED_KEY,
    CAPO_SHAPE_KEY,
    build_capo_context,
    capo_status_banner_html,
    chart_bundle_transpose_key,
    render_guitar_capo_practice_panel,
    render_guitar_capo_sidebar,
)
import studio_nav_history as _studio_nav_history

init_nav_history = _studio_nav_history.init_nav_history
navigate_studio_page = _studio_nav_history.navigate_studio_page
render_floating_nav_history = getattr(
    _studio_nav_history,
    "render_floating_nav_history",
    _studio_nav_history.render_sidebar_nav_history,
)
render_nav_deploy_marker = getattr(
    _studio_nav_history,
    "render_nav_deploy_marker",
    lambda _st: None,
)
NAVIGATION_UI_DEPLOY_MARKER = getattr(
    _studio_nav_history,
    "NAVIGATION_UI_DEPLOY_MARKER",
    "unknown",
)
from studio_cache import (
    invalidate_session_cache,
    sections_tuple_signature,
    session_cache_get_or_set,
)
from studio_scroll_anchors import (
    ANCHOR_BACKING_FOLLOW_ALONG,
    ANCHOR_BACKING_MAIN_CONTROLS,
    ANCHOR_CHOOSE_ACTIVE_SONG,
    ANCHOR_CHORD_COACH,
    ANCHOR_LYRICS_EDITOR,
    ANCHOR_CHART_EDITOR,
    ANCHOR_PRACTICE_COACH,
    render_pending_scroll_script,
    render_scroll_anchor_marker,
    set_pending_anchor,
)
from picker_song_editor import (
    PICKER_EDITOR_NOTICE_KEY,
    PICKER_EDITOR_OPEN_KEY,
    PICKER_EDITOR_TAB_KEY,
    collapse_picker_editor,
    consume_jump_to_chart_editor,
    consume_open_lyrics_request,
    open_picker_editor,
)
from studio_page_state import (
    apply_improv_song_source,
    flush_pending_improv_song_source,
    migrate_legacy_session_keys,
    note_page_visit,
    persist_improv_intelligence_tab,
    resolve_improv_song_source,
    sync_improv_song_source_for_handoff,
)
from studio_page_persistence import (
    ensure_creative_improv_initialized,
    ensure_page_initialized,
    handle_studio_page_transition,
    sanitize_persisted_snapshots,
)
from instrument_transposition import (
    CHART_IN_INSTRUMENT_KEY_KEY,
    TRANSPOSING_INSTRUMENTS,
    apply_pending_transposing_instrument,
    chart_in_instrument_key,
    effective_chart_key,
    effective_practice_key,
    instrument_display_name,
    is_transposing_instrument,
    options_for_instrument,
    chart_transpose_cache_signature,
    render_practice_transposing_controls,
    render_sidebar_transposing_controls,
    render_transposing_info_card,
    request_transposing_instrument_sync,
    resolve_practice_keys,
    sync_written_key_instrument_anchor,
    selected_saxophone_type,
    selected_transposing_type,
    semitone_steps_for_label,
    transpose_key_for_instrument,
    written_key_for_instrument,
)

from backing_audio import (
    _arrangement_intensity_overlay,
    _build_arrangement_context,
    _chord_head,
    _section_intensity,
    _section_role,
    backing_bytes_to_float,
    bass_note,
    chord_notes,
    generate_backing_track,
    infer_groove_style,
    pcm16_wav_bytes_from_float,
    synthesize_chords_to_numpy,
    wav_bytes_from_float,
)
import chord_subdivisions
from coach_overlay import section_overlay_html as _section_overlay
from groove_feel import (
    GROOVE_PROFILE,
    get_profile as _groove_profile,
    instrument_phrasing_hint as _groove_instrument_hint,
    resolve_groove_style as _groove_resolve,
    short_feel_tag as _groove_short_feel_tag,
)


def _resolve_groove_override(groove_override: str | None) -> str:
    """Resolve a user-facing groove pick into a concrete profile label.

    The Practice page passes the user's ``practice_groove_style`` selectbox
    value here. Anything blank or ``"Auto"`` falls back to the song-data
    inference that ``backing_audio.infer_groove_style`` provides, so this
    helper is safe to use anywhere we previously hard-coded
    ``infer_groove_style(globals().get("song_data", {}), "Auto")``.
    """
    return _groove_resolve(groove_override, globals().get("song_data") or {})

from song_chart_editor import render_chart_editor_panel
from songs.backing_chart import render_backing_chord_chart
from songs.sheet_format import (
    bars_per_row_for_song,
    has_lyric_chord_sheet,
    lead_sheet_body_class,
    lyric_chord_chart_sections,
    merge_lyric_cues_for_song,
)
from songs.lyric_chord_renderer import render_lyric_chord_sheet

_PRACTICE_STUDIO_IMPORT_ERROR: Exception | None = None
try:
    from practice_studio import (
        PRACTICE_FOCUS_FULL,
        beginner_transpose_suggestions,
        build_practice_session_from_logs,
        fretboard_ascii,
        practice_active_section_name,
        practice_display_sections,
        practice_first_section_for_type,
        practice_is_full_song,
        practice_resolve_focus_section,
        practice_section_options,
        practice_section_type,
        practice_sections_for_type,
        rhythm_guide_markdown,
        scale_suggestions_for_chord,
        section_deep_practice_markdown,
        active_song_card_details,
        song_card_meta,
        song_groove_seed,
    )
    from practice_notation import generate_practice_notation, notation_tab_html
except ImportError as _practice_studio_import_err:  # noqa: BLE001 - reported in dev mode
    _PRACTICE_STUDIO_IMPORT_ERROR = _practice_studio_import_err
    PRACTICE_FOCUS_FULL = "Full Song"

    import re as _ps_re

    _PS_FALLBACK_TRAILING_NUM = _ps_re.compile(r"\s+\d+[A-Za-z]?\s*$")

    def practice_section_type(name):
        s = str(name or "").strip()
        if not s:
            return ""
        return _PS_FALLBACK_TRAILING_NUM.sub("", s).strip() or s

    def practice_is_full_song(focus):
        if not focus:
            return True
        return str(focus).strip().lower() == PRACTICE_FOCUS_FULL.lower()

    def practice_section_options(sections):
        seen: set[str] = set()
        out: list[str] = [PRACTICE_FOCUS_FULL]
        for name in sections or {}:
            if not (sections or {}).get(name):
                continue
            t = practice_section_type(name)
            key = t.lower()
            if not t or key in seen:
                continue
            seen.add(key)
            out.append(t)
        return out

    def practice_first_section_for_type(sections, type_label):
        if not type_label:
            return None
        target = practice_section_type(type_label).lower()
        if not target:
            return None
        for name, chords in (sections or {}).items():
            if not chords:
                continue
            if practice_section_type(name).lower() == target:
                return name
        return None

    def practice_sections_for_type(sections, type_label):
        if not type_label:
            return []
        target = practice_section_type(type_label).lower()
        if not target:
            return []
        return [
            n
            for n, ch in (sections or {}).items()
            if ch and practice_section_type(n).lower() == target
        ]

    def practice_resolve_focus_section(focus, sections):
        if practice_is_full_song(focus):
            return None
        type_match = practice_first_section_for_type(sections or {}, focus)
        if type_match:
            return type_match
        if focus and focus in (sections or {}) and (sections or {}).get(focus):
            return focus
        return None

    def practice_display_sections(sections, focus):
        if practice_is_full_song(focus):
            return sections
        resolved = practice_resolve_focus_section(focus, sections)
        if resolved:
            return {resolved: (sections or {})[resolved]}
        return sections

    def practice_active_section_name(focus, sections):
        return practice_resolve_focus_section(focus, sections)
    def song_card_meta(record):
        return {"title": record.get("title", ""), "artist": record.get("artist", ""), "genre": "", "key": "C", "bpm": None, "difficulty": "", "instruments": "", "trusted": False}

    def beginner_transpose_suggestions(**kwargs):
        return []

    def section_deep_practice_markdown(**kwargs):
        return ""

    def scale_suggestions_for_chord(*args, **kwargs):
        return ""

    def rhythm_guide_markdown(*args, **kwargs):
        return ""

    def build_practice_session_from_logs(*args, **kwargs):
        return {}

    def fretboard_ascii(*args, **kwargs):
        return ""

    def song_groove_seed(*args, **kwargs):
        return 0

    def generate_practice_notation(**kwargs):
        from types import SimpleNamespace

        return SimpleNamespace(
            format="tab",
            title=kwargs.get("song_title", "Song"),
            chord_labels="C",
            rhythm_counts="1 2 3 4",
            body="e|--0---|\nB|--1---|\nG|--0---|\nD|--2---|\nA|--3---|\nE|--3---|",
            abc="",
            num_lines=1,
            instrument=kwargs.get("instrument", "Guitar"),
            section="Section",
            focus=kwargs.get("focus", ""),
            difficulty="medium",
        )

    def notation_tab_html(result):
        return f"<pre>{getattr(result, 'body', '')}</pre>"

_APP_UI_LOADED = False
_APP_UI_IMPORT_ERROR = None

try:
    from app_ui import (
        app_hero,
        compact_page_title,
        follow_along_status_html,
        inject_app_theme,
        page_header,
        begin_studio_control_deck,
        close_control_section,
        end_studio_control_deck,
        open_control_section,
        render_cross_page_links,
        render_global_studio_bar,
        nav_icon_button_label,
        render_page_quick_nav,
        render_section_jump_bar,
        render_studio_brand_header,
        render_studio_nav,
        render_sidebar_studio_nav,
        render_main_sidebar_nav_expand_chip,
        ensure_sidebar_nav_defaults,
        sync_sidebar_nav_body_dataset,
        ensure_studio_page,
        session_badges,
        sidebar_section,
        sidebar_source_banner,
        sidebar_goto_song_selection,
        render_song_library_panel_header,
        render_song_library_selection_chip,
        render_song_library_field_label,
        render_backing_panel_header,
        render_backing_panel_shell_open,
        render_backing_panel_shell_close,
        render_backing_field_label,
        render_backing_transport_status,
        render_backing_scope_panel_header,
        backing_scope_loop_summary_text,
        backing_scope_loop_summary_badge_html,
        BACKING_SCOPE_QUICK_LINKS,
        inject_backing_studio_styles,
        inject_song_picker_page_styles,
        inject_practice_page_styles,
        render_practice_control_panel_header,
        practice_setup_summary_text,
        practice_setup_summary_badge_html,
        PRACTICE_QUICK_LINKS,
        render_backing_studio_deck_header,
        render_backing_transport_feedback,
        render_backing_setup_group_open,
        render_backing_setup_group_close,
        render_backing_setup_section_open,
        render_backing_setup_section_close,
        render_backing_setup_context_strip,
        render_active_song_key_row,
        render_active_song_hub_open,
        render_active_song_hub_hero,
        render_active_song_hub_close,
        active_song_key_row_html,
    )
    _APP_UI_LOADED = True
except Exception as _app_ui_first_err:
    import traceback

    traceback.print_exc()
    _APP_UI_IMPORT_ERROR = _app_ui_first_err
    _app_ui_path = Path(__file__).resolve().parent / "app_ui.py"
    if _app_ui_path.is_file():
        try:
            import importlib.util

            _app_ui_spec = importlib.util.spec_from_file_location("app_ui", str(_app_ui_path))
            if _app_ui_spec and _app_ui_spec.loader:
                _app_ui_mod = importlib.util.module_from_spec(_app_ui_spec)
                _app_ui_spec.loader.exec_module(_app_ui_mod)
                app_hero = _app_ui_mod.app_hero
                compact_page_title = _app_ui_mod.compact_page_title
                follow_along_status_html = _app_ui_mod.follow_along_status_html
                inject_app_theme = _app_ui_mod.inject_app_theme
                page_header = _app_ui_mod.page_header
                begin_studio_control_deck = _app_ui_mod.begin_studio_control_deck
                close_control_section = _app_ui_mod.close_control_section
                end_studio_control_deck = _app_ui_mod.end_studio_control_deck
                open_control_section = _app_ui_mod.open_control_section
                render_cross_page_links = getattr(_app_ui_mod, "render_cross_page_links", None)
                render_global_studio_bar = _app_ui_mod.render_global_studio_bar
                nav_icon_button_label = getattr(_app_ui_mod, "nav_icon_button_label", lambda pid: pid)
                render_page_quick_nav = getattr(_app_ui_mod, "render_page_quick_nav", None)
                render_section_jump_bar = getattr(_app_ui_mod, "render_section_jump_bar", None)
                render_studio_brand_header = _app_ui_mod.render_studio_brand_header
                render_studio_nav = _app_ui_mod.render_studio_nav
                ensure_studio_page = getattr(_app_ui_mod, "ensure_studio_page", None)
                session_badges = _app_ui_mod.session_badges
                sidebar_section = _app_ui_mod.sidebar_section
                sidebar_source_banner = _app_ui_mod.sidebar_source_banner
                sidebar_goto_song_selection = getattr(
                    _app_ui_mod, "sidebar_goto_song_selection", None
                )
                render_song_library_panel_header = getattr(
                    _app_ui_mod, "render_song_library_panel_header", None
                )
                render_song_library_selection_chip = getattr(
                    _app_ui_mod, "render_song_library_selection_chip", None
                )
                render_song_library_field_label = getattr(
                    _app_ui_mod, "render_song_library_field_label", None
                )
                inject_backing_studio_styles = getattr(
                    _app_ui_mod, "inject_backing_studio_styles", lambda _st: None
                )
                inject_song_picker_page_styles = getattr(
                    _app_ui_mod, "inject_song_picker_page_styles", lambda _st: None
                )
                inject_practice_page_styles = getattr(
                    _app_ui_mod, "inject_practice_page_styles", lambda _st: None
                )
                render_practice_control_panel_header = getattr(
                    _app_ui_mod, "render_practice_control_panel_header", lambda *_a, **_k: None
                )
                practice_setup_summary_text = getattr(
                    _app_ui_mod, "practice_setup_summary_text", lambda **_k: ""
                )
                practice_setup_summary_badge_html = getattr(
                    _app_ui_mod, "practice_setup_summary_badge_html", lambda s: f"<span>{s}</span>"
                )
                PRACTICE_QUICK_LINKS = getattr(_app_ui_mod, "PRACTICE_QUICK_LINKS", [])
                render_backing_studio_deck_header = getattr(
                    _app_ui_mod, "render_backing_studio_deck_header", lambda _st: None
                )
                render_backing_transport_feedback = getattr(
                    _app_ui_mod,
                    "render_backing_transport_feedback",
                    lambda _st, **kwargs: None,
                )
                render_backing_setup_group_open = getattr(
                    _app_ui_mod, "render_backing_setup_group_open", lambda *_a, **_k: None
                )
                render_backing_setup_group_close = getattr(
                    _app_ui_mod, "render_backing_setup_group_close", lambda *_a, **_k: None
                )
                render_active_song_key_row = getattr(
                    _app_ui_mod, "render_active_song_key_row", lambda *_a, **_k: None
                )
                render_backing_setup_section_open = getattr(
                    _app_ui_mod, "render_backing_setup_section_open", lambda *_a, **_k: None
                )
                render_backing_setup_section_close = getattr(
                    _app_ui_mod, "render_backing_setup_section_close", lambda *_a, **_k: None
                )
                render_backing_setup_context_strip = getattr(
                    _app_ui_mod, "render_backing_setup_context_strip", lambda *_a, **_k: None
                )
                render_active_song_hub_open = getattr(
                    _app_ui_mod, "render_active_song_hub_open", lambda *_a, **_k: None
                )
                render_active_song_hub_close = getattr(
                    _app_ui_mod, "render_active_song_hub_close", lambda *_a, **_k: None
                )
                render_active_song_hub_hero = getattr(
                    _app_ui_mod, "render_active_song_hub_hero", lambda *_a, **_k: None
                )
                render_backing_panel_header = getattr(
                    _app_ui_mod, "render_backing_panel_header", lambda *_a, **_k: None
                )
                render_backing_panel_shell_open = getattr(
                    _app_ui_mod, "render_backing_panel_shell_open", lambda *_a, **_k: None
                )
                render_backing_panel_shell_close = getattr(
                    _app_ui_mod, "render_backing_panel_shell_close", lambda *_a, **_k: None
                )
                render_backing_field_label = getattr(
                    _app_ui_mod, "render_backing_field_label", lambda *_a, **_k: None
                )
                render_backing_transport_status = getattr(
                    _app_ui_mod, "render_backing_transport_status", lambda *_a, **_k: None
                )
                render_backing_scope_panel_header = getattr(
                    _app_ui_mod, "render_backing_scope_panel_header", lambda *_a, **_k: None
                )
                backing_scope_loop_summary_text = getattr(
                    _app_ui_mod,
                    "backing_scope_loop_summary_text",
                    lambda *_a, **_k: "Full song ×2",
                )
                backing_scope_loop_summary_badge_html = getattr(
                    _app_ui_mod,
                    "backing_scope_loop_summary_badge_html",
                    lambda s: f"<span>{s}</span>",
                )
                BACKING_SCOPE_QUICK_LINKS = getattr(
                    _app_ui_mod, "BACKING_SCOPE_QUICK_LINKS", []
                )
                _APP_UI_LOADED = True
                _APP_UI_IMPORT_ERROR = None
        except Exception as _app_ui_path_err:
            traceback.print_exc()
            _APP_UI_IMPORT_ERROR = _app_ui_path_err

def _fallback_active_song_hub_open(st: Any, *, extra_class: str = "") -> None:
    _cls = f"ui-active-song-hub {extra_class}".strip()
    st.markdown(f'<div class="{_cls}">', unsafe_allow_html=True)
    st.markdown(
        '<div class="ui-active-song-hub-head">'
        '<span class="ui-active-song-hub-label">Current active song</span></div>',
        unsafe_allow_html=True,
    )


def _fallback_active_song_hub_close(st: Any) -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def _fallback_active_song_hub_hero(st: Any, **kwargs: Any) -> None:
    title = str(kwargs.get("title") or "Active song")
    st.markdown(f"**{title}**")


def _fallback_backing_setup_section_open(st: Any, title: str, *, icon: str = "") -> None:
    st.markdown(f"**{icon} {title}**".strip())


def _fallback_backing_setup_section_close(st: Any) -> None:
    pass


def _fallback_backing_setup_context_strip(st: Any, **kwargs: Any) -> None:
    st.caption(
        f"Keys: {kwargs.get('original_key')} → {kwargs.get('practice_key')} · "
        f"{kwargs.get('meter')} · {kwargs.get('groove')} · {kwargs.get('range_summary')}"
    )


def _ensure_app_ui_helpers() -> None:
    """Bind app_ui helpers if the primary import path omitted them."""
    global render_active_song_hub_open, render_active_song_hub_close, render_active_song_hub_hero
    global render_backing_setup_section_open, render_backing_setup_section_close
    global render_backing_setup_context_strip
    if not callable(globals().get("render_active_song_hub_open")):
        render_active_song_hub_open = _fallback_active_song_hub_open
    if not callable(globals().get("render_active_song_hub_close")):
        render_active_song_hub_close = _fallback_active_song_hub_close
    if not callable(globals().get("render_active_song_hub_hero")):
        render_active_song_hub_hero = _fallback_active_song_hub_hero
    if not callable(globals().get("render_backing_setup_section_open")):
        render_backing_setup_section_open = _fallback_backing_setup_section_open
    if not callable(globals().get("render_backing_setup_section_close")):
        render_backing_setup_section_close = _fallback_backing_setup_section_close
    if not callable(globals().get("render_backing_setup_context_strip")):
        render_backing_setup_context_strip = _fallback_backing_setup_context_strip


_ensure_app_ui_helpers()

if not _APP_UI_LOADED:
    st.error(
        "app_ui import failed: "
        f"{_APP_UI_IMPORT_ERROR!r}. "
        "Ensure **app_ui.py** is in the repository root next to this file, then redeploy. "
        "Using basic layout fallbacks so the app can still run."
    )
    render_active_song_hub_open = _fallback_active_song_hub_open
    render_active_song_hub_close = _fallback_active_song_hub_close
    render_active_song_hub_hero = _fallback_active_song_hub_hero
    render_backing_setup_section_open = _fallback_backing_setup_section_open
    render_backing_setup_section_close = _fallback_backing_setup_section_close
    render_backing_setup_context_strip = _fallback_backing_setup_context_strip

    def inject_app_theme() -> None:
        st.markdown(
            "<style>.block-container{padding-top:0.75rem;max-width:1180px;}</style>",
            unsafe_allow_html=True,
        )

    def app_hero(title: str, subtitle: str) -> None:
        st.markdown(f"### {title}")
        st.caption(subtitle)

    def render_studio_brand_header(**kwargs) -> None:
        title = kwargs.get("title") or "Daniel Cohen Music Practice Coach AI"
        tagline = kwargs.get(
            "tagline",
            "AI-powered practice studio for songs, backing tracks, harmony, "
            "improvisation, recording, and instrument-specific coaching.",
        )
        st.markdown(f"### {title}")
        st.caption(tagline)

    def page_header(icon: str, title: str, subtitle: str = "", badges=None) -> None:
        st.subheader(f"{icon} {title}".strip())
        if subtitle:
            st.caption(subtitle)

    def compact_page_title(icon: str, title: str, subtitle: str = "") -> None:
        st.markdown(f"#### {icon} {title}".strip())
        if subtitle:
            st.caption(subtitle)

    def session_badges(**kwargs) -> list[tuple[str, str]]:
        return [
            (kwargs.get("source_label", "Source"), "accent"),
            (f"🎵 {kwargs.get('song', '')}", ""),
            (f"Key {kwargs.get('display_key', '')}", "green"),
        ]

    def sidebar_section(title: str, *, icon: str = "", tone: str = "") -> None:
        label = f"{icon} {title}".strip() if icon else title
        st.sidebar.markdown(f"**{label}**")

    def sidebar_source_banner(source_kind: str, detail: str) -> None:
        st.sidebar.markdown(f"**{source_kind}**  \n{detail}")

    def sidebar_goto_song_selection(*, on_navigate) -> None:
        st.sidebar.button(
            "🎼 Song Selection",
            key="sidebar_goto_song_selection",
            use_container_width=True,
            on_click=on_navigate,
        )

    def open_control_section(letter: str, title: str, subtitle: str = "") -> None:
        st.markdown(f"**{letter}. {title}**")
        if subtitle:
            st.caption(subtitle)

    def close_control_section() -> None:
        pass

    def begin_studio_control_deck() -> None:
        pass

    def end_studio_control_deck() -> None:
        pass

    def render_studio_nav(session_state, *, rerun_fn) -> str:
        pages = [
            ("practice", "🎯 Practice"),
            ("picker", "🎼 Song Selection"),
            ("backing", "🎧 Backing Track"),
            ("custom", "✏️ Custom Progression"),
            ("creative", "🧠 Creative Lab"),
            ("multitrack", "🎚️ Multitrack"),
            ("analysis", "🎙️ Upload Analysis"),
            ("log", "📓 Practice Log"),
        ]
        session_state.setdefault("studio_page", "practice")
        labels = [p[1] for p in pages]
        ids = [p[0] for p in pages]
        cur = session_state.get("studio_page", "practice")
        idx = ids.index(cur) if cur in ids else 0
        pick = st.selectbox("Page", labels, index=idx, key="studio_page_fallback_select")
        navigate_studio_page(session_state, ids[labels.index(pick)])
        return session_state["studio_page"]

    def render_global_studio_bar(**kwargs) -> None:
        display_key_options = kwargs.get("display_key_options") or ["C"]
        instrument_options = kwargs.get("instrument_options") or ["Piano"]
        focus_options = kwargs.get("focus_options") or ["General"]
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.markdown(f"**{kwargs.get('song', 'Song')}**")
            st.caption(kwargs.get("source_label", ""))
        with c2:
            st.selectbox(
                "Practice / Concert Key",
                display_key_options,
                key="display_key",
                on_change=kwargs.get("on_display_key_change"),
            )
        with c3:
            st.selectbox("Level", ["Beginner", "Intermediate", "Advanced"], key="level")
        with c4:
            st.selectbox("Instrument", instrument_options, key="instrument")
        with c5:
            st.selectbox("Focus", focus_options, key="focus")
        if kwargs.get("show_bpm"):
            st.slider(
                "BPM",
                BACKING_BPM_MIN,
                BACKING_BPM_MAX,
                100,
                5,
                key=kwargs.get("bpm_key", "backing_track_bpm"),
            )

    def render_section_jump_bar(section_names, session_state, *, state_key="practice_focus_section", rerun_fn=None):
        options = [n for n in section_names if n]
        if not options:
            return None
        if session_state.get(state_key) not in options:
            session_state.setdefault(state_key, options[0])
        return st.radio(
            "Section focus",
            options,
            horizontal=True,
            key=state_key,
            label_visibility="collapsed",
        )

    def follow_along_status_html(pos: dict) -> str:
        if not pos:
            return ""
        return (
            f"**{pos.get('section', '')}** · {pos.get('chord', '')} · "
            f"bar {pos.get('bar_in_section', '')}/{pos.get('section_bars', '')} · "
            f"next {pos.get('next_chord', '—')}"
        )
from creative_lab_text import (
    current_song_context_lab as lab_make_ctx,
    chord_quality as lab_chord_quality,
    deep_harmonic_analysis_text as lab_deep_harmonic,
    creativity_arrangement_text,
    improvisation_intelligence_text,
    adaptive_weakness_detection_text,
    musical_development_tracker_text as lab_musical_dev,
)
try:
    from custom_progression_lab import (
        CPL_ACTIVE_KEY,
        CPL_SAVED_KEY,
        default_active_progression,
        parse_chord_line,
        flatten_sections_to_events,
        sections_to_chord_lists,
        analyze_tonal_center,
        estimate_key_center,
        harmonic_analysis_markdown,
        maybe_update_inferred_home_key,
        sync_written_home_key,
        written_home_key,
        commit_home_sections,
        on_cpl_adopt_detected_home_key,
        on_cpl_apply_manual_home_key,
        tonal_center_markdown,
        generate_exercises_markdown,
        lab_context_for_coaching,
        save_progression,
        delete_progression,
        ensure_original_structure,
        display_sections_for_key,
        commit_display_sections_to_original,
        anchor_home_key_to_display,
        on_cpl_anchor_home_key,
        backing_signature,
        deep_copy_sections,
        invalidate_cpl_derived_outputs,
        cpl_transpose_explanation_markdown,
        format_chord_bar_line,
        transpose_debug_lines,
        CPL_STYLE_CHOICES,
        apply_style_preset,
        build_preset_entries,
        suggest_next_chords,
        chord_tiles_html,
    )
except Exception as _cpl_import_err:
    import traceback

    traceback.print_exc()
    st.error(
        "Custom Progression Lab failed to import. "
        f"Underlying error: {_cpl_import_err!r}"
    )
    raise

CATALOG_LOAD_ERROR = None
_ALL_GENRE_FILTER = "All genres"
_PRIMARY_GENRE_PILLS: tuple[str, ...] = (
    "Pop",
    "Rock",
    "Jazz",
    "Jewish",
    "Blues",
    "Funk",
    "Classical",
    "Soul",
    "Country",
)
LIBRARY_MODE_FULL = "Full library"
LIBRARY_MODE_CORE = "Core library"
CHART_FILTER_ALL = "All songs"
CHART_FILTER_CURATED = "Curated highlights"
CHART_FILTER_FULL_CHARTS = "Full chord charts"
CHART_FILTER_EXTENDED = "Extended library"
DEFAULT_CHART_LIBRARY_MODE = LIBRARY_MODE_FULL
DEFAULT_CHART_STATUS_FILTER = CHART_FILTER_ALL
CATALOG_DEFAULTS_VERSION = 4
_LEGACY_LIBRARY_MODES = {
    "Include practice approximations": LIBRARY_MODE_FULL,
    "Trusted core charts only": LIBRARY_MODE_CORE,
}
_LEGACY_CHART_FILTERS = {
    "Any non-placeholder": CHART_FILTER_ALL,
    "Trusted core": CHART_FILTER_CURATED,
    "Verified": CHART_FILTER_FULL_CHARTS,
    "Practice approximation": CHART_FILTER_EXTENDED,
}

_VALID_LIBRARY_MODES = {LIBRARY_MODE_FULL, LIBRARY_MODE_CORE}
_VALID_CHART_FILTERS = {
    CHART_FILTER_ALL,
    CHART_FILTER_CURATED,
    CHART_FILTER_FULL_CHARTS,
    CHART_FILTER_EXTENDED,
}


def _normalize_library_mode(mode: str) -> str:
    mapped = _LEGACY_LIBRARY_MODES.get(mode, mode)
    if mapped in _VALID_LIBRARY_MODES:
        return mapped
    return DEFAULT_CHART_LIBRARY_MODE


def _normalize_chart_filter(mode: str) -> str:
    mapped = _LEGACY_CHART_FILTERS.get(mode, mode)
    if mapped in _VALID_CHART_FILTERS:
        return mapped
    return DEFAULT_CHART_STATUS_FILTER


try:
    # Load once per process; ``CATALOG_REVISION`` below handles hot data bumps.
    SONG_LIBRARY, SONG_PICKER_CATALOG, GENRES, ALL_SONG_RECORDS = load_song_catalog()
except Exception as _catalog_load_err:
    CATALOG_LOAD_ERROR = _catalog_load_err
    traceback.print_exc()
    _cached = st.session_state.get("_catalog_backup_records") if hasattr(st, "session_state") else None
    if _cached and len(_cached) > 10:
        ALL_SONG_RECORDS = _cached
        SONG_LIBRARY = st.session_state.get("_catalog_backup_library") or {}
        SONG_PICKER_CATALOG = st.session_state.get("_catalog_backup_picker") or {}
        GENRES = st.session_state.get("_catalog_backup_genres") or []
    else:
        st.error(
            f"Song catalog failed to load: {_catalog_load_err!r}. "
            "Redeploy with song_catalog/ intact or reload the app."
        )
        st.stop()

if hasattr(st, "session_state"):
    st.session_state["_catalog_backup_records"] = ALL_SONG_RECORDS
    st.session_state["_catalog_backup_library"] = SONG_LIBRARY
    st.session_state["_catalog_backup_picker"] = SONG_PICKER_CATALOG
    st.session_state["_catalog_backup_genres"] = list(GENRES)

# Hot-reload catalog when song data changes without a full process restart.
CATALOG_REVISION = "2026-05-28-jewish-traditional-v1"
if hasattr(st, "session_state") and st.session_state.get("_catalog_revision") != CATALOG_REVISION:
    try:
        from song_catalog.catalog import reload_song_catalog as _reload_catalog

        SONG_LIBRARY, SONG_PICKER_CATALOG, GENRES, ALL_SONG_RECORDS = _reload_catalog()
        st.session_state["_catalog_revision"] = CATALOG_REVISION
        st.session_state["_catalog_backup_records"] = ALL_SONG_RECORDS
        st.session_state["_catalog_backup_library"] = SONG_LIBRARY
        st.session_state["_catalog_backup_picker"] = SONG_PICKER_CATALOG
        st.session_state["_catalog_backup_genres"] = list(GENRES)
        if hasattr(st, "session_state"):
            invalidate_session_cache(st.session_state)
    except Exception:
        pass

TRUSTED_CORE_RECORDS = [
    r for r in ALL_SONG_RECORDS
    if r.get("trusted_core") or r.get("chart_status") in {"verified", "practice_level_verified"}
]
DEFAULT_SONG_RECORDS = TRUSTED_CORE_RECORDS or ALL_SONG_RECORDS

if hasattr(st, "session_state"):
    _cat_rev = st.session_state.get("_catalog_revision")
    if st.session_state.get("_trusted_core_revision") != _cat_rev:
        st.session_state["_trusted_core_records"] = TRUSTED_CORE_RECORDS
        st.session_state["_default_song_records"] = DEFAULT_SONG_RECORDS
        st.session_state["_trusted_core_revision"] = _cat_rev
    TRUSTED_CORE_RECORDS = st.session_state.get("_trusted_core_records", TRUSTED_CORE_RECORDS)
    DEFAULT_SONG_RECORDS = st.session_state.get("_default_song_records", DEFAULT_SONG_RECORDS)

    try:
        from music_persistent_state import prepare_music_workspace

        prepare_music_workspace(
            st,
            song_picker_catalog=SONG_PICKER_CATALOG,
            song_library=SONG_LIBRARY,
        )
        try:
            from music_persistent_state import (
                maybe_flush_deferred_page_change_save,
                prepare_canonical_music_page_state,
            )

            prepare_canonical_music_page_state(
                st.session_state,
                song_picker_catalog=SONG_PICKER_CATALOG,
                song_library=SONG_LIBRARY,
            )
            maybe_flush_deferred_page_change_save(st)
            try:
                from music_restore_phase import complete_music_restore_phase

                complete_music_restore_phase(st.session_state)
            except Exception:
                pass
        except Exception:
            pass
    except Exception as _music_restore_exc:
        import traceback

        st.session_state["_music_restore_error"] = str(_music_restore_exc)
        st.session_state["_music_restore_error_trace"] = traceback.format_exc()

    try:
        from suite_resume_launch import finalize_suite_resume_launch

        finalize_suite_resume_launch(
            st,
            "music",
            song_picker_catalog=SONG_PICKER_CATALOG,
            song_library=SONG_LIBRARY,
        )
    except Exception:
        pass

def _music_has_saved_song_context(session_state) -> bool:
    try:
        from music_persistent_state import music_should_skip_master_song_init

        return music_should_skip_master_song_init(session_state)
    except Exception:
        sel = session_state.get(SELECTED_SONG_STATE_KEY)
        if isinstance(sel, dict) and str(sel.get("pick_key") or "").strip():
            return True
        return bool(str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip())


# Defer trusted-core default + startup diag until after AMI hydrate and second workspace sync.
_skip_master_song_init = True

if st.session_state.get("_music_restore_error") and st.session_state.get("developer_mode"):
    st.sidebar.warning(
        f"Music session restore error (developer): {st.session_state['_music_restore_error']}"
    )

if pp.is_demo_mode(st) and not pp.demo_applied(st, "practice"):
    pdemo.load_practice_demo(st, SONG_PICKER_CATALOG, SONG_LIBRARY, ALL_SONG_RECORDS)
    st.rerun()

# === KARAOKE SESSION ACTIVE-SONG OVERRIDE ====================================
# When a karaoke set is running AND the active instrument is Voice,
# the active song is dictated by the current queue position. This MUST
# run BEFORE `get_song_context` so the rest of the app (Backing Track,
# lyrics, chord-follow, etc.) loads the karaoke-correct song. Also
# applies any pending advance flag queued by the audio-ended JS bridge
# or the visible Skip button.
#
# Strict voice gate: when the user has switched to Guitar / Piano /
# Bass / etc., we drop any pending karaoke advance flag and STOP the
# session so non-voice instruments never get hijacked by a stale
# karaoke pick_key. The queue itself is preserved so flipping back to
# Voice can resume the setlist.
if km.is_voice_mode(st.session_state):
    km.consume_pending_advance(st.session_state)
    if km.is_karaoke_session_active(st.session_state):
        _karaoke_target_pk = km.current_session_pick_key(st.session_state)
        if _karaoke_target_pk and _karaoke_target_pk != st.session_state.get(ACTIVE_CATALOG_PICK_KEY):
            try:
                apply_pick_key(st, _karaoke_target_pk, SONG_PICKER_CATALOG, song_library=SONG_LIBRARY)
            except KeyError:
                # Queued pick_key no longer in catalog (e.g. after rebuild).
                # Drop it and try the next one on the next rerun.
                km.remove_from_queue(st.session_state, _karaoke_target_pk)
else:
    # Non-voice instrument: hibernate the karaoke session so no
    # karaoke UI / behaviour leaks into the instrumentalist workflow.
    if km.is_karaoke_session_active(st.session_state):
        km.stop_session(st.session_state)
    st.session_state.pop(km.PENDING_KARAOKE_ADVANCE_KEY, None)
    st.session_state.pop(km.PENDING_KARAOKE_AUTO_GENERATE_KEY, None)
    st.session_state.pop(km.KARAOKE_TRANSITION_LABEL_KEY, None)
    st.session_state.pop(km.KARAOKE_SONG_ENDED_KEY, None)

if CPL_ACTIVE_KEY not in st.session_state:
    st.session_state[CPL_ACTIVE_KEY] = default_active_progression()
if CPL_SAVED_KEY not in st.session_state and not st.session_state.get("_music_workspace_blob_applied"):
    st.session_state[CPL_SAVED_KEY] = {}
ensure_active_music_source(st.session_state)

_restored_pick_key = ""
_sel = st.session_state.get(SELECTED_SONG_STATE_KEY)
if isinstance(_sel, dict):
    _restored_pick_key = str(_sel.get("pick_key") or "").strip()
if not _restored_pick_key:
    _restored_pick_key = str(st.session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
_music_state_restored = bool(st.session_state.get(SUITE_LOCAL_STATE_RESTORED_KEY)) or bool(_restored_pick_key)

# Trusted-core default seeding runs only in run_post_nav_music_startup_init (after restore).

# -------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------

def all_chords_from_sections(sections):

    out = []

    for section_chords in sections.values():
        out.extend(section_chords)

    return out



def _simplify_chord(chord, genre_name=""):
    chord = str(chord).strip()
    bass = ""
    head = chord
    if "/" in chord:
        head, bass = chord.split("/", 1)

    root, suffix = split_chord(head)
    s = suffix.lower()
    if "m7b5" in s or "dim" in s:
        out = root + "dim"
    elif s.startswith("m") and "maj" not in s:
        out = root + "m"
    elif "7" in s and ("blues" in genre_name.lower()):
        out = root + "7"
    else:
        out = root

    return f"{out}/{bass}" if bass else out


def _intermediate_chord(chord):
    chord = str(chord).strip()
    if "maj9" in chord:
        return chord.replace("maj9", "maj7")
    if "m9" in chord:
        return chord.replace("m9", "m7")
    if "13" in chord:
        return chord.replace("13", "7")
    return chord.replace("7#9", "7").replace("7b9", "7")


def _advanced_chord(chord, genre_name):
    chord = str(chord).strip()
    head = _chord_head(chord)
    bass = ""
    if "/" in chord:
        bass = "/" + chord.split("/", 1)[1]
    root, suffix = split_chord(head)
    s = suffix.lower()
    jazzish = genre_name in ["Jazz", "Blues"] or "maj7" in s or "m7" in s or "m7b5" in s

    if "13" in s or "9" in s or "alt" in s or "#9" in s or "b9" in s:
        return chord
    if jazzish and "maj7" in s:
        return root + "maj9" + bass
    if jazzish and "m7b5" in s:
        return root + "m7b5" + bass
    if jazzish and "m7" in s:
        return root + "m9" + bass
    if jazzish and "7" in s and "maj" not in s:
        return root + "13" + bass
    if genre_name in ["Pop", "Rock"] and s == "":
        return root + "add9" + bass
    if genre_name in ["Pop", "Rock"] and s == "m":
        return root + "m7" + bass
    return chord


def sections_for_level(song_data, level):
    from chart_level_arrangement import sections_for_level as _sections_for_level

    return _sections_for_level(song_data, level)


def chart_status_label(song_data):
    """Internal catalog quality flag — not shown in the UI."""
    user_ov = song_data.get("user_override") or {}
    if user_ov:
        return ("saved_edits", "success")
    status = (song_data.get("chart_status") or "placeholder").strip()
    return (status, "info")


def chart_source_caption(song_data) -> str:
    """User-facing chord chart line (no catalog quality labels)."""
    from song_chart_editor import chart_active_source_label

    label, kind = chart_active_source_label(song_data)
    if kind == "override":
        return f"**Chord chart:** ✅ {label}"
    return "**Chord chart:** Using Catalog Chart — open **Edit Song Chart** to customize."


def trusted_core_records(records):
    return [
        r for r in records
        if r.get("trusted_core")
        or r.get("chart_status") in {"verified", "practice_level_verified", "user_verified"}
    ]


def visible_records_for_mode(records, mode):
    mode = _normalize_library_mode(mode)
    if mode == LIBRARY_MODE_CORE:
        return trusted_core_records(records)
    return [r for r in records if r.get("chart_status") != "placeholder"]


def filter_records_by_chart_status(records, status_filter):
    status_filter = _normalize_chart_filter(status_filter)
    if status_filter == CHART_FILTER_ALL:
        return [r for r in records if r.get("chart_status") != "placeholder"]
    if status_filter == CHART_FILTER_CURATED:
        return trusted_core_records(records)
    if status_filter == CHART_FILTER_FULL_CHARTS:
        return [r for r in records if r.get("chart_status") in {"verified", "practice_level_verified"}]
    if status_filter == CHART_FILTER_EXTENDED:
        return [
            r for r in records
            if r.get("chart_status") in {
                "practice_simplified",
                "practice_level_verified",
                "practice_needs_review",
            }
        ]
    return records


def filter_records_by_level(records, level_filter):
    if level_filter == "Any level":
        return records

    def has_level_chart(row):
        versions = row.get("chart_versions") or {}
        return level_filter in versions or row.get("chart_status") != "placeholder"

    return [r for r in records if has_level_chart(r)]


def chord_blocks_for_selected_sections(sections, selected_names=None, *, song_data=None):
    selected = set(selected_names or [])
    out = []
    for section_name, section_chords in section_order(
        sections,
        section_names=section_names_from_song(song_data),
    ):
        if selected and section_name not in selected:
            continue
        out.extend(section_chords)
    return out


def chord_events_for_selected_sections(sections, selected_names=None, *, song_data=None):
    selected = set(selected_names or [])
    out = []
    for section_name, section_chords in section_order(
        sections,
        section_names=section_names_from_song(song_data),
    ):
        if selected and section_name not in selected:
            continue
        section_bars = len(section_chords)
        for idx, chord in enumerate(section_chords):
            out.append({
                "chord": chord,
                "section": section_name,
                "bar_in_section": idx,
                "section_bars": section_bars,
            })
    return out


def _humanized_backing_sections(
    sections: dict[str, list[str]],
    *,
    song_data: dict | None,
    groove_style: str,
    time_signature: str,
    humanize_level: str,
    preserve_exact_timing: bool,
    section_lyrics: dict | None = None,
    lyric_cues: dict | None = None,
) -> tuple[dict[str, list[str]], dict[tuple[str, int], object]]:
    """Apply performance-feel inference for backing playback and chart preview."""
    song_id = str((song_data or {}).get("title") or (song_data or {}).get("id") or "song")
    sig = (
        sections_tuple_signature(sections),
        groove_style,
        time_signature,
        humanize_level,
        preserve_exact_timing,
        song_id,
        tuple(sorted((section_lyrics or {}).keys())),
        tuple(sorted((lyric_cues or {}).keys())),
    )

    def _build():
        result = apply_harmonic_rhythm_intelligence(
            sections,
            groove_style=groove_style,
            time_signature=time_signature,
            humanize_level=humanize_level,
            preserve_exact_timing=preserve_exact_timing,
            section_names=section_names_from_song(song_data),
            song_data=song_data,
            section_lyrics=section_lyrics,
            lyric_cues=lyric_cues,
        )
        return result.sections, annotations_lookup(result.annotations)

    return session_cache_get_or_set(
        st.session_state,
        "hri_sections",
        sig,
        _build,
        copy_result=True,
    )


def compact_bar_summary(chords):
    if not chords:
        return ""
    chunks = []
    last = chords[0]
    count = 1
    for ch in chords[1:]:
        if ch == last:
            count += 1
        else:
            chunks.append(f"{last} ({count} bar{'s' if count != 1 else ''})")
            last = ch
            count = 1
    chunks.append(f"{last} ({count} bar{'s' if count != 1 else ''})")
    return "| " + " | ".join(chunks) + " |"


def short_chord_summary(chords, limit=4):
    if not chords:
        return "No chords"
    unique = []
    for chord in chords:
        if chord not in unique:
            unique.append(chord)
    suffix = " ..." if len(unique) > limit else ""
    return " - ".join(unique[:limit]) + suffix


def _section_lyric_lines(section_name, lyric_cues=None, section_lyrics=None, limit=4):
    user_text = (section_lyrics or {}).get(section_name, "")
    lines = [line.strip() for line in str(user_text).splitlines() if line.strip()]
    if not lines:
        lines = [
            line.strip()
            for line in (lyric_cues or {}).get(section_name, [])
            if str(line).strip()
        ]
    return lines[:limit]


def _markdown_table_cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def bar_grid_markdown(chords, bars_per_row=4):
    rows = []
    for i in range(0, len(chords), bars_per_row):
        row = chords[i:i + bars_per_row]
        display = []
        for j, ch in enumerate(row):
            absolute = i + j
            if absolute > 0 and ch == chords[absolute - 1]:
                display.append("%")
            else:
                display.append(ch)
        bars = [f"Bar {i + j + 1}" for j in range(len(row))]
        rows.append("| " + " | ".join(bars) + " |")
        rows.append("| " + " | ".join(["---"] * len(row)) + " |")
        rows.append("| " + " | ".join(f"**{cell}**" for cell in display) + " |")
        rows.append("")
    return "\n".join(rows).strip()


def lyric_aligned_bar_grid_markdown(
    section_name,
    chords,
    lyric_cues=None,
    section_lyrics=None,
    bars_per_row=4,
    song_data=None,
):
    if song_data is not None:
        lyric_cues = merge_lyric_cues_for_song(song_data, lyric_cues)
        bars_per_row = bars_per_row_for_song(song_data, mobile=False)
    lyric_lines = _section_lyric_lines(
        section_name,
        lyric_cues=lyric_cues,
        section_lyrics=section_lyrics,
        limit=max(1, int(np.ceil(max(1, len(chords)) / bars_per_row))),
    )
    if not lyric_lines:
        return bar_grid_markdown(chords, bars_per_row=bars_per_row)

    rows = []
    for i in range(0, len(chords), bars_per_row):
        row = chords[i:i + bars_per_row]
        display = []
        for j, ch in enumerate(row):
            absolute = i + j
            if absolute > 0 and ch == chords[absolute - 1]:
                display.append("%")
            else:
                display.append(ch)
        lyric = lyric_lines[min(i // bars_per_row, len(lyric_lines) - 1)]
        bars = [f"Bar {i + j + 1}" for j in range(len(row))]
        rows.append("| " + " | ".join(bars) + " | Phrase |")
        rows.append("| " + " | ".join(["---"] * len(row)) + " |---|")
        rows.append(
            "| "
            + " | ".join(f"**{_markdown_table_cell(cell)}**" for cell in display)
            + f" | _{_markdown_table_cell(lyric)}_ |"
        )
        rows.append("")
    return "\n".join(rows).strip()


def form_summary_markdown(sections):
    rows = ["| Section | Bars | Harmonic rhythm |", "|---|---:|---|"]
    for section_name, chords in sections.items():
        if not chords:
            continue
        rows.append(f"| {section_name} | {len(chords)} | {compact_bar_summary(chords)} |")
    return "\n".join(rows)


def render_song_timeline(sections, lyric_cues=None, section_lyrics=None):
    blocks = []
    total_bars = max(1, sum(len(chords) for chords in sections.values()))
    for section_name, chords in sections.items():
        if not chords:
            continue
        width = max(14, min(38, round((len(chords) / total_bars) * 100)))
        lyric_lines = _section_lyric_lines(
            section_name,
            lyric_cues=lyric_cues,
            section_lyrics=section_lyrics,
            limit=1,
        )
        lyric = lyric_lines[0] if lyric_lines else "Add lyrics or cues on Song Selection"
        blocks.append(
            f"""
            <div class="song-timeline-block" style="flex: {max(1, len(chords))} 1 {width}%;">
              <div class="timeline-section-name">{html.escape(section_name)}</div>
              <div class="timeline-bars">{len(chords)} bars</div>
              <div class="timeline-chords">{html.escape(short_chord_summary(chords))}</div>
              <div class="timeline-lyric">{html.escape(lyric)}</div>
            </div>
            """
        )

    if not blocks:
        st.info("No section data is available for this song yet.")
        return

    st.markdown(
        f"""
        <style>
        .song-timeline {{
            display: flex;
            gap: 10px;
            overflow-x: auto;
            padding: 10px 0 14px 0;
            margin-bottom: 8px;
        }}
        .song-timeline-block {{
            min-width: 150px;
            border: 1px solid rgba(49, 51, 63, 0.18);
            border-radius: 12px;
            padding: 12px;
            background: linear-gradient(180deg, rgba(240, 247, 255, 0.95), rgba(255, 255, 255, 0.98));
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }}
        .timeline-section-name {{
            font-weight: 750;
            font-size: 0.98rem;
            margin-bottom: 4px;
        }}
        .timeline-bars {{
            color: #5f6b7a;
            font-size: 0.82rem;
            margin-bottom: 8px;
        }}
        .timeline-chords {{
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 0.84rem;
            color: #172033;
            margin-bottom: 8px;
            white-space: nowrap;
        }}
        .timeline-lyric {{
            color: #475569;
            font-size: 0.82rem;
            line-height: 1.25;
        }}
        </style>
        <div class="song-timeline">
          {''.join(blocks)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _song_slug(song_name, artist_name=""):
    raw = f"{song_name}_{artist_name}".lower()
    return "".join(c if c.isalnum() else "_" for c in raw).strip("_")


def _section_base_name(section_name):
    return section_name.split("(", 1)[0].split("/", 1)[0].strip().lower()


def lyric_cues_from_section_lyrics(section_lyrics):
    cues = {}
    for section_name, text in (section_lyrics or {}).items():
        lines = [line.strip() for line in str(text).splitlines() if line.strip()]
        if lines:
            cues[section_name] = lines
    return cues


def _lyrics_cues_session_keys(song_title: str, song_artist: str) -> tuple[str, str, str]:
    """Return (slug, full_song_key, per_section_state_key) for session persistence."""
    slug = _song_slug(song_title, song_artist)
    return slug, f"song_lyrics::{slug}", f"section_lyrics::{slug}"


def _ordered_section_names_for_lyrics(section_names: list[str]) -> list[str]:
    """Stable section order for lyric/cue text areas (Intro → Verse → …)."""
    names = [str(n).strip() for n in section_names if str(n).strip()]
    if not names:
        return []

    def _rank(name: str) -> tuple[int, str]:
        low = name.lower()
        if "intro" in low:
            return (0, name)
        if "verse" in low:
            return (1, name)
        if "pre" in low and "chorus" in low:
            return (2, name)
        if "chorus" in low:
            return (3, name)
        if "bridge" in low:
            return (4, name)
        if "solo" in low:
            return (5, name)
        if "outro" in low:
            return (6, name)
        return (7, name)

    return sorted(names, key=_rank)


def _render_lyrics_and_cues_panel(
    *,
    song_title: str,
    song_artist: str,
    section_names: list[str],
    song_data: dict | None = None,
    chart_sections: dict | None = None,
    expanded: bool | None = None,
    prominent: bool = False,
    module_globals: dict | None = None,
) -> None:
    """Lyrics and cues editor on Song Selection (session + permanent user saves)."""
    from lyrics_cues_panel import render_lyrics_and_cues_panel

    render_lyrics_and_cues_panel(
        st,
        song_title=song_title,
        song_artist=song_artist,
        section_names=section_names,
        song_data=song_data,
        chart_sections=chart_sections,
        expanded=expanded,
        prominent=prominent,
        module_globals=module_globals,
    )



def lyric_cue_markdown(section_name, chords, lyric_cues, instrument, full_section_lyrics=None):
    cues = lyric_cues.get(section_name, []) if lyric_cues else []
    section_text = (full_section_lyrics or {}).get(section_name, "")
    out = []

    if cues:
        out.append("**Lyric / phrase cues:**")
        for idx, cue in enumerate(cues[:4]):
            bar_hint = min(idx * 4 + 1, max(1, len(chords)))
            chord_hint = chords[bar_hint - 1] if chords else "the first chord"
            out.append(f"- Bar {bar_hint} ({chord_hint}): {cue}")
        if instrument == "Voice" and section_text:
            out.append("\n**User-provided lyric text for this section:**")
            for line in str(section_text).splitlines()[:8]:
                if line.strip():
                    out.append(f"> {line.strip()}")
    elif instrument == "Voice":
        entry = chords[0] if chords else "the first chord"
        peak = chords[max(0, len(chords) // 2)] if chords else "the middle of the phrase"
        end = chords[-1] if chords else "the final chord"
        out.append("**Vocal placement guide:**")
        out.append(f"- Enter lightly on **{entry}**; save stronger tone for the phrase peak.")
        out.append(f"- Breathe before the section and around bar {max(1, min(5, len(chords)))} if needed.")
        out.append(f"- Aim phrase shape toward **{peak}**, then release cleanly into **{end}**.")
        out.append("- Practice once on vowels only, then add diction without tightening the jaw.")
    else:
        entry = chords[0] if chords else "the first chord"
        out.append("**Section locator cue:**")
        out.append(f"- {section_name}: phrase/section entry starts around **{entry}**. Add your own lyric cue on **Song Selection** for tighter alignment.")

    return "\n".join(out)


def _render_jewish_traditional_lyrics_panel(song_data: dict | None) -> None:
    """Show catalog Hebrew + transliteration for Shabbat / congregational songs."""
    ext = (song_data or {}).get("extensions") or {}
    if not ext.get("jewish_traditional"):
        return
    hebrew = ext.get("hebrew_lyrics") or {}
    translit = ext.get("transliteration") or {}
    if not hebrew and not translit:
        return
    section_order = list((song_data or {}).get("section_order") or [])
    if not section_order:
        section_order = sorted(set(hebrew.keys()) | set(translit.keys()))
    with st.expander("Hebrew & transliteration", expanded=True):
        st.caption(
            "Congregational Shabbat text — sing in Hebrew or follow the transliteration. "
            "Backing stays warm and acoustic (guitar, piano, strings, light percussion)."
        )
        for section_name in section_order:
            heb = str(hebrew.get(section_name) or "").strip()
            tr = str(translit.get(section_name) or "").strip()
            if not heb and not tr:
                continue
            st.markdown(f"**{_html.escape(section_name)}**")
            if heb:
                st.markdown(
                    f"<p dir='rtl' style='font-size:1.15rem;line-height:1.6;margin:0.25rem 0;'>"
                    f"{_html.escape(heb)}</p>",
                    unsafe_allow_html=True,
                )
            if tr:
                st.markdown(f"*{_html.escape(tr)}*")


def _lyric_lines_for_section(
    section_name: str,
    lyric_cues: dict | None,
    section_lyrics: dict | None,
    limit: int = 8,
) -> list[str]:
    """Return the user-entered lyric lines for a section.

    Priority:

    1. The full-text editor block (``section_lyrics[section_name]``) - this
       is what the Lyrics & Cues editor writes when the user types or
       pastes lyrics.
    2. The short cue list (``lyric_cues[section_name]``) - shorter, more
       compact phrasing cues used when the user only typed cues.

    The app **never** auto-fills copyrighted lyrics; this function only
    reads back data the user has explicitly entered.
    """
    full = ""
    if section_lyrics:
        full = str(section_lyrics.get(section_name, "") or "")
    if full.strip():
        lines = [ln.strip() for ln in full.splitlines() if ln.strip()]
    else:
        raw = (lyric_cues or {}).get(section_name) or []
        if isinstance(raw, str):
            raw = [raw]
        lines = [str(c).strip() for c in raw if str(c).strip()]
    return lines[:limit]


def _distribute_chord_chips(
    chords: list[str], lyric_lines: list[str]
) -> list[tuple[str, str]]:
    """Pair each lyric line with one representative chord.

    Doesn't try to do perfect lyric-to-chord alignment (which would
    require lyric/audio sync data we don't have). Instead it spreads
    the section's chords evenly across the lyric lines so the user
    sees a useful harmonic anchor for each line:

    * First line always carries the first chord.
    * Remaining lines pick a chord proportional to their position.
    """
    if not lyric_lines:
        return []
    if not chords:
        return [(line, "") for line in lyric_lines]
    n = len(lyric_lines)
    m = len(chords)
    out: list[tuple[str, str]] = []
    for i, line in enumerate(lyric_lines):
        idx = 0 if n <= 1 else min(i * m // n, m - 1)
        out.append((line, chords[idx]))
    return out


def _chord_strip_html(chords: list[str], emphasis: bool = False) -> str:
    """Compact ``Em → C → G → D`` strip used above each lyric block."""
    if not chords:
        return ""
    cls_extra = " lyric-guide-chord-strip--emphasis" if emphasis else ""
    chips = (
        ' <span class="lg-arrow" aria-hidden="true">\u2192</span> '
    ).join(
        f'<span class="lg-chord">{_html.escape(str(c))}</span>'
        for c in chords
    )
    return (
        f'<div class="lyric-guide-chord-strip{cls_extra}" '
        f'aria-label="Section chords">{chips}</div>'
    )


_VOICE_PHRASING_TIPS = (
    "Breathe before the first line; let the air settle before you sing.",
    "Shape the phrase - lean into the long vowel near the middle of each line.",
    "Hold emotional words a moment longer; release the consonant cleanly.",
    "Lighten repeated lines so the next iteration can grow.",
    "Build dynamic intensity as you approach the chorus or hook.",
    "Lift the tail of the phrase to lead into the next section.",
)


def _voice_phrasing_tip(section_name: str, line_index: int = 0) -> str:
    """Stable singer cue per section + line, cycling through phrasing tips."""
    if not section_name:
        return _VOICE_PHRASING_TIPS[0]
    # Hashing keeps the tip stable across reruns for the same section.
    seed = sum(ord(c) for c in str(section_name)) + int(line_index)
    return _VOICE_PHRASING_TIPS[seed % len(_VOICE_PHRASING_TIPS)]


def lyric_guide_html(
    sections, lyric_cues, instrument, section_lyrics=None
) -> str:
    """Practice page Lyric Phrasing Guide.

    Lyrics-first by design - the Full Chord Chart already covers chords,
    so this card focuses on:

    * **All** user-entered lyrics / cues for the full song.
    * Organised by real section name (Verse 1, Verse 2, Chorus 1, ...).
    * Phrasing / breath / delivery hints (extra emphasis in Voice mode).

    Sections with no user-entered text are skipped so instrumental
    parts (Intro / Outro / Solos / Interludes) don't clutter the view.
    If the song has *no* lyrics anywhere, a friendly empty state
    points the user back to Song Selection.
    """
    voice_mode = (instrument == "Voice")
    parts: list[str] = []
    parts.append(
        '<div class="lyric-guide" '
        f'data-instrument="{_html.escape(str(instrument or ""))}">'
    )
    parts.append('<h3 class="lyric-guide-title">Lyric Phrasing Guide</h3>')
    if voice_mode:
        parts.append(
            '<p class="lyric-guide-caption">All your lyrics &amp; cues, section by section. '
            "Use the phrasing notes for breath, vowel sustain, and delivery shape.</p>"
        )
    else:
        parts.append(
            '<p class="lyric-guide-caption">All user-entered lyrics &amp; cues for this song, '
            "organised by section. (Chord chart lives in the panel above.)</p>"
        )

    rendered_any = False
    for section_name, _chords in sections.items():
        lyric_lines = _lyric_lines_for_section(
            section_name, lyric_cues, section_lyrics, limit=24
        )
        if not lyric_lines:
            # Skip sections without user text - the chord chart already
            # shows instrumental parts; this card stays lyrics-only.
            continue
        rendered_any = True

        parts.append('<div class="lyric-guide-section">')
        parts.append(
            '<div class="lyric-guide-section-head">'
            f'<span class="lyric-guide-section-name">{_html.escape(str(section_name))}</span>'
            f'<span class="lyric-guide-section-meta">{len(lyric_lines)} lines</span>'
            "</div>"
        )
        parts.append('<div class="lyric-guide-lyrics">')
        for line in lyric_lines:
            parts.append(
                '<div class="lyric-guide-line lyric-guide-line--lyrics-only">'
                f'<span class="lyric-guide-lyric-text">{_html.escape(line)}</span>'
                "</div>"
            )
        parts.append("</div>")
        if voice_mode:
            tip = _voice_phrasing_tip(str(section_name))
            parts.append(
                '<p class="lyric-guide-phrasing-tip">'
                f'<span class="lyric-guide-phrasing-icon" aria-hidden="true">\U0001F3A4</span> '
                f"{_html.escape(tip)}"
                "</p>"
            )
        parts.append("</div>")

    if not rendered_any:
        parts.append(
            '<div class="lyric-guide-section">'
            '<p class="lyric-guide-empty">'
            "No lyrics or cues entered yet. Open "
            "<strong>Song Selection &rsaquo; Lyrics &amp; Cues</strong> "
            "to add lyrics per section - they'll appear here automatically."
            "</p>"
            "</div>"
        )

    parts.append("</div>")
    return "\n".join(parts)


# Backwards-compatible alias - older imports / callers may still use the
# old name. New code should call ``lyric_guide_html``.
def lyric_guide_markdown(sections, lyric_cues, instrument, section_lyrics=None):
    return lyric_guide_html(sections, lyric_cues, instrument, section_lyrics)


GUITAR_VOICING_LIBRARY = {
    "C": "x32010", "Cmaj7": "x32000", "Cmaj9": "x32430", "Cadd9": "x32030",
    "Cm": "x35543", "Cm7": "x35343", "Cm9": "x3133x", "C7": "x32310", "C13": "x32335",
    "D": "xx0232", "D/F#": "2x0232", "Dmaj7": "xx0222", "Dmaj9": "x5465x", "Dm": "xx0231",
    "Dm7": "xx0211", "Dm9": "x5355x", "D7": "xx0212", "D13": "x54557",
    "E": "022100", "Emaj7": "021100", "Em": "022000", "Em7": "020000", "Em9": "020002", "E7": "020100",
    "F": "133211", "Fmaj7": "1x2210", "Fmaj9": "1x2010", "Fm": "133111", "Fm7": "131111", "F7": "131211",
    "G": "320003", "G/B": "x20003", "Gmaj7": "3x443x", "Gmaj9": "3x423x", "Gm": "355333", "Gm7": "353333", "G7": "320001", "G13": "3x3455",
    "A": "x02220", "A/G": "3x2220", "Amaj7": "x02120", "Am": "x02210", "Am7": "x02010", "Am9": "x05500", "A7": "x02020", "A13": "x02022",
    "Bb": "x13331", "Bbmaj7": "x13231", "Bbm7": "x13121", "Bb7": "x13131",
    "B": "x24442", "Bm": "x24432", "Bm7": "x24232", "B7": "x21202", "Bm7b5": "x2323x",
}


def _voicing_family(chord, level):
    head = _chord_head(chord)
    root, suffix = split_chord(head)
    low = suffix.lower()
    if "m7b5" in low:
        return f"{chord}: half-diminished shell, root on 5th string, shape `x-1-2-1-2-x` moved to {root}"
    if "maj9" in low:
        return f"{chord}: maj9 color grip, root + 3rd + 7th + 9th (avoid doubling the 5th)"
    if "13" in low:
        return f"{chord}: dominant 13 shell, play 3rd + b7 + 13, omit the root if bass is covered"
    if "m9" in low:
        return f"{chord}: minor 9 shell, root + b3 + b7 + 9"
    if "maj7" in low:
        return f"{chord}: movable maj7 shell, keep 3rd and 7th on adjacent strings"
    if "m7" in low:
        return f"{chord}: minor 7 shell / drop-2 grip"
    if "7" in low:
        return f"{chord}: dominant 7 shell; advanced: add 9 or 13 on top"
    if level == "Advanced":
        return f"{chord}: try a triad inversion plus 9th if it fits the melody"
    return f"{chord}: playable open/barre grip; keep the top note clean"


def guitar_voicing_lines(chords, song_data, display_key, level):
    tabs = transpose_guitar_tabs(
        song_data.get("guitar_tabs", {}),
        song_data["key"],
        display_key,
    )
    seen = []
    for ch in chords:
        if ch not in seen:
            seen.append(ch)
    lines = ["\n## Guitar Chord Diagrams / Voicings", "_String order: E A D G B e_"]
    for ch in seen[:24]:
        if ch in tabs:
            lines.append(f"- **{ch}**: `{tabs[ch]}`")
        elif ch in GUITAR_VOICING_LIBRARY:
            lines.append(f"- **{ch}**: `{GUITAR_VOICING_LIBRARY[ch]}`")
        else:
            lines.append(f"- **{_voicing_family(ch, level)}**")
    if len(seen) > 24:
        lines.append(f"- ...plus {len(seen) - 24} more chord symbols in the full form.")
    return lines

def midi_note_name(m):

    names = [
        "C","C#","D","Eb","E","F",
        "F#","G","Ab","A","Bb","B"
    ]

    return names[m % 12]

def abc_note(midi_num):

    names = [
        "C","^C","D","_E","E","F",
        "^F","G","_A","A","_B","B"
    ]

    return names[midi_num % 12]

def render_abc(abc_text):

    escaped = (
        abc_text
        .replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("${", "\\${")
    )

    html = f"""
    <html>
    <head>
    <script src="https://cdn.jsdelivr.net/npm/abcjs@6.4.4/dist/abcjs-basic-min.js"></script>
    </head>
    <body>
    <div id="paper"></div>
    <script>
    ABCJS.renderAbc(
        "paper",
        `{escaped}`,
        {{
            responsive:"resize",
            staffwidth:760
        }}
    );
    </script>
    </body>
    </html>
    """

    components.html(
        html,
        height=350,
        scrolling=True
    )


def build_abc(song_name, sections):

    chords = all_chords_from_sections(
        sections
    )[:8]

    melody = []

    for ch in chords:

        mids = chord_notes(ch)

        melody.extend([
            abc_note(mids[0]),
            abc_note(mids[1]),
            abc_note(mids[2]),
            abc_note(mids[0])
        ])

    bars = [
        " ".join(melody[i:i+4])
        for i in range(0, len(melody), 4)
    ]

    music = " | ".join(bars) + " |"

    return f"""
X:1
T:{song_name}
M:4/4
L:1/4
K:C
{music}
"""


def _chart_section_role(section_name):
    name = str(section_name or "").lower()
    if "chorus" in name and "pre" not in name:
        return "chorus"
    if "pre" in name:
        return "pre"
    if "verse" in name or "main loop" in name:
        return "verse"
    if "bridge" in name:
        return "bridge"
    if "solo" in name:
        return "solo"
    if "intro" in name or "outro" in name or "ending" in name:
        return "gray"
    return "neutral"


def _chart_feel_label(style):
    return {
        "Pop groove": "Pop 8th-note feel",
        "Rock groove": "Rock 8th-note feel",
        "Jazz swing": "Swing feel",
        "Bossa nova": "Bossa feel",
        "Funk groove": "Funk syncopation",
        "Ballad": "Ballad feel",
    }.get(style or "Pop groove", style or "Pop groove")


def _chart_lyric_lines(section_name, lyric_cues=None, section_lyrics=None):
    user_text = (section_lyrics or {}).get(section_name, "")
    lines = [line.strip() for line in str(user_text).splitlines() if line.strip()]
    if not lines:
        lines = [
            line.strip()
            for line in (lyric_cues or {}).get(section_name, [])
            if str(line).strip()
        ]
    return lines


def _chart_grid_html(chords, current_bar=None, section_name="", *, beats_per_bar=4.0):
    if not chords:
        return "<div class='empty-chart'>No chords entered for this section.</div>"
    cells = []
    safe_section_attr = html.escape(str(section_name), quote=True)
    bpb = float(beats_per_bar) if beats_per_bar else 4.0
    for idx, chord in enumerate(chords):
        previous = chords[idx - 1] if idx else None
        same_as_prev = bool(previous and chord == previous)
        is_sub = chord_subdivisions.is_subdivided_bar(chord)
        is_tacet = (not is_sub) and is_no_chord_token(chord)
        is_hit = (not is_sub) and chord_subdivisions.is_hit_token(chord)
        if same_as_prev and not (is_sub or is_tacet or is_hit):
            display_token = "%"
            symbol_html = "%"
            subdivided_cell = False
            cell_has_push = False
        elif is_tacet:
            display_token = "N.C."
            symbol_html = "N.C."
            subdivided_cell = False
            cell_has_push = False
        elif is_hit:
            display_token = chord_subdivisions.hit_underlying_chord(chord) or str(chord)
            symbol_html = html.escape(display_token)
            subdivided_cell = False
            cell_has_push = False
        else:
            display_token = str(chord)
            if is_sub:
                subs = chord_subdivisions.parse_subdivisions(chord, beats_per_bar=bpb)
                total_weight = sum(max(0.0, float(s.weight)) for s in subs) or 1.0
                inner = []
                cell_has_push = False
                for sub_idx, sub in enumerate(subs):
                    if sub_idx > 0:
                        inner.append("<span class='sub-sep'>&rarr;</span>")
                    share_pct = (max(0.0, float(sub.weight)) / total_weight) * 100.0
                    push_cls = " push" if sub.push else ""
                    if sub.push:
                        cell_has_push = True
                    push_attr = " data-push='1'" if sub.push else ""
                    inner.append(
                        "<span class='sub-chord{push_cls}' data-sub='{i}' "
                        "data-beats='{beats:g}'{push_attr} "
                        "style='flex-grow:{grow:g};flex-basis:{basis:.4f}%;'>"
                        "{chord}</span>".format(
                            push_cls=push_cls,
                            i=sub_idx,
                            beats=float(sub.weight),
                            push_attr=push_attr,
                            grow=float(sub.weight),
                            basis=share_pct,
                            chord=html.escape(str(sub.chord)),
                        )
                    )
                symbol_html = "".join(inner)
                subdivided_cell = True
            else:
                symbol_html = html.escape(display_token)
                subdivided_cell = False
                cell_has_push = False
        current_class = " current-chord" if current_bar == idx + 1 else ""
        sub_class = " subdivided" if subdivided_cell else ""
        if is_tacet:
            sub_class += " tacet"
        if is_hit:
            sub_class += " hit"
        repeat_count = 1
        if display_token != "%" and not subdivided_cell and not is_tacet and not is_hit:
            for nxt in chords[idx + 1:]:
                if nxt != chord:
                    break
                repeat_count += 1
        elif is_tacet:
            for nxt in chords[idx + 1:]:
                if not is_no_chord_token(nxt):
                    break
                repeat_count += 1
        duration = f"<span class='duration'>{repeat_count} bars</span>" if repeat_count > 1 else ""
        if subdivided_cell:
            push_tag_cls = " has-push" if cell_has_push else ""
            tag_label = "Pushed change" if cell_has_push else "Passing &middot; subdivided bar"
            duration = f"{duration}<span class='subdivided-tag{push_tag_cls}'>{tag_label}</span>"
        elif is_tacet:
            duration = f"{duration}<span class='tacet-tag'>Tacet &middot; drums only</span>"
        elif is_hit:
            duration = f"{duration}<span class='hit-tag'>Hit &middot; stop-time</span>"
        cells.append(
            f"<div class='chord-cell live-chart-cell{current_class}{sub_class}' data-section='{safe_section_attr}' data-bar='{idx + 1}'>"
            f"<div class='bar-num'>Bar {idx + 1}</div>"
            f"<div class='chord-symbol'>{symbol_html}</div>"
            f"{duration}"
            "</div>"
        )
    return "<div class='lead-grid'>" + "".join(cells) + "</div>"


def _roman_for_chord(chord, key_name):
    try:
        key_root, key_suffix = split_chord(str(key_name or "C"))
        root, suffix = split_chord(_chord_head(chord))
        if not root:
            return "?"
        minor_key = key_suffix.lower().startswith("m")
        romans = {
            0: ("I", "i"), 1: ("bII", "bII"), 2: ("II", "ii"), 3: ("bIII", "III"),
            4: ("III", "#III"), 5: ("IV", "iv"), 6: ("#IV", "#iv"), 7: ("V", "v"),
            8: ("bVI", "VI"), 9: ("VI", "#VI"), 10: ("bVII", "VII"), 11: ("VII", "#VII"),
        }
        r = NOTE_TO_MIDI.get(root, NOTE_TO_MIDI.get(normalize_root(root), 60)) % 12
        k = NOTE_TO_MIDI.get(key_root, NOTE_TO_MIDI.get(normalize_root(key_root), 60)) % 12
        roman = romans.get((r - k) % 12, ("?", "?"))[1 if minor_key else 0]
        low = str(suffix).lower()
        if low.startswith("m") and "maj" not in low:
            roman = roman.lower()
        if "dim" in low or "m7b5" in low:
            roman += "o"
        if "7" in low and "maj" not in low:
            roman += "7"
        return roman
    except Exception:
        return "?"


def _inline_harmonic_analysis(section_name, chords, key_name):
    if not chords:
        return "No harmonic movement entered yet."
    condensed = []
    for chord in chords:
        if not condensed or condensed[-1] != chord:
            condensed.append(chord)
    roman_text = "-".join(_roman_for_chord(ch, key_name) for ch in condensed[:6])
    role = _chart_section_role(section_name)
    if role == "chorus":
        return f"Chorus harmony centers on <strong>{roman_text}</strong>; play it broader and let the resolution feel earned."
    if role == "bridge":
        return f"Bridge color: <strong>{roman_text}</strong> gives contrast before returning to the main form."
    if role == "verse":
        return f"Verse loop: <strong>{roman_text}</strong>. Keep the texture lighter so the melody has room."
    if any("/" in str(ch) for ch in chords):
        return f"Listen for bass movement inside <strong>{roman_text}</strong>; slash chords help connect the section."
    return f"Harmonic shape: <strong>{roman_text}</strong> across the main phrase."


def _backing_chord_color_tip(chords, instrument):
    family = _instrument_family(instrument) if "_instrument_family" in globals() else "general"
    for chord in chords:
        low = str(chord).lower()
        safe = html.escape(str(chord))
        if "add9" in low:
            return f"{safe} has an open add9 color; keep the 9th audible instead of burying it in a thick attack."
        if "maj7" in low:
            if family == "piano":
                return f"{safe} wants a lighter touch; voice the maj7 inside and let the top extension sing."
            if family == "guitar":
                return f"{safe} sounds best as a smaller grip; let the maj7 color ring instead of using a heavy full barre."
            return f"{safe} is a soft color chord; phrase into it gently and avoid over-accenting the 7th."
        if "sus" in low:
            return f"{safe} delays resolution; lean into the suspension, then release cleanly into the next bar."
        if "/" in str(chord):
            return f"{safe} is about bass motion; respect the written bass note when practicing the section."
        if "dim" in low or "m7b5" in low:
            return f"{safe} is passing tension; keep the line moving and resolve it clearly."
        if "7#9" in low or "7b9" in low or "13" in low:
            return f"{safe} adds dominant bite; make the tension rhythmic, then relax into the resolution."
    return ""




def _section_lyric_html(section_name, chords, instrument, lyric_cues=None, section_lyrics=None):
    lines = _chart_lyric_lines(section_name, lyric_cues=lyric_cues, section_lyrics=section_lyrics)
    family = _instrument_family(instrument) if "_instrument_family" in globals() else "general"
    if not lines:
        if family == "voice":
            return "<div class='lyric-box'>Voice phrase: add a lyric cue for exact alignment. Breathe before bar 1 and shape toward the middle of the section.</div>"
        return "<div class='lyric-box muted'>No lyric cue added for this section.</div>"
    safe_lines = [html.escape(line) for line in lines]
    if family == "voice":
        peak_bar = max(1, min(len(chords), int(np.ceil(max(1, len(chords)) / 2))))
        visible = "<br>".join(f"&ldquo;{line}&rdquo;" for line in safe_lines[:4])
        return (
            "<div class='lyric-box voice'>"
            f"<strong>Lyric / phrase cue:</strong><br>{visible}"
            f"<div class='phrase-note'>Breath before bar 1; phrase start at bar 1; grow toward bar {peak_bar}; chorus/hook sections carry the strongest delivery.</div>"
            "</div>"
        )
    return f"<div class='lyric-box'><strong>Lyric cue:</strong> &ldquo;{safe_lines[0]}&rdquo;</div>"


def full_chord_markdown(
    song_name,
    song_data,
    sections,
    instrument,
    display_key=None,
    level="Intermediate",
    lyric_cues=None,
    section_lyrics=None,
    groove_style="Pop groove",
    bpm=100,
    time_signature="4/4",
    current_section=None,
    current_bar=None,
    focus="",
    *,
    chart_mode: str = "practice",
    selected_section_names: list[str] | None = None,
    shape_sections: dict[str, list[str]] | None = None,
    capo_fret: int = 0,
    capo_shape_key: str = "",
    auto_inferences: dict[tuple[str, int], object] | None = None,
):
    """Practice musician chart. Use ``chart_mode='backing'`` for backing follow-along."""
    dk = display_key or song_data["key"]
    if chart_mode == "backing":
        return render_backing_chord_chart(
            song_name,
            song_data,
            sections,
            display_key=dk,
            level=level,
            groove_style=groove_style,
            bpm=bpm,
            time_signature=time_signature,
            current_section=current_section,
            current_bar=current_bar,
            section_lyrics=section_lyrics,
            selected_section_names=selected_section_names,
            show_user_lyric_preview=bool(section_lyrics),
            shape_sections=shape_sections,
            capo_fret=capo_fret,
            capo_shape_key=capo_shape_key,
            auto_inferences=auto_inferences,
        )
    merged_lyric_cues = merge_lyric_cues_for_song(song_data, lyric_cues)
    sheet_class = lead_sheet_body_class(song_data)
    total_bars = sum(len(chords) for chords in sections.values())
    show_full = not current_section or str(current_section).strip().lower() in (
        "full song",
        "full form",
        "",
    )
    # Beginner mode swaps "Verse 1" / "Verse 2" -> "Verse" on display
    # only. The underlying section dict keys stay raw so resolvers,
    # focus-section lookups, lyric maps, and chord-event timelines
    # keep working unchanged - only the rendered card header text
    # changes.
    _practice_display_labels: dict[str, str] = dict(
        (song_data or {}).get("_beginner_display_labels") or {}
    )

    def _display_section_name(name: str) -> str:
        if not name:
            return name
        return _practice_display_labels.get(str(name), str(name))

    now_playing = (
        "Full song" if show_full else _display_section_name(str(current_section))
    )
    ext = song_data.get("extensions") or {}

    style = """
<style>
.lead-sheet { font-family: system-ui, -apple-system, Segoe UI, sans-serif; }
.lead-header {
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 16px;
  padding: 16px 18px;
  margin-bottom: 14px;
  background: linear-gradient(180deg, #ffffff, #f8fafc);
}
.lead-title { font-size: 1.35rem; font-weight: 800; margin-bottom: 4px; }
.lead-subtitle { color: #475569; margin-bottom: 12px; }
.meta-row { display: flex; gap: 8px; flex-wrap: wrap; }
.meta-pill {
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 999px;
  padding: 5px 10px;
  background: #fff;
  font-size: 0.82rem;
  color: #334155;
}
.now-playing {
  border-left: 5px solid #22c55e;
  background: #f0fdf4;
  padding: 10px 12px;
  border-radius: 12px;
  margin: 12px 0 16px 0;
  font-weight: 750;
}
.section-card {
  border: 1px solid rgba(15, 23, 42, 0.13);
  border-left-width: 7px;
  border-radius: 16px;
  padding: 14px;
  margin-bottom: 14px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
}
.section-card.gray { border-left-color: #94a3b8; background: #f5f6f8; }
.section-card.verse { border-left-color: #60a5fa; background: #eef6ff; }
.section-card.pre { border-left-color: #2dd4bf; background: #eafaf7; }
.section-card.chorus { border-left-color: #22c55e; background: #eefaf0; }
.section-card.bridge { border-left-color: #a78bfa; background: #f5f0ff; }
.section-card.solo { border-left-color: #fb923c; background: #fff4e6; }
.section-card.neutral { border-left-color: #cbd5e1; background: #ffffff; }
.section-card.current {
  outline: 3px solid rgba(34, 197, 94, 0.28);
  box-shadow: 0 0 0 5px rgba(34, 197, 94, 0.08);
}
.section-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: baseline;
  margin-bottom: 10px;
}
.section-title { font-size: 1.12rem; font-weight: 800; color: #0f172a; }
.section-meta { color: #475569; font-size: 0.88rem; }
.lead-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(92px, 1fr));
  gap: 10px 12px;
  margin: 12px 0 14px 0;
}
.verified-core-sheet .lead-grid {
  grid-template-columns: repeat(4, minmax(96px, 1fr));
  gap: 12px 14px;
}
.verified-core-sheet .chord-symbol {
  font-size: 1.22rem;
  letter-spacing: -0.02em;
}
.verified-core-sheet .chord-cell {
  min-height: 76px;
  border-color: rgba(30, 64, 175, 0.2);
}
.verified-core-sheet .section-card {
  scroll-margin-top: 4.5rem;
}
@media (max-width: 760px) {
  .verified-core-sheet .lead-grid {
    grid-template-columns: repeat(2, minmax(100px, 1fr)) !important;
  }
}
.chord-cell {
  min-height: 72px;
  border: 1.5px solid rgba(15, 23, 42, 0.22);
  border-radius: 12px;
  background: linear-gradient(180deg, #ffffff, #f8fafc);
  padding: 7px 9px;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.chord-cell.current-chord {
  background: linear-gradient(180deg, #bbf7d0, #dcfce7);
  border-color: #15803d;
  box-shadow: 0 0 0 4px rgba(22, 163, 74, 0.22), 0 8px 18px rgba(22, 163, 74, 0.18);
  transform: translateY(-1px);
}
.bar-num { color: #64748b; font-size: 0.68rem; font-weight: 700; margin-bottom: 4px; }
.chord-symbol {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 1.34rem;
  font-weight: 900;
  letter-spacing: -0.03em;
  color: #0f172a;
}
.duration {
  display: inline-block;
  margin-top: 3px;
  color: #64748b;
  font-size: 0.70rem;
  font-weight: 700;
}
.chord-cell.subdivided .chord-symbol {
  display: flex;
  align-items: stretch;
  justify-content: center;
  gap: 3px;
  flex-wrap: nowrap;
  font-size: 0.98rem;
  letter-spacing: -0.02em;
  line-height: 1.05;
  width: 100%;
}
.chord-cell.subdivided .sub-chord {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 5px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(15, 23, 42, 0.10);
  transition: background 0.12s ease, color 0.12s ease;
  flex: 1 1 auto;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  position: relative;
}
.chord-cell.subdivided .sub-sep {
  color: #94a3b8;
  font-weight: 700;
  font-size: 0.82rem;
  margin: 0 1px;
  align-self: center;
}
.chord-cell.subdivided.current-chord .sub-chord {
  background: rgba(255, 255, 255, 0.55);
  color: #14532d;
}
.chord-cell.subdivided .sub-chord.active-sub {
  background: #15803d;
  color: #f0fdf4;
  border-color: #14532d;
  box-shadow: 0 0 0 2px rgba(22, 163, 74, 0.45);
}
.chord-cell.subdivided .sub-chord.push {
  border-color: #ea580c;
  background: linear-gradient(180deg, #fff7ed, #ffedd5);
  color: #9a3412;
  font-weight: 800;
}
.chord-cell.subdivided .sub-chord.push::after {
  content: "push";
  display: block;
  font-size: 0.55rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #c2410c;
  margin-top: 1px;
  line-height: 1;
}
.chord-cell.subdivided .sub-chord.push.active-sub {
  background: #ea580c;
  color: #fff7ed;
  border-color: #9a3412;
  box-shadow: 0 0 0 2px rgba(234, 88, 12, 0.42);
}
.chord-cell.subdivided .sub-chord.push.active-sub::after {
  color: #fff7ed;
}
.chord-cell.subdivided .subdivided-tag {
  display: block;
  margin-top: 4px;
  color: #15803d;
  font-size: 0.66rem;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.chord-cell.subdivided .subdivided-tag.has-push {
  color: #c2410c;
}
/* N.C. (no-chord / tacet) cell — dashed silver border + muted glyph
   so band breakdowns read at a glance instead of looking like a
   normal chord that happens to spell "N.C.". */
.chord-cell.tacet {
  background:
    repeating-linear-gradient(
      135deg,
      rgba(148, 163, 184, 0.05) 0 6px,
      rgba(148, 163, 184, 0.00) 6px 12px),
    linear-gradient(180deg, #f8fafc, #eef2f7);
  border-style: dashed;
  border-color: rgba(100, 116, 139, 0.55);
  color: #475569;
}
.chord-cell.tacet .chord-symbol {
  font-size: 1.05rem;
  font-weight: 800;
  letter-spacing: 0.02em;
  color: #334155;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
.chord-cell.tacet .chord-symbol::before {
  content: "♪";
  display: inline-block;
  transform: rotate(-12deg) scale(1.05);
  color: #94a3b8;
  text-decoration: line-through;
  text-decoration-thickness: 2px;
  text-decoration-color: #94a3b8;
  font-weight: 900;
}
.chord-cell.tacet.current-chord {
  background:
    repeating-linear-gradient(
      135deg,
      rgba(148, 163, 184, 0.10) 0 6px,
      rgba(148, 163, 184, 0.00) 6px 12px),
    linear-gradient(180deg, #fef9c3, #fde68a);
  border-color: #b45309;
  box-shadow: 0 0 0 4px rgba(180, 83, 9, 0.15), 0 0 22px rgba(180, 83, 9, 0.20);
}
.chord-cell.tacet .tacet-tag {
  display: block;
  margin-top: 3px;
  color: #475569;
  font-size: 0.66rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
/* Rhythmic-hit / stop-time cell — orange starburst styling so it
   pops as a band-stab even mid-chart. */
.chord-cell.hit {
  background: linear-gradient(180deg, #fff7ed 0%, #ffedd5 100%);
  border-color: rgba(234, 88, 12, 0.55);
  border-style: solid;
}
.chord-cell.hit .chord-symbol {
  color: #9a3412;
  font-weight: 900;
}
.chord-cell.hit .chord-symbol::after {
  content: " ✦";
  color: #ea580c;
  font-weight: 900;
}
.chord-cell.hit .hit-tag {
  display: block;
  margin-top: 3px;
  color: #c2410c;
  font-size: 0.64rem;
  font-weight: 900;
  letter-spacing: 0.10em;
  text-transform: uppercase;
}
.lyric-box, .analysis-box, .overlay-box {
  border-radius: 10px;
  padding: 9px 10px;
  margin-top: 8px;
  background: rgba(255, 255, 255, 0.72);
  color: #1f2937;
}
.lyric-box { font-style: italic; }
.lyric-box.voice { font-style: normal; }
.phrase-note { margin-top: 6px; color: #475569; font-size: 0.86rem; }
.analysis-box { border-left: 3px solid rgba(15, 23, 42, 0.22); }
.overlay-box { border-left: 3px solid rgba(37, 99, 235, 0.35); }
.muted { color: #64748b; }
@media (max-width: 760px) { .lead-grid { grid-template-columns: repeat(2, minmax(110px, 1fr)); } }
</style>
"""

    key_text = f"Key: {html.escape(str(dk))}"
    if dk != song_data["key"]:
        key_text += f" (orig. {html.escape(str(song_data['key']))})"
    meta_bits = [
        key_text,
        f"Level: {html.escape(str(level))}",
        f"Form: {total_bars} bars",
        f"Tempo: {int(bpm)} BPM",
        f"Time: {html.escape(str(time_signature))}",
        f"Feel: {html.escape(_chart_feel_label(groove_style))}",
        "Drums/Bass/Comping: active",
    ]
    meta = "".join(f"<span class='meta-pill'>{bit}</span>" for bit in meta_bits)
    header_note = (
        f"<div class='lead-subtitle'>{html.escape(str(ext['arrangement_notes']))}</div>"
        if ext.get("arrangement_notes")
        else ""
    )

    section_cards = []
    current_parts = set()
    if not show_full:
        current_parts = {str(current_section).strip()}
    for section_name, chords in sections.items():
        if not chords:
            continue
        if not show_full and section_name not in current_parts:
            continue
        role = _chart_section_role(section_name)
        is_current = section_name in current_parts
        now_label = "Now Playing" if is_current else ""
        current_bar_for_section = current_bar if is_current else None
        _section_display = _display_section_name(section_name)
        section_cards.append(
            f"""
<section class="section-card {role}{' current' if is_current else ''}">
  <div class="section-head">
    <div>
      <div class="section-title">{html.escape(_section_display)} - {len(chords)} bars</div>
      <div class="section-meta">{html.escape(_chart_feel_label(groove_style))}</div>
    </div>
    <div class="section-meta">{now_label}</div>
  </div>
  {_chart_grid_html(chords, current_bar=current_bar_for_section, section_name=section_name)}
  {_section_lyric_html(section_name, chords, instrument, lyric_cues=merged_lyric_cues, section_lyrics=section_lyrics or {})}
  <div class="overlay-box"><strong>{html.escape(str(instrument))}:</strong> {_section_overlay(instrument, focus, chords, section_name=section_name, groove_style=groove_style, time_signature=time_signature, bpm=bpm)}</div>
  <div class="analysis-box">{_inline_harmonic_analysis(section_name, chords, dk)}</div>
</section>
"""
            )

    return f"""
{style}
<div class="{sheet_class}">
  <div class="lead-header">
    <div class="lead-title">{html.escape(song_name)} - Musician Chart</div>
    <div class="lead-subtitle">{html.escape(str(song_data.get('artist', '')))} | {html.escape(str(song_data.get('genre', '')))}</div>
    {header_note}
    <div class="meta-row">{meta}</div>
  </div>
  <div class="now-playing">Now Playing: {html.escape(str(now_playing))}</div>
  {''.join(section_cards)}
</div>
"""

def vocal_practice_text(level, sections):
    longest = max((len(chords) for chords in sections.values()), default=4)
    return f"""
### Voice-Specific Practice
- **Breathing:** mark breaths before each section and before long phrases over {min(longest, 8)}-bar spans.
- **Phrase length:** speak the rhythm first, then sing on a single vowel before adding words.
- **Range awareness:** find the pitch center from the first and last chord of each section; avoid pushing the top notes.
- **Sustains:** practice held notes with steady air, then taper the release into the next bar.
- **Diction:** keep consonants short and vowels consistent through sustained notes.
- **Dynamics:** sing verses lighter, choruses fuller, and bridges with a clear emotional shift.
- **Section practice:** loop verse entries quietly; practice chorus entrances with stronger breath support.
"""


def guitar_practice_text(focus, level):
    focus = focus or ""
    if focus == "Rhythm":
        return f"""
### Guitar Rhythm Practice
- **Groove feel:** mute lightly with the fretting hand and lock the strum to the backing track.
- **Strumming:** start with downstrokes on quarter notes, then add eighth-note upstrokes.
- **Muting:** practice dead-strum bars between chord changes to keep time moving.
- **Transitions:** isolate the two hardest chord changes and loop each for 2 minutes.
- **Comping:** use smaller 3- or 4-note voicings for clean rhythmic consistency.
- **Level target:** {level} players should keep time steady before adding syncopation or extensions.
"""
    if focus == "Melody":
        return f"""
### Guitar Melody / Lead Practice
- **Phrasing:** sing the line first, then play it; leave space between ideas.
- **Slides and bends:** target chord tones on strong beats, especially 3rds and 7ths.
- **Vibrato:** hold sustained notes over stable chords and match vibrato speed to the groove.
- **Hammer-ons / pull-offs:** use them as articulation, not speed tricks.
- **Double stops:** outline thirds/sixths through the section changes.
- **Positioning:** map the melody around one fretboard position, then shift only for expressive reasons.
"""
    return f"""
### Guitar Practice
- Use playable voicings from the chart; avoid full six-string shapes when a smaller grip sounds cleaner.
- Mark common tones between chords and keep them ringing where possible.
- Practice one section with metronome, then with the backing track.
- For {level} level, prioritize clean time, clean tone, and intentional voicing choices.
"""


GUITAR_FINGERING_OPTIONS = {
    "Fm9": [
        ("lower", "131113", "Lower movable color; keep it light because full minor-9 grips can get dense."),
        ("shell", "1x1113", "Root plus minor shell and 9th color; good for comping."),
        ("upper", "xx3143", "Upper-register color voicing when bass or piano covers the root."),
    ],
    "Aadd9": [
        ("open", "x02420", "Open, ringing pop color; let the B string carry the add9."),
        ("triad", "x07600", "Small upper-register color shape; useful for ambient sections."),
        ("barre", "577600", "Moveable A-root color with open top strings if the key allows it."),
    ],
    "Bsus4": [
        ("open-ish", "x24400", "Modern ringing sus color; mute the low E."),
        ("barre", "x24452", "Clear Bsus4 barre grip resolving easily to B."),
        ("triad", "xx4452", "Upper-string sus shape for clean rhythm comping."),
    ],
    "D/F#": [
        ("open", "2x0232", "Classic D over F# bass; use thumb or first finger on low F#."),
        ("compact", "2x023x", "Smaller grip if the top string rings too brightly."),
        ("no-root-top", "xx4232", "Upper inversion when bass covers F#."),
    ],
    "Dadd9": [
        ("open", "xx0230", "Easy open D color; leave high E open for the 9th."),
        ("triad", "x54255", "Higher D color around 5th position."),
        ("barre", "x57755", "A-shape D with added 9 on top for a fuller chorus."),
    ],
    "G/B": [
        ("open", "x20033", "Open G over B; very useful for stepwise bass motion."),
        ("compact", "x2003x", "Smaller version for clean voice leading."),
        ("triad", "xx5433", "Upper G inversion if bass handles B."),
    ],
    "Gadd9": [
        ("open", "320203", "Country-pop open G color; keep top notes clean."),
        ("open-alt", "3x0203", "Lighter grip with less low-end mud."),
        ("triad", "xx5435", "Upper-string G color for tighter comping."),
    ],
    "Bbmaj7": [
        ("barre", "x13231", "Standard A-shape maj7 color."),
        ("shell", "6x776x", "Moveable shell voicing; good for jazz/pop comping."),
        ("upper", "xx7765", "Higher color voicing with the maj7 on top."),
    ],
    "Am7b5": [
        ("standard", "x0101x", "Compact half-diminished grip; resolve it clearly."),
        ("movable", "5x554x", "Moveable root-position shell."),
        ("upper", "xx7888", "Upper-register color for jazzier sections."),
    ],
    "Eadd9": [
        ("open", "024100", "Open E with F# color; good for the Love Story key-change lift."),
        ("barre", "x79977", "Higher E add9 color for a bigger final chorus."),
        ("triad", "xx4452", "Compact upper-voice color."),
    ],
    "C#m7": [
        ("barre", "x46454", "Standard minor-7 barre shape."),
        ("easy", "x42400", "Open-string color; works when a ringing pop texture is acceptable."),
        ("triad", "xx2424", "Compact top-string minor color."),
    ],
    "B/D#": [
        ("slash", "x64442", "B chord with D# in the bass; supports stepwise bass motion."),
        ("compact", "xx4442", "Use when the bassist covers the slash bass."),
    ],
    "A/C#": [
        ("slash", "x42220", "A chord with C# in the bass; smooth descent into Bm."),
        ("compact", "xx2220", "Upper-string version if bass handles C#."),
    ],
}


def _interesting_chord_names(chords):
    out = []
    for chord in chords:
        low = str(chord).lower()
        interesting = (
            "maj7" in low
            or "m7" in low
            or "add9" in low
            or "sus" in low
            or "dim" in low
            or "7b9" in low
            or "7#9" in low
            or "13" in low
            or "9" in low
            or "/" in str(chord)
        )
        if interesting and chord not in out:
            out.append(chord)
    return out


def chord_function_summary(chord):
    low = str(chord).lower()
    if "/" in str(chord):
        return "Slash chord: the chord color stays familiar while the bass note creates smoother voice leading."
    if "add9" in low:
        return "Add9 chord: a major or minor triad with the 9th added for open, modern color."
    if "maj7" in low:
        return "Major 7 chord: a soft tonic/subdominant color; it sounds settled but more emotional than a plain major triad."
    if "m7b5" in low or "dim" in low:
        return "Diminished/half-diminished color: passing tension that wants clear resolution."
    if "sus" in low:
        return "Suspended chord: the 3rd is delayed, creating tension before resolving."
    if "7b9" in low or "7#9" in low or "13" in low:
        return "Altered/extended dominant: strong tension that points toward the next chord."
    if "m7" in low:
        return "Minor 7 chord: warmer and more relaxed than a plain minor triad."
    if "9" in low or "11" in low:
        return "Extended chord: upper chord tones add color while the 3rd and 7th define the harmony."
    if low.endswith("6") or "/6" in low or "6/" in low:
        return "Sixth chord: adds a warm color tone without the full maj7 sweetness—common in pop piano comping."
    return "Chord-tone target: identify root, 3rd, and 5th first, then add color tones."


def chord_playing_advice(chord, instrument, level):
    family = _instrument_family(instrument)
    tones = _chord_tone_names(chord)
    if family == "guitar":
        options = GUITAR_FINGERING_OPTIONS.get(str(chord), [])
        if options:
            lines = [f"- **{label.title()}** `{shape}`: {desc}" for label, shape, desc in options]
        else:
            root, suffix = split_chord(_chord_head(chord))
            lines = [
                f"- **Easy version:** play a clean {root} triad first; add the color tone only after the change is steady.",
                f"- **Barre/moveable version:** use a root-position shape around the 5th or 7th fret and keep only 3-4 strings if the full grip is muddy.",
                f"- **Triad version:** reduce **{chord}** to three adjacent strings for rhythm parts.",
            ]
        return "\n".join(lines)
    if family == "piano":
        if level == "Advanced":
            return (
                f"- Left hand: root plus 7th or rootless shell.\n"
                f"- Right hand: 3rd/7th plus color tone; spread **{chord}** so the top note sings.\n"
                f"- Practice nearest inversion into the next chord, not block jumping."
            )
        return (
            f"- Left hand: root or root-fifth.\n"
            f"- Right hand: play the 3rd and 7th if present, then add one color tone.\n"
            f"- Keep the top note stable while moving to the next chord."
        )
    if family == "bass":
        return (
            f"- Outline **{chord}** with root, 5th, octave, then one approach note.\n"
            f"- Emphasize chord tones: {tones}.\n"
            f"- If it is a slash chord, honor the written bass note on beat 1."
        )
    if family == "winds":
        return (
            f"- Target chord tones: {tones}.\n"
            f"- Put the 3rd or 7th on a strong beat for harmonic clarity.\n"
            f"- Use scale motion only to connect into a chord tone."
        )
    if family == "voice":
        return (
            f"- Sing the root, 3rd, and 5th of **{chord}** on a neutral vowel.\n"
            f"- For harmony singing, try holding the 3rd or 7th while the melody moves.\n"
            f"- Listen for whether the chord feels resolved or suspended before shaping the phrase."
        )
    return f"- Learn the chord tones first: {tones}. Then connect them to the next chord in the section."


def chord_coach_markdown(chord, instrument, level):
    return f"""
**{chord}**

{chord_function_summary(chord)}

**How to play / target it on {instrument}:**
{chord_playing_advice(chord, instrument, level)}
""".strip()


def render_chord_coach_ui(
    chords,
    instrument,
    level,
    key_prefix,
    expanded=True,
    *,
    display_key: str = "C",
):
    unique_chords = []
    for chord in chords:
        if chord not in unique_chords:
            unique_chords.append(chord)
    if not unique_chords:
        st.info("No chords are available for the current song/section.")
        return

    coach_options = list(unique_chords)
    if any("–" in c or "-" in c for c in coach_options) is False:
        coach_options = coach_options + ["ii–V–I (in key)"]

    with st.expander("Chord Finder / How to Play", expanded=expanded):
        instrument, level, _focus = render_setup_quick_controls(
            st,
            session_state=st.session_state,
            key_prefix=f"{key_prefix}::chord_finder",
            instrument_options=DEFAULT_INSTRUMENT_OPTIONS,
            label="Instrument · level · focus",
            show_sync_caption=False,
        )
        st.caption("Pick any chord from the selected song and get instrument-specific playing guidance.")
        selected_chord = st.selectbox(
            "Chord to explain",
            coach_options,
            key=f"{key_prefix}::chord_coach_select",
        )
        coach_target = "ii–V–I" if selected_chord == "ii–V–I (in key)" else selected_chord
        st.markdown(chord_coach_markdown(coach_target, instrument, level))
        st.markdown(scale_suggestions_for_chord(coach_target, display_key, level, instrument))
        if instrument == "Guitar":
            st.markdown(fretboard_ascii(coach_target if coach_target != "ii–V–I" else "G", level))


def transposing_instrument_options(instrument):
    """Transposing type labels for the active instrument (from instrument_transposition)."""
    return options_for_instrument(instrument)


def transposed_key_for_instrument(concert_key, instrument_label):
    steps = semitone_steps_for_label(instrument_label)
    return transpose_chord(concert_key, steps)


def render_transposition_helper(concert_key, instrument, key_prefix, wrap_expander=True):
    if instrument == "Flute":
        ctx = st.expander("Instrument Key / Transposition Helper", expanded=True) if wrap_expander else _null_expander()
        with ctx:
            st.write(f"Concert key: **{concert_key}**")
            st.write("Flute is a concert-pitch instrument, so no transposition is needed.")
        return concert_key, False, "Flute (concert pitch)"

    if is_transposing_instrument(instrument):
        ctx = (
            st.expander("Instrument Key / Transposition Helper", expanded=True)
            if wrap_expander
            else _null_expander()
        )
        with ctx:
            if not wrap_expander:
                st.markdown("#### Transposing instrument helper")
            st.caption(
                "Use the **sidebar** for saxophone type and "
                "“Show chart in written key for instrument” (app-wide)."
            )
            written_key = written_key_for_instrument(concert_key, instrument, st.session_state)
            st.write(f"Concert key: **{concert_key}**")
            st.write(f"Written key: **{written_key}**")
            chart_k, mode = effective_chart_key(concert_key, instrument, st.session_state)
            st.write(f"Charts showing: **{chart_k}** ({mode})")
        t_type = selected_transposing_type(st.session_state, instrument)
        show_written = chart_in_instrument_key(st.session_state)
        chart_k, _ = effective_chart_key(concert_key, instrument, st.session_state)
        return chart_k, show_written, t_type

    options = transposing_instrument_options(instrument)
    if not options:
        return concert_key, False, None

    ctx = (
        st.expander("Instrument Key / Transposition Helper", expanded=True)
        if wrap_expander
        else _null_expander()
    )
    with ctx:
        if not wrap_expander:
            st.markdown("#### Transposing instrument helper")
        col_a, col_b, col_c = st.columns([1.2, 1.2, 1])
        with col_a:
            instrument_key = st.selectbox(
                "Transposing instrument",
                options,
                key=f"{key_prefix}::transposing_instrument",
            )
        written_key = transposed_key_for_instrument(concert_key, instrument_key)
        with col_b:
            st.write(f"Concert key: **{concert_key}**")
            st.write(f"Written key: **{written_key}**")
        with col_c:
            show_written = st.checkbox(
                "Show chart in instrument key",
                value=False,
                key=f"{key_prefix}::show_written_key",
            )
        st.caption(
            f"{instrument_key}: read/play in **{written_key}** when the concert chart is **{concert_key}**."
        )
    return written_key if show_written else concert_key, show_written, instrument_key


def _null_expander():
    from contextlib import contextmanager

    @contextmanager
    def _noop():
        yield

    return _noop()


def render_general_transpose_helper(
    original_key,
    display_key,
    display_sections,
    source_sections,
    key_prefix,
):
    steps = semitone_distance(original_key, display_key)
    orig_sample = all_chords_from_sections(source_sections)[:6]
    disp_sample = all_chords_from_sections(display_sections)[:6]
    if not orig_sample:
        orig_sample = ["C", "Am", "F", "G"]
        disp_sample = [
            transpose_chord(ch, steps) for ch in orig_sample
        ]
    st.markdown("#### General key transpose")
    st.caption(
        f"Original **{original_key}** → practice **{display_key}** "
        "(shown on the Active Song card). "
        f"Semitone shift: **{'+' if steps else ''}{steps}**."
    )
    pairs = [
        f"{a} → {b}"
        for a, b in zip(orig_sample, disp_sample)
    ]
    st.caption("Example chord shift: " + " | ".join(pairs))


def render_guitar_capo_helper(
    base_sections,
    sounding_key,
    key_prefix,
    wrap_expander=True,
):
    ctx_manager = (
        st.expander("Capo / Guitar Shape Helper", expanded=True)
        if wrap_expander
        else _null_expander()
    )
    with ctx_manager:
        render_guitar_capo_practice_panel(
            st,
            st.session_state,
            concert_key=sounding_key,
            sections=base_sections,
            key_prefix=key_prefix,
        )


def build_chord_event_timeline(events, bpm, loops, time_signature="4/4", beats_per_bar=None):
    """Expand a per-bar chord-event list into a flat sub-event timeline.

    Honours weighted subdivisions and push markers parsed from each bar's
    chord token (see :mod:`chord_subdivisions`). For a plain bar token
    like ``"C"`` this is a no-op (one entry covering the full bar). For a
    weighted token like ``"C:2|G:2"`` (half-bar) or
    ``"Fmaj7|Am7|C/D"`` (Piano Man passing group in 3/4) it emits one
    entry per sub-chord with the *exact* start/end times so the player,
    follow-along highlight, and embedded JS bridge all stay in lock-step
    with the synthesizer.

    Push markers (``Subdivision.push == True``) shift the sub-event's
    start time slightly earlier so the chord-follow highlight matches
    the actual audio attack of a pushed chord.
    """
    timeline = []
    if not events:
        return timeline
    if beats_per_bar is not None:
        bpb = float(beats_per_bar)
        beat_duration = 60.0 / max(1, bpm)
        bar_duration = beat_duration * bpb
    else:
        timing = meter_timing(bpm, time_signature)
        bar_duration = timing.bar_sec
        bpb = float(timing.pulses_per_bar)
        beat_duration = bar_duration / bpb if bpb > 0 else (60.0 / max(1, bpm))
    looped_events = events * max(1, int(loops))
    total_bars = len(looped_events)
    # Pre-compute the arrangement context (chorus passes, final
    # chorus, phrase positions, bridge recovery) so each timeline
    # entry can carry the same arrangement-intelligence the synth
    # uses. Karaoke visuals key off these fields to dim during
    # tacet bridge bars and saturate during the final chorus.
    try:
        arr_ctx = _build_arrangement_context(looped_events)
    except Exception:
        # If the arrangement helper isn't available (e.g. partial
        # imports during a failed hot-reload) we fall back to None
        # and downstream code uses neutral defaults.
        arr_ctx = None
    event_index = 0
    push_offset = beat_duration * 0.5  # pushes anticipate by half a beat
    for bar_idx, event in enumerate(looped_events):
        bar_start = bar_idx * bar_duration
        chord_token = event.get("chord", "")
        subs = chord_subdivisions.parse_subdivisions(chord_token, beats_per_bar=bpb)
        if not subs:
            continue
        sub_count = len(subs)
        section_name = event.get("section", "")
        bar_in_section = int(event.get("bar_in_section", 0)) + 1
        section_bars = int(event.get("section_bars", 1))
        # ---- Arrangement-intelligence fields ----
        if arr_ctx is not None:
            try:
                role_for_event = _section_role(section_name)
                base_intensity = _section_intensity(section_name, "Pop groove")
                arr_mul = _arrangement_intensity_overlay(
                    bar_idx, role_for_event, arr_ctx
                )
                arrangement_intensity = float(base_intensity * arr_mul)
                chorus_pass = int(arr_ctx.chorus_pass_at(bar_idx))
                is_final_chorus = bool(
                    arr_ctx.is_final_chorus_event(bar_idx)
                )
                is_breakdown_recovery = bool(
                    bar_idx in arr_ctx.bridge_recovery
                )
                phrase_pos = float(arr_ctx.phrase_pos(bar_idx))
            except Exception:
                role_for_event = ""
                arrangement_intensity = 1.0
                chorus_pass = 0
                is_final_chorus = False
                is_breakdown_recovery = False
                phrase_pos = 0.0
        else:
            role_for_event = ""
            arrangement_intensity = 1.0
            chorus_pass = 0
            is_final_chorus = False
            is_breakdown_recovery = False
            phrase_pos = 0.0
        # Quantise the intensity into a coarse mood bucket so the JS
        # doesn't have to threshold on every tick. Bucket boundaries
        # are tuned around the base intensity table in
        # ``_section_intensity`` (verse ≈ 0.78, pre ≈ 0.95,
        # chorus ≈ 1.18, climax ≈ 1.30).
        if is_breakdown_recovery and bar_idx == 0:
            mood = "neutral"  # impossible state, but be safe
        elif arrangement_intensity >= 1.25:
            mood = "climax"
        elif arrangement_intensity >= 1.05:
            mood = "chorus"
        elif arrangement_intensity >= 0.90:
            mood = "lift"
        elif arrangement_intensity >= 0.75:
            mood = "verse"
        else:
            mood = "soft"
        # Tacet bars (any spelling) read as a breakdown regardless
        # of intensity bucket — the visual should dim even if the
        # last computed intensity overshot.
        if is_no_chord_token(chord_token):
            mood = "tacet"
        beat_cursor = 0.0
        for sub_idx, sub in enumerate(subs):
            start_time = bar_start + beat_cursor * beat_duration
            duration = float(sub.weight) * beat_duration
            if sub.push:
                # Pushed chord lands earlier than its written beat. We
                # shorten the previous sub-event (and extend this one)
                # by ``push_offset`` so the timeline reflects the actual
                # attack ordering the synth produces.
                shifted_start = max(bar_start, start_time - push_offset)
                if timeline and timeline[-1]["end_time"] > shifted_start:
                    timeline[-1]["end_time"] = shifted_start
                    timeline[-1]["duration"] = (
                        timeline[-1]["end_time"] - timeline[-1]["start_time"]
                    )
                duration += (start_time - shifted_start)
                start_time = shifted_start
            end_time = start_time + duration
            entry = {
                "event_index": event_index,
                "absolute_bar": bar_idx + 1,
                "total_bars": total_bars,
                "section": section_name,
                "bar_in_section": bar_in_section,
                "section_bars": section_bars,
                "chord": sub.chord if sub_count > 1 else chord_token,
                "start_time": start_time,
                "duration": duration,
                "end_time": end_time,
                "beat_offset": round(beat_cursor, 6),
                "beat_duration": round(float(sub.weight), 6),
                "arrangement_intensity": round(arrangement_intensity, 4),
                "chorus_pass": chorus_pass,
                "is_final_chorus": is_final_chorus,
                "is_breakdown_recovery": is_breakdown_recovery,
                "phrase_pos": round(phrase_pos, 4),
                "mood": mood,
            }
            if sub_count > 1:
                entry["subdivision_index"] = sub_idx
                entry["subdivision_count"] = sub_count
                entry["parent_chord"] = chord_token
            if sub.push:
                entry["push"] = True
            timeline.append(entry)
            event_index += 1
            beat_cursor += float(sub.weight)
    return timeline


# ---------------------------------------------------------------------------
# Cached backing-track generation (LRU-ish; tied to the input signature)
# ---------------------------------------------------------------------------
# We can't use st.cache_data here because the synth result is a bytes
# blob produced from numpy + per-song RNG seeding, and Streamlit's
# decorator infers an unhashable signature from the events list. A
# tiny manual cache keyed on the exact playback signature gives us
# instant repeat-Generate ("regenerate after stop", "skip Play and click
# Generate again") and stays bounded in memory.

_BACKING_WAV_CACHE: "dict[tuple, bytes]" = {}
_BACKING_TIMELINE_CACHE: "dict[tuple, list[dict]]" = {}
_BACKING_CACHE_MAX = 12  # last N distinct signatures - tiny memory footprint


def _evict_oldest(cache: dict) -> None:
    while len(cache) > _BACKING_CACHE_MAX:
        # Python dicts preserve insertion order, so popitem(last=False)
        # equivalent is just popping the first key.
        try:
            first_key = next(iter(cache))
        except StopIteration:
            return
        cache.pop(first_key, None)


def _cached_backing_wav(
    signature: tuple,
    *,
    backing_events,
    bpm,
    loops,
    style,
    level,
    song_title,
    song_artist,
    time_signature,
) -> tuple[bytes, bool]:
    cached = _BACKING_WAV_CACHE.get(signature)
    if cached is not None:
        return cached, True
    wav = generate_backing_track(
        backing_events,
        bpm=bpm,
        loops=loops,
        style=style,
        level=level,
        song_title=song_title,
        song_artist=song_artist,
        time_signature=time_signature,
    )
    _BACKING_WAV_CACHE[signature] = wav
    _evict_oldest(_BACKING_WAV_CACHE)
    return wav, False


def _cached_backing_timeline(
    signature: tuple,
    *,
    backing_events,
    bpm,
    loops,
    time_signature,
) -> tuple[list[dict], bool]:
    cached = _BACKING_TIMELINE_CACHE.get(signature)
    if cached is not None:
        return list(cached), True
    timeline = build_chord_event_timeline(
        backing_events,
        bpm,
        loops,
        time_signature=time_signature,
    )
    _BACKING_TIMELINE_CACHE[signature] = timeline
    _evict_oldest(_BACKING_TIMELINE_CACHE)
    return list(timeline), False


def playback_follow_position(timeline, playback_start_time=None, manual_index=0):
    if not timeline:
        return None
    total_duration = timeline[-1]["end_time"]
    if playback_start_time:
        elapsed = max(0, time.time() - playback_start_time)
        if elapsed >= total_duration:
            idx = len(timeline) - 1
            ended = True
        else:
            idx = next(
                (
                    i for i, event in enumerate(timeline)
                    if event["start_time"] <= elapsed < event["end_time"]
                ),
                0,
            )
            ended = False
    else:
        idx = int(manual_index) % len(timeline)
        elapsed = timeline[idx]["start_time"]
        ended = False
    event = dict(timeline[idx])
    next_event = timeline[(idx + 1) % len(timeline)]
    event["next_chord"] = next_event.get("chord", "")
    event["elapsed"] = elapsed
    event["ended"] = ended
    return event


def render_follow_along_controls(timeline, key_prefix):
    st.markdown(
        '<div class="ui-card soft"><div class="ui-card-title">🎯 Live chord follow-along</div>'
        '<div class="ui-card-sub">Manual controls when not using the synced audio player below.</div></div>',
        unsafe_allow_html=True,
    )
    start_key = f"{key_prefix}::follow_start_time"
    index_key = f"{key_prefix}::follow_manual_index"
    st.session_state.setdefault(index_key, 0)

    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        if st.button("▶ Start", key=f"{key_prefix}::follow_start", use_container_width=True):
            st.session_state[start_key] = time.time()
            st.session_state[index_key] = 0
    with col_b:
        if st.button("↻ Refresh", key=f"{key_prefix}::follow_refresh", use_container_width=True):
            st.rerun()
    with col_c:
        if st.button("⏭ Next bar", key=f"{key_prefix}::follow_next", use_container_width=True):
            st.session_state.pop(start_key, None)
            st.session_state[index_key] += 1
    with col_d:
        if st.button("■ Stop", key=f"{key_prefix}::follow_stop", use_container_width=True):
            st.session_state.pop(start_key, None)
            st.session_state[index_key] = 0

    pos = playback_follow_position(
        timeline,
        playback_start_time=st.session_state.get(start_key),
        manual_index=st.session_state.get(index_key, 0),
    )
    if not pos:
        st.info("Choose at least one section to use follow-along.")
        return None

    st.markdown(follow_along_status_html(pos), unsafe_allow_html=True)
    if pos.get("ended"):
        st.warning("Timeline ended — press **Start** or regenerate the backing track.")
    st.caption(
        f"Bar {pos['absolute_bar']} of {pos['total_bars']} · "
        f"{pos['start_time']:.1f}s–{pos['end_time']:.1f}s · highlighted on the chart."
    )
    return pos


def _build_karaoke_lyrics_panel_html(
    *,
    song_title: str,
    has_panel: bool,
    lyric_color: str = "white",
) -> str:
    """Static DOM scaffold for the karaoke section-aware lyric panel.

    The DOM order is intentional:

    1. Kicker (``Now Singing``)
    2. Title (active song)
    3. Section label (``Verse 1`` / ``Verse`` in beginner mode / ...)
    4. **Lyrics** - the main visual focus, large + centered.
    5. **Chord strip** - secondary support under the lyrics, with a
       chip per bar that highlights live as the backing plays.
    6. ``Next: ...`` cue.

    JS in :func:`_build_karaoke_lyrics_panel_script` keeps every field
    in sync with the chord-event timeline. Returns an empty string
    when the panel is disabled (non-voice mode), keeping the existing
    instrumentalist layout untouched.

    ``lyric_color`` (one of ``white`` / ``gold`` / ``cyan`` / ``cream``)
    is written onto the panel root as ``data-lyric-color="..."`` so
    the CSS theme variables pick up the user's preference for the
    active-line text color and accent glow.
    """
    if not has_panel:
        return ""
    safe_title = _html.escape(str(song_title or "Now Singing"))
    safe_color = _html.escape(str(lyric_color or "white").lower(), quote=True)
    return (
        f'<div class="karaoke-lyric-panel" id="karaoke-lyric-panel" '
        f'data-state="ready" data-lyric-color="{safe_color}">'
        '<p class="karaoke-lp-kicker">Now Singing</p>'
        f'<p class="karaoke-lp-title" id="karaoke-lp-title">{safe_title}</p>'
        '<p class="karaoke-lp-section" id="karaoke-lp-section">Section</p>'
        # Lyrics first, large and centered. The chord strip lives
        # underneath so the singer's eye lands on the lyrics first.
        '<div class="karaoke-lp-lyrics" id="karaoke-lp-lyrics">'
        '<div class="karaoke-lp-lyric-empty">Press play to follow the lyrics.</div>'
        "</div>"
        '<div class="karaoke-lp-chord-strip" id="karaoke-lp-chord-strip"></div>'
        '<p class="karaoke-lp-next" id="karaoke-lp-next"></p>'
        "</div>"
    )


def _build_karaoke_lyrics_panel_script(
    section_lyrics_map: dict | None,
    *,
    display_label_map: dict | None = None,
) -> str:
    """JS that wires the karaoke lyric panel to the chord-event timeline.

    Returns a snippet to inline inside the follow-along ``<script>``
    block (after the timeline + DOM-element constants). When
    ``section_lyrics_map`` is None / empty the snippet is empty - no
    panel + no listeners are registered for instrumentalists.

    The map is shaped::

        {
            "Verse 1": {"lyrics": ["line 1", "line 2"], "chords": ["C", "G", "Am", "F"]},
            "Chorus":  {"lyrics": [...],                "chords": [...]},
            ...
        }

    The chord array is the **per-bar** chord progression for that
    section (one token per bar, possibly subdivided with ``|`` like
    ``"Fmaj7|Am7|C/D"``).

    ``display_label_map`` (optional) maps raw section keys to display
    labels (e.g. ``{"Verse 1": "Verse"}``) for Beginner mode.

    Lookup is whitespace + case-insensitive so timeline section names
    (e.g. ``"Verse 1"``) still match map keys.

    On every chord-event tick the JS:

    * (section change) rebuilds the chord strip with one chip per
      bar, plus swaps the lyrics block.
    * (every event) highlights the chip matching ``event.bar_in_section``
      and the sub-chord matching ``event.subdivision_index`` so the
      singer can see which chord the band is on right now.
    """
    if not section_lyrics_map:
        return ""
    map_json = json.dumps(section_lyrics_map)
    label_json = json.dumps(display_label_map or {})
    return f"""
    (function() {{
      const LYRIC_MAP = {map_json};
      const DISPLAY_LABELS = {label_json};
      const lpSection = document.getElementById("karaoke-lp-section");
      const lpStrip = document.getElementById("karaoke-lp-chord-strip");
      const lpLyrics = document.getElementById("karaoke-lp-lyrics");
      const lpNext = document.getElementById("karaoke-lp-next");
      if (!lpSection || !lpStrip || !lpLyrics) return;

      // Build a case/space-insensitive lookup so timeline section
      // names (e.g. "Verse 1") still match map keys.
      const NORM_MAP = {{}};
      Object.keys(LYRIC_MAP).forEach((k) => {{
        NORM_MAP[String(k).trim().toLowerCase()] = LYRIC_MAP[k];
      }});
      const NORM_LABELS = {{}};
      Object.keys(DISPLAY_LABELS).forEach((k) => {{
        NORM_LABELS[String(k).trim().toLowerCase()] = DISPLAY_LABELS[k];
      }});

      function escapeHtml(s) {{
        return String(s == null ? "" : s)
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#39;");
      }}

      function dataFor(sectionName) {{
        if (!sectionName) return null;
        return NORM_MAP[String(sectionName).trim().toLowerCase()] || null;
      }}

      function displayLabelFor(sectionName) {{
        if (!sectionName) return "";
        const norm = String(sectionName).trim().toLowerCase();
        return NORM_LABELS[norm] || sectionName;
      }}

      function hasLyrics(sectionName) {{
        const data = dataFor(sectionName);
        return !!(data && Array.isArray(data.lyrics) && data.lyrics.length);
      }}

      function nextSectionAfter(eventIndex, lyricsOnly) {{
        if (!Array.isArray(window.__karaokeTimeline)) return "";
        const tl = window.__karaokeTimeline;
        const here = tl[eventIndex];
        if (!here) return "";
        const hereSection = here.section || "";
        for (let i = eventIndex + 1; i < tl.length; i++) {{
          const candidate = tl[i].section;
          if (!candidate || candidate === hereSection) continue;
          if (lyricsOnly && !hasLyrics(candidate)) continue;
          return candidate;
        }}
        return "";
      }}

      // Tokens like ``"N.C."``, ``"NC"``, ``"Tacet"``, ``"-"`` are
      // surfaced with a dashed-rest pill so the singer reads
      // breakdowns at a glance instead of as a chord they're meant
      // to play.
      const NO_CHORD_TOKENS = new Set([
        "N.C.", "NC", "N.C", "N/C", "(N.C.)", "TACET", "—", "-"
      ]);
      function isNoChordToken(s) {{
        if (s == null) return false;
        const cleaned = String(s).trim().replace(/\s+/g, "").toUpperCase();
        return NO_CHORD_TOKENS.has(cleaned);
      }}

      // ``"Bm.hit"`` / ``"Bm.HIT"`` -> one-shot stop-time hit pill.
      const HIT_SUFFIX_RE = /\.hit$/i;
      function isHitToken(s) {{
        if (s == null) return false;
        return HIT_SUFFIX_RE.test(String(s).trim());
      }}
      function hitUnderlying(s) {{
        return String(s == null ? "" : s).trim().replace(HIT_SUFFIX_RE, "").trim();
      }}

      // Mirror of chord_subdivisions.parse_subdivisions for one bar.
      // Recognises:
      //   "Fmaj7|Am7|C/D"        -> equal sub-chords
      //   "C:2|G:2"              -> weighted sub-chords
      //   "C:3.5|D:0.5p" / "D!"  -> push markers (anticipation)
      // Returns: [{{ chord, weight, push }}, ...]
      function parseBarSubdivisions(token, beatsPerBar) {{
        const raw = String(token == null ? "" : token).trim();
        if (!raw) return [];
        const beats = Math.max(1, Number(beatsPerBar) || 4);
        if (raw.indexOf("|") < 0) {{
          return [{{ chord: raw, weight: beats, push: false }}];
        }}
        const parts = raw.split("|").map((p) => p.trim()).filter(Boolean);
        if (!parts.length) return [];
        const subs = parts.map((part) => {{
          let chord = part;
          let weight = null;
          let push = false;
          // Push marker can be the trailing char of either the chord
          // section or after the ``:weight`` portion.
          if (chord.indexOf(":") >= 0) {{
            const colon = chord.lastIndexOf(":");
            const head = chord.slice(0, colon).trim();
            let tail = chord.slice(colon + 1).trim();
            if (/[pP!]$/.test(tail)) {{
              push = true;
              tail = tail.slice(0, -1).trim();
            }}
            const w = parseFloat(tail);
            if (!Number.isNaN(w)) {{
              weight = w;
            }}
            chord = head;
          }}
          if (/[pP!]$/.test(chord)) {{
            push = true;
            chord = chord.slice(0, -1).trim();
          }}
          return {{ chord: chord, weight: weight, push: push }};
        }});
        // Weight resolution: any sub without an explicit weight gets
        // an equal share of the remaining beats. If everything is
        // un-weighted we fall back to ``beats / parts.length``.
        const explicit = subs
          .map((s) => s.weight)
          .filter((w) => w !== null && w > 0);
        const totalExplicit = explicit.reduce((a, b) => a + b, 0);
        const unweighted = subs.length - explicit.length;
        let perFiller = 0;
        if (unweighted > 0) {{
          perFiller = Math.max(0.25, (beats - totalExplicit) / unweighted);
        }}
        return subs.map((s) => ({{
          chord: s.chord,
          weight: s.weight && s.weight > 0 ? s.weight : perFiller || beats / subs.length,
          push: !!s.push,
        }}));
      }}

      function buildChordStripForSection(sectionName, chords) {{
        if (!chords || !chords.length) {{
          lpStrip.innerHTML = "";
          return;
        }}
        const safeSection = escapeHtml(sectionName);
        const beatsPerBar = 4;
        const parts = [];
        chords.forEach((token, idx) => {{
          const bar = idx + 1;
          const raw = String(token == null ? "" : token).trim();
          // ---- N.C. / tacet bar ----
          if (isNoChordToken(raw)) {{
            parts.push(
              '<span class="karaoke-lp-chord karaoke-lp-chord--tacet" ' +
                'data-section="' + safeSection + '" ' +
                'data-bar-in-section="' + bar + '" ' +
                'data-sub-count="1" ' +
                'data-tacet="1">' +
                '<span class="kc-rest" aria-hidden="true">𝄽</span>' +
                '<span class="kc-tacet-label">N.C.</span>' +
              '</span>'
            );
            return;
          }}
          // ---- Hit / stop-time bar ----
          if (isHitToken(raw)) {{
            const display = escapeHtml(hitUnderlying(raw));
            parts.push(
              '<span class="karaoke-lp-chord karaoke-lp-chord--hit" ' +
                'data-section="' + safeSection + '" ' +
                'data-bar-in-section="' + bar + '" ' +
                'data-sub-count="1" ' +
                'data-hit="1">' +
                display +
                '<span class="kc-hit-spark" aria-hidden="true">✦</span>' +
              '</span>'
            );
            return;
          }}
          // ---- Subdivided / pushed bar ----
          const subs = parseBarSubdivisions(raw, beatsPerBar);
          let inner;
          let cellHasPush = false;
          if (subs.length > 1) {{
            const totalWeight = subs.reduce(
              (s, sub) => s + Math.max(0, sub.weight),
              0
            ) || 1;
            const subSpans = subs.map((sub, sIdx) => {{
              const grow = Math.max(0, sub.weight);
              const basis = (grow / totalWeight) * 100.0;
              const isPush = !!sub.push;
              if (isPush) cellHasPush = true;
              const isSubTacet = isNoChordToken(sub.chord);
              const subClass = isPush
                ? (isSubTacet ? 'sub-chord push tacet' : 'sub-chord push')
                : (isSubTacet ? 'sub-chord tacet' : 'sub-chord');
              const display = isSubTacet
                ? '<span class="kc-rest" aria-hidden="true">𝄽</span>'
                : escapeHtml(String(sub.chord || "").trim());
              return (
                '<span class="' + subClass + '" data-sub="' + sIdx + '"' +
                  (isPush ? ' data-push="1"' : '') +
                  ' style="flex-grow:' + grow.toFixed(3) +
                  ';flex-basis:' + basis.toFixed(3) + '%;">' +
                  display +
                '</span>'
              );
            }});
            inner =
              '<span class="sub-chord-list">' +
              subSpans.join('<span class="karaoke-lp-arrow" aria-hidden="true">&middot;</span>') +
              "</span>";
          }} else {{
            inner = escapeHtml(raw);
          }}
          const pushAttr = cellHasPush ? ' data-has-push="1"' : '';
          const pushClass = cellHasPush ? ' karaoke-lp-chord--push' : '';
          parts.push(
            '<span class="karaoke-lp-chord' + pushClass + '" ' +
              'data-section="' + safeSection + '" ' +
              'data-bar-in-section="' + bar + '" ' +
              'data-sub-count="' + subs.length + '"' +
              pushAttr + '>' +
              inner +
            "</span>"
          );
        }});
        lpStrip.innerHTML = parts.join("");
      }}

      function highlightActiveChord(event) {{
        // Clear previous highlight + re-apply to the cell matching
        // this event's section + bar_in_section + (optional) sub
        // index. We re-query the DOM each tick because the chord
        // strip is rebuilt on section change.
        const chips = lpStrip.querySelectorAll(".karaoke-lp-chord");
        const targetBar = Number(event.bar_in_section);
        const subIdx = Number(event.subdivision_index);
        chips.forEach((chip) => {{
          chip.classList.remove("active");
          const subs = chip.querySelectorAll(".sub-chord");
          subs.forEach((sub) => sub.classList.remove("active-sub"));
          if (
            chip.dataset.section === event.section &&
            Number(chip.dataset.barInSection) === targetBar
          ) {{
            chip.classList.add("active");
            if (!Number.isNaN(subIdx) && subs.length) {{
              const sub = chip.querySelector(
                '.sub-chord[data-sub="' + subIdx + '"]'
              );
              if (sub) sub.classList.add("active-sub");
            }}
          }}
        }});
      }}

      // Map this tick's bar-in-section position to a "current line"
      // index inside the section's lyric block. Sections rarely have
      // per-line timing data, so we evenly distribute the lines
      // across the section's bars: the singer sees one line lit per
      // chunk of the bar count. Re-applying classes is cheap (1-8
      // line elements) so we just rewrite them every tick.
      function highlightActiveLine(event) {{
        const lines = lpLyrics.querySelectorAll(".karaoke-lp-lyric-line");
        if (!lines.length) return;
        const totalBars = Math.max(1, Number(event.section_bars) || 1);
        const barInSection = Math.max(1, Number(event.bar_in_section) || 1);
        const fraction = Math.min(1, (barInSection - 1) / totalBars);
        const activeIdx = Math.min(
          lines.length - 1,
          Math.floor(fraction * lines.length)
        );
        let activeLine = null;
        lines.forEach((line, idx) => {{
          line.classList.remove("active", "before-active");
          if (idx === activeIdx) {{
            line.classList.add("active");
            activeLine = line;
          }} else if (idx < activeIdx) {{
            line.classList.add("before-active");
          }}
        }});
        if (activeLine && !audio.paused) {{
          activeLine.scrollIntoView({{ behavior: "smooth", block: "center", inline: "nearest" }});
        }}
      }}

      let lastSection = null;
      window.__karaokeUpdateLyricPanel = function(event) {{
        if (!event) return;
        const sectionName = event.section || "";

        // -- Section change: rebuild chord strip + swap lyrics. ----
        if (sectionName !== lastSection) {{
          lastSection = sectionName;
          const data = dataFor(sectionName);
          const chords = (data && data.chords) || [];
          const lines = (data && data.lyrics) || [];

          buildChordStripForSection(sectionName, chords);

          if (lines.length) {{
            // Lyric-bearing section - section label + lyrics.
            lpSection.textContent = displayLabelFor(sectionName);
            lpLyrics.classList.remove("empty");
            lpLyrics.classList.remove("instrumental");
            lpLyrics.innerHTML = lines
              .map((l) =>
                '<div class="karaoke-lp-lyric-line">' + escapeHtml(l) + "</div>"
              )
              .join("");
            const nxt = nextSectionAfter(event.event_index, false);
            lpNext.innerHTML = nxt
              ? ('Next: <strong>' + escapeHtml(displayLabelFor(nxt)) + '</strong>')
              : "";
          }} else {{
            // Instrumental section - show "get ready" + preview the
            // next *lyric-bearing* section so the singer can prep
            // their entry without searching the chart.
            lpSection.textContent = "Instrumental " + displayLabelFor(sectionName);
            lpLyrics.classList.add("empty");
            lpLyrics.classList.add("instrumental");
            const nextLyric = nextSectionAfter(event.event_index, true);
            if (nextLyric) {{
              lpLyrics.innerHTML =
                '<div class="karaoke-lp-lyric-empty">' +
                '<span class="karaoke-lp-instr-icon" aria-hidden="true">&#9835;</span> ' +
                "Instrumental section - get ready to sing " +
                '<strong>' + escapeHtml(displayLabelFor(nextLyric)) + '</strong>.' +
                "</div>";
              lpNext.innerHTML =
                'Next: <strong>' + escapeHtml(displayLabelFor(nextLyric)) + '</strong>';
            }} else {{
              lpLyrics.innerHTML =
                '<div class="karaoke-lp-lyric-empty">' +
                '<span class="karaoke-lp-instr-icon" aria-hidden="true">&#9835;</span> ' +
                "Instrumental section - no further lyric sections." +
                "</div>";
              lpNext.innerHTML = "";
            }}
          }}
        }}

        // -- Every tick: highlight the active chord under the
        //    lyrics, and pick the lyric line corresponding to the
        //    section's bar progress so the singer follows the line
        //    that's "due" right now (no per-line timing required).
        highlightActiveChord(event);
        highlightActiveLine(event);
        // ---- Arrangement-mood theming ----
        // Each timeline event carries a coarse ``mood`` bucket
        // (verse / lift / chorus / climax / tacet / soft) plus a
        // raw arrangement_intensity float. Sync them onto the
        // panel as data attributes + a CSS variable so the
        // stylesheet can dim during tacet bridges, saturate
        // during the final chorus, and pulse the background in
        // proportion to the band's energy. We update only when
        // values change to avoid forcing a layout recompute on
        // every tick.
        try {{
          const lpPanel = document.getElementById("karaoke-lyric-panel");
          if (lpPanel) {{
            const mood = event.mood || "verse";
            const intensity = Number(event.arrangement_intensity) || 1.0;
            if (lpPanel.dataset.mood !== mood) {{
              lpPanel.dataset.mood = mood;
            }}
            if (event.is_final_chorus) {{
              if (lpPanel.dataset.finalChorus !== "1") {{
                lpPanel.dataset.finalChorus = "1";
              }}
            }} else if (lpPanel.dataset.finalChorus === "1") {{
              lpPanel.dataset.finalChorus = "0";
            }}
            // Clamp + quantise the intensity to a few decimals so
            // CSS-var thrash is minimal. The custom property is
            // consumed by the panel's background gradient + glow.
            const clamped = Math.max(0.4, Math.min(1.45, intensity));
            const quantised = Math.round(clamped * 50) / 50;  // 0.02 step
            const current = parseFloat(
              lpPanel.style.getPropertyValue("--karaoke-arrangement-intensity") || "0"
            );
            if (Math.abs(current - quantised) > 0.005) {{
              lpPanel.style.setProperty(
                "--karaoke-arrangement-intensity", quantised.toFixed(3)
              );
            }}
          }}
        }} catch (_e) {{
          /* mood theming is decorative — never break the panel */
        }}
      }};
    }})();
    """


def live_follow_along_component_html(
    wav_bytes,
    timeline,
    chart_html,
    *,
    autoplay: bool = True,
    audio_b64: str | None = None,
    karaoke_auto_advance: bool = False,
    karaoke_continue_button_text: str = "Continue to next song",
    karaoke_countdown: bool = False,
    karaoke_countdown_seconds: int = 5,
    karaoke_lyrics_panel: dict | None = None,
    karaoke_song_title: str = "",
    karaoke_hide_chart: bool = False,
    karaoke_display_labels: dict | None = None,
    karaoke_lyric_color: str = "white",
):
    audio_b64 = audio_b64 or base64.b64encode(wav_bytes).decode("ascii")
    timeline_json = json.dumps(timeline)
    # When a karaoke countdown is queued we suppress native autoplay - the
    # countdown JS itself calls audio.play() when the 5-4-3-2-1 finishes
    # (or when the user clicks "Skip countdown").
    effective_autoplay = bool(autoplay) and not bool(karaoke_countdown)
    autoplay_attr = "autoplay" if effective_autoplay else ""
    karaoke_bridge_script = build_karaoke_audio_bridge_script(
        auto_advance=bool(karaoke_auto_advance),
        continue_button_text=karaoke_continue_button_text,
    )
    karaoke_countdown_script = build_karaoke_countdown_script(
        enabled=bool(karaoke_countdown),
        seconds=int(karaoke_countdown_seconds),
    )
    karaoke_lyric_panel_enabled = bool(karaoke_lyrics_panel)
    karaoke_lyric_panel_html = _build_karaoke_lyrics_panel_html(
        song_title=karaoke_song_title,
        has_panel=karaoke_lyric_panel_enabled,
        lyric_color=str(karaoke_lyric_color or "white"),
    )
    karaoke_lyric_panel_script = _build_karaoke_lyrics_panel_script(
        karaoke_lyrics_panel,
        display_label_map=karaoke_display_labels,
    )
    # Karaoke voice mode: the lyric panel is the main surface, so wrap
    # the chord chart in a collapsed ``<details>`` so it sits as a
    # quiet "Show chord chart" affordance. The chart DOM is still
    # mounted (just visually hidden) so the existing chord-highlight
    # JS keeps working - opening the details reveals the live-
    # following chart highlights.
    if karaoke_hide_chart:
        chart_root_html = (
            '<details class="live-chart-hidden-wrap">'
            "<summary><span class=\"live-chart-hidden-icon\">\U0001F3BC</span> "
            "Show chord chart (optional)</summary>"
            f'<div id="live-chart-root">{chart_html}</div>'
            "</details>"
        )
    else:
        chart_root_html = f'<div id="live-chart-root">{chart_html}</div>'
    return f"""
<div class="live-follow-shell">
  <style>
    .live-follow-shell {{
      font-family: system-ui, -apple-system, Segoe UI, sans-serif;
      color: #0f172a;
    }}
    .live-player {{
      position: sticky;
      top: 0;
      z-index: 20;
      border: 1px solid rgba(15, 23, 42, 0.14);
      border-radius: 16px;
      padding: 14px;
      margin-bottom: 14px;
      background: linear-gradient(180deg, #f8fff9, #ffffff);
      box-shadow: 0 4px 18px rgba(15, 23, 42, 0.10);
    }}
    .live-player audio {{
      width: 100%;
      margin: 8px 0 10px 0;
    }}
    .live-status-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(120px, 1fr));
      gap: 8px;
      margin-top: 10px;
    }}
    .live-status-card {{
      border: 1px solid rgba(15, 23, 42, 0.12);
      border-radius: 12px;
      padding: 9px 10px;
      background: #ffffff;
    }}
    .live-label {{
      color: #64748b;
      font-size: 0.72rem;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .live-value {{
      margin-top: 4px;
      font-size: 1.02rem;
      font-weight: 850;
    }}
    .live-help {{
      color: #475569;
      font-size: 0.86rem;
      margin-top: 6px;
    }}
    .live-follow-shell .chord-cell.current-chord {{
      background: #86efac !important;
      border-color: #15803d !important;
      box-shadow: 0 0 0 4px rgba(22, 163, 74, 0.28), 0 0 22px rgba(22, 163, 74, 0.28) !important;
      transform: translateY(-1px);
      animation: livePulse 1.1s ease-in-out infinite alternate;
    }}
    .live-follow-shell .section-card.current {{
      outline: 3px solid rgba(34, 197, 94, 0.34) !important;
      box-shadow: 0 0 0 6px rgba(34, 197, 94, 0.10) !important;
    }}
    @keyframes livePulse {{
      from {{ box-shadow: 0 0 0 4px rgba(22, 163, 74, 0.22), 0 0 12px rgba(22, 163, 74, 0.20); }}
      to {{ box-shadow: 0 0 0 5px rgba(22, 163, 74, 0.36), 0 0 26px rgba(22, 163, 74, 0.34); }}
    }}
    @media (max-width: 760px) {{
      .live-status-grid {{ grid-template-columns: repeat(2, minmax(120px, 1fr)); }}
    }}

    .karaoke-countdown-overlay {{
      position: fixed;
      inset: 0;
      z-index: 99999;
      background: radial-gradient(ellipse at center,
        rgba(15, 23, 42, 0.96) 0%,
        rgba(8, 11, 24, 0.985) 70%);
      color: #f8fafc;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 18px;
      font-family: system-ui, -apple-system, Segoe UI, sans-serif;
      animation: karaokeOverlayIn 220ms ease-out;
    }}
    @keyframes karaokeOverlayIn {{
      from {{ opacity: 0; }}
      to   {{ opacity: 1; }}
    }}
    .karaoke-countdown-kicker {{
      font-size: 0.92rem;
      letter-spacing: 0.22em;
      text-transform: uppercase;
      color: rgba(248, 250, 252, 0.65);
      font-weight: 700;
    }}
    .karaoke-countdown-number {{
      font-size: clamp(120px, 28vw, 240px);
      font-weight: 900;
      line-height: 1;
      letter-spacing: -0.04em;
      color: #f8fafc;
      text-shadow: 0 8px 40px rgba(56, 189, 248, 0.30);
    }}
    .karaoke-countdown-number.pulse {{
      animation: karaokeCountPulse 920ms ease-out;
    }}
    @keyframes karaokeCountPulse {{
      0%   {{ transform: scale(0.65); opacity: 0; }}
      40%  {{ transform: scale(1.12); opacity: 1; }}
      100% {{ transform: scale(1.0);  opacity: 1; }}
    }}
    .karaoke-countdown-skip {{
      margin-top: 18px;
      background: rgba(248, 250, 252, 0.12);
      border: 1px solid rgba(248, 250, 252, 0.32);
      color: #f8fafc;
      padding: 10px 22px;
      border-radius: 999px;
      font-size: 0.95rem;
      font-weight: 700;
      cursor: pointer;
      transition: background 0.18s ease, transform 0.18s ease;
    }}
    .karaoke-countdown-skip:hover {{
      background: rgba(248, 250, 252, 0.22);
      transform: translateY(-1px);
    }}

    /* Karaoke voice mode: chord chart sits inside a collapsed
       <details> so the lyric panel above is the dominant view.
       Singers can still pop it open for a quick chord glance. */
    .live-chart-hidden-wrap {{
      margin-top: 8px;
      border: 1px dashed rgba(190, 24, 93, 0.20);
      border-radius: 12px;
      background: rgba(255, 247, 251, 0.40);
    }}
    .live-chart-hidden-wrap > summary {{
      cursor: pointer;
      list-style: none;
      padding: 10px 14px;
      font-size: 0.84rem;
      font-weight: 800;
      letter-spacing: 0.10em;
      text-transform: uppercase;
      color: #831843;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .live-chart-hidden-wrap > summary::-webkit-details-marker {{ display: none; }}
    .live-chart-hidden-wrap > summary::after {{
      content: "+";
      margin-left: auto;
      font-size: 1.1rem;
      font-weight: 800;
      color: #be185d;
    }}
    .live-chart-hidden-wrap[open] > summary::after {{ content: "\u2212"; }}
    .live-chart-hidden-icon {{ font-size: 0.95rem; }}
    .live-chart-hidden-wrap > #live-chart-root {{
      padding: 6px 14px 14px 14px;
    }}

    /* ================================================================
       Karaoke "black screen" lyric panel — the main stage for voice
       practice. Renders a real karaoke-player look:
         * deep black gradient backdrop with a soft magenta vignette
         * large centered lyrics with active-line highlight
         * compact chord strip under the lyrics
         * polished kicker / title / section labels at the top
         * smooth transitions on section + active-line changes
       The user-picked lyric color (white / gold / cyan / cream) is
       applied via a CSS variable on the panel root, so the active-line
       glow and chord-strip accent both follow the preference.
       ================================================================ */
    .karaoke-lyric-panel {{
      /* Default lyric color; overridden by data-lyric-color="..." below. */
      --karaoke-lyric: #f8fafc;
      --karaoke-lyric-glow: rgba(248, 250, 252, 0.55);
      --karaoke-accent: #f472b6;
      --karaoke-accent-soft: rgba(244, 114, 182, 0.55);

      position: relative;
      margin: 14px 0 18px 0;
      padding: 26px clamp(18px, 4vw, 44px) 22px clamp(18px, 4vw, 44px);
      border-radius: 22px;
      border: 1px solid rgba(244, 114, 182, 0.22);
      background:
        radial-gradient(120% 90% at 18% -10%, rgba(236, 72, 153, 0.18) 0%, rgba(236, 72, 153, 0) 55%),
        radial-gradient(110% 90% at 90% 110%, rgba(168, 85, 247, 0.20) 0%, rgba(168, 85, 247, 0) 55%),
        radial-gradient(140% 70% at 50% 50%, rgba(15, 23, 42, 0.0) 0%, rgba(0, 0, 0, 0.45) 100%),
        linear-gradient(180deg, #07050d 0%, #0c0816 55%, #050309 100%);
      color: var(--karaoke-lyric);
      box-shadow:
        0 30px 72px -28px rgba(0, 0, 0, 0.95),
        0 6px 22px rgba(0, 0, 0, 0.55),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);
      overflow: hidden;
      isolation: isolate;
      text-align: center;
    }}
    /* Neon top sheen — same magenta-on-violet wash used on the
       Performance Setlist card so the two surfaces feel like one
       coherent stage. */
    .karaoke-lyric-panel::before {{
      content: "";
      position: absolute;
      inset: 0 0 auto 0;
      height: 2px;
      background: linear-gradient(90deg,
        transparent 0%,
        rgba(244, 114, 182, 0.55) 30%,
        rgba(216, 180, 254, 0.55) 50%,
        rgba(244, 114, 182, 0.55) 70%,
        transparent 100%);
      filter: blur(0.5px);
      z-index: 1;
    }}
    /* User-selectable lyric color tokens. The same value tints the
       active line text and the active chord chip's accent. */
    .karaoke-lyric-panel[data-lyric-color="white"] {{
      --karaoke-lyric: #f8fafc;
      --karaoke-lyric-glow: rgba(248, 250, 252, 0.45);
    }}
    .karaoke-lyric-panel[data-lyric-color="gold"] {{
      --karaoke-lyric: #fde68a;
      --karaoke-lyric-glow: rgba(253, 230, 138, 0.55);
    }}
    .karaoke-lyric-panel[data-lyric-color="cyan"] {{
      --karaoke-lyric: #67e8f9;
      --karaoke-lyric-glow: rgba(103, 232, 249, 0.55);
    }}
    .karaoke-lyric-panel[data-lyric-color="cream"] {{
      --karaoke-lyric: #fef3c7;
      --karaoke-lyric-glow: rgba(254, 243, 199, 0.50);
    }}

    /* ---- Arrangement-mood theming ----
       Each timeline tick the JS sets ``data-mood`` and the CSS
       custom property ``--karaoke-arrangement-intensity`` on the
       panel. The base design is intentionally minimal: a couple of
       subtle gradient overlays + a glow ring whose opacity scales
       with the band's energy. The result is the screen visibly
       brightens on the chorus, dims on a tacet bridge, and pulses
       to climax in the final chorus — without changing layout. */
    .karaoke-lyric-panel {{
      transition: background-color 600ms ease, box-shadow 400ms ease,
                  border-color 400ms ease;
    }}
    .karaoke-lyric-panel::after {{
      /* Mood overlay: a soft radial wash whose hue/intensity is
         driven by the data-mood attribute. Decoupled from the
         neon top sheen (::before) so both can co-exist. */
      content: "";
      position: absolute;
      inset: 0;
      pointer-events: none;
      background: radial-gradient(
        130% 110% at 50% 35%,
        var(--karaoke-mood-wash, rgba(244, 114, 182, 0.00)) 0%,
        rgba(0, 0, 0, 0) 65%);
      opacity: calc(var(--karaoke-arrangement-intensity, 1.0) * 0.85);
      transition: background 700ms ease, opacity 600ms ease;
      z-index: 0;
      mix-blend-mode: screen;
    }}
    .karaoke-lyric-panel[data-mood="soft"] {{
      --karaoke-mood-wash: rgba(99, 102, 241, 0.10);
      border-color: rgba(99, 102, 241, 0.18);
    }}
    .karaoke-lyric-panel[data-mood="verse"] {{
      --karaoke-mood-wash: rgba(129, 140, 248, 0.10);
      border-color: rgba(129, 140, 248, 0.18);
    }}
    .karaoke-lyric-panel[data-mood="lift"] {{
      /* Pre-chorus rise: introduce magenta hint so the eye senses
         the build before the drop. */
      --karaoke-mood-wash: rgba(217, 70, 239, 0.16);
      border-color: rgba(217, 70, 239, 0.32);
    }}
    .karaoke-lyric-panel[data-mood="chorus"] {{
      --karaoke-mood-wash: rgba(244, 114, 182, 0.22);
      border-color: rgba(244, 114, 182, 0.40);
      box-shadow:
        0 30px 72px -28px rgba(244, 114, 182, 0.50),
        0 8px 24px rgba(244, 114, 182, 0.18),
        inset 0 1px 0 rgba(255, 255, 255, 0.06);
    }}
    .karaoke-lyric-panel[data-mood="climax"] {{
      /* Final chorus / climax: brighter wash + saturated border +
         dramatic glow. The pulse animation sits on top of the
         intensity-driven opacity so it reads even at low intensity. */
      --karaoke-mood-wash: rgba(251, 191, 36, 0.22);
      border-color: rgba(251, 191, 36, 0.55);
      box-shadow:
        0 0 0 1px rgba(251, 191, 36, 0.35),
        0 30px 80px -24px rgba(251, 113, 133, 0.55),
        0 12px 32px rgba(251, 191, 36, 0.20),
        inset 0 1px 0 rgba(255, 255, 255, 0.08);
      animation: karaoke-climax-pulse 2.2s ease-in-out infinite;
    }}
    .karaoke-lyric-panel[data-mood="tacet"] {{
      /* Bridge breakdown / tacet bars: dim the room. The dashed
         lyric-line accent and the chord strip's tacet pills already
         signal "drums only" — this overlay quiets the whole stage. */
      --karaoke-mood-wash: rgba(15, 23, 42, 0.20);
      border-color: rgba(148, 163, 184, 0.20);
      filter: brightness(0.86) saturate(0.85);
    }}
    .karaoke-lyric-panel[data-final-chorus="1"][data-mood="chorus"],
    .karaoke-lyric-panel[data-final-chorus="1"][data-mood="climax"] {{
      /* Final chorus reads as the brightest moment of the song
         even before intensity peaks (some songs end on a sustained
         climax rather than a louder one). */
      border-color: rgba(251, 191, 36, 0.65);
      box-shadow:
        0 0 0 1px rgba(251, 191, 36, 0.40),
        0 30px 80px -24px rgba(251, 113, 133, 0.65),
        0 12px 32px rgba(251, 191, 36, 0.25),
        inset 0 1px 0 rgba(255, 255, 255, 0.08);
    }}
    @keyframes karaoke-climax-pulse {{
      0%   {{ box-shadow:
              0 0 0 1px rgba(251, 191, 36, 0.35),
              0 30px 80px -24px rgba(251, 113, 133, 0.45),
              0 12px 32px rgba(251, 191, 36, 0.18),
              inset 0 1px 0 rgba(255, 255, 255, 0.08); }}
      50%  {{ box-shadow:
              0 0 0 1px rgba(251, 191, 36, 0.55),
              0 36px 96px -22px rgba(251, 113, 133, 0.65),
              0 16px 40px rgba(251, 191, 36, 0.30),
              inset 0 1px 0 rgba(255, 255, 255, 0.10); }}
      100% {{ box-shadow:
              0 0 0 1px rgba(251, 191, 36, 0.35),
              0 30px 80px -24px rgba(251, 113, 133, 0.45),
              0 12px 32px rgba(251, 191, 36, 0.18),
              inset 0 1px 0 rgba(255, 255, 255, 0.08); }}
    }}
    /* Lyrics + chords sit above the mood overlay.  */
    .karaoke-lyric-panel > * {{ position: relative; z-index: 1; }}

    .karaoke-lp-kicker {{
      display: inline-block;
      margin: 0 auto 6px auto;
      font-size: 0.66rem;
      font-weight: 900;
      letter-spacing: 0.32em;
      text-transform: uppercase;
      color: #f9a8d4;
      text-shadow: 0 0 14px rgba(244, 114, 182, 0.55);
      padding: 3px 14px;
      border-radius: 999px;
      background: rgba(236, 72, 153, 0.10);
      border: 1px solid rgba(244, 114, 182, 0.30);
    }}
    .karaoke-lp-title {{
      margin: 4px 0 10px 0;
      font-size: clamp(1.35rem, 2.6vw, 1.85rem);
      font-weight: 800;
      letter-spacing: -0.005em;
      color: #ffffff;
      text-shadow: 0 1px 18px rgba(0, 0, 0, 0.85);
    }}
    .karaoke-lp-section {{
      margin: 0 auto 16px auto;
      display: inline-block;
      font-size: 0.78rem;
      font-weight: 800;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: #fbcfe8;
      padding: 4px 12px;
      border-radius: 999px;
      background: rgba(168, 85, 247, 0.18);
      border: 1px solid rgba(216, 180, 254, 0.30);
    }}

    /* Lyric stack — the visual focal point. Each line is a separate
       element so we can highlight the "current" line as the bar
       progresses through the section. Inactive lines stay dim and
       slightly smaller so the eye glides naturally to the active one. */
    .karaoke-lp-lyrics {{
      margin: 6px auto 14px auto;
      max-width: 52rem;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 0.45rem;
    }}
    .karaoke-lp-lyric-line {{
      font-size: clamp(1.45rem, 3.4vw, 2.45rem);
      font-weight: 750;
      line-height: 1.22;
      letter-spacing: -0.005em;
      color: rgba(248, 250, 252, 0.42);
      transition:
        color 220ms ease,
        text-shadow 240ms ease,
        transform 240ms ease,
        opacity 220ms ease;
      text-shadow: 0 1px 8px rgba(0, 0, 0, 0.65);
      will-change: transform, color;
    }}
    .karaoke-lp-lyric-line.active {{
      color: var(--karaoke-lyric);
      text-shadow:
        0 0 18px var(--karaoke-lyric-glow),
        0 2px 10px rgba(0, 0, 0, 0.85);
      transform: scale(1.04);
    }}
    .karaoke-lp-lyric-line.before-active {{
      color: rgba(248, 250, 252, 0.28);
      opacity: 0.78;
    }}
    .karaoke-lp-lyric-empty {{
      font-size: clamp(1.05rem, 2vw, 1.25rem);
      font-weight: 600;
      color: rgba(245, 208, 254, 0.62);
      font-style: italic;
      padding: 18px 8px;
    }}

    /* Chord strip under the lyrics. Each chip is one bar; the active
       chip glows magenta in time with the backing track. */
    .karaoke-lp-chord-strip {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px 8px;
      justify-content: center;
      margin: 6px auto 4px auto;
      max-width: 56rem;
      padding: 8px 4px 0 4px;
      border-top: 1px solid rgba(216, 180, 254, 0.12);
    }}
    .karaoke-lp-chord {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 44px;
      padding: 5px 10px;
      border-radius: 8px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.92rem;
      font-weight: 800;
      letter-spacing: 0.01em;
      color: #fbcfe8;
      background: rgba(46, 20, 75, 0.55);
      border: 1px solid rgba(216, 180, 254, 0.18);
      transition:
        background 160ms ease,
        color 160ms ease,
        border-color 160ms ease,
        box-shadow 200ms ease,
        transform 160ms ease;
    }}
    .karaoke-lp-chord.active {{
      background: linear-gradient(180deg, #ec4899 0%, #be185d 100%);
      color: #ffffff;
      border-color: rgba(251, 207, 232, 0.65);
      box-shadow:
        0 0 0 1px rgba(251, 207, 232, 0.40),
        0 8px 22px -6px rgba(236, 72, 153, 0.65);
      transform: translateY(-1px);
    }}
    .karaoke-lp-chord .sub-chord-list {{
      display: inline-flex;
      align-items: center;
      gap: 2px;
    }}
    .karaoke-lp-chord .sub-chord {{
      padding: 0 3px;
      border-radius: 4px;
      transition: background 160ms ease, color 160ms ease;
    }}
    .karaoke-lp-chord.active .sub-chord.active-sub {{
      background: rgba(255, 255, 255, 0.22);
      color: #ffffff;
    }}
    .karaoke-lp-arrow {{
      color: rgba(216, 180, 254, 0.55);
      font-weight: 700;
      font-size: 0.78rem;
      margin: 0 2px;
    }}
    /* Pushed sub-chord (anticipation) — orange accent + arrow so the
       singer can see "this lands a half-beat early" at a glance. */
    .karaoke-lp-chord .sub-chord.push {{
      background: rgba(234, 88, 12, 0.18);
      color: #fed7aa;
      box-shadow: inset 0 0 0 1px rgba(251, 146, 60, 0.55);
    }}
    .karaoke-lp-chord.active .sub-chord.push.active-sub {{
      background: linear-gradient(180deg, #f97316 0%, #c2410c 100%);
      color: #ffffff;
      box-shadow: inset 0 0 0 1px rgba(255, 237, 213, 0.85);
    }}
    .karaoke-lp-chord--push {{
      border-color: rgba(251, 146, 60, 0.55);
    }}
    /* N.C. / tacet bar in the chord strip — dashed silver pill with
       a struck-through eighth-rest glyph. The singer reads this as
       "drums only, lay out". */
    .karaoke-lp-chord--tacet {{
      gap: 4px;
      color: rgba(216, 180, 254, 0.78);
      background: repeating-linear-gradient(
          135deg,
          rgba(148, 163, 184, 0.10) 0 6px,
          rgba(148, 163, 184, 0.00) 6px 12px),
        rgba(46, 20, 75, 0.42);
      border-style: dashed;
      border-color: rgba(216, 180, 254, 0.32);
      letter-spacing: 0.04em;
    }}
    .karaoke-lp-chord--tacet .kc-rest {{
      font-size: 1.0rem;
      color: rgba(216, 180, 254, 0.88);
      filter: drop-shadow(0 0 4px rgba(216, 180, 254, 0.35));
    }}
    .karaoke-lp-chord--tacet .kc-tacet-label {{
      font-size: 0.78rem;
      font-weight: 800;
    }}
    .karaoke-lp-chord--tacet.active {{
      background: linear-gradient(180deg, #fde68a 0%, #b45309 100%);
      color: #1c1917;
      border-color: #fde68a;
      box-shadow: 0 8px 22px -6px rgba(180, 83, 9, 0.55);
    }}
    .karaoke-lp-chord--tacet.active .kc-rest,
    .karaoke-lp-chord--tacet.active .kc-tacet-label {{
      color: #1c1917;
    }}
    /* Hit / stop-time bar in the chord strip — orange starburst pill
       so the band-stab reads even on a quick glance. */
    .karaoke-lp-chord--hit {{
      gap: 4px;
      color: #fed7aa;
      background: linear-gradient(180deg, rgba(234, 88, 12, 0.40) 0%, rgba(154, 52, 18, 0.55) 100%);
      border-color: rgba(251, 146, 60, 0.65);
    }}
    .karaoke-lp-chord--hit .kc-hit-spark {{
      color: #fb923c;
      font-weight: 900;
      filter: drop-shadow(0 0 3px rgba(251, 146, 60, 0.55));
    }}
    .karaoke-lp-chord--hit.active {{
      background: linear-gradient(180deg, #f97316 0%, #c2410c 100%);
      color: #ffffff;
      border-color: #fed7aa;
      box-shadow:
        0 0 0 1px rgba(255, 237, 213, 0.55),
        0 8px 22px -6px rgba(234, 88, 12, 0.65);
      transform: translateY(-1px) scale(1.02);
    }}
    .karaoke-lp-chord--hit.active .kc-hit-spark {{
      color: #fff7ed;
    }}
    /* A bar that contains a tacet *sub-chord* gets a tiny dashed
       outline on just that sub-cell (lets a "C / N.C." or
       "G / N.C." half-bar still read). */
    .karaoke-lp-chord .sub-chord.tacet {{
      border: 1px dashed rgba(216, 180, 254, 0.45);
      color: rgba(216, 180, 254, 0.72);
    }}

    .karaoke-lp-next {{
      margin: 12px 0 0 0;
      font-size: 0.85rem;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #f5d0fe;
      opacity: 0.85;
    }}
    .karaoke-lp-next strong {{
      color: #ffffff;
      letter-spacing: 0.04em;
      margin-left: 4px;
      text-shadow: 0 0 10px rgba(244, 114, 182, 0.45);
    }}

    /* Karaoke instrumental-section state (Intro / Solo / Interlude).
       Reuses the dark stage palette so the breakdown reads as part of
       the same screen, not a stark light-mode card. */
    .karaoke-lp-lyrics.instrumental {{
      padding: 14px 18px;
      border-radius: 14px;
      background:
        radial-gradient(120% 90% at 50% 50%, rgba(168, 85, 247, 0.10), rgba(0, 0, 0, 0));
      border: 1px dashed rgba(216, 180, 254, 0.30);
    }}
    .karaoke-lp-instr-icon {{
      font-size: 1.05rem;
      margin-right: 6px;
      color: #f9a8d4;
      text-shadow: 0 0 8px rgba(244, 114, 182, 0.55);
    }}
    .karaoke-lp-lyrics.instrumental .karaoke-lp-lyric-empty {{
      color: rgba(248, 250, 252, 0.78);
      font-style: normal;
    }}
    .karaoke-lp-lyrics.instrumental .karaoke-lp-lyric-empty strong {{
      color: #ffffff;
      text-shadow: 0 0 12px var(--karaoke-lyric-glow);
    }}
  </style>

  <div class="live-player">
    <strong>Live Follow-Along Player</strong>
    <audio id="live-audio" controls {autoplay_attr} preload="auto" src="data:audio/wav;base64,{audio_b64}"></audio>
    <div class="live-player-toolbar">
      <button type="button" class="live-stop-btn" id="live-stop-btn">■ Stop playback</button>
      <span class="live-help" id="live-stop-hint">Stops audio immediately — use **Stop backing track** above to reset follow-along.</span>
    </div>
    <div class="live-status-grid">
      <div class="live-status-card">
        <div class="live-label">Now Playing</div>
        <div class="live-value" id="live-section">Ready</div>
      </div>
      <div class="live-status-card">
        <div class="live-label">Current Chord</div>
        <div class="live-value" id="live-chord">-</div>
      </div>
      <div class="live-status-card">
        <div class="live-label">Bar</div>
        <div class="live-value" id="live-bar">-</div>
      </div>
      <div class="live-status-card">
        <div class="live-label">Next Chord</div>
        <div class="live-value" id="live-next">-</div>
      </div>
    </div>
    <div class="live-help" id="live-detail">
      Press play. The chart highlight follows this audio player's current time using the same generated chord timeline.
    </div>
  </div>

  {karaoke_lyric_panel_html}

  {chart_root_html}

  <script>
    const timeline = {timeline_json};
    // Expose the timeline so the karaoke lyric-panel snippet can peek
    // at upcoming events to compute the "Next: ..." section label.
    window.__karaokeTimeline = timeline;
    const audio = document.getElementById("live-audio");
    {karaoke_countdown_script}
    {karaoke_lyric_panel_script}
    const sectionEl = document.getElementById("live-section");
    const chordEl = document.getElementById("live-chord");
    const barEl = document.getElementById("live-bar");
    const nextEl = document.getElementById("live-next");
    const detailEl = document.getElementById("live-detail");
    let lastEventIndex = null;
    let animationFrameId = null;

    function eventAt(timeSeconds) {{
      if (!timeline.length) return null;
      if (timeSeconds >= timeline[timeline.length - 1].end_time) {{
        return timeline[timeline.length - 1];
      }}
      let lo = 0;
      let hi = timeline.length - 1;
      while (lo <= hi) {{
        const mid = Math.floor((lo + hi) / 2);
        const event = timeline[mid];
        if (timeSeconds < event.start_time) {{
          hi = mid - 1;
        }} else if (timeSeconds >= event.end_time) {{
          lo = mid + 1;
        }} else {{
          return event;
        }}
      }}
      return timeline[Math.max(0, Math.min(lo, timeline.length - 1))] || timeline[0];
    }}

    function clearHighlight() {{
      document.querySelectorAll(".live-chart-cell.current-chord").forEach((el) => el.classList.remove("current-chord"));
      document.querySelectorAll(".section-card.current").forEach((el) => el.classList.remove("current"));
      document.querySelectorAll(".sub-chord.active-sub").forEach((el) => el.classList.remove("active-sub"));
      document.querySelectorAll(".section-card .section-head .section-meta:last-child").forEach((el) => {{
        if (el.textContent.trim() === "Now Playing") el.textContent = "";
      }});
    }}

    function updateHighlight(force = false) {{
      const audioTime = audio.currentTime || 0;
      const event = eventAt(audioTime);
      if (!event) return;
      const eventChanged = event.event_index !== lastEventIndex;
      if (!eventChanged && !force) {{
        detailEl.textContent = `Audio ${{audioTime.toFixed(2)}}s | Event ${{event.event_index + 1}} of ${{timeline.length}} | ${{event.start_time.toFixed(1)}}s-${{event.end_time.toFixed(1)}}s`;
        return;
      }}
      lastEventIndex = event.event_index;

      const next = timeline[(event.event_index + 1) % timeline.length] || event;
      const isSubdivided = typeof event.subdivision_index === "number";
      const displayChord = isSubdivided
        ? `${{event.chord}}  (${{event.subdivision_index + 1}}/${{event.subdivision_count}})`
        : (event.chord || "-");
      const nextDisplay = (typeof next.subdivision_index === "number" && next.subdivision_index > 0)
        ? next.chord
        : (next.chord || "-");
      sectionEl.textContent = event.section || "Section";
      chordEl.textContent = displayChord;
      barEl.textContent = `${{event.bar_in_section}} of ${{event.section_bars}}`;
      nextEl.textContent = nextDisplay;
      detailEl.textContent = `Audio ${{audioTime.toFixed(2)}}s | Event ${{event.event_index + 1}} of ${{timeline.length}} | ${{event.start_time.toFixed(1)}}s-${{event.end_time.toFixed(1)}}s`;
      // Karaoke section-aware lyric panel - voice mode only.
      // The snippet installs ``window.__karaokeUpdateLyricPanel`` only
      // when a lyrics map was provided, so this is a no-op for
      // instrumentalists (no panel rendered, no listener registered).
      if (typeof window.__karaokeUpdateLyricPanel === "function") {{
        try {{ window.__karaokeUpdateLyricPanel(event); }} catch (e) {{}}
      }}
      const nowPlayingBanner = document.querySelector(".now-playing");
      if (nowPlayingBanner) {{
        nowPlayingBanner.textContent = `Now Playing: ${{event.section}} | Bar ${{event.bar_in_section}} | ${{displayChord}}`;
      }}

      clearHighlight();
      const cells = Array.from(document.querySelectorAll(".live-chart-cell"));
      const currentCell = cells.find((cell) =>
        cell.dataset.section === event.section && Number(cell.dataset.bar) === Number(event.bar_in_section)
      );
      if (currentCell) {{
        currentCell.classList.add("current-chord");
        if (isSubdivided) {{
          const subEl = currentCell.querySelector(`.sub-chord[data-sub="${{event.subdivision_index}}"]`);
          if (subEl) subEl.classList.add("active-sub");
        }}
        const card = currentCell.closest(".section-card");
        if (card) {{
          card.classList.add("current");
          const labels = card.querySelectorAll(".section-head .section-meta");
          const label = labels[labels.length - 1];
          if (label) label.textContent = "Now Playing";
        }}
        if (eventChanged && !audio.paused) {{
          currentCell.scrollIntoView({{ behavior: "smooth", block: "center", inline: "nearest" }});
        }}
      }}
    }}

    function followLoop() {{
      updateHighlight(false);
      if (!audio.paused && !audio.ended) {{
        animationFrameId = window.requestAnimationFrame(followLoop);
      }}
    }}

    function startFollowLoop() {{
      if (animationFrameId) {{
        window.cancelAnimationFrame(animationFrameId);
      }}
      updateHighlight(true);
      animationFrameId = window.requestAnimationFrame(followLoop);
    }}

    document.getElementById("live-stop-btn").addEventListener("click", () => {{
      audio.pause();
      audio.currentTime = 0;
      if (animationFrameId) window.cancelAnimationFrame(animationFrameId);
      clearHighlight();
      sectionEl.textContent = "Stopped";
      chordEl.textContent = "-";
      barEl.textContent = "-";
      nextEl.textContent = "-";
      detailEl.textContent = "Playback stopped. Press play on the audio bar to resume, or regenerate the backing track.";
    }});

    audio.addEventListener("play", startFollowLoop);
    audio.addEventListener("playing", startFollowLoop);
    audio.addEventListener("timeupdate", () => updateHighlight(false));
    audio.addEventListener("seeked", () => updateHighlight(true));
    audio.addEventListener("pause", () => updateHighlight(true));
    audio.addEventListener("ended", () => {{
      if (animationFrameId) window.cancelAnimationFrame(animationFrameId);
      updateHighlight(true);
      detailEl.textContent = "Track ended. Press play to restart the follow-along.";
      {karaoke_bridge_script}
    }});
    window.setInterval(() => {{
      if (!audio.paused && !audio.ended) updateHighlight(false);
    }}, 125);
    updateHighlight(true);
  </script>
</div>
"""


def _section_for_exercise(sections, variation):
    items = [(name, chords) for name, chords in sections.items() if chords]
    if not items:
        return "Full form", []
    return items[variation % len(items)]


def _transition_pair(chords, variation):
    if len(chords) < 2:
        return (chords[0], chords[0]) if chords else ("the tonic", "the next chord")
    idx = variation % (len(chords) - 1)
    return chords[idx], chords[idx + 1]


def _chord_tone_names(chord):
    try:
        return " - ".join(midi_note_name(m) for m in chord_notes(chord)[:4])
    except Exception:
        return "root - 3rd - 5th"


def _technical_pattern_for_exercise(instrument, focus, first_chord, second_chord):
    tones = _chord_tone_names(first_chord)
    family = _instrument_family(instrument)
    if focus == "Harmony":
        return f"Play/sing arpeggios through **{first_chord} -> {second_chord}**: {tones}, then connect to the nearest chord tone in the next bar."
    if focus == "Improvisation":
        return f"Create a 4-note motif from **{first_chord}** chord tones ({tones}); sequence it into **{second_chord}** without changing rhythm."
    if focus == "Rhythm":
        return f"Use one pitch or muted strings/keys to drill the section rhythm first; then add **{first_chord} -> {second_chord}**."
    if focus == "Melody":
        return f"Play a chord-tone line using {tones}; add one approach note into the target note over **{second_chord}**."
    if family == "winds":
        return f"Long-tone ladder: sustain root, 3rd, 5th, 7th of **{first_chord}** with clean attacks."
    if family == "voice":
        return f"Sing chord tones of **{first_chord}** on 'mah', then repeat on the vowel from your lyric cue."
    if family == "guitar":
        return f"Alternate-pick the arpeggio of **{first_chord}**, then switch positions for **{second_chord}**."
    if family == "piano":
        return f"Play **{first_chord}** inversions up the keyboard, then resolve to the nearest inversion of **{second_chord}**."
    if family == "bass":
        return f"Play root-5th-octave-approach for **{first_chord}**, resolving into **{second_chord}** on beat 1."
    return f"Practice the arpeggio of **{first_chord}**, then resolve cleanly into **{second_chord}**."


def _instrument_family(instrument):
    if instrument in ["Saxophone", "Flute", "Trumpet", "Clarinet"]:
        return "winds"
    if instrument == "Voice":
        return "voice"
    if instrument == "Guitar":
        return "guitar"
    if instrument == "Piano":
        return "piano"
    if instrument == "Bass":
        return "bass"
    return "general"


def _focus_area(focus):
    text = str(focus or "").lower()
    if any(token in text for token in ["dynamic", "crescendo", "decrescendo", "loud", "soft", "intensity", "touch"]):
        return "Dynamics"
    if any(token in text for token in ["strum", "rhythm", "comp", "groove", "pocket", "syncopation", "left-hand", "left hand"]):
        return "Rhythm"
    if any(token in text for token in ["voicing", "voice leading", "inversion", "reharm", "harmony", "triad", "barre", "transition", "root motion"]):
        return "Harmony"
    if any(token in text for token in ["lead", "melody", "double stop", "phrasing", "articulation", "tone", "breath", "vibrato", "range", "endurance"]):
        return "Melody"
    if any(token in text for token in ["solo", "improv", "walking", "bebop", "scales", "guide tone"]):
        return "Improvisation"
    if "ear" in text or "pitch accuracy" in text:
        return "Ear Training"
    return "Technique"


def _difficulty_phrase(level, variation):
    if level == "Beginner":
        return [
            "slow and clean",
            "with a metronome on every beat",
            "two bars at a time",
        ][variation % 3]
    if level == "Intermediate":
        return [
            "with steady groove and connected phrasing",
            "using chord tones on strong beats",
            "then over the whole section without stopping",
        ][variation % 3]
    return [
        "with expressive timing and dynamic shape",
        "using guide tones, anticipations, and motivic development",
        "then displace the rhythm by one eighth-note while staying locked to the form",
    ][variation % 3]


def _practice_time_blocks(minutes):
    total = max(10, int(minutes or 30))
    warmup = max(2, int(round(total * 0.18)))
    section = max(3, int(round(total * 0.36)))
    focus_block = max(3, int(round(total * 0.30)))
    review = max(1, total - warmup - section - focus_block)
    return {
        "total": total,
        "warmup": warmup,
        "section": section,
        "focus": focus_block,
        "review": review,
    }


def _exercise_span(level, bars):
    bars = max(1, bars)
    if level == "Beginner":
        return min(4, bars)
    if level == "Intermediate":
        return min(8, bars)
    return bars


def _chord_run(chords, limit=4):
    if not chords:
        return "the first chord"
    return " | ".join(chords[:max(1, min(limit, len(chords)))])


def _guide_tone_pair(chord):
    try:
        tones = chord_notes(chord)
        if len(tones) >= 4:
            return midi_note_name(tones[1]), midi_note_name(tones[3])
        if len(tones) >= 2:
            return midi_note_name(tones[1]), midi_note_name(tones[-1])
    except Exception:
        pass
    return "3rd", "7th"


def _root_and_fifth(chord):
    try:
        root = bass_note(chord)
        return midi_note_name(root), midi_note_name(root + 7)
    except Exception:
        return "root", "5th"


def _section_role(section_name: str) -> str:
    """Classify a song section for rhythm/practice guidance."""
    name = str(section_name or "").strip().lower()

    if not name or name in {"full song", "full", "all"}:
        return "full"
    if "intro" in name:
        return "intro"
    if "verse" in name or "a section" in name or name == "a":
        return "verse"
    if "pre" in name:
        return "pre_chorus"
    if "chorus" in name or "refrain" in name or "b section" in name or name == "b":
        return "chorus"
    if "bridge" in name or "middle" in name:
        return "bridge"
    if "solo" in name or "improv" in name:
        return "solo"
    if "outro" in name or "ending" in name or "tag" in name:
        return "outro"

    return "section"


def _section_character(section_name):
    try:
        role = _section_role(section_name)
    except Exception:
        role = "section"
    if role == "chorus":
        return "play this fuller than the verse, with stronger beat-2/4 energy"
    if role == "verse":
        return "keep this lighter and leave space for the melody"
    if role == "bridge":
        return "change color here so the form feels like it has moved somewhere new"
    if role == "intro":
        return "make the entrance steady and uncluttered"
    if role == "outro":
        return "let the final pass relax without losing time"
    return "make the section shape clear without overplaying"


def _section_dynamic_shape(section_name):
    try:
        role = _section_role(section_name)
    except Exception:
        role = "section"
    if role == "chorus":
        return "build into a stronger, more projected chorus sound without rushing"
    if role == "verse":
        return "stay softer and more restrained so the lyric/melody can lead"
    if role == "bridge":
        return "create contrast: either pull back dramatically or swell into the return"
    if role == "intro":
        return "start controlled and leave headroom for the first main section"
    if role == "outro":
        return "release intensity gradually while keeping time steady"
    if role in ("pre", "pre_chorus"):
        return "crescendo through the section so the next arrival feels earned"
    return "shape the phrase with a clear beginning, lift, and release"


def _rhythm_profile(time_signature="4/4", groove_style="", section_name="", bpm=100):
    try:
        role = _section_role(section_name)
    except Exception:
        role = "section"
    text = f"{time_signature} {groove_style} {section_name}".lower()
    if "6/8" in text:
        profile = {
            "feel": "6/8 pulse",
            "count": "Count `1-2-3 4-5-6`; feel two big beats per bar.",
            "accent": "Accent beat 1 and beat 4; keep the inner eighths flowing.",
            "guitar": "`D - U D - U` or arpeggiate bass-treble-treble twice per bar.",
            "piano": "Left hand lands on 1 and 4; right hand rolls broken chords across the six eighths with light pedal.",
            "bass": "Place roots on 1 and 4, then add a pickup into the next bar only after the pulse is steady.",
            "winds": "Phrase in two groups of three; breathe before beat 1 and avoid clipping beat 4.",
            "voice": "Speak the lyric in two large pulses, then sing with breath support through beat 4.",
        }
    elif "bossa" in text:
        profile = {
            "feel": "bossa syncopation",
            "count": "Count straight eighths but keep the accent light and off the heavy downbeat.",
            "accent": "Let syncopated upbeats answer the bass; do not over-accent every beat.",
            "guitar": "Use a soft bass note on 1/3 with upper-string upbeats: `Bass - up - up | Bass - up - up`.",
            "piano": "Left hand plays a light root/fifth pulse; right hand comps short offbeat shells with minimal pedal.",
            "bass": "Keep a gentle root-fifth pulse and make note length even.",
            "winds": "Use airy, connected phrases with light articulation on syncopated answers.",
            "voice": "Keep consonants light and float over the syncopation rather than punching it.",
        }
    elif "swing" in text or "shuffle" in text:
        profile = {
            "feel": "swing/shuffle feel",
            "count": "Count triplet-based eighths: `1-trip-let 2-trip-let`; long-short, not straight.",
            "accent": "Lean into 2 and 4, with relaxed offbeats.",
            "guitar": "Use a light shuffle: `D - dU D - dU`, muting lightly on 2 and 4.",
            "piano": "Comp short shells behind the beat; left hand can walk or play sparse roots.",
            "bass": "Walk quarter notes with clean approach tones into chord changes.",
            "winds": "Tongue lightly on offbeats and place guide tones on strong beats.",
            "voice": "Let the phrase sit behind the beat; avoid straightening the swing.",
        }
    elif "funk" in text:
        profile = {
            "feel": "funk syncopation",
            "count": "Count sixteenths: `1 e & a 2 e & a`; keep the hand moving constantly.",
            "accent": "Strong pocket on 1, crisp muted ghosts, and tight 2/4 backbeat awareness.",
            "guitar": "`x x U x | x U x U` muted sixteenths first, then open only the target accents.",
            "piano": "Use short stabs on syncopated sixteenths; leave space for bass and drums.",
            "bass": "Lock the first note to the kick, then keep ghost-note fills short and repeatable.",
            "winds": "Use short falls/stabs as answers, not continuous lines.",
            "voice": "Keep rhythmic diction tight and make consonants part of the groove.",
        }
    elif "rock" in text:
        profile = {
            "feel": "rock 8th-note drive",
            "count": "Count straight eighths: `1 & 2 & 3 & 4 &`.",
            "accent": "Accent 2 and 4; make chorus downbeats bigger than verse downbeats.",
            "guitar": "Verse: palm-muted downstrokes. Chorus: `D D U U D U` with stronger 2/4 accents.",
            "piano": "Left hand plays steady octaves or root-fifths; right hand hits chord accents on 2/4 or anticipation upbeats.",
            "bass": "Use eighth-note roots/fifths with consistent attack and longer chorus notes.",
            "winds": "Use concise riff answers and save sustained notes for section arrivals.",
            "voice": "Use clearer consonants in the verse and stronger projection into the chorus.",
        }
    elif "ballad" in text or bpm <= 76:
        profile = {
            "feel": "ballad pulse",
            "count": "Count subdivisions quietly so slow bars do not sag.",
            "accent": "Keep beat 1 grounded and let the phrase breathe toward beat 4.",
            "guitar": "Use arpeggiated bass-to-treble picking or soft `D - D U` strums with wide dynamic space.",
            "piano": "Left hand plays sparse roots/5ths; right hand places voicings after the beat with tasteful sustain.",
            "bass": "Use long, even notes and avoid fills until phrase endings.",
            "winds": "Use supported long tones and leave real silence between phrases.",
            "voice": "Keep the verse intimate; crescendo only into emotional arrivals.",
        }
    else:
        profile = {
            "feel": "straight 8th-note pop groove",
            "count": "Count `1 & 2 & 3 & 4 &` with steady subdivisions.",
            "accent": "Keep 2 and 4 alive; make section endings slightly more intentional.",
            "guitar": "`D D U - U D U`; mute one practice pass before adding chord changes.",
            "piano": "Left hand roots on 1/3; right hand light offbeat chord stabs or broken-chord eighths.",
            "bass": "Root on 1, fifth/octave on 3, then one approach into the next chord.",
            "winds": "Use two-bar phrases and land chord tones on strong beats.",
            "voice": "Speak rhythm first, then sing with clean pickups into each phrase.",
        }
    if role == "verse":
        profile["section_note"] = "Verse approach: play it lighter and simpler than the chorus."
    elif role == "chorus":
        profile["section_note"] = "Chorus approach: increase accent weight and rhythmic confidence."
    elif role == "bridge":
        profile["section_note"] = "Bridge approach: leave more space or change the pattern for contrast."
    elif role in ("pre", "pre_chorus"):
        profile["section_note"] = "Pre-chorus approach: add motion gradually so the chorus lands."
    else:
        profile["section_note"] = "Keep the groove consistent and make phrase endings clear."
    return profile


def _rhythm_guidance(instrument, *, section_name, groove_style, time_signature, bpm):
    family = _instrument_family(instrument)
    profile = _rhythm_profile(time_signature, groove_style, section_name, bpm)
    instrument_line = profile.get(family, profile["guitar"] if family == "guitar" else profile["piano"])
    overlay = (
        f"Rhythm: {html.escape(profile['feel'])}. {html.escape(profile['count'])} "
        f"{html.escape(profile['accent'])} {html.escape(instrument_line)} "
        f"{html.escape(profile['section_note'])}"
    )
    practice = (
        f"{profile['feel']}: {profile['count']} {profile['accent']} "
        f"For {instrument}, {instrument_line} {profile['section_note']}"
    )
    return {
        "feel": profile["feel"],
        "count": profile["count"],
        "accent": profile["accent"],
        "instrument": instrument_line,
        "section_note": profile["section_note"],
        "practice": practice,
        "overlay": overlay,
    }


def _dynamics_guidance(instrument, section_name, first_chord, second_chord):
    family = _instrument_family(instrument)
    shape = _section_dynamic_shape(section_name)
    lines = {
        "guitar": f"strum **{first_chord} -> {second_chord}** at p, mp, mf, then f; keep the same tempo while changing pick attack and accent weight",
        "piano": f"balance left-hand roots softer than right-hand color tones, then crescendo through **{first_chord} -> {second_chord}** without speeding up",
        "bass": f"play the same groove at three intensities; keep note length and attack consistent while changing volume",
        "winds": f"hold a supported crescendo into **{second_chord}**, then repeat with a clean decrescendo and identical pitch center",
        "voice": f"sing the phrase softly first, then crescendo into the emotional word while keeping breath support stable",
    }
    line = lines.get(family, f"shape **{first_chord} -> {second_chord}** from soft to strong, then back down without changing tempo")
    overlay = f"Dynamics: {html.escape(shape)}. {html.escape(line)}."
    return {"shape": shape, "practice": line, "overlay": overlay}


def _instrument_drills(
    *,
    family,
    instrument,
    level,
    focus,
    section_name,
    section_chords,
    first_chord,
    second_chord,
    chord_tones,
    span,
    blocks,
    variation,
    lyric_line="",
    time_signature="4/4",
    groove_style="Pop groove",
    bpm=100,
):
    chord_path = _chord_run(section_chords, span)
    guide_a, guide_b = _guide_tone_pair(first_chord)
    next_guide_a, next_guide_b = _guide_tone_pair(second_chord)
    root_a, fifth_a = _root_and_fifth(first_chord)
    root_b, fifth_b = _root_and_fifth(second_chord)
    reps = 2 if blocks["total"] <= 20 else 3 if blocks["total"] <= 45 else 4
    advanced = level == "Advanced"
    beginner = level == "Beginner"
    focus_area = _focus_area(focus)
    rhythm = _rhythm_guidance(
        instrument,
        section_name=section_name,
        groove_style=groove_style,
        time_signature=time_signature,
        bpm=bpm,
    )
    dynamics = _dynamics_guidance(instrument, section_name, first_chord, second_chord)

    if family == "guitar":
        lead_task = (
            f"Lead drill: over **{first_chord}**, slide into **{guide_a}** from one fret below, "
            f"answer over **{second_chord}** by targeting **{next_guide_a}**, then add either a half-step bend or a double-stop on the last two beats."
        )
        rhythm_task = (
            f"Strumming drill ({rhythm['feel']}): loop **{chord_path}** for {reps} passes. "
            f"{rhythm['count']} {rhythm['accent']} Pattern: {rhythm['instrument']} "
            f"Pass 1 is muted strings only; pass 2 adds chord changes; pass 3 follows the section note: {rhythm['section_note']}"
        )
        dynamic_task = f"Dynamics drill: {dynamics['practice']}."
        harmony_task = (
            f"Voicing transition: play **{first_chord} -> {second_chord}** as two compact 3- or 4-string grips, then move the same change to a second neck position. "
            f"Keep any common tone ringing and shift only the fingers that must move."
        )
        technique_task = (
            f"Picking/fretboard drill: alternate-pick **{chord_tones}** through **{first_chord}**, shift position, then resolve to **{next_guide_a}** on beat 1 of **{second_chord}**."
        )
        if focus_area == "Rhythm":
            primary = rhythm_task
        elif focus_area == "Melody":
            primary = lead_task
        elif focus_area == "Harmony":
            primary = harmony_task
        elif focus_area == "Improvisation":
            primary = f"Solo cell: make a two-bar phrase from **{guide_a}**, **{guide_b}**, and one bend/slide; repeat it over **{second_chord}** with one rhythmic change."
        elif focus_area == "Ear Training":
            primary = f"Ear drill: sing the roots of **{chord_path}**, then find them on one string before playing the chords. Check each change by ear before looking down."
        elif focus_area == "Dynamics":
            primary = dynamic_task
        else:
            primary = technique_task
        secondary = lead_task if focus_area == "Rhythm" else rhythm_task
        return [
            primary,
            secondary,
            dynamic_task if focus_area != "Dynamics" else harmony_task,
        ]

    if family == "piano":
        shell = (
            f"Shell voicing drill: left hand plays roots **{root_a} -> {root_b}**; right hand plays guide tones "
            f"**{guide_a}/{guide_b} -> {next_guide_a}/{next_guide_b}** with the smallest possible motion."
        )
        inversion = (
            f"Inversion drill: play **{first_chord} -> {second_chord}** in three right-hand positions, choosing the inversion that keeps the top note moving by step."
        )
        comping = (
            f"Comping rhythm ({rhythm['feel']}): through **{chord_path}**, {rhythm['count']} "
            f"{rhythm['accent']} For piano, {rhythm['instrument']}"
        )
        dynamic_task = f"Dynamics drill: {dynamics['practice']}."
        reharm = (
            f"Reharm exercise: on the final bar of the {span}-bar loop, add a passing dominant or diminished approach into **{second_chord}**, then compare it to the plain chart."
        )
        if focus_area == "Rhythm":
            primary = comping
        elif focus_area == "Harmony":
            primary = shell if beginner else f"{shell} Then try: {reharm}"
        elif focus_area == "Melody":
            primary = f"Top-note melody: keep the right-hand top note singing through **{chord_path}** while the inner notes voice-lead quietly."
        elif focus_area == "Improvisation":
            primary = f"One-hand improv: left hand plays shells through **{chord_path}**; right hand improvises using **{chord_tones}** plus one neighbor tone."
        elif focus_area == "Ear Training":
            primary = f"Ear drill: play **{first_chord}**, sing its top note, then move to **{second_chord}** and identify whether the top note moved up, down, or stayed common."
        elif focus_area == "Dynamics":
            primary = dynamic_task
        else:
            primary = inversion
        return [primary, shell if focus_area != "Dynamics" else comping, dynamic_task if not advanced else reharm]

    if family == "winds":
        articulation = (
            f"Articulation/rhythm drill ({rhythm['feel']}): play **{chord_tones}** over **{first_chord}** twice. "
            f"{rhythm['count']} {rhythm['accent']} Then resolve to **{next_guide_a}** on beat 1 of **{second_chord}**."
        )
        guide = (
            f"Guide-tone target: make a {span}-bar line through **{chord_path}** where beat 1 of each bar lands on a 3rd or 7th, starting with **{guide_a}** or **{guide_b}**."
        )
        breath = (
            f"Breath/phrase plan: take one silent breath before **{section_name}**, play two-bar phrases, and leave a full eighth-note of space before the next phrase."
        )
        scale = (
            f"Scale-to-chord drill: run the scale around **{first_chord}** for one bar, then restrict bar 2 to chord tones only and land on **{next_guide_b}**."
        )
        dynamic_task = f"Dynamics drill: {dynamics['practice']}."
        if focus_area == "Rhythm":
            primary = articulation
        elif focus_area in ["Harmony", "Improvisation"]:
            primary = guide
        elif focus_area == "Melody":
            primary = f"Phrase shaping: play a two-bar question ending softly on **{guide_b}**, then answer louder into **{next_guide_a}** over **{second_chord}**."
        elif focus_area == "Ear Training":
            primary = f"Ear drill: sing **{guide_a}** and **{guide_b}** before playing them, then resolve by ear into **{next_guide_a}** over **{second_chord}**."
        elif focus_area == "Dynamics":
            primary = dynamic_task
        else:
            primary = scale
        return [primary, breath, dynamic_task if focus_area != "Dynamics" else guide]

    if family == "bass":
        groove = (
            f"Pocket drill: play **{root_a}** on beat 1 and **{fifth_a}** on beat 3 for **{first_chord}**, "
            f"then **{root_b}** and **{fifth_b}** for **{second_chord}**. Keep every note the same length."
        )
        walking = (
            f"Walking line: one note per beat over **{first_chord} -> {second_chord}**: root, fifth, octave, chromatic approach into **{root_b}**."
        )
        approach = (
            f"Approach-note drill: on beat 4 before each chord change in **{chord_path}**, approach the next root from a half-step below, then land firmly on beat 1."
        )
        rhythm = (
            f"Rhythmic consistency ({rhythm['feel']}): loop the first {span} bars with the backing track. "
            f"{rhythm['count']} {rhythm['accent']} For bass, {rhythm['instrument']}"
        )
        dynamic_task = f"Dynamics drill: {dynamics['practice']}."
        if focus_area == "Rhythm":
            primary = rhythm
        elif focus_area == "Harmony":
            primary = f"Outline drill: play root, 3rd, 5th, approach tone for each bar of **{chord_path}** without adding fills."
        elif focus_area == "Improvisation":
            primary = walking
        elif focus_area == "Melody":
            primary = f"Connecting line: write a simple bass melody from **{root_a}** to **{root_b}** using no more than four notes per bar."
        elif focus_area == "Ear Training":
            primary = f"Ear drill: sing each root in **{chord_path}**, then play root-fifth-root on bass and name the interval before moving on."
        elif focus_area == "Dynamics":
            primary = dynamic_task
        else:
            primary = approach
        return [primary, groove, dynamic_task if focus_area != "Dynamics" else walking if not beginner else approach]

    if family == "voice":
        cue = lyric_line or f"the first phrase of {section_name}"
        breathing = (
            f"Breathing drill: inhale silently for 2 counts before **{section_name}**, sing _{cue}_ on `oo`, then repeat on `ah` without changing jaw height."
        )
        delivery = (
            f"Lyric delivery: speak _{cue}_ in time over **{chord_path}**, mark the word that should peak emotionally, then sing it with a softer pickup and stronger release."
        )
        dynamics = (
            f"Dynamic shape: {dynamics['practice']}; sing bars 1-{span} mezzo-piano, grow into the strongest chord, then taper the final note without dropping pitch."
        )
        vowels = (
            f"Vowel shaping: sustain the main vowel from _{cue}_ over **{first_chord}**, then move to **{second_chord}** while keeping the vowel stable."
        )
        if focus_area == "Rhythm":
            primary = f"Rhythm/phrasing drill ({rhythm['feel']}): speak _{cue}_ with this pulse. {rhythm['count']} {rhythm['accent']} Then sing only the rhythm on one pitch."
        elif focus_area == "Melody":
            primary = dynamics
        elif focus_area == "Harmony":
            primary = f"Pitch-center drill: hum the root of **{first_chord}**, sing **{chord_tones}** on `mah`, then resolve into **{second_chord}**."
        elif focus_area == "Improvisation":
            primary = f"Vocal variation: sing _{cue}_ once as written, then improvise a two-note answer on `na` using chord tones from **{first_chord}**."
        elif focus_area == "Ear Training":
            primary = f"Ear drill: sing the root, 3rd, and 5th of **{first_chord}** on `loo`, then identify which note feels most stable against **{second_chord}**."
        elif focus_area == "Dynamics":
            primary = dynamics
        else:
            primary = breathing
        return [primary, delivery, vowels if focus_area != "Technique" else dynamics]

    return [
        f"Loop **{chord_path}** for {reps} passes and make the change **{first_chord} -> {second_chord}** land cleanly on beat 1.",
        f"Name and play/sing the chord tones of **{first_chord}**: {chord_tones}.",
        f"Record one pass of **{section_name}** and listen only for time, tone, and the section ending.",
    ]


def daily_practice_breakdown_markdown(
    song,
    sections,
    instrument,
    level,
    focus,
    minutes,
    variation=0,
    *,
    groove_override: str | None = None,
):
    section_name, section_chords = _section_for_exercise(sections, variation)
    first_chord, second_chord = _transition_pair(section_chords, variation)
    blocks = _practice_time_blocks(minutes)
    span = _exercise_span(level, len(section_chords))
    chord_path = _chord_run(section_chords, span)
    family = _instrument_family(instrument)
    time_signature = default_time_signature(song, sections)
    groove_style = _resolve_groove_override(groove_override)
    bpm = int(st.session_state.get("backing_track_bpm", 100))
    rhythm = _rhythm_guidance(
        instrument,
        section_name=section_name,
        groove_style=groove_style,
        time_signature=time_signature,
        bpm=bpm,
    )
    dynamics = _dynamics_guidance(instrument, section_name, first_chord, second_chord)

    instrument_focus = {
        "guitar": f"right-hand groove plus **{first_chord} -> {second_chord}** voicing movement",
        "piano": f"shells, inversions, and voice leading through **{first_chord} -> {second_chord}**",
        "winds": f"articulation and guide-tone targets through **{first_chord} -> {second_chord}**",
        "bass": f"pocket, root/fifth movement, and approach notes into **{second_chord}**",
        "voice": f"breath, vowel, lyric delivery, and dynamics for **{section_name}**",
    }.get(family, f"clean time and chord-tone control through **{first_chord} -> {second_chord}**")

    focus_area = _focus_area(focus)
    focus_task = {
        "Rhythm": f"{rhythm['practice']} Loop at about 70-80% tempo first; mute or simplify the part before adding full chord changes.",
        "Dynamics": f"{dynamics['practice']}. Record two passes: restrained verse-level intensity, then fuller chorus-level intensity.",
        "Harmony": f"name the function/color of **{first_chord} -> {second_chord}**, then voice-lead by nearest chord tones",
        "Melody": f"build a two-bar phrase that peaks once and resolves into **{second_chord}**",
        "Improvisation": f"improvise only with chord tones for one pass, then add one approach note into **{second_chord}**",
        "Ear Training": f"sing the root and 3rd of **{first_chord}**, then check it on your instrument before moving to **{second_chord}**",
    }.get(focus_area, f"make the change **{first_chord} -> {second_chord}** clean, musical, and repeatable")

    return f"""
**Coach assignment for today:** make **{section_name}** feel intentional, not just correct.

- Warmup ({blocks['warmup']} min): prepare **{instrument}** for {instrument_focus}; keep the sound relaxed and even.
- Song section ({blocks['section']} min): loop **{section_name}** from **{song}** for {span} bars: **{chord_path}**. First pass is accuracy, second pass is musical shape.
- {focus} block ({blocks['focus']} min): {focus_task}.
- Review ({blocks['review']} min): record one pass, then write one concrete fix for time, one for tone/phrasing, and one musical idea to keep tomorrow.
""".strip()


def song_practice_plan(
    song,
    sections,
    instrument,
    level,
    focus,
    variation,
    section_lyrics=None,
    minutes=30,
    *,
    groove_override: str | None = None,
):
    section_name, section_chords = _section_for_exercise(sections, variation)
    first_chord, second_chord = _transition_pair(section_chords, variation)
    family = _instrument_family(instrument)
    difficulty = _difficulty_phrase(level, variation)
    bars = len(section_chords)
    cycle = max(1, variation + 1)
    chord_tones = _chord_tone_names(first_chord)
    blocks = _practice_time_blocks(minutes)
    span = _exercise_span(level, bars)
    chord_path = _chord_run(section_chords, span)
    time_signature = default_time_signature(song, sections)
    groove_style = _resolve_groove_override(groove_override)
    bpm = int(st.session_state.get("backing_track_bpm", 100))
    section_text = (section_lyrics or {}).get(section_name, "")
    first_line = next(
        (line.strip() for line in str(section_text).splitlines() if line.strip()),
        "",
    )
    lyric_application = ""
    if section_text and instrument == "Voice":
        lyric_application = (
            f"\n**Lyric application**\n"
            f"- Start with this section text: _{first_line}_\n"
            f"- Speak it in rhythm over **{chord_path}**, mark one breath, then sing it on vowels before adding consonants.\n"
        )
    elif section_text:
        lyric_application = (
            f"\n**Form cue**\n"
            f"- Use this cue to locate the section while playing: _{first_line}_\n"
        )

    drills = _instrument_drills(
        family=family,
        instrument=instrument,
        level=level,
        focus=focus,
        section_name=section_name,
        section_chords=section_chords,
        first_chord=first_chord,
        second_chord=second_chord,
        chord_tones=chord_tones,
        span=span,
        blocks=blocks,
        variation=variation,
        lyric_line=first_line,
        time_signature=time_signature,
        groove_style=groove_style,
        bpm=bpm,
    )

    if level == "Beginner":
        development = f"Keep the loop to {span} bars. Slow down until the change **{first_chord} -> {second_chord}** is clean twice in a row."
        creative_step = f"Change only one thing on the final pass: softer verse touch, stronger chorus touch, or one cleaner breath/entrance."
    elif level == "Intermediate":
        development = f"Connect the drill to the backing track for {blocks['focus']} minutes, then record one full pass of **{section_name}**."
        creative_step = f"Create one alternate version of the same {span}-bar phrase: new register, new voicing, new articulation, or a small fill into **{second_chord}**."
    else:
        development = f"After the clean pass, add one controlled variation: displacement, reharm, articulation change, fill, or dynamic contrast based on your instrument."
        creative_step = f"Test one advanced choice in context: substitute a passing color, delay a resolution, displace the rhythm, or reharmonize only the last bar of the loop."

    return f"""
### Conservatory Coach Plan {cycle}: {section_name}
**Song:** {song}  
**Target section:** {section_name} — {bars} bars  
**Today:** {blocks['total']} minutes on **{instrument}**, **{level}**, **{focus}**  
**Chord focus:** **{first_chord} -> {second_chord}**  
**Loop:** **{chord_path}**  
**Section character:** {_section_character(section_name)}

**1. Technical Warm-up ({blocks['warmup']} min)**
- Play/sing the chord tones of **{first_chord}**: {chord_tones}. Then resolve into **{second_chord}** {difficulty}.

**2. Song-Specific Drill ({blocks['section']} min)**
- {drills[0]}

**3. Instrument + Focus Coaching ({blocks['focus']} min)**
- {drills[1]}
- {drills[2]}

**4. Creativity / Musicianship**
- {creative_step}

{lyric_application}

**5. Progress Check ({blocks['review']} min)**
- {development}
- Success standard: one clean take where time, tone, and section shape are all believable.
"""


def default_time_signature(song, sections):
    return default_time_signature_for_record(
        {"title": song},
        sections,
        song_title=song,
    )


def default_song_bpm(song_title: str, song_data: dict | None = None) -> int:
    title = (song_title or "").lower()
    if song_data:
        try:
            from song_catalog.verified_core_refs import reference_for

            ref = reference_for(song_data.get("title", ""), song_data.get("artist", ""))
            if ref and ref.get("default_bpm"):
                return int(ref["default_bpm"])
        except Exception:
            pass
    if "shape of you" in title:
        return 96
    if song_data and (song_data.get("extensions") or {}).get("default_bpm"):
        try:
            return int(song_data["extensions"]["default_bpm"])
        except (TypeError, ValueError):
            pass
    return 100


def _ensure_song_bpm_defaults(song_title: str, song_data: dict | None = None) -> int:
    """Sync BPM session state before any ``backing_track_bpm`` widget is rendered."""
    sid = playback_song_id(
        is_custom=is_custom_progression(st.session_state),
        song_title=song_title,
        song_artist=str((song_data or {}).get("artist", "")),
        custom_name=str((st.session_state.get(CPL_ACTIVE_KEY) or {}).get("name", "")),
        custom_revision=str((st.session_state.get(CPL_ACTIVE_KEY) or {}).get("id", "")),
    )
    return sync_backing_bpm_before_widget(
        st,
        sid,
        default_song_bpm(song_title, song_data),
    )


def practice_text(level, instrument=None, sections=None, focus=None, *, groove_override: str | None = None):
    sections = sections or {}
    section_name, section_chords = _section_for_exercise(sections, 0)
    first_chord, second_chord = _transition_pair(section_chords, 0)
    chord_path = _chord_run(section_chords, _exercise_span(level, len(section_chords)))
    focus_area = _focus_area(focus)
    time_signature = default_time_signature(globals().get("song", ""), sections)
    groove_style = _resolve_groove_override(groove_override)
    bpm = int(st.session_state.get("backing_track_bpm", 100))
    rhythm = _rhythm_guidance(
        instrument or "",
        section_name=section_name,
        groove_style=groove_style,
        time_signature=time_signature,
        bpm=bpm,
    )
    dynamics = _dynamics_guidance(instrument or "", section_name, first_chord, second_chord)
    coach_line = {
        "Rhythm": f"{rhythm['practice']} Mute/simplify first, then add the chord changes.",
        "Dynamics": f"{dynamics['practice']}. Keep tempo steady while changing volume and intensity.",
        "Harmony": f"Study **{first_chord} -> {second_chord}**: name common tones, then move to the nearest available voicing.",
        "Melody": f"Create a two-bar phrase over **{chord_path}** that lands clearly on a chord tone.",
        "Improvisation": f"Improvise one chorus using only chord tones, then repeat with one chromatic approach into **{second_chord}**.",
        "Ear Training": f"Sing the root and 3rd of **{first_chord}**, then verify on your instrument before playing the section.",
    }.get(focus_area, f"Make **{first_chord} -> {second_chord}** clean, in time, and expressive.")

    if level == "Beginner":
        base = f"""
### Beginner Practice Sheet
- Work on **{section_name}** only: **{chord_path}**.
- Count aloud, name each chord before playing it, and stop if the pulse wobbles.
- Coach target: {coach_line}
"""
        if instrument == "Voice":
            base += vocal_practice_text(level, sections or {})
        if instrument == "Guitar":
            base += guitar_practice_text(focus, level)
        return base

    if level == "Intermediate":
        base = f"""
### Intermediate Practice Sheet
- Loop **{section_name}** with a metronome/backing track: **{chord_path}**.
- First pass: accurate changes. Second pass: dynamic shape. Third pass: one creative variation.
- Coach target: {coach_line}
"""
        if instrument == "Voice":
            base += vocal_practice_text(level, sections or {})
        if instrument == "Guitar":
            base += guitar_practice_text(focus, level)
        return base

    base = f"""
### Advanced Practice Sheet
- Analyze **{section_name}** as a performance problem, not a chord list: **{chord_path}**.
- Run one clean take, one color/voicing take (extensions & voice leading), and one final musical take.
- Name the 3rd and 7th of each chord, then add one upper color (9, 11, or 6) without changing the groove.
- Coach target: {coach_line}
"""
    _song_lc = str(globals().get("song", "")).lower()
    if "rocket man" in _song_lc:
        base += (
            "\n- **Rocket Man:** Slash bass (**Bb/D, Cm7/Bb, F/A, F/C**) stays on beat 1; "
            "richness lives in **Gm9/Gm11** and **C13sus4→C9**. Chorus comp: smooth Bbmaj7↔Ebmaj9, not jazz reharm."
        )
    elif "billie jean" in _song_lc:
        base += (
            "\n- **Billie Jean:** Same pocket as Intermediate—**F#m9→G#m7→Amaj7→G#m7** with tight rhythm. "
            "**B5** stays power; bridge **Dmaj9/F#m9** is color only before **C#9**."
        )
    if instrument == "Voice":
        base += vocal_practice_text(level, sections or {})
    if instrument == "Guitar":
        base += guitar_practice_text(focus, level)
    return base

def load_logs():
    try:
        import streamlit as st

        from practice_log_persistence import load_practice_logs

        return load_practice_logs(st=st)
    except Exception:
        from music_workspace_paths import music_data_path

        data_file = music_data_path("practice_history")
        if data_file.exists():
            try:
                return json.loads(data_file.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []


def save_logs(logs):
    try:
        import streamlit as st

        from practice_log_persistence import save_practice_logs

        save_practice_logs(logs, st=st)
        return
    except Exception:
        pass
    from music_workspace_paths import music_data_path

    data_file = music_data_path("practice_history")
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text(json.dumps(logs, indent=2), encoding="utf-8")


def _inject_practice_log_studio_styles() -> None:
    st.markdown(
        """
<style>
.st-key-practice_log_dashboard_panel{
  border:1px solid rgba(148,163,184,.28);border-radius:18px;
  background:linear-gradient(180deg,rgba(255,255,255,.96),rgba(248,250,252,.94));
  box-shadow:0 18px 38px rgba(15,23,42,.08);padding:1rem 1.05rem .85rem;margin-top:.35rem;
}
.ui-log-banner{
  border:1px solid rgba(148,163,184,.24);border-radius:14px;padding:.8rem .95rem;margin:.1rem 0 .8rem;
  background:linear-gradient(130deg,rgba(30,64,175,.09),rgba(217,119,6,.10));
}
.ui-log-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.55rem;margin:.2rem 0 .85rem;}
.ui-log-kpi{border:1px solid rgba(148,163,184,.24);border-radius:12px;background:#fff;padding:.62rem .72rem;}
.ui-log-kpi-label{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em;font-weight:700;margin:0 0 .2rem;}
.ui-log-kpi-value{font-size:1.18rem;font-weight:850;color:#0f172a;line-height:1.2;margin:0;}
.ui-log-kpi-sub{font-size:.76rem;color:#475569;margin:.12rem 0 0;}
.st-key-log_filter_panel,.st-key-log_insights_panel,.st-key-log_add_session_panel,.st-key-log_history_panel,.st-key-log_summary_panel,.st-key-log_practice_analysis_panel{
  border:1px solid rgba(148,163,184,.24);border-radius:14px;background:rgba(255,255,255,.94);padding:.78rem .85rem;margin:.45rem 0;
}
.ui-log-section-title{font-size:.96rem;font-weight:800;color:#0f172a;margin:0 0 .15rem;}
.ui-log-section-sub{font-size:.82rem;color:#64748b;margin:0 0 .55rem;}
.ui-log-session-card{
  border:1px solid rgba(148,163,184,.24);border-radius:12px;background:#fff;padding:.66rem .72rem;margin:.45rem 0;
  box-shadow:0 8px 20px rgba(15,23,42,.05);
}
.ui-log-session-head{display:flex;justify-content:space-between;gap:.6rem;align-items:flex-start;}
.ui-log-session-song{font-size:.97rem;font-weight:800;color:#0f172a;line-height:1.3;margin:0;}
.ui-log-session-artist{font-size:.78rem;color:#64748b;margin:.1rem 0 0;}
.ui-log-badges{display:flex;flex-wrap:wrap;gap:.35rem;margin:.45rem 0 .35rem;}
.ui-log-badge{
  border-radius:999px;border:1px solid rgba(148,163,184,.28);padding:.2rem .5rem;
  background:#f8fafc;color:#1e293b;font-size:.72rem;font-weight:700;
}
.ui-log-notes{font-size:.8rem;color:#334155;margin:.35rem 0 0;}
</style>
        """,
        unsafe_allow_html=True,
    )


def _to_int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _parse_log_date(raw_value) -> date | None:
    if not raw_value:
        return None
    text = str(raw_value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except Exception:
            continue
    return None


def _log_mode_options() -> list[str]:
    return [
        "Song Work",
        "Technique",
        "Improvisation",
        "Ear Training",
        "Performance Prep",
        "Warmup",
        "Other",
    ]


def _refresh_practice_log_coach(
    session_state: dict,
    *,
    highlight_entry: dict | None = None,
    openai_api_key: str = "",
) -> None:
    """Rebuild Phase B coach view from disk logs and recording history."""
    from practice_log_coach import (
        build_practice_log_coach_view,
        maybe_enhance_coach_view_with_openai,
    )
    from practice_log_insights import load_analysis_history
    from practice_log_state import load_entries

    logs = load_entries(session_state)
    analysis_history = load_analysis_history()
    coach = build_practice_log_coach_view(
        logs,
        analysis_history=analysis_history,
        all_song_records=ALL_SONG_RECORDS,
        session_minutes=int(session_state.get("ai_session_builder_minutes", 30)),
        highlight_entry=highlight_entry,
    )
    if str(openai_api_key or "").strip():
        coach = maybe_enhance_coach_view_with_openai(
            coach,
            api_key=openai_api_key,
            logs=logs,
            analysis_history=analysis_history,
        )
    session_state["practice_log_coach"] = coach


def _render_practice_session_card(entry: dict) -> None:
    _song_name = str(entry.get("song") or "Untitled session")
    _artist = str(entry.get("artist") or "")
    _instrument = str(entry.get("instrument") or "Any")
    _duration = max(0, _to_int(entry.get("minutes"), 0))
    _mode = str(entry.get("mode") or "Song Work")
    _groove = str(entry.get("groove") or entry.get("genre") or "Auto")
    _rating = max(1, min(10, _to_int(entry.get("rating"), 6)))
    _meter = str(entry.get("time_signature") or "4/4")
    _section_count = max(0, _to_int(entry.get("section_count"), 0))
    _log_date = _parse_log_date(entry.get("date"))
    _date_label = _log_date.strftime("%b %d, %Y") if _log_date else str(entry.get("date") or "Unknown date")
    _progress_pct = int(round((_rating / 10) * 100))
    _notes = str(entry.get("practice") or "").strip()
    _notes = _notes[:230] + "..." if len(_notes) > 230 else _notes

    st.markdown(
        f"""
<div class="ui-log-session-card">
  <div class="ui-log-session-head">
    <div>
      <p class="ui-log-session-song">{html.escape(_song_name)}</p>
      <p class="ui-log-session-artist">{html.escape(_artist) if _artist else "Practice session"}</p>
    </div>
    <span class="ui-log-badge">{html.escape(_date_label)}</span>
  </div>
  <div class="ui-log-badges">
    <span class="ui-log-badge">🎸 {html.escape(_instrument)}</span>
    <span class="ui-log-badge">⏱ {int(_duration)} min</span>
    <span class="ui-log-badge">🎯 {html.escape(_mode)}</span>
    <span class="ui-log-badge">🥁 {html.escape(_groove)}</span>
    <span class="ui-log-badge">🕒 {html.escape(_meter)}</span>
    <span class="ui-log-badge">🧩 {int(_section_count)} sections</span>
    <span class="ui-log-badge">✅ Progress {int(_progress_pct)}%</span>
  </div>
  <p class="ui-log-notes">{html.escape(_notes) if _notes else "No notes added for this session."}</p>
</div>
        """,
        unsafe_allow_html=True,
    )


def _inject_practice_toolkit_styles() -> None:
    st.markdown(
        """
<style>
.st-key-practice_toolkit_panel{
  border:1px solid rgba(148,163,184,.26);border-radius:16px;
  background:linear-gradient(180deg,rgba(255,255,255,.97),rgba(248,250,252,.95));
  box-shadow:0 14px 30px rgba(15,23,42,.08);padding:.85rem .9rem .7rem;margin:.4rem 0 .6rem;
}
.ui-practice-toolkit-head{margin:0 0 .5rem;}
.ui-practice-toolkit-title{margin:0;font-size:1rem;font-weight:850;color:#0f172a;}
.ui-practice-toolkit-sub{margin:.18rem 0 0;font-size:.82rem;color:#64748b;}
.st-key-practice_toolkit_panel .st-key-practice_send_to_backing .stButton > button{
  min-height:2.3rem;padding:.3rem .9rem;font-weight:800;border-radius:10px;
}
.ui-practice-tool-actions{display:flex;flex-wrap:wrap;gap:.35rem;margin:.45rem 0 .2rem;}
.ui-practice-tool-action-chip{
  border:1px solid rgba(148,163,184,.28);border-radius:999px;padding:.22rem .52rem;
  background:#f8fafc;color:#1e293b;font-size:.74rem;font-weight:700;
}
.ui-practice-guidance-card{
  border:1px solid rgba(59,130,246,.22);border-radius:12px;padding:.58rem .68rem;
  background:linear-gradient(145deg,rgba(219,234,254,.58),rgba(224,242,254,.46));
  color:#0f172a;font-size:.8rem;margin:.42rem 0 .15rem;
}
.st-key-practice_tool_tuner,.st-key-practice_tool_metronome,.st-key-practice_tool_chart,.st-key-practice_tool_coach{
  border:1px solid rgba(148,163,184,.24);border-radius:13px;background:rgba(255,255,255,.92);
  padding:.52rem .65rem .28rem;margin:.42rem 0;
}
.st-key-practice_control_panel .ui-practice-focus-title{margin:.1rem 0 .35rem;}
.st-key-practice_control_panel .ui-badge-row{margin:.25rem 0 .35rem!important;}
.ui-practice-focus-title{margin:0;color:#0f172a;font-size:.94rem;font-weight:820;}
.ui-practice-focus-sub{margin:.15rem 0 .45rem;color:#64748b;font-size:.78rem;}
.ui-practice-focus-transition{
  border:1px dashed rgba(148,163,184,.36);border-radius:10px;background:#f8fafc;
  padding:.45rem .55rem;color:#334155;font-size:.78rem;margin:.4rem 0 .3rem;
}
.ui-practice-focus-transition strong{color:#0f172a;}
.ui-practice-tool-title{margin:0;color:#0f172a;font-size:.9rem;font-weight:800;}
.ui-practice-tool-sub{margin:.14rem 0 .4rem;color:#64748b;font-size:.78rem;}
.st-key-practice_tool_tuner [data-testid="stExpander"], .st-key-practice_tool_metronome [data-testid="stExpander"], .st-key-practice_tool_chart [data-testid="stExpander"], .st-key-practice_tool_coach [data-testid="stExpander"]{
  border:none;background:transparent;
}
.ui-section-jump{
  border:1px solid rgba(148,163,184,.28)!important;border-radius:14px!important;
  background:linear-gradient(180deg,#fff,#f8fafc)!important;box-shadow:0 8px 24px rgba(15,23,42,.07)!important;
  padding:.56rem .65rem!important;margin:0 0 .52rem 0!important;position:static!important;top:auto!important;
}
.ui-section-jump [data-testid="stRadio"] > div{
  gap:.35rem!important;flex-wrap:wrap!important;
}
.ui-section-jump [data-testid="stRadio"] label{
  border:1px solid rgba(148,163,184,.32)!important;border-radius:999px!important;
  padding:.24rem .55rem!important;background:#fff!important;
}
.ui-section-jump [data-testid="stRadio"] label:has(input:checked){
  border-color:rgba(59,130,246,.55)!important;background:linear-gradient(140deg,rgba(59,130,246,.14),rgba(14,165,233,.1))!important;
}
body[data-practice-setup-ui] [data-testid="stExpander"]{
  border:1px solid rgba(148,163,184,.24);border-radius:12px;background:rgba(255,255,255,.94);
  box-shadow:0 6px 16px rgba(15,23,42,.04);margin:.38rem 0;
}
body[data-practice-setup-ui] [data-testid="stExpander"] summary{
  font-weight:760;color:#0f172a;
}
.ui-active-song-meta-row{margin:.35rem 0 .5rem;font-size:.8rem;color:#475569;line-height:1.45;}
.ui-practice-tools-kicker{margin:.55rem 0 .25rem;font-size:.78rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:#64748b;}
.st-key-practice_control_panel [data-baseweb="tab-list"]{gap:.25rem;margin-bottom:.35rem;}
.st-key-practice_control_panel [data-baseweb="tab"]{font-size:.82rem;font-weight:700;padding:.35rem .55rem;}
body[data-practice-setup-ui] [data-testid="stTabs"] [data-testid="stVerticalBlock"]{
  gap:.35rem!important;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def make_count_in_click(*, bpm, beats, sr=44100):

    beat_dur = 60 / bpm
    total = int(np.ceil(sr * beat_dur * beats))
    y = np.zeros(total)

    def tick(t0, vol=0.35):

        dur = min(0.06, beat_dur * 0.25)
        t = np.linspace(0, dur, int(sr * dur), False)
        sig = np.sin(2 * np.pi * 880 * t) * vol
        env = np.linspace(1, 0.01, len(sig))
        sig = sig * env
        s0 = int(t0 * sr)
        e = min(total, s0 + len(sig))
        y[s0:e] += sig[: e - s0]

    for b in range(beats):
        tick(b * beat_dur)

    return y


def _load_audio_mono_bytes(audio_bytes, filename, sr):

    suffix = "." + filename.split(".")[-1].lower() if "." in filename else ".wav"

    if librosa is None:

        try:

            buf = io.BytesIO(audio_bytes)

            with wave.open(buf, "rb") as wf:

                n = wf.getnframes()
                ch = wf.getnchannels()
                raw = wf.readframes(n)
                sw = wf.getsampwidth()
                rate = wf.getframerate()

            if sw != 2:
                raise ValueError("Only 16-bit WAV supported without librosa.")

            x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32767.0

            if ch == 2:
                x = x.reshape(-1, 2).mean(axis=1)

            if rate != sr and rate > 0:

                x = np.interp(
                    np.linspace(0, len(x) - 1, int(len(x) * sr / rate)),
                    np.arange(len(x)),
                    x,
                )

            return x

        except Exception as exc:

            raise RuntimeError(
                "Loading this format needs librosa. Install librosa and soundfile, "
                f"or use WAV. ({exc})"
            ) from exc

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:

        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:

        y, _ = librosa.load(tmp_path, sr=sr, mono=True)

        return y

    finally:

        Path(tmp_path).unlink(missing_ok=True)


def mix_multitrack(backing_y, track_items, sr=44100):

    segs = []

    max_len = 0

    if backing_y is not None:

        max_len = len(backing_y)

    solo_active = any(bool(item.get("solo")) for item in track_items)

    for item in track_items:

        if item.get("mute"):
            continue
        if solo_active and not item.get("solo"):
            continue

        y = _load_audio_mono_bytes(
            item["audio_bytes"],
            item["filename"],
            sr,
        )

        y = y * float(item.get("volume", 1.0))

        delay = float(item.get("delay", 0.0))

        ds = int(delay * sr)

        if ds > 0:

            y = np.concatenate([np.zeros(ds, dtype=y.dtype), y])

        elif ds < 0:

            y = y[-ds:]

        segs.append(y)

        max_len = max(max_len, len(y))

    mix = np.zeros(max_len, dtype=np.float64)

    if backing_y is not None:

        mix[: len(backing_y)] += backing_y.astype(np.float64)

    for y in segs:

        mix[: len(y)] += y.astype(np.float64)

    peak = np.max(np.abs(mix)) + 1e-9

    mix = (mix / peak * 0.95).astype(np.float32)

    return mix




def ensure_multitrack_track_controls(session_state, track_names=None):
    try:
        from multitrack_mixer_state import ensure_multitrack_track_controls as _ensure

        return _ensure(session_state)
    except ImportError:
        controls = session_state.setdefault("mt_track_controls", {})
        names = track_names or []
        for name in names:
            controls.setdefault(
                name,
                {"volume": 1.0, "mute": False, "solo": False, "delay": 0.0},
            )
        return controls


def multitrack_studio_track_payloads(track_items, controls):
    payloads = []
    for item in track_items:
        name = item["name"]
        slot = str(item.get("slot") or name)
        track_id = "".join(ch if ch.isalnum() else "_" for ch in name.lower()).strip("_") or "track"
        ctrl = controls.get(slot) if isinstance(controls.get(slot), dict) else controls.get(name, {})
        filename = (item.get("filename") or "").lower()
        if filename.endswith(".mp3"):
            mime = "audio/mpeg"
        elif filename.endswith(".ogg"):
            mime = "audio/ogg"
        else:
            mime = "audio/wav"
        b64 = base64.b64encode(item["audio_bytes"]).decode("ascii")
        payloads.append(
            {
                "id": track_id,
                "name": name,
                "b64": f"data:{mime};base64,{b64}",
                "volume": float(ctrl.get("volume", item.get("volume", 1.0))),
                "mute": bool(ctrl.get("mute", item.get("mute", False))),
                "solo": bool(ctrl.get("solo", item.get("solo", False))),
                "delay": float(ctrl.get("delay", item.get("delay", 0.0))),
            }
        )
    return payloads


def multitrack_monitor_backing_bytes(
    sections,
    selected_section_names,
    *,
    bpm,
    loops,
    style,
    level,
    time_signature: str = "4/4",
):
    events = chord_events_for_selected_sections(sections, selected_section_names)
    if not events:
        return None, events
    backing_y = backing_bytes_to_float(
        events,
        bpm=bpm,
        style=style,
        level=level,
        time_signature=time_signature,
    )
    if loops > 1:
        backing_y = np.tile(backing_y, int(loops))
    return wav_bytes_from_float(backing_y), events


def _render_multitrack_session_setup_panel(
    *,
    mt_sec_names: list[str],
    mt_time_sig: str,
    song_data: dict | None,
    song_title: str,
    original_key: str,
    practice_key: str,
    setup_header_fn,
    context_strip_fn,
    section_open_fn,
    section_close_fn,
    field_label_fn,
) -> tuple[
    int,
    int,
    str,
    str,
    list[str],
    list,
    float,
    int,
    str,
]:
    """Step 1 — session setup card. Returns session control values for downstream steps."""
    setup_header_fn(st)
    _mt_bpm_default = int(st.session_state.get("multitrack_bpm") or st.session_state.get("bpm", 100))
    _mt_groove_default = str(st.session_state.get("mt_groove_style", "Auto") or "Auto")
    _scope_default = st.session_state.get("mt_playback_scope", "Full song")
    _mt_single = str(st.session_state.get("mt_single_section", "") or "")
    _mt_multi = list(st.session_state.get("mt_multi_sections") or [])
    _scope_preview = (
        "free layering"
        if _scope_default == "Free layering (no backing)"
        else (
            "full song"
            if _scope_default == "Full song"
            else (
                _mt_single
                if _scope_default == "Single section (verse, chorus, solo, …)"
                else (" + ".join(_mt_multi) if _mt_multi else "sections")
            )
        )
    )
    context_strip_fn(
        st,
        song_title=song_title,
        original_key=original_key,
        practice_key=practice_key,
        bpm=_mt_bpm_default,
        meter=mt_time_sig,
        groove=_mt_groove_default,
        scope_label=_scope_preview,
    )
    section_open_fn(st, "Song / project", icon="🎵")
    mt_scope = st.radio(
        "Loop / record range",
        [
            "Full song",
            "Single section (verse, chorus, solo, …)",
            "Multiple sections",
            "Free layering (no backing)",
        ],
        horizontal=True,
        key="mt_playback_scope",
        label_visibility="collapsed",
    )
    _free_layering = mt_scope == "Free layering (no backing)"
    try:
        from multitrack_session_persistence import apply_multitrack_free_layering_guard

        apply_multitrack_free_layering_guard(st.session_state)
    except ImportError:
        if _free_layering:
            st.session_state["include_backing_mix"] = False
            st.session_state["mt_use_backing_monitor"] = False
            st.session_state["mt_loop_backing"] = False
    if _free_layering:
        st.info(
            "Free Layering mode records layers without a generated backing track. "
            "Backing, section-repeat, and export-with-backing controls are disabled in Step 3. "
            "You can still record layers and use the click/metronome."
        )
    mt_selected_sections: list[str] = []
    if mt_scope == "Single section (verse, chorus, solo, …)" and mt_sec_names:
        field_label_fn(st, "Section")
        mt_selected_sections = [
            st.selectbox(
                "Section",
                mt_sec_names,
                key="mt_single_section",
                label_visibility="collapsed",
            )
        ]
    elif mt_scope == "Multiple sections" and mt_sec_names:
        mt_default = [
            name
            for name in mt_sec_names
            if any(token in name.lower() for token in ["verse", "chorus", "solo"])
        ] or mt_sec_names[:2]
        field_label_fn(st, "Sections (song order)")
        mt_selected_sections = st.multiselect(
            "Sections (song order)",
            mt_sec_names,
            default=mt_default,
            key="mt_multi_sections",
            label_visibility="collapsed",
        )
    section_close_fn(st)

    section_open_fn(st, "Key / BPM / meter", icon="⏱")
    _kbpm_c1, _kbpm_c2, _kbpm_c3 = st.columns(3, gap="small")
    with _kbpm_c1:
        mt_bpm = st.slider(
            "Session BPM",
            BACKING_BPM_MIN,
            BACKING_BPM_MAX,
            _mt_bpm_default,
            5,
            key="multitrack_bpm",
        )
    with _kbpm_c2:
        mt_loops = st.slider(
            "Section repeats",
            1,
            8,
            2,
            1,
            key="mt_section_loops",
            disabled=_free_layering,
            help="Loops the selected section range while recording.",
        )
    with _kbpm_c3:
        mt_groove = st.selectbox(
            "Groove / feel",
            [
                "Auto",
                "Pop groove",
                "Rock groove",
                "Jazz swing",
                "Bossa nova",
                "Funk groove",
                "Ballad",
            ],
            key="mt_groove_style",
            disabled=_free_layering,
        )
    section_close_fn(st)

    section_open_fn(st, "Count-in", icon="🎙")
    count_in_label = st.selectbox(
        "Count-in",
        ["None", "1 bar", "2 bars"],
        index=1,
        key="mt_count_in_bars",
        help="Bars of click before playback starts.",
    )
    section_close_fn(st)

    mt_count_in_bars = {"None": 0, "1 bar": 1, "2 bars": 2}[count_in_label]
    mt_scope_label = (
        "free layering"
        if _free_layering
        else ("full song" if not mt_selected_sections else " + ".join(mt_selected_sections))
    )
    mt_events = (
        chord_events_for_selected_sections(
            sections, mt_selected_sections, song_data=song_data
        )
        if not _free_layering
        else []
    )
    mt_resolved_groove = infer_groove_style(song_data, mt_groove)
    mt_bar_duration = meter_timing(mt_bpm, mt_time_sig).bar_sec
    mt_backing_duration = len(mt_events) * mt_bar_duration * max(1, mt_loops)

    _prep_info, _prep_btn = st.columns([2.1, 1], gap="small")
    with _prep_info:
        if not _free_layering and not mt_events:
            st.warning("Choose at least one section (or use Free layering).")
        elif not _free_layering:
            st.markdown(
                f'<p class="ui-mt-target-line">Target: <strong>{html.escape(mt_scope_label)}</strong> · '
                f"{html.escape(mt_time_sig)} @ <strong>{int(mt_bpm)}</strong> BPM · "
                f"{len(mt_events)} bars × {mt_loops} ≈ <strong>{mt_backing_duration:.1f}s</strong></p>",
                unsafe_allow_html=True,
            )
    with _prep_btn:
        _prep_clicked = st.button(
            "Prepare backing",
            key="mt_prepare_backing",
            type="primary",
            use_container_width=True,
            disabled=_free_layering or not mt_events,
        )
    st.caption(
        "Prepare Backing uses only the selected sections in song order, repeated by Section repeats "
        "(e.g. Verse + Chorus × 2 → Verse → Chorus → Verse → Chorus). "
        "If a project is loaded from Project Library, Prepare Backing replaces that project's monitor backing. "
        "Save to History to keep a separate version or sync across devices."
    )
    if _prep_clicked:
        practice_level = str(st.session_state.get("level") or "Intermediate")
        monitor_wav, _ = multitrack_monitor_backing_bytes(
            sections,
            mt_selected_sections,
            bpm=mt_bpm,
            loops=mt_loops,
            style=mt_resolved_groove,
            level=practice_level,
            time_signature=mt_time_sig,
        )
        st.session_state.mt_backing_scope = mt_scope_label
        st.session_state.mt_backing_duration = mt_backing_duration
        try:
            from media_multitrack_catalog import persist_prepared_multitrack_backing

            ok, msg = persist_prepared_multitrack_backing(
                st.session_state,
                monitor_wav,
                st=st,
                scope_label=mt_scope_label,
            )
            if ok and msg == "updated_project":
                st.success("Monitor backing ready — updated the loaded project's backing.")
            elif ok:
                st.success("Monitor backing ready — save the project to sync backing across devices.")
            else:
                st.session_state.multitrack_backing_music_wav = monitor_wav
                st.warning("Monitor backing ready locally — catalog update failed.")
        except ImportError:
            st.session_state.multitrack_backing_music_wav = monitor_wav
            st.success("Monitor backing ready — use Step 3 transport while recording.")
        try:
            from studio_page_persistence import flush_current_page_snapshot

            flush_current_page_snapshot(st.session_state)
        except Exception:
            pass

    return (
        mt_bpm,
        mt_loops,
        mt_groove,
        mt_resolved_groove,
        mt_selected_sections,
        mt_events,
        mt_backing_duration,
        mt_count_in_bars,
        mt_scope_label,
    )


def multitrack_studio_html(
    *,
    backing_b64,
    tracks,
    bpm,
    beats_per_bar,
    count_in_bars,
    metronome_during_playback,
    loop_backing,
    backing_monitor_enabled,
    backing_monitor_volume,
    scope_label,
    time_signature="4/4",
    backing_duration_sec=0,
):
    tracks_json = json.dumps(tracks)
    bar_duration = meter_timing(bpm, time_signature).bar_sec
    config = json.dumps({
        "bpm": bpm,
        "beatsPerBar": beats_per_bar,
        "barDuration": bar_duration,
        "countInBars": count_in_bars,
        "metronomeDuringPlayback": metronome_during_playback,
        "loopBacking": loop_backing,
        "backingMonitorEnabled": backing_monitor_enabled,
        "backingMonitorVolume": backing_monitor_volume,
        "scopeLabel": scope_label,
        "hasBacking": bool(backing_b64),
        "backingDurationSec": backing_duration_sec,
    })
    backing_attr = (
        f'src="data:audio/wav;base64,{backing_b64}"'
        if backing_b64
        else ""
    )
    return f"""
<div class="mt-studio" data-mt-transport-ui="2026-05-28-multitrack-v1">
  <style>
    .mt-studio {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif; color: #0f172a; }}
    .mt-toolbar {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-bottom:12px; padding:10px; border-radius:12px; border:1px solid rgba(245,158,11,0.28); background:linear-gradient(180deg,#fffbeb,#fff); }}
    .mt-toolbar button {{ padding:9px 16px; border-radius:10px; border:1px solid #fcd34d; background:#fff; cursor:pointer; font-weight:800; font-size:0.82rem; box-shadow:0 1px 4px rgba(15,23,42,0.06); }}
    .mt-toolbar button:hover {{ filter:brightness(0.98); transform:translateY(-1px); }}
    .mt-toolbar button.primary {{ background:linear-gradient(135deg,#f59e0b,#ea580c); color:#fff; border-color:#c2410c; box-shadow:0 4px 14px rgba(234,88,12,0.28); }}
    .mt-status {{ border:1px solid rgba(245,158,11,0.35); border-radius:14px; padding:12px 14px; background:linear-gradient(180deg,#fffbeb 0%,#ffffff 100%); margin-bottom:12px; box-shadow:0 2px 10px rgba(217,119,6,0.08); }}
    .mt-status strong {{ color:#b45309; letter-spacing:-0.01em; }}
    .mt-timeline {{ height:12px; background:#e2e8f0; border-radius:999px; overflow:hidden; margin:10px 0 14px 0; border:1px solid #cbd5e1; }}
    .mt-cursor {{ height:100%; width:0%; background:linear-gradient(90deg,#fbbf24,#f59e0b,#ea580c); transition: width 0.05s linear; box-shadow:0 0 8px rgba(245,158,11,0.45); }}
    .mt-track-list {{ display:grid; gap:10px; }}
    .mt-track-row {{ border:1px solid #e2e8f0; border-radius:12px; padding:12px; background:#fff; display:grid; grid-template-columns: 1.2fr 1fr 1fr 1fr; gap:10px; align-items:center; box-shadow:0 1px 6px rgba(15,23,42,0.05); }}
    .mt-track-row.muted {{ opacity:0.42; }}
    .mt-track-row.soloed {{ outline:2px solid #f59e0b; background:#fffbeb; }}
    .mt-track-row input[disabled] {{ opacity:0.85; cursor:not-allowed; }}
    .mt-track-row .mt-readonly {{ font-size:0.72rem; color:#94a3b8; font-weight:600; }}
    .mt-help {{ color:#64748b; font-size:0.8rem; margin-top:8px; line-height:1.45; }}
    .mt-beat {{ font-variant-numeric: tabular-nums; font-weight:800; color:#b45309; }}
    .mt-transport-readout {{ font-size:0.84rem; font-weight:700; color:#475569; margin-bottom:6px; }}
    .mt-toolbar label {{ font-size:0.78rem; font-weight:700; color:#475569; display:inline-flex; align-items:center; gap:4px; }}
  </style>

  <audio id="mt-backing" preload="auto" {backing_attr}></audio>

  <div class="mt-status">
    <strong>Transport</strong> — {html.escape(scope_label)} @ {bpm} BPM ({html.escape(time_signature)})
    <div class="mt-help" id="mt-playback-label">Ready. Monitor backing plays in headphones only — it is not baked into your recorded layers.</div>
  </div>

  <div class="mt-toolbar">
    <button class="primary" id="mt-play">▶ Play with count-in</button>
    <button id="mt-stop">■ Stop</button>
  </div>

  <div class="mt-transport-readout">Position: <span class="mt-beat" id="mt-time">0.0s</span> · Bar <span class="mt-beat" id="mt-bar">1</span> · Beat <span class="mt-beat" id="mt-beat">1</span></div>
  <div class="mt-timeline"><div class="mt-cursor" id="mt-cursor"></div></div>

  <div class="mt-track-list" id="mt-track-list"></div>
  <div class="mt-help">Read-only preview from Step 2. Edit volume, mute, and solo in Layer controls above.</div>

  <script>
    const cfg = {config};
    const tracks = {tracks_json};
    const backingEl = document.getElementById("mt-backing");
    const listEl = document.getElementById("mt-track-list");
    const playBtn = document.getElementById("mt-play");
    const stopBtn = document.getElementById("mt-stop");
    const timeEl = document.getElementById("mt-time");
    const barEl = document.getElementById("mt-bar");
    const beatEl = document.getElementById("mt-beat");
    const cursorEl = document.getElementById("mt-cursor");
    const labelEl = document.getElementById("mt-playback-label");

    let audioCtx = null;
    let startedAt = 0;
    let rafId = null;
    let metroTimer = null;
    let trackNodes = [];
    let backingGain = null;
    let masterGain = null;
    let sessionDuration = 8;

    function barDuration() {{ return cfg.barDuration; }}
    function beatDuration() {{ return 60 / cfg.bpm; }}

    function renderTracks() {{
      listEl.innerHTML = "";
      tracks.forEach((track) => {{
        const row = document.createElement("div");
        row.className = "mt-track-row";
        row.dataset.trackId = track.id;
        row.innerHTML = `
          <div><strong>${{track.name}}</strong><div style="font-size:12px;color:#64748b;">delay ${{track.delay}}s</div></div>
          <label>Vol <input type="range" min="0" max="200" value="${{Math.round((track.volume || 1) * 100)}}" data-vol disabled></label>
          <label><input type="checkbox" data-mute disabled> Mute</label>
          <label><input type="checkbox" data-solo disabled> Solo</label>
          <span class="mt-readonly">Step 2</span>
        `;
        row.querySelector("[data-mute]").checked = !!track.mute;
        row.querySelector("[data-solo]").checked = !!track.solo;
        if (track.mute) row.classList.add("muted");
        if (track.solo) row.classList.add("soloed");
        listEl.appendChild(row);
      }});
    }}

    function trackStateFromUI() {{
      return Array.from(listEl.querySelectorAll(".mt-track-row")).map((row) => {{
        const id = row.dataset.trackId;
        const meta = tracks.find((t) => t.id === id) || {{}};
        return {{
          id,
          mute: !!meta.mute,
          solo: !!meta.solo,
          volume: Number(meta.volume || 1),
          delay: Number(meta.delay || 0),
        }};
      }});
    }}

    function audibleTracks(state) {{
      const soloed = state.filter((t) => t.solo);
      if (soloed.length) return state.filter((t) => t.solo && !t.mute);
      return state.filter((t) => !t.mute);
    }}

    async function decodeTrack(track) {{
      const res = await fetch(track.b64);
      const buf = await res.arrayBuffer();
      return await audioCtx.decodeAudioData(buf);
    }}

    function playClick(when, accent) {{
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.frequency.value = accent ? 1180 : 760;
      gain.gain.setValueAtTime(accent ? 0.35 : 0.18, when);
      gain.gain.exponentialRampToValueAtTime(0.001, when + 0.07);
      osc.connect(gain);
      gain.connect(masterGain);
      osc.start(when);
      osc.stop(when + 0.08);
    }}

    function scheduleCountIn(startTime) {{
      const beats = Math.max(0, cfg.countInBars) * cfg.beatsPerBar;
      for (let i = 0; i < beats; i++) {{
        playClick(startTime + i * beatDuration(), i % cfg.beatsPerBar === 0);
      }}
      return startTime + beats * beatDuration();
    }}

    function stopAll() {{
      if (rafId) cancelAnimationFrame(rafId);
      if (metroTimer) clearInterval(metroTimer);
      rafId = null;
      metroTimer = null;
      trackNodes.forEach((node) => {{
        try {{ node.source.stop(); }} catch (e) {{}}
      }});
      trackNodes = [];
      if (audioCtx) audioCtx.close();
      audioCtx = null;
      cursorEl.style.width = "0%";
      timeEl.textContent = "0.0s";
      labelEl.textContent = "Stopped.";
    }}

    function updateTransport() {{
      if (!audioCtx) return;
      const t = Math.max(0, audioCtx.currentTime - startedAt);
      const bd = barDuration();
      const barNum = Math.floor(t / bd) + 1;
      const beatNum = Math.floor((t % bd) / beatDuration()) + 1;
      timeEl.textContent = `${{t.toFixed(1)}}s`;
      barEl.textContent = String(barNum);
      beatEl.textContent = String(beatNum);
      const pct = sessionDuration > 0 ? Math.min(100, (t / sessionDuration) * 100) : 0;
      cursorEl.style.width = `${{pct}}%`;
      rafId = requestAnimationFrame(updateTransport);
    }}

    async function playSession() {{
      stopAll();
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      masterGain = audioCtx.createGain();
      masterGain.gain.value = 0.95;
      masterGain.connect(audioCtx.destination);

      const state = trackStateFromUI();
      const playTracks = audibleTracks(state);
      const countInStart = audioCtx.currentTime;
      const musicStart = scheduleCountIn(countInStart);
      startedAt = musicStart;

      let maxEnd = musicStart;

      if (cfg.hasBacking && cfg.backingMonitorEnabled && backingEl.src) {{
        const backingBuf = await decodeTrack({{ b64: backingEl.src }});
        const src = audioCtx.createBufferSource();
        src.buffer = backingBuf;
        src.loop = cfg.loopBacking;
        backingGain = audioCtx.createGain();
        backingGain.gain.value = cfg.backingMonitorVolume;
        src.connect(backingGain);
        backingGain.connect(masterGain);
        src.start(musicStart);
        const backingLen = backingBuf.duration * (cfg.loopBacking ? 4 : 1);
        maxEnd = Math.max(maxEnd, musicStart + backingLen);
        trackNodes.push({{ source: src }});
      }}

      for (const track of playTracks) {{
        const meta = tracks.find((t) => t.id === track.id);
        if (!meta || !meta.b64) continue;
        const buf = await decodeTrack(meta);
        const src = audioCtx.createBufferSource();
        src.buffer = buf;
        const gain = audioCtx.createGain();
        gain.gain.value = track.volume;
        src.connect(gain);
        gain.connect(masterGain);
        const when = musicStart + Math.max(0, track.delay);
        src.start(when);
        maxEnd = Math.max(maxEnd, when + buf.duration);
        trackNodes.push({{ source: src }});
      }}

      sessionDuration = Math.max(
        4,
        cfg.backingDurationSec || 0,
        maxEnd - musicStart
      );
      labelEl.textContent = "Playing. Count-in finished — music started on beat 1.";
      updateTransport();

      if (cfg.metronomeDuringPlayback) {{
        let beat = 0;
        metroTimer = setInterval(() => {{
          if (!audioCtx) return;
          beat += 1;
          playClick(audioCtx.currentTime, beat % cfg.beatsPerBar === 1);
        }}, beatDuration() * 1000);
      }}
    }}

    renderTracks();
    playBtn.addEventListener("click", playSession);
    stopBtn.addEventListener("click", stopAll);
  </script>
</div>
"""

def _recording_analysis_context(recording_type: str = "practice") -> dict:
    from recording_analysis import analysis_context_from_app

    return analysis_context_from_app(
        song=song,
        song_data=song_data,
        display_key=chart_key,
        sections=sections_for_practice,
        target_chords=full_song_chords,
        instrument=instrument,
        level=level,
        focus=focus,
        recording_type=recording_type,
    )


def render_recording_analysis_report(result, song, focus):
    """Legacy wrapper — premium dashboard is rendered by the analysis page."""
    from recording_analysis_ui import render_analysis_dashboard

    if not result.get("ok"):
        st.error(result.get("message", "Analysis failed."))
        return
    st.markdown(render_analysis_dashboard(result), unsafe_allow_html=True)


def current_song_context_lab():
    return lab_make_ctx(
        genre=genre,
        song=song,
        song_data=song_data,
        display_key=chart_key,
        chart_key=chart_key,
        musical_key=chart_key,
        concert_key=practice_concert_key,
        original_key=original_key,
        written_key=written_key,
        shape_key=shape_key,
        sections=sections_for_practice,
        instrument=instrument,
        level=level,
        focus=focus,
    )


def chord_quality(ch):
    return lab_chord_quality(ch)


def deep_harmonic_analysis_text(ctx):
    ext = song_data.get("extensions") or {}
    ctx = {
        **ctx,
        "extensions": ext,
        "bpm": int(st.session_state.get("backing_track_bpm", _default_song_bpm)),
    }
    return lab_deep_harmonic(ctx, all_chords_from_sections, lab_chord_quality)


def musical_development_tracker_text():
    return lab_musical_dev(load_logs)


def _developer_mode_enabled() -> bool:
    try:
        from suite_workspace import can_show_developer_tools

        return can_show_developer_tools(st=st)
    except ImportError:
        return bool(st.session_state.get("developer_mode", False))


def _apply_catalog_filter_defaults() -> None:
    """One-time migration: show full library, not trusted-only / single-genre traps."""
    if st.session_state.get("_catalog_defaults_version") == CATALOG_DEFAULTS_VERSION:
        return
    lib = st.session_state.get("chart_library_mode", DEFAULT_CHART_LIBRARY_MODE)
    filt = st.session_state.get("song_picker_chart_status", DEFAULT_CHART_STATUS_FILTER)
    st.session_state["chart_library_mode"] = _normalize_library_mode(lib)
    st.session_state["song_picker_chart_status"] = _normalize_chart_filter(filt)
    st.session_state["song_search_scope"] = "Entire library"
    st.session_state["song_picker_level_filter"] = "Any level"
    st.session_state["_catalog_defaults_version"] = CATALOG_DEFAULTS_VERSION


def _pick_keys_from_records(
    records: list[dict],
    *,
    genre: str | None = None,
) -> list[str]:
    rows = records
    if genre and genre != _ALL_GENRE_FILTER:
        rows = [r for r in rows if r.get("genre") == genre]
    return [
        format_pick_key(r["genre"], f"{r['title']} — {r['artist']}")
        for r in rows
    ]


def _global_quick_songs_for_genre(genre: str) -> list[str]:
    """Legacy helper — prefer _pick_keys_from_records with visible catalog rows."""
    return _pick_keys_from_records(_picker_visible_records(), genre=genre)


def _render_catalog_health_debug(*, in_sidebar: bool = True) -> None:
    """Library diagnostics — intended for the bottom Developer / Library expander."""
    total = len(ALL_SONG_RECORDS)
    visible = len(_picker_visible_records())
    writer = st.sidebar if in_sidebar else st
    writer.caption(f"**Songs loaded:** {total} in catalog")
    writer.caption(f"**Visible songs:** {visible} match current filters")
    writer.caption(f"**Genres:** {len(GENRES)}")
    if CATALOG_LOAD_ERROR:
        writer.error(f"Last catalog load error: {CATALOG_LOAD_ERROR!r}")
    if total < 20:
        writer.warning(
            f"Only **{total}** songs loaded — expected 80+. Check song_catalog/ on deploy."
        )
    elif visible < total:
        writer.info(
            f"Filters hide {total - visible} songs. Enable **Developer Mode** below "
            f"to adjust library scope on **Song Selection**."
        )


def _render_sidebar_developer_library_panel() -> None:
    """Collapsed footer — catalog stats and developer mode (normal users can ignore)."""
    try:
        from suite_workspace import is_developer_workspace

        if not is_developer_workspace(st=st):
            return
    except ImportError:
        pass
    with st.sidebar.expander("Developer / Library Info", expanded=False):
        _render_catalog_health_debug(in_sidebar=False)
        st.checkbox(
            "Developer Mode",
            value=bool(st.session_state.get("developer_mode", False)),
            key="developer_mode",
            help="Shows advanced library filters on Song Selection (hidden for normal users).",
        )
        if st.session_state.get("developer_mode"):
            try:
                from openai_secrets_config import (
                    format_openai_secrets_diagnostics,
                    resolve_openai_api_key,
                )

                _probe = resolve_openai_api_key()[1]
                with st.expander("OpenAI secrets (admin diagnostics)", expanded=False):
                    for _line in format_openai_secrets_diagnostics(_probe):
                        st.caption(_line)
            except Exception as _openai_diag_err:
                st.caption(f"OpenAI diagnostics unavailable: {_openai_diag_err!r}")
        if CATALOG_LOAD_ERROR:
            st.caption(f"Load error: {CATALOG_LOAD_ERROR!r}")


def _fmt_global_pick(opt: str) -> str:
    g, lab = parse_pick_key(opt)
    return f"{lab}  [{g}]"


def _on_global_source_change() -> None:
    mode = st.session_state.get("global_source_mode", "Catalog song")
    if mode == "Custom progression":
        if not is_custom_progression(st.session_state):
            set_custom_source(st.session_state)
            note_active_source_change(st, invalidate_backing=invalidate_backing_cache)
            st.rerun()
    elif is_custom_progression(st.session_state):
        set_catalog_source(st.session_state)
        note_active_source_change(st, invalidate_backing=invalidate_backing_cache)
        st.rerun()


def _on_global_genre_change() -> None:
    g = st.session_state.get("global_quick_genre", _ALL_GENRE_FILTER)
    opts = _pick_keys_from_records(_picker_visible_records(), genre=g)
    if not opts:
        return
    current = st.session_state.get("global_quick_song")
    if current not in opts:
        st.session_state["global_quick_song"] = opts[0]
        set_catalog_source(st.session_state)
        apply_pick_key(st, opts[0], SONG_PICKER_CATALOG, song_library=SONG_LIBRARY)
        note_active_source_change(st, invalidate_backing=invalidate_backing_cache)
        st.rerun()


def _on_global_song_change() -> None:
    set_catalog_source(st.session_state)
    apply_pick_key(
        st,
        st.session_state["global_quick_song"],
        SONG_PICKER_CATALOG,
        song_library=SONG_LIBRARY,
    )
    note_active_source_change(st, invalidate_backing=invalidate_backing_cache)


PENDING_BACKING_SINGLE_SECTION = "_pending_backing_single_section"
PENDING_BACKING_SCOPE = "_pending_backing_scope"
PENDING_BACKING_LOOPS = "_pending_backing_loops"
BACKING_QUICK_SECTION_KEY = "backing_quick_section"
BACKING_AUTOPLAY = "_backing_autoplay"
BACKING_TRANSPORT_STATUS = "backing_transport_status"
BACKING_PLAY_FEEDBACK_KEY = "_backing_play_feedback"


def _prepare_backing_from_practice(focus: str | None) -> None:
    """Carry Practice section focus into Backing Track (pending keys — safe for widgets)."""
    try:
        from backing_source_navigation import (
            BACKING_INTENT_FROM_PRACTICE,
            set_backing_open_intent,
        )

        set_backing_open_intent(st.session_state, BACKING_INTENT_FROM_PRACTICE)
    except ImportError:
        pass
    if practice_is_full_song(focus):
        st.session_state[PENDING_BACKING_SCOPE] = "Full song"
        st.session_state.pop(PENDING_BACKING_SINGLE_SECTION, None)
    else:
        st.session_state[PENDING_BACKING_SCOPE] = "Single section"
        st.session_state[PENDING_BACKING_SINGLE_SECTION] = focus
        st.session_state[PENDING_BACKING_LOOPS] = 4
    st.session_state[BACKING_AUTOPLAY] = True


def _apply_pending_backing_scope(session_state, section_names: list[str]) -> bool:
    """Apply pending scope/section/loops before backing widgets are built."""
    opened_section = False
    pending_scope = session_state.pop(PENDING_BACKING_SCOPE, None)
    if pending_scope in ("Full song", "Single section", "Multiple selected sections"):
        session_state["backing_track_scope"] = pending_scope
        opened_section = pending_scope == "Single section"
    pending_sec = session_state.pop(PENDING_BACKING_SINGLE_SECTION, None)
    if pending_sec and pending_sec in section_names:
        session_state["backing_track_single_section"] = pending_sec
        opened_section = True
    pending_loops = session_state.pop(PENDING_BACKING_LOOPS, None)
    if pending_loops is not None:
        try:
            session_state["backing_track_loops"] = int(pending_loops)
        except (TypeError, ValueError):
            pass
    _prime_backing_quick_section_from_scope(session_state, section_names)
    return opened_section


def _prime_backing_quick_section_from_scope(
    session_state: dict,
    section_names: list[str],
) -> None:
    """Sync quick-section picker from scope — only call before that widget exists."""
    scope = session_state.get("backing_track_scope", "Full song")
    if scope == "Single section":
        sec = session_state.get("backing_track_single_section")
        if sec in section_names:
            session_state[BACKING_QUICK_SECTION_KEY] = sec
            return
    session_state[BACKING_QUICK_SECTION_KEY] = "Full song"


def request_backing_quick_section_change(
    choice: str,
    section_names: list[str],
) -> None:
    """Queue scope/section updates for the next rerun (safe after widgets exist)."""
    if choice == "Full song":
        st.session_state[PENDING_BACKING_SCOPE] = "Full song"
        st.session_state["backing_track_scope"] = "Full song"
        st.session_state.pop(PENDING_BACKING_SINGLE_SECTION, None)
    elif choice in section_names:
        st.session_state[PENDING_BACKING_SCOPE] = "Single section"
        st.session_state[PENDING_BACKING_SINGLE_SECTION] = choice
        st.session_state["backing_track_scope"] = "Single section"
        st.session_state["backing_track_single_section"] = choice
    _on_backing_filter_change()


def request_backing_loops_adjust(delta: int) -> None:
    """Queue loop count change before ``backing_track_loops`` widget is built."""
    try:
        current = int(st.session_state.get("backing_track_loops", 2))
    except (TypeError, ValueError):
        current = 2
    new_loops = max(1, min(10, current + int(delta)))
    st.session_state[PENDING_BACKING_LOOPS] = new_loops
    st.session_state["backing_track_loops"] = new_loops
    _on_backing_filter_change()


def _stop_backing_playback() -> None:
    """Stop follow-along playback without clearing the generated WAV."""
    st.session_state.pop("_backing_play_request", None)
    st.session_state[BACKING_AUTOPLAY] = False
    st.session_state[BACKING_TRANSPORT_STATUS] = "stopped"
    st.session_state["_backing_transport_user_stopped"] = True
    st.session_state[BACKING_PLAY_FEEDBACK_KEY] = "Playback stopped"
    st.session_state["backing_lead_sheet_open"] = False
    st.session_state.pop("playback_start_time", None)
    try:
        from backing_track_state import (
            commit_backing_canonical_blob_only,
            commit_backing_transport_from_session,
        )

        commit_backing_transport_from_session(st.session_state, reason="stop")
        commit_backing_canonical_blob_only(st.session_state, reason="stop")
    except ImportError:
        try:
            from backing_track_state import commit_backing_transport_from_session

            commit_backing_transport_from_session(st.session_state, reason="stop")
        except ImportError:
            pass
    for key in list(st.session_state.keys()):
        if str(key).endswith("::follow_start_time"):
            st.session_state.pop(key, None)
        if str(key).endswith("::follow_manual_index"):
            st.session_state[key] = 0


def _begin_backing_performance_follow_along(
    st: Any,
    *,
    follow_key_prefix: str,
    karaoke_voice: bool,
) -> None:
    """Open follow-along UI, scroll to it, and arm playback + timeline."""
    import time

    st.session_state.pop("_backing_transport_user_stopped", None)
    st.session_state["_backing_play_request"] = True
    st.session_state[BACKING_AUTOPLAY] = True
    st.session_state[BACKING_TRANSPORT_STATUS] = "playing"
    record_backing_timing_event(st.session_state, "play_start")
    st.session_state["playback_start_time"] = time.time()
    try:
        from backing_track_state import commit_backing_transport_from_session

        commit_backing_transport_from_session(st.session_state, reason="play")
    except ImportError:
        pass
    st.session_state[f"{follow_key_prefix}::follow_manual_index"] = 0
    if karaoke_voice:
        st.session_state[BACKING_PLAY_FEEDBACK_KEY] = (
            "Karaoke playback started — open the lead sheet below for lyrics and chord follow."
        )
    else:
        st.session_state[BACKING_PLAY_FEEDBACK_KEY] = (
            "Playback started — use the audio player below. Open the lead sheet below for chord follow."
        )


_PICKER_NAV_ANCHORS: dict[str, str] = {
    "practice": ANCHOR_PRACTICE_COACH,
    "backing": ANCHOR_BACKING_MAIN_CONTROLS,
}


_CATALOG_RECENT_KEY = "catalog_recent_pick_keys"


def _open_chart_editor_on_picker() -> None:
    """Jump to Song Selection chart editor for the active catalog song."""
    open_picker_editor(
        st.session_state,
        "Edit Song Chart",
        enable_chart_editing=True,
    )
    navigate_studio_page(st.session_state, "picker")
    st.rerun()


def _open_lyrics_editor_on_picker() -> None:
    """Jump to Song Selection lyrics & cues editor."""
    open_picker_editor(st.session_state, "Lyrics & Cues")
    navigate_studio_page(st.session_state, "picker")
    st.rerun()


def _push_recent_pick_key(session_state, pick_key: str) -> None:
    """Keep the last few catalog picks for quick-switch chips on Song Selection."""
    if not pick_key:
        return
    recent = [k for k in (session_state.get(_CATALOG_RECENT_KEY) or []) if k != pick_key]
    recent.insert(0, pick_key)
    session_state[_CATALOG_RECENT_KEY] = recent[:5]


def _picker_navigate(
    page: str,
    *,
    open_chord_coach: bool = False,
    anchor: str | None = None,
) -> None:
    """Open a studio page for the already-selected catalog song (no re-selection)."""
    if open_chord_coach:
        set_pending_anchor(st.session_state, ANCHOR_CHORD_COACH)
    elif anchor:
        set_pending_anchor(st.session_state, anchor)
    else:
        set_pending_anchor(st.session_state, _PICKER_NAV_ANCHORS.get(page))
    if page == "backing":
        try:
            from backing_source_navigation import BACKING_INTENT_FROM_PRACTICE, set_backing_open_intent

            set_backing_open_intent(st.session_state, BACKING_INTENT_FROM_PRACTICE)
        except ImportError:
            pass
    navigate_studio_page(st.session_state, page)
    if open_chord_coach:
        st.session_state["picker_open_chord_coach"] = True
    st.rerun()


_DEBUG_V2_CHART_TITLES: dict[tuple[str, str], str] = {
    # Temporary debug confirmation that the updated v2 charts are actually
    # loaded. Safe to delete once both pages are visually verified.
    ("Don't Stop Believin'", "Journey"): "v2 chart - 10 sections / 239 bars / E major / arena-rock pacing",
    ("Shallow", "Lady Gaga / Bradley Cooper"): "v2 chart - 10 sections / 173 bars / G major / cinematic ballad pacing",
}


def _render_backing_defaults_verification_pill(
    *,
    sync_id: str,
    song_card_bpm: int,
    applied_bpm: int,
    song_card_groove: str,
    applied_groove: str,
    song_card_meter: str,
    applied_meter: str,
    meter_override: bool,
    did_reset: bool,
) -> None:
    """Temporary debug pill - verifies song-card defaults match playback engine."""
    if not _developer_mode_enabled():
        return
    bpm_match = int(song_card_bpm) == int(applied_bpm)
    groove_match = (
        normalize_groove_label(song_card_groove)
        == normalize_groove_label(applied_groove)
    )
    meter_match = str(song_card_meter) == str(applied_meter)
    all_match = bpm_match and groove_match and meter_match and not meter_override
    color = "#15803d" if all_match else "#b45309"
    bg = "#dcfce7" if all_match else "#fef3c7"
    status_icon = "\u2714" if all_match else "\u26a0"
    status_text = (
        "Song defaults active"
        if all_match
        else (
            "User override active"
            if meter_override or not (bpm_match and groove_match and meter_match)
            else "Defaults active"
        )
    )
    reset_hint = " - just reset to song defaults" if did_reset else ""
    pill_html = (
        f'<div style="margin:8px 0 12px 0;padding:8px 14px;'
        f'background:{bg};color:{color};border-radius:10px;'
        'font-size:0.85rem;font-weight:600;'
        f'box-shadow:0 1px 4px {color}22;'
        'display:flex;flex-wrap:wrap;gap:0.6rem;align-items:center;">'
        f'<span style="font-size:0.95rem;">{status_icon}</span>'
        f'<span>{html.escape(status_text)}{html.escape(reset_hint)}</span>'
        '<span style="opacity:0.65;font-weight:500;">|</span>'
        f'<span>BPM <strong>{int(applied_bpm)}</strong>'
        + ("" if bpm_match else f' (card: {int(song_card_bpm)})')
        + '</span>'
        '<span style="opacity:0.65;font-weight:500;">|</span>'
        f'<span>Groove <strong>{html.escape(str(applied_groove))}</strong>'
        + ("" if groove_match else f' (card: {html.escape(str(song_card_groove))})')
        + '</span>'
        '<span style="opacity:0.65;font-weight:500;">|</span>'
        f'<span>Meter <strong>{html.escape(str(applied_meter))}</strong>'
        + ("" if meter_match else f' (card: {html.escape(str(song_card_meter))})')
        + ("  user override" if meter_override else "")
        + '</span>'
        '</div>'
    )
    st.markdown(pill_html, unsafe_allow_html=True)


def _render_v2_chart_debug_pill(rec: dict) -> None:
    if not _developer_mode_enabled():
        return
    title = str(rec.get("title") or "")
    artist = str(rec.get("artist") or "")
    label = _DEBUG_V2_CHART_TITLES.get((title, artist))
    if not label:
        return
    section_count = len((rec.get("section_order") or list((rec.get("sections") or {}).keys())))
    sections = rec.get("sections") or {}
    bar_count = sum(len(v) for v in sections.values())
    pill_html = (
        '<div style="margin:6px 0 14px 0;padding:8px 14px;'
        'background:linear-gradient(135deg,#0ea5e9 0%,#6366f1 100%);'
        'color:white;border-radius:10px;font-size:0.9rem;font-weight:600;'
        'box-shadow:0 2px 8px rgba(99,102,241,0.35);">'
        f'Using updated <span style="background:rgba(255,255,255,0.22);'
        'padding:2px 8px;border-radius:6px;margin:0 4px;">'
        f'{html.escape(title)}</span> {html.escape(label)} '
        f'<span style="opacity:0.85;font-weight:500;">(live: {section_count} sections, {bar_count} bars)</span>'
        '</div>'
    )
    st.markdown(pill_html, unsafe_allow_html=True)


def _active_song_key_pair(rec: dict | None = None) -> tuple[str, str]:
    """Original key and Practice / Concert key for the Active Song card."""
    ctx = resolve_active_musical_key(
        st.session_state,
        rec=rec,
        surface="song_card",
    )
    return ctx.original_key, ctx.practice_concert_key


def _render_active_song_card(rec: dict, *, show_key_row: bool = True) -> None:
    """Rich active-song summary with navigation shortcuts.

    Designed to **never render blank fields** on the active-song card.
    Every value reaches the markdown layer with a sensible fallback so
    a missing extension, partial chart, or upstream exception cannot
    blank out Levels / Sections / Instruments / Practice Focus.
    """
    level = st.session_state.get("level", "Intermediate")
    active_instrument = str(st.session_state.get("instrument") or "")
    _song_key_ctx = resolve_active_musical_key(
        st.session_state,
        rec=rec,
        instrument=active_instrument,
        surface="song_card",
    )
    _original_key = _song_key_ctx.original_key
    _practice_concert_key = _song_key_ctx.practice_concert_key
    _chart_key = _song_key_ctx.chart_key
    _details_error: Exception | None = None
    try:
        details = active_song_card_details(
            rec,
            level=level,
            instrument=active_instrument,
            practice_key=_practice_concert_key,
            chart_key=_chart_key,
        )
    except Exception as _details_exc:
        _details_error = _details_exc
        # Last-resort fallback - matches the live shape of
        # ``active_song_card_details`` so the template below renders
        # cleanly without dictionary KeyErrors.
        _fallback_meta = song_card_meta(rec)
        _raw_section_keys = list((rec.get("sections") or {}).keys())
        details = {
            **_fallback_meta,
            "time_signature": "4/4",
            "key_display": str(rec.get("key", "C") or "C"),
            "style_label": str(rec.get("genre", "Song") or "Song"),
            "sections": _raw_section_keys,
            "section_summary": (
                " -> ".join(_raw_section_keys[:8])
                if _raw_section_keys
                else "Intro -> Verse -> Chorus -> Outro"
            ),
            "practice_focus": "core chord changes · rhythm feel · clean transitions",
            "chord_concepts": [],
            "practice_goals": [],
            "why_practice": "",
            "visual_emoji": "🎵",
            "visual_gradient": "linear-gradient(145deg,#334155,#64748b)",
            "visual_genre": rec.get("genre", "Song") or "Song",
            "bpm": _fallback_meta.get("bpm") or 100,
        }
    # Ensure every field the template renders has a non-empty value.
    details.setdefault("levels_display", "Beginner / Intermediate / Advanced")
    details.setdefault("difficulty", "All levels")
    details.setdefault("instruments", "Piano, Guitar, Voice")
    details.setdefault("section_summary", "Intro -> Verse -> Chorus -> Outro")
    details.setdefault(
        "practice_focus",
        "core chord changes · rhythm feel · clean transitions",
    )
    for key, blank_fallback in (
        ("levels_display", "Beginner / Intermediate / Advanced"),
        ("difficulty", "All levels"),
        ("instruments", "Piano, Guitar, Voice"),
        ("section_summary", "Intro -> Verse -> Chorus -> Outro"),
        ("practice_focus", "core chord changes · rhythm feel · clean transitions"),
    ):
        if not str(details.get(key) or "").strip():
            details[key] = blank_fallback
    trusted_cls = " trusted" if details.get("trusted") else ""
    concepts = ", ".join(html.escape(c) for c in details.get("chord_concepts") or [])
    goals_html = "".join(
        f"<li>{html.escape(g)}</li>" for g in (details.get("practice_goals") or [])
    )
    try:
        from app_ui import studio_card_modifier_classes as _studio_card_modifier_classes
        modifier_cls = _studio_card_modifier_classes(
            genre=str(rec.get("genre") or details.get("visual_genre") or ""),
            instrument=str(st.session_state.get("instrument") or ""),
        )
    except Exception:
        modifier_cls = ""
    _ext = rec.get("extensions") or {}
    _groove_label = str(_ext.get("default_groove") or details.get("style_label") or rec.get("genre") or "Song")
    _section_keys = list((rec.get("sections") or {}).keys())
    _section_count = len(_section_keys)
    _bar_count = sum(len(v or []) for v in (rec.get("sections") or {}).values())
    _active_pk = st.session_state.get(ACTIVE_CATALOG_PICK_KEY) or ""
    _favorites = set(st.session_state.get(CATALOG_FAVORITES_KEY) or [])
    _is_fav = _active_pk in _favorites
    _fav_icon = "★" if _is_fav else "☆"
    _fav_title = "Remove from favorites" if _is_fav else "Add to favorites"
    _orig_label = _original_key
    _practice_label = _practice_concert_key
    _written_label = ""
    _written_badge_label = "Written Key"
    _charts_badge = ""
    _style_label = str(details.get("style_label") or rec.get("genre") or "Song")
    _source_label = "Catalog Song"
    try:
        from custom_progression_lab import format_key_label as _format_key_label
        from app_ui import studio_song_meta_badges_html as _studio_song_meta_badges_html

        _orig_label = _format_key_label(_original_key)
        _practice_label = _format_key_label(_practice_concert_key)
        if is_custom_progression(st.session_state):
            _source_label = "Custom Progression"
            _cpl_style = ensure_original_structure(
                st.session_state.get(CPL_ACTIVE_KEY) or {}
            ).get("progression_style")
            if _cpl_style:
                _style_label = str(_cpl_style)
        if _song_key_ctx.shape_key:
            _written_label = _format_key_label(_song_key_ctx.shape_key)
            _written_badge_label = "Shape Key"
        elif (
            _song_key_ctx.chart_key_mode == "written"
            and _song_key_ctx.written_key
            and _song_key_ctx.written_key != _practice_concert_key
        ):
            _written_label = _format_key_label(_song_key_ctx.written_key)
        if _chart_key and _chart_key != _practice_concert_key:
            _charts_badge = _format_key_label(_chart_key)
        _badge_html = _studio_song_meta_badges_html(
            display_key=_practice_label if show_key_row else "",
            written_key=_written_label if show_key_row else "",
            written_key_label=_written_badge_label,
            charts_key=_charts_badge,
            bpm=int(details.get("bpm") or 100),
            meter=str(details.get("time_signature") or "4/4"),
            style=_style_label,
            source=_source_label,
        )
    except Exception:
        _badge_html = ""
    _key_row_html = (
        active_song_key_row_html(_orig_label, _practice_label)
        if show_key_row
        else ""
    )
    _meta_row = ""
    _raw_artist = str(details.get("artist") or "").strip()
    if _raw_artist and _raw_artist.lower() not in ("your progression",):
        _artist_display = (
            _raw_artist if _raw_artist.lower().startswith("by ") else f"By {_raw_artist}"
        )
    else:
        _artist_display = ""
    _artist_html = (
        f'<p class="ui-active-song-artist">{html.escape(_artist_display)}</p>'
        if _artist_display
        else ""
    )
    card_html = (
        f'<div class="ui-active-song-card{trusted_cls}{modifier_cls}">'
        f'<div class="ui-active-song-art" style="background:{html.escape(details["visual_gradient"])};">'
        f'{html.escape(details["visual_emoji"])}<small>{html.escape(details["visual_genre"])}</small></div>'
        f'<div class="ui-active-song-body">'
        f'<p class="ui-active-song-kicker">Now loaded for practice</p>'
        f'<p class="ui-active-song-title">{html.escape(details["title"])}</p>'
        f'{_artist_html}'
        f'{_key_row_html}'
        f'{_badge_html}'
        f'{_meta_row}'
        f'<dl class="ui-active-song-facts">'
        f'<dt>Levels</dt><dd>{html.escape(details["levels_display"])}</dd>'
        f'<dt>Level fit</dt><dd>{html.escape(details["difficulty"])}</dd>'
        f'<dt>Instruments</dt><dd>{html.escape(details["instruments"])}</dd>'
        f'<dt>Practice focus</dt><dd>{html.escape(details["practice_focus"])}</dd>'
        f"</dl>"
        + (
            f'<p class="ui-active-song-blurb"><strong>Challenge:</strong> '
            f'{html.escape(str((details.get("coaching") or {}).get("biggest_challenge") or ""))}</p>'
            if str((details.get("coaching") or {}).get("biggest_challenge") or "").strip()
            else ""
        )
        + (
            f'<p class="ui-active-song-blurb"><strong>Harmony:</strong> {concepts}</p>'
            if concepts and not (details.get("coaching") or {})
            else (
                f'<p class="ui-active-song-blurb ui-active-song-blurb-muted"><strong>Harmony:</strong> {concepts}</p>'
                if concepts
                else ""
            )
        )
        + f'<p class="ui-active-song-blurb">{html.escape(str(details.get("why_practice", "")))}</p>'
        + (f'<ul class="ui-active-song-goals">{goals_html}</ul>' if goals_html else "")
        + "</div></div>"
    )
    st.markdown(card_html, unsafe_allow_html=True)
    if _details_error is not None and _developer_mode_enabled():
        st.warning(
            "Developer Mode · active-song card fell back to defaults "
            f"because ``active_song_card_details`` raised "
            f"``{type(_details_error).__name__}: {_details_error}``. "
            "The fields shown above are safe defaults - the underlying "
            "issue is logged here so we don't render blank rows silently."
        )
    _render_v2_chart_debug_pill(rec)
    st.markdown(
        '<div class="ui-chart-edit-cta">'
        '<p class="ui-chart-edit-cta-label">Chord chart</p>'
        '<p class="ui-chart-edit-cta-hint">'
        "Edit Verse, Chorus, Bridge, and other sections bar-by-bar — "
        "saved permanently for this song."
        "</p></div>",
        unsafe_allow_html=True,
    )
    if st.button(
        "Edit Song Chart",
        key="picker_card_edit_chart",
        type="primary",
        use_container_width=True,
        help="Jump to the chord chart editor below (enable editing, change bars, then Save corrected chart).",
    ):
        _open_chart_editor_on_picker()
    st.markdown('<div class="ui-song-card-actions ui-active-song-hub-actions">', unsafe_allow_html=True)
    fav_col, b1, b2, b3, b4 = st.columns([0.55, 1, 1, 1, 1])
    with fav_col:
        if _active_pk and st.button(_fav_icon, key="picker_card_favorite", help=_fav_title):
            toggle_catalog_favorite(st.session_state, _active_pk)
            st.rerun()
    with b1:
        if st.button(nav_icon_button_label("practice"), key="picker_card_practice", use_container_width=True):
            _picker_navigate("practice")
    with b2:
        if st.button(nav_icon_button_label("backing"), key="picker_card_backing", use_container_width=True):
            _picker_navigate("backing")
    with b3:
        if st.button("🎤 Karaoke", key="picker_card_karaoke", use_container_width=True):
            _picker_navigate("backing")
    with b4:
        if st.button("🎸 Chord Coach", key="picker_card_chord_coach", use_container_width=True):
            _picker_navigate("practice", open_chord_coach=True)
    st.markdown("</div>", unsafe_allow_html=True)
    # Karaoke "Add to Setlist" CTA - only visible when the active
    # instrument is Voice / Vocals / Singer. Instrumentalists never see
    # this button. (The button itself also self-gates as a safety net.)
    _active_pick_key = st.session_state.get(ACTIVE_CATALOG_PICK_KEY) or ""
    if _active_pick_key and km.is_voice_mode(st.session_state):
        _karaoke_title = str(rec.get("title", "") or "")
        _karaoke_artist = str(rec.get("artist", "") or "")
        if str(_active_pick_key).startswith("custom::"):
            from songs.music_source import (
                custom_display_artist_for_pick_key,
                custom_display_title_for_pick_key,
            )

            _karaoke_title = custom_display_title_for_pick_key(
                st.session_state,
                _active_pick_key,
                fallback_title=_karaoke_title,
            )
            _karaoke_artist = custom_display_artist_for_pick_key(
                st.session_state,
                _active_pick_key,
                fallback_artist=_karaoke_artist,
            )
        render_add_to_queue_button(
            st,
            pick_key=_active_pick_key,
            title=_karaoke_title,
            artist=_karaoke_artist,
            key_suffix=f"card_{_active_pick_key}",
            use_container_width=True,
        )


def _picker_song_dropdown_label(pick_key: str, *, favorites: set[str] | None = None) -> str:
    """Dropdown label with optional favorite star prefix."""
    genre, title = parse_pick_key(pick_key)
    base = f"{title}  ·  {genre}"
    if favorites and pick_key in favorites:
        return f"★ {base}"
    return base


def _ensure_catalog_favorites_pruned(valid_pick_keys: set[str]) -> None:
    """Drop stale favorite pick keys after catalog changes."""
    raw = list(st.session_state.get(CATALOG_FAVORITES_KEY) or [])
    pruned = prune_catalog_pick_keys(raw, valid_pick_keys)
    if pruned != raw:
        st.session_state[CATALOG_FAVORITES_KEY] = pruned


def _render_active_song_favorites_switch(
    visible_records: list[dict],
    valid_pick_keys: set[str],
    active_pick_key: str,
) -> None:
    """Quick-switch chips for favorited catalog songs."""
    _ensure_catalog_favorites_pruned(valid_pick_keys)
    favorites = [
        k for k in (st.session_state.get(CATALOG_FAVORITES_KEY) or [])
        if k in valid_pick_keys
    ]
    if not favorites:
        return
    st.markdown(
        '<p class="ui-active-song-recent-label">Favorites</p>',
        unsafe_allow_html=True,
    )
    for row_start in range(0, len(favorites), 4):
        chunk = favorites[row_start : row_start + 4]
        cols = st.columns(len(chunk))
        for col, pk in zip(cols, chunk):
            rec = record_for_pick_key(visible_records, pk)
            title = str(rec.get("title", parse_pick_key(pk)[1])) if rec else parse_pick_key(pk)[1]
            label = f"★ {title}" if pk == active_pick_key else title
            with col:
                if st.button(label, key=f"favorite_pick_{pk}", use_container_width=True):
                    st.session_state[PENDING_MATCHING_SONG_DROPDOWN] = pk
                    set_catalog_source(st.session_state)
                    apply_pick_key(st, pk, SONG_PICKER_CATALOG, song_library=SONG_LIBRARY)
                    _push_recent_pick_key(st.session_state, pk)
                    note_active_source_change(st, invalidate_backing=invalidate_backing_cache)
                    st.rerun()


def _render_custom_song_library_selector() -> None:
    """Pick a saved custom song to activate (Custom Progression source)."""
    from custom_progression_lab import list_saved_progression_names
    from custom_song_library import _format_saved_at, progression_row_summary, row_widget_suffix
    from songs.music_source import (
        CUSTOM_RECENT_ACTIVE_NAMES_KEY,
        custom_progression_is_active,
        queue_custom_library_action,
    )

    saved = st.session_state.get(CPL_SAVED_KEY) or {}
    if not isinstance(saved, dict):
        saved = {}
    names = list_saved_progression_names(saved)
    recent = [
        n
        for n in (st.session_state.get(CUSTOM_RECENT_ACTIVE_NAMES_KEY) or [])
        if n in names
    ]
    ordered = recent + [n for n in names if n not in recent]
    active_name = ""
    if custom_progression_is_active(st.session_state):
        active = ensure_original_structure(
            st.session_state.get(CPL_ACTIVE_KEY) or default_active_progression()
        )
        active_name = str(active.get("name") or "").strip()

    st.markdown(
        '<p class="ui-custom-library-label">Custom Songs</p>',
        unsafe_allow_html=True,
    )
    if st.button("New Song", key="custom_lib_new_song", use_container_width=True):
        queue_custom_library_action(st, action="new_song")
        st.rerun()

    if not ordered:
        st.caption("No saved custom songs yet. Build one in Custom Progression Lab, then Save to library.")
        return

    for name in ordered:
        data = saved.get(name) if isinstance(saved.get(name), dict) else {}
        summary = progression_row_summary(data) if data else ""
        saved_at = _format_saved_at(data.get("updated_at") or data.get("created_at"))
        suffix = row_widget_suffix({"payload": {"progression": data}, "item_key": data.get("id") or name})
        row_label = name
        meta_parts = [p for p in (saved_at, summary) if p]
        if meta_parts:
            row_label = f"{name}  ·  {' · '.join(meta_parts)}"
        is_active = name == active_name
        row_cols = st.columns([12, 1])
        with row_cols[0]:
            if is_active:
                st.caption(f"▸ {row_label}")
            elif st.button(row_label, key=f"custom_lib_pick_{suffix}", use_container_width=True):
                queue_custom_library_action(st, name=name, action="activate")
                st.rerun()
        with row_cols[1]:
            if st.button("✕", key=f"custom_lib_del_{suffix}", help="Delete custom song"):
                from custom_progression_lab import delete_progression

                st.session_state[CPL_SAVED_KEY] = delete_progression(dict(saved), name)
                if active_name == name:
                    queue_custom_library_action(st, action="new_song")
                st.rerun()


def _render_last_catalog_song_shortcut(
    *,
    key_prefix: str = "catalog",
) -> None:
    """Browser-back shortcut to the previous catalog song."""
    from songs.music_source import (
        custom_progression_is_active,
        previous_catalog_snapshot,
    )

    if custom_progression_is_active(st.session_state):
        return
    snap = previous_catalog_snapshot(st.session_state)
    if not snap:
        return
    sel = snap.get("selected_song") or {}
    title = str(sel.get("title") or "Catalog song").strip() or "Catalog song"
    artist = str(sel.get("artist") or "").strip()
    song_line = f"{title} \u2014 {artist}" if artist else title
    st.markdown(
        '<div class="ui-last-catalog-shortcut">'
        '<p class="ui-last-catalog-kicker">Load last song</p>'
        "</div>",
        unsafe_allow_html=True,
    )
    if st.button(
        song_line,
        key=f"{key_prefix}_restore_last_catalog",
        use_container_width=True,
        help="Restore the previous catalog song you had selected.",
    ):
        from songs.key_state import invalidate_backing_cache
        from songs.music_source import restore_previous_catalog_song

        restore_previous_catalog_song(
            st,
            song_picker_catalog=SONG_PICKER_CATALOG,
            song_library=SONG_LIBRARY,
            invalidate_backing=invalidate_backing_cache,
        )
        st.rerun()


def _render_active_song_recent_switch(
    visible_records: list[dict],
    pick_options: list[str],
    active_pick_key: str,
) -> None:
    """Quick-switch chips for recently selected catalog songs."""
    recent = [
        k for k in (st.session_state.get(_CATALOG_RECENT_KEY) or [])
        if k in pick_options and k != active_pick_key
    ][:3]
    if not recent:
        return
    st.markdown(
        '<p class="ui-active-song-recent-label">Recently selected</p>',
        unsafe_allow_html=True,
    )
    cols = st.columns(len(recent))
    for col, pk in zip(cols, recent):
        rec = record_for_pick_key(visible_records, pk)
        label = str(rec.get("title", parse_pick_key(pk)[1])) if rec else parse_pick_key(pk)[1]
        with col:
            if st.button(label, key=f"recent_pick_{pk}", use_container_width=True):
                st.session_state[PENDING_MATCHING_SONG_DROPDOWN] = pk
                set_catalog_source(st.session_state)
                apply_pick_key(st, pk, SONG_PICKER_CATALOG, song_library=SONG_LIBRARY)
                _push_recent_pick_key(st.session_state, pk)
                note_active_source_change(st, invalidate_backing=invalidate_backing_cache)
                st.rerun()


def _picker_visible_records() -> list[dict]:
    _apply_catalog_filter_defaults()
    st.session_state.setdefault("chart_library_mode", DEFAULT_CHART_LIBRARY_MODE)
    st.session_state.setdefault("song_picker_chart_status", DEFAULT_CHART_STATUS_FILTER)
    st.session_state.setdefault("song_search_scope", "Entire library")
    st.session_state.setdefault("song_picker_level_filter", "Any level")
    mode = st.session_state.get("chart_library_mode", DEFAULT_CHART_LIBRARY_MODE)
    visible = visible_records_for_mode(ALL_SONG_RECORDS, mode)
    status_filter = st.session_state.get("song_picker_chart_status", DEFAULT_CHART_STATUS_FILTER)
    level_filter = st.session_state.get("song_picker_level_filter", "Any level")
    visible = filter_records_by_chart_status(visible, status_filter)
    visible = filter_records_by_level(visible, level_filter)
    return visible


def _migrate_workspace_genre_filters(available_genres: set[str]) -> list[str]:
    """Migrate legacy single-genre dropdown to multi-select pill state."""
    available = {g for g in available_genres if g}
    if "Jewish Traditional" in available:
        available.discard("Jewish Traditional")
    if WORKSPACE_GENRE_FILTERS_KEY not in st.session_state:
        legacy = st.session_state.get("workspace_genre_filter", _ALL_GENRE_FILTER)
        if legacy == "Jewish Traditional":
            legacy = "Jewish"
        if legacy and legacy != _ALL_GENRE_FILTER and legacy in available:
            st.session_state[WORKSPACE_GENRE_FILTERS_KEY] = [legacy]
        else:
            st.session_state[WORKSPACE_GENRE_FILTERS_KEY] = []
    raw_filters = list(st.session_state.get(WORKSPACE_GENRE_FILTERS_KEY) or [])
    filters: list[str] = []
    for g in raw_filters:
        if g == "Jewish Traditional":
            g = "Jewish"
        if g in available and g not in filters:
            filters.append(g)
    st.session_state[WORKSPACE_GENRE_FILTERS_KEY] = filters
    return filters


def _cpl_to_song_record(active: dict) -> dict[str, Any]:
    """Catalog-shaped row for the Active Song hub when using Custom Progression."""
    from custom_progression_lab import cpl_draft_written_key, sections_to_chord_lists

    title = str(active.get("name") or "My Progression")
    home_key = cpl_draft_written_key(active)
    artist = str(active.get("artist") or "").strip()
    sections = sections_to_chord_lists(active.get("original_sections") or {})
    style = str(active.get("progression_style") or "Custom")
    bpm = int(active.get("bpm") or 100)
    groove = str(active.get("groove_style") or "Auto")
    meter = str(active.get("time_signature") or "4/4")
    return {
        "title": title,
        "artist": artist or "Your progression",
        "genre": "Custom",
        "key": home_key,
        "sections": sections,
        "chart_versions": {
            "Beginner": sections,
            "Intermediate": sections,
            "Advanced": sections,
        },
        "chart_status": "custom",
        "extensions": {
            "default_bpm": bpm,
            "default_groove": groove,
            "time_signature": meter,
            "arrangement_notes": f"Custom progression · {style} feel",
        },
    }


def _apply_picker_catalog_filters(
    visible_song_records: list[dict],
) -> tuple[list[dict], list[str], str]:
    """Return filtered rows, pick keys, and active pick key (strict — no out-of-filter rows)."""
    all_pick_keys = {
        format_pick_key(r["genre"], f"{r['title']} — {r['artist']}")
        for r in visible_song_records
    }
    _ensure_catalog_favorites_pruned(all_pick_keys)
    genres = list(st.session_state.get(WORKSPACE_GENRE_FILTERS_KEY) or [])
    query = str(st.session_state.get("song_search_text") or "")
    filtered = search_records(
        visible_song_records,
        query,
        genres=genres if genres else None,
        limit=max(500, len(ALL_SONG_RECORDS)),
    )
    if st.session_state.get(SONG_PICKER_FAVORITES_ONLY_KEY):
        favorites = set(st.session_state.get(CATALOG_FAVORITES_KEY) or [])
        filtered = [
            r
            for r in filtered
            if format_pick_key(r["genre"], f"{r['title']} — {r['artist']}") in favorites
        ]
    pick_options = [
        format_pick_key(r["genre"], f"{r['title']} — {r['artist']}") for r in filtered
    ]
    if not pick_options:
        return filtered, [], ""

    master_pk = (st.session_state.get("selected_song") or {}).get("pick_key")
    default_pk = master_pk if master_pk in pick_options else pick_options[0]
    if st.session_state.get(ACTIVE_CATALOG_PICK_KEY) not in pick_options:
        if is_custom_progression(st.session_state):
            active_pk = str(st.session_state.get(ACTIVE_CATALOG_PICK_KEY) or "")
            return filtered, pick_options, active_pk
        active_pk = str(st.session_state.get(ACTIVE_CATALOG_PICK_KEY) or default_pk)
        return filtered, pick_options, active_pk
    active_pk = sync_matching_song_dropdown_before_widget(st, pick_options, default_pk, song_picker_catalog=SONG_PICKER_CATALOG)
    return filtered, pick_options, active_pk


def _render_picker_music_source_toggle(*, polished: bool) -> bool:
    """Render catalog vs custom source radio. Returns True when custom is active."""
    if polished:
        st.markdown(
            '<p class="ui-page-nav-label" style="margin-top:0;">Music source</p>',
            unsafe_allow_html=True,
        )
    options = [
        "Song Selection (catalog song)",
        "Use Custom Progression / Create Your Own Song",
    ]
    from songs.music_source import (
        on_song_picker_source_change,
        reconcile_music_picker_source_widget,
        restore_last_catalog_active_song,
        sync_song_picker_source_widget,
    )

    if "song_picker_active_source" not in st.session_state:
        sync_song_picker_source_widget(st.session_state)
    reconcile_music_picker_source_widget(st.session_state)

    def _picker_source_on_change() -> None:
        on_song_picker_source_change(
            st,
            song_picker_catalog=SONG_PICKER_CATALOG,
            song_library=SONG_LIBRARY,
            invalidate_backing=invalidate_backing_cache,
        )

    st.radio(
        "Music source",
        options,
        horizontal=True,
        key="song_picker_active_source",
        label_visibility="collapsed" if polished else "visible",
        on_change=_picker_source_on_change,
    )
    choice = str(st.session_state.get("song_picker_active_source") or "").strip()
    return is_custom_progression(st.session_state) or choice.startswith("Use Custom")


def _render_custom_active_song_hub(*, wrap_section: bool) -> None:
    """Active Song hub for Custom Progression / Create Your Own Song."""
    active = ensure_original_structure(
        st.session_state.get(CPL_ACTIVE_KEY) or default_active_progression()
    )
    rec = _cpl_to_song_record(active)
    level = st.session_state.get("level", "Intermediate")
    try:
        from practice_studio import active_song_card_details as _hub_details_fn

        details = _hub_details_fn(
            rec,
            level=level,
            instrument=str(st.session_state.get("instrument") or ""),
        )
    except Exception:
        details = song_card_meta(rec)
    ext = rec.get("extensions") or {}

    with st.container(key="picker_active_song_hub"):
        render_active_song_hub_open(st, extra_class="source-custom")
        st.caption(
            "This is **your** song — Practice, Backing Track, and charts follow this custom progression."
        )
        _render_custom_song_library_selector()
        _render_active_song_card(rec)
        st.markdown('<div class="ui-song-card-actions ui-active-song-hub-actions">', unsafe_allow_html=True)
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button(nav_icon_button_label("practice"), key="custom_hub_practice", use_container_width=True):
                _picker_navigate("practice")
        with b2:
            if st.button(nav_icon_button_label("backing"), key="custom_hub_backing", use_container_width=True):
                _picker_navigate("backing")
        with b3:
            if st.button(nav_icon_button_label("custom") + " Edit", key="custom_hub_edit", use_container_width=True):
                from songs.music_source import queue_custom_library_action

                queue_custom_library_action(st, action="edit_active")
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        render_active_song_hub_close(st)

    render_cpl_lyrics_editor_panel(
        st,
        active=active,
        cpl_active_key=CPL_ACTIVE_KEY,
    )

    if wrap_section:
        close_control_section()


def _render_genre_filter_pills(available_genres: list[str]) -> None:
    """Multi-select genre pill bar with clear + more-genres expander."""
    from songs.picker_session import genre_filter_widget_key

    selected = set(st.session_state.get(WORKSPACE_GENRE_FILTERS_KEY) or [])
    head_l, head_r = st.columns([3, 1])
    with head_l:
        st.markdown(
            '<p class="ui-song-library-genre-chips-label">Genres — click to toggle</p>',
            unsafe_allow_html=True,
        )
    with head_r:
        st.button(
            "Clear filters",
            key="genre_clear_filters",
            use_container_width=True,
            on_click=request_clear_browse_filters,
            kwargs={"session_state": st.session_state},
        )

    primary = [g for g in _PRIMARY_GENRE_PILLS if g in available_genres]
    extra = sorted(g for g in available_genres if g not in primary)

    def _pill_row(genres: list[str], key_prefix: str) -> None:
        if not genres:
            return
        for row_start in range(0, len(genres), 5):
            chunk = genres[row_start : row_start + 5]
            cols = st.columns(len(chunk))
            for col, genre in zip(cols, chunk):
                with col:
                    is_active = genre in selected
                    genre_key = genre_filter_widget_key(genre)
                    st.button(
                        genre,
                        key=f"{key_prefix}_{genre_key}",
                        use_container_width=True,
                        type="primary" if is_active else "secondary",
                        on_click=toggle_genre_filter,
                        kwargs={"session_state": st.session_state, "genre": genre},
                    )

    _pill_row(primary, "genre_pill")
    if extra:
        with st.expander(f"More genres ({len(extra)})", expanded=False):
            for row_start in range(0, len(extra), 4):
                chunk = extra[row_start : row_start + 4]
                if not chunk:
                    continue
                cols = st.columns(len(chunk))
                for col, genre in zip(cols, chunk):
                    with col:
                        is_active = genre in selected
                        genre_key = genre_filter_widget_key(genre)
                        st.button(
                            genre,
                            key=f"genre_more_{row_start}_{genre_key}",
                            use_container_width=True,
                            type="primary" if is_active else "secondary",
                            on_click=toggle_genre_filter,
                            kwargs={"session_state": st.session_state, "genre": genre},
                        )

    if selected:
        st.markdown(
            f'<p class="ui-genre-filter-active-summary">Showing: '
            f'<strong>{", ".join(sorted(selected))}</strong></p>',
            unsafe_allow_html=True,
        )


def _render_catalog_active_song_hub(
    *,
    active_rec: dict | None,
    pick_options: list[str],
    active_pick_key: str,
    visible_song_records: list[dict],
    on_song_change: Callable[[], None],
    empty_message: str,
) -> None:
    """Featured Active Song hub for catalog picks."""
    with st.container(key="picker_active_song_hub"):
        render_active_song_hub_open(st)
        st.markdown(
            '<p class="ui-active-song-picker-label">Switch active song</p>',
            unsafe_allow_html=True,
        )
        if pick_options:
            _fav_set = set(st.session_state.get(CATALOG_FAVORITES_KEY) or [])
            st.selectbox(
                "Active song",
                pick_options,
                format_func=lambda opt: _picker_song_dropdown_label(opt, favorites=_fav_set),
                key="matching_song_dropdown",
                on_change=on_song_change,
                label_visibility="collapsed",
                help="Filtered by your genre pills, favorites, and search — updates Practice, Backing, and Karaoke.",
            )
        else:
            st.info(empty_message)
        _catalog_pick_keys = {
            format_pick_key(r["genre"], f"{r['title']} — {r['artist']}")
            for r in visible_song_records
        }
        st.markdown('<div class="ui-active-song-recent">', unsafe_allow_html=True)
        if active_rec:
            _render_active_song_card(active_rec)
            yt_title = str(active_rec.get("title", ""))
            yt_artist = str(active_rec.get("artist", ""))
            if yt_title:
                yt_slug, _, _ = _lyrics_cues_session_keys(yt_title, yt_artist)
                render_original_song_video_card(
                    st,
                    song_title=yt_title,
                    artist=yt_artist,
                    song_slug=yt_slug,
                    instrument=st.session_state.get("instrument", ""),
                    expanded=False,
                )
            _render_active_song_favorites_switch(
                visible_song_records,
                _catalog_pick_keys,
                active_pick_key,
            )
        _render_last_catalog_song_shortcut(key_prefix="catalog_hub")
        st.markdown("</div>", unsafe_allow_html=True)
        render_active_song_hub_close(st)


def _render_catalog_song_picker_block(
    *,
    show_source_toggle: bool = True,
    filters_in_expander: bool = False,
    wrap_section: bool = True,
    show_song_cards: bool = False,
) -> None:
    """Song / source controls — used in workspace panel section A."""
    if wrap_section:
        open_control_section(
            "A",
            "Song / Source",
            "Choose what music you are practicing — catalog song or custom progression.",
        )

    # On Song Selection the source toggle lives inside the library
    # panel; other surfaces keep the legacy placement above filters.
    if show_source_toggle and not show_song_cards:
        _picker_source_options = [
            "Song Selection (catalog song)",
            "Use Custom Progression / Create Your Own Song",
        ]
        from songs.music_source import (
            on_song_picker_source_change,
            reconcile_music_picker_source_widget,
            restore_last_catalog_active_song,
            sync_song_picker_source_widget,
        )

        if "song_picker_active_source" not in st.session_state:
            sync_song_picker_source_widget(st.session_state)
        reconcile_music_picker_source_widget(st.session_state)

        def _library_source_on_change() -> None:
            on_song_picker_source_change(
                st,
                song_picker_catalog=SONG_PICKER_CATALOG,
                song_library=SONG_LIBRARY,
                invalidate_backing=invalidate_backing_cache,
            )

        st.radio(
            "Music source",
            _picker_source_options,
                horizontal=True,
            key="song_picker_active_source",
            on_change=_library_source_on_change,
        )
        if is_custom_progression(st.session_state):
            _render_custom_active_song_hub(wrap_section=wrap_section)
            return

    visible_song_records = _picker_visible_records()
    available_genres = sorted({r.get("genre") for r in visible_song_records if r.get("genre")})
    _migrate_workspace_genre_filters(set(available_genres))
    apply_picker_session_resets(st.session_state)

    _library_polished = bool(show_song_cards)
    if _library_polished:
        render_scroll_anchor_marker(st, ANCHOR_CHOOSE_ACTIVE_SONG)
    _library_shell = st.container(key="song_library_panel") if _library_polished else None

    def _on_song_dropdown_change():
        set_catalog_source(st.session_state)
        raw_pick = st.session_state.get("matching_song_dropdown", "")
        resolved_pick = resolve_pick_key(
            raw_pick,
            song_picker_catalog=SONG_PICKER_CATALOG,
            records=visible_song_records,
        )
        if not resolved_pick:
            return
        if resolved_pick != raw_pick:
            st.session_state[PENDING_MATCHING_SONG_DROPDOWN] = resolved_pick
        apply_pick_key(
            st,
            resolved_pick,
            SONG_PICKER_CATALOG,
            song_library=SONG_LIBRARY,
        )
        _push_recent_pick_key(
            st.session_state,
            st.session_state.get(ACTIVE_CATALOG_PICK_KEY) or "",
        )
        note_active_source_change(st, invalidate_backing=invalidate_backing_cache)
        try:
            st.toast("Song updated — chart and backing track follow this selection.", icon="🎵")
        except Exception:
            pass

    if _library_polished and show_source_toggle:
        if _render_picker_music_source_toggle(polished=True):
            _render_custom_active_song_hub(wrap_section=wrap_section)
            return

    filtered, pick_options, active_pick_key = _apply_picker_catalog_filters(
        visible_song_records,
    )

    if _library_polished:
        active_rec = (
            record_for_pick_key(visible_song_records, active_pick_key) if active_pick_key else None
        )
        _render_catalog_active_song_hub(
            active_rec=active_rec,
            pick_options=pick_options,
            active_pick_key=active_pick_key,
            visible_song_records=visible_song_records,
            on_song_change=_on_song_dropdown_change,
            empty_message=(
                "No favorites yet — star a song on the Active Song card, or turn off the Favorites filter."
                if st.session_state.get(SONG_PICKER_FAVORITES_ONLY_KEY)
                else "No songs match your genre/search filters — adjust filters below."
            ),
        )

    def _render_browse_filters_legacy() -> str:
        """Legacy single-genre dropdown + search (non–Song Selection surfaces)."""
        _genre_filter_options = [_ALL_GENRE_FILTER] + available_genres
        st.session_state.setdefault("workspace_genre_filter", _ALL_GENRE_FILTER)
        _wgf = st.session_state.get("workspace_genre_filter", _ALL_GENRE_FILTER)
        if _wgf not in _genre_filter_options:
            st.session_state["workspace_genre_filter"] = _ALL_GENRE_FILTER
        _filter_cols = st.columns([1, 2])
        with _filter_cols[0]:
            workspace_genre = st.selectbox(
                "Filter songs by genre",
                _genre_filter_options,
                key="workspace_genre_filter",
            )
        with _filter_cols[1]:
            st.text_input(
                "Search / filter songs",
                placeholder="Title, artist, genre, style, difficulty…",
                key="song_search_text",
            )
        return workspace_genre

    if _library_polished:
        if _library_shell is not None:
            with _library_shell:
                render_song_library_panel_header(
                    st,
                    result_count=len(filtered) if filtered else len(visible_song_records),
                )
                render_song_library_field_label(
                    st,
                    "Search",
                    "Matches title, artist, genre, style, and chart level.",
                )
                st.text_input(
                    "Search",
                    placeholder="e.g. Shallow, shalom, Jewish ballad, beginner…",
                    key="song_search_text",
                    label_visibility="collapsed",
                )
                _fav_count = len(st.session_state.get(CATALOG_FAVORITES_KEY) or [])
                _fav_filter_on = bool(st.session_state.get(SONG_PICKER_FAVORITES_ONLY_KEY))
                _fav_btn_cols = st.columns([1.35, 2.65])
                with _fav_btn_cols[0]:
                    _fav_label = (
                        f"★ Favorites ({_fav_count})"
                        if _fav_count
                        else "★ Favorites"
                    )
                    st.button(
                        _fav_label,
                        key="song_picker_favorites_filter",
                        use_container_width=True,
                        type="primary" if _fav_filter_on else "secondary",
                        on_click=toggle_favorites_filter,
                        kwargs={"session_state": st.session_state},
                        help="Show only songs you have starred on the Active Song card.",
                    )
                with _fav_btn_cols[1]:
                    if _fav_filter_on:
                        st.markdown(
                            '<p class="ui-genre-filter-active-summary" style="margin-top:0.55rem;">'
                            "Showing <strong>favorites only</strong></p>",
                            unsafe_allow_html=True,
                        )
                _render_genre_filter_pills(available_genres)
                _filter_bits = ["genre pills", "search"]
                if _fav_filter_on:
                    _filter_bits.insert(0, "favorites")
                st.markdown(
                    f'<p class="ui-song-library-foot">'
                    f"<strong>{len(filtered)}</strong> songs match your filters "
                    f"· {', '.join(_filter_bits)} update the <strong>Active Song</strong> dropdown above</p>",
                    unsafe_allow_html=True,
                )
    else:
        if _library_shell is not None:
            with _library_shell:
                workspace_genre = _render_browse_filters_legacy()
        else:
            workspace_genre = _render_browse_filters_legacy()

        filter_genre = None if workspace_genre == _ALL_GENRE_FILTER else workspace_genre
        search_text = st.session_state.get("song_search_text", "")
        filtered = search_records(
            visible_song_records,
            search_text,
            genre=filter_genre,
            limit=max(500, len(ALL_SONG_RECORDS)),
        )
        if st.session_state.get(SONG_PICKER_FAVORITES_ONLY_KEY):
            favorites = set(st.session_state.get(CATALOG_FAVORITES_KEY) or [])
            filtered = [
                r
                for r in filtered
                if format_pick_key(r["genre"], f"{r['title']} — {r['artist']}") in favorites
            ]
        pick_options = [
            format_pick_key(r["genre"], f"{r['title']} — {r['artist']}") for r in filtered
        ]

        if not pick_options:
            if st.session_state.get(SONG_PICKER_FAVORITES_ONLY_KEY):
                st.warning(
                    "No favorites match your search — star a song on the Active Song card "
                    "or turn off the Favorites filter."
                )
            else:
                st.warning("No songs match your search — try another genre or clear the search box.")
            if wrap_section:
                close_control_section()
            return

        master_pk = (st.session_state.get("selected_song") or {}).get("pick_key")
        default_pk = master_pk if master_pk in pick_options else pick_options[0]
        if st.session_state.get(ACTIVE_CATALOG_PICK_KEY) not in pick_options:
            from songs.state import queue_pending_catalog_pick

            live_pk = str(st.session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
            target_pk = live_pk if live_pk else default_pk
            set_catalog_source(st.session_state)
            queue_pending_catalog_pick(st, target_pk)
            st.rerun()

        active_pick_key = sync_matching_song_dropdown_before_widget(
            st,
            pick_options,
            default_pk,
            song_picker_catalog=SONG_PICKER_CATALOG,
        )
        _legacy_fav_set = set(st.session_state.get(CATALOG_FAVORITES_KEY) or [])

        def _legacy_picker_label(opt: str) -> str:
            genre, title = parse_pick_key(opt)
            base = f"{title}  [{genre}]"
            return f"★ {base}" if opt in _legacy_fav_set else base

        st.selectbox(
            "Select song",
            pick_options,
            format_func=_legacy_picker_label,
            key="matching_song_dropdown",
            on_change=_on_song_dropdown_change,
            help="Primary selector — updates Practice, Backing Track, Creative Lab, and all coach tools.",
        )

    if not show_song_cards and not _developer_mode_enabled():
        st.caption(
            f"**{len(filtered)}** songs in list · open **Practice** or **Backing Track** after you pick one."
        )

    if _developer_mode_enabled():
        _library_options = [LIBRARY_MODE_FULL, LIBRARY_MODE_CORE]
        _chart_filter_options = [
            CHART_FILTER_ALL,
            CHART_FILTER_CURATED,
            CHART_FILTER_FULL_CHARTS,
            CHART_FILTER_EXTENDED,
        ]
        _dev_label = (
            "Refine library (browse filters)"
            if filters_in_expander
            else "Refine search & filters (developer)"
        )

        def _render_developer_library_filters() -> None:
            with st.expander(_dev_label, expanded=False):
                st.caption("Developer Mode — library scope and chart filters.")
                st.radio(
                    "Song library",
                    _library_options,
                    horizontal=True,
                    key="chart_library_mode",
                )
                st.radio(
                    "Search scope",
                    ["Entire library", "Single genre"],
                    horizontal=True,
                    key="song_search_scope",
                )
                c1, c2 = st.columns(2)
                with c1:
                    st.selectbox(
                        "Show songs",
                        _chart_filter_options,
                        key="song_picker_chart_status",
                    )
                with c2:
                    st.selectbox(
                        "Chart level available",
                        ["Any level", "Beginner", "Intermediate", "Advanced"],
                        key="song_picker_level_filter",
                    )

        if _library_shell is not None:
            with _library_shell:
                _render_developer_library_filters()
        else:
            _render_developer_library_filters()

    if wrap_section:
        close_control_section()


def _render_page_quick_nav(current_page: str) -> str:
    """Top-of-page navigation bar."""
    if not pp.show_quick_nav(st):
        return current_page
    return render_page_quick_nav(
        st.session_state,
        current_page=current_page,
        rerun_fn=st.rerun,
    )


def _sync_focus_options_before_widget(instrument: str) -> list[str]:
    """Compute focus options for ``instrument`` and clamp the global
    ``focus`` to a value Streamlit will accept.

    The old version used ``setdefault`` which silently leaves a stale
    out-of-options value in place when the user switches instruments;
    that caused page-to-page drift (the global was a Sax focus while
    the new page only offered Piano focuses). We overwrite directly so
    every surface sees the same value on the same render.
    """
    opts = focus_options_for_instrument(instrument)
    if opts and st.session_state.get("focus") not in opts:
        st.session_state["focus"] = opts[0]
        try:
            from practice_setup_globals import record_global_control_change

            record_global_control_change(
                st.session_state,
                "focus",
                "sync_focus_options_before_widget",
            )
        except Exception:
            pass
    return opts


def _render_practice_section_focus_details(
    *,
    focus_pick: str,
    sections_for_practice: dict,
    display_section_fn: Callable[[str | None], str],
    transition_pairs: list[str],
    prepare_backing_fn: Callable[[str], None],
) -> None:
    """Section metadata and loop action — rendered inside Practice Control Center."""
    _is_full_song = practice_is_full_song(focus_pick)
    _active_section = (
        practice_active_section_name(focus_pick, sections_for_practice)
        if not _is_full_song
        else None
    )
    _active_section_display = display_section_fn(_active_section)
    _view_sections = practice_display_sections(sections_for_practice, focus_pick)
    _view_chords = (
        all_chords_from_sections(_view_sections)
        if _is_full_song
        else list((_view_sections.get(_active_section) or []) if _active_section else [])
    )
    _focus_section_name = (
        "Full song" if _is_full_song else (_active_section_display or str(focus_pick or "Section"))
    )
    _focus_unique_chords = len({str(ch).strip() for ch in _view_chords if str(ch).strip()})
    _focus_bar_count = len(_view_chords)
    st.markdown(
        f'<div class="ui-badge-row">'
        f'<span class="ui-badge accent">{html.escape(_focus_section_name)}</span>'
        f'<span class="ui-badge">{_focus_unique_chords} chord{"s" if _focus_unique_chords != 1 else ""}</span>'
        f'<span class="ui-badge">{_focus_bar_count} bars</span>'
        f"</div>",
        unsafe_allow_html=True,
    )
    if transition_pairs:
        st.markdown(
            '<div class="ui-practice-focus-transition"><strong>Transition practice:</strong> '
            + " · ".join(html.escape(p) for p in transition_pairs)
            + "</div>",
            unsafe_allow_html=True,
        )
    if not _is_full_song and _active_section:
        if st.button(
            f"Loop {_active_section_display} in Backing Track",
            key="practice_loop_section_to_backing",
            use_container_width=True,
        ):
            prepare_backing_fn(_active_section)
            set_pending_anchor(st.session_state, ANCHOR_BACKING_MAIN_CONTROLS)
            navigate_studio_page(st.session_state, "backing")
            st.rerun()


def _practice_section_transition_pairs(
    section_chords: list,
    *,
    max_pairs: int = 4,
) -> list[str]:
    _transition_pairs: list[str] = []
    for _i in range(len(section_chords) - 1):
        _a = str(section_chords[_i]).strip()
        _b = str(section_chords[_i + 1]).strip()
        if not _a or not _b:
            continue
        _pair = f"{_a} → {_b}"
        if _pair not in _transition_pairs:
            _transition_pairs.append(_pair)
        if len(_transition_pairs) >= max_pairs:
            break
    return _transition_pairs


def _render_practice_setup_panel(
    *,
    instrument_options: list[str],
    default_groove: str,
    section_choices: list[str] | None = None,
    section_focus_after_jump: Callable[[], None] | None = None,
) -> None:
    """Practice Control Center — instrument, level, focus, groove, session length."""
    from practice_state import (
        PRACTICE_MINUTES_DEFAULT,
        coerce_practice_groove_for_widget,
        prepare_practice_minutes_for_widget,
    )
    from practice_ui_labels import (
        GROOVE_ICONS,
    )
    from songs.playback_defaults import GROOVE_STYLE_CHOICES

    grooves = list(GROOVE_STYLE_CHOICES)
    _groove = coerce_practice_groove_for_widget(st.session_state, default_groove=default_groove)
    _minutes = prepare_practice_minutes_for_widget(st.session_state)

    with st.container(key="practice_control_panel", border=False):
        render_practice_control_panel_header(st)

        _instrument, _level, _focus = render_setup_quick_controls(
            st,
            session_state=st.session_state,
            key_prefix="practice_panel",
            instrument_options=instrument_options,
            label="Instrument · level · focus",
            show_sync_caption=False,
        )

        g1, g2 = st.columns([1, 1])
        with g1:
            st.markdown('<div class="ui-practice-control-field">', unsafe_allow_html=True)
            render_backing_field_label(st, "Rhythm / groove feel", "Shapes coach pacing and backing style hints.")
            st.selectbox(
                "Rhythm / groove feel",
                grooves,
                key="practice_groove_style",
                label_visibility="collapsed",
                on_change=_on_practice_filter_change,
            )
            _groove_icon = GROOVE_ICONS.get(st.session_state.get("practice_groove_style", _groove), "✨")
            _groove_label = html.escape(str(st.session_state.get("practice_groove_style", _groove)))
            st.markdown(
                f'<span class="ui-practice-groove-badge">{html.escape(_groove_icon)} {_groove_label}</span>',
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)
        with g2:
            st.markdown('<div class="ui-practice-control-field">', unsafe_allow_html=True)
            render_backing_field_label(st, "Practice length", "Session goal in minutes — coach scales to this.")
            st.slider(
                "Practice length (minutes)",
                10,
                120,
                int(st.session_state.get("practice_minutes", _minutes or PRACTICE_MINUTES_DEFAULT)),
                5,
                key="practice_minutes",
                label_visibility="collapsed",
                on_change=_on_practice_filter_change,
            )
            st.markdown("</div>", unsafe_allow_html=True)

        _summary = practice_setup_summary_text(
            instrument=str(st.session_state.get("instrument", _instrument)),
            level=str(st.session_state.get("level", _level)),
            focus=str(st.session_state.get("focus", _focus)),
            groove=str(st.session_state.get("practice_groove_style", _groove)),
            minutes=int(st.session_state.get("practice_minutes", _minutes)),
        )
        st.markdown(practice_setup_summary_badge_html(_summary), unsafe_allow_html=True)

        st.markdown(
            '<p class="ui-practice-panel-hint">Coach and charts follow these choices. '
            "Tempo and section loops live on <strong>Backing Track</strong>.</p>",
            unsafe_allow_html=True,
        )

        if section_choices:
            st.markdown(
                '<hr class="ui-practice-focus-divider" style="margin:.7rem 0 .55rem;border:none;'
                'border-top:1px solid rgba(148,163,184,.22);">',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<p class="ui-practice-focus-title">Section Focus</p>',
                unsafe_allow_html=True,
            )
            from app_ui import render_section_jump_bar as _render_section_jump_bar

            _render_section_jump_bar(
                section_choices,
                st.session_state,
                state_key="practice_focus_section",
                rerun_fn=st.rerun,
                on_change=_on_practice_filter_change,
            )
            if section_focus_after_jump:
                section_focus_after_jump()


def _studio_page_header(
    icon: str,
    title: str,
    subtitle: str = "",
    *,
    page_id: str | None = None,
) -> None:
    """Page title plus subtle instrument-aware context strip."""
    compact_page_title(
        icon,
        title,
        subtitle,
        page_id=page_id or _studio_page,
        skip_chart_key_badge=(page_id or _studio_page) == "backing",
    )
    try:
        from instrument_aware import render_instrument_context_strip

        render_instrument_context_strip(st, instrument, _studio_page, st.session_state)
    except Exception:
        pass


def _render_backing_scope_controls(
    section_names: list[str],
    *,
    from_practice_handoff: bool,
    show_panel_header: bool = True,
) -> None:
    """Scope and loop controls inside the Playback Setup card (keyed container)."""
    with st.container(key="backing_scope_panel", border=False):
        if show_panel_header:
            _loop_summary = backing_scope_loop_summary_text(
                st.session_state.get("backing_track_scope", "Full song"),
                single_section=str(st.session_state.get("backing_track_single_section", "")),
                multi_sections=list(st.session_state.get("backing_track_multi_sections") or []),
                loops=int(st.session_state.get("backing_track_loops", 2)),
            )
            render_backing_scope_panel_header(
                st,
                summary_html=backing_scope_loop_summary_badge_html(_loop_summary),
            )

        st.markdown('<div class="ui-backing-scope-segment">', unsafe_allow_html=True)
        playback_scope = st.radio(
            "Playback range",
            ["Full song", "Single section", "Multiple selected sections"],
            horizontal=True,
            key="backing_track_scope",
            label_visibility="collapsed",
            on_change=_on_backing_filter_change,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        if playback_scope == "Single section" and section_names:
            st.markdown('<div class="ui-backing-scope-field">', unsafe_allow_html=True)
            render_backing_field_label(st, "Section", "Loops this section when generating.")
            st.selectbox(
                "Section to loop",
                section_names,
                key="backing_track_single_section",
                label_visibility="collapsed",
                on_change=_on_backing_filter_change,
            )
            st.markdown("</div>", unsafe_allow_html=True)
        elif playback_scope == "Multiple selected sections" and section_names:
            if "backing_track_multi_sections" not in st.session_state:
                _multi_seed: list[str] = []
                try:
                    from backing_track_state import canonical_backing_filters

                    _canon = canonical_backing_filters(st.session_state) or {}
                    _multi_seed = list(_canon.get("backing_track_multi_sections") or [])
                except ImportError:
                    pass
                st.session_state["backing_track_multi_sections"] = _multi_seed or [
                    name
                    for name in section_names
                    if any(token in name.lower() for token in ["verse", "chorus"])
                ] or section_names[:2]
            st.markdown('<div class="ui-backing-scope-field">', unsafe_allow_html=True)
            render_backing_field_label(st, "Sections", "Keeps original song order.")
            st.multiselect(
                "Sections to play (keeps original song order)",
                section_names,
                key="backing_track_multi_sections",
                label_visibility="collapsed",
                on_change=_on_backing_filter_change,
            )
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="ui-backing-scope-loops-row">', unsafe_allow_html=True)
        render_backing_field_label(st, "Repeats", "How many times to loop the chosen range.")
        try:
            from backing_track_state import BACKING_LOOPS_DEFAULT, normalize_backing_loops

            _loops_slider_val = normalize_backing_loops(
                st.session_state.get("backing_track_loops", BACKING_LOOPS_DEFAULT)
            )
        except ImportError:
            _loops_slider_val = int(st.session_state.get("backing_track_loops", 2))
        st.slider(
            "Number of repeats",
            1,
            10,
            _loops_slider_val,
            1,
            key="backing_track_loops",
            label_visibility="collapsed",
            on_change=_on_backing_filter_change,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        if from_practice_handoff:
            _handoff_sec = st.session_state.get("backing_track_single_section", "")
            st.markdown(
                f'<div class="ui-backing-scope-handoff">Opened from <strong>Practice</strong> — '
                f"defaults to <strong>{html.escape(_handoff_sec or 'the selected section')}</strong>.</div>",
                unsafe_allow_html=True,
            )


def _render_backing_playback_setup_panel(
    *,
    section_names: list[str],
    from_practice_handoff: bool,
    backing_ready: bool,
) -> None:
    """Step 1 — playback range and loops only."""
    _loop_summary = backing_scope_loop_summary_text(
        st.session_state.get("backing_track_scope", "Full song"),
        single_section=str(st.session_state.get("backing_track_single_section", "")),
        multi_sections=list(st.session_state.get("backing_track_multi_sections") or []),
        loops=int(st.session_state.get("backing_track_loops", 2)),
    )
    _badge = (
        '<span class="ui-backing-panel-badge ready">● Ready</span>'
        if backing_ready
        else '<span class="ui-backing-panel-badge">○ Not generated</span>'
    )

    with st.container(key="backing_step1_range", border=False):
        render_backing_panel_shell_open(st, "scope")
        render_backing_panel_header(
            st,
            kicker="Step 1",
            title="Playback range & loops",
            subtitle="Choose what to practice and how many times to loop.",
            badge_html=_badge
            + backing_scope_loop_summary_badge_html(_loop_summary),
        )
        _render_backing_scope_controls(
            section_names,
            from_practice_handoff=from_practice_handoff,
            show_panel_header=False,
        )
        render_backing_panel_shell_close(st)

    st.session_state[BACKING_HUMANIZE_LEVEL_KEY] = "Strong"
    st.session_state.setdefault(BACKING_PRESERVE_EXACT_KEY, False)


def _backing_transport_status_message(
    *,
    backing_ready: bool,
    stale_audio: bool,
    autoplay: bool,
) -> tuple[str, str]:
    """Return (message, ui_state) for the transport feedback strip."""
    play_feedback = str(st.session_state.get(BACKING_PLAY_FEEDBACK_KEY, "") or "").strip()
    if play_feedback:
        state = "active" if autoplay else "stopped"
        if "stopped" in play_feedback.lower():
            state = "stopped"
        return play_feedback, state
    explicit = str(st.session_state.get(BACKING_TRANSPORT_STATUS, "") or "").strip().lower()
    if explicit == "generating":
        return "Generating backing track…", "active"
    if explicit == "preparing":
        return "Preparing audio for playback…", "active"
    if explicit == "ready":
        return (
            "Audio ready — press Play or use the player below to start playback.",
            "ready",
        )
    if explicit == "playing":
        if autoplay:
            return "Playing — follow the lead sheet below.", "active"
        return "Playback ready — press Play to start.", "ready"
    if explicit == "stopped":
        return "Playback stopped — press Play to start again.", "stopped"
    if stale_audio:
        return "Settings changed — press Play to rebuild audio.", "warn"
    if backing_ready:
        return "Audio ready — press Play Backing Track or use the player below.", "ready"
    return "Press Play Backing Track to generate and play.", "idle"


def _render_backing_step2_playback_action(
    *,
    song_id: str,
    default_bpm: int,
    default_groove: str,
    default_meter: str,
    song_data: dict | None,
    section_names: list[str],
    backing_chords: list,
    section_scope_label: str,
    song_title: str,
    signature_for_bpm,
    song_just_reset: bool,
    lock_style_meter: bool = False,
    locked_style: str = "",
    locked_meter: str = "",
) -> tuple[int, bool]:
    """Step 2 — tempo, quick controls, play backing (generate-on-demand)."""
    song_id = str(song_id or st.session_state.get("_active_bpm_sync_id") or "").strip()
    if not song_id:
        song_id = resolve_active_bpm_sync_id(
            st.session_state,
            song_title=str(song_title or ""),
        )
    try:
        from backing_track_state import prepare_backing_meter_for_widget

        applied_meter, meter_override = prepare_backing_meter_for_widget(
            st.session_state,
            default_meter=default_meter,
        )
    except ImportError:
        applied_meter, meter_override, _song_meter = apply_backing_meter_for_song(
            st,
            song_id=song_id,
            default_time_signature=default_meter,
        )
    else:
        applied_meter, meter_override, _song_meter = apply_backing_meter_for_song(
            st,
            song_id=song_id,
            default_time_signature=default_meter,
        )
    _prime_backing_quick_section_from_scope(st.session_state, section_names)
    quick_opts = ["Full song"] + list(section_names)
    slider_key = backing_bpm_slider_widget_key(song_id)
    try:
        from backing_track_state import coerce_backing_groove_for_widget, prepare_backing_bpm_for_widget

        prepare_backing_bpm_for_widget(st.session_state, default_bpm=int(default_bpm))
        coerce_backing_groove_for_widget(st.session_state, default_groove=default_groove)
    except ImportError:
        pass
    widget_bpm = resolve_backing_bpm_for_slider(
        st,
        sync_id=song_id,
        default_bpm=default_bpm,
        song_just_reset=song_just_reset,
    )

    with st.container(key="backing_step2_action", border=False):
        render_backing_panel_shell_open(st, "transport")
        render_backing_panel_header(
            st,
            kicker="Step 2",
            title="Tempo & playback",
            subtitle="Set tempo, then play — audio generates automatically when needed.",
            badge_html="",
            compact=True,
        )
        st.markdown(
            '<div class="ui-backing-quick-controls ui-backing-action-controls">',
            unsafe_allow_html=True,
        )
        _tc1, _tc2, _tc3 = st.columns(3)
        with _tc1:
            st.markdown('<span class="ui-backing-inline-label">Tempo (BPM)</span>', unsafe_allow_html=True)

            def _on_bpm_slider_change() -> None:
                sync_backing_bpm_from_slider(
                    st,
                    slider_bpm=int(st.session_state.get(slider_key, widget_bpm)),
                )
                _on_backing_filter_change()

            bpm = st.slider(
                "Quick BPM",
                BACKING_BPM_MIN,
                BACKING_BPM_MAX,
                widget_bpm,
                5,
                key=slider_key,
                label_visibility="collapsed",
                help="Your tempo is kept until you change songs (20–180 BPM).",
                on_change=_on_bpm_slider_change,
            )
            bpm = sync_backing_bpm_from_slider(st, slider_bpm=int(bpm))
        with _tc2:
            st.markdown('<span class="ui-backing-inline-label">Section focus</span>', unsafe_allow_html=True)
            cur_quick = st.session_state.get(BACKING_QUICK_SECTION_KEY, "Full song")
            if cur_quick not in quick_opts:
                cur_quick = "Full song"
            idx = quick_opts.index(cur_quick)

            def _on_quick_section() -> None:
                request_backing_quick_section_change(
                    st.session_state.get(BACKING_QUICK_SECTION_KEY, "Full song"),
                    section_names,
                )
                st.rerun()

            st.selectbox(
                "Quick section",
                quick_opts,
                index=idx,
                key=BACKING_QUICK_SECTION_KEY,
                on_change=_on_quick_section,
                label_visibility="collapsed",
                help="Synced with Step 1 playback range.",
            )
        with _tc3:
            st.markdown('<span class="ui-backing-inline-label">Repeats</span>', unsafe_allow_html=True)
            _loops_val = int(st.session_state.get("backing_track_loops", 2))
            _lq1, _lq2, _lq3 = st.columns([1, 1.4, 1])
            with _lq1:
                st.button(
                    "−",
                    key="backing_loops_dec",
                    use_container_width=True,
                    on_click=request_backing_loops_adjust,
                    args=(-1,),
                )
            with _lq2:
                st.markdown(
                    f'<p style="margin:0.35rem 0 0;text-align:center;font-weight:800;color:#0f172a;">'
                    f"{_loops_val}×</p>",
                    unsafe_allow_html=True,
                )
            with _lq3:
                st.button(
                    "+",
                    key="backing_loops_inc",
                    use_container_width=True,
                    on_click=request_backing_loops_adjust,
                    args=(1,),
                )
        st.markdown("</div>", unsafe_allow_html=True)

        with st.expander("Advanced playback settings", expanded=False):
            st.markdown('<div class="ui-backing-feel-inline">', unsafe_allow_html=True)
            st.markdown("<div>", unsafe_allow_html=True)
            st.markdown('<span class="ui-backing-inline-label">Feel</span>', unsafe_allow_html=True)
            if lock_style_meter:
                _locked_style = str(locked_style or st.session_state.get("backing_groove_style") or default_groove)
                st.session_state["backing_groove_style"] = _locked_style
                st.markdown(
                    f'<p class="ui-backing-locked-setting"><strong>{html.escape(_locked_style)}</strong>'
                    f"<br><small>Inherited from your Creative jam — change style on the Creative page.</small></p>",
                    unsafe_allow_html=True,
                )
            else:
                st.selectbox(
                    "Groove style",
                    list(GROOVE_STYLE_CHOICES),
                    key="backing_groove_style",
                    label_visibility="collapsed",
                    on_change=_on_backing_filter_change,
                )
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("<div>", unsafe_allow_html=True)
            st.markdown('<span class="ui-backing-inline-label">Meter</span>', unsafe_allow_html=True)
            if lock_style_meter:
                _locked_meter = str(locked_meter or applied_meter or default_meter)
                st.session_state["backing_time_signature"] = _locked_meter
                st.markdown(
                    f'<p class="ui-backing-locked-setting"><strong>{html.escape(_locked_meter)}</strong>'
                    f"<br><small>Locked to your Creative jam meter.</small></p>",
                    unsafe_allow_html=True,
                )
            else:
                applied_meter = render_backing_meter_selector(
                    st,
                    song_default_meter=default_meter,
                    applied_meter=applied_meter,
                    user_override=meter_override,
                    after_change=_on_backing_filter_change,
                )
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            st.checkbox(
                "Preserve exact chart timing (disable harmonic rhythm intelligence)",
                key=BACKING_PRESERVE_EXACT_KEY,
                help="Off by default — the app uses Strong feel automatically.",
            )
            if not st.session_state.get(BACKING_PRESERVE_EXACT_KEY, False):
                st.session_state[BACKING_HUMANIZE_LEVEL_KEY] = "Strong"

        backing_ready = bool(
            st.session_state.get("_last_backing_wav")
            and st.session_state.get("_last_backing_signature") == signature_for_bpm(int(bpm))
        )
        stale_audio = bool(st.session_state.get("_last_backing_wav")) and not backing_ready
        _status_msg, _status_state = _backing_transport_status_message(
            backing_ready=backing_ready,
            stale_audio=stale_audio,
            autoplay=bool(st.session_state.get(BACKING_AUTOPLAY, False)),
        )
        render_backing_transport_feedback(st, message=_status_msg, state=_status_state)

        st.markdown('<div class="ui-backing-transport-toolbar">', unsafe_allow_html=True)
        _btn1, _btn2 = st.columns(2)
        with _btn1:
            _play_clicked = st.button(
                "▶ Play Backing Track",
                key="play_backing_btn",
                disabled=not bool(backing_chords),
                type="primary",
                use_container_width=True,
            )
        with _btn2:
            if st.button(
                "■ Stop",
                key="stop_backing_btn",
                disabled=not bool(st.session_state.get("_last_backing_wav")),
                use_container_width=True,
            ):
                _stop_backing_playback()
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        if backing_ready:
            _scope_bit = section_scope_label.replace(" ", "_").replace("/", "_")
            st.download_button(
                "⬇ Download WAV",
                st.session_state["_last_backing_wav"],
                file_name=f"{song_title.replace(' ', '_')}_{_scope_bit}_{int(st.session_state.get('backing_track_loops', 2))}loops.wav",
                mime="audio/wav",
                key="dl_backing_btn",
                use_container_width=True,
            )
        render_backing_panel_shell_close(st)

    return int(bpm), _play_clicked


# -------------------------------------------------
# APP UI
# -------------------------------------------------

inject_app_theme()
if _developer_mode_enabled():
    try:
        from app_ui import STUDIO_UI_RELEASE, use_simple_music_nav

        _simple_nav_on = use_simple_music_nav(st.session_state)
        st.sidebar.caption(
            f"Studio UI · `{STUDIO_UI_RELEASE}`  \n"
            f"Nav UI · `{NAVIGATION_UI_DEPLOY_MARKER}`  \n"
            f"Simple nav · `{'on' if _simple_nav_on else 'off'}`"
        )
    except Exception:
        pass

    try:
        render_nav_deploy_marker(st, developer_mode=True)
    except Exception:
        pass

try:
    ensure_sidebar_nav_defaults(st.session_state)
    sync_sidebar_nav_body_dataset(st.session_state, st)
except Exception:
    pass

# Voice / Karaoke body class - applied globally so the larger-lyric +
# vocal-focused CSS in app_ui.py (`[data-vocal-focus="true"]` selectors)
# is active on every page when the user's instrument is Voice. Set
# unconditionally on each rerun so toggling instruments instantly flips
# the styling without a hard page reload.
st.markdown(
    f"""
    <script>
      try {{
        document.body.dataset.vocalFocus = "{ 'true' if km.is_voice_mode(st.session_state) else 'false' }";
        document.body.dataset.karaokeSession = "{ 'true' if (km.is_voice_mode(st.session_state) and km.is_karaoke_session_active(st.session_state)) else 'false' }";
      }} catch (e) {{}}
    </script>
    """,
    unsafe_allow_html=True,
)

render_studio_brand_header()

from app_tutorial import (
    init_tutorial_state,
    open_tutorial,
    render_tutorial_walkthrough,
    tutorial_entry_visible,
)

init_tutorial_state(st.session_state)
init_nav_history(st.session_state)

try:
    render_floating_nav_history(st, st.session_state, rerun_fn=st.rerun)
except Exception as _early_nav_hist_exc:
    if st.session_state.get("developer_mode"):
        st.warning(f"Back/Forward nav render failed: {_early_nav_hist_exc}")

from openai_secrets_config import resolve_openai_api_key

_openai_api_key, _openai_secrets_probe = resolve_openai_api_key()

_studio_page_before_workspace = str(st.session_state.get("studio_page") or "practice")
try:
    from local_nav_trace import record_local_nav_checkpoint

    record_local_nav_checkpoint(st, "run_start", intent=_studio_page_before_workspace)
except Exception:
    pass

try:
    from applied_math_return_insight import hydrate_applied_math_insight_for_session
    from suite_resume_launch import finalize_ami_return_restore

    hydrate_applied_math_insight_for_session(st, "music")
    finalize_ami_return_restore(st, "music")
except Exception as exc:
    st.session_state["_ami_insight_startup_error"] = str(exc)

_nav_target = st.session_state.pop("_navigate_to_studio_page", None)
if _nav_target:
    try:
        from studio_nav_history import navigate_studio_page

        navigate_studio_page(st.session_state, str(_nav_target))
    except Exception:
        st.session_state["studio_page"] = str(_nav_target)

try:
    from music_persistent_state import prepare_music_workspace
    from suite_user_persistence import record_page_navigation_startup_diagnostics, show_persistence_messages

    record_page_navigation_startup_diagnostics(st, "music")
    st.session_state.pop("_music_workspace_prepared_for_run", None)
    prepare_music_workspace(
        st,
        song_picker_catalog=SONG_PICKER_CATALOG,
        song_library=SONG_LIBRARY,
    )
    try:
        from music_persistent_state import (
            maybe_flush_deferred_page_change_save,
            prepare_canonical_music_page_state,
        )

        from music_persistent_state import run_post_nav_music_startup_init

        _skip_master_song_init = run_post_nav_music_startup_init(
            st,
            song_picker_catalog=SONG_PICKER_CATALOG,
            song_library=SONG_LIBRARY,
            default_song_records=DEFAULT_SONG_RECORDS,
        )
        st.session_state["_music_post_nav_startup_done"] = True
        prepare_canonical_music_page_state(
            st.session_state,
            song_picker_catalog=SONG_PICKER_CATALOG,
            song_library=SONG_LIBRARY,
        )
        _catalog_genre, _catalog_song, _catalog_song_data = get_song_context(
            st,
            song_library=SONG_LIBRARY,
            song_picker_catalog=SONG_PICKER_CATALOG,
        )
        _pick_key_recovery = st.session_state.pop(PICK_KEY_RECOVERY_NOTICE_KEY, None)
        if _pick_key_recovery:
            st.warning(_pick_key_recovery)
        maybe_flush_deferred_page_change_save(st)
        try:
            from local_nav_trace import record_local_nav_checkpoint

            record_local_nav_checkpoint(st, "post_canonical")
        except Exception:
            pass
        try:
            from studio_nav_history import consume_history_nav_startup_flag, record_nav_history_trace

            if consume_history_nav_startup_flag(st.session_state):
                st.session_state["_studio_history_nav_consumed"] = True
            record_nav_history_trace(st, st.session_state)
        except Exception:
            pass
    except Exception:
        pass
    show_persistence_messages(st)
    try:
        from local_nav_trace import record_local_nav_checkpoint

        record_local_nav_checkpoint(st, "post_workspace")
    except Exception:
        pass
except Exception:
    pass

# Fallback if post-restore init skipped get_song_context (v17 defer path).
try:
    if not isinstance(_catalog_song_data, dict):
        raise NameError("_catalog_song_data invalid")
except NameError:
    try:
        _catalog_genre, _catalog_song, _catalog_song_data = get_song_context(
            st,
            song_library=SONG_LIBRARY,
            song_picker_catalog=SONG_PICKER_CATALOG,
        )
    except Exception:
        _catalog_genre, _catalog_song, _catalog_song_data = "Pop", "", {}

# Studio page bootstrap (sidebar order is rendered below Command Center link).
_studio_page = ensure_studio_page(st.session_state)
try:
    ensure_sidebar_nav_defaults(st.session_state)
except Exception:
    pass
migrate_legacy_session_keys(st.session_state)
sanitize_persisted_snapshots(st.session_state)
handle_studio_page_transition(st.session_state)
try:
    from local_nav_trace import record_local_nav_checkpoint

    record_local_nav_checkpoint(st, "post_transition")
except Exception:
    pass
note_page_visit(st.session_state, _studio_page)

if _studio_page == "openai" and not _openai_api_key:
    navigate_studio_page(st.session_state, "practice")
    st.rerun()

if not st.session_state.get("_music_sidebar_suite_top_css"):
    st.session_state["_music_sidebar_suite_top_css"] = True
    st.sidebar.markdown(
        """
<style>
[data-testid="stSidebar"] > div:first-child hr { margin: 0.15rem 0 !important; }
[data-testid="stSidebar"] .stExpander { margin-top: 0.1rem !important; }
</style>
        """,
        unsafe_allow_html=True,
    )

try:
    from music_persistent_state import default_reset_music_session
    from suite_user_persistence import render_reset_controls

    render_reset_controls(
        st,
        "music",
        on_reset=default_reset_music_session,
        label="Reset to default",
        help_text=(
            "Clears session, local saved state, and cloud session for this app. "
            "Catalog data and user chart overrides are not deleted."
        ),
    )
except Exception:
    pass

if pp.show_tutorial_entry(st) and tutorial_entry_visible(st.session_state):
    _brand_t1, _brand_t2 = st.columns([5, 1])
    with _brand_t2:
        if st.button("📖 Tutorial", key="tutorial_header_btn", use_container_width=True):
            open_tutorial(st.session_state)
            st.rerun()


def _ui_source_label() -> str:
    if is_custom_progression(st.session_state):
        return "Custom progression"
    return "Catalog song"


def _active_song_artist_label() -> str:
    """Artist line for the active song (catalog metadata or custom progression)."""
    if is_custom_progression(st.session_state):
        cpl = ensure_original_structure(st.session_state.get(CPL_ACTIVE_KEY) or {})
        return str(cpl.get("artist") or "").strip()
    return str((song_data or {}).get("artist") or "").strip()


# SIDEBAR — suite order: Command Center → Saved Session → Active Song → Practice Setup → Pages → Session

sidebar_section("Active Song", icon="🎼", tone="source")
_cpl_for_banner = ensure_original_structure(st.session_state.get(CPL_ACTIVE_KEY) or {})
_src_kind, _src_detail = unpack_active_source_banner(
    active_source_banner(
        st.session_state,
        catalog_title=_catalog_song_data.get("title", _catalog_song),
        catalog_artist=_catalog_song_data.get("artist", ""),
        custom_name=_cpl_for_banner.get("name", "Custom Progression"),
    )
)
sidebar_source_banner(_src_kind, _src_detail)


def _sidebar_open_song_selection() -> None:
    set_pending_anchor(st.session_state, ANCHOR_CHOOSE_ACTIVE_SONG)
    navigate_studio_page(st.session_state, "picker")


sidebar_goto_song_selection(on_navigate=_sidebar_open_song_selection)
if is_custom_progression(st.session_state):
    st.sidebar.caption("Edit chords in **Custom Progression Lab**.")
else:
    st.sidebar.caption(f"**{_catalog_song}** · {_catalog_genre}")

from practice_setup_globals import ensure_global_setup_defaults as _ensure_global_setup_defaults

# Single source of truth for Instrument / Level / Practice Focus.
# Initialise + validate the three global keys before any sidebar /
# page widget reads them, so any page that changes one of these values
# (sidebar, quick controls, YouTube panel, etc.) sees it everywhere.
_ensure_global_setup_defaults(st.session_state)

_studio_page_for_hydrate = str(st.session_state.get("studio_page") or "practice").strip() or "practice"
if _studio_page_for_hydrate == "practice":
    try:
        from backing_source_navigation import hydrate_practice_source_for_page

        hydrate_practice_source_for_page(st.session_state, st_like=st)
    except ImportError:
        pass
elif _studio_page_for_hydrate == "backing":
    try:
        from backing_source_navigation import hydrate_backing_source_for_page

        hydrate_backing_source_for_page(st.session_state, st_like=st)
    except ImportError:
        pass
elif _studio_page_for_hydrate == "creative":
    try:
        from backing_source_navigation import (
            CREATIVE_RESTORE_FROM_BACKING_KEY,
            rehydrate_creative_from_backing_context,
        )

        if st.session_state.get(CREATIVE_RESTORE_FROM_BACKING_KEY):
            rehydrate_creative_from_backing_context(st.session_state, st_like=st)
            st.session_state.pop(CREATIVE_RESTORE_FROM_BACKING_KEY, None)
        try:
            from studio_page_state import ensure_creative_widgets_from_backing_context

            ensure_creative_widgets_from_backing_context(st.session_state)
        except ImportError:
            pass
        try:
            from session_widget_safe import apply_pending_widget_hydrates

            apply_pending_widget_hydrates(st.session_state)
        except ImportError:
            pass
    except ImportError:
        pass

try:
    from app_ui import inject_studio_ui_release_marker

    inject_studio_ui_release_marker(st, page=str(_studio_page))
except Exception:
    pass
try:
    from session_widget_safe import apply_pending_widget_hydrates

    apply_pending_widget_hydrates(st.session_state, st_like=st)
except ImportError:
    pass

original_key, _song_identity = display_key_context(
    st.session_state,
    catalog_song_data=_catalog_song_data,
    cpl_active_key=CPL_ACTIVE_KEY,
)
from songs.music_source import cpl_session_is_active as _cpl_session_is_active

try:
    from backing_musical_state import should_skip_regular_song_defaults
    from creative_key_sync import (
        is_creative_major_jam_active,
        on_sidebar_practice_concert_key_change,
        prepare_backing_context_sidebar_display_key,
        prepare_creative_sidebar_display_key,
        should_use_live_practice_key_sidebar,
    )
    from backing_context import active_creative_backing_context, get_backing_context

    _backing_ctx_for_sidebar = get_backing_context(st.session_state)
    _catalog_regular_backing = (
        _backing_ctx_for_sidebar is not None
        and str(getattr(_backing_ctx_for_sidebar, "source", "") or "").strip() == "regular_song"
        and active_creative_backing_context(st.session_state) is None
    )
    if is_creative_major_jam_active(st.session_state):
        _display_key_options = prepare_creative_sidebar_display_key(st, st.session_state)
    elif _catalog_regular_backing:
        _display_key_options = sync_display_key_before_widget(
            st,
            original_key,
            _song_identity,
        )
    elif should_skip_regular_song_defaults(st.session_state) or should_use_live_practice_key_sidebar(
        st.session_state
    ):
        _display_key_options = prepare_backing_context_sidebar_display_key(st, st.session_state)
    else:
        _display_key_options = sync_display_key_before_widget(
            st,
            original_key,
            _song_identity,
        )
except Exception:
    _display_key_options = sync_display_key_before_widget(
        st,
        original_key,
        _song_identity,
    )
    try:
        from creative_key_sync import on_sidebar_practice_concert_key_change
    except ImportError:
        def on_sidebar_practice_concert_key_change() -> None:  # type: ignore[misc]
            mark_display_key_changed(st)

st.sidebar.markdown(
    f'<p class="ui-sidebar-key-caption">Song Original Key: <strong>{original_key}</strong></p>',
    unsafe_allow_html=True,
)
st.sidebar.selectbox(
    "Practice / Concert Key",
    _display_key_options,
    key="display_key",
    help="Concert pitch for charts and backing audio.",
    on_change=on_sidebar_practice_concert_key_change,
)
try:
    from music_restore_phase import STREAMLIT_WIDGETS_LOCKED_KEY

    st.session_state[STREAMLIT_WIDGETS_LOCKED_KEY] = True
except ImportError:
    st.session_state["_streamlit_widgets_locked_this_run"] = True

_instrument_options = DEFAULT_INSTRUMENT_OPTIONS


def _sync_canonical_backing_after_edit() -> None:
    """Phase C: flush canonical backing_track_state and force cloud save."""
    try:
        from music_persistent_state import flush_backing_edits_and_save

        flush_backing_edits_and_save(st, reason="backing_edit")
    except Exception:
        pass


def _on_backing_filter_change() -> None:
    try:
        from backing_track_state import BACKING_USER_EDITS_ALLOWED_KEY, mark_backing_user_edit

        if not st.session_state.get(BACKING_USER_EDITS_ALLOWED_KEY):
            return
        mark_backing_user_edit(st.session_state)
    except Exception:
        return
    _sync_canonical_backing_after_edit()


def _sync_canonical_practice_after_edit() -> None:
    """Phase C: flush canonical practice_state and force cloud save."""
    try:
        from music_persistent_state import flush_practice_edits_and_save

        flush_practice_edits_and_save(st, reason="practice_edit")
    except Exception:
        pass


def _on_practice_filter_change() -> None:
    try:
        from practice_state import mark_practice_pending_sync

        mark_practice_pending_sync(st.session_state)
    except Exception:
        pass
    _sync_canonical_practice_after_edit()


def _sync_canonical_active_song_after_edit() -> None:
    """Phase C: flush canonical active_song_state and force cloud save."""
    try:
        from music_persistent_state import flush_active_song_edits_and_save

        flush_active_song_edits_and_save(st, reason="song_edit")
    except Exception:
        persist_music_local_state(st)


def _on_written_key_checkbox_change() -> None:
    instrument = st.session_state.get("instrument", "Piano")
    sync_written_key_instrument_anchor(st.session_state, instrument)
    try:
        from backing_musical_state import clear_stale_chart_session_keys
        from creative_key_sync import invalidate_creative_backing_context
        from songs.key_state import BACKING_NEEDS_REGEN, invalidate_backing_cache

        clear_stale_chart_session_keys(st.session_state)
        invalidate_creative_backing_context(st.session_state)
        invalidate_backing_cache(st)
        st.session_state[BACKING_NEEDS_REGEN] = True
    except Exception:
        pass
    _sync_canonical_active_song_after_edit()


def _on_transposing_subtype_change() -> None:
    _sync_canonical_active_song_after_edit()


def _render_sidebar_transposing_controls_compat(
    *,
    concert_key: str,
    instrument: str,
) -> None:
    """Call transposing sidebar controls; tolerate older instrument_transposition signatures."""
    import inspect

    kwargs: dict[str, Any] = {
        "st": st,
        "concert_key": concert_key,
        "instrument": instrument,
        "on_written_key_change": _on_written_key_checkbox_change,
        "on_transposing_type_change": _on_transposing_subtype_change,
    }
    supported = inspect.signature(render_sidebar_transposing_controls).parameters
    render_sidebar_transposing_controls(
        **{k: v for k, v in kwargs.items() if k in supported}
    )


def _on_global_instrument_change() -> None:
    # Re-validate Practice Focus against the new instrument's option
    # list so other pages don't render a focus that the new instrument
    # doesn't offer. Done via the canonical setter so the focus key
    # is *also* clamped before downstream code reads it on this rerun.
    from active_song_state import mark_active_song_local_edit
    from practice_setup_globals import set_active_instrument

    mark_active_song_local_edit(st.session_state)
    previous = st.session_state.get("_activity_last_logged_instrument") or st.session_state.get(
        "instrument"
    )
    new_value = st.session_state.get("instrument", "Piano")
    set_active_instrument(st.session_state, new_value, source="sidebar_on_change")
    sync_written_key_instrument_anchor(st.session_state, new_value)
    request_transposing_instrument_sync(st.session_state, new_value)
    try:
        from music_activity import log_instrument_changed

        log_instrument_changed(st, instrument=str(new_value), previous=str(previous or ""))
    except Exception:
        pass
    _sync_canonical_active_song_after_edit()


def _on_global_focus_change() -> None:
    from active_song_state import mark_active_song_local_edit
    from practice_setup_globals import set_active_focus

    mark_active_song_local_edit(st.session_state)
    set_active_focus(st.session_state, st.session_state.get("focus"), source="sidebar_on_change")
    _sync_canonical_active_song_after_edit()


def _on_global_level_change() -> None:
    from active_song_state import mark_active_song_local_edit
    from practice_setup_globals import set_active_level

    mark_active_song_local_edit(st.session_state)
    set_active_level(st.session_state, st.session_state.get("level"), source="sidebar_on_change")
    _sync_canonical_active_song_after_edit()


sidebar_section("Your practice setup", icon="🎸", tone="session")
st.sidebar.selectbox(
    "Instrument",
    _instrument_options,
    key="instrument",
    on_change=_on_global_instrument_change,
    help="Applies on every page — Practice, Backing Track, Song Selection.",
)
st.sidebar.selectbox(
    "Level",
    ["Beginner", "Intermediate", "Advanced"],
    key="level",
    on_change=_on_global_level_change,
    help="Applies on every page — controls arrangement length and harmonic detail.",
)
_focus_options = _sync_focus_options_before_widget(st.session_state.get("instrument", "Piano"))
st.sidebar.selectbox(
    "Practice focus",
    _focus_options,
    key="focus",
    on_change=_on_global_focus_change,
    help="Applies on every page — drives practice goals, suggestions, and video matching.",
)

sidebar_section("Music Coach", icon="🎵", tone="session")
try:
    from music_coach_context import (
        build_music_coach_context,
        build_source_state,
        resolve_coach_source_page,
    )
    from music_persistent_state import force_save_music_state
    from suite_analytical_question import render_music_coach_sidebar_entry

    _coach_page = resolve_coach_source_page(st.session_state)
    render_music_coach_sidebar_entry(
        st,
        source_page=_coach_page,
        session_state=st.session_state,
        developer_mode=_developer_mode_enabled(),
        context_extra_builder=lambda: build_music_coach_context(_coach_page, st.session_state),
        source_state_builder=lambda: build_source_state(_coach_page, st.session_state),
        on_after_send=lambda: force_save_music_state(st, reason="music_coach_send"),
    )
except Exception as exc:
    st.session_state["_music_coach_sidebar_error"] = str(exc)
    if _developer_mode_enabled():
        st.sidebar.warning(f"Music Coach sidebar unavailable: {type(exc).__name__}: {exc}")

try:
    render_sidebar_studio_nav(
        st.session_state,
        current_page=_studio_page,
        rerun_fn=st.rerun,
        ai_enabled=bool(_openai_api_key),
    )
except Exception:
    pass

try:
    from applied_math_return_insight import hydrate_applied_math_insight_for_session
    from music_persistent_state import force_save_music_state

    hydrate_applied_math_insight_for_session(st, "music")
    if st.session_state.pop("_suite_persist_insight_dirty", None):
        force_save_music_state(st, reason="insight_hydrate")
except Exception:
    pass

sidebar_section("Session", icon="⏱️", tone="session")
try:
    from practice_state import PRACTICE_MINUTES_DEFAULT, canonical_practice_filters, normalize_practice_minutes

    _canonical_practice = canonical_practice_filters(st.session_state) or {}
    _canonical_minutes = normalize_practice_minutes(_canonical_practice.get("practice_minutes"))
    if _canonical_minutes is not None:
        st.session_state["practice_minutes"] = _canonical_minutes
except Exception:
    PRACTICE_MINUTES_DEFAULT = 30
_display_minutes = normalize_practice_minutes(
    st.session_state.get("practice_minutes"),
    default=PRACTICE_MINUTES_DEFAULT,
)
st.sidebar.caption(
    f"**Practice length:** {_display_minutes} min "
    "(adjust on the **Practice** page)"
)

try:
    from music_sidebar_layout import render_sidebar_layout_dev_marker

    render_sidebar_layout_dev_marker(st)
except Exception:
    pass

pp.render_sidebar_toggle(st)

try:
    from music_persistence_trace import render_persistence_trace_sidebar

    render_persistence_trace_sidebar(st)
except Exception:
    pass

if _developer_mode_enabled():
    try:
        from app_ui import render_quick_nav_dev_diagnostics

        render_quick_nav_dev_diagnostics(st)
    except Exception:
        pass

    try:
        from widget_control_debug import render_widget_control_debug

        render_widget_control_debug(st, st.session_state)
    except Exception:
        pass

try:
    from suite_deploy_probe import render_music_deploy_probe

    render_music_deploy_probe(st)
except Exception:
    pass

note_active_source_change(st, invalidate_backing=invalidate_backing_cache)

_master_pk = (st.session_state.get("selected_song") or {}).get("pick_key")
if _master_pk:
    _mg, _ = parse_pick_key(_master_pk)
    st.session_state.setdefault("global_quick_genre", _mg)
    st.session_state.setdefault("global_quick_song", _master_pk)
else:
    st.session_state.setdefault("global_quick_genre", _catalog_genre)
    if "global_quick_song" not in st.session_state:
        _fallback_opts = _global_quick_songs_for_genre(_catalog_genre)
        if _fallback_opts:
            st.session_state["global_quick_song"] = _fallback_opts[0]

_apply_catalog_filter_defaults()

minutes = int(
    normalize_practice_minutes(st.session_state.get("practice_minutes"), default=30) or 30
)

instrument = st.session_state.get("instrument", "Piano")
_skip_catalog_sidebar_rehydrate = False
try:
    from backing_musical_state import should_skip_regular_song_defaults

    _skip_catalog_sidebar_rehydrate = should_skip_regular_song_defaults(st.session_state)
except ImportError:
    pass
try:
    from active_song_state import rehydrate_capo_from_canonical, rehydrate_transposing_sidebar_from_canonical

    rehydrate_transposing_sidebar_from_canonical(st.session_state)
    if not _skip_catalog_sidebar_rehydrate:
        rehydrate_capo_from_canonical(st.session_state)
except ImportError:
    pass
sync_written_key_instrument_anchor(st.session_state, instrument)
level = st.session_state.get("level", "Intermediate")
focus = st.session_state.get("focus", _focus_options[0])
display_key = st.session_state.get("display_key", original_key)
if display_key not in _display_key_options:
    try:
        from creative_key_sync import is_creative_major_jam_active

        _creative_key_mode = is_creative_major_jam_active(st.session_state)
    except Exception:
        _creative_key_mode = False
    try:
        from backing_musical_state import should_skip_regular_song_defaults
        from creative_key_sync import should_use_live_practice_key_sidebar

        _skip_song_key_clamp = should_skip_regular_song_defaults(
            st.session_state
        ) or should_use_live_practice_key_sidebar(st.session_state)
    except Exception:
        _skip_song_key_clamp = False
    if not (_creative_key_mode or _skip_song_key_clamp):
        display_key = (
            original_key
            if original_key in _display_key_options
            else _display_key_options[0]
        )
        request_display_key(st, display_key)
    elif display_key:
        request_display_key(st, display_key)
key_changed_this_run = note_display_key_change(st, display_key)
try:
    from songs.key_state import detect_display_key_split, trace_display_key_surface

    trace_display_key_surface(
        st.session_state,
        "sidebar",
        str(display_key or ""),
        source="sidebar_after_widget",
    )
    _display_key_split = detect_display_key_split(st.session_state)
    if _display_key_split:
        st.session_state["_display_key_split_trace"] = _display_key_split
except Exception:
    pass

apply_pending_transposing_instrument(st.session_state, instrument)
try:
    from practice_setup_controls import snapshot_global_control_values

    snapshot_global_control_values(st.session_state)
except Exception:
    pass
_render_sidebar_transposing_controls_compat(
    concert_key=display_key,
    instrument=instrument,
)

_key_ctx = resolve_practice_keys(st.session_state, display_key, instrument)
_chart_rec = (
    None
    if (_cpl_session_is_active(st.session_state) or is_custom_progression(st.session_state))
    else _catalog_song_data
)
_musical_ctx = resolve_active_musical_key(
    st.session_state,
    rec=_chart_rec,
    instrument=instrument,
    surface="app",
)
practice_concert_key = _musical_ctx.practice_concert_key
concert_key = practice_concert_key
chart_key = _musical_ctx.chart_key
shape_key = _musical_ctx.shape_key
global_display_key = practice_concert_key
chart_key_mode = _musical_ctx.chart_key_mode
written_key = _musical_ctx.written_key

if instrument == "Guitar":
    sidebar_section("Guitar Capo / Chord Shapes", icon="🎸", tone="session")
    render_guitar_capo_sidebar(
        st.sidebar,
        st.session_state,
        practice_display_key=display_key,
        persist_st=st,
    )

_guitar_capo_on = instrument == "Guitar" and bool(st.session_state.get(CAPO_ENABLED_KEY))
_chart_bundle_transpose_key = chart_bundle_transpose_key(
    instrument=instrument,
    capo_enabled=_guitar_capo_on,
    concert_key=concert_key,
    chart_key=chart_key,
)
_capo_shape_cache = (
    str(st.session_state.get(CAPO_SHAPE_KEY) or "").strip()
    if _guitar_capo_on
    else ""
)

_chart_bundle = session_cache_get_or_set(
    st.session_state,
    "chart_bundle",
    (
        st.session_state.get(ACTIVE_CATALOG_PICK_KEY),
        "custom" if cpl_session_is_active(st.session_state) else "catalog",
        str((st.session_state.get(CPL_ACTIVE_KEY) or {}).get("id", ""))
        if cpl_session_is_active(st.session_state)
        else "",
        str((st.session_state.get(CPL_ACTIVE_KEY) or {}).get("original_key_center", "")),
        str((st.session_state.get(CPL_ACTIVE_KEY) or {}).get("progression_style", "")),
        level,
        _chart_bundle_transpose_key,
        chart_key_mode,
        _capo_shape_cache,
        chart_transpose_cache_signature(st.session_state, instrument),
        st.session_state.get("_catalog_revision"),
        st.session_state.get("_user_chart_overrides_revision", 0),
        ((_catalog_song_data.get("user_override") or {}).get("saved_at")),
    ),
    lambda: build_active_chart_bundle(
        st.session_state,
        catalog_genre=_catalog_genre,
        catalog_song=_catalog_song,
        catalog_song_data=_catalog_song_data,
        level=level,
        display_key=_chart_bundle_transpose_key,
        cpl_active_key=CPL_ACTIVE_KEY,
        sections_for_level=sections_for_level,
        transpose_sections=transpose_sections,
    ),
    copy_result=True,
)
genre = _chart_bundle["genre"]
song = _chart_bundle["song"]
song_data = _chart_bundle["song_data"]
original_key = _chart_bundle["original_key"]
level_source_sections = _chart_bundle["level_source_sections"]
sections = _chart_bundle["sections"]
_cpl_active = _chart_bundle.get("cpl_active")

# Level-specific arrangement (chord complexity + section form). Beginner and
# Intermediate use shorter forms; Advanced keeps the full catalog chart.
# Keep transposed chords from the chart bundle — only apply level metadata/order.
_level_song_data, _ = resolve_level_chart(song_data, level)
if _level_song_data:
    song_data = _level_song_data
_level_order = list(song_data.get("section_order") or [])
if _level_order:
    sections = level_view_of_sections(sections, section_order_for_level=_level_order)

_capo_ctx = build_capo_context(
    st.session_state,
    sections,
    concert_key=concert_key,
    instrument=instrument,
)
if _capo_ctx.enabled and instrument == "Guitar":
    sections_for_practice = _capo_ctx.shape_sections
    sections_for_backing = _capo_ctx.sounding_sections
    guitar_shape_chart_key = _capo_ctx.shape_key
else:
    sections_for_practice = sections
    sections_for_backing = sections
    guitar_shape_chart_key = chart_key


def _ui_page_badges() -> list[tuple[str, str]]:
    badges = session_badges(
        source_label=_ui_source_label(),
        song=song,
        original_key=original_key,
        display_key=global_display_key,
        instrument=instrument,
        level=level,
        focus=focus,
        genre=genre if genre != "Custom" else "",
    )
    if chart_key_mode == "written" and is_transposing_instrument(instrument):
        badges.append((f"Concert {concert_key}", ""))
    return badges


full_song_chords = chord_blocks_for_backing(sections_for_backing)
_default_bpm = int(
    _chart_bundle.get("default_bpm") or canonical_active_song_bpm(song_data)
)
_default_groove = str(
    _chart_bundle.get("default_groove")
    or default_groove_for_song(song_data, infer_fn=infer_groove_style)
)
if cpl_session_is_active(st.session_state) and _cpl_active:
    from custom_progression_lab import cpl_default_groove_for_active

    _default_bpm = int(_cpl_active.get("bpm", _default_bpm) or _default_bpm)
    _default_groove = normalize_groove_label(
        cpl_default_groove_for_active(_cpl_active),
        song_data=song_data,
        infer_fn=infer_groove_style,
    )
_default_meter = default_time_signature_for_record(
    song_data,
    sections_for_backing,
    song_title=song,
)
if cpl_session_is_active(st.session_state) and _cpl_active:
    _default_meter = str(_cpl_active.get("time_signature") or _default_meter)
_playback_id = playback_song_id(
    is_custom=is_custom_progression(st.session_state),
    song_title=song,
    song_artist=str(song_data.get("artist", "")),
    custom_name=str(_cpl_active.get("name", "") if _cpl_active else ""),
    custom_revision=str(_cpl_active.get("id", "") if _cpl_active else ""),
)
_active_pick_key = str(st.session_state.get(ACTIVE_CATALOG_PICK_KEY) or (st.session_state.get("selected_song") or {}).get("pick_key") or "")
_bpm_sync_id = resolve_active_bpm_sync_id(
    st.session_state,
    song_title=str(song),
    song_artist=str(song_data.get("artist", "")),
    custom_name=str(_cpl_active.get("name", "") if _cpl_active else ""),
    custom_revision=str(_cpl_active.get("id", "") if _cpl_active else ""),
    is_custom=cpl_session_is_active(st.session_state),
    pick_key=_active_pick_key,
)
_synced_bpm, default_groove_style = sync_playback_defaults_for_active_song(
    st,
    song_id=_playback_id,
    default_bpm=_default_bpm,
    default_groove=_default_groove,
    song_data=song_data,
    infer_fn=infer_groove_style,
    pick_key=_active_pick_key,
    is_custom=cpl_session_is_active(st.session_state),
)
_default_song_bpm = _synced_bpm

song_lyrics_slug = _song_slug(
    song,
    song_data.get("artist", ""),
)
song_lyrics_key = f"song_lyrics::{song_lyrics_slug}"
section_lyrics_state_key = f"section_lyrics::{song_lyrics_slug}"

if pp.show_developer_sidebar(st):
    _render_sidebar_developer_library_panel()

from songs.user_lyrics_runtime import hydrate_user_lyrics_session, resolve_user_lyrics_and_cues
from songs.cpl_lyrics_runtime import render_cpl_lyrics_editor_panel

hydrate_user_lyrics_session(
    st.session_state,
    title=str(song_data.get("title", "")),
    artist=str(song_data.get("artist", "")),
)
section_lyrics, _user_cue_lists, _performance_notes = resolve_user_lyrics_and_cues(
    st.session_state,
    title=str(song_data.get("title", "")),
    artist=str(song_data.get("artist", "")),
    song_data=song_data,
    include_catalog_cues=bool(song_data.get("trusted_core")),
)
lyric_cues = dict(_user_cue_lists)
for _sec, _lines in lyric_cues_from_section_lyrics(section_lyrics).items():
    if _sec not in lyric_cues and _lines:
        lyric_cues[_sec] = _lines

_practice_bpm = int(st.session_state.get("backing_track_bpm", _default_song_bpm))
_practice_groove = str(
    st.session_state.get("practice_groove_style", default_groove_style)
)

if st.session_state.get("tutorial_open"):

    def _tutorial_navigate(page_id: str) -> None:
        from app_tutorial import TUTORIAL_STEP_KEY, close_tutorial, step_index_for_page

        idx = step_index_for_page(page_id)
        if idx is not None:
            st.session_state[TUTORIAL_STEP_KEY] = idx
        close_tutorial(st.session_state)
        navigate_studio_page(st.session_state, page_id)
        st.rerun()

    render_tutorial_walkthrough(
        st,
        st.session_state,
        rerun_fn=st.rerun,
        navigate_fn=_tutorial_navigate,
    )
    st.stop()

# Inject the pending scroll-to-section script *before* the page dispatch
# so it survives early ``st.stop()`` calls (e.g. picker with no song,
# fatal-error guards). The JS polls for the anchor element for ~3s, so
# rendering it before the destination markup is fine - the markup will
# appear during the same render and the polling will find it.
render_pending_scroll_script(st)

# Canonical quick nav — exactly once per script run, every page, before page body.
try:
    from app_ui import reset_quick_nav_render_diagnostics

    reset_quick_nav_render_diagnostics(st.session_state)
except Exception:
    pass

if pp.show_quick_nav(st):
    _studio_page = render_page_quick_nav(
        st.session_state,
        current_page=_studio_page,
        rerun_fn=st.rerun,
    )
    try:
        from local_nav_trace import record_local_nav_checkpoint

        record_local_nav_checkpoint(st, "post_quick_nav")
    except Exception:
        pass

if _developer_mode_enabled():
    try:
        from applied_math_return_insight import render_insight_sync_debug

        render_insight_sync_debug(st)
    except Exception:
        pass

# -------------------------------------------------
# PRACTICE
# -------------------------------------------------

if _studio_page == "practice":

    try:
        from practice_state import prepare_practice_page
        from global_active_song_state import prepare_global_active_song
        from music_ami_context import cache_music_ami_context

        prepare_global_active_song(st.session_state)
        prepare_practice_page(st.session_state)
        cache_music_ami_context(st.session_state, coach_page="practice")
    except Exception:
        pass
    ensure_page_initialized(st.session_state, "practice")
    try:
        from practice_state import prepare_practice_page

        prepare_practice_page(st.session_state)
    except Exception:
        pass
    note_page_visit(st.session_state, "practice")
    if pp.is_screenshot_mode(st) or pp.is_demo_mode(st):
        pp.render_hero_banner(
            st,
            "Active Song Practice Studio",
            "Adaptive practice sheets, section focus, chord charts, and backing tracks for your current song.",
        )
    pp.render_executive_summary(
        st,
        "Practice the active song with section-aware chord charts, tempo controls, and coaching cues.",
        "Turns song context into a focused practice session instead of generic exercises.",
        "Section selector, chord chart, practice cues, backing track integration, and key/instrument controls.",
    )
    inject_practice_page_styles(st)
    try:
        from app_ui import inject_studio_ui_release_marker

        inject_studio_ui_release_marker(st, page="practice")
    except Exception:
        pass
    if not pp.is_screenshot_mode(st) and not pp.is_demo_mode(st):
        _studio_page_header(
            "🎯",
            "Song Practice",
            "Set up your session below — change key in the sidebar; pick songs on Song Selection.",
            page_id="practice",
        )
    try:
        from backing_source_navigation import render_source_context_debug

        render_source_context_debug(st, st.session_state)
    except ImportError:
        pass
    try:
        from music_coach_context import (
            build_music_coach_context,
            build_source_state,
            resolve_coach_source_page,
        )
        from music_persistent_state import force_save_music_state
        from suite_analytical_question import render_music_coach_page_entry

        _practice_coach_page = resolve_coach_source_page(st.session_state)
        render_music_coach_page_entry(
            st,
            source_page=_practice_coach_page,
            session_state=st.session_state,
            developer_mode=_developer_mode_enabled(),
            context_extra_builder=lambda: build_music_coach_context(
                _practice_coach_page, st.session_state
            ),
            source_state_builder=lambda: build_source_state(
                _practice_coach_page, st.session_state
            ),
            on_after_send=lambda: force_save_music_state(st, reason="music_coach_send"),
        )
    except Exception as exc:
        st.session_state["_music_coach_page_error"] = str(exc)
        if _developer_mode_enabled():
            st.warning(f"Music Coach page panel unavailable: {type(exc).__name__}: {exc}")
    _inject_practice_toolkit_styles()

    render_scroll_anchor_marker(st, ANCHOR_PRACTICE_COACH)

    _section_choices = practice_section_options(sections)
    try:
        from practice_state import coerce_practice_focus_for_widget

        coerce_practice_focus_for_widget(st.session_state, _section_choices or None)
    except ImportError:
        if _section_choices and st.session_state.get("practice_focus_section") not in _section_choices:
            st.session_state["practice_focus_section"] = _section_choices[0]

    _practice_display_label_map: dict[str, str] = dict(
        (song_data or {}).get("_beginner_display_labels") or {}
    )

    def _display_section(name: str | None) -> str:
        if not name:
            return ""
        return _practice_display_label_map.get(str(name), str(name))

    def _section_focus_after_jump() -> None:
        _fp = st.session_state.get(
            "practice_focus_section",
            _section_choices[0] if _section_choices else "",
        )
        _act = (
            practice_active_section_name(_fp, sections_for_practice)
            if not practice_is_full_song(_fp)
            else None
        )
        _preview = sections_for_practice.get(_act) or [] if _act else []
        _render_practice_section_focus_details(
            focus_pick=_fp,
            sections_for_practice=sections_for_practice,
            display_section_fn=_display_section,
            transition_pairs=_practice_section_transition_pairs(_preview),
            prepare_backing_fn=_prepare_backing_from_practice,
        )

    _render_practice_setup_panel(
        instrument_options=_instrument_options,
        default_groove=default_groove_style,
        section_choices=_section_choices or None,
        section_focus_after_jump=_section_focus_after_jump if _section_choices else None,
    )

    _focus_pick = st.session_state.get("practice_focus_section", _section_choices[0] if _section_choices else "")
    # ``_focus_pick`` is the *selector value* (e.g. "Verse" - a type label).
    # ``_resolved_send_section`` is the *real chart key* used by panels
    # that need actual chord data (Send to Backing, notation, etc.).
    _resolved_send_section = (
        practice_active_section_name(_focus_pick, sections_for_practice)
        if not practice_is_full_song(_focus_pick)
        else None
    )
    _is_full_song = practice_is_full_song(_focus_pick)
    _active_section = practice_active_section_name(_focus_pick, sections_for_practice)
    _view_sections = practice_display_sections(sections_for_practice, _focus_pick)
    _view_chords = (
        all_chords_from_sections(_view_sections)
        if _is_full_song
        else list((_view_sections.get(_active_section) or []) if _active_section else [])
    )
    _time_sig = default_time_signature(song, sections_for_practice)
    _section_bar_count = len(_view_chords) if _active_section else 0

    # Visible safety net: the Section Focus selector exposes *type
    # labels* (e.g. "Verse"). Downstream panels need a *real* chart key
    # (e.g. "Verse 1"). If the resolver failed - either because the
    # type label has no matching section in the current arrangement,
    # or because the matching section has an empty chord list - we
    # warn instead of silently rendering empty deep-focus / rhythm-
    # guide / chord-chart panels.
    if (
        not _is_full_song
        and (not _active_section or not _view_chords)
    ):
        st.warning(
            "Section focus could not be resolved to a chart section with "
            "chords - the panels below may render empty until either the "
            "song's section keys are corrected or a different focus is "
            "picked."
        )
        if _developer_mode_enabled():
            _dev_keys = list(sections_for_practice.keys())
            _dev_types = [
                practice_section_type(n) for n in _dev_keys if n
            ]
            st.caption(
                "Developer Mode · focus resolver diagnostics — "
                f"selected focus = `{_focus_pick}` · "
                f"resolved section = `{_active_section or 'None'}` · "
                f"available sections = {_dev_keys} · "
                f"section types = {_dev_types}"
            )
    if _PRACTICE_STUDIO_IMPORT_ERROR is not None and _developer_mode_enabled():
        st.caption(
            f"Developer Mode · practice_studio import fell back: "
            f"`{type(_PRACTICE_STUDIO_IMPORT_ERROR).__name__}: "
            f"{_PRACTICE_STUDIO_IMPORT_ERROR}` - the section resolver "
            "may be running in degraded mode."
        )

    _NOTATION_KEY = "practice_notation_result"
    for _old_key in (
        "custom_practice_sheet",
        "custom_practice_sheet_payload",
        "custom_practice_sheet_sig",
        "practice_copy_sheet",
        "practice_download_sheet",
    ):
        st.session_state.pop(_old_key, None)

    _capo_shape = guitar_shape_chart_key if (_capo_ctx.enabled and instrument == "Guitar") else None
    _practice_chart_key = chart_key
    _chart_key_mode = chart_key_mode

    if _capo_ctx.enabled and instrument == "Guitar":
        st.markdown(capo_status_banner_html(_capo_ctx), unsafe_allow_html=True)

    # ``_display_section`` was defined near the top of the practice
    # dispatch with the section-focus picker. It collapses raw chart
    # keys ("Verse 1") to Beginner display labels ("Verse") - a no-op
    # outside Beginner mode. ``_active_section_display`` is the
    # resolved real section name in display form, used by every panel
    # header / badge / caption below.
    _active_section_display = _display_section(_active_section)
    _focus_chords = sections_for_practice.get(_active_section) or [] if _active_section else []

    _chart_current = None if _is_full_song else _active_section
    _practice_chart_sig = (
        song,
        _practice_chart_key,
        _chart_key_mode,
        chart_transpose_cache_signature(st.session_state, instrument),
        level,
        instrument,
        focus,
        _practice_groove,
        _practice_bpm,
        _time_sig,
        _chart_current or "full",
        tuple(sorted(_view_sections.keys())),
        sections_tuple_signature(_view_sections),
    )
    _chart_scope = "full song" if _is_full_song else (_active_section_display or "section")
    _chart_key_note = ""
    if _chart_key_mode == "written" and is_transposing_instrument(instrument):
        _t_type = selected_transposing_type(st.session_state, instrument)
        _chart_key_note = (
            f" · {instrument_display_name(_t_type, instrument)}"
            f" · written key **{_practice_chart_key}**"
        )

    _notation_sig = (
        song,
        _focus_pick,
        _active_section or "",
        instrument,
        focus,
        _practice_chart_key,
        _practice_bpm,
        _practice_groove,
        selected_saxophone_type(st.session_state) if is_transposing_instrument(instrument) else "",
        st.session_state.get(CHART_IN_INSTRUMENT_KEY_KEY, False),
        _capo_ctx.enabled,
        _capo_ctx.shape_key if _capo_ctx.enabled else "",
        _capo_ctx.capo_fret if _capo_ctx.enabled else 0,
    )
    if st.session_state.get("practice_notation_sig") != _notation_sig:
        st.session_state.pop(_NOTATION_KEY, None)
    st.session_state["practice_notation_sig"] = _notation_sig

    exercise_key = f"exercise_variation::{song}::{instrument}::{level}::{focus}"
    if exercise_key not in st.session_state:
        st.session_state[exercise_key] = 0

    st.markdown(
        '<p class="ui-practice-tools-kicker">Practice tools</p>',
        unsafe_allow_html=True,
    )
    (
        _tab_coach,
        _tab_timing,
        _tab_chart,
        _tab_lyrics,
        _tab_transpose,
        _tab_tone,
    ) = st.tabs(
        [
            "Coach",
            "Timing",
            "Chart / TAB",
            "Lyrics",
            "Transpose / Instrument",
            "Tuner, Tone & Metronome",
        ]
    )

    _metro_section_bars = _section_bar_count if (_active_section and not _is_full_song) else 0
    _metro_loop = bool(_active_section and not _is_full_song and _metro_section_bars > 0)

    with _tab_tone:
        render_tuner_tone_section(
            st,
            instrument=instrument,
            display_key=chart_key,
            key_prefix=tuner_key_prefix_for_song(song),
            metronome_bpm=_practice_bpm,
            metronome_signature=_time_sig,
            metronome_section_bars=_metro_section_bars,
            metronome_section_label=_active_section or "",
            metronome_loop_section=_metro_loop,
        )

    with _tab_timing:
        if _is_full_song:
            render_metronome_widget(
                st,
                default_bpm=_practice_bpm,
                default_signature=_time_sig,
            )
        elif _active_section:
            render_metronome_widget(
                st,
                default_bpm=_practice_bpm,
                default_signature=_time_sig,
                section_bars=_section_bar_count,
                section_label=_active_section,
                loop_section=True,
            )
        else:
            st.caption("Choose a section in **Section Focus** above for a section loop metronome.")
        if not _is_full_song and _active_section:
            _rhythm_md = ""
            _rhythm_error: Exception | None = None
            try:
                _rhythm_md = rhythm_guide_markdown(
                    instrument,
                    _practice_groove,
                    _time_sig,
                    song_data=song_data,
                ) or ""
            except Exception as _rhythm_exc:
                _rhythm_error = _rhythm_exc
            with st.expander("Rhythm guide", expanded=pp.expander_default(st)):
                if _rhythm_md.strip():
                    st.markdown(_rhythm_md)
                else:
                    st.info(
                        f"Lock to **{_practice_groove}** at **{_time_sig}** — "
                        "use the metronome and stay relaxed on beats 2 & 4."
                    )
                    if _developer_mode_enabled() and _rhythm_error is not None:
                        st.caption(
                            f"Developer Mode · rhythm guide: "
                            f"`{type(_rhythm_error).__name__}: {_rhythm_error}`"
                        )

    with _tab_coach:
        try:
            from song_coaching import build_song_coaching, coaching_markdown, coaching_scale_summary

            _song_coaching = build_song_coaching(
                song_data,
                sections_for_practice,
                instrument=instrument,
                level=level,
                practice_key=_practice_chart_key,
            )
            with st.expander("Song coach", expanded=pp.feature_expander_default(st, default=False)):
                st.markdown(coaching_markdown(_song_coaching))
            _coaching_scale_line = coaching_scale_summary(_song_coaching)
        except Exception:
            _song_coaching = {}
            _coaching_scale_line = ""

        if not _is_full_song and _active_section:
            # ----- Section Deep Focus -----------------------------------
        # ``section_deep_practice_markdown`` returns "No chords in
        # this section." when ``section_chords`` is empty - which to
        # the user *looks* like the panel is blank. Detect that
        # explicitly and render an actionable fallback instead.
            _deep_focus_md = ""
            _deep_focus_error: Exception | None = None
            try:
                _deep_focus_md = section_deep_practice_markdown(
                    section_name=_active_section,
                    section_chords=_focus_chords,
                    instrument=instrument,
                    level=level,
                    focus=focus,
                    display_key=_practice_chart_key,
                    bpm=_practice_bpm,
                    groove_style=_practice_groove,
                    song_data=song_data,
                ) or ""
            except Exception as _deep_focus_exc:
                _deep_focus_error = _deep_focus_exc
            with st.expander(
                f"Section deep focus — {_active_section_display}",
                expanded=pp.feature_expander_default(st, default=False),
            ):
                if _deep_focus_md.strip() and not _deep_focus_md.strip().lower().startswith(
                    "no chords"
                ):
                    st.markdown(_deep_focus_md)
                else:
                    st.info(
                        f"This section (**{_active_section_display}**) has no chord data "
                        "in the current chart. Pick **Full Song** above to see "
                        "the whole arrangement, or pick a different section."
                    )
                    if _developer_mode_enabled():
                        st.caption(
                            f"Developer Mode · deep focus diagnostics — "
                            f"section={_active_section!r} · "
                            f"chord_count={len(_focus_chords)} · "
                            f"instrument={instrument!r} · "
                            f"level={level!r} · "
                            f"focus={focus!r}"
                            + (
                                f" · error=`{type(_deep_focus_error).__name__}: "
                                f"{_deep_focus_error}`"
                                if _deep_focus_error is not None
                                else ""
                            )
                        )

            with st.expander(
                "Scales & approaches",
                expanded=pp.feature_expander_default(st, default=False),
            ):
                if _coaching_scale_line:
                    st.markdown(_coaching_scale_line)
                    st.caption("Chord-by-chord scale reference is in Chord Coach below.")
                elif _focus_chords:
                    _scales_rendered = 0
                    _scales_errors: list[tuple[str, Exception]] = []
                    _seen_scale_suggestions: set[str] = set()
                    _scale_chord_cache: dict[str, str] = {}
                    _scale_repeats = 0
                    _scale_unique_cap = 2
                    for ch in _focus_chords:
                        if _scales_rendered >= _scale_unique_cap:
                            break
                        ch_str = str(ch)
                        if ch_str in _scale_chord_cache:
                            _scale_md = _scale_chord_cache[ch_str]
                        else:
                            try:
                                _scale_md = scale_suggestions_for_chord(
                                    ch_str, _practice_chart_key, level, instrument
                                ) or ""
                            except Exception as _scales_exc:
                                _scales_errors.append((ch_str, _scales_exc))
                                _scale_chord_cache[ch_str] = ""
                                continue
                            _scale_chord_cache[ch_str] = _scale_md
                        _scale_key = _scale_md.strip()
                        if not _scale_key:
                            continue
                        if _scale_key in _seen_scale_suggestions:
                            _scale_repeats += 1
                            continue
                        _seen_scale_suggestions.add(_scale_key)
                        st.markdown(_scale_md)
                        _scales_rendered += 1
                    if _scales_rendered == 0:
                        st.info(
                            f"No scale suggestions matched the chords in "
                            f"**{_active_section_display}** for **{instrument}** at "
                            f"**{level}** level. Try a different section or "
                            "switch instruments in the sidebar."
                        )
                    elif _scale_repeats > 0:
                        st.caption(
                            "↻ Repeated through section — these chords loop, so the "
                            "same scale choices apply each time they come around."
                        )
                    if _developer_mode_enabled() and _scales_errors:
                        st.caption(
                            "Developer Mode · scales errors: "
                            + "; ".join(
                                f"{ch}: {type(exc).__name__}: {exc}"
                                for ch, exc in _scales_errors[:6]
                            )
                        )
                else:
                    st.info(
                        f"**{_active_section_display}** has no chords in the current "
                        "chart, so there's nothing to suggest scales over. "
                        "Pick **Full Song** above or choose a different section."
                    )

        with st.expander("Practice coach & session", expanded=pp.expander_default(st)):
            _coach_inst, _coach_lvl, _coach_focus = render_setup_quick_controls(
                st,
                session_state=st.session_state,
                key_prefix="practice_coach",
                instrument_options=_instrument_options,
                label="Instrument · level · focus",
                show_sync_caption=False,
            )
            st.caption(
                f"Session length: **{minutes} min** · chart key: **{global_display_key}**"
                + (
                    f" (concert **{concert_key}**)"
                    if _chart_key_mode == "written"
                    else " (concert key from sidebar)."
                )
            )
            _coach_exercise_key = (
                f"exercise_variation::{song}::{_coach_inst}::{_coach_lvl}::{_coach_focus}"
            )
            if _coach_exercise_key not in st.session_state:
                st.session_state[_coach_exercise_key] = st.session_state.get(exercise_key, 0)
            st.markdown(
                '<div class="ui-card soft"><div class="ui-card-title">Personalized coach exercise</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                song_practice_plan(
                    song,
                    _view_sections,
                    _coach_inst,
                    _coach_lvl,
                    _coach_focus,
                    st.session_state[_coach_exercise_key],
                    section_lyrics=section_lyrics,
                    minutes=minutes,
                    groove_override=_practice_groove,
                )
            )
            st.markdown("</div>", unsafe_allow_html=True)
            col_ex_a, col_ex_b = st.columns([1, 2])
            with col_ex_a:
                if st.button("🔄 New exercise", use_container_width=True):
                    st.session_state[_coach_exercise_key] += 1
                    st.rerun()
            with col_ex_b:
                st.caption("Rotates section targets and raises demand gradually.")

        _coach_from_picker = st.session_state.pop("picker_open_chord_coach", False)
        _coach_chords = _view_chords or all_chords_from_sections(sections)
        render_scroll_anchor_marker(st, ANCHOR_CHORD_COACH)
        with st.expander("Chord coach", expanded=_coach_from_picker):
            if _active_section:
                st.caption(f"Chords from **{_active_section_display}** only.")
            render_chord_coach_ui(
                _coach_chords,
                instrument,
                level,
                key_prefix=f"practice::{song}::{instrument}::{level}",
                expanded=False,
                display_key=_practice_chart_key,
            )

        with st.expander("Daily time breakdown", expanded=False):
            st.markdown(
                daily_practice_breakdown_markdown(
                    song,
                    sections,
                    instrument,
                    level,
                    focus,
                    minutes,
                    variation=st.session_state[exercise_key],
                    groove_override=_practice_groove,
                )
            )

        with st.expander("Full song ABC sketch (optional)", expanded=False):
            st.caption("Optional overview — not required for daily practice.")
            if st.button("Render full-song ABC sketch", key="practice_full_abc_sketch"):
                render_abc(build_abc(song, sections))

    with _tab_chart:
        _practice_chart_open = bool(st.session_state.get("practice_chart_panel_open", False))
        with st.expander(
            f"Chord chart — {_chart_scope}{_chart_key_note}",
            expanded=_practice_chart_open,
        ):
            if not _practice_chart_open:
                st.caption("Chord chart is hidden by default to keep the page responsive.")
                if st.button("Load chord chart", key="practice_chart_show_btn", type="secondary"):
                    st.session_state["practice_chart_panel_open"] = True
                    st.rerun()
            else:
                if st.button("Hide chord chart", key="practice_chart_hide_btn"):
                    st.session_state["practice_chart_panel_open"] = False
                    st.rerun()
                _chart_html = session_cache_get_or_set(
                    st.session_state,
                    "practice_chart_html",
                    _practice_chart_sig,
                    lambda: full_chord_markdown(
                        song,
                        song_data,
                        _view_sections,
                        instrument,
                        display_key=_practice_chart_key,
                        level=level,
                        lyric_cues=lyric_cues,
                        section_lyrics=section_lyrics,
                        groove_style=_practice_groove,
                        bpm=_practice_bpm,
                        time_signature=_time_sig,
                        current_section=_chart_current,
                        focus=focus,
                        chart_mode="practice",
                    ),
                )
                st.markdown(_chart_html, unsafe_allow_html=True)

                # When the user has picked a *type* (Verse / Chorus / ...) and
                # the song has more than one numbered version of that type
                # (Verse 1 / Verse 2 / Verse 3 ...), offer opt-in toggles for
                # the extra lyric versions. The chord progression doesn't
                # change between versions, so we only surface their lyrics -
                # keeps the main chart uncluttered.
                if not _is_full_song and _active_section:
                    _focus_type = practice_section_type(_focus_pick)
                    _same_type_sections = practice_sections_for_type(
                        sections_for_practice, _focus_type
                    )
                    _other_versions = [
                        n for n in _same_type_sections if n != _active_section
                    ]
                    _versions_with_lyrics = [
                        name
                        for name in _other_versions
                        if _lyric_lines_for_section(
                            name, lyric_cues, section_lyrics, limit=24
                        )
                    ]
                    if _versions_with_lyrics:
                        st.markdown(
                            '<p class="ui-extra-lyrics-kicker">Other '
                            f'{_html.escape(_focus_type or "section")} versions</p>',
                            unsafe_allow_html=True,
                        )
                        st.caption(
                            "Toggle any additional verse / chorus to add its lyrics below "
                            "the chord chart. The chord progression stays the same."
                        )
                        for _ov_name in _versions_with_lyrics:
                            _ov_key = (
                                f"practice_show_extra_lyrics::{song}::{_focus_type}::{_ov_name}"
                            )
                            _show_ov = st.checkbox(
                                f"Show {_ov_name} lyrics",
                                key=_ov_key,
                                value=False,
                            )
                            if _show_ov:
                                _ov_lines = _lyric_lines_for_section(
                                    _ov_name, lyric_cues, section_lyrics, limit=24
                                )
                                _ov_html_parts = [
                                    '<div class="ui-extra-lyrics-block">',
                                    '<p class="ui-extra-lyrics-section">'
                                    f"{_html.escape(_ov_name)}"
                                    "</p>",
                                ]
                                for _ln in _ov_lines:
                                    _ov_html_parts.append(
                                        '<p class="ui-extra-lyrics-line">'
                                        f"{_html.escape(_ln)}"
                                        "</p>"
                                    )
                                _ov_html_parts.append("</div>")
                                st.markdown(
                                    "\n".join(_ov_html_parts),
                                    unsafe_allow_html=True,
                                )

        with st.expander(
            "Notation / TAB",
            expanded=bool(st.session_state.get(_NOTATION_KEY)),
        ):
            _notation_section_label = (
                "Full Song"
                if _is_full_song
                else (_active_section_display or _focus_pick or "Section")
            )
            st.caption(
                f"Song **{song}** · section **{_notation_section_label}** · "
                f"instrument **{instrument}** · focus **{focus}** · {_practice_bpm} BPM"
                + (
                    f" · chart key **{_practice_chart_key}** (concert {display_key})"
                    if _chart_key_mode == "written"
                    else ""
                )
            )
            _n_col1, _n_col2, _n_col3 = st.columns([1, 1, 1])
            with _n_col1:
                _notation_lines = st.slider(
                    "Number of lines",
                    min_value=1,
                    max_value=4,
                    value=int(st.session_state.get("practice_notation_lines", 2)),
                    key="practice_notation_lines",
                    on_change=_on_practice_filter_change,
                )
            with _n_col2:
                _diff_opts = ["easy", "medium", "advanced"]
                _diff_default = st.session_state.get("practice_notation_difficulty", "medium")
                _notation_difficulty = st.selectbox(
                    "Difficulty",
                    options=_diff_opts,
                    index=_diff_opts.index(_diff_default) if _diff_default in _diff_opts else 1,
                    key="practice_notation_difficulty",
                    on_change=_on_practice_filter_change,
                )
            with _n_col3:
                st.write("")
                _gen_notation = st.button(
                    "Generate notation / TAB",
                    key="practice_generate_notation",
                    type="primary",
                    use_container_width=True,
                )

            if _gen_notation:
                # Pass the *resolved* real section name (e.g. "Verse 1") so
                # the notation generator can look up the actual chord list
                # in ``sections_for_practice``. Passing the type label
                # ("Verse") here used to silently fall back to a stub chart.
                _notation_section_focus = (
                    PRACTICE_FOCUS_FULL
                    if _is_full_song
                    else (_active_section or _focus_pick)
                )
                st.session_state[_NOTATION_KEY] = generate_practice_notation(
                    song_title=song,
                    artist=song_data.get("artist", ""),
                    display_key=_practice_chart_key,
                    original_key=original_key,
                    bpm=_practice_bpm,
                    groove_style=_practice_groove,
                    instrument=instrument,
                    focus=focus,
                    section_focus=_notation_section_focus,
                    sections=sections_for_practice,
                    guitar_tabs=song_data.get("guitar_tabs") or {},
                    num_lines=_notation_lines,
                    difficulty=_notation_difficulty,
                )
                st.rerun()

            _notation = st.session_state.get(_NOTATION_KEY)
            if _notation:
                st.markdown(f"**{getattr(_notation, 'title', 'Practice notation')}**")
                st.caption(
                    f"Chords: **{getattr(_notation, 'chord_labels', '')}** · "
                    f"{getattr(_notation, 'rhythm_counts', '')}"
                )
                if getattr(_notation, "format", "") == "tab":
                    st.markdown(notation_tab_html(_notation), unsafe_allow_html=True)
                    with st.expander("Copy TAB text", expanded=False):
                        st.code(getattr(_notation, "body", ""), language=None)
                else:
                    if getattr(_notation, "body", ""):
                        st.markdown("**Note guide**")
                        st.code(getattr(_notation, "body", ""), language=None)
                    if getattr(_notation, "abc", ""):
                        st.markdown("**Standard notation (ABC)**")
                        render_abc(getattr(_notation, "abc", ""))
                    with st.expander("ABC source", expanded=False):
                        st.code(getattr(_notation, "abc", ""), language=None)

    with _tab_transpose:
        render_practice_transposing_controls(
            st,
            concert_key=concert_key,
            instrument=instrument,
        )
        with st.expander("Transpose / capo helpers", expanded=False):
            render_general_transpose_helper(
                original_key,
                concert_key,
                sections,
                level_source_sections,
                key_prefix=f"practice::{song}",
            )
            if instrument == "Guitar":
                st.divider()
                render_guitar_capo_helper(
                    sections,
                    concert_key,
                    key_prefix=f"practice::{song}",
                    wrap_expander=False,
                )
            if is_transposing_instrument(instrument):
                st.divider()
                st.caption(
                    "Saxophone type and **Show chart in written key for instrument** are in the sidebar."
                )
            elif instrument == "Flute":
                st.divider()
                render_transposition_helper(
                    concert_key,
                    instrument,
                    key_prefix=f"practice::{song}",
                    wrap_expander=False,
                )

    with _tab_lyrics:
        _yt_practice_title = str(song_data.get("title") or song or "")
        _yt_practice_artist = str(song_data.get("artist") or "")
        if _yt_practice_title:
            _yt_practice_slug, _, _ = _lyrics_cues_session_keys(
                _yt_practice_title, _yt_practice_artist
            )
            render_practice_learning_video_panel(
                st,
                song_title=_yt_practice_title,
                artist=_yt_practice_artist,
                song_slug=_yt_practice_slug,
                instrument=str(instrument or ""),
                level=str(level or ""),
                focus=str(focus or ""),
                instrument_options=list(_instrument_options),
                level_options=["Beginner", "Intermediate", "Advanced"],
                expanded=False,
            )
        _render_jewish_traditional_lyrics_panel(song_data)
        if has_lyric_chord_sheet(song_data):
            _ug_sections = lyric_chord_chart_sections(song_data)
            if _ug_sections:
                with st.expander("Lyric & chord sheet", expanded=False):
                    st.markdown(
                        render_lyric_chord_sheet(
                            _ug_sections,
                            song_name=song,
                            artist=str(song_data.get("artist", "")),
                            original_key=song_data["key"],
                            display_key=_practice_chart_key,
                            current_section=_chart_current,
                            meta_bits=[
                                f"Level: {level}",
                                f"Time: {_time_sig}",
                            ],
                            header_note=str(
                                (song_data.get("extensions") or {}).get("arrangement_notes") or ""
                            ),
                            now_playing=_active_section_display if not _is_full_song else "Full song",
                            show_full=_is_full_song,
                        ),
                        unsafe_allow_html=True,
                    )
        try:
            from songs.vocal_showcase import (
                is_vocal_showcase as _is_vocal_showcase,
                vocal_showcase_harmony_blurb as _vocal_showcase_harmony_blurb,
            )
        except ImportError:
            _is_vocal_showcase = lambda _sd: False  # type: ignore[assignment,misc]
            _vocal_showcase_harmony_blurb = lambda _sd: ""  # type: ignore[assignment,misc]
        _vocal_showcase_song = _is_vocal_showcase(song_data)
        if _vocal_showcase_song:
            mod = (song_data.get("extensions") or {}).get("modulation") or {}
            mod_line = ""
            if mod.get("from_key") and mod.get("to_key"):
                mod_line = (
                    f" Key change **{mod.get('from_key')} → {mod.get('to_key')}** "
                    f"at **{mod.get('section', 'Key Change')}**."
                )
            if instrument != "Voice":
                st.info(
                    "**Vocal Showcase** — switch to **Voice** for phrasing cues, "
                    "karaoke setlist tools, and harmony-focused practice."
                    + mod_line
                )
            else:
                st.caption(
                    "Vocal Showcase · prioritize breath phrasing and blend; "
                    "backing stays light for singers."
                    + mod_line
                )
                _harmony_blurb = _vocal_showcase_harmony_blurb(song_data)
                if _harmony_blurb:
                    st.caption(_harmony_blurb)
        with st.expander(
            "Lyric phrasing guide",
            expanded=(instrument == "Voice" or _vocal_showcase_song),
        ):
            if _performance_notes:
                st.markdown(
                    f'<p class="ui-performance-notes"><strong>Your performance notes:</strong> '
                    f'{_html.escape(_performance_notes)}</p>',
                    unsafe_allow_html=True,
                )
            st.markdown(
                lyric_guide_html(
                    sections_for_practice,
                    lyric_cues,
                    instrument,
                    section_lyrics=section_lyrics,
                ),
                unsafe_allow_html=True,
            )

    st.caption("Deep harmony & improvisation → **Creative Lab** page.")

# -------------------------------------------------
# SONG PICKER
# -------------------------------------------------

elif _studio_page == "picker":

    ensure_page_initialized(st.session_state, "picker")
    note_page_visit(st.session_state, "picker")
    inject_song_picker_page_styles(st)
    try:
        from app_ui import inject_studio_page_marker_sync

        inject_studio_page_marker_sync(st, page="picker")
    except Exception:
        pass

    if pp.is_capture_mode(st):
        pp.render_hero_banner(
            st,
            "Song Library & Selection",
            "Search, filter, and browse the catalog — pick your active song and open practice or backing tracks.",
        )
        pp.render_executive_summary(
            st,
            "Browse and select songs from a searchable, filterable catalog with rich metadata cards.",
            "Gives every downstream tool — practice, backing, karaoke — a concrete song to work with.",
            "Song cards, genre filters, search, active-song picker, and optional chart/lyrics editor.",
        )
    elif km.is_voice_mode(st.session_state):
        _studio_page_header(
            "🎤",
            "Song Selection",
            "Pick songs in **Active Song**, use **Edit Song Chart** for chords, or build your **Karaoke Performance Setlist** below.",
        )
    else:
        _studio_page_header(
            "🎼",
            "Song Selection",
            "Choose a song from your library. The active song drives Practice, Backing Track, "
            "Creative Lab, Karaoke, and Upload/Multitrack. Use Edit Song Chart to customize "
            "chords, sections, and song structure.",
        )

    try:
        from backing_source_navigation import (
            hydrate_picker_source_for_page,
            render_source_context_debug,
        )

        hydrate_picker_source_for_page(
            st.session_state,
            st_like=st,
            song_picker_catalog=SONG_PICKER_CATALOG,
        )
        render_source_context_debug(st, st.session_state)
    except ImportError:
        pass

    _render_catalog_song_picker_block(
        show_source_toggle=True,
        filters_in_expander=False,
        wrap_section=False,
        show_song_cards=True,
    )

    # ---- Karaoke Performance Setlist (Voice-only) ----
    # Karaoke UI is strictly voice-only. Instrumentalists never see the
    # setlist on Song Selection - they get the standard musician
    # workflow (Practice / Backing Track / Creative Lab) instead.
    if km.is_voice_mode(st.session_state):
        from song_catalog import record_for_pick_key as _record_for_pick_key
        from songs.state import apply_pick_key as _apply_pick_key

        def _navigate_to_backing_for_karaoke() -> None:
            try:
                from backing_source_navigation import (
                    BACKING_INTENT_FROM_PRACTICE,
                    set_backing_open_intent,
                )

                set_backing_open_intent(st.session_state, BACKING_INTENT_FROM_PRACTICE)
            except ImportError:
                pass
            set_pending_anchor(st.session_state, ANCHOR_BACKING_MAIN_CONTROLS)
            navigate_studio_page(st.session_state, "backing")

        def _on_pick_setlist_song(pick_key: str) -> None:
            """Make the clicked setlist row the active editing/viewing song.

            ``apply_pick_key`` handles every downstream concern:

            * writes ``selected_song`` / ``ACTIVE_CATALOG_PICK_KEY`` /
              ``active_genre`` / ``active_song_title``,
            * primes the song's canonical BPM,
            * resets playback tracking + invalidates backing cache so
              the Backing Track page regenerates audio for this song,
            * queues the dropdown widget alignment for the next run.

            We deliberately do **not** touch:

            * the karaoke queue (queue order stays),
            * the karaoke session state (current session position,
              auto-advance, countdown, show-chords),
            * the active instrument / voice mode,
            * any session-state lyrics override map.
            """
            try:
                _apply_pick_key(st, pick_key, SONG_PICKER_CATALOG, song_library=SONG_LIBRARY)
            except Exception:
                # Fallback: at minimum mark the selection so the
                # picker / song card update on the next rerun.
                from song_catalog import parse_pick_key as _parse_pk
                try:
                    _g, _l = _parse_pk(pick_key)
                    _data = SONG_PICKER_CATALOG.get(_g, {}).get(_l) or {}
                    st.session_state["selected_song"] = {
                        "pick_key": pick_key,
                        "title": _data.get("title", ""),
                        "artist": _data.get("artist", ""),
                        "genre": _g,
                        "label": _l,
                    }
                    st.session_state["active_genre"] = _g
                    st.session_state["active_song_title"] = _data.get("title", "")
                    st.session_state[ACTIVE_CATALOG_PICK_KEY] = pick_key
                except Exception:
                    pass
            # Land the user on the Lyrics & Cues editor for the newly
            # active song - that's the most common reason to switch
            # the editing song mid-setlist (filling in lyrics for the
            # whole performance set). The page re-renders on rerun
            # with the new song card up top + editor pre-positioned.
            open_picker_editor(st.session_state, "Lyrics & Cues")

        render_karaoke_setlist_panel(
            st,
            record_for_pick_key=_record_for_pick_key,
            all_records=ALL_SONG_RECORDS,
            navigate_to_backing=_navigate_to_backing_for_karaoke,
            on_pick_song=_on_pick_setlist_song,
        )

    if not is_custom_progression(st.session_state):
        pick_key = st.session_state.get(ACTIVE_CATALOG_PICK_KEY)
        if not pick_key:
            st.stop()
        from song_catalog import format_pick_key as _format_pick_key
        from song_catalog import resolve_picker_catalog_selection

        pick_genre, pick_label, selected_data = resolve_picker_catalog_selection(
            str(pick_key),
            SONG_PICKER_CATALOG,
            records=ALL_SONG_RECORDS,
        )
        if not selected_data:
            st.stop()
        _resolved_pick_key = (
            _format_pick_key(pick_genre, pick_label)
            if pick_genre and pick_label
            else str(pick_key)
        )
        if _resolved_pick_key and st.session_state.get(ACTIVE_CATALOG_PICK_KEY) != _resolved_pick_key:
            apply_pick_key(
                st,
                _resolved_pick_key,
                SONG_PICKER_CATALOG,
                song_library=SONG_LIBRARY,
                skip_activity_log=True,
            )

        _picker_level_sections = sections_for_level(selected_data, level)
        if consume_open_lyrics_request(st.session_state):
            open_picker_editor(st.session_state, "Lyrics & Cues")
        consume_jump_to_chart_editor(st.session_state)

        _editor_open = bool(st.session_state.get(PICKER_EDITOR_OPEN_KEY, False))
        _editor_notice = st.session_state.get(PICKER_EDITOR_NOTICE_KEY) or {}
        if (
            _editor_notice.get("title") == selected_data.get("title")
            and _editor_notice.get("artist") == selected_data.get("artist")
        ):
            st.success(str(_editor_notice.get("message") or "Saved successfully."))
            _cap = str(_editor_notice.get("chart_caption") or "").strip()
            if _cap:
                st.caption(_cap)

        render_scroll_anchor_marker(st, ANCHOR_LYRICS_EDITOR)
        render_scroll_anchor_marker(st, ANCHOR_CHART_EDITOR)

        if not (pp.is_screenshot_mode(st) and not _editor_open):
            with st.container(border=True):
                st.markdown("#### Song content editor")
                if not _editor_open and not _editor_notice and not pp.is_capture_mode(st):
                    st.caption(
                        "Open **Lyrics & Cues** or **Edit Song Chart** from the active song card above when you want to edit."
                    )
                _editor_tab = st.radio(
                    "Editor section",
                    ["Lyrics & Cues", "Edit Song Chart"],
                    horizontal=True,
                    key=PICKER_EDITOR_TAB_KEY,
                    label_visibility="collapsed",
                )
                if st.button(
                    "Open editor" if not _editor_open else "Close editor",
                    key="picker_toggle_song_editor",
                    use_container_width=False,
                ):
                    st.session_state[PICKER_EDITOR_OPEN_KEY] = not _editor_open
                    if not _editor_open:
                        if _editor_tab == "Edit Song Chart":
                            st.session_state["chart_edit_mode"] = True
                            set_pending_anchor(st.session_state, ANCHOR_CHART_EDITOR)
                        else:
                            set_pending_anchor(st.session_state, ANCHOR_LYRICS_EDITOR)
                    else:
                        st.session_state["chart_edit_mode"] = False
                    st.rerun()

                if _editor_open:
                    if _editor_tab == "Lyrics & Cues":
                        _render_lyrics_and_cues_panel(
                            song_title=str(selected_data.get("title", "")),
                            song_artist=str(selected_data.get("artist", "")),
                            section_names=list(_picker_level_sections.keys()),
                            song_data=selected_data,
                            chart_sections=_picker_level_sections,
                            prominent=True,
                            module_globals=globals(),
                        )
                    else:
                        if not pp.is_capture_mode(st):
                            st.caption(chart_source_caption(selected_data))
                        render_chart_editor_panel(
                            st,
                            module_globals=globals(),
                            all_records=ALL_SONG_RECORDS,
                            song_data=selected_data,
                            genre=pick_genre,
                            level=level,
                            sections_for_level=sections_for_level,
                            invalidate_backing=invalidate_backing_cache,
                        )
                        if chart_key != selected_data.get("key") and not pp.is_capture_mode(st):
                            st.caption(
                                f"Practice and Backing use **{global_display_key}** "
                                f"(+{semitone_distance(selected_data.get('key', 'C'), chart_key)} semitones from catalog key)."
                            )

# -------------------------------------------------
# BACKING TRACK
# -------------------------------------------------

elif _studio_page == "backing":

    ensure_page_initialized(st.session_state, "backing")
    note_page_visit(st.session_state, "backing")
    try:
        from backing_source_navigation import hydrate_backing_source_for_page

        hydrate_backing_source_for_page(st.session_state, st_like=st)
    except ImportError:
        pass
    try:
        from backing_context import reconcile_backing_context_on_backing_page

        reconcile_backing_context_on_backing_page(st.session_state, st_like=st)
    except Exception:
        pass
    try:
        from backing_context import get_backing_context
        from creative_session_state import (
            creative_session_is_active,
            hydrate_creative_session_for_page,
            render_creative_session_diagnostic,
            resolve_creative_backing_sections,
            sync_creative_session_before_persist,
        )

        _backing_ctx_for_hydrate = get_backing_context(st.session_state)
        if _backing_ctx_for_hydrate is None or _backing_ctx_for_hydrate.source != "regular_song":
            hydrate_creative_session_for_page(st.session_state)
            if creative_session_is_active(st.session_state):
                sync_creative_session_before_persist(st.session_state)
                _creative_playback_sections = resolve_creative_backing_sections(st.session_state)
                if _creative_playback_sections:
                    sections_for_backing = _creative_playback_sections
        render_creative_session_diagnostic(st, st.session_state)
    except Exception:
        pass
    st.session_state.pop("_active_bpm_sync_id", None)
    st.session_state.pop("_backing_trace_sync_id", None)
    _song_bpm_sync_id = resolve_active_bpm_sync_id(
        st.session_state,
        song_title=str(song),
        song_artist=str(song_data.get("artist", "")),
        custom_name=str(_cpl_active.get("name", "") if _cpl_active else ""),
        custom_revision=str(_cpl_active.get("id", "") if _cpl_active else ""),
        is_custom=cpl_session_is_active(st.session_state),
        pick_key=str(st.session_state.get(ACTIVE_CATALOG_PICK_KEY) or ""),
    )
    _creative_backing_ctx = None
    try:
        from backing_context import (
            active_creative_backing_context,
            backing_page_sync_id,
            backing_page_transport_defaults,
        )

        _creative_backing_ctx = active_creative_backing_context(st.session_state)
        _bpm_sync_id = backing_page_sync_id(st.session_state, song_sync_id=_song_bpm_sync_id)
        _td_bpm, _td_groove, _td_meter = backing_page_transport_defaults(st.session_state)
        _backing_source_default_bpm = int(_td_bpm)
        _backing_source_default_groove = str(_td_groove)
        _backing_source_default_meter = str(_td_meter)
    except Exception:
        _bpm_sync_id = _song_bpm_sync_id
        _backing_source_default_bpm = int(_default_bpm)
        _backing_source_default_groove = str(_default_groove)
        _backing_source_default_meter = str(_default_meter)
    try:
        from backing_track_state import begin_backing_page_widget_phase

        begin_backing_page_widget_phase(st.session_state)
    except Exception:
        pass
    if pp.is_capture_mode(st):
        if km.is_voice_mode(st.session_state):
            pp.render_hero_banner(
                st,
                "Karaoke & Performance Mode",
                "Lyrics, chord follow-along, and backing playback for live vocal performance.",
            )
            pp.render_executive_summary(
                st,
                "Full-screen karaoke experience with lyrics, queue controls, and generated backing tracks.",
                "Demonstrates performance UX — not just practice tools — with song-aware playback.",
                "Lyric panel, performance controls, backing generation, style/BPM settings, and lead sheet.",
            )
        else:
            pp.render_hero_banner(
                st,
                "Backing Track Studio",
                "Arrangement controls, style settings, and one-click playback matched to your active song.",
            )
            pp.render_executive_summary(
                st,
                "Play AI-backed accompaniment aligned to chord charts and section scope in one click.",
                "Shows audio + music-theory product engineering beyond static chord sheets.",
                "BPM/groove/meter controls, section scope, play backing track, lead sheet, and coaching overlay.",
            )

    # === CANONICAL SONG DEFAULTS - single source of truth ===================
    # Runs BEFORE any backing widget renders. When the active song changes,
    # this force-resets BPM, groove, meter, and override flags so the active
    # song card numbers match what the playback engine consumes everywhere
    # (Playback setup, Quick BPM, chord-follow timing, lead sheet, etc.).
    _backing_canon = canonicalize_backing_defaults_for_song(
        st,
        sync_id=_bpm_sync_id,
        active_song_bpm=_backing_source_default_bpm,
        active_song_groove=_backing_source_default_groove,
        active_song_meter=_backing_source_default_meter,
    )
    _synced_bpm = int(_backing_canon["applied_bpm"])
    default_groove_style = str(_backing_canon["applied_groove"])
    _backing_song_just_reset = bool(_backing_canon["did_reset"])

    # Seed durable widget keys from canonical before Step 1 widgets render.
    # Practice handoff (_apply_pending_backing_scope) runs later and may override scope/loops.
    try:
        from backing_track_state import prepare_backing_durable_widgets

        st.session_state["_backing_trace_sync_id"] = _bpm_sync_id
        prepare_backing_durable_widgets(
            st.session_state,
            sync_id=_bpm_sync_id,
            default_bpm=_backing_source_default_bpm,
            default_groove=default_groove_style,
            default_meter=_backing_source_default_meter,
        )
    except Exception:
        pass
    try:
        from backing_track_state import enable_backing_user_edits

        enable_backing_user_edits(st.session_state)
    except Exception:
        pass
    try:
        from backing_track_state import snapshot_backing_path_trace

        snapshot_backing_path_trace(st)
    except Exception:
        pass

    if not pp.is_capture_mode(st):
        if km.is_voice_mode(st.session_state):
            _studio_page_header(
                "🎧",
                km.voice_wording("backing_page_title", voice=True),
                km.voice_wording("backing_page_subtitle", voice=True),
                page_id="backing",
            )
        else:
            _studio_page_header(
                "🎧",
                "Backing Track Studio",
                "Play accompaniment matched to your active song — then play along.",
                page_id="backing",
            )
        try:
            from backing_context_ui import (
                render_backing_context_banner,
                render_backing_context_dev_diagnostics,
                render_backing_context_reset,
            )

            render_backing_context_banner(st, st.session_state)
            render_backing_context_reset(st, st.session_state)
        except Exception:
            pass
        try:
            from backing_source_navigation import render_source_context_debug

            render_source_context_debug(st, st.session_state)
        except ImportError:
            pass
    # The voice-mode `data-vocal-focus="true"` body attribute is set
    # globally at app init (search for `dataset.vocalFocus` upstream),
    # so the larger-lyric / vocal-focused CSS automatically applies on
    # this page whenever the active instrument is Voice.

    from songs.music_source import custom_selected_song_record as _custom_selected_song_record

    if cpl_session_is_active(st.session_state) and _cpl_active:
        _backing_card_record = dict(_custom_selected_song_record(_cpl_active))
        _backing_card_record.update(
            {
                "title": str(_cpl_active.get("name") or song),
                "artist": "Custom progression",
                "genre": genre or "Custom",
                "key": str(_backing_card_record.get("key") or _cpl_active.get("original_key_center") or "C"),
            }
        )
    else:
        _backing_card_record = dict(song_data or _catalog_song_data or {})
    # Apply meter from canonical state (no separate apply_backing_meter_for_song
    # call - canonicalize_backing_defaults_for_song handled that already).
    _applied_meter_pre = str(_backing_canon["applied_meter"])
    _meter_override_pre = bool(
        st.session_state.get(BACKING_METER_OVERRIDE_KEY, False)
    )
    _render_v2_chart_debug_pill(_backing_card_record)
    _render_backing_defaults_verification_pill(
        sync_id=_bpm_sync_id,
        song_card_bpm=int(_default_bpm),
        applied_bpm=int(_synced_bpm),
        song_card_groove=str(_default_groove),
        applied_groove=str(default_groove_style),
        song_card_meter=str(_default_meter),
        applied_meter=str(_applied_meter_pre),
        meter_override=bool(_meter_override_pre),
        did_reset=bool(_backing_canon["did_reset"]),
    )
    from songs.music_source import cpl_session_is_active as _cpl_session_is_active

    _backing_musical = None
    try:
        from backing_musical_state import (
            render_backing_key_state_diagnostics,
            resolve_current_backing_musical_state,
        )

        _backing_musical = resolve_current_backing_musical_state(
            st.session_state,
            rec=_backing_card_record,
            applied_bpm=_synced_bpm,
            sync_id=_bpm_sync_id,
            song_sync_id=_song_bpm_sync_id,
        )
        _backing_orig_key = str(_backing_card_record.get("key") or "C")
        _backing_practice_key = _backing_musical.practice_concert_key
        _backing_written_key = (
            _backing_musical.chart_badge_value if _backing_musical.show_chart_badge else ""
        )
        if _developer_mode_enabled():
            render_backing_key_state_diagnostics(st, st.session_state, _backing_musical)
    except Exception:
        from songs.key_state import resolve_active_musical_key as _resolve_active_musical_key

        _backing_mk = _resolve_active_musical_key(
            st.session_state,
            rec=_backing_card_record,
            surface="backing_card",
        )
        _backing_orig_key = _backing_mk.original_key
        _backing_practice_key = _backing_mk.practice_concert_key
        _backing_written_key = _backing_mk.shape_key or (
            _backing_mk.written_key if _backing_mk.chart_key_mode == "written" else ""
        )
    _backing_written_key = str(_backing_written_key or "").strip()
    _backing_source_label = (
        "Custom Progression"
        if _cpl_session_is_active(st.session_state)
        else "Catalog song"
    )
    try:
        from backing_context import (
            active_creative_backing_context,
            get_backing_context,
            sections_dict_for_chart_display,
            sections_dict_from_backing_context,
        )
        from backing_context_ui import (
            render_backing_creative_context_card,
            render_backing_custom_progression_context_card,
        )

        if _creative_backing_ctx is None:
            _creative_backing_ctx = active_creative_backing_context(st.session_state)
        _backing_ctx_for_card = get_backing_context(st.session_state)
        if _creative_backing_ctx is not None:
            if _backing_musical is None:
                try:
                    from backing_musical_state import resolve_current_backing_musical_state

                    _backing_musical = resolve_current_backing_musical_state(
                        st.session_state,
                        rec=None,
                        applied_bpm=_synced_bpm,
                        sync_id=_bpm_sync_id,
                        song_sync_id=_song_bpm_sync_id,
                    )
                    _backing_practice_key = _backing_musical.practice_concert_key
                    _backing_written_key = (
                        _backing_musical.chart_badge_value if _backing_musical.show_chart_badge else ""
                    )
                except Exception:
                    pass
            else:
                _backing_musical = resolve_current_backing_musical_state(
                    st.session_state,
                    rec=None,
                    applied_bpm=_synced_bpm,
                    sync_id=_bpm_sync_id,
                    song_sync_id=_song_bpm_sync_id,
                )
                _backing_practice_key = _backing_musical.practice_concert_key
                _backing_written_key = (
                    _backing_musical.chart_badge_value if _backing_musical.show_chart_badge else ""
                )
            if _backing_musical and _backing_musical.concert_sections:
                sections_for_backing = _backing_musical.concert_sections
            else:
                _creative_sections_concert = sections_dict_from_backing_context(
                    st.session_state,
                    _creative_backing_ctx,
                )
                if _creative_sections_concert:
                    sections_for_backing = _creative_sections_concert
            render_backing_creative_context_card(
                st,
                _creative_backing_ctx,
                st.session_state,
                applied_bpm=_synced_bpm,
                applied_groove=default_groove_style,
                applied_meter=_applied_meter_pre,
                practice_key=_backing_practice_key,
                written_key=_backing_written_key,
                musical_state=_backing_musical,
            )
            try:
                from backing_context_ui import render_backing_edit_source_action

                def _backing_edit_source_navigate() -> None:
                    from backing_source_navigation import prepare_return_to_backing_source
                    from studio_page_persistence import save_page_snapshot

                    save_page_snapshot(st.session_state, "backing")
                    save_page_snapshot(st.session_state, "creative")
                    target = prepare_return_to_backing_source(st.session_state)
                    navigate_studio_page(st.session_state, target)
                    st.rerun()

                render_backing_edit_source_action(
                    st,
                    st.session_state,
                    _creative_backing_ctx,
                    on_navigate=_backing_edit_source_navigate,
                )
            except Exception:
                pass
        elif (
            _backing_ctx_for_card is not None
            and _backing_ctx_for_card.source == "custom_progression"
        ):
            render_backing_custom_progression_context_card(
                st,
                _backing_ctx_for_card,
                st.session_state,
                applied_bpm=_synced_bpm,
                applied_groove=default_groove_style,
                applied_meter=_applied_meter_pre,
                practice_key=_backing_practice_key,
                written_key=_backing_written_key,
            )
        else:
            render_backing_active_song_card(
                st,
                _backing_card_record,
                level=level,
                applied_bpm=_synced_bpm,
                song_default_bpm=int(_default_bpm),
                applied_groove=default_groove_style,
                applied_meter=_applied_meter_pre,
                original_key=_backing_orig_key,
                practice_key=_backing_practice_key,
                source_label=_backing_source_label,
                written_key=_backing_written_key,
            )
            if st.button(
                "🎵 Return to Catalog Song",
                key="backing_go_catalog_song_btn",
                use_container_width=False,
            ):
                set_pending_anchor(st.session_state, ANCHOR_CHOOSE_ACTIVE_SONG)
                navigate_studio_page(st.session_state, "picker")
                st.rerun()
    except Exception as _backing_card_err:
        if _developer_mode_enabled():
            st.caption(f"Developer · backing card render: {_backing_card_err}")
        render_backing_active_song_card(
            st,
            _backing_card_record,
            level=level,
            applied_bpm=_synced_bpm,
            song_default_bpm=int(_default_bpm),
            applied_groove=default_groove_style,
            applied_meter=_applied_meter_pre,
            original_key=_backing_orig_key,
            practice_key=_backing_practice_key,
            source_label=_backing_source_label,
            written_key=_backing_written_key,
        )
    if _developer_mode_enabled() and _creative_backing_ctx is not None:
        try:
            from backing_context_ui import render_backing_context_dev_diagnostics

            render_backing_context_dev_diagnostics(
                st,
                st.session_state,
                skipped_song_defaults=bool(_backing_canon.get("skipped_for_creative_context")),
            )
        except Exception:
            pass

    inject_backing_studio_styles(st)
    try:
        from app_ui import inject_studio_ui_release_marker

        inject_studio_ui_release_marker(st, page="backing")
    except Exception:
        pass
    if _developer_mode_enabled():
        try:
            from app_ui import BACKING_STUDIO_UI_VERSION as _bs_ui_ver

            st.caption(f"Developer · Backing Studio UI `{_bs_ui_ver}` loaded")
        except Exception:
            pass

    _creative_section_names = (
        list(sections_for_backing.keys()) if _creative_backing_ctx and sections_for_backing else None
    )
    _sec_names = [
        name
        for name, chs in section_order(
            sections_for_backing,
            section_names=_creative_section_names or section_names_from_song(song_data),
        )
        if chs
    ]
    _from_practice_section = _apply_pending_backing_scope(st.session_state, _sec_names)
    _backing_audio_ready_pre = bool(st.session_state.get("_last_backing_wav"))

    backing_time_signature = str(
        st.session_state.get("backing_time_signature", _default_meter)
    )
    _meter_override = bool(st.session_state.get("backing_time_signature_override", False))
    selected_section_names: list[str] = []
    form_loops = int(st.session_state.get("backing_track_loops", 2))

    playback_scope = st.session_state.get("backing_track_scope", "Full song")
    if playback_scope == "Single section":
        selected_section_names = [
            st.session_state.get("backing_track_single_section", "")
        ]
        selected_section_names = [n for n in selected_section_names if n in _sec_names]
    elif playback_scope == "Multiple selected sections":
        selected_section_names = list(
            st.session_state.get("backing_track_multi_sections") or []
        )
    else:
        selected_section_names = []

    selected_section_names = selected_section_names or []
    groove_style = st.session_state.get("backing_groove_style", "Auto")
    resolved_groove = infer_groove_style(song_data, groove_style)
    _humanize_level = "Strong"
    _preserve_exact_timing = bool(st.session_state.get(BACKING_PRESERVE_EXACT_KEY, False))
    _humanize_song_data = song_data
    if _creative_backing_ctx is not None:
        _humanize_song_data = {
            "title": str(_creative_backing_ctx.style or _creative_backing_ctx.song_title or "Creative"),
            "id": str(_creative_backing_ctx.source_signature or "creative"),
        }
    if not _preserve_exact_timing:
        st.session_state[BACKING_HUMANIZE_LEVEL_KEY] = _humanize_level
    performed_sections, _hri_annotations = _humanized_backing_sections(
        sections_for_backing,
        song_data=_humanize_song_data,
        groove_style=resolved_groove,
        time_signature=backing_time_signature,
        humanize_level=_humanize_level,
        preserve_exact_timing=_preserve_exact_timing,
        section_lyrics=section_lyrics,
        lyric_cues=lyric_cues,
    )
    st.session_state["_backing_hri_annotations"] = _hri_annotations

    backing_chords = chord_blocks_for_selected_sections(
        performed_sections, selected_section_names, song_data=song_data
    )
    backing_events = chord_events_for_selected_sections(
        performed_sections, selected_section_names, song_data=song_data
    )
    if not backing_chords and _creative_backing_ctx is not None:
        try:
            from creative_session_state import resolve_creative_backing_sections

            _fallback_sections = resolve_creative_backing_sections(st.session_state)
            if _fallback_sections:
                _fb_performed, _ = _humanized_backing_sections(
                    _fallback_sections,
                    song_data=_humanize_song_data,
                    groove_style=resolved_groove,
                    time_signature=backing_time_signature,
                    humanize_level=_humanize_level,
                    preserve_exact_timing=_preserve_exact_timing,
                    section_lyrics=section_lyrics,
                    lyric_cues=lyric_cues,
                )
                backing_chords = chord_blocks_for_selected_sections(
                    _fb_performed, selected_section_names, song_data=song_data
                )
                backing_events = chord_events_for_selected_sections(
                    _fb_performed, selected_section_names, song_data=song_data
                )
        except Exception:
            pass
    if not backing_chords:
        st.warning("Choose at least one section to generate a backing track.")
    section_scope_label = (
        "full form"
        if not selected_section_names
        else " + ".join(selected_section_names)
    )
    backing_time_signature = str(
        st.session_state.get("backing_time_signature", backing_time_signature)
    )

    _audio_signature_key = (
        _backing_musical.practice_concert_key
        if _backing_musical is not None and _creative_backing_ctx is not None
        else chart_key
    )

    def _backing_signature_for_bpm(bpm_val: int) -> tuple:
        return (
            song,
            _audio_signature_key,
            level,
            resolved_groove,
            int(bpm_val),
            backing_time_signature,
            form_loops,
            tuple(selected_section_names),
            _humanize_level,
            _preserve_exact_timing,
            tuple(backing_chords),
        )

    render_scroll_anchor_marker(st, ANCHOR_BACKING_MAIN_CONTROLS)
    _lock_creative_style_meter = False
    _locked_creative_style = default_groove_style
    _locked_creative_meter = _backing_source_default_meter
    if _creative_backing_ctx is not None and _creative_backing_ctx.source == "entry_jam":
        try:
            from creative_key_sync import is_creative_major_jam_active

            _lock_creative_style_meter = is_creative_major_jam_active(st.session_state)
            _locked_creative_style = str(_creative_backing_ctx.style or default_groove_style)
            _locked_creative_meter = str(_creative_backing_ctx.meter or _backing_source_default_meter)
        except ImportError:
            pass
    bpm, _play_clicked = _render_backing_step2_playback_action(
        song_id=_bpm_sync_id,
        default_bpm=_backing_source_default_bpm,
        default_groove=default_groove_style,
        default_meter=_backing_source_default_meter,
        song_data=song_data,
        section_names=_sec_names,
        backing_chords=backing_chords,
        section_scope_label=section_scope_label,
        song_title=str(song),
        signature_for_bpm=_backing_signature_for_bpm,
        song_just_reset=_backing_song_just_reset,
        lock_style_meter=_lock_creative_style_meter,
        locked_style=_locked_creative_style,
        locked_meter=_locked_creative_meter,
    )
    _current_backing_signature = _backing_signature_for_bpm(bpm)
    _backing_audio_ready = bool(
        st.session_state.get("_last_backing_wav")
        and st.session_state.get("_last_backing_signature") == _current_backing_signature
    )

    _leadsheet_open = bool(st.session_state.get("backing_lead_sheet_open", False))

    # Karaoke session UI — collapsed by default; skip controls stay visible when
    # a session is active (JS auto-advance needs the skip button in the DOM).
    _karaoke_session_ui = (
        km.is_voice_mode(st.session_state) and km.is_karaoke_session_active(st.session_state)
    )
    if _karaoke_session_ui or km.is_voice_mode(st.session_state):
        with st.expander("Karaoke session", expanded=_karaoke_session_ui):
            render_karaoke_now_singing_banner(st)
            render_karaoke_status_pill(st)
            if _karaoke_session_ui:
                from song_catalog import record_for_pick_key as _record_for_pick_key

                render_karaoke_queue_preview(
                    st,
                    record_for_pick_key=_record_for_pick_key,
                    all_records=ALL_SONG_RECORDS,
                    max_upcoming=3,
                )
    if _karaoke_session_ui:
        from song_catalog import record_for_pick_key as _record_for_pick_key

        render_karaoke_skip_controls(
            st,
            record_for_pick_key=_record_for_pick_key,
            all_records=ALL_SONG_RECORDS,
        )

    with st.expander("Playback range & loops", expanded=False):
        _render_backing_playback_setup_panel(
            section_names=_sec_names,
            from_practice_handoff=_from_practice_section,
            backing_ready=_backing_audio_ready_pre,
        )

    # Voice mode: when the active karaoke song has no lyric cues yet,
    # surface a friendly "Add lyrics" prompt so the singer can fill them
    # in before performing. The CTA only renders for Voice / Vocals /
    # Singer; instrument mode never sees it.
    def _open_lyrics_editor_from_backing() -> None:
        set_pending_anchor(st.session_state, ANCHOR_LYRICS_EDITOR)
        navigate_studio_page(st.session_state, "picker")
        st.rerun()

    render_karaoke_missing_lyrics_cta(
        st,
        song_data=song_data,
        active_song_title=str(song_data.get("title") or song),
        on_open_editor=_open_lyrics_editor_from_backing,
    )
    if _developer_mode_enabled():
        render_backing_defaults_debug(
            st,
            song_bpm=_default_bpm,
            applied_bpm=_synced_bpm,
            song_groove=_default_groove,
            applied_groove=default_groove_style,
            song_meter=_default_meter,
            applied_meter=_applied_meter_pre,
            meter_override=_meter_override_pre,
            developer_mode=_developer_mode_enabled(),
        )
        render_backing_generation_debug(
            st,
            profile=st.session_state.get("_backing_last_gen_profile"),
            developer_mode=_developer_mode_enabled(),
        )

    if _capo_ctx.enabled and instrument == "Guitar":
        st.markdown(capo_status_banner_html(_capo_ctx), unsafe_allow_html=True)

    if not pp.skip_heavy_work(st) and (key_changed_this_run or st.session_state.get(BACKING_NEEDS_REGEN)):
        _regen_reasons = []
        if st.session_state.get(BACKING_METER_OVERRIDE_KEY):
            _regen_reasons.append(
                f"meter changed to **{st.session_state.get(BACKING_METER_KEY, _default_meter)}**"
            )
        if key_changed_this_run:
            _regen_reasons.append("key changed")
        _reason_text = (
            " (" + ", ".join(_regen_reasons) + ")" if _regen_reasons else ""
        )
        st.warning(
            f"Playback settings changed{_reason_text} - press **Play Backing Track** above "
            "to rebuild the backing track in the new settings."
        )

    chart_display_key = chart_key
    chart_sections = performed_sections
    if _creative_backing_ctx is not None and _backing_musical is not None:
        chart_display_key = _backing_musical.chart_display_key or chart_key
        if _backing_musical.chart_sections:
            chart_sections, _ = _humanized_backing_sections(
                _backing_musical.chart_sections,
                song_data=_humanize_song_data,
                groove_style=resolved_groove,
                time_signature=backing_time_signature,
                humanize_level=_humanize_level,
                preserve_exact_timing=_preserve_exact_timing,
                section_lyrics=section_lyrics,
                lyric_cues=lyric_cues,
            )

    coach_section = (
        selected_section_names[0]
        if selected_section_names
        else next(
            (
                name
                for name, chs in section_order(
                    chart_sections,
                    section_names=section_names_from_song(song_data),
                )
                if chs
            ),
            "",
        )
    )
    coach_chords = chart_sections.get(coach_section, []) if coach_section else []

    if coach_chords:
        with st.expander(
            f"💡 Quick coaching — {coach_section}",
            expanded=False,
        ):
            st.markdown(
                _section_overlay(
                    instrument,
                    focus,
                    coach_chords,
                    section_name=coach_section,
                    groove_style=resolved_groove,
                    time_signature=default_time_signature(song, chart_sections),
                    bpm=bpm,
                ),
                unsafe_allow_html=True,
            )

    _follow_key_prefix = (
        f"backing::{song}::{tuple(selected_section_names)}::"
        f"{_audio_signature_key}::{bpm}::{form_loops}"
    )

    # Karaoke auto-generate: when a transition flips the active song in a
    # karaoke set, the new song has no backing audio yet. Consume the
    # one-shot flag and proceed exactly as if the user had clicked
    # Generate, so the singer never has to click between songs.
    # Voice-only: instrumentalists never auto-generate from a karaoke flag.
    _karaoke_auto_gen = False
    if km.is_voice_mode(st.session_state) and km.consume_pending_auto_generate(st.session_state):
        if backing_chords and not _backing_audio_ready:
            _karaoke_auto_gen = True

    _play_needs_generate = bool(_play_clicked and not _backing_audio_ready)

    if _play_needs_generate or _karaoke_auto_gen:
        try:
            from backing_musical_state import (
                preserve_backing_musical_keys_after_generate,
                resolve_current_backing_musical_state,
            )

            _gen_musical = resolve_current_backing_musical_state(
                st.session_state,
                rec=song_data if _creative_backing_ctx is None else None,
                applied_bpm=bpm,
                sync_id=_bpm_sync_id,
                song_sync_id=_song_bpm_sync_id,
            )
            if _gen_musical.creative_active and _gen_musical.concert_sections:
                performed_sections, _hri_annotations = _humanized_backing_sections(
                    _gen_musical.concert_sections,
                    song_data=_humanize_song_data,
                    groove_style=resolved_groove,
                    time_signature=backing_time_signature,
                    humanize_level=_humanize_level,
                    preserve_exact_timing=_preserve_exact_timing,
                    section_lyrics=section_lyrics,
                    lyric_cues=lyric_cues,
                )
                st.session_state["_backing_hri_annotations"] = _hri_annotations
                backing_chords = chord_blocks_for_selected_sections(
                    performed_sections, selected_section_names, song_data=song_data
                )
                backing_events = chord_events_for_selected_sections(
                    performed_sections, selected_section_names, song_data=song_data
                )
                bpm = int(_gen_musical.applied_bpm)
                _audio_signature_key = _gen_musical.practice_concert_key
                _current_backing_signature = _backing_signature_for_bpm(bpm)
                if _gen_musical.chart_sections:
                    chart_sections, _ = _humanized_backing_sections(
                        _gen_musical.chart_sections,
                        song_data=_humanize_song_data,
                        groove_style=resolved_groove,
                        time_signature=backing_time_signature,
                        humanize_level=_humanize_level,
                        preserve_exact_timing=_preserve_exact_timing,
                        section_lyrics=section_lyrics,
                        lyric_cues=lyric_cues,
                    )
                    chart_display_key = _gen_musical.chart_display_key or chart_display_key
            preserve_backing_musical_keys_after_generate(st, st.session_state, _gen_musical)
        except Exception:
            pass
        st.session_state[BACKING_TRANSPORT_STATUS] = "generating"
        record_backing_timing_event(
            st.session_state,
            "generate_start",
            signature=_current_backing_signature,
        )
        _gen_profile = BackingGenProfile(bar_count=len(backing_events) * max(1, form_loops))
        _gen_t0 = time.perf_counter()
        _session_wav_hit = False
        _cached_session_wav = None
        if (
            st.session_state.get("_last_backing_signature") == _current_backing_signature
            and st.session_state.get("_last_backing_wav")
        ):
            _cached_session_wav = st.session_state["_last_backing_wav"]
            _session_wav_hit = True
        with st.spinner("Generating backing track…"):
            _tl_t0 = time.perf_counter()
            timeline, _tl_hit = _cached_backing_timeline(
                _current_backing_signature,
                backing_events=backing_events,
                bpm=bpm,
                loops=form_loops,
                time_signature=backing_time_signature,
            )
            _gen_profile.timeline_ms = profile_elapsed_ms(_tl_t0)
            _gen_profile.cache_hit_timeline = _tl_hit

            if _cached_session_wav is not None:
                wav = _cached_session_wav
                _wav_hit = True
                _gen_profile.synthesis_ms = 0.0
                _gen_profile.cache_hit_wav = True
            else:
                _syn_t0 = time.perf_counter()
                wav, _wav_hit = _cached_backing_wav(
                    _current_backing_signature,
                    backing_events=backing_events,
                    bpm=bpm,
                    loops=form_loops,
                    style=resolved_groove,
                    level=level,
                    song_title=str(song_data.get("title", song)),
                    song_artist=str(song_data.get("artist", "")),
                    time_signature=backing_time_signature,
                )
                _gen_profile.synthesis_ms = profile_elapsed_ms(_syn_t0)
                _gen_profile.cache_hit_wav = _wav_hit
            _gen_profile.wav_kb = len(wav) / 1024.0

            st.session_state[BACKING_TRANSPORT_STATUS] = "preparing"
            _b64, _b64_ms, _b64_hit = prepare_wav_b64(
                st.session_state, _current_backing_signature, wav
            )
            _gen_profile.b64_ms = _b64_ms
            _gen_profile.cache_hit_b64 = _b64_hit

        _gen_profile.total_ms = profile_elapsed_ms(_gen_t0)
        st.session_state["_backing_last_gen_profile"] = _gen_profile.as_dict()
        record_backing_timing_event(
            st.session_state,
            "generate_complete",
            signature=_current_backing_signature,
            extra={
                "session_cache_hit": _session_wav_hit,
                "module_cache_hit_wav": bool(_gen_profile.cache_hit_wav and not _session_wav_hit),
                "module_cache_hit_timeline": _gen_profile.cache_hit_timeline,
                "module_cache_hit_b64": _gen_profile.cache_hit_b64,
                "total_ms": round(_gen_profile.total_ms, 1),
            },
        )
        st.session_state["_last_backing_wav_b64"] = _b64

        st.session_state["_last_backing_wav"] = wav
        st.session_state["_last_backing_signature"] = _current_backing_signature
        try:
            from music_activity import log_backing_track_started

            log_backing_track_started(
                st,
                bpm=int(bpm),
                loops=int(form_loops),
                scope=section_scope_label,
            )
        except Exception:
            pass
        st.session_state["_last_backing_timeline"] = timeline
        st.session_state["playback_start_time"] = time.time()
        st.session_state["current_chord_timeline"] = timeline
        st.session_state["selected_sections"] = list(selected_section_names)
        st.session_state["bpm"] = bpm
        st.session_state["beats_per_bar"] = beats_per_bar_from_signature(backing_time_signature)
        st.session_state["backing_time_signature_applied"] = backing_time_signature
        st.session_state[f"{_follow_key_prefix}::follow_manual_index"] = 0
        st.session_state[BACKING_AUTOPLAY] = bool(_karaoke_auto_gen or _play_needs_generate)
        if _karaoke_auto_gen or _play_needs_generate:
            st.session_state["_backing_play_request"] = True
        st.session_state[BACKING_TRANSPORT_STATUS] = "ready"
        set_pending_anchor(st.session_state, ANCHOR_BACKING_FOLLOW_ALONG)
        if _karaoke_auto_gen:
            st.session_state[BACKING_PLAY_FEEDBACK_KEY] = (
                "Karaoke backing generated — press Play to start."
                if km.is_voice_mode(st.session_state)
                else "Backing generated — press Play to start."
            )
        elif _play_needs_generate:
            st.session_state[BACKING_PLAY_FEEDBACK_KEY] = "Backing ready — starting playback."
        st.session_state.pop("_backing_transport_user_stopped", None)
        try:
            from backing_track_state import commit_backing_transport_from_session

            commit_backing_transport_from_session(st.session_state, reason="generate")
        except ImportError:
            pass
        clear_backing_needs_regen(st)
        if _play_needs_generate or _karaoke_auto_gen:
            st.rerun()

    if _play_clicked:
        _karaoke_voice_play = bool(km.is_voice_mode(st.session_state))
        _begin_backing_performance_follow_along(
            st,
            follow_key_prefix=_follow_key_prefix,
            karaoke_voice=_karaoke_voice_play,
        )
        if not (_play_needs_generate or _karaoke_auto_gen):
            st.rerun()

    _backing_audio_ready = bool(
        st.session_state.get("_last_backing_wav")
        and st.session_state.get("_last_backing_signature") == _current_backing_signature
    )
    _leadsheet_open = bool(st.session_state.get("backing_lead_sheet_open", False))
    if _backing_audio_ready and not _leadsheet_open and not st.session_state.get(
        "_backing_transport_user_stopped"
    ):
        st.markdown("#### Audio player")
        record_backing_timing_event(st.session_state, "audio_load_complete")
        st.audio(
            st.session_state["_last_backing_wav"],
            format="audio/wav",
            autoplay=bool(st.session_state.get(BACKING_AUTOPLAY, False)),
        )
        if st.session_state.get(BACKING_AUTOPLAY, False):
            st.caption("Playback started — use the player controls below.")
        else:
            st.caption(
                "Audio ready — press **▶ Play** below or use the player **Play** button."
            )

    _stored_timeline = (
        st.session_state.get("_last_backing_timeline")
        if st.session_state.get("_last_backing_signature") == _current_backing_signature
        else None
    )
    _follow_timeline = _stored_timeline or build_chord_event_timeline(
        backing_events,
        bpm,
        form_loops,
        time_signature=backing_time_signature,
    )

    # ---- Lead sheet open-state handling ------------------------------------
    if st.session_state.pop("_pending_open_backing_lead_sheet", False):
        st.session_state["backing_lead_sheet_open"] = True
        _leadsheet_open = True

    _backing_chart_sig = (
        song,
        chart_key,
        level,
        resolved_groove,
        bpm,
        backing_time_signature,
        tuple(selected_section_names),
        tuple(backing_chords),
        instrument,
        focus,
        _capo_ctx.enabled,
        _capo_ctx.capo_fret if _capo_ctx.enabled else 0,
        tuple(_hri_annotations.keys()) if _hri_annotations else (),
    )
    chart_html = ""
    if _leadsheet_open:
        chart_html = session_cache_get_or_set(
            st.session_state,
            "backing_chart_html",
            _backing_chart_sig,
            lambda: full_chord_markdown(
                song,
                song_data,
                chart_sections,
                instrument,
                display_key=chart_display_key,
                level=level,
                section_lyrics=section_lyrics,
                groove_style=resolved_groove,
                bpm=bpm,
                time_signature=backing_time_signature,
                current_section=None,
                current_bar=None,
                focus=focus,
                chart_mode="backing",
                selected_section_names=selected_section_names,
                shape_sections=_capo_ctx.shape_sections if _capo_ctx.enabled else None,
                capo_fret=_capo_ctx.capo_fret if _capo_ctx.enabled else 0,
                capo_shape_key=_capo_ctx.shape_key if _capo_ctx.enabled else "",
                auto_inferences=_hri_annotations,
            ),
        )

    # The lead-sheet visibility is *purely* driven by ``backing_lead_sheet_open``
    # so the user's "Hide chart" / "Show chart" clicks always win. Generate
    # auto-opens by toggling the flag above; from then on it's a plain
    # session_state boolean that survives reruns without resetting playback,
    # audio, scroll position, song, karaoke queue, or section selection.

    # Lead sheet is opt-in only — the iframe chart player is heavy and stays
    # off the page until the user explicitly opens it.
    if _backing_audio_ready:
        _ls_col_a, _ls_col_b = st.columns([1, 5])
        with _ls_col_a:
            if _leadsheet_open:
                if st.button(
                    "Close lead sheet",
                    key="backing_leadsheet_hide_btn",
                    use_container_width=True,
                ):
                    st.session_state["backing_lead_sheet_open"] = False
                    st.rerun()
            elif st.button(
                "Open lead sheet",
                key="backing_leadsheet_show_btn",
                type="secondary",
                use_container_width=True,
            ):
                st.session_state["backing_lead_sheet_open"] = True
                st.rerun()
        with _ls_col_b:
            st.caption(
                "Optional chord follow-along — opens on demand to keep the page light."
                if not _leadsheet_open
                else "Live chord highlighting while the backing track plays."
            )

    if _backing_audio_ready and _leadsheet_open:
        st.markdown(
            '<div class="ui-backing-leadsheet-card" data-state="open" id="backing-lead-sheet-anchor">',
            unsafe_allow_html=True,
        )
        if not st.session_state.get(BACKING_AUTOPLAY, False):
            st.info(
                "Backing playback stopped — press **▶ Play** above to resume."
            )
        _karaoke_active = km.is_karaoke_session_active(st.session_state)
        _karaoke_voice = km.is_voice_mode(st.session_state)
        _karaoke_engaged = _karaoke_active and _karaoke_voice
        _show_countdown = bool(
            _karaoke_engaged
            and km.countdown_enabled(st.session_state)
            and bool(st.session_state.get(BACKING_AUTOPLAY, False))
        )
        _karaoke_lyric_panel: dict | None = None
        if _karaoke_voice:
            _user_section_text = section_lyrics or {}
            _catalog_cues = song_data.get("lyric_cues") or {}
            _panel_map: dict[str, dict] = {}
            for _sec_name, _sec_chords in (chart_sections or {}).items():
                _lines = _lyric_lines_for_section(
                    _sec_name,
                    _catalog_cues,
                    _user_section_text,
                    limit=16,
                )
                _panel_map[str(_sec_name)] = {
                    "lyrics": _lines,
                    "chords": [str(c) for c in (_sec_chords or [])],
                }
            if any(entry.get("lyrics") for entry in _panel_map.values()):
                _karaoke_lyric_panel = _panel_map
        _karaoke_song_title = str(song_data.get("title") or song or "Now Singing")
        _karaoke_hide_chart = bool(_karaoke_voice and _karaoke_lyric_panel)
        _karaoke_display_labels = dict(
            song_data.get("_beginner_display_labels") or {}
        )
        _player_b64 = st.session_state.get("_last_backing_wav_b64")
        if not _player_b64 and st.session_state.get("_last_backing_wav"):
            _player_b64, _, _ = prepare_wav_b64(
                st.session_state,
                _current_backing_signature,
                st.session_state["_last_backing_wav"],
            )
            st.session_state["_last_backing_wav_b64"] = _player_b64
        record_backing_timing_event(st.session_state, "audio_load_complete")
        render_scroll_anchor_marker(st, ANCHOR_BACKING_FOLLOW_ALONG)
        _play_feedback = str(
            st.session_state.get(BACKING_PLAY_FEEDBACK_KEY, "") or ""
        ).strip()
        if _play_feedback:
            st.info(_play_feedback)
        components.html(
            live_follow_along_component_html(
                st.session_state["_last_backing_wav"],
                _follow_timeline,
                chart_html,
                autoplay=bool(st.session_state.get(BACKING_AUTOPLAY, False)),
                audio_b64=_player_b64,
                karaoke_auto_advance=(
                    _karaoke_engaged and km.auto_advance_enabled(st.session_state)
                ),
                karaoke_countdown=_show_countdown,
                karaoke_countdown_seconds=km.countdown_seconds(st.session_state),
                karaoke_lyrics_panel=_karaoke_lyric_panel,
                karaoke_song_title=_karaoke_song_title,
                karaoke_hide_chart=_karaoke_hide_chart,
                karaoke_display_labels=_karaoke_display_labels,
                karaoke_lyric_color=km.lyric_color(st.session_state),
            ),
            height=820 if _karaoke_lyric_panel else 720,
            scrolling=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    if _developer_mode_enabled():
        with st.expander("📋 Form timeline & section order (dev)", expanded=False):
            _tl_rows = form_timeline_rows(sections)

            st.dataframe(
                pd.DataFrame(_tl_rows).rename(
                    columns={
                        "section": "Section",
                        "start_bar": "Start bar",
                        "end_bar": "End bar",
                        "bars": "Bars (chords)",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

            selected_rows = [
                {
                    "Section": name,
                    "Bars": len(chords),
                    "Included": "Yes" if (not selected_section_names or name in selected_section_names) else "No",
                }
                for name, chords in section_order(
                    sections,
                    section_names=section_names_from_song(song_data),
                )
                if chords
            ]
            st.dataframe(
                pd.DataFrame(selected_rows),
                use_container_width=True,
                hide_index=True,
            )

    try:
        from backing_track_state import enable_backing_user_edits

        enable_backing_user_edits(st.session_state)
    except Exception:
        pass


# -------------------------------------------------
# UPLOAD / RECORDING ANALYSIS
# -------------------------------------------------

elif _studio_page == "analysis":

    try:
        from media_multitrack_export_catalog import (
            PENDING_EXPORT_ANALYSIS_KEY,
            apply_pending_multitrack_export_analysis,
            upload_analysis_has_export_handoff,
        )

        if st.session_state.get(PENDING_EXPORT_ANALYSIS_KEY):
            apply_pending_multitrack_export_analysis(st.session_state, st=st)
    except Exception:
        pass

    try:
        from media_multitrack_export_catalog import upload_analysis_has_export_handoff

        if not upload_analysis_has_export_handoff(st.session_state):
            from analysis_session_persistence import restore_analysis_session

            restore_analysis_session(st.session_state, st=st)
    except Exception:
        pass

    try:
        from media_upload_catalog import migrate_legacy_upload_history

        migrate_legacy_upload_history(st=st)
    except Exception:
        pass

    try:
        from media_diagnostics import render_media_diagnostics

        render_media_diagnostics(st, st.session_state, page="analysis")
    except Exception:
        pass

    try:
        from studio_history_bootstrap import apply_pending_studio_history

        apply_pending_studio_history(st.session_state, page="analysis", st=st)
    except Exception:
        pass
    ensure_page_initialized(st.session_state, "analysis")
    note_page_visit(st.session_state, "analysis")
    from recording_analysis import analyze_multitrack, analyze_recording
    from recording_analysis_ui import render_analysis_dashboard

    try:
        from app_ui import (
            inject_studio_ui_release_marker,
            inject_upload_studio_styles,
            render_upload_studio_panel_header,
            upload_format_chips_html,
            upload_session_context_html,
        )
    except Exception:
        inject_upload_studio_styles = lambda _st: None  # type: ignore
        inject_studio_ui_release_marker = lambda *_a, **_k: None  # type: ignore
        render_upload_studio_panel_header = lambda *_a, **_k: None  # type: ignore
        upload_format_chips_html = lambda: ""  # type: ignore
        upload_session_context_html = lambda **_k: ""  # type: ignore

    inject_upload_studio_styles(st)
    inject_studio_ui_release_marker(st, page="analysis")
    _studio_page_header(
        "🎙️",
        "Upload & AI Coach",
        "Drop a take, get timing and pitch feedback, then jump to practice or multitrack.",
    )

    _song_title = str(song or "Your song")
    _song_artist = _active_song_artist_label()

    with st.container(key="upload_studio_panel", border=False):
        render_upload_studio_panel_header(st, song_title=_song_title, artist=_song_artist)
        st.markdown(
            upload_session_context_html(
                song_title=_song_title,
                artist=_song_artist,
                display_key=str(chart_key or display_key or "C"),
                instrument=str(instrument or "Guitar"),
            ),
            unsafe_allow_html=True,
        )

        with st.container(key="upload_mode_segment", border=False):
            from upload_analysis_modes import (
                WORKFLOW_OPTIONS,
                is_multitrack_workflow,
                normalize_analysis_workflow,
            )

            normalize_analysis_workflow(st.session_state)
            col_mode, col_type = st.columns([1, 1])
            with col_mode:
                analysis_mode = st.radio(
                    "Workflow",
                    list(WORKFLOW_OPTIONS),
                    horizontal=True,
                    key="analysis_mode",
                )
            with col_type:
                recording_type = st.selectbox(
                    "Recording type",
                    [
                        "Practice take",
                        "Solo performance",
                        "Over backing track",
                        "Multitrack layer",
                        "Multitrack mix",
                    ],
                    key="analysis_recording_type",
                )

        if not is_multitrack_workflow(st.session_state):
            from mission_analysis_ui import (
                is_analysis_criteria_locked,
                render_analysis_criteria_summary,
                render_mission_goals_selector,
                ANALYSIS_RETURN_TO_METRICS,
            )

            with st.container(key="upload_capture_panel", border=False):
                st.markdown(
                    '<p class="ui-upload-step-kicker">Step 1 · Capture audio</p>',
                    unsafe_allow_html=True,
                )
                st.markdown(upload_format_chips_html(), unsafe_allow_html=True)
                st.caption(
                    "Drag and drop a take, or record live. WAV gives the most accurate timing analysis. "
                    "MP4/MOV uploads extract audio automatically."
                )

                if is_analysis_criteria_locked(st.session_state):
                    mission_ids = render_analysis_criteria_summary(st, st.session_state)
                else:
                    mission_ids = render_mission_goals_selector(st, st.session_state)

                from upload_media import (
                    PreparedUpload,
                    UPLOAD_ACCEPT_TYPES,
                    VideoExtractionError,
                    is_video_filename,
                )
                try:
                    from media_multitrack_export_catalog import (
                        analysis_export_handoff_ready,
                        clear_multitrack_export_analysis_handoff,
                        loaded_multitrack_export_analysis_banner,
                        resolve_upload_analysis_prepared_upload,
                    )
                    from media_upload_catalog import clear_upload_analysis_saved_edit_state
                except ImportError:
                    analysis_export_handoff_ready = lambda _ss: False  # type: ignore[assignment,misc]
                    loaded_multitrack_export_analysis_banner = lambda _ss: ""  # type: ignore[assignment,misc]
                    clear_multitrack_export_analysis_handoff = lambda _ss: None  # type: ignore[assignment,misc]
                    resolve_upload_analysis_prepared_upload = lambda _ss, **_: None  # type: ignore[assignment,misc]
                    clear_upload_analysis_saved_edit_state = lambda _ss: None  # type: ignore[assignment,misc]

                _export_handoff_label = loaded_multitrack_export_analysis_banner(st.session_state)
                _handoff_prepared = resolve_upload_analysis_prepared_upload(
                    st.session_state,
                    st=st,
                )
                _export_handoff_ready = bool(
                    _export_handoff_label
                    and _handoff_prepared is not None
                    and analysis_export_handoff_ready(st.session_state)
                )
                if _export_handoff_ready and _export_handoff_label:
                    st.success(_export_handoff_label)
                    st.markdown("**Preview**")
                    st.audio(_handoff_prepared.getvalue(), format="audio/wav")
                    _capture_expander = st.expander("Replace with a different file", expanded=False)
                else:
                    _capture_expander = st.container()

                with _capture_expander:
                    analysis_audio = st.file_uploader(
                        "Drop your recording here",
                        type=UPLOAD_ACCEPT_TYPES,
                        key="analysis_audio_upload",
                    )
                    try:
                        mic_audio = st.audio_input("Or record live", key="analysis_audio_record")
                    except Exception:
                        mic_audio = None
                        st.caption("Live mic may be unavailable in this build — file upload still works.")

                audio_obj = None
                if mic_audio is not None:
                    clear_multitrack_export_analysis_handoff(st.session_state)
                    clear_upload_analysis_saved_edit_state(st.session_state)
                    audio_obj = PreparedUpload(
                        mic_audio.getvalue(),
                        str(getattr(mic_audio, "name", None) or "recording.wav"),
                    )
                elif analysis_audio is not None:
                    import hashlib

                    clear_multitrack_export_analysis_handoff(st.session_state)
                    clear_upload_analysis_saved_edit_state(st.session_state)
                    _raw = analysis_audio.getvalue()
                    _raw_name = str(getattr(analysis_audio, "name", None) or "upload.wav")
                    _sig = (
                        hashlib.sha256(_raw[:65536] + str(len(_raw)).encode()).hexdigest()[:20],
                        _raw_name,
                    )
                    if st.session_state.get("_analysis_upload_prep_sig") != _sig:
                        if is_video_filename(_raw_name):
                            with st.spinner("Video detected. Extracting audio…"):
                                try:
                                    audio_obj = PreparedUpload.from_uploaded(analysis_audio)
                                except VideoExtractionError as _vid_exc:
                                    st.warning(str(_vid_exc))
                                    st.caption(
                                        "Try a shorter clip or re-export the video as MP4 with an audio track."
                                    )
                                    if _developer_mode_enabled():
                                        st.markdown("**Developer · video extraction diagnostics**")
                                        st.json(_vid_exc.meta)
                                    audio_obj = None
                                except Exception as _vid_exc:
                                    st.warning("Could not extract audio from this video.")
                                    if _developer_mode_enabled():
                                        st.caption(f"Developer · {type(_vid_exc).__name__}: {_vid_exc}")
                                    audio_obj = None
                        else:
                            audio_obj = PreparedUpload(_raw, _raw_name)
                        if audio_obj is not None:
                            st.session_state["_analysis_upload_prep_sig"] = _sig
                            st.session_state["_analysis_prepared_upload"] = audio_obj
                            try:
                                from music_activity import log_media_upload

                                log_media_upload(
                                    st,
                                    media_type=(
                                        "video"
                                        if is_video_filename(_raw_name)
                                        else "audio"
                                    ),
                                    filename=_raw_name,
                                )
                            except Exception:
                                pass
                    else:
                        audio_obj = st.session_state.get("_analysis_prepared_upload")

                    if audio_obj is not None and is_video_filename(_raw_name):
                        _meta = getattr(audio_obj, "meta", {}) or {}
                        if _meta.get("ok"):
                            st.success("Audio extracted successfully.")
                            _detail_bits: list[str] = []
                            if _meta.get("video_duration_sec") is not None:
                                _detail_bits.append(
                                    f"video {_meta['video_duration_sec']:.1f}s"
                                )
                            if _meta.get("audio_duration_sec") is not None:
                                _detail_bits.append(
                                    f"audio {_meta['audio_duration_sec']:.1f}s"
                                )
                            if _meta.get("extracted_wav_bytes"):
                                _kb = int(_meta["extracted_wav_bytes"]) / 1024
                                _detail_bits.append(f"extracted WAV {_kb:.0f} KB")
                            if _detail_bits:
                                st.caption(" · ".join(_detail_bits))

                elif _export_handoff_ready and _handoff_prepared is not None:
                    audio_obj = _handoff_prepared
                elif st.session_state.get("_analysis_prepared_upload") is not None:
                    audio_obj = st.session_state.get("_analysis_prepared_upload")

                if audio_obj is not None and not (_export_handoff_ready and _export_handoff_label):
                    st.markdown("**Preview**")
                    st.audio(audio_obj.getvalue(), format="audio/wav")

            if st.button(
                "Run AI coach analysis",
                type="primary",
                key="analysis_run_btn",
                use_container_width=True,
            ):
                if audio_obj is None:
                    st.warning("Upload or record audio first.")
                else:
                    ctx = _recording_analysis_context(
                        recording_type=recording_type.lower().replace(" ", "_"),
                    )
                    ctx["mission_ids"] = mission_ids
                    if not is_analysis_criteria_locked(st.session_state):
                        ctx["custom_goal"] = str(
                            st.session_state.get("analysis_custom_goal") or ""
                        ).strip()
                    else:
                        ctx["custom_goal"] = ""
                    from mission_analysis import mission_ids_from_legacy

                    ctx["active_practice_mission_ids"] = mission_ids_from_legacy(
                        str(st.session_state.get("improv_active_mission") or "")
                    )
                    ctx["display_key"] = chart_key
                    spin = (
                        "Analyzing timing, pitch, groove, musicality, and improvisation missions…"
                        if mission_ids
                        else "Analyzing timing, pitch, groove, and musicality…"
                    )
                    with st.spinner(spin):
                        result = analyze_recording(
                            audio_obj.getvalue(),
                            getattr(audio_obj, "name", "recording.wav"),
                            ctx,
                        )
                    st.session_state["last_analysis_result"] = result
                    st.session_state["last_analysis_audio"] = audio_obj.getvalue()
                    st.session_state["last_analysis_source_label"] = str(
                        getattr(audio_obj, "name", None) or "recording.wav"
                    )
                    try:
                        from analysis_session_persistence import save_analysis_session
                        from music_persistent_state import force_save_music_state

                        save_analysis_session(st.session_state, st=st)
                        force_save_music_state(st, reason="analysis_complete")
                        try:
                            from media_upload_catalog import register_upload_analysis_in_catalog

                            register_upload_analysis_in_catalog(st.session_state, st=st)
                        except Exception:
                            pass
                    except Exception:
                        pass
                    if result.get("ok"):
                        try:
                            from music_activity import log_recording_reviewed

                            log_recording_reviewed(st)
                        except Exception:
                            pass
                        from ai_performance_history import (
                            SOURCE_METRICS_UPLOAD,
                            append_performance_record,
                            resolve_analysis_source,
                        )

                        src = resolve_analysis_source(st.session_state)
                        append_performance_record(result, ctx=ctx, source=src)
                        result["analysis_source"] = src
                        if src == SOURCE_METRICS_UPLOAD:
                            went, imp = "", ""
                            missions = result.get("mission_results") or []
                            if missions:
                                best = max(missions, key=lambda m: int(m.get("score") or 0))
                                worst = min(missions, key=lambda m: int(m.get("score") or 0))
                                went = str(best.get("went_well") or "")
                                imp = str(worst.get("improve_to") or "")
                            result["went_well"] = went
                            result["improve_to"] = imp
                            result["next_practice"] = str(
                                result.get("mission_next_recommendation") or ""
                            )
                            result["recommendations"] = [
                                str(result.get("mission_next_recommendation") or "")
                            ]
                        st.session_state["last_analysis_result"] = result
                        if st.session_state.get(ANALYSIS_RETURN_TO_METRICS):
                            st.session_state["creative_lab_last_mode"] = (
                                "Improvisation Intelligence"
                            )
                            st.session_state["improv_intelligence_tab"] = "Metrics & AI"
                            navigate_studio_page(st.session_state, "creative")
                            st.rerun()

            if (
                st.session_state.get("last_analysis_result")
                and not st.session_state.get(ANALYSIS_RETURN_TO_METRICS)
            ):
                with st.container(key="upload_results_panel", border=False):
                    st.markdown(
                        '<p class="ui-upload-step-kicker">Step 2 · Coach report</p>',
                        unsafe_allow_html=True,
                    )
                    last = st.session_state["last_analysis_result"]
                    st.markdown(
                        render_analysis_dashboard(last),
                        unsafe_allow_html=True,
                    )
                    mission_rows = last.get("mission_results") or []
                    if mission_rows:
                        overall = last.get("overall_improv_score")
                        if overall:
                            st.metric("Overall Improvisation Score", f"{overall}%")
                        with st.expander("AI metric feedback (detail)", expanded=True):
                            for m in mission_rows:
                                st.markdown(f"#### {m.get('label', '')} — {m.get('score', 0)}%")
                                st.markdown(m.get("summary", ""))
                                if m.get("went_well"):
                                    st.success(f"**What went well:** {m.get('went_well')}")
                                if m.get("improve_to"):
                                    st.warning(f"**To improve:** {m.get('improve_to')}")
                                for tip in m.get("tips") or []:
                                    st.markdown(f"- {tip}")
                    if st.session_state.get("last_analysis_audio"):
                        with st.expander("Playback — analyzed take", expanded=False):
                            st.audio(st.session_state["last_analysis_audio"], format="audio/wav")

        else:
            with st.container(key="upload_capture_panel", border=False):
                st.markdown(
                    '<p class="ui-upload-step-kicker">Step 1 · Upload stems</p>',
                    unsafe_allow_html=True,
                )
                st.caption(
                    "Upload 2–6 layers (e.g. guitar, vocal, keys) for multitrack recording analysis."
                )
                st.markdown(upload_format_chips_html(), unsafe_allow_html=True)
                mt_files = st.file_uploader(
                    "Multitrack layers",
                    type=["wav", "mp3", "m4a", "ogg"],
                    accept_multiple_files=True,
                    key="analysis_multitrack_upload",
                )
                if mt_files and st.button(
                    "Analyze ensemble",
                    type="primary",
                    key="analysis_mt_btn",
                    use_container_width=True,
                ):
                    tracks = []
                    for f in mt_files[:6]:
                        tracks.append(
                            {
                                "name": f.name,
                                "filename": f.name,
                                "bytes": f.getvalue(),
                                "instrument": "",
                            }
                        )
                    ctx = _recording_analysis_context(recording_type="multitrack")
                    with st.spinner("Comparing layers…"):
                        mt_result = analyze_multitrack(tracks, ctx)
                    st.session_state["last_analysis_result"] = mt_result
                    if mt_result.get("ok"):
                        from ai_performance_history import (
                            SOURCE_MULTITRACK,
                            append_performance_record,
                        )

                        append_performance_record(mt_result, ctx=ctx, source=SOURCE_MULTITRACK)
                    try:
                        from analysis_session_persistence import save_analysis_session
                        from music_persistent_state import force_save_music_state

                        save_analysis_session(st.session_state, st=st)
                        force_save_music_state(st, reason="analysis_complete")
                        try:
                            from media_upload_catalog import register_upload_analysis_in_catalog

                            register_upload_analysis_in_catalog(st.session_state, st=st)
                        except Exception:
                            pass
                    except Exception:
                        pass
            if st.session_state.get("last_analysis_result", {}).get("multitrack"):
                with st.container(key="upload_results_panel", border=False):
                    st.markdown(
                        '<p class="ui-upload-step-kicker">Step 2 · Ensemble report</p>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        render_analysis_dashboard(st.session_state["last_analysis_result"]),
                        unsafe_allow_html=True,
                    )


    try:
        from studio_history_ui import render_upload_history_panel

        render_upload_history_panel(st)
    except Exception:
        pass


# -------------------------------------------------
# CUSTOM PROGRESSION LAB
# -------------------------------------------------

elif _studio_page == "custom":

    ensure_page_initialized(st.session_state, "custom")
    note_page_visit(st.session_state, "custom")
    try:
        from app_ui import inject_custom_builder_styles, inject_studio_page_marker_sync

        inject_custom_builder_styles(st)
        inject_studio_page_marker_sync(st, page="custom")
    except Exception:
        pass
    _studio_page_header(
        "✏️",
        "Custom Progression Lab",
        "Build chord progressions for your active song — then open in Backing Track.",
    )
    from cpl_page_ui import render_custom_progression_lab_page

    render_custom_progression_lab_page()


# -------------------------------------------------
# CREATIVE LAB
# -------------------------------------------------

elif _studio_page == "creative":

    ensure_page_initialized(st.session_state, "creative")
    note_page_visit(st.session_state, "creative")
    try:
        from creative_session_state import (
            hydrate_creative_session_for_page,
            sync_creative_session_before_persist,
        )

        hydrate_creative_session_for_page(st.session_state)
    except ImportError:
        pass
    try:
        from app_ui import inject_creative_studio_styles

        inject_creative_studio_styles(st)
        from app_ui import inject_studio_ui_release_marker

        inject_studio_ui_release_marker(st, page="creative")
    except Exception:
        pass

    if pp.is_capture_mode(st):
        _studio_page_header(
            "✏️",
            "Creative Lab",
            "Deep harmonic analysis, improvisation intelligence, and adaptive musical development tools.",
        )
        pp.render_executive_summary(
            st,
            "Analyze harmony, generate improvisation ideas, and track musical growth from your active song.",
            "Shows AI-assisted music education and analytics applied to real repertoire.",
            "Harmonic analyzer, improvisation coach, arrangement assistant, weakness detection, and progress tracking.",
        )
    else:
        _studio_page_header(
            "✏️",
            "Creative Lab",
            "Harmony, improvisation, and growth tools for your active song.",
        )

    try:
        from backing_source_navigation import render_source_context_debug

        render_source_context_debug(st, st.session_state)
    except ImportError:
        pass

    ctx = current_song_context_lab()

    from creative_key_sync import ensure_creative_analysis_mode_restored, on_creative_analysis_mode_change

    ensure_creative_analysis_mode_restored(st.session_state)

    lab_mode = st.selectbox(
        "Analysis mode",
        [
            "Deep Harmonic Analyzer",
            "Improvisation Intelligence",
            "Creative Arrangement Assistant",
            "Adaptive Weakness Detection",
            "AI-Guided Musical Development Tracking",
        ],
        key="creative_lab_analysis_mode",
        on_change=on_creative_analysis_mode_change,
    )
    st.session_state["creative_lab_last_mode"] = lab_mode

    def _improv_apply_playback_from_style() -> None:
        meta = st.session_state.get("improv_style_meta") or {}
        if meta.get("bpm"):
            request_backing_bpm(st, int(meta["bpm"]))
        style = str(meta.get("backing_style") or meta.get("style") or "").strip()
        if style and style != "Auto":
            request_backing_groove(st, style)

    def _improv_on_song_source(source: str) -> None:
        apply_improv_song_source(
            st.session_state,
            source,
            set_catalog_source=set_catalog_source,
            set_custom_source=set_custom_source,
            widget_safe=True,
        )

    def _improv_open_backing() -> None:
        from backing_context import open_backing_from_creative
        from creative_key_sync import persist_creative_analysis_mode, sync_creative_style_jam_meta
        from creative_session_state import sync_creative_session_from_session
        from studio_page_persistence import save_page_snapshot

        sync_creative_style_jam_meta(st.session_state)
        sync_creative_session_from_session(st.session_state)
        source = resolve_improv_song_source(st.session_state)
        sync_improv_song_source_for_handoff(
            st.session_state,
            source,
            set_catalog_source=set_catalog_source,
            set_custom_source=set_custom_source,
        )
        entry = str(st.session_state.get("improv_entry_mode") or "").strip()
        if str(st.session_state.get("improv_intelligence_tab") or "") == "Missions":
            creative_source = "mission"
        elif entry == "Song-Based Improvisation":
            if source == "Custom progression":
                creative_source = "custom_progression"
            else:
                creative_source = "song_improv"
                st.session_state["improv_song_concert_sections"] = dict(sections_for_backing)
                st.session_state["improv_song_chart_sections"] = dict(sections_for_practice)
        elif entry in ("Style Jam Mode", "Jam Session Generator"):
            creative_source = "entry_jam"
        else:
            creative_source = "entry_jam"
        persist_creative_analysis_mode(st.session_state)
        persist_improv_intelligence_tab(st.session_state)
        save_page_snapshot(st.session_state, "creative")
        open_backing_from_creative(st.session_state, source=creative_source, st_like=st)
        try:
            from backing_source_navigation import BACKING_INTENT_FROM_CREATIVE, set_backing_open_intent

            set_backing_open_intent(st.session_state, BACKING_INTENT_FROM_CREATIVE)
        except ImportError:
            pass
        set_pending_anchor(st.session_state, ANCHOR_BACKING_MAIN_CONTROLS)
        navigate_studio_page(st.session_state, "backing")
        st.rerun()

    def _improv_open_practice() -> None:
        source = resolve_improv_song_source(st.session_state)
        sync_improv_song_source_for_handoff(
            st.session_state,
            source,
            set_catalog_source=set_catalog_source,
            set_custom_source=set_custom_source,
        )
        note_active_source_change(st, invalidate_backing=invalidate_backing_cache)
        set_pending_anchor(st.session_state, ANCHOR_PRACTICE_COACH)
        navigate_studio_page(st.session_state, "practice")
        st.rerun()

    def _improv_open_analysis() -> None:
        from mission_analysis_ui import prepare_analysis_from_creative

        prepare_analysis_from_creative(st.session_state)
        navigate_studio_page(st.session_state, "analysis")
        st.rerun()

    def _improv_go_song_selection() -> None:
        set_pending_anchor(st.session_state, ANCHOR_CHOOSE_ACTIVE_SONG)
        navigate_studio_page(st.session_state, "picker")
        st.rerun()

    def _improv_go_custom_progression() -> None:
        navigate_studio_page(st.session_state, "custom")
        st.rerun()

    if lab_mode == "Improvisation Intelligence":
        from improvisation_intelligence_ui import render_improvisation_intelligence_lab

        render_improvisation_intelligence_lab(
            st,
            ctx=ctx,
            session_state=st.session_state,
            chart_key=chart_key,
            sections=sections_for_practice,
            song_data=song_data,
            bpm=int(st.session_state.get("backing_track_bpm", _default_song_bpm)),
            genre=genre,
            is_custom=is_custom_progression(st.session_state),
            on_open_backing=_improv_open_backing,
            on_open_practice=_improv_open_practice,
            on_open_analysis=_improv_open_analysis,
            on_song_source_change=_improv_on_song_source,
            apply_style_to_playback=_improv_apply_playback_from_style,
            on_go_song_selection=_improv_go_song_selection,
            on_go_custom_progression=_improv_go_custom_progression,
        )
        try:
            from creative_session_state import sync_creative_session_before_persist

            sync_creative_session_before_persist(st.session_state)
        except ImportError:
            pass
        try:
            from creative_session_state import render_creative_session_diagnostic

            render_creative_session_diagnostic(st, st.session_state)
        except ImportError:
            pass
    else:
        with st.expander(lab_mode, expanded=pp.feature_expander_default(st, default=True)):
            if lab_mode == "Deep Harmonic Analyzer":
                st.markdown(deep_harmonic_analysis_text(ctx))
            elif lab_mode == "Creative Arrangement Assistant":
                _style_opts = [
                    "Jobim / Bossa",
                    "Jazz Fusion",
                    "Neo-Soul",
                    "Rock Ballad",
                    "Funk",
                    "Cinematic",
                ]
                target_style = st.selectbox(
                    "Transform toward style",
                    _style_opts,
                    key="creative_arrangement_target_style",
                )
                _sec_opts = ["Full song"] + [
                    name for name, chords in sections.items() if chords
                ]
                if (
                    st.session_state.get("creative_arrangement_section_focus")
                    not in _sec_opts
                ):
                    st.session_state["creative_arrangement_section_focus"] = _sec_opts[0]
                arrangement_section = st.selectbox(
                    "Arrangement focus",
                    _sec_opts,
                    key="creative_arrangement_section_focus",
                )
                st.markdown(creativity_arrangement_text(ctx, target_style, arrangement_section))
            elif lab_mode == "Adaptive Weakness Detection":
                st.markdown(adaptive_weakness_detection_text(ctx))
            else:
                st.markdown(musical_development_tracker_text())


# -------------------------------------------------
# MULTITRACK
# -------------------------------------------------

elif _studio_page == "multitrack":

    try:
        from studio_history_bootstrap import apply_pending_studio_history

        apply_pending_studio_history(st.session_state, page="multitrack", st=st)
    except Exception:
        pass

    ensure_page_initialized(st.session_state, "multitrack")
    note_page_visit(st.session_state, "multitrack")
    try:
        from app_ui import (
            inject_multitrack_studio_styles,
            inject_studio_ui_release_marker,
            multitrack_layer_badge_html,
            multitrack_session_context_html,
            render_multitrack_field_label,
            render_multitrack_session_context_strip,
            render_multitrack_session_setup_header,
            render_multitrack_setup_section_close,
            render_multitrack_setup_section_open,
            render_multitrack_studio_panel_header,
        )
    except Exception:
        inject_multitrack_studio_styles = lambda _st: None  # type: ignore
        inject_studio_ui_release_marker = lambda *_a, **_k: None  # type: ignore
        multitrack_layer_badge_html = lambda **_k: ""  # type: ignore
        multitrack_session_context_html = lambda **_k: ""  # type: ignore
        render_multitrack_field_label = lambda *_a, **_k: None  # type: ignore
        render_multitrack_session_context_strip = lambda *_a, **_k: None  # type: ignore
        render_multitrack_session_setup_header = lambda _st: None  # type: ignore
        render_multitrack_setup_section_close = lambda _st: None  # type: ignore
        render_multitrack_setup_section_open = lambda *_a, **_k: None  # type: ignore
        render_multitrack_studio_panel_header = lambda *_a, **_k: None  # type: ignore


    try:
        from media_multitrack_catalog import migrate_legacy_multitrack_history

        migrate_legacy_multitrack_history(st=st)
    except Exception:
        pass

    try:
        from media_diagnostics import render_media_diagnostics

        render_media_diagnostics(st, st.session_state, page="multitrack")
    except Exception:
        pass

    _mt_orig_key, _mt_practice_key = _active_song_key_pair(song_data)

    inject_multitrack_studio_styles(st)
    inject_studio_ui_release_marker(st, page="multitrack")
    _studio_page_header(
        "🎚️",
        "Multitrack Session Workspace",
        "Overdub layers with monitor backing, mix, and export — synced to your active song.",
    )

    from multitrack_slots import MT_SLOTS

    try:
        from music_restore_phase import mark_page_snapshot_hydrated, should_hydrate_page_snapshot
        from studio_page_persistence import restore_current_page_snapshot_if_needed

        if should_hydrate_page_snapshot(
            st.session_state,
            page_id="multitrack",
            page_changed=False,
        ):
            restore_current_page_snapshot_if_needed(st.session_state)
            mark_page_snapshot_hydrated(st.session_state, "multitrack")
    except Exception:
        pass
    try:
        from multitrack_mixer_state import (
            prepare_multitrack_mixer_widgets,
            prepare_multitrack_transport_widgets,
        )

        prepare_multitrack_transport_widgets(st.session_state)
        prepare_multitrack_mixer_widgets(st.session_state)
    except ImportError:
        pass
    try:
        from multitrack_session_persistence import restore_multitrack_layers_from_workspace

        restore_multitrack_layers_from_workspace(st.session_state)
    except Exception:
        pass
    if "mt_tracks" not in st.session_state:
        st.session_state.mt_tracks = {slot: None for slot in MT_SLOTS}
    if "mt_track_filenames" not in st.session_state:
        st.session_state.mt_track_filenames = {
            slot: f"{slot.replace(' ', '_').lower()}.wav" for slot in MT_SLOTS
        }

    _default_mt_time_sig = default_time_signature(song, sections)
    _existing_mt_time_sig = str(st.session_state.get("mt_time_signature") or "").strip()
    if not _existing_mt_time_sig:
        st.session_state["mt_time_signature"] = _default_mt_time_sig
        mt_time_sig = _default_mt_time_sig
    else:
        mt_time_sig = _existing_mt_time_sig
    mt_beats_per_bar = beats_per_bar_from_signature(mt_time_sig)
    mt_sec_names = [
        name
        for name, chs in section_order(
            sections,
            section_names=section_names_from_song(song_data),
        )
        if chs
    ]

    with st.container(key="multitrack_studio_panel", border=False):
        render_multitrack_studio_panel_header(st, song_title=str(song or "Your song"))

        with st.container(key="multitrack_session_panel", border=False):
            (
                mt_bpm,
                mt_loops,
                mt_groove,
                mt_resolved_groove,
                mt_selected_sections,
                mt_events,
                mt_backing_duration,
                mt_count_in_bars,
                mt_scope_label,
            ) = _render_multitrack_session_setup_panel(
                mt_sec_names=mt_sec_names,
                mt_time_sig=mt_time_sig,
                song_data=song_data,
                song_title=str(song or "Your song"),
                original_key=_mt_orig_key,
                practice_key=_mt_practice_key,
                setup_header_fn=render_multitrack_session_setup_header,
                context_strip_fn=render_multitrack_session_context_strip,
                section_open_fn=render_multitrack_setup_section_open,
                section_close_fn=render_multitrack_setup_section_close,
                field_label_fn=render_multitrack_field_label,
            )

        monitor_wav = st.session_state.get("multitrack_backing_music_wav")
        backing_load_error = str(st.session_state.get("_mt_backing_load_error") or "").strip()
        backing_playback_status = str(st.session_state.get("_mt_backing_playback_status") or "").strip()
        if backing_load_error and not monitor_wav:
            st.warning(
                "Saved backing settings loaded, but monitor backing audio is not playable on this device "
                f"({backing_load_error.replace('_', ' ')})."
            )
        elif backing_playback_status == "metadata_only" and not monitor_wav:
            st.info("Saved backing settings loaded — prepare backing again or reload when cloud audio is available.")
        use_backing_monitor = bool(st.session_state.get("mt_use_backing_monitor", True))
        backing_b64 = (
            base64.b64encode(monitor_wav).decode("ascii")
            if monitor_wav and use_backing_monitor
            else None
        )

        if monitor_wav and use_backing_monitor:
            with st.expander("Preview monitor backing", expanded=False):
                st.audio(monitor_wav, format="audio/wav")

        track_items_for_mix = []
        try:
            from multitrack_mixer_state import (
                commit_all_multitrack_mixer_widgets,
                prepare_multitrack_mixer_widgets,
            )

            prepare_multitrack_mixer_widgets(st.session_state)
        except ImportError:
            commit_all_multitrack_mixer_widgets = None  # type: ignore[assignment]
            prepare_multitrack_mixer_widgets = None  # type: ignore[assignment]

        mt_controls = ensure_multitrack_track_controls(st.session_state)

        with st.container(key="multitrack_layers_panel", border=False):
            st.markdown(
                '<p class="ui-multitrack-step-kicker">Step 2 · Layers</p>',
                unsafe_allow_html=True,
            )
            st.caption("Record or upload each instrument slot, then adjust volume, mute, and solo.")
            st.caption(
                "**How this works:** Align = shift a layer earlier/later · "
                "Mute = silence a layer · Solo = hear one layer by itself · "
                "Monitor backing = hear the backing while recording · "
                "Loop section = repeat the selected section while recording"
            )

            for slot in MT_SLOTS:
                _slot_ready = bool(st.session_state.mt_tracks.get(slot))
                st.markdown(
                    f"**{html.escape(slot)}** {multitrack_layer_badge_html(ready=_slot_ready)}",
                    unsafe_allow_html=True,
                )
                with st.expander(f"Layer controls — {slot}", expanded=_slot_ready):
                    c1, c2, c3 = st.columns([1.2, 1, 1])

                    with c1:
                        layer_name = st.text_input(
                            "Layer name",
                            value=st.session_state.get(f"mt_name_{slot}", slot),
                            key=f"mt_name_{slot}",
                        )
                        uploaded = st.file_uploader(
                            f"Upload — {slot}",
                            type=["wav", "mp3", "m4a", "ogg"],
                            key=f"mt_upload_{slot}",
                        )
                        try:
                            recorded = st.audio_input(f"Record — {slot}", key=f"mt_record_{slot}")
                        except Exception:
                            recorded = None
                            st.caption("Recording unavailable in this build — upload still works.")

                        _mt_audio_obj = recorded if recorded is not None else uploaded
                        if _mt_audio_obj is not None:
                            _mt_bytes = _mt_audio_obj.getvalue()
                            if st.session_state.mt_tracks.get(slot) != _mt_bytes:
                                st.session_state.mt_tracks[slot] = _mt_bytes
                                st.session_state.mt_track_filenames[slot] = getattr(
                                    _mt_audio_obj, "name", f"{slot}.wav"
                                )
                                try:
                                    from music_persistent_state import force_save_music_state
                                    from studio_page_persistence import flush_current_page_snapshot

                                    flush_current_page_snapshot(st.session_state)
                                    force_save_music_state(st, reason="multitrack_upload")
                                except Exception:
                                    pass

                        if st.button(f"Save layer — {slot}", key=f"mt_save_{slot}"):
                            audio_obj = recorded if recorded is not None else uploaded
                            if audio_obj is not None:
                                st.session_state.mt_tracks[slot] = audio_obj.getvalue()
                                st.session_state.mt_track_filenames[slot] = getattr(
                                    audio_obj, "name", f"{slot}.wav"
                                )
                                try:
                                    from music_activity import log_media_upload

                                    log_media_upload(
                                        st,
                                        media_type="audio",
                                        filename=str(
                                            getattr(audio_obj, "name", None) or f"{slot}.wav"
                                        ),
                                        page="Multitrack",
                                    )
                                except Exception:
                                    pass
                                st.success(f"{layer_name} saved.")
                                try:
                                    from music_persistent_state import force_save_music_state

                                    force_save_music_state(st, reason="multitrack_layer_save")
                                except Exception:
                                    pass
                                st.rerun()
                            st.warning("Record or upload audio first.")

                    with c2:
                        st.slider(
                            "Volume",
                            0.0,
                            2.0,
                            step=0.05,
                            key=f"mt_vol_{slot}",
                        )
                        st.slider(
                            "Align timing",
                            -3.0,
                            3.0,
                            step=0.05,
                            key=f"mt_delay_{slot}",
                            help="Move this layer earlier or later to line it up with the backing.",
                        )
                        st.caption(
                            "Negative = earlier. Positive = later. "
                            "Use this if the layer sounds ahead of or behind the backing."
                        )

                    with c3:
                        st.checkbox(
                            "Mute",
                            key=f"mt_mute_{slot}",
                            help="Temporarily silence this layer during playback.",
                        )
                        st.checkbox(
                            "Solo",
                            key=f"mt_solo_{slot}",
                            help="Hear this layer by itself to check it more clearly.",
                        )
                        try:
                            from multitrack_mixer_state import commit_multitrack_mixer_widget

                            ctrl = commit_multitrack_mixer_widget(
                                st.session_state,
                                slot,
                                layer_name=layer_name,
                            )
                        except ImportError:
                            ctrl = mt_controls.setdefault(
                                slot,
                                {"volume": 1.0, "mute": False, "solo": False, "delay": 0.0},
                            )
                            ctrl["volume"] = float(st.session_state.get(f"mt_vol_{slot}", 1.0))
                            ctrl["delay"] = float(st.session_state.get(f"mt_delay_{slot}", 0.0))
                            ctrl["mute"] = bool(st.session_state.get(f"mt_mute_{slot}", False))
                            ctrl["solo"] = bool(st.session_state.get(f"mt_solo_{slot}", False))

                    saved_audio = st.session_state.mt_tracks.get(slot)
                    if saved_audio:
                        st.audio(saved_audio)
                        track_items_for_mix.append(
                            {
                                "slot": slot,
                                "name": layer_name,
                                "audio_bytes": saved_audio,
                                "filename": st.session_state.mt_track_filenames.get(
                                    slot, f"{slot}.wav"
                                ),
                                "volume": float(ctrl.get("volume", 1.0)),
                                "delay": float(ctrl.get("delay", 0.0)),
                                "mute": bool(ctrl.get("mute", False)),
                                "solo": bool(ctrl.get("solo", False)),
                            }
                        )

            if commit_all_multitrack_mixer_widgets is not None:
                mt_controls = commit_all_multitrack_mixer_widgets(st.session_state)
            else:
                st.session_state["mt_track_controls"] = dict(mt_controls)
            try:
                from studio_page_persistence import flush_current_page_snapshot

                flush_current_page_snapshot(st.session_state)
            except Exception:
                pass

        if track_items_for_mix:
            st.markdown(
                f'<p class="ui-mt-target-line">'
                f'<strong>{len(track_items_for_mix)}</strong> layer(s) saved for this session.</p>',
                unsafe_allow_html=True,
            )

        track_items_for_studio = list(track_items_for_mix)
        ensure_multitrack_track_controls(st.session_state)
        studio_tracks = multitrack_studio_track_payloads(track_items_for_studio, mt_controls)

        with st.container(key="multitrack_transport_panel", border=False):
            st.markdown(
                '<p class="ui-multitrack-step-kicker">Step 3 · Transport &amp; mixer</p>',
                unsafe_allow_html=True,
            )
            try:
                from multitrack_session_persistence import (
                    apply_multitrack_free_layering_guard,
                    multitrack_is_free_layering_mode,
                    multitrack_step3_backing_controls_disabled,
                )

                _free_layering = multitrack_is_free_layering_mode(st.session_state)
                _backing_controls_disabled = multitrack_step3_backing_controls_disabled(
                    st.session_state
                )
                apply_multitrack_free_layering_guard(st.session_state)
            except ImportError:
                _free_layering = (
                    str(st.session_state.get("mt_playback_scope") or "")
                    == "Free layering (no backing)"
                )
                _backing_controls_disabled = _free_layering
                if _free_layering:
                    st.session_state["include_backing_mix"] = False
                    st.session_state["mt_use_backing_monitor"] = False
                    st.session_state["mt_loop_backing"] = False
            _has_backing = bool(monitor_wav)
            try:
                from media_multitrack_catalog import seed_multitrack_backing_volume

                seed_multitrack_backing_volume(st.session_state)
            except ImportError:
                if "mt_backing_volume" not in st.session_state:
                    st.session_state["mt_backing_volume"] = 0.75
            st.caption(
                "Press **Play with count-in** for a studio-style start. "
                "Volume, mute, and solo are edited in **Step 2** — the mixer below shows a read-only preview."
            )
            _tr1, _tr2, _tr3 = st.columns(3, gap="small")
            with _tr1:
                mt_loop_backing = st.checkbox(
                    "Repeat selected section while recording",
                    key="mt_loop_backing",
                    disabled=_backing_controls_disabled,
                    help="Keeps looping the selected section while you record.",
                )
            with _tr2:
                mt_metronome_playback = st.checkbox(
                    "Click monitor",
                    key="mt_metronome_playback",
                    help="Metronome click during playback.",
                )
            with _tr3:
                use_backing_monitor = st.checkbox(
                    "Hear backing during playback",
                    key="mt_use_backing_monitor",
                    disabled=_backing_controls_disabled,
                    help="Play the prepared backing track while transport runs.",
                )
            _mix1, _mix2 = st.columns([1.2, 1], gap="small")
            with _mix1:
                backing_volume = st.slider(
                    "Backing level",
                    min_value=0.0,
                    max_value=1.5,
                    step=0.05,
                    key="mt_backing_volume",
                    disabled=_backing_controls_disabled,
                    help="Controls how loud the backing track is compared with your recorded layers.",
                )
            with _mix2:
                include_backing_in_mix = st.checkbox(
                    "Include backing in exported mix",
                    key="include_backing_mix",
                    disabled=_backing_controls_disabled,
                    help="When enabled, Step 4 export mixes the prepared backing with your layers.",
                )
            if _free_layering:
                st.caption(
                    "Free Layering mode: backing monitor, section repeat, backing level, and "
                    "export-with-backing are disabled. Layer recording and click monitor remain available."
                )
            elif not _has_backing:
                st.caption(
                    "Prepare a backing track in Step 1 before playback/export uses these settings. "
                    "You can still configure backing level, monitor, repeat, and export options here."
                )
            else:
                st.caption(
                    "Transport and mix-export settings persist across refresh and saved projects. "
                    "Edit layer volume, mute, and solo in Step 2."
                )
            try:
                from studio_page_persistence import flush_current_page_snapshot

                flush_current_page_snapshot(st.session_state)
            except Exception:
                pass
            use_backing_monitor = bool(st.session_state.get("mt_use_backing_monitor", True))
            include_backing_in_mix = bool(st.session_state.get("include_backing_mix", False))
            backing_volume = float(st.session_state.get("mt_backing_volume", 0.75))
            backing_b64_for_studio = (
                base64.b64encode(monitor_wav).decode("ascii")
                if monitor_wav and use_backing_monitor
                else None
            )
            components.html(
                multitrack_studio_html(
                    backing_b64=backing_b64_for_studio,
                    tracks=studio_tracks,
                    bpm=mt_bpm,
                    beats_per_bar=mt_beats_per_bar,
                    count_in_bars=mt_count_in_bars,
                    metronome_during_playback=mt_metronome_playback,
                    loop_backing=mt_loop_backing,
                    backing_monitor_enabled=bool(backing_b64_for_studio),
                    backing_monitor_volume=float(st.session_state.get("mt_backing_volume", backing_volume)),
                    scope_label=st.session_state.get("mt_backing_scope", mt_scope_label),
                    time_signature=mt_time_sig,
                    backing_duration_sec=float(
                        st.session_state.get("mt_backing_duration", mt_backing_duration)
                    ),
                ),
                height=560,
                scrolling=True,
            )

        with st.container(key="multitrack_export_panel", border=False):
            st.markdown(
                '<p class="ui-multitrack-step-kicker">Step 4 · Export</p>',
                unsafe_allow_html=True,
            )

            if not track_items_for_mix:
                st.info("Save at least one layer above to export a mix.")

            if st.button("Create mixed WAV", disabled=not track_items_for_mix, use_container_width=True):
                try:
                    backing_y = None
                    _include_backing_in_mix = bool(st.session_state.get("include_backing_mix", False))
                    _backing_volume = float(st.session_state.get("mt_backing_volume", 0.75))
                    if _include_backing_in_mix and mt_events:
                        backing_y = backing_bytes_to_float(
                            mt_events,
                            bpm=mt_bpm,
                            style=mt_resolved_groove,
                            level=level,
                        )
                        if mt_loops > 1:
                            backing_y = np.tile(backing_y, int(mt_loops))
                        backing_y = backing_y * _backing_volume

                    mixed = mix_multitrack(backing_y, track_items_for_mix)
                    st.session_state.mixed_track_wav = wav_bytes_from_float(mixed)
                    st.success("Mixed track created.")
                except Exception as e:
                    st.error(f"Could not create mix: {e}")

            from multitrack_export_ui import (
                render_multitrack_export_library,
                render_step4_save_export_panel,
            )
            from multitrack_session_persistence import resolve_mixed_export_wav_bytes

            mixed_export_wav = resolve_mixed_export_wav_bytes(st.session_state)
            if mixed_export_wav:
                st.audio(mixed_export_wav, format="audio/wav")
                st.download_button(
                    "Download mixed track WAV",
                    mixed_export_wav,
                    file_name=f"{song.replace(' ', '_')}_multitrack_mix.wav",
                    mime="audio/wav",
                    use_container_width=True,
                )
                render_step4_save_export_panel(
                    st,
                    st.session_state,
                    song_title=str(song or ""),
                    track_items_for_mix=track_items_for_mix,
                    include_backing=bool(st.session_state.get("include_backing_mix", False)),
                    backing_volume=float(st.session_state.get("mt_backing_volume", 0.75)),
                    mixed_wav=mixed_export_wav,
                )
                st.caption(
                    "Want AI coaching on this take? Save the export, then use **Send to Upload Analysis** below."
                )

            render_multitrack_export_library(st, st.session_state, song_title=str(song or ""))

            if st.button("Clear all multitrack layers", use_container_width=True):
                try:
                    from multitrack_session_persistence import clear_multitrack_persisted_state
                    from music_persistent_state import force_save_music_state
                    from studio_page_persistence import flush_current_page_snapshot

                    clear_multitrack_persisted_state(st.session_state)
                    flush_current_page_snapshot(st.session_state)
                    force_save_music_state(st, reason="multitrack_clear_all")
                except Exception:
                    st.session_state.mt_tracks = {slot: None for slot in MT_SLOTS}
                    st.session_state.mt_track_filenames = {
                        slot: f"{slot.replace(' ', '_').lower()}.wav" for slot in MT_SLOTS
                    }
                    st.session_state.mixed_track_wav = None
                    st.session_state.pop("multitrack_backing_music_wav", None)
                    st.session_state.mt_track_controls = {}
                st.success("Layers cleared.")
                st.rerun()

            try:
                from multitrack_project_load_trace import capture_post_render_session_trace

                capture_post_render_session_trace(st.session_state, source="multitrack_page_pre_history")
            except ImportError:
                pass
            try:
                from multitrack_session_persistence import flush_multitrack_workspace_snapshot

                flush_multitrack_workspace_snapshot(st.session_state, st=st)
            except ImportError:
                pass

            try:
                from studio_history_ui import render_multitrack_history_panel

                render_multitrack_history_panel(st, song_title=str(song or ""))
            except Exception:
                pass

# -------------------------------------------------
# OPENAI COACHING HUB
# -------------------------------------------------

elif _studio_page == "openai":

    ensure_page_initialized(st.session_state, "openai")
    note_page_visit(st.session_state, "openai")

    _studio_page_header(
        "✨",
        "OpenAI Coaching",
        "AI-powered practice tools for your active song and session history.",
    )

    st.markdown(
        '<div class="ui-card soft" style="margin:0 0 1rem 0;">'
        "<strong>Your AI coach is ready.</strong> "
        "Use the tools below for insights, analysis, and creative guidance. "
        "More features will land here over time."
        "</div>",
        unsafe_allow_html=True,
    )

    _ai_c1, _ai_c2 = st.columns(2)
    with _ai_c1:
        st.markdown("#### Available now")
        if st.button(
            "Practice log insights",
            key="openai_hub_log",
            use_container_width=True,
            help="AI review of your practice history and session patterns.",
        ):
            navigate_studio_page(st.session_state, "log")
            st.rerun()
        if st.button(
            "Upload analysis",
            key="openai_hub_analysis",
            use_container_width=True,
            help="Analyze a recording with AI-assisted feedback.",
        ):
            navigate_studio_page(st.session_state, "analysis")
            st.rerun()
        if st.button(
            "Creative Lab",
            key="openai_hub_creative",
            use_container_width=True,
            help="Harmony, improvisation, and growth tools.",
        ):
            navigate_studio_page(st.session_state, "creative")
            st.rerun()
    with _ai_c2:
        st.markdown("#### Coming soon")
        st.caption("Practice coaching on the active song")
        st.caption("Personalized song recommendations")
        st.caption("Recording comparisons")
        st.caption("Practice summaries")
        st.caption("AI-generated next-session plans")

# -------------------------------------------------
# PRACTICE LOG
# -------------------------------------------------

elif _studio_page == "log":

    ensure_page_initialized(st.session_state, "log")
    note_page_visit(st.session_state, "log")
    st.session_state.setdefault(
        "_practice_log_load_workspace_at_page_open",
        st.session_state.get("_suite_active_workspace_id"),
    )
    _studio_page_header(
        "📓",
        "Practice Log",
        "Log sessions and get specific coaching — what to keep working on next.",
        page_id="log",
    )
    _inject_practice_log_studio_styles()

    from practice_log_state import load_entries
    from practice_log_ui import render_practice_log_page

    def _on_practice_log_saved(saved_entry: dict) -> None:
        try:
            from suite_activity_client import record_activity

            local_state = build_music_local_state(st)
            song_title = str(saved_entry.get("active_song") or saved_entry.get("song") or song)
            local_state["mode"] = str(saved_entry.get("practice_type") or saved_entry.get("mode") or "")
            record_activity(
                "music",
                "practice",
                page="Practice Log",
                metrics={
                    "song": song_title,
                    "artist": str(saved_entry.get("artist") or (song_data or {}).get("artist") or ""),
                    "pick_key": str(
                        saved_entry.get("song_id")
                        or local_state.get("pick_key")
                        or st.session_state.get("active_catalog_pick_key")
                        or ""
                    ),
                    "minutes": int(saved_entry.get("duration_minutes") or saved_entry.get("minutes") or 0),
                    "focus": str(saved_entry.get("focus_area") or saved_entry.get("focus") or focus),
                    "instrument": saved_entry.get("instrument") or local_state.get("instrument", ""),
                    "display_key": saved_entry.get("display_key") or local_state.get("display_key", ""),
                    "practice_focus_section": local_state.get("practice_focus_section", ""),
                },
                summary=f"Practiced {song_title}",
                resume_key=f"song:{st.session_state.get('active_catalog_pick_key', song_title)}",
                resume_title=f"Continue: {song_title}",
                resume_subtitle=str(saved_entry.get("focus_area") or focus or instrument),
                local_state=local_state,
            )
            st.session_state["last_practice_mode"] = str(
                saved_entry.get("practice_type") or saved_entry.get("mode") or ""
            )
        except Exception:
            pass

    with st.container(key="log_add_session_panel", border=False):
        render_practice_log_page(st, st.session_state, on_saved=_on_practice_log_saved)

    with st.container(key="log_practice_analysis_panel", border=False):
        from practice_log_analysis_panel import render_practice_analysis_panel

        render_practice_analysis_panel(st, st.session_state)

    with st.container(key="log_timed_planner_panel", border=False):
        st.markdown(
            '<div class="ui-plog-planner-banner">'
            '<p class="ui-plog-planner-banner-title">Timed Session Planner</p>'
            '<p class="ui-plog-planner-banner-sub">Plan your next practice session by time block</p>'
            "</div>",
            unsafe_allow_html=True,
        )
        with st.expander("Build a timed session plan", expanded=False):
            st.session_state.setdefault("ai_session_builder_minutes", 30)
            _session_mins = st.slider(
                "Target session length (minutes)",
                20,
                90,
                int(st.session_state.get("ai_session_builder_minutes", 30)),
                5,
                key="ai_session_builder_minutes",
            )
            if st.button("Build timed session plan", key="build_session_from_logs", use_container_width=False):
                st.session_state["_ai_practice_session_plan"] = build_practice_session_from_logs(
                    load_entries(st.session_state),
                    ALL_SONG_RECORDS,
                    minutes=int(_session_mins),
                )
            _plan = st.session_state.get("_ai_practice_session_plan")
            if _plan:
                st.caption(_plan.get("summary", ""))
                for label, icon in (
                    ("warmup", "🌅"),
                    ("technique", "⚙️"),
                    ("main", "🎯"),
                    ("challenge", "🔥"),
                    ("cooldown", "🌙"),
                ):
                    if _plan.get(label):
                        st.markdown(f"{icon} **{label.title()}** — {_plan[label]}")

try:
    from studio_nav_history import flush_deferred_history_nav_save, record_nav_history_trace

    if flush_deferred_history_nav_save(st):
        record_nav_history_trace(st, st.session_state)
except Exception:
    pass

if not pp.skip_background_persistence(st):
    try:
        from music_persistent_state import (
            autosave_music_state,
            clear_music_workspace_autosave_block,
            force_save_music_state,
            maybe_flush_pending_active_song_edits,
            maybe_flush_pending_backing_edits,
            maybe_flush_pending_practice_edits,
        )

        maybe_flush_pending_active_song_edits(st)
        maybe_flush_pending_practice_edits(st)
        maybe_flush_pending_backing_edits(st)
        autosave_music_state(st)
        if st.session_state.pop("_suite_persist_insight_dirty", None):
            force_save_music_state(st, reason="insight_persist")
        clear_music_workspace_autosave_block(st)
    except Exception:
        pass

try:
    from app_ui import render_deferred_music_coach_insight

    render_deferred_music_coach_insight(
        st,
        studio_page=str(st.session_state.get("studio_page") or _studio_page or "practice"),
    )
except Exception as exc:
    st.session_state["_ami_deferred_insight_render_error"] = str(exc)

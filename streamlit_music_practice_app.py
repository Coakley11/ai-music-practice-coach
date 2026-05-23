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
import time
import base64
import traceback
from pathlib import Path
from datetime import date

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------

st.set_page_config(
    page_title="Daniel Cohen AI Music Practice Coach",
    page_icon="🎵",
    layout="wide"
)

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
    record_for_pick_key,
)
from songs import (
    ACTIVE_CATALOG_PICK_KEY,
    ACTIVE_MUSIC_SOURCE_KEY,
    BACKING_NEEDS_REGEN,
    SOURCE_CATALOG,
    SOURCE_CUSTOM,
    active_source_banner,
    unpack_active_source_banner,
    apply_pick_key,
    build_active_chart_bundle,
    chord_blocks_for_backing,
    clear_backing_needs_regen,
    display_key_context,
    ensure_active_music_source,
    ensure_master_song_initialized,
    form_timeline_rows,
    get_song_context,
    invalidate_backing_cache,
    is_custom_progression,
    note_active_source_change,
    note_display_key_change,
    on_cpl_jump_home_key,
    prepare_cpl_jump_home,
    request_backing_bpm,
    request_display_key,
    section_order,
    sync_matching_song_dropdown_before_widget,
    sync_backing_bpm_before_widget,
    set_catalog_source,
    set_custom_source,
    sync_display_key_before_widget,
)
from songs.key_state import mark_display_key_changed
from songs.playback_defaults import (
    default_bpm_for_song_data,
    default_groove_for_song,
    playback_song_id,
    sync_backing_groove_before_widget,
    sync_playback_defaults_for_active_song,
)
from instrument_transposition import (
    CHART_IN_INSTRUMENT_KEY_KEY,
    SELECTED_TRANSPOSING_INSTRUMENT_KEY,
    is_transposing_instrument,
    render_practice_transposing_helper,
    render_sidebar_transposing_controls,
    selected_saxophone_type,
)

from backing_audio import (
    _chord_head,
    backing_bytes_to_float,
    bass_note,
    chord_notes,
    generate_backing_track,
    infer_groove_style,
    pcm16_wav_bytes_from_float,
    synthesize_chords_to_numpy,
    wav_bytes_from_float,
)
from coach_overlay import section_overlay_html as _section_overlay

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

try:
    from practice_studio import (
        PRACTICE_FOCUS_FULL,
        beginner_transpose_suggestions,
        build_practice_session_from_logs,
        fretboard_ascii,
        practice_active_section_name,
        practice_display_sections,
        practice_is_full_song,
        practice_section_options,
        rhythm_guide_markdown,
        scale_suggestions_for_chord,
        section_deep_practice_markdown,
        active_song_card_details,
        song_card_meta,
        song_groove_seed,
    )
    from practice_notation import generate_practice_notation, notation_tab_html
except Exception:
    PRACTICE_FOCUS_FULL = "Full Song"

    def practice_section_options(sections):
        return [PRACTICE_FOCUS_FULL] + list(sections.keys())

    def practice_is_full_song(focus):
        return not focus or focus == PRACTICE_FOCUS_FULL

    def practice_display_sections(sections, focus):
        if practice_is_full_song(focus):
            return sections
        if focus in sections:
            return {focus: sections[focus]}
        return sections

    def practice_active_section_name(focus, sections):
        return None if practice_is_full_song(focus) else focus
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
        render_page_quick_nav,
        render_section_jump_bar,
        render_studio_brand_header,
        render_studio_nav,
        ensure_studio_page,
        session_badges,
        sidebar_section,
        sidebar_source_banner,
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
                render_page_quick_nav = getattr(_app_ui_mod, "render_page_quick_nav", None)
                render_section_jump_bar = getattr(_app_ui_mod, "render_section_jump_bar", None)
                render_studio_brand_header = _app_ui_mod.render_studio_brand_header
                render_studio_nav = _app_ui_mod.render_studio_nav
                ensure_studio_page = getattr(_app_ui_mod, "ensure_studio_page", None)
                session_badges = _app_ui_mod.session_badges
                sidebar_section = _app_ui_mod.sidebar_section
                sidebar_source_banner = _app_ui_mod.sidebar_source_banner
                _APP_UI_LOADED = True
                _APP_UI_IMPORT_ERROR = None
        except Exception as _app_ui_path_err:
            traceback.print_exc()
            _APP_UI_IMPORT_ERROR = _app_ui_path_err

if not _APP_UI_LOADED:
    st.error(
        "app_ui import failed: "
        f"{_APP_UI_IMPORT_ERROR!r}. "
        "Ensure **app_ui.py** is in the repository root next to this file, then redeploy. "
        "Using basic layout fallbacks so the app can still run."
    )

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
        session_state["studio_page"] = ids[labels.index(pick)]
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
                "Display / practice key",
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
            st.slider("BPM", 50, 180, 100, 5, key=kwargs.get("bpm_key", "backing_track_bpm"))

    def render_section_jump_bar(section_names, session_state, *, state_key="practice_focus_section", rerun_fn=None):
        options = [n for n in section_names if n]
        if not options:
            return None
        if session_state.get(state_key) not in options:
            session_state[state_key] = options[0]
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

TRUSTED_CORE_RECORDS = [
    r for r in ALL_SONG_RECORDS
    if r.get("trusted_core") or r.get("chart_status") in {"verified", "practice_level_verified"}
]
DEFAULT_SONG_RECORDS = TRUSTED_CORE_RECORDS or ALL_SONG_RECORDS

ensure_master_song_initialized(
    st,
    all_records=DEFAULT_SONG_RECORDS,
    song_library=SONG_LIBRARY,
    song_picker_catalog=SONG_PICKER_CATALOG,
)

_catalog_genre, _catalog_song, _catalog_song_data = get_song_context(
    st,
    song_library=SONG_LIBRARY,
    song_picker_catalog=SONG_PICKER_CATALOG,
)

if CPL_ACTIVE_KEY not in st.session_state:
    st.session_state[CPL_ACTIVE_KEY] = default_active_progression()
if CPL_SAVED_KEY not in st.session_state:
    st.session_state[CPL_SAVED_KEY] = {}
ensure_active_music_source(st.session_state)

if (
    DEFAULT_SONG_RECORDS
    and _normalize_library_mode(st.session_state.get("chart_library_mode", DEFAULT_CHART_LIBRARY_MODE))
    == LIBRARY_MODE_CORE
    and not _catalog_song_data.get("trusted_core")
    and _catalog_song_data.get("chart_status") not in {"verified", "practice_level_verified"}
):
    _r0 = DEFAULT_SONG_RECORDS[0]
    _pk0 = format_pick_key(_r0["genre"], f"{_r0['title']} — {_r0['artist']}")
    apply_pick_key(st, _pk0, SONG_PICKER_CATALOG)
    _catalog_genre, _catalog_song, _catalog_song_data = get_song_context(
        st,
        song_library=SONG_LIBRARY,
        song_picker_catalog=SONG_PICKER_CATALOG,
    )

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
    explicit_versions = song_data.get("chart_versions") or {}
    if level in explicit_versions and explicit_versions[level]:
        return explicit_versions[level]

    raw = song_data.get("sections", {})
    genre_name = song_data.get("genre", "")
    if level == "Beginner":
        return {name: [_simplify_chord(ch, genre_name) for ch in chords] for name, chords in raw.items()}
    if level == "Intermediate":
        return {name: [_intermediate_chord(ch) for ch in chords] for name, chords in raw.items()}
    return {name: [_advanced_chord(ch, song_data.get("genre", "")) for ch in chords] for name, chords in raw.items()}


def chart_status_label(song_data):
    """Internal catalog quality flag — not shown in the UI."""
    user_ov = song_data.get("user_override") or {}
    if user_ov:
        return ("saved_edits", "success")
    status = (song_data.get("chart_status") or "placeholder").strip()
    return (status, "info")


def chart_source_caption(song_data) -> str:
    """User-facing chord chart line (no catalog quality labels)."""
    user_ov = song_data.get("user_override") or {}
    if user_ov:
        return "**Chord chart:** Your saved edits apply everywhere in the studio."
    return "**Chord chart:** Open **Edit Song Chart** below to refine chords if needed."


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


def chord_blocks_for_selected_sections(sections, selected_names=None):
    selected = set(selected_names or [])
    out = []
    for section_name, section_chords in section_order(sections):
        if selected and section_name not in selected:
            continue
        out.extend(section_chords)
    return out


def chord_events_for_selected_sections(sections, selected_names=None):
    selected = set(selected_names or [])
    out = []
    for section_name, section_chords in section_order(sections):
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
        lyric = lyric_lines[0] if lyric_lines else "Add a cue in the sidebar"
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


def _section_match_score(label, section_name):
    label_norm = " ".join(label.lower().replace("-", " ").replace("/", " ").split())
    section_norm = " ".join(section_name.lower().replace("-", " ").replace("/", " ").split())
    section_base = _section_base_name(section_name).replace("-", " ")
    if not label_norm or not section_norm:
        return None
    if label_norm == section_norm:
        return 0
    if label_norm == section_base:
        return 1
    section_tokens = set(section_norm.split())
    label_tokens = set(label_norm.split())
    if label_tokens and label_tokens.issubset(section_tokens):
        if label_norm == "chorus" and "pre" in section_tokens:
            return 8
        return 2
    if label_norm in section_norm:
        if label_norm == "chorus" and "pre chorus" in section_norm:
            return 8
        return 4
    return None


def match_lyric_section_label(label, section_names):
    scored = []
    for idx, section_name in enumerate(section_names):
        score = _section_match_score(label, section_name)
        if score is not None:
            scored.append((score, len(section_name), idx, section_name))
    if not scored:
        return None
    return sorted(scored)[0][3]


def parse_user_lyric_cues(raw_text, section_names):
    """User-provided cues only. No lyric scraping or generation."""
    if not raw_text:
        return {}

    cues = {name: [] for name in section_names}
    current = None

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if ":" in line:
            maybe_section, cue = line.split(":", 1)
            match = match_lyric_section_label(maybe_section.strip(), section_names)
            if match:
                current = match
                if cue.strip():
                    cues[current].append(cue.strip())
                continue

        if current is None:
            current = section_names[0] if section_names else None

        if current:
            cues[current].append(line)

    return {name: lines for name, lines in cues.items() if lines}


def _song_slug(song_name, artist_name=""):
    raw = f"{song_name}_{artist_name}".lower()
    return "".join(c if c.isalnum() else "_" for c in raw).strip("_")


def _section_base_name(section_name):
    return section_name.split("(", 1)[0].split("/", 1)[0].strip().lower()


def split_lyrics_by_sections(raw_text, section_names):
    """Best-effort assignment from user-provided lyrics/cues to chart sections."""
    if not raw_text:
        return {}

    parsed = parse_user_lyric_cues(raw_text, section_names)
    if parsed:
        return {name: "\n".join(lines) for name, lines in parsed.items()}

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines or not section_names:
        return {}

    out = {name: "" for name in section_names}
    chunk_size = max(1, int(np.ceil(len(lines) / max(1, len(section_names)))))
    for idx, section_name in enumerate(section_names):
        chunk = lines[idx * chunk_size:(idx + 1) * chunk_size]
        if chunk:
            out[section_name] = "\n".join(chunk)
    return {name: text for name, text in out.items() if text.strip()}


def lyric_cues_from_section_lyrics(section_lyrics):
    cues = {}
    for section_name, text in (section_lyrics or {}).items():
        lines = [line.strip() for line in str(text).splitlines() if line.strip()]
        if lines:
            cues[section_name] = lines
    return cues


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
        out.append(f"- {section_name}: phrase/section entry starts around **{entry}**. Add your own lyric cue in the sidebar for tighter alignment.")

    return "\n".join(out)


def lyric_guide_markdown(sections, lyric_cues, instrument, section_lyrics=None):
    out = ["### Lyric / Section Cue Guide"]
    if instrument == "Voice":
        out.append("_Use this to map entrances, breaths, vowels, phrase peaks, and delivery. Paste your own lyrics/cues in the sidebar for exact alignment._")
    else:
        out.append("_Short locator cues help you know where you are in the form. The app does not fetch or generate full copyrighted lyrics._")

    for section_name, chords in sections.items():
        cue_lines = lyric_cues.get(section_name, []) if lyric_cues else []
        full_text = (section_lyrics or {}).get(section_name, "")
        entry = chords[0] if chords else "the first chord"
        peak = chords[max(0, len(chords) // 2)] if chords else "the middle"
        if cue_lines:
            cue = "; ".join(cue_lines[:2])
        elif instrument == "Voice":
            cue = f"Enter on {entry}; breathe before the section; shape toward {peak}."
        else:
            cue = f"{section_name} entry around {entry}; listen for the section change and phrase shape."
        out.append(f"- **{section_name}** ({len(chords)} bars): {cue}")
        if instrument == "Voice" and full_text:
            out.append(f"  - Delivery: speak the text in rhythm first, mark a breath before bar 1, and sing stronger near **{peak}**.")
            for line in str(full_text).splitlines()[:2]:
                if line.strip():
                    out.append(f"  - Lyric line: _{line.strip()}_")
    return "\n".join(out)


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


def render_metronome_widget(
    default_bpm=100,
    default_signature="4/4",
    *,
    section_bars: int = 0,
    section_label: str = "",
    loop_section: bool = False,
):
    config = json.dumps({
        "bpm": int(default_bpm),
        "signature": default_signature,
        "sectionBars": int(section_bars) if loop_section and section_bars > 0 else 0,
        "sectionLabel": section_label or "",
    })
    loop_note = ""
    if loop_section and section_bars > 0 and section_label:
        loop_note = (
            f"<p style='margin:0 0 8px 0;color:#166534;font-weight:650;'>"
            f"Section loop: <strong>{html.escape(section_label)}</strong> "
            f"({section_bars} bar{'s' if section_bars != 1 else ''}) — metronome resets after each pass.</p>"
        )
    widget_html = f"""
    <div id="metro-root" style="font-family: system-ui, -apple-system, Segoe UI, sans-serif; border:1px solid #ddd; border-radius:12px; padding:14px; max-width:760px;">
      <h4 style="margin:0 0 10px 0;">Practice Metronome</h4>
      {loop_note}
      <div style="display:flex; gap:12px; flex-wrap:wrap; align-items:end;">
        <label>BPM<br><input id="metro-bpm" type="range" min="40" max="240" value="{default_bpm}" style="width:220px;"></label>
        <div><strong id="metro-bpm-label">{default_bpm}</strong> BPM</div>
        <label>Time signature<br>
          <select id="metro-sig">
            <option>2/4</option><option>3/4</option><option selected>4/4</option>
            <option>6/8</option><option>3/8</option><option>5/4</option><option>7/8</option>
          </select>
        </label>
        <button id="metro-start" style="padding:8px 14px;">Start Metronome</button>
        <button id="metro-stop" style="padding:8px 14px;">Stop Metronome</button>
      </div>
      <div style="margin-top:12px;">
        <div>Beat: <strong id="metro-beat">-</strong> / <span id="metro-beats-per-measure">4</span> | Measure: <strong id="metro-measure">0</strong></div>
        <div id="metro-dots" style="display:flex; gap:8px; margin-top:10px;"></div>
      </div>
      <p style="margin:10px 0 0 0; color:#666; font-size:13px;">First beat is accented higher/louder; other beats are softer/lower. Audio starts after pressing Start.</p>
    </div>
    <script>
    (() => {{
      const cfg = {config};
      const bpmInput = document.getElementById("metro-bpm");
      const bpmLabel = document.getElementById("metro-bpm-label");
      const sigSelect = document.getElementById("metro-sig");
      const beatEl = document.getElementById("metro-beat");
      const measureEl = document.getElementById("metro-measure");
      const beatsPerEl = document.getElementById("metro-beats-per-measure");
      const dotsEl = document.getElementById("metro-dots");
      let ctx = null;
      let timer = null;
      let beat = 0;
      let measure = 0;

      bpmInput.value = cfg.bpm;
      bpmLabel.textContent = cfg.bpm;
      sigSelect.value = cfg.signature;

      function beatsPerMeasure() {{
        return parseInt(sigSelect.value.split("/")[0], 10);
      }}

      function drawDots(activeBeat) {{
        const beats = beatsPerMeasure();
        beatsPerEl.textContent = beats;
        dotsEl.innerHTML = "";
        for (let i = 1; i <= beats; i++) {{
          const dot = document.createElement("div");
          dot.textContent = i;
          dot.style.width = "34px";
          dot.style.height = "34px";
          dot.style.borderRadius = "50%";
          dot.style.display = "flex";
          dot.style.alignItems = "center";
          dot.style.justifyContent = "center";
          dot.style.border = "1px solid #aaa";
          dot.style.background = i === activeBeat ? (i === 1 ? "#ffcc66" : "#b7e4ff") : "#f5f5f5";
          dot.style.fontWeight = i === activeBeat ? "700" : "400";
          dotsEl.appendChild(dot);
        }}
      }}

      function click(accent) {{
        if (!ctx) return;
        const now = ctx.currentTime;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.frequency.value = accent ? 1180 : 760;
        gain.gain.setValueAtTime(accent ? 0.42 : 0.20, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.07);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.08);
      }}

      function tick() {{
        const beats = beatsPerMeasure();
        beat += 1;
        if (beat > beats) {{
          beat = 1;
          measure += 1;
          if (cfg.sectionBars > 0 && measure > cfg.sectionBars) {{
            measure = 1;
          }}
        }}
        click(beat === 1);
        beatEl.textContent = beat;
        measureEl.textContent = measure;
        drawDots(beat);
      }}

      function start() {{
        stop();
        ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
        beat = 0;
        measure = 1;
        tick();
        const intervalMs = 60000 / parseInt(bpmInput.value, 10);
        timer = setInterval(tick, intervalMs);
      }}

      function stop() {{
        if (timer) clearInterval(timer);
        timer = null;
        beat = 0;
        measure = 0;
        beatEl.textContent = "-";
        measureEl.textContent = "0";
        drawDots(0);
      }}

      bpmInput.addEventListener("input", () => {{
        bpmLabel.textContent = bpmInput.value;
        if (timer) start();
      }});
      sigSelect.addEventListener("change", () => {{
        if (timer) start();
        else drawDots(0);
      }});
      document.getElementById("metro-start").addEventListener("click", start);
      document.getElementById("metro-stop").addEventListener("click", stop);
      drawDots(0);
    }})();
    </script>
    """
    components.html(widget_html, height=230)

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


def _chart_grid_html(chords, current_bar=None, section_name=""):
    if not chords:
        return "<div class='empty-chart'>No chords entered for this section.</div>"
    cells = []
    safe_section_attr = html.escape(str(section_name), quote=True)
    for idx, chord in enumerate(chords):
        previous = chords[idx - 1] if idx else None
        display = "%" if previous and chord == previous else str(chord)
        current_class = " current-chord" if current_bar == idx + 1 else ""
        repeat_count = 1
        if display != "%":
            for nxt in chords[idx + 1:]:
                if nxt != chord:
                    break
                repeat_count += 1
        duration = f"<span class='duration'>{repeat_count} bars</span>" if repeat_count > 1 else ""
        cells.append(
            f"<div class='chord-cell live-chart-cell{current_class}' data-section='{safe_section_attr}' data-bar='{idx + 1}'>"
            f"<div class='bar-num'>Bar {idx + 1}</div>"
            f"<div class='chord-symbol'>{html.escape(display)}</div>"
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
        )
    merged_lyric_cues = merge_lyric_cues_for_song(song_data, lyric_cues)
    sheet_class = lead_sheet_body_class(song_data)
    total_bars = sum(len(chords) for chords in sections.values())
    show_full = not current_section or str(current_section).strip().lower() in (
        "full song",
        "full form",
        "",
    )
    now_playing = "Full song" if show_full else str(current_section)
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
        section_cards.append(
            f"""
<section class="section-card {role}{' current' if is_current else ''}">
  <div class="section-head">
    <div>
      <div class="section-title">{html.escape(section_name)} - {len(chords)} bars</div>
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


TRANSPOSING_INSTRUMENTS = {
    "Alto Sax (Eb)": 9,
    "Tenor Sax (Bb)": 2,
    "Soprano Sax (Bb)": 2,
    "Bari Sax (Eb)": 9,
    "Bb Trumpet": 2,
    "Bb Clarinet": 2,
}


def transposing_instrument_options(instrument):
    if instrument == "Saxophone":
        return ["Alto Sax (Eb)", "Tenor Sax (Bb)", "Soprano Sax (Bb)", "Bari Sax (Eb)"]
    if instrument == "Trumpet":
        return ["Bb Trumpet"]
    if instrument == "Clarinet":
        return ["Bb Clarinet"]
    return []


def transposed_key_for_instrument(concert_key, instrument_label):
    steps = TRANSPOSING_INSTRUMENTS.get(instrument_label, 0)
    return transpose_chord(concert_key, steps)


def render_transposition_helper(concert_key, instrument, key_prefix, wrap_expander=True):
    if instrument == "Flute":
        ctx = st.expander("Instrument Key / Transposition Helper", expanded=True) if wrap_expander else _null_expander()
        with ctx:
            st.write(f"Concert key: **{concert_key}**")
            st.write("Flute is a concert-pitch instrument, so no transposition is needed.")
        return concert_key, False, "Flute (concert pitch)"

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


def capo_fret_for_shape(sounding_key, shape_key):
    return semitone_distance(shape_key, sounding_key)


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
    st.write(f"**Original key:** {original_key}")
    st.write(f"**Display / practice key:** {display_key}")
    st.write(f"Semitone shift: **{'+' if steps else ''}{steps}**")
    pairs = [
        f"{a} → {b}"
        for a, b in zip(orig_sample, disp_sample)
    ]
    st.caption("Example chord shift: " + " | ".join(pairs))


def render_guitar_capo_helper(base_sections, sounding_key, key_prefix, wrap_expander=True):
    ctx = (
        st.expander("Capo / Guitar Shape Helper", expanded=True)
        if wrap_expander
        else _null_expander()
    )
    with ctx:
        if not wrap_expander:
            st.markdown("#### Guitar capo helper")
        col_a, col_b, col_c = st.columns([1.1, 1.1, 1])
        _capo_keys = display_key_options(sounding_key)
        with col_a:
            actual_key = st.selectbox(
                "Actual sounding key",
                _capo_keys,
                index=_capo_keys.index(sounding_key) if sounding_key in _capo_keys else 0,
                key=f"{key_prefix}::capo_actual_key",
            )
            shape_key = st.selectbox(
                "Desired guitar shape key",
                COMMON_KEYS,
                index=COMMON_KEYS.index("G") if "G" in COMMON_KEYS else 0,
                key=f"{key_prefix}::capo_shape_key",
            )
        capo = capo_fret_for_shape(actual_key, shape_key)
        actual_sections = transpose_sections_dict(base_sections, sounding_key, actual_key)
        shape_sections = transpose_sections_dict(actual_sections, actual_key, shape_key)
        shape_chords = chord_blocks_for_selected_sections(shape_sections)[:8]
        with col_b:
            st.write(f"Sounding key: **{actual_key}**")
            st.write(f"Play using: **{shape_key} shapes**")
            st.write(f"Will sound in: **{actual_key}**")
        with col_c:
            st.metric("Capo position", f"{capo} fret" if capo == 1 else f"{capo} frets")
        st.caption(
            "Use the capo position so your chosen chord shapes sound in the actual song key."
        )
        if shape_chords:
            st.write("Playable chord shapes: `" + " | ".join(shape_chords) + "`")


def build_chord_event_timeline(events, bpm, loops, beats_per_bar=4):
    timeline = []
    if not events:
        return timeline
    bar_duration = (60 / max(1, bpm)) * beats_per_bar
    looped_events = events * max(1, int(loops))
    for idx, event in enumerate(looped_events):
        start_time = idx * bar_duration
        end_time = start_time + bar_duration
        timeline.append({
            "event_index": idx,
            "absolute_bar": idx + 1,
            "total_bars": len(looped_events),
            "section": event.get("section", ""),
            "bar_in_section": int(event.get("bar_in_section", 0)) + 1,
            "section_bars": int(event.get("section_bars", 1)),
            "chord": event.get("chord", ""),
            "start_time": start_time,
            "duration": bar_duration,
            "end_time": end_time,
        })
    return timeline


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


def live_follow_along_component_html(wav_bytes, timeline, chart_html, *, autoplay: bool = True):
    audio_b64 = base64.b64encode(wav_bytes).decode("ascii")
    timeline_json = json.dumps(timeline)
    autoplay_attr = "autoplay" if autoplay else ""
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

  <div id="live-chart-root">
    {chart_html}
  </div>

  <script>
    const timeline = {timeline_json};
    const audio = document.getElementById("live-audio");
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
      sectionEl.textContent = event.section || "Section";
      chordEl.textContent = event.chord || "-";
      barEl.textContent = `${{event.bar_in_section}} of ${{event.section_bars}}`;
      nextEl.textContent = next.chord || "-";
      detailEl.textContent = `Audio ${{audioTime.toFixed(2)}}s | Event ${{event.event_index + 1}} of ${{timeline.length}} | ${{event.start_time.toFixed(1)}}s-${{event.end_time.toFixed(1)}}s`;
      const nowPlayingBanner = document.querySelector(".now-playing");
      if (nowPlayingBanner) {{
        nowPlayingBanner.textContent = `Now Playing: ${{event.section}} | Bar ${{event.bar_in_section}} | ${{event.chord}}`;
      }}

      clearHighlight();
      const cells = Array.from(document.querySelectorAll(".live-chart-cell"));
      const currentCell = cells.find((cell) =>
        cell.dataset.section === event.section && Number(cell.dataset.bar) === Number(event.bar_in_section)
      );
      if (currentCell) {{
        currentCell.classList.add("current-chord");
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


FOCUS_OPTIONS_BY_INSTRUMENT = {
    "Guitar": [
        "Strumming",
        "Rhythm Guitar",
        "Chord Transitions",
        "Barre Chords",
        "Fingerstyle",
        "Triads",
        "Double Stops",
        "Lead Guitar",
        "Soloing",
        "Dynamics",
        "Ear Training",
    ],
    "Piano": [
        "Voicings",
        "Left-Hand Patterns",
        "Comping",
        "Voice Leading",
        "Inversions",
        "Reharmonization",
        "Dynamics",
        "Ear Training",
    ],
    "Bass": [
        "Groove",
        "Pocket",
        "Root Motion",
        "Walking Bass",
        "Syncopation",
        "Dynamics",
        "Ear Training",
    ],
    "Saxophone": [
        "Tone",
        "Scales",
        "Articulation",
        "Bebop Phrasing",
        "Breath Support",
        "Guide Tones",
        "Dynamics",
        "Ear Training",
    ],
    "Flute": [
        "Tone",
        "Scales",
        "Articulation",
        "Breath Support",
        "Guide Tones",
        "Phrasing",
        "Dynamics",
        "Ear Training",
    ],
    "Trumpet": [
        "Tone",
        "Endurance",
        "Articulation",
        "Range",
        "Jazz Phrasing",
        "Guide Tones",
        "Dynamics",
        "Ear Training",
    ],
    "Clarinet": [
        "Tone",
        "Scales",
        "Articulation",
        "Breath Support",
        "Guide Tones",
        "Dynamics",
        "Ear Training",
    ],
    "Voice": [
        "Breath Control",
        "Phrasing",
        "Pitch Accuracy",
        "Emotional Delivery",
        "Harmony Singing",
        "Vibrato",
        "Dynamics",
        "Ear Training",
    ],
}


def focus_options_for_instrument(instrument):
    return FOCUS_OPTIONS_BY_INSTRUMENT.get(
        instrument,
        ["Melody", "Harmony", "Rhythm", "Dynamics", "Improvisation", "Technique", "Ear Training"],
    )


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


def daily_practice_breakdown_markdown(song, sections, instrument, level, focus, minutes, variation=0):
    section_name, section_chords = _section_for_exercise(sections, variation)
    first_chord, second_chord = _transition_pair(section_chords, variation)
    blocks = _practice_time_blocks(minutes)
    span = _exercise_span(level, len(section_chords))
    chord_path = _chord_run(section_chords, span)
    family = _instrument_family(instrument)
    time_signature = default_time_signature(song, sections)
    groove_style = infer_groove_style(globals().get("song_data", {}), "Auto")
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


def song_practice_plan(song, sections, instrument, level, focus, variation, section_lyrics=None, minutes=30):
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
    groove_style = infer_groove_style(globals().get("song_data", {}), "Auto")
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
    text = " ".join([song] + list(sections.keys())).lower()
    if "3/4" in text or "piano man" in text:
        return "3/4"
    if "6/8" in text:
        return "6/8"
    if "perfect" in text:
        return "6/8"
    return "4/4"


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


def practice_text(level, instrument=None, sections=None, focus=None):
    sections = sections or {}
    section_name, section_chords = _section_for_exercise(sections, 0)
    first_chord, second_chord = _transition_pair(section_chords, 0)
    chord_path = _chord_run(section_chords, _exercise_span(level, len(section_chords)))
    focus_area = _focus_area(focus)
    time_signature = default_time_signature(globals().get("song", ""), sections)
    groove_style = infer_groove_style(globals().get("song_data", {}), "Auto")
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

    if DATA_FILE.exists():

        try:
            return json.loads(
                DATA_FILE.read_text(
                    encoding="utf-8"
                )
            )

        except Exception:
            return []

    return []

def save_logs(logs):

    DATA_FILE.write_text(
        json.dumps(logs, indent=2),
        encoding="utf-8"
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


def beats_per_bar_from_signature(time_signature):
    try:
        return max(1, int(str(time_signature).split("/")[0]))
    except Exception:
        return 4


def ensure_multitrack_track_controls(track_names):
    controls = st.session_state.setdefault("mt_track_controls", {})
    for name in track_names:
        controls.setdefault(
            name,
            {"volume": 1.0, "mute": False, "solo": False, "delay": 0.0},
        )
    return controls


def multitrack_studio_track_payloads(track_items, controls):
    payloads = []
    for item in track_items:
        name = item["name"]
        track_id = "".join(ch if ch.isalnum() else "_" for ch in name.lower()).strip("_") or "track"
        ctrl = controls.get(name, {})
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
):
    events = chord_events_for_selected_sections(sections, selected_section_names)
    if not events:
        return None, events
    backing_y = backing_bytes_to_float(
        events,
        bpm=bpm,
        style=style,
        level=level,
    )
    if loops > 1:
        backing_y = np.tile(backing_y, int(loops))
    return wav_bytes_from_float(backing_y), events


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
    bar_duration = (60 / max(1, bpm)) * beats_per_bar
    loop_checked = "checked" if loop_backing else ""
    metro_checked = "checked" if metronome_during_playback else ""
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
<div class="mt-studio">
  <style>
    .mt-studio {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif; color: #0f172a; }}
    .mt-toolbar {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-bottom:12px; }}
    .mt-toolbar button {{ padding:8px 14px; border-radius:10px; border:1px solid #cbd5e1; background:#fff; cursor:pointer; font-weight:700; }}
    .mt-toolbar button.primary {{ background:#16a34a; color:#fff; border-color:#15803d; }}
    .mt-status {{ border:1px solid #cbd5e1; border-radius:12px; padding:10px 12px; background:#f8fafc; margin-bottom:12px; }}
    .mt-timeline {{ height:10px; background:#e2e8f0; border-radius:999px; overflow:hidden; margin:10px 0 14px 0; }}
    .mt-cursor {{ height:100%; width:0%; background:linear-gradient(90deg,#22c55e,#16a34a); transition: width 0.05s linear; }}
    .mt-track-list {{ display:grid; gap:8px; }}
    .mt-track-row {{ border:1px solid #e2e8f0; border-radius:12px; padding:10px; background:#fff; display:grid; grid-template-columns: 1.2fr 1fr 1fr 1fr; gap:8px; align-items:center; }}
    .mt-track-row.muted {{ opacity:0.45; }}
    .mt-track-row.soloed {{ outline:2px solid #f59e0b; }}
    .mt-help {{ color:#475569; font-size:0.86rem; margin-top:8px; }}
    .mt-beat {{ font-variant-numeric: tabular-nums; }}
  </style>

  <audio id="mt-backing" preload="auto" {backing_attr}></audio>

  <div class="mt-status">
    <strong>Multitrack Studio</strong> — {html.escape(scope_label)} @ {bpm} BPM ({html.escape(time_signature)})
    <div class="mt-help" id="mt-playback-label">Ready. Backing is monitor-only and is not printed into your recorded tracks.</div>
  </div>

  <div class="mt-toolbar">
    <button class="primary" id="mt-play">Play with count-in</button>
    <button id="mt-stop">Stop</button>
    <label><input type="checkbox" id="mt-loop" {loop_checked}> Loop backing</label>
    <label><input type="checkbox" id="mt-metronome" {metro_checked}> Metronome during playback</label>
    <label>Backing monitor <input type="range" id="mt-backing-vol" min="0" max="150" value="{int(backing_monitor_volume * 100)}"></label>
  </div>

  <div>Transport: <span class="mt-beat" id="mt-time">0.0s</span> | Bar <span class="mt-beat" id="mt-bar">1</span> | Beat <span class="mt-beat" id="mt-beat">1</span></div>
  <div class="mt-timeline"><div class="mt-cursor" id="mt-cursor"></div></div>

  <div class="mt-track-list" id="mt-track-list"></div>
  <div class="mt-help">Use headphones when possible. Record each layer below with Streamlit's recorder while this transport plays. For AI coaching, use the Upload &amp; Recording Analysis tab.</div>

  <script>
    const cfg = {config};
    const tracks = {tracks_json};
    const backingEl = document.getElementById("mt-backing");
    const listEl = document.getElementById("mt-track-list");
    const playBtn = document.getElementById("mt-play");
    const stopBtn = document.getElementById("mt-stop");
    const loopCb = document.getElementById("mt-loop");
    const metroCb = document.getElementById("mt-metronome");
    const backingVol = document.getElementById("mt-backing-vol");
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
          <label>Vol <input type="range" min="0" max="200" value="${{Math.round((track.volume || 1) * 100)}}" data-vol></label>
          <label><input type="checkbox" data-mute> Mute</label>
          <label><input type="checkbox" data-solo> Solo</label>
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
          mute: row.querySelector("[data-mute]").checked,
          solo: row.querySelector("[data-solo]").checked,
          volume: Number(row.querySelector("[data-vol]").value) / 100,
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
        src.loop = loopCb.checked;
        backingGain = audioCtx.createGain();
        backingGain.gain.value = Number(backingVol.value) / 100;
        src.connect(backingGain);
        backingGain.connect(masterGain);
        src.start(musicStart);
        const backingLen = backingBuf.duration * (loopCb.checked ? 4 : 1);
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

      if (metroCb.checked) {{
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
    backingVol.addEventListener("input", () => {{
      if (backingGain) backingGain.gain.value = Number(backingVol.value) / 100;
    }});
  </script>
</div>
"""

def _recording_analysis_context(recording_type: str = "practice") -> dict:
    from recording_analysis import analysis_context_from_app

    return analysis_context_from_app(
        song=song,
        song_data=song_data,
        display_key=display_key,
        sections=sections,
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
        display_key=display_key,
        sections=sections,
        instrument=instrument,
        level=level,
        focus=focus,
    )


def chord_quality(ch):
    return lab_chord_quality(ch)


def deep_harmonic_analysis_text(ctx):
    return lab_deep_harmonic(ctx, all_chords_from_sections, lab_chord_quality)


def musical_development_tracker_text():
    return lab_musical_dev(load_logs)


def _developer_mode_enabled() -> bool:
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


def _render_catalog_health_debug() -> None:
    """Sidebar / debug counts so a shrunken catalog is obvious."""
    total = len(ALL_SONG_RECORDS)
    visible = len(_picker_visible_records())
    st.sidebar.caption(f"**Songs loaded:** {total} in catalog · **{visible}** match current filters")
    if CATALOG_LOAD_ERROR:
        st.sidebar.error(f"Last catalog load error: {CATALOG_LOAD_ERROR!r}")
    if total < 20:
        st.sidebar.warning(
            f"Only **{total}** songs loaded — expected 80+. Check song_catalog/ on deploy."
        )
    elif visible < total:
        st.sidebar.info(
            f"Filters hide {total - visible} songs. Enable **Developer Mode** in Catalog debug "
            f"to adjust library scope on **Song Selection**."
        )


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
        apply_pick_key(st, opts[0], SONG_PICKER_CATALOG)
        note_active_source_change(st, invalidate_backing=invalidate_backing_cache)
        st.rerun()


def _on_global_song_change() -> None:
    set_catalog_source(st.session_state)
    apply_pick_key(st, st.session_state["global_quick_song"], SONG_PICKER_CATALOG)
    note_active_source_change(st, invalidate_backing=invalidate_backing_cache)


PENDING_BACKING_SINGLE_SECTION = "_pending_backing_single_section"
PENDING_BACKING_SCOPE = "_pending_backing_scope"
PENDING_BACKING_LOOPS = "_pending_backing_loops"
BACKING_AUTOPLAY = "_backing_autoplay"


def _prepare_backing_from_practice(focus: str | None) -> None:
    """Carry Practice section focus into Backing Track (pending keys — safe for widgets)."""
    if practice_is_full_song(focus):
        st.session_state[PENDING_BACKING_SCOPE] = "Full song"
        st.session_state.pop(PENDING_BACKING_SINGLE_SECTION, None)
    else:
        st.session_state[PENDING_BACKING_SCOPE] = "Single section"
        st.session_state[PENDING_BACKING_SINGLE_SECTION] = focus
        st.session_state[PENDING_BACKING_LOOPS] = 4
    st.session_state[BACKING_AUTOPLAY] = True


def _apply_pending_backing_scope(session_state, section_names: list[str]) -> bool:
    """Apply Practice → Backing handoff before scope/section widgets are built."""
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
    return opened_section


def _stop_backing_playback() -> None:
    """Stop follow-along playback without clearing the generated WAV."""
    st.session_state[BACKING_AUTOPLAY] = False
    st.session_state.pop("playback_start_time", None)
    for key in list(st.session_state.keys()):
        if str(key).endswith("::follow_start_time"):
            st.session_state.pop(key, None)
        if str(key).endswith("::follow_manual_index"):
            st.session_state[key] = 0


def _picker_navigate(page: str, *, open_chord_coach: bool = False) -> None:
    """Open a studio page for the already-selected catalog song (no re-selection)."""
    st.session_state["studio_page"] = page
    if open_chord_coach:
        st.session_state["picker_open_chord_coach"] = True
    st.rerun()


def _render_active_song_card(rec: dict) -> None:
    """Rich active-song summary with navigation shortcuts."""
    level = st.session_state.get("level", "Intermediate")
    try:
        details = active_song_card_details(rec, level=level)
    except Exception:
        details = {**song_card_meta(rec), "time_signature": "4/4", "key_display": rec.get("key", "C"), "style_label": rec.get("genre", ""), "sections": list((rec.get("sections") or {}).keys()), "section_summary": "", "practice_focus": "", "chord_concepts": [], "practice_goals": [], "why_practice": "", "visual_emoji": "🎵", "visual_gradient": "linear-gradient(145deg,#334155,#64748b)", "visual_genre": rec.get("genre", "Song"), "bpm": 100}
    trusted_cls = " trusted" if details.get("trusted") else ""
    concepts = ", ".join(html.escape(c) for c in details.get("chord_concepts") or [])
    goals_html = "".join(
        f"<li>{html.escape(g)}</li>" for g in (details.get("practice_goals") or [])
    )
    card_html = (
        f'<div class="ui-active-song-card{trusted_cls}">'
        f'<div class="ui-active-song-art" style="background:{html.escape(details["visual_gradient"])};">'
        f'{html.escape(details["visual_emoji"])}<small>{html.escape(details["visual_genre"])}</small></div>'
        f'<div class="ui-active-song-body">'
        f'<p class="ui-active-song-kicker">Active Song</p>'
        f'<p class="ui-active-song-title">{html.escape(details["title"])}</p>'
        f'<p class="ui-active-song-artist">{html.escape(details["artist"])}</p>'
        f'<dl class="ui-active-song-facts">'
        f'<dt>Key</dt><dd>{html.escape(details.get("key_display", details.get("key", "")))}</dd>'
        f'<dt>Style</dt><dd>{html.escape(details.get("style_label", details.get("genre", "")))}</dd>'
        f'<dt>Level</dt><dd>{html.escape(details.get("difficulty", ""))}</dd>'
        f'<dt>BPM</dt><dd>{int(details.get("bpm") or 100)}</dd>'
        f'<dt>Time</dt><dd>{html.escape(details.get("time_signature", "4/4"))}</dd>'
        f'<dt>Sections</dt><dd>{html.escape(details.get("section_summary") or "—")}</dd>'
        f'<dt>Instruments</dt><dd>{html.escape(details.get("instruments", ""))}</dd>'
        f'<dt>Practice focus</dt><dd>{html.escape(details.get("practice_focus", ""))}</dd>'
        f"</dl>"
        + (f'<p class="ui-active-song-blurb"><strong>Harmony:</strong> {concepts}</p>' if concepts else "")
        + f'<p class="ui-active-song-blurb">{html.escape(str(details.get("why_practice", "")))}</p>'
        + (f'<ul class="ui-active-song-goals">{goals_html}</ul>' if goals_html else "")
        + "</div></div>"
    )
    st.markdown(card_html, unsafe_allow_html=True)
    st.markdown('<div class="ui-song-card-actions">', unsafe_allow_html=True)
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        if st.button("Practice", key="picker_card_practice", use_container_width=True):
            _picker_navigate("practice")
    with b2:
        if st.button("Backing Track", key="picker_card_backing", use_container_width=True):
            _picker_navigate("backing")
    with b3:
        if st.button("Creative", key="picker_card_creative", use_container_width=True):
            _picker_navigate("creative")
    with b4:
        if st.button("Chord Coach", key="picker_card_chord_coach", use_container_width=True):
            _picker_navigate("practice", open_chord_coach=True)
    st.markdown("</div>", unsafe_allow_html=True)


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

    if show_source_toggle:
        _picker_source_options = [
            "Song Selection (catalog song)",
            "Use Custom Progression / Create Your Own Song",
        ]
        _picker_source_index = 1 if is_custom_progression(st.session_state) else 0
        picker_source = st.radio(
            "Music source",
            _picker_source_options,
            index=_picker_source_index,
            horizontal=True,
            key="song_picker_active_source",
        )
        if picker_source.startswith("Use Custom"):
            if not is_custom_progression(st.session_state):
                set_custom_source(st.session_state)
                note_active_source_change(st, invalidate_backing=invalidate_backing_cache)
                st.rerun()
            _cpl_pick = ensure_original_structure(st.session_state.get(CPL_ACTIVE_KEY) or {})
            st.info(
                f"**Custom Progression** — {_cpl_pick.get('name', 'Untitled')}. "
                "Edit in **Custom Progression** · transpose with **Practice / Display Key** in the sidebar."
            )
            if wrap_section:
                close_control_section()
            return
        if is_custom_progression(st.session_state):
            set_catalog_source(st.session_state)
            note_active_source_change(st, invalidate_backing=invalidate_backing_cache)
            st.rerun()

    visible_song_records = _picker_visible_records()
    _genre_filter_options = [_ALL_GENRE_FILTER] + sorted(
        {r.get("genre") for r in visible_song_records if r.get("genre")}
    )
    st.session_state.setdefault("workspace_genre_filter", _ALL_GENRE_FILTER)
    _wgf = st.session_state.get("workspace_genre_filter", _ALL_GENRE_FILTER)
    if _wgf not in _genre_filter_options:
        st.session_state["workspace_genre_filter"] = _ALL_GENRE_FILTER

    genre_col, search_col = st.columns([1, 2])
    with genre_col:
        workspace_genre = st.selectbox(
            "Filter songs by genre",
            _genre_filter_options,
            key="workspace_genre_filter",
        )
    with search_col:
        st.text_input(
            "Search / filter songs",
            placeholder="Title, artist, genre…",
            key="song_search_text",
        )
    filter_genre = None if workspace_genre == _ALL_GENRE_FILTER else workspace_genre

    search_text = st.session_state.get("song_search_text", "")
    filtered = search_records(
        visible_song_records,
        search_text,
        genre=filter_genre,
        limit=max(500, len(ALL_SONG_RECORDS)),
    )
    if not filtered:
        filtered = list(visible_song_records)

    master_sel = st.session_state.get("selected_song") or {}
    master_pk = master_sel.get("pick_key")
    master_rec = record_for_pick_key(visible_song_records, master_pk) if master_pk else None
    if master_rec:
        mk = format_pick_key(master_rec["genre"], f"{master_rec['title']} — {master_rec['artist']}")
        if mk not in {format_pick_key(r["genre"], f"{r['title']} — {r['artist']}") for r in filtered}:
            filtered = [master_rec] + filtered

    pick_options = [format_pick_key(r["genre"], f"{r['title']} — {r['artist']}") for r in filtered]

    if not pick_options:
        st.warning("No songs match your search — try another genre or clear the search box.")
        if wrap_section:
            close_control_section()
        return

    default_pk = master_pk if master_pk in pick_options else pick_options[0]
    if st.session_state.get(ACTIVE_CATALOG_PICK_KEY) not in pick_options:
        set_catalog_source(st.session_state)
        apply_pick_key(st, default_pk, SONG_PICKER_CATALOG)
        note_active_source_change(st, invalidate_backing=invalidate_backing_cache)

    def _on_song_dropdown_change():
        set_catalog_source(st.session_state)
        apply_pick_key(
            st,
            st.session_state["matching_song_dropdown"],
            SONG_PICKER_CATALOG,
        )
        note_active_source_change(st, invalidate_backing=invalidate_backing_cache)
        try:
            st.toast("Song updated — chart and backing track follow this selection.", icon="🎵")
        except Exception:
            pass

    active_pick_key = sync_matching_song_dropdown_before_widget(
        st,
        pick_options,
        default_pk,
    )
    if show_song_cards:
        st.markdown("### Choose active song")
    st.selectbox(
        "Select song",
        pick_options,
        format_func=lambda opt: f"{parse_pick_key(opt)[1]}  [{parse_pick_key(opt)[0]}]",
        key="matching_song_dropdown",
        on_change=_on_song_dropdown_change,
        help="Primary selector — updates Practice, Backing Track, Creative Lab, and all coach tools.",
    )

    if show_song_cards:
        st.caption(f"**{len(filtered)}** songs available in this list.")
        st.markdown("#### Active song")
        active_rec = record_for_pick_key(visible_song_records, active_pick_key)
        if active_rec:
            _render_active_song_card(active_rec)
        else:
            st.info("Select a song from the menu above.")
    elif not _developer_mode_enabled():
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

    if wrap_section:
        close_control_section()


def _render_page_quick_nav(current_page: str) -> str:
    """Top-of-page navigation bar."""
    return render_page_quick_nav(
        st.session_state,
        current_page=current_page,
        rerun_fn=st.rerun,
    )


def _sync_focus_options_before_widget(instrument: str) -> list[str]:
    opts = focus_options_for_instrument(instrument)
    if st.session_state.get("focus") not in opts:
        st.session_state["focus"] = opts[0]
    return opts


def _render_practice_setup_panel(
    *,
    instrument_options: list[str],
    default_groove: str,
) -> None:
    """Practice-only setup controls (instrument, level, focus, session length, groove)."""
    from practice_ui_labels import (
        GROOVE_ICONS,
        INSTRUMENT_ICONS,
        LEVEL_ICONS,
        icon_for_focus,
        setup_pill_html,
    )

    st.markdown(
        '<div class="practice-setup-card">'
        '<p class="ui-page-nav-label">Practice setup</p></div>',
        unsafe_allow_html=True,
    )
    levels = ["Beginner", "Intermediate", "Advanced"]
    grooves = [
        "Auto",
        "Pop groove",
        "Rock groove",
        "Jazz swing",
        "Bossa nova",
        "Funk groove",
        "Ballad",
    ]

    p1, p2, p3, p4 = st.columns(4)
    with p1:
        st.selectbox("Instrument", instrument_options, key="instrument")
        st.markdown(
            setup_pill_html(st.session_state["instrument"], INSTRUMENT_ICONS.get(st.session_state["instrument"], "🎵")),
            unsafe_allow_html=True,
        )
    with p2:
        st.selectbox("Level", levels, key="level")
        st.markdown(
            setup_pill_html(st.session_state["level"], LEVEL_ICONS.get(st.session_state["level"], "🌱")),
            unsafe_allow_html=True,
        )
    with p3:
        focus_options = _sync_focus_options_before_widget(st.session_state.get("instrument", "Piano"))
        st.selectbox("Practice focus", focus_options, key="focus")
        st.markdown(
            setup_pill_html(st.session_state["focus"], icon_for_focus(st.session_state["focus"])),
            unsafe_allow_html=True,
        )
    with p4:
        st.session_state.setdefault("practice_minutes", 30)
        st.slider(
            "Practice length (minutes)",
            10,
            120,
            int(st.session_state.get("practice_minutes", 30)),
            5,
            key="practice_minutes",
        )

    st.session_state.setdefault("backing_groove_style", default_groove)
    g1, g2 = st.columns([1, 1])
    with g1:
        st.selectbox(
            "Rhythm / groove feel",
            grooves,
            key="practice_groove_style",
        )
        st.markdown(
            setup_pill_html(
                st.session_state["practice_groove_style"],
                GROOVE_ICONS.get(st.session_state["practice_groove_style"], "✨"),
            ),
            unsafe_allow_html=True,
        )
    with g2:
        st.caption("Coach and charts follow these choices. Tempo and backing are on **Backing Track**.")
    render_cross_page_links(
        st.session_state,
        current_page="practice",
        rerun_fn=st.rerun,
        key_prefix="practice_x",
    )


def _render_backing_tempo_panel(
    *,
    song_title: str,
    song_id: str,
    default_bpm: int,
    default_groove: str,
    backing_ready: bool,
) -> int:
    """Backing Track page — BPM and groove (widget created once per run)."""
    sync_backing_bpm_before_widget(st, song_id, default_bpm)
    sync_backing_groove_before_widget(st, song_id, default_groove)
    st.markdown(
        '<p class="ui-page-nav-label">Backing / tempo</p>',
        unsafe_allow_html=True,
    )
    b1, b2, b3 = st.columns(3)
    with b1:
        bpm = st.slider(
            "BPM (tempo)",
            50,
            180,
            int(st.session_state.get("backing_track_bpm", default_bpm)),
            5,
            key="backing_track_bpm",
        )
    with b2:
        st.selectbox(
            "Groove / style",
            [
                "Auto",
                "Pop groove",
                "Rock groove",
                "Jazz swing",
                "Bossa nova",
                "Funk groove",
                "Ballad",
            ],
            key="backing_groove_style",
        )
    with b3:
        if backing_ready:
            st.markdown(
                '<span class="ui-backing-pill ready">● Backing audio ready</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<span class="ui-backing-pill">○ Generate backing below</span>',
                unsafe_allow_html=True,
            )
    render_cross_page_links(
        st.session_state,
        current_page="backing",
        rerun_fn=st.rerun,
        key_prefix="backing_x",
    )
    return int(bpm)


# -------------------------------------------------
# APP UI
# -------------------------------------------------

inject_app_theme()

render_studio_brand_header()


def _ui_source_label() -> str:
    if is_custom_progression(st.session_state):
        return "Custom progression"
    return "Catalog song"


# SIDEBAR

_studio_page = ensure_studio_page(st.session_state)

sidebar_section("Active source", icon="🎼", tone="source")
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
if is_custom_progression(st.session_state):
    st.sidebar.caption("Edit chords in **Custom Progression Lab**.")
else:
    st.sidebar.caption(f"**{_catalog_song}** · {_catalog_genre}")
    st.sidebar.caption(chart_source_caption(_catalog_song_data))

st.session_state.setdefault("instrument", "Piano")
st.session_state.setdefault("level", "Intermediate")

original_key, _song_identity = display_key_context(
    st.session_state,
    catalog_song_data=_catalog_song_data,
    cpl_active_key=CPL_ACTIVE_KEY,
)
_display_key_options = sync_display_key_before_widget(
    st,
    original_key,
    _song_identity,
)

sidebar_section("Practice key", icon="🎹", tone="key")
st.sidebar.markdown(
    '<p class="ui-key-global-hint">Practice / Display Key — concert pitch for the song (global transpose).</p>',
    unsafe_allow_html=True,
)
st.sidebar.caption(f"Song original key: **{original_key}**")
st.sidebar.selectbox(
    "Practice / Display Key (concert)",
    _display_key_options,
    key="display_key",
    help="Transposes charts, backing audio, and coach content together.",
    on_change=lambda: mark_display_key_changed(st),
)

_instrument_options = [
    "Piano", "Guitar", "Bass", "Saxophone", "Flute",
    "Trumpet", "Clarinet", "Voice", "Other",
]
_focus_options = focus_options_for_instrument(st.session_state.get("instrument", "Piano"))

sidebar_section("Library", icon="📚", tone="library")
_render_catalog_health_debug()
with st.sidebar.expander("Catalog debug", expanded=False):
    st.checkbox(
        "Developer Mode",
        value=bool(st.session_state.get("developer_mode", False)),
        key="developer_mode",
        help="Shows advanced library filters on Song Selection (hidden for normal users).",
    )
    st.write("Songs loaded:", len(ALL_SONG_RECORDS))
    st.write("Songs visible (filters):", len(_picker_visible_records()))
    st.write("Genres:", len(GENRES))
    if CATALOG_LOAD_ERROR:
        st.write("Load error:", repr(CATALOG_LOAD_ERROR))

sidebar_section("Session", icon="⏱️", tone="session")
st.session_state.setdefault("practice_minutes", 30)
st.sidebar.caption(
    f"**Practice length:** {int(st.session_state.get('practice_minutes', 30))} min "
    "(adjust on the **Practice** page)"
)

note_active_source_change(st, invalidate_backing=invalidate_backing_cache)

_master_pk = (st.session_state.get("selected_song") or {}).get("pick_key")
if _master_pk:
    _mg, _ = parse_pick_key(_master_pk)
    st.session_state.setdefault("global_quick_genre", _mg)
    st.session_state.setdefault("global_quick_song", _master_pk)
else:
    st.session_state.setdefault("global_quick_genre", _catalog_genre)
    _fallback_opts = _global_quick_songs_for_genre(_catalog_genre)
    if _fallback_opts:
        st.session_state.setdefault("global_quick_song", _fallback_opts[0])

_apply_catalog_filter_defaults()

minutes = int(st.session_state.get("practice_minutes", 30))

instrument = st.session_state.get("instrument", "Piano")
level = st.session_state.get("level", "Intermediate")
focus = st.session_state.get("focus", _focus_options[0])
display_key = st.session_state.get("display_key", original_key)
if display_key not in _display_key_options:
    display_key = (
        original_key
        if original_key in _display_key_options
        else _display_key_options[0]
    )
    request_display_key(st, display_key)
key_changed_this_run = note_display_key_change(st, display_key)

render_sidebar_transposing_controls(
    st,
    concert_key=display_key,
    instrument=instrument,
)

_chart_bundle = build_active_chart_bundle(
    st.session_state,
    catalog_genre=_catalog_genre,
    catalog_song=_catalog_song,
    catalog_song_data=_catalog_song_data,
    level=level,
    display_key=display_key,
    cpl_active_key=CPL_ACTIVE_KEY,
    sections_for_level=sections_for_level,
    transpose_sections=transpose_sections,
)
genre = _chart_bundle["genre"]
song = _chart_bundle["song"]
song_data = _chart_bundle["song_data"]
original_key = _chart_bundle["original_key"]
level_source_sections = _chart_bundle["level_source_sections"]
sections = _chart_bundle["sections"]
_cpl_active = _chart_bundle.get("cpl_active")


def _ui_page_badges() -> list[tuple[str, str]]:
    return session_badges(
        source_label=_ui_source_label(),
        song=song,
        original_key=original_key,
        display_key=display_key,
        instrument=instrument,
        level=level,
        focus=focus,
        genre=genre if genre != "Custom" else "",
    )


full_song_chords = chord_blocks_for_backing(sections)
_default_bpm = default_bpm_for_song_data(song_data)
_default_groove = default_groove_for_song(song_data, infer_fn=infer_groove_style)
if is_custom_progression(st.session_state) and _cpl_active:
    _default_bpm = int(_cpl_active.get("bpm", _default_bpm) or _default_bpm)
    _cpl_groove = str(_cpl_active.get("groove_style") or "Auto")
    _default_groove = (
        infer_groove_style(song_data, _cpl_groove)
        if _cpl_groove == "Auto"
        else _cpl_groove
    )
_playback_id = playback_song_id(
    is_custom=is_custom_progression(st.session_state),
    song_title=song,
    song_artist=str(song_data.get("artist", "")),
    custom_name=str(_cpl_active.get("name", "") if _cpl_active else ""),
    custom_revision=str(_cpl_active.get("id", "") if _cpl_active else ""),
)
_synced_bpm, default_groove_style = sync_playback_defaults_for_active_song(
    st,
    song_id=_playback_id,
    default_bpm=_default_bpm,
    default_groove=_default_groove,
)
_default_song_bpm = _synced_bpm

song_lyrics_slug = _song_slug(
    song,
    song_data.get("artist", ""),
)
song_lyrics_key = f"song_lyrics::{song_lyrics_slug}"
section_lyrics_state_key = f"section_lyrics::{song_lyrics_slug}"

sidebar_section("Lyrics & cues", icon="📝", tone="lyrics")
with st.sidebar.expander("Lyric cues for active chart", expanded=(instrument == "Voice")):
    st.caption(
        "Paste only lyrics or cues you provide. The app does not fetch or generate copyrighted lyrics."
    )
    full_song_lyrics = st.text_area(
        "Paste lyrics for this song",
        value=st.session_state.get(song_lyrics_key, ""),
        placeholder=(
            "Paste user-provided lyrics or short cues here.\n"
            "Optional format:\n"
            "Verse: lyric/cue line\n"
            "Chorus: hook cue\n"
            "Bridge: delivery cue"
        ),
        key=song_lyrics_key,
        height=150,
    )

    suggested_section_lyrics = split_lyrics_by_sections(
        full_song_lyrics,
        list(sections.keys()),
    )
    section_lyrics_state = st.session_state.setdefault(section_lyrics_state_key, {})

    if st.button("Auto-assign lyrics to sections", key=f"auto_assign_lyrics::{song_lyrics_slug}"):
        st.session_state[section_lyrics_state_key] = dict(suggested_section_lyrics)
        st.rerun()

    st.caption("Adjust section lyric boxes below if automatic assignment is uncertain.")
    for section_name in sections.keys():
        default_text = section_lyrics_state.get(
            section_name,
            suggested_section_lyrics.get(section_name, ""),
        )
        section_lyrics_state[section_name] = st.text_area(
            f"{section_name} lyrics / cues",
            value=default_text,
            key=f"section_lyrics::{song_lyrics_slug}::{_song_slug(section_name)}",
            height=90,
        )

sidebar_section("Optional AI", icon="🔑", tone="ai")
user_api_key = st.sidebar.text_input(
    "OpenAI API key",
    type="password",
    help="Optional — for AI-powered suggestions only.",
    key="openai_api_key_box",
)
if user_api_key:
    st.sidebar.caption("API key loaded.")
else:
    st.sidebar.caption("Local features work without a key.")

section_lyrics = st.session_state.get(section_lyrics_state_key, {})
catalog_lyric_cues = song_data.get("lyric_cues") or {}
lyric_cues = {
    **catalog_lyric_cues,
    **lyric_cues_from_section_lyrics(section_lyrics),
}

_practice_bpm = int(st.session_state.get("backing_track_bpm", _default_song_bpm))
_practice_groove = str(
    st.session_state.get("practice_groove_style", default_groove_style)
)

# -------------------------------------------------
# PRACTICE
# -------------------------------------------------

if _studio_page == "practice":

    _render_page_quick_nav("practice")

    compact_page_title(
        "🎯",
        "Song Practice",
        "Set up your session below — change key in the sidebar; pick songs on **Song Selection**.",
    )

    _render_practice_setup_panel(
        instrument_options=_instrument_options,
        default_groove=default_groove_style,
    )

    # Key / level / focus recap
    st.markdown(
        f'<div class="ui-badge-row">'
        f'<span class="ui-badge accent">{html.escape(_ui_source_label())}</span>'
        f'<span class="ui-badge green">Key {html.escape(display_key)}</span>'
        f'<span class="ui-badge">{html.escape(level)}</span>'
        f'<span class="ui-badge">{html.escape(instrument)}</span>'
        f'<span class="ui-badge purple">{html.escape(focus)}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )

    _section_choices = practice_section_options(sections)
    _focus_pick = render_section_jump_bar(
        _section_choices,
        st.session_state,
        state_key="practice_focus_section",
        rerun_fn=st.rerun,
    )
    _send_label = (
        "Send to Backing Track (full song)"
        if practice_is_full_song(_focus_pick)
        else f"Send to Backing Track — loop {practice_active_section_name(_focus_pick, sections) or _focus_pick}"
    )
    if st.button(
        _send_label,
        key="practice_send_to_backing",
        type="primary",
        use_container_width=True,
    ):
        _prepare_backing_from_practice(_focus_pick)
        st.session_state["studio_page"] = "backing"
        st.rerun()
    _is_full_song = practice_is_full_song(_focus_pick)
    _active_section = practice_active_section_name(_focus_pick, sections)
    _view_sections = practice_display_sections(sections, _focus_pick)
    _view_chords = (
        all_chords_from_sections(_view_sections)
        if _is_full_song
        else list((_view_sections.get(_active_section) or []) if _active_section else [])
    )
    _time_sig = default_time_signature(song, sections)
    _section_bar_count = len(_view_chords) if _active_section else 0

    _NOTATION_KEY = "practice_notation_result"
    for _old_key in (
        "custom_practice_sheet",
        "custom_practice_sheet_payload",
        "custom_practice_sheet_sig",
        "practice_copy_sheet",
        "practice_download_sheet",
    ):
        st.session_state.pop(_old_key, None)

    _practice_chart_key, _chart_key_mode = render_practice_transposing_helper(
        st,
        concert_key=display_key,
        instrument=instrument,
    )

    if _is_full_song:
        st.info(
            "Select a **section** above (Verse, Chorus, Bridge, etc.) to isolate chords, "
            "lyrics, metronome loop, deep focus, scales, and rhythm tools for that part only."
        )
    elif _active_section:
        _focus_chords = sections.get(_active_section) or []
        st.markdown(
            f'<div class="ui-badge-row">'
            f'<span class="ui-badge accent">Section focus</span>'
            f'<span class="ui-badge green">{html.escape(_active_section)}</span>'
            f'<span class="ui-badge">{_section_bar_count} bars</span>'
            f"</div>",
            unsafe_allow_html=True,
        )

        with st.expander(f"🔬 Section deep focus — {_active_section}", expanded=True):
            st.markdown(
                section_deep_practice_markdown(
                    section_name=_active_section,
                    section_chords=_focus_chords,
                    instrument=instrument,
                    level=level,
                    focus=focus,
                    display_key=display_key,
                    bpm=_practice_bpm,
                    groove_style=_practice_groove,
                )
            )

        if instrument in ("Guitar", "Piano"):
            with st.expander("🥁 Rhythm guide (this section)", expanded=False):
                st.markdown(
                    rhythm_guide_markdown(
                        instrument,
                        _practice_groove,
                        _time_sig,
                    )
                )

        if _focus_chords:
            with st.expander("🎼 Scales & approaches (this section)", expanded=False):
                for ch in _focus_chords[:12]:
                    st.markdown(
                        scale_suggestions_for_chord(ch, _practice_chart_key, level, instrument)
                    )

        with st.expander(
            f"⏱️ Metronome — {_active_section} only ({_section_bar_count} bars)",
            expanded=False,
        ):
            render_metronome_widget(
                default_bpm=_practice_bpm,
                default_signature=_time_sig,
                section_bars=_section_bar_count,
                section_label=_active_section,
                loop_section=True,
            )

    _chart_current = None if _is_full_song else _active_section
    _chart_html = full_chord_markdown(
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
    )
    _chart_scope = "full song" if _is_full_song else str(_active_section)
    _chart_key_note = ""
    if _chart_key_mode == "written" and is_transposing_instrument(instrument):
        from instrument_transposition import sax_display_name

        _chart_key_note = (
            f" · {sax_display_name(selected_saxophone_type(st.session_state))}"
            f" · written key **{_practice_chart_key}**"
        )
    with st.expander(f"Chord Chart — {_chart_scope}{_chart_key_note}", expanded=False):
        st.markdown(_chart_html, unsafe_allow_html=True)
    if has_lyric_chord_sheet(song_data):
        _ug_sections = lyric_chord_chart_sections(song_data)
        if _ug_sections:
            with st.expander("🎤 Lyric & chord sheet (Ultimate Guitar style)", expanded=False):
                st.caption("Separate from the practice grid — aligned chord pills above lyrics.")
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
                            f"Tempo: {int(_practice_bpm)} BPM",
                            f"Time: {_time_sig}",
                        ],
                        header_note=str((song_data.get("extensions") or {}).get("arrangement_notes") or ""),
                        now_playing=_active_section if not _is_full_song else "Full song",
                        show_full=_is_full_song,
                    ),
                    unsafe_allow_html=True,
                )

    _notation_sig = (
        song,
        _focus_pick,
        instrument,
        focus,
        _practice_chart_key,
        _practice_bpm,
        _practice_groove,
        selected_saxophone_type(st.session_state) if is_transposing_instrument(instrument) else "",
        st.session_state.get(CHART_IN_INSTRUMENT_KEY_KEY, False),
    )
    if st.session_state.get("practice_notation_sig") != _notation_sig:
        st.session_state.pop(_NOTATION_KEY, None)
    st.session_state["practice_notation_sig"] = _notation_sig

    with st.expander("Generated Music Notation / TAB", expanded=False):
        st.caption(
            f"Song **{song}** · section **{_focus_pick}** · "
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
            )
        with _n_col2:
            _diff_opts = ["easy", "medium", "advanced"]
            _diff_default = st.session_state.get("practice_notation_difficulty", "medium")
            _notation_difficulty = st.selectbox(
                "Difficulty",
                options=_diff_opts,
                index=_diff_opts.index(_diff_default) if _diff_default in _diff_opts else 1,
                key="practice_notation_difficulty",
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
            st.session_state[_NOTATION_KEY] = generate_practice_notation(
                song_title=song,
                artist=song_data.get("artist", ""),
                display_key=_practice_chart_key,
                original_key=original_key,
                bpm=_practice_bpm,
                groove_style=_practice_groove,
                instrument=instrument,
                focus=focus,
                section_focus=_focus_pick,
                sections=sections,
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

    exercise_key = f"exercise_variation::{song}::{instrument}::{level}::{focus}"
    if exercise_key not in st.session_state:
        st.session_state[exercise_key] = 0

    with st.expander("🎯 Practice coach & session settings", expanded=False):
        st.caption(
            f"Session length: **{minutes} min** · practice key: **{display_key}** (sidebar)."
        )
        st.markdown(
            '<div class="ui-card soft"><div class="ui-card-title">Personalized coach exercise</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            song_practice_plan(
                song,
                _view_sections,
                instrument,
                level,
                focus,
                st.session_state[exercise_key],
                section_lyrics=section_lyrics,
                minutes=minutes,
            )
        )
        st.markdown("</div>", unsafe_allow_html=True)
        col_ex_a, col_ex_b = st.columns([1, 2])
        with col_ex_a:
            if st.button("🔄 New exercise", use_container_width=True):
                st.session_state[exercise_key] += 1
                st.rerun()
        with col_ex_b:
            st.caption("Rotates section targets and raises demand gradually.")

    _coach_from_picker = st.session_state.pop("picker_open_chord_coach", False)
    _coach_chords = _view_chords or all_chords_from_sections(sections)
    with st.expander("🎸 Musician tools — chord coach", expanded=_coach_from_picker):
        if _active_section:
            st.caption(f"Chords from **{_active_section}** only.")
        render_chord_coach_ui(
            _coach_chords,
            instrument,
            level,
            key_prefix=f"practice::{song}::{instrument}::{level}",
            expanded=True,
            display_key=display_key,
        )

    with st.expander("🎚️ Transpose / capo / instrument key", expanded=False):
        render_general_transpose_helper(
            original_key,
            display_key,
            sections,
            level_source_sections,
            key_prefix=f"practice::{song}",
        )
        if instrument == "Guitar":
            st.divider()
            render_guitar_capo_helper(
                sections,
                display_key,
                key_prefix=f"practice::{song}",
                wrap_expander=False,
            )
        if transposing_instrument_options(instrument) and instrument != "Saxophone":
            st.divider()
            render_transposition_helper(
                display_key,
                instrument,
                key_prefix=f"practice::{song}",
                wrap_expander=False,
            )
        elif instrument == "Flute":
            st.divider()
            render_transposition_helper(
                display_key,
                instrument,
                key_prefix=f"practice::{song}",
                wrap_expander=False,
            )

    if _is_full_song:
        with st.expander("⏱️ Metronome (full song)", expanded=False):
            render_metronome_widget(
                default_bpm=_practice_bpm,
                default_signature=_time_sig,
            )

    with st.expander("📝 Lyric / phrasing guide", expanded=(instrument == "Voice")):
        st.markdown(
            lyric_guide_markdown(
                _view_sections,
                lyric_cues,
                instrument,
                section_lyrics=section_lyrics,
            )
        )

    with st.expander("Full-song ABC sketch (optional)", expanded=False):
        if st.button("Render full-song ABC sketch", key="practice_full_abc_sketch"):
            render_abc(build_abc(song, sections))

    with st.expander("📆 Suggested daily time breakdown", expanded=False):
        st.markdown(
            daily_practice_breakdown_markdown(
                song,
                sections,
                instrument,
                level,
                focus,
                minutes,
                variation=st.session_state[exercise_key],
            )
        )
    st.caption("Deep harmony & improvisation → **Creative Lab** page.")

# -------------------------------------------------
# SONG PICKER
# -------------------------------------------------

elif _studio_page == "picker":

    _render_page_quick_nav("picker")

    compact_page_title(
        "📚",
        "Song Selection",
        "Pick your active song from the menu — the card below opens Practice, Backing Track, Creative, or Chord Coach.",
    )

    _render_catalog_song_picker_block(
        show_source_toggle=True,
        filters_in_expander=False,
        wrap_section=False,
        show_song_cards=True,
    )

    if not is_custom_progression(st.session_state):
        pick_key = st.session_state.get(ACTIVE_CATALOG_PICK_KEY)
        if not pick_key:
            st.stop()
        pick_genre, pick_label = parse_pick_key(pick_key)
        selected_data = SONG_PICKER_CATALOG[pick_genre][pick_label]

        selected_versions = selected_data.get("chart_versions") or {}
        available_levels = ", ".join(selected_versions.keys()) if selected_versions else "Beginner · Intermediate · Advanced"

        st.success(
            f"**Active source: Song** — **{selected_data['title']}** — {selected_data['artist']}."
        )

        st.write(
            f"**Genre/style:** {selected_data.get('genre', 'Unknown')}  \n"
            f"**Original key:** {selected_data.get('key', 'Unknown')}  \n"
            f"**Display / practice key:** {display_key}  \n"
            f"**Chart levels:** {available_levels}"
        )
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
        if display_key != selected_data.get("key"):
            st.caption(
                f"Chords in Practice and Backing Track are shown in **{display_key}** "
                f"(+{semitone_distance(selected_data.get('key', 'C'), display_key)} semitones)."
            )

        st.info(
            "Go to **Backing Track** for the full chart and playback. "
            "Go to **Practice** for exercises. "
            "Go to **Multitrack Recorder** to record."
        )

# -------------------------------------------------
# BACKING TRACK
# -------------------------------------------------

elif _studio_page == "backing":

    _render_page_quick_nav("backing")

    compact_page_title(
        "🎧",
        "Backing Track",
        f"Play & follow — **{song}**" + ("" if is_custom_progression(st.session_state) else f" · {song_data.get('artist', '')}"),
    )

    if key_changed_this_run or st.session_state.get(BACKING_NEEDS_REGEN):
        st.warning("Key changed — regenerate backing track")

    st.caption(
        f"Song defaults: **{_default_song_bpm} BPM** · **{default_groove_style}** "
        f"(from active song metadata — change anytime below)."
    )
    bpm = _render_backing_tempo_panel(
        song_title=song,
        song_id=_playback_id,
        default_bpm=_default_bpm,
        default_groove=default_groove_style,
        backing_ready=bool(st.session_state.get("_last_backing_wav")),
    )

    selected_section_names: list[str] = []
    form_loops = int(st.session_state.get("backing_track_loops", 2))

    _sec_names = [name for name, chs in section_order(sections) if chs]
    _from_practice_section = _apply_pending_backing_scope(st.session_state, _sec_names)
    with st.expander(
        "Playback settings (scope & loops)",
        expanded=_from_practice_section,
    ):
        playback_scope = st.radio(
            "Playback range",
            ["Full song", "Single section", "Multiple selected sections"],
            horizontal=True,
            key="backing_track_scope",
        )
        selected_section_names = []
        if playback_scope == "Single section" and _sec_names:
            selected_section_names = [
                st.selectbox("Section to loop", _sec_names, key="backing_track_single_section")
            ]
        elif playback_scope == "Multiple selected sections" and _sec_names:
            default_sections = [
                name for name in _sec_names
                if any(token in name.lower() for token in ["verse", "chorus"])
            ] or _sec_names[:2]
            selected_section_names = st.multiselect(
                "Sections to play (keeps original song order)",
                _sec_names,
                default=default_sections,
                key="backing_track_multi_sections",
            )
        form_loops = st.slider("Number of repeats", 1, 10, 2, 1, key="backing_track_loops")

    if _from_practice_section:
        _handoff_sec = st.session_state.get("backing_track_single_section", "")
        st.info(
            f"Opened from **Practice** — playback defaults to "
            f"**{_handoff_sec or 'the selected section'}** (full song or other sections still available below)."
        )

    selected_section_names = selected_section_names or []
    groove_style = st.session_state.get("backing_groove_style", "Auto")
    backing_chords = chord_blocks_for_selected_sections(sections, selected_section_names)
    backing_events = chord_events_for_selected_sections(sections, selected_section_names)

    resolved_groove = infer_groove_style(song_data, groove_style)
    section_scope_label = (
        "full form"
        if not selected_section_names
        else " + ".join(selected_section_names)
    )

    if not backing_chords:
        st.warning("Choose at least one section to generate a backing track.")

    st.markdown(
        f'<div class="ui-badge-row">'
        f'<span class="ui-badge accent">{html.escape(section_scope_label)}</span>'
        f'<span class="ui-badge purple">{html.escape(resolved_groove)}</span>'
        f'<span class="ui-badge amber">{bpm} BPM</span>'
        f'<span class="ui-badge">{len(backing_chords)} bars × {form_loops}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )

    chart_level_song_data = {
        **song_data,
        "sections": level_source_sections,
    }
    chart_display_key = display_key
    chart_sections = transpose_sections(
        chart_level_song_data,
        chart_display_key,
    )
    chart_backing_chords = chord_blocks_for_selected_sections(
        chart_sections,
        selected_section_names,
    )
    chart_backing_events = chord_events_for_selected_sections(
        chart_sections,
        selected_section_names,
    )

    coach_section = selected_section_names[0] if selected_section_names else next((name for name, chs in section_order(chart_sections) if chs), "")
    coach_chords = chart_sections.get(coach_section, []) if coach_section else []
    if coach_chords:
        with st.expander(f"💡 Quick coaching — {coach_section}", expanded=False):
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

    _current_backing_signature = (
        song,
        display_key,
        level,
        resolved_groove,
        bpm,
        form_loops,
        tuple(selected_section_names),
        tuple(backing_chords),
    )
    _follow_key_prefix = f"backing::{song}::{tuple(selected_section_names)}::{display_key}::{bpm}::{form_loops}"

    st.markdown(
        '<div class="ui-card soft"><div class="ui-card-title">Generate & play</div>',
        unsafe_allow_html=True,
    )
    _backing_audio_ready = bool(
        st.session_state.get("_last_backing_wav")
        and st.session_state.get("_last_backing_signature") == _current_backing_signature
    )
    _gen_col, _stop_col = st.columns([2, 1])
    with _gen_col:
        _gen_clicked = st.button(
            "▶ Generate backing track",
            key="gen_backing_btn",
            disabled=not bool(backing_chords),
            type="primary",
            use_container_width=True,
        )
    with _stop_col:
        if st.button(
            "■ Stop backing track",
            key="stop_backing_btn",
            disabled=not _backing_audio_ready,
            use_container_width=True,
        ):
            _stop_backing_playback()
            st.rerun()
    if _gen_clicked:
        wav = generate_backing_track(
            backing_events,
            bpm=bpm,
            loops=form_loops,
            style=resolved_groove,
            level=level,
            song_title=song_data.get("title", song),
            song_artist=song_data.get("artist", ""),
        )

        st.session_state["_last_backing_wav"] = wav
        st.session_state["_last_backing_signature"] = _current_backing_signature
        st.session_state["_last_backing_timeline"] = build_chord_event_timeline(
            backing_events,
            bpm,
            form_loops,
        )
        st.session_state["playback_start_time"] = time.time()
        st.session_state["current_chord_timeline"] = st.session_state["_last_backing_timeline"]
        st.session_state["selected_sections"] = list(selected_section_names)
        st.session_state["bpm"] = bpm
        st.session_state["beats_per_bar"] = 4
        st.session_state[f"{_follow_key_prefix}::follow_manual_index"] = 0
        st.session_state[BACKING_AUTOPLAY] = True
        clear_backing_needs_regen(st)

    if _backing_audio_ready:
        _scope_bit = section_scope_label.replace(" ", "_").replace("/", "_")

        st.download_button(
            "Download backing track WAV",
            st.session_state["_last_backing_wav"],
            file_name=f"{song.replace(' ', '_')}_{_scope_bit}_{form_loops}loops.wav",
            mime="audio/wav",
            key="dl_backing_btn",
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
    )

    _chart_expanded = _backing_audio_ready
    with st.expander("Lead-sheet chart & chord follow", expanded=_chart_expanded):
        st.caption("Chord boxes highlight when backing audio is playing.")
        chart_html = full_chord_markdown(
            song,
            song_data,
            chart_sections,
            instrument,
            display_key=chart_display_key,
            level=level,
            section_lyrics=section_lyrics,
            groove_style=resolved_groove,
            bpm=bpm,
            time_signature=default_time_signature(song, chart_sections),
            current_section=None,
            current_bar=None,
            focus=focus,
            chart_mode="backing",
            selected_section_names=selected_section_names,
        )
        if _backing_audio_ready:
            if not st.session_state.get(BACKING_AUTOPLAY, True):
                st.info("Backing playback stopped — press **Generate backing track** or use the player **Play** button to resume.")
            components.html(
                live_follow_along_component_html(
                    st.session_state["_last_backing_wav"],
                    _follow_timeline,
                    chart_html,
                    autoplay=bool(st.session_state.get(BACKING_AUTOPLAY, True)),
                ),
                height=720,
                scrolling=True,
            )
        else:
            st.caption("Generate backing audio above to enable live chord highlighting.")
            st.markdown(chart_html, unsafe_allow_html=True)

    with st.expander("📋 Form timeline & section order", expanded=False):
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
            for name, chords in section_order(sections)
            if chords
        ]
        st.dataframe(
            pd.DataFrame(selected_rows),
            use_container_width=True,
            hide_index=True,
        )

# -------------------------------------------------
# UPLOAD / RECORDING ANALYSIS
# -------------------------------------------------

elif _studio_page == "analysis":

    from recording_analysis import analyze_multitrack, analyze_recording
    from recording_analysis_ui import render_analysis_dashboard

    _render_page_quick_nav("analysis")

    compact_page_title(
        "🎙️",
        "AI Recording Coach",
        "Deep timing, pitch, technique, and musicality feedback — personalized practice plans.",
    )

    st.markdown(
        '<div class="ui-card soft"><div class="ui-card-sub">'
        "Coach reads rhythm, intonation, groove, dynamics, and ensemble balance from your audio. "
        "Scores are encouraging estimates — not exam grades. "
        "Future-ready for live mic, chord ID, and DAW-style markers."
        "</div></div>",
        unsafe_allow_html=True,
    )

    col_mode, col_type = st.columns([1, 1])
    with col_mode:
        analysis_mode = st.radio(
            "Analysis mode",
            ["Single recording", "Multitrack comparison"],
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
            ],
            key="analysis_recording_type",
        )

    if analysis_mode == "Single recording":
        analysis_audio = st.file_uploader(
            "Upload a recording",
            type=["wav", "mp3", "m4a", "ogg", "flac"],
            key="analysis_audio_upload",
        )
        try:
            mic_audio = st.audio_input("Or record live", key="analysis_audio_record")
        except Exception:
            mic_audio = None
            st.caption("Live mic may be unavailable in this Streamlit build — upload still works.")

        audio_obj = mic_audio if mic_audio is not None else analysis_audio
        if audio_obj is not None:
            st.audio(audio_obj.getvalue(), format="audio/wav")

        if st.button("Run AI coach analysis", type="primary", key="analysis_run_btn"):
            if audio_obj is None:
                st.warning("Upload or record audio first.")
            else:
                ctx = _recording_analysis_context(
                    recording_type=recording_type.lower().replace(" ", "_"),
                )
                with st.spinner("Analyzing timing, pitch, groove, and musicality…"):
                    result = analyze_recording(
                        audio_obj.getvalue(),
                        getattr(audio_obj, "name", "recording.wav"),
                        ctx,
                    )
                st.session_state["last_analysis_result"] = result
                st.session_state["last_analysis_audio"] = audio_obj.getvalue()

        if st.session_state.get("last_analysis_result"):
            st.divider()
            st.markdown(
                render_analysis_dashboard(st.session_state["last_analysis_result"]),
                unsafe_allow_html=True,
            )
            if st.session_state.get("last_analysis_audio"):
                with st.expander("Playback — analyzed take", expanded=False):
                    st.audio(st.session_state["last_analysis_audio"], format="audio/wav")

    else:
        st.caption("Upload 2–6 stems (e.g. guitar, vocal, keys) to compare timing and mix balance.")
        mt_files = st.file_uploader(
            "Multitrack layers",
            type=["wav", "mp3", "m4a", "ogg"],
            accept_multiple_files=True,
            key="analysis_multitrack_upload",
        )
        if mt_files and st.button("Analyze ensemble", type="primary", key="analysis_mt_btn"):
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
        if st.session_state.get("last_analysis_result", {}).get("multitrack"):
            st.markdown(
                render_analysis_dashboard(st.session_state["last_analysis_result"]),
                unsafe_allow_html=True,
            )




# -------------------------------------------------
# CUSTOM PROGRESSION LAB
# -------------------------------------------------

elif _studio_page == "custom":

    from cpl_page_ui import render_custom_progression_lab_page

    render_custom_progression_lab_page()


# -------------------------------------------------
# CREATIVE LAB
# -------------------------------------------------

elif _studio_page == "creative":

    _render_page_quick_nav("creative")

    compact_page_title("🧠", "Creative Lab", "Harmony, improvisation, and growth tools.")

    ctx = current_song_context_lab()

    lab_mode = st.selectbox(
        "Analysis mode",
        [
            "Deep Harmonic Analyzer",
            "Improvisation Intelligence",
            "Creative Arrangement Assistant",
            "Adaptive Weakness Detection",
            "AI-Guided Musical Development Tracking"
        ]
    )

    with st.expander(lab_mode, expanded=False):
        if lab_mode == "Deep Harmonic Analyzer":
            st.markdown(deep_harmonic_analysis_text(ctx))
        elif lab_mode == "Improvisation Intelligence":
            st.markdown(improvisation_intelligence_text(ctx))
        elif lab_mode == "Creative Arrangement Assistant":
            target_style = st.selectbox(
                "Transform toward style",
                ["Jobim / Bossa", "Jazz Fusion", "Neo-Soul", "Rock Ballad", "Funk", "Cinematic"],
            )
            arrangement_section = st.selectbox(
                "Arrangement focus",
                ["Full song"] + [name for name, chords in sections.items() if chords],
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

    _render_page_quick_nav("multitrack")

    compact_page_title(
        "🎚️",
        "Multitrack Recorder",
        "Overdub studio — AI feedback on **Analysis** page.",
    )
    st.caption("Headphones recommended. Mic input only unless you include backing in the export.")

    MT_SLOTS = [
        "Guitar",
        "Bass",
        "Piano / Keys",
        "Vocals",
        "Sax / winds",
        "Extra layer",
    ]

    if "mt_tracks" not in st.session_state:
        st.session_state.mt_tracks = {slot: None for slot in MT_SLOTS}
    if "mt_track_filenames" not in st.session_state:
        st.session_state.mt_track_filenames = {
            slot: f"{slot.replace(' ', '_').lower()}.wav" for slot in MT_SLOTS
        }

    mt_time_sig = default_time_signature(song, sections)
    mt_beats_per_bar = beats_per_bar_from_signature(mt_time_sig)
    mt_sec_names = [name for name, chs in section_order(sections) if chs]

    with st.expander("1. Session setup (scope, BPM, monitor backing)", expanded=True):
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
        )

        mt_selected_sections = []
        if mt_scope == "Single section (verse, chorus, solo, …)" and mt_sec_names:
            mt_selected_sections = [
                st.selectbox(
                    "Section",
                    mt_sec_names,
                    key="mt_single_section",
                )
            ]
        elif mt_scope == "Multiple sections" and mt_sec_names:
            mt_default = [
                name
                for name in mt_sec_names
                if any(token in name.lower() for token in ["verse", "chorus", "solo"])
            ] or mt_sec_names[:2]
            mt_selected_sections = st.multiselect(
                "Sections (song order)",
                mt_sec_names,
                default=mt_default,
                key="mt_multi_sections",
            )
        elif mt_scope == "Free layering (no backing)":
            mt_selected_sections = []

        mt_scope_label = (
            "free layering"
            if mt_scope == "Free layering (no backing)"
            else ("full song" if not mt_selected_sections else " + ".join(mt_selected_sections))
        )

        col_mt_a, col_mt_b, col_mt_c = st.columns(3)

        with col_mt_a:
            mt_bpm = st.slider(
                "Session BPM",
                50,
                180,
                int(st.session_state.get("bpm", 100)),
                5,
                key="multitrack_bpm",
            )
            mt_loops = st.slider(
                "Section repeats (loop recording)",
                1,
                8,
                2,
                1,
                key="mt_section_loops",
                disabled=mt_scope == "Free layering (no backing)",
            )
            mt_groove = st.selectbox(
                "Groove style",
                ["Auto", "Pop groove", "Rock groove", "Jazz swing", "Bossa nova", "Funk groove", "Ballad"],
                key="mt_groove_style",
                disabled=mt_scope == "Free layering (no backing)",
            )

        with col_mt_b:
            count_in_label = st.selectbox(
                "Count-in before playback",
                ["None", "1 bar", "2 bars"],
                index=1,
                key="mt_count_in_bars",
            )
            mt_count_in_bars = {"None": 0, "1 bar": 1, "2 bars": 2}[count_in_label]
            mt_metronome_playback = st.checkbox(
                "Metronome during playback",
                value=False,
                key="mt_metronome_playback",
            )
            mt_loop_backing = st.checkbox(
                "Loop backing / section",
                value=True,
                key="mt_loop_backing",
            )

        with col_mt_c:
            use_backing_monitor = st.checkbox(
                "Use backing track while recording",
                value=mt_scope != "Free layering (no backing)",
                help="Plays in headphones/speakers for timing. Not baked into your recorded layers.",
                key="mt_use_backing_monitor",
            )
            include_backing_in_mix = st.checkbox(
                "Include backing in exported mix",
                value=False,
                key="include_backing_mix",
            )
            backing_volume = st.slider(
                "Backing level (monitor + export)",
                0.0,
                1.5,
                0.75,
                0.05,
                key="backing_volume",
            )

        mt_events = (
            chord_events_for_selected_sections(sections, mt_selected_sections)
            if mt_scope != "Free layering (no backing)"
            else []
        )
        mt_resolved_groove = infer_groove_style(song_data, mt_groove)
        mt_bar_duration = (60 / max(1, mt_bpm)) * mt_beats_per_bar
        mt_backing_duration = len(mt_events) * mt_bar_duration * max(1, mt_loops)

        if mt_scope != "Free layering (no backing)" and not mt_events:
            st.warning("Choose at least one section (or use Free layering).")
        else:
            st.caption(
                f"Target: **{mt_scope_label}** | {mt_time_sig} @ {mt_bpm} BPM | "
                f"{len(mt_events)} bars per pass × {mt_loops} repeat(s) ≈ {mt_backing_duration:.1f}s"
            )

        if st.button(
            "Prepare monitor backing (no count-in in file)",
            key="mt_prepare_backing",
            disabled=mt_scope == "Free layering (no backing)" or not mt_events,
        ):
            monitor_wav, _ = multitrack_monitor_backing_bytes(
                sections,
                mt_selected_sections,
                bpm=mt_bpm,
                loops=mt_loops,
                style=mt_resolved_groove,
                level=level,
            )
            st.session_state.multitrack_backing_music_wav = monitor_wav
            st.session_state.mt_backing_scope = mt_scope_label
            st.session_state.mt_backing_duration = mt_backing_duration
            st.success("Monitor backing ready. Use the studio transport below while recording layers.")

    monitor_wav = st.session_state.get("multitrack_backing_music_wav")
    backing_b64 = (
        base64.b64encode(monitor_wav).decode("ascii")
        if monitor_wav and use_backing_monitor
        else None
    )

    if monitor_wav and use_backing_monitor:
        with st.expander("Preview monitor backing WAV"):
            st.audio(monitor_wav, format="audio/wav")

    st.divider()
    st.markdown("**2. Record or upload layers**")
    st.caption("Expand a slot to record or upload that instrument.")
    track_items_for_mix = []
    mt_controls = ensure_multitrack_track_controls([])

    for slot in MT_SLOTS:
        with st.expander(slot, expanded=False):
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
                    st.caption("Recording unavailable in this Streamlit build — upload still works.")

                if st.button(f"Save layer — {slot}", key=f"mt_save_{slot}"):
                    audio_obj = recorded if recorded is not None else uploaded
                    if audio_obj is not None:
                        st.session_state.mt_tracks[slot] = audio_obj.getvalue()
                        st.session_state.mt_track_filenames[slot] = getattr(
                            audio_obj, "name", f"{slot}.wav"
                        )
                        st.session_state[f"mt_name_{slot}"] = layer_name
                        st.success(f"{layer_name} saved.")
                        st.rerun()
                    st.warning("Record or upload audio first.")

            with c2:
                st.session_state[f"mt_vol_{slot}"] = st.slider(
                    "Volume",
                    0.0,
                    2.0,
                    float(st.session_state.get(f"mt_vol_{slot}", 1.0)),
                    0.05,
                    key=f"mt_vol_slider_{slot}",
                )
                st.session_state[f"mt_delay_{slot}"] = st.slider(
                    "Align (seconds ±)",
                    -3.0,
                    3.0,
                    float(st.session_state.get(f"mt_delay_{slot}", 0.0)),
                    0.05,
                    key=f"mt_delay_slider_{slot}",
                )
                st.caption("Positive = later. Negative = earlier.")

            with c3:
                ctrl = mt_controls.setdefault(
                    layer_name,
                    {"volume": 1.0, "mute": False, "solo": False, "delay": 0.0},
                )
                ctrl["mute"] = st.checkbox("Mute", key=f"mt_mute_{slot}")
                ctrl["solo"] = st.checkbox("Solo", key=f"mt_solo_{slot}")
                ctrl["volume"] = st.session_state[f"mt_vol_{slot}"]
                ctrl["delay"] = st.session_state[f"mt_delay_{slot}"]

            saved_audio = st.session_state.mt_tracks.get(slot)
            if saved_audio:
                st.audio(saved_audio)
                track_items_for_mix.append(
                    {
                        "name": layer_name,
                        "audio_bytes": saved_audio,
                        "filename": st.session_state.mt_track_filenames.get(slot, f"{slot}.wav"),
                        "volume": st.session_state[f"mt_vol_{slot}"],
                        "delay": st.session_state[f"mt_delay_{slot}"],
                        "mute": mt_controls.get(layer_name, {}).get("mute", False),
                        "solo": mt_controls.get(layer_name, {}).get("solo", False),
                    }
                )

    track_items_for_studio = list(track_items_for_mix)
    layer_names = [item["name"] for item in track_items_for_studio]
    ensure_multitrack_track_controls(layer_names)
    studio_tracks = multitrack_studio_track_payloads(track_items_for_studio, mt_controls)

    st.divider()
    st.subheader("3. Studio transport & track mixer")
    st.caption(
        "Press **Play with count-in** for a studio-style start on beat 1. "
        "Mute, solo, and volume here mirror your layer controls above."
    )
    components.html(
        multitrack_studio_html(
            backing_b64=backing_b64,
            tracks=studio_tracks,
            bpm=mt_bpm,
            beats_per_bar=mt_beats_per_bar,
            count_in_bars=mt_count_in_bars,
            metronome_during_playback=mt_metronome_playback,
            loop_backing=mt_loop_backing,
            backing_monitor_enabled=bool(backing_b64),
            backing_monitor_volume=backing_volume,
            scope_label=st.session_state.get("mt_backing_scope", mt_scope_label),
            time_signature=mt_time_sig,
            backing_duration_sec=float(
                st.session_state.get("mt_backing_duration", mt_backing_duration)
            ),
        ),
        height=520,
        scrolling=True,
    )

    st.divider()
    st.subheader("4. Export mix")

    if not track_items_for_mix:
        st.info("Save at least one layer above to export a mix.")

    if st.button("Create mixed WAV", disabled=not track_items_for_mix):
        try:
            backing_y = None
            if include_backing_in_mix and mt_events:
                backing_y = backing_bytes_to_float(
                    mt_events,
                    bpm=mt_bpm,
                    style=mt_resolved_groove,
                    level=level,
                )
                if mt_loops > 1:
                    backing_y = np.tile(backing_y, int(mt_loops))
                backing_y = backing_y * backing_volume

            mixed = mix_multitrack(backing_y, track_items_for_mix)
            st.session_state.mixed_track_wav = wav_bytes_from_float(mixed)
            st.success("Mixed track created.")
        except Exception as e:
            st.error(f"Could not create mix: {e}")

    if st.session_state.get("mixed_track_wav"):
        st.audio(st.session_state.mixed_track_wav, format="audio/wav")
        st.download_button(
            "Download mixed track WAV",
            st.session_state.mixed_track_wav,
            file_name=f"{song.replace(' ', '_')}_multitrack_mix.wav",
            mime="audio/wav",
        )
        st.caption(
            "Want interpretation, pitch/chord feedback, or practice coaching on this take? "
            "Open **Upload & Recording Analysis**."
        )

    st.divider()
    if st.button("Clear all multitrack layers"):
        st.session_state.mt_tracks = {slot: None for slot in MT_SLOTS}
        st.session_state.mt_track_filenames = {
            slot: f"{slot.replace(' ', '_').lower()}.wav" for slot in MT_SLOTS
        }
        st.session_state.mixed_track_wav = None
        st.session_state.multitrack_backing_music_wav = None
        st.session_state.mt_track_controls = {}
        st.success("Layers cleared.")
        st.rerun()

# -------------------------------------------------
# PRACTICE LOG
# -------------------------------------------------

elif _studio_page == "log":

    _render_page_quick_nav("log")

    compact_page_title("📓", "Practice Log", "Session history and progress over time.")

    _session_mins = st.slider(
        "Target session length (minutes)",
        20,
        90,
        45,
        5,
        key="ai_session_builder_minutes",
    )
    if st.button("Build practice session from log history", key="build_session_from_logs"):
        st.session_state["_ai_practice_session_plan"] = build_practice_session_from_logs(
            load_logs(),
            ALL_SONG_RECORDS,
            minutes=int(_session_mins),
        )
    _plan = st.session_state.get("_ai_practice_session_plan")
    if _plan:
        st.markdown(
            '<div class="ui-card soft"><div class="ui-card-title">Suggested session</div>',
            unsafe_allow_html=True,
        )
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
        st.markdown("</div>", unsafe_allow_html=True)
        if st.button("Start warmup on Practice page", key="session_go_practice"):
            st.session_state["studio_page"] = "practice"
            st.rerun()

    if st.button("Clear practice log", type="secondary"):

        save_logs([])

        st.success(
            "Practice log cleared."
        )

    with st.form("practice_form"):

        practice_text_input = st.text_area(
            "What did you practice today?",
            value=f"{genre} practice — {song}"
        )

        rating = st.slider(
            "How did it go?",
            1,
            10,
            6
        )

        submitted = st.form_submit_button(
            "Save Practice Log"
        )

    if submitted:

        logs = load_logs()

        logs.append({
            "date": str(date.today()),
            "genre": genre,
            "song": song,
            "instrument": instrument,
            "level": level,
            "focus": focus,
            "practice": practice_text_input,
            "rating": rating
        })

        save_logs(logs)

        st.success(
            "Practice log saved."
        )

    logs = load_logs()

    if logs:

        st.dataframe(
            pd.DataFrame(logs),
            use_container_width=True
        )

    else:

        st.info(
            "No practice logs yet."
        )

"""Streamlit UI — Improvisation Intelligence (Creative Lab)."""

from __future__ import annotations

import html
import re
from dataclasses import replace
from typing import Any, Callable

from app_ui import nav_icon_button_label

II_SELECTED_CHORD = "ii_selected_chord"
II_SELECTED_SECTION = "ii_selected_section"
II_SELECTED_CHORD_INDEX = "ii_selected_chord_index"
II_SELECTED_CHORD_LABEL = "ii_selected_chord_label"

_LEGACY_CHORD_TILE_KEY = re.compile(r"^improv_(live|motif)_s\d+_c\d+$")

import streamlit.components.v1 as components

from improvisation_intelligence import (
    DIFFICULTY_LEVELS,
    GROOVE_INTENSITY,
    MOOD_OPTIONS,
    STYLE_JAM_STYLES,
    ChordCoachInsight,
    ImprovSessionContext,
    ai_feedback_preview_lines,
    build_scale_suggestion,
    chord_coach_insight,
    coaching_reference_key,
    format_scale_line,
    flatten_sections,
    generate_jam_session,
    generate_style_progression,
    level_coaching_summary,
)
from creative_key_sync import (
    CREATIVE_MAJOR_KEY_OPTIONS,
    creative_complete_concert_key_options,
    creative_major_shape_key_options,
    on_improv_jam_key_change,
    on_improv_jam_setting_change,
    on_improv_style_jam_setting_change,
    on_improv_style_key_change,
    render_creative_progression_block,
)
from improvisation_harmony import (
    HARMONY_MAP_CHIP_CSS,
    analyze_chord_for_harmony_map,
    deduped_section_chords,
)
from improvisation_missions import (
    IMPROV_MISSION_BACKING_HANDOFF,
    MISSION_EXAMPLE_KEY,
    MISSION_NEW_NONCE_KEY,
    MISSION_NEW_IDEA_DIAG_KEY,
    MISSION_EXAMPLE_GEN_DIAG_KEY,
    MISSION_EXAMPLE_FRESH_RUN_KEY,
    MISSIONS_GENERATE_CONTEXT_KEY,
    MISSIONS_LAST_EXAMPLE_CALLBACK_KEY,
    MISSION_PRACTICE_LICK_KEY,
    MissionExample,
    PRACTICE_MISSIONS,
    apply_mission_motif_transform,
    generate_mission_example,
    load_mission_example,
    mission_example_fingerprint,
    mission_example_for_display,
    motif_material_fingerprint,
    mission_practice_lick_payload,
    queue_mission_practice_lick_handoff,
    rebuild_mission_outputs,
    store_mission_example,
    store_mission_practice_lick_for_backing,
    instrument_family,
    wind_phrasing_lines,
)
from motif_engine import (
    build_motif_guitar_tab,
    build_motif_notation_abc,
    generate_mission_phrase,
    generate_musical_phrase,
    transform_motif,
)
from improvisation_motif import (
    flatten_section_map,
    global_chord_index,
    resolve_improv_chords,
    resolve_improv_sections,
    section_and_chord_at_global_index,
)

MOTIF_OUTPUT_NONE = "none"
MOTIF_OUTPUT_NOTATION = "notation"
MOTIF_OUTPUT_TAB = "tab"


def _overlay_pending_practice_key(session_state: dict, token: str) -> str:
    try:
        from music_workflow_pending_song_practice_key_edit import (
            overlay_concert_token_with_pending_practice_key,
        )

        return overlay_concert_token_with_pending_practice_key(session_state, token) or token
    except ImportError:
        return token


def _authoritative_practice_chart_key(session_state: dict, fallback: str) -> str:
    try:
        from workflow_key_identity import resolve_practice_key_identity_for_ui

        ident = resolve_practice_key_identity_for_ui(session_state)
        if ident is not None:
            return _overlay_pending_practice_key(session_state, ident.practice_key_token)
    except ImportError:
        pass
    try:
        from creative_key_sync import entry_jam_practice_key_authority_active, resolve_creative_tab_practice_key_token

        if entry_jam_practice_key_authority_active(session_state):
            jam_tok = resolve_creative_tab_practice_key_token(session_state)
            if jam_tok:
                return jam_tok
    except ImportError:
        pass
    try:
        from music_workflow_song_practice import resolve_song_practice_key_token

        tok = resolve_song_practice_key_token(session_state)
        if tok:
            return _overlay_pending_practice_key(session_state, tok)
    except ImportError:
        pass
    try:
        from musical_context_authority import resolve_authoritative_practice_key
        from music_theory import key_center_token

        pk = resolve_authoritative_practice_key(session_state)
        return _overlay_pending_practice_key(
            session_state,
            key_center_token(pk.practice_tonic, pk.practice_mode),
        )
    except ImportError:
        return _overlay_pending_practice_key(
            session_state,
            str(session_state.get("display_key") or fallback or "C"),
        )


def _authoritative_concert_sections(
    session_state: dict,
    fallback: dict[str, list[str]],
) -> dict[str, list[str]]:
    try:
        from improvisation_motif import concert_song_sections_from_session

        concert = concert_song_sections_from_session(session_state)
        if concert:
            return concert
    except ImportError:
        pass
    return fallback if isinstance(fallback, dict) else {}


def _parent_practice_key_label(improv_ctx: ImprovSessionContext) -> str:
    return str(improv_ctx.display_key or improv_ctx.key_center or "C")


def _target_focus_chord(session_state: dict, chords: list[str]) -> str:
    if not chords:
        return ""
    cur, _idx = _selected_chord(session_state, chords)
    return str(cur or "")


def _coherent_improv_key_pair(session_state: dict, improv_ctx: ImprovSessionContext) -> tuple[str, str]:
    """Return (concert_practice_key, musician_facing_chart_key)."""
    fallback = str(improv_ctx.key_center or improv_ctx.display_key or "C")
    concert = _authoritative_practice_chart_key(session_state, fallback)
    try:
        from effective_practice_context import musician_facing_chart_key

        chart = musician_facing_chart_key(session_state, concert)
    except ImportError:
        chart = str(improv_ctx.display_key or concert)
    return concert, chart


def _player_facing_chord(session_state: dict, chord: str, *, concert_key: str) -> str:
    """Concert chord → Written/Shape display symbol. Empty in stays empty out."""
    src = str(chord or "").strip()
    if not src:
        return ""
    try:
        from effective_practice_context import musician_facing_chart_key, musician_facing_chord

        chart = musician_facing_chart_key(session_state, concert_key)
        return musician_facing_chord(src, concert_key=concert_key, chart_key=chart)
    except ImportError:
        return src


def _motif_notation_reference_key(improv_ctx: ImprovSessionContext, chord: str = "") -> str:
    if chord:
        try:
            from harmonic_spelling import harmonic_reference_for_chord

            return harmonic_reference_for_chord(
                chord,
                song_display_key=improv_ctx.display_key,
                song_key_center=improv_ctx.key_center,
            )
        except ImportError:
            pass
    return coaching_reference_key(
        key_center=improv_ctx.key_center,
        display_key=improv_ctx.display_key,
    )


def _touch_creative_workspace(session_state: dict) -> None:
    try:
        from creative_workspace_persistence import mark_creative_workspace_dirty

        mark_creative_workspace_dirty(session_state)
    except ImportError:
        pass

from studio_page_state import (
    CREATIVE_TOOL_ICONS,
    IMPROV_ENTRY_MODES,
    IMPROV_SONG_SOURCES,
    IMPROV_TAB_NAMES,
    apply_improv_song_source,
    creative_song_source_display_label,
    creative_tool_display_label,
    creative_tool_heading_markdown,
    flush_pending_improv_song_source,
    init_improvisation_state,
    resolve_improv_song_preview,
    resolve_improv_song_source,
    ensure_improv_entry_mode_restored,
    ensure_improv_intelligence_tab_restored,
    ensure_creative_widgets_from_backing_context,
)
from songs.picker_session import mark_improv_tab_user_touched

# Bump when Missions tab layout/flow changes (visible in ?dev=1 route marker).
MISSIONS_UI_BUILD_ID = "phase2a-live-only-mix-v3"

# Read-only dispatch shadow (not a Streamlit widget key).
IMPROV_INTELLIGENCE_TAB_FOR_RENDER_KEY = "_improv_intelligence_tab_for_render"


def _improv_dev_mode(session_state: dict, st_module: Any | None = None) -> bool:
    try:
        from suite_workspace import is_developer_mode_enabled

        return bool(is_developer_mode_enabled(st=st_module))
    except ImportError:
        return bool(session_state.get("_dev_mode") or session_state.get("dev_mode"))


def _deploy_commit_short() -> str:
    try:
        from suite_deploy_marker import resolve_git_commit_short

        return str(resolve_git_commit_short() or "unknown")
    except ImportError:
        return "unknown"


def _render_missions_route_dev_marker(
    st_module: Any,
    session_state: dict,
    *,
    renderer: str,
    branch: str,
    extra: dict[str, Any] | None = None,
) -> None:
    if not _improv_dev_mode(session_state, st_module):
        return
    lab = str(session_state.get("creative_lab_analysis_mode") or "")
    tab = str(session_state.get("improv_intelligence_tab") or "")
    bits = extra or {}
    st_module.markdown(
        f"<p style='font-size:0.78rem;color:#7c3aed;margin:0 0 0.35rem 0;'>"
        f"<strong>DEV Missions route</strong> · renderer <code>{html.escape(renderer)}</code> · "
        f"module <code>improvisation_intelligence_ui</code> · "
        f"UI version <code>{html.escape(MISSIONS_UI_BUILD_ID)}</code> · "
        f"deploy <code>{html.escape(_deploy_commit_short())}</code> · "
        f"branch <code>{html.escape(branch)}</code> · "
        f"lab <code>{html.escape(lab)}</code> · tab <code>{html.escape(tab)}</code>"
        f"{(' · ' + html.escape(str(bits))) if bits else ''}"
        f"</p>",
        unsafe_allow_html=True,
    )


def _normalize_improv_tab_for_render(radio_value: Any) -> str:
    """Map radio return value to a valid tab name — read-only, no session writes."""
    tab = str(radio_value or IMPROV_TAB_NAMES[0]).strip()
    if tab in IMPROV_TAB_NAMES:
        return tab
    return IMPROV_TAB_NAMES[0]


def _queue_style_jam_generation_intent(session_state: dict[str, Any]) -> None:
    from music_workflow_pending_generated_progression import queue_generated_progression_intent

    queue_generated_progression_intent(session_state, owner="style_jam")


def _queue_jam_session_generation_intent(session_state: dict[str, Any]) -> None:
    from music_workflow_pending_generated_progression import queue_generated_progression_intent

    queue_generated_progression_intent(session_state, owner="jam_session_generator")


def render_improvisation_intelligence_lab(
    st: Any,
    *,
    ctx: dict[str, Any],
    session_state: dict,
    chart_key: str,
    sections: dict[str, list[str]],
    song_data: dict,
    bpm: int,
    genre: str,
    is_custom: bool,
    on_open_backing: Callable[[], None] | None = None,
    on_open_practice: Callable[[], None] | None = None,
    on_open_analysis: Callable[[], None] | None = None,
    on_song_source_change: Callable[[str], None] | None = None,
    apply_style_to_playback: Callable[[], None] | None = None,
    on_go_song_selection: Callable[[], None] | None = None,
    on_go_custom_progression: Callable[[], None] | None = None,
) -> None:
    """Full Improvisation Intelligence workspace under Creative Lab."""
    from music_dev_route_baseline import render_route_baseline_caption, route_perf_begin, route_perf_end

    route_perf_begin(session_state, "creative.improv_intelligence", st_module=st)
    try:
        from music_route_gates import resolve_route_context

        resolve_route_context(session_state)
    except ImportError:
        pass
    from studio_page_persistence import ensure_creative_improv_initialized

    ensure_creative_improv_initialized(session_state, is_custom_active=is_custom)
    try:
        from music_workflow_activation import bootstrap_active_workflow_if_needed

        bootstrap_active_workflow_if_needed(session_state)
    except ImportError:
        pass
    flush_pending_improv_song_source(session_state)
    from creative_key_sync import flush_pending_creative_major_keys

    flush_pending_creative_major_keys(session_state)
    try:
        from session_widget_safe import apply_pending_widget_hydrates

        apply_pending_widget_hydrates(session_state)
    except ImportError:
        pass
    ensure_creative_widgets_from_backing_context(session_state)
    ensure_improv_intelligence_tab_restored(session_state)
    _creative_tab = str(session_state.get("improv_intelligence_tab") or "Entry & Jam")
    if _improv_dev_mode(session_state, st) and _creative_tab in ("Entry & Jam", "Missions", "Metrics & AI"):
        try:
            from backing_musical_state import (
                render_backing_key_state_diagnostics,
                resolve_current_backing_musical_state,
            )

            _creative_musical = resolve_current_backing_musical_state(session_state)
            render_backing_key_state_diagnostics(st, session_state, _creative_musical)
        except Exception:
            pass

    instrument = str(ctx.get("instrument") or "Guitar")
    level = str(ctx.get("level") or "Intermediate")
    _sel = session_state.get("selected_song") if isinstance(session_state.get("selected_song"), dict) else {}
    _pick = str(session_state.get("active_catalog_pick_key") or "").strip()
    _sel_pk = str((_sel or {}).get("pick_key") or "").strip()
    if _sel and _pick and _sel_pk == _pick:
        song_title = str((_sel or {}).get("title") or session_state.get("song") or ctx.get("song") or "Song")
        artist = str((_sel or {}).get("artist") or ctx.get("artist") or "")
    else:
        song_title = str(session_state.get("song") or (_sel or {}).get("title") or ctx.get("song") or "Song")
        artist = str(ctx.get("artist") or (_sel or {}).get("artist") or "")

    try:
        from app_ui import (
            inject_creative_studio_styles,
            render_creative_studio_panel_header,
        )
    except Exception:
        inject_creative_studio_styles = lambda _st: None  # type: ignore
        render_creative_studio_panel_header = lambda *_a, **_k: None  # type: ignore

    inject_creative_studio_styles(st)

    concert_key = _authoritative_practice_chart_key(session_state, chart_key)
    try:
        from effective_practice_context import musician_facing_chart_key

        display_chart = musician_facing_chart_key(session_state, concert_key)
    except ImportError:
        display_chart = concert_key
    sections = _authoritative_concert_sections(session_state, sections)

    _section_order = list(song_data.get("section_order") or ctx.get("section_order") or list(sections.keys()))
    improv_ctx = ImprovSessionContext(
        song_title=song_title,
        artist=artist,
        key_center=concert_key,
        display_key=display_chart,
        instrument=instrument,
        level=level,
        focus=str(ctx.get("focus") or "Improvisation"),
        sections=sections,
        bpm=bpm,
        style_label=genre,
        progression_flat=flatten_sections(sections, section_names=_section_order or None),
        section_order=_section_order,
    )

    with st.container(key="creative_studio_panel", border=False):
        st.markdown('<div class="ui-creative-studio-shell">', unsafe_allow_html=True)
        try:
            render_creative_studio_panel_header(
                st,
                instrument=instrument,
                level=level,
                song_title=song_title,
            )
        except Exception:
            pass

        st.markdown('<div class="ui-creative-mode-segment">', unsafe_allow_html=True)
        def _on_improv_tab_change() -> None:
            mark_improv_tab_user_touched(session_state)
            try:
                from music_workflow_creative_nav import sync_workflow_for_creative_tab

                sync_workflow_for_creative_tab(
                    session_state,
                    str(session_state.get("improv_intelligence_tab") or "").strip(),
                )
            except ImportError:
                pass

        try:
            from widget_callback_diagnostics import log_widget_callback_registration

            log_widget_callback_registration(
                widget_key="improv_intelligence_tab",
                callback=_on_improv_tab_change,
            )
        except ImportError:
            pass

        active_tab = st.radio(
            "Improvisation section",
            list(IMPROV_TAB_NAMES),
            horizontal=True,
            key="improv_intelligence_tab",
            format_func=creative_tool_display_label,
            label_visibility="collapsed",
            on_change=_on_improv_tab_change,
        )
        _wf_tab_status = "skipped"
        try:
            from music_workflow_creative_nav import sync_workflow_for_creative_tab

            _wf_tab_status = sync_workflow_for_creative_tab(session_state, str(active_tab or "").strip())
        except ImportError:
            pass
        if _wf_tab_status == "queued":
            try:
                from music_app_rerun import request_app_rerun
                from music_workflow_creative_nav import (
                    creative_tab_workflow_rerun_fingerprint,
                    should_request_creative_tab_workflow_rerun,
                )

                if should_request_creative_tab_workflow_rerun(session_state, str(active_tab or "")):
                    fp = creative_tab_workflow_rerun_fingerprint(session_state, str(active_tab or ""))
                    request_app_rerun(
                        st,
                        session_state,
                        reason="creative_tab_workflow_queued",
                        stage="page_dispatch_creative_tab",
                        fingerprint=fp,
                    )
            except ImportError:
                st.rerun()
        try:
            from music_workflow_activation import activation_user_notice

            notice = activation_user_notice(session_state)
            if notice:
                st.warning(notice)
        except ImportError:
            pass
        st.markdown("</div>", unsafe_allow_html=True)

        tab_for_render = _normalize_improv_tab_for_render(active_tab)
        session_state[IMPROV_INTELLIGENCE_TAB_FOR_RENDER_KEY] = tab_for_render

        if tab_for_render == "Entry & Jam":
            _tab_entry_modes(
                st,
                session_state=session_state,
                improv_ctx=improv_ctx,
                is_custom=is_custom,
                on_open_backing=on_open_backing,
                on_open_practice=on_open_practice,
                on_song_source_change=on_song_source_change,
                apply_style_to_playback=apply_style_to_playback,
                on_go_song_selection=on_go_song_selection,
                on_go_custom_progression=on_go_custom_progression,
            )
        elif tab_for_render == "Live Coach":
            _tab_live_coach(st, session_state=session_state, improv_ctx=improv_ctx)
        elif tab_for_render == "Phrase / Motif":
            _tab_motif(
                st,
                session_state=session_state,
                improv_ctx=improv_ctx,
                level=level,
                instrument=instrument,
                bpm=bpm,
            )
        elif tab_for_render == "Missions":
            _tab_missions(
                st,
                session_state=session_state,
                improv_ctx=improv_ctx,
                bpm=bpm,
                on_open_backing=on_open_backing,
                on_open_practice=on_open_practice,
                on_open_analysis=on_open_analysis,
            )
        elif tab_for_render == "Harmony Map":
            _tab_harmony_map(st, session_state=session_state, improv_ctx=improv_ctx)
        elif tab_for_render == "Deep Harmony":
            _tab_deep_harmony(
                st,
                session_state=session_state,
                improv_ctx=improv_ctx,
                song_data=song_data,
                genre=genre,
            )
        elif tab_for_render == "Metrics & AI":
            _tab_metrics_ai(
                st,
                session_state=session_state,
                improv_ctx=improv_ctx,
                on_open_analysis=on_open_analysis,
            )

        route_perf_end(session_state, "creative.improv_intelligence", st_module=st)
        render_route_baseline_caption(st, session_state, route_id="creative.improv_intelligence")
        st.markdown("</div>", unsafe_allow_html=True)


def _tab_entry_modes(
    st: Any,
    *,
    session_state: dict,
    improv_ctx: ImprovSessionContext,
    is_custom: bool,
    on_open_backing: Callable[[], None] | None,
    on_open_practice: Callable[[], None] | None,
    on_song_source_change: Callable[[str], None] | None,
    apply_style_to_playback: Callable[[], None] | None,
    on_go_song_selection: Callable[[], None] | None = None,
    on_go_custom_progression: Callable[[], None] | None = None,
) -> None:
    try:
        from app_ui import render_creative_song_context_card
    except Exception:
        render_creative_song_context_card = None  # type: ignore

    st.markdown(
        '<p class="ui-creative-section-label">Improvisation entry mode</p>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="ui-creative-entry-segment">', unsafe_allow_html=True)

    def _on_entry_mode_change() -> None:
        try:
            from creative_tab_tool_persistence import handle_user_creative_selector_change

            handle_user_creative_selector_change(session_state, "improv_entry_mode")
        except ImportError:
            mark_improv_tab_user_touched(session_state)
            try:
                from creative_session_state import sync_creative_session_before_persist

                sync_creative_session_before_persist(session_state)
            except ImportError:
                pass
        else:
            try:
                from creative_session_state import sync_creative_session_before_persist

                sync_creative_session_before_persist(session_state)
            except ImportError:
                pass
        try:
            from music_workflow_pending_activation import queue_workflow_activation_for_entry_mode

            queue_workflow_activation_for_entry_mode(session_state)
        except ImportError:
            pass
        if str(session_state.get("improv_entry_mode") or "").strip() == "Song-Based Improvisation":
            try:
                from song_improv_scope_authority import apply_song_improv_entry_defaults

                apply_song_improv_entry_defaults(session_state, source="entry_mode_song_based")
            except ImportError:
                pass

    ensure_improv_entry_mode_restored(session_state)
    try:
        from creative_return_trace import snapshot_improv_selector_render_state, trace_improv_selector_restore

        trace_improv_selector_restore(
            session_state,
            "BEFORE_IMPROV_ENTRY_MODE_RADIO",
            before=snapshot_improv_selector_render_state(session_state),
        )
    except ImportError:
        pass
    entry = st.radio(
        "Improvisation entry mode",
        list(IMPROV_ENTRY_MODES),
        horizontal=True,
        key="improv_entry_mode",
        format_func=creative_tool_display_label,
        label_visibility="collapsed",
        on_change=_on_entry_mode_change,
    )
    try:
        from creative_return_trace import snapshot_improv_selector_render_state, trace_improv_selector_restore

        trace_improv_selector_restore(
            session_state,
            "AFTER_IMPROV_ENTRY_MODE_RADIO",
            after=snapshot_improv_selector_render_state(session_state),
            returned=str(entry or ""),
        )
    except ImportError:
        pass
    st.markdown("</div>", unsafe_allow_html=True)

    if entry == "Song-Based Improvisation":
        try:
            from song_improv_scope_authority import ensure_song_improv_scope_on_entry_mode

            ensure_song_improv_scope_on_entry_mode(session_state)
        except ImportError:
            pass
        def _sync_song_source() -> None:
            if on_song_source_change:
                on_song_source_change(
                    str(session_state.get("improv_song_source") or "Active song").strip()
                    or "Active song"
                )

        st.markdown('<p class="ui-creative-section-label">Song source</p>', unsafe_allow_html=True)
        with st.container(key="creative_song_source_panel", border=False):
            st.markdown('<div class="ui-creative-source-panel">', unsafe_allow_html=True)
            source = st.radio(
                "Song source",
                list(IMPROV_SONG_SOURCES),
                horizontal=True,
                key="improv_song_source",
                format_func=creative_song_source_display_label,
                on_change=_sync_song_source,
                label_visibility="collapsed",
            )
            st.markdown("</div>", unsafe_allow_html=True)

        song_preview = resolve_improv_song_preview(session_state)
        preview_sections = dict(song_preview.get("sections") or {})
        if source == "Custom progression":
            pass  # preview_sections already from custom_session bucket
        elif source == "Active song":
            preview_sections = _authoritative_concert_sections(
                session_state,
                preview_sections or improv_ctx.sections,
            )
            if not preview_sections and not is_custom:
                preview_sections = improv_ctx.sections
        elif not preview_sections:
            preview_sections = improv_ctx.sections

        if source == "Active song":
            flat_preview = [c for chs in preview_sections.values() for c in chs if str(c).strip()]
            chord_count = len(flat_preview) if flat_preview else len(improv_ctx.progression_flat)
            practice_key = _authoritative_practice_chart_key(
                session_state,
                str(song_preview.get("display_key") or improv_ctx.display_key or "C"),
            )
            if render_creative_song_context_card:
                render_creative_song_context_card(
                    st,
                    title=str(song_preview.get("title") or improv_ctx.song_title),
                    artist=str(song_preview.get("artist") or improv_ctx.artist),
                    display_key=practice_key,
                    chord_count=chord_count,
                    source_label="Active song · Song Selection",
                )
            st.markdown(
                '<p class="ui-creative-progression-preview">Uses the song selected in '
                "<strong>Song Selection</strong> (global studio source).</p>",
                unsafe_allow_html=True,
            )
            if on_go_song_selection:
                _nav1, _nav2, _ = st.columns([1.1, 1.1, 2.8])
                with _nav1:
                    st.markdown('<div class="ui-creative-quick-actions">', unsafe_allow_html=True)
                    if st.button("🎼 Songs", key="improv_go_picker", type="secondary"):
                        on_go_song_selection()
                    st.markdown("</div>", unsafe_allow_html=True)
        else:
            custom_sections = song_preview.get("sections") or {}
            flat_custom = [c for chs in custom_sections.values() for c in chs if str(c).strip()]
            if render_creative_song_context_card:
                render_creative_song_context_card(
                    st,
                    title=str(song_preview.get("title") or "Custom Progression"),
                    artist=str(song_preview.get("artist") or "Custom"),
                    display_key=str(song_preview.get("display_key") or "C"),
                    chord_count=len(flat_custom),
                    source_label="Custom progression",
                    variant="custom",
                )
            if not is_custom and source == "Custom progression":
                st.markdown(
                    '<p class="ui-creative-progression-preview">Preview only — your catalog active song '
                    "stays unchanged until you open Practice or Backing.</p>",
                    unsafe_allow_html=True,
                )
            if on_go_custom_progression:
                _nav1, _ = st.columns([1.2, 3.8])
                with _nav1:
                    st.markdown('<div class="ui-creative-quick-actions">', unsafe_allow_html=True)
                    if st.button("✏️ Custom", key="improv_go_custom", type="secondary"):
                        on_go_custom_progression()
                    st.markdown("</div>", unsafe_allow_html=True)

        if preview_sections:
            practice_key = _authoritative_practice_chart_key(
                session_state,
                str(song_preview.get("display_key") or improv_ctx.display_key or "C"),
            )
            render_creative_progression_block(
                st,
                session_state,
                preview_sections,
                concert_key=practice_key,
            )

        _render_open_practice_backing_row(
            st,
            on_open_backing=on_open_backing,
            on_open_practice=on_open_practice,
            workflow="song",
        )

    elif entry == "Style Jam Mode":
        try:
            from music_workflow_pending_generated_key_edit import (
                PENDING_GENERATED_KEY_EDIT_LAST_DIAG_KEY,
                PENDING_GENERATED_KEY_EDIT_USER_MESSAGE_KEY,
            )

            _gen_key_msg = str(session_state.get(PENDING_GENERATED_KEY_EDIT_USER_MESSAGE_KEY) or "").strip()
            if _gen_key_msg:
                st.warning(_gen_key_msg)
            _diag = session_state.get(PENDING_GENERATED_KEY_EDIT_LAST_DIAG_KEY)
            if isinstance(_diag, dict) and _diag.get("failed_predicate"):
                st.caption(f"Key change diagnostic: {_diag.get('failed_predicate')}")
        except ImportError:
            pass
        st.markdown(
            f'<p class="ui-creative-section-label">{html.escape(creative_tool_display_label("Style Jam Mode"))}</p>',
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            st.selectbox(
                "Style",
                list(STYLE_JAM_STYLES),
                key="improv_style",
                on_change=on_improv_style_jam_setting_change,
            )
            try:
                from music_theory import display_key_label

                _style_key_opts = creative_complete_concert_key_options(
                    session_state,
                    selected=str(session_state.get("improv_style_key") or "C"),
                )
            except Exception:
                _style_key_opts = list(CREATIVE_MAJOR_KEY_OPTIONS)
                display_key_label = lambda k: k  # type: ignore
            st.selectbox(
                "Concert Key",
                _style_key_opts,
                key="improv_style_key",
                format_func=display_key_label,
                on_change=on_improv_style_key_change,
            )
        with c2:
            st.selectbox(
                "Difficulty",
                list(DIFFICULTY_LEVELS),
                key="improv_difficulty",
                on_change=on_improv_style_jam_setting_change,
            )
            st.selectbox(
                "Mood",
                list(MOOD_OPTIONS),
                key="improv_mood",
                on_change=on_improv_style_jam_setting_change,
            )
        with c3:
            st.slider(
                "Tempo (BPM)",
                60,
                200,
                key="improv_style_bpm",
                step=1,
                on_change=on_improv_style_jam_setting_change,
            )
            st.selectbox(
                "Groove intensity",
                list(GROOVE_INTENSITY),
                key="improv_groove",
                on_change=on_improv_style_jam_setting_change,
            )

        prompt = st.text_input(
            "Describe your jam (optional)",
            placeholder="e.g. medium jazz-funk progression in D minor",
            key="improv_style_prompt",
        )
        if st.button(
            "Generate progression",
            type="primary",
            key="improv_gen_style",
            on_click=_queue_style_jam_generation_intent,
            args=(session_state,),
        ):
            pass

        gen = session_state.get("improv_generated_sections")
        if gen:
            _style_label = str(session_state.get("improv_style") or "Style jam")
            _key_token = str(session_state.get("improv_style_key") or "C")
            try:
                from music_theory import display_key_label

                _key_label = display_key_label(_key_token)
            except ImportError:
                _key_label = _key_token
            st.success(
                f"Generated **{_style_label}** in **{_key_label}** · "
                f"{str(session_state.get('improv_mood') or 'Mellow')} · "
                f"{int(session_state.get('improv_style_bpm', 110))} BPM"
            )
            for sec, chs in gen.items():
                st.markdown(f"**{sec}**")
                render_creative_progression_block(st, session_state, {sec: chs})
            if apply_style_to_playback:
                apply_style_to_playback()
            _render_open_practice_backing_row(
                st,
                on_open_backing=on_open_backing,
                on_open_practice=on_open_practice,
                workflow="jam",
            )

    else:
        try:
            from music_workflow_pending_generated_key_edit import (
                PENDING_GENERATED_KEY_EDIT_LAST_DIAG_KEY,
                PENDING_GENERATED_KEY_EDIT_USER_MESSAGE_KEY,
            )

            _gen_key_msg = str(session_state.get(PENDING_GENERATED_KEY_EDIT_USER_MESSAGE_KEY) or "").strip()
            if _gen_key_msg:
                st.warning(_gen_key_msg)
            _diag = session_state.get(PENDING_GENERATED_KEY_EDIT_LAST_DIAG_KEY)
            if isinstance(_diag, dict) and _diag.get("failed_predicate"):
                st.caption(f"Key change diagnostic: {_diag.get('failed_predicate')}")
        except ImportError:
            pass
        st.markdown(creative_tool_heading_markdown("Jam Session Generator"))
        e1, e2 = st.columns(2)
        with e1:
            ensemble = st.selectbox(
                "Ensemble",
                [
                    "Jazz trio",
                    "Jazz quartet",
                    "Neo-soul band",
                    "Rock trio",
                    "Latin quartet",
                    "Lo-fi duo",
                ],
                key="improv_ensemble",
            )
            style = st.selectbox(
                "Groove style",
                list(STYLE_JAM_STYLES),
                key="improv_jam_style",
                on_change=on_improv_jam_setting_change,
            )
        with e2:
            try:
                from creative_key_sync import creative_complete_concert_key_options
                from music_theory import display_key_label

                _jam_key_opts = creative_complete_concert_key_options(
                    session_state,
                    selected=str(session_state.get("improv_jam_key") or "C"),
                )
            except ImportError:
                _jam_key_opts = list(CREATIVE_MAJOR_KEY_OPTIONS)
                display_key_label = lambda k: k  # type: ignore
            key_c = st.selectbox(
                "Concert Key",
                _jam_key_opts,
                key="improv_jam_key",
                format_func=display_key_label,
                on_change=on_improv_jam_key_change,
            )
            tempo = st.slider(
                "Tempo",
                70,
                180,
                key="improv_jam_bpm",
                step=1,
                on_change=on_improv_jam_setting_change,
            )
            st.selectbox(
                "Atmosphere",
                list(MOOD_OPTIONS),
                key="improv_jam_mood",
                on_change=on_improv_jam_setting_change,
            )

        if st.button(
            "Generate jam session",
            type="primary",
            key="improv_gen_jam",
            on_click=_queue_jam_session_generation_intent,
            args=(session_state,),
        ):
            pass

        jam = session_state.get("improv_jam_session")
        if jam:
            st.markdown(f"### {jam.get('title', 'Jam session')}")
            st.caption(jam.get("prompt", ""))
            for sec, chs in (jam.get("sections") or {}).items():
                st.markdown(f"**{sec}**")
                render_creative_progression_block(st, session_state, {sec: chs})
            _render_open_practice_backing_row(
                st,
                on_open_backing=on_open_backing,
                on_open_practice=on_open_practice,
                workflow="jam",
            )


def _render_open_practice_backing_row(
    st: Any,
    *,
    on_open_backing: Callable[[], None] | None,
    on_open_practice: Callable[[], None] | None,
    workflow: str = "song",
) -> None:
    """Song/custom workflows offer Practice; Style Jam / Jam Session focus on Backing Studio."""
    st.markdown("---")
    if workflow == "jam":
        if on_open_backing:
            st.button(
                "🎧 Open in Backing Studio",
                key="improv_to_backing_jam",
                type="primary",
                use_container_width=True,
                on_click=on_open_backing,
            )
        return

    c1, c2 = st.columns([2, 1])
    with c1:
        if on_open_backing:
            st.button(
                "🎧 Open in Backing Studio",
                key="improv_to_backing",
                type="primary",
                use_container_width=True,
                on_click=on_open_backing,
            )
    with c2:
        if on_open_practice:
            st.button(
                "🎯 Send to Practice Page",
                key="improv_to_practice",
                use_container_width=True,
                on_click=on_open_practice,
            )


def _tab_live_coach(st: Any, *, session_state: dict, improv_ctx: ImprovSessionContext) -> None:
    try:
        from song_creative_focus import hydrate_creative_pages_from_song_focus

        hydrate_creative_pages_from_song_focus(session_state, tab="Live Coach")
    except ImportError:
        pass
    st.markdown(creative_tool_heading_markdown("Live Coach"))
    from practice_setup_controls import (
        DEFAULT_INSTRUMENT_OPTIONS,
        render_setup_quick_controls,
    )

    live_inst, live_level, live_focus = render_setup_quick_controls(
        st,
        session_state=session_state,
        key_prefix="improv_live_coach",
        instrument_options=DEFAULT_INSTRUMENT_OPTIONS,
        label="Instrument · level · focus",
        show_sync_caption=False,
    )
    summary = level_coaching_summary(live_level)
    st.caption(
        f"**{live_level}** · focus **{live_focus}** — {summary['focus']} · {summary['harmony']}"
    )
    try:
        from instrument_transposition import is_transposing_instrument

        if is_transposing_instrument(live_inst):
            st.caption(
                f"Chord tones and scales follow your chart in **{improv_ctx.display_key}** "
                f"(written key for {live_inst})."
            )
    except ImportError:
        pass

    section_map = resolve_improv_sections(session_state, improv_ctx)
    chords = flatten_section_map(section_map)
    if not chords:
        st.warning(
            "No chords in the active chart — pick a song on **Song Selection**, "
            "open **Custom progression**, or generate a style jam in **Entry & Jam**."
        )
        return

    _ensure_chord_selection(session_state, chords, section_map)
    cur, idx = _selected_chord(session_state, chords, section_map)
    concert_key, chart_key = _coherent_improv_key_pair(session_state, improv_ctx)
    parent_key = chart_key or _parent_practice_key_label(improv_ctx)
    shown_cur = _player_facing_chord(session_state, cur, concert_key=concert_key)
    bound_ctx = replace(improv_ctx, key_center=concert_key, display_key=chart_key)
    analysis_ref = _motif_notation_reference_key(bound_ctx, shown_cur or cur)
    _render_section_chord_map(
        st,
        section_map,
        session_state,
        key_prefix="improv_live",
        source_id=_improv_source_id(session_state, improv_ctx),
        key_center=concert_key,
    )

    nxt = chords[idx + 1] if idx + 1 < len(chords) else ""
    shown_nxt = _player_facing_chord(session_state, nxt, concert_key=concert_key)
    insight = chord_coach_insight(
        shown_cur or cur,
        key_center=parent_key,
        next_chord=shown_nxt,
        instrument=live_inst,
        level=live_level,
    )
    _render_chord_coach_card(st, insight, reference_key=analysis_ref)

    st.markdown("##### Instrument-adaptive coaching")
    for line in insight.instrument_tips:
        st.markdown(f"- {line}")

    if session_state.get("_last_backing_timeline"):
        st.caption("Tip: play your backing track and tap each chord as it passes.")


def _render_chord_coach_card(
    st: Any, insight: ChordCoachInsight, *, reference_key: str = "C"
) -> None:
    st.markdown(
        f'<div class="ui-card soft" style="border-left:4px solid #22c55e;">'
        f'<p class="ui-card-title">Current chord: {html.escape(insight.chord)}</p></div>',
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Suggested scales**")
        suggestions = insight.scale_suggestions or [
            build_scale_suggestion(label, reference_key=reference_key)
            for label in insight.scales
        ]
        for suggestion in suggestions:
            st.markdown(format_scale_line(suggestion, insight.chord_tones))
        st.markdown("**Chord tones**")
        st.markdown("`" + " · ".join(insight.chord_tones) + "`")
    with c2:
        st.markdown("**Tensions / extensions**")
        for t in insight.tensions:
            st.markdown(f"- {t}")
        st.markdown("**Avoid**")
        for a in insight.avoid_notes:
            st.markdown(f"- {a}")
    st.markdown("**Target notes:** " + ", ".join(insight.target_notes))
    st.info(insight.motif_idea)
    if insight.resolve_hint:
        st.success(insight.resolve_hint)


def _tab_motif(
    st: Any,
    *,
    session_state: dict,
    improv_ctx: ImprovSessionContext,
    level: str,
    instrument: str,
    bpm: int,
) -> None:
    try:
        from song_creative_focus import hydrate_creative_pages_from_song_focus

        hydrate_creative_pages_from_song_focus(session_state, tab="Phrase / Motif")
    except ImportError:
        pass
    st.markdown(creative_tool_heading_markdown("Phrase / Motif"))
    st.caption("Tap a chord → get a short phrase → transform it → view notation or TAB.")

    try:
        from creative_mission_artifact_persistence import project_mission_artifacts_from_canonical
        from creative_tab_tool_persistence import selector_hydration_complete
        from music_route_gates import guard_creative_tab_heavy

        if selector_hydration_complete(session_state) and guard_creative_tab_heavy(
            session_state, "Phrase / Motif", "artifact_projection"
        ):
            from creative_mission_artifact_persistence import should_skip_mission_artifact_projection

            if not should_skip_mission_artifact_projection(session_state):
                project_mission_artifacts_from_canonical(session_state, overwrite=False)
    except ImportError:
        pass

    section_map = resolve_improv_sections(session_state, improv_ctx)
    chords = flatten_section_map(section_map)
    if not chords:
        st.warning("No chords available — select a song or custom progression first.")
        return

    _ensure_chord_selection(session_state, chords, section_map)
    _render_section_chord_map(
        st,
        section_map,
        session_state,
        key_prefix="improv_motif",
        source_id=_improv_source_id(session_state, improv_ctx),
        key_center=improv_ctx.key_center,
        generate_motif_on_select=True,
    )

    cur, _idx = _selected_chord(session_state, chords, section_map)
    concert_key, _chart_key = _coherent_improv_key_pair(session_state, improv_ctx)
    shown_cur = _player_facing_chord(session_state, cur, concert_key=concert_key)
    motif_key = _motif_notation_reference_key(improv_ctx, cur)

    g0, g1, g2, g3 = st.columns(4)
    with g0:
        if st.button(
            f"Generate motif for {shown_cur or cur}",
            type="primary",
            key="improv_gen_motif_chord",
            use_container_width=True,
        ):
            session_state["improv_motif"] = generate_musical_phrase(
                cur, key_center=motif_key, level=level, kind="creative"
            )
            _clear_motif_outputs(session_state)
            _persist_motif_artifact(session_state, interaction="motif_generate_chord")
            st.rerun()
    with g1:
        if st.button("New motif", key="improv_motif_new", use_container_width=True):
            session_state["improv_motif"] = generate_musical_phrase(
                cur,
                key_center=motif_key,
                level=level,
                kind="creative",
                variant="new",
                session_state=session_state,
            )
            _clear_motif_outputs(session_state)
            _persist_motif_artifact(session_state, interaction="motif_new")
            st.rerun()
    with g2:
        if st.button("Harder motif", key="improv_motif_harder", use_container_width=True):
            session_state["improv_motif"] = generate_musical_phrase(
                cur,
                key_center=motif_key,
                level=level,
                kind="creative",
                variant="harder",
            )
            _clear_motif_outputs(session_state)
            _persist_motif_artifact(session_state, interaction="motif_harder")
            st.rerun()
    with g3:
        if st.button("Easier motif", key="improv_motif_easier", use_container_width=True):
            session_state["improv_motif"] = generate_musical_phrase(
                cur,
                key_center=motif_key,
                level=level,
                kind="creative",
                variant="easier",
            )
            _clear_motif_outputs(session_state)
            _persist_motif_artifact(session_state, interaction="motif_easier")
            st.rerun()

    motif = session_state.get("improv_motif")
    if not motif:
        st.info(f"Click **Generate motif for {cur}** or tap another chord tile.")
        return

    st.markdown(
        f'<div class="ui-card soft" style="border-left:4px solid #a855f7;">'
        f'<p class="ui-card-title">Motif on {html.escape(str(motif.get("chord", cur)))}</p>'
        f'<p style="font-size:1.35rem;font-weight:700;margin:0.25rem 0;">'
        f'{html.escape(motif.get("display", ""))}</p>'
        f'<p class="ui-card-sub">Rhythm: {html.escape(motif.get("rhythm", ""))}</p></div>',
        unsafe_allow_html=True,
    )

    st.markdown("**Transform**")
    t1, t2, t3, t4 = st.columns(4)
    transforms = [
        (t1, "sequence_up", "Sequence Up ↑", "improv_xform_up"),
        (t2, "sequence_down", "Sequence Down ↓", "improv_xform_down"),
        (t3, "invert", "Invert ↓↑", "improv_xform_invert"),
        (t4, "rhythmic", "Rhythmic Variation", "improv_xform_rhythm"),
    ]
    for col, op, label, key in transforms:
        with col:
            if st.button(label, key=key, use_container_width=True):
                session_state["improv_motif"] = transform_motif(
                    motif,
                    op,
                    key_center=motif_key,
                )
                _refresh_motif_output_after_transform(
                    session_state,
                    key_center=_motif_notation_reference_key(improv_ctx, cur),
                    bpm=bpm,
                )
                _persist_motif_artifact(session_state, interaction=f"motif_transform_{op}")
                st.rerun()

    st.markdown("---")
    n1, n2 = st.columns(2)
    with n1:
        if st.button(
            "Generate Sheet Music",
            key="improv_motif_sheet",
            type="primary",
            use_container_width=True,
        ):
            session_state["improv_motif_output_mode"] = MOTIF_OUTPUT_NOTATION
            session_state["improv_motif_abc"] = build_motif_notation_abc(
                session_state["improv_motif"],
                key_center=_motif_notation_reference_key(improv_ctx),
                bpm=bpm,
            )
            session_state.pop("improv_motif_tab", None)
            _persist_motif_artifact(session_state, interaction="motif_notation_output")
            st.rerun()
    with n2:
        if instrument == "Guitar" and st.button(
            "Generate Guitar TAB",
            key="improv_motif_tab_btn",
            use_container_width=True,
        ):
            session_state["improv_motif_output_mode"] = MOTIF_OUTPUT_TAB
            session_state["improv_motif_tab"] = build_motif_guitar_tab(
                session_state["improv_motif"]
            )
            session_state.pop("improv_motif_abc", None)
            _persist_motif_artifact(session_state, interaction="motif_tab_output")
            st.rerun()

    if session_state.get("improv_motif_output_mode") == MOTIF_OUTPUT_NOTATION:
        if session_state.get("improv_motif_abc"):
            st.markdown("**Sheet music**")
            _render_abc(st, session_state["improv_motif_abc"])
            with st.expander("ABC source", expanded=False):
                st.code(session_state["improv_motif_abc"], language=None)

    if session_state.get("improv_motif_output_mode") == MOTIF_OUTPUT_TAB:
        if session_state.get("improv_motif_tab"):
            st.markdown("**Guitar TAB**")
            st.code(session_state["improv_motif_tab"], language=None)

    if level == "Beginner":
        st.caption("Beginner: play the motif 4×, then try one transformation.")
    elif level == "Advanced":
        st.caption("Advanced: chain transforms, then regenerate notation to check the new shape.")


def _safe_widget_key_part(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(text).strip())
    return (slug[:48] or "x").strip("_")


def _improv_source_id(session_state: dict, improv_ctx: ImprovSessionContext) -> str:
    if str(session_state.get("improv_song_source") or "") == "Custom progression":
        return "custom"
    return _safe_widget_key_part(improv_ctx.song_title or "song")


def _migrate_ii_chord_selection(session_state: dict) -> None:
    """Move legacy selection keys; drop stale chord-tile button widget keys."""
    if II_SELECTED_CHORD_INDEX not in session_state:
        if "improv_chord_idx" in session_state or "improv_selected_chord" in session_state:
            session_state[II_SELECTED_CHORD_INDEX] = int(
                session_state.get("improv_chord_idx", 0)
            )
            legacy_ch = str(session_state.get("improv_selected_chord") or "")
            session_state[II_SELECTED_CHORD] = legacy_ch
            session_state[II_SELECTED_CHORD_LABEL] = legacy_ch
        session_state.pop("improv_chord_idx", None)
        session_state.pop("improv_selected_chord", None)
    for key in list(session_state.keys()):
        if _LEGACY_CHORD_TILE_KEY.match(key):
            session_state.pop(key, None)


def _ensure_chord_selection(
    session_state: dict,
    chords: list[str],
    section_map: list[tuple[str, list[str]]] | None = None,
) -> None:
    """Keep one canonical chord — (section, symbol) wins; index must match that pair on section_map."""
    _migrate_ii_chord_selection(session_state)
    if not chords:
        return
    try:
        from music_workflow_pending_song_practice_key_edit import pending_selected_practice_key_token

        if pending_selected_practice_key_token(session_state):
            return
    except ImportError:
        pass

    try:
        from creative_chord_selection_authority import (
            authoritative_pair_matches_index,
            global_chord_index_for_section_chord,
            resolve_authoritative_chord_selection,
            write_authoritative_chord_selection,
        )
    except ImportError:
        authoritative_pair_matches_index = None  # type: ignore[assignment,misc]
        global_chord_index_for_section_chord = None  # type: ignore[assignment,misc]
        resolve_authoritative_chord_selection = None  # type: ignore[assignment,misc]
        write_authoritative_chord_selection = None  # type: ignore[assignment,misc]

    sym = str(session_state.get(II_SELECTED_CHORD) or "").strip()
    sec = str(session_state.get(II_SELECTED_SECTION) or "").strip()
    try:
        idx = int(session_state.get(II_SELECTED_CHORD_INDEX, -1))
    except (TypeError, ValueError):
        idx = -1

    if (
        section_map
        and sym
        and sec
        and resolve_authoritative_chord_selection is not None
        and write_authoritative_chord_selection is not None
    ):
        rsym, rsec, ridx = resolve_authoritative_chord_selection(session_state, section_map)
        if rsym and rsec:
            write_authoritative_chord_selection(
                session_state,
                section_map,
                chord_symbol=rsym,
                section_label=rsec,
                chord_index=ridx,
            )
            session_state.pop("harmony_map_section_selections", None)
            session_state["improv_mission_chord_options"] = list(chords)
            return

    try:
        from song_creative_focus import read_song_creative_focus, resolve_focus_against_progression

        focus = read_song_creative_focus(session_state)
        if focus and section_map:
            resolved = resolve_focus_against_progression(session_state, focus)
            target = str(resolved.get("selected_concert_chord") or "").strip()
            fsec = str(resolved.get("selected_section_id") or "").strip()
            if target and fsec and global_chord_index_for_section_chord:
                gidx = global_chord_index_for_section_chord(section_map, fsec, target)
                if gidx is not None and write_authoritative_chord_selection:
                    write_authoritative_chord_selection(
                        session_state,
                        section_map,
                        chord_symbol=target,
                        section_label=fsec,
                        chord_index=gidx,
                    )
                    session_state.pop("harmony_map_section_selections", None)
                    session_state["improv_mission_chord_options"] = list(chords)
                    return
            if target and target in chords:
                idx = int(resolved.get("selected_chord_id") or 0)
                if idx < 0 or idx >= len(chords) or chords[idx] != target:
                    idx = -1
                if idx < 0:
                    pass
                elif authoritative_pair_matches_index and not authoritative_pair_matches_index(
                    section_map,
                    section_label=fsec,
                    chord_symbol=target,
                    chord_index=idx,
                ):
                    pass
                else:
                    session_state[II_SELECTED_CHORD_INDEX] = idx
                    session_state[II_SELECTED_CHORD] = chords[idx]
                    sec_at, _ = section_and_chord_at_global_index(section_map, idx)
                    if sec_at:
                        session_state[II_SELECTED_SECTION] = sec_at
                        session_state[II_SELECTED_CHORD_LABEL] = f"{sec_at} · {chords[idx]}"
                    session_state["harmony_map_chord"] = chords[idx]
                    session_state["harmony_map_section"] = sec_at or fsec
                    session_state.pop("harmony_map_section_selections", None)
                    session_state["improv_mission_chord_options"] = list(chords)
                    return
    except ImportError:
        pass
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session_state)
        if ptr and ptr.workflow_owner == "mission_jam":
            blob = get_workflow_blob(session_state, ptr.workflow_owner, ptr.workflow_session_id)
            if blob and blob.selected_chord_symbol:
                sym = str(blob.selected_chord_symbol).strip()
                bsec = str(blob.selected_section or "").strip()
                if sym and section_map and bsec and write_authoritative_chord_selection:
                    write_authoritative_chord_selection(
                        session_state,
                        section_map,
                        chord_symbol=sym,
                        section_label=bsec,
                        chord_index=int(blob.selected_chord_index or 0),
                    )
                    session_state["improv_mission_chord_options"] = list(chords)
                    return
                if sym in chords and section_map and bsec and global_chord_index_for_section_chord:
                    gidx = global_chord_index_for_section_chord(section_map, bsec, sym)
                    if gidx is not None and write_authoritative_chord_selection:
                        write_authoritative_chord_selection(
                            session_state, section_map, chord_symbol=sym, section_label=bsec, chord_index=gidx
                        )
                        session_state["improv_mission_chord_options"] = list(chords)
                        return
    except ImportError:
        pass
    try:
        from music_workflow_mutation import should_project_mission_config_from_canonical

        if not should_project_mission_config_from_canonical(session_state):
            if section_map and resolve_authoritative_chord_selection:
                sym, sec, idx = resolve_authoritative_chord_selection(session_state, section_map)
                if sym and write_authoritative_chord_selection:
                    write_authoritative_chord_selection(
                        session_state, section_map, chord_symbol=sym, section_label=sec, chord_index=idx
                    )
            return
    except ImportError:
        pass
    try:
        from creative_mission_config_persistence import canonical_mission_config_value

        raw = canonical_mission_config_value(session_state, II_SELECTED_CHORD_INDEX)
        if raw is not None:
            idx = int(raw)
        else:
            idx = int(session_state.get(II_SELECTED_CHORD_INDEX, 0))
    except ImportError:
        idx = int(session_state.get(II_SELECTED_CHORD_INDEX, 0))
    if idx < 0 or idx >= len(chords):
        idx = 0
        session_state[II_SELECTED_CHORD_INDEX] = 0
    chord = chords[idx]
    if section_map:
        sec, _ = section_and_chord_at_global_index(section_map, idx)
        if sec and write_authoritative_chord_selection:
            write_authoritative_chord_selection(
                session_state, section_map, chord_symbol=chord, section_label=sec, chord_index=idx
            )
        elif sec:
            session_state[II_SELECTED_SECTION] = sec
            session_state[II_SELECTED_CHORD_LABEL] = f"{sec} · {chord}"
            session_state[II_SELECTED_CHORD] = chord
        else:
            session_state.setdefault(II_SELECTED_SECTION, "")
            session_state[II_SELECTED_CHORD_LABEL] = chord
            session_state[II_SELECTED_CHORD] = chord
    else:
        session_state.setdefault(II_SELECTED_SECTION, "")
        if not str(session_state.get(II_SELECTED_CHORD_LABEL) or "").strip():
            session_state[II_SELECTED_CHORD_LABEL] = chord
        session_state[II_SELECTED_CHORD] = chord
    session_state["improv_mission_chord_options"] = list(chords)


def _selected_chord(session_state: dict, chords: list[str], section_map: list[tuple[str, list[str]]] | None = None) -> tuple[str, int]:
    if section_map:
        try:
            from creative_chord_selection_authority import resolve_authoritative_chord_selection

            sym, sec, idx = resolve_authoritative_chord_selection(session_state, section_map)
            if sym:
                return sym, idx
        except ImportError:
            pass
    sym = str(session_state.get(II_SELECTED_CHORD) or "").strip()
    try:
        idx = int(session_state.get(II_SELECTED_CHORD_INDEX, 0))
    except (TypeError, ValueError):
        idx = 0
    if sym and chords and 0 <= idx < len(chords) and chords[idx] == sym:
        return sym, idx
    idx = max(0, min(idx, len(chords) - 1)) if chords else 0
    return chords[idx], idx if chords else 0


def _clear_motif_outputs(session_state: dict) -> None:
    session_state["improv_motif_output_mode"] = MOTIF_OUTPUT_NONE
    session_state.pop("improv_motif_abc", None)
    session_state.pop("improv_motif_tab", None)
    _touch_creative_workspace(session_state)


def _persist_motif_artifact(session_state: dict, *, interaction: str) -> None:
    try:
        from creative_mission_artifact_persistence import handle_user_motif_artifact_change

        handle_user_motif_artifact_change(session_state, interaction=interaction)
    except ImportError:
        _touch_creative_workspace(session_state)


def _refresh_motif_output_after_transform(
    session_state: dict,
    *,
    key_center: str,
    bpm: int,
) -> None:
    mode = session_state.get("improv_motif_output_mode", MOTIF_OUTPUT_NONE)
    motif = session_state.get("improv_motif")
    if not motif or mode == MOTIF_OUTPUT_NONE:
        return
    if mode == MOTIF_OUTPUT_NOTATION:
        session_state["improv_motif_abc"] = build_motif_notation_abc(
            motif, key_center=key_center, bpm=bpm
        )
    elif mode == MOTIF_OUTPUT_TAB:
        session_state["improv_motif_tab"] = build_motif_guitar_tab(motif)


def _apply_harmony_map_chord_selection(
    session_state: dict,
    *,
    chord: str,
    section: str,
    chord_index: int,
    button_key: str = "",
) -> None:
    """Harmony Map chord pick — same canonical path as Live Coach / Motif / Missions tiles."""
    sec = str(section or "").strip()
    ch = str(chord or "").strip()
    if not sec or not ch:
        return
    gidx = int(chord_index)
    label = f"{sec} · {ch}"
    btn = str(button_key or f"harmony_map_{gidx}_{ch}")
    try:
        from active_musical_workflow_envelope import apply_atomic_mission_chord_selection

        apply_atomic_mission_chord_selection(
            session_state,
            chord=ch,
            section=sec,
            chord_index=gidx,
            chord_label=label,
            button_key=btn,
        )
    except ImportError:
        try:
            from creative_mission_config_persistence import handle_user_mission_target_selection

            handle_user_mission_target_selection(
                session_state,
                chord=ch,
                section=sec,
                chord_index=gidx,
                chord_label=label,
                button_key=btn,
            )
        except ImportError:
            session_state[II_SELECTED_CHORD] = ch
            session_state[II_SELECTED_SECTION] = sec
            session_state[II_SELECTED_CHORD_INDEX] = gidx
            session_state[II_SELECTED_CHORD_LABEL] = label
    session_state["harmony_map_section"] = sec
    session_state["harmony_map_chord"] = ch
    try:
        from creative_context_snapshot_persistence import handle_user_harmony_map_context_change

        handle_user_harmony_map_context_change(session_state, section=sec, chord=ch)
    except ImportError:
        _touch_creative_workspace(session_state)


def _harmony_map_chord_on_click(ch: str, sec_label: str, gidx: int, button_key: str) -> None:
    import streamlit as st

    _apply_harmony_map_chord_selection(
        st.session_state,
        chord=ch,
        section=sec_label,
        chord_index=int(gidx),
        button_key=button_key,
    )


def _render_section_chord_map(
    st: Any,
    section_map: list[tuple[str, list[str]]],
    session_state: dict,
    *,
    key_prefix: str,
    source_id: str,
    key_center: str = "C",
    generate_motif_on_select: bool = False,
) -> None:
    st.markdown("**Chord map by section**")
    _migrate_ii_chord_selection(session_state)
    try:
        from creative_chord_selection_authority import resolve_authoritative_chord_selection

        sel_chord, sel_section, _sel_idx = resolve_authoritative_chord_selection(session_state, section_map)
    except ImportError:
        sel_chord = str(session_state.get(II_SELECTED_CHORD) or "")
        sel_section = str(session_state.get(II_SELECTED_SECTION) or "")
    src = _safe_widget_key_part(source_id)

    def _chord_tile_on_click(ch: str, label: str, gidx: int, btn_key: str) -> None:
        import streamlit as st

        ss = st.session_state
        try:
            from active_musical_workflow_envelope import apply_atomic_mission_chord_selection

            apply_atomic_mission_chord_selection(
                ss,
                chord=ch,
                section=label,
                chord_index=gidx,
                chord_label=f"{label} · {ch}",
                button_key=btn_key,
            )
        except ImportError:
            try:
                from creative_mission_config_persistence import handle_user_mission_target_selection

                handle_user_mission_target_selection(
                    ss,
                    chord=ch,
                    section=label,
                    chord_index=gidx,
                    chord_label=f"{label} · {ch}",
                    button_key=btn_key,
                )
            except ImportError:
                pass
        if generate_motif_on_select:
            ss["improv_motif"] = generate_musical_phrase(ch, key_center=key_center, kind="creative")
            _clear_motif_outputs(ss)
            _persist_motif_artifact(ss, interaction="motif_chord_tile_select")

    for sec_i, (label, chords) in enumerate(section_map):
        st.markdown(f"**{html.escape(label)}**")
        section_slug = _safe_widget_key_part(label)
        cols_per_row = 8
        for row_start in range(0, len(chords), cols_per_row):
            row = chords[row_start : row_start + cols_per_row]
            cols = st.columns(len(row))
            for ci, ch in enumerate(row):
                gidx = global_chord_index(section_map, sec_i, row_start + ci)
                safe_ch = _safe_widget_key_part(ch)
                button_key = (
                    f"ii_chord_tile_{src}_{key_prefix}_{section_slug}_{gidx}_{safe_ch}"
                )
                with cols[ci]:
                    is_sel = sel_section == label and sel_chord == ch
                    try:
                        from effective_practice_context import musician_facing_chart_key, musician_facing_chord

                        chart_key = musician_facing_chart_key(session_state, key_center)
                        tile_label = musician_facing_chord(
                            ch,
                            concert_key=key_center,
                            chart_key=chart_key,
                        )
                    except ImportError:
                        tile_label = ch
                    st.button(
                        tile_label,
                        key=button_key,
                        type="primary" if is_sel else "secondary",
                        use_container_width=True,
                        on_click=_chord_tile_on_click,
                        args=(ch, label, gidx, button_key),
                    )
    cap = (
        "One progression per section — repeated verses/choruses and multi-bar holds "
        "are collapsed. Tap a chord to select."
    )
    if generate_motif_on_select:
        cap += " Motif updates when you tap a chord."
    st.caption(cap)
    try:
        from creative_mission_config_persistence import mark_mission_widgets_instantiated

        mark_mission_widgets_instantiated(session_state)
    except ImportError:
        pass


def _render_motif_sheet_music(st: Any, abc_text: str, *, height: int = 360) -> None:
    """Staff notation first; ABC source in a collapsed expander below (no overlap)."""
    with st.container():
        _render_abc(st, abc_text, height=height)
    with st.expander("ABC source (optional)", expanded=False):
        st.code(abc_text, language=None)


def _render_abc(st: Any, abc_text: str, *, height: int = 360) -> None:
    escaped = (
        abc_text.replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("${", "\\${")
    )
    doc = f"""
    <html>
    <head>
    <style>
      body {{ margin: 0; padding: 8px 4px 16px 4px; overflow: visible; }}
      #paper {{ min-height: 200px; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/abcjs@6.4.4/dist/abcjs-basic-min.js"></script>
    </head>
    <body>
    <div id="paper"></div>
    <script>
    ABCJS.renderAbc("paper", `{escaped}`, {{ responsive: "resize", staffwidth: 520, paddingbottom: 12 }});
    </script>
    </body>
    </html>
    """
    components.html(doc, height=height, scrolling=True)


def _mission_example_type_label(variant: str) -> str:
    labels = {
        "normal": "Normal",
        "harder": "Harder",
        "easier": "Easier",
        "new": "New idea",
    }
    key = str(variant or "normal").strip().lower()
    return labels.get(key, key.title() or "Normal")


def render_mission_practice_lick_on_backing(
    st: Any,
    session_state: dict,
    *,
    applied_bpm: int,
    on_return_to_mission: Callable[[], None] | None = None,
) -> None:
    """Mission lick panel on Backing Jam — notation/TAB rebuilt from stored motif at current BPM."""
    try:
        from backing_session_route import mission_backing_ui_allowed

        if not mission_backing_ui_allowed(session_state):
            return
    except ImportError:
        try:
            from backing_context import get_backing_context

            ctx = get_backing_context(session_state)
            if ctx is None or str(ctx.source or "") != "mission":
                return
        except ImportError:
            pass
    payload = mission_practice_lick_payload(session_state)
    if not payload:
        return
    inst = str(payload.get("instrument") or "Piano")
    chord = str(payload.get("chord") or "")
    key_center = str(payload.get("key_center") or "C")
    song = str(payload.get("song_title") or "")
    section = str(payload.get("section_label") or "")
    level = str(payload.get("level") or "")
    example_type = _mission_example_type_label(str(payload.get("example_variant") or "normal"))
    motif = dict(payload.get("motif") or {})
    out = rebuild_mission_outputs(
        motif,
        chord=chord,
        instrument=inst,
        key_center=key_center,
        bpm=int(applied_bpm),
    )
    family = instrument_family(inst)
    st.markdown("---")
    head_l, head_r = st.columns([3, 1])
    with head_l:
        st.markdown(f"#### {CREATIVE_TOOL_ICONS['Missions']} Mission Practice")
        st.caption("You are still in your mission — loop the backing and work this lick at any tempo.")
    with head_r:
        if on_return_to_mission and st.button(
            "← Return to Mission",
            key="mission_practice_return_to_mission",
            type="primary",
            use_container_width=True,
        ):
            on_return_to_mission()
    st.markdown(
        f'<div class="ui-card soft" style="border-left:4px solid #8b5cf6;">'
        f'<p class="ui-card-sub">'
        f"<strong>Song</strong> {html.escape(song)} · "
        f"<strong>Section</strong> {html.escape(section)} · "
        f"<strong>Chord</strong> {html.escape(chord)} · "
        f"<strong>Instrument</strong> {html.escape(inst)} · "
        f"<strong>Difficulty</strong> {html.escape(level)} · "
        f"<strong>Example</strong> {html.escape(example_type)} · "
        f"Groove {html.escape(str(payload.get('groove') or 'Auto'))} · "
        f"Meter {html.escape(str(payload.get('meter') or '4/4'))}"
        f"</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"**Notes:** `{out['motif'].get('display', '')}` · "
        f"**Rhythm:** `{out['motif'].get('rhythm', '')}`"
    )
    if out.get("abc"):
        st.markdown("**Sheet music** (updates when you change tempo)")
        n_notes = len(out["motif"].get("notes") or [])
        staff_h = min(720, max(360, 280 + n_notes * 14))
        _render_motif_sheet_music(st, out["abc"], height=staff_h)
    if family == "guitar" and out.get("tab"):
        st.markdown("**Guitar TAB**")
        st.code(out["tab"], language=None)
    if family == "wind":
        st.markdown("**Phrasing**")
        for line in wind_phrasing_lines(inst, out["motif"]):
            st.markdown(f"- {line}")


def _on_mission_pick_change() -> None:
    import streamlit as st

    try:
        from creative_mission_config_persistence import handle_user_mission_pick_change

        handle_user_mission_pick_change(st.session_state)
    except ImportError:
        pick = str(st.session_state.get("improv_mission_pick") or "").strip()
        if pick:
            st.session_state["improv_active_mission"] = pick


def _chords_identity_equal(left: str, right: str) -> bool:
    """True when two chord labels are the same musical identity (ignore display spelling noise)."""
    a = str(left or "").strip()
    b = str(right or "").strip()
    if not a or not b:
        return False
    if a == b:
        return True
    try:
        from music_theory import normalize_chord_for_theory, normalize_root, split_chord

        na = normalize_chord_for_theory(a)
        nb = normalize_chord_for_theory(b)
        if na and nb and na == nb:
            return True
        ra, qa = split_chord(na or a)
        rb, qb = split_chord(nb or b)
        return bool(ra and rb and normalize_root(ra) == normalize_root(rb) and str(qa) == str(qb))
    except Exception:
        return False


def _example_matches_active_context(
    example: MissionExample,
    *,
    mission: str,
    cur_chord: str,
    section_label: str,
    song_title: str = "",
) -> bool:
    if str(example.mission or "").strip() != str(mission or "").strip():
        return False
    if song_title and str(example.song_title or "").strip() not in ("", song_title):
        return False
    # Chord identity must match across enharmonic spellings and concert vs Shape projection
    # of the same selection (e.g. stored concert Dm vs UI Em under Guitar Shape).
    cur = str(cur_chord or "").strip()
    candidates: list[str] = [str(example.chord or "").strip()]
    motif = example.motif if isinstance(example.motif, dict) else {}
    concert_stored = str(motif.get("_concert_chord") or "").strip()
    if concert_stored:
        candidates.append(concert_stored)
    chord_ok = any(_chords_identity_equal(c, cur) for c in candidates if c)
    if not chord_ok:
        ck = str(example.concert_key or "").strip()
        dk = str(example.display_key or "").strip()
        if ck and dk and ck != dk:
            try:
                from effective_practice_context import musician_facing_chord

                base = concert_stored or candidates[0]
                if base:
                    facing = musician_facing_chord(base, concert_key=ck, chart_key=dk)
                    chord_ok = _chords_identity_equal(facing, cur) or _chords_identity_equal(base, cur)
            except ImportError:
                chord_ok = False
    if not chord_ok:
        return False
    ex_sec = str(example.section or "").strip()
    cur_sec = str(section_label or "").strip()
    if ex_sec and cur_sec and ex_sec != cur_sec:
        return False
    return True


def _canonical_mission_example_fingerprint(session_state: dict) -> str:
    try:
        from creative_mission_artifact_persistence import canonical_mission_artifact_value
        from improvisation_missions import mission_example_fingerprint

        raw = canonical_mission_artifact_value(session_state, MISSION_EXAMPLE_KEY)
        if not isinstance(raw, dict):
            return ""
        ctx = ImprovSessionContext(
            song_title=str(session_state.get("song") or "Song"),
            artist=str(session_state.get("artist") or ""),
            key_center=str(session_state.get("concert_key") or session_state.get("display_key") or "C"),
            display_key=str(session_state.get("display_key") or "C"),
            instrument=str(session_state.get("instrument") or "Guitar"),
            level=str(session_state.get("level") or "Intermediate"),
            focus=str(session_state.get("focus") or "Improvisation"),
            sections={},
        )
        loaded = load_mission_example(session_state | {MISSION_EXAMPLE_KEY: raw}, ctx)
        return mission_example_fingerprint(loaded) if loaded else ""
    except Exception:
        return ""


def _record_mission_example_gen_diag(
    session_state: dict,
    *,
    variant: str,
    prior: MissionExample | None,
    example: MissionExample,
    prev_fp: str,
    prev_mat: str,
    gen_fp: str,
    retries: int,
    retried: bool,
) -> None:
    gen_mat = motif_material_fingerprint(example.motif)
    stored_raw = session_state.get(MISSION_EXAMPLE_KEY)
    stored_mat = ""
    if isinstance(stored_raw, dict):
        stored_mat = str(stored_raw.get("material_fp") or "")
    canon_fp = _canonical_mission_example_fingerprint(session_state)
    diag = {
        "callback": f"mission_example_generate_{variant}",
        "callback_fired": True,
        "variant": variant,
        "previous_fp": prev_fp,
        "generated_fp": gen_fp,
        "stored_artifact_fp": gen_fp,
        "canonical_artifact_fp": canon_fp,
        "previous_material_fp": prev_mat,
        "generated_material_fp": gen_mat,
        "stored_material_fp": stored_mat or gen_mat,
        "loaded_fp": gen_fp,
        "displayed_fp": gen_fp,
        "displayed_material_fp": gen_mat,
        "retried": retried,
        "retry_count": retries,
        "artifact_overwritten": False,
    }
    session_state[MISSION_EXAMPLE_GEN_DIAG_KEY] = diag
    session_state[MISSION_NEW_IDEA_DIAG_KEY] = dict(diag)


def _normalize_section_map_for_generate(raw: Any) -> list[tuple[str, list[str]]]:
    if isinstance(raw, dict):
        return [(str(k), list(v)) for k, v in raw.items() if isinstance(v, list)]
    if not isinstance(raw, list):
        return []
    out: list[tuple[str, list[str]]] = []
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) >= 2 and isinstance(item[1], list):
            out.append((str(item[0]), list(item[1])))
    return out


def _sync_missions_session_from_improv_ctx(
    session_state: dict,
    improv_ctx: ImprovSessionContext,
    *,
    section_map: dict[str, list[str]] | None,
) -> None:
    session_state.setdefault("song", improv_ctx.song_title)
    session_state.setdefault("artist", improv_ctx.artist)
    session_state.setdefault("display_key", improv_ctx.display_key)
    session_state.setdefault("concert_key", improv_ctx.key_center)
    session_state.setdefault("instrument", improv_ctx.instrument)
    session_state.setdefault("level", improv_ctx.level)
    session_state.setdefault("focus", improv_ctx.focus)
    # home_sections must stay catalog-original pitch. Concert/practice section maps
    # must never be written back here — that caused Bm→Dm overlay to run twice (Fm).
    if not session_state.get("home_sections"):
        if section_map and isinstance(section_map, list):
            session_state.setdefault(
                "home_sections",
                {str(label): list(chs) for label, chs in section_map if isinstance(chs, list)},
            )
        elif section_map and isinstance(section_map, dict):
            session_state.setdefault(
                "home_sections",
                {k: list(v) for k, v in section_map.items()},
            )
        elif improv_ctx.sections and isinstance(improv_ctx.sections, dict):
            session_state.setdefault(
                "home_sections",
                {k: list(v) for k, v in improv_ctx.sections.items()},
            )


def _stash_missions_generate_context(
    session_state: dict,
    *,
    improv_ctx: ImprovSessionContext,
    section_map: list[tuple[str, list[str]]],
    mission: str,
    cur_chord: str,
    section_label: str,
    chord_idx: int,
    live_inst: str,
    live_level: str,
    live_focus: str,
    bpm: int,
) -> None:
    session_state[MISSIONS_GENERATE_CONTEXT_KEY] = {
        "mission": mission,
        "cur_chord": cur_chord,
        "section_label": section_label,
        "chord_idx": int(chord_idx),
        "live_inst": live_inst,
        "live_level": live_level,
        "live_focus": live_focus,
        "bpm": int(bpm),
        "improv_ctx": {
            "song_title": improv_ctx.song_title,
            "artist": improv_ctx.artist,
            "key_center": improv_ctx.key_center,
            "display_key": improv_ctx.display_key,
            "instrument": improv_ctx.instrument,
            "level": improv_ctx.level,
            "focus": improv_ctx.focus,
            "bpm": improv_ctx.bpm,
            "sections": _normalize_section_map_for_generate(section_map),
        },
    }


def _improv_ctx_from_generate_context(session_state: dict) -> ImprovSessionContext | None:
    snap = session_state.get(MISSIONS_GENERATE_CONTEXT_KEY)
    if not isinstance(snap, dict):
        return None
    raw = snap.get("improv_ctx")
    if not isinstance(raw, dict):
        return None
    sections_raw = raw.get("sections")
    sections: dict[str, list[str]] = {}
    if isinstance(sections_raw, list):
        for item in sections_raw:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                sections[str(item[0])] = list(item[1])
    elif isinstance(sections_raw, dict):
        sections = {str(k): list(v) for k, v in sections_raw.items() if isinstance(v, list)}
    return ImprovSessionContext(
        song_title=str(raw.get("song_title") or "Song"),
        artist=str(raw.get("artist") or ""),
        key_center=str(raw.get("key_center") or raw.get("display_key") or "C"),
        display_key=str(raw.get("display_key") or "C"),
        instrument=str(snap.get("live_inst") or raw.get("instrument") or "Guitar"),
        level=str(snap.get("live_level") or raw.get("level") or "Intermediate"),
        focus=str(snap.get("live_focus") or raw.get("focus") or "Improvisation"),
        sections={str(k): list(v) for k, v in sections.items() if isinstance(v, list)},
        bpm=int(snap.get("bpm") or raw.get("bpm") or 100),
        style_label="",
        progression_flat=[],
        section_order=list(sections.keys()),
    )


def _mission_improv_ctx_from_session(session_state: dict) -> ImprovSessionContext | None:
    from improvisation_motif import flatten_section_map, resolve_improv_sections

    song_title = str(session_state.get("song") or "Song")
    artist = str(session_state.get("artist") or "")
    concert_key = _authoritative_practice_chart_key(
        session_state,
        str(session_state.get("display_key") or session_state.get("chart_key") or "C"),
    )
    try:
        from effective_practice_context import musician_facing_chart_key

        chart_key = musician_facing_chart_key(session_state, concert_key)
    except ImportError:
        chart_key = concert_key
    ctx = ImprovSessionContext(
        song_title=song_title,
        artist=artist,
        key_center=concert_key,
        display_key=chart_key,
        instrument=str(session_state.get("instrument") or "Guitar"),
        level=str(session_state.get("level") or "Intermediate"),
        focus=str(session_state.get("focus") or "Improvisation"),
        sections={},
        bpm=int(session_state.get("backing_track_bpm") or 100),
        style_label="",
        progression_flat=[],
    )
    home = session_state.get("home_sections")
    if isinstance(home, dict) and home:
        ctx.sections = {str(k): list(v) for k, v in home.items() if isinstance(v, list)}
        ctx.progression_flat = flatten_sections(ctx.sections)
    section_map = resolve_improv_sections(session_state, ctx)
    if section_map:
        ctx.sections = {label: list(chs) for label, chs in section_map}
        ctx.progression_flat = flatten_section_map(section_map)
    return ctx


def _run_mission_example_generate(session_state: dict, variant: str) -> None:
    practice_key_before = str(
        session_state.get("display_key") or session_state.get("concert_key") or ""
    ).strip()
    try:
        from music_workflow_pending_backing_handoff import clear_stale_backing_handoff_for_mission_example_generate

        clear_stale_backing_handoff_for_mission_example_generate(session_state)
    except ImportError:
        pass
    from improvisation_motif import flatten_section_map, resolve_improv_sections
    from improvisation_missions import (
        generate_mission_example,
        generate_mission_example_distinct,
        load_mission_example,
        mission_example_artifact_id,
        mission_example_fingerprint,
        motif_material_fingerprint,
    )

    snap = session_state.get(MISSIONS_GENERATE_CONTEXT_KEY)
    improv_ctx = _improv_ctx_from_generate_context(session_state)
    if improv_ctx is None:
        improv_ctx = _mission_improv_ctx_from_session(session_state)
    if improv_ctx is None:
        session_state[MISSION_EXAMPLE_GEN_DIAG_KEY] = {
            "callback": f"mission_example_generate_{variant}",
            "callback_fired": True,
            "abort": "no_improv_ctx",
            "practice_key_before": practice_key_before,
            "practice_key_after": str(session_state.get("display_key") or ""),
        }
        return

    session_state[MISSION_EXAMPLE_GEN_DIAG_KEY] = {
        "callback": f"mission_example_generate_{variant}",
        "callback_fired": True,
        "practice_key_before": practice_key_before,
    }

    concert, chart_key = _coherent_improv_key_pair(session_state, improv_ctx)
    improv_ctx.key_center = concert
    improv_ctx.display_key = chart_key

    if isinstance(snap, dict):
        snap_key = str(snap.get("chart_key") or snap.get("key_center") or "").strip()
        if snap_key and snap_key != concert and snap_key != chart_key:
            session_state.pop(MISSIONS_GENERATE_CONTEXT_KEY, None)
            snap = session_state.get(MISSIONS_GENERATE_CONTEXT_KEY)

    sealed_from_snap = isinstance(snap, dict) and bool(snap.get("cur_chord"))
    if isinstance(snap, dict) and snap.get("cur_chord"):
        cur_chord = str(snap.get("cur_chord"))
        section_label = str(snap.get("section_label") or "Progression")
        mission = str(snap.get("mission") or "").strip()
        chord_idx = int(snap.get("chord_idx") or 0)
        live_inst = str(snap.get("live_inst") or improv_ctx.instrument)
        live_level = str(snap.get("live_level") or improv_ctx.level)
        live_focus = str(snap.get("live_focus") or improv_ctx.focus)
        bpm = int(snap.get("bpm") or improv_ctx.bpm or 100)
        section_map_raw = snap.get("improv_ctx", {}).get("sections")
        section_map_norm = _normalize_section_map_for_generate(section_map_raw)
        chords = flatten_section_map(section_map_norm) if section_map_norm else list(improv_ctx.progression_flat or [])
    else:
        section_map = resolve_improv_sections(session_state, improv_ctx)
        chords = flatten_section_map(section_map) if section_map else []
        if not chords:
            session_state[MISSION_EXAMPLE_GEN_DIAG_KEY] = {
                "callback": f"mission_example_generate_{variant}",
                "callback_fired": True,
                "abort": "no_chords",
                "improv_ctx_sections": bool(improv_ctx.sections),
                "home_sections": bool(session_state.get("home_sections")),
            }
            return
        _ensure_chord_selection(session_state, chords, section_map)
        cur_chord, chord_idx = _selected_chord(session_state, chords, section_map)
        section_label = str(session_state.get(II_SELECTED_SECTION) or "Progression")
        mission = str(
            session_state.get("improv_mission_pick")
            or session_state.get("improv_active_mission")
            or ""
        ).strip()
        live_inst = str(session_state.get("instrument") or improv_ctx.instrument)
        live_level = str(session_state.get("level") or improv_ctx.level)
        live_focus = str(session_state.get("focus") or improv_ctx.focus)
        bpm = int(session_state.get("backing_track_bpm") or improv_ctx.bpm or 100)

    try:
        from mission_workflow_context import resolve_missions_section_map

        auth_section_map, _auth_owner = resolve_missions_section_map(session_state, improv_ctx)
    except ImportError:
        auth_section_map = resolve_improv_sections(session_state, improv_ctx)
    sealed_from_snap = isinstance(snap, dict) and bool(snap.get("cur_chord"))
    if auth_section_map:
        auth_chords = flatten_section_map(auth_section_map)
        if auth_chords:
            if not sealed_from_snap:
                _ensure_chord_selection(session_state, auth_chords, auth_section_map)
            try:
                from creative_chord_selection_authority import resolve_authoritative_chord_selection

                cur_chord, section_label, chord_idx = resolve_authoritative_chord_selection(
                    session_state, auth_section_map
                )
            except ImportError:
                if not sealed_from_snap:
                    cur_chord, chord_idx = _selected_chord(session_state, auth_chords, auth_section_map)
                    section_label = str(session_state.get(II_SELECTED_SECTION) or section_label)

    try:
        from creative_chord_selection_authority import read_authoritative_mission_chord_selection

        auth_ch, auth_sec, auth_idx = read_authoritative_mission_chord_selection(session_state)
        if auth_ch:
            cur_chord = auth_ch
            section_label = auth_sec or section_label
            chord_idx = int(auth_idx)
    except ImportError:
        pass

    if not chords or not mission:
        session_state[MISSION_EXAMPLE_GEN_DIAG_KEY] = {
            "callback": f"mission_example_generate_{variant}",
            "callback_fired": True,
            "abort": "empty_chords_or_mission",
            "chords_n": len(chords),
            "mission": mission,
        }
        return

    focus_before = ""
    try:
        from song_creative_focus import read_song_creative_focus

        fb = read_song_creative_focus(session_state)
        if fb:
            focus_before = str(fb.get("selected_concert_chord") or "")
    except ImportError:
        pass

    prior = load_mission_example(session_state, improv_ctx)
    prev_fp = mission_example_fingerprint(prior)
    prev_mat = motif_material_fingerprint(prior.motif if prior else None)

    retries = 0
    retried = False
    if variant == "new":
        nonce_override = int(session_state.get(MISSION_NEW_NONCE_KEY) or 0) + 1
        example, retries, retried = generate_mission_example_distinct(
            mission,
            improv_ctx=improv_ctx,
            chord=cur_chord,
            section=section_label,
            level=live_level,
            instrument=live_inst,
            focus=live_focus,
            variant="new",
            bpm=bpm,
            session_state=session_state,
            nonce_override=nonce_override,
            prior_material_fp=prev_mat,
            max_attempts=8,
        )
    else:
        example = generate_mission_example(
            mission,
            improv_ctx=improv_ctx,
            chord=cur_chord,
            section=section_label,
            level=live_level,
            instrument=live_inst,
            focus=live_focus,
            variant=variant,
            bpm=bpm,
            session_state=session_state,
        )

    session_state["_mission_example_artifact_id"] = mission_example_artifact_id(
        session_state,
        mission=mission,
        chord=cur_chord,
        section=section_label,
        chord_index=int(chord_idx),
    )
    session_state.pop("_mission_example_last_transform", None)
    store_mission_example(
        session_state,
        example,
        persist_artifact=True,
        interaction=f"mission_example_generate_{variant}",
    )
    gen_fp = mission_example_fingerprint(example)
    session_state["_mission_example_output_fp"] = gen_fp
    session_state["_mission_example_material_fp"] = motif_material_fingerprint(example.motif)
    _record_mission_example_gen_diag(
        session_state,
        variant=variant,
        prior=prior,
        example=example,
        prev_fp=prev_fp,
        prev_mat=prev_mat,
        gen_fp=gen_fp,
        retries=retries,
        retried=retried,
    )
    diag = session_state.get(MISSION_EXAMPLE_GEN_DIAG_KEY) or {}
    if isinstance(diag, dict):
        diag["mission"] = mission
        diag["chord"] = cur_chord
        diag["section"] = section_label
        diag["used_generate_context"] = isinstance(snap, dict) and bool(snap.get("cur_chord"))
        diag["sealed_generate_context"] = sealed_from_snap
        diag["focus_chord_before"] = focus_before
        try:
            from song_creative_focus import read_song_creative_focus

            fa = read_song_creative_focus(session_state)
            diag["focus_chord_after"] = str(fa.get("selected_concert_chord") or "") if fa else focus_before
        except ImportError:
            diag["focus_chord_after"] = focus_before
        practice_after = _authoritative_practice_chart_key(session_state, improv_ctx.display_key)
        diag["parent_practice_key"] = practice_after
        diag["practice_key_before"] = str(diag.get("practice_key_before") or practice_after)
        diag["practice_key_after"] = practice_after
        diag["display_key_after"] = str(session_state.get("display_key") or "")
        diag["concert_key_after"] = str(session_state.get("concert_key") or "")
        diag["chart_key"] = str(improv_ctx.display_key or "")
        diag["example_chord"] = str(getattr(example, "chord", "") or "")
        session_state[MISSION_EXAMPLE_GEN_DIAG_KEY] = diag
    try:
        from studio_page_persistence import save_page_snapshot

        save_page_snapshot(session_state, "creative")
    except ImportError:
        pass


def _finalize_mission_gen_callback(session_state: dict, variant: str) -> None:
    session_state[MISSIONS_LAST_EXAMPLE_CALLBACK_KEY] = f"mission_example_generate_{variant}"
    session_state[MISSION_EXAMPLE_FRESH_RUN_KEY] = True
    prior_notes = str(session_state.get("_missions_display_notes_before") or "")
    session_state["_missions_display_notes_before"] = prior_notes


def _on_mission_gen_normal() -> None:
    import streamlit as st

    _run_mission_example_generate(st.session_state, "normal")
    _finalize_mission_gen_callback(st.session_state, "normal")


def _on_mission_gen_easier() -> None:
    import streamlit as st

    _run_mission_example_generate(st.session_state, "easier")
    _finalize_mission_gen_callback(st.session_state, "easier")


def _on_mission_gen_harder() -> None:
    import streamlit as st

    _run_mission_example_generate(st.session_state, "harder")
    _finalize_mission_gen_callback(st.session_state, "harder")


def _on_mission_gen_new_idea() -> None:
    import streamlit as st

    _run_mission_example_generate(st.session_state, "new")
    _finalize_mission_gen_callback(st.session_state, "new")


def _maybe_refresh_mission_example_outputs(
    session_state: dict,
    example: MissionExample,
    *,
    instrument: str,
    bpm: int,
) -> MissionExample:
    from improvisation_missions import mission_example_fingerprint, mission_example_for_display

    concert = str(
        example.concert_key
        or session_state.get("improv_song_concert_key")
        or ""
    ).strip()
    try:
        concert = _authoritative_practice_chart_key(session_state, concert or example.concert_key or example.display_key)
    except Exception:
        if not concert:
            concert = str(session_state.get("concert_key") or example.concert_key or example.display_key or "")
    try:
        from effective_practice_context import musician_facing_chart_key

        chart = musician_facing_chart_key(session_state, concert)
    except ImportError:
        chart = str(example.display_key or concert)
    fp = mission_example_fingerprint(example)
    projected = str((example.motif or {}).get("_projected_display_key") or "")
    spell_fp = str((example.motif or {}).get("spelling_reference") or "")
    needs = (
        session_state.get("_mission_example_output_fp") != fp
        or not spell_fp
        or projected != str(chart or "")
        or str(example.concert_key or "") != str(concert or "")
    )
    if not needs:
        return example
    example.display_key = chart
    example.concert_key = concert
    refreshed = mission_example_for_display(
        example,
        instrument=instrument,
        bpm=bpm,
        song_concert_key=concert,
        session_state=session_state,
        authoritative_concert_key=concert,
        authoritative_display_key=str(example.display_key or ""),
    )
    session_state["_mission_example_output_fp"] = mission_example_fingerprint(refreshed)
    # Persist reprojected motif so Shape changes survive refresh and later Generate.
    try:
        from improvisation_missions import store_mission_example

        store_mission_example(
            session_state,
            refreshed,
            persist_artifact=True,
            interaction="mission_example_shape_reproject",
        )
    except Exception:
        pass
    return refreshed


def _render_mission_example_buttons_dev_panel(
    st_module: Any,
    session_state: dict,
    improv_ctx: ImprovSessionContext,
) -> None:
    diag = dict(session_state.get(MISSION_EXAMPLE_GEN_DIAG_KEY) or {})
    loaded = load_mission_example(session_state, improv_ctx)
    loaded_fp = mission_example_fingerprint(loaded) if loaded else ""
    loaded_mat = motif_material_fingerprint(loaded.motif) if loaded else ""
    raw = session_state.get(MISSION_EXAMPLE_KEY)
    stored_mat = str((raw or {}).get("material_fp") or "") if isinstance(raw, dict) else ""
    st_module.markdown(
        f"<p style='font-size:0.72rem;color:#6b21a8;margin:0.15rem 0 0.5rem 0;'>"
        f"<strong>DEV example buttons</strong> · "
        f"callback: <code>{html.escape(str(session_state.get(MISSIONS_LAST_EXAMPLE_CALLBACK_KEY) or diag.get('callback') or '—'))}</code> · "
        f"abort: <code>{html.escape(str(diag.get('abort') or '—'))}</code> · "
        f"context: <code>{'yes' if session_state.get(MISSIONS_GENERATE_CONTEXT_KEY) else 'no'}</code><br/>"
        f"prev mat: <code>{html.escape(str(diag.get('previous_material_fp') or '—')[:12])}</code> · "
        f"gen mat: <code>{html.escape(str(diag.get('generated_material_fp') or stored_mat)[:12])}</code> · "
        f"stored mat: <code>{html.escape(stored_mat[:12] or '—')}</code> · "
        f"canon: <code>{html.escape(str(diag.get('canonical_artifact_fp') or _canonical_mission_example_fingerprint(session_state))[:12])}</code><br/>"
        f"loaded: <code>{html.escape(loaded_fp[:12] or '—')}</code> / "
        f"<code>{html.escape(loaded_mat[:12] or '—')}</code> · "
        f"display: <code>{html.escape(str(diag.get('displayed_material_fp') or loaded_mat)[:12])}</code> · "
        f"artifact id: <code>{html.escape(str(session_state.get('_mission_example_artifact_id') or '—')[:24])}</code> · "
        f"overwrite: <code>{diag.get('artifact_overwritten')}</code><br/>"
        f"notes before: <code>{html.escape(str(session_state.get('_missions_display_notes_before') or '—')[:40])}</code> · "
        f"notes now: <code>{html.escape(str(loaded.motif.get('display') if loaded else '—')[:40])}</code>"
        f"</p>",
        unsafe_allow_html=True,
    )


def _tab_missions(
    st: Any,
    *,
    session_state: dict,
    improv_ctx: ImprovSessionContext,
    bpm: int,
    on_open_backing: Callable[[], None] | None,
    on_open_practice: Callable[[], None] | None,
    on_open_analysis: Callable[[], None] | None = None,
) -> None:
    from music_dev_perf import dev_perf_span, render_dev_perf_caption

    from practice_setup_controls import (
        DEFAULT_INSTRUMENT_OPTIONS,
        render_setup_quick_controls,
    )

    try:
        from song_creative_focus import hydrate_creative_pages_from_song_focus

        hydrate_creative_pages_from_song_focus(session_state, tab="Missions")
    except ImportError:
        pass

    try:
        from creative_mission_config_persistence import project_mission_config_from_canonical_before_widgets

        project_mission_config_from_canonical_before_widgets(session_state)
    except ImportError:
        pass

    try:
        from creative_mission_artifact_persistence import (
            CREATIVE_MISSION_ARTIFACT_USER_EVENT_KEY,
            project_mission_artifacts_from_canonical,
            should_skip_mission_artifact_projection,
        )
        from creative_tab_tool_persistence import selector_hydration_complete

        skip_project = bool(session_state.get(MISSION_EXAMPLE_FRESH_RUN_KEY))
        user_ev = session_state.get(CREATIVE_MISSION_ARTIFACT_USER_EVENT_KEY)
        if isinstance(user_ev, dict) and user_ev.get("field") == MISSION_EXAMPLE_KEY:
            skip_project = True
        if selector_hydration_complete(session_state) and not skip_project:
            if should_skip_mission_artifact_projection(session_state):
                try:
                    from music_dev_nav import dev_count

                    dev_count(session_state, "missions_artifact_project_skipped")
                except ImportError:
                    pass
            else:
                try:
                    from music_dev_nav import dev_count

                    dev_count(session_state, "missions_artifact_project")
                except ImportError:
                    pass
                with dev_perf_span(session_state, "missions_project_artifacts", st_module=st):
                    project_mission_artifacts_from_canonical(session_state, overwrite=False)
    except ImportError:
        pass

    st.markdown(creative_tool_heading_markdown("Missions"))
    _render_missions_route_dev_marker(
        st,
        session_state,
        renderer="_tab_missions",
        branch="missions_heading",
        extra={
            "studio_engaged": bool(session_state.get("_mission_recording_studio_engaged")),
            "has_target_chord_card": False,
        },
    )
    st.caption(
        f"Interactive coach for **{html.escape(improv_ctx.song_title)}** "
        f"({html.escape(improv_ctx.artist)})"
    )

    live_inst, live_level, live_focus = render_setup_quick_controls(
        st,
        session_state=session_state,
        key_prefix="improv_mission",
        instrument_options=DEFAULT_INSTRUMENT_OPTIONS,
        label="Instrument · level · focus",
        show_sync_caption=False,
    )

    mission_options = list(PRACTICE_MISSIONS)
    default_mission = session_state.get("improv_active_mission") or mission_options[0]
    if default_mission not in mission_options:
        default_mission = mission_options[0]
    mission_idx = mission_options.index(default_mission)

    mission = st.selectbox(
        "Choose a mission",
        mission_options,
        index=mission_idx,
        key="improv_mission_pick",
        on_change=_on_mission_pick_change,
    )
    mission = str(session_state.get("improv_mission_pick") or session_state.get("improv_active_mission") or mission_options[mission_idx])

    try:
        from music_workflow_song_practice import ensure_missions_parent_practice_key_hydrated

        ensure_missions_parent_practice_key_hydrated(session_state)
    except ImportError:
        try:
            from workflow_musical_authority import sync_song_improv_sections_to_practice_key

            sync_song_improv_sections_to_practice_key(session_state)
        except ImportError:
            pass

    concert_key, chart_key = _coherent_improv_key_pair(session_state, improv_ctx)
    blob_key = str(improv_ctx.key_center or concert_key)
    try:
        from music_workflow_song_practice import resolve_song_practice_key_token

        committed = str(resolve_song_practice_key_token(session_state) or "").strip()
        if committed:
            blob_key = committed
    except ImportError:
        try:
            from workflow_key_identity import resolve_song_practice_key_identity

            ident = resolve_song_practice_key_identity(session_state)
            if ident is not None and str(ident.practice_key_token or "").strip():
                blob_key = str(ident.practice_key_token)
        except ImportError:
            pass
    try:
        from music_workflow_pending_song_practice_key_edit import overlay_sections_with_pending_practice_key

        if isinstance(improv_ctx.sections, dict) and improv_ctx.sections:
            overlayed = overlay_sections_with_pending_practice_key(
                session_state,
                dict(improv_ctx.sections),
                spelled_in_key=blob_key,
            )
            improv_ctx = replace(
                improv_ctx,
                sections=overlayed,
                key_center=concert_key,
                display_key=chart_key,
            )
        else:
            improv_ctx = replace(improv_ctx, key_center=concert_key, display_key=chart_key)
    except ImportError:
        improv_ctx = replace(improv_ctx, key_center=concert_key, display_key=chart_key)

    try:
        from active_musical_workflow_envelope import (
            inspect_mission_workflow_envelope,
            render_workflow_envelope_dev_panel,
        )

        rep = inspect_mission_workflow_envelope(session_state)
        if not rep.get("consistent"):
            st.caption("Mission context is still syncing — use Mission Backing after refresh if navigation fails.")
        render_workflow_envelope_dev_panel(st, session_state)
    except ImportError:
        pass

    try:
        from mission_workflow_context import resolve_missions_section_map

        section_map, _prog_owner = resolve_missions_section_map(session_state, improv_ctx)
    except ImportError:
        section_map = resolve_improv_sections(session_state, improv_ctx)
    if not section_map:
        section_map = resolve_improv_sections(session_state, improv_ctx)
    try:
        from creative_mission_config_persistence import IMPROV_MISSION_SECTION_MAP_SESSION_KEY

        session_state[IMPROV_MISSION_SECTION_MAP_SESSION_KEY] = section_map
    except ImportError:
        session_state["_improv_mission_section_map"] = section_map
    chords = flatten_section_map(section_map)
    if not chords:
        st.warning("Select a song with chords first (Song Selection or Custom Progression).")
        return

    _ensure_chord_selection(session_state, chords, section_map)
    cur_chord, chord_idx = _selected_chord(session_state, chords, section_map)
    section_label = str(session_state.get(II_SELECTED_SECTION) or "Progression")

    try:
        from mission_workflow_context import (
            reconcile_missions_workflow_context,
            render_mission_context_dev_panel,
        )

        section_map, ctx_report = reconcile_missions_workflow_context(
            session_state,
            improv_ctx,
            mission=mission,
            cur_chord=cur_chord,
            section_label=section_label,
        )
        try:
            from music_workflow_pending_mission_envelope import (
                peek_pending_mission_envelope_reconciliation,
                request_pending_mission_envelope_rerun,
            )

            if peek_pending_mission_envelope_reconciliation(session_state):
                request_pending_mission_envelope_rerun(st, session_state)
        except ImportError:
            pass
        try:
            from creative_mission_config_persistence import IMPROV_MISSION_SECTION_MAP_SESSION_KEY

            session_state[IMPROV_MISSION_SECTION_MAP_SESSION_KEY] = section_map
        except ImportError:
            session_state["_improv_mission_section_map"] = section_map
        chords = flatten_section_map(section_map)
        _ensure_chord_selection(session_state, chords, section_map)
        cur_chord, chord_idx = _selected_chord(session_state, chords, section_map)
        section_label = str(session_state.get(II_SELECTED_SECTION) or "Progression")
        render_mission_context_dev_panel(st, session_state)
        if not ctx_report.ok:
            st.caption(
                "Mission context was reconciled to your active catalog song (stale jam data removed)."
            )
    except ImportError:
        pass

    _render_section_chord_map(
        st,
        section_map,
        session_state,
        key_prefix="improv_mission",
        source_id=_improv_source_id(session_state, improv_ctx),
        key_center=concert_key,
    )
    cur_chord, chord_idx = _selected_chord(session_state, chords, section_map)
    section_label = str(session_state.get(II_SELECTED_SECTION) or "Progression")
    try:
        from music_workflow_pending_song_practice_key_edit import overlay_chord_with_pending_practice_key

        cur_chord = overlay_chord_with_pending_practice_key(
            session_state, cur_chord, spelled_in_key=blob_key
        )
    except ImportError:
        pass
    practice_key = _authoritative_practice_chart_key(session_state, improv_ctx.display_key)
    try:
        from effective_practice_context import musician_facing_chart_key, musician_facing_chord

        chart_key = musician_facing_chart_key(session_state, practice_key)
        shown_chord = musician_facing_chord(
            cur_chord,
            concert_key=practice_key,
            chart_key=chart_key,
        )
    except ImportError:
        shown_chord = cur_chord
        chart_key = practice_key
    chart_note = ""
    if chart_key != practice_key:
        try:
            from music_theory import format_key_label_from_parts, split_key_center

            tonic, mode = split_key_center(chart_key)
            chart_label = format_key_label_from_parts(tonic, mode)
        except ImportError:
            chart_label = chart_key
        chart_note = f" · Charts in **{html.escape(chart_label)}**"
    st.caption(
        f"Practice Key: **{html.escape(practice_key)}** · "
        f"Selected Mission Chord: **{html.escape(shown_chord)}** · "
        f"Section: **{html.escape(section_label)}**{chart_note}"
    )

    _sync_missions_session_from_improv_ctx(session_state, improv_ctx, section_map=section_map)

    from improvisation_missions import mission_brief_for_practice

    st.markdown("##### Mission instructions")
    st.markdown(mission_brief_for_practice(mission))
    st.caption("Improvise freely — you are not required to copy any example notes.")

    session_state["improv_active_mission"] = mission
    try:
        from mission_practice_context import mark_mission_practice_context_dirty

        mark_mission_practice_context_dirty(session_state)
    except ImportError:
        pass

    def _open_mission_upload_analysis() -> None:
        if not on_open_analysis:
            return
        from mission_analysis_ui import prepare_mission_upload_from_missions

        session_state["improv_active_mission"] = mission
        prepare_mission_upload_from_missions(session_state)
        on_open_analysis()

    st.markdown("---")
    st.markdown("##### Optional example idea")
    st.caption(
        "This is one possible way to practice the mission. You may create your own notes and phrases."
    )

    _prior_loaded = load_mission_example(session_state, improv_ctx)
    session_state["_missions_display_notes_before"] = str(
        (_prior_loaded.motif.get("display") if _prior_loaded else "")
        or (session_state.get(MISSION_EXAMPLE_KEY) or {}).get("motif", {}).get("display")
        or ""
    )

    _stash_missions_generate_context(
        session_state,
        improv_ctx=improv_ctx,
        section_map=section_map,
        mission=mission,
        cur_chord=cur_chord,
        section_label=section_label,
        chord_idx=int(chord_idx),
        live_inst=live_inst,
        live_level=live_level,
        live_focus=live_focus,
        bpm=bpm,
    )

    g1, g2, g3, g4 = st.columns(4)
    with g1:
        st.button(
            "Generate example",
            key="improv_mission_gen",
            type="primary",
            use_container_width=True,
            on_click=_on_mission_gen_normal,
        )
    with g2:
        st.button(
            "Easier example",
            key="improv_mission_easier",
            use_container_width=True,
            on_click=_on_mission_gen_easier,
        )
    with g3:
        st.button(
            "Harder example",
            key="improv_mission_harder",
            use_container_width=True,
            on_click=_on_mission_gen_harder,
        )
    with g4:
        st.button(
            "New idea",
            key="improv_mission_new",
            use_container_width=True,
            on_click=_on_mission_gen_new_idea,
        )

    if _improv_dev_mode(session_state, st):
        _render_mission_example_buttons_dev_panel(st, session_state, improv_ctx)

    example = load_mission_example(session_state, improv_ctx)
    if example and not _example_matches_active_context(
        example, mission=mission, cur_chord=cur_chord, section_label=section_label, song_title=improv_ctx.song_title
    ):
        example = None

    pre_render_fp = str(session_state.get("_mission_example_output_fp") or "")
    raw_example = session_state.get(MISSION_EXAMPLE_KEY)
    pre_render_mat = ""
    if isinstance(raw_example, dict):
        pre_render_mat = str(raw_example.get("material_fp") or "")

    def _mission_backing_on_click(*, with_practice_lick: bool, widget_key: str) -> None:
        if not on_open_backing:
            return
        import streamlit as st

        from widget_callback_diagnostics import log_widget_callback_enter

        from music_workflow_mission_backing_click import (
            capture_mission_backing_click_intent,
        )

        log_widget_callback_enter(widget_key=widget_key, callback=_mission_backing_on_click)
        ss = st.session_state
        try:
            from creative_chord_selection_authority import read_authoritative_mission_chord_selection

            click_chord, click_section, click_idx = read_authoritative_mission_chord_selection(ss)
        except ImportError:
            click_chord = str(ss.get(II_SELECTED_CHORD) or cur_chord or "")
            click_section = str(ss.get(II_SELECTED_SECTION) or section_label or "")
            click_idx = int(ss.get(II_SELECTED_CHORD_INDEX, chord_idx))
        click_mission = str(
            ss.get("improv_mission_pick") or ss.get("improv_active_mission") or mission or ""
        ).strip()
        capture_mission_backing_click_intent(
            ss,
            with_practice_lick=with_practice_lick,
            mission=click_mission,
            cur_chord=str(click_chord or ""),
            section_label=str(click_section or ""),
            chord_idx=int(click_idx),
            song_title=str(improv_ctx.song_title or ""),
            concert_key=str(improv_ctx.key_center or ""),
            display_key=str(improv_ctx.display_key or ""),
        )
        try:
            from music_mission_backing_handoff_trace import log_mission_backing_click
            from music_workflow_pending_backing_handoff import (
                mission_backing_click_must_defer,
                resolve_backing_workflow_owner,
            )
            from session_widget_safe import widgets_likely_instantiated

            log_mission_backing_click(
                st.session_state,
                with_practice_lick=with_practice_lick,
                mission_id=click_mission,
                mission_session_id="",
                section=str(click_section or ""),
                chord=str(click_chord or ""),
                workflow_owner=resolve_backing_workflow_owner(st.session_state, backing_source="mission"),
                widgets_locked=widgets_likely_instantiated(st.session_state),
                mission_widgets_instantiated=bool(
                    session_state.get("_creative_mission_widgets_instantiated")
                ),
            )
            st.session_state["_mission_backing_click_must_defer"] = mission_backing_click_must_defer(
                st.session_state
            )
        except ImportError:
            pass

    def _on_plain_mission_backing() -> None:
        _mission_backing_on_click(with_practice_lick=False, widget_key="improv_mission_over_backing")

    def _on_practice_in_backing_jam() -> None:
        _mission_backing_on_click(with_practice_lick=True, widget_key="improv_mission_over_backing_bottom")

    if not example:
        if on_open_backing:
            try:
                from widget_callback_diagnostics import log_widget_callback_registration

                log_widget_callback_registration(
                    widget_key="improv_mission_over_backing",
                    callback=_on_plain_mission_backing,
                )
            except ImportError:
                pass
            st.button(
                nav_icon_button_label("backing") + " Jam",
                key="improv_mission_over_backing",
                type="primary",
                use_container_width=True,
                on_click=_on_plain_mission_backing,
            )

    if on_open_analysis:
        pass  # optional recording expander rendered at bottom

    if not example:
        st.info(
            "Press **Generate example** for optional inspiration tied to "
            f"**{html.escape(improv_ctx.song_title)}** — or improvise your own ideas."
        )
    else:
        example = _maybe_refresh_mission_example_outputs(
            session_state, example, instrument=live_inst, bpm=bpm
        )
        family = instrument_family(live_inst)

        st.markdown("##### Optional example (inspiration only)")
        example_heading_chord = shown_chord
        try:
            from effective_practice_context import musician_facing_chord

            example_heading_chord = musician_facing_chord(
                str(
                    (example.motif or {}).get("_concert_chord")
                    or example.chord
                    or cur_chord
                    or shown_chord
                ),
                concert_key=practice_key,
                chart_key=chart_key,
            )
        except ImportError:
            example_heading_chord = shown_chord
        if example_heading_chord:
            st.markdown(f"**Mission example · {html.escape(example_heading_chord)}**")
        st.markdown(
            f"**Notes:** `{example.motif.get('display', '')}` · "
            f"**Rhythm:** `{example.motif.get('rhythm', '')}`"
        )
        st.markdown(f"**Why it works:** {example.why}")
        for step in example.practice_steps:
            st.markdown(f"- {step}")

        st.markdown("**Transform idea**")
        t1, t2, t3, t4 = st.columns(4)
        transform_clicked = False
        with t1:
            if st.button("Sequence Up ↑", key="improv_mission_seq_up", use_container_width=True):
                apply_mission_motif_transform(
                    session_state, improv_ctx, "sequence_up", bpm=bpm
                )
                transform_clicked = True
        with t2:
            if st.button("Sequence Down ↓", key="improv_mission_seq_down", use_container_width=True):
                apply_mission_motif_transform(
                    session_state, improv_ctx, "sequence_down", bpm=bpm
                )
                transform_clicked = True
        with t3:
            if st.button("Invert ↓↑", key="improv_mission_invert", use_container_width=True):
                apply_mission_motif_transform(
                    session_state, improv_ctx, "invert", bpm=bpm
                )
                transform_clicked = True
        with t4:
            if st.button(
                "Change Rhythm",
                key="improv_mission_change_rhythm",
                use_container_width=True,
            ):
                apply_mission_motif_transform(
                    session_state, improv_ctx, "change_rhythm", bpm=bpm
                )
                transform_clicked = True
        if transform_clicked:
            try:
                from studio_page_persistence import save_page_snapshot

                save_page_snapshot(session_state, "creative")
            except ImportError:
                pass
            st.rerun()

        example = load_mission_example(session_state, improv_ctx)
        if example:
            example = _maybe_refresh_mission_example_outputs(
                session_state, example, instrument=live_inst, bpm=bpm
            )
            try:
                from improvisation_missions import ensure_mission_sheet_music_authority

                example = ensure_mission_sheet_music_authority(
                    session_state,
                    example,
                    improv_ctx=improv_ctx,
                    instrument=live_inst,
                    bpm=bpm,
                )
            except ImportError:
                pass

        st.markdown("**Chord tones**")
        st.markdown("`" + " · ".join(example.insight.chord_tones) + "`")
        if family != "wind":
            st.markdown("**Suggested scales**")
            suggestions = example.insight.scale_suggestions or [
                build_scale_suggestion(label, reference_key=example.display_key)
                for label in example.insight.scales
            ]
            for suggestion in suggestions:
                st.markdown(format_scale_line(suggestion, example.insight.chord_tones))

        if example.abc:
            st.markdown("**Sheet music**")
            n_notes = len(example.motif.get("notes") or [])
            staff_h = min(720, max(360, 280 + n_notes * 14))
            _render_motif_sheet_music(st, example.abc, height=staff_h)
            try:
                from suite_workspace import is_developer_mode_enabled

                if is_developer_mode_enabled(st=st):
                    diag = dict(session_state.get("_mission_notation_diag") or {})
                    if diag:
                        st.caption(
                            "DEV notation · "
                            f"concert_key={diag.get('concert_key')} · "
                            f"written_key={diag.get('written_key')} · "
                            f"chord={diag.get('chord')} · "
                            f"abc_key={diag.get('abc_key')} · "
                            f"authority_v={diag.get('authority_version')}"
                        )
            except ImportError:
                pass

        if family == "guitar" and example.tab:
            st.markdown("**Guitar TAB**")
            st.code(example.tab, language=None)

        if family == "piano" and example.piano_html:
            st.markdown("**Piano guide**")
            st.markdown(example.piano_html, unsafe_allow_html=True)

        if family == "wind":
            st.markdown("**Phrasing & articulation**")
            for line in wind_phrasing_lines(live_inst, example.motif):
                st.markdown(f"- {line}")

        st.markdown("---")
        try:
            from mission_example_normalization import MISSION_BACKING_EXAMPLE_ERROR_KEY

            mission_example_err = str(session_state.get(MISSION_BACKING_EXAMPLE_ERROR_KEY) or "").strip()
            if mission_example_err:
                st.error(mission_example_err)
        except ImportError:
            mission_example_err = ""
        try:
            from music_workflow_pending_backing_handoff import PENDING_BACKING_HANDOFF_USER_MESSAGE_KEY

            handoff_msg = str(session_state.get(PENDING_BACKING_HANDOFF_USER_MESSAGE_KEY) or "").strip()
            if handoff_msg:
                st.warning(handoff_msg)
        except ImportError:
            pass
        practice_in_jam = st.checkbox(
            "Practice this lick in Backing Jam",
            value=True,
            key="improv_mission_practice_lick_toggle",
            help="Optional: open Backing Jam with this example for reference — not required for scoring.",
        )
        if on_open_backing:
            try:
                from widget_callback_diagnostics import log_widget_callback_registration

                log_widget_callback_registration(
                    widget_key="improv_mission_over_backing_bottom",
                    callback=_on_practice_in_backing_jam,
                )
            except ImportError:
                pass
            st.button(
                "▶ Practice in Backing Jam" if practice_in_jam else nav_icon_button_label("backing") + " Jam",
                key="improv_mission_over_backing_bottom",
                type="primary",
                use_container_width=True,
                on_click=_on_practice_in_backing_jam if practice_in_jam else _on_plain_mission_backing,
            )

        st.caption(
            f"Inspiration variant: **{example.variant}** · "
            f"notation shown for **{html.escape(live_inst)}** — scoring uses your mission, not these exact pitches."
        )

    st.markdown("---")
    try:
        from mission_upload_recording_ui import (
            MISSIONS_RECORDING_KEY_PREFIX,
            render_mission_recording_upload_expander,
        )

        dev_mode = _improv_dev_mode(session_state, st)

        render_mission_recording_upload_expander(
            st,
            session_state,
            key_prefix=MISSIONS_RECORDING_KEY_PREFIX,
            on_open_upload_analysis=_open_mission_upload_analysis if on_open_analysis else None,
            dev_mode=dev_mode,
        )
    except Exception as exc:
        if _improv_dev_mode(session_state, st):
            st.error(f"Mission recording expander failed: {exc!r}")

    loaded_after = load_mission_example(session_state, improv_ctx)
    diag = dict(session_state.get(MISSION_EXAMPLE_GEN_DIAG_KEY) or {})
    if diag:
        diag["loaded_fp_after_render"] = (
            mission_example_fingerprint(loaded_after) if loaded_after else ""
        )
        if example:
            diag["displayed_fp"] = mission_example_fingerprint(example)
            diag["displayed_material_fp"] = motif_material_fingerprint(example.motif)
            diag["display_notes"] = str(example.motif.get("display") or "")
        else:
            diag["displayed_fp"] = ""
            diag["displayed_material_fp"] = ""
            diag["display_notes"] = ""
        diag["canonical_artifact_fp"] = _canonical_mission_example_fingerprint(session_state)
        post_fp = str(session_state.get("_mission_example_output_fp") or "")
        post_mat = ""
        raw_post = session_state.get(MISSION_EXAMPLE_KEY)
        if isinstance(raw_post, dict):
            post_mat = str(raw_post.get("material_fp") or "")
        diag["artifact_overwritten"] = bool(
            pre_render_fp
            and post_fp
            and pre_render_fp != post_fp
            and pre_render_mat
            and post_mat
            and pre_render_mat != post_mat
        )
        session_state[MISSION_EXAMPLE_GEN_DIAG_KEY] = diag
        session_state[MISSION_NEW_IDEA_DIAG_KEY] = dict(diag)
    session_state.pop(MISSION_EXAMPLE_FRESH_RUN_KEY, None)

    if _improv_dev_mode(session_state, st) and diag.get("callback_fired"):
        st.caption(
            f"DEV example · {diag.get('callback', '—')} · "
            f"mat {str(diag.get('previous_material_fp') or '—')[:8]}→"
            f"{str(diag.get('displayed_material_fp') or '—')[:8]} · "
            f"overwrite={diag.get('artifact_overwritten')}"
        )

    try:
        from creative_mission_artifact_persistence import collect_creative_mission_artifact_diagnostics

        if _improv_dev_mode(session_state, st):
            dev_diag = dict(session_state.get(MISSION_EXAMPLE_GEN_DIAG_KEY) or {})
            dev_diag["artifact"] = collect_creative_mission_artifact_diagnostics(session_state)
            with st.expander("Developer · mission example / artifact", expanded=False):
                st.json(dev_diag)
    except ImportError:
        pass

    render_dev_perf_caption(st, session_state, route="_tab_missions")


def _tab_harmony_map(
    st: Any,
    *,
    session_state: dict,
    improv_ctx: ImprovSessionContext,
) -> None:
    from practice_setup_controls import (
        DEFAULT_INSTRUMENT_OPTIONS,
        render_setup_quick_controls,
    )

    try:
        from song_creative_focus import hydrate_creative_pages_from_song_focus

        hydrate_creative_pages_from_song_focus(session_state, tab="Harmony Map")
    except ImportError:
        pass

    st.markdown(creative_tool_heading_markdown("Harmony Map"))
    concert_key, chart_key = _coherent_improv_key_pair(session_state, improv_ctx)
    caption_key = chart_key if chart_key != concert_key else concert_key
    _sel = session_state.get("selected_song") if isinstance(session_state.get("selected_song"), dict) else {}
    live_title = str((_sel or {}).get("title") or session_state.get("song") or improv_ctx.song_title)
    st.caption(
        f"**{html.escape(live_title)}** · key **{html.escape(caption_key)}** · "
        "one progression per section — tap a chord for stable & color tones."
    )

    live_inst, live_level, live_focus = render_setup_quick_controls(
        st,
        session_state=session_state,
        key_prefix="improv_harmony",
        instrument_options=DEFAULT_INSTRUMENT_OPTIONS,
        label="Instrument · level · focus",
        show_sync_caption=False,
    )
    concert_sections = _authoritative_concert_sections(session_state, improv_ctx.sections)
    concert_key, chart_key = _coherent_improv_key_pair(session_state, improv_ctx)
    _sel = session_state.get("selected_song") if isinstance(session_state.get("selected_song"), dict) else {}
    improv_ctx = ImprovSessionContext(
        song_title=str((_sel or {}).get("title") or session_state.get("song") or improv_ctx.song_title),
        artist=str((_sel or {}).get("artist") or improv_ctx.artist),
        key_center=concert_key,
        display_key=chart_key,
        instrument=live_inst,
        level=live_level,
        focus=live_focus,
        sections=concert_sections,
        bpm=improv_ctx.bpm,
        style_label=improv_ctx.style_label,
        progression_flat=flatten_sections(
            concert_sections,
            section_names=list(improv_ctx.section_order) or None,
        ),
        section_order=list(improv_ctx.section_order) or list(concert_sections.keys()),
    )

    section_map = resolve_improv_sections(session_state, improv_ctx)
    if not section_map:
        section_map = deduped_section_chords(
            improv_ctx.sections,
            section_names=list(improv_ctx.section_order) or None,
        )
    chords_flat = flatten_section_map(section_map) if section_map else []
    if section_map and chords_flat:
        _ensure_chord_selection(session_state, chords_flat, section_map)
        sel_chord, _ = _selected_chord(session_state, chords_flat, section_map)
        sel_section = str(session_state.get(II_SELECTED_SECTION) or "")
    else:
        sel_section = str(session_state.get("harmony_map_section") or "")
        sel_chord = str(session_state.get("harmony_map_chord") or "")

    if not section_map:
        st.info("No chords in the active chart — pick a song or custom progression first.")
        return

    st.markdown(HARMONY_MAP_CHIP_CSS, unsafe_allow_html=True)

    src = _safe_widget_key_part(improv_ctx.song_title or "song")

    for sec_i, (sec_label, chords) in enumerate(section_map):
        chips = []
        for ch in chords:
            selected = sel_section == sec_label and sel_chord == ch
            shown = _player_facing_chord(session_state, ch, concert_key=concert_key)
            chips.append(
                f'<span class="hm-chord-chip{" selected" if selected else ""}">'
                f"{html.escape(shown)}</span>"
            )
        st.markdown(
            f'<div class="hm-section-block">'
            f'<p class="hm-section-title">{html.escape(sec_label)}</p>'
            f'<div class="hm-chord-row">{"".join(chips)}</div></div>',
            unsafe_allow_html=True,
        )

        cols = st.columns(min(len(chords), 8) or 1)
        for i, ch in enumerate(chords):
            with cols[i % len(cols)]:
                button_key = (
                    f"hm_pick_{src}_{_safe_widget_key_part(sec_label)}_{i}_{_safe_widget_key_part(ch)}"
                )
                shown = _player_facing_chord(session_state, ch, concert_key=concert_key)
                if st.button(
                    shown,
                    key=button_key,
                    type="primary" if sel_section == sec_label and sel_chord == ch else "secondary",
                    use_container_width=True,
                    on_click=_harmony_map_chord_on_click,
                    args=(ch, sec_label, global_chord_index(list(section_map), sec_i, i), button_key),
                ):
                    pass

    if not sel_chord:
        st.info("Tap a chord above to see stable tones, color tones, and practical improvisation ideas.")
        return

    next_ch = ""
    prev_ch = ""
    for si, (sec_label, chords) in enumerate(section_map):
        if sec_label != sel_section:
            continue
        for i, ch in enumerate(chords):
            if ch != sel_chord:
                continue
            if i + 1 < len(chords):
                next_ch = chords[i + 1]
            elif si + 1 < len(section_map) and section_map[si + 1][1]:
                next_ch = section_map[si + 1][1][0]
            if i > 0:
                prev_ch = chords[i - 1]
            elif si > 0 and section_map[si - 1][1]:
                prev_ch = section_map[si - 1][1][-1]
            break

    shown_sel = _player_facing_chord(session_state, sel_chord, concert_key=concert_key)
    shown_next = _player_facing_chord(session_state, next_ch, concert_key=concert_key)
    shown_prev = _player_facing_chord(session_state, prev_ch, concert_key=concert_key)
    guide = analyze_chord_for_harmony_map(
        shown_sel or sel_chord,
        improv_ctx=improv_ctx,
        section=sel_section,
        next_chord=shown_next,
        prev_chord=shown_prev,
    )
    try:
        from harmonic_spelling import assert_mission_spelling_consistency

        scale_text = " ".join(guide.scale_lines or [])
        assert_mission_spelling_consistency(
            session_state,
            chord_symbol=shown_sel or sel_chord,
            stable_tones=guide.stable_tones,
            coaching_tones=list(guide.stable_tones),
            color_tones=[c.note for c in guide.color_tones],
            scale_note_text=scale_text,
        )
    except ImportError:
        pass

    st.markdown(
        f'<div class="hm-guide-card">'
        f'<p style="margin:0 0 0.35rem 0;font-weight:850;font-size:1.05rem;">'
        f"Chord: {html.escape(guide.chord)}</p>"
        f'<p style="margin:0;color:#64748b;font-size:0.88rem;">'
        f"Section: {html.escape(guide.section)} · {html.escape(live_inst)} · "
        f"{html.escape(live_level)} · {html.escape(live_focus)}</p></div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"**Stable chord tones:** "
        f"<span class='hm-stable'>{', '.join(html.escape(n) for n in guide.stable_tones)}</span>",
        unsafe_allow_html=True,
    )

    if guide.color_tones:
        st.markdown("**Color tones**")
        for ct in guide.color_tones:
            st.markdown(
                f"- **{html.escape(ct.note)}** = {html.escape(ct.role)} — {html.escape(ct.effect)}"
            )

    if guide.avoid_notes and live_level != "Beginner":
        st.markdown("**Avoid / use carefully**")
        for av in guide.avoid_notes:
            st.markdown(
                f"- **{html.escape(av.note)}** — {html.escape(av.reason)}"
            )

    st.markdown(guide.phrase_idea)
    if guide.focus_note:
        st.caption(guide.focus_note)

    if guide.scale_lines:
        st.markdown("**Scales (with notes)**")
        for line in guide.scale_lines:
            st.markdown(line)

    st.markdown("**Instrument tips**")
    for tip in guide.instrument_tips:
        st.markdown(f"- {tip}")

    if next_chord := shown_next:
        st.caption(f"Next chord in this section: **{html.escape(next_chord)}**")


def _tab_deep_harmony(
    st: Any,
    *,
    session_state: dict,
    improv_ctx: ImprovSessionContext,
    song_data: dict,
    genre: str,
) -> None:
    from deep_harmonic_analyzer_ui import render_deep_harmonic_analyzer_tab

    try:
        from song_creative_focus import hydrate_creative_pages_from_song_focus

        hydrate_creative_pages_from_song_focus(session_state, tab="Deep Harmony")
    except ImportError:
        pass
    concert_key, chart_key = _coherent_improv_key_pair(session_state, improv_ctx)
    concert_sections = _authoritative_concert_sections(session_state, improv_ctx.sections)
    _sel = session_state.get("selected_song") if isinstance(session_state.get("selected_song"), dict) else {}
    improv_ctx = replace(
        improv_ctx,
        song_title=str((_sel or {}).get("title") or session_state.get("song") or improv_ctx.song_title),
        artist=str((_sel or {}).get("artist") or improv_ctx.artist),
        key_center=concert_key,
        display_key=chart_key,
        sections=concert_sections,
        progression_flat=flatten_sections(
            concert_sections,
            section_names=list(improv_ctx.section_order) or None,
        ),
        section_order=list(improv_ctx.section_order) or list(concert_sections.keys()),
    )
    render_deep_harmonic_analyzer_tab(
        st,
        session_state=session_state,
        improv_ctx=improv_ctx,
        song_data=song_data,
        genre=genre,
        key_prefix="improv_deep_harmony",
    )


def _tab_metrics_ai(
    st: Any,
    *,
    session_state: dict,
    improv_ctx: ImprovSessionContext | None = None,
    on_open_analysis: Callable[[], None] | None,
) -> None:
    from mission_analysis_ui import render_ai_improv_metrics_selector

    st.markdown(creative_tool_heading_markdown("Metrics & AI"))
    if improv_ctx:
        st.caption(
            f"Scores will judge your take against **{html.escape(improv_ctx.song_title)}** "
            f"in **{html.escape(improv_ctx.display_key)}** · "
            f"{html.escape(improv_ctx.instrument)} · {html.escape(improv_ctx.level)} · "
            f"{html.escape(improv_ctx.focus)}"
        )

    selected = render_ai_improv_metrics_selector(st, session_state, key_prefix="improv")

    if not selected:
        st.info(
            "Select at least one metric above, then open Upload Analysis to record or upload a take."
        )

    st.markdown("---")
    st.markdown("##### How scoring works")
    for line in ai_feedback_preview_lines():
        st.markdown(f"- {line}")

    if on_open_analysis:
        if st.button(
            "Open Upload Analysis",
            key="improv_to_analysis",
            type="primary",
            use_container_width=True,
        ):
            from mission_analysis_ui import prepare_metrics_upload_workflow

            prepare_metrics_upload_workflow(session_state)
            on_open_analysis()

    result = session_state.get("last_analysis_result")
    if result and result.get("ok") and result.get("mission_results"):
        from mission_analysis_ui import (
            ANALYSIS_RETURN_TO_METRICS,
            clear_analysis_workflow_flags,
            render_improv_metrics_results,
        )

        render_improv_metrics_results(st, result)
        if session_state.get(ANALYSIS_RETURN_TO_METRICS):
            clear_analysis_workflow_flags(session_state)

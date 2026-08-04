"""Streamlit UI — Improvisation Intelligence (Creative Lab)."""

from __future__ import annotations

import html
import re
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
    MISSION_PRACTICE_LICK_KEY,
    MissionExample,
    PRACTICE_MISSIONS,
    apply_mission_motif_transform,
    generate_mission_example,
    load_mission_example,
    mission_example_for_display,
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


def _motif_notation_reference_key(improv_ctx: ImprovSessionContext) -> str:
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
    IMPROV_ENTRY_MODES,
    IMPROV_SONG_SOURCES,
    IMPROV_TAB_NAMES,
    apply_improv_song_source,
    flush_pending_improv_song_source,
    init_improvisation_state,
    resolve_improv_song_preview,
    resolve_improv_song_source,
    ensure_improv_entry_mode_restored,
    ensure_improv_intelligence_tab_restored,
    ensure_creative_widgets_from_backing_context,
)
from songs.picker_session import mark_improv_tab_user_touched


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
    from studio_page_persistence import ensure_creative_improv_initialized

    ensure_creative_improv_initialized(session_state, is_custom_active=is_custom)
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
    if _creative_tab in ("Entry & Jam", "Missions", "Metrics & AI"):
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
    song_title = str(ctx.get("song") or "Song")
    artist = str(ctx.get("artist") or "")

    try:
        from app_ui import (
            inject_creative_studio_styles,
            render_creative_studio_panel_header,
        )
    except Exception:
        inject_creative_studio_styles = lambda _st: None  # type: ignore
        render_creative_studio_panel_header = lambda *_a, **_k: None  # type: ignore

    inject_creative_studio_styles(st)

    _section_order = list(song_data.get("section_order") or ctx.get("section_order") or [])
    improv_ctx = ImprovSessionContext(
        song_title=song_title,
        artist=artist,
        key_center=str(ctx.get("practice_concert_key") or ctx.get("concert_key") or chart_key or "C"),
        display_key=chart_key,
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
        active_tab = st.radio(
            "Improvisation section",
            list(IMPROV_TAB_NAMES),
            horizontal=True,
            key="improv_intelligence_tab",
            label_visibility="collapsed",
            on_change=mark_improv_tab_user_touched,
            kwargs={"session_state": session_state},
        )
        st.markdown("</div>", unsafe_allow_html=True)

        if active_tab == "Entry & Jam":
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
        elif active_tab == "Live Coach":
            _tab_live_coach(st, session_state=session_state, improv_ctx=improv_ctx)
        elif active_tab == "Phrase / Motif":
            _tab_motif(
                st,
                session_state=session_state,
                improv_ctx=improv_ctx,
                level=level,
                instrument=instrument,
                bpm=bpm,
            )
        elif active_tab == "Missions":
            _tab_missions(
                st,
                session_state=session_state,
                improv_ctx=improv_ctx,
                bpm=bpm,
                on_open_backing=on_open_backing,
                on_open_practice=on_open_practice,
                on_open_analysis=on_open_analysis,
            )
        elif active_tab == "Harmony Map":
            _tab_harmony_map(st, session_state=session_state, improv_ctx=improv_ctx)
        elif active_tab == "Deep Harmony":
            _tab_deep_harmony(
                st,
                session_state=session_state,
                improv_ctx=improv_ctx,
                song_data=song_data,
                genre=genre,
            )
        elif active_tab == "Metrics & AI":
            _tab_metrics_ai(
                st,
                session_state=session_state,
                improv_ctx=improv_ctx,
                on_open_analysis=on_open_analysis,
            )

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

    ensure_improv_entry_mode_restored(session_state)
    entry = st.radio(
        "Improvisation entry mode",
        list(IMPROV_ENTRY_MODES),
        horizontal=True,
        key="improv_entry_mode",
        label_visibility="collapsed",
        on_change=_on_entry_mode_change,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if entry == "Song-Based Improvisation":
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
                on_change=_sync_song_source,
                label_visibility="collapsed",
            )
            st.markdown("</div>", unsafe_allow_html=True)

        song_preview = resolve_improv_song_preview(session_state)
        preview_sections = dict(song_preview.get("sections") or {})
        if source == "Custom progression":
            pass  # preview_sections already from custom_session bucket
        elif source == "Active song":
            if not preview_sections and not is_custom:
                preview_sections = improv_ctx.sections
        elif not preview_sections:
            preview_sections = improv_ctx.sections

        if source == "Active song":
            flat_preview = [c for chs in preview_sections.values() for c in chs if str(c).strip()]
            chord_count = len(flat_preview) if flat_preview else len(improv_ctx.progression_flat)
            if render_creative_song_context_card:
                render_creative_song_context_card(
                    st,
                    title=str(song_preview.get("title") or improv_ctx.song_title),
                    artist=str(song_preview.get("artist") or improv_ctx.artist),
                    display_key=str(song_preview.get("display_key") or improv_ctx.display_key),
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
            render_creative_progression_block(st, session_state, preview_sections)

        _render_open_practice_backing_row(
            st,
            on_open_backing=on_open_backing,
            on_open_practice=on_open_practice,
            workflow="song",
        )

    elif entry == "Style Jam Mode":
        st.markdown('<p class="ui-creative-section-label">Style jam generator</p>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.selectbox(
                "Style",
                list(STYLE_JAM_STYLES),
                key="improv_style",
                on_change=on_improv_style_jam_setting_change,
            )
            try:
                _style_key_opts = creative_major_shape_key_options(
                    session_state,
                    selected=str(session_state.get("improv_style_key") or "C"),
                )
            except Exception:
                _style_key_opts = list(CREATIVE_MAJOR_KEY_OPTIONS)
            st.selectbox(
                "Concert Key",
                _style_key_opts,
                key="improv_style_key",
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
                step=5,
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
        if st.button("Generate progression", type="primary", key="improv_gen_style"):
            from creative_key_sync import (
                IMPROV_STYLE_KEY_TRACKER,
                apply_creative_concert_key,
                sync_creative_style_jam_meta,
            )

            k = str(session_state.get("improv_style_key") or "C")
            style = str(session_state.get("improv_style") or STYLE_JAM_STYLES[0])
            if "d minor" in (prompt or "").lower():
                k = "Dm"
                try:
                    from session_widget_safe import safe_session_assign

                    safe_session_assign(
                        session_state, "improv_style_key", k, widget_safe=True
                    )
                except ImportError:
                    session_state["improv_style_key"] = k
            session_state["improv_generated_sections"] = generate_style_progression(
                style=style,
                key_center=k,
                difficulty=str(session_state.get("improv_difficulty") or "Intermediate"),
                mood=str(session_state.get("improv_mood") or "Mellow"),
            )
            sync_creative_style_jam_meta(session_state)
            apply_creative_concert_key(session_state, k, st_like=st)
            session_state[IMPROV_STYLE_KEY_TRACKER] = k
            try:
                from creative_session_state import sync_creative_session_from_session

                sync_creative_session_from_session(session_state)
            except ImportError:
                pass
            st.rerun()

        gen = session_state.get("improv_generated_sections")
        if gen:
            _style_label = str(session_state.get("improv_style") or "Style jam")
            _key_label = str(session_state.get("improv_style_key") or "C")
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
        st.markdown("#### 🌙 Jam Session Generator")
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
                "Groove style", list(STYLE_JAM_STYLES), key="improv_jam_style"
            )
        with e2:
            try:
                from creative_key_sync import creative_major_shape_key_options

                _jam_key_opts = creative_major_shape_key_options(
                    session_state,
                    selected=str(session_state.get("improv_jam_key") or "C"),
                )
            except ImportError:
                _jam_key_opts = list(CREATIVE_MAJOR_KEY_OPTIONS)
            key_c = st.selectbox(
                "Concert Key",
                _jam_key_opts,
                key="improv_jam_key",
                on_change=on_improv_jam_key_change,
            )
            tempo = st.slider(
                "Tempo",
                70,
                180,
                key="improv_jam_bpm",
                step=5,
                on_change=on_improv_jam_setting_change,
            )
            st.selectbox(
                "Atmosphere",
                list(MOOD_OPTIONS),
                key="improv_jam_mood",
                on_change=on_improv_jam_setting_change,
            )

        if st.button("Generate jam session", type="primary", key="improv_gen_jam"):
            jam = generate_jam_session(
                ensemble=ensemble,
                style=style,
                key_center=key_c,
                tempo=int(session_state.get("improv_jam_bpm") or 110),
                mood=str(session_state.get("improv_jam_mood") or "Mellow"),
            )
            try:
                from creative_session_state import capture_jam_session_generator_state

                capture_jam_session_generator_state(
                    session_state,
                    ensemble=ensemble,
                    style=style,
                    concert_key=str(key_c or "C"),
                    bpm=int(session_state.get("improv_jam_bpm") or 110),
                    mood=str(session_state.get("improv_jam_mood") or "Mellow"),
                    jam_session=jam,
                    st_like=st,
                )
            except ImportError:
                session_state["improv_jam_session"] = jam
            st.rerun()

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
        if on_open_backing and st.button(
            "🎧 Open in Backing Studio",
            key="improv_to_backing_jam",
            type="primary",
            use_container_width=True,
        ):
            on_open_backing()
        return

    c1, c2 = st.columns([2, 1])
    with c1:
        if on_open_backing and st.button(
            "🎧 Open in Backing Studio",
            key="improv_to_backing",
            type="primary",
            use_container_width=True,
        ):
            on_open_backing()
    with c2:
        if on_open_practice and st.button(
            "🎯 Send to Practice Page",
            key="improv_to_practice",
            use_container_width=True,
        ):
            on_open_practice()


def _tab_live_coach(st: Any, *, session_state: dict, improv_ctx: ImprovSessionContext) -> None:
    st.markdown("#### Real-time improvisation coach")
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
    cur, idx = _selected_chord(session_state, chords)
    _render_section_chord_map(
        st,
        section_map,
        session_state,
        key_prefix="improv_live",
        source_id=_improv_source_id(session_state, improv_ctx),
        key_center=improv_ctx.key_center,
    )

    nxt = chords[idx + 1] if idx + 1 < len(chords) else ""
    ref_key = improv_ctx.display_key or improv_ctx.key_center
    insight = chord_coach_insight(
        cur,
        key_center=ref_key,
        next_chord=nxt,
        instrument=live_inst,
        level=live_level,
    )
    _render_chord_coach_card(st, insight, reference_key=ref_key)

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
    st.markdown("#### Phrase / motif training")
    st.caption("Tap a chord → get a short phrase → transform it → view notation or TAB.")

    try:
        from creative_mission_artifact_persistence import project_mission_artifacts_from_canonical
        from creative_tab_tool_persistence import selector_hydration_complete

        if selector_hydration_complete(session_state):
            project_mission_artifacts_from_canonical(session_state, overwrite=True)
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

    cur, _idx = _selected_chord(session_state, chords)

    g0, g1, g2, g3 = st.columns(4)
    with g0:
        if st.button(
            f"Generate motif for {cur}",
            type="primary",
            key="improv_gen_motif_chord",
            use_container_width=True,
        ):
            session_state["improv_motif"] = generate_musical_phrase(
                cur, key_center=improv_ctx.key_center, level=level, kind="creative"
            )
            _clear_motif_outputs(session_state)
            _persist_motif_artifact(session_state, interaction="motif_generate_chord")
            st.rerun()
    with g1:
        if st.button("New motif", key="improv_motif_new", use_container_width=True):
            session_state["improv_motif"] = generate_musical_phrase(
                cur,
                key_center=improv_ctx.key_center,
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
                key_center=improv_ctx.key_center,
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
                key_center=improv_ctx.key_center,
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
                    key_center=improv_ctx.key_center,
                )
                _refresh_motif_output_after_transform(
                    session_state,
                    key_center=_motif_notation_reference_key(improv_ctx),
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
    """Keep selection keyed by global chord index (section + position), not chord name."""
    _migrate_ii_chord_selection(session_state)
    if not chords:
        return
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
    session_state[II_SELECTED_CHORD] = chord
    if section_map:
        sec, _ = section_and_chord_at_global_index(section_map, idx)
        if sec:
            session_state[II_SELECTED_SECTION] = sec
            session_state[II_SELECTED_CHORD_LABEL] = f"{sec} · {chord}"
        else:
            session_state.setdefault(II_SELECTED_SECTION, "")
            session_state[II_SELECTED_CHORD_LABEL] = chord
    else:
        session_state.setdefault(II_SELECTED_SECTION, "")
        if not str(session_state.get(II_SELECTED_CHORD_LABEL) or "").strip():
            session_state[II_SELECTED_CHORD_LABEL] = chord
    session_state["improv_mission_chord_options"] = list(chords)


def _selected_chord(session_state: dict, chords: list[str]) -> tuple[str, int]:
    idx = int(session_state.get(II_SELECTED_CHORD_INDEX, 0))
    idx = max(0, min(idx, len(chords) - 1))
    return chords[idx], idx


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
        from creative_mission_config_persistence import sync_mission_target_from_canonical

        sel_idx = sync_mission_target_from_canonical(session_state)
    except ImportError:
        sel_idx = int(session_state.get(II_SELECTED_CHORD_INDEX, 0))
    src = _safe_widget_key_part(source_id)

    def _chord_tile_on_click(ch: str, label: str, gidx: int, btn_key: str) -> None:
        import streamlit as st

        ss = st.session_state
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
                    is_sel = gidx == sel_idx
                    st.button(
                        ch,
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
        st.markdown("#### Mission Practice")
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


def _mission_improv_ctx_from_session(session_state: dict) -> ImprovSessionContext | None:
    from improvisation_motif import flatten_section_map, resolve_improv_sections

    song_title = str(session_state.get("song") or "Song")
    artist = str(session_state.get("artist") or "")
    chart_key = str(session_state.get("display_key") or session_state.get("chart_key") or "C")
    ctx = ImprovSessionContext(
        song_title=song_title,
        artist=artist,
        key_center=str(session_state.get("concert_key") or chart_key),
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
    from improvisation_motif import flatten_section_map, resolve_improv_sections
    from improvisation_missions import (
        generate_mission_example,
        generate_mission_example_distinct,
        load_mission_example,
        mission_example_artifact_id,
        mission_example_fingerprint,
        motif_material_fingerprint,
        MISSION_NEW_IDEA_DIAG_KEY,
    )

    improv_ctx = _mission_improv_ctx_from_session(session_state)
    if improv_ctx is None:
        return
    section_map = resolve_improv_sections(session_state, improv_ctx)
    chords = flatten_section_map(section_map) if section_map else []
    if not chords:
        return
    _ensure_chord_selection(session_state, chords, section_map)
    cur_chord, chord_idx = _selected_chord(session_state, chords)
    section_label = str(session_state.get(II_SELECTED_SECTION) or "Progression")
    mission = str(
        session_state.get("improv_mission_pick")
        or session_state.get("improv_active_mission")
        or ""
    ).strip()
    if not mission:
        return
    live_inst = str(session_state.get("instrument") or improv_ctx.instrument)
    live_level = str(session_state.get("level") or improv_ctx.level)
    live_focus = str(session_state.get("focus") or improv_ctx.focus)
    bpm = int(session_state.get("backing_track_bpm") or improv_ctx.bpm or 100)

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
    session_state[MISSION_NEW_IDEA_DIAG_KEY] = {
        "previous_fp": prev_fp,
        "generated_fp": gen_fp,
        "committed_fp": gen_fp,
        "displayed_fp": gen_fp,
        "retried": retried,
        "retry_count": retries,
        "previous_material_fp": prev_mat,
        "generated_material_fp": motif_material_fingerprint(example.motif),
    }
    try:
        from studio_page_persistence import save_page_snapshot

        save_page_snapshot(session_state, "creative")
    except ImportError:
        pass


def _on_mission_gen_normal() -> None:
    import streamlit as st

    _run_mission_example_generate(st.session_state, "normal")


def _on_mission_gen_easier() -> None:
    import streamlit as st

    _run_mission_example_generate(st.session_state, "easier")


def _on_mission_gen_harder() -> None:
    import streamlit as st

    _run_mission_example_generate(st.session_state, "harder")


def _on_mission_gen_new_idea() -> None:
    import streamlit as st

    _run_mission_example_generate(st.session_state, "new")


def _maybe_refresh_mission_example_outputs(
    session_state: dict,
    example: MissionExample,
    *,
    instrument: str,
    bpm: int,
) -> MissionExample:
    from improvisation_missions import mission_example_fingerprint, mission_example_for_display

    fp = mission_example_fingerprint(example)
    if session_state.get("_mission_example_output_fp") == fp:
        return example
    refreshed = mission_example_for_display(example, instrument=instrument, bpm=bpm)
    session_state["_mission_example_output_fp"] = mission_example_fingerprint(refreshed)
    return refreshed


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
    from practice_setup_controls import (
        DEFAULT_INSTRUMENT_OPTIONS,
        render_setup_quick_controls,
    )

    try:
        from creative_mission_config_persistence import project_mission_config_from_canonical_before_widgets

        project_mission_config_from_canonical_before_widgets(session_state)
    except ImportError:
        pass

    try:
        from creative_mission_artifact_persistence import project_mission_artifacts_from_canonical
        from creative_tab_tool_persistence import selector_hydration_complete

        if selector_hydration_complete(session_state):
            project_mission_artifacts_from_canonical(session_state, overwrite=False)
    except ImportError:
        pass

    st.markdown("#### Practice missions")
    st.caption(
        f"Interactive coach for **{html.escape(improv_ctx.song_title)}** "
        f"({html.escape(improv_ctx.artist)}) · key **{html.escape(improv_ctx.display_key)}**"
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
    _render_section_chord_map(
        st,
        section_map,
        session_state,
        key_prefix="improv_mission",
        source_id=_improv_source_id(session_state, improv_ctx),
        key_center=improv_ctx.key_center,
    )
    cur_chord, _ = _selected_chord(session_state, chords)
    section_label = str(session_state.get(II_SELECTED_SECTION) or "Progression")

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

    example = load_mission_example(session_state, improv_ctx)
    if example and example.mission != mission:
        example = None
    if example and (
        example.chord != cur_chord
        or str(example.section or "").strip() != str(section_label or "").strip()
    ):
        example = None

    def _open_mission_backing(*, with_practice_lick: bool = False) -> None:
        if not on_open_backing:
            return
        if with_practice_lick and example:
            style_meta = session_state.get("improv_style_meta") or {}
            groove = str(
                session_state.get("improv_groove")
                or session_state.get("backing_groove_style")
                or style_meta.get("backing_style")
                or style_meta.get("style")
                or "Auto"
            )
            meter = str(
                session_state.get("backing_time_signature")
                or style_meta.get("meter")
                or "4/4"
            )
            store_mission_practice_lick_for_backing(
                session_state,
                example=example,
                mission_title=mission,
                instrument=live_inst,
                bpm=bpm,
                groove=groove,
                meter=meter,
                song_title=improv_ctx.song_title,
                section_label=section_label,
                persist_artifact=False,
            )
            queue_mission_practice_lick_handoff(session_state)
            try:
                from mission_backing_handoff_persistence import begin_mission_backing_handoff

                begin_mission_backing_handoff(
                    session_state,
                    navigation_callback="_open_mission_backing",
                    with_practice_lick=True,
                )
            except ImportError:
                pass
        elif not with_practice_lick:
            session_state.pop(MISSION_PRACTICE_LICK_KEY, None)
        session_state[IMPROV_MISSION_BACKING_HANDOFF] = True
        on_open_backing()

    if not example:
        if on_open_backing and st.button(
            nav_icon_button_label("backing") + " Jam",
            key="improv_mission_over_backing",
            type="primary",
            use_container_width=True,
        ):
            _open_mission_backing(with_practice_lick=False)

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
        practice_in_jam = st.checkbox(
            "Practice this lick in Backing Jam",
            value=True,
            key="improv_mission_practice_lick_toggle",
            help="Optional: open Backing Jam with this example for reference — not required for scoring.",
        )
        if on_open_backing and st.button(
            "▶ Practice in Backing Jam" if practice_in_jam else nav_icon_button_label("backing") + " Jam",
            key="improv_mission_over_backing_bottom",
            type="primary",
            use_container_width=True,
        ):
            _open_mission_backing(with_practice_lick=practice_in_jam)

        st.caption(
            f"Inspiration variant: **{example.variant}** · "
            f"notation shown for **{html.escape(live_inst)}** — scoring uses your mission, not these exact pitches."
        )

    st.markdown("---")
    try:
        from mission_upload_recording_ui import render_mission_recording_upload_expander

        dev_mode = bool(session_state.get("_dev_mode") or session_state.get("dev_mode"))
        render_mission_recording_upload_expander(
            st,
            session_state,
            key_prefix="improv_mission_upload",
            on_open_upload_analysis=_open_mission_upload_analysis if on_open_analysis else None,
            dev_mode=dev_mode,
        )
    except ImportError:
        pass

    try:
        from improvisation_missions import MISSION_NEW_IDEA_DIAG_KEY
        from creative_mission_artifact_persistence import collect_creative_mission_artifact_diagnostics

        if dev_mode:
            diag = dict(session_state.get(MISSION_NEW_IDEA_DIAG_KEY) or {})
            ex = session_state.get("improv_mission_example") or {}
            if isinstance(ex, dict):
                from improvisation_missions import mission_example_fingerprint, load_mission_example

                loaded = load_mission_example(session_state, improv_ctx)
                diag["displayed_fp"] = mission_example_fingerprint(loaded)
            diag["artifact"] = collect_creative_mission_artifact_diagnostics(session_state)
            with st.expander("Developer · mission example / artifact", expanded=False):
                st.json(diag)
    except ImportError:
        pass


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

    st.markdown("#### Harmony map")
    st.caption(
        f"**{html.escape(improv_ctx.song_title)}** · key **{html.escape(improv_ctx.display_key)}** · "
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
    improv_ctx = ImprovSessionContext(
        song_title=improv_ctx.song_title,
        artist=improv_ctx.artist,
        key_center=improv_ctx.key_center,
        display_key=improv_ctx.display_key,
        instrument=live_inst,
        level=live_level,
        focus=live_focus,
        sections=improv_ctx.sections,
        bpm=improv_ctx.bpm,
        style_label=improv_ctx.style_label,
        progression_flat=improv_ctx.progression_flat,
        section_order=list(improv_ctx.section_order),
    )

    section_map = deduped_section_chords(
        improv_ctx.sections,
        section_names=list(improv_ctx.section_order) or None,
    )
    if not section_map:
        st.info("No chords in the active chart — pick a song or custom progression first.")
        return

    st.markdown(HARMONY_MAP_CHIP_CSS, unsafe_allow_html=True)

    sel_section = str(session_state.get("harmony_map_section") or "")
    sel_chord = str(session_state.get("harmony_map_chord") or "")

    src = _safe_widget_key_part(improv_ctx.song_title or "song")
    for sec_label, chords in section_map:
        chips = []
        for ch in chords:
            selected = sel_section == sec_label and sel_chord == ch
            chips.append(
                f'<span class="hm-chord-chip{" selected" if selected else ""}">'
                f"{html.escape(ch)}</span>"
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
                if st.button(
                    ch,
                    key=f"hm_pick_{src}_{_safe_widget_key_part(sec_label)}_{i}_{_safe_widget_key_part(ch)}",
                    type="primary" if sel_section == sec_label and sel_chord == ch else "secondary",
                    use_container_width=True,
                ):
                    session_state["harmony_map_section"] = sec_label
                    session_state["harmony_map_chord"] = ch
                    try:
                        from creative_context_snapshot_persistence import handle_user_harmony_map_context_change

                        handle_user_harmony_map_context_change(
                            session_state,
                            section=sec_label,
                            chord=ch,
                        )
                    except ImportError:
                        _touch_creative_workspace(session_state)
                    st.rerun()

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

    guide = analyze_chord_for_harmony_map(
        sel_chord,
        improv_ctx=improv_ctx,
        section=sel_section,
        next_chord=next_ch,
        prev_chord=prev_ch,
    )

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

    if next_chord := next_ch:
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

    st.markdown("#### AI Metrics / Mission Criteria")
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

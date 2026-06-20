"""Custom Progression — click chords to build a song, then open in Backing Track."""

from __future__ import annotations

from app_ui import nav_icon_button_label


def _pending_chord_key(section: str) -> str:
    return f"cpl_pending_chord_{section}"


def _last_bars_key(section: str) -> str:
    return f"cpl_last_bars_{section}"


def _render_subbar_timing_panel(
    home_entries: list[dict],
    *,
    edit_section: str,
    pending_key: str,
    save,
) -> None:
    """Quick buttons that turn the last bar of the section into a
    subdivided / pushed bar (half-bar, thirds, quarters, push)."""
    import streamlit as st

    from chord_subdivisions import Subdivision, join_weighted_subdivisions

    if not home_entries:
        return

    import portfolio_polish as pp

    with st.expander(
        "Sub-bar timing (half-bar, beats, pushed chord)",
        expanded=pp.expander_default(st),
    ):
        pp.instructional_caption(
            st,
            "Add a chord, then click one of these to fold it into the LAST bar.",
        )
        pending = st.session_state.get(pending_key)
        if not pending:
            st.info(
                "Pick a chord above first, then come back here. "
                "Example: select **G**, click **Half-bar** to make the last bar `C:2|G:2`."
            )
            return

        last_entry = home_entries[-1]
        last_chord = str(last_entry.get("chord", "")).strip()
        if "|" in last_chord:
            st.caption(
                f"Last bar is already subdivided ({last_chord}). "
                "Re-clicking a button below replaces that subdivision."
            )
        prev_head = last_chord.split("|", 1)[0].split(":", 1)[0] or "C"

        def _apply_token(token: str) -> None:
            home_entries[-1] = {"chord": token, "bars": 1}
            st.session_state.pop(pending_key, None)
            save()
            st.rerun()

        section_tag = str(edit_section or "section").replace(" ", "_")
        cols = st.columns(4)
        with cols[0]:
            if st.button(
                "Half-bar",
                key=f"cpl_sub_half_{section_tag}",
                use_container_width=True,
                help="C → C:2|G:2 (4/4) or C:1.5|G:1.5 (3/4)",
            ):
                _apply_token(
                    join_weighted_subdivisions([
                        Subdivision(prev_head, 2.0, False),
                        Subdivision(pending, 2.0, False),
                    ])
                )
        with cols[1]:
            if st.button(
                "Thirds (3/4 group)",
                key=f"cpl_sub_thirds_{section_tag}",
                use_container_width=True,
                help="Fmaj7 → Am7 → C/D, one chord per beat (Piano Man style)",
            ):
                _apply_token(
                    join_weighted_subdivisions([
                        Subdivision(prev_head, 1.0, False),
                        Subdivision(prev_head, 1.0, False),
                        Subdivision(pending, 1.0, False),
                    ])
                )
        with cols[2]:
            if st.button(
                "Quarters (4 chords/bar)",
                key=f"cpl_sub_quarters_{section_tag}",
                use_container_width=True,
                help="1 chord per beat in 4/4",
            ):
                _apply_token(
                    join_weighted_subdivisions([
                        Subdivision(prev_head, 1.0, False),
                        Subdivision(prev_head, 1.0, False),
                        Subdivision(prev_head, 1.0, False),
                        Subdivision(pending, 1.0, False),
                    ])
                )
        with cols[3]:
            if st.button(
                "Push (last 1/2 beat)",
                key=f"cpl_sub_push_{section_tag}",
                use_container_width=True,
                help="Anticipates the next chord on the last 8th note",
            ):
                _apply_token(
                    join_weighted_subdivisions([
                        Subdivision(prev_head, 3.5, False),
                        Subdivision(pending, 0.5, True),
                    ])
                )


def render_custom_progression_lab_page() -> None:
    import html

    import streamlit as st

    from custom_progression_lab import (
        CHORD_QUICK_EDIT_KEYS,
        CPL_ACTIVE_KEY,
        CPL_BUILDER_VERSION,
        CPL_PROGRESSION_STYLES,
        CPL_SAVED_KEY,
        CPL_TIME_SIGNATURES,
        CPL_UI_SECTION_ORDER,
        apply_cpl_session_progression,
        apply_quick_chord_edit,
        build_style_preset_entries,
        clear_all_cpl_sections,
        build_cpl_developer_diagnostics,
        cpl_active_from_session,
        cpl_draft_written_key,
        cpl_save_draft,
        cpl_section_progression_view,
        cpl_steps_strip_html,
        cpl_whole_song_progression_view,
        deep_copy_sections,
        delete_progression,
        display_entries_for_section,
        display_sections_for_key,
        ensure_all_cpl_sections,
        cpl_draft_preview_key,
        ensure_cpl_draft_home_tracking,
        ensure_cpl_widget_keys_initialized,
        reset_cpl_widget_initialization,
        ensure_original_structure,
        entries_chord_tiles_html,
        filled_section_names,
        flatten_sections_to_events,
        format_key_label,
        CPL_KEY_OPTIONS,
        invalidate_cpl_derived_outputs,
        list_saved_progression_names,
        load_saved_progression,
        migrate_cpl_builder_version,
        normalize_chord_symbol,
        preset_button_label,
        prepare_cpl_backing_handoff,
        presets_for_style,
        progression_is_empty,
        purge_cpl_ephemeral_widget_keys,
        save_progression,
        section_is_empty,
        simple_chords_for_key,
        song_structure_overview_html,
        start_new_progression,
        sync_cpl_draft_widgets_to_active,
        written_home_key,
    )
    from progression_helpers import (
        default_active_progression,
        invalidate_backing_cache,
        session_display_key,
    )
    from jazz_demo_charts import build_demo_progression, demo_presets_for_style
    from songs.music_source import (
        is_custom_progression,
        note_active_source_change,
        queue_custom_active_song_activation,
        set_custom_source,
    )
    try:
        from app_ui import (
            custom_song_preview_card_html,
            inject_custom_builder_styles,
            render_custom_builder_panel_header,
        )
    except Exception:
        inject_custom_builder_styles = lambda _st: None  # type: ignore
        render_custom_builder_panel_header = lambda *_a, **_k: None  # type: ignore
        custom_song_preview_card_html = lambda **_k: ""  # type: ignore

    inject_custom_builder_styles(st)

    if toast_title := st.session_state.pop("_cpl_activation_toast", None):
        st.success(f"**{toast_title}** is now your active song.")

    purge_cpl_ephemeral_widget_keys(st.session_state)

    if st.session_state.get("cpl_builder_version") != CPL_BUILDER_VERSION:
        migrate_cpl_builder_version(st.session_state)

    if CPL_ACTIVE_KEY not in st.session_state:
        st.session_state[CPL_ACTIVE_KEY] = default_active_progression()
    if CPL_SAVED_KEY not in st.session_state:
        st.session_state[CPL_SAVED_KEY] = {}

    active = cpl_active_from_session(st.session_state)
    active = ensure_cpl_draft_home_tracking(st, active)
    force_widget_seed = False
    if st.session_state.pop("_cpl_reseed_widgets_from_active", False):
        reset_cpl_widget_initialization(st.session_state)
        force_widget_seed = True
    active = ensure_cpl_widget_keys_initialized(
        st.session_state,
        active,
        force=force_widget_seed,
    )

    display_key = session_display_key(st.session_state)
    original_key = cpl_draft_written_key(active)
    preview_key = cpl_draft_preview_key(active)
    preview_label = format_key_label(preview_key)
    display_label = format_key_label(display_key)
    original_label = preview_label
    home_ns = original_key.replace("#", "s").replace("b", "f")
    finished = bool(st.session_state.get("cpl_finished"))
    saved = st.session_state[CPL_SAVED_KEY]
    prog_title = str(active.get("name") or "My Progression").strip() or "My Progression"

    if st.session_state.get("cpl_edit_section") not in CPL_UI_SECTION_ORDER:
        st.session_state["cpl_edit_section"] = "Verse"

    def _save(sections: dict | None = None, *, persist: bool = True) -> None:
        nonlocal active
        active = cpl_save_draft(
            st.session_state,
            active,
            sections,
            persist=persist,
            st=st if persist else None,
        )

    def _open_backing() -> None:
        _save(None)
        set_custom_source(st.session_state)
        note_active_source_change(st, invalidate_backing=invalidate_backing_cache)
        prepare_cpl_backing_handoff(st.session_state, active, section=None)
        from studio_nav_history import navigate_studio_page
        from studio_scroll_anchors import (
            ANCHOR_BACKING_MAIN_CONTROLS,
            set_pending_anchor,
        )

        set_pending_anchor(st.session_state, ANCHOR_BACKING_MAIN_CONTROLS)
        navigate_studio_page(st.session_state, "backing")
        st.rerun()

    def _home_sections() -> dict:
        return ensure_all_cpl_sections(cpl_active_from_session(st.session_state).get("original_sections"))

    def _activate_custom_song(*, toast: bool = True) -> None:
        nonlocal active
        _save(None)
        active = cpl_active_from_session(st.session_state)
        queue_custom_active_song_activation(
            st,
            active,
            toast_title=prog_title if toast else None,
        )
        st.rerun()

    def _open_practice() -> None:
        _save(None)
        set_custom_source(st.session_state)
        note_active_source_change(st, invalidate_backing=invalidate_backing_cache)
        from studio_nav_history import navigate_studio_page

        navigate_studio_page(st.session_state, "practice")
        st.rerun()

    with st.container(key="custom_song_builder_panel", border=False):
        render_custom_builder_panel_header(st, working_title=prog_title)
        st.markdown('<div class="cpl-title-panel">', unsafe_allow_html=True)
        info_a, info_b = st.columns([2, 1])
        with info_a:
            st.text_input(
                "Song title",
                key="cpl_title_input",
                placeholder="e.g. My Ballad",
            )
        with info_b:
            st.text_input(
                "Artist (optional)",
                key="cpl_artist_input",
                placeholder="Your name",
            )

        row2 = st.columns([1, 1, 1])
        with row2[0]:
            st.radio(
                "Meter",
                CPL_TIME_SIGNATURES,
                horizontal=True,
                key="cpl_time_signature",
            )
        with row2[1]:
            st.slider("BPM", 50, 200, step=5, key="cpl_bpm_builder")
        with row2[2]:
            st.selectbox(
                "Genre / style",
                CPL_PROGRESSION_STYLES,
                key="cpl_style_early",
            )

        st.markdown(
            f'<p class="cpl-now-editing">Editing <span>{html.escape(prog_title)}</span></p>',
            unsafe_allow_html=True,
        )

        st.selectbox(
            "Original Key",
            CPL_KEY_OPTIONS,
            format_func=format_key_label,
            key="cpl_original_key",
            help="The song's base key. Instrument written keys are calculated later from transposition settings.",
        )

        active = sync_cpl_draft_widgets_to_active(
            st.session_state,
            cpl_active_from_session(st.session_state),
        )
        st.session_state[CPL_ACTIVE_KEY] = active
        prog_title = str(active.get("name") or "My Progression").strip() or "My Progression"
        n1, n2, n3 = st.columns(3)
        with n1:
            if st.button("Save to library", key="cpl_save_prog", use_container_width=True):
                save_progression(saved, active["name"], active)
                st.success(f"Saved **{active['name']}** to your library.")
        with n2:
            if st.button("New song", key="cpl_start_new", use_container_width=True):
                apply_cpl_session_progression(st.session_state, start_new_progression())
                st.rerun()
        with n3:
            if st.button(
                "Set as Active Song",
                key="cpl_set_active",
                type="primary",
                use_container_width=True,
            ):
                _activate_custom_song()

        with st.expander("Load saved or demo charts", expanded=False):
            saved_names = list_saved_progression_names(saved)
            if not saved_names:
                st.caption("No saved songs yet — build chords below, then save.")
            else:
                load_pick = st.selectbox("Saved songs", saved_names, key="cpl_load_pick")
                if st.button("Load selected", key="cpl_load_btn", use_container_width=True):
                    loaded = load_saved_progression(saved, load_pick)
                    apply_cpl_session_progression(st.session_state, loaded)
                    st.rerun()
        with st.expander("Jazz chart demos", expanded=False):
            st.caption("Load a full jazz-standard chart with measure bars and repeat (%) notation.")
            d1, d2 = st.columns(2)
            with d1:
                if st.button("Load Blue Bossa", key="cpl_demo_blue_bossa", use_container_width=True):
                    apply_cpl_session_progression(
                        st.session_state, build_demo_progression("blue_bossa")
                    )
                    st.rerun()
            with d2:
                if st.button("Load Take The A Train", key="cpl_demo_att", use_container_width=True):
                    apply_cpl_session_progression(
                        st.session_state, build_demo_progression("take_the_a_train")
                    )
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        active = cpl_active_from_session(st.session_state)
        prog_title = str(active.get("name") or "My Progression").strip() or "My Progression"
        original_key = cpl_draft_written_key(active)
        original_label = format_key_label(original_key)
        home_ns = original_key.replace("#", "s").replace("b", "f")

        display_sections = deep_copy_sections(display_sections_for_key(active, preview_key))
        has_chords = bool(flatten_sections_to_events(display_sections))
        _filled = filled_section_names(_home_sections())
        _sections_line = (
            f"Sections: {', '.join(_filled)}" if _filled else "No sections with chords yet"
        )
        st.markdown(
            custom_song_preview_card_html(
                title=prog_title,
                artist=str(active.get("artist") or ""),
                key_label=original_label,
                bpm=int(active.get("bpm", 100) or 100),
                time_signature=str(active.get("time_signature") or "4/4"),
                style=str(active.get("progression_style") or "Pop"),
                sections_line=_sections_line,
                has_chords=has_chords,
                is_active=is_custom_progression(st.session_state),
            ),
            unsafe_allow_html=True,
        )

        # --- Finished view ---
        if finished:
            st.markdown(
                cpl_steps_strip_html(
                    style=True,
                    key_set=True,
                    has_section_chords=True,
                    finished=True,
                ),
                unsafe_allow_html=True,
            )
            map_html = song_structure_overview_html(active, display_key, only_filled=True)
            if map_html:
                st.markdown(f'<div class="cpl-finish-panel">{map_html}</div>', unsafe_allow_html=True)

            launch = st.columns([1, 1, 1])
            with launch[0]:
                if st.button(
                    "Set as Active Song",
                    key="cpl_set_active_finish",
                    type="primary",
                    use_container_width=True,
                ):
                    _activate_custom_song()
            with launch[1]:
                if st.button(
                    nav_icon_button_label("backing"),
                    key="cpl_to_backing_finish",
                    use_container_width=True,
                    disabled=not has_chords,
                ):
                    _open_backing()
            with launch[2]:
                if st.button("Keep editing", key="cpl_unfinish", use_container_width=True):
                    st.session_state["cpl_finished"] = False
                    st.rerun()

            c1, c2 = st.columns(2)
            with c1:
                active["bpm"] = st.slider(
                    "BPM", 50, 200, int(active.get("bpm", 100)), 5, key="cpl_bpm_finish"
                )
            with c2:
                active["loops"] = st.slider(
                    "Loops", 1, 10, int(active.get("loops", 2)), 1, key="cpl_loops_finish"
                )
            _save(None)
            return

        # --- Builder ---
        style = str(active.get("progression_style") or "Pop")
        edit_section = st.selectbox(
            "Section to edit",
            CPL_UI_SECTION_ORDER,
            key="cpl_edit_section",
            help="Intro, Verse, Chorus, Bridge, and more.",
        )
        active = cpl_active_from_session(st.session_state)
        home_sections = _home_sections()
        home_entries = home_sections[edit_section]
        original_key = cpl_draft_written_key(active)
        original_label = format_key_label(original_key)
        home_ns = original_key.replace("#", "s").replace("b", "f")
        simple = simple_chords_for_key(original_key)
        style_presets = presets_for_style(style)
        time_sig = str(active.get("time_signature") or "4/4")
        use_lead_sheet = bool(active.get("section_labels")) or bool(active.get("demo_chart_id"))
        pending_key = _pending_chord_key(edit_section)
        last_bars_key = _last_bars_key(edit_section)
        st.session_state.setdefault(last_bars_key, 1)
        pending_chord = st.session_state.get(pending_key)

        st.markdown(
            cpl_steps_strip_html(
                style=bool(style),
                key_set=True,
                has_section_chords=not progression_is_empty(home_sections),
                finished=False,
            ),
            unsafe_allow_html=True,
        )

        st.markdown('<div class="cpl-builder-panel">', unsafe_allow_html=True)
        st.markdown(f'<p class="cpl-section-heading">{edit_section}</p>', unsafe_allow_html=True)
        if is_custom_progression(st.session_state) and preview_key != display_key:
            st.markdown(
                f'<p class="cpl-key-line">Original key <strong>{preview_label}</strong> · '
                f"Practice key <strong>{display_label}</strong> (sidebar)</p>",
                unsafe_allow_html=True,
            )
        elif not is_custom_progression(st.session_state):
            st.markdown(
                f'<p class="cpl-key-line">Draft key: <strong>{preview_label}</strong> · '
                f"global practice key stays <strong>{display_label}</strong> until you "
                f"<strong>Set as Active Song</strong></p>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<p class="cpl-key-line">Key: <strong>{preview_label}</strong></p>',
                unsafe_allow_html=True,
            )

        st.markdown("**1. Click a chord**")
        cols = st.columns(min(6, max(1, len(simple))))
        for i, ch in enumerate(simple):
            with cols[i % len(cols)]:
                if st.button(ch, key=f"cpl_pick_{home_ns}_{edit_section}_{ch}", use_container_width=True):
                    st.session_state[pending_key] = ch
                    st.rerun()

        # ----- Slash chord / custom chord builder -----
        # Lets the user create a slash chord (D/F#, C/E, G/B, A/C#, D/A, ...) by
        # picking root + bass, or type any chord (e.g. Cmaj7, F#m7b5, Bbmaj9/D).
        # The exact symbol — slash included — is preserved end-to-end (chart, save,
        # backing handoff) via normalize_chord_symbol.
        with st.expander("➕ Custom / slash chord", expanded=False):
            _root_options = list(simple) + [
                ch for ch in ("C", "D", "E", "F", "G", "A", "B") if ch not in simple
            ]
            _bass_options = [
                "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
            ]
            st.caption(
                "Build a slash chord with root + bass (e.g. **D/F#**, **C/E**, **G/B**), "
                "or type any chord directly. The exact symbol — slash included — is preserved."
            )
            _sc_root_key = f"cpl_slash_root_{home_ns}_{edit_section}"
            _sc_bass_key = f"cpl_slash_bass_{home_ns}_{edit_section}"
            _sc_text_key = f"cpl_custom_text_{home_ns}_{edit_section}"
            st.session_state.setdefault(_sc_root_key, _root_options[0])
            st.session_state.setdefault(_sc_bass_key, _bass_options[0])
            st.session_state.setdefault(_sc_text_key, "")

            sc1, sc2, sc3 = st.columns([1, 1, 1])
            with sc1:
                _slash_root = st.selectbox(
                    "Root chord",
                    _root_options,
                    key=_sc_root_key,
                    help="The chord quality on top (D, Em7, Cmaj7, etc.).",
                )
            with sc2:
                _slash_bass = st.selectbox(
                    "Bass note",
                    _bass_options,
                    key=_sc_bass_key,
                    help="The note in the bass — appears after the slash.",
                )
            with sc3:
                st.markdown(
                    f'<div style="padding-top:1.65rem;font-size:1.4rem;font-weight:900;'
                    f'color:#1e3a8a;letter-spacing:-0.02em;">'
                    f'{html.escape(str(_slash_root))}/<span style="color:#6d28d9;">'
                    f"{html.escape(str(_slash_bass))}</span></div>",
                    unsafe_allow_html=True,
                )
            if st.button(
                f"Use {_slash_root}/{_slash_bass}",
                key=f"cpl_use_slash_{home_ns}_{edit_section}",
                use_container_width=True,
            ):
                slash_symbol = f"{_slash_root}/{_slash_bass}"
                # normalize_chord_symbol preserves slashes; just be defensive about whitespace.
                st.session_state[pending_key] = normalize_chord_symbol(slash_symbol) or slash_symbol
                st.rerun()

            st.markdown("**Or type any chord** (e.g. `Cmaj7`, `F#m7b5`, `Bbmaj9/D`):")
            tc_col, tc_btn = st.columns([3, 1])
            with tc_col:
                _typed = st.text_input(
                    "Custom chord",
                    key=_sc_text_key,
                    label_visibility="collapsed",
                    placeholder="e.g. D/F#",
                )
            with tc_btn:
                if st.button(
                    "Use chord",
                    key=f"cpl_use_typed_{home_ns}_{edit_section}",
                    use_container_width=True,
                    disabled=not _typed.strip(),
                ):
                    cleaned = normalize_chord_symbol(_typed) or _typed.strip()
                    if cleaned:
                        st.session_state[pending_key] = cleaned
                        st.session_state.pop(_sc_text_key, None)
                        st.rerun()

        st.markdown("**2. Choose bars** (adds selected chord, or changes the last chord)")
        b1, b2, b4 = st.columns(3)

        def _apply_bars(bars: int) -> None:
            nonlocal active, pending_chord, home_sections, home_entries
            bars = int(bars)
            st.session_state[last_bars_key] = bars
            home_sections = _home_sections()
            home_entries = home_sections[edit_section]
            pending = st.session_state.get(pending_key)
            if pending:
                home_entries.append({"chord": pending, "bars": bars})
                st.session_state.pop(pending_key, None)
                pending_chord = None
            elif home_entries:
                home_entries[-1]["bars"] = bars
            else:
                return
            _save(home_sections)
            active = cpl_active_from_session(st.session_state)
            st.rerun()

        with b1:
            if st.button("1 bar", key=f"cpl_b1_{edit_section}", use_container_width=True):
                _apply_bars(1)
        with b2:
            if st.button("2 bars", key=f"cpl_b2_{edit_section}", use_container_width=True):
                _apply_bars(2)
        with b4:
            if st.button("4 bars", key=f"cpl_b4_{edit_section}", use_container_width=True):
                _apply_bars(4)

        def _render_section_progression(*, pending: str | None = None) -> dict:
            active_now = cpl_active_from_session(st.session_state)
            preview_key_now = cpl_draft_preview_key(active_now)
            view = cpl_section_progression_view(
                active_now,
                section_name=edit_section,
                preview_key=preview_key_now,
                pending_chord=pending,
                time_signature=time_sig,
                use_lead_sheet=use_lead_sheet,
            )
            st.markdown("**Progression in this section**")
            if not view["show_panel"]:
                st.info("Tap a chord above, then choose **1**, **2**, or **4** bars to add it.")
                return view

            native_rows = view["native_rows"]
            if native_rows:
                with st.container(border=True):
                    head_ch, head_bars = st.columns([2, 1])
                    with head_ch:
                        st.markdown("**Chord**")
                    with head_bars:
                        st.markdown("**Bars**")
                    for chord_label, bar_count in native_rows:
                        col_ch, col_bars = st.columns([2, 1])
                        with col_ch:
                            st.markdown(f"### {chord_label}")
                        with col_bars:
                            unit = "bar" if bar_count == 1 else "bars"
                            st.write(f"{bar_count} {unit}")
            if pending:
                st.info(
                    f"Selected: **{pending}** — choose **1**, **2**, or **4** bars above to add it."
                )
            return view

        progression_view = _render_section_progression(pending=pending_chord)
        section_has_chords = progression_view["has_chords"]
        section_display = progression_view["section_display"]

        st.markdown("**Type any chord**")
        tc1, tc2, tc3 = st.columns([3, 1, 1])
        with tc1:
            custom_ch = st.text_input(
                "Type any chord",
                placeholder="Bb, B7, F#dim, Fmaj7|Am7|C/D, C:2|G:2…",
                key=f"cpl_custom_{edit_section}",
                label_visibility="collapsed",
            )
        with tc2:
            if st.button("Select", key=f"cpl_custom_sel_{edit_section}", use_container_width=True):
                ch = normalize_chord_symbol(custom_ch)
                if ch:
                    st.session_state[pending_key] = ch
                    st.rerun()
        with tc3:
            if st.button("Add now", key=f"cpl_custom_add_{edit_section}", use_container_width=True):
                ch = normalize_chord_symbol(custom_ch)
                if ch:
                    home_entries.append({
                        "chord": ch,
                        "bars": int(st.session_state.get(last_bars_key, 1)),
                    })
                    st.session_state.pop(pending_key, None)
                    _save(home_sections)
                    st.rerun()
        st.caption(
            "Tip: separate chords with `|` to put several inside one bar — "
            "`Fmaj7|Am7|C/D` for three equal beats in 3/4, "
            "`C:2|G:2` for a half-bar change in 4/4, "
            "`C:3.5|D:0.5p` for a pushed chord on the last 8th."
        )

        _render_subbar_timing_panel(
            home_entries,
            edit_section=edit_section,
            pending_key=pending_key,
            save=lambda: _save(home_sections),
        )

        with st.expander("Chord extensions — optional", expanded=False):
            st.caption("Pick a chord, then tap an extension (e.g. G + 7 → G7).")
            st.session_state.setdefault("cpl_ext_root", simple[0] if simple else "C")
            rcols = st.columns(min(6, max(1, len(simple))))
            for i, ch in enumerate(simple):
                with rcols[i % len(rcols)]:
                    if st.button(ch, key=f"cpl_ext_root_{home_ns}_{edit_section}_{ch}"):
                        st.session_state["cpl_ext_root"] = ch
                        st.rerun()
            ext_cols = st.columns(len(CHORD_QUICK_EDIT_KEYS))
            for i, ek in enumerate(CHORD_QUICK_EDIT_KEYS):
                with ext_cols[i]:
                    if st.button(ek, key=f"cpl_ext_{home_ns}_{edit_section}_{ek}"):
                        staged = apply_quick_chord_edit(st.session_state["cpl_ext_root"], ek)
                        st.session_state[pending_key] = staged
                        st.rerun()

        demo_presets = demo_presets_for_style(style)
        if demo_presets:
            st.markdown('<div class="cpl-preset-block">', unsafe_allow_html=True)
            st.markdown(f"**{style} chart demos** ({original_label})")
            for demo_label, demo_id in demo_presets.items():
                if st.button(
                    demo_label,
                    key=f"cpl_demo_{demo_id}_{edit_section}",
                    use_container_width=True,
                    type="primary",
                ):
                    apply_cpl_session_progression(
                        st.session_state, build_demo_progression(demo_id)
                    )
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        if style_presets:
            st.markdown('<div class="cpl-preset-block">', unsafe_allow_html=True)
            st.markdown(f"**{style} presets** ({original_label}) — fills {edit_section} only")
            for preset_id, spec in style_presets.items():
                label = preset_button_label(preset_id, original_key, spec)
                if st.button(
                    label,
                    key=f"cpl_pre_{home_ns}_{style}_{edit_section}_{preset_id}",
                    use_container_width=True,
                ):
                    home_sections[edit_section] = build_style_preset_entries(
                        style, preset_id, original_key
                    )
                    st.session_state.pop(pending_key, None)
                    if home_sections[edit_section]:
                        st.session_state[last_bars_key] = int(
                            home_sections[edit_section][-1].get("bars", 1) or 1
                        )
                    _save(home_sections)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        if section_has_chords:
            with st.expander("Edit chords in this section", expanded=False):
                section_display = display_entries_for_section(active, preview_key, edit_section)
                for idx, entry in enumerate(list(home_entries)):
                    e1, e2, e3 = st.columns([2, 2, 1])
                    with e1:
                        st.markdown(
                            entries_chord_tiles_html(
                                [section_display[idx]],
                                time_signature=time_sig,
                            ),
                            unsafe_allow_html=True,
                        )
                    with e2:
                        cur_bars = max(1, int(entry.get("bars", 1) or 1))
                        bar_ix = [1, 2, 4].index(cur_bars if cur_bars in (1, 2, 4) else 1)
                        new_bars = st.selectbox(
                            "Bars",
                            [1, 2, 4],
                            index=bar_ix,
                            key=f"cpl_bar_{home_ns}_{edit_section}_{idx}",
                            label_visibility="collapsed",
                        )
                        if int(new_bars) != cur_bars:
                            entry["bars"] = int(new_bars)
                            _save(home_sections)
                            st.rerun()
                    with e3:
                        if st.button("Remove", key=f"cpl_rm_{home_ns}_{edit_section}_{idx}"):
                            home_entries.pop(idx)
                            _save(home_sections)
                            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        active = cpl_active_from_session(st.session_state)
        preview_key = cpl_draft_preview_key(active)
        whole_song = cpl_whole_song_progression_view(active, preview_key)
        has_chords = whole_song["has_any"]
        if whole_song["has_any"]:
            st.markdown("**Whole song progression**")
            with st.container(border=True):
                for block in whole_song["sections"]:
                    st.markdown(f"**{block['name']}**")
                    st.write(block["line"])
                    for chord_label, bar_count in block["rows"]:
                        st.caption(
                            f"{chord_label} — {bar_count} bar{'s' if bar_count != 1 else ''}"
                        )

        st.markdown("---")
        u1, u2, u3 = st.columns(3)
        with u1:
            if st.button(
                "Undo last chord",
                key=f"cpl_undo_{edit_section}",
                use_container_width=True,
                disabled=not home_entries,
            ):
                home_entries.pop()
                st.session_state.pop(pending_key, None)
                _save(home_sections)
                st.rerun()
        with u2:
            if st.button(
                "Clear section",
                key=f"cpl_clear_{edit_section}",
                use_container_width=True,
                disabled=not section_has_chords and not pending_chord,
            ):
                home_sections[edit_section] = []
                st.session_state.pop(pending_key, None)
                _save(home_sections)
                st.rerun()
        with u3:
            if st.button(
                "Finish Song",
                key="cpl_finish",
                type="primary",
                use_container_width=True,
                disabled=not filled_section_names(home_sections),
            ):
                st.session_state["cpl_finished"] = True
                _save(home_sections)
                st.rerun()

        map_html = song_structure_overview_html(
            active,
            preview_key if not is_custom_progression(st.session_state) else display_key,
            highlight_section=edit_section,
            only_filled=True,
        )
        if map_html:
            st.markdown("**Song structure**")
            st.markdown(map_html, unsafe_allow_html=True)

        st.markdown("#### Launch in the studio")
        setup = st.columns(3)
        with setup[0]:
            if st.button(
                "Set as Active Song",
                key="cpl_set_active_bottom",
                type="primary",
                use_container_width=True,
            ):
                _activate_custom_song()
        with setup[1]:
            if st.button(
                nav_icon_button_label("backing"),
                key="cpl_open_backing_bottom",
                use_container_width=True,
                disabled=not has_chords,
            ):
                _open_backing()
        with setup[2]:
            if st.button(
                nav_icon_button_label("practice"),
                key="cpl_open_practice_bottom",
                use_container_width=True,
                disabled=not has_chords,
            ):
                _open_practice()

        with st.expander("More options", expanded=False):
            if saved_names := list_saved_progression_names(saved):
                del_pick = st.selectbox("Delete saved", ["—"] + saved_names, key="cpl_del_pick")
                if st.button("Delete saved progression", disabled=del_pick == "—"):
                    delete_progression(saved, del_pick)
                    st.rerun()

        before_original_key = cpl_draft_written_key(cpl_active_from_session(st.session_state))
        _save(None)
        if cpl_draft_written_key(cpl_active_from_session(st.session_state)) != before_original_key:
            st.rerun()

        try:
            from music_persistence_trace import music_developer_mode

            if music_developer_mode(st):
                edit_for_diag = str(st.session_state.get("cpl_edit_section") or "Verse")
                diag = build_cpl_developer_diagnostics(
                    st.session_state,
                    cpl_active_from_session(st.session_state),
                    edit_section=edit_for_diag,
                )
                with st.expander("Developer: CPL draft diagnostics", expanded=False):
                    st.json(diag)
        except Exception:
            pass

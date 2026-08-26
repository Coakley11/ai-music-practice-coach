"""Custom Progression — click chords to build a song, then open in Backing Track."""

from __future__ import annotations

from app_ui import nav_icon_button_label


def _cpl_active_is_substantive(active: object) -> bool:
    """True when live CPL is a real Custom song, not the empty My Progression shell."""
    try:
        from songs.music_source import cpl_active_is_substantive

        return cpl_active_is_substantive(active)
    except ImportError:
        if not isinstance(active, dict):
            return False
        title = str(active.get("name") or "").strip()
        if title and title not in {"My Progression", "My progression"}:
            return True
        for key in ("original_sections", "sections"):
            secs = active.get(key)
            if isinstance(secs, dict):
                for chs in secs.values():
                    if isinstance(chs, list) and any(str(c).strip() for c in chs):
                        return True
        return False


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
    import copy
    import html

    import streamlit as st

    try:
        from app_ui import inject_studio_page_marker_sync

        inject_studio_page_marker_sync(st, page="custom")
    except Exception:
        pass

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
        cpl_apply_chord_with_bars_to_session,
        cpl_clear_pending_chord,
        cpl_draft_chord_count,
        cpl_draft_written_key,
        cpl_get_pending_chord,
        cpl_on_apply_bars_callback,
        cpl_on_clear_section_callback,
        cpl_on_new_song_callback,
        cpl_on_pick_chord_callback,
        cpl_on_save_library_callback,
        cpl_on_undo_last_chord_callback,
        cpl_set_pending_chord,
        cpl_save_draft,
        cpl_section_progression_view,
        cpl_steps_strip_html,
        deep_copy_sections,
        delete_progression,
        display_entries_for_section,
        display_sections_for_key,
        ensure_all_cpl_sections,
        cpl_draft_preview_key,
        cpl_workspace_practice_key,
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
        practice_entries_to_original_key,
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
        sync_custom_workspace_practice_key,
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

    if CPL_ACTIVE_KEY not in st.session_state or not _cpl_active_is_substantive(
        st.session_state.get(CPL_ACTIVE_KEY)
    ):
        # Restore LAST_CUSTOM identity before minting blank "My Progression / C".
        restored = False
        try:
            from songs.music_source import install_last_custom_into_live_cpl, snapshot_last_custom_state

            restored = install_last_custom_into_live_cpl(
                st.session_state, reset_practice_key_to_original=False
            )
            if restored and _cpl_active_is_substantive(st.session_state.get(CPL_ACTIVE_KEY)):
                st.session_state["_cpl_reseed_widgets_from_active"] = True
            elif CPL_ACTIVE_KEY in st.session_state:
                snapshot_last_custom_state(st.session_state)
                restored = False
        except Exception:
            restored = False
        if not restored and CPL_ACTIVE_KEY not in st.session_state:
            st.session_state[CPL_ACTIVE_KEY] = default_active_progression()
        elif not restored and not _cpl_active_is_substantive(st.session_state.get(CPL_ACTIVE_KEY)):
            if CPL_ACTIVE_KEY not in st.session_state:
                st.session_state[CPL_ACTIVE_KEY] = default_active_progression()
            # Keep non-substantive only when LAST_CUSTOM absent; mint default if missing.
            if not isinstance(st.session_state.get(CPL_ACTIVE_KEY), dict):
                st.session_state[CPL_ACTIVE_KEY] = default_active_progression()
    if CPL_SAVED_KEY not in st.session_state:
        st.session_state[CPL_SAVED_KEY] = {}

    active = cpl_active_from_session(st.session_state)
    active = ensure_cpl_draft_home_tracking(st, active)
    force_widget_seed = False
    if st.session_state.pop("_cpl_reseed_widgets_from_active", False):
        reset_cpl_widget_initialization(st.session_state)
        force_widget_seed = True
    # Substantive draft must own title/Original Key widgets. Stale Streamlit
    # widget values (My Progression / C) must not overwrite LAST_CUSTOM restore.
    # Do NOT wipe a user Original Key advance (active still C, widget now D) —
    # that was blocking first-interaction Original Key changes.
    if _cpl_active_is_substantive(active):
        widget_title = str(st.session_state.get("cpl_title_input") or "").strip()
        active_title = str(active.get("name") or "").strip()
        widget_orig = str(st.session_state.get("cpl_original_key") or "").strip()
        active_orig = str(cpl_draft_written_key(active) or "").strip()
        shell_titles = {"", "My Progression", "My progression"}
        stale_shell_title = (
            bool(active_title)
            and active_title not in shell_titles
            and widget_title in shell_titles
        )
        # LAST_CUSTOM / loaded song at D while widget still default C.
        stale_shell_orig = (
            bool(active_orig)
            and active_orig != "C"
            and widget_orig == "C"
            and (stale_shell_title or widget_title in shell_titles or widget_title == active_title)
        )
        title_shell_overwrite = (
            bool(active_title)
            and active_title not in shell_titles
            and widget_title in {"My Progression", "My progression"}
            and widget_title != active_title
        )
        if stale_shell_title or stale_shell_orig or title_shell_overwrite:
            reset_cpl_widget_initialization(st.session_state)
            force_widget_seed = True
    active = ensure_cpl_widget_keys_initialized(
        st.session_state,
        active,
        force=force_widget_seed,
    )

    display_key = session_display_key(st.session_state)
    original_key = cpl_draft_written_key(active)
    # Builder + in-page progression projection always follow Practice Key.
    practice_key = cpl_workspace_practice_key(st.session_state, active)
    preview_key = practice_key
    preview_label = format_key_label(preview_key)
    display_label = format_key_label(display_key)
    original_label = format_key_label(original_key)
    home_ns = (
        practice_key.replace("#", "s")
        .replace("b", "f")
        .replace("♭", "b")
        .replace("♯", "s")
    )
    finished = bool(st.session_state.get("cpl_finished"))
    saved = st.session_state[CPL_SAVED_KEY]
    prog_title = str(active.get("name") or "My Progression").strip() or "My Progression"

    if st.session_state.get("cpl_edit_section") not in CPL_UI_SECTION_ORDER:
        st.session_state["cpl_edit_section"] = "Verse"

    def _save(sections: dict | None = None, *, persist: bool = True) -> None:
        nonlocal active
        if persist:
            try:
                from music_persistent_state import clear_music_workspace_autosave_block

                clear_music_workspace_autosave_block(st)
            except Exception:
                pass
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

    def _go_songs() -> None:
        _save(None)
        from studio_nav_history import navigate_studio_page

        navigate_studio_page(st.session_state, "picker")
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
        # Keep LAST_CUSTOM fresh while the user works here (Global Active may stay Catalog).
        try:
            from songs.music_source import snapshot_last_custom_state

            snapshot_last_custom_state(st.session_state)
        except Exception:
            pass
        prog_title = str(active.get("name") or "My Progression").strip() or "My Progression"
        _save(_home_sections(), persist=False)
        n1, n2, n3 = st.columns(3)
        with n1:
            st.button(
                "Save to library",
                key="cpl_save_prog",
                use_container_width=True,
                on_click=cpl_on_save_library_callback,
            )
        with n2:
            st.button(
                "New song",
                key="cpl_start_new",
                use_container_width=True,
                on_click=cpl_on_new_song_callback,
            )
        with n3:
            if st.button(
                "Set as Active Song",
                key="cpl_set_active",
                type="primary",
                use_container_width=True,
            ):
                _activate_custom_song()
        _save_flash = st.session_state.pop("_cpl_save_library_flash", False)
        if _save_flash:
            if isinstance(_save_flash, str) and str(_save_flash).startswith("error:"):
                st.error(str(_save_flash))
            else:
                st.success("saved to custom library")
        _new_flash = st.session_state.pop("_cpl_new_song_flash", False)
        if _new_flash:
            if isinstance(_new_flash, str) and str(_new_flash).startswith("error:"):
                st.error(str(_new_flash))
            else:
                st.info("New blank song started — add chords below.")
        with st.expander("Load saved or demo charts", expanded=False):
            saved_names = list_saved_progression_names(saved)
            if not saved_names:
                st.caption("No saved songs yet — build chords below, then save.")
            else:
                load_pick = st.selectbox("Saved songs", saved_names, key="cpl_load_pick")
                if st.button("Load selected", key="cpl_load_btn", use_container_width=True):
                    try:
                        from songs.music_source import clear_cpl_intentional_new_song

                        clear_cpl_intentional_new_song(st.session_state)
                    except ImportError:
                        st.session_state.pop("_cpl_skip_last_custom_restore", None)
                    loaded = load_saved_progression(saved, load_pick)
                    apply_cpl_session_progression(
                        st.session_state, loaded, reset_display_key=True
                    )
                    st.rerun()
        with st.expander("Jazz chart demos", expanded=False):
            st.caption("Load a full jazz-standard chart with measure bars and repeat (%) notation.")
            d1, d2 = st.columns(2)
            with d1:
                if st.button("Load Blue Bossa", key="cpl_demo_blue_bossa", use_container_width=True):
                    apply_cpl_session_progression(
                        st.session_state,
                        build_demo_progression("blue_bossa"),
                        reset_display_key=True,
                    )
                    st.rerun()
            with d2:
                if st.button("Load Take The A Train", key="cpl_demo_att", use_container_width=True):
                    apply_cpl_session_progression(
                        st.session_state,
                        build_demo_progression("take_the_a_train"),
                        reset_display_key=True,
                    )
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        active = cpl_active_from_session(st.session_state)
        prog_title = str(active.get("name") or "My Progression").strip() or "My Progression"
        original_key = cpl_draft_written_key(active)
        original_label = format_key_label(original_key)
        practice_key = cpl_workspace_practice_key(st.session_state, active)
        preview_key = practice_key
        preview_label = format_key_label(preview_key)
        display_key = session_display_key(st.session_state)
        display_label = format_key_label(display_key)
        home_ns = (
            practice_key.replace("#", "s")
            .replace("b", "f")
            .replace("♭", "b")
            .replace("♯", "s")
        )

        display_sections = deep_copy_sections(display_sections_for_key(active, practice_key))
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
                display_key_label=display_label,
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
        edit_section = str(st.session_state.get("cpl_edit_section") or edit_section or "Verse")
        active = cpl_active_from_session(st.session_state)
        home_sections = _home_sections()
        home_entries = home_sections[edit_section]
        original_key = cpl_draft_written_key(active)
        original_label = format_key_label(original_key)
        practice_key = cpl_workspace_practice_key(st.session_state, active)
        preview_key = practice_key
        preview_label = format_key_label(preview_key)
        display_key = session_display_key(st.session_state)
        display_label = format_key_label(display_key)
        home_ns = (
            practice_key.replace("#", "s")
            .replace("b", "f")
            .replace("♭", "b")
            .replace("♯", "s")
        )
        simple = simple_chords_for_key(practice_key)
        style_presets = presets_for_style(style)
        time_sig = str(active.get("time_signature") or "4/4")
        use_lead_sheet = bool(active.get("section_labels")) or bool(active.get("demo_chart_id"))
        pending_key = _pending_chord_key(edit_section)
        last_bars_key = _last_bars_key(edit_section)
        st.session_state.setdefault(last_bars_key, 1)
        pending_chord = cpl_get_pending_chord(st.session_state, edit_section)

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
        st.markdown(
            f'<p class="cpl-key-line">Original key <strong>{original_label}</strong> · '
            f"Practice key <strong>{preview_label}</strong> "
            f"(builder, presets, and progression project from Practice Key)</p>",
            unsafe_allow_html=True,
        )

        st.markdown("**1. Click a chord**")
        cols = st.columns(min(6, max(1, len(simple))))
        for i, ch in enumerate(simple):
            with cols[i % len(cols)]:
                st.button(
                    ch,
                    key=f"cpl_pick_{edit_section}_{ch}",
                    on_click=cpl_on_pick_chord_callback,
                    args=(ch,),
                    use_container_width=True,
                )

        try:
            from music_persistence_trace import music_developer_mode

            if music_developer_mode(st):
                last_click = st.session_state.get("_cpl_last_chord_click")
                if last_click:
                    st.caption(f"Debug last_chord_click: {last_click}")
        except Exception:
            pass

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
                cpl_set_pending_chord(
                    st.session_state,
                    section=edit_section,
                    chord=normalize_chord_symbol(slash_symbol) or slash_symbol,
                )
                st.rerun()

            st.markdown("**Or type any chord** (e.g. `Cmaj7`, `F#m7b5`, `Bbmaj9/D`):")
            _typed = st.text_input(
                "Custom chord",
                key=_sc_text_key,
                placeholder="e.g. Cmaj7, D/F#, F#m7b5",
            )
            typed_clean = str(st.session_state.get(_sc_text_key) or _typed or "").strip()
            if st.button(
                "Use chord",
                key=f"cpl_use_typed_{home_ns}_{edit_section}",
                type="primary",
                use_container_width=True,
                disabled=not typed_clean,
            ):
                cleaned = normalize_chord_symbol(typed_clean) or typed_clean
                if cleaned:
                    cpl_set_pending_chord(st.session_state, section=edit_section, chord=cleaned)
                    st.session_state.pop(_sc_text_key, None)
                    st.rerun()

        st.markdown("**2. Choose duration** (adds selected chord, or changes the last chord)")

        def _render_section_progression(*, pending: str | None = None) -> dict:
            active_now = cpl_active_from_session(st.session_state)
            preview_key_now = cpl_workspace_practice_key(st.session_state, active_now)
            view = cpl_section_progression_view(
                active_now,
                section_name=edit_section,
                preview_key=preview_key_now,
                pending_chord=pending,
                time_signature=time_sig,
                use_lead_sheet=use_lead_sheet,
            )
            st.markdown(f"**{edit_section} Progression**")
            if not view["show_panel"]:
                st.info("Tap a chord above, then choose **1**, **2**, or **4** bars to add it.")
                return view

            if view["panel_html"]:
                st.markdown(view["panel_html"], unsafe_allow_html=True)
            return view

        progression_view = _render_section_progression(pending=pending_chord)
        section_has_chords = progression_view["has_chords"]
        section_display = progression_view["section_display"]

        bq, bh, b1, b2, b4 = st.columns(5)

        with bq:
            st.button(
                "¼ bar",
                key=f"cpl_bquarter_{edit_section}",
                on_click=cpl_on_apply_bars_callback,
                args=(0.25,),
                use_container_width=True,
                help="One beat in 4/4 — merges with the previous bar when possible",
            )
        with bh:
            st.button(
                "½ bar",
                key=f"cpl_bhalf_{edit_section}",
                on_click=cpl_on_apply_bars_callback,
                args=(0.5,),
                use_container_width=True,
                help="Two beats in 4/4 — half-bar change",
            )
        with b1:
            st.button(
                "1 bar",
                key=f"cpl_b1_{edit_section}",
                on_click=cpl_on_apply_bars_callback,
                args=(1,),
                use_container_width=True,
            )
        with b2:
            st.button(
                "2 bars",
                key=f"cpl_b2_{edit_section}",
                on_click=cpl_on_apply_bars_callback,
                args=(2,),
                use_container_width=True,
            )
        with b4:
            st.button(
                "4 bars",
                key=f"cpl_b4_{edit_section}",
                on_click=cpl_on_apply_bars_callback,
                args=(4,),
                use_container_width=True,
            )

        st.caption(
            "Tip: separate chords with `|` inside one bar — "
            "`Fmaj7|Am7|C/D` for three equal beats in 3/4, "
            "`C:2|G:2` for a half-bar change in 4/4."
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
                        cpl_set_pending_chord(st.session_state, section=edit_section, chord=staged)
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
            st.markdown(f"**{style} presets** ({preview_label}) — fills {edit_section} only")
            for preset_id, spec in style_presets.items():
                label = preset_button_label(preset_id, practice_key, spec)
                if st.button(
                    label,
                    key=f"cpl_pre_{home_ns}_{style}_{edit_section}_{preset_id}",
                    use_container_width=True,
                ):
                    practice_entries = build_style_preset_entries(
                        style, preset_id, practice_key
                    )
                    home_sections[edit_section] = practice_entries_to_original_key(
                        practice_entries, practice_key, original_key
                    )
                    cpl_clear_pending_chord(st.session_state, edit_section)
                    if home_sections[edit_section]:
                        st.session_state[last_bars_key] = int(
                            home_sections[edit_section][-1].get("bars", 1) or 1
                        )
                    _save(home_sections)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        if section_has_chords:
            with st.expander("Edit chords in this section", expanded=False):
                section_display = display_entries_for_section(active, practice_key, edit_section)
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
        practice_key = cpl_workspace_practice_key(st.session_state, active)
        preview_key = practice_key
        has_chords = bool(filled_section_names(home_sections))

        st.markdown("---")
        u1, u2, u3 = st.columns(3)
        with u1:
            st.button(
                "Undo last chord",
                key=f"cpl_undo_{edit_section}",
                use_container_width=True,
                disabled=not home_entries,
                on_click=cpl_on_undo_last_chord_callback,
            )
        with u2:
            st.button(
                "Clear section",
                key=f"cpl_clear_{edit_section}",
                use_container_width=True,
                disabled=not section_has_chords and not pending_chord,
                on_click=cpl_on_clear_section_callback,
            )
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
            practice_key,
            highlight_section=edit_section,
            only_filled=True,
        )
        if map_html:
            st.markdown("**Song structure**")
            st.markdown(map_html, unsafe_allow_html=True)

        st.markdown("#### Launch in the studio")
        setup = st.columns(4)
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
                nav_icon_button_label("picker"),
                key="cpl_go_songs_bottom",
                use_container_width=True,
            ):
                _go_songs()
        with setup[2]:
            if st.button(
                nav_icon_button_label("backing"),
                key="cpl_open_backing_bottom",
                use_container_width=True,
                disabled=not has_chords,
            ):
                _open_backing()
        with setup[3]:
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
        _save(_home_sections())
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

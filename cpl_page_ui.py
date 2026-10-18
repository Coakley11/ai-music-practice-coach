"""Custom Progression — click chords to build a song, then open in Backing Track."""

from __future__ import annotations

from app_ui import nav_icon_button_label
from music_feature_icons import feature_label


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
    time_signature: str = "4/4",
) -> None:
    """Measure-split presets: replace the last bar's chord layout with a
    simple beat pattern (2+2, 3+1, 1+3, push)."""
    import streamlit as st

    from chord_subdivisions import Subdivision, join_weighted_subdivisions

    if not home_entries:
        return

    import portfolio_polish as pp

    with st.expander(
        "Measure splits — combine chords in one bar",
        expanded=pp.expander_default(st),
    ):
        pp.instructional_caption(
            st,
            "Pick a chord above, then click a split pattern to combine it with the last bar's chord.",
        )
        pending = st.session_state.get(pending_key)
        if not pending:
            st.info(
                "Pick a chord above first, then choose a split. "
                "Example: select **G**, click **2+2** to make the last bar `C:2|G:2`."
            )
            return

        last_entry = home_entries[-1]
        last_chord = str(last_entry.get("chord", "")).strip()
        if "|" in last_chord:
            st.caption(
                f"Last bar is already split ({last_chord}). "
                "Clicking a pattern below replaces that split."
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
                "2+2",
                key=f"cpl_sub_half_{section_tag}",
                use_container_width=True,
                help=f"{prev_head} for 2 beats, {pending} for 2 beats",
            ):
                _apply_token(
                    join_weighted_subdivisions([
                        Subdivision(prev_head, 2.0, False),
                        Subdivision(pending, 2.0, False),
                    ])
                )
        with cols[1]:
            if st.button(
                "3+1",
                key=f"cpl_sub_threeplusone_{section_tag}",
                use_container_width=True,
                help=f"{prev_head} for 3 beats, {pending} for 1 beat",
            ):
                _apply_token(
                    join_weighted_subdivisions([
                        Subdivision(prev_head, 3.0, False),
                        Subdivision(pending, 1.0, False),
                    ])
                )
        with cols[2]:
            if st.button(
                "1+3",
                key=f"cpl_sub_oneplusthree_{section_tag}",
                use_container_width=True,
                help=f"{prev_head} for 1 beat, {pending} for 3 beats",
            ):
                _apply_token(
                    join_weighted_subdivisions([
                        Subdivision(prev_head, 1.0, False),
                        Subdivision(pending, 3.0, False),
                    ])
                )
        with cols[3]:
            if st.button(
                "Push",
                key=f"cpl_sub_push_{section_tag}",
                use_container_width=True,
                help=f"{pending} anticipated on the last half-beat of the bar",
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
        CPL_RANGE_CLIPBOARD_KEY,
        CPL_SAVED_KEY,
        CPL_TIME_SIGNATURES,
        CPL_UI_SECTION_ORDER,
        apply_cpl_session_progression,
        apply_quick_chord_edit,
        clear_all_cpl_sections,
        build_cpl_developer_diagnostics,
        cpl_active_from_session,
        cpl_collapse_identical_adjacent,
        cpl_copy_chord_range,
        cpl_expand_chord_group,
        cpl_paste_at_position,
        cpl_remove_chord_at_index,
        cpl_split_measure_at_index,
        cpl_apply_chord_with_bars_to_session,
        cpl_clear_pending_chord,
        cpl_draft_chord_count,
        cpl_draft_written_key,
        cpl_get_pending_chord,
        cpl_on_apply_bars_callback,
        cpl_on_append_preset_callback,
        cpl_on_clear_section_callback,
        cpl_on_new_song_callback,
        cpl_on_pick_chord_callback,
        cpl_on_save_library_callback,
        cpl_on_open_backing_callback,
        apply_pending_cpl_open_backing,
        cpl_on_undo_last_chord_callback,
        on_cpl_original_key_change,
        apply_pending_custom_original_key,
        apply_pending_custom_title,
        commit_user_original_key,
        commit_user_title,
        on_cpl_title_input_change,
        is_generic_cpl_title,
        CPL_TITLE_MOUNTED_KEY,
        cpl_library_saved_for_current_song,
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
        preset_button_label,
        prepare_cpl_backing_handoff,
        presets_for_style,
        progression_is_empty,
        purge_cpl_ephemeral_widget_keys,
        save_progression,
        section_is_empty,
        simple_chords_for_key,
        editable_chord_options_for_key,
        chromatic_roots_for_key,
        extract_chord_root_and_suffix,
        CHORD_EDIT_QUALITIES,
        cpl_replace_chord_in_section,
        song_structure_overview_html,
        start_new_progression,
        sync_cpl_draft_widgets_to_active,
        seed_cpl_presets_key_widget,
        CPL_PRESETS_KEY_WIDGET,
        CPL_PRESETS_SEEDED_FROM_KEY,
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

    if apply_pending_cpl_open_backing(st.session_state, st=st):
        st.rerun()

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
    library_saved = cpl_library_saved_for_current_song(st.session_state, active)
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

    def _snapshot_custom_workspace() -> None:
        try:
            from songs.music_source import snapshot_last_custom_state

            snapshot_last_custom_state(st.session_state)
        except Exception:
            pass

    def _go_songs() -> None:
        _save(None)
        _snapshot_custom_workspace()
        from studio_nav_history import navigate_studio_page

        navigate_studio_page(st.session_state, "picker")
        st.rerun()

    def _go_practice_keep_workspace() -> None:
        """Open Practice without promoting Custom or touching Global Active."""
        _save(None)
        _snapshot_custom_workspace()
        from studio_nav_history import navigate_studio_page

        navigate_studio_page(st.session_state, "practice")
        st.rerun()

    def _render_launch_in_studio(
        *,
        has_chords: bool,
        include_workspace_nav: bool,
        include_practice_backing: bool = True,
    ) -> None:
        """Launch actions. Backing/Practice appear once the draft has chords."""
        st.markdown("#### Launch in the studio")
        saved_now = cpl_library_saved_for_current_song(
            st.session_state, cpl_active_from_session(st.session_state)
        )
        cells = ["save"]
        if include_workspace_nav:
            cells.extend(["active", "songs"])
        if include_practice_backing and (
            saved_now or has_chords or not is_generic_cpl_title(str(cpl_active_from_session(st.session_state).get("name") or ""))
        ):
            cells.extend(["backing", "practice"])
        with st.container(key=f"cpl_launch_actions_{'ws' if include_workspace_nav else 'finish'}"):
            cols = st.columns(max(1, len(cells)))
            for col, kind in zip(cols, cells):
                with col:
                    if kind == "save":
                        st.button(
                            "Save to library",
                            key="cpl_save_prog_launch",
                            type="primary",
                            use_container_width=True,
                            on_click=cpl_on_save_library_callback,
                        )
                    elif kind == "active":
                        if st.button(
                            "Set as Active Song",
                            key="cpl_set_active_bottom",
                            type="primary",
                            use_container_width=True,
                        ):
                            _activate_custom_song()
                    elif kind == "songs":
                        if st.button(
                            nav_icon_button_label("picker"),
                            key="cpl_go_songs_bottom",
                            use_container_width=True,
                        ):
                            _go_songs()
                    elif kind == "backing":
                        st.button(
                            feature_label("backing", "Open in Backing Studio"),
                            key="cpl_open_backing_bottom",
                            use_container_width=True,
                            disabled=not has_chords,
                            on_click=cpl_on_open_backing_callback,
                        )
                    elif kind == "practice":
                        if st.button(
                            nav_icon_button_label("practice"),
                            key="cpl_open_practice_bottom",
                            use_container_width=True,
                            disabled=not has_chords,
                        ):
                            _open_practice()

    with st.container(key="custom_song_builder_panel", border=False):
        render_custom_builder_panel_header(st, working_title=prog_title)
        st.markdown('<div class="cpl-title-panel">', unsafe_allow_html=True)
        info_a, info_b = st.columns([2, 1])
        with info_a:
            active = apply_pending_custom_title(
                st.session_state, cpl_active_from_session(st.session_state)
            )
            st.session_state[CPL_ACTIVE_KEY] = active
            live_title = str(active.get("name") or "").strip() or "My Progression"
            st.markdown(
                f'<div id="cpl-title-marker" data-cpl-title="{html.escape(live_title)}"></div>',
                unsafe_allow_html=True,
            )
            st.text_input(
                "Song title",
                key="cpl_title_input",
                placeholder="e.g. My Ballad",
                on_change=on_cpl_title_input_change,
            )
            st.session_state[CPL_TITLE_MOUNTED_KEY] = True
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

        # Commit pending/widget D before the selectbox mounts. A remounted default C
        # must not become the live Original Key for a named Trial Song.
        active = apply_pending_custom_original_key(
            st.session_state, cpl_active_from_session(st.session_state)
        )
        st.session_state[CPL_ACTIVE_KEY] = active

        st.caption("Choose the Original Key, then Save to library.")
        current_orig = str(cpl_draft_written_key(active) or "C").strip() or "C"

        st.selectbox(
            feature_label("original_key", "Original Key"),
            CPL_KEY_OPTIONS,
            format_func=format_key_label,
            key="cpl_original_key",
            on_change=on_cpl_original_key_change,
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
        try:
            from songs.music_source import LAST_CUSTOM_STATE_KEY, custom_pick_key_for

            last_snap = st.session_state.get(LAST_CUSTOM_STATE_KEY)
        except ImportError:
            last_snap = st.session_state.get("_last_custom_song_state")
            custom_pick_key_for = lambda _a: ""  # type: ignore
        last_snap = last_snap if isinstance(last_snap, dict) else {}
        last_active = last_snap.get("active") if isinstance(last_snap.get("active"), dict) else {}
        ident_live = cpl_active_from_session(st.session_state)
        ident_pick = str(
            last_snap.get("pick_key") or custom_pick_key_for(ident_live) or ident_live.get("id") or ""
        )
        ident_chords = int(cpl_draft_chord_count(ident_live) or 0)
        st.markdown(
            f'<div id="cpl-saved-identity" '
            f'data-title="{html.escape(str(ident_live.get("name") or ""))}" '
            f'data-orig="{html.escape(str(cpl_draft_written_key(ident_live) or ""))}" '
            f'data-id="{html.escape(str(ident_live.get("id") or ""))}" '
            f'data-pick="{html.escape(ident_pick)}" '
            f'data-practice="{html.escape(str(practice_key or ""))}" '
            f'data-chords="{ident_chords}" '
            f'data-last-title="{html.escape(str(last_snap.get("name") or ""))}" '
            f'data-last-orig="{html.escape(str(last_active.get("original_key_center") or last_snap.get("custom_home_key") or ""))}" '
            f'data-last-pick="{html.escape(str(last_snap.get("pick_key") or ""))}" '
            f'style="display:none" aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )
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
                display_key_label=preview_label,
                bpm=int(active.get("bpm", 100) or 100),
                time_signature=str(active.get("time_signature") or "4/4"),
                style=str(active.get("progression_style") or "Pop"),
                sections_line=_sections_line,
                has_chords=has_chords,
                is_active=is_custom_progression(st.session_state),
            ),
            unsafe_allow_html=True,
        )

        _preview_chords = int(cpl_draft_chord_count(active) or 0)
        _can_open_backing = bool(has_chords or _preview_chords > 0)
        st.markdown(
            f'<div id="cpl-open-backing-marker" data-enabled="{1 if _can_open_backing else 0}" '
            f'data-chords="{_preview_chords}" data-title="{html.escape(prog_title)}"></div>',
            unsafe_allow_html=True,
        )
        st.button(
            feature_label("backing", "Open in Backing Studio"),
            key="cpl_open_backing",
            type="primary",
            use_container_width=True,
            disabled=not _can_open_backing,
            on_click=cpl_on_open_backing_callback,
        )

        # --- Finished view ---
        if finished:
            st.markdown(
                cpl_steps_strip_html(
                    style=True,
                    key_set=True,
                    has_section_chords=True,
                    finished=True,
                    saved=library_saved,
                ),
                unsafe_allow_html=True,
            )
            map_html = song_structure_overview_html(active, practice_key, only_filled=True)
            if map_html:
                st.markdown(f'<div class="cpl-finish-panel">{map_html}</div>', unsafe_allow_html=True)

            st.markdown("**Open**")
            if library_saved or has_chords:
                go_p, go_s, go_b = st.columns(3)
                with go_p:
                    if st.button(
                        nav_icon_button_label("practice"),
                        key="cpl_to_practice_finish",
                        type="primary",
                        use_container_width=True,
                    ):
                        _go_practice_keep_workspace()
                with go_s:
                    if st.button(
                        nav_icon_button_label("picker"),
                        key="cpl_to_songs_finish",
                        use_container_width=True,
                    ):
                        _go_songs()
                with go_b:
                    st.button(
                        feature_label("backing", "Open in Backing Studio"),
                        key="cpl_to_backing_finish",
                        use_container_width=True,
                        disabled=not has_chords,
                        on_click=cpl_on_open_backing_callback,
                    )
            else:
                if st.button(
                    nav_icon_button_label("picker"),
                    key="cpl_to_songs_finish",
                    use_container_width=True,
                ):
                    _go_songs()

            launch = st.columns(2)
            with launch[0]:
                if st.button(
                    "Set as Active Song",
                    key="cpl_set_active_finish",
                    type="primary",
                    use_container_width=True,
                ):
                    _activate_custom_song()
            with launch[1]:
                if st.button("Keep Editing", key="cpl_unfinish", use_container_width=True):
                    st.session_state["cpl_finished"] = False
                    st.rerun()

            _render_launch_in_studio(
                has_chords=has_chords,
                include_workspace_nav=False,
                include_practice_backing=False,
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
                saved=library_saved,
            ),
            unsafe_allow_html=True,
        )

        st.markdown('<div class="cpl-builder-panel">', unsafe_allow_html=True)
        st.markdown(f'<p class="cpl-section-heading">{edit_section}</p>', unsafe_allow_html=True)
        st.markdown(
            f'<p class="cpl-key-line">Original key <strong>{original_label}</strong> · '
            f"Practice key <strong>{preview_label}</strong> "
            f"(builder and progression project from Practice Key; "
            f"preset buttons use Presets key)</p>",
            unsafe_allow_html=True,
        )

        st.markdown("**1. Pick a chord**")
        from responsive_layout import iter_ui_rows

        with st.container(key="cpl_chord_pick_grid"):
            for chunk in iter_ui_rows(simple, 6):
                cols = st.columns(len(chunk) or 1)
                for col, ch in zip(cols, chunk):
                    with col:
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
            _chromatic_notes = chromatic_roots_for_key(practice_key)
            _custom_qualities = [
                ("", "(major)"), ("m", "minor"),
                ("7", "7"), ("maj7", "maj7"), ("m7", "m7"), ("mMaj7", "mMaj7"),
                ("m7b5", "m7b5"), ("dim", "dim"), ("dim7", "dim7"),
                ("aug", "aug"), ("sus2", "sus2"), ("sus4", "sus4"),
                ("6", "6"), ("m6", "m6"), ("6/9", "6/9"), ("add9", "add9"),
                ("9", "9"), ("m9", "m9"), ("maj9", "maj9"),
                ("11", "11"), ("m11", "m11"),
                ("13", "13"), ("maj13", "maj13"), ("m13", "m13"),
                ("7b9", "7b9"), ("7#9", "7#9"), ("7#11", "7#11"), ("7b13", "7b13"),
            ]
            _bass_options = _chromatic_notes

            st.caption(
                "Build any chord: pick root, quality, and optional slash bass. "
                "Or type any chord directly below."
            )
            _sc_root_key = f"cpl_slash_root_{home_ns}_{edit_section}"
            _sc_qual_key = f"cpl_custom_qual_{home_ns}_{edit_section}"
            _sc_bass_key = f"cpl_slash_bass_{home_ns}_{edit_section}"
            _sc_text_key = f"cpl_custom_text_{home_ns}_{edit_section}"

            sc1, sc2, sc3 = st.columns([1, 2, 1])
            with sc1:
                _custom_root = st.selectbox(
                    "Root note",
                    _chromatic_notes,
                    key=_sc_root_key,
                    help="The root note of the chord.",
                )
            with sc2:
                _custom_qual = st.selectbox(
                    "Quality",
                    [q for q, _ in _custom_qualities],
                    format_func=lambda q: dict(_custom_qualities).get(q, q),
                    key=_sc_qual_key,
                    help="Chord quality / extensions.",
                )
            with sc3:
                _use_bass = st.checkbox("Slash bass", key=f"cpl_use_bass_{home_ns}_{edit_section}")

            if _use_bass:
                sb1, sb2 = st.columns([1, 2])
                with sb1:
                    _slash_bass = st.selectbox(
                        "Bass note",
                        _bass_options,
                        key=_sc_bass_key,
                        help="The note in the bass (after the slash).",
                    )
                _built_chord = f"{_custom_root}{_custom_qual}/{_slash_bass}"
            else:
                _built_chord = f"{_custom_root}{_custom_qual}"

            st.markdown(
                f'<div style="padding:0.5rem 0;font-size:1.4rem;font-weight:900;'
                f'color:#1e3a8a;letter-spacing:-0.02em;">'
                f'{html.escape(_built_chord)}</div>',
                unsafe_allow_html=True,
            )
            if st.button(
                f"Use {_built_chord}",
                key=f"cpl_use_slash_{home_ns}_{edit_section}",
                use_container_width=True,
                type="primary",
            ):
                cpl_set_pending_chord(
                    st.session_state,
                    section=edit_section,
                    chord=normalize_chord_symbol(_built_chord) or _built_chord,
                )
                st.rerun()

            st.markdown("---")
            st.markdown("**Or type any chord** (e.g. `Cmaj7`, `F#m7b5`, `Bbmaj9/D`, `Fm6/Ab`):")
            _typed = st.text_input(
                "Custom chord",
                key=_sc_text_key,
                placeholder="e.g. Cmaj7, D/F#, F#m7b5, Fm6/Ab",
            )
            typed_clean = str(st.session_state.get(_sc_text_key) or _typed or "").strip()
            if st.button(
                "Use chord",
                key=f"cpl_use_typed_{home_ns}_{edit_section}",
                use_container_width=True,
                disabled=not typed_clean,
            ):
                cleaned = normalize_chord_symbol(typed_clean) or typed_clean
                if cleaned:
                    cpl_set_pending_chord(st.session_state, section=edit_section, chord=cleaned)
                    st.session_state.pop(_sc_text_key, None)
                    st.rerun()

        st.markdown("**2. Choose duration** (adds the chord, or resizes the last one)")

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

        with st.container(key="cpl_bar_duration_row"):
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
            "Tip: use **Measure splits** below (2+2, 3+1, 1+3) to put two chords in one bar. "
            "You can also type `C:2|G:2` in the custom chord box for manual splits."
        )

        _render_subbar_timing_panel(
            home_entries,
            edit_section=edit_section,
            pending_key=pending_key,
            save=lambda: _save(home_sections),
            time_signature=time_sig,
        )

        with st.expander("Chord extensions — optional", expanded=False):
            st.caption("Pick a root chord, then tap an extension (e.g. G + 7 → G7).")
            st.session_state.setdefault("cpl_ext_root", simple[0] if simple else "C")
            from responsive_layout import iter_ui_rows

            with st.container(key="cpl_ext_root_grid"):
                for chunk in iter_ui_rows(simple, 6):
                    rcols = st.columns(len(chunk) or 1)
                    for col, ch in zip(rcols, chunk):
                        with col:
                            if st.button(ch, key=f"cpl_ext_root_{home_ns}_{edit_section}_{ch}"):
                                st.session_state["cpl_ext_root"] = ch
                                st.rerun()
            ext_root = st.session_state.get("cpl_ext_root", simple[0] if simple else "C")
            st.markdown(f"Apply to **{ext_root}**:")
            _ext_groups = [
                ("7ths", ["7", "maj7", "m7", "mMaj7", "m7b5", "dim7"]),
                ("Triads", ["dim", "aug", "sus2", "sus4"]),
                ("Color", ["6", "m6", "6/9", "add9"]),
                ("Extended", ["9", "m9", "maj9", "11", "m11", "13", "maj13", "m13"]),
                ("Altered", ["7b9", "7#9", "7#11", "7b13"]),
            ]
            for group_label, group_keys in _ext_groups:
                st.caption(group_label)
                ext_cols = st.columns(len(group_keys) or 1)
                for i, ek in enumerate(group_keys):
                    with ext_cols[i]:
                        if st.button(ek, key=f"cpl_ext_{home_ns}_{edit_section}_{ek}"):
                            staged = apply_quick_chord_edit(ext_root, ek)
                            cpl_set_pending_chord(st.session_state, section=edit_section, chord=staged)
                            st.rerun()

        demo_presets = demo_presets_for_style(style)
        try:
            from songs.key_state import display_key_options as _preset_key_options
            from music_theory import coerce_key_to_mode, key_mode
        except ImportError:
            from custom_progression_lab import CPL_KEY_OPTIONS as _fallback_keys

            def _preset_key_options(home: str) -> list[str]:
                return list(_fallback_keys)

            def coerce_key_to_mode(token: str, mode: str) -> str:
                return str(token or "").strip()

            def key_mode(token: str) -> str:
                t = str(token or "").strip().lower()
                return "minor" if t.endswith("m") and not t.endswith("emaj") else "major"

        seed_cpl_presets_key_widget(
            st.session_state,
            practice_key,
            song_sig=str(active.get("id") or active.get("name") or ""),
        )
        preset_opts = list(_preset_key_options(original_key) or [original_key])
        live_presets = str(st.session_state.get(CPL_PRESETS_KEY_WIDGET) or practice_key).strip()
        if live_presets not in preset_opts:
            coerced = coerce_key_to_mode(live_presets, key_mode(original_key)) or original_key
            if coerced not in preset_opts:
                preset_opts = [coerced] + [k for k in preset_opts if k != coerced]
            st.session_state[CPL_PRESETS_KEY_WIDGET] = coerced

        def _on_presets_key_change() -> None:
            tok = str(st.session_state.get(CPL_PRESETS_KEY_WIDGET) or "").strip()
            if not tok:
                return
            st.session_state[CPL_PRESETS_SEEDED_FROM_KEY] = tok

        st.markdown('<div class="cpl-preset-block">', unsafe_allow_html=True)
        st.markdown("**Presets**")
        st.selectbox(
            "Presets key",
            preset_opts,
            format_func=format_key_label,
            key=CPL_PRESETS_KEY_WIDGET,
            help="Local construction key for preset buttons only. "
            "Does not change this song's Practice / Concert Key.",
            on_change=_on_presets_key_change,
        )
        presets_key = str(st.session_state.get(CPL_PRESETS_KEY_WIDGET) or practice_key).strip() or practice_key
        presets_label = format_key_label(presets_key)
        st.caption(
            f"Preset buttons use **{presets_label}**. "
            f"Song Practice Key stays **{preview_label}**."
        )

        if demo_presets:
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

        if style_presets:
            preset_ns = (
                presets_key.replace("#", "s")
                .replace("b", "f")
                .replace("♭", "b")
                .replace("♯", "s")
            )
            st.markdown(f"**{style} presets** ({presets_label}) — appends to {edit_section}")
            for preset_id, spec in style_presets.items():
                label = preset_button_label(preset_id, presets_key, spec)
                st.button(
                    label,
                    key=f"cpl_pre_{preset_ns}_{style}_{edit_section}_{preset_id}",
                    use_container_width=True,
                    on_click=cpl_on_append_preset_callback,
                    args=(style, preset_id),
                )
        st.markdown("</div>", unsafe_allow_html=True)

        if section_has_chords:
            with st.expander("Edit existing chords", expanded=False):
                section_display = display_entries_for_section(active, practice_key, edit_section)
                from custom_progression_lab import semitone_distance, transpose_chord
                _pk_to_ok_steps = semitone_distance(practice_key, original_key)
                _edit_idx_key = f"_cpl_editing_idx_{edit_section}"
                _split_idx_key = f"_cpl_splitting_idx_{edit_section}"
                editing_idx = st.session_state.get(_edit_idx_key, -1)
                splitting_idx = st.session_state.get(_split_idx_key, -1)
                _chromatic = chromatic_roots_for_key(practice_key)

                # --- Range selection state ---
                _sel_start_key = f"_cpl_sel_start_{edit_section}"
                _sel_end_key = f"_cpl_sel_end_{edit_section}"
                sel_start = st.session_state.get(_sel_start_key, -1)
                sel_end = st.session_state.get(_sel_end_key, -1)

                st.caption("Click **Edit** to change a chord, **Split** to divide a measure, or select a range to copy.")

                for idx, entry in enumerate(list(home_entries)):
                    display_entry = section_display[idx] if idx < len(section_display) else entry
                    display_chord = str(display_entry.get("chord") or "").split("|")[0].split(":")[0].strip()
                    full_display = str(display_entry.get("chord") or "").strip()
                    cur_bars = max(1, int(entry.get("bars", 1) or 1))
                    is_split = "|" in str(entry.get("chord") or "")
                    in_selection = sel_start >= 0 and sel_end >= 0 and sel_start <= idx <= sel_end

                    if editing_idx == idx:
                        # --- EDIT MODE ---
                        st.markdown(f"**Editing chord {idx + 1}:** {display_chord}")
                        root_pk, suffix = extract_chord_root_and_suffix(display_chord)
                        root_idx = _chromatic.index(root_pk) if root_pk in _chromatic else 0
                        suffix_idx = CHORD_EDIT_QUALITIES.index(suffix) if suffix in CHORD_EDIT_QUALITIES else 0
                        r1, r2, r3 = st.columns([2, 3, 2])
                        with r1:
                            new_root = st.selectbox(
                                "Root",
                                _chromatic,
                                index=root_idx,
                                key=f"cpl_edt_root_{home_ns}_{edit_section}_{idx}",
                            )
                        with r2:
                            new_suffix = st.selectbox(
                                "Quality",
                                CHORD_EDIT_QUALITIES,
                                index=suffix_idx,
                                format_func=lambda q: "(major)" if q == "" else q,
                                key=f"cpl_edt_qual_{home_ns}_{edit_section}_{idx}",
                            )
                        with r3:
                            bar_opts = [1, 2, 3, 4]
                            bar_ix = bar_opts.index(cur_bars) if cur_bars in bar_opts else 0
                            new_bars = st.selectbox(
                                "Bars",
                                bar_opts,
                                index=bar_ix,
                                key=f"cpl_bar_{home_ns}_{edit_section}_{idx}",
                            )
                        assembled_pk = f"{new_root}{new_suffix}"
                        changed = assembled_pk != display_chord or int(new_bars) != cur_bars
                        d1, d2, d3 = st.columns(3)
                        with d1:
                            if st.button("Apply", key=f"cpl_edt_apply_{home_ns}_{edit_section}_{idx}", type="primary", disabled=not changed):
                                if assembled_pk != display_chord:
                                    new_chord_ok = transpose_chord(
                                        assembled_pk, _pk_to_ok_steps, reference_key=original_key,
                                    ) if _pk_to_ok_steps else assembled_pk
                                    cpl_replace_chord_in_section(
                                        st.session_state,
                                        section_name=edit_section,
                                        index=idx,
                                        new_chord=new_chord_ok,
                                        st_module=st,
                                    )
                                if int(new_bars) != cur_bars:
                                    active_now = cpl_active_from_session(st.session_state)
                                    home_now = ensure_all_cpl_sections(active_now.get("original_sections"))
                                    entries_now = list(home_now.get(edit_section) or [])
                                    if idx < len(entries_now):
                                        entries_now[idx]["bars"] = int(new_bars)
                                        home_now[edit_section] = entries_now
                                        cpl_save_draft(st.session_state, active_now, home_now, persist=True, st=st)
                                st.session_state.pop(_edit_idx_key, None)
                                st.rerun()
                        with d2:
                            if st.button("Remove", key=f"cpl_edt_rm_{home_ns}_{edit_section}_{idx}"):
                                cpl_remove_chord_at_index(
                                    st.session_state,
                                    section_name=edit_section,
                                    index=idx,
                                    st_module=st,
                                )
                                st.session_state.pop(_edit_idx_key, None)
                                st.rerun()
                        with d3:
                            if st.button("Cancel", key=f"cpl_edt_cancel_{home_ns}_{edit_section}_{idx}"):
                                st.session_state.pop(_edit_idx_key, None)
                                st.rerun()

                    elif splitting_idx == idx:
                        # --- SPLIT MODE ---
                        st.markdown(f"**Split measure {idx + 1}:** {display_chord}")
                        st.caption("Choose a second chord and a beat pattern.")
                        sp1, sp2 = st.columns([1, 1])
                        with sp1:
                            split_chord_key = f"cpl_split_chord_{home_ns}_{edit_section}_{idx}"
                            split_chord_opts = editable_chord_options_for_key(practice_key)
                            _split_chord = st.selectbox(
                                "Second chord",
                                split_chord_opts,
                                key=split_chord_key,
                            )
                        with sp2:
                            _split_pattern = st.selectbox(
                                "Pattern",
                                ["2+2", "3+1", "1+3", "Push"],
                                key=f"cpl_split_pat_{home_ns}_{edit_section}_{idx}",
                            )
                        sb1, sb2 = st.columns(2)
                        with sb1:
                            if st.button("Apply split", key=f"cpl_split_apply_{home_ns}_{edit_section}_{idx}", type="primary"):
                                split_ok_chord = transpose_chord(
                                    _split_chord, _pk_to_ok_steps, reference_key=original_key,
                                ) if _pk_to_ok_steps else _split_chord
                                cpl_split_measure_at_index(
                                    st.session_state,
                                    section_name=edit_section,
                                    index=idx,
                                    pattern=_split_pattern.lower(),
                                    second_chord=split_ok_chord,
                                    st_module=st,
                                )
                                st.session_state.pop(_split_idx_key, None)
                                st.rerun()
                        with sb2:
                            if st.button("Cancel", key=f"cpl_split_cancel_{home_ns}_{edit_section}_{idx}"):
                                st.session_state.pop(_split_idx_key, None)
                                st.rerun()

                    else:
                        # --- COMPACT ROW ---
                        sel_marker = ">> " if in_selection else ""
                        bars_label = f"{cur_bars} bar{'s' if cur_bars != 1 else ''}"
                        if is_split:
                            bars_label += " (split)"

                        c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 1])
                        with c1:
                            st.markdown(
                                entries_chord_tiles_html(
                                    [display_entry],
                                    time_signature=time_sig,
                                ),
                                unsafe_allow_html=True,
                            )
                        with c2:
                            st.caption(bars_label)
                        with c3:
                            if st.button("Edit", key=f"cpl_edit_btn_{home_ns}_{edit_section}_{idx}"):
                                st.session_state[_edit_idx_key] = idx
                                st.session_state.pop(_split_idx_key, None)
                                st.rerun()
                        with c4:
                            can_expand = cur_bars > 1 and not is_split
                            can_split = cur_bars == 1 and not is_split
                            if can_expand:
                                if st.button("Expand", key=f"cpl_expand_{home_ns}_{edit_section}_{idx}", help=f"Expand {cur_bars} bars into individual measures"):
                                    cpl_expand_chord_group(
                                        st.session_state,
                                        section_name=edit_section,
                                        index=idx,
                                        st_module=st,
                                    )
                                    st.rerun()
                            elif can_split:
                                if st.button("Split", key=f"cpl_split_btn_{home_ns}_{edit_section}_{idx}", help="Split this measure into beat subdivisions"):
                                    st.session_state[_split_idx_key] = idx
                                    st.session_state.pop(_edit_idx_key, None)
                                    st.rerun()
                            else:
                                st.write("")
                        with c5:
                            if st.button("Remove", key=f"cpl_rm_{home_ns}_{edit_section}_{idx}"):
                                cpl_remove_chord_at_index(
                                    st.session_state,
                                    section_name=edit_section,
                                    index=idx,
                                    st_module=st,
                                )
                                if editing_idx == idx:
                                    st.session_state.pop(_edit_idx_key, None)
                                st.rerun()

                # --- Range copy/paste controls ---
                st.markdown("---")
                st.caption("**Copy a range of chords**")
                rc1, rc2, rc3 = st.columns(3)
                n_chords = len(home_entries)
                chord_labels = [f"{i+1}" for i in range(n_chords)]
                with rc1:
                    _range_start = st.selectbox(
                        "From chord #",
                        list(range(n_chords)),
                        format_func=lambda i: chord_labels[i] if i < len(chord_labels) else str(i + 1),
                        key=f"cpl_range_start_{home_ns}_{edit_section}",
                    )
                with rc2:
                    _range_end = st.selectbox(
                        "To chord #",
                        list(range(n_chords)),
                        index=min(n_chords - 1, _range_start) if n_chords else 0,
                        format_func=lambda i: chord_labels[i] if i < len(chord_labels) else str(i + 1),
                        key=f"cpl_range_end_{home_ns}_{edit_section}",
                    )
                with rc3:
                    if st.button("Copy range", key=f"cpl_copy_range_{home_ns}_{edit_section}", disabled=_range_start > _range_end):
                        cpl_copy_chord_range(
                            st.session_state,
                            section_name=edit_section,
                            start=_range_start,
                            end=_range_end,
                        )
                        st.rerun()

                range_clip = st.session_state.get(CPL_RANGE_CLIPBOARD_KEY)
                if range_clip:
                    clip_desc = ", ".join(str(e.get("chord", "?")).split("|")[0].split(":")[0] for e in range_clip[:5])
                    if len(range_clip) > 5:
                        clip_desc += f"... ({len(range_clip)} total)"
                    st.caption(f"Clipboard: {clip_desc}")
                    pi1, pi2 = st.columns(2)
                    with pi1:
                        _paste_pos = st.selectbox(
                            "Insert after chord #",
                            list(range(n_chords + 1)),
                            index=n_chords,
                            format_func=lambda i: "Start" if i == 0 else str(i),
                            key=f"cpl_paste_pos_{home_ns}_{edit_section}",
                        )
                    with pi2:
                        if st.button("Paste here", key=f"cpl_paste_range_{home_ns}_{edit_section}", type="primary"):
                            cpl_paste_at_position(
                                st.session_state,
                                section_name=edit_section,
                                position=_paste_pos,
                                st_module=st,
                            )
                            st.rerun()

                # --- Collapse adjacent identical chords ---
                if n_chords >= 2:
                    has_adjacent = False
                    for i in range(len(home_entries) - 1):
                        if str(home_entries[i].get("chord", "")).strip() == str(home_entries[i + 1].get("chord", "")).strip():
                            has_adjacent = True
                            break
                    if has_adjacent:
                        if st.button("Combine adjacent identical chords", key=f"cpl_collapse_{home_ns}_{edit_section}"):
                            cpl_collapse_identical_adjacent(
                                st.session_state,
                                section_name=edit_section,
                                st_module=st,
                            )
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

        from custom_progression_lab import (
            CPL_CLIPBOARD_KEY,
            CPL_EDITABLE_SECTIONS,
            cpl_copy_section,
            cpl_paste_section,
            cpl_duplicate_section,
        )
        clipboard = st.session_state.get(CPL_CLIPBOARD_KEY)
        cp1, cp2, cp3 = st.columns(3)
        with cp1:
            if st.button(
                "Copy section",
                key=f"cpl_copy_{edit_section}",
                use_container_width=True,
                disabled=not section_has_chords,
            ):
                cpl_copy_section(st.session_state, section_name=edit_section)
                st.rerun()
        with cp2:
            if st.button(
                "Paste",
                key=f"cpl_paste_{edit_section}",
                use_container_width=True,
                disabled=not clipboard,
            ):
                cpl_paste_section(
                    st.session_state, section_name=edit_section, st_module=st,
                )
                st.rerun()
        with cp3:
            other_sections = [s for s in CPL_EDITABLE_SECTIONS if s != edit_section]
            dup_target = st.selectbox(
                "Duplicate to",
                ["—"] + other_sections,
                key=f"cpl_dup_target_{edit_section}",
                label_visibility="collapsed",
                disabled=not section_has_chords,
            )
            if dup_target != "—" and section_has_chords:
                cpl_duplicate_section(
                    st.session_state,
                    from_section=edit_section,
                    to_section=dup_target,
                    st_module=st,
                )
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

        _render_launch_in_studio(has_chords=has_chords, include_workspace_nav=True)

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

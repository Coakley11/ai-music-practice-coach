"""Custom Progression — professional chord builder with Backing Track handoff."""

from __future__ import annotations


def render_custom_progression_lab_page() -> None:
    import streamlit as st

    from custom_progression_lab import (
        CHORD_QUICK_EDIT_KEYS,
        CPL_ACTIVE_KEY,
        CPL_BUILDER_VERSION,
        CPL_PROGRESSION_STYLES,
        CPL_SAVED_KEY,
        CPL_UI_SECTION_ORDER,
        apply_quick_chord_edit,
        build_style_preset_entries,
        clear_all_cpl_sections,
        commit_home_sections,
        deep_copy_sections,
        display_entries_for_section,
        display_sections_for_key,
        ensure_all_cpl_sections,
        ensure_cpl_editing_in_display_key,
        ensure_original_structure,
        entries_chord_tiles_html,
        filled_section_names,
        flatten_sections_to_events,
        format_key_label,
        invalidate_cpl_derived_outputs,
        normalize_chord_symbol,
        preset_button_label,
        prepare_cpl_backing_handoff,
        presets_for_style,
        progression_is_empty,
        save_progression,
        section_is_empty,
        simple_chords_for_key,
        song_structure_overview_html,
    )
    from progression_helpers import (
        default_active_progression,
        invalidate_backing_cache,
        render_cpl_page_header,
        session_display_key,
    )
    from songs.music_source import note_active_source_change, set_custom_source

    render_cpl_page_header()

    if st.session_state.get("cpl_builder_version") != CPL_BUILDER_VERSION:
        st.session_state[CPL_ACTIVE_KEY] = default_active_progression()
        st.session_state["cpl_builder_version"] = CPL_BUILDER_VERSION
        st.session_state.pop("_cpl_editing_display_key", None)
        st.session_state.pop("cpl_finished", None)
        invalidate_cpl_derived_outputs(st.session_state)

    if CPL_ACTIVE_KEY not in st.session_state:
        st.session_state[CPL_ACTIVE_KEY] = default_active_progression()
    if CPL_SAVED_KEY not in st.session_state:
        st.session_state[CPL_SAVED_KEY] = {}

    display_key = session_display_key(st.session_state)
    active = ensure_original_structure(st.session_state[CPL_ACTIVE_KEY])
    home_sections = ensure_all_cpl_sections(active.get("original_sections"))
    active["original_sections"] = home_sections
    active = ensure_cpl_editing_in_display_key(st, active, display_key)
    st.session_state[CPL_ACTIVE_KEY] = active

    key_label = format_key_label(display_key)
    ns = display_key.replace("#", "s").replace("b", "f")
    finished = bool(st.session_state.get("cpl_finished"))

    if st.session_state.get("cpl_edit_section") not in CPL_UI_SECTION_ORDER:
        st.session_state["cpl_edit_section"] = "Verse"

    def _save() -> None:
        nonlocal active, home_sections
        active = commit_home_sections(active, home_sections)
        active["user_locked_home_key"] = True
        st.session_state[CPL_ACTIVE_KEY] = active

    def _open_backing() -> None:
        _save()
        set_custom_source(st.session_state)
        note_active_source_change(st, invalidate_backing=invalid_backing_cache)
        prepare_cpl_backing_handoff(st.session_state, active, section=None)
        st.session_state["studio_page"] = "backing"
        st.rerun()

    st.markdown(
        '<p class="cpl-flow-hint">To transpose, change the global key on the left.</p>',
        unsafe_allow_html=True,
    )

    _save()
    display_sections = deep_copy_sections(display_sections_for_key(active, display_key))
    has_chords = bool(flatten_sections_to_events(display_sections))

    if finished:
        st.markdown("### Your progression")
        st.markdown(
            '<div class="cpl-finish-panel">'
            + song_structure_overview_html(active, display_key, only_filled=True)
            + "</div>",
            unsafe_allow_html=True,
        )

        b1, b2, b3 = st.columns([2, 1, 1])
        with b1:
            if st.button(
                "▶ Open in Backing Track",
                key="cpl_to_backing_finish",
                type="primary",
                use_container_width=True,
                disabled=not has_chords,
            ):
                _open_backing()
        with b2:
            active["bpm"] = st.slider(
                "BPM",
                50,
                180,
                int(active.get("bpm", 100)),
                5,
                key="cpl_bpm_finish",
            )
        with b3:
            active["loops"] = st.slider(
                "Loops",
                1,
                10,
                int(active.get("loops", 2)),
                1,
                key="cpl_loops_finish",
            )
        if st.button("← Keep editing", key="cpl_unfinish", use_container_width=True):
            st.session_state["cpl_finished"] = False
            st.rerun()
        st.session_state[CPL_ACTIVE_KEY] = active
        return

    # --- Builder mode ---
    style = st.selectbox(
        "What kind of progression do you want?",
        CPL_PROGRESSION_STYLES,
        index=CPL_PROGRESSION_STYLES.index(
            active.get("progression_style", "Pop")
            if active.get("progression_style") in CPL_PROGRESSION_STYLES
            else "Pop"
        ),
        key="cpl_style",
    )
    if active.get("progression_style") != style:
        active["progression_style"] = style
        _save()

    edit_section = st.selectbox("Section", CPL_UI_SECTION_ORDER, key="cpl_edit_section")
    home_entries = home_sections[edit_section]
    section_display = display_entries_for_section(active, display_key, edit_section)
    simple = simple_chords_for_key(display_key)
    style_presets = presets_for_style(style)

    st.markdown(f"**Key:** {key_label} · **Section:** {edit_section}")

    if not section_is_empty(home_entries):
        st.markdown(
            entries_chord_tiles_html(section_display),
            unsafe_allow_html=True,
        )

    st.markdown("**Bars**")
    add_bars = st.radio(
        "Bars",
        [1, 2, 4],
        format_func=lambda n: "1 bar" if n == 1 else f"{n} bars",
        horizontal=True,
        key="cpl_add_bars",
        label_visibility="collapsed",
    )

    st.markdown("**Click a chord to add it**")
    cols = st.columns(min(6, max(1, len(simple))))
    for i, ch in enumerate(simple):
        with cols[i % len(cols)]:
            if st.button(ch, key=f"cpl_add_{ns}_{edit_section}_{ch}", use_container_width=True):
                home_entries.append({"chord": ch, "bars": int(add_bars)})
                _save()
                st.rerun()

    st.markdown("**Type any chord**")
    cc1, cc2 = st.columns([3, 1])
    with cc1:
        custom_ch = st.text_input(
            "Type any chord",
            placeholder="Bb, B7, F#dim, Eb, G7, Cmaj7…",
            key=f"cpl_custom_{edit_section}",
            label_visibility="collapsed",
        )
    with cc2:
        if st.button("Add", key=f"cpl_custom_add_{edit_section}", use_container_width=True):
            ch = normalize_chord_symbol(custom_ch)
            if ch:
                home_entries.append({"chord": ch, "bars": int(add_bars)})
                _save()
                st.rerun()

    with st.expander("Extensions — optional", expanded=False):
        st.caption("Choose a root, then tap an extension to add that chord.")
        st.session_state.setdefault("cpl_ext_root", simple[0] if simple else "C")
        rcols = st.columns(min(6, max(1, len(simple))))
        for i, ch in enumerate(simple):
            with rcols[i % len(rcols)]:
                if st.button(ch, key=f"cpl_ext_root_{ns}_{edit_section}_{ch}"):
                    st.session_state["cpl_ext_root"] = ch
                    st.rerun()
        st.markdown(f"**Root:** {st.session_state['cpl_ext_root']}")
        ecols = st.columns(len(CHORD_QUICK_EDIT_KEYS))
        for i, ek in enumerate(CHORD_QUICK_EDIT_KEYS):
            with ecols[i]:
                if st.button(ek, key=f"cpl_ext_{ns}_{edit_section}_{ek}"):
                    staged = apply_quick_chord_edit(st.session_state["cpl_ext_root"], ek)
                    home_entries.append({"chord": staged, "bars": int(add_bars)})
                    _save()
                    st.rerun()

    if style_presets:
        st.markdown("**Presets**")
        st.caption(f"{style} progressions in **{key_label}** — applies to **{edit_section}** only.")
        for preset_id, spec in style_presets.items():
            label = preset_button_label(preset_id, display_key, spec)
            if st.button(label, key=f"cpl_pre_{ns}_{style}_{edit_section}_{preset_id}", use_container_width=True):
                home_sections[edit_section] = build_style_preset_entries(style, preset_id, display_key)
                _save()
                st.rerun()

    st.markdown("---")
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        if st.button(
            "Undo last chord",
            key=f"cpl_undo_{edit_section}",
            use_container_width=True,
            disabled=not home_entries,
        ):
            home_entries.pop()
            _save()
            st.rerun()
    with a2:
        if st.button(
            "Clear section",
            key=f"cpl_clear_{edit_section}",
            use_container_width=True,
            disabled=section_is_empty(home_entries),
        ):
            home_sections[edit_section] = []
            _save()
            st.rerun()
    with a3:
        if st.button(
            "Clear all",
            key="cpl_clear_all",
            use_container_width=True,
            disabled=progression_is_empty(home_sections),
        ):
            clear_all_cpl_sections(home_sections)
            _save()
            st.rerun()
    with a4:
        finish_disabled = not filled_section_names(home_sections)
        if st.button(
            "Finish Song",
            key="cpl_finish",
            type="primary",
            use_container_width=True,
            disabled=finish_disabled,
        ):
            st.session_state["cpl_finished"] = True
            _save()
            st.rerun()

    if filled_section_names(home_sections):
        st.markdown("### Song structure")
        st.markdown(
            song_structure_overview_html(
                active,
                display_key,
                highlight_section=edit_section,
                only_filled=True,
            ),
            unsafe_allow_html=True,
        )

    with st.expander("Save / reset", expanded=False):
        if st.button("Start fresh", key="cpl_reset_all"):
            st.session_state[CPL_ACTIVE_KEY] = default_active_progression()
            st.session_state["original_key_center"] = display_key
            st.session_state.pop("_cpl_editing_display_key", None)
            st.session_state.pop("cpl_finished", None)
            invalidate_cpl_derived_outputs(st.session_state)
            st.rerun()
        saved = st.session_state[CPL_SAVED_KEY]
        if st.button("Save song", key="cpl_save_btn"):
            save_progression(saved, active.get("name", "My song"), active)
            st.success("Saved.")

    st.session_state[CPL_ACTIVE_KEY] = active

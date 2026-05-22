"""Custom Progression — simple click-to-build song (beginner-first)."""

from __future__ import annotations


def render_custom_progression_lab_page() -> None:
    import html

    import streamlit as st

    from custom_progression_lab import (
        CHORD_QUICK_EDIT_KEYS,
        CPL_ACTIVE_KEY,
        CPL_EDITABLE_SECTIONS,
        CPL_SAVED_KEY,
        apply_quick_chord_edit,
        backing_signature,
        build_preset_entries,
        build_simple_preset_entries,
        commit_home_sections,
        deep_copy_sections,
        diatonic_chords_for_key,
        display_entries_for_section,
        display_sections_for_key,
        ensure_all_cpl_sections,
        ensure_cpl_editing_in_display_key,
        ensure_original_structure,
        flatten_sections_to_events,
        format_entries_bar_line,
        format_key_label,
        invalidate_cpl_derived_outputs,
        normalize_chord_symbol,
        parse_chord_line,
        progression_is_empty,
        save_progression,
        section_is_empty,
        simple_chords_for_key,
        song_structure_overview_html,
        harmonic_analysis_markdown,
        lab_context_for_coaching,
        SIMPLE_PRESET_SPECS,
    )
    from progression_helpers import (
        default_active_progression,
        generate_backing_track,
        infer_groove_style,
        invalidate_backing_cache,
        is_custom_progression,
        render_cpl_page_header,
        section_overlay_html,
        session_display_key,
        session_focus,
        session_instrument,
        session_level,
    )
    from songs.music_source import note_active_source_change, set_custom_source

    render_cpl_page_header()

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

    if st.session_state.get("cpl_edit_section") not in CPL_EDITABLE_SECTIONS:
        st.session_state["cpl_edit_section"] = "Verse"

    def _save() -> None:
        nonlocal active, home_sections
        active = commit_home_sections(active, home_sections)
        active["user_locked_home_key"] = True
        st.session_state[CPL_ACTIVE_KEY] = active

    st.markdown("## Click chords to build a simple song")
    st.caption(
        "Set your key on the **left** (Practice / Display Key). Pick a section. Click chords. Done."
    )

    if st.button("Use as active song", key="cpl_set_active_source"):
        set_custom_source(st.session_state)
        note_active_source_change(st, invalidate_backing=invalid_backing_cache)
        st.rerun()

    view_full = st.toggle("View full song", key="cpl_view_full_song", value=False)

    if view_full:
        st.markdown("### Full song")
        st.markdown(
            song_structure_overview_html(active, display_key),
            unsafe_allow_html=True,
        )
        st.caption("Turn off **View full song** to add chords to one section.")
    else:
        edit_section = st.selectbox(
            "Section",
            CPL_EDITABLE_SECTIONS,
            key="cpl_edit_section",
        )

        home_entries = home_sections[edit_section]
        section_display = display_entries_for_section(active, display_key, edit_section)
        simple = simple_chords_for_key(display_key)

        st.markdown(f"**Key:** {key_label} · **Section:** {edit_section}")

        st.markdown(f"#### Your {edit_section} progression")
        if section_is_empty(home_entries):
            st.markdown(
                '<p class="cpl-progression-line cpl-empty">(empty)</p>',
                unsafe_allow_html=True,
            )
            st.info("Click chords below to start building your progression.")
        else:
            bar = format_entries_bar_line(section_display)
            st.markdown(f'<p class="cpl-progression-line">{html.escape(bar)}</p>', unsafe_allow_html=True)

        st.markdown("#### Click a chord to add it")
        cols = st.columns(min(6, len(simple)))
        for i, ch in enumerate(simple):
            with cols[i % len(cols)]:
                if st.button(ch, key=f"cpl_add_{ns}_{edit_section}_{ch}", use_container_width=True):
                    home_entries.append({"chord": ch, "bars": 1})
                    _save()
                    st.rerun()

        u1, u2, u3 = st.columns([1, 1, 1])
        with u1:
            if st.button("↩ Undo last chord", key=f"cpl_undo_{edit_section}", use_container_width=True, type="primary"):
                if home_entries:
                    home_entries.pop()
                    _save()
                    st.rerun()
        with u2:
            if st.button("Clear this section", key=f"cpl_clear_{edit_section}", use_container_width=True):
                home_sections[edit_section] = []
                _save()
                st.rerun()
        with u3:
            simple_presets = list(SIMPLE_PRESET_SPECS.keys())
            pick = st.selectbox("Quick fill", ["—"] + simple_presets, key=f"cpl_simp_pre_{edit_section}")
            if st.button("Apply quick fill", key=f"cpl_simp_apply_{edit_section}", disabled=pick == "—"):
                home_sections[edit_section] = build_simple_preset_entries(pick, display_key)
                _save()
                st.rerun()

        with st.expander("Advanced chord options (optional)", expanded=False):
            st.caption("Jazz chords, custom types, and editing — only if you want them.")
            jazz = diatonic_chords_for_key(display_key)
            if jazz:
                st.markdown("**More chord colors**")
                jcols = st.columns(4)
                for i, ch in enumerate(jazz):
                    with jcols[i % 4]:
                        if st.button(ch, key=f"cpl_jazz_{ns}_{edit_section}_{ch}"):
                            home_entries.append({"chord": ch, "bars": 1})
                            _save()
                            st.rerun()
            if home_entries and not section_is_empty(home_entries):
                last = home_entries[-1]
                last_disp = section_display[-1]["chord"] if section_display else last.get("chord", "")
                st.markdown(f"**Last chord:** {last_disp}")
                eq = st.columns(len(CHORD_QUICK_EDIT_KEYS))
                for i, ek in enumerate(CHORD_QUICK_EDIT_KEYS):
                    with eq[i]:
                        if st.button(f"+{ek}", key=f"cpl_adv_{ns}_{edit_section}_{ek}"):
                            last["chord"] = apply_quick_chord_edit(last.get("chord", ""), ek)
                            _save()
                            st.rerun()
            custom = st.text_input("Custom chord", placeholder="F#m9", key="cpl_custom_adv")
            if st.button("Add custom chord", key="cpl_custom_adv_btn"):
                ch = normalize_chord_symbol(custom)
                if ch:
                    home_entries.append({"chord": ch, "bars": 1})
                    _save()
                    st.rerun()
            paste = st.text_input("Paste chords", placeholder="C | G | Am", key="cpl_paste_adv")
            if st.button("Add pasted", key="cpl_paste_adv_btn"):
                for item in parse_chord_line(paste):
                    home_entries.append(item)
                _save()
                st.rerun()
            from custom_progression_lab import CPL_PRESET_NAMES

            st.markdown("**Jazz presets** (replace this section)")
            for pname in CPL_PRESET_NAMES:
                if st.button(pname, key=f"cpl_jpre_{ns}_{edit_section}_{pname}"):
                    home_sections[edit_section] = build_preset_entries(pname, display_key)
                    _save()
                    st.rerun()
            for idx, entry in enumerate(list(home_entries)):
                entry["chord"] = st.text_input(
                    f"Slot {idx + 1}",
                    value=entry.get("chord", ""),
                    key=f"cpl_edit_slot_{ns}_{edit_section}_{idx}",
                )
                entry["bars"] = int(
                    st.number_input(
                        "Bars",
                        1,
                        16,
                        int(entry.get("bars", 1)),
                        key=f"cpl_edit_bars_{ns}_{edit_section}_{idx}",
                    )
                )
            _save()

    st.markdown("### Song structure")
    st.markdown(
        song_structure_overview_html(active, display_key, highlight_section=st.session_state.get("cpl_edit_section")),
        unsafe_allow_html=True,
    )

    _save()
    display_sections = deep_copy_sections(display_sections_for_key(active, display_key))

    with st.expander("Save / reset song", expanded=False):
        if st.button("Start fresh (empty song)", key="cpl_reset_all"):
            st.session_state[CPL_ACTIVE_KEY] = default_active_progression()
            st.session_state["original_key_center"] = display_key
            st.session_state.pop("_cpl_editing_display_key", None)
            invalidate_cpl_derived_outputs(st.session_state)
            st.rerun()
        saved = st.session_state[CPL_SAVED_KEY]
        if st.button("Save song", key="cpl_save_btn"):
            save_progression(saved, active.get("name", "My song"), active)
            st.success("Saved.")

    st.markdown("---")
    st.markdown("### Play")
    loops = st.slider("Loop repeats", 1, 12, int(active.get("loops", 2)), key="cpl_loops")
    active["loops"] = loops
    active["bpm"] = st.slider("BPM", 50, 200, int(active.get("bpm", 100)), 5, key="cpl_bpm")
    events = flatten_sections_to_events(display_sections)
    groove = infer_groove_style({}, active.get("groove_style", "Auto"))

    p1, p2 = st.columns(2)
    with p1:
        if st.button("▶ Play", key="cpl_play_button", disabled=not events, type="primary", use_container_width=True):
            st.session_state["cpl_backing_wav"] = generate_backing_track(
                events,
                bpm=int(active["bpm"]),
                loops=loops,
                style=groove,
                level=session_level(st.session_state),
                song_title=active.get("name", "My song"),
                song_artist="",
            )
            st.rerun()
    with p2:
        if st.button("Stop", key="cpl_stop_backing", use_container_width=True):
            st.session_state.pop("cpl_backing_wav", None)
            st.rerun()
    if st.session_state.get("cpl_backing_wav"):
        st.audio(st.session_state["cpl_backing_wav"], format="audio/wav")

    st.session_state[CPL_ACTIVE_KEY] = active

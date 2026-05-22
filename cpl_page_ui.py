"""Custom Progression — simple practice backing-track builder (beginner-first)."""

from __future__ import annotations


def render_custom_progression_lab_page() -> None:
    import html

    import streamlit as st

    from custom_progression_lab import (
        CHORD_QUICK_EDIT_KEYS,
        CPL_ACTIVE_KEY,
        CPL_BUILDER_VERSION,
        CPL_PRESET_NAMES,
        CPL_SAVED_KEY,
        CPL_UI_SECTION_ORDER,
        apply_quick_chord_edit,
        build_preset_entries,
        build_simple_preset_entries,
        clear_all_cpl_sections,
        commit_home_sections,
        deep_copy_sections,
        display_entries_for_section,
        display_sections_for_key,
        ensure_all_cpl_sections,
        ensure_cpl_editing_in_display_key,
        ensure_original_structure,
        flatten_sections_to_events,
        format_entries_bar_line,
        format_entries_friendly_line,
        format_key_label,
        invalidate_cpl_derived_outputs,
        normalize_chord_symbol,
        parse_chord_line,
        prepare_cpl_backing_handoff,
        progression_is_empty,
        save_progression,
        section_is_empty,
        simple_chords_for_key,
        song_structure_overview_html,
        SIMPLE_PRESET_SPECS,
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

    if st.session_state.get("cpl_edit_section") not in CPL_UI_SECTION_ORDER:
        st.session_state["cpl_edit_section"] = "Verse"

    def _save() -> None:
        nonlocal active, home_sections
        active = commit_home_sections(active, home_sections)
        active["user_locked_home_key"] = True
        st.session_state[CPL_ACTIVE_KEY] = active

    def _open_backing(*, section: str | None = None) -> None:
        _save()
        set_custom_source(st.session_state)
        note_active_source_change(st, invalidate_backing=invalid_backing_cache)
        focus = section
        if focus and section_is_empty(home_sections.get(focus, [])):
            focus = None
        prepare_cpl_backing_handoff(st.session_state, active, section=focus)
        st.session_state["studio_page"] = "backing"
        st.rerun()

    st.markdown("## Build a simple progression for practice")
    st.caption(
        "1. Set key on the **left** · 2. Pick a section · 3. Click chords · "
        "4. **Open in Backing Track** to play with loop, BPM, and groove."
    )
    st.markdown(
        '<p class="cpl-flow-hint">To transpose, change the global key on the left.</p>',
        unsafe_allow_html=True,
    )

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
            CPL_UI_SECTION_ORDER,
            key="cpl_edit_section",
        )

        home_entries = home_sections[edit_section]
        section_display = display_entries_for_section(active, display_key, edit_section)
        simple = simple_chords_for_key(display_key)

        st.markdown(f"**Key:** {key_label} · **Section:** {edit_section}")

        st.markdown(f"#### {edit_section}")
        if section_is_empty(home_entries):
            st.markdown(
                '<p class="cpl-progression-line cpl-empty">Empty — click a chord or preset to start.</p>',
                unsafe_allow_html=True,
            )
        else:
            friendly = format_entries_friendly_line(section_display)
            bar = format_entries_bar_line(section_display)
            st.markdown(
                f'<p class="cpl-progression-line">{html.escape(friendly)}</p>'
                f'<p class="cpl-progression-line cpl-bar-detail">{html.escape(bar)}</p>',
                unsafe_allow_html=True,
            )

        st.markdown("**Bars** (for the next chord you add)")
        add_bars = st.radio(
            "Bars",
            [1, 2, 4],
            format_func=lambda n: "1 bar" if n == 1 else f"{n} bars",
            horizontal=True,
            key="cpl_add_bars",
            label_visibility="collapsed",
        )

        st.markdown("#### Click a chord")
        cols = st.columns(min(6, max(1, len(simple))))
        for i, ch in enumerate(simple):
            with cols[i % len(cols)]:
                if st.button(ch, key=f"cpl_add_{ns}_{edit_section}_{ch}", use_container_width=True):
                    home_entries.append({"chord": ch, "bars": int(add_bars)})
                    _save()
                    st.rerun()

        st.markdown("#### Actions")
        a1, a2, a3 = st.columns(3)
        with a1:
            if st.button(
                "↩ Undo last chord",
                key=f"cpl_undo_{edit_section}",
                use_container_width=True,
                disabled=not home_entries,
            ):
                home_entries.pop()
                _save()
                st.rerun()
        with a2:
            if st.button(
                "Clear this section",
                key=f"cpl_clear_{edit_section}",
                use_container_width=True,
                disabled=section_is_empty(home_entries),
            ):
                home_sections[edit_section] = []
                _save()
                st.rerun()
        with a3:
            if st.button(
                "Clear all sections",
                key="cpl_clear_all",
                use_container_width=True,
                disabled=progression_is_empty(home_sections),
            ):
                clear_all_cpl_sections(home_sections)
                _save()
                st.rerun()

        with st.expander("Quick presets (optional)", expanded=False):
            st.caption("Only fills the section you are editing — nothing is added until you click Apply.")
            simple_presets = list(SIMPLE_PRESET_SPECS.keys())
            pick = st.selectbox("Preset", ["—"] + simple_presets, key=f"cpl_simp_pre_{edit_section}")
            if st.button(
                "Apply preset to this section",
                key=f"cpl_simp_apply_{edit_section}",
                disabled=pick == "—",
            ):
                home_sections[edit_section] = build_simple_preset_entries(pick, display_key)
                _save()
                st.rerun()

        with st.expander("Advanced chord colors (optional)", expanded=False):
            st.caption("Pick a root, add a color, choose bars, then **Add chord**.")
            st.session_state.setdefault("cpl_adv_root", simple[0] if simple else "C")
            st.session_state.setdefault("cpl_adv_suffix", "")
            rcols = st.columns(min(6, max(1, len(simple))))
            for i, ch in enumerate(simple):
                with rcols[i % len(rcols)]:
                    if st.button(ch, key=f"cpl_adv_root_{ns}_{edit_section}_{ch}"):
                        st.session_state["cpl_adv_root"] = ch
                        st.session_state["cpl_adv_suffix"] = ""
                        st.rerun()
            st.markdown(f"**Root:** {st.session_state['cpl_adv_root']}")
            ecols = st.columns(len(CHORD_QUICK_EDIT_KEYS))
            for i, ek in enumerate(CHORD_QUICK_EDIT_KEYS):
                with ecols[i]:
                    if st.button(ek, key=f"cpl_adv_col_{ns}_{edit_section}_{ek}"):
                        st.session_state["cpl_adv_suffix"] = ek
                        st.rerun()
            suffix = st.session_state.get("cpl_adv_suffix", "")
            root = st.session_state["cpl_adv_root"]
            staged = apply_quick_chord_edit(root, suffix) if suffix else root
            st.markdown(f"**Chord:** {staged}")
            adv_bars = st.radio(
                "Bars",
                [1, 2, 4],
                format_func=lambda n: "1 bar" if n == 1 else f"{n} bars",
                horizontal=True,
                key="cpl_adv_bars",
            )
            if st.button("Add chord", key=f"cpl_adv_add_{edit_section}", type="primary"):
                home_entries.append({"chord": staged, "bars": int(adv_bars)})
                _save()
                st.rerun()
            custom = st.text_input("Or type a chord", placeholder="Dmaj7", key="cpl_custom_adv")
            if st.button("Add typed chord", key="cpl_custom_adv_btn"):
                ch = normalize_chord_symbol(custom)
                if ch:
                    home_entries.append({"chord": ch, "bars": int(adv_bars)})
                    _save()
                    st.rerun()
            paste = st.text_input("Paste line", placeholder="C | G | Am | F", key="cpl_paste_adv")
            if st.button("Add pasted chords", key="cpl_paste_adv_btn"):
                for item in parse_chord_line(paste):
                    home_entries.append(item)
                _save()
                st.rerun()
            st.markdown("**Jazz presets** (replace this section only)")
            for pname in CPL_PRESET_NAMES:
                if st.button(pname, key=f"cpl_jpre_{ns}_{edit_section}_{pname}"):
                    home_sections[edit_section] = build_preset_entries(pname, display_key)
                    _save()
                    st.rerun()

    st.markdown("### Song structure")
    st.markdown(
        song_structure_overview_html(
            active,
            display_key,
            highlight_section=st.session_state.get("cpl_edit_section"),
        ),
        unsafe_allow_html=True,
    )

    _save()
    display_sections = deep_copy_sections(display_sections_for_key(active, display_key))
    has_chords = bool(flatten_sections_to_events(display_sections))

    st.markdown("---")
    st.markdown("### Backing Track")
    st.caption("Practice with the full Backing Track page — same controls as catalog songs.")

    tempo_col, loop_col = st.columns(2)
    with tempo_col:
        active["bpm"] = st.slider("BPM (for backing track)", 50, 180, int(active.get("bpm", 100)), 5, key="cpl_bpm")
    with loop_col:
        active["loops"] = st.slider("Loops (for backing track)", 1, 10, int(active.get("loops", 2)), 1, key="cpl_loops")

    open_col, full_col = st.columns(2)
    with open_col:
        if st.button(
            "▶ Open in Backing Track",
            key="cpl_to_backing",
            type="primary",
            use_container_width=True,
            disabled=not has_chords,
        ):
            _open_backing(section=st.session_state.get("cpl_edit_section"))
    with full_col:
        if st.button(
            "Open full song in Backing Track",
            key="cpl_to_backing_full",
            use_container_width=True,
            disabled=not has_chords,
        ):
            _open_backing(section=None)

    if not has_chords:
        st.info("Add at least one chord, then open in Backing Track to play.")

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

    st.session_state[CPL_ACTIVE_KEY] = active

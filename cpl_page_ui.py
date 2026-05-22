"""Custom Progression — build one section at a time from sidebar key."""

from __future__ import annotations


def render_custom_progression_lab_page() -> None:
    import html

    import streamlit as st

    from custom_progression_lab import (
        CPL_ACTIVE_KEY,
        CPL_EDITABLE_SECTIONS,
        CPL_PRESET_NAMES,
        CPL_SAVED_KEY,
        CPL_SECTION_NAMES,
        apply_style_preset,
        backing_signature,
        build_preset_entries,
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
        parse_chord_line,
        save_progression,
        sync_written_home_key,
        harmonic_analysis_markdown,
        lab_context_for_coaching,
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

    if st.button("Use as active song", key="cpl_set_active_source", type="primary"):
        set_custom_source(st.session_state)
        note_active_source_change(st, invalidate_backing=invalid_backing_cache)
        st.rerun()

    if is_custom_progression(st.session_state):
        st.caption("This progression is your **active song** across the app.")
    else:
        st.caption("Click **Use as active song** when you are ready to practice with this progression.")

    if CPL_ACTIVE_KEY not in st.session_state:
        st.session_state[CPL_ACTIVE_KEY] = default_active_progression()
    if CPL_SAVED_KEY not in st.session_state:
        st.session_state[CPL_SAVED_KEY] = {}

    display_key = session_display_key(st.session_state)
    active = ensure_original_structure(st.session_state[CPL_ACTIVE_KEY])
    active = ensure_cpl_editing_in_display_key(st, active, display_key)
    active = sync_written_home_key(active)
    st.session_state[CPL_ACTIVE_KEY] = active
    saved = st.session_state[CPL_SAVED_KEY]

    key_label = format_key_label(display_key)
    cpl_widget_ns = display_key.replace("#", "s").replace("b", "f")

    home_sections = ensure_all_cpl_sections(active.get("original_sections") or {})
    active["original_sections"] = home_sections

    if st.session_state.get("cpl_edit_section") not in CPL_SECTION_NAMES:
        st.session_state["cpl_edit_section"] = "Verse"

    active["name"] = st.text_input(
        "Progression name",
        value=active.get("name", "My progression"),
        key="cpl_title",
    )

    st.markdown(
        """
<div class="cpl-flow-hint">
<strong>Build your song</strong><br>
① Set <strong>key</strong> in the left sidebar ·
② Pick a <strong>section</strong> ·
③ Click <strong>suggested chords</strong> or a <strong>preset</strong> ·
④ Edit below ·
⑤ Play
</div>
""",
        unsafe_allow_html=True,
    )

    head_l, head_r = st.columns([1, 1])
    with head_l:
        st.markdown(f"### Current key: **{key_label}**")
    with head_r:
        edit_section = st.selectbox(
            "Selected section",
            CPL_SECTION_NAMES,
            key="cpl_edit_section",
        )

    st.caption(
        "To transpose the **entire** progression, change **Practice / Display Key** on the **left** panel. "
        "Suggestions and presets update to match."
    )

    can_edit = edit_section != "Full Song"
    section_display_entries = display_entries_for_section(active, display_key, edit_section)
    home_entries = list(home_sections.get(edit_section, []) if can_edit else [])

    suggested = diatonic_chords_for_key(display_key)

    def _save_sections() -> None:
        nonlocal active, home_sections
        active = commit_home_sections(active, home_sections)
        st.session_state[CPL_ACTIVE_KEY] = active

    st.markdown("#### Add chords")
    if not can_edit:
        st.warning(
            "**Full Song** shows every section combined. Select **Intro**, **Verse**, **Chorus**, etc. "
            "to add or edit chords for that part."
        )
    else:
        st.markdown(f"**Suggested chords in {key_label}** — click to add to **{edit_section}**")
        if suggested:
            ncols = min(len(suggested), 4)
            row = st.columns(ncols)
            for i, ch in enumerate(suggested):
                with row[i % ncols]:
                    if st.button(
                        ch,
                        key=f"cpl_add_{cpl_widget_ns}_{edit_section}_{ch}",
                        use_container_width=True,
                    ):
                        home_sections[edit_section].append({"chord": ch, "bars": 1})
                        _save_sections()
                        st.rerun()
        else:
            st.caption("Set a key in the sidebar to see suggestions.")

        st.markdown(f"**Presets in {key_label}** — fills **{edit_section}**")
        pcols = st.columns(min(len(CPL_PRESET_NAMES), 5))
        for i, pname in enumerate(CPL_PRESET_NAMES):
            with pcols[i % len(pcols)]:
                if st.button(
                    pname,
                    key=f"cpl_preset_{cpl_widget_ns}_{edit_section}_{pname}",
                    use_container_width=True,
                ):
                    home_sections[edit_section] = build_preset_entries(pname, display_key)
                    _save_sections()
                    st.rerun()

    st.markdown(f"#### Your progression for **{edit_section}**")
    bar_line = format_entries_bar_line(section_display_entries)
    st.markdown(f'<p class="cpl-progression-line">{bar_line}</p>', unsafe_allow_html=True)

    if can_edit:
        st.markdown("#### Edit progression")
        if not home_entries:
            st.caption("Empty — click a suggested chord or preset above to start building.")
        else:
            st.caption("Reorder, change length, substitute, or remove each slot.")

        remove_indices: list[int] = []
        for idx, entry in enumerate(list(home_entries)):
            disp_ch = section_display_entries[idx]["chord"] if idx < len(section_display_entries) else entry.get("chord", "")
            st.markdown(
                f'<div class="cpl-slot-row"><span class="cpl-slot-chord">{html.escape(str(disp_ch))}</span></div>',
                unsafe_allow_html=True,
            )
            c1, c2, c3, c4, c5 = st.columns([1.2, 0.8, 0.35, 0.35, 1.5])
            with c1:
                entry["bars"] = int(
                    st.number_input(
                        "Bars",
                        min_value=1,
                        max_value=16,
                        value=int(entry.get("bars", 1)),
                        key=f"cpl_bars_{cpl_widget_ns}_{edit_section}_{idx}",
                    )
                )
            with c2:
                if st.button("Remove", key=f"cpl_rm_{cpl_widget_ns}_{edit_section}_{idx}"):
                    remove_indices.append(idx)
            with c3:
                if st.button("↑", key=f"cpl_up_{cpl_widget_ns}_{edit_section}_{idx}", disabled=idx == 0):
                    home_entries[idx], home_entries[idx - 1] = home_entries[idx - 1], home_entries[idx]
                    home_sections[edit_section] = home_entries
                    _save_sections()
                    st.rerun()
            with c4:
                if st.button(
                    "↓",
                    key=f"cpl_dn_{cpl_widget_ns}_{edit_section}_{idx}",
                    disabled=idx >= len(home_entries) - 1,
                ):
                    home_entries[idx], home_entries[idx + 1] = home_entries[idx + 1], home_entries[idx]
                    home_sections[edit_section] = home_entries
                    _save_sections()
                    st.rerun()
            with c5:
                sub_opts = [disp_ch] + [c for c in suggested if c != disp_ch]
                pick = st.selectbox(
                    "Substitute",
                    sub_opts,
                    index=0,
                    key=f"cpl_sub_{cpl_widget_ns}_{edit_section}_{idx}",
                    label_visibility="collapsed",
                )
                if pick != disp_ch and st.button(
                    "Apply",
                    key=f"cpl_sub_apply_{cpl_widget_ns}_{edit_section}_{idx}",
                ):
                    entry["chord"] = pick
                    home_sections[edit_section] = home_entries
                    _save_sections()
                    st.rerun()

        for ri in sorted(remove_indices, reverse=True):
            home_entries.pop(ri)
        if remove_indices:
            home_sections[edit_section] = home_entries
            _save_sections()
            st.rerun()

        paste_col, clear_col = st.columns(2)
        with paste_col:
            bulk = st.text_input(
                "Paste chords",
                placeholder="Dm7 | G7 | Cmaj7",
                key="cpl_progression_editor",
                label_visibility="collapsed",
            )
            if st.button("Add pasted chords", key="cpl_bulk_add"):
                for item in parse_chord_line(bulk):
                    home_entries.append(item)
                home_sections[edit_section] = home_entries
                _save_sections()
                st.rerun()
        with clear_col:
            if st.button(f"Clear {edit_section}", key=f"cpl_clear_{edit_section}"):
                home_sections[edit_section] = []
                _save_sections()
                st.rerun()

    _save_sections()
    display_sections = deep_copy_sections(display_sections_for_key(active, display_key))

    with st.expander("Optional: style template & saved progressions", expanded=False):
        from custom_progression_lab import CPL_STYLE_CHOICES

        style_pick = st.selectbox("Style template", CPL_STYLE_CHOICES, key="cpl_style_select")
        if st.button("Apply style to all sections", key="cpl_apply_style"):
            preset = apply_style_preset(style_pick, display_key)
            if preset:
                active["groove_style"] = preset["groove_style"]
                home_sections = ensure_all_cpl_sections(preset["sections"])
                active = commit_home_sections(active, home_sections)
                st.session_state[CPL_ACTIVE_KEY] = active
                st.rerun()
        if st.button("Harmonic analysis", key="cpl_analyze"):
            st.session_state["cpl_analysis_md"] = harmonic_analysis_markdown(
                display_sections, display_key, active.get("time_signature", "4/4")
            )
        if st.session_state.get("cpl_analysis_md"):
            st.markdown(st.session_state["cpl_analysis_md"])
        save_name = st.text_input("Save as", value=active.get("name", "Untitled"), key="cpl_save_name")
        if st.button("Save progression", key="cpl_save_btn"):
            save_progression(saved, save_name.strip() or "Untitled", active)
            st.session_state[CPL_SAVED_KEY] = saved
            st.success(f"Saved **{save_name}**.")
        if saved:
            pick_saved = st.selectbox("Load saved", ["—"] + sorted(saved.keys()), key="cpl_pick_saved")
            if st.button("Load", key="cpl_load_btn", disabled=pick_saved == "—"):
                st.session_state[CPL_ACTIVE_KEY] = ensure_original_structure(dict(saved[pick_saved]))
                st.session_state.pop("_cpl_editing_display_key", None)
                invalidate_cpl_derived_outputs(st.session_state)
                st.rerun()
        if st.button("Start fresh (empty all sections)", key="cpl_reset_all"):
            fresh = default_active_progression()
            fresh["name"] = active.get("name", "My progression")
            fresh["original_key_center"] = display_key
            st.session_state[CPL_ACTIVE_KEY] = fresh
            st.session_state.pop("_cpl_editing_display_key", None)
            invalidate_cpl_derived_outputs(st.session_state)
            st.rerun()

    st.markdown("---")
    st.markdown("### Practice & playback")
    active["time_signature"] = st.selectbox(
        "Time signature",
        ["4/4", "3/4", "6/8"],
        index=["4/4", "3/4", "6/8"].index(active.get("time_signature", "4/4"))
        if active.get("time_signature", "4/4") in ["4/4", "3/4", "6/8"]
        else 0,
        key="cpl_time_sig",
    )
    pb1, pb2, pb3 = st.columns(3)
    with pb1:
        active["bpm"] = st.slider("BPM", 50, 200, int(active.get("bpm", 100)), 5, key="cpl_bpm")
    with pb2:
        active["loops"] = st.slider("Loop repeats", 1, 12, int(active.get("loops", 2)), 1, key="cpl_loops")
    with pb3:
        _groove_opts = ["Auto", "Pop groove", "Rock groove", "Jazz swing", "Bossa nova", "Funk groove", "Ballad"]
        _gcur = active.get("groove_style", "Auto")
        active["groove_style"] = st.selectbox(
            "Groove",
            _groove_opts,
            index=_groove_opts.index(_gcur) if _gcur in _groove_opts else 0,
            key="cpl_groove",
        )

    st.session_state[CPL_ACTIVE_KEY] = active
    cpl_events = flatten_sections_to_events(display_sections)
    cpl_groove = infer_groove_style({}, active.get("groove_style", "Auto"))
    cpl_sig = backing_signature(
        display_key,
        display_sections,
        active.get("bpm", 100),
        active.get("loops", 2),
        cpl_groove,
    )

    play_c1, play_c2 = st.columns(2)
    with play_c1:
        gen = st.button(
            "Generate backing track",
            key="cpl_play_button",
            disabled=not cpl_events,
            type="primary",
            use_container_width=True,
        )
    with play_c2:
        stop = st.button("Stop / clear backing", key="cpl_stop_backing", use_container_width=True)

    if stop:
        st.session_state.pop("cpl_backing_wav", None)
        st.session_state.pop("cpl_backing_signature", None)
        st.rerun()
    if gen and cpl_events:
        st.session_state["cpl_backing_wav"] = generate_backing_track(
            cpl_events,
            bpm=int(active.get("bpm", 100)),
            loops=int(active.get("loops", 2)),
            style=cpl_groove,
            level=session_level(st.session_state),
            song_title=active.get("name", "Custom"),
            song_artist="",
        )
        st.session_state["cpl_backing_signature"] = cpl_sig
        st.rerun()

    if st.session_state.get("cpl_backing_wav"):
        st.audio(st.session_state["cpl_backing_wav"], format="audio/wav")

    pt1, pt2 = st.columns(2)
    with pt1:
        if st.button("Send to Practice page", key="cpl_to_practice", use_container_width=True):
            set_custom_source(st.session_state)
            st.session_state["studio_page"] = "practice"
            st.rerun()
    with pt2:
        if st.button("Open Backing Track page", key="cpl_to_backing", use_container_width=True):
            st.session_state["studio_page"] = "backing"
            st.rerun()

    _inst = session_instrument(st.session_state)
    _lvl = session_level(st.session_state)
    _foc = session_focus(st.session_state)
    coach_ctx = lab_context_for_coaching(display_sections, display_key, _inst, _lvl, _foc)
    if coach_ctx["first_chords"]:
        st.info(
            section_overlay_html(
                _inst,
                _foc,
                coach_ctx["first_chords"],
                section_name=coach_ctx["first_section"],
                groove_style=cpl_groove,
                time_signature=active.get("time_signature", "4/4"),
                bpm=int(active.get("bpm", 100)),
            )
        )

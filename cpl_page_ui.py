"""Custom Progression page — key from sidebar, clear build flow."""

from __future__ import annotations


def render_custom_progression_lab_page() -> None:
    import streamlit as st

    from custom_progression_lab import (
        CPL_ACTIVE_KEY,
        CPL_SAVED_KEY,
        CPL_STYLE_CHOICES,
        apply_style_preset,
        backing_signature,
        build_preset_entries,
        chord_tiles_html,
        commit_home_sections,
        deep_copy_sections,
        display_sections_for_key,
        ensure_cpl_editing_in_display_key,
        ensure_original_structure,
        flatten_sections_to_events,
        format_chord_bar_line,
        format_key_label,
        invalidate_cpl_derived_outputs,
        parse_chord_line,
        save_progression,
        sections_to_chord_lists,
        diatonic_chords_for_key,
        sync_written_home_key,
        written_home_key,
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
        st.success("This progression is your **active source** across the app.")
    else:
        st.caption("Catalog song is still active — click **Use as active song** when ready.")

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

    home_key = written_home_key(active)
    key_label = format_key_label(display_key)
    cpl_widget_ns = display_key.replace("#", "s").replace("b", "f")

    home_sections = deep_copy_sections(active.get("original_sections") or {})
    display_sections = deep_copy_sections(display_sections_for_key(active, display_key))

    active["name"] = st.text_input(
        "Progression name",
        value=active.get("name", "My progression"),
        key="cpl_title",
    )

    st.markdown(
        """
<div class="cpl-flow-hint">
<strong>How to use this page</strong><br>
1. Set your key in the <strong>left sidebar</strong> (Practice / Display Key).<br>
2. Click suggested chords to add them.<br>
3. Edit your progression below.<br>
4. Generate backing and practice.
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(f"### Current key: **{key_label}**")
    st.info(
        "To change the key of the whole progression, use the **Practice / Display Key** "
        "selector on the **left** sidebar. Chord suggestions update automatically."
    )

    suggested = diatonic_chords_for_key(display_key)
    st.markdown(f"#### Suggested chords in {key_label}")
    st.caption("Click a chord to add it to your progression")
    if suggested:
        ncols = min(len(suggested), 4)
        sug_cols = st.columns(ncols)
        for i, ch in enumerate(suggested):
            with sug_cols[i % ncols]:
                if st.button(ch, key=f"cpl_sug_{cpl_widget_ns}_{ch}", use_container_width=True):
                    sec = st.session_state.get("cpl_edit_section", "Verse")
                    if sec not in home_sections:
                        home_sections[sec] = []
                    home_sections[sec].append({"chord": ch, "bars": 1})
                    active = commit_home_sections(active, home_sections)
                    st.session_state[CPL_ACTIVE_KEY] = active
                    st.rerun()
    else:
        st.caption("Set a key in the sidebar to see chord suggestions.")

    st.markdown("#### Your progression")
    prog_line = format_chord_bar_line(display_sections)
    st.markdown(f'<p class="cpl-progression-line">{prog_line}</p>', unsafe_allow_html=True)
    flat_chords = []
    for _n, chs in sections_to_chord_lists(display_sections).items():
        flat_chords.extend(chs)
    if flat_chords:
        st.markdown(chord_tiles_html(flat_chords), unsafe_allow_html=True)
    else:
        st.caption("No chords yet — click suggestions above to start.")

    st.markdown("#### Edit progression")
    st.caption("Add chords from suggestions above, then remove, reorder, or change duration here.")

    sec_names = list(home_sections.keys()) or ["Verse"]
    edit_section = st.selectbox(
        "Section to edit",
        sec_names,
        key=f"cpl_edit_section_{cpl_widget_ns}",
    )
    entries = home_sections.setdefault(edit_section, [])

    bulk = st.text_input(
        "Or paste chords (e.g. Dm7 | G7 | Cmaj7)",
        placeholder="Dm7 | G7 | Cmaj7",
        key="cpl_progression_editor",
    )
    if st.button("Add pasted chords", key="cpl_bulk_add", use_container_width=False):
        for item in parse_chord_line(bulk):
            entries.append(item)
        active = commit_home_sections(active, home_sections)
        st.session_state[CPL_ACTIVE_KEY] = active
        st.rerun()

    remove_indices = []
    if not entries:
        st.caption("This section is empty — click a suggested chord to add one.")
    for idx, entry in enumerate(list(entries)):
        st.markdown(f"**Chord {idx + 1}**")
        c1, c2, c3, c4 = st.columns([3, 1, 0.5, 0.5])
        with c1:
            entry["chord"] = st.text_input(
                "Chord name",
                value=entry.get("chord", display_key),
                key=f"cpl_ch_{cpl_widget_ns}_{edit_section}_{idx}",
                label_visibility="collapsed",
            )
        with c2:
            entry["bars"] = int(
                st.number_input(
                    "Bars",
                    min_value=1,
                    max_value=16,
                    value=int(entry.get("bars", 1)),
                    key=f"cpl_bars_{cpl_widget_ns}_{edit_section}_{idx}",
                    label_visibility="visible",
                )
            )
        with c3:
            if st.button("↑", key=f"cpl_up_{cpl_widget_ns}_{edit_section}_{idx}", help="Move up"):
                if idx > 0:
                    entries[idx], entries[idx - 1] = entries[idx - 1], entries[idx]
                    active = commit_home_sections(active, home_sections)
                    st.session_state[CPL_ACTIVE_KEY] = active
                    st.rerun()
        with c4:
            if st.button("✕", key=f"cpl_rm_{cpl_widget_ns}_{edit_section}_{idx}", help="Remove"):
                remove_indices.append(idx)
    for ri in sorted(remove_indices, reverse=True):
        entries.pop(ri)
    if remove_indices:
        active = commit_home_sections(active, home_sections)
        st.session_state[CPL_ACTIVE_KEY] = active
        st.rerun()

    active = commit_home_sections(active, home_sections)
    st.session_state[CPL_ACTIVE_KEY] = active
    display_sections = deep_copy_sections(display_sections_for_key(active, display_key))

    st.markdown(f"#### Presets in {key_label}")
    st.caption("Replace the current section with a common pattern in this key")
    preset_names = ["ii–V–I", "I–V–vi–IV", "Jazz turnaround", "Bossa cadence"]
    pcols = st.columns(2)
    for i, pname in enumerate(preset_names):
        with pcols[i % 2]:
            label = f"{pname} in {display_key}"
            if st.button(label, key=f"cpl_preset_{cpl_widget_ns}_{pname}", use_container_width=True):
                entries = build_preset_entries(pname, display_key)
                home_sections[edit_section] = entries
                active = commit_home_sections(active, home_sections)
                st.session_state[CPL_ACTIVE_KEY] = active
                st.rerun()

    with st.expander("Optional: groove style", expanded=False):
        cur_style = st.session_state.get("cpl_style_pick", "Custom")
        style_pick = st.selectbox("Style template", CPL_STYLE_CHOICES, index=CPL_STYLE_CHOICES.index(cur_style) if cur_style in CPL_STYLE_CHOICES else 0, key="cpl_style_select")
        if st.button("Apply style template", key="cpl_apply_style"):
            preset = apply_style_preset(style_pick, display_key)
            if preset:
                active["groove_style"] = preset["groove_style"]
                home_sections = deep_copy_sections(preset["sections"])
                active = commit_home_sections(active, home_sections)
                st.session_state[CPL_ACTIVE_KEY] = active
                st.session_state["cpl_style_pick"] = style_pick
                st.rerun()
            st.caption("Custom keeps your chords; other styles load a starter progression in the current key.")

    with st.expander("Advanced tools", expanded=False):
        if st.button("Harmonic analysis", key="cpl_analyze"):
            st.session_state["cpl_analysis_md"] = harmonic_analysis_markdown(
                display_sections, display_key, active.get("time_signature", "4/4")
            )
        if st.session_state.get("cpl_analysis_md"):
            st.markdown(st.session_state["cpl_analysis_md"])

    with st.expander("Saved progressions", expanded=False):
        save_name = st.text_input("Save as", value=active.get("name", "Untitled"), key="cpl_save_name")
        if st.button("Save", key="cpl_save_btn"):
            save_progression(saved, save_name.strip() or "Untitled", active)
            st.session_state[CPL_SAVED_KEY] = saved
            st.success(f"Saved **{save_name}**.")
        if saved:
            pick_saved = st.selectbox("Load", ["—"] + sorted(saved.keys()), key="cpl_pick_saved")
            if st.button("Load", key="cpl_load_btn", disabled=pick_saved == "—"):
                st.session_state[CPL_ACTIVE_KEY] = ensure_original_structure(dict(saved[pick_saved]))
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

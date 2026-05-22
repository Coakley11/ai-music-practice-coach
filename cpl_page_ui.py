"""Custom Progression page — simplified step-by-step UI."""

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
        ensure_original_structure,
        flatten_sections_to_events,
        format_chord_bar_line,
        invalidate_cpl_derived_outputs,
        on_cpl_apply_manual_home_key,
        on_cpl_anchor_home_key,
        parse_chord_line,
        save_progression,
        sections_to_chord_lists,
        suggest_next_chords,
        sync_written_home_key,
        written_home_key,
        harmonic_analysis_markdown,
        lab_context_for_coaching,
    )
    from music_theory import display_key_options
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
    from songs.music_source import set_custom_source
    from songs.state import note_active_source_change

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

    active = ensure_original_structure(st.session_state[CPL_ACTIVE_KEY])
    active = sync_written_home_key(active)
    st.session_state[CPL_ACTIVE_KEY] = active
    saved = st.session_state[CPL_SAVED_KEY]

    home_sections = deep_copy_sections(active.get("original_sections") or {})
    cpl_home_key = written_home_key(active)
    cpl_practice_key = session_display_key(st.session_state)
    cpl_widget_ns = cpl_home_key.replace("#", "s").replace("b", "f")
    display_sections = deep_copy_sections(display_sections_for_key(active, cpl_practice_key))
    flat_chords = []
    for _n, chs in sections_to_chord_lists(display_sections).items():
        flat_chords.extend(chs)

    active["name"] = st.text_input(
        "Progression name",
        value=active.get("name", "My progression"),
        key="cpl_title",
    )

    # --- Step 1: Style ---
    st.markdown(
        '<div class="cpl-step-card"><span class="cpl-step-num">1</span>'
        '<span class="cpl-step-title">Choose style</span></div>',
        unsafe_allow_html=True,
    )
    style_cols = st.columns(9)
    for i, style_name in enumerate(CPL_STYLE_CHOICES):
        with style_cols[i % 9]:
            if st.button(style_name, key=f"cpl_style_{style_name}", use_container_width=True):
                st.session_state["cpl_style_pick"] = style_name
                preset = apply_style_preset(style_name, cpl_home_key)
                if preset:
                    active["groove_style"] = preset["groove_style"]
                    home_sections = deep_copy_sections(preset["sections"])
                    active = commit_home_sections(active, home_sections)
                    st.session_state[CPL_ACTIVE_KEY] = active
                st.rerun()
    st.caption(f"Style: **{st.session_state.get('cpl_style_pick', 'Custom')}**")

    # --- Step 2: Key ---
    st.markdown(
        '<div class="cpl-step-card"><span class="cpl-step-num">2</span>'
        '<span class="cpl-step-title">Choose key</span></div>',
        unsafe_allow_html=True,
    )
    key_buttons = ["C", "F", "Bb", "Eb", "G", "D", "Am", "Em"]
    kcols = st.columns(len(key_buttons))
    for i, k in enumerate(key_buttons):
        with kcols[i]:
            if st.button(k, key=f"cpl_key_{k}", use_container_width=True):
                st.session_state["cpl_manual_home_key_picker"] = k
                on_cpl_apply_manual_home_key()
                st.rerun()
    st.caption(f"Written key **{cpl_home_key}** · Practice key **{cpl_practice_key}** (sidebar)")

    # --- Step 3: Build progression ---
    st.markdown(
        '<div class="cpl-step-card"><span class="cpl-step-num">3</span>'
        '<span class="cpl-step-title">Build progression</span></div>',
        unsafe_allow_html=True,
    )

    st.markdown("**Progression**")
    st.markdown(chord_tiles_html(flat_chords), unsafe_allow_html=True)

    st.caption("Quick presets")
    preset_cols = st.columns(3)
    preset_names = list(
        {
            "ii–V–I": None,
            "I–V–vi–IV": None,
            "Jazz turnaround": None,
            "Bossa cadence": None,
            "Blues (8 bars)": None,
            "Neo soul": None,
        }.keys()
    )
    for i, pname in enumerate(preset_names):
        with preset_cols[i % 3]:
            if st.button(pname, key=f"cpl_preset_{pname}", use_container_width=True):
                entries = build_preset_entries(pname, cpl_home_key)
                sec = st.session_state.get("cpl_edit_section", "Verse")
                if sec not in home_sections:
                    home_sections[sec] = []
                home_sections[sec] = entries
                active = commit_home_sections(active, home_sections)
                st.session_state[CPL_ACTIVE_KEY] = active
                st.rerun()

    sec_names = list(home_sections.keys()) or ["Verse"]
    edit_section = st.selectbox("Edit section", sec_names, key=f"cpl_edit_section_{cpl_widget_ns}")
    entries = home_sections.setdefault(edit_section, [])

    tool_a, tool_b, tool_c, tool_d = st.columns(4)
    with tool_a:
        if st.button("➕ Add chord", key="cpl_add_chord", use_container_width=True):
            entries.append({"chord": cpl_home_key, "bars": 1})
            active = commit_home_sections(active, home_sections)
            st.session_state[CPL_ACTIVE_KEY] = active
            st.rerun()
    with tool_b:
        bulk = st.text_input(
            "Paste chords",
            placeholder="Dm7 | G7 | Cmaj7",
            key="cpl_progression_editor",
            label_visibility="collapsed",
        )
    with tool_c:
        if st.button("Add from text", key="cpl_bulk_add", use_container_width=True):
            for item in parse_chord_line(bulk):
                entries.append(item)
            active = commit_home_sections(active, home_sections)
            st.session_state[CPL_ACTIVE_KEY] = active
            st.rerun()
    with tool_d:
        if st.button("🔁 Variation", key="cpl_variation", use_container_width=True):
            if entries:
                entries.append(dict(entries[-1]))
            active = commit_home_sections(active, home_sections)
            st.session_state[CPL_ACTIVE_KEY] = active
            st.rerun()

    suggestions = suggest_next_chords(home_sections, cpl_home_key, limit=4)
    st.markdown("**You may also like**")
    sug_cols = st.columns(len(suggestions))
    for i, sug in enumerate(suggestions):
        with sug_cols[i]:
            if st.button(sug, key=f"cpl_sug_{cpl_widget_ns}_{sug}", use_container_width=True):
                entries.append({"chord": sug, "bars": 1})
                active = commit_home_sections(active, home_sections)
                st.session_state[CPL_ACTIVE_KEY] = active
                st.rerun()

    remove_indices = []
    for idx, entry in enumerate(list(entries)):
        c1, c2, c3, c4 = st.columns([3, 1, 0.4, 0.4])
        with c1:
            entry["chord"] = st.text_input(
                f"Chord {idx + 1}",
                value=entry.get("chord", cpl_home_key),
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
                    label_visibility="collapsed",
                )
            )
        with c3:
            if st.button("↑", key=f"cpl_up_{cpl_widget_ns}_{edit_section}_{idx}", disabled=idx == 0):
                entries[idx], entries[idx - 1] = entries[idx - 1], entries[idx]
                active = commit_home_sections(active, home_sections)
                st.session_state[CPL_ACTIVE_KEY] = active
                st.rerun()
        with c4:
            if st.button("✕", key=f"cpl_rm_{cpl_widget_ns}_{edit_section}_{idx}"):
                remove_indices.append(idx)
    for ri in sorted(remove_indices, reverse=True):
        entries.pop(ri)
    if remove_indices:
        active = commit_home_sections(active, home_sections)
        st.session_state[CPL_ACTIVE_KEY] = active
        st.rerun()

    active = commit_home_sections(active, home_sections)
    st.session_state[CPL_ACTIVE_KEY] = active
    display_sections = deep_copy_sections(display_sections_for_key(active, cpl_practice_key))
    flat_chords = []
    for _n, chs in sections_to_chord_lists(display_sections).items():
        flat_chords.extend(chs)
    st.markdown(chord_tiles_html(flat_chords), unsafe_allow_html=True)

    with st.expander("Advanced: key & harmony tools", expanded=False):
        st.markdown(f"Home `{cpl_home_key}` → Practice `{cpl_practice_key}`")
        st.code(format_chord_bar_line(home_sections), language=None)
        st.code(format_chord_bar_line(display_sections), language=None)
        _home_opts = display_key_options(cpl_home_key)
        st.selectbox("Set home key", _home_opts, key="cpl_manual_home_key_picker")
        ac1, ac2 = st.columns(2)
        with ac1:
            st.button("Apply home key", key="cpl_apply_manual_home", on_click=on_cpl_apply_manual_home_key)
        with ac2:
            st.button("Anchor practice key as home", key="cpl_anchor_home", on_click=on_cpl_anchor_home_key)
        if st.button("Harmonic analysis", key="cpl_analyze"):
            st.session_state["cpl_analysis_md"] = harmonic_analysis_markdown(
                display_sections, cpl_practice_key, active.get("time_signature", "4/4")
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
                invalidate_cpl_derived_outputs(st.session_state)
                st.rerun()

    # --- Step 4: Playback ---
    st.markdown(
        '<div class="cpl-step-card"><span class="cpl-step-num">4</span>'
        '<span class="cpl-step-title">Practice & playback</span></div>',
        unsafe_allow_html=True,
    )
    active["time_signature"] = st.selectbox(
        "Time",
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
        cpl_practice_key,
        display_sections,
        active.get("bpm", 100),
        active.get("loops", 2),
        cpl_groove,
    )

    play_c1, play_c2, play_c3 = st.columns(3)
    with play_c1:
        gen = st.button(
            "▶ Generate backing",
            key="cpl_play_button",
            disabled=not cpl_events,
            use_container_width=True,
        )
    with play_c2:
        stop = st.button("⏹ Stop / clear", key="cpl_stop_backing", use_container_width=True)
    with play_c3:
        st.caption(f"🔁 {active.get('loops', 2)}× loop · {len(cpl_events)} bars")

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

    st.markdown("**Practice tools**")
    pt1, pt2, pt3 = st.columns(3)
    with pt1:
        if st.button("Send to Practice", key="cpl_to_practice", use_container_width=True):
            set_custom_source(st.session_state)
            st.session_state["studio_page"] = "practice"
            st.rerun()
    with pt2:
        if st.button("Open Backing Track", key="cpl_to_backing", use_container_width=True):
            st.session_state["studio_page"] = "backing"
            st.rerun()
    with pt3:
        st.caption("Notation on **Practice** page")

    _inst = session_instrument(st.session_state)
    _lvl = session_level(st.session_state)
    _foc = session_focus(st.session_state)
    coach_ctx = lab_context_for_coaching(display_sections, cpl_practice_key, _inst, _lvl, _foc)
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

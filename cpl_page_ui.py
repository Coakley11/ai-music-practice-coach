"""Custom Progression — build a full song section by section."""

from __future__ import annotations


def render_custom_progression_lab_page() -> None:
    import html

    import streamlit as st

    from custom_progression_lab import (
        CHORD_QUICK_EDIT_KEYS,
        CPL_ACTIVE_KEY,
        CPL_EDITABLE_SECTIONS,
        CPL_PRESET_NAMES,
        CPL_SAVED_KEY,
        apply_quick_chord_edit,
        apply_style_preset,
        backing_signature,
        build_preset_entries,
        chord_with_bass,
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
        save_progression,
        song_structure_overview_html,
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

    col_act, _ = st.columns([1, 2])
    with col_act:
        if st.button("Use as active song", key="cpl_set_active_source", type="primary"):
            set_custom_source(st.session_state)
            note_active_source_change(st, invalidate_backing=invalid_backing_cache)
            st.rerun()
    if is_custom_progression(st.session_state):
        st.caption("Active across Practice, Backing Track, and charts.")
    else:
        st.caption("Click **Use as active song** when ready.")

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
    ns = display_key.replace("#", "s").replace("b", "f")

    home_sections = ensure_all_cpl_sections(active.get("original_sections") or {})
    active["original_sections"] = home_sections

    if st.session_state.get("cpl_edit_section") not in CPL_EDITABLE_SECTIONS:
        st.session_state["cpl_edit_section"] = "Verse"

    active["name"] = st.text_input("Song name", value=active.get("name", "My song"), key="cpl_title")

    st.markdown(
        """
<div class="cpl-flow-hint">
You are writing a <strong>whole song</strong> — one section at a time (Verse, Chorus, Bridge…).
<br><strong>①</strong> Key in left sidebar ·
<strong>②</strong> Pick section ·
<strong>③</strong> Add chords ·
<strong>④</strong> See full song below ·
<strong>⑤</strong> Play
</div>
""",
        unsafe_allow_html=True,
    )

    view_mode = st.radio(
        "Mode",
        ["Build a section", "View full song"],
        horizontal=True,
        key="cpl_view_mode",
        label_visibility="collapsed",
    )
    st.caption(
        "Change key for the **whole song** using **Practice / Display Key** on the **left** panel."
    )

    edit_section = st.session_state.get("cpl_edit_section", "Verse")
    if view_mode == "View full song":
        st.markdown("### Your full song")
        st.markdown(
            song_structure_overview_html(active, display_key, highlight_section=edit_section),
            unsafe_allow_html=True,
        )
        st.caption("Switch to **Build a section** to add or edit chords in Intro, Verse, Chorus, etc.")
    else:
        edit_section = st.selectbox(
            "Which section are you writing?",
            CPL_EDITABLE_SECTIONS,
            key="cpl_edit_section",
        )
        st.markdown(
            f'<div class="cpl-panel cpl-panel-muted">'
            f"<strong>Current key:</strong> {html.escape(key_label)} &nbsp;·&nbsp; "
            f"<strong>Current section:</strong> {html.escape(edit_section)}"
            f"</div>",
            unsafe_allow_html=True,
        )

        section_entries = display_entries_for_section(active, display_key, edit_section)
        home_entries = home_sections.setdefault(edit_section, [])
        suggested = diatonic_chords_for_key(display_key)

        def _save() -> None:
            nonlocal active, home_sections
            active = commit_home_sections(active, home_sections)
            st.session_state[CPL_ACTIVE_KEY] = active

        st.markdown('<div class="cpl-panel">', unsafe_allow_html=True)
        st.markdown(f"##### Suggested chords in {key_label} *(optional helpers)*")
        st.caption("Click to add to **" + edit_section + "** — or type any chord below.")
        if suggested:
            cols = st.columns(min(4, len(suggested)))
            for i, ch in enumerate(suggested):
                with cols[i % len(cols)]:
                    if st.button(ch, key=f"cpl_sug_{ns}_{edit_section}_{ch}", use_container_width=True):
                        home_entries.append({"chord": ch, "bars": 1})
                        _save()
                        st.rerun()

        st.markdown(f"##### Presets in {key_label}")
        pcols = st.columns(min(5, len(CPL_PRESET_NAMES)))
        for i, pname in enumerate(CPL_PRESET_NAMES):
            with pcols[i % len(pcols)]:
                if st.button(pname, key=f"cpl_pre_{ns}_{edit_section}_{pname}", use_container_width=True):
                    home_sections[edit_section] = build_preset_entries(pname, display_key)
                    _save()
                    st.rerun()

        st.markdown("##### Custom chord")
        cc1, cc2 = st.columns([3, 1])
        with cc1:
            custom_ch = st.text_input(
                "Type any chord",
                placeholder="F#m9, Bb13, Gsus4, Cmaj9, Eb7#11, G/B …",
                key="cpl_custom_chord",
                label_visibility="collapsed",
            )
        with cc2:
            if st.button("Add", key="cpl_custom_add", use_container_width=True):
                ch = normalize_chord_symbol(custom_ch)
                if ch:
                    home_entries.append({"chord": ch, "bars": 1})
                    _save()
                    st.rerun()
                else:
                    st.warning("Type a chord first.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(f"##### Your **{edit_section}** progression")
        bar_line = format_entries_bar_line(section_entries)
        st.markdown(f'<p class="cpl-progression-line">{html.escape(bar_line)}</p>', unsafe_allow_html=True)

        st.markdown('<div class="cpl-panel">', unsafe_allow_html=True)
        st.markdown("##### Edit chords in this section")
        if not home_entries:
            st.info("**(empty)** — click a suggestion, preset, or type a custom chord above.")
        else:
            st.caption("Change the chord, length, or use quick edits. Each row is one slot in your progression.")

        remove_at: list[int] = []
        for idx, entry in enumerate(list(home_entries)):
            disp = (
                section_entries[idx]["chord"]
                if idx < len(section_entries)
                else entry.get("chord", "")
            )
            st.markdown('<div class="cpl-edit-slot">', unsafe_allow_html=True)
            row1 = st.columns([2, 1, 1, 1, 1])
            with row1[0]:
                new_ch = st.text_input(
                    "Chord",
                    value=str(disp),
                    key=f"cpl_chord_txt_{ns}_{edit_section}_{idx}",
                    label_visibility="collapsed",
                )
                entry["chord"] = normalize_chord_symbol(new_ch) or entry.get("chord", "")
            with row1[1]:
                entry["bars"] = int(
                    st.number_input(
                        "Bars",
                        1,
                        16,
                        int(entry.get("bars", 1)),
                        key=f"cpl_bars_{ns}_{edit_section}_{idx}",
                    )
                )
            with row1[2]:
                if st.button("Copy", key=f"cpl_dup_{ns}_{edit_section}_{idx}", help="Duplicate"):
                    home_entries.insert(idx + 1, dict(entry))
                    home_sections[edit_section] = home_entries
                    _save()
                    st.rerun()
            with row1[3]:
                if st.button("Remove", key=f"cpl_rm_{ns}_{edit_section}_{idx}"):
                    remove_at.append(idx)
            with row1[4]:
                if st.button("↑", key=f"cpl_up_{ns}_{edit_section}_{idx}", disabled=idx == 0):
                    home_entries[idx], home_entries[idx - 1] = home_entries[idx - 1], home_entries[idx]
                    home_sections[edit_section] = home_entries
                    _save()
                    st.rerun()

            st.caption("Quick change:")
            qcols = st.columns(len(CHORD_QUICK_EDIT_KEYS) + 2)
            for qi, ek in enumerate(CHORD_QUICK_EDIT_KEYS):
                with qcols[qi]:
                    if st.button(f"+{ek}", key=f"cpl_q_{ns}_{edit_section}_{idx}_{ek}"):
                        entry["chord"] = apply_quick_chord_edit(entry.get("chord", disp), ek)
                        home_sections[edit_section] = home_entries
                        _save()
                        st.rerun()
            with qcols[len(CHORD_QUICK_EDIT_KEYS)]:
                bass_note = st.text_input(
                    "Bass",
                    placeholder="/G",
                    key=f"cpl_bass_{ns}_{edit_section}_{idx}",
                    label_visibility="collapsed",
                )
            with qcols[len(CHORD_QUICK_EDIT_KEYS) + 1]:
                if st.button("Slash", key=f"cpl_slash_{ns}_{edit_section}_{idx}"):
                    b = bass_note.strip().lstrip("/")
                    if b:
                        entry["chord"] = chord_with_bass(entry.get("chord", disp), b)
                        home_sections[edit_section] = home_entries
                        _save()
                        st.rerun()
            if idx < len(home_entries) - 1:
                if st.button("Move down ↓", key=f"cpl_dn_{ns}_{edit_section}_{idx}"):
                    home_entries[idx], home_entries[idx + 1] = home_entries[idx + 1], home_entries[idx]
                    home_sections[edit_section] = home_entries
                    _save()
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        for ri in sorted(remove_at, reverse=True):
            home_entries.pop(ri)
        if remove_at:
            home_sections[edit_section] = home_entries
            _save()
            st.rerun()

        p1, p2 = st.columns(2)
        with p1:
            bulk = st.text_input("Paste several chords", placeholder="Dm7 | G7 | Cmaj7", key="cpl_paste")
            if st.button("Add pasted chords", key="cpl_paste_btn"):
                for item in parse_chord_line(bulk):
                    home_entries.append(item)
                home_sections[edit_section] = home_entries
                _save()
                st.rerun()
        with p2:
            if st.button(f"Clear all {edit_section} chords", key=f"cpl_clear_{edit_section}"):
                home_sections[edit_section] = []
                _save()
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### Song structure")
    st.caption("Each part of your song — tap **View full song** above for a focused overview.")
    st.markdown(
        song_structure_overview_html(active, display_key, highlight_section=edit_section),
        unsafe_allow_html=True,
    )

    active = commit_home_sections(active, home_sections)
    st.session_state[CPL_ACTIVE_KEY] = active
    display_sections = deep_copy_sections(display_sections_for_key(active, display_key))

    with st.expander("Save / load / reset", expanded=False):
        if st.button("Start fresh (empty song)", key="cpl_reset_all"):
            fresh = default_active_progression()
            fresh["name"] = active.get("name", "My song")
            fresh["original_key_center"] = display_key
            st.session_state[CPL_ACTIVE_KEY] = fresh
            st.session_state.pop("_cpl_editing_display_key", None)
            invalidate_cpl_derived_outputs(st.session_state)
            st.rerun()
        save_name = st.text_input("Save as", value=active.get("name", "Untitled"), key="cpl_save_name")
        if st.button("Save song", key="cpl_save_btn"):
            save_progression(saved, save_name.strip() or "Untitled", active)
            st.session_state[CPL_SAVED_KEY] = saved
            st.success(f"Saved **{save_name}**.")
        if saved:
            pick = st.selectbox("Load saved", ["—"] + sorted(saved.keys()), key="cpl_pick_saved")
            if st.button("Load", key="cpl_load_btn", disabled=pick == "—"):
                st.session_state[CPL_ACTIVE_KEY] = ensure_original_structure(dict(saved[pick]))
                st.session_state.pop("_cpl_editing_display_key", None)
                invalidate_cpl_derived_outputs(st.session_state)
                st.rerun()

    st.markdown("---")
    st.markdown("### Play your song")
    active["time_signature"] = st.selectbox("Time", ["4/4", "3/4", "6/8"], key="cpl_time_sig")
    b1, b2, b3 = st.columns(3)
    with b1:
        active["bpm"] = st.slider("BPM", 50, 200, int(active.get("bpm", 100)), 5, key="cpl_bpm")
    with b2:
        active["loops"] = st.slider("Loops", 1, 12, int(active.get("loops", 2)), key="cpl_loops")
    with b3:
        grooves = ["Auto", "Pop groove", "Rock groove", "Jazz swing", "Bossa nova", "Funk groove", "Ballad"]
        g = active.get("groove_style", "Auto")
        active["groove_style"] = st.selectbox("Groove", grooves, index=grooves.index(g) if g in grooves else 0, key="cpl_groove")

    st.session_state[CPL_ACTIVE_KEY] = active
    events = flatten_sections_to_events(display_sections)
    groove = infer_groove_style({}, active.get("groove_style", "Auto"))

    g1, g2 = st.columns(2)
    with g1:
        if st.button("Generate backing", key="cpl_play_button", disabled=not events, type="primary", use_container_width=True):
            st.session_state["cpl_backing_wav"] = generate_backing_track(
                events,
                bpm=int(active.get("bpm", 100)),
                loops=int(active.get("loops", 2)),
                style=groove,
                level=session_level(st.session_state),
                song_title=active.get("name", "Custom"),
                song_artist="",
            )
            st.session_state["cpl_backing_signature"] = backing_signature(
                display_key, display_sections, active.get("bpm", 100), active.get("loops", 2), groove
            )
            st.rerun()
    with g2:
        if st.button("Clear backing", key="cpl_stop_backing", use_container_width=True):
            st.session_state.pop("cpl_backing_wav", None)
            st.rerun()
    if st.session_state.get("cpl_backing_wav"):
        st.audio(st.session_state["cpl_backing_wav"], format="audio/wav")

    t1, t2 = st.columns(2)
    with t1:
        if st.button("Open Practice page", key="cpl_to_practice", use_container_width=True):
            set_custom_source(st.session_state)
            st.session_state["studio_page"] = "practice"
            st.rerun()
    with t2:
        if st.button("Open Backing Track", key="cpl_to_backing", use_container_width=True):
            st.session_state["studio_page"] = "backing"
            st.rerun()

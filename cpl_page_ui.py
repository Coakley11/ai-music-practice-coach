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


def assemble_custom_chord(root: str, quality: str = "", bass: str = "") -> str:
    """Exact symbol for root + quality (+ slash bass); the quality is never dropped."""
    root = str(root or "").strip()
    quality = str(quality or "").strip()
    bass = str(bass or "").strip()
    symbol = f"{root}{quality}"
    return f"{symbol}/{bass}" if bass else symbol


def _tap_pick(
    label: str,
    options: list[str],
    *,
    key: str,
    default: str | None = None,
    format_func=None,
) -> str:
    """One-of-N chooser that is safe on touch screens.

    A ``selectbox`` virtualizes long lists and keeps typed filter text that is
    never committed when the field loses focus, so the previous value silently
    stays selected. Pills commit on tap and always hold exactly one value.
    """
    import streamlit as st

    opts = [str(o) for o in options]
    fallback = str(default) if default is not None and str(default) in opts else (opts[0] if opts else "")
    last_key = f"{key}__last"

    if key in st.session_state and st.session_state.get(key) not in opts + [None]:
        st.session_state.pop(key, None)

    def _keep_one() -> None:
        cur = st.session_state.get(key)
        if cur is None:
            st.session_state[key] = st.session_state.get(last_key) or fallback
        else:
            st.session_state[last_key] = cur

    picked = st.pills(
        label,
        opts,
        selection_mode="single",
        default=fallback,
        key=key,
        format_func=format_func or str,
        label_visibility="collapsed",
        on_change=_keep_one,
    )
    value = str(picked) if picked is not None else str(st.session_state.get(last_key) or fallback)
    st.session_state[last_key] = value
    return value


def _quality_pill_label(q: str) -> str:
    return "major" if q == "" else q


def _pending_chord_key(section: str) -> str:
    return f"cpl_pending_chord_{section}"


def _last_bars_key(section: str) -> str:
    return f"cpl_last_bars_{section}"


def _render_split_chord_selector(
    *,
    label: str,
    default_chord: str,
    practice_key: str,
    key_prefix: str,
    suggestions: list[tuple[str, str]] | None = None,
) -> str:
    """Shared chord selector: suggested dropdown, chord builder, or text entry.

    *suggestions* is an optional list of (chord, reason) tuples that replaces
    the generic key-based dropdown in "Suggested" mode. The first entry is
    auto-selected as the default.

    Returns the selected chord symbol (in Practice Key).
    """
    import html as _html

    import streamlit as st

    from custom_progression_lab import (
        chromatic_roots_for_key,
        diatonic_roots_for_key,
        editable_chord_options_for_key,
        extract_chord_root_and_suffix,
    )
    from responsive_layout import iter_ui_rows

    chord_opts = editable_chord_options_for_key(practice_key)
    if default_chord and default_chord not in chord_opts:
        chord_opts = [default_chord] + chord_opts
    default_idx = chord_opts.index(default_chord) if default_chord in chord_opts else 0

    _method_key = f"{key_prefix}_method"
    method = st.session_state.get(_method_key, "Suggested")

    tab_cols = st.columns(3)
    for i, tab_label in enumerate(["Suggested", "Builder", "Type"]):
        with tab_cols[i]:
            btn_type = "primary" if method == tab_label else "secondary"
            if st.button(
                tab_label,
                key=f"{key_prefix}_tab_{tab_label}",
                type=btn_type,
                use_container_width=True,
            ):
                st.session_state[_method_key] = tab_label
                st.rerun()

    result_key = f"{key_prefix}_result"
    st.session_state.setdefault(result_key, default_chord or chord_opts[0])

    if method == "Builder":
        _diatonic = diatonic_roots_for_key(practice_key)
        _all_chromatic = chromatic_roots_for_key(practice_key)
        _extra_roots = [r for r in _all_chromatic if r not in _diatonic]

        _bld_root_key = f"{key_prefix}_bld_root"
        _bld_qual_key = f"{key_prefix}_bld_qual"
        _bld_ext_key = f"{key_prefix}_bld_ext"
        _bld_slash_key = f"{key_prefix}_bld_slash"

        existing_root, _ = extract_chord_root_and_suffix(default_chord or "")
        st.session_state.setdefault(_bld_root_key, existing_root or (_diatonic[0] if _diatonic else "C"))

        st.caption("Root:")
        for chunk in iter_ui_rows(_diatonic, 7):
            rcols = st.columns(len(chunk) or 1)
            for col, note in zip(rcols, chunk):
                with col:
                    is_active = st.session_state.get(_bld_root_key) == note
                    if st.button(
                        note,
                        key=f"{key_prefix}_root_{note}",
                        type="primary" if is_active else "secondary",
                    ):
                        st.session_state[_bld_root_key] = note
                        st.rerun()
        if _extra_roots:
            st.caption("Chromatic:")
            for chunk in iter_ui_rows(_extra_roots, 5):
                rcols = st.columns(len(chunk) or 1)
                for col, note in zip(rcols, chunk):
                    with col:
                        is_active = st.session_state.get(_bld_root_key) == note
                        if st.button(
                            note,
                            key=f"{key_prefix}_root_{note}",
                            type="primary" if is_active else "secondary",
                        ):
                            st.session_state[_bld_root_key] = note
                            st.rerun()

        bld_root = st.session_state.get(_bld_root_key, "C")

        _quality_opts = [
            ("", "Major"), ("m", "Minor"),
            ("dim", "Dim"), ("aug", "Aug"),
            ("sus2", "Sus2"), ("sus4", "Sus4"),
        ]
        cur_qual = st.session_state.get(_bld_qual_key, "")
        qcols = st.columns(len(_quality_opts))
        for i, (qval, qlabel) in enumerate(_quality_opts):
            with qcols[i]:
                if st.button(
                    qlabel,
                    key=f"{key_prefix}_qual_{qlabel}",
                    type="primary" if cur_qual == qval else "secondary",
                ):
                    st.session_state[_bld_qual_key] = qval
                    st.rerun()

        _ext_groups = [
            ("7ths", ["7", "maj7", "6"]),
            ("Ext", ["9", "11", "13", "6/9", "add9"]),
            ("Alt", ["7b9", "7#9", "7#11", "7b13"]),
        ]
        cur_ext = st.session_state.get(_bld_ext_key, "")
        for grp_label, grp_keys in _ext_groups:
            ecols = st.columns(len(grp_keys) + 1)
            with ecols[0]:
                st.caption(grp_label)
            for j, ek in enumerate(grp_keys):
                with ecols[j + 1]:
                    if st.button(
                        ek,
                        key=f"{key_prefix}_ext_{ek}",
                        type="primary" if cur_ext == ek else "secondary",
                    ):
                        st.session_state[_bld_ext_key] = "" if cur_ext == ek else ek
                        st.rerun()

        slash_bass = st.text_input(
            "Slash bass (optional, e.g. Bb)",
            value=st.session_state.get(_bld_slash_key, ""),
            key=f"{key_prefix}_slash_input",
        )
        st.session_state[_bld_slash_key] = slash_bass.strip()

        _incompat = {
            ("dim", "7"): "dim7", ("dim", "maj7"): "dim7",
            ("aug", "7"): "aug7",
        }
        combo = (cur_qual, cur_ext)
        if combo in _incompat:
            assembled = f"{bld_root}{_incompat[combo]}"
        elif cur_qual in ("dim", "aug", "sus2", "sus4") and cur_ext:
            assembled = f"{bld_root}{cur_qual}{cur_ext}"
        elif cur_qual == "m" and cur_ext:
            assembled = f"{bld_root}m{cur_ext}"
        elif cur_qual and not cur_ext:
            assembled = f"{bld_root}{cur_qual}"
        elif cur_ext and not cur_qual:
            assembled = f"{bld_root}{cur_ext}"
        else:
            assembled = bld_root

        if slash_bass.strip():
            assembled = f"{assembled}/{slash_bass.strip()}"

        st.session_state[result_key] = assembled
        st.markdown(f"**{label}:** {_html.escape(assembled)}")

    elif method == "Type":
        typed = st.text_input(
            label,
            value=st.session_state.get(result_key, default_chord),
            key=f"{key_prefix}_typed",
        )
        typed = typed.strip()
        if typed:
            root, _ = extract_chord_root_and_suffix(typed.split("/", 1)[0])
            if root:
                st.session_state[result_key] = typed
            else:
                st.warning(f"'{typed}' doesn't look like a valid chord (must start with A-G).")
        else:
            st.session_state[result_key] = default_chord or chord_opts[0]

    else:
        if suggestions:
            sug_chords = [ch for ch, _ in suggestions]
            sug_reasons = {ch: reason for ch, reason in suggestions}
            for ch in sug_chords:
                if ch not in chord_opts:
                    chord_opts.append(ch)
            combined = sug_chords + [c for c in chord_opts if c not in sug_chords]
            sug_default = combined[0] if combined else (default_chord or "C")

            def _fmt_option(ch: str) -> str:
                r = sug_reasons.get(ch)
                return f"{ch}  --  {r}" if r else ch

            chosen = st.selectbox(
                label,
                combined,
                index=0,
                format_func=_fmt_option,
                key=f"{key_prefix}_suggested",
            )
            st.session_state[result_key] = chosen
            if chosen in sug_reasons:
                st.caption(f"_{sug_reasons[chosen]}_")
        else:
            chosen = st.selectbox(
                label,
                chord_opts,
                index=default_idx,
                key=f"{key_prefix}_suggested",
            )
            st.session_state[result_key] = chosen

    return str(st.session_state.get(result_key, default_chord or "C"))


def _render_split_measure_panel(
    home_entries: list[dict],
    *,
    edit_section: str,
    practice_key: str,
    original_key: str,
    save,
    time_signature: str = "4/4",
    style: str = "Pop",
) -> None:
    """Explicit measure-based split editor: select measure, pattern, chords, preview, apply."""
    import streamlit as st

    from chord_subdivisions import Subdivision, join_weighted_subdivisions, parse_subdivisions
    from custom_progression_lab import (
        cpl_split_measure_at_index,
        editable_chord_options_for_key,
        semitone_distance,
        suggest_split_second_chords,
        transpose_chord,
        cpl_active_from_session,
        ensure_all_cpl_sections,
        cpl_save_draft,
    )
    from roman_numeral_analysis import chord_to_roman as _c2r_split

    if not home_entries:
        return

    import portfolio_polish as pp

    with st.expander(
        "Split measure — put two chords in one bar",
        expanded=pp.expander_default(st),
    ):
        st.caption(
            "Select a measure, choose a beat pattern, pick the chords, "
            "then click **Apply Split**."
        )

        _pk_to_ok = semitone_distance(practice_key, original_key)
        section_tag = str(edit_section or "section").replace(" ", "_")

        measure_labels: list[str] = []
        for i, entry in enumerate(home_entries):
            ch = str(entry.get("chord") or "").strip()
            head = ch.split("|", 1)[0].split(":", 1)[0]
            bars = int(entry.get("bars", 1) or 1)
            is_split = "|" in ch
            tag = f"(split)" if is_split else ""
            if bars > 1:
                tag = f"({bars} bars)"
            measure_labels.append(f"#{i+1}: {head} {tag}".strip())

        _split_sel_key = f"cpl_splitmeasure_sel_{section_tag}"
        selected_idx = st.selectbox(
            "Which measure to split",
            list(range(len(home_entries))),
            format_func=lambda i: measure_labels[i] if i < len(measure_labels) else str(i + 1),
            key=_split_sel_key,
        )

        entry = home_entries[selected_idx]
        existing_chord = str(entry.get("chord") or "").strip()
        is_already_split = "|" in existing_chord
        cur_bars = int(entry.get("bars", 1) or 1)

        if cur_bars > 1:
            st.info(
                f"This chord spans {cur_bars} bars. Use **Expand** in the edit panel above "
                "to break it into individual measures first, then split one."
            )
            return

        head = existing_chord.split("|", 1)[0].split(":", 1)[0] or "C"
        if _pk_to_ok:
            display_head = transpose_chord(head, -_pk_to_ok, reference_key=practice_key)
        else:
            display_head = head

        if is_already_split:
            subs = parse_subdivisions(existing_chord, beats_per_bar=4)
            sub_parts = []
            for s in subs:
                sc = transpose_chord(s.chord, -_pk_to_ok, reference_key=practice_key) if _pk_to_ok else s.chord
                sub_parts.append(f"{sc} ({s.weight} beats)")
            st.caption(f"Currently split: {' + '.join(sub_parts)}")
            st.caption("Choosing a new pattern below will replace the existing split.")

        _pat_key = f"cpl_splitpat_{section_tag}"
        pattern = st.selectbox(
            "Beat pattern",
            ["2+2", "3+1", "1+3", "Push", "1+1+1+1"],
            key=_pat_key,
            help="How to divide the 4 beats in this measure.",
        )

        _next_ok = ""
        _prev_ok = ""
        if selected_idx + 1 < len(home_entries):
            _next_ok = str(home_entries[selected_idx + 1].get("chord") or "").split("|", 1)[0].split(":", 1)[0]
        if selected_idx > 0:
            _prev_ok = str(home_entries[selected_idx - 1].get("chord") or "").split("|", 1)[0].split(":", 1)[0]
        _sug_ok = suggest_split_second_chords(
            current_chord=head,
            next_chord=_next_ok,
            prev_chord=_prev_ok,
            home_key=original_key,
            style=style,
        )
        _sug_pk: list[tuple[str, str]] = []
        for _sc, _sr in _sug_ok:
            _sc_pk = transpose_chord(_sc, -_pk_to_ok, reference_key=practice_key) if _pk_to_ok else _sc
            _sr_pk = _sr
            if _next_ok and _pk_to_ok:
                _next_pk = transpose_chord(_next_ok, -_pk_to_ok, reference_key=practice_key)
                _sr_pk = _sr.replace(
                    _next_ok.split("|", 1)[0].split(":", 1)[0],
                    _next_pk,
                )
            _sug_pk.append((_sc_pk, _sr_pk))

        if pattern == "1+1+1+1":
            st.caption("Four equal beats — each gets its own chord.")
            for beat_num in range(1, 5):
                default = display_head if beat_num in (1, 3) else ""
                st.markdown(f"---\n**Beat {beat_num}:**")
                _render_split_chord_selector(
                    label=f"Beat {beat_num} chord",
                    default_chord=default or display_head,
                    practice_key=practice_key,
                    key_prefix=f"cpl_split4_c{beat_num}_{section_tag}",
                    suggestions=_sug_pk if beat_num in (2, 4) else None,
                )
            chords_4 = [
                st.session_state.get(f"cpl_split4_c{b}_{section_tag}_result", display_head)
                for b in range(1, 5)
            ]
            def _fmt4(c):
                _r = _c2r_split(c, practice_key) if practice_key else ""
                return f"{c} ({_r}) - 1 beat" if _r else f"{c} - 1 beat"
            preview = " | ".join(_fmt4(c) for c in chords_4)
            st.markdown(f"**Preview:** [{preview}]")
            if st.button("✂️ Apply Split", key=f"cpl_split4_apply_{section_tag}", type="primary"):
                ok_chords = [
                    transpose_chord(c, _pk_to_ok, reference_key=original_key) if _pk_to_ok else c
                    for c in chords_4
                ]
                token = join_weighted_subdivisions([
                    Subdivision(ok_chords[i], 1.0, False) for i in range(4)
                ])
                home_entries[selected_idx] = {"chord": token, "bars": 1}
                save()
                st.rerun()
        else:
            if pattern == "2+2":
                beats_a, beats_b = 2, 2
            elif pattern == "3+1":
                beats_a, beats_b = 3, 1
            elif pattern == "1+3":
                beats_a, beats_b = 1, 3
            else:
                beats_a, beats_b = 3.5, 0.5

            is_push = pattern == "Push"
            beat_a_label = f"{beats_a} beat{'s' if beats_a != 1 else ''}"
            beat_b_label = f"{beats_b} beat{'s' if beats_b != 1 else ''}"
            if is_push:
                beat_b_label = "push (anticipated)"

            st.markdown(f"---\n**First chord ({beat_a_label}):**")
            _render_split_chord_selector(
                label=f"First chord ({beat_a_label})",
                default_chord=display_head,
                practice_key=practice_key,
                key_prefix=f"cpl_split_first_{section_tag}",
            )
            st.markdown(f"---\n**Second chord ({beat_b_label}):**")
            _render_split_chord_selector(
                label=f"Second chord ({beat_b_label})",
                default_chord="",
                practice_key=practice_key,
                key_prefix=f"cpl_split_second_{section_tag}",
                suggestions=_sug_pk,
            )

            _first = st.session_state.get(f"cpl_split_first_{section_tag}_result", display_head)
            _second = st.session_state.get(f"cpl_split_second_{section_tag}_result", display_head)

            _r1 = _c2r_split(_first, practice_key) if practice_key else ""
            _r2 = _c2r_split(_second, practice_key) if practice_key else ""
            _rlbl1 = f" ({_r1})" if _r1 else ""
            _rlbl2 = f" ({_r2})" if _r2 else ""
            preview = f"[{_first}{_rlbl1} - {beat_a_label}] [{_second}{_rlbl2} - {beat_b_label}]"
            st.markdown(f"**Preview:** {preview}")

            if st.button("✂️ Apply Split", key=f"cpl_split_apply_{section_tag}", type="primary"):
                first_ok = transpose_chord(_first, _pk_to_ok, reference_key=original_key) if _pk_to_ok else _first
                second_ok = transpose_chord(_second, _pk_to_ok, reference_key=original_key) if _pk_to_ok else _second
                token = join_weighted_subdivisions([
                    Subdivision(first_ok, float(beats_a), False),
                    Subdivision(second_ok, float(beats_b), is_push),
                ])
                home_entries[selected_idx] = {"chord": token, "bars": 1}
                save()
                st.rerun()


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
        diatonic_roots_for_key,
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

    def _open_song_aware_coaching() -> None:
        """Creative in Song-Aware Coaching mode for the active Custom song."""
        _save(None)
        _snapshot_custom_workspace()
        from studio_nav_history import navigate_studio_page
        from studio_page_state import request_song_aware_coaching

        request_song_aware_coaching(st.session_state)
        navigate_studio_page(st.session_state, "creative")
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
                            "💾 Save to library",
                            key="cpl_save_prog_launch",
                            type="primary",
                            use_container_width=True,
                            on_click=cpl_on_save_library_callback,
                        )
                    elif kind == "active":
                        if st.button(
                            "☑️ Set as Active Song",
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

        from music_feature_icons import SEMANTIC_FIELD_ICONS

        row2 = st.columns([1, 1, 1])
        with row2[0]:
            st.radio(
                f"{SEMANTIC_FIELD_ICONS.get('meter', '')} Meter",
                CPL_TIME_SIGNATURES,
                horizontal=True,
                key="cpl_time_signature",
            )
        with row2[1]:
            st.slider(f"{SEMANTIC_FIELD_ICONS.get('bpm', '')} BPM", 50, 200, step=5, key="cpl_bpm_builder")
        with row2[2]:
            st.selectbox(
                f"{SEMANTIC_FIELD_ICONS.get('style', '')} Genre / style",
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
                "💾 Save to library",
                key="cpl_save_prog",
                use_container_width=True,
                on_click=cpl_on_save_library_callback,
            )
        with n2:
            st.button(
                "➕ New song",
                key="cpl_start_new",
                use_container_width=True,
                on_click=cpl_on_new_song_callback,
            )
        with n3:
            if st.button(
                "☑️ Set as Active Song",
                key="cpl_set_active",
                type="primary",
                use_container_width=True,
            ):
                _activate_custom_song()
        _save_flash = st.session_state.pop("_cpl_save_library_flash", False)
        _cloud_status = st.session_state.pop("_cpl_cloud_save_status", None) or {}
        if _save_flash:
            if isinstance(_save_flash, str) and str(_save_flash).startswith("error:"):
                st.error(str(_save_flash))
            else:
                # Green only when the cloud really holds the song. Anything else is said
                # plainly: a copy on this server alone does not survive a restart.
                from custom_song_library import describe_save_status

                _level, _text = describe_save_status(
                    str(_cloud_status.get("state") or ""), str(_cloud_status.get("error") or "")
                )
                {"success": st.success, "error": st.error, "warning": st.warning}.get(_level, st.info)(_text)
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
                if st.button("📂 Load selected", key="cpl_load_btn", use_container_width=True):
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
        # Song-Aware Coaching only once this draft is the active song (Set as Active Song).
        try:
            from songs.music_source import custom_song_ready_for_coaching

            _coaching_ready = custom_song_ready_for_coaching(st.session_state)
        except ImportError:
            _coaching_ready = False
        if _coaching_ready and st.button(
            feature_label("song_aware_coaching", "Song-Aware Coaching"),
            key="cpl_song_aware_coaching",
            use_container_width=True,
        ):
            _open_song_aware_coaching()

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
            map_html = song_structure_overview_html(
                active, practice_key, only_filled=True, show_roman=False
            )
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
                    "☑️ Set as Active Song",
                    key="cpl_set_active_finish",
                    type="primary",
                    use_container_width=True,
                ):
                    _activate_custom_song()
            with launch[1]:
                if st.button("✏️ Keep Editing", key="cpl_unfinish", use_container_width=True):
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
        from roman_numeral_analysis import chord_to_roman as _c2r

        with st.container(key="cpl_chord_pick_grid"):
            for chunk in iter_ui_rows(simple, 6):
                cols = st.columns(len(chunk) or 1)
                for col, ch in zip(cols, chunk):
                    with col:
                        _roman = _c2r(ch, preview_key) if preview_key else ""
                        st.button(
                            ch,
                            key=f"cpl_pick_{edit_section}_{ch}",
                            on_click=cpl_on_pick_chord_callback,
                            args=(ch,),
                            use_container_width=True,
                        )
                        if _roman:
                            st.markdown(
                                f'<div class="cpl-pick-roman" aria-label="Roman numeral {html.escape(_roman)}">'
                                f"{html.escape(_roman)}</div>",
                                unsafe_allow_html=True,
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

            st.markdown("**Root note**")
            _custom_root = _tap_pick(
                "Root note", _chromatic_notes, key=_sc_root_key, default=_chromatic_notes[0] if _chromatic_notes else "C"
            )
            st.markdown("**Quality**")
            _qual_tokens = [_quality_pill_label(q) for q, _ in _custom_qualities]
            _qual_token = _tap_pick(
                "Quality",
                _qual_tokens,
                key=_sc_qual_key,
                default="major",
                format_func=lambda t: "minor" if t == "m" else t,
            )
            _custom_qual = "" if _qual_token == "major" else _qual_token
            _use_bass = st.checkbox("Slash bass", key=f"cpl_use_bass_{home_ns}_{edit_section}")
            _slash_bass = ""
            if _use_bass:
                st.markdown("**Bass note**")
                _slash_bass = _tap_pick(
                    "Bass note", _bass_options, key=_sc_bass_key, default=_bass_options[0] if _bass_options else "C"
                )
            _built_chord = assemble_custom_chord(_custom_root, _custom_qual, _slash_bass if _use_bass else "")

            _built_roman = _c2r(_built_chord, preview_key) if preview_key else ""
            _built_roman_html = (
                f' <span class="cpl-roman-label">{html.escape(_built_roman)}</span>'
                if _built_roman
                else ""
            )
            st.markdown(
                f'<div style="padding:0.5rem 0;font-size:1.4rem;font-weight:900;'
                f'color:#1e3a8a;letter-spacing:-0.02em;">'
                f'{html.escape(_built_chord)}{_built_roman_html}</div>',
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

        _render_split_measure_panel(
            home_entries,
            edit_section=edit_section,
            practice_key=practice_key,
            original_key=original_key,
            save=lambda: _save(home_sections),
            time_signature=time_sig,
            style=style,
        )

        with st.expander("Chord builder — root + quality + extension", expanded=False):
            st.caption(
                "1. Select a root note.  2. Choose a quality.  "
                "3. Optionally add an extension.  4. Add the chord."
            )
            from responsive_layout import iter_ui_rows

            _diatonic = diatonic_roots_for_key(practice_key)
            _all_chromatic = chromatic_roots_for_key(practice_key)
            _extra_roots = [r for r in _all_chromatic if r not in _diatonic]

            _ext_root_key = "cpl_ext_root_note"
            _root_default = _diatonic[0] if _diatonic else "C"
            st.session_state.setdefault(_ext_root_key, _root_default)
            # A root left over from another key must not stay "selected" while invisible.
            if st.session_state.get(_ext_root_key) not in set(_diatonic) | set(_extra_roots):
                st.session_state[_ext_root_key] = _root_default
            _cur_root = st.session_state[_ext_root_key]

            st.markdown("**Root note:**")
            with st.container(key="cpl_ext_root_grid"):
                for chunk in iter_ui_rows(_diatonic, 7):
                    rcols = st.columns(len(chunk) or 1)
                    for col, note in zip(rcols, chunk):
                        with col:
                            if st.button(
                                note,
                                key=f"cpl_extroot_{home_ns}_{edit_section}_{note}",
                                type="primary" if note == _cur_root else "secondary",
                            ):
                                st.session_state[_ext_root_key] = note
                                st.rerun()
            if _extra_roots:
                with st.container(key="cpl_ext_chromatic_grid"):
                    st.caption("Chromatic:")
                    for chunk in iter_ui_rows(_extra_roots, 5):
                        rcols = st.columns(len(chunk) or 1)
                        for col, note in zip(rcols, chunk):
                            with col:
                                if st.button(
                                    note,
                                    key=f"cpl_extroot_{home_ns}_{edit_section}_{note}",
                                    type="primary" if note == _cur_root else "secondary",
                                ):
                                    st.session_state[_ext_root_key] = note
                                    st.rerun()

            ext_root_note = st.session_state.get(_ext_root_key, _diatonic[0] if _diatonic else "C")

            _quality_options = [
                ("", "Major"), ("m", "Minor"),
                ("dim", "Diminished"), ("aug", "Augmented"),
                ("sus2", "Sus2"), ("sus4", "Sus4"),
            ]
            _ext_quality_key = "cpl_ext_quality"
            cur_quality = st.session_state.get(_ext_quality_key, "")

            st.markdown("**Quality:**")
            qcols = st.columns(len(_quality_options))
            for i, (qval, qlabel) in enumerate(_quality_options):
                with qcols[i]:
                    is_active = cur_quality == qval
                    btn_type = "primary" if is_active else "secondary"
                    if st.button(qlabel, key=f"cpl_extqual_{home_ns}_{edit_section}_{qlabel}", type=btn_type):
                        st.session_state[_ext_quality_key] = qval
                        st.session_state.pop("cpl_ext_extension", None)
                        st.rerun()

            _extension_groups = [
                ("7ths", ["7", "maj7", "6"]),
                ("Extended", ["9", "11", "13", "6/9", "add9"]),
                ("Altered", ["7b9", "7#9", "7#11", "7b13"]),
            ]
            _ext_extension_key = "cpl_ext_extension"
            cur_extension = st.session_state.get(_ext_extension_key, "")

            st.markdown("**Extension** (optional):")
            for group_label, group_keys in _extension_groups:
                ext_cols = st.columns(len(group_keys) + 1)
                with ext_cols[0]:
                    st.caption(group_label)
                for i, ek in enumerate(group_keys):
                    with ext_cols[i + 1]:
                        is_active = cur_extension == ek
                        btn_type = "primary" if is_active else "secondary"
                        if st.button(ek, key=f"cpl_extext_{home_ns}_{edit_section}_{ek}", type=btn_type):
                            if cur_extension == ek:
                                st.session_state.pop(_ext_extension_key, None)
                            else:
                                st.session_state[_ext_extension_key] = ek
                            st.rerun()

            _incompatible_combos = {
                ("dim", "7"): "dim7", ("dim", "maj7"): "dim7",
                ("aug", "7"): "aug7",
            }
            combo_key = (cur_quality, cur_extension)
            if combo_key in _incompatible_combos:
                assembled = f"{ext_root_note}{_incompatible_combos[combo_key]}"
            elif cur_quality in ("dim", "aug", "sus2", "sus4") and cur_extension:
                assembled = f"{ext_root_note}{cur_quality}{cur_extension}"
            elif cur_quality == "m" and cur_extension:
                assembled = f"{ext_root_note}m{cur_extension}"
            elif cur_quality and not cur_extension:
                assembled = f"{ext_root_note}{cur_quality}"
            elif cur_extension and not cur_quality:
                assembled = f"{ext_root_note}{cur_extension}"
            else:
                assembled = ext_root_note

            _asm_roman = _c2r(assembled, preview_key) if preview_key else ""
            _asm_roman_html = (
                f' <span class="cpl-roman-label">{html.escape(_asm_roman)}</span>'
                if _asm_roman
                else ""
            )
            st.markdown(
                f'<div style="padding:0.5rem 0;font-size:1.6rem;font-weight:900;'
                f'color:#1e3a8a;letter-spacing:-0.02em;">'
                f'Selected chord: {html.escape(assembled)}{_asm_roman_html}</div>',
                unsafe_allow_html=True,
            )

            ab1, ab2 = st.columns(2)
            with ab1:
                if st.button(
                    f"Add {assembled}",
                    key=f"cpl_ext_add_{home_ns}_{edit_section}",
                    type="primary",
                    use_container_width=True,
                ):
                    cpl_set_pending_chord(st.session_state, section=edit_section, chord=assembled)
                    st.rerun()
            with ab2:
                if st.button(
                    "Clear selection",
                    key=f"cpl_ext_clear_{home_ns}_{edit_section}",
                    use_container_width=True,
                ):
                    st.session_state.pop(_ext_quality_key, None)
                    st.session_state.pop(_ext_extension_key, None)
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
            with st.expander("✏️ Edit existing chords", expanded=False):
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
                        _edt_root_key = f"cpl_edt_root_{home_ns}_{edit_section}_{idx}"
                        _edt_qual_key = f"cpl_edt_qual_{home_ns}_{edit_section}_{idx}"
                        st.markdown("**Root**")
                        new_root = _tap_pick(
                            "Root",
                            _chromatic,
                            key=_edt_root_key,
                            default=root_pk if root_pk in _chromatic else (_chromatic[0] if _chromatic else "C"),
                        )
                        st.markdown("**Quality**")
                        _edt_tokens = [_quality_pill_label(q) for q in CHORD_EDIT_QUALITIES]
                        _cur_suffix = suffix if suffix in CHORD_EDIT_QUALITIES else ""
                        _edt_token = _tap_pick(
                            "Quality",
                            _edt_tokens,
                            key=_edt_qual_key,
                            default=_quality_pill_label(_cur_suffix),
                            format_func=lambda t: "minor" if t == "m" else t,
                        )
                        new_suffix = "" if _edt_token == "major" else _edt_token
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
                            if st.button("🗑️ Remove", key=f"cpl_edt_rm_{home_ns}_{edit_section}_{idx}"):
                                cpl_remove_chord_at_index(
                                    st.session_state,
                                    section_name=edit_section,
                                    index=idx,
                                    st_module=st,
                                )
                                st.session_state.pop(_edit_idx_key, None)
                                st.rerun()
                        with d3:
                            if st.button("❌ Cancel", key=f"cpl_edt_cancel_{home_ns}_{edit_section}_{idx}"):
                                st.session_state.pop(_edit_idx_key, None)
                                st.rerun()

                    elif splitting_idx == idx:
                        # --- SPLIT MODE ---
                        st.markdown(f"**Split measure {idx + 1}:** {display_chord}")

                        ok_chord = str(entry.get("chord") or "").split("|", 1)[0].split(":", 1)[0]
                        _inl_next_ok = ""
                        _inl_prev_ok = ""
                        entries_list = list(home_entries)
                        if idx + 1 < len(entries_list):
                            _inl_next_ok = str(entries_list[idx + 1].get("chord") or "").split("|", 1)[0].split(":", 1)[0]
                        if idx > 0:
                            _inl_prev_ok = str(entries_list[idx - 1].get("chord") or "").split("|", 1)[0].split(":", 1)[0]
                        from custom_progression_lab import suggest_split_second_chords
                        _inl_sug_ok = suggest_split_second_chords(
                            current_chord=ok_chord,
                            next_chord=_inl_next_ok,
                            prev_chord=_inl_prev_ok,
                            home_key=original_key,
                            style=style,
                        )
                        _inl_sug_pk: list[tuple[str, str]] = []
                        for _isc, _isr in _inl_sug_ok:
                            _isc_pk = transpose_chord(_isc, -_pk_to_ok_steps, reference_key=practice_key) if _pk_to_ok_steps else _isc
                            _isr_pk = _isr
                            if _inl_next_ok and _pk_to_ok_steps:
                                _inl_next_pk = transpose_chord(_inl_next_ok, -_pk_to_ok_steps, reference_key=practice_key)
                                _isr_pk = _isr.replace(
                                    _inl_next_ok.split("|", 1)[0].split(":", 1)[0],
                                    _inl_next_pk,
                                )
                            _inl_sug_pk.append((_isc_pk, _isr_pk))

                        _split_pattern = st.selectbox(
                            "Pattern",
                            ["2+2", "3+1", "1+3", "Push"],
                            key=f"cpl_split_pat_{home_ns}_{edit_section}_{idx}",
                        )
                        if _split_pattern == "2+2":
                            _ba, _bb = 2, 2
                        elif _split_pattern == "3+1":
                            _ba, _bb = 3, 1
                        elif _split_pattern == "1+3":
                            _ba, _bb = 1, 3
                        else:
                            _ba, _bb = 3.5, 0.5
                        _lbl_a = f"{_ba} beat{'s' if _ba != 1 else ''}"
                        _lbl_b = f"{_bb} beat{'s' if _bb != 1 else ''}"
                        if _split_pattern == "Push":
                            _lbl_b = "push"

                        st.markdown(f"**First chord ({_lbl_a}):**")
                        _render_split_chord_selector(
                            label=f"First chord ({_lbl_a})",
                            default_chord=display_chord,
                            practice_key=practice_key,
                            key_prefix=f"cpl_isplit_first_{home_ns}_{edit_section}_{idx}",
                        )
                        st.markdown(f"**Second chord ({_lbl_b}):**")
                        _render_split_chord_selector(
                            label=f"Second chord ({_lbl_b})",
                            default_chord="",
                            practice_key=practice_key,
                            key_prefix=f"cpl_isplit_second_{home_ns}_{edit_section}_{idx}",
                            suggestions=_inl_sug_pk,
                        )

                        _inline_first = st.session_state.get(
                            f"cpl_isplit_first_{home_ns}_{edit_section}_{idx}_result", display_chord,
                        )
                        _inline_second = st.session_state.get(
                            f"cpl_isplit_second_{home_ns}_{edit_section}_{idx}_result", display_chord,
                        )
                        st.markdown(f"**Preview:** [{_inline_first} - {_lbl_a}] [{_inline_second} - {_lbl_b}]")

                        sb1, sb2 = st.columns(2)
                        with sb1:
                            if st.button("✂️ Apply split", key=f"cpl_split_apply_{home_ns}_{edit_section}_{idx}", type="primary"):
                                first_ok = transpose_chord(
                                    _inline_first, _pk_to_ok_steps, reference_key=original_key,
                                ) if _pk_to_ok_steps else _inline_first
                                second_ok = transpose_chord(
                                    _inline_second, _pk_to_ok_steps, reference_key=original_key,
                                ) if _pk_to_ok_steps else _inline_second
                                cpl_split_measure_at_index(
                                    st.session_state,
                                    section_name=edit_section,
                                    index=idx,
                                    pattern=_split_pattern.lower(),
                                    first_chord=first_ok,
                                    second_chord=second_ok,
                                    st_module=st,
                                )
                                st.session_state.pop(_split_idx_key, None)
                                st.rerun()
                        with sb2:
                            if st.button("❌ Cancel", key=f"cpl_split_cancel_{home_ns}_{edit_section}_{idx}"):
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
                            if st.button("✏️ Edit", key=f"cpl_edit_btn_{home_ns}_{edit_section}_{idx}"):
                                for _stale in (
                                    f"cpl_edt_root_{home_ns}_{edit_section}_{idx}",
                                    f"cpl_edt_qual_{home_ns}_{edit_section}_{idx}",
                                ):
                                    st.session_state.pop(_stale, None)
                                    st.session_state.pop(f"{_stale}__last", None)
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
                                if st.button("✂️ Split", key=f"cpl_split_btn_{home_ns}_{edit_section}_{idx}", help="Split this measure into beat subdivisions"):
                                    st.session_state[_split_idx_key] = idx
                                    st.session_state.pop(_edit_idx_key, None)
                                    st.rerun()
                            else:
                                st.write("")
                        with c5:
                            if st.button("🗑️ Remove", key=f"cpl_rm_{home_ns}_{edit_section}_{idx}"):
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
                    if st.button("📋 Copy range", key=f"cpl_copy_range_{home_ns}_{edit_section}", disabled=_range_start > _range_end):
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
                        if st.button("📌 Paste here", key=f"cpl_paste_range_{home_ns}_{edit_section}", type="primary"):
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
                "↩️ Undo last chord",
                key=f"cpl_undo_{edit_section}",
                use_container_width=True,
                disabled=not home_entries,
                on_click=cpl_on_undo_last_chord_callback,
            )
        with u2:
            st.button(
                "🧹 Clear section",
                key=f"cpl_clear_{edit_section}",
                use_container_width=True,
                disabled=not section_has_chords and not pending_chord,
                on_click=cpl_on_clear_section_callback,
            )
        with u3:
            if st.button(
                "🏁 Finish Song",
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
                "📋 Copy section",
                key=f"cpl_copy_{edit_section}",
                use_container_width=True,
                disabled=not section_has_chords,
            ):
                cpl_copy_section(st.session_state, section_name=edit_section)
                st.rerun()
        with cp2:
            if st.button(
                "📌 Paste",
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
            # A summary of the song so far, not a composing aid: chord names only.
            show_roman=False,
        )
        if map_html:
            st.markdown("**Song structure**")
            st.markdown(map_html, unsafe_allow_html=True)

        _render_launch_in_studio(has_chords=has_chords, include_workspace_nav=True)

        with st.expander("More options", expanded=False):
            if saved_names := list_saved_progression_names(saved):
                del_pick = st.selectbox("Delete saved", ["—"] + saved_names, key="cpl_del_pick")
                if st.button("🗑️ Delete saved progression", disabled=del_pick == "—"):
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

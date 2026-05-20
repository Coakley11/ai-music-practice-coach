"""In-app chart editor UI (user overrides persisted to data/user_chart_overrides.json)."""

from __future__ import annotations

import copy
from typing import Any, Callable

import streamlit as st

from song_catalog.user_overrides import (
    USER_CORRECTED,
    USER_VERIFIED,
    catalog_snapshot_from_record,
    delete_user_override,
    export_overrides_json,
    get_user_override,
    import_overrides_json,
    normalize_sections,
    parse_pipe_chord_line,
    save_user_override,
)


def _draft_key(title: str, artist: str, level: str) -> str:
    return f"chart_edit_draft::{title}::{artist}::{level}"


def _catalog_record_for_song(
    all_records: list[dict[str, Any]],
    title: str,
    artist: str,
) -> dict[str, Any] | None:
    for row in all_records:
        if row.get("title") == title and row.get("artist") == artist:
            return row
    return None


def _catalog_record_without_override(
    all_records: list[dict[str, Any]],
    title: str,
    artist: str,
) -> dict[str, Any] | None:
    row = _catalog_record_for_song(all_records, title, artist)
    if not row:
        return None
    snap = (row.get("user_override") or {}).get("catalog_snapshot")
    if snap:
        base = copy.deepcopy(row)
        base["sections"] = copy.deepcopy(snap.get("sections") or {})
        base["chart_versions"] = copy.deepcopy(snap.get("chart_versions") or {})
        base["key"] = snap.get("key", base.get("key"))
        base["chart_status"] = snap.get("chart_status", "practice_simplified")
        base.pop("user_override", None)
        return base
    if row.get("user_override"):
        base = copy.deepcopy(row)
        base.pop("user_override", None)
        return base
    return copy.deepcopy(row)


def collect_draft_from_widgets(
    st: Any,
    *,
    title: str,
    artist: str,
    draft: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Read latest chord cell values from session state before save."""
    collected: dict[str, list[str]] = {}
    for sec_name, template in draft.items():
        quick_key = f"chart_edit_quick::{title}::{artist}::{sec_name}"
        quick_val = st.session_state.get(quick_key)
        if quick_val and "|" in str(quick_val):
            parsed = parse_pipe_chord_line(str(quick_val))
            if parsed:
                collected[sec_name] = parsed
                continue
        chords: list[str] = []
        for idx in range(len(template)):
            key = f"chart_edit_cell::{title}::{artist}::{sec_name}::{idx}"
            raw = st.session_state.get(key, template[idx])
            token = normalize_sections({sec_name: [str(raw)]}).get(sec_name, [])
            if token:
                chords.append(token[0])
        if chords:
            collected[sec_name] = chords
    return collected


def init_draft(
    st: Any,
    *,
    title: str,
    artist: str,
    level: str,
    sections: dict[str, list[str]],
    section_order: list[str] | None,
) -> dict[str, list[str]]:
    key = _draft_key(title, artist, level)
    if key not in st.session_state:
        ordered = list(section_order or sections.keys())
        st.session_state[key] = {
            name: list(sections[name])
            for name in ordered
            if name in sections
        }
        for name, chords in sections.items():
            if name not in st.session_state[key]:
                st.session_state[key][name] = list(chords)
    return st.session_state[key]


def _reload_catalog_libraries():
    """Re-read catalog + user overrides (imported only when saving/reverting)."""
    from song_catalog.catalog import load_song_catalog

    try:
        from song_catalog.catalog import clear_catalog_cache

        clear_catalog_cache()
    except (ImportError, AttributeError):
        pass
    return load_song_catalog()


def refresh_app_catalog_globals(module_globals: dict[str, Any]) -> None:
    library, picker, genres, records = _reload_catalog_libraries()
    module_globals["SONG_LIBRARY"] = library
    module_globals["SONG_PICKER_CATALOG"] = picker
    module_globals["GENRES"] = genres
    module_globals["ALL_SONG_RECORDS"] = records
    module_globals["TRUSTED_CORE_RECORDS"] = [
        r for r in records
        if r.get("trusted_core")
        or r.get("chart_status") in {"verified", "practice_level_verified", USER_VERIFIED}
    ]
    module_globals["DEFAULT_SONG_RECORDS"] = (
        module_globals["TRUSTED_CORE_RECORDS"] or records
    )


def render_chart_editor_panel(
    st: Any,
    *,
    module_globals: dict[str, Any],
    all_records: list[dict[str, Any]],
    song_data: dict[str, Any],
    genre: str,
    level: str,
    sections_for_level: Callable[[dict, str], dict],
    invalidate_backing: Callable[[Any], None],
) -> None:
    title = song_data.get("title", "")
    artist = song_data.get("artist", "")
    user_ov = song_data.get("user_override")
    catalog_row = _catalog_record_without_override(all_records, title, artist)

    st.markdown("### ✏️ Edit Song Chart")
    edit_on = st.toggle(
        "Edit Song Chart mode",
        value=bool(st.session_state.get("chart_edit_mode")),
        key="chart_edit_mode_toggle",
        help="Edit chords bar-by-bar in written (home) key. Save to override the catalog everywhere.",
    )
    st.session_state["chart_edit_mode"] = edit_on

    if user_ov:
        cat_status = user_ov.get("catalog_chart_status", "catalog")
        st.info(
            f"**Chart source:** User {'verified' if user_ov.get('status') == USER_VERIFIED else 'corrected'} "
            f"(saved {user_ov.get('saved_at', '?')}) · **Catalog was:** {cat_status}"
        )
    else:
        st.caption(
            f"**Chart source:** Catalog ({song_data.get('chart_status', 'unknown')}). "
            f"Edits are saved to `data/user_chart_overrides.json`."
        )

    if not edit_on:
        return

    home_sections = sections_for_level(song_data, level)
    if not home_sections and catalog_row:
        home_sections = sections_for_level(catalog_row, level)

    draft = init_draft(
        st,
        title=title,
        artist=artist,
        level=level,
        sections=home_sections,
        section_order=song_data.get("section_order"),
    )

    st.caption(
        f"Editing **{level}** chart in written key **{song_data.get('key', 'C')}**. "
        "One box = one bar (3/4 or 4/4 as in the song). Press Save when done."
    )

    section_names = list(draft.keys())
    with st.expander("Section order", expanded=False):
        order_text = st.text_area(
            "Section names (top to bottom = playback order)",
            value="\n".join(section_names),
            height=120,
            key=f"chart_edit_order::{title}::{artist}",
        )
        if st.button("Apply section order", key=f"chart_edit_apply_order::{title}"):
            new_order = [ln.strip() for ln in order_text.splitlines() if ln.strip()]
            reordered: dict[str, list[str]] = {}
            for name in new_order:
                if name in draft:
                    reordered[name] = draft[name]
            for name, chords in draft.items():
                if name not in reordered:
                    reordered[name] = chords
            st.session_state[_draft_key(title, artist, level)] = reordered
            st.rerun()

    cols_top = st.columns([1, 1, 1, 2])
    with cols_top[0]:
        new_section = st.text_input("New section name", key=f"chart_edit_new_sec::{title}")
    with cols_top[1]:
        if st.button("Add section", key=f"chart_edit_add_sec::{title}") and new_section.strip():
            draft[new_section.strip()] = ["C"]
            st.rerun()
    with cols_top[2]:
        del_section = st.selectbox(
            "Remove section",
            ["—"] + section_names,
            key=f"chart_edit_del_sec_pick::{title}",
        )
        if st.button("Delete section", key=f"chart_edit_del_sec::{title}"):
            if del_section != "—" and del_section in draft:
                del draft[del_section]
                st.rerun()

    for sec_name in list(draft.keys()):
        chords = draft[sec_name]
        st.markdown(f"**{sec_name}** · {len(chords)} bars")
        quick = st.text_input(
            f"Quick edit (paste: C | G/B | Am7 | F)",
            value=" | ".join(chords),
            key=f"chart_edit_quick::{title}::{artist}::{sec_name}",
            label_visibility="collapsed",
            placeholder=f"{sec_name}: C | G/B | Am7 | F",
        )
        if quick and parse_pipe_chord_line(quick) != chords:
            if st.button(f"Apply pasted chords to {sec_name}", key=f"chart_edit_quick_apply::{sec_name}"):
                draft[sec_name] = parse_pipe_chord_line(quick)
                st.rerun()

        per_row = 4
        for row_start in range(0, max(len(chords), per_row), per_row):
            row = chords[row_start : row_start + per_row]
            cols = st.columns(per_row)
            for col_i in range(per_row):
                idx = row_start + col_i
                with cols[col_i]:
                    if idx < len(chords):
                        val = st.text_input(
                            f"bar {idx + 1}",
                            value=chords[idx],
                            key=f"chart_edit_cell::{title}::{artist}::{sec_name}::{idx}",
                            label_visibility="visible",
                        )
                        if val.strip() and val.strip() != chords[idx]:
                            draft[sec_name][idx] = val.strip()
                    else:
                        st.caption("")

        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button(f"+ bar @ end ({sec_name})", key=f"chart_edit_add_bar::{sec_name}"):
                draft[sec_name].append(draft[sec_name][-1] if draft[sec_name] else "C")
                st.rerun()
        with b2:
            if st.button(f"− last bar ({sec_name})", key=f"chart_edit_rm_bar::{sec_name}"):
                if draft[sec_name]:
                    draft[sec_name].pop()
                    st.rerun()
        with b3:
            dup = st.text_input(
                "Repeat last N bars",
                value="1",
                key=f"chart_edit_dup::{sec_name}",
                help="Append copies of the last bar(s).",
            )
            if st.button(f"Duplicate ({sec_name})", key=f"chart_edit_dup_go::{sec_name}"):
                try:
                    n = max(1, int(dup))
                except ValueError:
                    n = 1
                tail = draft[sec_name][-n:] if draft[sec_name] else ["C"]
                draft[sec_name].extend(tail)
                st.rerun()

    st.divider()
    apply_all = st.checkbox(
        "Apply saved chords to Beginner, Intermediate, and Advanced",
        value=True,
        key=f"chart_edit_all_levels::{title}",
        help="When off, only the current sidebar level is stored in your override.",
    )

    save_a, save_b, save_c, save_d = st.columns(4)
    with save_a:
        save_corrected = st.button("Save corrected chart", type="primary", use_container_width=True)
    with save_b:
        save_verified = st.button("Save as user verified", use_container_width=True)
    with save_c:
        revert = st.button("Revert to catalog", use_container_width=True)
    with save_d:
        reload_draft = st.button("Reset draft", use_container_width=True)

    if reload_draft:
        st.session_state.pop(_draft_key(title, artist, level), None)
        st.rerun()

    if revert:
        if delete_user_override(title, artist):
            refresh_app_catalog_globals(module_globals)
            invalidate_backing(st)
            st.session_state.pop(_draft_key(title, artist, level), None)
            st.success("Reverted to catalog chart.")
            st.rerun()
        else:
            st.warning("No saved override for this song.")

    if save_corrected or save_verified:
        status = USER_VERIFIED if save_verified else USER_CORRECTED
        draft = collect_draft_from_widgets(
            st,
            title=title,
            artist=artist,
            draft=draft,
        )
        st.session_state[_draft_key(title, artist, level)] = draft
        cleaned = normalize_sections(draft)
        if not cleaned:
            st.error("Chart is empty — add at least one section with chords.")
            return

        chart_versions: dict[str, dict[str, list[str]]] = {}
        base_versions = copy.deepcopy((catalog_row or song_data).get("chart_versions") or {})
        if apply_all:
            for lv in ("Beginner", "Intermediate", "Advanced"):
                chart_versions[lv] = copy.deepcopy(cleaned)
        else:
            chart_versions = copy.deepcopy(base_versions)
            chart_versions[level] = copy.deepcopy(cleaned)

        existing = get_user_override(title, artist)
        if existing and existing.get("catalog_snapshot"):
            snapshot = existing["catalog_snapshot"]
        else:
            snapshot = catalog_snapshot_from_record(catalog_row or song_data)

        save_user_override(
            title=title,
            artist=artist,
            genre=genre,
            key=song_data.get("key", "C"),
            sections=cleaned,
            chart_versions=chart_versions,
            section_order=list(cleaned.keys()),
            override_status=status,
            edited_level=level,
            catalog_snapshot=snapshot,
        )
        refresh_app_catalog_globals(module_globals)
        invalidate_backing(st)
        st.session_state.pop(_draft_key(title, artist, level), None)
        st.success(
            "Saved — your chart is now used in Practice, Backing Track, Creative Lab, "
            "Chord Finder, follow-along, transpose, and exercises."
        )
        st.rerun()

    with st.expander("Backup / restore overrides", expanded=False):
        st.download_button(
            "Download all overrides (JSON)",
            export_overrides_json(),
            file_name="user_chart_overrides.json",
            mime="application/json",
        )
        uploaded = st.file_uploader("Import overrides JSON", type=["json"], key="chart_override_import")
        if uploaded is not None:
            if st.button("Merge imported overrides"):
                try:
                    count = import_overrides_json(uploaded.getvalue().decode("utf-8"), merge=True)
                    refresh_app_catalog_globals(module_globals)
                    invalidate_backing(st)
                    st.success(f"Imported {count} override(s).")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Import failed: {exc}")

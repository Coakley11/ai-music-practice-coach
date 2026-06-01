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
    """Read latest chord values from per-bar widgets before save.

    Quick-edit lines are initialized with ``|`` separators; preferring them on
    save would ignore bar-box edits. Use bar widgets (and the in-memory draft).
    """
    collected: dict[str, list[str]] = {}
    for sec_name, bars in draft.items():
        chords: list[str] = []
        for idx in range(len(bars)):
            key = f"chart_edit_cell::{title}::{artist}::{sec_name}::{idx}"
            raw = st.session_state.get(key, bars[idx])
            token = normalize_sections({sec_name: [str(raw)]}).get(sec_name, [])
            if token:
                chords.append(token[0])
            elif bars[idx]:
                chords.append(str(bars[idx]).strip())
        if chords:
            collected[sec_name] = chords
    return collected


CHART_SAVE_NOTICE_KEY = "chart_last_save_notice"
CHART_OVERRIDE_DEBUG_KEY = "chart_override_debug"
USER_CHART_OVERRIDES_REVISION_KEY = "_user_chart_overrides_revision"


def chart_override_bar_preview(
    entry: dict[str, Any] | None,
    *,
    section: str = "Verse",
    bar_index: int = 0,
    level: str | None = None,
) -> str:
    """One-line summary for save/load debug (e.g. ``Verse bar 1 = Gmaj7``)."""
    if not entry:
        return f"{section} bar {bar_index + 1} = (none)"
    sections: dict[str, list[str]] = {}
    versions = entry.get("chart_versions") or {}
    use_level = level or entry.get("edited_level")
    if use_level and versions.get(use_level):
        sections = versions[use_level]
    if not sections:
        sections = entry.get("sections") or {}
    bars = list(sections.get(section) or [])
    if bar_index < len(bars):
        chord = str(bars[bar_index]).strip()
    elif bars:
        chord = str(bars[0]).strip()
        section = next(iter(sections.keys()), section)
        bar_index = 0
    else:
        first_sec = next(iter(sections.keys()), None)
        if first_sec:
            section = first_sec
            bars = list(sections.get(first_sec) or [])
            chord = str(bars[0]).strip() if bars else "(empty)"
            bar_index = 0
        else:
            chord = "(empty)"
    return f"{section} bar {bar_index + 1} = {chord}"


def invalidate_chart_session_caches(st: Any) -> None:
    """Drop cached chart bundles/HTML so overrides appear immediately."""
    try:
        st.session_state[USER_CHART_OVERRIDES_REVISION_KEY] = (
            int(st.session_state.get(USER_CHART_OVERRIDES_REVISION_KEY) or 0) + 1
        )
    except Exception:
        pass
    try:
        from studio_cache import invalidate_session_cache

        invalidate_session_cache(st.session_state, "chart_bundle")
        invalidate_session_cache(st.session_state, "backing_chart_html")
    except Exception:
        pass


def chart_save_preview_lines(
    saved: dict[str, list[str]],
    *,
    before: dict[str, list[str]] | None = None,
    section_order: list[str] | None = None,
    max_edits: int = 8,
    max_fallback_sections: int = 4,
) -> list[str]:
    """Lines for post-save confirmation (edited bars first, else first bar per section)."""
    ordered = list(section_order or saved.keys())
    for name in saved.keys():
        if name not in ordered:
            ordered.append(name)

    edits: list[str] = []
    for sec in ordered:
        saved_bars = list(saved.get(sec) or [])
        before_bars = list((before or {}).get(sec) or [])
        max_len = max(len(saved_bars), len(before_bars))
        for idx in range(max_len):
            new_chord = saved_bars[idx] if idx < len(saved_bars) else None
            old_chord = before_bars[idx] if idx < len(before_bars) else None
            if new_chord is None:
                continue
            new_chord = str(new_chord).strip()
            old_chord = str(old_chord).strip() if old_chord is not None else None
            if new_chord != old_chord:
                edits.append(f"{sec} bar {idx + 1}: {new_chord}")
                if len(edits) >= max_edits:
                    return edits

    if edits:
        return edits

    fallback: list[str] = []
    for sec in ordered:
        bars = saved.get(sec) or []
        if bars:
            fallback.append(f"{sec} bar 1: {bars[0]}")
        if len(fallback) >= max_fallback_sections:
            break
    return fallback


def chart_active_source_label(song_data: dict[str, Any]) -> tuple[str, str]:
    """Return (banner text, kind) where kind is ``override`` or ``catalog``."""
    user_ov = song_data.get("user_override") or {}
    if not user_ov:
        return ("Using Catalog Chart", "catalog")
    if user_ov.get("status") == USER_VERIFIED:
        return ("Using User Override Chart (user verified)", "override")
    return ("Using User Override Chart", "override")


def _render_chart_source_banner(st: Any, song_data: dict[str, Any]) -> None:
    label, kind = chart_active_source_label(song_data)
    user_ov = song_data.get("user_override") or {}
    if kind == "override":
        saved_at = user_ov.get("saved_at", "?")
        st.success(f"✅ {label} · saved {saved_at}")
    else:
        st.info(label)


def _pop_chart_save_notice(
    st: Any,
    *,
    title: str,
    artist: str,
) -> dict[str, Any] | None:
    notice = st.session_state.get(CHART_SAVE_NOTICE_KEY)
    if not notice:
        return None
    if notice.get("title") != title or notice.get("artist") != artist:
        return None
    st.session_state.pop(CHART_SAVE_NOTICE_KEY, None)
    return notice


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
    try:
        st_obj = module_globals.get("st")
        if st_obj is not None and hasattr(st_obj, "session_state"):
            invalidate_chart_session_caches(st_obj)
            st_obj.session_state["_catalog_backup_records"] = records
            st_obj.session_state["_catalog_backup_library"] = library
            st_obj.session_state["_catalog_backup_picker"] = picker
            st_obj.session_state["_catalog_backup_genres"] = list(genres)
    except Exception:
        pass


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

    st.markdown("### Edit Song Chart")
    save_notice = _pop_chart_save_notice(st, title=title, artist=artist)
    if save_notice:
        st.success(str(save_notice.get("message") or "✅ Chart saved successfully"))
        detail = str(save_notice.get("detail") or "").strip()
        if detail:
            st.caption(detail)
        preview_lines = save_notice.get("preview_lines") or []
        if preview_lines:
            st.markdown("**Saved preview:**")
            for line in preview_lines:
                st.markdown(f"- {line}")
        debug = save_notice.get("override_debug") or {}
        if debug:
            st.markdown("**Override debug (temporary):**")
            if debug.get("saved_line"):
                st.markdown(f"- Saved override: {debug['saved_line']}")
            if debug.get("loaded_line"):
                st.markdown(f"- Loaded override: {debug['loaded_line']}")
            if debug.get("disk_path"):
                st.caption(f"Override file: `{debug['disk_path']}`")

    _debug_live = st.session_state.get(CHART_OVERRIDE_DEBUG_KEY)
    if _debug_live and _debug_live.get("title") == title and _debug_live.get("artist") == artist:
        st.markdown("**Override debug (last save):**")
        if _debug_live.get("saved_line"):
            st.markdown(f"- Saved override: {_debug_live['saved_line']}")
        if _debug_live.get("loaded_line"):
            st.markdown(f"- Loaded override: {_debug_live['loaded_line']}")

    _render_chart_source_banner(st, song_data)

    edit_on = st.toggle(
        "Enable editing",
        value=bool(st.session_state.get("chart_edit_mode")),
        key="chart_edit_mode_toggle",
        help="Turn on to edit chords bar-by-bar in the song's written (home) key, then Save.",
    )
    st.session_state["chart_edit_mode"] = edit_on

    if not user_ov:
        st.caption(
            "Turn **Enable editing** on, change chords below, then click "
            "**Save corrected chart** or **Save as user verified**. "
            "Your version is kept for this song across sessions."
        )

    if not edit_on:
        st.info(
            "Toggle **Enable editing** above to change chords, add bars, or add sections "
            "(Verse, Chorus, Bridge, etc.)."
        )
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

        if existing:
            prior_versions = existing.get("chart_versions") or {}
            if level in prior_versions and prior_versions[level]:
                before_sections = copy.deepcopy(prior_versions[level])
            else:
                before_sections = copy.deepcopy(existing.get("sections") or {})
        elif catalog_row:
            before_sections = sections_for_level(catalog_row, level)
        else:
            snap_versions = (snapshot or {}).get("chart_versions") or {}
            if level in snap_versions and snap_versions[level]:
                before_sections = copy.deepcopy(snap_versions[level])
            else:
                before_sections = copy.deepcopy((snapshot or {}).get("sections") or {})

        preview_lines = chart_save_preview_lines(
            cleaned,
            before=normalize_sections(before_sections),
            section_order=list(cleaned.keys()),
        )

        from song_catalog.user_overrides import OVERRIDES_PATH

        saved_entry = save_user_override(
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
        loaded_entry = get_user_override(title, artist)
        _debug_section = next(iter(cleaned.keys()), "Verse")
        saved_line = chart_override_bar_preview(
            saved_entry, section=_debug_section, bar_index=0, level=level
        )
        loaded_line = chart_override_bar_preview(
            loaded_entry, section=_debug_section, bar_index=0, level=level
        )
        try:
            from song_catalog.user_song_content import CONTENT_MY_VERSION, CONTENT_USER_VERIFIED
            from songs.user_lyrics_runtime import collect_lyrics_payload, save_user_song_content

            payload = collect_lyrics_payload(
                st,
                title=title,
                artist=artist,
                section_names=list(cleaned.keys()),
            )
            if (
                payload.get("section_lyrics")
                or payload.get("lyric_cues")
                or payload.get("performance_notes")
            ):
                save_user_song_content(
                    title=title,
                    artist=artist,
                    genre=genre,
                    content_status=CONTENT_USER_VERIFIED if save_verified else CONTENT_MY_VERSION,
                    **payload,
                )
        except Exception:
            pass
        refresh_app_catalog_globals(module_globals)
        invalidate_backing(st)
        invalidate_chart_session_caches(st)
        try:
            from songs.state import ACTIVE_CATALOG_PICK_KEY, apply_pick_key

            pick_key = str(st.session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
            picker = module_globals.get("SONG_PICKER_CATALOG") or {}
            library = module_globals.get("SONG_LIBRARY")
            if pick_key and picker:
                apply_pick_key(
                    st,
                    pick_key,
                    picker,
                    song_library=library,
                    skip_activity_log=True,
                )
        except Exception:
            pass
        st.session_state.pop(_draft_key(title, artist, level), None)
        status_label = (
            "user verified"
            if status == USER_VERIFIED
            else "corrected chart"
        )
        override_debug = {
            "saved_line": saved_line,
            "loaded_line": loaded_line,
            "disk_path": str(OVERRIDES_PATH),
        }
        st.session_state[CHART_OVERRIDE_DEBUG_KEY] = {
            "title": title,
            "artist": artist,
            **override_debug,
        }
        try:
            from picker_song_editor import collapse_picker_editor

            _status = saved_entry.get("override_status", status)
            _cap = ""
            if _status == USER_VERIFIED:
                _cap = "Using User Override Chart (user verified)."
            elif _status == USER_CORRECTED:
                _cap = "Using User Override Chart."
            collapse_picker_editor(
                st.session_state,
                title=title,
                artist=artist,
                message="Saved successfully.",
                chart_caption=_cap,
            )
        except Exception:
            pass
        st.session_state[CHART_SAVE_NOTICE_KEY] = {
            "title": title,
            "artist": artist,
            "message": "✅ Chart saved successfully",
            "detail": (
                f"Saved as **{status_label}** to disk · "
                f"{len(cleaned)} section(s) · "
                "Practice, Backing Track, Karaoke, and Creative Lab will use this chart."
            ),
            "preview_lines": preview_lines,
            "override_status": status,
            "saved_at": saved_entry.get("saved_at"),
            "override_debug": override_debug,
        }
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

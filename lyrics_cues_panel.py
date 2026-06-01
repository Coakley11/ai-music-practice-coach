"""Lyrics & cues editor — simple layout, permanent save (like the chart editor)."""

from __future__ import annotations

import html
from typing import Any

from song_catalog.user_overrides import USER_VERIFIED, catalog_snapshot_from_record
from song_catalog.user_song_content import CONTENT_USER_VERIFIED, get_user_song_content
from songs.user_lyrics_runtime import (
    hydrate_user_lyrics_session,
    lyrics_active_source_label,
    lyrics_save_status,
    lyrics_session_keys,
    lyrics_status_label,
    mark_lyrics_dirty,
    pop_lyrics_save_notice,
    revert_user_lyrics,
    save_lyrics_my_version,
    save_lyrics_user_verified,
)


def _render_lyrics_source_banner(
    st: Any,
    *,
    title: str,
    artist: str,
) -> None:
    label, kind = lyrics_active_source_label(
        st.session_state, title=title, artist=artist
    )
    entry = get_user_song_content(title, artist)
    if kind == "user":
        saved_at = (entry or {}).get("saved_at", "?")
        st.success(f"✅ {label} · saved {saved_at}")
    else:
        st.info(label)


def _sync_dirty_flag(
    session_state: dict,
    *,
    slug: str,
    title: str,
    artist: str,
    section_names: list[str],
) -> None:
    from songs.user_lyrics_runtime import collect_lyrics_payload

    current = collect_lyrics_payload(
        session_state, title=title, artist=artist, section_names=section_names
    )
    saved = get_user_song_content(title, artist) or {}
    if current.get("section_lyrics") != saved.get("section_lyrics"):
        mark_lyrics_dirty(session_state, slug)
        return
    if current.get("lyric_cues") != saved.get("lyric_cues"):
        mark_lyrics_dirty(session_state, slug)


def render_lyrics_and_cues_panel(
    st: Any,
    *,
    song_title: str,
    song_artist: str,
    section_names: list[str],
    song_data: dict | None = None,
    chart_sections: dict | None = None,
    expanded: bool | None = None,
    prominent: bool = False,
    module_globals: dict[str, Any] | None = None,
) -> None:
    """Lyrics & cues editor on Song Selection."""
    from songs.lyrics_editor import (
        add_lyrics_section,
        apply_auto_assign_lyrics,
        filter_lyric_bearing_sections,
        lyrics_paste_placeholder,
        optional_sections_to_add,
        reset_lyrics_section_layout,
        resolve_lyrics_editor_sections,
        section_lyrics_widget_key,
    )

    title = str(song_title or "")
    artist = str(song_artist or "")
    genre = str((song_data or {}).get("genre") or "Song")
    keys = lyrics_session_keys(title, artist)
    slug = keys["slug"]

    hydrate_user_lyrics_session(st.session_state, title=title, artist=artist)

    has_content = bool(
        st.session_state.get(keys["section_lyrics"])
        or st.session_state.get(keys["lyric_cues"])
    )
    if expanded is None:
        expanded = True if prominent else has_content

    def _refresh_catalog() -> None:
        if module_globals:
            try:
                from song_chart_editor import refresh_app_catalog_globals

                refresh_app_catalog_globals(module_globals)
            except Exception:
                pass

    def _body() -> None:
        if song_data is not None and chart_sections is not None:
            ordered_all = resolve_lyrics_editor_sections(
                st.session_state,
                slug,
                song_data,
                chart_sections,
            )
        else:
            ordered_all = list(section_names) if section_names else ["Full song"]
        if not ordered_all:
            ordered_all = ["Full song"]

        _sync_dirty_flag(
            st.session_state,
            slug=slug,
            title=title,
            artist=artist,
            section_names=ordered_all,
        )

        notice = pop_lyrics_save_notice(st.session_state, title=title, artist=artist)
        if notice:
            st.success(notice)

        _render_lyrics_source_banner(st, title=title, artist=artist)

        status = lyrics_save_status(
            st.session_state, slug=slug, title=title, artist=artist
        )
        if status == "unsaved":
            st.warning(f"⚠️ {lyrics_status_label(status)}")

        st.caption(
            "Add **your own** lyrics and short cues per section. "
            "Fields start blank. Saved copies are kept separately from the core catalog."
        )

        _existing_user = st.session_state.get(keys["section_lyrics"]) or {}
        ordered = filter_lyric_bearing_sections(
            ordered_all,
            show_instrumental=False,
            catalog_lyric_cues=None,
            user_section_lyrics=_existing_user,
        )

        with st.expander("Paste all lyrics at once", expanded=False):
            st.text_area(
                "Paste all lyrics",
                value=st.session_state.get(keys["song_lyrics"], ""),
                placeholder=lyrics_paste_placeholder(ordered),
                key=keys["song_lyrics"],
                height=140,
                label_visibility="collapsed",
            )
            if st.button(
                "Auto-assign to sections",
                key=f"auto_assign_lyrics::{slug}",
                use_container_width=True,
            ):
                raw_paste = str(st.session_state.get(keys["song_lyrics"]) or "")
                assigned, blocks, _debug = apply_auto_assign_lyrics(
                    st.session_state,
                    song_slug=slug,
                    section_lyrics_store_key=keys["section_lyrics"],
                    section_names=ordered,
                    raw_paste=raw_paste,
                )
                mark_lyrics_dirty(st.session_state, slug)
                if len(blocks) <= 1 and len(assigned) <= 1:
                    st.warning(
                        "Use **[Section]** headers or blank lines between sections."
                    )
                elif assigned:
                    st.success(f"Assigned {len(assigned)} section(s).")
                else:
                    st.warning(
                        "Use **[Section]** headers or blank lines between sections."
                    )
                st.rerun()

        if song_data is not None and chart_sections is not None:
            with st.expander("Manage sections", expanded=False):
                add_opts = optional_sections_to_add(ordered_all)
                if add_opts:
                    ac1, ac2 = st.columns([2, 1])
                    with ac1:
                        pick_add = st.selectbox(
                            "Add section",
                            add_opts,
                            key=f"lyrics_add_pick::{slug}",
                            label_visibility="collapsed",
                        )
                    with ac2:
                        if st.button("Add", key=f"lyrics_add_btn::{slug}", use_container_width=True):
                            add_lyrics_section(st.session_state, slug, pick_add)
                            mark_lyrics_dirty(st.session_state, slug)
                            st.rerun()
                if st.button(
                    "Reset sections to match chart",
                    key=f"lyrics_reset_layout::{slug}",
                    use_container_width=True,
                ):
                    reset_lyrics_section_layout(
                        st.session_state, slug, song_data, chart_sections
                    )
                    mark_lyrics_dirty(st.session_state, slug)
                    st.rerun()

        section_lyrics_state = st.session_state.setdefault(keys["section_lyrics"], {})
        cues_state = st.session_state.setdefault(keys["lyric_cues"], {})

        st.markdown("**Edit by section**")
        for section_name in ordered:
            widget_key = section_lyrics_widget_key(slug, section_name)
            if widget_key not in st.session_state:
                st.session_state[widget_key] = str(
                    section_lyrics_state.get(section_name, "")
                )

            st.markdown(f"**{html.escape(section_name)}**")
            l_col, c_col = st.columns([2, 1])
            with l_col:
                st.text_area(
                    "Lyrics",
                    key=widget_key,
                    height=72,
                    placeholder="Your lyrics for this section…",
                    label_visibility="collapsed",
                )
                section_lyrics_state[section_name] = str(
                    st.session_state.get(widget_key, "") or ""
                ).strip()
            with c_col:
                cue_key = f"lyric_cues_edit::{slug}::{section_name}"
                if cue_key not in st.session_state:
                    st.session_state[cue_key] = "\n".join(
                        cues_state.get(section_name) or []
                    )
                st.caption("Cues")
                st.text_area(
                    "Cues",
                    key=cue_key,
                    height=72,
                    placeholder="One cue per line",
                    label_visibility="collapsed",
                )
                raw_cue_lines = [
                    ln.strip()
                    for ln in str(st.session_state.get(cue_key, "") or "").splitlines()
                    if ln.strip()
                ]
                if raw_cue_lines:
                    cues_state[section_name] = raw_cue_lines
                elif section_name in cues_state:
                    cues_state.pop(section_name, None)

        st.session_state[keys["section_lyrics"]] = dict(section_lyrics_state)
        st.session_state[keys["lyric_cues"]] = dict(cues_state)

        with st.expander("Advanced karaoke tools", expanded=False):
            st.caption("Optional — most users can skip this.")
            st.text_area(
                "Performance notes (whole song)",
                key=keys["performance_notes"],
                height=80,
                placeholder="Overall feel, dynamics, band notes…",
                label_visibility="collapsed",
            )
            st.text_area(
                "Karaoke timing notes",
                value=str(st.session_state.get(keys["karaoke_markers"]) or ""),
                key=f"karaoke_markers_raw::{slug}",
                height=60,
                placeholder='Optional timing reminders per section',
                label_visibility="collapsed",
            )

        st.divider()
        save_a, save_b, save_c = st.columns(3)
        section_list = list(ordered_all)

        with save_a:
            if st.button(
                "Save Lyrics & Cues",
                key=f"save_lyrics::{slug}",
                type="primary",
                use_container_width=True,
                help="Save permanently for this song.",
            ):
                save_lyrics_my_version(
                    st.session_state,
                    title=title,
                    artist=artist,
                    genre=genre,
                    section_names=section_list,
                )
                _refresh_catalog()
                try:
                    from picker_song_editor import collapse_picker_editor

                    collapse_picker_editor(
                        st.session_state,
                        title=title,
                        artist=artist,
                        message="Saved successfully.",
                    )
                except Exception:
                    pass
                try:
                    st.toast("Lyrics & cues saved.", icon="🎤")
                except Exception:
                    pass
                st.rerun()
        with save_b:
            if st.button(
                "Save as user verified",
                key=f"save_lyrics_verified::{slug}",
                use_container_width=True,
                help="Mark as your preferred lyrics/cues (and verified chart if present).",
            ):
                snap = catalog_snapshot_from_record(song_data) if song_data else None
                save_lyrics_user_verified(
                    st.session_state,
                    title=title,
                    artist=artist,
                    genre=genre,
                    section_names=section_list,
                    song_data=song_data or {},
                    catalog_snapshot=snap,
                )
                _refresh_catalog()
                try:
                    from picker_song_editor import collapse_picker_editor

                    collapse_picker_editor(
                        st.session_state,
                        title=title,
                        artist=artist,
                        message="Saved successfully.",
                        chart_caption="Using User Verified Lyrics.",
                    )
                except Exception:
                    pass
                try:
                    st.toast("User verified version saved.", icon="✅")
                except Exception:
                    pass
                st.rerun()
        with save_c:
            if st.button(
                "Revert my lyrics",
                key=f"revert_lyrics::{slug}",
                use_container_width=True,
                help="Remove your saved lyrics and cues for this song.",
            ):
                revert_user_lyrics(st.session_state, title=title, artist=artist)
                _refresh_catalog()
                st.rerun()

        user_ov = (song_data or {}).get("user_override") or {}
        if user_ov.get("status") == USER_VERIFIED or (
            (song_data or {}).get("user_song_content") or {}
        ).get("status") in {CONTENT_USER_VERIFIED, USER_VERIFIED}:
            st.caption(
                "User verified is also set for the chord chart when you save from "
                "**Edit Song Chart** or **Save as user verified** here."
            )

    if prominent:
        st.markdown(
            '<div class="ui-card soft" style="margin:1rem 0 1.25rem 0;border:2px solid #c7d2fe;">',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p class="ui-card-title" style="font-size:1.05rem;">🎤 Lyrics & Cues'
            f' — {html.escape(title)}</p>',
            unsafe_allow_html=True,
        )
        _body()
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        with st.expander("🎤 Lyrics & Cues", expanded=bool(expanded)):
            _body()

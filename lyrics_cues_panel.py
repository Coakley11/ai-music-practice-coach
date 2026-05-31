"""Lyrics & performance cues editor (session + permanent user saves)."""

from __future__ import annotations

import html
from typing import Any

from song_catalog.user_overrides import USER_VERIFIED, catalog_snapshot_from_record
from song_catalog.user_song_content import CONTENT_USER_VERIFIED
from song_catalog.user_song_content import get_user_song_content
from songs.user_lyrics_runtime import (
    PERFORMANCE_CUE_PRESETS,
    collect_lyrics_payload,
    hydrate_user_lyrics_session,
    lyrics_save_status,
    lyrics_session_keys,
    lyrics_status_label,
    mark_lyrics_dirty,
    pop_lyrics_save_notice,
    save_lyrics_for_session,
    save_lyrics_my_version,
    save_lyrics_user_verified,
)


def _sync_dirty_flag(
    session_state: dict,
    *,
    slug: str,
    title: str,
    artist: str,
    section_names: list[str],
) -> None:
    """Mark unsaved when current editor content differs from last disk save."""
    from song_catalog.user_song_content import CONTENT_SESSION

    if session_state.get(f"_lyrics_save_tier::{slug}") == CONTENT_SESSION:
        return
    current = collect_lyrics_payload(
        session_state, title=title, artist=artist, section_names=section_names
    )
    saved = get_user_song_content(title, artist) or {}
    for field in ("section_lyrics", "lyric_cues", "performance_notes"):
        if current.get(field) != saved.get(field):
            mark_lyrics_dirty(session_state, slug)
            return
    if current.get("section_layout") != saved.get("section_layout"):
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
        filter_lyric_bearing_sections,
        move_lyrics_section,
        optional_sections_to_add,
        remove_lyrics_section,
        rename_lyrics_section,
        reset_lyrics_section_layout,
        apply_auto_assign_lyrics,
        lyrics_paste_placeholder,
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
        or st.session_state.get(keys["performance_notes"])
    )
    if expanded is None:
        expanded = True if prominent else has_content

    def _render_status_banner(section_list: list[str]) -> None:
        _sync_dirty_flag(
            st.session_state,
            slug=slug,
            title=title,
            artist=artist,
            section_names=section_list,
        )
        notice = pop_lyrics_save_notice(st.session_state, title=title, artist=artist)
        if notice:
            st.success(notice)
        status = lyrics_save_status(
            st.session_state, slug=slug, title=title, artist=artist
        )
        label = lyrics_status_label(status)
        if status == "unsaved":
            st.warning(f"⚠️ {label}")
        elif status == "session":
            st.info(f"ℹ️ {label}")
        elif status == "my_version":
            st.success(f"✅ {label}")
        elif status == "user_verified":
            st.success(f"✅ {label}")
        else:
            st.caption(label)

        user_ov = (song_data or {}).get("user_override") or {}
        if user_ov.get("status") == USER_VERIFIED or (
            (song_data or {}).get("user_song_content") or {}
        ).get("status") in {CONTENT_USER_VERIFIED, USER_VERIFIED}:
            st.caption("Chord chart: **User verified** version may also be active for this song.")

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

        _render_status_banner(ordered_all)
        st.caption(
            "Enter **your own** lyrics and cues — fields start blank. "
            "Nothing here changes the core catalog. Used on **Practice**, **Backing Track**, and **Karaoke**."
        )

        _existing_user = st.session_state.get(keys["section_lyrics"]) or {}
        ordered = filter_lyric_bearing_sections(
            ordered_all,
            show_instrumental=False,
            catalog_lyric_cues=None,
            user_section_lyrics=_existing_user,
        )

        st.markdown("**Paste all lyrics (optional)**")
        st.caption(
            "Use section headers like **[Verse]** or blank lines between sections, "
            "then **Auto-assign to sections**."
        )
        st.text_area(
            "Paste all lyrics (optional)",
            value=st.session_state.get(keys["song_lyrics"], ""),
            placeholder=lyrics_paste_placeholder(ordered),
            key=keys["song_lyrics"],
            height=min(120 + max(0, len(ordered) - 4) * 18, 320),
            label_visibility="collapsed",
        )

        section_lyrics_state = st.session_state.setdefault(keys["section_lyrics"], {})
        cues_state = st.session_state.setdefault(keys["lyric_cues"], {})

        assign_notice = st.session_state.pop(f"_lyrics_assign_notice::{slug}", None)
        if assign_notice:
            st.success(assign_notice)
        if st.session_state.pop(f"_lyrics_assign_warn::{slug}", None):
            st.warning(
                "Use blank lines between sections or **[Section]** headers to split the text."
            )

        if song_data is not None and chart_sections is not None:
            with st.expander("Manage song sections", expanded=False):
                add_opts = optional_sections_to_add(ordered_all)
                if add_opts:
                    ac1, ac2 = st.columns([2, 1])
                    with ac1:
                        pick_add = st.selectbox(
                            "Add optional section",
                            add_opts,
                            key=f"lyrics_add_pick::{slug}",
                            label_visibility="collapsed",
                        )
                    with ac2:
                        if st.button("Add section", key=f"lyrics_add_btn::{slug}", use_container_width=True):
                            add_lyrics_section(st.session_state, slug, pick_add)
                            mark_lyrics_dirty(st.session_state, slug)
                            st.rerun()
                custom_name = st.text_input(
                    "Custom section name",
                    placeholder="e.g. Verse 3, Tag",
                    key=f"lyrics_custom_name::{slug}",
                )
                if st.button("Add custom section", key=f"lyrics_add_custom::{slug}", use_container_width=True) and custom_name.strip():
                    add_lyrics_section(st.session_state, slug, custom_name.strip())
                    mark_lyrics_dirty(st.session_state, slug)
                    st.rerun()
                if st.button("Reset sections to song chart", key=f"lyrics_reset_layout::{slug}", use_container_width=True):
                    reset_lyrics_section_layout(st.session_state, slug, song_data, chart_sections)
                    mark_lyrics_dirty(st.session_state, slug)
                    st.rerun()

        if st.button("Auto-assign to sections", key=f"auto_assign_lyrics::{slug}", use_container_width=True):
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
                st.session_state[f"_lyrics_assign_warn::{slug}"] = True
            elif assigned:
                st.session_state[f"_lyrics_assign_notice::{slug}"] = (
                    f"Assigned {len(assigned)} section(s)."
                )
            else:
                st.session_state[f"_lyrics_assign_warn::{slug}"] = True
            st.rerun()

        with st.expander("Performance notes (whole song)", expanded=False):
            st.text_area(
                "Performance notes",
                key=keys["performance_notes"],
                height=100,
                placeholder="Overall notes: feel, dynamics, story, band communication…",
                label_visibility="collapsed",
            )

        with st.expander("Karaoke timing markers (optional)", expanded=False):
            st.caption("JSON-style notes per section, e.g. {\"Chorus\": [\"hold 2 beats before entrance\"]}")
            st.text_area(
                "Karaoke markers",
                value=str(st.session_state.get(keys["karaoke_markers"]) or ""),
                key=f"karaoke_markers_raw::{slug}",
                height=80,
                label_visibility="collapsed",
            )

        st.markdown("---")
        st.markdown("**Lyrics & cues by section**")
        st.caption(
            "Cue presets: "
            + ", ".join(PERFORMANCE_CUE_PRESETS[:4])
            + ", … — type one cue per line below."
        )

        for section_name in ordered:
            widget_key = section_lyrics_widget_key(slug, section_name)
            if widget_key not in st.session_state:
                st.session_state[widget_key] = str(
                    section_lyrics_state.get(section_name, "")
                )
            st.markdown(f"**{html.escape(section_name)}**")
            st.text_area(
                f"{section_name} lyrics",
                key=widget_key,
                height=88,
                placeholder="Your lyrics for this section (leave blank if instrumental)…",
                label_visibility="collapsed",
            )
            section_lyrics_state[section_name] = str(
                st.session_state.get(widget_key, "") or ""
            ).strip()

            existing_cues = cues_state.get(section_name) or []
            cue_key = f"lyric_cues_edit::{slug}::{section_name}"
            if cue_key not in st.session_state:
                st.session_state[cue_key] = "\n".join(existing_cues)
            st.text_area(
                f"{section_name} performance cues",
                key=cue_key,
                height=72,
                placeholder="Soft entrance\nBreathe here\nPause",
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

            preset_cols = st.columns(4)
            for i, preset in enumerate(PERFORMANCE_CUE_PRESETS[:8]):
                with preset_cols[i % 4]:
                    if st.button(
                        preset,
                        key=f"cue_preset::{slug}::{section_name}::{i}",
                        use_container_width=True,
                    ):
                        lines = raw_cue_lines[:]
                        if preset not in lines:
                            lines.append(preset)
                        st.session_state[cue_key] = "\n".join(lines)
                        cues_state[section_name] = lines
                        mark_lyrics_dirty(st.session_state, slug)
                        st.rerun()

        st.session_state[keys["section_lyrics"]] = dict(section_lyrics_state)
        st.session_state[keys["lyric_cues"]] = dict(cues_state)

        st.markdown("---")
        st.markdown("**Save lyrics & cues**")
        b1, b2, b3 = st.columns(3)
        section_list = list(ordered_all)

        with b1:
            if st.button(
                "Save for Current Session",
                key=f"save_lyrics_session::{slug}",
                use_container_width=True,
                help="Temporary — until app refresh or restart.",
            ):
                payload = collect_lyrics_payload(
                    st.session_state,
                    title=title,
                    artist=artist,
                    section_names=section_list,
                )
                st.session_state[keys["section_lyrics"]] = payload["section_lyrics"]
                st.session_state[keys["lyric_cues"]] = payload["lyric_cues"]
                save_lyrics_for_session(st.session_state, title=title, artist=artist)
                try:
                    st.toast("Saved for this session.", icon="🎤")
                except Exception:
                    pass
                st.rerun()
        with b2:
            if st.button(
                "Save to My Song Version",
                key=f"save_lyrics_my_version::{slug}",
                type="primary",
                use_container_width=True,
                help="Permanent — reloads when you open this song again.",
            ):
                save_lyrics_my_version(
                    st.session_state,
                    title=title,
                    artist=artist,
                    genre=genre,
                    section_names=section_list,
                )
                if module_globals:
                    try:
                        from song_chart_editor import refresh_app_catalog_globals

                        refresh_app_catalog_globals(module_globals)
                    except Exception:
                        pass
                try:
                    st.toast("Saved to My Song Version.", icon="💾")
                except Exception:
                    pass
                st.rerun()
        with b3:
            if st.button(
                "Save as User Verified Version",
                key=f"save_lyrics_verified::{slug}",
                use_container_width=True,
                help="Preferred version — lyrics, cues, notes, and verified chart flag.",
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
                if module_globals:
                    try:
                        from song_chart_editor import refresh_app_catalog_globals

                        refresh_app_catalog_globals(module_globals)
                    except Exception:
                        pass
                try:
                    st.toast("User verified version saved.", icon="✅")
                except Exception:
                    pass
                st.rerun()

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

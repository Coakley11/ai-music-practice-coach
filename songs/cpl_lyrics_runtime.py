"""Section lyrics for Custom Progression songs (scoped to CPL identity)."""

from __future__ import annotations

from typing import Any

CPL_LYRICS_BY_SECTION_KEY = "lyrics_by_section"
CPL_LYRICS_DIRTY_KEY = "_cpl_lyrics_dirty"
CPL_LYRICS_NOTICE_KEY = "_cpl_lyrics_save_notice"


def cpl_lyrics_identity(active: dict[str, Any]) -> str:
    rev = str(active.get("id") or "").strip()
    if rev:
        return rev
    return str(active.get("name") or "custom").strip() or "custom"


def cpl_lyrics_widget_key(identity: str, section_name: str) -> str:
    safe_id = str(identity).replace(":", "_").replace("/", "_").replace(" ", "_")
    safe_sec = str(section_name).replace(":", "_").replace("/", "_").replace(" ", "_")
    return f"cpl_section_lyrics::{safe_id}::{safe_sec}"


def cpl_section_names_for_lyrics(active: dict[str, Any]) -> list[str]:
    from custom_progression_lab import CPL_EDITABLE_SECTIONS, filled_section_names

    home = active.get("original_sections") or {}
    filled = filled_section_names(home)
    if filled:
        return filled
    return [name for name in CPL_EDITABLE_SECTIONS if name != "Full Song"]


def hydrate_cpl_lyrics_widgets(session_state: dict[str, Any], active: dict[str, Any]) -> None:
    """Seed widget keys from the CPL blob before text areas render."""
    identity = cpl_lyrics_identity(active)
    stored = dict(active.get(CPL_LYRICS_BY_SECTION_KEY) or {})
    for section_name in cpl_section_names_for_lyrics(active):
        wkey = cpl_lyrics_widget_key(identity, section_name)
        if wkey not in session_state:
            session_state[wkey] = str(stored.get(section_name) or "")


def collect_cpl_lyrics_from_session(
    session_state: dict[str, Any],
    active: dict[str, Any],
) -> dict[str, str]:
    identity = cpl_lyrics_identity(active)
    out: dict[str, str] = {}
    for section_name in cpl_section_names_for_lyrics(active):
        wkey = cpl_lyrics_widget_key(identity, section_name)
        text = str(session_state.get(wkey) or "").strip()
        if text:
            out[section_name] = text
    return out


def save_cpl_lyrics_to_active(session_state: dict[str, Any], active: dict[str, Any]) -> dict[str, Any]:
    """Persist section lyrics into the CPL active blob (cloud/disk via CPL persistence)."""
    lyrics = collect_cpl_lyrics_from_session(session_state, active)
    active = dict(active)
    active[CPL_LYRICS_BY_SECTION_KEY] = lyrics
    session_state[CPL_LYRICS_DIRTY_KEY] = False
    session_state[CPL_LYRICS_NOTICE_KEY] = "Saved lyrics for your Custom Progression."
    try:
        from songs.state import persist_music_local_state

        class _Proxy:
            session_state = session_state

        persist_music_local_state(_Proxy())
    except Exception:
        pass
    return active


def resolve_cpl_section_lyrics(
    session_state: dict[str, Any],
    active: dict[str, Any],
) -> dict[str, str]:
    """Merged lyrics for display — widget values win over stored blob."""
    stored = dict(active.get(CPL_LYRICS_BY_SECTION_KEY) or {})
    live = collect_cpl_lyrics_from_session(session_state, active)
    merged = dict(stored)
    merged.update(live)
    return merged


def render_cpl_lyrics_editor_panel(
    st: Any,
    *,
    active: dict[str, Any],
    cpl_active_key: str = "cpl_active_progression",
) -> None:
    """Section-based lyrics editor for the active Custom Progression on Songs page."""
    from custom_progression_lab import ensure_original_structure

    active = ensure_original_structure(active)
    section_names = cpl_section_names_for_lyrics(active)
    if not section_names:
        return

    hydrate_cpl_lyrics_widgets(st.session_state, active)
    notice = st.session_state.pop(CPL_LYRICS_NOTICE_KEY, None)
    if notice:
        st.success(str(notice))

    with st.container(border=True):
        st.markdown("#### Custom song lyrics")
        st.caption(
            "Add lyrics by section for your Custom Progression. "
            "Saved with this song — separate from catalog song lyrics."
        )
        identity = cpl_lyrics_identity(active)
        for section_name in section_names:
            st.text_area(
                f"{section_name} lyrics",
                key=cpl_lyrics_widget_key(identity, section_name),
                height=120,
                placeholder=f"Lyrics for {section_name}…",
            )

        col_save, col_status = st.columns([1, 2])
        with col_save:
            if st.button("Save lyrics", key="cpl_save_lyrics_btn", use_container_width=True):
                updated = save_cpl_lyrics_to_active(st.session_state, active)
                st.session_state[cpl_active_key] = updated
                st.rerun()
        with col_status:
            stored = active.get(CPL_LYRICS_BY_SECTION_KEY) or {}
            if stored:
                st.caption(f"Saved sections: {', '.join(sorted(stored.keys()))}")
            else:
                st.caption("No saved lyrics yet for this custom song.")

"""Backing track UI helpers (active song card, meter selector, debug)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import html


def render_backing_active_song_card(
    st: Any,
    song_record: dict,
    *,
    level: str,
    applied_bpm: int,
    applied_groove: str,
    applied_meter: str,
    written_key: str = "",
) -> None:
    """Compact active-song summary for Backing Track Studio."""
    title = html.escape(str(song_record.get("title") or "Active song"))
    artist = html.escape(str(song_record.get("artist") or ""))
    genre = html.escape(str(song_record.get("genre") or ""))
    written_badge = ""
    _written = html.escape(str(written_key or "").strip())
    if _written:
        written_badge = (
            f'<span class="ui-backing-badge written-key">Written {_written}</span>'
        )
    st.markdown(
        f'<div class="ui-backing-active-song-card">'
        f'<div class="ui-backing-active-song-title">{title}</div>'
        f'<div class="ui-backing-active-song-meta">{artist} · {genre} · {html.escape(level)}</div>'
        f'<div class="ui-backing-active-song-badges">'
        f"{written_badge}"
        f'<span class="ui-backing-badge bpm">{int(applied_bpm)} BPM</span>'
        f'<span class="ui-backing-badge groove">{html.escape(applied_groove)}</span>'
        f'<span class="ui-backing-badge meter">{html.escape(applied_meter)}</span>'
        f"</div></div></div>",
        unsafe_allow_html=True,
    )


def render_backing_meter_selector(
    st: Any,
    *,
    song_default_meter: str,
    applied_meter: str,
    user_override: bool,
    after_change: Callable[[], None] | None = None,
) -> str:
    """Time signature control for backing playback."""
    from songs.meter import BACKING_TIME_SIGNATURES, normalize_time_signature
    from songs.meter_state import (
        BACKING_METER_KEY,
        BACKING_METER_OVERRIDE_KEY,
        sync_backing_meter_override_from_widget,
    )

    options = list(BACKING_TIME_SIGNATURES)
    song_default = normalize_time_signature(song_default_meter)
    seed = normalize_time_signature(applied_meter if applied_meter in options else song_default)
    if BACKING_METER_KEY not in st.session_state:
        st.session_state[BACKING_METER_KEY] = seed
    if BACKING_METER_OVERRIDE_KEY not in st.session_state:
        st.session_state[BACKING_METER_OVERRIDE_KEY] = bool(user_override)

    def _on_meter_change() -> None:
        try:
            from backing_track_state import BACKING_USER_EDITS_ALLOWED_KEY, mark_backing_user_edit

            if st.session_state.get(BACKING_USER_EDITS_ALLOWED_KEY):
                mark_backing_user_edit(st.session_state)
        except ImportError:
            pass
        if after_change is not None:
            after_change()

    st.markdown('<p class="ui-playback-setup-label">Meter</p>', unsafe_allow_html=True)
    choice = st.radio(
        "Time signature",
        options,
        horizontal=True,
        key=BACKING_METER_KEY,
        on_change=_on_meter_change,
        label_visibility="collapsed",
        help="Defaults from the active song. Change to override — regenerate backing audio after.",
    )
    choice, override = sync_backing_meter_override_from_widget(st.session_state, song_default_meter)
    override_note = " · user override" if override else ""
    st.caption(f"**{choice}**{override_note}")
    return str(choice)


def render_backing_defaults_debug(
    st: Any,
    *,
    song_bpm: int,
    applied_bpm: int,
    song_groove: str,
    applied_groove: str,
    song_meter: str = "4/4",
    applied_meter: str = "4/4",
    meter_override: bool = False,
    developer_mode: bool = False,
) -> None:
    lines = [
        f"- Active song BPM: **{int(song_bpm)}**",
        f"- Applied backing BPM: **{int(applied_bpm)}**",
        f"- Active song groove: **{html.escape(song_groove)}**",
        f"- Applied groove: **{html.escape(applied_groove)}**",
        f"- Active song meter: **{html.escape(song_meter)}**",
        f"- Applied backing meter: **{html.escape(applied_meter)}**"
        + (" (override)" if meter_override else ""),
    ]
    if not developer_mode:
        return
    with st.expander("Developer Debug: Playback Defaults", expanded=False):
        st.markdown("\n".join(lines))

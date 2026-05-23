"""Backing Track page — active song card and defaults debug."""

from __future__ import annotations

import html
from typing import Any

from practice_studio import active_song_card_details, genre_visual_style


def render_backing_active_song_card(
    st: Any,
    record: dict[str, Any],
    *,
    level: str = "Intermediate",
    applied_bpm: int | None = None,
    applied_groove: str | None = None,
) -> None:
    """Premium active-song card (Song Selection style) for Backing Track."""
    try:
        details = active_song_card_details(record, level=level)
    except Exception:
        details = {
            "title": record.get("title", "Song"),
            "artist": record.get("artist", ""),
            "genre": record.get("genre", "Song"),
            "bpm": applied_bpm or 100,
            "style_label": record.get("genre", ""),
            "visual_emoji": "🎵",
            "visual_gradient": "linear-gradient(145deg,#1e3a8a,#312e81)",
            "visual_genre": record.get("genre", "Song"),
        }
    genre = html.escape(str(details.get("genre") or details.get("visual_genre") or "Song"))
    bpm = int(applied_bpm if applied_bpm is not None else details.get("bpm") or 100)
    groove = html.escape(str(applied_groove or details.get("style_label") or "Auto"))
    visual = genre_visual_style(str(record.get("genre") or "Song"))
    gradient = visual.get("gradient") or "linear-gradient(145deg,#1e3a8a,#312e81)"
    emoji = html.escape(visual.get("emoji") or details.get("visual_emoji") or "🎵")

    st.markdown(
        f'<div class="ui-backing-active-song">'
        f'<div class="ui-backing-active-art" style="background:{html.escape(gradient)};">'
        f'{emoji}<small>{genre}</small></div>'
        f'<div class="ui-backing-active-body">'
        f'<p class="ui-backing-active-kicker">Active song · Backing Track</p>'
        f'<p class="ui-backing-active-title">{html.escape(details["title"])}'
        f'<span class="ui-backing-active-dash"> — </span>'
        f'{html.escape(details["artist"])}</p>'
        f'<div class="ui-backing-active-badges">'
        f'<span class="ui-backing-badge genre">{genre}</span>'
        f'<span class="ui-backing-badge bpm">{bpm} BPM</span>'
        f'<span class="ui-backing-badge groove">{groove}</span>'
        f"</div></div></div>",
        unsafe_allow_html=True,
    )


def render_backing_defaults_debug(
    st: Any,
    *,
    song_bpm: int,
    applied_bpm: int,
    song_groove: str,
    applied_groove: str,
) -> None:
    with st.expander("Playback defaults (debug)", expanded=False):
        st.markdown(
            f"- Active song BPM: **{int(song_bpm)}**\n"
            f"- Applied backing BPM: **{int(applied_bpm)}**\n"
            f"- Active song groove: **{html.escape(song_groove)}**\n"
            f"- Applied groove: **{html.escape(applied_groove)}**"
        )

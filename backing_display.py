"""Backing Track page — active song card, meter selector, and defaults debug."""

from __future__ import annotations

import html
from typing import Any, Callable

__all__ = (
    "render_backing_active_song_card",
    "render_backing_defaults_debug",
    "render_backing_generation_debug",
    "render_backing_meter_selector",
)

from backing_generation import render_backing_generation_debug  # noqa: E402


def render_backing_active_song_card(
    st: Any,
    record: dict[str, Any],
    *,
    level: str = "Intermediate",
    applied_bpm: int | None = None,
    applied_groove: str | None = None,
    applied_meter: str | None = None,
) -> None:
    """Premium active-song card (Song Selection style) for Backing Track."""
    from practice_studio import active_song_card_details, genre_visual_style
    try:
        from app_ui import studio_card_modifier_classes
    except Exception:  # pragma: no cover - defensive
        def studio_card_modifier_classes(**_kwargs: Any) -> str:
            return ""

    try:
        import streamlit as _st_for_instrument  # type: ignore
        _active_instrument = str(_st_for_instrument.session_state.get("instrument") or "")
    except Exception:
        _active_instrument = ""
    try:
        details = active_song_card_details(
            record,
            level=level,
            instrument=_active_instrument,
        )
    except Exception:
        details = {
            "title": record.get("title", "Song"),
            "artist": record.get("artist", ""),
            "genre": record.get("genre", "Song"),
            "bpm": applied_bpm or 100,
            "style_label": record.get("genre", ""),
            "time_signature": applied_meter or "4/4",
            "visual_emoji": "🎵",
            "visual_gradient": "linear-gradient(145deg,#1e3a8a,#312e81)",
            "visual_genre": record.get("genre", "Song"),
        }
    raw_genre = str(record.get("genre") or details.get("visual_genre") or "Song")
    genre = html.escape(str(details.get("genre") or details.get("visual_genre") or "Song"))
    bpm = int(applied_bpm if applied_bpm is not None else details.get("bpm") or 100)
    groove = html.escape(str(applied_groove or details.get("style_label") or "Auto"))
    meter = html.escape(str(applied_meter or details.get("time_signature") or "4/4"))
    visual = genre_visual_style(raw_genre)
    gradient = visual.get("gradient") or "linear-gradient(145deg,#1e3a8a,#312e81)"
    emoji = html.escape(visual.get("emoji") or details.get("visual_emoji") or "🎵")
    try:
        import streamlit as _st  # type: ignore
        _instrument = str(_st.session_state.get("instrument") or "")
        _session_state = _st.session_state
    except Exception:
        _instrument = ""
        _session_state = None
    modifier_cls = studio_card_modifier_classes(genre=raw_genre, instrument=_instrument)
    # Karaoke session modifier class layered on top.
    _voice_mode = False
    _karaoke_active = False
    if _session_state is not None:
        try:
            import karaoke_mode as _km
            _voice_mode = _km.is_voice_mode(_session_state)
            _karaoke_active = _km.is_karaoke_session_active(_session_state)
        except Exception:
            _voice_mode = False
            _karaoke_active = False
    if _karaoke_active:
        modifier_cls = (modifier_cls + " mode-karaoke").strip()
        modifier_cls = " " + modifier_cls if not modifier_cls.startswith(" ") else modifier_cls
    kicker_label = "Now Singing · Vocal Performance" if _voice_mode else "Active song · Backing Track"

    original_key = str(record.get("key") or "C")
    practice_key = str(
        (_session_state or {}).get("display_key") or original_key
    )
    try:
        from app_ui import active_song_key_row_html

        key_row = active_song_key_row_html(original_key, practice_key)
    except Exception:
        key_row = ""

    st.markdown(
        f'<div class="ui-backing-active-song{modifier_cls}">'
        f'<div class="ui-backing-active-art" style="background:{html.escape(gradient)};">'
        f'{emoji}<small>{genre}</small></div>'
        f'<div class="ui-backing-active-body">'
        f'<p class="ui-backing-active-kicker">{html.escape(kicker_label)}</p>'
        f'<p class="ui-backing-active-title">{html.escape(details["title"])}'
        f'<span class="ui-backing-active-dash"> — </span>'
        f'{html.escape(details["artist"])}</p>'
        f'{key_row}'
        f'<div class="ui-backing-active-badges">'
        f'<span class="ui-backing-badge genre">{genre}</span>'
        f'<span class="ui-backing-badge bpm">{bpm} BPM</span>'
        f'<span class="ui-backing-badge groove">{groove}</span>'
        f'<span class="ui-backing-badge meter">{meter}</span>'
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
            from backing_track_state import mark_backing_pending_sync

            mark_backing_pending_sync(st.session_state)
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

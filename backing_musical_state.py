"""Canonical live resolver for Backing Studio / Creative musical state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ChartMode = Literal["concert", "written", "shape"]
SourceType = Literal[
    "regular_song", "entry_jam", "mission", "custom_progression", "song_improv", "none"
]


@dataclass(frozen=True)
class BackingMusicalState:
    """Single resolved view of keys, BPM, chart mode, and sections for the active backing source."""

    source_type: SourceType
    source_signature: str
    sync_id: str
    creative_active: bool
    skip_regular_song_defaults: bool

    practice_concert_key: str
    sidebar_display_key: str
    creative_selected_key: str
    key_mode: str

    chart_mode: ChartMode
    chart_display_key: str
    written_charts_on: bool
    guitar_shape_on: bool
    written_key: str
    shape_key: str
    show_chart_badge: bool
    chart_badge_label: str
    chart_badge_value: str

    source_bpm: int
    context_bpm: int
    slider_bpm: int
    applied_bpm: int
    bpm_source: str

    style: str
    meter: str
    groove: str

    concert_sections: dict[str, list[str]] = field(default_factory=dict)
    chart_sections: dict[str, list[str]] = field(default_factory=dict)
    progression_key_audio: str = ""
    progression_key_chart: str = ""

    instrument: str = ""


def clear_stale_chart_session_keys(session: dict[str, Any]) -> None:
    """Drop cached chart keys that can leak across chart-mode toggles."""
    session.pop("_creative_chart_display_key", None)
    session.pop("_backing_creative_chart_sections", None)


def should_skip_regular_song_defaults(session: dict[str, Any]) -> bool:
    """True when a non-catalog Creative/custom backing source owns the session."""
    try:
        from backing_context import active_creative_backing_context, get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and ctx.source == "custom_progression":
            return True
        if active_creative_backing_context(session) is not None:
            return True
    except ImportError:
        pass
    try:
        from creative_session_state import creative_session_is_active

        if creative_session_is_active(session):
            return True
    except ImportError:
        pass
    return False


def preserve_backing_musical_keys_after_generate(
    st_like: Any,
    session: dict[str, Any],
    state: BackingMusicalState,
) -> None:
    """Keep sidebar practice concert key aligned with resolver after Generate reruns."""
    if not state.creative_active:
        return
    practice = str(state.practice_concert_key or "").strip()
    if not practice:
        return
    session["concert_key"] = practice
    session["display_key"] = practice
    try:
        from songs.key_state import request_display_key

        request_display_key(st_like, practice)
    except ImportError:
        session["_pending_display_key"] = practice
    try:
        from creative_key_sync import invalidate_creative_backing_context

        invalidate_creative_backing_context(session)
    except ImportError:
        pass


def _resolve_creative_practice_concert_key(
    session: dict[str, Any],
    *,
    creative: Any,
    major_jam: bool,
) -> str:
    """Resolve practice concert key for Creative backing — sidebar wins after user edits."""
    from creative_key_sync import (
        CREATIVE_CONCERT_KEY_SOURCE,
        creative_entry_concert_key,
        to_major_key_preserve_spelling,
    )
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

        if is_fixed_practice_key_mode(session):
            original = str(getattr(creative, "key", "") or "C").strip() or "C"
            return resolve_practice_concert_key_for_song(session, original, fallback=str(creative.concert_key or "C"))
    except ImportError:
        pass

    live = str(session.get("display_key") or "").strip()
    creative_sel = str(creative_entry_concert_key(session) or creative.concert_key or "").strip()
    key_source = str(session.get(CREATIVE_CONCERT_KEY_SOURCE) or "").strip()
    if live and key_source:
        practice = live
    elif creative_sel and live and live != creative_sel and not key_source:
        practice = creative_sel
    else:
        practice = live or creative_sel or str(creative.concert_key or "C").strip() or "C"
    if major_jam and practice:
        practice = to_major_key_preserve_spelling(practice)
    return practice


def resolve_current_backing_musical_state(
    session: dict[str, Any],
    *,
    rec: dict[str, Any] | None = None,
    applied_bpm: int | None = None,
    sync_id: str = "",
    song_sync_id: str = "",
) -> BackingMusicalState:
    """Resolve live musical state for the currently active backing source."""
    from backing_context import (
        active_creative_backing_context,
        backing_page_sync_id,
        get_backing_context,
        refresh_backing_context_from_session,
        sections_dict_for_chart_display,
        sections_dict_from_backing_context,
    )
    from creative_key_sync import (
        creative_entry_concert_key,
        is_creative_major_jam_active,
        to_major_key_preserve_spelling,
    )
    from music_theory import key_mode
    from songs.bpm_state import BPM_WIDGET_KEY
    from songs.playback_defaults import backing_bpm_slider_widget_key

    ctx = get_backing_context(session)
    custom_ctx = ctx if ctx is not None and ctx.source == "custom_progression" else None
    if ctx is not None and ctx.source in {"regular_song", "custom_progression"}:
        creative = None
    else:
        creative = active_creative_backing_context(session)
    if ctx is not None and ctx.source != "regular_song" and creative is not None:
        refreshed = refresh_backing_context_from_session(session)
        if refreshed is not None:
            creative = refreshed

    creative_active = creative is not None
    major_jam = is_creative_major_jam_active(session) if creative_active else False
    source_type: SourceType = (
        creative.source
        if creative
        else (
            "custom_progression"
            if custom_ctx is not None
            else ("regular_song" if ctx and ctx.source == "regular_song" else "none")
        )
    )
    source_signature = str(
        creative.source_signature
        if creative
        else (
            custom_ctx.source_signature
            if custom_ctx is not None
            else (ctx.source_signature if ctx else "")
        )
    ).strip()
    sid = str(
        sync_id
        or backing_page_sync_id(session, song_sync_id=song_sync_id)
        or song_sync_id
        or ""
    ).strip()

    creative_selected = str(creative_entry_concert_key(session) or "").strip()
    live_practice = str(session.get("display_key") or "").strip()
    if creative_active and creative:
        practice = _resolve_creative_practice_concert_key(
            session,
            creative=creative,
            major_jam=major_jam,
        )
    elif custom_ctx is not None:
        try:
            from backing_context import _live_backing_concert_keys

            _, _, practice = _live_backing_concert_keys(session)
        except ImportError:
            practice = str(
                session.get("display_key") or session.get("concert_key") or custom_ctx.concert_key or ""
            ).strip()
    else:
        practice = ""
    if not practice:
        from songs.key_state import resolve_active_musical_key

        mk = resolve_active_musical_key(session, rec=rec, surface="backing_resolver")
        practice = str(mk.practice_concert_key or "C").strip() or "C"

    if major_jam:
        practice = to_major_key_preserve_spelling(practice)
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

        if is_fixed_practice_key_mode(session):
            fixed_original = "C"
            if creative:
                fixed_original = str(getattr(creative, "key", "") or "C").strip() or "C"
            elif custom_ctx is not None:
                fixed_original = str(custom_ctx.key or "C").strip() or "C"
            elif rec:
                fixed_original = str(rec.get("key") or practice or "C").strip() or "C"
            practice = resolve_practice_concert_key_for_song(session, fixed_original, fallback=practice)
    except ImportError:
        pass

    sidebar = str(session.get("display_key") or practice).strip() or practice
    try:
        from practice_key_mode import is_fixed_practice_key_mode

        if is_fixed_practice_key_mode(session):
            sidebar = practice
    except ImportError:
        pass
    if major_jam and sidebar:
        sidebar = to_major_key_preserve_spelling(sidebar)

    from instrument_transposition import (
        chart_in_instrument_key,
        is_transposing_instrument,
        written_key_for_instrument,
    )

    try:
        from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY
    except ImportError:
        CAPO_ENABLED_KEY = "guitar_capo_enabled"
        CAPO_SHAPE_KEY = "guitar_capo_shape_key"

    instrument = str(session.get("instrument") or "Piano").strip() or "Piano"
    written_on = bool(is_transposing_instrument(instrument) and chart_in_instrument_key(session))
    shape_on = bool(instrument == "Guitar" and session.get(CAPO_ENABLED_KEY))

    shape_key_raw = str(session.get(CAPO_SHAPE_KEY) or "").strip()
    if major_jam and shape_key_raw:
        shape_key_raw = to_major_key_preserve_spelling(shape_key_raw)

    written_key = ""
    if written_on:
        written_key = str(written_key_for_instrument(practice, instrument, session) or "").strip()
        if major_jam and written_key:
            written_key = to_major_key_preserve_spelling(written_key)

    if shape_on and shape_key_raw:
        chart_mode: ChartMode = "shape"
        chart_display = shape_key_raw
    elif written_on and written_key:
        chart_mode = "written"
        chart_display = written_key
    else:
        chart_mode = "concert"
        chart_display = practice
        clear_stale_chart_session_keys(session)

    show_badge = chart_mode != "concert" and chart_display != practice
    if show_badge:
        if chart_mode == "shape":
            badge_label, badge_val = "Guitar shape", chart_display
        else:
            badge_label, badge_val = "Written key", chart_display
    else:
        badge_label, badge_val = "", ""

    if creative:
        source_bpm = int(creative.bpm or 100)
        style = str(creative.style or "").strip()
        meter = str(creative.meter or "4/4").strip()
        groove = str(creative.groove or "").strip()
        context_bpm = source_bpm
        bpm_source = f"creative:{creative.source}"
    elif custom_ctx is not None:
        source_bpm = int(custom_ctx.bpm or 100)
        style = str(custom_ctx.style or "").strip()
        meter = str(custom_ctx.meter or session.get("backing_time_signature") or "4/4").strip()
        groove = str(custom_ctx.groove or "").strip()
        context_bpm = source_bpm
        bpm_source = "custom_progression"
    else:
        source_bpm = 100
        for key in ("active_song_bpm", "backing_track_bpm", "bpm"):
            try:
                source_bpm = int(session.get(key) or 0) or source_bpm
                break
            except (TypeError, ValueError):
                continue
        if rec:
            try:
                source_bpm = int(rec.get("bpm") or source_bpm)
            except (TypeError, ValueError):
                pass
        style = ""
        meter = str(session.get("backing_time_signature") or "4/4").strip()
        groove = str(session.get("backing_groove_style") or "").strip()
        context_bpm = source_bpm
        bpm_source = "catalog_song"

    slider_key = backing_bpm_slider_widget_key(sid) if sid else BPM_WIDGET_KEY
    slider_bpm = int(session.get(slider_key) or session.get(BPM_WIDGET_KEY) or context_bpm)
    resolved_applied = int(applied_bpm if applied_bpm is not None else slider_bpm)

    concert_sections: dict[str, list[str]] = {}
    chart_sections: dict[str, list[str]] = {}
    if creative:
        concert_sections = sections_dict_from_backing_context(session, creative)
        if concert_sections:
            chart_sections = sections_dict_for_chart_display(
                session,
                concert_sections,
                concert_key=practice,
            )
    elif custom_ctx is not None:
        concert_sections = sections_dict_from_backing_context(session, custom_ctx)
        if concert_sections:
            chart_sections = sections_dict_for_chart_display(
                session,
                concert_sections,
                concert_key=practice,
            )

    return BackingMusicalState(
        source_type=source_type,
        source_signature=source_signature,
        sync_id=sid,
        creative_active=creative_active,
        skip_regular_song_defaults=creative_active,
        practice_concert_key=practice,
        sidebar_display_key=sidebar,
        creative_selected_key=creative_selected,
        key_mode=key_mode(practice),
        chart_mode=chart_mode,
        chart_display_key=chart_display,
        written_charts_on=written_on,
        guitar_shape_on=shape_on,
        written_key=written_key,
        shape_key=shape_key_raw if shape_on else "",
        show_chart_badge=show_badge,
        chart_badge_label=badge_label,
        chart_badge_value=badge_val,
        source_bpm=source_bpm,
        context_bpm=context_bpm,
        slider_bpm=slider_bpm,
        applied_bpm=resolved_applied,
        bpm_source=bpm_source,
        style=style,
        meter=meter,
        groove=groove,
        concert_sections=dict(concert_sections),
        chart_sections=dict(chart_sections),
        progression_key_audio=practice,
        progression_key_chart=chart_display,
        instrument=instrument,
    )


def render_backing_key_state_diagnostics(st: Any, session: dict[str, Any], state: BackingMusicalState) -> None:
    """Developer-only backing key/BPM trace (?dev=1)."""
    try:
        from music_persistence_trace import music_developer_mode
    except ImportError:
        return
    if not music_developer_mode(st):
        return
    with st.expander("Developer · Backing key state", expanded=False):
        st.markdown(
            "\n".join(
                [
                    f"- **active backing source:** `{state.source_type}`",
                    f"- **source signature:** `{state.source_signature}`",
                    f"- **sync id:** `{state.sync_id}`",
                    f"- **creative selected key:** `{state.creative_selected_key or '—'}`",
                    f"- **practice concert key:** `{state.practice_concert_key}`",
                    f"- **sidebar display key:** `{state.sidebar_display_key}`",
                    f"- **key mode:** `{state.key_mode}`",
                    f"- **chart mode:** `{state.chart_mode}`",
                    f"- **chart display key:** `{state.chart_display_key}`",
                    f"- **written charts on:** `{state.written_charts_on}`",
                    f"- **guitar shape mode on:** `{state.guitar_shape_on}`",
                    f"- **bpm source:** `{state.bpm_source}`",
                    f"- **source bpm:** `{state.source_bpm}`",
                    f"- **context bpm:** `{state.context_bpm}`",
                    f"- **slider bpm:** `{state.slider_bpm}`",
                    f"- **applied bpm:** `{state.applied_bpm}`",
                    f"- **progression key (audio):** `{state.progression_key_audio}`",
                    f"- **progression key (chart):** `{state.progression_key_chart}`",
                    f"- **skipped active-song defaults:** `{state.skip_regular_song_defaults}`",
                    f"- **session display_key:** `{session.get('display_key', '')}`",
                    f"- **stale _creative_chart_display_key:** `{session.get('_creative_chart_display_key', '')}`",
                ]
            )
        )


__all__ = [
    "BackingMusicalState",
    "ChartMode",
    "SourceType",
    "clear_stale_chart_session_keys",
    "preserve_backing_musical_keys_after_generate",
    "render_backing_key_state_diagnostics",
    "resolve_current_backing_musical_state",
    "should_skip_regular_song_defaults",
]

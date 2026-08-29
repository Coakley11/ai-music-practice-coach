"""Display-only Backing Track context banner and reset control."""

from __future__ import annotations

import html
from typing import Any

from backing_context import (
    BackingContext,
    format_backing_context_banner,
    get_backing_context,
    restore_custom_song_backing,
    restore_regular_song_backing,
    sections_dict_for_chart_display,
    sections_dict_from_backing_context,
)

_MOOD_THEMES: dict[str, dict[str, str]] = {
    "Dreamy": {"accent": "#6366f1", "gradient": "linear-gradient(145deg,#6366f1,#312e81)", "badge": "badge-mood"},
    "Energetic": {"accent": "#f97316", "gradient": "linear-gradient(145deg,#fb923c,#ea580c)", "badge": "badge-mood"},
    "Bright": {"accent": "#0ea5e9", "gradient": "linear-gradient(145deg,#38bdf8,#0284c7)", "badge": "badge-mood"},
    "Mellow": {"accent": "#14b8a6", "gradient": "linear-gradient(145deg,#2dd4bf,#0f766e)", "badge": "badge-mood"},
    "Dark": {"accent": "#475569", "gradient": "linear-gradient(145deg,#334155,#0f172a)", "badge": "badge-mood"},
    "Gritty": {"accent": "#78716c", "gradient": "linear-gradient(145deg,#57534e,#292524)", "badge": "badge-mood"},
}

_STYLE_THEMES: dict[str, dict[str, str]] = {
    "Bossa Nova": {"accent": "#ea580c", "gradient": "linear-gradient(145deg,#fb923c,#c2410c)", "badge": "badge-style"},
    "Jazz Swing": {"accent": "#2563eb", "gradient": "linear-gradient(145deg,#3b82f6,#1e3a8a)", "badge": "badge-style"},
    "Blues": {"accent": "#4338ca", "gradient": "linear-gradient(145deg,#6366f1,#312e81)", "badge": "badge-style"},
    "Funk": {"accent": "#ca8a04", "gradient": "linear-gradient(145deg,#eab308,#a16207)", "badge": "badge-style"},
    "Pop": {"accent": "#ec4899", "gradient": "linear-gradient(145deg,#f472b6,#be185d)", "badge": "badge-style"},
    "Rock": {"accent": "#dc2626", "gradient": "linear-gradient(145deg,#ef4444,#991b1b)", "badge": "badge-style"},
    "Neo Soul": {"accent": "#9333ea", "gradient": "linear-gradient(145deg,#a855f7,#6b21a8)", "badge": "badge-style"},
    "Fusion": {"accent": "#0891b2", "gradient": "linear-gradient(145deg,#22d3ee,#0e7490)", "badge": "badge-style"},
    "Modal Vamp": {"accent": "#7c3aed", "gradient": "linear-gradient(145deg,#8b5cf6,#5b21b6)", "badge": "badge-style"},
    "Lo-fi": {"accent": "#64748b", "gradient": "linear-gradient(145deg,#94a3b8,#475569)", "badge": "badge-style"},
    "Latin": {"accent": "#e11d48", "gradient": "linear-gradient(145deg,#fb7185,#be123c)", "badge": "badge-style"},
}


_MOOD_ICONS: dict[str, str] = {
    "Bright": "☀️",
    "Dreamy": "🌙",
    "Dark": "🌙",
    "Energetic": "⚡",
    "Mellow": "🍃",
    "Gritty": "🎸",
}


def _groove_badge_class(intensity: str) -> str:
    low = str(intensity or "").strip().lower()
    if low == "light":
        return "badge-groove badge-groove-light"
    if low == "heavy":
        return "badge-groove badge-groove-heavy"
    return "badge-groove"


def _resolve_theme(ctx: BackingContext) -> dict[str, str]:
    mood = str(ctx.mood or "").strip()
    style = str(ctx.style or "").strip()
    if mood in _MOOD_THEMES:
        return _MOOD_THEMES[mood]
    for key, theme in _STYLE_THEMES.items():
        if key.lower() in style.lower() or style.lower() in key.lower():
            return theme
    return {"accent": "#5b21b6", "gradient": "linear-gradient(145deg,#5b21b6,#312e81)", "badge": "badge-style"}


def _themed_badge(icon: str, label: str, value: str, css_class: str = "badge-meta") -> str:
    if not str(value or "").strip():
        return ""
    return (
        f'<span class="ui-backing-badge {css_class}">'
        f"{html.escape(icon)} {html.escape(label)} · {html.escape(str(value).strip())}</span>"
    )


def _chart_badge_label(session: dict[str, Any], chart_key: str) -> tuple[str, str]:
    inst = str(session.get("instrument") or "")
    try:
        from songs.key_state import resolve_active_musical_key

        mk = resolve_active_musical_key(session)
        mode = str(mk.chart_key_mode or "").strip()
    except Exception:
        mode = ""
    if inst == "Guitar" and session.get("guitar_capo_enabled"):
        return "Guitar shape", chart_key
    if mode == "written":
        return "Written key", chart_key
    return "Charts", chart_key


def render_backing_context_banner(st: Any, session: dict[str, Any]) -> bool:
    """Show backing source banner. Returns True when a non-regular source is active."""
    from backing_musical_state import resolve_current_backing_musical_state

    ctx = get_backing_context(session)
    state = resolve_current_backing_musical_state(session)
    label = format_backing_context_banner(
        ctx,
        practice_concert_key=state.practice_concert_key,
    )
    if not label:
        return False
    if state.show_chart_badge:
        label = f"{label} · {state.chart_badge_label} {state.chart_badge_value}"
    accent = "#2563eb" if ctx and ctx.source == "entry_jam" else "#7c3aed"
    if ctx and ctx.source == "mission":
        accent = "#9333ea"
    elif ctx and ctx.source == "custom_progression":
        accent = "#0891b2"
    elif ctx and ctx.source == "regular_song":
        accent = "#64748b"
    st.markdown(
        f'<div style="border-left:4px solid {accent};border-radius:10px;padding:0.55rem 0.75rem;'
        f'margin:0.35rem 0 0.65rem;background:rgba(248,250,252,.95);">'
        f'<span style="font-size:0.88rem;font-weight:750;color:#0f172a;">{label}</span></div>',
        unsafe_allow_html=True,
    )
    return bool(ctx and ctx.source != "regular_song")


def render_backing_creative_context_card(
    st: Any,
    ctx: BackingContext,
    session: dict[str, Any],
    *,
    applied_bpm: int,
    applied_groove: str,
    applied_meter: str = "4/4",
    practice_key: str = "",
    written_key: str = "",
    musical_state: Any | None = None,
) -> None:
    """Replace the blue active-song card when Creative backing is active."""
    if ctx.source not in {"entry_jam", "song_improv", "mission"}:
        return
    from backing_musical_state import resolve_current_backing_musical_state

    state = musical_state or resolve_current_backing_musical_state(
        session,
        applied_bpm=applied_bpm,
    )
    theme = _resolve_theme(ctx)
    if ctx.source == "mission":
        source_title = "Mission Backing Jam"
        mission_chord = str(ctx.progression[0] if ctx.progression else ctx.progression_label or "").strip()
        sec_name = str(ctx.section or "").strip()
        title = html.escape(str(ctx.song_title or "Mission"))
        if ctx.mission_id:
            subtitle = html.escape(
                f"{ctx.mission_id} · {sec_name} · {mission_chord}".strip(" ·")
            )
        else:
            subtitle = html.escape(f"{sec_name} · {mission_chord}".strip(" ·"))
    elif ctx.source == "entry_jam":
        source_title = (
            "Jam Session Generator"
            if str(ctx.entry_mode or "").strip() == "Jam Session Generator"
            else (
                "Entry & Jam"
                if str(ctx.entry_mode or "").strip() in {"Style Jam Mode", "Entry & Jam"}
                else "Entry Style Jam"
            )
        )
        mode_label = str(ctx.mode_label or ctx.entry_mode or "Style Jam").replace(" Mode", "").replace(" Generator", "").strip()
        style_label = str(ctx.style or state.style or applied_groove or "Auto").strip()
        if not style_label or style_label.lower() in {"jewish ballad", "pop groove"}:
            style_label = str(ctx.style or ctx.groove or applied_groove or mode_label or "Auto").strip()
        title = html.escape(style_label or mode_label or "Creative backing")
        subtitle = html.escape(f"{source_title} · {mode_label or 'Jam'}")
    elif ctx.source == "song_improv":
        source_title = "Song-Based Improvisation"
        mode_label = str(ctx.mode_label or ctx.entry_mode or "Style Jam").replace(" Mode", "").replace(" Generator", "").strip()
        style_label = str(ctx.song_title or state.style or applied_groove or "Active song").strip()
        title = html.escape(style_label)
        subtitle = html.escape(f"{source_title} · {mode_label or style_label}")
    else:
        source_title = ctx.source_label
        mode_label = str(ctx.mode_label or ctx.entry_mode or "Style Jam").replace(" Mode", "").replace(" Generator", "").strip()
        style_label = str(state.style or ctx.style or applied_groove or "Auto").strip()
        title = html.escape(style_label or ctx.song_title or "Creative backing")
        subtitle = html.escape(f"{source_title} · {mode_label or 'Jam'}")

    if ctx.source != "mission":
        style_label = str(state.style or ctx.style or applied_groove or "Auto").strip()
    elif ctx.source == "mission":
        style_label = str(state.style or ctx.style or applied_groove or ctx.style or "Auto").strip()

    backing_style = html.escape(str(applied_groove or state.groove or style_label or "Auto"))
    try:
        from musical_context_authority import format_practice_concert_key_line

        concert = html.escape(
            format_practice_concert_key_line(
                session,
                fallback=str(state.practice_concert_key or practice_key or "C"),
            )
        )
    except ImportError:
        concert = html.escape(str(state.practice_concert_key or practice_key or "C"))
    inst_raw = str(state.instrument or session.get("instrument") or "Piano")
    try:
        from instrument_aware import instrument_theme

        inst_icon = instrument_theme(inst_raw).get("icon") or "🎵"
    except ImportError:
        try:
            from practice_ui_labels import INSTRUMENT_ICONS

            inst_icon = INSTRUMENT_ICONS.get(inst_raw, "🎵")
        except ImportError:
            inst_icon = "🎵"
    instrument = html.escape(inst_raw)
    chart_key_raw = str(state.chart_badge_value or "").strip() if state.show_chart_badge else ""
    chart_key = html.escape(chart_key_raw)
    meter = html.escape(str(applied_meter or state.meter or ctx.meter or "4/4"))
    bpm = int(state.applied_bpm or applied_bpm or ctx.bpm or 100)
    mood = str(ctx.mood or "").strip()
    groove_intensity = str(ctx.groove_intensity or "").strip()
    difficulty = str(ctx.difficulty or "").strip()

    display_sections = state.chart_sections or state.concert_sections
    if ctx.source == "mission":
        if ctx.progression:
            progression_line = html.escape(" – ".join(ctx.progression))
        else:
            progression_line = html.escape(str(ctx.progression_label or mission_chord or "Mission chord"))
    elif display_sections:
        progression_line = html.escape(" / ".join(list(display_sections.keys())[:4]))
        sample = [c for chs in display_sections.values() for c in chs[:4]]
        if sample:
            progression_line += html.escape(" · " + " – ".join(sample[:6]))
    elif ctx.progression:
        progression_line = html.escape(" – ".join(ctx.progression[:6]))
    else:
        progression_line = html.escape(str(ctx.progression_label or "Full form"))

    mood_icon = _MOOD_ICONS.get(mood, "🌙")
    groove_class = _groove_badge_class(groove_intensity)
    badges = [
        _themed_badge("🎷", "Style", style_label, _STYLE_THEMES.get(style_label, {}).get("badge", "badge-style")),
        _themed_badge(mood_icon, "Mood", mood, "badge-mood"),
        _themed_badge("🔥", "Groove", groove_intensity, groove_class),
        _themed_badge("🎯", "Jam level", difficulty, "badge-groove"),
        _themed_badge("🎼", "Concert key", concert, "badge-key"),
        _themed_badge("⏱", "BPM", str(bpm), "badge-key"),
        _themed_badge("𝄞", "Meter", meter, "badge-key"),
        _themed_badge(inst_icon, "Instrument", instrument, "badge-meta"),
    ]
    if chart_key_raw and state.show_chart_badge:
        chart_label = state.chart_badge_label or "Charts"
        badges.append(_themed_badge("📄", chart_label, chart_key_raw, "badge-key"))
    if ctx.source == "mission" and str(ctx.section or "").strip():
        badges.append(_themed_badge("🎵", "Section", str(ctx.section).strip(), "badge-meta"))
    elif display_sections:
        sec_label = " + ".join(list(display_sections.keys())[:4])
        badges.append(_themed_badge("🎵", "Sections", sec_label, "badge-meta"))
    badges_html = "".join(b for b in badges if b)

    chart_line = ""
    if chart_key and state.show_chart_badge:
        chart_label = state.chart_badge_label or "Charts"
        chart_line = (
            f'<p class="ui-backing-active-key-line">{html.escape(chart_label)}: '
            f"<strong>{chart_key}</strong></p>"
        )

    st.markdown(
        f'<div class="ui-backing-active-song mode-creative-backing ui-creative-jam-card" '
        f'style="--creative-accent:{theme["accent"]};">'
        f'<div class="ui-backing-active-art ui-creative-jam-art" style="background:{theme["gradient"]};">'
        f"🎷<small>{html.escape(source_title)}</small></div>"
        f'<div class="ui-backing-active-body ui-creative-jam-body">'
        f'<p class="ui-backing-active-kicker ui-creative-jam-kicker">'
        f'{"Mission backing jam" if ctx.source == "mission" else "Creative backing session"}</p>'
        f'<p class="ui-backing-active-title ui-creative-jam-title">{title}'
        f'<span class="ui-backing-active-dash"> · </span>'
        f'<span class="ui-backing-active-source">{subtitle}</span></p>'
        f'<p class="ui-backing-active-key-line">Practice concert key: <strong>{concert}</strong>'
        f" · BPM: <strong>{bpm}</strong> · Style: <strong>{backing_style}</strong> · Meter: <strong>{meter}</strong></p>"
        f"{chart_line}"
        f'<p class="ui-backing-active-key-line">Progression: <strong>{progression_line}</strong></p>'
        f'<div class="ui-backing-active-badges">{badges_html}</div>'
        f"</div></div>",
        unsafe_allow_html=True,
    )


def _format_progression_preview(sections: dict[str, list[str]], *, max_chords: int = 6) -> str:
    if not sections:
        return ""
    line = " / ".join(list(sections.keys())[:4])
    sample = [c for chs in sections.values() for c in chs[:max_chords]]
    if sample:
        line += " · " + " – ".join(sample[:max_chords])
    return line


def render_backing_custom_progression_context_card(
    st: Any,
    ctx: BackingContext,
    session: dict[str, Any],
    *,
    applied_bpm: int,
    applied_groove: str,
    applied_meter: str = "4/4",
    practice_key: str = "",
    written_key: str = "",
    musical_state: Any | None = None,
) -> None:
    """Blue card for CPL custom progression backing — not Creative."""
    if ctx.source != "custom_progression":
        return
    from backing_musical_state import resolve_current_backing_musical_state

    state = musical_state or resolve_current_backing_musical_state(session, applied_bpm=applied_bpm)
    title = html.escape(str(ctx.song_title or "Custom progression").strip() or "Custom progression")
    concert_raw = str(state.practice_concert_key or practice_key or ctx.concert_key or "C").strip() or "C"
    try:
        from musical_context_authority import format_practice_concert_key_line

        concert = html.escape(format_practice_concert_key_line(session, fallback=concert_raw))
    except ImportError:
        concert = html.escape(concert_raw)
    bpm = int(state.applied_bpm or applied_bpm or ctx.bpm or 100)
    groove = html.escape(str(applied_groove or state.groove or ctx.groove or "Auto").strip() or "Auto")
    meter = html.escape(str(applied_meter or state.meter or ctx.meter or "4/4").strip() or "4/4")
    source_badge = html.escape(str(ctx.source_label or "Custom progression").strip() or "Custom progression")
    try:
        from music_feature_icons import FEATURE_ICONS

        source_art_icon = FEATURE_ICONS.get("custom", "✍️")
    except ImportError:
        source_art_icon = "✍️"

    concert_sections = state.concert_sections or {}
    if not concert_sections:
        try:
            from backing_context import sections_dict_from_backing_context

            concert_sections = sections_dict_from_backing_context(session, ctx)
        except ImportError:
            pass
    if not concert_sections and ctx.progression:
        label = str(ctx.song_title or ctx.progression_label or "Progression").strip() or "Progression"
        concert_sections = {label: list(ctx.progression)}

    concert_line = html.escape(_format_progression_preview(concert_sections) or "Full form")
    chart_sections = state.chart_sections or {}
    chart_key_raw = str(state.chart_badge_value or written_key or "").strip() if state.show_chart_badge else ""
    chart_line = ""
    if chart_sections and chart_key_raw and state.chart_mode != "concert":
        chart_label = "Shape key" if state.chart_mode == "shape" else "Written key"
        chart_line = (
            f'<p class="ui-backing-active-key-line">{html.escape(chart_label)} progression: '
            f"<strong>{html.escape(_format_progression_preview(chart_sections))}</strong></p>"
        )

    gradient = "linear-gradient(145deg,#0891b2,#0e7490)"
    st.markdown(
        f'<div class="ui-backing-active-song mode-custom-progression-backing">'
        f'<div class="ui-backing-active-art" style="background:{gradient};">'
        f"{source_art_icon}<small>{source_badge}</small></div>"
        f'<div class="ui-backing-active-body">'
        f'<p class="ui-backing-active-kicker">Custom progression backing</p>'
        f'<p class="ui-backing-active-title">{title}'
        f'<span class="ui-backing-active-dash"> · </span>'
        f'<span class="ui-backing-active-source">{source_badge}</span></p>'
        f'<p class="ui-backing-active-key-line">Practice concert key: <strong>{concert}</strong>'
        f" · BPM: <strong>{bpm}</strong> · Groove: <strong>{groove}</strong> · Meter: <strong>{meter}</strong></p>"
        f'<p class="ui-backing-active-key-line">Concert practice key progression: <strong>{concert_line}</strong></p>'
        f"{chart_line}"
        f"</div></div>",
        unsafe_allow_html=True,
    )


def render_backing_edit_source_action(
    st: Any,
    session: dict[str, Any],
    ctx: BackingContext,
    *,
    on_navigate: Any,
) -> None:
    """Button row under the backing card — return to the source editor."""
    from backing_source_navigation import return_to_source_button_label

    label = return_to_source_button_label(ctx)
    if st.button(label, key="backing_edit_source_btn", use_container_width=False):
        on_navigate()


def render_backing_context_reset(st: Any, session: dict[str, Any]) -> None:
    """Reset Creative/custom backing to catalog or custom active song."""
    try:
        from backing_nav_actions import catalog_return_action_visible

        if catalog_return_action_visible(session):
            return
    except ImportError:
        pass
    ctx = get_backing_context(session)
    if ctx is None or ctx.source == "regular_song":
        return
    show_custom = _custom_progression_available(session) and ctx.source != "custom_progression"
    cols = st.columns(2) if show_custom else [st.container()]
    with cols[0]:
        if st.button("Use catalog song backing", key="backing_context_reset_btn", use_container_width=False):
            try:
                from backing_source_navigation import BACKING_INTENT_SWITCH_CATALOG, set_key_transition_intent

                set_key_transition_intent(session, BACKING_INTENT_SWITCH_CATALOG)
            except ImportError:
                pass
            restore_regular_song_backing(session, st_like=st)
            st.rerun()
    if show_custom:
        with cols[1]:
            if st.button(
                "Use custom progression backing",
                key="backing_context_reset_custom_btn",
                use_container_width=False,
            ):
                try:
                    from backing_source_navigation import BACKING_INTENT_SWITCH_CUSTOM, set_key_transition_intent

                    set_key_transition_intent(session, BACKING_INTENT_SWITCH_CUSTOM)
                except ImportError:
                    pass
                restore_custom_song_backing(session, st_like=st)
                st.rerun()


def _custom_progression_available(session: dict[str, Any]) -> bool:
    try:
        from songs.music_source import cpl_session_is_active, is_custom_progression

        return bool(cpl_session_is_active(session) or is_custom_progression(session))
    except ImportError:
        return False


def render_backing_context_dev_diagnostics(st: Any, session: dict[str, Any], *, skipped_song_defaults: bool = False) -> None:
    """Developer-only backing context trace."""
    ctx = get_backing_context(session)
    with st.expander("Developer · Backing context", expanded=False):
        if ctx is None:
            st.caption("No backing_context in session.")
            return
        st.markdown(
            "\n".join(
                [
                    f"- **source:** `{ctx.source}`",
                    f"- **source_label:** `{ctx.source_label}`",
                    f"- **mode_label:** `{ctx.mode_label}`",
                    f"- **concert_key:** `{ctx.concert_key}`",
                    f"- **chart_display_key:** `{ctx.chart_display_key}`",
                    f"- **display_key:** `{ctx.display_key}`",
                    f"- **bpm:** `{ctx.bpm}`",
                    f"- **meter:** `{ctx.meter}`",
                    f"- **mood / intensity / difficulty:** `{ctx.mood}` / `{ctx.groove_intensity}` / `{ctx.difficulty}`",
                    f"- **groove/style:** `{ctx.groove}` / `{ctx.style}`",
                    f"- **sections:** `{ctx.sections or ctx.section_labels}`",
                    f"- **progression_label:** `{ctx.progression_label}`",
                    f"- **source_signature:** `{ctx.source_signature}`",
                    f"- **skipped catalog-song defaults:** `{skipped_song_defaults}`",
                ]
            )
        )
        try:
            from music_source_ownership import CATALOG_BACKING_RESTORE_DIAG_KEY

            restore_diag = session.get(CATALOG_BACKING_RESTORE_DIAG_KEY)
            if isinstance(restore_diag, dict) and restore_diag:
                st.markdown("**Catalog restore trace**")
                st.json(restore_diag)
        except ImportError:
            pass
        play_diag = session.get("_backing_play_diag")
        if isinstance(play_diag, dict) and play_diag:
            st.markdown("**Play handler trace**")
            st.json(play_diag)

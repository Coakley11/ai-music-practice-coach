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
    label = format_backing_context_banner(ctx)
    if not label:
        return False
    state = resolve_current_backing_musical_state(session)
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
    """Replace the blue active-song card when Creative/custom backing is active."""
    from backing_musical_state import resolve_current_backing_musical_state

    state = musical_state or resolve_current_backing_musical_state(
        session,
        applied_bpm=applied_bpm,
    )
    theme = _resolve_theme(ctx)
    source_title = (
        "Entry Style Jam"
        if ctx.source == "entry_jam" and str(ctx.entry_mode or "").strip() == "Style Jam Mode"
        else (
            "Entry & Jam"
            if ctx.source == "entry_jam"
            else ("Song-Based Improvisation" if ctx.source == "song_improv" else ctx.source_label)
        )
    )
    mode_label = str(ctx.mode_label or ctx.entry_mode or "Style Jam").replace(" Mode", "").replace(" Generator", "").strip()
    if ctx.source == "song_improv":
        style_label = str(ctx.song_title or state.style or applied_groove or "Active song").strip()
        title = html.escape(style_label)
        subtitle = html.escape(f"{source_title} · {mode_label or style_label}")
    else:
        style_label = str(state.style or ctx.style or applied_groove or "Auto").strip()
        title = html.escape(style_label or ctx.song_title or "Creative backing")
        subtitle = html.escape(f"{source_title} · {mode_label or 'Jam'}")

    backing_style = html.escape(str(applied_groove or state.groove or style_label or "Auto"))
    concert = html.escape(str(state.practice_concert_key or practice_key or "C"))
    instrument = html.escape(str(state.instrument or session.get("instrument") or "Piano"))
    chart_key_raw = str(state.chart_badge_value or "").strip() if state.show_chart_badge else ""
    chart_key = html.escape(chart_key_raw)
    meter = html.escape(str(applied_meter or state.meter or ctx.meter or "4/4"))
    bpm = int(state.applied_bpm or applied_bpm or ctx.bpm or 100)
    mood = str(ctx.mood or "").strip()
    groove_intensity = str(ctx.groove_intensity or "").strip()
    difficulty = str(ctx.difficulty or "").strip()

    display_sections = state.chart_sections or state.concert_sections
    if display_sections:
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
        _themed_badge("🎺", "Instrument", instrument, "badge-meta"),
    ]
    if chart_key_raw and state.show_chart_badge:
        chart_label = state.chart_badge_label or "Charts"
        badges.append(_themed_badge("📄", chart_label, chart_key_raw, "badge-key"))
    if display_sections:
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
        f'<p class="ui-backing-active-kicker ui-creative-jam-kicker">Creative backing session</p>'
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
    ctx = get_backing_context(session)
    if ctx is None or ctx.source == "regular_song":
        return
    show_custom = _custom_progression_available(session) and ctx.source != "custom_progression"
    cols = st.columns(2) if show_custom else [st.container()]
    with cols[0]:
        if st.button("Use catalog song backing", key="backing_context_reset_btn", use_container_width=False):
            restore_regular_song_backing(session, st_like=st)
            st.rerun()
    if show_custom:
        with cols[1]:
            if st.button(
                "Use custom progression backing",
                key="backing_context_reset_custom_btn",
                use_container_width=False,
            ):
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

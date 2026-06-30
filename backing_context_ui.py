"""Display-only Backing Track context banner and reset control."""

from __future__ import annotations

import html
from typing import Any

from backing_context import (
    BackingContext,
    format_backing_context_banner,
    get_backing_context,
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
    ctx = get_backing_context(session)
    label = format_backing_context_banner(ctx)
    if not label:
        return False
    try:
        from songs.key_state import resolve_active_musical_key

        mk = resolve_active_musical_key(session)
        chart = str(mk.chart_key or ctx.chart_display_key if ctx else "").strip()
        concert = str(mk.practice_concert_key or "").strip()
        if chart and concert and chart != concert:
            label = f"{label} · Charts shown in {chart}"
    except Exception:
        pass
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
) -> None:
    """Replace the blue active-song card when Creative/custom backing is active."""
    theme = _resolve_theme(ctx)
    source_title = "Entry & Jam" if ctx.source == "entry_jam" else ctx.source_label
    mode_label = str(ctx.mode_label or ctx.entry_mode or "Style Jam").replace(" Mode", "").strip()
    style_label = str(ctx.style or applied_groove or "Auto").strip()
    backing_style = html.escape(str(applied_groove or ctx.groove or style_label or "Auto"))
    concert = html.escape(str(practice_key or ctx.concert_key or ctx.display_key or ctx.key or "C"))
    chart_key_raw = str(written_key or ctx.chart_display_key or "").strip()
    chart_key = html.escape(chart_key_raw)
    meter = html.escape(str(applied_meter or ctx.meter or "4/4"))
    bpm = int(applied_bpm or ctx.bpm or 100)
    title = html.escape(style_label or ctx.song_title or "Creative backing")
    subtitle = html.escape(f"{source_title} · {mode_label}")

    concert_sections = sections_dict_from_backing_context(session, ctx)
    chart_sections = sections_dict_for_chart_display(
        session,
        concert_sections,
        concert_key=str(practice_key or ctx.concert_key or "C"),
        ctx=ctx,
    )
    display_sections = chart_sections or concert_sections
    if ctx.section:
        progression_line = html.escape(str(ctx.section))
    elif ctx.section_labels:
        progression_line = html.escape(" + ".join(ctx.section_labels[:4]))
    elif display_sections:
        progression_line = html.escape(" / ".join(list(display_sections.keys())[:4]))
        sample = [c for chs in display_sections.values() for c in chs[:4]]
        if sample:
            progression_line += html.escape(" · " + " – ".join(sample[:6]))
    elif ctx.progression:
        progression_line = html.escape(" – ".join(ctx.progression[:6]))
    else:
        progression_line = html.escape(str(ctx.progression_label or "Full form"))

    badges = [
        _themed_badge("🎷", "Style", style_label, _STYLE_THEMES.get(style_label, {}).get("badge", "badge-style")),
        _themed_badge("🌙", "Mood", ctx.mood, "badge-mood"),
        _themed_badge("🔥", "Groove", ctx.groove_intensity, "badge-groove"),
        _themed_badge("🎯", "Jam level", ctx.difficulty, "badge-groove"),
        _themed_badge("🎼", "Concert key", concert, "badge-key"),
        _themed_badge("⏱", "BPM", str(bpm), "badge-key"),
        _themed_badge("𝄞", "Meter", meter, "badge-key"),
    ]
    if chart_key_raw and chart_key_raw != str(practice_key or ctx.concert_key or ""):
        chart_label, chart_val = _chart_badge_label(session, chart_key_raw)
        badges.append(_themed_badge("📄", chart_label, chart_val, "badge-key"))
    if ctx.sections or ctx.section_labels:
        sec_label = " + ".join((ctx.sections or ctx.section_labels)[:4])
        badges.append(_themed_badge("🎵", "Sections", sec_label, "badge-meta"))
    badges_html = "".join(b for b in badges if b)

    chart_line = ""
    if chart_key and chart_key != concert:
        chart_label, _ = _chart_badge_label(session, chart_key_raw)
        if "shape" in chart_label.lower() or "Written" in chart_label:
            chart_line = (
                f'<p class="ui-backing-active-key-line">{html.escape(chart_label)}: '
                f"<strong>{chart_key}</strong></p>"
            )
        else:
            chart_line = (
                f'<p class="ui-backing-active-key-line">Charts shown in <strong>{chart_key}</strong></p>'
            )

    st.markdown(
        f'<div class="ui-backing-active-song mode-creative-backing" '
        f'style="--creative-accent:{theme["accent"]};">'
        f'<div class="ui-backing-active-art" style="background:{theme["gradient"]};">'
        f"🎷<small>{html.escape(source_title)}</small></div>"
        f'<div class="ui-backing-active-body">'
        f'<p class="ui-backing-active-kicker">Creative backing track</p>'
        f'<p class="ui-backing-active-title">{title}'
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


def render_backing_context_reset(st: Any, session: dict[str, Any]) -> None:
    """Reset Creative/custom backing to regular active song."""
    ctx = get_backing_context(session)
    if ctx is None or ctx.source == "regular_song":
        return
    if st.button("Use regular song backing", key="backing_context_reset_btn", use_container_width=False):
        restore_regular_song_backing(session, st_like=st)
        st.rerun()


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
                    f"- **skipped regular-song defaults:** `{skipped_song_defaults}`",
                ]
            )
        )

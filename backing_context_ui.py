"""Display-only Backing Track context banner and reset control."""

from __future__ import annotations

import html
from typing import Any

from backing_context import (
    BackingContext,
    format_backing_context_banner,
    get_backing_context,
    restore_regular_song_backing,
    sections_dict_from_backing_context,
)


def render_backing_context_banner(st: Any, session: dict[str, Any]) -> bool:
    """Show backing source banner. Returns True when a non-regular source is active."""
    ctx = get_backing_context(session)
    label = format_backing_context_banner(ctx)
    if not label:
        return False
    try:
        from songs.key_state import resolve_active_musical_key

        mk = resolve_active_musical_key(session)
        chart = str(mk.chart_key or "").strip()
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
    source_titles = {
        "entry_jam": "Entry & Jam",
        "mission": "Mission",
        "custom_progression": "Custom progression",
    }
    source_title = source_titles.get(ctx.source, ctx.source_label or "Creative")
    mode_label = ""
    if ctx.source == "entry_jam":
        mode_label = str(ctx.entry_mode or "Style Jam").strip()
    elif ctx.source == "mission":
        mode_label = str(ctx.mission_id or "Mission").strip()
    style_groove = str(ctx.style or ctx.groove or applied_groove or "Auto").strip()
    concert = html.escape(str(practice_key or ctx.concert_key or ctx.display_key or ctx.key or "C"))
    groove = html.escape(str(applied_groove or ctx.groove or "Auto"))
    meter = html.escape(str(applied_meter or "4/4"))
    bpm = int(applied_bpm or ctx.bpm or 100)
    title = html.escape(str(ctx.style or ctx.song_title or "Creative backing"))
    subtitle_parts = [html.escape(source_title)]
    if mode_label and mode_label not in subtitle_parts:
        subtitle_parts.append(html.escape(mode_label))
    if style_groove and style_groove not in {title, mode_label}:
        subtitle_parts.append(html.escape(style_groove))
    subtitle = " · ".join(subtitle_parts)

    section_names = list(sections_dict_from_backing_context(session, ctx).keys())
    if ctx.section:
        progression_line = html.escape(str(ctx.section))
    elif section_names:
        progression_line = html.escape(" / ".join(section_names[:4]))
    elif ctx.progression:
        progression_line = html.escape(" – ".join(ctx.progression[:6]))
    else:
        progression_line = html.escape(str(ctx.progression_label or "Full form"))

    written_badge = ""
    _written = html.escape(str(written_key or "").strip())
    if _written and _written != concert:
        written_badge = f'<span class="ui-backing-badge written-key">Charts in {_written}</span>'

    st.markdown(
        f'<div class="ui-backing-active-song mode-creative-backing">'
        f'<div class="ui-backing-active-art" style="background:linear-gradient(145deg,#5b21b6,#312e81);">'
        f"🎷<small>{html.escape(source_title)}</small></div>"
        f'<div class="ui-backing-active-body">'
        f'<p class="ui-backing-active-kicker">Creative backing track</p>'
        f'<p class="ui-backing-active-title">{title}'
        f'<span class="ui-backing-active-dash"> · </span>'
        f'<span class="ui-backing-active-source">{subtitle}</span></p>'
        f'<p class="ui-backing-active-key-line">Concert key: <strong>{concert}</strong>'
        f" · BPM: <strong>{bpm}</strong> · Groove: <strong>{groove}</strong></p>"
        f'<p class="ui-backing-active-key-line">Progression: <strong>{progression_line}</strong></p>'
        f'<div class="ui-backing-active-badges">'
        f"{written_badge}"
        f'<span class="ui-backing-badge bpm">Backing {bpm} BPM</span>'
        f'<span class="ui-backing-badge meter">{meter}</span>'
        f'<span class="ui-backing-badge groove">{groove}</span>'
        f"</div></div></div>",
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
                    f"- **concert_key:** `{ctx.concert_key}`",
                    f"- **display_key:** `{ctx.display_key}`",
                    f"- **bpm:** `{ctx.bpm}`",
                    f"- **groove/style:** `{ctx.groove}` / `{ctx.style}`",
                    f"- **progression_label:** `{ctx.progression_label}`",
                    f"- **source_signature:** `{ctx.source_signature}`",
                    f"- **skipped regular-song defaults:** `{skipped_song_defaults}`",
                ]
            )
        )

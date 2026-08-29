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
    mk = None
    mode = ""
    try:
        from songs.key_state import resolve_active_musical_key

        mk = resolve_active_musical_key(session)
        mode = str(mk.chart_key_mode or "").strip()
    except Exception:
        mode = ""
    if inst == "Guitar" and session.get("guitar_capo_enabled"):
        try:
            from guitar_capo import shape_chart_label_for_concert

            concert = str(getattr(mk, "practice_concert_key", None) or chart_key or "C")
            shape = str(session.get("guitar_capo_shape_key") or chart_key or "")
            return "Charts in", shape_chart_label_for_concert(concert, shape)
        except Exception:
            return "Charts in", chart_key
    if mode == "written":
        return "Written key", chart_key
    return "Charts", chart_key


def render_backing_context_banner(
    st: Any,
    session: dict[str, Any],
    *,
    applied_bpm: int | None = None,
) -> bool:
    """Show backing source banner. Returns True when a non-regular source is active."""
    from backing_musical_state import resolve_current_backing_musical_state

    ctx = get_backing_context(session)
    live_bpm: int | None = int(applied_bpm) if applied_bpm is not None and int(applied_bpm) > 0 else None
    if live_bpm is None:
        try:
            from backing_play_session import current_backing_play_bpm

            live_bpm = int(
                current_backing_play_bpm(
                    session,
                    default=0,
                    sync_id=str(session.get("_backing_page_bpm_sync_id") or ""),
                )
                or 0
            ) or None
        except ImportError:
            live_bpm = None
    if live_bpm is None:
        try:
            from songs.bpm_state import BPM_WIDGET_KEY

            for key in ("backing_track_bpm", BPM_WIDGET_KEY, "bpm"):
                try:
                    val = int(session.get(key) or 0)
                except (TypeError, ValueError):
                    val = 0
                if val > 0:
                    live_bpm = val
                    break
        except ImportError:
            live_bpm = None

    state = resolve_current_backing_musical_state(session, applied_bpm=live_bpm)
    mission_chord = ""
    if ctx is not None and str(getattr(ctx, "source", "") or "") == "mission":
        try:
            from mission_projection_state import resolve_mission_projection_state

            sm = session.get("_improv_mission_section_map")
            if not isinstance(sm, list):
                from creative_chord_selection_authority import read_mission_section_map_from_session

                sm = read_mission_section_map_from_session(session)
            proj = resolve_mission_projection_state(
                session,
                section_map=sm if isinstance(sm, list) else None,
                fallback_key=str(state.practice_concert_key or ctx.concert_key or "C"),
            )
            mission_chord = str(proj.display_chord or proj.concert_chord or "").strip()
        except Exception:
            mission_chord = str(session.get("ii_selected_chord") or "").strip()
    label = format_backing_context_banner(
        ctx,
        practice_concert_key=state.practice_concert_key,
        applied_bpm=int(live_bpm or state.applied_bpm or 0) or None,
        mission_chord=mission_chord,
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
        mission_chord = ""
        try:
            from mission_projection_state import resolve_mission_projection_state

            sm = session.get("_improv_mission_section_map")
            if not isinstance(sm, list):
                try:
                    from creative_chord_selection_authority import read_mission_section_map_from_session

                    sm = read_mission_section_map_from_session(session)
                except ImportError:
                    sm = None
            proj = resolve_mission_projection_state(
                session,
                section_map=sm if isinstance(sm, list) else None,
                fallback_key=str(practice_key or ctx.concert_key or "C"),
            )
            mission_chord = str(proj.display_chord or proj.concert_chord or "").strip()
        except ImportError:
            mission_chord = ""
        if not mission_chord:
            # Prefer live selected concert identity over sealed ctx progression.
            mission_chord = str(
                session.get("ii_selected_chord")
                or (ctx.progression[0] if ctx.progression else "")
                or ctx.progression_label
                or ""
            ).strip()
            try:
                from effective_practice_context import musician_facing_chord, musician_facing_chart_key

                concert = str(practice_key or ctx.concert_key or session.get("display_key") or "C")
                chart = musician_facing_chart_key(session, concert)
                if mission_chord and chart and concert and chart != concert:
                    mission_chord = musician_facing_chord(
                        mission_chord, concert_key=concert, chart_key=chart
                    )
            except ImportError:
                pass
        sec_name = str(ctx.section or session.get("ii_selected_section") or "").strip()
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
        style_label = str(ctx.song_title or state.style or applied_groove or "Active song").strip()
        try:
            from source_session_state import format_sbi_backing_blue_card_subtitle

            subtitle = html.escape(
                format_sbi_backing_blue_card_subtitle(session, ctx=ctx)
            )
        except ImportError:
            mode_label = str(ctx.mode_label or ctx.entry_mode or "Style Jam").replace(" Mode", "").replace(" Generator", "").strip()
            subtitle = html.escape(f"{source_title} · {mode_label or style_label}")
        title = html.escape(style_label)
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

    # Current Style/Meter = live Backing widgets / play-session (same-rerun owner).
    # Sealed ctx.style/meter are Default/source only when live values are empty.
    live_groove = ""
    live_meter = ""
    try:
        from backing_play_session import (
            backing_play_session_has_override,
            effective_backing_play_overrides,
        )

        resolved = effective_backing_play_overrides(session)
        if backing_play_session_has_override(session, "groove"):
            live_groove = str(resolved.get("groove") or "").strip()
        if backing_play_session_has_override(session, "meter"):
            live_meter = str(resolved.get("meter") or "").strip()
    except ImportError:
        pass
    if not live_groove:
        live_groove = str(
            session.get("backing_groove_style")
            or applied_groove
            or state.groove
            or ""
        ).strip()
    if not live_meter:
        live_meter = str(
            session.get("backing_time_signature")
            or applied_meter
            or state.meter
            or ""
        ).strip()
    if live_groove:
        style_label = live_groove
        backing_style = html.escape(live_groove)
    else:
        backing_style = html.escape(str(applied_groove or state.groove or style_label or "Auto"))
    default_style = str(ctx.style or ctx.groove or "").strip()
    default_meter = str(ctx.meter or "4/4").strip() or "4/4"
    concert_raw = str(practice_key or state.practice_concert_key or ctx.concert_key or "C")
    if str(getattr(ctx, "source", "") or "") == "mission":
        # Mission visit: live sidebar / mission widget outranks stale resolver D.
        live_sidebar = str(session.get("display_key") or "").strip()
        mission_widget = ""
        for _k, _v in list(session.items()):
            if str(_k).startswith("display_key_mission_backing_") and str(_v or "").strip():
                mission_widget = str(_v).strip()
                break
        preferred = mission_widget or live_sidebar
        if preferred:
            concert_raw = preferred
        try:
            from pathlib import Path

            Path(__file__).resolve().parent.joinpath(
                "scripts/evidence-creative-backing/_mission_pk_card_diag.txt"
            ).write_text(
                f"practice_key={practice_key!r} state_pk={getattr(state,'practice_concert_key',None)!r} "
                f"ctx_ck={getattr(ctx,'concert_key',None)!r} display={session.get('display_key')!r} "
                f"mission_widget={mission_widget!r} concert_raw={concert_raw!r}\n",
                encoding="utf-8",
            )
        except Exception:
            pass
    try:
        from music_theory import format_key_label_from_parts, split_key_center

        tonic, mode = split_key_center(concert_raw)
        concert = html.escape(format_key_label_from_parts(tonic, mode) or concert_raw)
    except ImportError:
        concert = html.escape(concert_raw)
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
    meter = html.escape(str(live_meter or applied_meter or state.meter or ctx.meter or "4/4"))
    live_bpm = 0
    try:
        from backing_play_session import current_backing_play_bpm

        live_bpm = int(current_backing_play_bpm(session, default=0, sync_id=str(session.get("_backing_page_bpm_sync_id") or "")) or 0)
    except ImportError:
        try:
            live_bpm = int(session.get("backing_track_bpm") or session.get("bpm") or 0)
        except (TypeError, ValueError):
            live_bpm = 0
    bpm = int(live_bpm or state.applied_bpm or applied_bpm or ctx.bpm or 100)
    mood = str(ctx.mood or "").strip()
    groove_intensity = str(ctx.groove_intensity or "").strip()
    groove_display = str(ctx.groove or "").strip()
    if groove_display and groove_display.lower() in {"light", "medium", "heavy"}:
        groove_display = ""
    st_low = str(ctx.style or "").strip().lower()
    gd_low = groove_display.lower()
    if groove_display and "jewish" in gd_low and "jewish" not in st_low:
        groove_display = ""
    difficulty = str(ctx.difficulty or "").strip()

    display_sections = state.chart_sections or state.concert_sections
    # Prefer live Backing section multiselect over sealed ctx snapshot (same-rerun).
    try:
        from backing_track_state import resolve_selected_section_names

        live_names = resolve_selected_section_names(
            session,
            list((display_sections or {}).keys())
            or list((state.concert_sections or {}).keys())
            or list((getattr(ctx, "sections", None) or [])),
        )
        if live_names and isinstance(display_sections, dict) and display_sections:
            filtered = {
                name: list(display_sections[name])
                for name in live_names
                if name in display_sections
            }
            if filtered:
                display_sections = filtered
        elif live_names and isinstance(state.concert_sections, dict):
            filtered = {
                name: list(state.concert_sections[name])
                for name in live_names
                if name in state.concert_sections
            }
            if filtered:
                display_sections = filtered
    except ImportError:
        pass
    if ctx.source == "mission":
        if mission_chord:
            progression_line = html.escape(mission_chord)
        elif ctx.progression:
            # Retranspose sealed progression to live chart when possible.
            try:
                from effective_practice_context import musician_facing_chord, musician_facing_chart_key

                concert = str(practice_key or ctx.concert_key or session.get("display_key") or "C")
                chart = musician_facing_chart_key(session, concert)
                shown = [
                    musician_facing_chord(c, concert_key=concert, chart_key=chart)
                    if chart and concert and chart != concert
                    else c
                    for c in ctx.progression
                ]
                progression_line = html.escape(" – ".join(shown))
            except ImportError:
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
    ]
    if groove_display and groove_display.lower() not in {style_label.lower(), mood.lower()}:
        badges.append(_themed_badge("🔥", "Groove", groove_display, groove_class))
    badges.extend([
        _themed_badge("🎯", "Jam level", difficulty, "badge-groove"),
        _themed_badge("🎼", "Concert key", concert, "badge-key"),
        _themed_badge("⏱", "BPM", str(bpm), "badge-key"),
        _themed_badge("𝄞", "Meter", meter, "badge-key"),
        _themed_badge(inst_icon, "Instrument", instrument, "badge-meta"),
    ])
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

    style_line = f"Style: <strong>{backing_style}</strong>"
    if default_style and live_groove and default_style.lower() != live_groove.lower():
        style_line = (
            f"Default Style: <strong>{html.escape(default_style)}</strong>"
            f" · Current Style: <strong>{backing_style}</strong>"
        )
    meter_line = f"Meter: <strong>{meter}</strong>"
    current_meter_raw = str(live_meter or applied_meter or state.meter or ctx.meter or "4/4").strip()
    if default_meter and current_meter_raw and default_meter != current_meter_raw:
        meter_line = (
            f"Default Meter: <strong>{html.escape(default_meter)}</strong>"
            f" · Current Meter: <strong>{meter}</strong>"
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
        f" · BPM: <strong>{bpm}</strong> · {style_line} · {meter_line}</p>"
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
        f"🎼<small>{source_badge}</small></div>"
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
                from pathlib import Path

                Path("scripts/evidence-creative-backing/h9-use-catalog-click.txt").write_text(
                    "clicked\n", encoding="utf-8"
                )
            except Exception:
                pass
            try:
                from backing_source_navigation import BACKING_INTENT_SWITCH_CATALOG, set_key_transition_intent

                set_key_transition_intent(session, BACKING_INTENT_SWITCH_CATALOG)
            except ImportError:
                pass
            # Capture Global Active sticky PK *before* ownership switch — Custom visit
            # must not demote it to Original Key on same-pick return.
            _sticky_pick = ""
            _sticky_pk = ""
            try:
                from songs.music_source import CATALOG_BEFORE_CUSTOM_KEY, LAST_CATALOG_STATE_KEY
                from songs.practice_key_state import get_practice_concert_key, set_practice_concert_key

                for _sk in (CATALOG_BEFORE_CUSTOM_KEY, LAST_CATALOG_STATE_KEY):
                    _raw = session.get(_sk)
                    if isinstance(_raw, dict):
                        _cand = str(_raw.get("pick_key") or "").strip()
                        if _cand and not _cand.startswith("custom::") and not _cand.startswith("custom\x1f"):
                            _sticky_pick = _cand
                            break
                if not _sticky_pick:
                    _sticky_pick = str(session.get("active_catalog_pick_key") or "").strip()
                if _sticky_pick.startswith("custom::") or _sticky_pick.startswith("custom\x1f"):
                    _sticky_pick = ""
                if _sticky_pick:
                    _sticky_pk = str(get_practice_concert_key(session, _sticky_pick) or "").strip()
                    if _sticky_pk:
                        set_practice_concert_key(session, _sticky_pk, pick_key=_sticky_pick)
            except ImportError:
                pass
            try:
                from songs.key_state import invalidate_backing_cache
                from songs.music_source import (
                    SONG_PICKER_ACTIVE_SOURCE_KEY,
                    SONG_PICKER_SOURCE_CATALOG,
                    ensure_song_library,
                    ensure_song_picker_catalog,
                    switch_to_catalog_from_custom,
                    sync_song_picker_source_widget,
                )
                from songs.practice_key_state import set_practice_concert_key

                # Clear Custom surface FIRST so no later reconcile can see CPL as
                # practice owner and call activate_custom_ownership (H9 reclaim).
                session.pop("cpl_active", None)
                try:
                    from custom_progression_lab import CPL_ACTIVE_KEY

                    session.pop(CPL_ACTIVE_KEY, None)
                except ImportError:
                    pass
                try:
                    from backing_context import (
                        BACKING_PREF_CATALOG,
                        clear_backing_context,
                        set_backing_source_preference,
                    )

                    clear_backing_context(session)
                    set_backing_source_preference(session, BACKING_PREF_CATALOG)
                except ImportError:
                    session.pop("backing_context", None)

                catalog = ensure_song_picker_catalog(session)
                library = ensure_song_library(session) or catalog
                # Full ownership transition (not just a label / sealed-ctx wipe).
                # force=True: explicit button must restore Catalog even if Custom
                # flags were already partially cleared on a prior failed click.
                # Do NOT call release_specialized here — that reconciles while CPL
                # may still look active and reclaims Custom ownership.
                switch_to_catalog_from_custom(
                    st,
                    song_picker_catalog=catalog if isinstance(catalog, dict) else {},
                    song_library=library if isinstance(library, dict) else None,
                    invalidate_backing=invalidate_backing_cache,
                    force=True,
                )
                session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
                try:
                    from songs.music_source import (
                        LAST_RECONCILED_SONG_PICKER_SOURCE_KEY,
                        SONG_PICKER_PRESENTED_SOURCE_KEY,
                    )

                    session[SONG_PICKER_PRESENTED_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
                    session[LAST_RECONCILED_SONG_PICKER_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
                except ImportError:
                    pass
                # Suppress stale Custom radio restores across dual hydrate + callbacks.
                session["_block_stale_custom_radio_reclaim"] = 4
                sync_song_picker_source_widget(session, force=True, widget_safe=False)
                if _sticky_pick and _sticky_pk:
                    set_practice_concert_key(session, _sticky_pk, pick_key=_sticky_pick)
                    session["active_catalog_pick_key"] = _sticky_pick
                    # Widget may already own display_key on this run — use pending /
                    # safe assign (never direct session["display_key"] after widgets).
                    try:
                        from session_widget_safe import safe_assign_display_key

                        safe_assign_display_key(
                            session, _sticky_pk, widget_safe=True, st_like=st
                        )
                    except ImportError:
                        session["_pending_display_key"] = _sticky_pk
                        session["concert_key"] = _sticky_pk
                restore_regular_song_backing(session, st_like=st)
                session["_force_catalog_backing_after_use_catalog"] = 4
                try:
                    from pathlib import Path

                    Path("scripts/evidence-creative-backing/h9-post-switch.txt").write_text(
                        f"song={session.get('song')!r}\n"
                        f"pick={session.get('active_catalog_pick_key')!r}\n"
                        f"source={session.get('active_music_source')!r}\n"
                        f"user_catalog={session.get('_user_chose_catalog_music_source')!r}\n"
                        f"force={session.get('_force_catalog_backing_after_use_catalog')!r}\n"
                        f"ctx_source={(session.get('backing_context') or {}).get('source') if isinstance(session.get('backing_context'), dict) else session.get('backing_context')!r}\n",
                        encoding="utf-8",
                    )
                except Exception:
                    pass
                try:
                    from backing_source_navigation import (
                        BACKING_INTENT_RESTORE_LAST,
                        mark_generic_catalog_backing_entry,
                        set_backing_open_intent,
                    )

                    mark_generic_catalog_backing_entry(session)
                    set_backing_open_intent(session, BACKING_INTENT_RESTORE_LAST)
                except ImportError:
                    pass
            except Exception as _use_catalog_err:
                try:
                    from pathlib import Path
                    import traceback

                    Path("scripts/evidence-creative-backing/h9-use-catalog-error.txt").write_text(
                        f"{type(_use_catalog_err).__name__}: {_use_catalog_err}\n{traceback.format_exc()}",
                        encoding="utf-8",
                    )
                except Exception:
                    pass
                try:
                    restore_regular_song_backing(session, st_like=st)
                except Exception:
                    pass
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

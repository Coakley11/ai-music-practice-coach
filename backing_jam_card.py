"""Backing's own cards for the two generated jams: Entry & Style Jam (light blue) and Jam Session Generator (navy).

They wear the Creative cards' artwork and colours (``jam_card_art``) without any setup control. Everything named is
the jam being played: its sealed Backing context and the resolved musical state. Never the Creative controls
(``improv_*``), which Streamlit resets off that page, and never the active song. The concert key is named once,
by the Original / Practice Key row under the artwork; a written or shape key only when the chart uses one.
"""

from __future__ import annotations

import html
import re
from functools import lru_cache
from typing import Any, Mapping

import jam_card_art as art

BACKING_STYLE_JAM_CARD = "jam_card_backing_style"
BACKING_GENERATOR_CARD = "jam_card_backing_generator"

_E = html.escape


def jam_card_key(ctx: Any) -> str:
    """The Backing card container of this context ("" when Backing is not playing a generated jam)."""
    if ctx is None or str(getattr(ctx, "source", "") or "") != "entry_jam":
        return ""
    generator = str(getattr(ctx, "entry_mode", "") or "") == "Jam Session Generator"
    return BACKING_GENERATOR_CARD if generator else BACKING_STYLE_JAM_CARD


def _text(value: Any) -> str:
    return str(value or "").strip()


def jam_card_facts(
    ctx: Any, *, state: Any = None, groove: str = "", meter: str = "", bpm: int = 0, selected: Any = None,
) -> dict[str, Any]:
    """The facts the card shows, from the jam's context and the resolved state only."""
    from songs.playback_defaults import normalize_groove_label

    generator = jam_card_key(ctx) == BACKING_GENERATOR_CARD
    style = _text(getattr(ctx, "style", "")) or "Jam"
    live_groove = _text(groove) or _text(getattr(ctx, "groove", "")) or style
    ensemble = _text(getattr(ctx, "ensemble", ""))
    badge = bool(getattr(state, "show_chart_badge", False)) if state is not None else False
    sections: Mapping[str, Any] = {}
    if state is not None:
        sections = (getattr(state, "chart_sections", None) if badge else getattr(state, "concert_sections", None)) or {}
    if not sections:
        chords = [c for c in (getattr(ctx, "progression", None) or []) if _text(c)]
        sections = {style: chords} if chords else {}
    wanted = [n for n in (selected or []) if n in sections]
    if wanted:
        sections = {n: sections[n] for n in wanted}
    band, missing = "", []
    try:
        from backing_performance_plan import band_summary, performance_plan_for_backing_context

        plan = performance_plan_for_backing_context(ctx, style=normalize_groove_label(live_groove))
        band = _text(band_summary(plan))
        missing = list(getattr(plan, "unavailable", ()) or ())
    except Exception:
        pass
    return {
        "generator": generator,
        "title": (ensemble or "Jam session") if generator else f"{style} jam",
        "kicker": "Jam Session Generator" if generator else "Entry & Style Jam",
        "style": style,
        "groove": live_groove,
        "mood": _text(getattr(ctx, "mood", "")),
        "level": _text(getattr(ctx, "difficulty", "")),
        "intensity": _text(getattr(ctx, "groove_intensity", "")),
        "meter": _text(meter) or _text(getattr(ctx, "meter", "")) or "4/4",
        "bpm": int(bpm or getattr(ctx, "bpm", 0) or 0),
        "ensemble": ensemble,
        "band": band,
        "missing": missing,
        "sections": {str(n): [str(c) for c in (chs or [])] for n, chs in sections.items()},
        "chart_label": _text(getattr(state, "chart_badge_label", "")) if badge else "",
        "chart_key": _text(getattr(state, "chart_badge_value", "")) if badge else "",
        "instrument": _text(getattr(state, "instrument", "")) if state is not None else "",
    }


def _section_html(sections: Mapping[str, list[str]]) -> str:
    return "".join(
        f'<div class="jc-sec">{art.section_head_html(name, chords, i)}</div>'
        for i, (name, chords) in enumerate(art.arrangement_form(sections))
    )


def jam_card_html(facts: Mapping[str, Any]) -> str:
    """The card above its controls: artwork, what the jam is, its band (Generator), its form and chords."""
    generator = bool(facts["generator"])
    style, groove = facts["style"], facts["groove"]
    chips = [("🎼", style), ("🥁", groove if groove.lower() != style.lower() else ""), ("⏱", f"{facts['bpm']} BPM" if facts["bpm"] else ""),
             ("", facts["meter"]), ("Mood", facts["mood"]), ("Level", facts["level"]), ("Intensity", facts["intensity"])]
    if facts["chart_key"]:
        icon = "🎼"
        try:
            from instrument_aware import instrument_theme

            icon = str(instrument_theme(facts["instrument"] or "Piano").get("icon") or icon)
        except Exception:
            pass
        chips.append((f"{icon} {facts['chart_label'] or 'Charts'}", facts["chart_key"]))
    form = art.arrangement_form(facts["sections"])
    chords = sum(len(c) for _, c in form)
    line = f"{len(form)} section{'' if len(form) == 1 else 's'}, {chords} bar{'' if chords == 1 else 's'} — generated for this session"
    if not facts["sections"]:
        line = "Generate this jam on Creative to see its progression here."
    hero = art.hero_html(
        "jam_generator" if generator else "style_jam",
        kicker=str(facts["kicker"]), title=str(facts["title"]), line=line, chips=[c for c in chips if c[1]],
    )
    band = ""
    if generator and facts["ensemble"]:
        band = art.lineup_html(str(facts["ensemble"]), str(groove))
    elif facts["band"]:
        band = f'<div class="jc-lineup"><p class="jc-lineup-h">Your band</p><p class="jc-lineup-name">{_E(str(facts["band"]))}</p></div>'
    strip = ""
    if form:
        cells = "".join(
            f'<span class="jc-form-cell jc-tone-{i % art.SECTION_TONES}" style="flex:{max(1, len(chs))} 1 0">'
            f"<b>{_E(name)}</b><small>{len(chs)} bar{'' if len(chs) == 1 else 's'}</small></span>"
            for i, (name, chs) in enumerate(form)
        )
        strip = f'<div class="jc-form" role="img" aria-label="{_E("Form: " + ", ".join(n for n, _ in form))}">{cells}</div>'
    body = f"{band}{strip}{_section_html(facts['sections'])}"
    owner = "jam_session_generator" if generator else "style_jam"
    return (
        f'<div class="jc-backing" data-backing-card-owner="entry_jam" data-jam-owner="{owner}">{hero}'
        f'<div class="jc-backing-body">{body}</div></div>'
    )


@lru_cache(maxsize=1)
def backing_jam_css() -> str:
    """The Creative cards' look on Backing's containers, and the key / tempo / Play row inside them."""
    text = art.jam_cards_css()
    base = re.sub(r"^<style>|</style>$", "", text)
    base = base.replace(art.STYLE_JAM_CARD, BACKING_STYLE_JAM_CARD).replace(art.GENERATOR_CARD, BACKING_GENERATOR_CARD)
    out = [base]
    for key in (BACKING_STYLE_JAM_CARD, BACKING_GENERATOR_CARD):
        c = f".st-key-{key}"
        k = f"{c} .st-key-backing_card_key_row"
        out.append(
            f"{c}{{container-type:inline-size;container-name:jamcard}}"
            f"{c} .jc-backing-body{{display:flex;flex-direction:column;gap:.55rem;margin-top:.6rem}}"
            f"{c} .jc-sec{{padding:.5rem .7rem .1rem;border-radius:14px;background:var(--jc-panel);border:1px solid var(--jc-line)}}"
            # the controls: ordinary flow, no strip, no fixed height or negative margin
            f"{c} .st-key-backing_card_controls{{height:auto !important;min-height:0 !important;max-height:none !important;margin:0 !important;"
            "padding:.2rem 0 0 !important;background:transparent !important;border:0 !important;overflow:visible !important;z-index:auto;gap:.7rem}"
            f"{c} .st-key-backing_card_controls [data-testid=\"stHorizontalBlock\"]{{height:auto !important;flex-direction:row;flex-wrap:nowrap}}"
            f"{k} [data-testid=\"stHorizontalBlock\"]{{gap:.7rem !important;align-items:stretch !important}}"
            f"{k} [data-testid=\"stHorizontalBlock\"]>[data-testid=\"stColumn\"],{k} [data-testid=\"stHorizontalBlock\"]>[data-testid=\"stColumn\"]:first-child"
            "{flex:1 1 0 !important;min-width:0 !important;padding:.6rem .8rem .65rem !important;border-radius:14px;"
            "background:var(--jc-panel);border:1px solid var(--jc-line) !important}"
            f"{k} .ui-skp-label,{k} .ui-skp-cap,{k} .ui-skp-cap-fixed{{color:var(--jc-muted) !important}}"
            f"{k} .ui-skp-value{{color:var(--jc-ink) !important}}"
            f"{k} .ui-skp-locked{{background:var(--jc-chip) !important;border-color:var(--jc-chip-line) !important;color:var(--jc-ink) !important}}"
            f"{c} .st-key-backing_art_play_row{{padding:.55rem .8rem;border-radius:14px;background:var(--jc-panel);border:1px solid var(--jc-line)}}"
            f"{c} .st-key-backing_art_play_row [data-testid=\"stHorizontalBlock\"]>[data-testid=\"stColumn\"]:last-child{{flex:0 0 250px !important;width:250px !important;min-width:0 !important}}"
            f"{c} .st-key-backing_art_play_row label p,{c} .st-key-backing_art_play_row [data-testid=\"stMarkdownContainer\"] p,"
            f"{c} .st-key-backing_art_play_row .ui-backing-inline-label{{color:var(--jc-ink) !important}}"
            f"@container jamcard (max-width:640px){{{k} [data-testid=\"stHorizontalBlock\"],"
            f"{c} .st-key-backing_art_play_row [data-testid=\"stHorizontalBlock\"]{{flex-direction:column !important;align-items:stretch !important}}"
            f"{k} [data-testid=\"stHorizontalBlock\"]>[data-testid=\"stColumn\"],"
            f"{c} .st-key-backing_art_play_row [data-testid=\"stHorizontalBlock\"]>[data-testid=\"stColumn\"]:last-child"
            "{width:100% !important;flex:1 1 auto !important}}"
        )
    return "<style>" + re.sub(r"\s*\n\s*", " ", "".join(out)).strip() + "</style>"


def render_backing_jam_card(st: Any, ctx: Any, session: Mapping[str, Any], *, state: Any, groove: str, meter: str, bpm: int) -> None:
    from backing_musical_state import card_view

    shown = card_view(state)  # the saved Practice Key: Key Cycling only moves the sounding fields
    selected = None
    try:
        from backing_track_state import resolve_selected_section_names

        names = list((getattr(shown, "concert_sections", None) or {}).keys())
        selected = resolve_selected_section_names(session, names) if names else None
    except Exception:
        selected = None
    facts = jam_card_facts(ctx, state=shown, groove=groove, meter=meter, bpm=bpm, selected=selected)
    st.markdown(backing_jam_css() + jam_card_html(facts), unsafe_allow_html=True)


__all__ = (
    "BACKING_GENERATOR_CARD", "BACKING_STYLE_JAM_CARD", "backing_jam_css", "jam_card_facts", "jam_card_html", "jam_card_key",
    "render_backing_jam_card",
)

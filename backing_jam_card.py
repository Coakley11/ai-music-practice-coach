"""Backing's own cards for the two generated jams: Entry & Style Jam (light blue) and Jam Session Generator (navy).

They are Backing cards, built like the song cards' album covers (user, 2026-11-26: "not a copy of the Creative page"):
the artwork is the jam's own stage with the band that plays (``jam_backing_art``: a trio three instruments, a quintet
five, each the instrument the engine renders), tinted by the jam's style and lit by its energy; the card's crest is
the jam's identity (the saxophone of Style Jam, the dice of the Generator) beside its style and groove logos. Under
the artwork: the existing Original / Practice Key row, then the facts (style, groove, meter, mood, level; a written
or shape key only when the chart uses one, each with its own icon), the band and the form; then BPM and Play, then
Lead sheet / Advanced settings / Key Cycling and what Backing is set to do.

Everything named is the jam being played: its sealed Backing context and the resolved musical state. Never the
Creative controls, which Streamlit resets off that page, and never the active song. The concert key is named once,
by the key row under the artwork.
"""

from __future__ import annotations

import html
import re
from functools import lru_cache
from typing import Any, Mapping

import jam_backing_art as stage
import jam_card_art as art

BACKING_STYLE_JAM_CARD = "jam_card_backing_style"
BACKING_GENERATOR_CARD = "jam_card_backing_generator"

DICE_ICON = "\U0001F3B2"
SAX_ICON = "\U0001F3B7"

_E = html.escape


def jam_card_key(ctx: Any) -> str:
    """The Backing card container of this context ("" when Backing is not playing a generated jam)."""
    if ctx is None or str(getattr(ctx, "source", "") or "") != "entry_jam":
        return ""
    generator = str(getattr(ctx, "entry_mode", "") or "") == "Jam Session Generator"
    return BACKING_GENERATOR_CARD if generator else BACKING_STYLE_JAM_CARD


def _text(value: Any) -> str:
    return str(value or "").strip()


_SIZE_WORDS = {1: "Solo", 2: "Duo", 3: "Trio", 4: "Quartet", 5: "Quintet", 6: "Sextet", 7: "Septet"}


def band_size_word(count: int) -> str:
    return _SIZE_WORDS.get(int(count), f"{int(count)}-piece band" if count else "")


def _plan_band(plan: Any, family: str) -> tuple[list[str], list[str]]:
    """(playing, not yet) by name for a band without an ensemble name (Style Jam): the engine's own roles."""
    jazzy = family in {"jazz", "latin"}
    horn_names = {"tenor": "Tenor sax", "trumpet": "Trumpet", "trombone": "Trombone"}
    stand_in = False
    try:
        from backing_performance_plan import keys_stand_in_for_guitar

        stand_in = bool(keys_stand_in_for_guitar(plan))
    except Exception:
        stand_in = False

    def names(roles: Any) -> list[str]:
        out: list[str] = []
        for role in roles or ():
            role = str(role)
            if role == "keys":
                out.append(art.STAND_IN_PIANO if stand_in else ("Piano" if jazzy else "Keys"))
            elif role == "bass":
                out.append("Upright bass" if family == "jazz" else "Bass")
            elif role == "drums":
                out.append("Drums")
            elif role == "guitar":
                out.append("Electric guitar")
            elif role == "percussion":
                out.append("Latin percussion")
            elif role == "horns":
                out.extend(horn_names.get(str(h), str(h).title()) for h in (getattr(plan, "horns", ()) or ("tenor",)))
            else:
                out.append(role.title())
        return out

    playing = names(getattr(plan, "roles", ()))
    later = [n for n in names(getattr(plan, "unavailable", ())) if not (stand_in and "uitar" in n)]
    return playing, later


def jam_card_facts(
    ctx: Any, *, state: Any = None, groove: str = "", meter: str = "", bpm: int = 0, selected: Any = None,
) -> dict[str, Any]:
    """The facts the card shows, from the jam's context and the resolved state only."""
    from songs.playback_defaults import normalize_groove_label

    generator = jam_card_key(ctx) == BACKING_GENERATOR_CARD
    style = _text(getattr(ctx, "style", "")) or "Jam"
    live_groove = _text(groove) or _text(getattr(ctx, "groove", "")) or style
    ensemble = _text(getattr(ctx, "ensemble", ""))
    family = stage.style_family(style, live_groove)
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
    playing: list[str] = []
    later: list[str] = []
    try:
        from backing_performance_plan import jam_performance_enabled

        follows_plan = bool(jam_performance_enabled())
    except Exception:
        follows_plan = False
    if not follows_plan:
        # MUSIC_JAM_PERFORMANCE off: the engine renders its ordinary band, not the jam's plan. The card draws no
        # ensemble it cannot vouch for (user, 2026-11-26: never show an instrument as playing that is not).
        playing, later = [], []
    elif generator and ensemble:
        on, off = art.ensemble_lineup(ensemble, live_groove)
        playing, later = [n for _, n in on], [n for _, n in off]
    if follows_plan and not playing:
        try:
            from backing_performance_plan import performance_plan_for_backing_context

            plan = performance_plan_for_backing_context(ctx, style=normalize_groove_label(live_groove))
            playing, later = _plan_band(plan, family)
        except Exception:
            playing, later = [], []
    chart_mode = _text(getattr(state, "chart_mode", "")) if state is not None else ""
    shape_key = _text(getattr(state, "shape_key", "")) if state is not None else ""
    concert = _text(getattr(state, "practice_concert_key", "")) if state is not None else ""
    capo = 0
    if badge and chart_mode == "shape" and shape_key and concert:
        try:
            from guitar_capo import capo_fret_for_shape

            capo = int(capo_fret_for_shape(concert, shape_key)) % 12
        except Exception:
            capo = 0
    mood = _text(getattr(ctx, "mood", ""))
    intensity = _text(getattr(ctx, "groove_intensity", ""))
    return {
        "generator": generator,
        "title": (ensemble or "Jam session") if generator else f"{style} jam",
        "kicker": "Jam Session Generator" if generator else "Entry & Style Jam",
        "style": style,
        "groove": live_groove,
        "family": family,
        "mood": mood,
        "level": _text(getattr(ctx, "difficulty", "")),
        "intensity": intensity,
        "energy": stage.energy_level(mood, intensity),
        "meter": _text(meter) or _text(getattr(ctx, "meter", "")) or "4/4",
        "bpm": int(bpm or getattr(ctx, "bpm", 0) or 0),
        "ensemble": ensemble,
        "playing": playing,
        "not_yet": later,
        "sections": {str(n): [str(c) for c in (chs or [])] for n, chs in sections.items()},
        "chart_mode": chart_mode,
        "chart_label": _text(getattr(state, "chart_badge_label", "")) if badge else "",
        "chart_key": _text(getattr(state, "chart_badge_value", "")) if badge else "",
        "capo": capo,
        "instrument": _text(getattr(state, "instrument", "")) if state is not None else "",
    }


# --- the card -------------------------------------------------------------------------------------------------


def _member_icon(name: str) -> str:
    from music_feature_icons import instrument_icon

    low = name.lower()
    if "drum" in low:
        return "\U0001F941"
    if "percussion" in low or "conga" in low:
        return "\U0001FA98"
    if "upright" in low:
        return "\U0001F3BB"
    if "trombone" in low:
        return "\U0001F3BA"
    if low.startswith("piano") or low in {"keys", "keyboard"}:
        return instrument_icon("Piano")
    return instrument_icon(name)


_GROOVE_NAMED_STYLES = ("bossa", "samba", "swing")
_GROOVE_STYLE_PARENT = {"latin": "Latin", "jazz": "Jazz"}


def _logo(glyph: str, caption: str, cls: str = "", kind: str = "") -> str:
    if not glyph or not caption:
        return ""
    head = f"<i>{_E(kind)}</i>" if kind else ""
    title = f' title="{_E(kind)}: {_E(caption)}"' if kind else ""
    return f'<div class="jb-logo {cls}"{title}>{head}<b>{glyph}</b><small>{_E(caption)}</small></div>'


def silent_reason(name: str) -> str:
    """Why a band member is not heard: its sound is switched off, or it has none yet (never shown as playing)."""
    low = str(name or "").lower()
    if any(h in low for h in ("sax", "trumpet", "trombone", "horn")):
        try:
            import backing_horns

            if not backing_horns.enabled():
                return "recorded horns are switched off"
        except Exception:
            pass
        return "its recorded sound is not installed"
    if "percussion" in low or "conga" in low:
        return "no percussion sound yet"
    if "guitar" in low:
        return "no guitar sound for this groove yet"
    return "no sound yet"


def jam_card_head_html(facts: Mapping[str, Any]) -> str:
    """The artwork: the jam's stage and band, its identity, style and groove logos, its name."""
    from music_feature_icons import groove_logo, style_logo

    generator = bool(facts["generator"])
    style, groove = str(facts["style"]), str(facts["groove"])
    playing, later = list(facts.get("playing") or []), list(facts.get("not_yet") or [])
    count = len(playing) + len(later)
    art_name = stage.GENERATOR if generator else stage.STYLE_JAM
    who = ", ".join(playing) or "the band"
    svg = stage.jam_stage_svg(
        art_name, playing=playing, not_yet=later, style=style, groove=groove, mood=str(facts.get("mood") or ""),
        intensity=str(facts.get("intensity") or ""), featured="" if generator else "Saxophone",
        label=f"{facts['kicker']} stage: {who}",
    )
    crest = _logo(DICE_ICON, "Generated", "jb-crest") if generator else _logo(SAX_ICON, "Style Jam", "jb-crest")
    same = groove.lower() == style.lower()
    if same:
        # A jam whose style is itself a Backing groove ("Bossa Nova", "Jazz Swing", "Samba") shows that name as the
        # groove, with the groove's logo, under its style family (Latin, Jazz): Bossa is a groove, Latin a style.
        parent = _GROOVE_STYLE_PARENT.get(stage.style_family(style))
        if parent and any(t in style.lower() for t in _GROOVE_NAMED_STYLES) and groove_logo(groove):
            style, same = parent, False
    logos =_logo(style_logo(style), style, kind="Style") + ("" if same else _logo(groove_logo(groove), groove, kind="Groove"))
    size_pill = ""
    if count:
        size = band_size_word(count)
        size_pill = (f'<span class="jb-pill">{_E(size)} · {count} player{"" if count == 1 else "s"}</span>' if generator
                     else f'<span class="jb-pill">{_E(size)} backing</span>')
    mood = str(facts.get("mood") or "")
    # Style and groove are the labelled tiles beside the name; the line says the feel and the tempo.
    intensity = str(facts.get("intensity") or "")
    sub = " · ".join(x for x in (mood, f"{intensity} intensity" if intensity else "", f"{facts['bpm']} BPM" if facts["bpm"] else "") if x)
    kicker_icon = DICE_ICON if generator else SAX_ICON
    return (
        f'<div class="jb-hero jb-{art_name} jc-hero-{art_name} jb-e{int(facts.get("energy", 1))}">'
        f'<div class="jb-art">{svg}</div><div class="jb-scrim"></div>'
        f'<div class="jb-top"><span class="jb-kicker">{kicker_icon} {_E(str(facts["kicker"]))}</span>{size_pill}</div>'
        f'<div class="jb-id"><div class="jb-crests">{crest}{logos}</div>'
        f'<div class="jb-names"><h3 class="jb-title">{_E(str(facts["title"]))}</h3><p class="jb-sub">{_E(sub)}</p></div></div>'
        "</div>"
    )


def chart_key_chip(facts: Mapping[str, Any]) -> tuple[str, str, str]:
    """(icon, label, value) of the chart key the card shows, or ("", "", "") when the chart is in concert pitch."""
    from music_feature_icons import chart_key_badge

    value = str(facts.get("chart_key") or "")
    if not value:
        return "", "", ""
    icon, label = chart_key_badge(str(facts.get("chart_mode") or ""), label=str(facts.get("chart_label") or ""),
                                  instrument=str(facts.get("instrument") or ""))
    if label == "Shape key" and int(facts.get("capo") or 0):
        value = f"{value} · capo {int(facts['capo'])}"
    return icon, label, value


def _stat(icon: str, label: str, value: str, logo: str = "") -> str:
    if not str(value or "").strip():
        return ""
    from music_feature_icons import format_icon_html

    logo_html = f'<em class="jb-vg">{logo}</em> ' if logo else ""
    return f'<span class="jb-stat"><i>{format_icon_html(icon)}</i><span>{_E(label)}</span> <b>{logo_html}{_E(value)}</b></span>'


def jam_card_facts_html(facts: Mapping[str, Any]) -> str:
    """Under the key row: style, groove, meter, mood, intensity, level, the chart key; the band; the form."""
    from music_feature_icons import FEATURE_ICONS, SEMANTIC_FIELD_ICONS, groove_logo, style_logo
    from practice_ui_labels import LEVEL_ICONS

    style, groove = str(facts["style"]), str(facts["groove"])
    same = groove.lower() == style.lower()
    c_icon, c_label, c_value = chart_key_chip(facts)
    # Style, groove, mood, intensity and tempo are on the artwork (labelled tiles and the line under the name): the
    # chips add only what it does not say -- no heading or fact twice (user, 2026-11-26).
    del style, groove, same, FEATURE_ICONS, groove_logo, style_logo
    stats = "".join((
        _stat(SEMANTIC_FIELD_ICONS["meter"], "Meter", str(facts["meter"])),
        _stat(LEVEL_ICONS.get(str(facts.get("level") or ""), SEMANTIC_FIELD_ICONS["level"]), "Level", str(facts.get("level") or "")),
        _stat(c_icon, c_label, c_value) if c_value else "",
    ))
    playing, later = list(facts.get("playing") or []), list(facts.get("not_yet") or [])
    band = ""
    if playing or later:
        members = "".join(f'<span class="jb-member"><i>{_member_icon(n)}</i>{_E(n)}</span>' for n in playing)
        members += "".join(
            f'<span class="jb-member jb-member-off" title="Sound off: {_E(silent_reason(n))}"><i>{_member_icon(n)}</i>{_E(n)}'
            '<em class="jb-off">🔇 sound off</em></span>' for n in later
        )
        # The ensemble is already the card's title: the strip only says it is the band.
        ens = str(facts.get("ensemble") or "")
        head = f"Your band · {ens}" if ens and ens != str(facts.get("title") or "") else "Your band"
        notes = ""
        if any(n == art.STAND_IN_PIANO for n in playing):
            notes += '<p class="jb-note">The recorded guitar is not available here, so the piano plays the guitar&#39;s part.</p>'
        if later:
            why = "; ".join(f"{n}: {silent_reason(n)}" for n in later)
            notes += f'<p class="jb-note">Shown in grey, not heard: {_E(why)}.</p>'
        band = f'<div class="jb-band"><p class="jb-h">{_E(head)}</p><div class="jb-members">{members}</div>{notes}</div>'
    form = art.arrangement_form(facts["sections"])
    if form:
        bars = sum(len(c) for _, c in form)
        cells = "".join(
            f'<span class="jb-form-cell jb-tone-{i % art.SECTION_TONES}" style="flex:{max(1, len(chs))} 1 0">'
            f"<b>{_E(name)}</b><small>{len(chs)} bar{'' if len(chs) == 1 else 's'}</small></span>"
            for i, (name, chs) in enumerate(form)
        )
        rows = "".join(
            f'<div class="jb-prog-row"><span class="jb-prog-name jb-tone-{i % art.SECTION_TONES}">{_E(name)}</span>'
            f'<span class="jb-prog-chords">{"".join(f"<span>{_E(c)}</span>" for c in chs)}</span></div>'
            for i, (name, chs) in enumerate(form)
        )
        summary = f"Form · {len(form)} section{'' if len(form) == 1 else 's'}, {bars} bar{'' if bars == 1 else 's'}"
        label = _E("Form: " + ", ".join(n for n, _ in form))
        form_html = (
            f'<div class="jb-form-wrap"><div class="jb-form" role="img" aria-label="{label}">{cells}</div>'
            f'<details class="jb-prog"><summary>{_E(summary)} · chords</summary>{rows}</details></div>'
        )
    else:
        form_html = '<p class="jb-note jb-empty">Generate this jam on Creative to see its progression here.</p>'
    return f'<div class="jb-facts"><div class="jb-stats">{stats}</div>{band}{form_html}</div>'


def jam_card_html(facts: Mapping[str, Any]) -> str:
    """The whole card's own markup (artwork and facts), as one block."""
    owner = "jam_session_generator" if facts["generator"] else "style_jam"
    return (
        f'<div class="jb-card" data-backing-card-owner="entry_jam" data-jam-owner="{owner}">'
        f"{jam_card_head_html(facts)}{jam_card_facts_html(facts)}</div>"
    )


# --- what Backing is set to do, under Lead sheet / Advanced settings / Key Cycling ------------------------------


def backing_state_items(session: Mapping[str, Any], *, sheet_visible: bool, sheet_on_play: bool) -> list[tuple[str, str]]:
    """(icon, words) for the settings a musician wants at a glance: Key Cycling, the lead sheet, count-in, what plays
    and how often. Read only: each comes from the control that owns it."""
    from music_feature_icons import FEATURE_ICONS

    items: list[tuple[str, str]] = []
    if str(session.get("backing_key_cycle_enabled_ui") or "Off") == "On":
        step = _text(session.get("backing_key_cycle_step_ui")).lower()
        direction = _text(session.get("backing_key_cycle_direction_ui")).lower()
        detail = " ".join(x for x in (step, direction) if x)
        items.append((FEATURE_ICONS["key_cycle"], f"Key Cycling on{' · ' + detail if detail else ''}"))
    if sheet_visible:
        items.append(("\U0001F4D6", "Lead sheet open"))
    elif sheet_on_play:
        items.append(("\U0001F4D6", "Lead sheet opens on Play"))
    else:
        items.append(("\U0001F4D5", "Lead sheet stays closed on Play"))
    try:
        from backing_count_in import COUNT_IN_SETTING_KEY

        if session.get(COUNT_IN_SETTING_KEY):
            items.append(("⏱️", "Count-in on"))
    except Exception:
        pass
    scope = _text(session.get("backing_track_scope")) or "Full song"
    try:
        loops_n = int(session.get("backing_track_loops") or 0)
    except (TypeError, ValueError):
        loops_n = 0
    items.append((FEATURE_ICONS["section_focus"], f"{scope}{f' × {loops_n}' if loops_n > 0 else ''}"))
    return items


def backing_state_html(items: list[tuple[str, str]]) -> str:
    if not items:
        return ""
    cells = "".join(f'<span class="jb-state"><i>{_E(i)}</i>{_E(t)}</span>' for i, t in items)
    return f'<div class="jb-states" aria-label="Backing settings">{cells}</div>'


# --- CSS ------------------------------------------------------------------------------------------------------


def _card_rules(key: str) -> str:
    c = f".st-key-{key}"
    k = f"{c} .st-key-backing_card_key_row"
    if key == BACKING_GENERATOR_CARD:
        scrim = ("linear-gradient(90deg,rgba(8,14,38,.9) 0%,rgba(8,14,38,.55) 38%,rgba(8,14,38,0) 62%),"
                 "linear-gradient(0deg,rgba(8,14,38,.82) 0%,rgba(8,14,38,0) 46%)")
    else:
        scrim = ("linear-gradient(90deg,rgba(240,249,255,.94) 0%,rgba(240,249,255,.6) 36%,rgba(240,249,255,0) 60%),"
                 "linear-gradient(0deg,rgba(240,249,255,.88) 0%,rgba(240,249,255,0) 44%)")
    return (
        f"{c}{{container-type:inline-size;container-name:jamcard;padding:0 0 14px !important;overflow:hidden}}"
        f"{c} .jb-hero{{position:relative;overflow:hidden;min-height:250px;border-radius:21px 21px 0 0;background:var(--jc-hero-bg)}}"
        f"{c} .jb-art{{position:absolute;inset:0}}"
        f"{c} .jb-art svg{{width:100%;height:100%;display:block}}"
        f"{c} .jb-scrim{{position:absolute;inset:0;background:{scrim};pointer-events:none}}"
        f"{c} .jb-top{{position:relative;display:flex;justify-content:space-between;flex-wrap:wrap;gap:.5rem;padding:14px 16px 0}}"
        f"{c} .jb-kicker,{c} .jb-pill{{display:inline-flex;align-items:center;gap:.3rem;padding:.2rem .65rem;border-radius:999px;"
        "font-size:.72rem;font-weight:850;letter-spacing:.04em;background:var(--jc-chip);border:1px solid var(--jc-chip-line);color:var(--jc-ink)}"
        f"{c} .jb-pill{{letter-spacing:0}}"
        f"{c} .jb-id{{position:absolute;left:16px;right:16px;bottom:14px;display:flex;align-items:flex-end;gap:.8rem}}"
        f"{c} .jb-crests{{display:flex;gap:.4rem;flex:0 0 auto}}"
        f"{c} .jb-logo{{display:flex;flex-direction:column;align-items:center;justify-content:center;min-width:3.6rem;padding:.35rem .4rem .3rem;"
        "border-radius:14px;background:var(--jc-chip);border:1px solid var(--jc-chip-line);box-shadow:0 4px 14px rgba(2,32,71,.18)}"
        f"{c} .jb-logo b{{font-size:1.45rem;line-height:1.1}}"
        f"{c} .jb-logo small{{font-size:.62rem;font-weight:800;color:var(--jc-muted);max-width:4.6rem;text-align:center;line-height:1.15;"
        "overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
        f"{c} .jb-logo i{{font-style:normal;font-size:.52rem;font-weight:850;letter-spacing:.08em;text-transform:uppercase;color:var(--jc-muted);line-height:1}}"
        f"{c} .jb-off{{font-style:normal;font-size:.68rem;font-weight:800;margin-left:.2rem;color:var(--jc-muted)}}"
        f"{c} .jb-crest{{background:var(--jc-accent);border-color:var(--jc-accent)}}"
        f"{c} .jb-crest small{{color:var(--jc-accent-ink)}}"
        f"{c} .jb-names{{min-width:0}}"
        f"{c} .jb-title{{margin:0;padding:0;font-size:1.6rem;line-height:1.12;font-weight:850;color:var(--jc-ink);text-wrap:balance}}"
        f"{c} .jb-sub{{margin:.15rem 0 0;font-size:.86rem;font-weight:650;color:var(--jc-muted)}}"
        f"{c} .jb-facts{{display:flex;flex-direction:column;gap:.55rem}}"
        f"{c} .jb-stats{{display:flex;flex-wrap:wrap;gap:.35rem .4rem}}"
        f"{c} .jb-stat{{display:inline-flex;align-items:center;gap:.3rem;padding:.22rem .6rem;border-radius:999px;font-size:.78rem;"
        "background:var(--jc-chip);border:1px solid var(--jc-chip-line);color:var(--jc-muted);white-space:nowrap}"
        f"{c} .jb-stat i,{c} .jb-vg,{c} .jb-member i,{c} .jb-state i{{font-style:normal}}"
        f"{c} .jb-stat i svg{{width:1em;height:1em;vertical-align:-.12em}}"
        f"{c} .jb-stat b{{color:var(--jc-ink);font-weight:800}}"
        f"{c} .jb-band,{c} .jb-form-wrap{{padding:.5rem .7rem;border-radius:14px;background:var(--jc-panel);border:1px solid var(--jc-line)}}"
        f"{c} .jb-h{{margin:0 0 .35rem;font-size:.7rem;font-weight:850;letter-spacing:.06em;text-transform:uppercase;color:var(--jc-muted)}}"
        f"{c} .jb-members{{display:flex;flex-wrap:wrap;gap:.35rem}}"
        f"{c} .jb-member{{display:inline-flex;align-items:center;gap:.3rem;padding:.22rem .6rem;border-radius:12px;font-size:.8rem;font-weight:800;"
        "background:var(--jc-chip);border:1px solid var(--jc-chip-line);color:var(--jc-ink)}"
        f"{c} .jb-member-off{{opacity:.55;border-style:dashed}}"
        f"{c} .jb-note{{margin:.35rem 0 0;font-size:.74rem;color:var(--jc-muted)}}"
        f"{c} .jb-form{{display:flex;gap:4px}}"
        f"{c} .jb-form-cell{{min-width:2.6rem;display:flex;flex-direction:column;padding:.28rem .45rem;border-radius:10px;"
        "background:color-mix(in srgb,var(--jc-tone) 16%,transparent);border-top:4px solid var(--jc-tone);color:var(--jc-ink)}"
        f"{c} .jb-form-cell b{{font-size:.78rem;line-height:1.2;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}"
        f"{c} .jb-form-cell small{{font-size:.66rem;color:var(--jc-muted);white-space:nowrap}}"
        f"{c} .jb-tone-0{{--jc-tone:var(--jc-t0)}}{c} .jb-tone-1{{--jc-tone:var(--jc-t1)}}"
        f"{c} .jb-tone-2{{--jc-tone:var(--jc-t2)}}{c} .jb-tone-3{{--jc-tone:var(--jc-t3)}}"
        f"{c} .jb-prog{{margin-top:.4rem}}"
        f"{c} .jb-prog summary{{cursor:pointer;font-size:.76rem;font-weight:800;color:var(--jc-muted)}}"
        f"{c} .jb-prog-row{{display:flex;gap:.5rem;align-items:baseline;margin-top:.35rem}}"
        f"{c} .jb-prog-name{{flex:0 0 auto;padding:.08rem .5rem;border-radius:999px;background:var(--jc-tone);color:#fff;font-size:.72rem;font-weight:850}}"
        f"{c} .jb-prog-chords{{display:flex;flex-wrap:wrap;gap:.25rem .55rem;font-weight:800;color:var(--jc-chord-ink)}}"
        f"{c} .jb-states{{display:flex;flex-wrap:wrap;gap:.3rem .7rem;margin-top:.1rem}}"
        f"{c} .jb-state{{display:inline-flex;align-items:center;gap:.3rem;font-size:.74rem;font-weight:700;color:var(--jc-muted)}}"
        # every block under the artwork keeps the card's side margin
        f"{c} .st-key-backing_card_controls,{c} .st-key-backing_art_actions{{padding-left:14px !important;padding-right:14px !important}}"
        # the controls: ordinary flow, no strip, no fixed height or negative margin
        f"{c} .st-key-backing_card_controls{{height:auto !important;min-height:0 !important;max-height:none !important;margin:0 !important;"
        "padding-top:.2rem !important;padding-bottom:0 !important;background:transparent !important;border:0 !important;overflow:visible !important;"
        "z-index:auto;gap:.6rem}"
        f"{c} .st-key-backing_card_controls [data-testid=\"stHorizontalBlock\"]{{height:auto !important;flex-direction:row;flex-wrap:nowrap}}"
        # the Songs strip's pale ground (app_ui) would sit under the card's own panels: on the night card that made
        # the Original Key a pale value on near-white (browser check 2026-11-26) -- the card's panels are the ground
        f"{k}{{background:transparent !important;border:0 !important}}"
        f"{k} [data-testid=\"stHorizontalBlock\"]{{gap:.7rem !important;align-items:stretch !important}}"
        f"{k} [data-testid=\"stHorizontalBlock\"]>[data-testid=\"stColumn\"],{k} [data-testid=\"stHorizontalBlock\"]>[data-testid=\"stColumn\"]:first-child"
        "{flex:1 1 0 !important;min-width:0 !important;padding:.6rem .8rem .65rem !important;border-radius:14px;"
        "background:var(--jc-panel);border:1px solid var(--jc-line) !important}"
        f"{k} .ui-skp-label,{k} .ui-skp-cap,{k} .ui-skp-cap-fixed{{color:var(--jc-muted) !important}}"
        f"{k} .ui-skp-value{{color:var(--jc-ink) !important}}"
        f"{k} .ui-skp-locked{{background:var(--jc-chip) !important;border-color:var(--jc-chip-line) !important;color:var(--jc-ink) !important}}"
        f"{c} .st-key-backing_art_play_row{{padding:.55rem .8rem;border-radius:14px;background:var(--jc-panel);border:1px solid var(--jc-line)}}"
        f"{c} .st-key-backing_art_play_row [data-testid=\"stHorizontalBlock\"]>[data-testid=\"stColumn\"]:last-child"
        "{flex:0 0 250px !important;width:250px !important;min-width:0 !important}"
        f"{c} .st-key-backing_art_play_row label p,{c} .st-key-backing_art_play_row [data-testid=\"stMarkdownContainer\"] p,"
        f"{c} .st-key-backing_art_play_row .ui-backing-inline-label{{color:var(--jc-ink) !important}}"
        f"{c} .st-key-backing_art_actions button{{border-radius:999px !important;background:var(--jc-chip) !important;"
        "border:1px solid var(--jc-chip-line) !important;color:var(--jc-ink) !important;font-weight:750 !important}"
        f"{c} .st-key-backing_art_actions button[kind=\"primary\"]{{background:var(--jc-accent) !important;color:var(--jc-accent-ink) !important}}"
        f"{c} .st-key-backing_art_actions button p{{color:inherit !important}}"
        # Phone (the card is narrower than 640 px). Original | Practice key stay side by side (each one short
        # panel); BPM above a full-width Play; the three card buttons wrap into short rows instead of three
        # full-width ones; smaller chips and art text.
        f"@container jamcard (max-width:640px){{"
        f"{c} .st-key-backing_art_play_row [data-testid=\"stHorizontalBlock\"]{{flex-direction:column !important;align-items:stretch !important}}"
        f"{c} .st-key-backing_art_play_row [data-testid=\"stHorizontalBlock\"]>[data-testid=\"stColumn\"]:last-child"
        "{width:100% !important;flex:1 1 auto !important}"
        f"{k} [data-testid=\"stHorizontalBlock\"]{{flex-direction:row !important;flex-wrap:nowrap !important;gap:.45rem !important}}"
        f"{k} [data-testid=\"stHorizontalBlock\"]>[data-testid=\"stColumn\"],{k} [data-testid=\"stHorizontalBlock\"]>[data-testid=\"stColumn\"]:first-child"
        "{padding:.45rem .55rem .5rem !important;width:auto !important;flex:1 1 0 !important;min-width:0 !important}"
        f"{c} .st-key-backing_art_actions [data-testid=\"stHorizontalBlock\"]{{flex-direction:row !important;flex-wrap:wrap !important;gap:.4rem !important}}"
        f"{c} .st-key-backing_art_actions [data-testid=\"stHorizontalBlock\"]>[data-testid=\"stColumn\"]"
        "{flex:1 1 9.5rem !important;width:auto !important;min-width:0 !important}"
        f"{c} .st-key-backing_art_actions button{{min-height:34px !important;padding:.2rem .6rem !important}}"
        f"{c} .st-key-backing_art_actions button p{{font-size:.8rem !important}}"
        f"{c} .jb-stat{{font-size:.72rem;padding:.18rem .5rem}}"
        f"{c} .jb-member{{font-size:.74rem;padding:.18rem .5rem}}"
        f"{c} .jb-band,{c} .jb-form-wrap{{padding:.4rem .55rem}}"
        # The artwork is the band: on a phone the name and the style / groove tiles sit in a strip under it, never
        # over an instrument (only the two pills stay on the art).
        f"{c} .jb-hero{{min-height:0}}"
        f"{c} .jb-art{{position:relative;inset:auto;height:176px}}"
        f"{c} .jb-scrim{{bottom:auto;height:176px;background:linear-gradient(180deg,var(--jc-hero-bg) 0%,transparent 34%)}}"
        f"{c} .jb-top{{position:absolute;top:0;left:0;right:0}}"
        f"{c} .jb-id{{position:relative;left:auto;right:auto;bottom:auto;padding:8px 12px 6px;flex-direction:row !important;"
        "align-items:center !important;gap:.6rem}"
        f"{c} .jb-title{{font-size:1.25rem}}"
        f"{c} .jb-sub{{font-size:.78rem}}"
        f"{c} .jb-logo{{min-width:2.9rem;padding:.25rem .3rem}}"
        f"{c} .jb-logo b{{font-size:1.15rem}}"
        f"{c} .jb-top{{padding:10px 12px 0}}"
        f"{c} .jb-form{{flex-wrap:wrap}}"
        f"{c} .jb-form-cell{{flex:1 1 4.5rem !important}}"
        f"{c} .st-key-backing_card_controls,{c} .st-key-backing_art_actions{{padding-left:10px !important;padding-right:10px !important}}"
        "}"
    )


@lru_cache(maxsize=1)
def backing_jam_css() -> str:
    """The jam cards' Backing look, scoped to their two containers: the Creative jam cards' colours, the album-cover
    layout of the song cards."""
    text = art.jam_cards_css()
    base = re.sub(r"^<style>|</style>$", "", text)
    base = base.replace(art.STYLE_JAM_CARD, BACKING_STYLE_JAM_CARD).replace(art.GENERATOR_CARD, BACKING_GENERATOR_CARD)
    out = [base]
    for key, theme in ((BACKING_STYLE_JAM_CARD, art._THEMES[art.STYLE_JAM_CARD]), (BACKING_GENERATOR_CARD, art._THEMES[art.GENERATOR_CARD])):
        t = theme["tones"].split(",")
        out.append(f".st-key-{key}{{--jc-t0:{t[0]};--jc-t1:{t[1]};--jc-t2:{t[2]};--jc-t3:{t[3]}}}")
        out.append(_card_rules(key))
    return "<style>" + re.sub(r"\s*\n\s*", " ", "".join(out)).strip() + "</style>"


# --- drawing it on Backing ----------------------------------------------------------------------------------------


def _facts_for(ctx: Any, session: Mapping[str, Any], *, state: Any, groove: str, meter: str, bpm: int) -> dict[str, Any]:
    from backing_musical_state import card_view

    shown = card_view(state)  # the saved Practice Key: Key Cycling only moves the sounding fields
    selected = None
    try:
        from backing_track_state import resolve_selected_section_names

        names = list((getattr(shown, "concert_sections", None) or {}).keys())
        selected = resolve_selected_section_names(session, names) if names else None
    except Exception:
        selected = None
    return jam_card_facts(ctx, state=shown, groove=groove, meter=meter, bpm=bpm, selected=selected)


def render_backing_jam_card(
    st: Any, ctx: Any, session: Mapping[str, Any], *, state: Any, groove: str, meter: str, bpm: int, facts_slot: Any = None,
) -> None:
    """The artwork where this is called; the facts in ``facts_slot`` (under the key row), or right after the artwork."""
    facts = _facts_for(ctx, session, state=state, groove=groove, meter=meter, bpm=bpm)
    owner = "jam_session_generator" if facts["generator"] else "style_jam"
    st.markdown(
        backing_jam_css()
        + f'<div class="jb-card" data-backing-card-owner="entry_jam" data-jam-owner="{owner}">{jam_card_head_html(facts)}</div>',
        unsafe_allow_html=True,
    )
    if facts_slot is None:
        st.markdown(jam_card_facts_html(facts), unsafe_allow_html=True)
        return
    with facts_slot:
        st.markdown(jam_card_facts_html(facts), unsafe_allow_html=True)


__all__ = (
    "BACKING_GENERATOR_CARD", "BACKING_STYLE_JAM_CARD", "backing_jam_css", "backing_state_html", "backing_state_items",
    "band_size_word", "chart_key_chip", "jam_card_facts", "jam_card_facts_html", "jam_card_head_html", "jam_card_html",
    "jam_card_key", "render_backing_jam_card",
)

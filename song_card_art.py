"""Artistic Songs and Backing cards: the approved genre artwork, frames and icons.

Presentation only. Every icon comes from the app's own definitions. Widgets such as the Practice Key
selector stay real Streamlit widgets and sit between the fragments this module returns.

Off by default until reviewed: set ``MUSIC_SONG_ART_CARDS=1`` to use it.
"""

from __future__ import annotations

import html
import os
import pathlib
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable

from music_feature_icons import FEATURE_ICONS, SEMANTIC_FIELD_ICONS, instrument_icon
from practice_studio import genre_visual_style
from practice_ui_labels import FOCUS_ICONS, LEVEL_ICONS, icon_for_focus

HERE = pathlib.Path(__file__).resolve().parent
ART_DIR = HERE / "static" / "song_art"
ART_URL = "app/static/song_art"
CHALLENGE_ICON = "\U0001F525"  # the session plan's challenge icon
CATALOG, CUSTOM, COMPOSITION = "catalog", "custom", "composition"
GENRES = ("pop", "rock", "jazz", "blues", "country", "soul", "funk", "jewish", "classical")
_SOURCE_NAME = {CATALOG: "Catalog", CUSTOM: "Custom", COMPOSITION: "Composition"}
_SOURCE_ICON = {CATALOG: "songs", CUSTOM: "custom", COMPOSITION: "composition"}
_STYLE_ART = {CUSTOM: ("blues", "pop"), COMPOSITION: ("blues", "classical")}

# The part of each artwork a narrow card shows, so the instrument stays in view.
_PHONE_VIEW = {
    "jewish": "780,0,620,640", "rock": "820,0,620,640", "soul": "800,0,720,640", "classical": "900,20,640,620",
    "jazz": "900,0,620,640", "pop": "900,0,620,640", "custom_blues": "800,120,720,520", "custom_pop": "880,40,620,600",
    "composition_blues": "740,60,690,580", "composition_classical": "740,40,700,600", "funk": "820,0,720,640",
    "blues": "800,60,720,580", "country": "940,0,660,640",
}
# A second line above the title, for songs that have one.
_FLOURISH = {"Shalom Aleichem": ("שלום עליכם", "he"), "Ode to Joy": ("from Symphony No. 9", "en")}

# Instruments reviewed against each song's best-known recordings. A song only says "Great on" once it is here.
REVIEWED_INSTRUMENTS: dict[str, tuple[str, ...]] = {
    "Blue Bossa": ("Sax", "Trumpet", "Piano", "Bass"),
    "I'm Yours": ("Guitar", "Voice", "Piano"),
    "Shalom Aleichem": ("Voice", "Clarinet", "Piano", "Guitar"),
    "Let It Be": ("Piano", "Voice", "Guitar", "Bass"),
    "Ode to Joy": ("Violin", "Flute", "Piano", "Voice"),
    "12-Bar Blues in F": ("Guitar", "Piano", "Sax", "Trumpet"),
    "Take Me Home, Country Roads": ("Guitar", "Voice", "Piano"),
    "Just the Two of Us": ("Sax", "Voice", "Keys", "Bass"),
    "Superstition": ("Keys", "Drums", "Trumpet", "Sax"),
}
# General lists that need correcting from the genre default. Voice is per song in Classical, not general.
_STYLE_INSTRUMENTS = {"Classical": ("Piano", "Violin", "Flute")}


def song_art_cards_enabled() -> bool:
    return str(os.environ.get("MUSIC_SONG_ART_CARDS") or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class CardIdentity:
    source: str  # catalog / custom / composition
    family: str  # the visual world: a genre, or custom / composition
    style_id: str  # the song's genre as an id, "" when unknown
    style_name: str
    style_logo: str
    art: str  # artwork file name

    @property
    def source_name(self) -> str:
        return _SOURCE_NAME[self.source]

    @property
    def source_logo(self) -> str:
        return FEATURE_ICONS[_SOURCE_ICON[self.source]]

    @property
    def crest(self) -> str:
        return self.style_logo if self.source == CATALOG else self.source_logo

    @property
    def crest_name(self) -> str:
        return self.style_name if self.source == CATALOG else self.source_name

    @property
    def classes(self) -> str:
        return f"g-{self.family} st-{self.style_id}"


def _source_id(source: str) -> str:
    s = str(source or "").lower()
    if "compos" in s:
        return COMPOSITION
    if "custom" in s or "progression" in s:
        return CUSTOM
    return CATALOG


def card_identity(source: str, style: str) -> CardIdentity:
    """The artistic identity: source says where the song came from, style says its artistic world."""
    src = _source_id(source)
    visual = genre_visual_style(str(style or "Pop"))
    name = str(visual.get("label") or style or "Pop")
    style_id = name.lower() if name.lower() in GENRES else ""
    logo = str(visual.get("emoji") or "")
    if src == CATALOG:
        family = art = style_id or "pop"
    else:
        family = src
        art = f"{src}_{style_id}" if style_id in _STYLE_ART[src] else src
    return CardIdentity(src, family, style_id, name, logo, art)


def _instrument_glyph(name: str) -> str:
    low = str(name).strip().lower()
    if low in {"keys", "keyboard", "keyboards"}:
        return instrument_icon("Piano")
    if low in {"drums", "drum kit", "percussion"}:
        return SEMANTIC_FIELD_ICONS["meter"]
    if low == "violin":
        return genre_visual_style("Classical")["emoji"]
    return instrument_icon(name)


def song_instruments(title: str, source: str, style: str, general: str = "") -> tuple[str, tuple[str, ...]]:
    """(heading, instruments). Only a reviewed Catalog song says "Great on"; the rest say "Common in <style>"."""
    if _source_id(source) == CATALOG and title in REVIEWED_INSTRUMENTS:
        return "Great on", REVIEWED_INSTRUMENTS[title]
    identity = card_identity(source, style)
    names = _STYLE_INSTRUMENTS.get(identity.style_name) or tuple(p.strip() for p in str(general or "").split(",") if p.strip())
    return f"Common in {identity.style_name}", names


_E = html.escape


def _art(name: str, view: str) -> str:
    return f"{ART_URL}/{name}.svg#svgView(viewBox({view});preserveAspectRatio(xMaxYMin slice))"


def hero_html(identity: CardIdentity, *, title: str, artist: str = "", page: str = "songs", status: str = "", bars: Iterable[str] = (), bars_note: str = "") -> str:
    view = "240,0,1360,640" if page.startswith("backing") else "0,0,1600,640"
    phone = _PHONE_VIEW.get(identity.art)
    source_tag = f'<source media="(max-width:560px)" srcset="{_E(_art(identity.art, phone))}">' if phone else ""
    alt = f"{identity.style_name} artwork for {title}"
    flourish = _FLOURISH.get(title) if identity.source == CATALOG else None
    flourish_html = f'<p class="sc-flourish" lang="{flourish[1]}">{_E(flourish[0])}</p>' if flourish else ""
    bar_list = [str(b) for b in bars if str(b or "").strip()][:4]
    prog = ""
    if bar_list:
        cells = "".join(f'<span class="sc-bar">{_E(b)}</span>' for b in bar_list)
        label = _E(f"{bars_note}: {', '.join(bar_list)}")
        prog = f'<div class="sc-prog" role="img" aria-label="{label}"><span class="sc-prog-note">{_E(bars_note)}</span><div class="sc-prog-bars">{cells}</div></div>'
    style_logo = ""
    if identity.source != CATALOG and identity.style_id:
        style_logo = f'<div class="sc-stylelogo"><b>{identity.style_logo}</b><small>{_E(identity.style_name)}</small></div>'
    status_html = f'<div class="sc-act"><span class="sc-pill">● {_E(status)}</span></div>' if status else ""
    return (
        f'<div class="sc-frag sc-frag-hero {identity.classes} p-{_E(page)}"><div class="sc-hero">'
        f'<picture>{source_tag}<img class="sc-heroart" src="{_E(_art(identity.art, view))}" alt="{_E(alt)}"></picture>'
        '<div class="sc-scrim"></div><div class="sc-top">'
        f'<div class="sc-chips"><span class="sc-src">{_E(identity.source_name)}</span></div>{status_html}</div>{prog}'
        f'<div class="sc-id"><div class="sc-crest"><div class="sc-logo"><b>{identity.crest}</b><small>{_E(identity.crest_name)}</small></div>{style_logo}</div>'
        f'<div class="sc-names">{flourish_html}<h3 class="sc-title">{_E(title)}</h3><p class="sc-artist">{_E(artist)}</p></div></div>'
        "</div></div>"
    )


def _stat(icon: str, label: str, value: str, logo: str = "") -> str:
    logo_html = f'<em class="vg">{logo}</em> ' if logo else ""
    return f'<span class="stat"><i>{icon}</i><span>{_E(label)}</span> <b>{logo_html}{_E(value)}</b></span>'


def _level_chips(levels: Iterable[str], active: str) -> str:
    out = []
    for lv in levels:
        cls = "lvl lvl-on" if lv == active else "lvl"
        out.append(f'<span class="{cls}"><em class="pg">{LEVEL_ICONS.get(lv, "")}</em> {_E(lv)}</span>')
    return "".join(out)


def _music_block(icon: str, heading: str, text: Any, small: str = "") -> str:
    if not str(text or "").strip():
        return ""
    small_html = f"<small>{_E(small)}</small>" if small else ""
    return f'<div class="mus"><h4><i>{icon}</i>{_E(heading)}</h4><p>{_E(str(text))}</p>{small_html}</div>'


def songs_body_html(
    identity: CardIdentity,
    *,
    title: str,
    bpm: Any,
    meter: str,
    level: str,
    instrument: str,
    focus: str,
    levels: Iterable[str],
    instruments_general: str,
    guide: dict[str, Any],
    shown_in: str = "",
) -> str:
    """Everything below the keys on the Songs card."""
    stats = "".join(
        (
            _stat(SEMANTIC_FIELD_ICONS["bpm"], "BPM", str(bpm)),
            _stat(SEMANTIC_FIELD_ICONS["meter"], "Meter", str(meter or "4/4")),
            _stat(SEMANTIC_FIELD_ICONS["style"], "Style", identity.style_name, identity.style_logo),
            _stat(SEMANTIC_FIELD_ICONS["source"], "Source", identity.source_name, identity.source_logo),
        )
    )
    pills = [(LEVEL_ICONS.get(level, ""), level), (instrument_icon(instrument) if instrument else "", instrument), (icon_for_focus(focus) if focus else "", focus)]
    pills_html = "".join(f'<span class="pill"><em class="pg">{g}</em> {_E(t)}</span>' for g, t in pills if str(t or "").strip())
    heading, names = song_instruments(title, identity.source, identity.style_name, instruments_general)
    medals = "".join(f'<span class="inst"><em class="im">{_instrument_glyph(n)}</em><small>{_E(n)}</small></span>' for n in names)
    focus_label = str(guide.get("focus_label") or focus or "General")
    music = "".join(
        (
            _music_block(FOCUS_ICONS["Harmony"], "Harmony", guide.get("harmony"), f"Shown in {shown_in}" if shown_in else ""),
            _music_block(FOCUS_ICONS["Melody"], "Melody", guide.get("melody")),
            _music_block(FEATURE_ICONS["practice_focus"], f"Your focus: {focus_label}", guide.get("focus")),
            _music_block(CHALLENGE_ICON, "Your challenge", guide.get("challenge")),
        )
    )
    return (
        f'<div class="sc-frag sc-frag-body {identity.classes} p-songs"><div class="sc-body">'
        f'<div class="stats">{stats}</div><div class="setup">'
        f'<div class="tile"><h4><i>{FEATURE_ICONS["practice_setup"]}</i>Your setup</h4><div class="pills">{pills_html}</div></div>'
        f'<div class="tile"><h4><i>{SEMANTIC_FIELD_ICONS["level"]}</i>Chart levels</h4><div class="lvls">{_level_chips(levels, level)}</div></div>'
        f'<div class="tile tile-on"><h4>{_E(heading)}</h4><div class="insts">{medals}</div></div></div>'
        f'<div class="music">{music}</div></div></div>'
    )


@lru_cache(maxsize=1)
def _base_css() -> str:
    return (HERE / "song_card_art.css").read_text(encoding="utf-8")


def _family_vars(family: str) -> str:
    """The custom properties of one family, for the Streamlit container that holds the card's fragments."""
    found = re.findall(r"\.g-" + re.escape(family) + r"\{([^}]*)\}", _base_css())
    decls: dict[str, str] = {}
    for block in found:
        for name, value in re.findall(r"(--[\w-]+)\s*:\s*([^;]+)", block):
            decls[name] = value.strip()
    return ";".join(f"{k}:{v}" for k, v in decls.items())


def card_style_tag(identity: CardIdentity, *, container_key: str = "picker_active_song_card_content") -> str:
    """The card's CSS, plus this card's colors, frame and lower artwork on the Streamlit container around it."""
    sel = f".st-key-{container_key}"
    body_art = f"{ART_URL}/{identity.art}.svg#svgView(viewBox(0,660,1600,1140);preserveAspectRatio(xMidYMin slice))"
    return (
        f"<style>{_base_css()}\n"
        f"{sel}{{{_family_vars(identity.family)}}}\n"
        f'{sel}{{position:relative;overflow:hidden;gap:0;border-radius:var(--radius,26px);border:var(--frame,5px solid var(--accent));background:#111 url("{body_art}") center top/100% 100% no-repeat;color:var(--ink)}}\n'
        "</style>"
    )


# --- Backing: the same album cover, with the real Practice Key, BPM and Play widgets in it. ----------------

BACKING_CONTAINER = "backing_art_card"


def backing_chips_html(identity: CardIdentity, *, groove: str, meter: str, written: str = "", written_label: str = "") -> str:
    """Style, Backing groove, Meter, Source (and the written key when charts differ), under the keys."""
    from practice_ui_labels import GROOVE_ICONS

    groove_name = str(groove or "Auto").strip() or "Auto"
    chips = [
        _stat(SEMANTIC_FIELD_ICONS["style"], "Style", identity.style_name, identity.style_logo),
        _stat(SEMANTIC_FIELD_ICONS["groove"], "Backing groove", groove_name, GROOVE_ICONS.get(groove_name, "")),
        _stat(SEMANTIC_FIELD_ICONS["meter"], "Meter", str(meter or "4/4")),
        _stat(SEMANTIC_FIELD_ICONS["source"], "Source", identity.source_name, identity.source_logo),
    ]
    if str(written or "").strip():
        chips.append(_stat(SEMANTIC_FIELD_ICONS["written_key"], str(written_label or "Charts in"), str(written)))
    return f'<div class="sc-frag sc-frag-chips {identity.classes} p-backing"><div class="stats bk-stats">{"".join(chips)}</div></div>'


def backing_key_label(which: str) -> str:
    """The two key panels' headings, with the app's own key icons."""
    if which == "original":
        return f'<p class="ui-skp-label bk-label"><i>{FEATURE_ICONS["original_key"]}</i>Original key</p>'
    return f'<p class="ui-skp-label bk-label"><i>{FEATURE_ICONS["practice_concert_key"]}</i>I&rsquo;m playing in</p>'


def play_theme(identity: CardIdentity) -> dict[str, str]:
    """The Play button's colors for this card, for the transport control's own frame."""
    found = dict(part.split(":", 1) for part in _family_vars(identity.family).split(";") if ":" in part)
    return {
        "bg": found.get("--play-bg") or found.get("--accent") or "",
        "ink": found.get("--play-ink") or found.get("--accent-ink") or "#fff",
        "accent": found.get("--accent") or "",
    }

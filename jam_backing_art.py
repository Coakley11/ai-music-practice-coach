"""The Backing card artwork of a generated jam, drawn for the jam being played.

The two jam artworks (``static/jam_art``) are this app's hand-drawn stages: Style Jam a daylight rehearsal stage with
its saxophone, Jam Session Generator a late-night club stage. Their instruments are drawn here one by one, so the
Backing card shows the band that plays: a trio three instruments, a quintet five, each the instrument the engine
renders (a member the backing cannot play yet stands in outline). The stage takes the jam's style (a tint and a
motif: palms for Latin / Bossa, a crescent for Jazz, lightning for Rock ...) and its energy (a mellow jam is lit
softly; an energetic or heavy one gets every spotlight and the sound in the air).

Presentation only: nothing here reads or writes session state.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Iterable, Sequence

STYLE_JAM = "style_jam"
GENERATOR = "jam_generator"

# --- the instruments, as drawn on the two stages ------------------------------------------------------------
# (markup in its own coordinates, bounding box x, y, width, height, natural scale on the stage).
# Colours: {ink} outlines and stands, {acc} accent, {lite} highlights / keys, {wood} wooden bodies, {body} a guitar's
# body, {skin} drum heads; brass is the stage's gradient (#jb-brass), cymbals #jb-cym.
_DRAWINGS: dict[str, tuple[str, tuple[float, float, float, float], float]] = {
    "keys": (
        '<line x1="16" y1="38" x2="4" y2="86" stroke="{ink}" stroke-width="6" stroke-linecap="round"/>'
        '<line x1="134" y1="38" x2="146" y2="86" stroke="{ink}" stroke-width="6" stroke-linecap="round"/>'
        '<rect x="0" y="12" width="150" height="30" rx="5" fill="{ink}" stroke="{acc}" stroke-width="1.5"/>'
        '<rect x="6" y="20" width="138" height="18" rx="2" fill="{lite}"/>'
        '<g fill="{ink}"><rect x="15" y="20" width="6" height="11"/><rect x="29" y="20" width="6" height="11"/>'
        '<rect x="50" y="20" width="6" height="11"/><rect x="64" y="20" width="6" height="11"/><rect x="78" y="20" width="6" height="11"/>'
        '<rect x="99" y="20" width="6" height="11"/><rect x="113" y="20" width="6" height="11"/><rect x="134" y="20" width="6" height="11"/></g>',
        (0, 12, 150, 76), 1.0,
    ),
    "drums": (
        '<line x1="-6" y1="40" x2="-6" y2="118" stroke="{ink}" stroke-width="4"/>'
        '<ellipse cx="-6" cy="38" rx="34" ry="6" fill="url(#jb-cym)"/>'
        '<line x1="132" y1="24" x2="132" y2="118" stroke="{ink}" stroke-width="4"/>'
        '<ellipse cx="132" cy="22" rx="40" ry="7" fill="url(#jb-cym)" transform="rotate(-8 132 22)"/>'
        '<circle cx="62" cy="88" r="44" fill="{ink}"/><circle cx="62" cy="88" r="35" fill="{skin}"/>'
        '<circle cx="62" cy="88" r="35" fill="none" stroke="{acc}" stroke-width="4"/>'
        '<text x="62" y="96" text-anchor="middle" font-family="system-ui, sans-serif" font-size="22" font-weight="800" fill="{acc}">&#9834;</text>'
        '<rect x="16" y="46" width="34" height="20" rx="6" fill="{acc}"/><rect x="74" y="44" width="34" height="20" rx="6" fill="{acc}"/>'
        '<ellipse cx="33" cy="46" rx="17" ry="4" fill="{lite}"/><ellipse cx="91" cy="44" rx="17" ry="4" fill="{lite}"/>'
        '<rect x="114" y="82" width="38" height="36" rx="6" fill="{ink}"/><ellipse cx="133" cy="82" rx="19" ry="5" fill="{lite}"/>',
        (-40, 15, 212, 117), 1.0,
    ),
    "upright_bass": (
        '<path d="M22 0 q8 -4 12 4 q-2 8 -8 8" fill="none" stroke="#7c2d12" stroke-width="5" stroke-linecap="round"/>'
        '<rect x="22" y="8" width="8" height="110" rx="3" fill="#431407"/>'
        '<path d="M26 112 c-34 0 -44 22 -34 44 c6 12 -8 20 -6 36 c4 26 26 38 40 38 c14 0 36 -12 40 -38 c2 -16 -12 -24 -6 -36 c10 -22 0 -44 -34 -44 z" fill="#b45309"/>'
        '<path d="M26 112 c-34 0 -44 22 -34 44 c6 12 -8 20 -6 36 c4 26 26 38 40 38" fill="none" stroke="#7c2d12" stroke-width="3"/>'
        '<path d="M12 160 q4 6 0 12 M40 160 q-4 6 0 12" fill="none" stroke="#431407" stroke-width="3"/>'
        '<rect x="18" y="196" width="16" height="6" rx="2" fill="#431407"/>'
        '<g stroke="#fef3c7" stroke-width="1.2"><line x1="24" y1="10" x2="23" y2="198"/><line x1="28" y1="10" x2="29" y2="198"/></g>'
        '<line x1="26" y1="228" x2="26" y2="240" stroke="{ink}" stroke-width="3"/>',
        (-14, -4, 84, 244), 0.8,
    ),
    "bass_guitar": (
        '<line x1="4" y1="226" x2="16" y2="190" stroke="{ink}" stroke-width="3"/><line x1="44" y1="226" x2="32" y2="190" stroke="{ink}" stroke-width="3"/>'
        '<path d="M19 0 h12 l2 22 h-16 z" fill="{ink}"/>'
        '<g fill="{lite}"><circle cx="16" cy="5" r="2.4"/><circle cx="16" cy="14" r="2.4"/><circle cx="34" cy="5" r="2.4"/><circle cx="34" cy="14" r="2.4"/></g>'
        '<rect x="21.5" y="20" width="7" height="118" rx="1.5" fill="#78350f"/>'
        '<g stroke="#fde68a" stroke-width="1" opacity=".7">'
        + "".join(f'<line x1="21.5" y1="{y}" x2="28.5" y2="{y}"/>' for y in (34, 48, 61, 73, 84, 94, 103, 111, 118))
        + '</g>'
        '<path d="M25 128 c-8 0 -10 -10 -18 -8 c-9 2 -8 16 -5 24 c3 10 -9 15 -7 31 c2 18 16 30 30 30 c14 0 28 -12 30 -30 c2 -16 -10 -21 -7 -31 c3 -8 4 -22 -5 -24 c-8 -2 -10 8 -18 8 z" fill="{lite}" stroke="{acc}" stroke-width="2"/>'
        '<path d="M33 142 c9 5 12 20 6 30 c-5 8 -14 7 -18 2 z" fill="{body}" opacity=".35"/>'
        '<rect x="16" y="158" width="18" height="5" rx="2" fill="{ink}"/><rect x="17" y="180" width="16" height="4" rx="1.5" fill="#94a3b8"/>'
        '<g stroke="#94a3b8" stroke-width=".7"><line x1="23" y1="20" x2="22.5" y2="182"/><line x1="24.6" y1="20" x2="24.4" y2="182"/>'
        '<line x1="26.2" y1="20" x2="26.4" y2="182"/><line x1="27.8" y1="20" x2="28.2" y2="182"/></g>',
        (-4, 0, 58, 226), 0.8,
    ),
    "electric_guitar": (
        '<line x1="8" y1="186" x2="18" y2="154" stroke="{ink}" stroke-width="3"/><line x1="48" y1="186" x2="38" y2="154" stroke="{ink}" stroke-width="3"/>'
        '<path d="M22 0 h12 l2 18 h-16 z" fill="{ink}"/>'
        '<g fill="{lite}"><circle cx="19" cy="4" r="2"/><circle cx="19" cy="10" r="2"/><circle cx="19" cy="16" r="2"/>'
        '<circle cx="37" cy="4" r="2"/><circle cx="37" cy="10" r="2"/><circle cx="37" cy="16" r="2"/></g>'
        '<rect x="25" y="16" width="6" height="88" rx="1.5" fill="#78350f"/>'
        '<g stroke="#fde68a" stroke-width="1" opacity=".7">'
        + "".join(f'<line x1="25" y1="{y}" x2="31" y2="{y}"/>' for y in (28, 39, 49, 58, 66, 74, 81, 88, 94))
        + '</g>'
        '<path d="M28 98 c-8 0 -11 -12 -19 -10 c-8 2 -7 15 -4 23 c3 10 -10 14 -8 30 c2 18 17 29 31 29 c14 0 29 -11 31 -29 c2 -16 -11 -20 -8 -30 c3 -8 4 -21 -4 -23 c-8 -2 -11 10 -19 10 z" fill="{body}" stroke="{lite}" stroke-width="2"/>'
        '<path d="M36 110 c10 4 14 19 8 31 c-6 10 -17 8 -21 2 z" fill="{lite}" opacity=".85"/>'
        '<rect x="19" y="118" width="18" height="4" rx="1.5" fill="{ink}"/><rect x="19" y="132" width="18" height="4" rx="1.5" fill="{ink}"/>'
        '<rect x="20" y="148" width="16" height="3" rx="1" fill="#cbd5e1"/>'
        '<g fill="{lite}"><circle cx="44" cy="152" r="2.5"/><circle cx="48" cy="160" r="2.5"/></g>'
        '<g stroke="#e5e7eb" stroke-width=".6"><line x1="26.2" y1="16" x2="25" y2="150"/><line x1="27.4" y1="16" x2="26.8" y2="150"/>'
        '<line x1="28.6" y1="16" x2="28.6" y2="150"/><line x1="29.8" y1="16" x2="30.4" y2="150"/></g>',
        (-3, 0, 64, 186), 0.85,
    ),
    "amp": (
        '<rect width="60" height="52" rx="5" fill="{ink}" stroke="{acc}" stroke-width="2"/>'
        '<rect x="6" y="6" width="48" height="8" rx="2" fill="{acc}" opacity=".55"/>'
        '<circle cx="30" cy="33" r="14" fill="{skin}" stroke="{acc}" stroke-width="2"/><circle cx="30" cy="33" r="5" fill="{ink}"/>',
        (0, 0, 60, 52), 1.0,
    ),
    "sax": (
        '<line x1="44" y1="128" x2="44" y2="150" stroke="{ink}" stroke-width="3"/><line x1="44" y1="150" x2="26" y2="152" stroke="{ink}" stroke-width="3"/>'
        '<line x1="44" y1="150" x2="62" y2="152" stroke="{ink}" stroke-width="3"/>'
        '<path d="M6 0 l14 -6 l4 8 l-10 6 z" fill="{ink}"/>'
        '<path d="M18 4 c8 16 6 44 2 70 c-4 26 -2 48 18 56 c18 6 32 -6 34 -22 l-6 -12 c0 14 -10 22 -20 18 c-12 -6 -10 -24 -6 -42 c4 -22 6 -50 -6 -70 z" fill="url(#jb-brass)" stroke="#b45309" stroke-width="2"/>'
        '<ellipse cx="68" cy="94" rx="11" ry="6" fill="#92400e" transform="rotate(-30 68 94)"/>'
        '<g fill="#fef3c7"><circle cx="24" cy="40" r="3"/><circle cx="23" cy="54" r="3"/><circle cx="22" cy="68" r="3"/><circle cx="24" cy="96" r="3"/></g>',
        (6, -6, 72, 158), 0.95,
    ),
    "trumpet": (
        '<line x1="56" y1="58" x2="56" y2="122" stroke="{ink}" stroke-width="3"/><line x1="56" y1="122" x2="38" y2="124" stroke="{ink}" stroke-width="3"/>'
        '<line x1="56" y1="122" x2="74" y2="124" stroke="{ink}" stroke-width="3"/>'
        '<rect x="20" y="44" width="40" height="16" rx="8" fill="none" stroke="#f59e0b" stroke-width="5"/>'
        '<path d="M10 40 H74" stroke="#f59e0b" stroke-width="7" stroke-linecap="round"/>'
        '<path d="M72 33 L106 16 V64 L72 47 Z" fill="url(#jb-brass)" stroke="#b45309" stroke-width="2"/>'
        '<g fill="{lite}" stroke="#b45309" stroke-width="1"><rect x="30" y="24" width="5" height="16" rx="1.5"/>'
        '<rect x="39" y="24" width="5" height="16" rx="1.5"/><rect x="48" y="24" width="5" height="16" rx="1.5"/></g>'
        '<rect x="2" y="36" width="10" height="8" rx="3" fill="{ink}"/>',
        (2, 16, 104, 108), 0.95,
    ),
    "trombone": (
        '<line x1="70" y1="66" x2="70" y2="128" stroke="{ink}" stroke-width="3"/><line x1="70" y1="128" x2="52" y2="130" stroke="{ink}" stroke-width="3"/>'
        '<line x1="70" y1="128" x2="88" y2="130" stroke="{ink}" stroke-width="3"/>'
        '<rect x="2" y="52" width="104" height="14" rx="7" fill="none" stroke="#f59e0b" stroke-width="4"/>'
        '<path d="M100 30 H46 q-9 0 -9 9 V52" fill="none" stroke="#f59e0b" stroke-width="5"/>'
        '<path d="M98 22 L138 6 V58 L98 40 Z" fill="url(#jb-brass)" stroke="#b45309" stroke-width="2"/>'
        '<rect x="30" y="24" width="10" height="8" rx="3" fill="{ink}"/>',
        (0, 6, 140, 126), 0.9,
    ),
    "congas": (
        '<path d="M10 22 Q2 64 14 112 H50 Q62 64 54 22 Z" fill="{wood}" stroke="{ink}" stroke-width="2"/>'
        '<ellipse cx="32" cy="22" rx="22" ry="6" fill="{skin}" stroke="{ink}" stroke-width="2"/>'
        '<path d="M52 40 Q46 78 56 112 H88 Q98 78 92 40 Z" fill="{wood}" stroke="{ink}" stroke-width="2" opacity=".92"/>'
        '<ellipse cx="72" cy="40" rx="20" ry="5.5" fill="{skin}" stroke="{ink}" stroke-width="2"/>'
        '<g stroke="{lite}" stroke-width="2" opacity=".7"><line x1="8" y1="60" x2="56" y2="60"/><line x1="50" y1="76" x2="94" y2="76"/></g>',
        (2, 16, 96, 96), 1.0,
    ),
    "mic": (
        '<line x1="10" y1="22" x2="10" y2="114" stroke="{ink}" stroke-width="3"/>'
        '<line x1="10" y1="114" x2="-8" y2="116" stroke="{ink}" stroke-width="3"/><line x1="10" y1="114" x2="28" y2="116" stroke="{ink}" stroke-width="3"/>'
        '<rect x="3" y="0" width="14" height="24" rx="7" fill="{lite}"/>'
        '<g stroke="{acc}" stroke-width="1"><line x1="4" y1="6" x2="16" y2="6"/><line x1="4" y1="11" x2="16" y2="11"/><line x1="4" y1="16" x2="16" y2="16"/></g>',
        (-8, 0, 36, 116), 1.0,
    ),
}

# The band's names (backing_performance_plan roles, jam_card_art line-up names) -> a drawing.
_INSTRUMENT_FOR_NAME = (
    ("upright", "upright_bass"),
    ("bass", "bass_guitar"),
    ("drum", "drums"),
    ("percussion", "congas"),
    ("conga", "congas"),
    ("trombone", "trombone"),
    ("trumpet", "trumpet"),
    ("sax", "sax"),
    ("horn", "sax"),
    ("guitar", "electric_guitar"),
    ("piano", "keys"),
    ("keys", "keys"),
    ("voice", "mic"),
    ("vocal", "mic"),
)

# Where each instrument stands, left to right (the drums at the back of the middle, the bass at the end).
_STAGE_ORDER = ("keys", "electric_guitar", "trumpet", "trombone", "sax", "drums", "congas", "bass_guitar", "upright_bass", "mic")


def instrument_drawing(name: str) -> str:
    """The drawing for a band member's name ("Upright bass", "Tenor sax", "Piano (for the guitar)" ...), "" if none."""
    low = str(name or "").strip().lower()
    if not low:
        return ""
    if low.startswith("piano"):
        return "keys"
    for token, drawing in _INSTRUMENT_FOR_NAME:
        if token in low:
            return drawing
    return ""


# --- the stage: per card, its colours; per style, a tint and a motif; per energy, the light --------------------

_PALETTE = {
    STYLE_JAM: {"ink": "#0c4a6e", "acc": "#0284c7", "lite": "#ffffff", "wood": "#b45309", "body": "#0ea5e9", "skin": "#e0f2fe"},
    GENERATOR: {"ink": "#0f172a", "acc": "#60a5fa", "lite": "#e2e8f0", "wood": "#92400e", "body": "#2563eb", "skin": "#1e293b"},
}

# A style family per jam style: its tint and the motif painted at the left of the stage.
_STYLE_FAMILY = (
    ("bossa", "latin"), ("samba", "latin"), ("latin", "latin"),
    ("jazz", "jazz"), ("swing", "jazz"), ("modal", "jazz"),
    ("blues", "blues"), ("rock", "rock"), ("funk", "funk"), ("fusion", "funk"), ("disco", "funk"),
    ("soul", "soul"), ("r&b", "soul"), ("lo-fi", "lofi"), ("lofi", "lofi"), ("lo fi", "lofi"),
    ("ballad", "lofi"), ("pop", "pop"), ("jewish", "jewish"), ("klezmer", "jewish"), ("hora", "jewish"),
)
_TINT = {
    "latin": "#f97316", "jazz": "#6d28d9", "blues": "#b45309", "rock": "#dc2626", "funk": "#eab308",
    "soul": "#a21caf", "lofi": "#0d9488", "pop": "#db2777", "jewish": "#2563eb", "": "#0ea5e9",
}


def style_family(style: str, groove: str = "") -> str:
    """The visual family of a jam: its style first ("Latin"), then its groove ("Bossa nova"); "" when neither names one."""
    for raw in (style, groove):
        low = str(raw or "").strip().lower()
        for token, family in _STYLE_FAMILY:
            if token in low:
                return family
    return ""


_CALM_MOODS = frozenset({"mellow", "relaxed", "dreamy", "dark"})
_DRIVING_MOODS = frozenset({"energetic", "gritty", "bright"})


def energy_level(mood: str = "", intensity: str = "") -> int:
    """0 calm, 1 steady, 2 intense: the groove's intensity (Light / Medium / Heavy), moved one step by the mood."""
    level = {"light": 0, "medium": 1, "heavy": 2}.get(str(intensity or "").strip().lower(), 1)
    mood_low = str(mood or "").strip().lower()
    if mood_low in _CALM_MOODS:
        level -= 1
    elif mood_low in _DRIVING_MOODS:
        level += 1
    return max(0, min(2, level))


def _motif(family: str, card: str) -> str:
    """The style's mark on the open left of the stage (behind the card's words, so it stays quiet)."""
    ink = "#0c4a6e" if card == STYLE_JAM else "#bfdbfe"
    if family == "latin":
        leaf = "M0 0 q40 -24 86 -6 q-44 -2 -86 6 z"
        fronds = "".join(f'<path d="{leaf}" transform="rotate({a})"/>' for a in (-150, -120, -80, -40, -10, 20))
        return (f'<g opacity=".22" fill="#15803d"><path d="M70 300 q12 -100 -4 -190" stroke="#78350f" stroke-width="8" fill="none"/>'
                f'<g transform="translate(66 112)">{fronds}</g>'
                f'<path d="M230 300 q-8 -70 10 -130" stroke="#78350f" stroke-width="6" fill="none"/><g transform="translate(240 172) scale(.7)">{fronds}</g></g>')
    if family == "jazz":
        return (f'<g opacity=".28" fill="{ink}"><path d="M210 40 a34 34 0 1 0 30 52 a28 28 0 1 1 -30 -52 z"/>'
                '<rect x="20" y="190" width="40" height="110"/><rect x="66" y="160" width="34" height="140"/><rect x="106" y="205" width="46" height="95"/>'
                '<rect x="158" y="176" width="30" height="124"/><rect x="194" y="214" width="44" height="86"/></g>')
    if family == "rock":
        bolt = "M0 0 l24 0 l-12 34 l20 0 l-40 56 l12 -40 l-18 0 z"
        return (f'<g opacity=".3" fill="#f59e0b"><path d="{bolt}" transform="translate(60 60) scale(1.3)"/>'
                f'<path d="{bolt}" transform="translate(230 120) scale(.9)"/></g>')
    if family == "funk":
        tiles = "".join(f'<rect x="{x}" y="{y}" width="9" height="9" rx="1"/>' for x in range(122, 196, 12) for y in range(52, 126, 12)
                        if (x - 158) ** 2 + (y - 88) ** 2 < 40 ** 2)
        return (f'<g opacity=".34"><line x1="160" y1="0" x2="160" y2="48" stroke="{ink}" stroke-width="2"/>'
                f'<circle cx="160" cy="90" r="42" fill="#fde68a"/><g fill="#ffffff">{tiles}</g></g>')
    if family == "blues":
        return (f'<g opacity=".3"><circle cx="170" cy="80" r="40" fill="#fde68a"/>'
                f'<path d="M0 300 V230 q80 -30 160 0 t160 0 V300 z" fill="{ink}"/></g>')
    if family == "soul":
        return (f'<g opacity=".3"><circle cx="160" cy="130" r="64" fill="{ink}"/><circle cx="160" cy="130" r="46" fill="none" stroke="#f0abfc" stroke-width="2"/>'
                '<circle cx="160" cy="130" r="30" fill="none" stroke="#f0abfc" stroke-width="2"/><circle cx="160" cy="130" r="14" fill="#f0abfc"/></g>')
    if family == "lofi":
        return (f'<g opacity=".3" fill="none" stroke="{ink}" stroke-width="4"><rect x="80" y="50" width="150" height="120" rx="6"/>'
                '<line x1="155" y1="50" x2="155" y2="170"/><line x1="80" y1="110" x2="230" y2="110"/>'
                '<path d="M120 300 v-60 q-30 -20 -10 -40 M120 240 q30 -24 20 -44" stroke-width="5"/></g>')
    if family == "pop":
        star = "M0 -14 L4 -4 L14 -4 L6 3 L9 14 L0 7 L-9 14 L-6 3 L-14 -4 L-4 -4 Z"
        return "".join(f'<path d="{star}" fill="#f9a8d4" opacity=".4" transform="translate({x} {y}) scale({s})"/>'
                       for x, y, s in ((70, 70, 1.4), (190, 50, 1), (140, 140, .8), (260, 100, 1.1)))
    if family == "jewish":
        return f'<g opacity=".22" fill="none" stroke="{ink}" stroke-width="5"><path d="M160 50 l46 80 h-92 z"/><path d="M160 156 l46 -80 h-92 z"/></g>'
    return ""


def _backdrop(card: str, family: str, energy: int, mood: str) -> str:
    tint = _TINT.get(family, _TINT[""])
    mood_low = str(mood or "").strip().lower()
    if card == STYLE_JAM:
        bokeh = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" opacity="{o}"/>' for x, y, r, o in
                        ((120, 60, 34, .35), (300, 34, 18, .4), (470, 78, 26, .28), (610, 40, 14, .5), (900, 56, 30, .32),
                         (380, 140, 12, .3), (720, 30, 20, .3))[: 4 + energy * 2])
        parts = [
            '<rect width="960" height="300" fill="url(#jb-sky)"/>',
            f'<rect width="960" height="300" fill="{tint}" opacity="{.05 + .04 * energy:.2f}"/>',
            '<rect width="960" height="300" fill="url(#jb-glow)"/>',
            f'<g fill="#ffffff">{bokeh}</g>',
            # the flowing staff of the Style Jam artwork; on an intense jam it moves faster (steeper waves).
            '<g fill="none" stroke="#0369a1" stroke-opacity=".22" stroke-width="2">'
            + "".join(f'<path d="M0 {118 + 12 * i} C160 {88 + 12 * i - 18 * energy} 320 {148 + 12 * i + 18 * energy} 480 {118 + 12 * i} '
                      f'S800 {88 + 12 * i - 18 * energy} 960 {118 + 12 * i}"/>' for i in range(5))
            + "</g>",
            _motif(family, card),
            '<ellipse cx="700" cy="300" rx="360" ry="62" fill="url(#jb-floor)"/>',
            '<ellipse cx="700" cy="292" rx="330" ry="44" fill="#e0f2fe" opacity=".35"/>',
        ]
    else:
        beams = ((526, 640, 430, "url(#jb-beam)"), (666, 790, 570, "url(#jb-gold)"), (806, 940, 700, "url(#jb-beam)"))
        shown = {0: (beams[1],), 1: (beams[0], beams[2]), 2: beams}[energy]
        stars = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" opacity=".7"/>' for x, y, r in
                        ((60, 40, 1.6), (150, 80, 1.2), (240, 30, 1.8), (330, 66, 1.2), (420, 24, 1.5), (96, 128, 1.1), (300, 118, 1.4), (520, 58, 1.3)))
        parts = [
            '<rect width="960" height="300" fill="url(#jb-night)"/>',
            f'<rect width="960" height="300" fill="{tint}" opacity="{.14 + .07 * energy:.2f}"/>',
            f'<g fill="#dbeafe">{stars}</g>',
            _motif(family, card),
            '<rect x="400" y="8" width="560" height="8" fill="#1e293b"/>',
            '<g fill="#334155"><rect x="520" y="14" width="22" height="16" rx="3"/><rect x="660" y="14" width="22" height="16" rx="3"/>'
            '<rect x="800" y="14" width="22" height="16" rx="3"/></g>',
            "".join(f'<polygon points="{x},28 {x + 10},28 {r},300 {l},300" fill="{f}" opacity="{.7 + .15 * energy:.2f}"/>' for x, r, l, f in shown),
            '<rect x="380" y="252" width="580" height="48" fill="url(#jb-floor)"/>',
            f'<rect x="380" y="250" width="580" height="4" fill="#60a5fa" opacity="{.45 + .2 * energy:.2f}"/>',
        ]
    if mood_low == "dark":
        parts.append('<rect width="960" height="300" fill="#020617" opacity=".22"/>')
    elif mood_low == "dreamy":
        parts.append('<rect width="960" height="300" fill="#c4b5fd" opacity=".16"/>')
    elif mood_low == "gritty":
        parts.append('<rect width="960" height="300" fill="#7c2d12" opacity=".14"/>')
    return "".join(parts)


def _defs(card: str) -> str:
    common = (
        '<filter id="jb-mute" color-interpolation-filters="sRGB"><feColorMatrix type="saturate" values="0"/></filter>'
        '<linearGradient id="jb-brass" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fde68a"/><stop offset="1" stop-color="#d97706"/></linearGradient>'
        '<linearGradient id="jb-cym" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fcd34d"/><stop offset="1" stop-color="#b45309"/></linearGradient>'
    )
    if card == STYLE_JAM:
        return common + (
            '<linearGradient id="jb-sky" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f0f9ff"/><stop offset=".55" stop-color="#bae6fd"/>'
            '<stop offset="1" stop-color="#7dd3fc"/></linearGradient>'
            '<linearGradient id="jb-floor" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#38bdf8" stop-opacity=".55"/>'
            '<stop offset="1" stop-color="#0284c7" stop-opacity=".75"/></linearGradient>'
            '<radialGradient id="jb-glow" cx=".72" cy=".35" r=".6"><stop offset="0" stop-color="#ffffff" stop-opacity=".85"/>'
            '<stop offset="1" stop-color="#ffffff" stop-opacity="0"/></radialGradient>'
        )
    return common + (
        '<linearGradient id="jb-night" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0b1330"/><stop offset=".6" stop-color="#132a5e"/>'
        '<stop offset="1" stop-color="#1e3a8a"/></linearGradient>'
        '<linearGradient id="jb-beam" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#bfdbfe" stop-opacity=".55"/>'
        '<stop offset="1" stop-color="#bfdbfe" stop-opacity="0"/></linearGradient>'
        '<linearGradient id="jb-gold" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fde68a" stop-opacity=".5"/>'
        '<stop offset="1" stop-color="#fde68a" stop-opacity="0"/></linearGradient>'
        '<linearGradient id="jb-floor" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1d4ed8" stop-opacity=".65"/>'
        '<stop offset="1" stop-color="#0b1330" stop-opacity="1"/></linearGradient>'
    )


_STAGE_LEFT, _STAGE_RIGHT, _FLOOR = 420.0, 950.0, 254.0

# The Generator's identity on its own stage: two dice resting at the front edge, left of the band.
_DICE = (
    '<g class="jb-dice" transform="translate(352 240)">'
    '<g transform="rotate(-12)"><rect x="-17" y="-17" width="34" height="34" rx="7" fill="#f8fafc" stroke="#93c5fd" stroke-width="2"/>'
    '<g fill="#1e3a8a"><circle cx="-8" cy="-8" r="3.2"/><circle cx="0" cy="0" r="3.2"/><circle cx="8" cy="8" r="3.2"/></g></g>'
    '<g transform="translate(30 6) rotate(14)"><rect x="-14" y="-14" width="28" height="28" rx="6" fill="#dbeafe" stroke="#93c5fd" stroke-width="2"/>'
    '<g fill="#1e3a8a"><circle cx="-6" cy="-6" r="2.7"/><circle cx="6" cy="-6" r="2.7"/><circle cx="-6" cy="6" r="2.7"/><circle cx="6" cy="6" r="2.7"/></g></g>'
    "</g>"
)
_MAX_HEIGHT = 206.0


def _place(drawing: str, cx: float, slot: float, palette: dict[str, str], *, ghost: bool) -> str:
    markup, (x0, y0, w, h), natural = _DRAWINGS[drawing]
    scale = min(natural, slot * 1.3 / w, _MAX_HEIGHT / h)
    tx = cx - (x0 + w / 2) * scale
    ty = _FLOOR - (y0 + h) * scale
    body = markup.format(**palette)
    if not ghost:
        return f'<g transform="translate({tx:.1f} {ty:.1f}) scale({scale:.3f})" data-instrument="{drawing}">{body}</g>'
    # A member the backing cannot play (its sound switched off, or none yet): grey, faded and tagged, so it never
    # reads as playing (user, 2026-11-26).
    top = max(14.0, ty + y0 * scale - 10)
    tag = (f'<g class="jb-off-tag" transform="translate({cx:.1f} {top:.1f})">'
           '<rect x="-50" y="-13" width="108" height="22" rx="11" fill="#0f172a" fill-opacity=".78" stroke="#e2e8f0" stroke-opacity=".55"/>'
           '<path d="M-42 -5 h5 l6 -5 v14 l-6 -5 h-5 z" fill="#e2e8f0"/>'
           '<path d="M-27 -6 l7 8 M-20 -6 l-7 8" stroke="#fca5a5" stroke-width="2" stroke-linecap="round"/>'
           '<text x="-14" y="3" text-anchor="start" font-family="system-ui, sans-serif" font-size="11" font-weight="800" '
           'fill="#f8fafc" letter-spacing=".06em">SOUND OFF</text></g>')
    return (f'<g transform="translate({tx:.1f} {ty:.1f}) scale({scale:.3f})" opacity=".38" filter="url(#jb-mute)" '
            f'stroke-dasharray="6 5" class="jb-ghost" data-instrument="{drawing}">{body}</g>{tag}')


def _sound(energy: int, card: str, centers: Sequence[float]) -> str:
    """Sound in the air over the band: none on a calm jam, a few arcs on a steady one, more on an intense one."""
    if not energy or not centers:
        return ""
    colour = "#0284c7" if card == STYLE_JAM else "#bfdbfe"
    arcs = []
    for cx in centers[:: 2 if energy == 1 else 1]:
        for i in range(energy + 1):
            r = 16 + 12 * i
            arcs.append(f'<path d="M{cx - r:.0f} {70 - i * 6} q{r} -{r * 0.8:.0f} {2 * r} 0" />')
    return f'<g fill="none" stroke="{colour}" stroke-width="3" stroke-linecap="round" opacity="{.25 + .12 * energy:.2f}">{"".join(arcs)}</g>'


def stage_members(names: Iterable[str]) -> list[str]:
    """Drawings for a band, in stage order, each member once per mention (two horns, two drawings)."""
    drawings = [d for d in (instrument_drawing(n) for n in names) if d]
    return sorted(drawings, key=lambda d: (_STAGE_ORDER.index(d) if d in _STAGE_ORDER else len(_STAGE_ORDER)))


def jam_stage_svg(
    card: str,
    *,
    playing: Sequence[str] = (),
    not_yet: Sequence[str] = (),
    style: str = "",
    groove: str = "",
    mood: str = "",
    intensity: str = "",
    featured: str = "",
    label: str = "",
) -> str:
    """The card's artwork, one line of inline SVG.

    ``playing`` / ``not_yet``: the band by name (as the Backing engine plays it, and members it cannot play yet, drawn in
    outline). ``featured``: an instrument drawn at the front (Style Jam's own saxophone). Empty band: the card's own
    instruments."""
    card = GENERATOR if card == GENERATOR else STYLE_JAM
    return _stage_svg(card, tuple(playing), tuple(not_yet), str(style or ""), str(groove or ""), str(mood or ""), str(intensity or ""),
                      str(featured or ""), str(label or ""))


@lru_cache(maxsize=64)
def _stage_svg(card: str, playing: tuple[str, ...], not_yet: tuple[str, ...], style: str, groove: str, mood: str, intensity: str,
               featured: str, label: str) -> str:
    palette = _PALETTE[card]
    family = style_family(style, groove)
    energy = energy_level(mood, intensity)
    band = [(d, False) for d in stage_members(playing)] + [(d, True) for d in stage_members(not_yet)]
    if not band:
        band = [(d, False) for d in (("keys", "drums", "upright_bass") if card == STYLE_JAM else ("electric_guitar", "keys", "drums", "bass_guitar"))]
    band.sort(key=lambda item: _STAGE_ORDER.index(item[0]) if item[0] in _STAGE_ORDER else len(_STAGE_ORDER))
    feature = instrument_drawing(featured) if featured else ""
    if feature and any(d == feature and not ghost for d, ghost in band):
        feature = ""  # the band already has it
    slots = len(band) + (1 if feature else 0)
    width = (_STAGE_RIGHT - _STAGE_LEFT) / max(1, slots)
    parts, centers = [], []
    order = list(band)
    if feature:
        # The featured instrument at the front of the band, just left of centre.
        order.insert(max(0, len(order) // 2), (feature, False))
    for i, (drawing, ghost) in enumerate(order):
        cx = _STAGE_LEFT + width * (i + 0.5)
        if not ghost:
            centers.append(cx)  # the sound rises only over instruments that play
        parts.append(_place(drawing, cx, width, palette, ghost=ghost))
    if card == GENERATOR:
        parts.append(_DICE)
    if family == "rock" and "electric_guitar" in {d for d, _ in order} and slots < 5:
        parts.insert(0, _place("amp", _STAGE_LEFT - 10, 70, palette, ghost=False))
    aria = label or "A stage with the band"
    body = _backdrop(card, family, energy, mood) + _sound(energy, card, centers) + "".join(parts)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 300" preserveAspectRatio="xMaxYMid slice" role="img" '
        f'aria-label="{_attr(aria)}" class="jb-stage jb-e{energy} jb-f-{family or "plain"}"><defs>{_defs(card)}</defs>{body}</svg>'
    )
    return re.sub(r"\s*\n\s*", " ", svg)


def _attr(text: str) -> str:
    return str(text).replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


__all__ = (
    "GENERATOR", "STYLE_JAM", "energy_level", "instrument_drawing", "jam_stage_svg", "stage_members", "style_family",
)

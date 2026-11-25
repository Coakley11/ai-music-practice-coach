"""Creative › Entry & Jam: the Style Jam and Jam Session Generator cards (artwork, layout, read-only facts).

Presentation only. Every control on these cards stays the same Streamlit widget with the same key,
callback, options and default; this module draws the artwork, the group headings and the read-only
"what was generated" panels around them, from each tool's OWN generated data (Style Jam:
``improv_generated_sections``; the Generator: ``improv_jam_session``), never from the active song.

Each card is a keyed ``st.container`` and all of its CSS is scoped to that container's
``.st-key-…`` class, so no other page changes. The cards set their own surface and ink colours
(light blue for Style Jam, dark blue for the Generator), so they read the same in Streamlit's light
and dark themes.
"""

from __future__ import annotations

import html
import pathlib
import re
from functools import lru_cache
from typing import Any, Callable, Iterable, Mapping

HERE = pathlib.Path(__file__).resolve().parent
ART_DIR = HERE / "static" / "jam_art"

# st.container keys (the page's CSS hooks: ``.st-key-<key>``).
STYLE_JAM_CARD = "jam_card_style_jam"
STYLE_JAM_ACTIONS = "jam_card_style_actions"
STYLE_JAM_RESULT = "jam_card_style_result"
STYLE_JAM_SECTION_PREFIX = "jam_card_style_sec_"
GENERATOR_CARD = "jam_card_generator"
GENERATOR_BAND = "jam_card_gen_band"
GENERATOR_ACTIONS = "jam_card_gen_actions"
GENERATOR_RESULT = "jam_card_gen_result"
GENERATOR_SECTION_PREFIX = "jam_card_gen_sec_"

ART_NAMES = ("style_jam", "jam_generator")
SECTION_TONES = 4  # section badges cycle through this many colours

_E = html.escape

# Band roles the Backing engine renders, as a musician reads them.
_ROLE_LABELS: dict[str, tuple[str, str]] = {
    "keys": ("\U0001F3B9", "Keys"),
    "bass": ("\U0001F3B8", "Bass"),
    "drums": ("\U0001F941", "Drums"),
    "guitar": ("\U0001F3B8", "Guitar"),
    "horns": ("\U0001F3B7", "Horn"),
    "percussion": ("\U0001FA98", "Percussion"),
}
# Where an ensemble's own wording is more exact than the role ("Jazz trio": piano, upright bass, drums).
_ROLE_NAMES_BY_ENSEMBLE: dict[str, dict[str, str]] = {
    "Jazz trio": {"keys": "Piano", "bass": "Upright bass"},
    "Jazz quartet": {"keys": "Piano", "bass": "Upright bass", "horns": "Sax / trumpet"},
    "Rock trio": {"guitar": "Electric guitar"},
    "Latin quartet": {"keys": "Piano", "percussion": "Congas / timbales"},
}


@lru_cache(maxsize=len(ART_NAMES))
def artwork_svg(name: str) -> str:
    """One card's artwork as a single line of inline SVG (comments dropped).

    Inline, so it needs no static route and no cache-busting; one line, because a blank line or an
    indented line would end Streamlit's HTML block and print the rest as Markdown."""
    if name not in ART_NAMES:
        raise ValueError(f"unknown jam artwork: {name!r}")
    text = (ART_DIR / f"{name}.svg").read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return re.sub(r"\s*\n\s*", " ", text).strip()


def ensemble_lineup(ensemble: str) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]]:
    """(playing, not_yet): the ensemble's real roster from the Backing engine, as (icon, name) pairs.

    ``not_yet`` are members the engine cannot render yet (shown as such, never as playing)."""
    name = str(ensemble or "").strip()
    try:
        from backing_performance_plan import ENSEMBLES
    except Exception:
        return (), ()
    spec = ENSEMBLES.get(name)
    if spec is None:
        return (), ()
    overrides = _ROLE_NAMES_BY_ENSEMBLE.get(name, {})

    def _pairs(roles: Iterable[str]) -> tuple[tuple[str, str], ...]:
        out = []
        for role in roles:
            icon, label = _ROLE_LABELS.get(role, ("\U0001F3B5", role.title()))
            label = overrides.get(role, label)
            out.append(("\U0001F3BB" if label == "Upright bass" else icon, label))
        return tuple(out)

    return _pairs(spec.roles), _pairs(spec.missing)


def arrangement_form(sections: Mapping[str, Iterable[str]] | None) -> list[tuple[str, list[str]]]:
    """The generated sections in order, each with its non-empty chords."""
    out: list[tuple[str, list[str]]] = []
    for name, chords in (sections or {}).items():
        chs = [str(c).strip() for c in (chords or []) if str(c or "").strip()]
        out.append((str(name), chs))
    return out


def _form_line(form: list[tuple[str, list[str]]]) -> str:
    return " → ".join(name for name, _ in form)


def _count(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def style_jam_summary(
    sections: Mapping[str, Iterable[str]] | None,
    *,
    style: str,
    key_label: str,
    mood: str,
    difficulty: str,
    groove: str,
    bpm: Any,
) -> dict[str, str]:
    """What the Style Jam generated, in words: a title and one descriptive line."""
    form = arrangement_form(sections)
    chords = sum(len(c) for _, c in form)
    style_name = str(style or "Style jam").strip() or "Style jam"
    feel = ", ".join(x for x in (str(mood or "").strip().lower(), str(difficulty or "").strip().lower()) if x)
    line = f"A {feel} {style_name} progression" if feel else f"A {style_name} progression"
    try:
        line += f" at {int(bpm)} BPM"
    except (TypeError, ValueError):
        pass
    if str(groove or "").strip():
        line += f" with a {str(groove).strip().lower()} groove"
    line += f" — {_count(len(form), 'section')}, {_count(chords, 'chord')}"
    if form:
        line += f": {_form_line(form)}."
    else:
        line += "."
    return {"title": f"{style_name} in {key_label}".strip(), "line": line}


def generator_summary(jam: Mapping[str, Any] | None, *, key_label: Callable[[str], str] = str) -> dict[str, str]:
    """What the Jam Session Generator generated, from the jam's own record only."""
    jam = jam or {}
    form = arrangement_form(jam.get("sections"))
    chords = sum(len(c) for _, c in form)
    ensemble = str(jam.get("ensemble") or "").strip()
    style = str(jam.get("style") or "").strip()
    key = str(jam.get("key") or "").strip()
    parts = [p for p in (ensemble, f"in {key_label(key)}" if key else "", style) if p]
    line = " · ".join(parts)
    try:
        line += f" · ~{int(jam.get('bpm'))} BPM"
    except (TypeError, ValueError):
        pass
    atmosphere = str(jam.get("atmosphere") or "").strip()
    if atmosphere:
        line += f" · {atmosphere}"
    line += f" — {_count(len(form), 'section')}, {_count(chords, 'chord')}."
    return {"title": str(jam.get("title") or "Jam session"), "line": line}


# --- HTML fragments ---------------------------------------------------------------------------------


def _chips(items: Iterable[tuple[str, str]], cls: str = "jc-chip") -> str:
    return "".join(
        f'<span class="{cls}"><span class="jc-chip-k">{_E(k)}</span> {_E(v)}</span>' for k, v in items if str(v or "").strip()
    )


def hero_html(
    art: str,
    *,
    kicker: str,
    title: str,
    line: str,
    chips: Iterable[tuple[str, str]] = (),
) -> str:
    """The card's artwork banner: kicker, title, one line, and the current settings as chips."""
    chip_html = _chips(chips)
    chips_block = f'<div class="jc-hero-chips">{chip_html}</div>' if chip_html else ""
    return (
        f'<div class="jc-hero jc-hero-{_E(art)}">'
        f'<div class="jc-hero-art" aria-hidden="true">{artwork_svg(art)}</div>'
        f'<div class="jc-hero-copy"><p class="jc-kicker">{_E(kicker)}</p>'
        f'<h3 class="jc-title">{_E(title)}</h3><p class="jc-line">{_E(line)}</p>{chips_block}</div>'
        "</div>"
    )


def group_label_html(icon: str, text: str) -> str:
    """A small heading over a group of controls (Sound, Feel, Groove …)."""
    return f'<p class="jc-group"><span class="jc-group-i">{_E(icon)}</span>{_E(text)}</p>'


def step_html(number: int, text: str) -> str:
    return f'<p class="jc-step"><span class="jc-step-n">{int(number)}</span>{_E(text)}</p>'


def lineup_html(ensemble: str) -> str:
    """The band that will play: who plays now, and members the backing cannot play yet."""
    playing, later = ensemble_lineup(ensemble)
    if not playing:
        return f'<div class="jc-lineup"><p class="jc-lineup-h">Your band</p><p class="jc-lineup-name">{_E(ensemble)}</p></div>'
    members = "".join(f'<span class="jc-member"><i>{_E(i)}</i>{_E(n)}</span>' for i, n in playing)
    later_html = ""
    if later:
        names = ", ".join(n for _, n in later)
        later_html = f'<p class="jc-lineup-later">Not in the backing yet: {_E(names)}</p>'
    return (
        f'<div class="jc-lineup"><p class="jc-lineup-h">Your band · {_E(ensemble)}</p>'
        f'<div class="jc-members">{members}</div>{later_html}</div>'
    )


def result_head_html(*, kicker: str, title: str, line: str, sections: Mapping[str, Iterable[str]] | None) -> str:
    """The generated arrangement's heading, description and song-structure strip."""
    form = arrangement_form(sections)
    cells = "".join(
        f'<span class="jc-form-cell jc-tone-{i % SECTION_TONES}" style="flex:{max(1, len(chs))} 1 0">'
        f"<b>{_E(name)}</b><small>{_E(_count(len(chs), 'chord'))}</small></span>"
        for i, (name, chs) in enumerate(form)
    )
    strip = (
        f'<div class="jc-form" role="img" aria-label="{_E("Song structure: " + _form_line(form))}">{cells}</div>'
        if form
        else ""
    )
    return (
        f'<div class="jc-result-head"><p class="jc-kicker">{_E(kicker)}</p>'
        f'<h4 class="jc-result-title">{_E(title)}</h4><p class="jc-result-line">{_E(line)}</p>{strip}</div>'
    )


def section_head_html(name: str, chords: Iterable[str], index: int) -> str:
    """One generated section: its name, bar/chord count, and its chords as chips (exactly as generated)."""
    chs = [str(c).strip() for c in (chords or []) if str(c or "").strip()]
    chips = "".join(f'<span class="jc-chord">{_E(c)}</span>' for c in chs)
    return (
        f'<div class="jc-sec-head jc-tone-{int(index) % SECTION_TONES}">'
        f'<span class="jc-sec-badge">{_E(name)}</span>'
        f'<span class="jc-sec-count">{_E(_count(len(chs), "chord"))}</span></div>'
        f'<div class="jc-chords" aria-label="{_E(name)} chords">{chips}</div>'
    )


# --- CSS ---------------------------------------------------------------------------------------------

# Per card: surface, ink, muted ink, accent, line, panel; section tones a..d.
_THEMES: dict[str, dict[str, str]] = {
    STYLE_JAM_CARD: {
        "surface": "linear-gradient(180deg,#f0f9ff 0%,#e0f2fe 100%)",
        "ink": "#0c3553",
        "muted": "#2f5f80",
        "accent": "#0284c7",
        "accent_ink": "#ffffff",
        "line": "rgba(2,132,199,.30)",
        "panel": "rgba(255,255,255,.82)",
        "chip": "rgba(255,255,255,.78)",
        "chip_line": "rgba(2,132,199,.35)",
        "chord_bg": "#ffffff",
        "chord_ink": "#075985",
        "shadow": "0 10px 28px rgba(14,116,144,.14)",
        "hero_bg": "#eef8fe",
        "button": "linear-gradient(135deg,#0ea5e9,#0369a1)",
        "tones": "#0284c7,#0d9488,#4f46e5,#c2410c",
    },
    GENERATOR_CARD: {
        "surface": "linear-gradient(180deg,#0e1a3d 0%,#13244f 100%)",
        "ink": "#e8f0ff",
        "muted": "#b4c6ea",
        "accent": "#60a5fa",
        "accent_ink": "#0b1330",
        "line": "rgba(147,197,253,.30)",
        "panel": "rgba(255,255,255,.06)",
        "chip": "rgba(15,23,42,.55)",
        "chip_line": "rgba(147,197,253,.40)",
        "chord_bg": "rgba(191,219,254,.12)",
        "chord_ink": "#dbeafe",
        "shadow": "0 14px 34px rgba(11,19,48,.38)",
        "hero_bg": "#0c1534",
        "button": "linear-gradient(135deg,#3b82f6,#1d4ed8)",
        "tones": "#60a5fa,#34d399,#a78bfa,#fbbf24",
    },
}

PHONE_MAX_WIDTH_PX = 640


def _card_css(key: str, t: Mapping[str, str]) -> str:
    c = f".st-key-{key}"
    bc = f".block-container {c}"
    tones = t["tones"].split(",")
    tone_rules = "".join(f"{c} .jc-tone-{i}{{--jc-tone:{tone}}}" for i, tone in enumerate(tones))
    return f"""
{c}{{--jc-ink:{t['ink']};--jc-muted:{t['muted']};--jc-accent:{t['accent']};--jc-accent-ink:{t['accent_ink']};
 --jc-line:{t['line']};--jc-panel:{t['panel']};--jc-chip:{t['chip']};--jc-chip-line:{t['chip_line']};
 --jc-chord-bg:{t['chord_bg']};--jc-chord-ink:{t['chord_ink']};--jc-tone:{t['accent']};--jc-hero-bg:{t['hero_bg']};
 background:{t['surface']};color:var(--jc-ink);border:1px solid var(--jc-line);border-radius:22px;
 padding:12px 14px 16px;box-shadow:{t['shadow']};gap:.55rem;}}
{tone_rules}
{bc} label[data-testid="stWidgetLabel"] p,{bc} .stSelectbox label p,{bc} .stSlider label p,{bc} .stTextInput label p{{color:var(--jc-ink) !important;font-weight:750}}
{c} :where([data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p){{color:var(--jc-muted) !important}}
{c} :where([data-testid="stMarkdownContainer"] p){{color:var(--jc-ink)}}
{c} .ui-creative-progression-preview{{color:var(--jc-muted) !important;margin:.3rem 0 0 !important}}
{c} .ui-creative-progression-preview strong{{color:var(--jc-ink)}}
{c} [data-testid="stSliderThumbValue"],{c} [data-testid="stSliderTickBarMin"],{c} [data-testid="stSliderTickBarMax"]{{color:var(--jc-ink) !important}}
{c} hr{{border-color:var(--jc-line) !important;margin:.6rem 0 !important}}
{c} .st-key-improv_gen_style button,{c} .st-key-improv_gen_jam button,{c} .st-key-improv_to_backing_jam button{{
 background:{t['button']} !important;border:1px solid var(--jc-accent) !important;color:#fff !important;font-weight:800 !important;
 border-radius:999px !important;min-height:2.75rem !important;box-shadow:0 6px 16px rgba(2,32,71,.22) !important}}
{c} .st-key-improv_gen_style button *,{c} .st-key-improv_gen_jam button *,{c} .st-key-improv_to_backing_jam button *{{color:#fff !important}}
"""


def _shared_css() -> str:
    cards = ",".join(f".st-key-{k}" for k in _THEMES)

    def each(rule: str) -> str:
        return ",".join(f".st-key-{k} {rule}" for k in _THEMES)

    secs = ",".join(f'[class*="st-key-{p}"]' for p in (STYLE_JAM_SECTION_PREFIX, GENERATOR_SECTION_PREFIX))
    results = ",".join(f".st-key-{k}" for k in (STYLE_JAM_RESULT, GENERATOR_RESULT))
    bands = f".st-key-{GENERATOR_BAND}"
    return f"""
{each('.jc-hero')}{{position:relative;overflow:hidden;border-radius:16px;min-height:210px;display:flex;align-items:center;
 background:var(--jc-hero-bg);border:1px solid var(--jc-line)}}
{each('.jc-hero-art')}{{position:absolute;top:0;right:0;height:100%;aspect-ratio:16/5}}
{each('.jc-hero-art svg')}{{width:100%;height:100%;display:block}}
{each('.jc-hero-art::after')}{{content:"";position:absolute;top:0;bottom:0;left:0;width:40%;background:linear-gradient(90deg,var(--jc-hero-bg),transparent)}}
{each('.jc-hero-copy')}{{position:relative;z-index:1;padding:16px 20px;max-width:48%}}
{each('.jc-kicker')}{{margin:0 0 .15rem;font-size:.68rem;font-weight:850;letter-spacing:.09em;text-transform:uppercase;color:var(--jc-accent)}}
{each('.jc-title')}{{margin:0 0 .25rem;padding:0;font-size:1.55rem;line-height:1.15;font-weight:850;color:var(--jc-ink)}}
{each('.jc-line')}{{margin:0 0 .5rem;font-size:.9rem;line-height:1.4;color:var(--jc-muted)}}
{each('.jc-hero-chips')}{{display:flex;flex-wrap:wrap;gap:.3rem .35rem}}
{each('.jc-chip')}{{display:inline-flex;align-items:center;gap:.2rem;padding:.14rem .55rem;border-radius:999px;font-size:.74rem;font-weight:750;
 background:var(--jc-chip);border:1px solid var(--jc-chip-line);color:var(--jc-ink);white-space:nowrap}}
{each('.jc-chip-k')}{{font-weight:600;color:var(--jc-muted)}}
{each('.jc-group')}{{margin:.1rem 0 .1rem;font-size:.7rem;font-weight:850;letter-spacing:.07em;text-transform:uppercase;color:var(--jc-accent)}}
{each('.jc-group-i')}{{margin-right:.3rem}}
{each('.jc-step')}{{display:flex;align-items:center;gap:.45rem;margin:.35rem 0 0;font-size:.82rem;font-weight:850;color:var(--jc-ink)}}
{each('.jc-step-n')}{{display:inline-grid;place-items:center;width:1.45rem;height:1.45rem;border-radius:999px;background:var(--jc-accent);color:var(--jc-accent-ink);font-size:.75rem}}
{each('.jc-lineup')}{{padding:.55rem .7rem;border-radius:14px;background:var(--jc-panel);border:1px solid var(--jc-line)}}
{each('.jc-lineup-h')}{{margin:0 0 .35rem;font-size:.72rem;font-weight:850;letter-spacing:.06em;text-transform:uppercase;color:var(--jc-muted)}}
{each('.jc-lineup-name')}{{margin:0;font-weight:800;color:var(--jc-ink)}}
{each('.jc-members')}{{display:flex;flex-wrap:wrap;gap:.35rem}}
{each('.jc-member')}{{display:inline-flex;align-items:center;gap:.3rem;padding:.25rem .65rem;border-radius:12px;font-size:.82rem;font-weight:800;
 background:var(--jc-chip);border:1px solid var(--jc-chip-line);color:var(--jc-ink)}}
{each('.jc-member i')}{{font-style:normal}}
{each('.jc-lineup-later')}{{margin:.35rem 0 0;font-size:.74rem;color:var(--jc-muted)}}
{results}{{padding:.75rem .8rem .5rem;border-radius:18px;background:var(--jc-panel);border:1px solid var(--jc-line);gap:.5rem}}
{each('.jc-result-title')}{{margin:0 0 .2rem;padding:0;font-size:1.2rem;font-weight:850;color:var(--jc-ink)}}
{each('.jc-result-line')}{{margin:0 0 .55rem;font-size:.86rem;line-height:1.45;color:var(--jc-muted)}}
{each('.jc-form')}{{display:flex;gap:4px;margin:0 0 .2rem}}
{each('.jc-form-cell')}{{min-width:2.6rem;display:flex;flex-direction:column;padding:.3rem .45rem;border-radius:10px;
 background:color-mix(in srgb,var(--jc-tone) 16%,transparent);border-top:4px solid var(--jc-tone);color:var(--jc-ink)}}
{each('.jc-form-cell b')}{{font-size:.8rem;line-height:1.2;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
{each('.jc-form-cell small')}{{font-size:.68rem;color:var(--jc-muted);white-space:nowrap}}
{secs}{{padding:.55rem .7rem .5rem;border-radius:14px;background:var(--jc-panel);border:1px solid var(--jc-line);gap:.15rem}}
{each('.jc-sec-head')}{{display:flex;align-items:center;gap:.5rem;margin:0 0 .4rem}}
{each('.jc-sec-badge')}{{padding:.12rem .6rem;border-radius:999px;background:var(--jc-tone);color:#fff;font-weight:850;font-size:.8rem;
 text-shadow:0 1px 1px rgba(0,0,0,.25)}}
{each('.jc-sec-count')}{{font-size:.74rem;font-weight:700;color:var(--jc-muted)}}
{each('.jc-chords')}{{display:flex;flex-wrap:wrap;gap:.35rem}}
{each('.jc-chord')}{{min-width:3rem;text-align:center;padding:.32rem .6rem;border-radius:10px;font-weight:850;font-size:.95rem;
 background:var(--jc-chord-bg);color:var(--jc-chord-ink);border:1px solid var(--jc-chip-line);border-left:4px solid var(--jc-tone)}}
{bands}{{gap:.35rem}}
{each('.st-key-improv_gen_style button')}{{width:100% !important}}
{each('.st-key-improv_gen_jam button')}{{min-width:16rem !important}}
@media (max-width:{PHONE_MAX_WIDTH_PX}px){{
 {cards}{{padding:10px 10px 12px;border-radius:18px}}
 {each('.jc-hero')}{{display:block;min-height:0}}
 {each('.jc-hero-art')}{{position:relative;width:100%;height:132px;aspect-ratio:auto}}
 {each('.jc-hero-art::after')}{{width:18%}}
 {each('.jc-hero-copy')}{{max-width:100%;padding:10px 12px 12px}}
 {each('.jc-title')}{{font-size:1.25rem}}
 {each('.jc-line')}{{font-size:.82rem}}
 {each('.jc-form')}{{flex-wrap:wrap}}
 {each('.jc-form-cell')}{{flex:1 1 4.5rem !important}}
 {each('.jc-chord')}{{min-width:2.7rem;font-size:.9rem;padding:.3rem .5rem}}
 {results}{{padding:.6rem .6rem .4rem}}
 {each('.st-key-improv_gen_jam button')}{{width:100% !important;min-width:0 !important}}
}}
"""


@lru_cache(maxsize=1)
def jam_cards_css() -> str:
    """Both cards' CSS (scoped to their containers), as one <style> tag."""
    # Cards first: the shared rules (including the phone media block) come later and win ties.
    body = "".join(_card_css(k, t) for k, t in _THEMES.items()) + _shared_css()
    # One line: see artwork_svg (a blank line would end Streamlit's HTML block).
    return "<style>" + re.sub(r"\s*\n\s*", " ", body).strip() + "</style>"


__all__ = (
    "GENERATOR_ACTIONS",
    "GENERATOR_BAND",
    "GENERATOR_CARD",
    "GENERATOR_RESULT",
    "GENERATOR_SECTION_PREFIX",
    "STYLE_JAM_ACTIONS",
    "STYLE_JAM_CARD",
    "STYLE_JAM_RESULT",
    "STYLE_JAM_SECTION_PREFIX",
    "arrangement_form",
    "artwork_svg",
    "ensemble_lineup",
    "generator_summary",
    "group_label_html",
    "hero_html",
    "jam_cards_css",
    "lineup_html",
    "result_head_html",
    "section_head_html",
    "step_html",
    "style_jam_summary",
)

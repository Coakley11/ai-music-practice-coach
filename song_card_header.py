"""Song card header: source identity + style treatment (Songs / Backing redesign, v12).

One header for the active-song cards. The source sets the base (Catalog blue, Custom
green with a yellow rule, Composition black with gold); the song's style adds a glow,
a fine texture and a line-art motif (Jazz saxophone, Blues guitar, Soul vinyl, ...).
Style names come from the app's existing genre definitions (``genre_visual_style``),
so a style the app already knows always gets a header, and an unknown one falls back
to a neutral treatment.

The HTML is presentation only: no widgets, no state. Layout adapts to the card's own
width with container queries (phone below 560 px, tablet below 820 px).
"""
from __future__ import annotations

import html
from typing import Iterable

SOURCE_CATALOG = "catalog"
SOURCE_CUSTOM = "custom"
SOURCE_COMPOSITION = "composition"

_SOURCE_BASE = {
    SOURCE_CATALOG: "linear-gradient(135deg, #0f172a 0%, #1e3a8a 45%, #1e40af 75%, #172554 100%)",
    SOURCE_CUSTOM: "linear-gradient(135deg, #064e3b 0%, #047857 45%, #059669 75%, #065f46 100%)",
    SOURCE_COMPOSITION: "linear-gradient(135deg, #020617 0%, #0f172a 50%, #1e293b 100%)",
}
# label, chip ink, chip ring
_SOURCE_CHIP = {
    SOURCE_CATALOG: ("Catalog", "#bfdbfe", "rgba(191,219,254,0.5)"),
    SOURCE_CUSTOM: ("Custom progression", "#fef08a", "rgba(253,224,71,0.85)"),
    SOURCE_COMPOSITION: ("Composition", "#e9c46a", "rgba(233,196,106,0.6)"),
}

# Tile icons (24x24 strokes)
_ICON = {
    "notes": "M9 18V5l12-2v13M6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM18 19a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    "vinyl": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    "bars": "M4 20V10M9 20V4M14 20v-7M19 20V8",
    "wave": "M3 17c3-4 6-4 9 0s6 4 9 0M12 3v8M9 6h6",
    "guitar": "M14 4l6 6M17 7l-8 8M5 15a3 3 0 1 0 4 4l2-2-4-4z",
    "mic": "M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zM19 11a7 7 0 0 1-14 0M12 18v3",
    "quill": "M20 4C14 6 9 11 6 18l-2 3M20 4c-2 5-6 9-12 12",
}

# Style treatment, keyed by genre_visual_style()["label"]: glow, second glow, art colour, art, tile icon
_STYLE = {
    "Jazz": ("rgba(124,58,237,0.55)", "rgba(251,191,36,0.16)", "#fcd34d", "sax", "notes"),
    "Soul": ("rgba(147,51,234,0.6)", "rgba(190,24,93,0.35)", "#e9d5ff", "vinyl", "vinyl"),
    "Funk": ("rgba(202,138,4,0.55)", "rgba(154,52,18,0.4)", "#fdba74", "bars", "bars"),
    "Country": ("rgba(101,163,13,0.55)", "rgba(161,98,7,0.35)", "#d9f99d", "guitar", "wave"),
    "Blues": ("rgba(180,83,9,0.6)", "rgba(28,25,23,0.4)", "#fde68a", "guitar", "guitar"),
    "Pop": ("rgba(236,72,153,0.5)", "rgba(99,102,241,0.4)", "#fbcfe8", "mic", "mic"),
    "Rock": ("rgba(220,38,38,0.5)", "rgba(30,41,59,0.5)", "#fecaca", "guitar", "guitar"),
    "Bossa": ("rgba(13,148,136,0.5)", "rgba(250,204,21,0.18)", "#99f6e4", "guitar", "wave"),
    "Latin": ("rgba(234,88,12,0.5)", "rgba(185,28,28,0.35)", "#fed7aa", "bars", "bars"),
    "Classical": ("rgba(148,163,184,0.35)", "rgba(15,23,42,0.5)", "#e2e8f0", "staff", "notes"),
    "Jewish": ("rgba(99,102,241,0.45)", "rgba(202,138,4,0.3)", "#fde68a", "vinyl", "notes"),
}
_NEUTRAL = ("rgba(148,163,184,0.35)", "rgba(15,23,42,0.4)", "#e2e8f0", "vinyl", "notes")

_ART = {
    "sax": (
        '<svg viewBox="0 0 200 200" fill="none" stroke="{c}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M58 20 L84 30"/><path d="M84 30 C96 36 100 48 100 62 L104 140 C106 176 132 188 150 174 C162 164 163 148 159 136"/>'
        '<path d="M150 130 L178 116 L186 136 L160 142 Z"/>'
        '<circle cx="101" cy="80" r="5"/><circle cx="102" cy="99" r="5"/><circle cx="103" cy="118" r="5"/><circle cx="116" cy="158" r="4"/>'
        '<path d="M36 150 V112 L56 106 V144"/><circle cx="30" cy="152" r="7"/><circle cx="50" cy="146" r="7"/></svg>'
    ),
    "guitar": (
        '<svg viewBox="-20 -30 240 240" fill="none" stroke="{c}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">'
        '<g transform="rotate(-32 100 100)">'
        '<path d="M100 52 C78 52 70 70 74 86 C77 98 62 104 60 124 C58 154 78 178 100 178 C122 178 142 154 140 124 C138 104 123 98 126 86 C130 70 122 52 100 52 Z"/>'
        '<circle cx="100" cy="114" r="13"/><path d="M94 54 V-4 H106 V54"/><rect x="90" y="-26" width="20" height="22" rx="4"/>'
        '<path d="M86 152 H114"/><path d="M97 -10 V152" stroke-width="1.5"/><path d="M100 -10 V152" stroke-width="1.5"/>'
        '<path d="M103 -10 V152" stroke-width="1.5"/></g></svg>'
    ),
    "vinyl": (
        '<svg viewBox="0 0 200 200" fill="none" stroke="{c}" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="100" cy="108" r="80" stroke-width="4"/><circle cx="100" cy="108" r="64" stroke-width="1.5"/>'
        '<circle cx="100" cy="108" r="50" stroke-width="1.5"/><circle cx="100" cy="108" r="36" stroke-width="1.5"/>'
        '<circle cx="100" cy="108" r="18" stroke-width="4"/><circle cx="100" cy="108" r="3" stroke-width="3"/>'
        '<path d="M184 14 L164 64 L128 92" stroke-width="4"/><circle cx="184" cy="14" r="6" stroke-width="3"/></svg>'
    ),
    "bars": (
        '<svg viewBox="0 0 200 200" fill="{c}" stroke="none">'
        '<rect x="14" y="120" width="13" height="60" rx="6.5"/><rect x="36" y="70" width="13" height="110" rx="6.5"/>'
        '<rect x="58" y="140" width="13" height="40" rx="6.5"/><rect x="80" y="40" width="13" height="140" rx="6.5"/>'
        '<rect x="102" y="100" width="13" height="80" rx="6.5"/><rect x="124" y="60" width="13" height="120" rx="6.5"/>'
        '<rect x="146" y="130" width="13" height="50" rx="6.5"/><rect x="168" y="80" width="13" height="100" rx="6.5"/>'
        '<circle cx="42" cy="50" r="5"/><circle cx="86" cy="22" r="5"/><circle cx="130" cy="40" r="5"/><circle cx="174" cy="60" r="5"/></svg>'
    ),
    "mic": (
        '<svg viewBox="0 0 200 200" fill="none" stroke="{c}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="78" y="20" width="44" height="78" rx="22"/><path d="M80 44 H120" stroke-width="1.5"/>'
        '<path d="M80 58 H120" stroke-width="1.5"/><path d="M80 72 H120" stroke-width="1.5"/>'
        '<path d="M62 78 C62 104 80 120 100 120 C120 120 138 104 138 78"/><path d="M100 120 V164"/><path d="M74 166 H126"/>'
        '<circle cx="160" cy="40" r="4"/><circle cx="40" cy="62" r="3"/><circle cx="168" cy="120" r="3"/></svg>'
    ),
    "quill": (
        '<svg viewBox="0 0 200 200" fill="none" stroke="{c}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M176 14 C150 58 118 98 68 130 C94 90 128 50 176 14 Z"/><path d="M176 14 C122 30 84 74 64 130 L50 178"/>'
        '<path d="M152 38 L132 46" stroke-width="2"/><path d="M136 60 L114 70" stroke-width="2"/>'
        '<path d="M118 82 L96 94" stroke-width="2"/><path d="M100 102 L82 112" stroke-width="2"/>'
        '<path d="M50 178 L44 194 L58 184 Z" fill="{c}"/><path d="M70 192 C90 186 108 194 128 188" stroke-width="2"/></svg>'
    ),
    "staff": (
        '<svg viewBox="0 0 200 200" fill="none" stroke="{c}" stroke-width="3" stroke-linecap="round">'
        '<path d="M10 70 H190"/><path d="M10 88 H190"/><path d="M10 106 H190"/><path d="M10 124 H190"/><path d="M10 142 H190"/>'
        '<ellipse cx="70" cy="124" rx="11" ry="8" fill="{c}"/><path d="M80 124 V60"/>'
        '<ellipse cx="130" cy="97" rx="11" ry="8" fill="{c}"/><path d="M140 97 V36"/></svg>'
    ),
}

_STAFF_STRIP = (
    '<svg class="ui-sch-staff" aria-hidden="true" viewBox="0 0 1000 64" preserveAspectRatio="none">'
    '<g stroke="#e9c46a" stroke-width="1.2" fill="none"><path d="M0 8 H1000"/><path d="M0 20 H1000"/>'
    '<path d="M0 32 H1000"/><path d="M0 44 H1000"/><path d="M0 56 H1000"/></g>'
    '<g fill="#e9c46a"><ellipse cx="520" cy="38" rx="7" ry="5"/><ellipse cx="580" cy="26" rx="7" ry="5"/>'
    '<ellipse cx="640" cy="32" rx="7" ry="5"/><ellipse cx="700" cy="14" rx="7" ry="5"/></g></svg>'
)

_TEXTURE = "repeating-linear-gradient(135deg, rgba(255,255,255,0.035) 0 2px, transparent 2px 11px)"


def header_source(source: str) -> str:
    """Normalize any of the app's source spellings to catalog / custom / composition."""
    s = str(source or "").strip().lower()
    if "compos" in s:
        return SOURCE_COMPOSITION
    if "custom" in s or "progression" in s:
        return SOURCE_CUSTOM
    return SOURCE_CATALOG


def header_style_label(style: str) -> str:
    """The style's canonical label from the app's genre definitions ('' when unknown)."""
    raw = str(style or "").strip()
    if not raw:
        return ""
    try:
        from practice_studio import genre_visual_style

        label = str(genre_visual_style(raw).get("label") or "").strip()
    except Exception:
        label = raw
    return label if label in _STYLE else raw


def header_theme(source: str, style: str) -> dict[str, str]:
    """Colours, artwork and icon for one header (no markup)."""
    src = header_source(source)
    label = header_style_label(style)
    glow, glow2, art_color, art, icon = _STYLE.get(label, _NEUTRAL)
    if src == SOURCE_COMPOSITION:
        # Composition keeps its black/gold identity: the style only warms it faintly.
        glow, glow2, art_color, art, icon = "rgba(233,196,106,0.16)", "rgba(30,41,59,0.6)", "#e9c46a", "quill", "quill"
    elif src == SOURCE_CUSTOM:
        # Custom keeps its green base with a clear yellow accent; the style glow sits beside it.
        glow, glow2, art_color = "rgba(250,204,21,0.42)", glow, "#fde047"
    background = (
        f"radial-gradient(ellipse 60% 120% at 88% 30%, {glow} 0%, transparent 70%), "
        f"radial-gradient(ellipse 50% 90% at 62% 110%, {glow2} 0%, transparent 70%), "
        f"{_TEXTURE}, {_SOURCE_BASE[src]}"
    )
    chip_label, chip_ink, chip_ring = _SOURCE_CHIP[src]
    return {
        "source": src,
        "style_label": label,
        "background": background,
        "art": art,
        "art_color": art_color,
        "icon": _ICON[icon],
        "source_label": chip_label,
        "source_ink": chip_ink,
        "source_ring": chip_ring,
    }


def song_card_header_html(
    *,
    source: str,
    style: str,
    title: str,
    artist: str = "",
    status: str = "Now loaded for practice",
    favorite: bool = False,
    bars: Iterable[str] | None = None,
    variant: str = "songs",
) -> str:
    """The header markup (CSS included). ``bars``: up to four chords shown on Custom headers."""
    t = header_theme(source, style)
    esc = html.escape
    art_svg = _ART[t["art"]].format(c=t["art_color"])
    chips = (
        f'<span class="ui-sch-chip ui-sch-chip-source" style="color:{t["source_ink"]};border-color:{t["source_ring"]};">'
        f'{esc(t["source_label"])}</span>'
    )
    if t["style_label"]:
        chips += f'<span class="ui-sch-chip ui-sch-chip-style">{esc(t["style_label"])}</span>'
    status_html = (
        f'<span class="ui-sch-status"><span class="ui-sch-dot"></span>{esc(status)}</span>' if status else ""
    )
    fav_html = '<span class="ui-sch-fav" title="Favorite" aria-label="Favorite">★</span>' if favorite else ""
    grid_html = ""
    bar_list = [str(b) for b in (bars or []) if str(b or "").strip()][:4]
    # The bar grid sits beside the title: only with a short title, so it never runs into it.
    if t["source"] == SOURCE_CUSTOM and bar_list and len(str(title or "")) <= 18:
        cells = "".join(f'<span class="ui-sch-bar">{esc(b)}</span>' for b in bar_list)
        grid_html = f'<div class="ui-sch-grid" aria-hidden="true">{cells}</div>'
    staff_html = _STAFF_STRIP if t["source"] == SOURCE_COMPOSITION else ""
    artist_html = f'<p class="ui-sch-artist">{esc(artist)}</p>' if str(artist or "").strip() else ""
    classes = f'ui-sch ui-sch-{t["source"]} ui-sch-art-{t["art"]} ui-sch-v-{esc(variant)}'
    return (
        f"<style>{SONG_CARD_HEADER_CSS}</style>"
        f'<div class="ui-sch-wrap"><header class="{classes}" data-source="{t["source"]}" '
        f'data-style="{esc(t["style_label"])}" style="background:{t["background"]};">'
        f"{staff_html}{grid_html}"
        f'<div class="ui-sch-art" aria-hidden="true">{art_svg}</div>'
        f'<div class="ui-sch-top"><div class="ui-sch-chips">{chips}</div>'
        f'<div class="ui-sch-right">{status_html}{fav_html}</div></div>'
        f'<div class="ui-sch-titlerow"><div class="ui-sch-tile" aria-hidden="true">'
        f'<svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round"><path d="{t["icon"]}"/></svg></div>'
        f'<div class="ui-sch-names"><h2 class="ui-sch-title">{esc(title)}</h2>{artist_html}</div></div>'
        "</header></div>"
    )


SONG_CARD_HEADER_CSS = """
.ui-sch-wrap{container-type:inline-size;container-name:sch;width:100%;}
.ui-sch{position:relative;overflow:hidden;box-sizing:border-box;min-height:224px;padding:26px 36px 32px;
  display:flex;flex-direction:column;justify-content:space-between;gap:22px;color:#fff;border-radius:18px 18px 0 0;
  font-family:'Source Sans 3','Source Sans Pro',system-ui,sans-serif;}
.ui-sch-custom{border-bottom:3px solid rgba(250,204,21,0.8);}
.ui-sch-composition{border-bottom:3px solid rgba(233,196,106,0.75);}
.ui-sch-art{position:absolute;right:56px;bottom:-34px;width:270px;height:270px;opacity:0.24;pointer-events:none;}
.ui-sch-art svg{width:100%;height:100%;display:block;}
.ui-sch-staff{position:absolute;left:0;top:118px;width:100%;height:64px;opacity:0.2;pointer-events:none;}
.ui-sch-grid{position:absolute;right:290px;top:104px;display:flex;gap:8px;opacity:0.45;pointer-events:none;}
.ui-sch-bar{box-sizing:border-box;width:86px;height:56px;border:1.5px dashed #fde68a;border-radius:8px;color:#fde68a;
  font-weight:700;font-size:20px;display:flex;align-items:center;padding-left:14px;}
.ui-sch-top{position:relative;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:nowrap;}
.ui-sch-chips{display:flex;flex-wrap:wrap;gap:8px;}
.ui-sch-chip{display:inline-flex;align-items:center;padding:5px 12px;border-radius:999px;font-size:12px;font-weight:700;
  letter-spacing:0.06em;text-transform:uppercase;line-height:1.3;}
.ui-sch-chip-source{background:rgba(2,6,23,0.28);border:1px solid;}
.ui-sch-chip-style{background:rgba(255,255,255,0.14);border:1px solid rgba(255,255,255,0.32);color:#fff;}
.ui-sch-right{display:flex;align-items:center;gap:10px;}
.ui-sch-status{display:inline-flex;align-items:center;gap:8px;padding:7px 13px;border-radius:999px;background:rgba(2,6,23,0.32);
  border:1px solid rgba(255,255,255,0.34);font-size:12px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;white-space:nowrap;}
.ui-sch-dot{width:8px;height:8px;border-radius:50%;background:#86efac;flex:0 0 8px;}
.ui-sch-fav{width:40px;height:40px;border-radius:12px;border:1px solid rgba(255,255,255,0.4);background:rgba(2,6,23,0.3);
  color:#fbbf24;font-size:22px;display:flex;align-items:center;justify-content:center;}
.ui-sch-titlerow{position:relative;display:flex;align-items:center;gap:18px;max-width:68%;}
.ui-sch-tile{width:66px;height:66px;flex:0 0 66px;border-radius:16px;background:rgba(255,255,255,0.14);
  border:1px solid rgba(255,255,255,0.32);display:flex;align-items:center;justify-content:center;}
.ui-sch-tile svg{width:30px;height:30px;}
.ui-sch-names{display:flex;flex-direction:column;gap:4px;min-width:0;}
.ui-sch .ui-sch-title{margin:0;padding:0;font-size:36px;line-height:1.12;font-weight:800;letter-spacing:-0.02em;color:#fff;
  text-shadow:0 1px 12px rgba(2,6,23,0.35);overflow-wrap:anywhere;}
.ui-sch .ui-sch-artist{margin:0;font-size:18px;line-height:1.3;font-weight:600;color:#e2e8f0;}
@container sch (max-width: 820px){
  .ui-sch{min-height:212px;padding:22px 26px 26px;}
  .ui-sch-art{right:14px;width:220px;height:220px;}
  .ui-sch-grid{right:150px;top:96px;}
  .ui-sch-titlerow{max-width:74%;}
  .ui-sch-tile{width:58px;height:58px;flex-basis:58px;}
  .ui-sch .ui-sch-title{font-size:30px;}
  .ui-sch .ui-sch-artist{font-size:17px;}
}
@container sch (max-width: 560px){
  .ui-sch{min-height:0;padding:16px 16px 20px;gap:14px;border-radius:16px 16px 0 0;}
  .ui-sch-top{flex-wrap:wrap;}
  .ui-sch-chips{order:2;}
  .ui-sch-right{order:1;flex:1 1 100%;justify-content:space-between;}
  .ui-sch-chip,.ui-sch-status{font-size:11px;}
  .ui-sch-art{right:-14px;bottom:-22px;width:150px;height:150px;opacity:0.16;}
  .ui-sch-grid{display:none;}
  .ui-sch-staff{top:auto;bottom:18px;}
  .ui-sch-titlerow{max-width:100%;gap:12px;}
  .ui-sch-tile{width:48px;height:48px;flex-basis:48px;border-radius:12px;}
  .ui-sch-tile svg{width:24px;height:24px;}
  .ui-sch .ui-sch-title{font-size:24px;}
  .ui-sch .ui-sch-artist{font-size:15px;}
}
""".strip()

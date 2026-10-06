"""Canonical musician-facing icons for major studio features.

Same concept → same icon across Tutorial, nav, and in-app chrome.
Different major concepts → distinguishable icons (do not share a symbol).

Page-level identities live here; Creative Lab *tool* icons remain in
``studio_page_state.CREATIVE_TOOL_ICONS`` (Missions uses the same glyph as
``FEATURE_ICONS['mission']``).
"""

from __future__ import annotations

import html as _html

# Compact black clarinet silhouette for HTML badges / instrument strips.
# There is no Unicode clarinet emoji; never reuse Saxophone / Songs / note glyphs.
# Diagonal tube + flared bell + mouthpiece barrel + tone holes (not a pen/nib).
CLARINET_ICON_SVG = """<svg class="ui-instrument-icon-clarinet" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="1em" height="1em" aria-hidden="true" focusable="false"><path fill="#111827" d="M2.2 16.8c-.3 1.6 1.2 2.9 2.8 2.4l3.4-1.2c.6-.2.8-.9.4-1.4l-1.3-1.8c-.3-.5-1-.6-1.5-.2l-3.8 2.2z"/><path fill="#111827" d="M6.8 15.6 17.2 5.2c.5-.5 1.2-.5 1.7 0l1.4 1.4c.5.5.5 1.2 0 1.7L9.9 18.5c-.3.3-.7.3-1 .1l-1.9-.7c-.5-.2-.6-.8-.2-1.3z"/><path fill="#111827" d="M18.2 4.8 20 3c.4-.4 1-.4 1.4 0l1 1c.4.4.4 1 0 1.4l-1.8 1.8-2.4-2.4z"/><rect fill="#111827" x="17.2" y="4.3" width="2.4" height="0.75" rx="0.2" transform="rotate(-45 18.4 4.7)"/><circle fill="#f8fafc" cx="14.8" cy="8" r="0.6"/><circle fill="#f8fafc" cx="13.2" cy="9.6" r="0.6"/><circle fill="#f8fafc" cx="11.6" cy="11.2" r="0.6"/><circle fill="#f8fafc" cx="10" cy="12.8" r="0.6"/><circle fill="#f8fafc" cx="8.4" cy="14.4" r="0.6"/></svg>"""

# Brand note — traced from the white eighth note in the MPC logo emblem so the
# standalone note on the song cover matches the logo rather than the generic
# note emoji: tilted oval head, straight stem, broad sweeping flag.
BRAND_NOTE_ICON_SVG = (
    '<svg class="ui-brand-note-icon" xmlns="http://www.w3.org/2000/svg" '
    'viewBox="0 0 24 24" width="1em" height="1em" aria-hidden="true" focusable="false">'
    '<ellipse fill="currentColor" cx="8.1" cy="17.4" rx="4.7" ry="3.5" '
    'transform="rotate(-21 8.1 17.4)"/>'
    '<path fill="currentColor" d="M11.9 16.1V3.5c0-.5.4-.9.9-.9s.9.4.9.9v12.6c0 .5-.4.9-.9.9'
    's-.9-.4-.9-.9z"/>'
    '<path fill="currentColor" d="M13.1 2.7c2.5 1.6 5.2 3.2 6.5 5.4 1.3 2.2.8 4.5-1.3 6.5'
    '.6-2 .2-3.7-1.1-5.1-1.3-1.5-3-2.6-4.4-3.6z"/>'
    "</svg>"
)

# Major product concepts — keep values unique across this map.
FEATURE_ICONS: dict[str, str] = {
    "practice": "🎯",
    "practice_setup": "🎸",
    "practice_focus": "🔍",
    # Loop / restrict playback to one song section (not Practice Focus).
    "section_focus": "🔁",
    "original_key": "📜",
    # Key-related; not Songs (🎼) and not musical-note glyphs (🎵/🎶).
    "practice_concert_key": "🗝️",
    "pitch_tone_tuner": "🎛️",
    "timing_tempo_metronome": "⏱️",
    "mission": "🚩",
    "upload_analysis": "🎙️",
    "backing": "🎧",
    "creative": "🎨",
    # Writing/composing — not the Piano instrument glyph (🎹).
    "composition": "🪶",
    "custom": "✍️",
    "songs": "🎼",
    "multitrack": "🎚️",
    "practice_log": "📓",
    "music_coach": "💬",
    # Song/chord teaching — not Practice Setup (🎸) and not Music Coach (💬).
    "chord_song_coach": "📖",
    "karaoke": "🎤",
    # Catalog song chart + lyrics editing / save / revert (Tutorial: Charts & lyrics).
    "charts_lyrics": "📝",
    "transpose_helpers": "↔️",
    # Temporary key-cycle through a sequence (rotation) — not transpose (↔️)
    # and not section loop (🔁).
    "key_cycle": "🔄",
    # Session duration / timed practice. Same glyph as metronome by design.
    "session": "⏱️",
    "level": "📈",
}

# Instrument identity glyphs — same instrument → same icon across Practice,
# Songs, Backing, Creative, helpers, and written-key badges.
# Clarinet must never share Saxophone (🎷), Songs (🎼), or generic note (🎵).
INSTRUMENT_ICONS: dict[str, str] = {
    "Piano": "🎹",
    "Guitar": "🎸",
    "Bass": "🎸",
    "Saxophone": "🎷",
    "Flute": "🪈",
    "Trumpet": "🎺",
    # Black clarinet SVG (no Unicode clarinet emoji).
    "Clarinet": CLARINET_ICON_SVG,
    "Voice": "🎤",
    "Other": "✨",
}

# Semantic meta-badge fields — Songs / Custom / Composition / Karaoke / Backing.
# Same field → same glyph everywhere. Source logos (✍️/🪶/🎼) stay on left art.
SEMANTIC_FIELD_ICONS: dict[str, str] = {
    "style": "✨",
    "concert_key": FEATURE_ICONS["practice_concert_key"],
    "original_key": FEATURE_ICONS["original_key"],
    # Neutral written-charts field when instrument is unknown. Prefer
    # ``semantic_field_icon("written_key", instrument=...)`` so Clarinet/Sax
    # badges use the correct instrument glyph.
    "written_key": "📝",
    "shape_key": INSTRUMENT_ICONS["Guitar"],
    "charts": "📊",
    "bpm": "⏱",
    "meter": "🥁",
    "section": FEATURE_ICONS["section_focus"],
    "groove": "✨",
    # Feel / groove style field (same glyph as style badges).
    "feel": "✨",
    # Advanced Key cycling control — same glyph as FEATURE_ICONS["key_cycle"].
    "key_cycle": FEATURE_ICONS["key_cycle"],
    # Source *field* badge — not Catalog/Custom/Composition identity logos.
    "source_other": "📀",
    "source_catalog": FEATURE_ICONS["songs"],
    "practice_focus": FEATURE_ICONS["practice_focus"],
    "level": FEATURE_ICONS["level"],
}
SEMANTIC_FIELD_ICONS["source"] = SEMANTIC_FIELD_ICONS["source_other"]


def _normalize_instrument_family(instrument: str) -> str:
    name = str(instrument or "").strip()
    if not name:
        return ""
    if name in INSTRUMENT_ICONS:
        return name
    low = name.lower()
    if "sax" in low:
        return "Saxophone"
    if "clarinet" in low:
        return "Clarinet"
    if "trumpet" in low or "flugel" in low:
        return "Trumpet"
    if "flute" in low:
        return "Flute"
    if "guitar" in low:
        return "Guitar"
    if "bass" in low:
        return "Bass"
    if "piano" in low or "keyboard" in low:
        return "Piano"
    if "voice" in low or "vocal" in low or "sing" in low:
        return "Voice"
    return name


def instrument_icon(instrument: str) -> str:
    """Canonical icon for an instrument family (presentation only)."""
    family = _normalize_instrument_family(instrument)
    if family in INSTRUMENT_ICONS:
        return INSTRUMENT_ICONS[family]
    return INSTRUMENT_ICONS["Other"]


def icon_is_markup(icon: str) -> bool:
    """True when the icon value is trusted inline SVG/HTML markup."""
    return str(icon or "").lstrip().startswith("<")


def format_icon_html(icon: str) -> str:
    """Render an icon for HTML badges: trusted SVG passes through; text is escaped."""
    raw = str(icon or "")
    if not raw:
        return ""
    if icon_is_markup(raw):
        return raw
    return _html.escape(raw)


def semantic_field_icon(field: str, *, instrument: str = "") -> str:
    key = str(field or "").strip()
    if key == "shape_key":
        return INSTRUMENT_ICONS["Guitar"]
    if key == "written_key":
        family = _normalize_instrument_family(instrument)
        if family and family in INSTRUMENT_ICONS and family != "Other":
            return INSTRUMENT_ICONS[family]
    return SEMANTIC_FIELD_ICONS.get(key, "")


# Studio page id → concept key (nav, headers, compact buttons).
PAGE_FEATURE_KEYS: dict[str, str] = {
    "practice": "practice",
    "picker": "songs",
    "backing": "backing",
    "custom": "custom",
    "composer": "composition",
    "creative": "creative",
    "multitrack": "multitrack",
    "analysis": "upload_analysis",
    "log": "practice_log",
}


def feature_icon(concept: str) -> str:
    return FEATURE_ICONS.get(str(concept or "").strip(), "")


def feature_label(concept: str, text: str) -> str:
    """Prefix a control/heading with its canonical icon."""
    icon = feature_icon(concept)
    label = str(text or "").strip()
    if not icon:
        return label
    if not label:
        return icon
    return f"{icon} {label}"


def page_feature_icon(page_id: str) -> str:
    concept = PAGE_FEATURE_KEYS.get(str(page_id or "").strip(), "")
    return feature_icon(concept) if concept else ""


def page_feature_label(page_id: str, text: str) -> str:
    icon = page_feature_icon(page_id)
    label = str(text or "").strip()
    if not icon:
        return label
    return f"{icon} {label}" if label else icon


__all__ = (
    "BRAND_NOTE_ICON_SVG",
    "CLARINET_ICON_SVG",
    "FEATURE_ICONS",
    "INSTRUMENT_ICONS",
    "SEMANTIC_FIELD_ICONS",
    "PAGE_FEATURE_KEYS",
    "feature_icon",
    "feature_label",
    "format_icon_html",
    "icon_is_markup",
    "instrument_icon",
    "semantic_field_icon",
    "page_feature_icon",
    "page_feature_label",
)

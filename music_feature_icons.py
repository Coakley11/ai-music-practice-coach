"""Canonical musician-facing icons for major studio features.

Same concept → same icon across Tutorial, nav, and in-app chrome.
Different major concepts → distinguishable icons (do not share a symbol).

Page-level identities live here; Creative Lab *tool* icons remain in
``studio_page_state.CREATIVE_TOOL_ICONS`` (Missions uses the same glyph as
``FEATURE_ICONS['mission']``).
"""

from __future__ import annotations

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
    # Woodwind stand-in (no Unicode clarinet); distinct from sax / songs / note.
    "Clarinet": "🎐",
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
    "FEATURE_ICONS",
    "INSTRUMENT_ICONS",
    "SEMANTIC_FIELD_ICONS",
    "PAGE_FEATURE_KEYS",
    "feature_icon",
    "feature_label",
    "instrument_icon",
    "semantic_field_icon",
    "page_feature_icon",
    "page_feature_label",
)

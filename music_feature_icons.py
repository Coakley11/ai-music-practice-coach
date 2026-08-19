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
    "practice_focus": "🔍",
    "original_key": "📜",
    "practice_concert_key": "🔄",
    "pitch_tone_tuner": "🎛️",
    "timing_tempo_metronome": "⏱️",
    "mission": "🚩",
    "upload_analysis": "🎙️",
    "backing": "🎧",
    "creative": "🎨",
    "composition": "🎹",
    "custom": "✍️",
    "songs": "🎼",
    "multitrack": "🎚️",
    "practice_log": "📓",
    "music_coach": "💬",
    "karaoke": "🎤",
    "transpose_helpers": "↔️",
}

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
    "PAGE_FEATURE_KEYS",
    "feature_icon",
    "feature_label",
    "page_feature_icon",
    "page_feature_label",
)

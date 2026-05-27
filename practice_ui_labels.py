"""Icon labels for Practice Setup and related UI."""

from __future__ import annotations

import html
import re

INSTRUMENT_ICONS: dict[str, str] = {
    "Piano": "🎹",
    "Guitar": "🎸",
    "Bass": "🎸",
    "Saxophone": "🎷",
    "Flute": "🎵",
    "Trumpet": "🎺",
    "Clarinet": "🎵",
    "Voice": "🎤",
    "Other": "🎵",
}

LEVEL_ICONS: dict[str, str] = {
    "Beginner": "🌱",
    "Intermediate": "🚀",
    "Advanced": "🧠",
}

GROOVE_ICONS: dict[str, str] = {
    "Auto": "✨",
    "Pop groove": "🎧",
    "Rock groove": "🤘",
    "Jazz swing": "🎷",
    "Bossa nova": "🌴",
    "Funk groove": "🕺",
    "Ballad": "🎹",
    "Jewish groove": "✡",
}

FOCUS_ICONS: dict[str, str] = {
    "Voicings": "🎼",
    "Left-Hand Patterns": "🎹",
    "Comping": "🎹",
    "Voice Leading": "🎼",
    "Inversions": "🎼",
    "Reharmonization": "🎼",
    "Strumming": "🥁",
    "Rhythm Guitar": "🥁",
    "Chord Transitions": "🔁",
    "Barre Chords": "🎸",
    "Fingerstyle": "🎸",
    "Triads": "🎼",
    "Double Stops": "🎸",
    "Lead Guitar": "🎶",
    "Soloing": "🎷",
    "Groove": "🥁",
    "Pocket": "🥁",
    "Root Motion": "🔁",
    "Walking Bass": "🎶",
    "Syncopation": "🥁",
    "Tone": "🎤",
    "Scales": "🎶",
    "Articulation": "🎵",
    "Bebop Phrasing": "🎷",
    "Breath Support": "🎤",
    "Guide Tones": "🎼",
    "Melody": "🎶",
    "Harmony": "🎼",
    "Rhythm": "🥁",
    "Dynamics": "🎚️",
    "Improvisation": "🎷",
    "Technique": "🎯",
    "Ear Training": "👂",
    "Breath Control": "🎤",
    "Phrasing": "🎤",
    "Pitch Accuracy": "🎤",
    "Emotional Delivery": "🎤",
    "Harmony Singing": "🎼",
    "Vibrato": "🎤",
    "Endurance": "💪",
    "Range": "🎶",
    "Jazz Phrasing": "🎷",
}

_EMOJI_TAIL = re.compile(
    r"\s+[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F900-\U0001F9FF]+\s*$"
)


def icon_for_focus(name: str) -> str:
    if name in FOCUS_ICONS:
        return FOCUS_ICONS[name]
    low = name.lower()
    if "chord" in low or "voic" in low or "harmony" in low or "inversion" in low:
        return "🎼"
    if "rhythm" in low or "strum" in low or "groove" in low or "pocket" in low:
        return "🥁"
    if "scale" in low or "solo" in low or "improv" in low or "lead" in low:
        return "🎶"
    if "transition" in low:
        return "🔁"
    return "🎯"


def option_label(name: str, icon: str) -> str:
    return f"{name} {icon}".strip() if icon else name


def strip_option_label(label: str) -> str:
    return _EMOJI_TAIL.sub("", label).strip()


def labeled_options(names: list[str], icon_map: dict[str, str]) -> tuple[list[str], dict[str, str]]:
    """Return display labels and label→value map."""
    labels: list[str] = []
    back: dict[str, str] = {}
    for name in names:
        icon = icon_map.get(name) if name in icon_map else icon_for_focus(name)
        lab = option_label(name, icon)
        labels.append(lab)
        back[lab] = name
    return labels, back


def setup_pill_html(name: str, icon: str) -> str:
    ic = html.escape(icon or "")
    nm = html.escape(name or "")
    return f'<span class="setup-field-pill">{ic} {nm}</span>'

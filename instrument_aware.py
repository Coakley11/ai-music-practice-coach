"""Subtle instrument-aware accents for page headers (visual + copy)."""

from __future__ import annotations

import html
from typing import Any

_INSTRUMENT_THEMES: dict[str, dict[str, str]] = {
    "Guitar": {
        "icon": "🎸",
        "accent": "#d97706",
        "label": "Guitar practice mode",
        "hint": "Chord shapes · strumming · picking · fretboard connection",
    },
    "Piano": {
        "icon": "🎹",
        "accent": "#2563eb",
        "label": "Piano practice mode",
        "hint": "Voicings · LH/RH balance · voice-leading between chords",
    },
    "Saxophone": {
        "icon": "🎷",
        "accent": "#7c3aed",
        "label": "Saxophone practice mode",
        "hint": "Tone · articulation · breath support · phrasing",
    },
    "Trumpet": {
        "icon": "🎺",
        "accent": "#dc2626",
        "label": "Trumpet practice mode",
        "hint": "Tone · articulation · range · clean attacks",
    },
    "Clarinet": {
        "icon": "🎵",
        "accent": "#0891b2",
        "label": "Clarinet practice mode",
        "hint": "Even tone · articulation · breath · register connection",
    },
    "Flute": {
        "icon": "🪈",
        "accent": "#0d9488",
        "label": "Flute practice mode",
        "hint": "Breath · tone color · smooth phrasing · intonation",
    },
    "Bass": {
        "icon": "🎸",
        "accent": "#4f46e5",
        "label": "Bass practice mode",
        "hint": "Groove pocket · root movement · line clarity",
    },
    "Voice": {
        "icon": "🎤",
        "accent": "#db2777",
        "label": "Vocal practice mode",
        "hint": "Pitch · breath · lyric phrasing · vowel placement",
    },
    "Other": {
        "icon": "✨",
        "accent": "#64748b",
        "label": "Practice mode",
        "hint": "Listen · phrase · connect chords to melody",
    },
}

_PAGE_HINTS: dict[str, dict[str, str]] = {
    "practice": {"lead": "Build technique on the active chart."},
    "backing": {"lead": "Play along with generated accompaniment."},
    "picker": {"lead": "Choose your active song for the whole studio."},
    "creative": {"lead": "Explore harmony, improv, and creative tools."},
    "analysis": {"lead": "Review recordings with AI coaching feedback."},
    "custom": {"lead": "Edit your custom chord progression."},
    "multitrack": {"lead": "Layer and review practice takes."},
    "log": {"lead": "Track sessions over time."},
}


def instrument_theme(instrument: str) -> dict[str, str]:
    return dict(_INSTRUMENT_THEMES.get(instrument, _INSTRUMENT_THEMES["Other"]))


def render_instrument_context_strip(
    st: Any,
    instrument: str,
    page_id: str,
    session_state: dict[str, Any] | None = None,
) -> None:
    """Compact instrument accent below page title."""
    theme = instrument_theme(instrument)
    page = _PAGE_HINTS.get(page_id, {})
    lead = page.get("lead", "")
    pitch_family = _transposing_pitch_family_label(instrument, session_state or {})
    label = theme["label"]
    if pitch_family:
        label = f"{label} · {pitch_family}"
    st.markdown(
        f'<div class="ui-instrument-strip" style="border-left-color:{html.escape(theme["accent"])};">'
        f'<span class="ui-instrument-strip-icon">{html.escape(theme["icon"])}</span>'
        f'<span class="ui-instrument-strip-body">'
        f'<strong>{html.escape(label)}</strong>'
        f' · {html.escape(theme["hint"])}'
        + (f' · <span class="ui-instrument-strip-muted">{html.escape(lead)}</span>' if lead else "")
        + "</span></div>",
        unsafe_allow_html=True,
    )
    if pitch_family:
        st.markdown(
            f'<p class="ui-instrument-pitch-family"><strong>{html.escape(pitch_family)}</strong></p>',
            unsafe_allow_html=True,
        )


def _transposing_pitch_family_label(instrument: str, session_state: dict[str, Any]) -> str:
    """B-flat / E-flat family label for saxophone, trumpet, and clarinet."""
    if instrument not in {"Saxophone", "Trumpet", "Clarinet"}:
        return ""
    try:
        from instrument_transposition import is_eb_instrument, selected_transposing_type

        t_type = selected_transposing_type(session_state, instrument)
        if not t_type:
            return ""
        return "E♭ Instrument" if is_eb_instrument(t_type) else "B♭ Instrument"
    except ImportError:
        return ""

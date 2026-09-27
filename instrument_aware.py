"""Subtle instrument-aware accents for page headers (visual + copy)."""

from __future__ import annotations

import html
from typing import Any

def _theme(icon: str, accent: str, label: str, hint: str) -> dict[str, str]:
    return {"icon": icon, "accent": accent, "label": label, "hint": hint}


def _instrument_themes() -> dict[str, dict[str, str]]:
    try:
        from music_feature_icons import INSTRUMENT_ICONS
    except ImportError:
        INSTRUMENT_ICONS = {
            "Guitar": "🎸",
            "Piano": "🎹",
            "Saxophone": "🎷",
            "Trumpet": "🎺",
            "Clarinet": "Cl",
            "Flute": "🪈",
            "Bass": "🎸",
            "Voice": "🎤",
            "Other": "✨",
        }
    return {
        "Guitar": _theme(
            INSTRUMENT_ICONS["Guitar"],
            "#d97706",
            "Guitar practice mode",
            "Chord shapes · strumming · picking · fretboard connection",
        ),
        "Piano": _theme(
            INSTRUMENT_ICONS["Piano"],
            "#2563eb",
            "Piano practice mode",
            "Voicings · LH/RH balance · voice-leading between chords",
        ),
        "Saxophone": _theme(
            INSTRUMENT_ICONS["Saxophone"],
            "#7c3aed",
            "Saxophone practice mode",
            "Tone · articulation · breath support · phrasing",
        ),
        "Trumpet": _theme(
            INSTRUMENT_ICONS["Trumpet"],
            "#dc2626",
            "Trumpet practice mode",
            "Tone · articulation · range · clean attacks",
        ),
        "Clarinet": _theme(
            INSTRUMENT_ICONS["Clarinet"],
            "#0891b2",
            "Clarinet practice mode",
            "Even tone · articulation · breath · register connection",
        ),
        "Flute": _theme(
            INSTRUMENT_ICONS["Flute"],
            "#0d9488",
            "Flute practice mode",
            "Breath · tone color · smooth phrasing · intonation",
        ),
        "Bass": _theme(
            INSTRUMENT_ICONS["Bass"],
            "#4f46e5",
            "Bass practice mode",
            "Groove pocket · root movement · line clarity",
        ),
        "Voice": _theme(
            INSTRUMENT_ICONS["Voice"],
            "#db2777",
            "Vocal practice mode",
            "Pitch · breath · lyric phrasing · vowel placement",
        ),
        "Other": _theme(
            INSTRUMENT_ICONS["Other"],
            "#64748b",
            "Practice mode",
            "Listen · phrase · connect chords to melody",
        ),
    }


_INSTRUMENT_THEMES = _instrument_themes()

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
    themes = _instrument_themes()
    name = str(instrument or "").strip()
    if name in themes:
        return dict(themes[name])
    low = name.lower()
    if "sax" in low:
        return dict(themes["Saxophone"])
    if "clarinet" in low:
        return dict(themes["Clarinet"])
    if "trumpet" in low or "flugel" in low:
        return dict(themes["Trumpet"])
    if "flute" in low:
        return dict(themes["Flute"])
    if "bass" in low:
        return dict(themes["Bass"])
    if "guitar" in low:
        return dict(themes["Guitar"])
    if "piano" in low or "keyboard" in low:
        return dict(themes["Piano"])
    if "voice" in low or "vocal" in low:
        return dict(themes["Voice"])
    return dict(themes["Other"])


def instrument_practice_mode_hint(
    instrument: str,
    session_state: dict[str, Any] | None = None,
) -> str:
    """Instrument default plus live Practice Focus coaching, not a frozen Voicings line."""
    theme = instrument_theme(instrument)
    default = str(theme.get("hint") or "").strip()
    if not session_state:
        return default
    try:
        from practice_focus_creative import format_practice_focus_coaching_line

        line = str(format_practice_focus_coaching_line(session_state) or "").strip()
        if line:
            return line
    except Exception:
        pass
    return default


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
    hint = instrument_practice_mode_hint(instrument, session_state)
    try:
        from music_feature_icons import format_icon_html

        icon_html = format_icon_html(theme["icon"])
    except ImportError:
        icon_html = html.escape(theme["icon"])
    st.markdown(
        f'<div class="ui-instrument-strip" style="border-left-color:{html.escape(theme["accent"])};">'
        f'<span class="ui-instrument-strip-icon">{icon_html}</span>'
        f'<span class="ui-instrument-strip-body">'
        f'<strong>{html.escape(label)}</strong>'
        f' · {html.escape(hint)}'
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

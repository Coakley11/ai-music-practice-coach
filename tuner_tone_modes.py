"""Mode helpers for Practice page tuner / tone sustain UI (testable without Streamlit)."""

from __future__ import annotations

MODE_TUNE_LIVE = "Tune Live"
MODE_TONE_SUSTAIN = "Tone Sustain Practice"

# Legacy session/widget values still accepted when reading persisted mode.
_MODE_ALIASES: dict[str, str] = {
    "tune (live)": MODE_TUNE_LIVE,
    "tune live": MODE_TUNE_LIVE,
    "tone practice (sustain)": MODE_TONE_SUSTAIN,
    "tone sustain practice": MODE_TONE_SUSTAIN,
}


def normalize_tuner_mode(mode: str) -> str:
    text = str(mode or "").strip()
    if text in (MODE_TUNE_LIVE, MODE_TONE_SUSTAIN):
        return text
    return _MODE_ALIASES.get(text.lower(), text)


def is_tune_live_mode(mode: str) -> bool:
    return normalize_tuner_mode(mode) == MODE_TUNE_LIVE


def is_tone_sustain_mode(mode: str) -> bool:
    return normalize_tuner_mode(mode) == MODE_TONE_SUSTAIN


def shows_live_target_note_input(mode: str, profile_mode: str) -> bool:
    """Tune Live is free tuning — never show optional/free-text target note input."""
    del mode, profile_mode
    return False


def shows_tone_sustain_note_dropdown(mode: str, profile_mode: str) -> bool:
    """Tone Sustain Practice requires a chromatic pitch-class dropdown."""
    if not is_tone_sustain_mode(mode):
        return False
    return profile_mode in ("wind", "voice", "chromatic", "strings")

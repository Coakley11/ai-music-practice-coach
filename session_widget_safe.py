"""Safe session writes when Streamlit widgets may already be instantiated."""

from __future__ import annotations

from typing import Any

from songs.key_state import PENDING_DISPLAY_KEY

# Keys bound to Streamlit widgets — never assign directly after widget render.
WIDGET_BOUND_KEYS: frozenset[str] = frozenset(
    {
        "display_key",
        "instrument",
        "level",
        "focus",
        "backing_track_bpm",
        "bpm",
        "improv_entry_mode",
        "improv_intelligence_tab",
        "creative_lab_analysis_mode",
        "improv_style_key",
        "improv_jam_key",
        "improv_style_bpm",
        "improv_jam_bpm",
        "improv_mood",
        "improv_difficulty",
        "improv_groove",
        "improv_jam_mood",
    }
)

PENDING_INSTRUMENT_KEY = "_pending_instrument"
PENDING_LEVEL_KEY = "_pending_level"
PENDING_FOCUS_KEY = "_pending_focus"
PENDING_IMPROV_ENTRY_MODE_KEY = "_pending_improv_entry_mode"
PENDING_IMPROV_INTELLIGENCE_TAB_KEY = "_pending_improv_intelligence_tab"
PENDING_CREATIVE_LAB_MODE_KEY = "_pending_creative_lab_analysis_mode"
PENDING_IMPROV_STYLE_KEY = "_pending_improv_style_key"
PENDING_IMPROV_JAM_KEY = "_pending_improv_jam_key"
PENDING_IMPROV_STYLE_BPM_KEY = "_pending_improv_style_bpm"
PENDING_IMPROV_JAM_BPM_KEY = "_pending_improv_jam_bpm"
PENDING_IMPROV_MOOD_KEY = "_pending_improv_mood"
PENDING_IMPROV_DIFFICULTY_KEY = "_pending_improv_difficulty"
PENDING_IMPROV_GROOVE_KEY = "_pending_improv_groove"
PENDING_IMPROV_JAM_MOOD_KEY = "_pending_improv_jam_mood"

_PENDING_FOR_WIDGET_KEY: dict[str, str] = {
    "display_key": PENDING_DISPLAY_KEY,
    "instrument": PENDING_INSTRUMENT_KEY,
    "level": PENDING_LEVEL_KEY,
    "focus": PENDING_FOCUS_KEY,
    "improv_entry_mode": PENDING_IMPROV_ENTRY_MODE_KEY,
    "improv_intelligence_tab": PENDING_IMPROV_INTELLIGENCE_TAB_KEY,
    "creative_lab_analysis_mode": PENDING_CREATIVE_LAB_MODE_KEY,
    "improv_style_key": PENDING_IMPROV_STYLE_KEY,
    "improv_jam_key": PENDING_IMPROV_JAM_KEY,
    "improv_style_bpm": PENDING_IMPROV_STYLE_BPM_KEY,
    "improv_jam_bpm": PENDING_IMPROV_JAM_BPM_KEY,
    "improv_mood": PENDING_IMPROV_MOOD_KEY,
    "improv_difficulty": PENDING_IMPROV_DIFFICULTY_KEY,
    "improv_groove": PENDING_IMPROV_GROOVE_KEY,
    "improv_jam_mood": PENDING_IMPROV_JAM_MOOD_KEY,
}


def widgets_likely_instantiated(session: dict[str, Any]) -> bool:
    """True when sidebar/global widgets have probably rendered this rerun."""
    try:
        from music_restore_phase import music_restore_phase_complete

        if not music_restore_phase_complete(session):
            return False
    except ImportError:
        pass
    return "display_key" in session


def safe_session_assign(
    session: dict[str, Any],
    key: str,
    value: Any,
    *,
    widget_safe: bool = True,
) -> None:
    """Write session value without touching locked widget keys when ``widget_safe``."""
    if not widget_safe or key not in WIDGET_BOUND_KEYS:
        session[key] = value
        return
    if not widgets_likely_instantiated(session):
        session[key] = value
        return
    pending_key = _PENDING_FOR_WIDGET_KEY.get(key)
    if pending_key:
        session[pending_key] = value
        return
    try:
        from music_state_writes import WriteOrigin, guarded_session_set

        if guarded_session_set(
            session,
            key,
            value,
            origin=WriteOrigin.RESTORE,
            writer="session_widget_safe",
        ):
            return
    except ImportError:
        pass


def safe_assign_display_key(
    session: dict[str, Any],
    key: str,
    *,
    widget_safe: bool = True,
    st_like: Any | None = None,
) -> None:
    """Set concert/display key via pending queue when widgets may exist."""
    concert = str(key or "C").strip() or "C"
    session["concert_key"] = concert
    if not widget_safe or not widgets_likely_instantiated(session):
        session["display_key"] = concert
        session[PENDING_DISPLAY_KEY] = concert
        return
    session[PENDING_DISPLAY_KEY] = concert
    if st_like is not None:
        try:
            from songs.key_state import request_display_key

            request_display_key(st_like, concert)
        except ImportError:
            pass


def apply_pending_widget_hydrates(session: dict[str, Any]) -> None:
    """Apply queued pending values before widgets render (early in rerun)."""
    pending_display = session.pop(PENDING_DISPLAY_KEY, None)
    if pending_display is not None and "display_key" not in session:
        session["display_key"] = str(pending_display)
    for widget_key, pending_key in _PENDING_FOR_WIDGET_KEY.items():
        if widget_key == "display_key":
            continue
        pending = session.pop(pending_key, None)
        if pending is not None and widget_key not in session:
            session[widget_key] = pending


__all__ = [
    "PENDING_CREATIVE_LAB_MODE_KEY",
    "PENDING_IMPROV_ENTRY_MODE_KEY",
    "PENDING_IMPROV_INTELLIGENCE_TAB_KEY",
    "PENDING_IMPROV_JAM_BPM_KEY",
    "PENDING_IMPROV_JAM_KEY",
    "PENDING_IMPROV_STYLE_BPM_KEY",
    "PENDING_IMPROV_STYLE_KEY",
    "PENDING_INSTRUMENT_KEY",
    "WIDGET_BOUND_KEYS",
    "apply_pending_widget_hydrates",
    "safe_assign_display_key",
    "safe_session_assign",
    "widgets_likely_instantiated",
]

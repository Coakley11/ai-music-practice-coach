"""Evaluation focus for mission recording analysis (Phase 2A)."""

from __future__ import annotations

from typing import Any

MISSION_EVALUATION_FOCUS_KEY = "improv_mission_evaluation_focus"
MISSION_MATCH_EXAMPLE_MODE_KEY = "improv_mission_match_example_mode"

EVALUATION_FOCUS_OPTIONS: tuple[str, ...] = (
    "Overall mission execution",
    "Phrasing",
    "Melodic development",
    "Motif development",
    "Rhythmic variety",
    "Use of space",
    "Chord-tone targeting",
    "Harmonic fit",
)

_DEFAULT_FOCUS = EVALUATION_FOCUS_OPTIONS[0]


def normalize_evaluation_focus(value: Any) -> str:
    text = str(value or "").strip()
    if text in EVALUATION_FOCUS_OPTIONS:
        return text
    return _DEFAULT_FOCUS


def authoritative_evaluation_focus(session: dict[str, Any]) -> str:
    try:
        from creative_mission_config_persistence import canonical_mission_config_value
    except ImportError:
        canonical_mission_config_value = lambda _s, k: _s.get(k)  # type: ignore[assignment,misc]

    raw = canonical_mission_config_value(session, MISSION_EVALUATION_FOCUS_KEY)
    if raw is None:
        raw = session.get(MISSION_EVALUATION_FOCUS_KEY)
    return normalize_evaluation_focus(raw)


def example_match_mode_enabled(session: dict[str, Any]) -> bool:
    return bool(session.get(MISSION_MATCH_EXAMPLE_MODE_KEY))


def default_mission_recording_expander_expanded() -> bool:
    return False

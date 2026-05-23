"""Persistent per-page UI state — defaults only when keys are missing (never on revisit)."""

from __future__ import annotations

from typing import Any, Callable

# Creative Lab — Improvisation Intelligence
IMPROV_TAB_NAMES: tuple[str, ...] = (
    "Entry & Jam",
    "Live Coach",
    "Phrase / Motif",
    "Missions",
    "Harmony Map",
    "Metrics & AI",
)

IMPROV_SONG_SOURCES: tuple[str, ...] = ("Active song", "Custom progression")

IMPROV_ENTRY_MODES: tuple[str, ...] = (
    "Song-Based Improvisation",
    "Style Jam Mode",
    "Jam Session Generator",
)

_LEGACY_SONG_SOURCE_MAP: dict[str, str] = {
    "Use active studio song": "Active song",
    "Custom progression (CPL)": "Custom progression",
    "Blue Bossa": "Active song",
    "Autumn Leaves": "Active song",
    "Hotel California": "Active song",
    "All of Me": "Active song",
}


def migrate_legacy_session_keys(session_state: dict) -> None:
    """One-time renames so older sessions keep working."""
    old_preset = session_state.get("improv_song_preset")
    if old_preset and "improv_song_source" not in session_state:
        session_state["improv_song_source"] = _LEGACY_SONG_SOURCE_MAP.get(
            str(old_preset),
            "Active song",
        )
    session_state.pop("improv_song_preset", None)


def init_improvisation_state(session_state: dict, *, is_custom_active: bool) -> None:
    """Set improv widget defaults only if the user has not visited before."""
    migrate_legacy_session_keys(session_state)
    session_state.setdefault("improv_intelligence_tab", IMPROV_TAB_NAMES[0])
    session_state.setdefault("improv_entry_mode", IMPROV_ENTRY_MODES[0])
    if "improv_song_source" not in session_state:
        session_state["improv_song_source"] = (
            "Custom progression" if is_custom_active else "Active song"
        )
    session_state.setdefault("improv_chord_idx", 0)
    session_state.setdefault("improv_style", "Jazz Swing")
    session_state.setdefault("improv_style_key", "G")
    session_state.setdefault("improv_difficulty", "Intermediate")
    session_state.setdefault("improv_mood", "Mellow")
    session_state.setdefault("improv_style_bpm", 110)
    session_state.setdefault("improv_groove", "Medium")
    session_state.setdefault("improv_style_prompt", "")
    session_state.setdefault("improv_ensemble", "Jazz trio")
    session_state.setdefault("improv_jam_style", "Jazz Swing")
    session_state.setdefault("improv_jam_key", "Eb")
    session_state.setdefault("improv_jam_bpm", 120)
    session_state.setdefault("improv_jam_mood", "Dark")


def init_creative_lab_state(session_state: dict) -> None:
    session_state.setdefault(
        "creative_lab_analysis_mode",
        "Improvisation Intelligence",
    )
    session_state.setdefault("creative_arrangement_target_style", "Jobim / Bossa")
    session_state.setdefault("creative_arrangement_section_focus", "Full song")


def init_practice_page_state(session_state: dict) -> None:
    session_state.setdefault("practice_focus_section", "Full song")
    session_state.setdefault("practice_minutes", 30)


def init_backing_page_state(session_state: dict) -> None:
    session_state.setdefault("backing_track_scope", "Full song")
    session_state.setdefault("backing_track_loops", 2)
    session_state.setdefault("backing_quick_section", "Full song")


def init_analysis_page_state(session_state: dict) -> None:
    session_state.setdefault("analysis_mode", "Single recording")
    session_state.setdefault("analysis_recording_type", "Practice take")


def apply_improv_song_source(
    session_state: dict,
    source: str,
    *,
    set_catalog_source: Callable[[dict], None],
    set_custom_source: Callable[[dict], None],
) -> None:
    """Align global music source with Creative Lab song source choice."""
    session_state["improv_song_source"] = source
    if source == "Custom progression":
        set_custom_source(session_state)
    else:
        set_catalog_source(session_state)


def note_page_visit(session_state: dict, page_id: str) -> None:
    """Track visited pages (for debugging); does not reset other pages."""
    log = session_state.setdefault("_studio_pages_visited", [])
    if page_id not in log:
        log.append(page_id)


def setdefault_if_missing(session_state: dict, key: str, value: Any) -> None:
    if key not in session_state:
        session_state[key] = value

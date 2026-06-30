"""Persistent per-page UI state — defaults only when keys are missing (never on revisit)."""

from __future__ import annotations

from typing import Any, Callable

from music_theory import ENHARMONIC_MAJOR_KEYS

# Creative Lab — Improvisation Intelligence
IMPROV_TAB_NAMES: tuple[str, ...] = (
    "Entry & Jam",
    "Live Coach",
    "Phrase / Motif",
    "Missions",
    "Harmony Map",
    "Deep Harmony",
    "Metrics & AI",
)

IMPROV_SONG_SOURCES: tuple[str, ...] = ("Active song", "Custom progression")

IMPROV_ENTRY_MODES: tuple[str, ...] = (
    "Song-Based Improvisation",
    "Style Jam Mode",
    "Jam Session Generator",
)

# Major keys only — both flat and sharp spellings (C#/Db, D#/Eb, etc.).
CREATIVE_MAJOR_KEY_OPTIONS: tuple[str, ...] = tuple(ENHARMONIC_MAJOR_KEYS)

CREATIVE_BACKING_SONG_SOURCE_KEY = "creative_backing_song_source"
PENDING_IMPROV_SONG_SOURCE = "_pending_improv_song_source"
CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY = "creative_improv_intelligence_tab"

__all__ = (
    "CREATIVE_BACKING_SONG_SOURCE_KEY",
    "CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY",
    "CREATIVE_MAJOR_KEY_OPTIONS",
    "IMPROV_ENTRY_MODES",
    "IMPROV_SONG_SOURCES",
    "IMPROV_TAB_NAMES",
    "PENDING_IMPROV_SONG_SOURCE",
    "apply_improv_song_source",
    "ensure_improv_intelligence_tab_restored",
    "flush_pending_improv_song_source",
    "init_analysis_page_state",
    "init_backing_page_state",
    "init_creative_lab_state",
    "init_improvisation_state",
    "init_practice_page_state",
    "migrate_legacy_session_keys",
    "note_page_visit",
    "persist_improv_intelligence_tab",
    "resolve_improv_song_source",
    "setdefault_if_missing",
    "sync_improv_song_source_for_handoff",
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
    if "ii_selected_chord_index" not in session_state:
        if "improv_chord_idx" in session_state:
            session_state["ii_selected_chord_index"] = int(
                session_state.get("improv_chord_idx", 0)
            )
        legacy_ch = session_state.get("improv_selected_chord")
        if legacy_ch:
            session_state.setdefault("ii_selected_chord", legacy_ch)
            session_state.setdefault("ii_selected_chord_label", legacy_ch)
    session_state.pop("improv_chord_idx", None)
    session_state.pop("improv_selected_chord", None)


def init_improvisation_state(session_state: dict, *, is_custom_active: bool) -> None:
    """Set improv widget defaults only if the user has not visited before."""
    migrate_legacy_session_keys(session_state)
    try:
        from creative_session_state import (
            apply_creative_session_to_session,
            creative_session_is_active,
            get_creative_session,
        )

        _creative_sess = get_creative_session(session_state)
        if _creative_sess is not None and creative_session_is_active(session_state):
            apply_creative_session_to_session(session_state, _creative_sess)
    except ImportError:
        pass
    saved_tab = str(session_state.get(CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY) or "").strip()
    session_state.setdefault(
        CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY,
        saved_tab if saved_tab in IMPROV_TAB_NAMES else IMPROV_TAB_NAMES[0],
    )
    session_state.setdefault("improv_intelligence_tab", session_state[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY])
    if "improv_entry_mode" not in session_state:
        session_state["improv_entry_mode"] = IMPROV_ENTRY_MODES[0]
    if "improv_song_source" not in session_state:
        session_state["improv_song_source"] = (
            "Custom progression" if is_custom_active else "Active song"
        )
    session_state.setdefault("ii_selected_chord_index", 0)
    session_state.setdefault("ii_selected_chord", "")
    session_state.setdefault("ii_selected_section", "")
    session_state.setdefault("ii_selected_chord_label", "")
    session_state.setdefault("improv_motif_output_mode", "none")
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
    last = str(session_state.get("creative_lab_last_mode") or "").strip()
    if last:
        session_state.setdefault("creative_lab_analysis_mode", last)
    else:
        session_state.setdefault("creative_lab_analysis_mode", "Deep Harmonic Analyzer")
    session_state.setdefault(
        "creative_lab_last_mode",
        session_state.get("creative_lab_analysis_mode") or "Deep Harmonic Analyzer",
    )
    session_state.setdefault("creative_arrangement_target_style", "Jobim / Bossa")
    session_state.setdefault("creative_arrangement_section_focus", "Full song")


def init_practice_page_state(session_state: dict) -> None:
    try:
        from practice_studio import PRACTICE_FOCUS_FULL

        session_state.setdefault("practice_focus_section", PRACTICE_FOCUS_FULL)
    except ImportError:
        session_state.setdefault("practice_focus_section", "Full Song")


def init_backing_page_state(session_state: dict) -> None:
    try:
        from backing_track_state import has_restored_backing_canonical

        if has_restored_backing_canonical(session_state):
            return
    except ImportError:
        pass
    session_state.setdefault("backing_track_scope", "Full song")
    session_state.setdefault("backing_track_loops", 2)
    session_state.setdefault("backing_quick_section", "Full song")


def init_analysis_page_state(session_state: dict) -> None:
    session_state.setdefault("analysis_mode", "Single recording")
    session_state.setdefault("analysis_recording_type", "Practice take")
    session_state.setdefault("analysis_mission_ids", [])
    session_state.setdefault("analysis_sync_creative_mission", True)
    session_state.setdefault("analysis_custom_goal_enabled", False)
    session_state.setdefault("analysis_custom_goal", "")
    session_state.setdefault("improv_ai_metric_ids", [])
    session_state.setdefault("analysis_ai_metric_ids", [])


def resolve_improv_song_source(session_state: dict) -> str:
    """Read Creative song source without writing widget keys."""
    for key in (
        CREATIVE_BACKING_SONG_SOURCE_KEY,
        PENDING_IMPROV_SONG_SOURCE,
        "improv_song_source",
    ):
        val = str(session_state.get(key) or "").strip()
        if val:
            return val
    return "Active song"


def sync_improv_song_source_for_handoff(
    session_state: dict,
    source: str,
    *,
    set_catalog_source: Callable[[dict], None],
    set_custom_source: Callable[[dict], None],
) -> None:
    """Align music source for handoff — never writes widget-owned improv_song_source."""
    src = str(source or "Active song").strip() or "Active song"
    session_state[CREATIVE_BACKING_SONG_SOURCE_KEY] = src
    session_state[PENDING_IMPROV_SONG_SOURCE] = src
    if src == "Custom progression":
        set_custom_source(session_state)
    else:
        set_catalog_source(session_state)


def apply_improv_song_source(
    session_state: dict,
    source: str,
    *,
    set_catalog_source: Callable[[dict], None],
    set_custom_source: Callable[[dict], None],
    widget_safe: bool = False,
) -> None:
    """Align global music source with Creative Lab song source choice."""
    src = str(source or "Active song").strip() or "Active song"
    if widget_safe:
        sync_improv_song_source_for_handoff(
            session_state,
            src,
            set_catalog_source=set_catalog_source,
            set_custom_source=set_custom_source,
        )
        return
    session_state["improv_song_source"] = src
    session_state[CREATIVE_BACKING_SONG_SOURCE_KEY] = src
    if src == "Custom progression":
        set_custom_source(session_state)
    else:
        set_catalog_source(session_state)


def flush_pending_improv_song_source(session_state: dict) -> None:
    """Seed widget key from pending saved source before Creative widgets render."""
    pending = str(session_state.pop(PENDING_IMPROV_SONG_SOURCE, None) or "").strip()
    if not pending:
        return
    session_state.setdefault("improv_song_source", pending)
    session_state[CREATIVE_BACKING_SONG_SOURCE_KEY] = pending


def ensure_improv_intelligence_tab_restored(session_state: dict) -> str:
    """Restore Improvisation Intelligence sub-tab before the radio renders."""
    last = str(session_state.get(CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY) or "").strip()
    current = str(session_state.get("improv_intelligence_tab") or "").strip()
    if last and last in IMPROV_TAB_NAMES and last != current:
        session_state["improv_intelligence_tab"] = last
        return last
    if current and current in IMPROV_TAB_NAMES:
        session_state[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = current
        return current
    if last and last in IMPROV_TAB_NAMES:
        session_state["improv_intelligence_tab"] = last
        return last
    default = IMPROV_TAB_NAMES[0]
    session_state["improv_intelligence_tab"] = default
    session_state[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = default
    return default


def persist_improv_intelligence_tab(session_state: dict) -> str:
    """Persist sub-tab to a non-widget key (safe after radio renders)."""
    tab = str(session_state.get("improv_intelligence_tab") or "").strip()
    if not tab:
        tab = str(session_state.get(CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY) or "").strip()
    if tab and tab in IMPROV_TAB_NAMES:
        session_state[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = tab
    return tab


def note_page_visit(session_state: dict, page_id: str) -> None:
    """Track visited pages (for debugging); does not reset other pages."""
    log = session_state.setdefault("_studio_pages_visited", [])
    if page_id not in log:
        log.append(page_id)


def setdefault_if_missing(session_state: dict, key: str, value: Any) -> None:
    if key not in session_state:
        session_state[key] = value

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
    "ensure_improv_entry_mode_restored",
    "ensure_creative_widgets_from_backing_context",
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
    "resolve_improv_song_preview",
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
            apply_creative_session_to_session(
                session_state,
                _creative_sess,
                widget_safe=bool(session_state.get("display_key")),
            )
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
    try:
        from source_session_state import SBI_PREVIEW_SOURCE_KEY, set_sbi_preview_source

        if SBI_PREVIEW_SOURCE_KEY not in session_state:
            set_sbi_preview_source(
                session_state,
                str(session_state.get("improv_song_source") or "Active song"),
            )
    except ImportError:
        pass
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
    live = str(session_state.get("creative_lab_analysis_mode") or "").strip()
    if last:
        if not live:
            session_state["creative_lab_analysis_mode"] = last
    elif not live:
        session_state.setdefault("creative_lab_analysis_mode", "Deep Harmonic Analyzer")
    session_state.setdefault(
        "creative_lab_last_mode",
        session_state.get("creative_lab_analysis_mode") or last or "Deep Harmonic Analyzer",
    )
    session_state.setdefault("creative_arrangement_target_style", "Jobim / Bossa")
    session_state.setdefault("creative_arrangement_section_focus", "Full song")


def init_practice_page_state(session_state: dict) -> None:
    try:
        from music_workspace_hydration import workspace_blob_hydrated

        if not workspace_blob_hydrated(session_state) and session_state.get(
            "_music_workspace_hydration_started"
        ):
            return
    except ImportError:
        pass
    if session_state.get("_music_authoritative_cloud_apply"):
        return
    try:
        from practice_workspace_persistence import practice_workspace_restored

        if practice_workspace_restored(session_state):
            return
    except ImportError:
        pass
    if isinstance(session_state.get("practice_workspace_state"), dict) and str(
        (session_state.get("practice_workspace_state") or {}).get("selected_practice_tool") or ""
    ).strip():
        return
    try:
        from practice_studio import PRACTICE_FOCUS_FULL

        session_state.setdefault("practice_focus_section", PRACTICE_FOCUS_FULL)
    except ImportError:
        session_state.setdefault("practice_focus_section", "Full Song")
    if "practice_active_tool" not in session_state:
        session_state["practice_active_tool"] = ""


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
    """Read SBI preview song source (preview bucket — not handoff keys)."""
    try:
        from source_session_state import get_sbi_preview_source

        return get_sbi_preview_source(session_state)
    except ImportError:
        val = str(session_state.get("improv_song_source") or "").strip()
        if val in IMPROV_SONG_SOURCES:
            return val
        return "Active song"


def resolve_improv_song_preview(session_state: dict) -> dict[str, Any]:
    """SBI song card preview — isolated catalog/custom session buckets."""
    try:
        from source_session_state import resolve_sbi_preview

        return resolve_sbi_preview(session_state)
    except ImportError:
        return {
            "source": resolve_improv_song_source(session_state),
            "title": "Active song",
            "artist": "",
            "display_key": "C",
            "sections": {},
        }


def sync_improv_song_source_for_handoff(
    session_state: dict,
    source: str,
    *,
    set_catalog_source: Callable[[dict], None],
    set_custom_source: Callable[[dict], None],
) -> None:
    """Align global music source when opening Practice/Backing from SBI."""
    src = str(source or "Active song").strip() or "Active song"
    try:
        from source_session_state import set_sbi_preview_source

        set_sbi_preview_source(session_state, src)
    except ImportError:
        pass
    session_state[CREATIVE_BACKING_SONG_SOURCE_KEY] = src
    session_state[PENDING_IMPROV_SONG_SOURCE] = src
    session_state["improv_song_source"] = src
    if src == "Custom progression":
        set_custom_source(session_state)
    else:
        set_catalog_source(session_state)
        try:
            from songs.music_source import restore_catalog_identity_from_snapshot

            restore_catalog_identity_from_snapshot(session_state)
        except ImportError:
            pass


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
        try:
            from source_session_state import set_sbi_preview_source

            set_sbi_preview_source(session_state, src)
        except ImportError:
            pass
        session_state[PENDING_IMPROV_SONG_SOURCE] = src
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
    try:
        from source_session_state import set_sbi_preview_source

        set_sbi_preview_source(session_state, pending)
    except ImportError:
        pass


def ensure_improv_intelligence_tab_restored(session_state: dict) -> str:
    """Restore Improvisation Intelligence sub-tab before the radio renders."""
    _tab_trace_before = None
    try:
        from creative_return_trace import snapshot_improv_selector_render_state, trace_improv_selector_restore

        _tab_trace_before = snapshot_improv_selector_render_state(session_state)
        trace_improv_selector_restore(
            session_state,
            "BEFORE_ENSURE_IMPROV_INTELLIGENCE_TAB_RESTORED",
            before=_tab_trace_before,
        )
    except ImportError:
        pass
    try:
        from creative_tab_tool_persistence import (
            canonical_creative_selector_value,
            hydrate_improv_intelligence_tab_from_canonical,
            project_startup_default_selector,
            selector_hydration_complete,
        )

        canon_tab = hydrate_improv_intelligence_tab_from_canonical(session_state)
        if canon_tab:
            try:
                from creative_return_trace import snapshot_improv_selector_render_state, trace_improv_selector_restore

                trace_improv_selector_restore(
                    session_state,
                    "AFTER_ENSURE_IMPROV_INTELLIGENCE_TAB_RESTORED",
                    before=_tab_trace_before,
                    after=snapshot_improv_selector_render_state(session_state),
                    returned=canon_tab,
                )
            except ImportError:
                pass
            return canon_tab
        canon = canonical_creative_selector_value(session_state, "improv_intelligence_tab")
        if canon:
            session_state["improv_intelligence_tab"] = canon
            session_state[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = canon
            try:
                from creative_return_trace import snapshot_improv_selector_render_state, trace_improv_selector_restore

                trace_improv_selector_restore(
                    session_state,
                    "AFTER_ENSURE_IMPROV_INTELLIGENCE_TAB_RESTORED",
                    before=_tab_trace_before,
                    after=snapshot_improv_selector_render_state(session_state),
                    returned=canon,
                )
            except ImportError:
                pass
            return canon
        if not selector_hydration_complete(session_state):
            _ret = str(session_state.get("improv_intelligence_tab") or "").strip()
            try:
                from creative_return_trace import snapshot_improv_selector_render_state, trace_improv_selector_restore

                trace_improv_selector_restore(
                    session_state,
                    "AFTER_ENSURE_IMPROV_INTELLIGENCE_TAB_RESTORED",
                    before=_tab_trace_before,
                    after=snapshot_improv_selector_render_state(session_state),
                    returned=_ret,
                )
            except ImportError:
                pass
            return _ret
    except ImportError:
        pass
    if session_state.get("_improv_tab_user_touched"):
        current = str(session_state.get("improv_intelligence_tab") or "").strip()
        if current in IMPROV_TAB_NAMES:
            session_state[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = current
            return current
    restoring_from_backing = bool(session_state.get("_creative_restore_from_backing"))
    backing_entry = _active_creative_backing_entry_mode(session_state)
    if backing_entry and restoring_from_backing:
        try:
            from backing_context import active_creative_backing_context

            ctx = active_creative_backing_context(session_state)
            src = str(getattr(ctx, "source", "") or "").strip() if ctx is not None else ""
        except ImportError:
            src = ""
        tab = "Missions" if src == "mission" else "Entry & Jam"
        try:
            from session_widget_safe import PENDING_IMPROV_INTELLIGENCE_TAB_KEY

            session_state.pop(PENDING_IMPROV_INTELLIGENCE_TAB_KEY, None)
        except ImportError:
            session_state.pop("_pending_improv_intelligence_tab", None)
        if str(session_state.get("improv_intelligence_tab") or "").strip() != tab:
            session_state["improv_intelligence_tab"] = tab
        session_state[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = tab
        return tab
    try:
        from session_widget_safe import PENDING_IMPROV_INTELLIGENCE_TAB_KEY
    except ImportError:
        PENDING_IMPROV_INTELLIGENCE_TAB_KEY = "_pending_improv_intelligence_tab"  # type: ignore[misc,assignment]
    pending_tab = str(session_state.pop(PENDING_IMPROV_INTELLIGENCE_TAB_KEY, None) or "").strip()
    if pending_tab and pending_tab in IMPROV_TAB_NAMES:
        session_state["improv_intelligence_tab"] = pending_tab
        session_state[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = pending_tab
        return pending_tab
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
    try:
        from creative_tab_tool_persistence import project_startup_default_selector, selector_hydration_complete

        if selector_hydration_complete(session_state):
            projected = project_startup_default_selector(session_state, "improv_intelligence_tab", IMPROV_TAB_NAMES[0])
            if projected:
                session_state[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = projected
                return projected
    except ImportError:
        pass
    default = IMPROV_TAB_NAMES[0]
    session_state["improv_intelligence_tab"] = default
    session_state[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = default
    return default


_BACKING_SOURCE_TO_ENTRY_MODE: dict[str, str] = {
    "song_improv": "Song-Based Improvisation",
    "mission": "Song-Based Improvisation",
}


def _active_creative_backing_entry_mode(session_state: dict) -> str:
    """Entry mode dictated by an active entry_jam/song_improv/mission backing context."""
    try:
        from backing_context import active_creative_backing_context
    except ImportError:
        return ""
    ctx = active_creative_backing_context(session_state)
    if ctx is None:
        return ""
    src = str(getattr(ctx, "source", "") or "").strip()
    if src == "entry_jam":
        try:
            from backing_source_navigation import resolve_entry_jam_entry_mode

            return resolve_entry_jam_entry_mode(session_state, ctx=ctx)
        except ImportError:
            entry = str(getattr(ctx, "entry_mode", "") or "").strip()
            if entry in IMPROV_ENTRY_MODES and entry != "Song-Based Improvisation":
                return entry
            return "Style Jam Mode"
    return _BACKING_SOURCE_TO_ENTRY_MODE.get(src, "")


def ensure_creative_widgets_from_backing_context(
    session_state: dict,
    *,
    restoring_from_backing: bool = False,
) -> bool:
    """Force Entry & Jam tab + entry-mode radio to match active Creative backing context.

    Only overrides widgets when returning from Backing Studio — not on a plain refresh,
    so creative_session / user entry-mode choices stay durable.
    """
    if not restoring_from_backing:
        return False
    entry = _active_creative_backing_entry_mode(session_state)
    if not entry:
        return False
    try:
        from backing_context import active_creative_backing_context

        ctx = active_creative_backing_context(session_state)
        src = str(getattr(ctx, "source", "") or "").strip() if ctx is not None else ""
    except ImportError:
        src = ""
    tab = "Missions" if src == "mission" else "Entry & Jam"
    if str(session_state.get("improv_intelligence_tab") or "").strip() != tab:
        session_state["improv_intelligence_tab"] = tab
    session_state[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = tab
    session_state["_improv_tab_user_touched"] = False
    if str(session_state.get("improv_entry_mode") or "").strip() != entry:
        session_state["improv_entry_mode"] = entry
    try:
        from session_widget_safe import (
            PENDING_IMPROV_ENTRY_MODE_KEY,
            PENDING_IMPROV_INTELLIGENCE_TAB_KEY,
        )

        session_state.pop(PENDING_IMPROV_ENTRY_MODE_KEY, None)
        session_state.pop(PENDING_IMPROV_INTELLIGENCE_TAB_KEY, None)
    except ImportError:
        session_state.pop("_pending_improv_entry_mode", None)
        session_state.pop("_pending_improv_intelligence_tab", None)
    return True


def ensure_improv_entry_mode_restored(session_state: dict) -> str:
    """Restore Entry / Style Jam / SBI radio before the entry-mode widget renders."""
    _entry_before = None

    def _done(result: str) -> str:
        try:
            from creative_return_trace import snapshot_improv_selector_render_state, trace_improv_selector_restore

            trace_improv_selector_restore(
                session_state,
                "AFTER_ENSURE_IMPROV_ENTRY_MODE_RESTORED",
                before=_entry_before,
                after=snapshot_improv_selector_render_state(session_state),
                returned=result,
            )
        except ImportError:
            pass
        return result

    try:
        from creative_return_trace import snapshot_improv_selector_render_state, trace_improv_selector_restore

        _entry_before = snapshot_improv_selector_render_state(session_state)
        trace_improv_selector_restore(
            session_state,
            "BEFORE_ENSURE_IMPROV_ENTRY_MODE_RESTORED",
            before=_entry_before,
        )
    except ImportError:
        pass
    try:
        from creative_tab_tool_persistence import (
            canonical_creative_selector_value,
            project_startup_default_selector,
            selector_hydration_complete,
        )

        canon = canonical_creative_selector_value(session_state, "improv_entry_mode")
        if canon:
            if str(session_state.get("improv_entry_mode") or "").strip() != canon:
                session_state["improv_entry_mode"] = canon
            return _done(canon)
        if not selector_hydration_complete(session_state):
            return _done(str(session_state.get("improv_entry_mode") or "").strip())
    except ImportError:
        pass
    if session_state.get("_improv_tab_user_touched"):
        current = str(session_state.get("improv_entry_mode") or "").strip()
        if current in IMPROV_ENTRY_MODES:
            return _done(current)
    page = str(session_state.get("studio_page") or "").strip().lower()
    if page == "creative" and not session_state.get("_creative_restore_from_backing"):
        try:
            from creative_session_state import get_creative_session

            sess = get_creative_session(session_state)
            if sess is not None:
                entry = str(sess.entry_mode or "").strip()
                if entry in IMPROV_ENTRY_MODES and sess.tool_type in {
                    "entry_style_jam",
                    "jam_session_generator",
                }:
                    if str(session_state.get("improv_entry_mode") or "").strip() != entry:
                        session_state["improv_entry_mode"] = entry
                    return _done(entry)
        except ImportError:
            pass
    backing_entry = _active_creative_backing_entry_mode(session_state)
    if backing_entry and session_state.get("_creative_restore_from_backing"):
        try:
            from session_widget_safe import PENDING_IMPROV_ENTRY_MODE_KEY

            session_state.pop(PENDING_IMPROV_ENTRY_MODE_KEY, None)
        except ImportError:
            session_state.pop("_pending_improv_entry_mode", None)
        if str(session_state.get("improv_entry_mode") or "").strip() != backing_entry:
            session_state["improv_entry_mode"] = backing_entry
        return _done(backing_entry)
    try:
        from session_widget_safe import PENDING_IMPROV_ENTRY_MODE_KEY
    except ImportError:
        PENDING_IMPROV_ENTRY_MODE_KEY = "_pending_improv_entry_mode"  # type: ignore[misc,assignment]
    pending_entry = str(session_state.pop(PENDING_IMPROV_ENTRY_MODE_KEY, None) or "").strip()
    if pending_entry and pending_entry in IMPROV_ENTRY_MODES:
        session_state["improv_entry_mode"] = pending_entry
        return _done(pending_entry)
    current = str(session_state.get("improv_entry_mode") or "").strip()
    if session_state.get("_improv_tab_user_touched") and current in IMPROV_ENTRY_MODES:
        return _done(current)
    jam = session_state.get("improv_jam_session")
    has_jam_sections = isinstance(jam, dict) and bool(jam.get("sections"))
    if has_jam_sections and current == "Jam Session Generator":
        return _done(current)
    if has_jam_sections and current not in IMPROV_ENTRY_MODES:
        session_state["improv_entry_mode"] = "Jam Session Generator"
        return _done("Jam Session Generator")
    try:
        from creative_session_state import get_creative_session

        sess = get_creative_session(session_state)
        if sess is not None:
            entry = str(sess.entry_mode or "").strip()
            if entry in IMPROV_ENTRY_MODES:
                if has_jam_sections and entry == "Style Jam Mode":
                    session_state["improv_entry_mode"] = "Jam Session Generator"
                    return _done("Jam Session Generator")
                if current != entry:
                    session_state["improv_entry_mode"] = entry
                return _done(entry)
    except ImportError:
        pass
    current = str(session_state.get("improv_entry_mode") or "").strip()
    if current in IMPROV_ENTRY_MODES:
        return _done(current)
    try:
        from creative_tab_tool_persistence import project_startup_default_selector, selector_hydration_complete

        if selector_hydration_complete(session_state):
            projected = project_startup_default_selector(
                session_state, "improv_entry_mode", IMPROV_ENTRY_MODES[0]
            )
            if projected:
                return _done(projected)
    except ImportError:
        pass
    default = IMPROV_ENTRY_MODES[0]
    session_state["improv_entry_mode"] = default
    return _done(default)


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
    prev = str(session_state.get("_last_studio_page_for_hydrate") or "").strip()
    if prev and prev != page_id:
        for key in list(session_state.keys()):
            if str(key).startswith("_creative_session_hydrated_"):
                session_state.pop(key, None)
    session_state["_last_studio_page_for_hydrate"] = page_id
    log = session_state.setdefault("_studio_pages_visited", [])
    if page_id not in log:
        log.append(page_id)


def setdefault_if_missing(session_state: dict, key: str, value: Any) -> None:
    if key not in session_state:
        session_state[key] = value

"""Creative → Entry & Jam → Song-Based Improvisation as one navigation (shared helper).

Choosing Song-Based Improvisation by hand takes two clicks — the Improvisation Intelligence
tab radio ("Entry & Jam") and the entry-mode radio ("Song-Based Improvisation") — and each
radio's ``on_change`` runs side effects: navigation history, Creative selector persistence,
workflow ownership, releasing a Mission's page ownership and the Song-Based entry defaults.
:func:`request_song_based_improvisation` performs that same navigation in one step, for a
feature that sends the musician there (Song-Aware Coaching's "Continue in Song-Based
Improvisation"), and :func:`apply_song_based_entry` is the Song-Based part the entry-mode
radio itself runs.

Both are meant for widget callbacks (they run before the next script run renders widgets, so
assigning the tab and entry-mode values is safe). Nothing here starts playback, writes the
Practice Key, instrument or Practice Focus, or touches Backing / Key Cycling transport.
"""

from __future__ import annotations

from typing import Any

SBI_TAB = "Entry & Jam"
SBI_ENTRY_MODE = "Song-Based Improvisation"
SBI_HISTORY_DESTINATION = "creative::SBI"


def apply_song_based_entry(
    session: dict[str, Any],
    *,
    release_reason: str = "entry_mode_song_based",
    defaults_source: str = "entry_mode_song_based",
) -> None:
    """What choosing Song-Based Improvisation does: a Mission's Creative page ownership is
    released (Entry & Jam stays the tab) and the Song-Based entry defaults (full-song scope)
    are applied. This is the entry-mode radio's own Song-Based branch."""
    try:
        from backing_source_navigation import release_mission_creative_page_ownership

        release_mission_creative_page_ownership(session, reason=release_reason, force_entry_jam_tab=True)
    except ImportError:
        session.pop("improv_mission_backing_handoff", None)
        session["_backing_released_specialized_context"] = True
    try:
        from song_improv_scope_authority import apply_song_improv_entry_defaults

        apply_song_improv_entry_defaults(session, source=defaults_source)
    except ImportError:
        pass


def request_song_based_improvisation(
    session: dict[str, Any],
    reason: str,
    *,
    sync_source_to_global_owner: bool = False,
) -> bool:
    """Go to Entry & Jam → Song-Based Improvisation as if the musician had chosen the tab and
    the entry mode, with one Back step to where they were.

    ``sync_source_to_global_owner`` also returns the Song source lane to the app's global
    owner (the active song, Custom progression or Composition), dropping any temporary
    Creative preview — the same reset the app applies when the musician enters Creative from
    another page. Returns ``False`` (and changes nothing) outside the Creative page."""
    if str(session.get("studio_page") or "").strip() != "creative":
        return False
    try:
        from studio_page_state import CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY
    except ImportError:
        CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY = "creative_improv_intelligence_tab"  # type: ignore[misc]
    previous_tab = str(session.get(CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY) or session.get("improv_intelligence_tab") or "").strip()
    previous_mode = str(session.get("improv_entry_mode") or "").strip()
    previous_dest = str(session.get("_history_live_creative_dest") or "").strip()

    # The new workspace, as the two radios would leave it.
    session["improv_intelligence_tab"] = SBI_TAB
    session[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = SBI_TAB
    session["_improv_intelligence_tab_for_render"] = SBI_TAB
    session["improv_entry_mode"] = SBI_ENTRY_MODE
    try:
        from session_widget_safe import PENDING_IMPROV_ENTRY_MODE_KEY, PENDING_IMPROV_INTELLIGENCE_TAB_KEY

        session.pop(PENDING_IMPROV_INTELLIGENCE_TAB_KEY, None)  # an older queued choice must not win
        session.pop(PENDING_IMPROV_ENTRY_MODE_KEY, None)
    except ImportError:
        pass
    try:
        from songs.picker_session import mark_improv_tab_user_touched

        mark_improv_tab_user_touched(session)
    except ImportError:
        session["_improv_tab_user_touched"] = True

    # One Back step to the previous workspace. This is an explicit request, not a widget
    # remount echo: a Back restore's seal (which reverts remount snaps) must not cancel it.
    try:
        from studio_nav_history import clear_creative_history_seal, record_creative_workspace_change

        clear_creative_history_seal(session)
        session.pop("_pending_history_creative_dest", None)  # armed by the seal for re-application
        record_creative_workspace_change(
            session, previous_tab=previous_tab, previous_entry_mode=previous_mode, previous_destination=previous_dest,
        )
    except ImportError:
        pass

    # Workflow ownership and Creative selector persistence (tab radio + entry-mode radio).
    try:
        from music_workflow_creative_nav import sync_workflow_for_creative_tab

        sync_workflow_for_creative_tab(session, SBI_TAB)
    except ImportError:
        pass
    try:
        from creative_tab_tool_persistence import handle_user_creative_selector_change

        handle_user_creative_selector_change(session, "improv_entry_mode")
    except ImportError:
        pass
    try:
        from creative_session_state import sync_creative_session_before_persist

        sync_creative_session_before_persist(session)
    except ImportError:
        pass
    try:
        from music_workflow_pending_activation import queue_workflow_activation_for_entry_mode

        queue_workflow_activation_for_entry_mode(session)
    except ImportError:
        pass

    apply_song_based_entry(session, release_reason=f"song_based_request:{reason}")

    if sync_source_to_global_owner:
        try:
            from source_session_state import reset_creative_source_to_global_owner

            reset_creative_source_to_global_owner(session)
        except ImportError:
            pass

    session["_history_prev_entry_mode"] = SBI_ENTRY_MODE
    try:
        from studio_nav_history import sync_live_creative_history_dest

        sync_live_creative_history_dest(session)
    except ImportError:
        pass
    session["_song_based_request_reason"] = str(reason or "")
    return True


__all__ = [
    "SBI_ENTRY_MODE",
    "SBI_HISTORY_DESTINATION",
    "SBI_TAB",
    "apply_song_based_entry",
    "request_song_based_improvisation",
]

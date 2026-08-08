"""Sidebar Song-Based / Mission practice key — capture intent + pre-widget apply."""

from __future__ import annotations

import logging
from typing import Any

_LOG = logging.getLogger("music.song_practice_key_change")

SONG_PRACTICE_KEY_EDIT_OUTCOME_KEY = "_music_song_practice_key_edit_outcome"


def _widgets_locked(session: dict[str, Any]) -> bool:
    try:
        from session_widget_safe import widgets_likely_instantiated

        return bool(widgets_likely_instantiated(session))
    except ImportError:
        return bool(session.get("_streamlit_widgets_locked_this_run"))


def sidebar_song_practice_key_mutation_deferred(session: dict[str, Any]) -> bool:
    """True when blob mutation must wait for pre-widget consume."""
    try:
        from music_workflow_pending_song_practice_key_edit import peek_pending_song_practice_key_edit

        if peek_pending_song_practice_key_edit(session):
            return True
    except ImportError:
        pass
    return _widgets_locked(session)


def finalize_sidebar_song_practice_key_after_mutation(
    session: dict[str, Any],
    new_key: str,
    *,
    st_like: Any | None = None,
) -> None:
    """Legacy session + backing sync after canonical practice key commit."""
    session["concert_key"] = new_key
    try:
        from improvisation_missions import MISSION_EXAMPLE_KEY, MISSIONS_GENERATE_CONTEXT_KEY

        session.pop(MISSIONS_GENERATE_CONTEXT_KEY, None)
        session.pop(MISSION_EXAMPLE_KEY, None)
        session.pop("_mission_example_output_fp", None)
        session.pop("_mission_example_material_fp", None)
    except ImportError:
        session.pop("_missions_tab_generate_context", None)
        session.pop("improv_mission_example", None)
    try:
        from music_workflow_mutation import _invalidate_mission_chord_dependent_session

        _invalidate_mission_chord_dependent_session(session, new_chord=str(new_key or ""))
    except ImportError:
        pass
    try:
        from mission_practice_context import ensure_mission_practice_context

        ensure_mission_practice_context(session, force=True)
    except ImportError:
        pass
    try:
        from music_workflow_song_practice import rehydrate_full_song_concert_sections

        rehydrate_full_song_concert_sections(session, source="sidebar_song_practice_key_finalize")
    except ImportError:
        pass
    try:
        from music_workflow_legacy_projection import project_active_blob_to_legacy_session
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if ptr and str(ptr.workflow_owner or "") in {"mission_jam", "song_based_improvisation"}:
            blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
            if blob is not None:
                project_active_blob_to_legacy_session(session, blob)
    except ImportError:
        pass
    try:
        from backing_context import sync_improv_widgets_from_live_concert_key

        sync_improv_widgets_from_live_concert_key(session)
    except ImportError:
        pass
    try:
        from backing_musical_state import clear_stale_chart_session_keys
        from songs.key_state import BACKING_NEEDS_REGEN, invalidate_backing_cache

        clear_stale_chart_session_keys(session)
        if st_like is not None:
            invalidate_backing_cache(st_like)
        session[BACKING_NEEDS_REGEN] = True
    except ImportError:
        pass
    try:
        from creative_key_sync import invalidate_creative_backing_context

        invalidate_creative_backing_context(session)
    except ImportError:
        pass
    try:
        from creative_key_sync import _apply_pending_backing_context_on_page

        _apply_pending_backing_context_on_page(session, st_like=st_like)
    except ImportError:
        pass
    try:
        from creative_session_state import sync_creative_session_from_session

        sync_creative_session_from_session(session)
    except ImportError:
        pass


def capture_sidebar_song_practice_key_edit_intent(session: dict[str, Any]) -> bool:
    """Sidebar callback — queue only; canonical mutation runs pre-widget next run."""
    requested = str(session.get("display_key") or "").strip()
    if not requested:
        return False
    try:
        from music_workflow_state_store import get_active_workflow_pointer
    except ImportError:
        return False
    ptr = get_active_workflow_pointer(session)
    if not ptr or str(ptr.workflow_owner or "") not in {"song_based_improvisation", "mission_jam"}:
        return False
    try:
        from music_workflow_pending_song_practice_key_edit import queue_pending_song_practice_key_edit

        pending = queue_pending_song_practice_key_edit(
            session,
            selected_key_token=requested,
            workflow_owner=str(ptr.workflow_owner or ""),
            workflow_session_id=str(ptr.workflow_session_id or ""),
        )
        if not pending:
            return False
        _LOG.info(
            "[song_practice_key_change] intent_captured seq=%s owner=%s key=%s locked=%s",
            pending.get("request_seq"),
            pending.get("workflow_owner"),
            requested,
            _widgets_locked(session),
        )
        return True
    except ImportError:
        return False


def apply_pending_song_practice_key_edit_pre_widget(
    session: dict[str, Any],
    pending: dict[str, Any],
    *,
    st_like: Any | None = None,
) -> bool:
    requested = str(pending.get("selected_key_token") or "").strip()
    if not requested:
        return False
    try:
        from music_workflow_mutation import update_active_practice_key

        result = update_active_practice_key(
            session,
            requested,
            source="sidebar_song_improv",
            transpose_progression=True,
        )
        if not result.ok:
            session[SONG_PRACTICE_KEY_EDIT_OUTCOME_KEY] = {
                "canonical_commit": "FAIL",
                "error_code": result.error_code,
            }
            _LOG.info("[song_practice_key_change] mutation_failed %s", result.error_code)
            return False
    except ImportError:
        return False
    session[SONG_PRACTICE_KEY_EDIT_OUTCOME_KEY] = {"canonical_commit": "SUCCESS"}
    finalize_sidebar_song_practice_key_after_mutation(session, requested, st_like=st_like)
    try:
        from song_creative_focus import retarget_song_creative_focus_after_practice_key_change

        retarget_song_creative_focus_after_practice_key_change(session)
    except ImportError:
        pass
    return True


__all__ = [
    "SONG_PRACTICE_KEY_EDIT_OUTCOME_KEY",
    "apply_pending_song_practice_key_edit_pre_widget",
    "capture_sidebar_song_practice_key_edit_intent",
    "finalize_sidebar_song_practice_key_after_mutation",
    "sidebar_song_practice_key_mutation_deferred",
]

"""Canonical Song-Based Improvisation playback / practice section scope (Full Song default)."""

from __future__ import annotations

from typing import Any

SONG_IMPROV_PLAYBACK_FULL = "Full song"
PRACTICE_FOCUS_FULL_SONG = "Full Song"

_SCOPE_RESET_SOURCES = frozenset(
    {
        "return_from_backing",
        "creative_return_consume",
        "creative_return_entry_jam",
        "catalog_handoff",
        "picker_to_creative_handoff",
        "entry_mode_song_based",
        "creative_pre_widget",
        "creative_tab_change",
        "post_workflow_activation",
        "missions_tab_entry_jam_parent_key",
        "song_improv_entry_hydrate",
    }
)


def apply_song_improv_entry_defaults(session: dict[str, Any], *, source: str) -> None:
    """Reset backing + practice section scope to Full Song for Song-Based entry."""
    reset_song_improv_playback_scope(session, source=source)
    try:
        from practice_studio import PRACTICE_FOCUS_FULL

        session["practice_focus_section"] = PRACTICE_FOCUS_FULL
    except ImportError:
        session["practice_focus_section"] = PRACTICE_FOCUS_FULL_SONG
    try:
        from practice_state import normalize_practice_focus_section, write_canonical_practice_state

        focus = normalize_practice_focus_section(session.get("practice_focus_section"))
        canonical = {
            "practice_focus_section": focus,
        }
        write_canonical_practice_state(session, canonical, reason=f"song_improv_scope:{source}", local_edit=False)
    except ImportError:
        pass
    _persist_playback_scope_on_blob(session, SONG_IMPROV_PLAYBACK_FULL)


def reset_song_improv_playback_scope(session: dict[str, Any], *, source: str) -> None:
    try:
        from backing_track_state import reset_backing_playback_scope_to_full_song

        reset_backing_playback_scope_to_full_song(session, source=source)
    except ImportError:
        session["backing_track_scope"] = SONG_IMPROV_PLAYBACK_FULL
        session.pop("backing_track_single_section", None)
        session.pop("backing_track_multi_sections", None)
    session["_song_improv_scope_last_reset_source"] = str(source or "")


def should_apply_song_improv_entry_defaults(session: dict[str, Any], *, activation_source: str) -> bool:
    src = str(activation_source or "").strip()
    if src in _SCOPE_RESET_SOURCES:
        return True
    if src.startswith("song_improv_scope"):
        return True
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and str(ctx.source or "") == "song_improv" and src == "pending_consume":
            return True
    except ImportError:
        pass
    return False


def ensure_song_improv_scope_on_entry_mode(session: dict[str, Any]) -> None:
    entry = str(session.get("improv_entry_mode") or "").strip()
    if entry != "Song-Based Improvisation":
        return
    flag = "_song_improv_entry_defaults_for_seq"
    seq = int(session.get("_script_run_seq") or 0)
    if session.get(flag) == seq:
        return
    apply_song_improv_entry_defaults(session, source="song_improv_entry_hydrate")
    session[flag] = seq


def _persist_playback_scope_on_blob(session: dict[str, Any], scope: str) -> None:
    try:
        from music_workflow_song_practice import song_based_blob_session_id
        from music_workflow_state_store import get_workflow_blob, save_workflow_blob

        sid = song_based_blob_session_id(session)
        blob = get_workflow_blob(session, "song_based_improvisation", sid)
        if blob is None:
            return
        blob.playback_scope = str(scope or SONG_IMPROV_PLAYBACK_FULL)
        save_workflow_blob(session, blob, source="song_improv_scope_authority")
    except ImportError:
        pass


def restore_song_improv_creative_navigation(session: dict[str, Any]) -> None:
    """Return / handoff: Song-Based on Entry & Jam — not stale Missions tab."""
    session["improv_entry_mode"] = "Song-Based Improvisation"
    session["improv_intelligence_tab"] = "Entry & Jam"
    try:
        from studio_page_state import CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY

        session[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = "Entry & Jam"
    except ImportError:
        pass


__all__ = [
    "PRACTICE_FOCUS_FULL_SONG",
    "SONG_IMPROV_PLAYBACK_FULL",
    "apply_song_improv_entry_defaults",
    "ensure_song_improv_scope_on_entry_mode",
    "reset_song_improv_playback_scope",
    "restore_song_improv_creative_navigation",
    "should_apply_song_improv_entry_defaults",
]

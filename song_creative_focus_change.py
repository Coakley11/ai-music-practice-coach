"""Capture + pre-widget apply for shared SongCreativeFocus edits."""

from __future__ import annotations

import logging
from typing import Any

_LOG = logging.getLogger("music.song_creative_focus")

SONG_CREATIVE_FOCUS_EDIT_OUTCOME_KEY = "_music_song_creative_focus_edit_outcome"


def _widgets_locked(session: dict[str, Any]) -> bool:
    try:
        from music_workflow_pre_widget_bootstrap import PRE_WIDGET_BOOTSTRAP_ACTIVE_KEY

        if session.get(PRE_WIDGET_BOOTSTRAP_ACTIVE_KEY):
            return False
    except ImportError:
        pass
    try:
        from session_widget_safe import widgets_likely_instantiated

        return bool(widgets_likely_instantiated(session))
    except ImportError:
        return bool(session.get("_streamlit_widgets_locked_this_run"))


def commit_song_creative_focus_selection(
    session: dict[str, Any],
    *,
    section: str,
    concert_chord: str,
    chord_index: int,
    source_page: str,
    written_chord: str = "",
) -> dict[str, Any] | None:
    from song_creative_focus import build_song_creative_focus, commit_song_creative_focus, resolve_focus_against_progression

    focus = build_song_creative_focus(
        session,
        section=section,
        concert_chord=concert_chord,
        chord_index=int(chord_index),
        source_page=source_page,
        written_chord=written_chord,
    )
    focus = resolve_focus_against_progression(session, focus)
    commit_song_creative_focus(session, focus)
    session[SONG_CREATIVE_FOCUS_EDIT_OUTCOME_KEY] = {"result": "committed", "revision": focus.get("revision")}
    return focus


def capture_song_creative_focus_intent(
    session: dict[str, Any],
    *,
    section: str,
    concert_chord: str,
    chord_index: int,
    source_page: str,
    written_chord: str = "",
) -> bool:
    if _widgets_locked(session):
        try:
            from music_workflow_pending_song_creative_focus_edit import queue_pending_song_creative_focus_edit

            pending = queue_pending_song_creative_focus_edit(
                session,
                section=section,
                concert_chord=concert_chord,
                chord_index=int(chord_index),
                source_page=source_page,
                written_chord=written_chord,
            )
            return bool(pending)
        except ImportError:
            pass
    commit_song_creative_focus_selection(
        session,
        section=section,
        concert_chord=concert_chord,
        chord_index=chord_index,
        source_page=source_page,
        written_chord=written_chord,
    )
    return True


def apply_pending_song_creative_focus_pre_widget(
    session: dict[str, Any],
    pending: dict[str, Any],
) -> bool:
    section = str(pending.get("selected_section_id") or "").strip()
    chord = str(pending.get("selected_concert_chord") or "").strip()
    idx = int(pending.get("selected_chord_id") or 0)
    page = str(pending.get("source_page") or "").strip()
    if not chord:
        return False
    commit_song_creative_focus_selection(
        session,
        section=section,
        concert_chord=chord,
        chord_index=idx,
        source_page=page,
        written_chord=str(pending.get("selected_written_chord") or ""),
    )
    return True


__all__ = [
    "SONG_CREATIVE_FOCUS_EDIT_OUTCOME_KEY",
    "apply_pending_song_creative_focus_pre_widget",
    "capture_song_creative_focus_intent",
    "commit_song_creative_focus_selection",
]

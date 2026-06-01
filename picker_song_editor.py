"""Song Selection content editor open/collapse state (lyrics + chart)."""

from __future__ import annotations

from typing import Any

from studio_scroll_anchors import (
    ANCHOR_CHART_EDITOR,
    ANCHOR_LYRICS_EDITOR,
    set_pending_anchor,
)

PICKER_EDITOR_OPEN_KEY = "picker_song_editor_open"
PICKER_EDITOR_TAB_KEY = "picker_editor_tab"
PICKER_EDITOR_NOTICE_KEY = "picker_editor_save_notice"
_JUMP_TO_CHART_EDITOR_KEY = "_jump_to_chart_editor"
_PENDING_OPEN_LYRICS_EDITOR_KEY = "_pending_open_lyrics_editor"


def open_picker_editor(
    session_state: Any,
    tab: str,
    *,
    enable_chart_editing: bool = False,
) -> None:
    """Expand the Song Selection content editor on ``tab``."""
    session_state[PICKER_EDITOR_OPEN_KEY] = True
    session_state[PICKER_EDITOR_TAB_KEY] = tab
    session_state.pop(PICKER_EDITOR_NOTICE_KEY, None)
    if tab == "Edit Song Chart":
        session_state[_JUMP_TO_CHART_EDITOR_KEY] = True
        if enable_chart_editing:
            session_state["chart_edit_mode"] = True
        set_pending_anchor(session_state, ANCHOR_CHART_EDITOR)
    else:
        session_state[_PENDING_OPEN_LYRICS_EDITOR_KEY] = True
        set_pending_anchor(session_state, ANCHOR_LYRICS_EDITOR)


def collapse_picker_editor(
    session_state: Any,
    *,
    title: str,
    artist: str,
    message: str,
    chart_caption: str = "",
) -> None:
    """Collapse editor body after a successful save; keep tab header visible."""
    session_state[PICKER_EDITOR_OPEN_KEY] = False
    session_state["chart_edit_mode"] = False
    session_state[PICKER_EDITOR_NOTICE_KEY] = {
        "title": title,
        "artist": artist,
        "message": message,
        "chart_caption": chart_caption,
    }


def consume_open_lyrics_request(session_state: Any) -> bool:
    return bool(session_state.pop(_PENDING_OPEN_LYRICS_EDITOR_KEY, False))


def consume_jump_to_chart_editor(session_state: Any) -> bool:
    jumped = bool(session_state.pop(_JUMP_TO_CHART_EDITOR_KEY, False))
    if jumped:
        session_state[PICKER_EDITOR_TAB_KEY] = "Edit Song Chart"
        session_state["chart_edit_mode"] = True
    return jumped

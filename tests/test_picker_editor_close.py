"""Close editor holds after a Lyrics & Cues open request.

Live first wrong step: an editor opened by a Lyrics & Cues request (Karaoke
"Add lyrics & cues", lyrics navigation) re-armed that request every time the
Songs page applied it, so the editor reopened on the next rerun after Close.
"""

from __future__ import annotations

from pathlib import Path

from picker_song_editor import (
    PICKER_EDITOR_OPEN_KEY,
    consume_open_lyrics_request,
    open_picker_editor,
)


def _songs_page_run(session: dict) -> None:
    """What the Songs page does with a queued open request."""
    if consume_open_lyrics_request(session):
        open_picker_editor(session, "Lyrics & Cues", arm_request=False)


def test_close_holds_after_a_lyrics_open_request() -> None:
    session: dict = {"active_catalog_pick_key": "Pop\x1fPerfect — Ed Sheeran"}
    open_picker_editor(session, "Lyrics & Cues")          # e.g. Karaoke "Add lyrics & cues"
    _songs_page_run(session)
    assert session[PICKER_EDITOR_OPEN_KEY] is True
    session[PICKER_EDITOR_OPEN_KEY] = False               # Close editor
    for _ in range(3):
        _songs_page_run(session)
    assert session[PICKER_EDITOR_OPEN_KEY] is False


def test_songs_page_applies_requests_without_re_arming() -> None:
    app = (Path(__file__).resolve().parent.parent / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
    i = app.index("if consume_open_lyrics_request(st.session_state):")
    assert 'open_picker_editor(st.session_state, "Lyrics & Cues", arm_request=False)' in app[i : i + 200]

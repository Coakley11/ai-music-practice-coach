"""Backing presentation opens only after an explicit Play initialization."""

from pathlib import Path

from backing_track_state import (
    BACKING_PRESENTATION_SESSION_ID_KEY,
    backing_lead_sheet_is_open,
    backing_presentation_is_initialized,
    initialize_backing_presentation,
)


def test_initial_entry_closes_stale_lead_sheet_without_opening_presentation() -> None:
    session = {
        "backing_lead_sheet_open": True,
        "_pending_open_backing_lead_sheet": True,
    }

    assert not backing_presentation_is_initialized(session, "song-a")
    assert not backing_lead_sheet_is_open(session, "song-a")
    assert session["backing_lead_sheet_open"] is False
    assert "_pending_open_backing_lead_sheet" not in session


def test_play_initializes_song_but_lead_sheet_remains_opt_in() -> None:
    session = {"backing_lead_sheet_open": True}

    assert initialize_backing_presentation(session, "song-a") is True
    assert session[BACKING_PRESENTATION_SESSION_ID_KEY] == "song-a"
    assert backing_presentation_is_initialized(session, "song-a")
    assert not backing_lead_sheet_is_open(session, "song-a")

    session["backing_lead_sheet_open"] = True
    assert backing_lead_sheet_is_open(session, "song-a")


def test_selecting_another_song_requires_play_and_cannot_inherit_lead_sheet() -> None:
    session: dict = {}
    initialize_backing_presentation(session, "song-a")
    session["backing_lead_sheet_open"] = True

    assert not backing_presentation_is_initialized(session, "song-b")
    assert not backing_lead_sheet_is_open(session, "song-b")
    assert session["backing_lead_sheet_open"] is False


def test_app_gates_song_card_audio_and_lead_sheet_on_presentation_state() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py"
    ).read_text(encoding="utf-8")

    assert "Key cycling unavailable:" not in source
    assert "if _backing_presentation_open and _backing_banner_slot is not None" in source
    assert "if _backing_presentation_open and _backing_card_slot is not None" in source
    assert "_backing_presentation_open\n        and _session_backing_audio_ready" in source
    assert "initialize_backing_presentation(st.session_state, _bpm_sync_id)" in source

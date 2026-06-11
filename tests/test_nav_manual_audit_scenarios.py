"""Programmatic Back/Forward audit — mirrors manual nav protocol scenarios."""

from __future__ import annotations

from unittest.mock import patch

from instrument_transposition import (
    CHART_IN_INSTRUMENT_KEY_KEY,
    SELECTED_TRANSPOSING_INSTRUMENT_KEY,
)
from studio_nav_history import go_back, go_forward, init_nav_history, navigate_studio_page
from studio_page_persistence import handle_studio_page_transition


def _global_session() -> dict:
    """Non-default globals that must survive Back/Forward."""
    return {
        "studio_page": "practice",
        "instrument": "Saxophone",
        "level": "Intermediate",
        "focus": "Improvisation",
        "display_key": "Db",
        SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Tenor saxophone (Bb)",
        CHART_IN_INSTRUMENT_KEY_KEY: True,
        "selected_song": {"pick_key": "pk::Pop::Photograph — Ed Sheeran", "title": "Photograph"},
        "active_catalog_pick_key": "pk::Pop::Photograph — Ed Sheeran",
        "practice_focus_section": "Chorus",
        "practice_groove_style": "Swing",
        "backing_track_bpm": 92,
        "backing_groove_style": "Bossa",
        "selected_sections": ["Verse", "Chorus"],
    }


def _globals_snapshot(state: dict) -> dict:
    return {
        "instrument": state.get("instrument"),
        "display_key": state.get("display_key"),
        "pick_key": (state.get("selected_song") or {}).get("pick_key"),
        "written_on": state.get(CHART_IN_INSTRUMENT_KEY_KEY),
        "transposing": state.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY),
        "practice_focus_section": state.get("practice_focus_section"),
        "practice_groove_style": state.get("practice_groove_style"),
        "backing_track_bpm": state.get("backing_track_bpm"),
        "backing_groove_style": state.get("backing_groove_style"),
        "selected_sections": list(state.get("selected_sections") or []),
    }


def _nav(state: dict, page: str) -> None:
    with patch("music_persistent_state.after_studio_page_change"):
        navigate_studio_page(state, page)
    handle_studio_page_transition(state)


def _back(state: dict) -> None:
    assert go_back(state) is True
    handle_studio_page_transition(state)


def _forward(state: dict) -> None:
    assert go_forward(state) is True
    handle_studio_page_transition(state)


@patch("music_persistent_state.after_studio_page_change")
def test_audit_practice_backing_back_returns_practice(_mock_save):
    state = _global_session()
    init_nav_history(state)
    before = _globals_snapshot(state)
    _nav(state, "backing")
    assert state["studio_page"] == "backing"
    _back(state)
    assert state["studio_page"] == "practice"
    assert _globals_snapshot(state) == before


@patch("music_persistent_state.after_studio_page_change")
def test_audit_practice_backing_creative_back_returns_backing(_mock_save):
    state = _global_session()
    init_nav_history(state)
    _nav(state, "backing")
    _nav(state, "creative")
    assert state["studio_page"] == "creative"
    _back(state)
    assert state["studio_page"] == "backing"


@patch("music_persistent_state.after_studio_page_change")
def test_audit_back_forward_restores_creative(_mock_save):
    state = _global_session()
    init_nav_history(state)
    before = _globals_snapshot(state)
    _nav(state, "backing")
    _nav(state, "creative")
    _back(state)
    assert state["studio_page"] == "backing"
    _forward(state)
    assert state["studio_page"] == "creative"
    assert _globals_snapshot(state) == before


@patch("music_persistent_state.after_studio_page_change")
def test_audit_picker_practice_backing_back_forward(_mock_save):
    state = _global_session()
    state["studio_page"] = "picker"
    init_nav_history(state)
    before = _globals_snapshot(state)
    _nav(state, "practice")
    _nav(state, "backing")
    _back(state)
    assert state["studio_page"] == "practice"
    _forward(state)
    assert state["studio_page"] == "backing"
    assert _globals_snapshot(state) == before


@patch("music_persistent_state.after_studio_page_change")
def test_audit_page_local_practice_focus_preserved(_mock_save):
    state = _global_session()
    init_nav_history(state)
    state["practice_focus_section"] = "Bridge"
    state["practice_groove_style"] = "Funk"
    _nav(state, "backing")
    _back(state)
    assert state["practice_focus_section"] == "Bridge"
    assert state["practice_groove_style"] == "Funk"


@patch("music_persistent_state.after_studio_page_change")
def test_audit_page_local_backing_bpm_preserved(_mock_save):
    state = _global_session()
    init_nav_history(state)
    state["backing_track_bpm"] = 118
    state["backing_groove_style"] = "Shuffle"
    state["selected_sections"] = ["Intro", "Solo"]
    _nav(state, "practice")
    _nav(state, "creative")
    _back(state)
    _forward(state)
    assert state["backing_track_bpm"] == 118
    assert state["backing_groove_style"] == "Shuffle"
    assert state["selected_sections"] == ["Intro", "Solo"]


@patch("music_persistent_state.after_studio_page_change")
def test_back_survives_stale_cloud_workspace_restore(_mock_save):
    """Live Back must not revert when cloud workspace still says the prior page."""
    from unittest.mock import MagicMock

    from music_persistent_state import apply_music_disk_state

    state = _global_session()
    init_nav_history(state)
    _nav(state, "backing")
    assert go_back(state) is True
    state["_studio_nav_from_history"] = True
    state["active_page_source"] = "history_back"
    handle_studio_page_transition(state)

    st = MagicMock()
    st.session_state = state
    cloud = {
        "studio_nav_state": {"studio_page": "backing"},
        "music_workspace_state": {"studio_page": "backing"},
        "core": {"studio_page": "backing", "instrument": "Saxophone"},
    }
    apply_music_disk_state(st, cloud, song_picker_catalog={}, song_library={})
    assert st.session_state["studio_page"] == "practice"
    assert st.session_state.get("_suite_page_overwrite_source") == "history_nav_preserved"

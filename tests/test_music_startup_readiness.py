from __future__ import annotations

from unittest.mock import MagicMock

from music_startup_readiness import (
    collect_music_startup_readiness,
    render_music_startup_ready_marker,
)
from music_workspace_hydration import mark_workspace_empty_confirmed


def _ready_session() -> dict:
    session = {
        "_music_post_nav_startup_done": True,
        "selected_song": {"pick_key": "Pop::Say", "title": "Say"},
        "active_catalog_pick_key": "Pop::Say",
        "active_music_source": "catalog",
        "display_key": "G",
    }
    mark_workspace_empty_confirmed(session, "no workspace blob")
    return session


def test_shell_is_not_ready_before_workspace_outcome() -> None:
    session = {
        "_music_post_nav_startup_done": True,
        "selected_song": {"pick_key": "Pop::Say", "title": "Say"},
    }
    state = collect_music_startup_readiness(
        session,
        song_title="Say",
        song_data={"title": "Say", "key": "G"},
    )
    assert not state.ready
    assert state.reason == "workspace_not_finalized"


def test_hydrated_shell_is_not_ready_before_first_song_context() -> None:
    session = _ready_session()
    state = collect_music_startup_readiness(session, song_title="", song_data={})
    assert not state.ready
    assert state.reason == "song_data_unresolved"


def test_first_song_context_exposes_navigation_safe_contract() -> None:
    session = _ready_session()
    state = collect_music_startup_readiness(
        session,
        song_title="Say",
        song_data={"title": "Say", "key": "G"},
    )
    assert state.ready
    assert state.pick_key == "Pop::Say"
    assert state.source == "catalog"
    assert state.practice_key == "G"


def test_ready_marker_contains_music_and_entitlement_state(monkeypatch) -> None:
    monkeypatch.setenv("MUSIC_ENTITLEMENT_DEV_CONTROLS", "1")
    monkeypatch.setenv("MUSIC_ENTITLEMENT_RUNTIME", "test")
    monkeypatch.setenv("MUSIC_ENTITLEMENT_DEV_PLAN", "free")
    st = MagicMock()
    st.session_state = _ready_session()

    assert render_music_startup_ready_marker(
        st,
        song_title="Say",
        song_data={"title": "Say", "key": "G"},
        studio_page="practice",
    )
    markup = st.markdown.call_args.args[0]
    assert 'id="music-startup-ready-marker"' in markup
    assert 'data-pick-key="Pop::Say"' in markup
    assert 'data-music-source="catalog"' in markup
    assert 'data-practice-key="G"' in markup
    assert 'data-entitlement-plan="free"' in markup

"""History Back/Forward must block workspace restore from stomping the target page."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from studio_nav_history import (
    _apply_history_nav_transition,
    go_back,
    history_nav_blocks_workspace_sync,
    init_nav_history,
    navigate_studio_page,
)


def test_history_nav_blocks_workspace_sync_when_flag_set() -> None:
    state = {"_studio_nav_from_history": True, "studio_page": "backing"}
    assert history_nav_blocks_workspace_sync(state) is True


def test_history_nav_blocks_workspace_sync_when_pending_save() -> None:
    state = {"_studio_history_nav_pending_save": "practice", "studio_page": "practice"}
    assert history_nav_blocks_workspace_sync(state) is True


@patch("suite_cloud_state.should_skip_workspace_restore_for_resume", return_value=False)
@patch("suite_cloud_state.reconcile_stale_resume_session_flags", return_value=False)
@patch("suite_cloud_state.load_cloud_full_session", return_value=({}, None))
@patch("suite_user_persistence._load_raw", return_value=({}, None, None))
def test_sync_workspace_skipped_for_history_nav(_disk, _cloud, _reconcile, _skip_resume) -> None:
    from suite_user_persistence import sync_workspace_protocol

    st = MagicMock()
    st.session_state = {
        "studio_page": "backing",
        "_studio_nav_from_history": True,
        "studio_nav_state": {"studio_page": "backing"},
    }
    applied = sync_workspace_protocol(
        st,
        "music",
        apply_state=lambda _st, _blob: None,
        cloud_first=True,
    )
    assert applied is False
    assert "history navigation" in str(st.session_state.get("_suite_persist_restore_skip_reason", ""))


def test_on_click_style_history_back_survives_restore() -> None:
    from music_persistent_state import apply_music_disk_state

    state = {
        "studio_page": "practice",
        "instrument": "Saxophone",
        "display_key": "Db",
    }
    init_nav_history(state)
    navigate_studio_page(state, "backing")
    navigate_studio_page(state, "creative")
    assert go_back(state) is True
    _apply_history_nav_transition(state, source="history_back")
    assert state["studio_page"] == "backing"
    assert history_nav_blocks_workspace_sync(state) is True

    st = MagicMock()
    st.session_state = state
    cloud = {
        "studio_nav_state": {"studio_page": "creative"},
        "music_workspace_state": {"studio_page": "creative"},
        "core": {"studio_page": "creative"},
    }
    apply_music_disk_state(st, cloud, song_picker_catalog={}, song_library={})
    assert st.session_state["studio_page"] == "backing"
    assert st.session_state.get("_suite_page_overwrite_source") == "history_nav_preserved"

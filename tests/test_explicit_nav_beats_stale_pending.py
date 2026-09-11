"""Explicit UI navigation must beat stale pending restore/return targets."""

from __future__ import annotations

from unittest.mock import patch

from app_ui import clear_stale_nav_overrides_for_explicit_click, navigate_studio_page


def test_explicit_click_clears_stale_navigate_to_studio_page() -> None:
    ss: dict = {
        "studio_page": "practice",
        "_navigate_to_studio_page": "creative",
        "_music_pending_mission_return_handoff": {"request_seq": 1},
        "_suite_deferred_page_change_save": "analysis",
    }
    cleared = clear_stale_nav_overrides_for_explicit_click(ss, "backing")
    assert "_navigate_to_studio_page" in cleared
    assert "_music_pending_mission_return_handoff" in cleared
    assert "_suite_deferred_page_change_save" in cleared
    assert "studio_page" not in ss or ss.get("studio_page") == "practice"
    assert ss.get("_suite_page_user_nav") is True
    assert ss.get("nav_target_page") == "backing"
    assert ss.get("_navigate_to_studio_page") is None
    assert ss.get("_music_pending_mission_return_handoff") is None


def test_explicit_navigate_clears_stale_before_history_nav() -> None:
    ss: dict = {
        "studio_page": "practice",
        "_navigate_to_studio_page": "creative",
        "_music_pending_creative_return_handoff": {"request_seq": 2},
    }
    with patch("music_persistent_state.after_studio_page_change"):
        changed = navigate_studio_page(ss, "backing")
    assert changed is True
    assert ss.get("studio_page") == "backing"
    assert ss.get("_navigate_to_studio_page") is None
    assert ss.get("_music_pending_creative_return_handoff") is None


def test_workflow_history_navigate_does_not_use_ui_clear_helper() -> None:
    """Mission/Jam return may still call studio_nav_history.navigate directly."""
    from studio_nav_history import navigate_studio_page as history_nav

    ss: dict = {
        "studio_page": "backing",
        "_music_pending_mission_return_handoff": {"request_seq": 9},
        "_navigate_to_studio_page": "analysis",
    }
    with patch("music_persistent_state.after_studio_page_change"):
        history_nav(ss, "creative")
    assert ss.get("studio_page") == "creative"
    # History path must not silently drop a pending return that consume owns.
    assert ss.get("_music_pending_mission_return_handoff") == {"request_seq": 9}

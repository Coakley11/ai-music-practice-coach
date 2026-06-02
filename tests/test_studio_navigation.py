"""Smoke tests for studio page navigation and history stacks."""

from app_ui import OPENAI_PAGE_ID, sidebar_studio_page_items
from studio_nav_history import (
    STUDIO_PAGE_IDS,
    go_back,
    go_forward,
    init_nav_history,
    navigate_studio_page,
)
from studio_page_persistence import handle_studio_page_transition


def test_sidebar_openai_page_only_when_ai_enabled():
    without = [pid for pid, _ in sidebar_studio_page_items(ai_enabled=False)]
    with_ai = [pid for pid, _ in sidebar_studio_page_items(ai_enabled=True)]
    assert OPENAI_PAGE_ID not in without
    assert OPENAI_PAGE_ID in with_ai
    assert "practice" in without and "practice" in with_ai


def test_studio_page_order_includes_all_pages():
    expected = {
        "practice",
        "picker",
        "backing",
        "custom",
        "creative",
        "multitrack",
        "analysis",
        "log",
        "openai",
    }
    assert expected == set(STUDIO_PAGE_IDS)


def test_navigate_studio_page_records_history():
    state: dict = {"studio_page": "practice"}
    init_nav_history(state)
    assert navigate_studio_page(state, "backing") is True
    assert state["studio_page"] == "backing"
    assert len(state["studio_nav_back"]) == 1
    assert state["studio_nav_forward"] == []


def test_back_and_forward_restore_pages():
    state: dict = {"studio_page": "practice"}
    init_nav_history(state)
    navigate_studio_page(state, "picker")
    navigate_studio_page(state, "backing")
    assert state["studio_page"] == "backing"
    assert go_back(state) is True
    handle_studio_page_transition(state)
    assert state["studio_page"] == "picker"
    assert go_forward(state) is True
    handle_studio_page_transition(state)
    assert state["studio_page"] == "backing"


def test_invalid_page_id_is_rejected():
    state: dict = {"studio_page": "practice"}
    init_nav_history(state)
    assert navigate_studio_page(state, "not_a_page") is False
    assert state["studio_page"] == "practice"


def test_same_page_navigation_is_noop():
    state: dict = {"studio_page": "practice"}
    init_nav_history(state)
    assert navigate_studio_page(state, "practice") is False
    assert state["studio_nav_back"] == []

"""Smoke tests for studio page navigation and history stacks."""

from unittest.mock import patch

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


def test_nav_history_public_exports():
    import studio_nav_history as mod

    for name in (
        "init_nav_history",
        "navigate_studio_page",
        "render_floating_nav_history",
        "render_sidebar_nav_history",
        "render_nav_deploy_marker",
    ):
        assert hasattr(mod, name), name
        assert callable(getattr(mod, name))
    assert getattr(mod, "NAVIGATION_UI_DEPLOY_MARKER", "")


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


@patch("music_persistent_state.after_studio_page_change")
def test_navigate_studio_page_records_history(_mock_save):
    state: dict = {"studio_page": "practice"}
    init_nav_history(state)
    assert navigate_studio_page(state, "backing") is True
    _mock_save.assert_called_once()
    assert state["studio_page"] == "backing"
    assert len(state["studio_nav_back"]) == 1
    assert state["studio_nav_forward"] == []


@patch("music_persistent_state.after_studio_page_change")
def test_back_and_forward_restore_pages(_mock_save):
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


def test_quick_nav_css_restores_art_face_without_hidden_buttons():
    from app_ui import (
        STUDIO_QUICK_NAV_PANEL_KEY,
        _nav_art_face_html,
        _quick_nav_artistic_css,
        _resolve_quick_nav_current_page,
        _studio_quick_nav_button_key,
        nav_compact_button_label,
    )

    css = _quick_nav_artistic_css().lower()
    assert "opacity: 0" not in css
    assert "color: transparent" not in css
    assert "text-indent: -9999" not in css
    assert "position: absolute" not in css
    assert "caveat" in css
    assert "ui-nav-script-label" in css
    assert "ui-nav-art-face" in css
    assert STUDIO_QUICK_NAV_PANEL_KEY == "studio_quick_nav_panel"
    assert _studio_quick_nav_button_key("practice") == "studio_quick_nav_btn_practice"
    assert nav_compact_button_label("picker") == "Songs"
    assert _resolve_quick_nav_current_page({"studio_page": "backing"}, "practice") == "backing"
    face = _nav_art_face_html("practice", active=True)
    assert "Practice" in face
    assert "ui-nav-icon" in face
    assert "_art_" not in _studio_quick_nav_button_key("picker")


def test_quick_nav_uses_one_stable_button_key_per_page():
    from app_ui import TOP_NAV_PAGE_IDS, _studio_quick_nav_button_key

    keys = [_studio_quick_nav_button_key(page_id) for page_id in TOP_NAV_PAGE_IDS]
    assert len(keys) == len(set(keys))
    assert all(key.startswith("studio_quick_nav_btn_") for key in keys)
    assert all("_art_" not in key for key in keys)


def test_simple_nav_mode_uses_plain_button_keys():
    from app_ui import (
        SIMPLE_NAV_PAGE_IDS,
        USE_SIMPLE_MUSIC_NAV_KEY,
        _simple_nav_css,
        _studio_simple_nav_button_key,
        use_simple_music_nav,
    )

    css = _simple_nav_css().lower()
    assert "caveat" not in css
    assert "ui-nav-art" not in css
    assert "studio_simple_nav_btn_" in css
    assert use_simple_music_nav({USE_SIMPLE_MUSIC_NAV_KEY: True})
    assert not use_simple_music_nav({})
    keys = [_studio_simple_nav_button_key(page_id) for page_id in SIMPLE_NAV_PAGE_IDS]
    assert keys == [
        "studio_simple_nav_btn_practice",
        "studio_simple_nav_btn_picker",
        "studio_simple_nav_btn_backing",
        "studio_simple_nav_btn_custom",
        "studio_simple_nav_btn_multitrack",
    ]

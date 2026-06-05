"""Portfolio polish — screenshot mode helpers and symbol coverage."""

from __future__ import annotations

import portfolio_polish as pp
import portfolio_demo as pdemo
from portfolio_polish import (
    is_capture_mode,
    show_developer_sidebar,
    show_quick_nav,
    show_tutorial_entry,
)
from studio_nav_history import render_nav_deploy_marker

# Every ``pp.<name>`` referenced across the Music app (keep in sync with repo).
_REQUIRED_PORTFOLIO_POLISH_SYMBOLS = frozenset({
    "demo_applied",
    "expander_default",
    "feature_expander_default",
    "inject_polish_css",
    "instructional_caption",
    "is_capture_mode",
    "is_demo_mode",
    "is_screenshot_mode",
    "mark_demo_applied",
    "render_executive_summary",
    "render_hero_banner",
    "render_sidebar_toggle",
    "show_developer_sidebar",
    "show_quick_nav",
    "show_tutorial_entry",
})


class _FakeSt:
    def __init__(self):
        self.markdown_calls: list[str] = []
        self.session_state = {}

    def markdown(self, body, **kwargs):
        self.markdown_calls.append(body)


def test_required_portfolio_polish_symbols_exist():
    missing = [name for name in _REQUIRED_PORTFOLIO_POLISH_SYMBOLS if not hasattr(pp, name)]
    assert not missing, f"portfolio_polish missing: {missing}"
    for name in ("show_tutorial_entry", "show_quick_nav", "is_capture_mode", "show_developer_sidebar"):
        assert name in pp.__all__


def test_capture_mode_helpers():
    st = _FakeSt()
    st.session_state["portfolio_screenshot_mode"] = True
    assert is_capture_mode(st)
    assert not show_quick_nav(st)
    assert not show_tutorial_entry(st)
    assert not show_developer_sidebar(st)


def test_tutorial_and_quick_nav_enabled_in_normal_mode():
    st = _FakeSt()
    assert show_quick_nav(st)
    assert show_tutorial_entry(st)
    assert show_developer_sidebar(st)


def test_nav_deploy_marker_hidden_by_default():
    fake = _FakeSt()
    render_nav_deploy_marker(fake, developer_mode=False)
    assert fake.markdown_calls == []


def test_nav_deploy_marker_shows_in_developer_mode():
    fake = _FakeSt()
    render_nav_deploy_marker(fake, developer_mode=True)
    assert len(fake.markdown_calls) == 1
    assert "Navigation UI version" in fake.markdown_calls[0]


def test_portfolio_demo_import_smoke():
    assert hasattr(pdemo, "apply_auto_demo")
    assert hasattr(pdemo, "load_practice_demo")

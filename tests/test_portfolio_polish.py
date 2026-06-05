"""Portfolio polish — screenshot mode helpers."""

from portfolio_polish import (
    is_capture_mode,
    show_developer_sidebar,
    show_quick_nav,
    show_tutorial_entry,
)
from studio_nav_history import render_nav_deploy_marker


class _FakeSt:
    def __init__(self):
        self.markdown_calls: list[str] = []
        self.session_state = {}

    def markdown(self, body, **kwargs):
        self.markdown_calls.append(body)


def test_capture_mode_helpers():
    st = _FakeSt()
    st.session_state["portfolio_screenshot_mode"] = True
    assert is_capture_mode(st)
    assert not show_quick_nav(st)
    assert not show_tutorial_entry(st)
    assert not show_developer_sidebar(st)


def test_nav_deploy_marker_hidden_by_default():
    fake = _FakeSt()
    render_nav_deploy_marker(fake, developer_mode=False)
    assert fake.markdown_calls == []


def test_nav_deploy_marker_shows_in_developer_mode():
    fake = _FakeSt()
    render_nav_deploy_marker(fake, developer_mode=True)
    assert len(fake.markdown_calls) == 1
    assert "Navigation UI version" in fake.markdown_calls[0]

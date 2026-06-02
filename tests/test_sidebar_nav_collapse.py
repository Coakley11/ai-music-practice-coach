"""Collapsible sidebar page navigation."""

from __future__ import annotations

from app_ui import SIDEBAR_NAV_COLLAPSED_KEY, sidebar_nav_is_collapsed


def test_sidebar_nav_collapsed_defaults_false():
    assert sidebar_nav_is_collapsed({}) is False


def test_sidebar_nav_collapsed_reads_session():
    state = {SIDEBAR_NAV_COLLAPSED_KEY: True}
    assert sidebar_nav_is_collapsed(state) is True

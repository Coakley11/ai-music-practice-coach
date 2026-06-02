"""Collapsible sidebar page navigation — defaults collapsed for Music App."""

from __future__ import annotations

from app_ui import (
    SIDEBAR_NAV_COLLAPSED_KEY,
    ensure_sidebar_nav_defaults,
    sidebar_nav_is_collapsed,
)


def test_sidebar_nav_collapsed_defaults_true_when_unset():
    assert sidebar_nav_is_collapsed({}) is True


def test_ensure_sidebar_nav_defaults_sets_true_on_first_load():
    state: dict = {}
    assert ensure_sidebar_nav_defaults(state) is True
    assert state[SIDEBAR_NAV_COLLAPSED_KEY] is True


def test_sidebar_nav_expanded_when_user_opted_in():
    state = {SIDEBAR_NAV_COLLAPSED_KEY: False}
    assert ensure_sidebar_nav_defaults(state) is False
    assert sidebar_nav_is_collapsed(state) is False


def test_sidebar_nav_collapsed_reads_session():
    state = {SIDEBAR_NAV_COLLAPSED_KEY: True}
    assert sidebar_nav_is_collapsed(state) is True

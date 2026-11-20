"""The sidebar PAGES list keeps the state the musician chose.

Navigating is not a reason to change it. The owner's rules:

A. Expanded stays expanded when you pick any destination.
B. A manual collapse stays collapsed while moving among non-Home pages.
C. Home always arrives expanded, even after a collapse.
D. Ordinary reruns never change it.

``apply_page_defaults`` is the one authority for the state; the only other writers
are the user's own collapse/expand controls.
"""

from __future__ import annotations

import inspect

from app_ui import (
    SIDEBAR_NAV_COLLAPSED_KEY,
    render_sidebar_studio_nav,
    sidebar_nav_is_collapsed,
)
from music_sidebar_policy import LAST_PAGE, PAGES_COLLAPSED, apply_page_defaults

NON_HOME = ("practice", "picker", "backing", "custom", "composer", "creative")


def _expanded(state: dict) -> bool:
    """Read the state the way the renderer does."""
    return not sidebar_nav_is_collapsed(state)


def test_the_key_is_the_one_app_ui_reads() -> None:
    """A second key name would give two authorities that silently disagree."""
    assert PAGES_COLLAPSED == SIDEBAR_NAV_COLLAPSED_KEY


# --- Rule A -------------------------------------------------------------------

def test_expanded_survives_every_destination() -> None:
    state: dict = {}
    apply_page_defaults(state, "home")
    assert _expanded(state), "Home should arrive expanded"
    for page in NON_HOME:
        apply_page_defaults(state, page)
        assert _expanded(state), f"navigating to {page} collapsed the page list"


def test_expanding_on_a_non_home_page_then_navigating_stays_expanded() -> None:
    """The user expands while on Practice - Backing must not take it away."""
    state: dict = {}
    apply_page_defaults(state, "practice")
    state[PAGES_COLLAPSED] = False  # the "Pages" button
    apply_page_defaults(state, "backing")
    assert _expanded(state)


# --- Rule B -------------------------------------------------------------------

def test_a_manual_collapse_is_respected_across_non_home_pages() -> None:
    state: dict = {}
    apply_page_defaults(state, "home")
    state[PAGES_COLLAPSED] = True  # the collapse triangle
    for page in NON_HOME:
        apply_page_defaults(state, page)
        assert not _expanded(state), f"{page} re-opened a list the user collapsed"


# --- Rule C -------------------------------------------------------------------

def test_home_always_expands_even_after_a_collapse() -> None:
    state: dict = {}
    apply_page_defaults(state, "practice")
    state[PAGES_COLLAPSED] = True
    apply_page_defaults(state, "home")
    assert _expanded(state)


def test_after_home_expands_it_the_next_page_keeps_it() -> None:
    state: dict = {}
    apply_page_defaults(state, "custom")
    state[PAGES_COLLAPSED] = True
    apply_page_defaults(state, "home")
    apply_page_defaults(state, "composer")
    assert _expanded(state)


# --- Rule D -------------------------------------------------------------------

def test_reruns_on_the_same_page_change_nothing() -> None:
    for chosen in (True, False):
        state: dict = {PAGES_COLLAPSED: chosen, LAST_PAGE: "backing"}
        for _ in range(5):  # choosing a song, a setting, a section...
            apply_page_defaults(state, "backing")
            assert state[PAGES_COLLAPSED] is chosen


def test_a_first_rerun_does_not_invent_a_preference() -> None:
    """Arriving with no stored choice must not then flip on the next rerun."""
    state: dict = {}
    first = apply_page_defaults(state, "practice")
    second = apply_page_defaults(state, "practice")
    assert first is second is True  # the studio has always opened collapsed


# --- the owner's worked example, end to end -----------------------------------

def test_the_owners_walkthrough() -> None:
    state: dict = {}
    steps = [
        ("home", True, "Open Home -> expanded"),
        ("picker", True, "Song Selection -> remains expanded"),
        ("backing", True, "Backing Track -> remains expanded"),
    ]
    for page, want_expanded, why in steps:
        apply_page_defaults(state, page)
        assert _expanded(state) is want_expanded, why

    state[PAGES_COLLAPSED] = True  # the collapse triangle
    apply_page_defaults(state, "custom")
    assert not _expanded(state), "Custom -> remains collapsed"

    apply_page_defaults(state, "home")
    assert _expanded(state), "Home -> automatically expands"

    apply_page_defaults(state, "composer")
    assert _expanded(state), "Composition -> remains expanded"


# --- no competing writer ------------------------------------------------------

def test_only_the_users_own_controls_write_the_state_in_the_renderer() -> None:
    """Writes in the nav renderer must come from a button branch, not a nav side effect."""
    src = inspect.getsource(render_sidebar_studio_nav)
    writes = [
        line.strip()
        for line in src.splitlines()
        if "SIDEBAR_NAV_COLLAPSED_KEY]" in line and "=" in line
    ]
    assert writes, "expected the collapse/expand buttons to still set the state"
    # The rail "Pages" button (expand) and the collapse triangle - nothing else.
    assert len(writes) == 2, writes
    assert sum("False" in line for line in writes) == 1, writes
    assert sum("True" in line for line in writes) == 1, writes


def test_navigation_does_not_touch_the_state() -> None:
    """A page change through the nav authority is not allowed to write the key."""
    import studio_nav_history

    src = inspect.getsource(studio_nav_history.navigate_studio_page)
    assert "sidebar_nav_collapsed" not in src

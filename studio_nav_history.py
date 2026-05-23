"""Back / forward navigation history for studio pages (session_state stacks)."""

from __future__ import annotations

from typing import Any, Callable

STUDIO_PAGE_IDS: frozenset[str] = frozenset(
    {
        "practice",
        "picker",
        "backing",
        "custom",
        "creative",
        "multitrack",
        "analysis",
        "log",
    }
)

NAV_BACK_STACK = "studio_nav_back"
NAV_FORWARD_STACK = "studio_nav_forward"
_NAV_FROM_HISTORY = "_studio_nav_from_history"


def init_nav_history(session_state: dict) -> None:
    session_state.setdefault(NAV_BACK_STACK, [])
    session_state.setdefault(NAV_FORWARD_STACK, [])


def can_go_back(session_state: dict) -> bool:
    return bool(session_state.get(NAV_BACK_STACK))


def can_go_forward(session_state: dict) -> bool:
    return bool(session_state.get(NAV_FORWARD_STACK))


def navigate_studio_page(session_state: dict, page_id: str) -> bool:
    """
    Set ``studio_page`` and record history (clears forward stack).
    Returns True if the page actually changed.
    """
    page_id = str(page_id).strip()
    if page_id not in STUDIO_PAGE_IDS:
        return False
    current = str(session_state.get("studio_page", "practice"))
    if current == page_id:
        return False
    if not session_state.pop(_NAV_FROM_HISTORY, False):
        if current in STUDIO_PAGE_IDS:
            back: list[str] = session_state.setdefault(NAV_BACK_STACK, [])
            if not back or back[-1] != current:
                back.append(current)
        session_state[NAV_FORWARD_STACK] = []
    session_state["studio_page"] = page_id
    return True


def go_back(session_state: dict) -> bool:
    back: list[str] = list(session_state.get(NAV_BACK_STACK) or [])
    if not back:
        return False
    target = back.pop()
    current = str(session_state.get("studio_page", "practice"))
    forward: list[str] = session_state.setdefault(NAV_FORWARD_STACK, [])
    if current in STUDIO_PAGE_IDS:
        forward.append(current)
    session_state[NAV_BACK_STACK] = back
    session_state[_NAV_FROM_HISTORY] = True
    session_state["studio_page"] = target
    return True


def go_forward(session_state: dict) -> bool:
    forward: list[str] = list(session_state.get(NAV_FORWARD_STACK) or [])
    if not forward:
        return False
    target = forward.pop()
    current = str(session_state.get("studio_page", "practice"))
    back: list[str] = session_state.setdefault(NAV_BACK_STACK, [])
    if current in STUDIO_PAGE_IDS:
        if not back or back[-1] != current:
            back.append(current)
    session_state[NAV_FORWARD_STACK] = forward
    session_state[_NAV_FROM_HISTORY] = True
    session_state["studio_page"] = target
    return True


def render_sidebar_nav_history(
    sidebar: Any,
    session_state: dict,
    *,
    rerun_fn: Callable[[], None],
) -> None:
    """Back / Forward buttons at the top of the sidebar."""
    import streamlit as st

    init_nav_history(session_state)
    back_ok = can_go_back(session_state)
    fwd_ok = can_go_forward(session_state)
    sidebar.markdown(
        '<p class="ui-sb-nav-label">Navigate</p>',
        unsafe_allow_html=True,
    )
    c1, c2 = sidebar.columns(2, gap="small")
    with c1:
        if st.button(
            "←",
            key="studio_nav_back_btn",
            disabled=not back_ok,
            use_container_width=True,
            help="Previous page",
        ):
            if go_back(session_state):
                rerun_fn()
    with c2:
        if st.button(
            "→",
            key="studio_nav_forward_btn",
            disabled=not fwd_ok,
            use_container_width=True,
            help="Forward",
        ):
            if go_forward(session_state):
                rerun_fn()

"""Back / forward navigation history for studio pages (session_state stacks).

Each stack entry stores ``page`` + **page-local** snapshot only (see
``studio_page_persistence``). Global instrument, level, focus, display key,
song, and transposition are never reverted by back/forward.
"""

from __future__ import annotations

from typing import Any, Callable

from studio_page_persistence import (
    make_history_entry,
    restore_history_entry,
    save_page_snapshot,
)

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


def _normalize_stack_entry(entry: Any) -> dict[str, Any]:
    """Support legacy stacks that stored only a page id string."""
    if isinstance(entry, dict) and entry.get("page"):
        return entry
    if isinstance(entry, str) and entry in STUDIO_PAGE_IDS:
        return {"page": entry, "snapshot": {}}
    return {"page": "practice", "snapshot": {}}


def can_go_back(session_state: dict) -> bool:
    return bool(session_state.get(NAV_BACK_STACK))


def can_go_forward(session_state: dict) -> bool:
    return bool(session_state.get(NAV_FORWARD_STACK))


def navigate_studio_page(session_state: dict, page_id: str) -> bool:
    """
    Set ``studio_page`` and record history (clears forward stack).
    Snapshots page state when leaving. Returns True if the page changed.
    """
    page_id = str(page_id).strip()
    if page_id not in STUDIO_PAGE_IDS:
        return False
    current = str(session_state.get("studio_page", "practice"))
    if current == page_id:
        return False
    if not session_state.pop(_NAV_FROM_HISTORY, False):
        if current in STUDIO_PAGE_IDS:
            save_page_snapshot(session_state, current)
            back: list[Any] = session_state.setdefault(NAV_BACK_STACK, [])
            entry = make_history_entry(session_state, current)
            if not back or _normalize_stack_entry(back[-1]).get("page") != current:
                back.append(entry)
        session_state[NAV_FORWARD_STACK] = []
    # Only change the page id here; ``handle_studio_page_transition`` restores
    # page-local state on the next run while global settings stay untouched.
    session_state["studio_page"] = page_id
    return True


def go_back(session_state: dict) -> bool:
    back: list[Any] = list(session_state.get(NAV_BACK_STACK) or [])
    if not back:
        return False
    entry = _normalize_stack_entry(back.pop())
    current = str(session_state.get("studio_page", "practice"))
    forward: list[Any] = session_state.setdefault(NAV_FORWARD_STACK, [])
    if current in STUDIO_PAGE_IDS:
        save_page_snapshot(session_state, current)
        fwd_entry = make_history_entry(session_state, current)
        forward.append(fwd_entry)
    session_state[NAV_BACK_STACK] = back
    session_state[_NAV_FROM_HISTORY] = True
    target = restore_history_entry(session_state, entry)
    session_state["studio_page"] = target
    return True


def go_forward(session_state: dict) -> bool:
    forward: list[Any] = list(session_state.get(NAV_FORWARD_STACK) or [])
    if not forward:
        return False
    entry = _normalize_stack_entry(forward.pop())
    current = str(session_state.get("studio_page", "practice"))
    back: list[Any] = session_state.setdefault(NAV_BACK_STACK, [])
    if current in STUDIO_PAGE_IDS:
        save_page_snapshot(session_state, current)
        back_entry = make_history_entry(session_state, current)
        if not back or _normalize_stack_entry(back[-1]).get("page") != current:
            back.append(back_entry)
    session_state[NAV_FORWARD_STACK] = forward
    session_state[_NAV_FROM_HISTORY] = True
    target = restore_history_entry(session_state, entry)
    session_state["studio_page"] = target
    return True


def render_sidebar_nav_history(
    sidebar: Any,
    session_state: dict,
    *,
    rerun_fn: Callable[[], None],
) -> None:
    """Compact browser-style back / forward arrows at the top of the sidebar."""
    import streamlit as st

    init_nav_history(session_state)
    back_ok = can_go_back(session_state)
    fwd_ok = can_go_forward(session_state)
    sidebar.markdown(
        '<div class="ui-studio-history-nav">'
        '<span class="ui-sb-nav-label">Navigate</span>'
        "</div>",
        unsafe_allow_html=True,
    )
    c1, c2 = sidebar.columns([1, 1], gap="small")
    with c1:
        if st.button(
            "←",
            key="studio_nav_back_btn",
            disabled=not back_ok,
            use_container_width=False,
            type="secondary",
            help="Previous page in history",
        ):
            if go_back(session_state):
                rerun_fn()
    with c2:
        if st.button(
            "→",
            key="studio_nav_forward_btn",
            disabled=not fwd_ok,
            use_container_width=False,
            type="secondary",
            help="Next page in history",
        ):
            if go_forward(session_state):
                rerun_fn()

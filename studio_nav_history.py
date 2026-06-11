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
        "openai",
    }
)

NAV_BACK_STACK = "studio_nav_back"
NAV_FORWARD_STACK = "studio_nav_forward"
_NAV_FROM_HISTORY = "_studio_nav_from_history"

# Bump when verifying Streamlit Cloud picked up navigation UI changes.
NAVIGATION_UI_DEPLOY_MARKER = "studio-nav-history-live-fix"

__all__ = (
    "STUDIO_PAGE_IDS",
    "NAV_BACK_STACK",
    "NAV_FORWARD_STACK",
    "NAVIGATION_UI_DEPLOY_MARKER",
    "init_nav_history",
    "can_go_back",
    "can_go_forward",
    "navigate_studio_page",
    "go_back",
    "go_forward",
    "render_floating_nav_history",
    "render_sidebar_nav_history",
    "render_nav_deploy_marker",
    "record_nav_history_trace",
    "consume_history_nav_startup_flag",
)


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


def _stack_page_ids(session_state: dict, stack_key: str) -> list[str]:
    stack = session_state.get(stack_key) or []
    if not isinstance(stack, list):
        return []
    pages: list[str] = []
    for entry in stack:
        page = _normalize_stack_entry(entry).get("page")
        if page:
            pages.append(str(page))
    return pages


def record_nav_history_trace(st: Any | None, session_state: dict, **extra: Any) -> None:
    """Update ?dev=1 trace fields for live back/forward diagnostics."""
    if st is None:
        return
    try:
        from music_persistence_trace import update_trace

        payload: dict[str, Any] = {
            "nav_history_stack": _stack_page_ids(session_state, NAV_BACK_STACK),
            "nav_forward_stack": _stack_page_ids(session_state, NAV_FORWARD_STACK),
            "nav_current_page": session_state.get("studio_page"),
            "final_studio_page": session_state.get("studio_page"),
            "page_overwrite_source": session_state.get("_suite_page_overwrite_source"),
            "active_page_source": session_state.get("active_page_source"),
        }
        payload.update(extra)
        update_trace(st, **payload)
    except Exception:
        pass


def consume_history_nav_startup_flag(session_state: dict) -> bool:
    """Clear one-shot history nav flag after workspace restore consumed it."""
    return bool(session_state.pop(_NAV_FROM_HISTORY, False))


def _claim_history_nav_ownership(session_state: dict, target_page: str, *, source: str) -> None:
    session_state[_NAV_FROM_HISTORY] = True
    session_state["active_page_source"] = source
    session_state["_suite_page_user_nav"] = True
    session_state["nav_target_page"] = target_page
    try:
        from studio_nav_state import mark_studio_nav_local_edit, write_canonical_studio_nav_state

        write_canonical_studio_nav_state(
            session_state,
            target_page,
            reason=source,
            local_edit=True,
        )
        mark_studio_nav_local_edit(session_state)
    except ImportError:
        pass


def _after_history_nav(
    st: Any,
    session_state: dict,
    *,
    target_page: str,
    source: str,
) -> None:
    _claim_history_nav_ownership(session_state, target_page, source=source)
    try:
        from music_persistent_state import after_studio_page_change

        after_studio_page_change(st, session_state, target_page=target_page)
    except Exception:
        try:
            from music_persistent_state import claim_studio_page_ownership

            claim_studio_page_ownership(st, target_page, session_state=session_state)
        except Exception:
            pass


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
    session_state["studio_page"] = page_id
    _nav_ss = session_state

    class _St:
        session_state = _nav_ss

    try:
        from music_persistent_state import after_studio_page_change, prepare_page_change_save_state

        prepare_page_change_save_state(session_state, page_id, st=_St())
        try:
            from local_nav_trace import record_local_nav_checkpoint

            record_local_nav_checkpoint(
                _St(),
                "post_navigate_before_save",
                session=session_state,
                intent=page_id,
            )
        except ImportError:
            pass
        after_studio_page_change(_St(), session_state, target_page=page_id)
    except Exception:
        try:
            from music_persistent_state import claim_studio_page_ownership

            claim_studio_page_ownership(_St(), page_id, session_state=session_state)
        except Exception:
            pass
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
    target = restore_history_entry(session_state, entry)
    session_state["studio_page"] = target
    session_state["nav_target_page"] = target
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
    target = restore_history_entry(session_state, entry)
    session_state["studio_page"] = target
    session_state["nav_target_page"] = target
    return True


def render_nav_deploy_marker(st_module: Any, *, developer_mode: bool = False) -> None:
    """Dev-only deploy marker — hidden from normal use and portfolio screenshots."""
    if not developer_mode:
        return
    label = f"Navigation UI version {NAVIGATION_UI_DEPLOY_MARKER} loaded"
    st_module.markdown(
        f'<p class="ui-nav-deploy-marker" title="Streamlit Cloud branch should be dev">'
        f"{label}</p>",
        unsafe_allow_html=True,
    )


def render_floating_nav_history(
    st_module: Any,
    session_state: dict,
    *,
    rerun_fn: Callable[[], None],
) -> None:
    """Fixed back / forward controls at the left and right edges of the main viewport."""
    import streamlit as st

    init_nav_history(session_state)
    back_ok = can_go_back(session_state)
    fwd_ok = can_go_forward(session_state)
    session_state["back_button_rendered"] = True
    session_state["forward_button_rendered"] = True
    session_state["back_button_disabled"] = not back_ok
    session_state["forward_button_disabled"] = not fwd_ok
    record_nav_history_trace(
        st_module,
        session_state,
        back_button_rendered=True,
        forward_button_rendered=True,
        back_button_disabled=not back_ok,
        forward_button_disabled=not fwd_ok,
    )

    if st_module.button(
        "← Back",
        key="studio_nav_back_btn",
        disabled=not back_ok,
        use_container_width=False,
        type="secondary",
        help="Previous page in history",
    ):
        session_state["back_button_clicked"] = True
        record_nav_history_trace(st_module, session_state, back_button_clicked=True)
        if go_back(session_state):
            _after_history_nav(
                st,
                session_state,
                target_page=str(session_state.get("studio_page") or ""),
                source="history_back",
            )
            record_nav_history_trace(st_module, session_state, back_button_clicked=True)
            rerun_fn()
    if st_module.button(
        "Forward →",
        key="studio_nav_forward_btn",
        disabled=not fwd_ok,
        use_container_width=False,
        type="secondary",
        help="Next page in history",
    ):
        session_state["forward_button_clicked"] = True
        record_nav_history_trace(st_module, session_state, forward_button_clicked=True)
        if go_forward(session_state):
            _after_history_nav(
                st,
                session_state,
                target_page=str(session_state.get("studio_page") or ""),
                source="history_forward",
            )
            record_nav_history_trace(st_module, session_state, forward_button_clicked=True)
            rerun_fn()


def render_sidebar_nav_history(
    sidebar: Any,
    session_state: dict,
    *,
    rerun_fn: Callable[[], None],
) -> None:
    """Deprecated: use ``render_floating_nav_history`` in the main area instead."""
    render_floating_nav_history(sidebar, session_state, rerun_fn=rerun_fn)


# Backward-compatible alias if an older deploy imported only this name.
render_main_nav_history = render_floating_nav_history

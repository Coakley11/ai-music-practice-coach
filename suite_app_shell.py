"""
Consistent account + workspace sidebar shell for all Daniel AI Suite apps.

Synced to sibling repos via ``scripts/sync_suite_cloud_modules.py``.
Call near the top of each app's sidebar (after ``set_page_config`` / workspace init).
"""

from __future__ import annotations

from typing import Any, Callable

__all__ = (
    "apply_suite_auth_gate",
    "render_suite_sidebar_account_shell",
    "render_suite_namespace_notices",
)


def apply_suite_auth_gate(st: Any) -> None:
    """Block app body when Real Accounts are enabled and user is not signed in."""
    try:
        from suite_auth import render_auth_gate

        render_auth_gate(st)
    except ImportError:
        pass


def render_suite_namespace_notices(st: Any) -> None:
    """Compact sidebar warnings when workspace URL/state may be inconsistent."""
    try:
        from suite_account_settings import detect_workspace_namespace_issues
    except ImportError:
        return
    for issue in detect_workspace_namespace_issues(st=st):
        severity = str(issue.get("severity") or "warning").strip()
        title = str(issue.get("title") or "Workspace notice").strip()
        detail = str(issue.get("detail") or "").strip()
        text = f"**{title}** — {detail}" if detail else f"**{title}**"
        if severity == "error":
            st.sidebar.error(text)
        elif severity == "info":
            st.sidebar.info(text)
        else:
            st.sidebar.warning(text)


def render_suite_sidebar_account_shell(
    st: Any,
    *,
    show_command_center_link: bool = True,
    show_account_panel: bool = True,
    account_panel_expanded: bool = False,
    command_center_divider: bool = True,
    top_divider: bool = False,
    nest_account_utilities: bool = True,
    saved_session_on_reset: Callable[[Any], None] | None = None,
    saved_session_app_id: str = "music",
    saved_session_label: str = "Reset to default",
    saved_session_help: str = "Clears your saved session for this app only.",
) -> None:
    """Render compact Account & Workspace (optionally nesting Command Center + Saved Sessions)."""
    try:
        from suite_workspace import bootstrap_suite_workspace

        bootstrap_suite_workspace(st)
    except ImportError:
        pass

    if top_divider:
        st.sidebar.divider()

    try:
        from suite_workspace import can_show_developer_tools

        if can_show_developer_tools(st=st):
            render_suite_namespace_notices(st)
    except ImportError:
        pass

    nest = bool(nest_account_utilities)
    try:
        from suite_account_settings import render_account_workspace_access

        if show_account_panel:
            render_account_workspace_access(
                st,
                sidebar=True,
                account_panel_expanded=account_panel_expanded,
                include_command_center=bool(show_command_center_link and nest),
                saved_session_on_reset=saved_session_on_reset if nest else None,
                saved_session_app_id=saved_session_app_id,
                saved_session_label=saved_session_label,
                saved_session_help=saved_session_help,
            )
    except ImportError:
        st.sidebar.caption("Account settings module unavailable on this deploy.")

    # Legacy top-level Command Center only when nesting is disabled.
    if show_command_center_link and not nest:
        try:
            from suite_command_center_link import render_command_center_sidebar_link

            render_command_center_sidebar_link(
                st,
                show_divider=command_center_divider,
            )
        except ImportError:
            pass
    elif command_center_divider and not nest:
        st.sidebar.divider()

    try:
        from suite_workspace import can_show_developer_tools

        if can_show_developer_tools(st=st):
            with st.sidebar.expander("Auth persistence (dev)", expanded=False):
                try:
                    from suite_auth_browser import browser_auth_storage_status

                    st.json(browser_auth_storage_status(st))
                except ImportError:
                    st.caption("suite_auth_browser unavailable")
            try:
                from suite_auth import render_auth_recovery_diagnostics

                render_auth_recovery_diagnostics(st, expanded=False)
            except ImportError:
                pass
            try:
                from suite_workspace import render_workspace_ownership_diagnostics

                render_workspace_ownership_diagnostics(st, sidebar=True)
            except ImportError:
                pass
    except Exception:
        pass

    try:
        from suite_egress_trace import render_egress_sidebar_panel

        render_egress_sidebar_panel(st)
    except ImportError:
        pass

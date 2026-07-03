"""Developer diagnostics for account-owned workspace isolation (``?dev=1``)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

WORKSPACE_ISOLATION_DEPLOY_MARKER = "workspace-ownership-v1-714655a"


def _secrets_external_user_id() -> str:
    import os

    env_id = os.environ.get("SUITE_USER_ID", "").strip()
    if env_id:
        return env_id
    try:
        import streamlit as st  # noqa: WPS433

        block = st.secrets.get("suite_activity") if hasattr(st, "secrets") else None
        if block is None:
            try:
                block = st.secrets["suite_activity"]
            except Exception:
                block = None
        if block is not None:
            for name in ("suite_user_id", "user_id", "account_id"):
                val = ""
                if hasattr(block, "get"):
                    try:
                        val = str(block.get(name) or "").strip()
                    except Exception:
                        val = ""
                if val:
                    return val
    except Exception:
        pass
    return "default"


def _secrets_user_email() -> str:
    import os

    env = os.environ.get("SUITE_USER_EMAIL", "").strip()
    if env:
        return env
    try:
        import streamlit as st  # noqa: WPS433

        block = st.secrets.get("suite_activity") if hasattr(st, "secrets") else None
        if block is None:
            try:
                block = st.secrets["suite_activity"]
            except Exception:
                block = None
        if block is not None:
            for name in ("suite_user_email", "user_email", "email"):
                val = ""
                if hasattr(block, "get"):
                    try:
                        val = str(block.get(name) or "").strip()
                    except Exception:
                        val = ""
                if val:
                    return val
    except Exception:
        pass
    return ""


def _git_short() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=2,
            cwd=str(Path(__file__).resolve().parent),
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


def _secrets_auth_enabled() -> bool | None:
    try:
        import streamlit as st  # noqa: WPS433

        block = st.secrets.get("suite_activity") if hasattr(st, "secrets") else None
        if block is None:
            try:
                block = st.secrets["suite_activity"]
            except Exception:
                return None
        if block is None:
            return None
        raw = ""
        if hasattr(block, "get"):
            try:
                raw = str(block.get("suite_auth_enabled") or "").strip().lower()
            except Exception:
                raw = ""
        return raw in ("1", "true", "yes", "on")
    except Exception:
        return None


def build_workspace_isolation_snapshot(*, st: Any | None = None) -> dict[str, Any]:
    """Structured isolation state for traces, tests, and dev sidebar."""
    ss: dict[str, Any] = {}
    if st is not None:
        try:
            ss = dict(st.session_state)
        except Exception:
            ss = {}

    auth_enabled = False
    authenticated = False
    signed_in_email = ""
    auth_external_id = ""
    owner_user_id = ""
    allowed: tuple[str, ...] = ()
    owned_workspace_id = ""
    active_workspace_id = ""
    music_data_path = ""
    music_state_path = ""
    cloud_app_key = ""
    secrets_external_id = ""
    secrets_email = ""

    try:
        from suite_auth import (
            allowed_workspaces_for_session,
            current_auth_email,
            is_auth_enabled,
            is_authenticated,
            resolve_auth_external_id,
        )

        auth_enabled = is_auth_enabled()
        authenticated = bool(ss) and is_authenticated(ss)
        if authenticated:
            signed_in_email = current_auth_email(ss)
            auth_external_id = resolve_auth_external_id(ss)
            owner_user_id = str(ss.get("_suite_auth_user_id") or "").strip()
            allowed = allowed_workspaces_for_session(ss)
    except ImportError:
        pass

    try:
        from suite_workspace_registry import get_owned_workspace_id

        if ss:
            owned_workspace_id = str(get_owned_workspace_id(ss) or "").strip()
    except ImportError:
        pass

    try:
        from suite_workspace import get_active_workspace_id, scoped_cloud_app_id

        active_workspace_id = get_active_workspace_id(st)
        cloud_app_key = scoped_cloud_app_id("music", active_workspace_id)
    except ImportError:
        active_workspace_id = str(ss.get("_suite_active_workspace_id") or "").strip()

    try:
        from music_workspace_paths import music_data_path

        music_data_path = str(music_data_path("practice_history", active_workspace_id or None))
    except Exception:
        pass

    try:
        from suite_user_persistence import state_file_path

        music_state_path = str(state_file_path("music", active_workspace_id or None))
    except Exception:
        pass

    secrets_external_id = ""
    secrets_email = ""
    try:
        secrets_external_id = _secrets_external_user_id()
        secrets_email = _secrets_user_email()
    except Exception:
        pass

    resolved_external = ""
    resolved_email = ""
    resolved_account = ""
    if authenticated:
        try:
            from suite_user import get_account_user_id, get_external_user_id, get_user_email

            resolved_external = get_external_user_id()
            resolved_email = get_user_email()
            resolved_account = get_account_user_id()
        except ImportError:
            pass

    isolation_commit = "714655a"
    head = _git_short()
    deploy_matches_isolation = head.startswith(isolation_commit) or isolation_commit.startswith(head)

    mismatch_active_vs_owned = bool(
        owned_workspace_id and active_workspace_id and owned_workspace_id != active_workspace_id
    )
    mismatch_auth_vs_active = bool(
        authenticated
        and auth_external_id
        and active_workspace_id
        and len(allowed) == 1
        and active_workspace_id not in allowed
    )

    return {
        "deploy_marker": WORKSPACE_ISOLATION_DEPLOY_MARKER,
        "git_commit": head,
        "isolation_commit": isolation_commit,
        "deploy_matches_isolation_commit": deploy_matches_isolation,
        "suite_auth_enabled_runtime": auth_enabled,
        "suite_auth_enabled_secrets": _secrets_auth_enabled(),
        "authenticated": authenticated,
        "signed_in_email": signed_in_email,
        "auth_external_id": auth_external_id,
        "owner_user_id": owner_user_id,
        "owned_workspace_id": owned_workspace_id,
        "active_workspace_id": active_workspace_id,
        "allowed_workspaces": list(allowed),
        "music_practice_history_path": music_data_path,
        "music_user_state_path": music_state_path,
        "music_cloud_app_key": cloud_app_key,
        "resolved_external_id": resolved_external,
        "resolved_account_user_id": resolved_account,
        "resolved_email": resolved_email,
        "secrets_external_id_fallback": secrets_external_id,
        "secrets_email_fallback": secrets_email,
        "mismatch_active_vs_owned": mismatch_active_vs_owned,
        "mismatch_auth_vs_active": mismatch_auth_vs_active,
        "likely_root_cause": _infer_root_cause(
            auth_enabled=auth_enabled,
            authenticated=authenticated,
            active_workspace_id=active_workspace_id,
            owned_workspace_id=owned_workspace_id,
            allowed=allowed,
            auth_external_id=auth_external_id,
            mismatch_active_vs_owned=mismatch_active_vs_owned,
        ),
    }


def _infer_root_cause(
    *,
    auth_enabled: bool,
    authenticated: bool,
    active_workspace_id: str,
    owned_workspace_id: str,
    allowed: tuple[str, ...],
    auth_external_id: str,
    mismatch_active_vs_owned: bool,
) -> str:
    if not auth_enabled:
        return "suite_auth_enabled is false — all users share legacy daniel workspace + secrets identity"
    if not authenticated:
        return "not signed in — workspace may fall back to global suite_active_workspace.json"
    if active_workspace_id == "daniel" and auth_external_id not in ("", "daniel"):
        return "active_workspace_id is daniel while signed in as non-admin — ownership clamp failed or deploy is stale"
    if mismatch_active_vs_owned:
        return "active_workspace_id differs from owned_workspace_id — session not clamped to account"
    if owned_workspace_id and active_workspace_id == owned_workspace_id:
        return "workspace id looks correct — if data is wrong, cloud/local path may still use shared secrets user row"
    if allowed and active_workspace_id not in allowed:
        return f"active workspace {active_workspace_id!r} not in allowed {list(allowed)!r}"
    return "inspect paths and cloud_app_key below"


def render_workspace_isolation_diagnostics(st: Any) -> None:
    """Sidebar expander for ``?dev=1`` (any signed-in user)."""
    try:
        from suite_workspace import is_developer_mode_enabled
    except ImportError:
        return
    if not is_developer_mode_enabled(st=st):
        return

    snap = build_workspace_isolation_snapshot(st=st)
    with st.sidebar.expander("Workspace isolation (dev)", expanded=True):
        st.markdown("**Deploy**")
        st.text(f"marker: {snap['deploy_marker']}")
        st.text(f"git_commit: {snap['git_commit']}")
        st.text(f"isolation_commit: {snap['isolation_commit']}")
        st.text(f"deploy_matches_isolation: {snap['deploy_matches_isolation_commit']}")

        st.markdown("**Auth**")
        st.text(f"suite_auth_enabled (runtime): {snap['suite_auth_enabled_runtime']}")
        secrets_flag = snap["suite_auth_enabled_secrets"]
        st.text(f"suite_auth_enabled (secrets): {secrets_flag if secrets_flag is not None else '(unreadable)'}")
        st.text(f"authenticated: {snap['authenticated']}")
        st.text(f"signed_in_email: {snap['signed_in_email'] or '(none)'}")
        st.text(f"auth_external_id: {snap['auth_external_id'] or '(none)'}")
        st.text(f"owner_user_id: {snap['owner_user_id'] or '(none)'}")

        st.markdown("**Workspace**")
        st.text(f"owned_workspace_id: {snap['owned_workspace_id'] or '(none)'}")
        st.text(f"active_workspace_id: {snap['active_workspace_id'] or '(none)'}")
        st.text(f"allowed_workspaces: {snap['allowed_workspaces']}")

        st.markdown("**Music paths**")
        st.text(f"music_data_path: {snap['music_practice_history_path'] or '(none)'}")
        st.text(f"music_user_state: {snap['music_user_state_path'] or '(none)'}")
        st.text(f"music_cloud_app_key: {snap['music_cloud_app_key'] or '(none)'}")

        st.markdown("**Resolved account (cloud rows)**")
        st.text(f"resolved_external_id: {snap['resolved_external_id'] or '(none)'}")
        st.text(f"resolved_account_user_id: {snap['resolved_account_user_id'] or '(none)'}")
        st.text(f"resolved_email: {snap['resolved_email'] or '(none)'}")
        if snap.get("secrets_external_id_fallback"):
            st.text(f"secrets suite_user_id (deploy): {snap['secrets_external_id_fallback']}")

        cause = str(snap.get("likely_root_cause") or "").strip()
        if cause:
            st.warning(f"Likely issue: {cause}")
        if snap.get("mismatch_active_vs_owned"):
            st.error("active_workspace_id ≠ owned_workspace_id")
        if snap.get("mismatch_auth_vs_active"):
            st.error("active workspace not allowed for this account")

"""
Resolve the unified suite account (same user on phone, laptop, and all apps).

Set ``suite_user_id`` in Streamlit secrets (or ``SUITE_USER_ID`` env) to the same
value on every deployment so activity and state sync across devices.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from suite_storage_config import get_cloud_config, reset_cloud_config_cache


def get_external_user_id() -> str:
    """Stable account key from env or [suite_activity] secrets; prefers signed-in auth when available."""
    try:
        import streamlit as st  # noqa: WPS433
        from suite_auth import is_auth_enabled, is_authenticated, resolve_auth_external_id

        if is_auth_enabled() and is_authenticated(st.session_state):
            ext = str(resolve_auth_external_id(st.session_state) or "").strip()
            if ext:
                return ext
    except Exception:
        pass
    env_id = os.environ.get("SUITE_USER_ID", "").strip()
    if env_id:
        return env_id
    try:
        import streamlit as st  # noqa: WPS433

        block = None
        try:
            block = st.secrets.get("suite_activity")
        except Exception:
            try:
                block = st.secrets["suite_activity"]
            except Exception:
                block = None
        if block is not None:
            for name in ("suite_user_id", "user_id", "account_id"):
                val = _read_secret(block, name)
                if val:
                    return val
    except Exception:
        pass
    return "default"


def get_user_email() -> str:
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
                val = _read_secret(block, name)
                if val:
                    return val
    except Exception:
        pass
    return ""


def get_display_name() -> str:
    env = os.environ.get("SUITE_USER_DISPLAY_NAME", "").strip()
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
            val = _read_secret(block, "display_name")
            if val:
                return val
    except Exception:
        pass
    email = get_user_email()
    if email and "@" in email:
        return email.split("@", 1)[0].replace(".", " ").title()
    ext = get_external_user_id()
    return ext.replace("_", " ").replace("-", " ").title()


def _read_secret(block: Any, name: str) -> str:
    if block is None:
        return ""
    val: Any = None
    if hasattr(block, "get"):
        try:
            val = block.get(name)
        except Exception:
            val = None
    if val is None and hasattr(block, name):
        try:
            val = getattr(block, name)
        except Exception:
            val = None
    return str(val or "").strip()


# Only a *successful* lookup is remembered. A failed ``ensure_user_row`` (a transient
# network/Supabase error) used to be cached by ``lru_cache`` for the whole process, which
# pinned the app to ``local:<id>`` and silently stopped every cloud save until a restart.
_ACCOUNT_UID_CACHE: dict[str, str] = {}
_ACCOUNT_UID_FAILURE: dict[str, Any] = {"at": 0.0, "error": ""}
_ACCOUNT_UID_RETRY_SECONDS = 20.0


def reset_account_cache() -> None:
    reset_cloud_config_cache()
    _ACCOUNT_UID_CACHE.clear()
    _ACCOUNT_UID_FAILURE.update({"at": 0.0, "error": ""})


def last_account_error() -> str:
    """Why the cloud identity could not be resolved (empty when it resolved or is unconfigured)."""
    return str(_ACCOUNT_UID_FAILURE.get("error") or "")


def _resolve_account_user_id() -> str:
    """
    Return Supabase user UUID when cloud is configured, else ``local:{external_id}``.

    A failure is not cached beyond a short back-off, so a recovered Supabase is picked up
    without restarting the app.
    """
    import time

    external = get_external_user_id()
    cfg = get_cloud_config()
    if cfg is None:
        return f"local:{external}"
    cached = _ACCOUNT_UID_CACHE.get(external)
    if cached:
        return cached
    failed_at = float(_ACCOUNT_UID_FAILURE.get("at") or 0.0)
    if failed_at and (time.time() - failed_at) < _ACCOUNT_UID_RETRY_SECONDS:
        return f"local:{external}"
    try:
        from suite_storage_supabase import ensure_user_row

        uid = ensure_user_row(
            external,
            email=get_user_email(),
            display_name=get_display_name(),
        )
    except Exception as exc:
        _ACCOUNT_UID_FAILURE.update({"at": time.time(), "error": f"{type(exc).__name__}: {str(exc)[:160]}"})
        return f"local:{external}"
    _ACCOUNT_UID_FAILURE.update({"at": 0.0, "error": ""})
    _ACCOUNT_UID_CACHE[external] = uid
    return uid


_resolve_account_user_id.cache_clear = reset_account_cache  # type: ignore[attr-defined]


def get_account_user_id() -> str:
    return _resolve_account_user_id()


def account_mode() -> str:
    """``cloud`` when Supabase user UUID is active, else ``local``."""
    uid = get_account_user_id()
    return "cloud" if uid and not uid.startswith("local:") else "local"

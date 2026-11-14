"""Explicit, fail-closed access policy for signed-in accounts (security hotfix).

Why this exists: the account (``suite_users.external_id``) and workspace used to be derived from the
signed-in EMAIL ("daniel"/"ariel" anywhere in the address, otherwise the local part) and admin was decided by
the email local part. Anyone who can register an address could therefore land in another person's account or
become admin. The Supabase service key bypasses row-level security, so the application is the only gate.

Policy (independent of any feature flag):

* an account is identified ONLY by its immutable Supabase Auth user id (a UUID); the email plays no part;
* by default an account gets its own fresh workspace ``u<first 20 hex of the id>``;
* an existing legacy workspace (``daniel``, ``ariel`` or an old local-part id) is attached ONLY through the
  operator-written map ``SUITE_PERSONAL_ACCOUNTS`` = ``{"<auth user id>": "<legacy id>"}``;
  two auth ids mapped to one legacy id are ambiguous and attach to NOBODY;
* admin is ONLY ``SUITE_ADMIN_USER_IDS`` (auth user ids);
* missing, empty or malformed configuration grants nothing (no admin, no personal workspace).

Nothing here reads, moves or rewrites stored data.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

_LOG = logging.getLogger(__name__)
PERSONAL_ENV = "SUITE_PERSONAL_ACCOUNTS"
ADMIN_ENV = "SUITE_ADMIN_USER_IDS"
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_LEGACY_ID_RE = re.compile(r"^[a-z0-9_]{1,64}$")
_OWN_ID_RE = re.compile(r"^u[0-9a-f]{20}$")


def normalize_auth_user_id(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if _UUID_RE.match(text) else ""


def is_own_workspace_id(value: Any) -> bool:
    return bool(_OWN_ID_RE.match(str(value or "").strip().lower()))


def _raw(env_name: str, secret_name: str) -> Any:
    env = os.environ.get(env_name, "").strip()
    if env:
        try:
            return json.loads(env)
        except ValueError:
            return env  # lists may be given as "id1,id2"; a malformed map is rejected by the parser
    try:
        import streamlit as st  # noqa: WPS433

        block = st.secrets.get("suite_auth")
        return block.get(secret_name) if block is not None else None
    except Exception:
        return None


def personal_accounts() -> dict[str, str]:
    """``auth user id -> legacy workspace id`` entries; ambiguous or malformed entries are dropped."""
    raw = _raw(PERSONAL_ENV, "personal_accounts")
    if raw in (None, "", {}):
        return {}
    try:
        items = dict(raw).items()
    except (TypeError, ValueError):
        _LOG.error("%s is malformed; no personal workspace is attached", PERSONAL_ENV)
        return {}
    out: dict[str, str] = {}
    for key, legacy in items:
        uid = normalize_auth_user_id(key)
        ext = str(legacy or "").strip().lower()
        if uid and _LEGACY_ID_RE.match(ext) and not is_own_workspace_id(ext) and ext != "default":
            out[uid] = ext
        else:
            _LOG.error("%s: an entry is not '<auth user uuid>': '<legacy id>' and was ignored", PERSONAL_ENV)
    counts: dict[str, int] = {}
    for ext in out.values():
        counts[ext] = counts.get(ext, 0) + 1
    return {uid: ext for uid, ext in out.items() if counts[ext] == 1}


def admin_user_ids() -> frozenset[str]:
    raw = _raw(ADMIN_ENV, "admin_user_ids")
    if isinstance(raw, str):
        raw = [p for p in re.split(r"[,\s]+", raw) if p]
    try:
        values = list(raw or [])
    except TypeError:
        return frozenset()
    return frozenset(u for u in (normalize_auth_user_id(v) for v in values) if u)


def external_id_for_auth_user(auth_user_id: Any) -> str:
    """Account/workspace key for an authenticated user; ``""`` when the id is not a valid Auth uuid."""
    uid = normalize_auth_user_id(auth_user_id)
    if not uid:
        return ""
    return personal_accounts().get(uid) or "u" + uid.replace("-", "")[:20]


def is_admin_auth_user(auth_user_id: Any) -> bool:
    uid = normalize_auth_user_id(auth_user_id)
    return bool(uid) and uid in admin_user_ids()

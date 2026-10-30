"""Who owns the AMI conversation state in this browser session.

The working exercise, its version history, the recent-turn log and the Claude enrichment cache are private to one
signed-in account in one workspace. Streamlit's ``session_state`` outlives a sign-out and an account switch in the same
tab, so ownership is recorded and checked on every READ, not only dropped on the events we know about:

* ``owner_token`` names the (account, workspace) pair the session currently belongs to.
* ``ensure_owner`` runs at the top of every AMI submit. If the state on hand was written for a different token (or for
  none, once somebody is signed in) it is purged before anything can read it.
* ``stamp`` / ``is_owned`` bind one stored object to its owner, so a reader that bypasses ``ensure_owner`` still rejects it.
* ``clear_conversation_state`` is what sign-out calls.

Only conversation state is touched. Practice Key, Key Cycling, Backing, Composition, Missions and Insight state are not.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

OWNER_KEY = "_ami_conv_owner"
OWNER_FIELD = "_owner"

# Everything AMI remembers about the conversation. Anything new that holds exercise or coaching context belongs here.
CONVERSATION_KEYS = ("_ami_last_generated_exercise",)
CONVERSATION_PREFIXES = ("_ami_conv_", "_ami_claude_")
# The caller re-derives this flag from developer mode and writes it just before every submit. It carries no private data,
# so an ownership purge must not eat it (that would silently switch enrichment off for the first submit after a purge).
_PURGE_EXEMPT = frozenset({OWNER_KEY, "_ami_claude_dev_mode"})

_ANONYMOUS = "anonymous"


def _account_of(session: Any) -> str:
    for key in ("_suite_auth_user_id", "_suite_auth_user_email"):
        value = str(session.get(key) or "").strip().lower()
        if value:
            return value
    return _ANONYMOUS


def owner_token(session: Any) -> str:
    """``account|workspace`` for the session as it is right now."""
    try:
        workspace = str(session.get("_suite_active_workspace_id") or "").strip().lower()
    except Exception:
        workspace = ""
        session = {}
    return f"{_account_of(session)}|{workspace}"


def is_conversation_key(key: object) -> bool:
    text = str(key)
    return text in CONVERSATION_KEYS or text.startswith(CONVERSATION_PREFIXES)


def clear_conversation_state(session: Any, *, keep: frozenset[str] = frozenset()) -> int:
    """Drop all remembered conversation state (sign-out, account switch). Returns how many keys went."""
    if not isinstance(session, MutableMapping):
        return 0
    removed = 0
    for key in list(session.keys()):
        if is_conversation_key(key) and str(key) not in keep:
            try:
                session.pop(key, None)
                removed += 1
            except Exception:
                continue
    return removed


def ensure_owner(session: Any) -> bool:
    """Purge conversation state that belongs to someone else. True when a purge happened."""
    if not isinstance(session, MutableMapping):
        return False
    token = owner_token(session)
    held = session.get(OWNER_KEY)
    if held == token:
        return False
    has_state = any(is_conversation_key(k) and str(k) not in _PURGE_EXEMPT for k in list(session.keys()))
    purged = False
    # ``held is None`` with state present means the state predates ownership stamping: only a session that has not
    # signed in as anyone can have produced it, so it is kept for the anonymous session and refused for everyone else.
    if has_state and (held is not None or not token.startswith(f"{_ANONYMOUS}|")):
        clear_conversation_state(session, keep=_PURGE_EXEMPT)
        purged = True
    try:
        session[OWNER_KEY] = token
    except Exception:
        pass
    return purged


def stamp(record: dict[str, Any], session: Any) -> dict[str, Any]:
    out = dict(record)
    out[OWNER_FIELD] = owner_token(session)
    return out


def is_owned(record: Any, session: Any) -> bool:
    """A stored object is usable only by the owner that wrote it. Unstamped objects count only for the anonymous owner."""
    if not isinstance(record, dict):
        return False
    token = owner_token(session)
    held = record.get(OWNER_FIELD)
    if held is None:
        return token.startswith(f"{_ANONYMOUS}|")
    return held == token


def unstamped(record: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if k != OWNER_FIELD}

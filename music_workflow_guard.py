"""Guard direct writes to authoritative workflow keys (Commit 4)."""

from __future__ import annotations

from typing import Any

AUTHORITATIVE_SESSION_KEYS: frozenset[str] = frozenset(
    {
        "_music_active_workflow",
        "_music_workflow_state_store",
        "_active_workflow_owner",
    }
)

ALLOWED_WRITER_PREFIXES: tuple[str, ...] = (
    "music_workflow_",
    "music_workflow_activation",
    "music_workflow_mutation",
    "music_workflow_legacy_projection",
    "music_workflow_state_store",
    "music_workflow_canonical_persistence",
)


def guarded_session_write(
    session: dict[str, Any],
    key: str,
    value: Any,
    *,
    caller_module: str,
    compatibility: bool = False,
) -> bool:
    if key not in AUTHORITATIVE_SESSION_KEYS:
        session[key] = value
        return True
    allowed = any(caller_module.startswith(p) for p in ALLOWED_WRITER_PREFIXES)
    try:
        from music_workflow_mutation import log_direct_owner_write_attempt

        log_direct_owner_write_attempt(session, key, caller=f"{caller_module}:{'compat' if compatibility else 'blocked'}")
    except ImportError:
        pass
    if allowed or compatibility:
        session[key] = value
        return True
    return False


__all__ = ["AUTHORITATIVE_SESSION_KEYS", "ALLOWED_WRITER_PREFIXES", "guarded_session_write"]

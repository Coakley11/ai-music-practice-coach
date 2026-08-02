"""Central write gate for contested Music session keys.

After restore phase completes, only USER-origin writes may change live widget
keys unless the workspace is truly empty (cold-start default seeding).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

MUSIC_STATE_WRITE_TRACE_KEY = "_music_state_write_trace"
MUSIC_STATE_WRITE_TRACE_MAX = 24

CONTESTED_KEYS: frozenset[str] = frozenset(
    {
        "active_catalog_pick_key",
        "selected_song",
        "matching_song_dropdown",
        "active_music_source",
        "song_picker_active_source",
        "_user_chose_catalog_music_source",
        "_backing_autoplay",
        "backing_transport_status",
        "backing_track_bpm",
        "bpm",
        "display_key",
        "active_genre",
        "active_song_title",
        "instrument",
        "level",
        "focus",
    }
)


class WriteOrigin(str, Enum):
    USER = "user"
    RESTORE = "restore"
    DEFAULT_STAMP = "default"
    CANONICAL = "canonical"
    RECONCILE = "reconcile"
    RECOVERY = "recovery"
    WIDGET_SYNC = "widget_sync"


def _trace(session: dict[str, Any], entry: dict[str, Any]) -> None:
    trace = session.setdefault(MUSIC_STATE_WRITE_TRACE_KEY, [])
    if not isinstance(trace, list):
        trace = []
        session[MUSIC_STATE_WRITE_TRACE_KEY] = trace
    trace.append(entry)
    if len(trace) > MUSIC_STATE_WRITE_TRACE_MAX:
        del trace[: len(trace) - MUSIC_STATE_WRITE_TRACE_MAX]


def record_state_write_trace(
    session: dict[str, Any],
    *,
    key: str,
    origin: WriteOrigin | str,
    writer: str,
    value: Any = None,
    blocked: bool = False,
) -> None:
    _trace(
        session,
        {
            "key": key,
            "origin": str(origin),
            "writer": writer,
            "value": str(value)[:120] if value is not None else "",
            "blocked": bool(blocked),
        },
    )


def may_write_contested(
    session: dict[str, Any],
    origin: WriteOrigin | str,
    key: str,
) -> bool:
    """True when ``key`` may be written with the given origin."""
    if key not in CONTESTED_KEYS:
        return True
    origin_val = WriteOrigin(str(origin)) if not isinstance(origin, WriteOrigin) else origin
    if origin_val == WriteOrigin.USER:
        return True
    try:
        from music_restore_phase import music_restore_phase_complete, workspace_is_truly_empty

        phase_done = music_restore_phase_complete(session)
    except ImportError:
        return True
    if not phase_done:
        return True
    if origin_val == WriteOrigin.RESTORE:
        return bool(
            session.get("_cloud_workspace_restored_this_run")
            or session.get("_suite_persist_restore_applied")
        )
    if origin_val == WriteOrigin.DEFAULT_STAMP and workspace_is_truly_empty(session):
        return True
    return False


def guarded_session_set(
    session: dict[str, Any],
    key: str,
    value: Any,
    *,
    origin: WriteOrigin | str,
    writer: str,
) -> bool:
    """Set session key when write gate allows; returns True if written."""
    if not may_write_contested(session, origin, key):
        record_state_write_trace(
            session,
            key=key,
            origin=origin,
            writer=writer,
            value=value,
            blocked=True,
        )
        try:
            from music_phase1_write_journal import record_phase1_global_write

            record_phase1_global_write(
                session,
                key=key,
                old_value=session.get(key),
                new_value=value,
                module="music_state_writes",
                function="guarded_session_set",
                reason=writer,
                origin=str(origin),
                blocked=True,
            )
        except ImportError:
            pass
        return False
    old = session.get(key)
    session[key] = value
    try:
        from music_phase1_write_journal import record_phase1_session_key_write

        record_phase1_session_key_write(
            session,
            key,
            value,
            module="music_state_writes",
            function="guarded_session_set",
            reason=writer,
            origin=str(origin),
        )
    except ImportError:
        pass
    record_state_write_trace(
        session,
        key=key,
        origin=origin,
        writer=writer,
        value=value,
        blocked=False,
    )
    return True


def last_contested_write(session: dict[str, Any], key: str) -> dict[str, Any] | None:
    trace = session.get(MUSIC_STATE_WRITE_TRACE_KEY)
    if not isinstance(trace, list):
        return None
    for entry in reversed(trace):
        if isinstance(entry, dict) and entry.get("key") == key and not entry.get("blocked"):
            return entry
    return None

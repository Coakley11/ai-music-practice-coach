"""Resolve Music Coach instrument without treating setup default Piano as user choice."""

from __future__ import annotations

from typing import Any


def _default_instrument_name() -> str:
    try:
        from practice_setup_globals import DEFAULT_INSTRUMENT

        return str(DEFAULT_INSTRUMENT or "Piano")
    except ImportError:
        return "Piano"


def instrument_change_source(session_state: dict[str, Any]) -> str:
    try:
        from practice_setup_globals import INSTRUMENT_CHANGE_SOURCE_KEY

        return str(session_state.get(INSTRUMENT_CHANGE_SOURCE_KEY) or "").strip()
    except ImportError:
        return ""


def raw_session_instrument(session_state: dict[str, Any]) -> str:
    try:
        from practice_setup_globals import GLOBAL_INSTRUMENT_KEY

        return str(session_state.get(GLOBAL_INSTRUMENT_KEY) or session_state.get("instrument") or "").strip()
    except ImportError:
        return str(session_state.get("instrument") or "").strip()


def is_uncommitted_default_piano(session_state: dict[str, Any], instrument: str) -> bool:
    """True when ``instrument`` is only the app setup default, not an explicit user pick."""
    name = str(instrument or "").strip()
    if not name:
        return False
    if name != _default_instrument_name():
        return False
    return not bool(instrument_change_source(session_state))


def resolve_coach_instrument(
    session_state: dict[str, Any],
    *,
    question_entity: str = "",
    ctx_instrument: str = "",
    snapshot_instrument: str = "",
) -> str:
    """
    Priority:
    1. Instrument named in the question (entity extract)
    2. Session / snapshot instrument when genuinely selected (not untouched default Piano)
    3. Empty → caller uses “your instrument”
    """
    q = str(question_entity or "").strip()
    if q:
        return q

    try:
        from practice_setup_globals import get_active_instrument

        active = str(get_active_instrument(session_state) or "").strip()
    except ImportError:
        active = raw_session_instrument(session_state)

    if active:
        if not is_uncommitted_default_piano(session_state, active):
            return active

    for candidate in (snapshot_instrument, ctx_instrument):
        c = str(candidate or "").strip()
        if not c:
            continue
        if not is_uncommitted_default_piano(session_state, c):
            return c
        if instrument_change_source(session_state):
            return c

    return ""


def instrument_provenance_trace(
    session_state: dict[str, Any],
    *,
    question_entity: str = "",
    ctx_instrument: str = "",
    snapshot_instrument: str = "",
    resolved: str = "",
) -> dict[str, Any]:
    """Dev-facing trace of where instrument text came from."""
    raw = raw_session_instrument(session_state)
    default_name = _default_instrument_name()
    return {
        "raw_session_instrument": raw,
        "session_equals_default_piano": raw == default_name,
        "instrument_change_source": instrument_change_source(session_state),
        "snapshot_instrument": str(snapshot_instrument or ""),
        "ctx_instrument": str(ctx_instrument or ""),
        "question_entity_instrument": str(question_entity or ""),
        "resolved_coach_instrument": str(resolved or ""),
        "resolved_is_empty": not str(resolved or "").strip(),
    }

"""Canonical, app-wide session-state for Instrument / Level / Practice Focus.

Any UI surface that changes one of these three values *must* go through
the setters in this module (or write to the canonical keys directly).
Reads can use the getters or read the keys directly - both paths are
guaranteed to return the same answer because the setters keep
``focus`` consistent with the current ``instrument``'s option list.

Canonical session_state keys
----------------------------

* ``"instrument"`` -> str (e.g. ``"Saxophone"``)
* ``"level"``      -> ``"Beginner" | "Intermediate" | "Advanced"``
* ``"focus"``      -> str matching one of
  :func:`practice_setup_controls.focus_options_for_instrument(instrument)`

These are the **only** keys the rest of the app should read from. Page-
local widgets (sidebar selectbox, quick-control row, YouTube panel,
etc.) may use prefixed widget keys *as long as they sync to / from*
these canonical keys via ``sync_widget_state_from_globals`` (before
render) and ``commit_widget_state_to_globals`` (on-change). That keeps
every surface showing the same value.
"""

from __future__ import annotations

from typing import Any, Mapping

from practice_setup_controls import (
    DEFAULT_INSTRUMENT_OPTIONS,
    LEVEL_OPTIONS,
    focus_options_for_instrument,
)

# Canonical session_state keys - importing modules should reference
# these constants rather than hardcoding the string literals so a future
# rename stays painless.
GLOBAL_INSTRUMENT_KEY = "instrument"
GLOBAL_LEVEL_KEY = "level"
GLOBAL_FOCUS_KEY = "focus"

DEFAULT_INSTRUMENT = "Piano"
DEFAULT_LEVEL = "Intermediate"

INSTRUMENT_CHANGE_SOURCE_KEY = "instrument_change_source"
LEVEL_CHANGE_SOURCE_KEY = "level_change_source"
FOCUS_CHANGE_SOURCE_KEY = "focus_change_source"
DISPLAY_KEY_CHANGE_SOURCE_KEY = "display_key_change_source"
GLOBAL_CONTROL_OVERWRITE_SOURCE_KEY = "global_control_overwrite_source"

_GLOBAL_CONTROL_SOURCE_KEYS: dict[str, str] = {
    GLOBAL_INSTRUMENT_KEY: INSTRUMENT_CHANGE_SOURCE_KEY,
    GLOBAL_LEVEL_KEY: LEVEL_CHANGE_SOURCE_KEY,
    GLOBAL_FOCUS_KEY: FOCUS_CHANGE_SOURCE_KEY,
    "display_key": DISPLAY_KEY_CHANGE_SOURCE_KEY,
}

__all__ = (
    "GLOBAL_INSTRUMENT_KEY",
    "GLOBAL_LEVEL_KEY",
    "GLOBAL_FOCUS_KEY",
    "DEFAULT_INSTRUMENT",
    "DEFAULT_LEVEL",
    "INSTRUMENT_CHANGE_SOURCE_KEY",
    "LEVEL_CHANGE_SOURCE_KEY",
    "FOCUS_CHANGE_SOURCE_KEY",
    "DISPLAY_KEY_CHANGE_SOURCE_KEY",
    "GLOBAL_CONTROL_OVERWRITE_SOURCE_KEY",
    "get_active_instrument",
    "get_active_level",
    "get_active_focus",
    "set_active_instrument",
    "set_active_level",
    "set_active_focus",
    "ensure_global_setup_defaults",
    "record_global_control_change",
    "valid_focus_for",
    "sync_widget_state_from_globals",
    "commit_widget_state_to_globals",
)


def _as_str(value: Any, fallback: str) -> str:
    raw = str(value or "").strip()
    return raw or fallback


# ---------------------------------------------------------------------------
# Getters
# ---------------------------------------------------------------------------


def get_active_instrument(session_state: Any) -> str:
    return _as_str(session_state.get(GLOBAL_INSTRUMENT_KEY), DEFAULT_INSTRUMENT)


def get_active_level(session_state: Any) -> str:
    raw = _as_str(session_state.get(GLOBAL_LEVEL_KEY), DEFAULT_LEVEL)
    if raw not in LEVEL_OPTIONS:
        return DEFAULT_LEVEL
    return raw


def get_active_focus(session_state: Any) -> str:
    instrument = get_active_instrument(session_state)
    opts = focus_options_for_instrument(instrument)
    raw = _as_str(session_state.get(GLOBAL_FOCUS_KEY), opts[0] if opts else "")
    if opts and raw not in opts:
        return opts[0]
    return raw


def valid_focus_for(instrument: str, candidate: Any) -> str:
    """Return ``candidate`` if it's a valid focus for ``instrument``, else
    the instrument's first focus option."""
    opts = focus_options_for_instrument(instrument)
    raw = _as_str(candidate, opts[0] if opts else "")
    if opts and raw not in opts:
        return opts[0]
    return raw


# ---------------------------------------------------------------------------
# Setters
# ---------------------------------------------------------------------------


def record_global_control_change(
    session_state: Any,
    field: str,
    source: str,
    *,
    overwrite: bool = False,
) -> None:
    """Record who last wrote a global control (sidebar, canonical prepare, etc.)."""
    diag_key = _GLOBAL_CONTROL_SOURCE_KEYS.get(field)
    if diag_key:
        session_state[diag_key] = str(source or "").strip() or "unknown"
    if overwrite:
        session_state[GLOBAL_CONTROL_OVERWRITE_SOURCE_KEY] = (
            f"{field}:{source or 'unknown'}"
        )


def ensure_global_setup_defaults(session_state: Any) -> None:
    """Populate any missing global setup keys with safe defaults.

    Safe to call multiple times per render - existing values are kept.
    """
    if not session_state.get(GLOBAL_INSTRUMENT_KEY):
        session_state[GLOBAL_INSTRUMENT_KEY] = DEFAULT_INSTRUMENT
    if session_state.get(GLOBAL_LEVEL_KEY) not in LEVEL_OPTIONS:
        session_state[GLOBAL_LEVEL_KEY] = DEFAULT_LEVEL
    # Validate focus against the current instrument's option list.
    inst = get_active_instrument(session_state)
    opts = focus_options_for_instrument(inst)
    current_focus = _as_str(session_state.get(GLOBAL_FOCUS_KEY), "")
    if opts and current_focus not in opts:
        session_state[GLOBAL_FOCUS_KEY] = opts[0]


def set_active_instrument(session_state: Any, value: Any, *, source: str = "setter") -> str:
    """Set the global instrument and re-validate the global focus.

    Returns the actual value stored (may differ from the input when an
    unknown instrument falls back to the default).
    """
    instrument = _as_str(value, DEFAULT_INSTRUMENT)
    if instrument not in DEFAULT_INSTRUMENT_OPTIONS:
        # Unknown instruments still flow through - some pages add
        # "Other" or instrument variants. Don't drop the value; just
        # keep it as-is.
        pass
    session_state[GLOBAL_INSTRUMENT_KEY] = instrument
    record_global_control_change(session_state, GLOBAL_INSTRUMENT_KEY, source)
    # Re-align focus against the new instrument's option list.
    opts = focus_options_for_instrument(instrument)
    current_focus = _as_str(session_state.get(GLOBAL_FOCUS_KEY), "")
    if opts and current_focus not in opts:
        session_state[GLOBAL_FOCUS_KEY] = opts[0]
        record_global_control_change(session_state, GLOBAL_FOCUS_KEY, f"{source}:focus_clamp")
    return instrument


def set_active_level(session_state: Any, value: Any, *, source: str = "setter") -> str:
    level = _as_str(value, DEFAULT_LEVEL)
    if level not in LEVEL_OPTIONS:
        level = DEFAULT_LEVEL
    session_state[GLOBAL_LEVEL_KEY] = level
    record_global_control_change(session_state, GLOBAL_LEVEL_KEY, source)
    return level


def set_active_focus(session_state: Any, value: Any, *, source: str = "setter") -> str:
    """Set the global focus, validated against the current instrument."""
    instrument = get_active_instrument(session_state)
    opts = focus_options_for_instrument(instrument)
    focus = _as_str(value, opts[0] if opts else "")
    if opts and focus not in opts:
        focus = opts[0]
    session_state[GLOBAL_FOCUS_KEY] = focus
    record_global_control_change(session_state, GLOBAL_FOCUS_KEY, source)
    return focus


# ---------------------------------------------------------------------------
# Widget-state sync helpers
# ---------------------------------------------------------------------------


def sync_widget_state_from_globals(
    session_state: Any,
    *,
    instrument_widget_key: str | None = None,
    level_widget_key: str | None = None,
    focus_widget_key: str | None = None,
    instrument_options: Mapping[int, str] | list[str] | None = None,
    level_options: Mapping[int, str] | list[str] | None = None,
    focus_options: Mapping[int, str] | list[str] | None = None,
) -> tuple[str, str, str]:
    """Pre-fill page-local widget keys from the global setup keys.

    Must be called **before** the widgets render. Each ``*_widget_key``
    is optional - omit it if the surface doesn't render that control.

    The function also clamps any out-of-options value back to the
    first valid option (and writes the clamped value back to the
    global key) so widgets never receive a value Streamlit would
    refuse.
    """
    ensure_global_setup_defaults(session_state)

    instrument = get_active_instrument(session_state)
    if instrument_options is not None:
        opts = list(instrument_options)
        if opts and instrument not in opts:
            instrument = opts[0]
            session_state[GLOBAL_INSTRUMENT_KEY] = instrument
    if instrument_widget_key:
        session_state[instrument_widget_key] = instrument

    level = get_active_level(session_state)
    if level_options is not None:
        opts = list(level_options)
        if opts and level not in opts:
            level = opts[0]
            session_state[GLOBAL_LEVEL_KEY] = level
    if level_widget_key:
        session_state[level_widget_key] = level

    focus = get_active_focus(session_state)
    if focus_options is not None:
        opts = list(focus_options)
        if opts and focus not in opts:
            focus = opts[0]
            session_state[GLOBAL_FOCUS_KEY] = focus
    if focus_widget_key:
        session_state[focus_widget_key] = focus

    return instrument, level, focus


def commit_widget_state_to_globals(
    session_state: Any,
    *,
    instrument_widget_key: str | None = None,
    level_widget_key: str | None = None,
    focus_widget_key: str | None = None,
) -> tuple[str, str, str]:
    """Push the value currently held in page-local widget keys back to
    the canonical globals.

    Intended for ``on_change`` callbacks: when a local control changes,
    call this so every other surface (sidebar, other pages, status
    bars) reads the new value on next render.
    """
    if instrument_widget_key and session_state.get(instrument_widget_key) is not None:
        set_active_instrument(session_state, session_state[instrument_widget_key])
    if level_widget_key and session_state.get(level_widget_key) is not None:
        set_active_level(session_state, session_state[level_widget_key])
    if focus_widget_key and session_state.get(focus_widget_key) is not None:
        set_active_focus(session_state, session_state[focus_widget_key])
    return (
        get_active_instrument(session_state),
        get_active_level(session_state),
        get_active_focus(session_state),
    )

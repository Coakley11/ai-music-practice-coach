"""Trace global instrument/level/focus overwrites (?dev=1)."""

from __future__ import annotations

from typing import Any

GLOBAL_CONTROL_DIAG_KEY = "_music_global_control_diag"


def record_global_control_diag(session: dict[str, Any], **fields: Any) -> None:
    diag = session.get(GLOBAL_CONTROL_DIAG_KEY)
    if not isinstance(diag, dict):
        diag = {}
    diag.update({k: v for k, v in fields.items() if v is not None})
    session[GLOBAL_CONTROL_DIAG_KEY] = diag


def note_global_control_widget_attempt(
    session: dict[str, Any],
    *,
    field: str,
    attempted_value: str,
    source: str = "widget_callback",
) -> None:
    record_global_control_diag(
        session,
        widget_field=field,
        widget_attempted_value=attempted_value,
        canonical_before=session.get(field),
        overwrite_source=source,
    )


def collect_global_control_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    diag = session.get(GLOBAL_CONTROL_DIAG_KEY)
    out = dict(diag) if isinstance(diag, dict) else {}
    for key in ("instrument", "level", "focus"):
        out.setdefault(f"final_{key}", session.get(key))
    try:
        from music_startup_save_suppression import collect_startup_save_suppression_diagnostics

        out["startup"] = collect_startup_save_suppression_diagnostics(session)
    except ImportError:
        pass
    return out


__all__ = [
    "GLOBAL_CONTROL_DIAG_KEY",
    "collect_global_control_diagnostics",
    "note_global_control_widget_attempt",
    "record_global_control_diag",
]

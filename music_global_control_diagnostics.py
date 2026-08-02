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
    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY

        meta = session.get(ACTIVE_SONG_STATE_KEY)
        canon_before = (
            str(meta.get(field) or "").strip()
            if isinstance(meta, dict)
            else str(session.get(field) or "").strip()
        )
    except ImportError:
        canon_before = str(session.get(field) or "").strip()
    record_global_control_diag(
        session,
        widget_field=field,
        widget_attempted_value=attempted_value,
        attempted_widget_value=attempted_value,
        canonical_before=canon_before,
        overwrite_source=source,
        overwrite_function=f"sidebar_on_change_{field}",
    )


def finalize_global_control_widget_diag(session: dict[str, Any], *, field: str) -> None:
    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY

        meta = session.get(ACTIVE_SONG_STATE_KEY)
        final_canonical = (
            str(meta.get(field) or "").strip()
            if isinstance(meta, dict)
            else str(session.get(field) or "").strip()
        )
    except ImportError:
        final_canonical = str(session.get(field) or "").strip()
    record_global_control_diag(
        session,
        canonical_after_callback=final_canonical,
        final_canonical_value=final_canonical,
        final_widget_value=session.get(field),
    )


def collect_global_control_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    diag = session.get(GLOBAL_CONTROL_DIAG_KEY)
    out = dict(diag) if isinstance(diag, dict) else {}
    for key in ("instrument", "level", "focus"):
        out.setdefault(f"final_{key}", session.get(key))
        out.setdefault(f"final_widget_value", session.get(key))
    try:
        from music_restore_phase import global_controls_restore_projection_complete

        out.setdefault(
            "restore_projection_applied_this_run",
            global_controls_restore_projection_complete(session),
        )
    except ImportError:
        pass
    try:
        from music_startup_save_suppression import collect_startup_save_suppression_diagnostics

        out["startup"] = collect_startup_save_suppression_diagnostics(session)
    except ImportError:
        pass
    return out


__all__ = [
    "GLOBAL_CONTROL_DIAG_KEY",
    "collect_global_control_diagnostics",
    "finalize_global_control_widget_diag",
    "note_global_control_widget_attempt",
    "record_global_control_diag",
]

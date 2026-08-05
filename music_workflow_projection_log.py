"""Diagnostics for deferred workflow legacy projection."""

from __future__ import annotations

import sys
from typing import Any


def log_projection_defer(
    session: dict[str, Any],
    *,
    result: str,
    rollback_mode: str,
    legacy_restore_attempted: bool,
    deferred_projection: bool,
    widgets_locked: bool,
    extra: dict[str, Any] | None = None,
) -> None:
    payload = {
        "widgets_locked": widgets_locked,
        "result": result,
        "rollback_mode": rollback_mode,
        "legacy_restore_attempted": legacy_restore_attempted,
        "deferred_projection": deferred_projection,
    }
    if extra:
        payload.update(extra)
    session["_music_projection_diag"] = payload
    line = (
        f"[music_projection] widgets_locked={widgets_locked} "
        f"result={result} rollback_mode={rollback_mode} "
        f"legacy_restore_attempted={legacy_restore_attempted} "
        f"deferred_projection={deferred_projection}"
    )
    print(line, flush=True, file=sys.stderr)


__all__ = ["log_projection_defer"]

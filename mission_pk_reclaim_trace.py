"""Env-gated Mission Backing reclaim dump. Writes only under MUSIC_APP_DATA_DIR."""

from __future__ import annotations

import json
import os
import time
import traceback
from pathlib import Path
from typing import Any


def _enabled() -> bool:
    return bool(str(os.environ.get("MUSIC_APP_DATA_DIR") or "").strip())


def _path() -> Path:
    return Path(str(os.environ.get("MUSIC_APP_DATA_DIR") or "").strip()) / "_mission_pk_reclaim.jsonl"


def note_mission_pk_reclaim(
    session: dict[str, Any],
    *,
    writer: str,
    extra: dict[str, Any] | None = None,
) -> None:
    if not _enabled():
        return
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
    except Exception:
        ctx = None
    prev = str(session.get("_mission_pk_reclaim_prev_src") or "").strip()
    src = str(getattr(ctx, "source", "") or "").strip() if ctx is not None else ""
    row: dict[str, Any] = {
        "t": time.time(),
        "writer": writer,
        "prev_src": prev,
        "ctx_source": src,
        "handoff": str(session.get("_backing_explicit_handoff_source") or ""),
        "released": bool(session.get("_backing_released_specialized_context")),
        "intent": str(session.get("_backing_open_intent") or ""),
        "display_key": str(session.get("display_key") or ""),
        "concert_key": str(session.get("concert_key") or ""),
        "studio_page": str(session.get("studio_page") or ""),
        "active_music_source": str(session.get("active_music_source") or ""),
        "pick": str(session.get("active_catalog_pick_key") or ""),
        "mission": str(session.get("improv_active_mission") or ""),
        "stack": "".join(traceback.format_stack(limit=18)),
    }
    if extra:
        row.update(extra)
    try:
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except Exception:
        pass
    session["_mission_pk_reclaim_prev_src"] = src or prev


def stamp_mission_ctx_source(session: dict[str, Any]) -> None:
    if not _enabled():
        return
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        session["_mission_pk_reclaim_prev_src"] = str(getattr(ctx, "source", "") or "")
    except Exception:
        pass

"""Trace Capo canonical vs widget on sidebar render (refresh hydrate order)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

TRACE_PATH = Path("scripts/evidence-creative-backing/capo-refresh-trace.jsonl")
SEQ_KEY = "_capo_refresh_trace_seq"


def _snap(session: dict[str, Any]) -> dict[str, Any]:
    from guitar_capo import (
        CAPO_ENABLED_KEY,
        CAPO_ENABLED_WIDGET_KEY,
        CAPO_SHAPE_KEY,
        CAPO_SHAPE_WIDGET_KEY,
        CAPO_SOUNDING_KEY,
        capo_fret_for_shape,
    )

    meta = session.get("active_song_state") if isinstance(session.get("active_song_state"), dict) else {}
    enabled = bool(session.get(CAPO_ENABLED_KEY))
    shape = str(session.get(CAPO_SHAPE_KEY) or "").strip()
    sounding = str(session.get(CAPO_SOUNDING_KEY) or session.get("display_key") or "").strip()
    fret = None
    try:
        if enabled and shape and sounding:
            fret = int(capo_fret_for_shape(sounding, shape))
    except Exception:
        fret = None
    restore_complete = None
    try:
        from music_restore_phase import music_restore_phase_complete

        restore_complete = bool(music_restore_phase_complete(session))
    except Exception:
        pass
    return {
        "t": time.time(),
        "studio_page": str(session.get("studio_page") or ""),
        "instrument": str(session.get("instrument") or ""),
        "display_key": str(session.get("display_key") or ""),
        "capo_enabled": enabled,
        "capo_shape": shape,
        "capo_sounding": sounding,
        "capo_fret": fret,
        "widget_enabled": session.get(CAPO_ENABLED_WIDGET_KEY),
        "widget_shape": str(session.get(CAPO_SHAPE_WIDGET_KEY) or ""),
        "pending_enabled": session.get("_pending_capo_enabled_widget"),
        "pending_shape": str(session.get("_pending_capo_shape_key") or ""),
        "seeded": bool(session.get("_capo_on_shape_seeded")),
        "meta_enabled": bool(meta.get(CAPO_ENABLED_KEY)) if meta else None,
        "meta_shape": str(meta.get(CAPO_SHAPE_KEY) or "") if meta else "",
        "restore_complete": restore_complete,
        "song": str(session.get("song") or ""),
        "pick": str(session.get("active_catalog_pick_key") or "")[:80],
    }


def note_capo_refresh(session: dict[str, Any], *, phase: str, **extra: Any) -> None:
    try:
        seq = int(session.get(SEQ_KEY) or 0) + 1
        session[SEQ_KEY] = seq
        row = {"event": "capo_refresh", "seq": seq, "phase": phase, **_snap(session), **extra}
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass

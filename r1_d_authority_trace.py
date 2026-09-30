"""R1 D authority trace — ordered owner fields around Use Catalog remount reclaim."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

_TRACE_PATH = Path("scripts/evidence-creative-backing/r1-d-authority-trace.jsonl")
_SEQ = 0


def reset_r1_d_authority_trace() -> None:
    global _SEQ
    _SEQ = 0
    try:
        _TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _TRACE_PATH.write_text("", encoding="utf-8")
    except Exception:
        pass


def _snap(session: dict[str, Any]) -> dict[str, Any]:
    ctx = session.get("backing_context")
    ctx_source = ""
    if isinstance(ctx, dict):
        ctx_source = str(ctx.get("source") or "")
    elif ctx is not None:
        ctx_source = str(getattr(ctx, "source", "") or "")
    sel = session.get("selected_song")
    sel_pick = ""
    sel_title = ""
    if isinstance(sel, dict):
        sel_pick = str(sel.get("pick_key") or "")
        sel_title = str(sel.get("title") or "")
    meta = session.get("active_song_state")
    meta_pick = ""
    meta_src = ""
    if isinstance(meta, dict):
        meta_pick = str(meta.get("pick_key") or "")
        meta_src = str(meta.get("music_source") or "")
    loop = session.get("practice_loop_backing") or session.get("_practice_loop_backing")
    loop_owner = ""
    if isinstance(loop, dict):
        loop_owner = str(loop.get("owner") or "")
    return {
        "active_music_source": str(session.get("active_music_source") or ""),
        "explicit_choice": str(session.get("explicit_music_source_choice") or ""),
        "user_catalog": bool(session.get("_user_chose_catalog_music_source")),
        "force_catalog": int(session.get("_force_catalog_backing_after_use_catalog") or 0),
        "force_composition": bool(session.get("_force_composition_backing_open")),
        "pick": str(session.get("active_catalog_pick_key") or ""),
        "song": str(session.get("song") or ""),
        "selected_pick": sel_pick,
        "selected_title": sel_title,
        "meta_pick": meta_pick,
        "meta_src": meta_src,
        "picker_radio": str(session.get("song_picker_active_source") or ""),
        "backing_ctx": ctx_source,
        "backing_pref": str(session.get("backing_source_preference") or ""),
        "display_key": str(session.get("display_key") or ""),
        "concert_key": str(session.get("concert_key") or ""),
        "loop_owner": loop_owner,
    }


def trace_r1_d_authority(
    session: dict[str, Any],
    *,
    phase: str,
    fn: str = "",
    note: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    """Append one ordered authority snapshot for R1 journey D."""
    global _SEQ
    _SEQ += 1
    row: dict[str, Any] = {
        "seq": _SEQ,
        "t": time.time(),
        "phase": phase,
        "fn": fn,
        "note": note,
        "state": _snap(session),
    }
    if extra:
        row["extra"] = extra
    try:
        # Cheap derived owner signals for reading the reclaim story.
        from songs.music_source import (
            composition_song_is_active,
            picker_composition_mode,
        )

        row["derived"] = {
            "composition_song_is_active": bool(composition_song_is_active(session)),
            "picker_composition_mode": bool(picker_composition_mode(session)),
        }
    except Exception as exc:
        row["derived_error"] = f"{type(exc).__name__}: {exc}"
    try:
        _TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _TRACE_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass

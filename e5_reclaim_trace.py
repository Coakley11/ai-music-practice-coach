"""High-frequency E5 reclaim tracer — Custom Trial → Catalog Country Roads.

Writes JSONL rows to scripts/evidence-creative-backing/e5-reclaim-trace.jsonl
whenever active ownership flips custom→catalog (or samples on request).
"""

from __future__ import annotations

import json
import time
import traceback
from pathlib import Path
from typing import Any

TRACE_PATH = Path("scripts/evidence-creative-backing/e5-reclaim-trace.jsonl")
SAMPLE_ENABLED_KEY = "_e5_reclaim_sample_enabled"
LAST_OWNER_SNAP_KEY = "_e5_reclaim_last_owner_snap"
SEQ_KEY = "_e5_reclaim_seq"


def _owner_snap(session: dict[str, Any]) -> dict[str, Any]:
    from songs.music_source import (
        ACTIVE_MUSIC_SOURCE_KEY,
        PENDING_CATALOG_FROM_PICKER_KEY,
        PENDING_CUSTOM_ACTIVE_SONG_KEY,
        PENDING_CUSTOM_LIBRARY_ACTION_KEY,
        SONG_PICKER_ACTIVE_SOURCE_KEY,
        USER_CATALOG_SOURCE_CHOICE_KEY,
        LAST_RECONCILED_SONG_PICKER_SOURCE_KEY,
        SOURCE_CUSTOM,
        custom_progression_is_active,
        is_custom_progression,
    )
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    sel = session.get(SELECTED_SONG_STATE_KEY) if isinstance(session.get(SELECTED_SONG_STATE_KEY), dict) else {}
    meta = session.get("active_song_state") if isinstance(session.get("active_song_state"), dict) else {}
    cpl = session.get("cpl_active_progression") if isinstance(session.get("cpl_active_progression"), dict) else {}
    cloud_pk = ""
    try:
        from songs.state import _pick_key_from_cloud_payload

        cloud_pk = str(_pick_key_from_cloud_payload(session) or "").strip()
    except Exception:
        pass
    return {
        "t": time.time(),
        "studio_page": str(session.get("studio_page") or ""),
        "active_music_source": str(session.get(ACTIVE_MUSIC_SOURCE_KEY) or ""),
        "is_custom": bool(is_custom_progression(session)),
        "custom_active": bool(custom_progression_is_active(session)),
        "pick": str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").strip(),
        "sel_title": str(sel.get("title") or sel.get("name") or "").strip(),
        "sel_pick": str(sel.get("pick_key") or "").strip(),
        "meta_source": str(meta.get("music_source") or "").strip(),
        "meta_pick": str(meta.get("pick_key") or "").strip(),
        "meta_name": str(meta.get("custom_progression_name") or "").strip(),
        "cpl_name": str(cpl.get("name") or "").strip(),
        "cpl_id": str(cpl.get("id") or "").strip(),
        "picker": str(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip(),
        "last_reconciled": str(session.get(LAST_RECONCILED_SONG_PICKER_SOURCE_KEY) or "").strip(),
        "user_catalog": bool(session.get(USER_CATALOG_SOURCE_CHOICE_KEY)),
        "pending_catalog": bool(session.get(PENDING_CATALOG_FROM_PICKER_KEY)),
        "pending_custom": bool(session.get(PENDING_CUSTOM_ACTIVE_SONG_KEY)),
        "pending_lib": bool(session.get(PENDING_CUSTOM_LIBRARY_ACTION_KEY)),
        "cloud_pk": cloud_pk,
        "custom_epoch": session.get("_explicit_custom_activation_epoch"),
        "owns_custom": bool(
            is_custom_progression(session)
            or custom_progression_is_active(session)
            or str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").startswith("custom::")
            or str(meta.get("music_source") or "") == SOURCE_CUSTOM
        ),
    }


def _append(row: dict[str, Any]) -> None:
    try:
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=True, default=str) + "\n")
    except Exception:
        pass


def enable_e5_reclaim_sampling(session: dict[str, Any]) -> None:
    session[SAMPLE_ENABLED_KEY] = True
    session[LAST_OWNER_SNAP_KEY] = _owner_snap(session)
    _append({"event": "sample_enabled", **session[LAST_OWNER_SNAP_KEY]})


def note_e5_reclaim_sample(session: dict[str, Any], *, phase: str = "") -> None:
    """Call from prepare/hydrate hot paths while sampling is enabled."""
    if not session.get(SAMPLE_ENABLED_KEY):
        return
    snap = _owner_snap(session)
    prev = session.get(LAST_OWNER_SNAP_KEY) if isinstance(session.get(LAST_OWNER_SNAP_KEY), dict) else {}
    session[LAST_OWNER_SNAP_KEY] = snap
    seq = int(session.get(SEQ_KEY) or 0) + 1
    session[SEQ_KEY] = seq
    flipped = bool(prev.get("owns_custom")) and not bool(snap.get("owns_custom"))
    row = {
        "event": "reclaim" if flipped else "sample",
        "seq": seq,
        "phase": phase,
        **snap,
        "prev_owns_custom": prev.get("owns_custom"),
        "prev_pick": prev.get("pick"),
        "prev_source": prev.get("active_music_source"),
        "prev_sel": prev.get("sel_title"),
    }
    if flipped:
        row["stack"] = "".join(traceback.format_stack(limit=18))
    _append(row)
    if flipped:
        # Keep sampling a few more ticks after reclaim for context.
        session["_e5_reclaim_caught"] = True


def note_e5_reclaim_writer(
    session: dict[str, Any],
    *,
    writer: str,
    reason: str = "",
    new_pick: str = "",
) -> None:
    """Call at catalog-commit entry points when leaving custom ownership."""
    try:
        from songs.music_source import SOURCE_CUSTOM, is_custom_progression, custom_progression_is_active

        was_custom = bool(
            is_custom_progression(session)
            or custom_progression_is_active(session)
            or str(session.get("active_catalog_pick_key") or "").startswith("custom::")
            or (
                isinstance(session.get("active_song_state"), dict)
                and str((session.get("active_song_state") or {}).get("music_source") or "")
                == SOURCE_CUSTOM
            )
        )
    except Exception:
        was_custom = False
    if not was_custom and not session.get(SAMPLE_ENABLED_KEY):
        return
    snap = _owner_snap(session)
    seq = int(session.get(SEQ_KEY) or 0) + 1
    session[SEQ_KEY] = seq
    _append(
        {
            "event": "writer",
            "seq": seq,
            "writer": writer,
            "reason": reason,
            "new_pick": new_pick,
            "was_custom": was_custom,
            "stack": "".join(traceback.format_stack(limit=20)),
            **snap,
        }
    )

"""Where an unsaved Multitrack take actually lives, at every transition that could lose it.

A take was recorded on a laptop, Save Layer was never pressed, the musician visited another page
and came back, and the recording was gone. A completed take goes straight into
``mt_tracks[slot]`` and nowhere else, while three places are meant to be able to answer for it:

    mt_tracks[slot]                                   the live working session
    _mt_tracks_persist_blob[slot]                     the encoded copy for saving
    _studio_page_snapshots["multitrack"]["mt_tracks"] the per-page snapshot

``resolve_multitrack_slot_bytes`` reads them in that order, so a draft can be present in one and
absent from another and still look fine - or look gone while the bytes are really there. Reading
the code narrows the suspects (a page snapshot captured BEFORE the recording, re-applied on the
way back) but cannot say which one actually happens, so this records it.

It logs **sizes and fingerprints only** - never audio, never a filename a musician typed, never
anything from the take itself. A fingerprint is the first 8 hex characters of the SHA-256 of the
bytes, which is enough to tell "the same take" from "a different take" and nothing else.

Env-gated: set ``MUSIC_MT_DRAFT_TRACE=1``. Off, every call returns immediately.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

TRACE_FILENAME = "_mt_draft_trace.jsonl"


def enabled() -> bool:
    return str(os.environ.get("MUSIC_MT_DRAFT_TRACE") or "").strip().lower() in (
        "1", "true", "yes", "on")


def _fp(data: Any) -> dict[str, Any]:
    """Size and a short fingerprint. Never the content."""
    if data is None:
        return {"present": False}
    try:
        raw = bytes(data)
    except Exception:
        return {"present": True, "not_bytes": type(data).__name__}
    if not raw:
        return {"present": False, "empty": True}
    return {"present": True, "bytes": len(raw),
            "fp": hashlib.sha256(raw).hexdigest()[:8]}


def _slot_map(value: Any, slot: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"map": False}
    return _fp(value.get(slot))


def snapshot(session_state: Any, slot: str) -> dict[str, Any]:
    """Every place this slot's audio could be, measured the same way."""
    out: dict[str, Any] = {"slot": slot}
    try:
        out["mt_tracks"] = _slot_map(session_state.get("mt_tracks"), slot)
    except Exception as exc:
        out["mt_tracks"] = {"error": type(exc).__name__}
    try:
        blob = session_state.get("_mt_tracks_persist_blob")
        if isinstance(blob, dict):
            entry = blob.get(slot)
            # The blob holds encoded strings rather than raw bytes, so its length is reported
            # as the encoded length - comparable with itself across transitions, which is what
            # this is for.
            if isinstance(entry, str):
                out["persist_blob"] = {"present": True, "encoded_len": len(entry),
                                       "fp": hashlib.sha256(entry.encode()).hexdigest()[:8]}
            else:
                out["persist_blob"] = _fp(entry)
        else:
            out["persist_blob"] = {"map": False}
    except Exception as exc:
        out["persist_blob"] = {"error": type(exc).__name__}
    try:
        store = session_state.get("_studio_page_snapshots")
        snap = store.get("multitrack") if isinstance(store, dict) else None
        out["page_snapshot"] = (_slot_map(snap.get("mt_tracks"), slot)
                                if isinstance(snap, dict) else {"snapshot": False})
    except Exception as exc:
        out["page_snapshot"] = {"error": type(exc).__name__}
    try:
        from multitrack_session_persistence import resolve_multitrack_slot_bytes

        out["resolved"] = _fp(resolve_multitrack_slot_bytes(session_state, slot))
    except Exception as exc:
        out["resolved"] = {"error": type(exc).__name__}
    return out


def note(session_state: Any, stage: str, *, slots: Any = None, **extra: Any) -> None:
    """One line: what stage this is, and where the audio for each slot is."""
    if not enabled():
        return
    try:
        if slots is None:
            try:
                from multitrack_slots import MULTITRACK_SLOTS

                slots = MULTITRACK_SLOTS
            except ImportError:
                slots = ()
        row: dict[str, Any] = {
            "t": round(time.time(), 3),
            "stage": str(stage),
        }
        for key in ("studio_page", "multitrack_catalog_active_id"):
            try:
                row[key] = str(session_state.get(key) or "")
            except Exception:
                row[key] = "<unreadable>"
        row.update({k: v for k, v in extra.items()})
        places = []
        for slot in slots:
            place = snapshot(session_state, slot)
            if any(isinstance(v, dict) and v.get("present") for v in place.values()):
                places.append(place)
        row["slots_with_audio"] = places
        row["slots_with_audio_count"] = len(places)
        path = os.path.join(os.environ.get("MUSIC_APP_DATA_DIR") or ".", TRACE_FILENAME)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        return


__all__ = ["TRACE_FILENAME", "enabled", "note", "snapshot"]

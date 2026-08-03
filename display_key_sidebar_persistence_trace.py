"""Trace explicit sidebar Display key changes vs Creative projection (?dev=1)."""

from __future__ import annotations

import copy
from typing import Any

DISPLAY_KEY_SIDEBAR_TRACE_KEY = "_display_key_sidebar_user_change_trace"


def _trace(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(DISPLAY_KEY_SIDEBAR_TRACE_KEY)
    if isinstance(raw, dict):
        return raw
    d: dict[str, Any] = {"events": []}
    session[DISPLAY_KEY_SIDEBAR_TRACE_KEY] = d
    return d


def _canonical_display_key(session: dict[str, Any]) -> str:
    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY, canonical_active_song_context

        ctx = canonical_active_song_context(session)
        if isinstance(ctx, dict):
            return str(ctx.get("display_key") or "").strip()
    except ImportError:
        pass
    meta = session.get(ACTIVE_SONG_STATE_KEY)
    if isinstance(meta, dict):
        return str(meta.get("display_key") or "").strip()
    return ""


def record_display_key_sidebar_event(session: dict[str, Any], phase: str, **fields: Any) -> None:
    if not session.get("developer_mode"):
        return
    d = _trace(session)
    events = d.setdefault("events", [])
    if not isinstance(events, list):
        events = []
        d["events"] = events
    entry = {
        "phase": phase,
        "session_display_key": str(session.get("display_key") or "").strip() or None,
        "canonical_display_key": _canonical_display_key(session) or None,
        "display_key_change_source": str(session.get("display_key_change_source") or "").strip() or None,
        **{k: v for k, v in fields.items() if v is not None},
    }
    events.append(entry)
    if len(events) > 40:
        del events[:-40]


def collect_display_key_sidebar_trace(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(DISPLAY_KEY_SIDEBAR_TRACE_KEY)
    if not isinstance(raw, dict):
        return {}
    out = copy.deepcopy(raw)
    events = out.get("events")
    if isinstance(events, list) and events:
        last = events[-1]
        if isinstance(last, dict):
            out["last_event"] = last.get("phase")
            for key in (
                "widget_before",
                "widget_after",
                "callback_invoked",
                "display_key_change_source",
                "session_display_key",
                "canonical_display_key",
                "skipped_projection",
                "resolver_key",
                "backing_key",
                "save_reason",
                "cloud_save_requested",
            ):
                if key not in out and last.get(key) is not None:
                    out[key] = last.get(key)
    return out


__all__ = [
    "DISPLAY_KEY_SIDEBAR_TRACE_KEY",
    "collect_display_key_sidebar_trace",
    "record_display_key_sidebar_event",
]

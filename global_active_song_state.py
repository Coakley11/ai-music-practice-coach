"""Global active song — Song Selection owns the catalog pick; all pages read it.

Canonical keys: ``selected_song``, ``active_catalog_pick_key``. Picker widgets
mirror these values so practice, backing, and analysis pages stay aligned.
"""

from __future__ import annotations

from typing import Any

from songs.state import (
    ACTIVE_CATALOG_PICK_KEY,
    SELECTED_SONG_STATE_KEY,
)

GLOBAL_PICK_KEY = ACTIVE_CATALOG_PICK_KEY
GLOBAL_SONG_KEY = SELECTED_SONG_STATE_KEY

# Session aliases that should mirror the canonical active song pick.
SONG_PICK_ALIASES: tuple[str, ...] = (
    "_master_song_pick_key",
    "matching_song_dropdown",
)

_SONG_TRACE_KEY = "_global_active_song_trace"
_SONG_TRACE_MAX = 30


def get_active_pick_key(session: dict[str, Any]) -> str:
    active = str(session.get(GLOBAL_PICK_KEY) or "").strip()
    if active:
        return active
    song = session.get(GLOBAL_SONG_KEY)
    if isinstance(song, dict) and song.get("pick_key"):
        return str(song["pick_key"]).strip()
    return ""


def get_active_song(session: dict[str, Any]) -> dict[str, Any]:
    song = session.get(GLOBAL_SONG_KEY)
    if isinstance(song, dict) and song:
        return dict(song)
    pick = get_active_pick_key(session)
    if pick:
        return {"pick_key": pick}
    return {}


def sync_active_song_to_canonical(session: dict[str, Any]) -> dict[str, Any]:
    """Push canonical pick/song into alias keys."""
    song = get_active_song(session)
    pick = get_active_pick_key(session)
    if pick:
        session[GLOBAL_PICK_KEY] = pick
    if song:
        session[GLOBAL_SONG_KEY] = song
    for alias in SONG_PICK_ALIASES:
        if pick:
            session[alias] = pick
    session["_active_song_pick_propagated"] = pick or None
    return song


def prepare_global_active_song(session: dict[str, Any]) -> dict[str, Any]:
    """Call before widgets on any page — canonical song wins over stale aliases."""
    try:
        from active_song_state import prepare_active_song_context

        prepare_active_song_context(session)
    except ImportError:
        pass
    return sync_active_song_to_canonical(session)


def record_active_song_trace(session: dict[str, Any], step: str) -> None:
    if not session.get("_suite_dev_mode"):
        try:
            import streamlit as st

            qp = st.query_params
            if str(qp.get("dev") or qp.get("developer") or "").strip().lower() not in ("1", "true", "yes"):
                return
        except Exception:
            return
    entry = {
        "step": step,
        "pick_key": get_active_pick_key(session),
        "song_title": str((get_active_song(session) or {}).get("title") or ""),
        "aliases": {a: session.get(a) for a in SONG_PICK_ALIASES},
    }
    trace = session.get(_SONG_TRACE_KEY)
    if not isinstance(trace, list):
        trace = []
    trace.append(entry)
    session[_SONG_TRACE_KEY] = trace[-_SONG_TRACE_MAX:]

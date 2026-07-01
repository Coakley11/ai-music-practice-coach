"""Per-source practice concert key — survives refresh until the user changes song/source."""

from __future__ import annotations

from typing import Any

PRACTICE_KEY_BY_SOURCE_KEY = "practice_key_by_source"
FORCE_BPM_SYNC_ONCE_KEY = "_force_bpm_sync_once"


def _practice_key_store(session: dict[str, Any]) -> dict[str, str]:
    raw = session.get(PRACTICE_KEY_BY_SOURCE_KEY)
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items() if str(k).strip() and str(v).strip()}


def resolve_practice_source_pick(session: dict[str, Any]) -> str:
    """Stable pick_key for catalog or custom progression practice-key storage."""
    try:
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY
    except ImportError:
        ACTIVE_CATALOG_PICK_KEY = "active_catalog_pick_key"  # type: ignore[misc,assignment]
        SELECTED_SONG_STATE_KEY = "selected_song"  # type: ignore[misc,assignment]

    pick = str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if pick:
        return pick
    sel = session.get(SELECTED_SONG_STATE_KEY)
    if isinstance(sel, dict):
        pick = str(sel.get("pick_key") or "").strip()
        if pick:
            return pick
    try:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import custom_pick_key_for, ensure_custom_active_song_identity

        ensure_custom_active_song_identity(session, cpl_active_key=CPL_ACTIVE_KEY)
        pick = str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
        if pick:
            return pick
        active = session.get(CPL_ACTIVE_KEY)
        if isinstance(active, dict):
            return custom_pick_key_for(active)
    except ImportError:
        pass
    return ""


def get_practice_concert_key(
    session: dict[str, Any],
    pick_key: str = "",
    *,
    default: str = "",
) -> str:
    pk = str(pick_key or resolve_practice_source_pick(session) or "").strip()
    if not pk:
        return str(default or "").strip()
    saved = _practice_key_store(session).get(pk, "").strip()
    return saved or str(default or "").strip()


def set_practice_concert_key(
    session: dict[str, Any],
    concert_key: str,
    *,
    pick_key: str = "",
) -> None:
    pk = str(pick_key or resolve_practice_source_pick(session) or "").strip()
    key = str(concert_key or "").strip()
    if not pk or not key:
        return
    store = _practice_key_store(session)
    store[pk] = key
    session[PRACTICE_KEY_BY_SOURCE_KEY] = store


def clear_practice_concert_key(session: dict[str, Any], pick_key: str) -> None:
    pk = str(pick_key or "").strip()
    if not pk:
        return
    store = _practice_key_store(session)
    if pk not in store:
        return
    store.pop(pk, None)
    session[PRACTICE_KEY_BY_SOURCE_KEY] = store


def mark_force_bpm_sync(session: dict[str, Any], sync_id: str) -> None:
    sid = str(sync_id or "").strip()
    if sid:
        session[FORCE_BPM_SYNC_ONCE_KEY] = sid


def consume_force_bpm_sync(session: dict[str, Any], sync_id: str) -> bool:
    forced = str(session.get(FORCE_BPM_SYNC_ONCE_KEY) or "").strip()
    if forced and forced == str(sync_id or "").strip():
        session.pop(FORCE_BPM_SYNC_ONCE_KEY, None)
        return True
    return False


def sbi_uses_custom_progression_preview(session: dict[str, Any]) -> bool:
    """True when Song-Based Improvisation is previewing custom without global custom ownership."""
    try:
        from studio_page_state import resolve_improv_song_source

        return str(resolve_improv_song_source(session) or "").strip() == "Custom progression"
    except ImportError:
        return False


__all__ = [
    "FORCE_BPM_SYNC_ONCE_KEY",
    "PRACTICE_KEY_BY_SOURCE_KEY",
    "clear_practice_concert_key",
    "consume_force_bpm_sync",
    "get_practice_concert_key",
    "mark_force_bpm_sync",
    "resolve_practice_source_pick",
    "sbi_uses_custom_progression_preview",
    "set_practice_concert_key",
]

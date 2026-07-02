"""Per-source practice settings — concert key and BPM survive refresh per pick_key."""

from __future__ import annotations

from typing import Any

PRACTICE_KEY_BY_SOURCE_KEY = "practice_key_by_source"
BPM_BY_SOURCE_KEY = "bpm_by_source"
FORCE_BPM_SYNC_ONCE_KEY = "_force_bpm_sync_once"


def _practice_key_store(session: dict[str, Any]) -> dict[str, str]:
    raw = session.get(PRACTICE_KEY_BY_SOURCE_KEY)
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items() if str(k).strip() and str(v).strip()}


def _bpm_store(session: dict[str, Any]) -> dict[str, int]:
    raw = session.get(BPM_BY_SOURCE_KEY)
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for k, v in raw.items():
        pk = str(k).strip()
        if not pk:
            continue
        try:
            bpm = int(v)
        except (TypeError, ValueError):
            continue
        if bpm > 0:
            out[pk] = bpm
    return out


def pick_key_from_bpm_sync_id(sync_id: str) -> str:
    """Extract catalog/custom pick_key from a playback sync id."""
    sid = str(sync_id or "").strip()
    if sid.startswith("pk::"):
        return sid[4:].strip()
    if sid.startswith("custom::"):
        return sid
    return ""


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
        from source_session_state import get_sbi_preview_source

        return get_sbi_preview_source(session) == "Custom progression"
    except ImportError:
        try:
            from studio_page_state import resolve_improv_song_source

            return str(resolve_improv_song_source(session) or "").strip() == "Custom progression"
        except ImportError:
            return False


def resolve_practice_concert_key_for_pick(
    session: dict[str, Any],
    pick_key: str,
    *,
    original_key: str = "",
) -> str:
    """Saved practice key for one source, else catalog/custom original."""
    saved = get_practice_concert_key(session, pick_key)
    if saved:
        return saved
    return str(original_key or "").strip() or "C"


def get_source_bpm(
    session: dict[str, Any],
    pick_key: str = "",
    *,
    default: int = 0,
) -> int:
    pk = str(pick_key or resolve_practice_source_pick(session) or "").strip()
    if not pk:
        return int(default or 0)
    saved = _bpm_store(session).get(pk)
    if saved and saved > 0:
        return int(saved)
    return int(default or 0)


def set_source_bpm(
    session: dict[str, Any],
    bpm: int,
    *,
    pick_key: str = "",
) -> None:
    pk = str(pick_key or resolve_practice_source_pick(session) or "").strip()
    try:
        val = int(bpm)
    except (TypeError, ValueError):
        return
    if not pk or val <= 0:
        return
    store = _bpm_store(session)
    store[pk] = val
    session[BPM_BY_SOURCE_KEY] = store


def clear_source_bpm(session: dict[str, Any], pick_key: str) -> None:
    pk = str(pick_key or "").strip()
    if not pk:
        return
    store = _bpm_store(session)
    if pk not in store:
        return
    store.pop(pk, None)
    session[BPM_BY_SOURCE_KEY] = store


def resolve_source_bpm_for_pick(
    session: dict[str, Any],
    pick_key: str,
    *,
    default_bpm: int,
) -> int:
    """Saved BPM for one source, else song default."""
    saved = get_source_bpm(session, pick_key, default=0)
    if saved > 0:
        return saved
    return int(default_bpm or 100)


__all__ = [
    "BPM_BY_SOURCE_KEY",
    "FORCE_BPM_SYNC_ONCE_KEY",
    "PRACTICE_KEY_BY_SOURCE_KEY",
    "clear_practice_concert_key",
    "clear_source_bpm",
    "consume_force_bpm_sync",
    "get_practice_concert_key",
    "get_source_bpm",
    "mark_force_bpm_sync",
    "pick_key_from_bpm_sync_id",
    "resolve_practice_concert_key_for_pick",
    "resolve_practice_source_pick",
    "resolve_source_bpm_for_pick",
    "sbi_uses_custom_progression_preview",
    "set_practice_concert_key",
    "set_source_bpm",
]

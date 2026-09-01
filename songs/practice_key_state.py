"""Per-source practice settings — concert key and BPM survive refresh per pick_key."""

from __future__ import annotations

from typing import Any

PRACTICE_KEY_BY_SOURCE_KEY = "practice_key_by_source"
BPM_BY_SOURCE_KEY = "bpm_by_source"
FORCE_BPM_SYNC_ONCE_KEY = "_force_bpm_sync_once"
CREATIVE_STYLE_JAM_PICK = "creative::entry_style_jam"
CREATIVE_JAM_SESSION_PICK = "creative::jam_session_generator"
CREATIVE_SBI_PICK = "creative::song_improv"


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


def is_song_source_pick(pick_key: str) -> bool:
    """True for catalog/custom picks — not creative-only namespace keys."""
    pk = str(pick_key or "").strip()
    if not pk:
        return False
    return not pk.startswith("creative::")


def resolve_creative_settings_pick(session: dict[str, Any]) -> str:
    """Stable pick_key for Style Jam / Jam Session / SBI creative settings."""
    entry = str(session.get("improv_entry_mode") or "").strip()
    if entry == "Style Jam Mode":
        return CREATIVE_STYLE_JAM_PICK
    if entry == "Jam Session Generator":
        return CREATIVE_JAM_SESSION_PICK
    if entry == "Song-Based Improvisation":
        return CREATIVE_SBI_PICK
    try:
        from creative_session_state import get_creative_session

        sess = get_creative_session(session)
        if sess is not None:
            if sess.tool_type == "entry_style_jam":
                return CREATIVE_STYLE_JAM_PICK
            if sess.tool_type == "jam_session_generator":
                return CREATIVE_JAM_SESSION_PICK
            if sess.tool_type == "song_based_improvisation":
                return CREATIVE_SBI_PICK
    except ImportError:
        pass
    return ""


def creative_jam_owns_practice_settings(session: dict[str, Any]) -> bool:
    """Style Jam / Jam Session must not write catalog/custom per-source maps."""
    try:
        from creative_key_sync import is_creative_major_jam_active

        if is_creative_major_jam_active(session):
            return True
    except ImportError:
        pass
    page = str(session.get("studio_page") or "").strip().lower()
    entry = str(session.get("improv_entry_mode") or "").strip()
    if page == "creative" and entry in {"Style Jam Mode", "Jam Session Generator"}:
        return True
    try:
        from creative_session_state import creative_session_is_active, get_creative_session

        if creative_session_is_active(session):
            sess = get_creative_session(session)
            if sess is not None and sess.tool_type in {"entry_style_jam", "jam_session_generator"}:
                return True
    except ImportError:
        pass
    return False


def should_write_song_source_settings(session: dict[str, Any], pick_key: str = "") -> bool:
    """True when practice_key_by_source / bpm_by_source may receive this pick_key."""
    pk = str(pick_key or resolve_practice_source_pick(session) or "").strip()
    if not pk:
        return False
    if pk.startswith("custom::"):
        return True
    if not is_song_source_pick(pk):
        return True
    return not creative_jam_owns_practice_settings(session)


def resolve_settings_pick_for_write(
    session: dict[str, Any],
    pick_key: str = "",
) -> str:
    """Target pick_key for set_practice_concert_key / set_source_bpm."""
    explicit = str(pick_key or "").strip()
    if explicit.startswith("custom::"):
        return explicit
    if creative_jam_owns_practice_settings(session):
        if explicit.startswith("creative::"):
            return explicit
        if explicit and is_song_source_pick(explicit):
            cp = resolve_creative_settings_pick(session)
            return cp or ""
        cp = resolve_creative_settings_pick(session)
        if cp:
            return cp
        return ""
    if explicit:
        return explicit
    return resolve_practice_source_pick(session)


def resolve_practice_source_pick(session: dict[str, Any]) -> str:
    """Stable pick_key for catalog or custom progression practice-key storage."""
    try:
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY
    except ImportError:
        ACTIVE_CATALOG_PICK_KEY = "active_catalog_pick_key"  # type: ignore[misc,assignment]
        SELECTED_SONG_STATE_KEY = "selected_song"  # type: ignore[misc,assignment]

    pick = str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if pick.startswith("custom::"):
        try:
            from custom_progression_lab import CPL_ACTIVE_KEY
            from songs.music_source import custom_pick_key_for, ensure_custom_active_song_identity

            ensure_custom_active_song_identity(session, cpl_active_key=CPL_ACTIVE_KEY)
            active = session.get(CPL_ACTIVE_KEY)
            if isinstance(active, dict):
                canonical = str(custom_pick_key_for(active) or "").strip()
                if canonical:
                    return canonical
        except ImportError:
            pass
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
    pk = resolve_settings_pick_for_write(session, pick_key)
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


def reset_practice_key_to_original_on_source_switch(
    session: dict[str, Any],
    *,
    pick_key: str,
    original_key: str,
) -> str:
    """Explicit Catalog/Custom/Composition (or song) switch → original key only.

    Clears any previously saved Practice Key for ``pick_key`` so hydration cannot
    restore a modified key after leaving and returning to this source/song.
    Same-source refresh/navigation must NOT call this.
    """
    pk = str(pick_key or "").strip()
    original = str(original_key or "C").strip() or "C"
    if pk:
        clear_practice_concert_key(session, pk)
    try:
        from session_widget_safe import reconcile_practice_key_fields

        reconcile_practice_key_fields(session, authoritative=original)
    except ImportError:
        session["concert_key"] = original
        if not session.get("_streamlit_widgets_locked_this_run"):
            session["display_key"] = original
            session.pop("_pending_display_key", None)
        else:
            session["_pending_display_key"] = original
    return original


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
    original = str(original_key or "").strip() or "C"
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

        if is_fixed_practice_key_mode(session):
            return resolve_practice_concert_key_for_song(
                session,
                original,
                pick_key=pick_key,
            )
    except ImportError:
        pass
    saved = get_practice_concert_key(session, pick_key)
    if saved:
        return saved
    return original


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
    pk = resolve_settings_pick_for_write(session, pick_key)
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
    "CREATIVE_JAM_SESSION_PICK",
    "CREATIVE_SBI_PICK",
    "CREATIVE_STYLE_JAM_PICK",
    "FORCE_BPM_SYNC_ONCE_KEY",
    "PRACTICE_KEY_BY_SOURCE_KEY",
    "clear_practice_concert_key",
    "clear_source_bpm",
    "consume_force_bpm_sync",
    "creative_jam_owns_practice_settings",
    "get_practice_concert_key",
    "get_source_bpm",
    "is_song_source_pick",
    "mark_force_bpm_sync",
    "pick_key_from_bpm_sync_id",
    "resolve_creative_settings_pick",
    "resolve_practice_concert_key_for_pick",
    "resolve_practice_source_pick",
    "resolve_settings_pick_for_write",
    "resolve_source_bpm_for_pick",
    "should_write_song_source_settings",
    "sbi_uses_custom_progression_preview",
    "set_practice_concert_key",
    "set_source_bpm",
]

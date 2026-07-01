"""Explicit source state buckets — catalog, custom, creative preview, practice keys.

SBI preview reads/writes ``sbi_preview_source`` and session buckets only.
Global catalog/custom ownership changes happen on explicit Practice/Backing handoff.
"""

from __future__ import annotations

from typing import Any

SBI_PREVIEW_SOURCE_KEY = "sbi_preview_source"
CATALOG_SESSION_KEY = "catalog_session"
CUSTOM_SESSION_KEY = "custom_session"

IMPROV_SONG_SOURCES = ("Active song", "Custom progression")


def get_sbi_preview_source(session: dict[str, Any]) -> str:
    """Read SBI preview source (never reads handoff-only keys)."""
    val = str(session.get(SBI_PREVIEW_SOURCE_KEY) or "").strip()
    if val in IMPROV_SONG_SOURCES:
        return val
    val = str(session.get("improv_song_source") or "").strip()
    if val in IMPROV_SONG_SOURCES:
        return val
    try:
        from songs.music_source import cpl_session_is_active

        if cpl_session_is_active(session):
            return "Custom progression"
    except ImportError:
        pass
    return "Active song"


def set_sbi_preview_source(session: dict[str, Any], source: str) -> None:
    src = str(source or "Active song").strip() or "Active song"
    if src not in IMPROV_SONG_SOURCES:
        src = "Active song"
    session[SBI_PREVIEW_SOURCE_KEY] = src


def sync_catalog_session(session: dict[str, Any]) -> dict[str, Any] | None:
    """Capture live catalog identity into the catalog_session bucket."""
    try:
        from songs.music_source import _catalog_snapshot_from_session

        snap = _catalog_snapshot_from_session(session)
    except ImportError:
        snap = None
    if not snap:
        for fallback_key in ("_catalog_before_custom_state", "_last_catalog_song_state"):
            raw = session.get(fallback_key)
            if isinstance(raw, dict) and str(raw.get("pick_key") or "").strip():
                if not str(raw.get("pick_key") or "").strip().startswith("custom::"):
                    snap = dict(raw)
                    break
    if not snap:
        return None
    pick = str(snap.get("pick_key") or "").strip()
    if not pick or pick.startswith("custom::"):
        return None
    try:
        from songs.practice_key_state import get_practice_concert_key

        saved = get_practice_concert_key(session, pick)
        if saved:
            snap["display_key"] = saved
    except ImportError:
        pass
    session[CATALOG_SESSION_KEY] = dict(snap)
    return session[CATALOG_SESSION_KEY]


def get_catalog_session(session: dict[str, Any]) -> dict[str, Any] | None:
    """Read catalog_session bucket, syncing from live state when missing."""
    raw = session.get(CATALOG_SESSION_KEY)
    if isinstance(raw, dict) and str(raw.get("pick_key") or "").strip():
        pick = str(raw.get("pick_key") or "").strip()
        if not pick.startswith("custom::"):
            return raw
    return sync_catalog_session(session)


def sync_custom_session(session: dict[str, Any]) -> dict[str, Any] | None:
    """Capture live custom progression into the custom_session bucket."""
    try:
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
            default_active_progression,
            ensure_original_structure,
            written_home_key,
        )
        from songs.music_source import custom_pick_key_for
    except ImportError:
        return None

    active = ensure_original_structure(
        session.get(CPL_ACTIVE_KEY) or default_active_progression()
    )
    pick = custom_pick_key_for(active)
    home = str(written_home_key(active) or active.get("original_key_center") or "C").strip() or "C"
    try:
        from songs.practice_key_state import get_practice_concert_key

        display_key = get_practice_concert_key(session, pick, default=home) or home
    except ImportError:
        display_key = home
    sections_raw = (
        active.get("original_sections")
        if isinstance(active.get("original_sections"), dict)
        else {}
    )
    sections = {
        str(sec): [str(c) for c in chords if str(c).strip()]
        for sec, chords in sections_raw.items()
        if isinstance(chords, list)
    }
    blob = {
        "pick_key": pick,
        "title": str(active.get("name") or "Custom progression").strip(),
        "artist": "Custom progression",
        "original_key": home,
        "display_key": display_key,
        "sections": sections,
        "progression_id": str(active.get("id") or "").strip(),
    }
    session[CUSTOM_SESSION_KEY] = blob
    return blob


def get_custom_session(session: dict[str, Any]) -> dict[str, Any] | None:
    raw = session.get(CUSTOM_SESSION_KEY)
    if isinstance(raw, dict) and str(raw.get("pick_key") or "").strip().startswith("custom::"):
        return raw
    return sync_custom_session(session)


def _catalog_display_key(session: dict[str, Any], catalog: dict[str, Any]) -> str:
    pick = str(catalog.get("pick_key") or "").strip()
    sel = catalog.get("selected_song")
    original = "C"
    if isinstance(sel, dict):
        original = str(sel.get("key") or catalog.get("original_key") or "C").strip() or "C"
    else:
        original = str(catalog.get("original_key") or "C").strip() or "C"
    if pick:
        try:
            from songs.practice_key_state import get_practice_concert_key

            saved = get_practice_concert_key(session, pick)
            if saved:
                return saved
        except ImportError:
            pass
    dk = str(catalog.get("display_key") or "").strip()
    return dk or original


def _catalog_sections(session: dict[str, Any], catalog: dict[str, Any]) -> dict[str, list[str]]:
    pick = str(catalog.get("pick_key") or "").strip()
    stored = session.get("improv_song_concert_sections")
    if isinstance(stored, dict) and stored:
        ctx_pick = str(session.get("active_catalog_pick_key") or "").strip()
        if not pick or not ctx_pick or pick == ctx_pick or ctx_pick.startswith("custom::"):
            if not ctx_pick.startswith("custom::"):
                return {
                    str(name): [str(c) for c in chords if str(c).strip()]
                    for name, chords in stored.items()
                    if isinstance(chords, list)
                }
    return {}


def resolve_sbi_preview(session: dict[str, Any]) -> dict[str, Any]:
    """Authoritative SBI card — title/key/progression from one source only."""
    source = get_sbi_preview_source(session)
    if source == "Custom progression":
        custom = get_custom_session(session)
        if custom:
            return {
                "source": source,
                "title": str(custom.get("title") or "Custom progression"),
                "artist": str(custom.get("artist") or "Custom progression"),
                "display_key": str(custom.get("display_key") or custom.get("original_key") or "C"),
                "original_key": str(custom.get("original_key") or "C"),
                "sections": dict(custom.get("sections") or {}),
                "pick_key": str(custom.get("pick_key") or ""),
            }
        return {
            "source": source,
            "title": "Custom progression",
            "artist": "Custom progression",
            "display_key": "C",
            "original_key": "C",
            "sections": {},
            "pick_key": "",
        }

    catalog = get_catalog_session(session)
    if not catalog:
        try:
            from songs.music_source import CATALOG_BEFORE_CUSTOM_KEY, LAST_CATALOG_STATE_KEY

            for key in (CATALOG_BEFORE_CUSTOM_KEY, LAST_CATALOG_STATE_KEY):
                raw = session.get(key)
                if isinstance(raw, dict) and str(raw.get("pick_key") or "").strip():
                    if not str(raw.get("pick_key") or "").strip().startswith("custom::"):
                        catalog = raw
                        break
        except ImportError:
            pass

    if catalog:
        sel = catalog.get("selected_song")
        if isinstance(sel, dict):
            title = str(sel.get("title") or "Active song").strip()
            artist = str(sel.get("artist") or "").strip()
            original = str(sel.get("key") or catalog.get("original_key") or "C").strip() or "C"
        else:
            title = "Active song"
            artist = ""
            original = str(catalog.get("original_key") or "C").strip() or "C"
        return {
            "source": source,
            "title": title,
            "artist": artist,
            "display_key": _catalog_display_key(session, catalog),
            "original_key": original,
            "sections": _catalog_sections(session, catalog),
            "pick_key": str(catalog.get("pick_key") or ""),
        }

    return {
        "source": source,
        "title": "Active song",
        "artist": "",
        "display_key": "C",
        "original_key": "C",
        "sections": {},
        "pick_key": "",
    }


def resolve_improv_song_source_for_handoff(session: dict[str, Any]) -> str:
    """Song source for Practice/Backing open — preview bucket first, then widget."""
    return get_sbi_preview_source(session)


__all__ = [
    "CATALOG_SESSION_KEY",
    "CUSTOM_SESSION_KEY",
    "IMPROV_SONG_SOURCES",
    "SBI_PREVIEW_SOURCE_KEY",
    "get_catalog_session",
    "get_custom_session",
    "get_sbi_preview_source",
    "resolve_improv_song_source_for_handoff",
    "resolve_sbi_preview",
    "set_sbi_preview_source",
    "sync_catalog_session",
    "sync_custom_session",
]

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
    """Read SBI preview source (never reads handoff-only keys).

    Do **not** infer Custom from ``cpl_session_is_active``: a live CPL draft /
    LAST_CUSTOM memory can exist while Global Active stays Catalog and the user
    is on Creative → SBI → Active. That inference collapsed nested SBI Custom
    into “we’re on Custom” semantics and helped reboot land on top-level Custom.
    """
    val = str(session.get(SBI_PREVIEW_SOURCE_KEY) or "").strip()
    if val in IMPROV_SONG_SOURCES:
        return val
    val = str(session.get("improv_song_source") or "").strip()
    if val in IMPROV_SONG_SOURCES:
        return val
    return "Active song"


def set_sbi_preview_source(session: dict[str, Any], source: str) -> None:
    src = str(source or "Active song").strip() or "Active song"
    if src not in IMPROV_SONG_SOURCES:
        src = "Active song"
    session[SBI_PREVIEW_SOURCE_KEY] = src
    # Nested SBI source tab must survive refresh/reboot with Creative page.
    try:
        from creative_workspace_persistence import mark_creative_workspace_dirty

        mark_creative_workspace_dirty(session)
    except ImportError:
        pass


def sync_catalog_session(session: dict[str, Any]) -> dict[str, Any] | None:
    """Capture live catalog identity into the catalog_session bucket."""
    try:
        from songs.music_source import _catalog_snapshot_from_session, _catalog_title_matches_live

        snap = _catalog_snapshot_from_session(session)
    except ImportError:
        snap = None
        _catalog_title_matches_live = None  # type: ignore[assignment]
    live_title = str(session.get("song") or session.get("active_song_title") or "").strip()
    if not snap:
        for fallback_key in ("_catalog_before_custom_state", "_last_catalog_song_state"):
            raw = session.get(fallback_key)
            if not isinstance(raw, dict):
                continue
            pk = str(raw.get("pick_key") or "").strip()
            if not pk or pk.startswith("custom::"):
                continue
            # Never rehydrate Say into catalog_session when Global Active title is Shape.
            if live_title and not live_title.lower().startswith("my progression"):
                fb_title = str((raw.get("selected_song") or {}).get("title") or "").strip()
                if not fb_title:
                    label = pk.split("\x1f", 1)[-1] if "\x1f" in pk else pk
                    fb_title = label.split(" — ", 1)[0].strip()
                if fb_title and _catalog_title_matches_live is not None:
                    if not _catalog_title_matches_live(fb_title, live_title):
                        continue
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
            live_pick = str(session.get("active_catalog_pick_key") or "").strip()
            if live_pick and not live_pick.startswith("custom::") and live_pick != pick:
                return sync_catalog_session(session)
            try:
                from songs.practice_key_state import get_practice_concert_key

                saved = get_practice_concert_key(session, pick)
                if saved and str(raw.get("display_key") or "").strip() != saved:
                    raw = dict(raw)
                    raw["display_key"] = saved
                    session[CATALOG_SESSION_KEY] = raw
            except ImportError:
                pass
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
    sections_raw = active.get("original_sections")
    if not isinstance(sections_raw, dict) or not sections_raw:
        sections_raw = active.get("sections") if isinstance(active.get("sections"), dict) else {}
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
    # Prefer live Practice/Concert Key for the active catalog pick — never catalog.original.
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    ctx_pick = str(session.get("active_catalog_pick_key") or "").strip()
    pick_active = bool(pick) and (not ctx_pick or ctx_pick == pick)
    if pick_active and live:
        return live
    if pick:
        # SBI "Active song" preview can resolve a catalog bucket while global ownership
        # is Custom. Do not let the custom live key overlay that catalog snapshot.
        if pick_active or not ctx_pick.startswith("custom::"):
            try:
                from music_workflow_pending_song_practice_key_edit import overlay_destination_practice_key

                dest = overlay_destination_practice_key(session)
                if dest:
                    return dest
            except ImportError:
                pass
        try:
            from songs.practice_key_state import get_practice_concert_key

            saved = get_practice_concert_key(session, pick)
            if saved:
                return saved
        except ImportError:
            pass
    if pick_active and live:
        return live
    dk = str(catalog.get("display_key") or "").strip()
    return dk or original


def _sections_overlay_pending_practice_key(
    session: dict[str, Any],
    sections: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Retranspose catalog sections toward the effective Practice Key on the same rerun."""
    if not isinstance(sections, dict) or not sections:
        return sections
    try:
        from music_workflow_pending_song_practice_key_edit import (
            overlay_sections_with_pending_practice_key,
        )
        from music_workflow_song_practice import resolve_song_practice_key_token

        spelled = resolve_song_practice_key_token(session) or str(
            session.get("concert_key") or ""
        )
        return overlay_sections_with_pending_practice_key(
            session,
            sections,
            spelled_in_key=spelled,
        )
    except ImportError:
        return sections


def _catalog_sections(session: dict[str, Any], catalog: dict[str, Any]) -> dict[str, list[str]]:
    pick = str(catalog.get("pick_key") or "").strip()
    ctx_pick = str(session.get("active_catalog_pick_key") or "").strip()
    live_is_catalog = bool(ctx_pick) and not ctx_pick.startswith("custom::")
    if live_is_catalog and pick and ctx_pick != pick:
        return {}
    if live_is_catalog and (not pick or pick == ctx_pick):
        try:
            from workflow_musical_authority import sync_song_improv_sections_to_practice_key

            synced = sync_song_improv_sections_to_practice_key(session)
            if isinstance(synced, dict) and synced:
                cleaned = {
                    str(name): [str(c) for c in chords if str(c).strip()]
                    for name, chords in synced.items()
                    if isinstance(chords, list)
                }
                return _sections_overlay_pending_practice_key(session, cleaned)
        except ImportError:
            pass
    stored = session.get("improv_song_concert_sections")
    if live_is_catalog and isinstance(stored, dict) and stored:
        if not pick or pick == ctx_pick:
            cleaned = {
                str(name): [str(c) for c in chords if str(c).strip()]
                for name, chords in stored.items()
                if isinstance(chords, list)
            }
            return _sections_overlay_pending_practice_key(session, cleaned)
    bucket = catalog.get("sections")
    if isinstance(bucket, dict) and bucket:
        cleaned = {
            str(name): [str(c) for c in chords if str(c).strip()]
            for name, chords in bucket.items()
            if isinstance(chords, list)
        }
        return _sections_overlay_pending_practice_key(session, cleaned)
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

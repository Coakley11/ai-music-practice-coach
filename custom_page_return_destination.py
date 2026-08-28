"""Sealed Custom-page return destination for Custom Backing → Return to Custom.

Custom Backing launched from Trial must restore Trial's Custom workspace on
Return. Do not infer from a later Creative tab / SBI source / Catalog owner,
and do not treat Return as Set as Active.
"""

from __future__ import annotations

import copy
from typing import Any

CUSTOM_PAGE_RETURN_DESTINATION_KEY = "_custom_page_return_destination"
CUSTOM_PAGE_RETURN_DESTINATION_BLOB_KEY = "custom_page_return_destination"


def _backing_context_blob(session: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from backing_context import BACKING_CONTEXT_KEY

        raw = session.get(BACKING_CONTEXT_KEY)
    except ImportError:
        raw = session.get("backing_context")
    return raw if isinstance(raw, dict) else None


def _valid_dest(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    active = raw.get("active")
    if not isinstance(active, dict):
        return None
    name = str(active.get("name") or raw.get("song_title") or "").strip()
    if not name or name.lower() in {"my progression", "myprogression"}:
        return None
    return copy.deepcopy(raw)


def _editor_state(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "cpl_finished": bool(session.get("cpl_finished")),
        "cpl_edit_section": str(session.get("cpl_edit_section") or "").strip(),
        "cpl_title_input": str(session.get("cpl_title_input") or "").strip(),
    }


def build_custom_page_return_destination(session: dict[str, Any]) -> dict[str, Any] | None:
    """Capture Trial Custom identity, progression, local PK, and editor state."""
    try:
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
            cpl_active_from_session,
            cpl_workspace_practice_key,
        )
    except ImportError:
        return None
    active = cpl_active_from_session(session) if callable(cpl_active_from_session) else session.get(CPL_ACTIVE_KEY)
    if not isinstance(active, dict):
        try:
            from songs.music_source import LAST_CUSTOM_STATE_KEY

            snap = session.get(LAST_CUSTOM_STATE_KEY)
            if isinstance(snap, dict) and isinstance(snap.get("active"), dict):
                active = dict(snap["active"])
        except ImportError:
            active = None
    if not isinstance(active, dict):
        return None
    name = str(active.get("name") or "").strip()
    if not name or name.lower() in {"my progression", "myprogression"}:
        return None
    try:
        practice_key = str(cpl_workspace_practice_key(session, active) or "").strip()
    except Exception:
        practice_key = str(active.get("original_key_center") or "").strip()
    dest = {
        "destination_page": "custom",
        "song_title": name,
        "song_id": str(active.get("id") or "").strip(),
        "practice_key": practice_key,
        "original_key": str(active.get("original_key_center") or "").strip(),
        "active": copy.deepcopy(active),
        "editor": _editor_state(session),
        "global_active_source": str(session.get("active_music_source") or "").strip(),
        "global_active_pick": str(session.get("active_catalog_pick_key") or "").strip(),
    }
    return dest


def stamp_custom_page_return_destination_on_backing_context(
    session: dict[str, Any],
    destination: dict[str, Any] | None = None,
) -> None:
    dest = _valid_dest(destination) or _valid_dest(session.get(CUSTOM_PAGE_RETURN_DESTINATION_KEY))
    blob = _backing_context_blob(session)
    if dest is None or blob is None:
        return
    blob[CUSTOM_PAGE_RETURN_DESTINATION_BLOB_KEY] = copy.deepcopy(dest)


def seal_custom_page_return_destination(
    session: dict[str, Any],
    destination: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    dest = _valid_dest(destination) or build_custom_page_return_destination(session)
    if dest is None:
        return None
    session[CUSTOM_PAGE_RETURN_DESTINATION_KEY] = dest
    stamp_custom_page_return_destination_on_backing_context(session, dest)
    return copy.deepcopy(dest)


def peek_custom_page_return_destination(session: dict[str, Any]) -> dict[str, Any] | None:
    existing = _valid_dest(session.get(CUSTOM_PAGE_RETURN_DESTINATION_KEY))
    if existing is not None:
        return existing
    blob = _backing_context_blob(session)
    if blob is None:
        return None
    recovered = _valid_dest(blob.get(CUSTOM_PAGE_RETURN_DESTINATION_BLOB_KEY))
    if recovered is None:
        return None
    session[CUSTOM_PAGE_RETURN_DESTINATION_KEY] = copy.deepcopy(recovered)
    return recovered


def apply_custom_page_return_destination(
    session: dict[str, Any],
    *,
    consume: bool = False,
    set_page: bool = True,
) -> bool:
    """Restore Trial Custom workspace. Does not change Global Active ownership.

    The Backing click must not pop the dest until the Custom page actually
    hydrates. Persist/rerun can bounce the first paint back to Catalog Backing;
    keeping the dest makes Return to Custom Page still work.

    ``set_page=False`` leaves ``studio_page`` alone so the caller can
    ``navigate_studio_page(..., "custom")`` and persist the transition. If apply
    already flipped the page, navigate is a no-op and disk still has Backing.
    """
    dest = peek_custom_page_return_destination(session)
    if dest is None:
        return False
    active = dest.get("active")
    if not isinstance(active, dict):
        return False
    try:
        from custom_progression_lab import apply_cpl_session_progression, sync_custom_workspace_practice_key
    except ImportError:
        return False
    apply_cpl_session_progression(session, copy.deepcopy(active), reset_display_key=False)
    editor = dest.get("editor") if isinstance(dest.get("editor"), dict) else {}
    if editor.get("cpl_finished"):
        session["cpl_finished"] = True
    section = str(editor.get("cpl_edit_section") or "").strip()
    if section:
        session["cpl_edit_section"] = section
    title = str(editor.get("cpl_title_input") or dest.get("song_title") or "").strip()
    if title:
        session["cpl_title_input"] = title
    practice_key = str(dest.get("practice_key") or "").strip()
    if practice_key:
        try:
            sync_custom_workspace_practice_key(
                session,
                practice_key=practice_key,
                active=session.get("cpl_active_progression") or active,
                source="custom_page_return",
            )
        except Exception:
            session["concert_key"] = practice_key
            try:
                from session_widget_safe import safe_assign_display_key

                safe_assign_display_key(session, practice_key, widget_safe=True)
            except ImportError:
                session["display_key"] = practice_key
    try:
        from songs.music_source import snapshot_last_custom_state

        snapshot_last_custom_state(session)
    except ImportError:
        pass
    try:
        from source_session_state import sync_custom_session

        sync_custom_session(session)
    except ImportError:
        pass
    if set_page:
        session["studio_page"] = "custom"
    # Keep the Catalog-launch flag until Custom actually hydrates and consumes
    # dest. Persist/rerun can bounce the first paint back onto Backing; dropping
    # the flag here lets hydrate overlay Trial onto Catalog Shape and replaces
    # Return to Custom Page with Return to Song Catalog.
    if consume and str(session.get("studio_page") or "").strip().lower() == "custom":
        session.pop(CUSTOM_PAGE_RETURN_DESTINATION_KEY, None)
        blob = _backing_context_blob(session)
        if isinstance(blob, dict):
            blob.pop(CUSTOM_PAGE_RETURN_DESTINATION_BLOB_KEY, None)
        try:
            from custom_progression_lab import CUSTOM_PAGE_LAUNCHED_CATALOG_BACKING_KEY

            session.pop(CUSTOM_PAGE_LAUNCHED_CATALOG_BACKING_KEY, None)
        except ImportError:
            session.pop("_custom_page_launched_catalog_backing", None)
    return True


def consume_custom_page_return_destination(session: dict[str, Any]) -> bool:
    """Restore Trial Custom workspace and drop the dest after a Custom-page apply."""
    page = str(session.get("studio_page") or "").strip().lower()
    return apply_custom_page_return_destination(session, consume=(page == "custom"))


def navigate_return_to_custom_page(session: dict[str, Any]) -> bool:
    """Restore Trial, then persist Custom via navigate so rerun cannot restore Backing.

    Apply must not claim ``studio_page`` first — ``navigate_studio_page`` no-ops
    when the page is already custom and skips the page-change persist.
    """
    ok = apply_custom_page_return_destination(session, consume=False, set_page=False)
    try:
        from studio_nav_history import navigate_studio_page

        navigate_studio_page(session, "custom")
    except ImportError:
        session["studio_page"] = "custom"
    return ok


__all__ = [
    "CUSTOM_PAGE_RETURN_DESTINATION_BLOB_KEY",
    "CUSTOM_PAGE_RETURN_DESTINATION_KEY",
    "apply_custom_page_return_destination",
    "build_custom_page_return_destination",
    "consume_custom_page_return_destination",
    "navigate_return_to_custom_page",
    "peek_custom_page_return_destination",
    "seal_custom_page_return_destination",
    "stamp_custom_page_return_destination_on_backing_context",
]

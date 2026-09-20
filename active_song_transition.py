"""Active-song transition classes for Practice Key initialization.

Page navigation and temporary Custom/Composition/SBI visits must not reset a
catalog song's saved Practice Key. Only a genuine committed active-song change
may initialize the newly activated UUID from its Original Key.

Classification is stamp-first. Leftover page/intent strings are not enough to
treat a render as a committed song change.
"""

from __future__ import annotations

from typing import Any

PREVIEW_OR_EDIT = "preview_or_edit"
TEMPORARY_WORKFLOW_OWNER = "temporary_workflow_owner"
COMMITTED_ACTIVE_SONG_CHANGE = "committed_active_song_change"

COMMITTED_FLAG_KEY = "_committed_active_song_change"
TEMPORARY_WORKFLOW_OWNER_KEY = "_temporary_workflow_owner"


def mark_committed_active_song_change(session: dict[str, Any]) -> None:
    session[COMMITTED_FLAG_KEY] = True
    session.pop(TEMPORARY_WORKFLOW_OWNER_KEY, None)


def consume_committed_active_song_change(session: dict[str, Any]) -> bool:
    return bool(session.pop(COMMITTED_FLAG_KEY, False))


def mark_temporary_workflow_owner(session: dict[str, Any], owner: str = "") -> None:
    kind = str(owner or "").strip()
    session[TEMPORARY_WORKFLOW_OWNER_KEY] = kind or "temporary"
    session.pop(COMMITTED_FLAG_KEY, None)


def clear_temporary_workflow_owner(session: dict[str, Any]) -> None:
    session.pop(TEMPORARY_WORKFLOW_OWNER_KEY, None)


def classify_active_song_transition(session: dict[str, Any], *, surface: str = "") -> str:
    """Classify the current ownership move.

    ``committed_active_song_change`` is the only class that may initialize
    Practice Key from Original Key. Stamps outrank leftover page/intent.
    """
    del surface  # callers may pass surface; stamps decide, not the render page
    if session.get(COMMITTED_FLAG_KEY):
        return COMMITTED_ACTIVE_SONG_CHANGE
    preview = str(session.get("sbi_preview_source") or session.get("improv_song_source") or "").strip()
    try:
        from source_session_state import get_sbi_preview_source

        preview = str(get_sbi_preview_source(session) or preview).strip()
    except ImportError:
        pass
    if preview in {"Custom progression", "Composition"}:
        return TEMPORARY_WORKFLOW_OWNER
    if session.get(TEMPORARY_WORKFLOW_OWNER_KEY):
        return TEMPORARY_WORKFLOW_OWNER
    page = str(session.get("studio_page") or "").strip().lower()
    if page in {"composer", "custom"}:
        return PREVIEW_OR_EDIT
    return PREVIEW_OR_EDIT


def may_initialize_practice_key_from_original(session: dict[str, Any], *, surface: str = "") -> bool:
    return classify_active_song_transition(session, surface=surface) == COMMITTED_ACTIVE_SONG_CHANGE


def capture_owner_key_boundary(session: dict[str, Any], *, surface: str = "") -> dict[str, Any]:
    """Diagnostics at an ownership boundary — competing authorities in one row."""
    pick = str(session.get("active_catalog_pick_key") or "").strip()
    custom_uuid = pick if pick.startswith("custom::") else ""
    try:
        from songs.music_source import LAST_CUSTOM_STATE_KEY, custom_pick_key_for

        snap = session.get(LAST_CUSTOM_STATE_KEY)
        if isinstance(snap, dict):
            active = snap.get("active") if isinstance(snap.get("active"), dict) else {}
            custom_uuid = str(custom_pick_key_for(active) or snap.get("pick_key") or custom_uuid or "").strip()
    except Exception:
        pass
    preview = str(session.get("sbi_preview_source") or session.get("improv_song_source") or "").strip()
    original = str(session.get("original_key") or "").strip()
    selected = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
    if not original:
        original = str((selected or {}).get("key") or "").strip()
    saved = ""
    try:
        from songs.practice_key_state import get_practice_concert_key, resolve_practice_source_pick

        scoped = str(resolve_practice_source_pick(session) or pick or "").strip()
        saved = str(get_practice_concert_key(session, scoped) or "").strip()
    except Exception:
        saved = ""
    return {
        "transition_class": classify_active_song_transition(session, surface=surface),
        "surface": str(surface or ""),
        "studio_page": str(session.get("studio_page") or ""),
        "global_active_source": str(session.get("active_music_source") or ""),
        "global_active_pick": pick,
        "visible_workflow_owner": str(session.get(TEMPORARY_WORKFLOW_OWNER_KEY) or preview or "catalog"),
        "catalog_pick": pick if not pick.startswith("custom::") else str(session.get("_last_catalog_pick_key") or ""),
        "custom_uuid": custom_uuid,
        "original_key": original,
        "scoped_practice_key": saved,
        "sidebar_key": str(session.get("display_key") or ""),
        "canonical_key": str(session.get("concert_key") or saved or ""),
        "pending_hydrate": str(session.get("_pending_display_key") or ""),
        "sbi_submode": preview,
        "focus_owner": str(session.get("improv_intelligence_tab") or ""),
        "committed_stamp": bool(session.get(COMMITTED_FLAG_KEY)),
    }

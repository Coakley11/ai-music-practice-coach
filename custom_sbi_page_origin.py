"""Origin stamp when Custom SBI opens the Custom page.

Returning to Creative must restore Custom SBI / Trial — not remount Active SBI
with a Trial title and Catalog chords. Global Active is not changed.
"""

from __future__ import annotations

import copy
from typing import Any

CUSTOM_SBI_PAGE_ORIGIN_KEY = "_custom_sbi_page_origin"


def _trial_active_from_session(session: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from custom_progression_lab import CPL_ACTIVE_KEY, cpl_active_from_session

        active = cpl_active_from_session(session)
    except ImportError:
        active = session.get("cpl_active_progression")
    if isinstance(active, dict) and str(active.get("name") or "").strip():
        name = str(active.get("name") or "").strip()
        if name.lower() not in {"my progression", "myprogression"}:
            return copy.deepcopy(active)
    try:
        from songs.music_source import LAST_CUSTOM_STATE_KEY

        snap = session.get(LAST_CUSTOM_STATE_KEY)
        if isinstance(snap, dict) and isinstance(snap.get("active"), dict):
            return copy.deepcopy(snap["active"])
    except ImportError:
        pass
    return None


def stamp_custom_sbi_page_origin(session: dict[str, Any]) -> dict[str, Any] | None:
    """Stamp Custom SBI / Trial when leaving SBI for the Custom page."""
    try:
        from source_session_state import get_sbi_preview_source
    except ImportError:
        get_sbi_preview_source = None  # type: ignore[assignment]
    source = ""
    if callable(get_sbi_preview_source):
        source = str(get_sbi_preview_source(session) or "").strip()
    if not source:
        source = str(session.get("sbi_preview_source") or session.get("improv_song_source") or "").strip()
    if source != "Custom progression":
        session.pop(CUSTOM_SBI_PAGE_ORIGIN_KEY, None)
        return None
    active = _trial_active_from_session(session)
    if active is None:
        return None
    try:
        from custom_progression_lab import custom_sbi_local_practice_key

        practice_key = str(custom_sbi_local_practice_key(session, active) or "").strip()
    except Exception:
        practice_key = str(active.get("original_key_center") or "").strip()
    origin = {
        "source": "Custom progression",
        "entry_mode": "Song-Based Improvisation",
        "intelligence_tab": str(
            session.get("improv_intelligence_tab")
            or session.get("creative_improv_intelligence_tab")
            or "Entry & Jam"
        ).strip()
        or "Entry & Jam",
        "song_title": str(active.get("name") or "").strip(),
        "song_id": str(active.get("id") or "").strip(),
        "practice_key": practice_key,
        "active": active,
        "global_active_source": str(session.get("active_music_source") or "").strip(),
        "global_active_pick": str(session.get("active_catalog_pick_key") or "").strip(),
        "global_active_title": str(session.get("song") or session.get("active_song_title") or "").strip(),
        "global_active_pk": str(session.get("display_key") or session.get("concert_key") or "").strip(),
    }
    try:
        from source_session_state import resolve_sbi_preview

        preview = resolve_sbi_preview(session)
        if isinstance(preview, dict) and preview.get("sections"):
            origin["sections"] = copy.deepcopy(preview.get("sections") or {})
    except ImportError:
        pass
    session[CUSTOM_SBI_PAGE_ORIGIN_KEY] = origin
    return copy.deepcopy(origin)


def peek_custom_sbi_page_origin(session: dict[str, Any]) -> dict[str, Any] | None:
    raw = session.get(CUSTOM_SBI_PAGE_ORIGIN_KEY)
    if not isinstance(raw, dict) or str(raw.get("source") or "") != "Custom progression":
        return None
    if not isinstance(raw.get("active"), dict):
        return None
    return copy.deepcopy(raw)


def apply_custom_sbi_origin_on_custom_page(session: dict[str, Any]) -> bool:
    """Project sealed Custom SBI / Trial onto the Custom page without consuming.

    Opening Custom Lab must not hydrate Catalog Bm into Trial's local workspace.
    Origin stays sealed for Creative return.
    """
    page = str(session.get("studio_page") or "").strip().lower()
    if page != "custom":
        return False
    origin = peek_custom_sbi_page_origin(session)
    if origin is None:
        return False
    active = origin.get("active")
    if not isinstance(active, dict):
        return False
    try:
        from custom_progression_lab import apply_cpl_session_progression, sync_custom_workspace_practice_key

        apply_cpl_session_progression(session, copy.deepcopy(active), reset_display_key=False)
        practice_key = str(origin.get("practice_key") or "").strip()
        if practice_key:
            sync_custom_workspace_practice_key(
                session,
                practice_key=practice_key,
                active=active,
                source="custom_sbi_origin_custom_page",
            )
    except ImportError:
        session["cpl_active_progression"] = copy.deepcopy(active)
    ga_source = str(origin.get("global_active_source") or "").strip()
    ga_pick = str(origin.get("global_active_pick") or "").strip()
    if ga_source:
        session["active_music_source"] = ga_source
    if ga_pick and not ga_pick.startswith("custom::"):
        session["active_catalog_pick_key"] = ga_pick
    return True


def consume_custom_sbi_page_origin_on_creative(session: dict[str, Any]) -> bool:
    """Restore Custom SBI / Trial when remounting Creative. Does not change GA."""
    page = str(session.get("studio_page") or "").strip().lower()
    if page != "creative":
        return False
    origin = peek_custom_sbi_page_origin(session)
    if origin is None:
        return False
    active = origin.get("active")
    if not isinstance(active, dict):
        return False
    ga_source = str(origin.get("global_active_source") or session.get("active_music_source") or "").strip()
    ga_pick = str(origin.get("global_active_pick") or session.get("active_catalog_pick_key") or "").strip()
    try:
        from custom_progression_lab import apply_cpl_session_progression

        apply_cpl_session_progression(session, copy.deepcopy(active), reset_display_key=False)
    except ImportError:
        session["cpl_active_progression"] = copy.deepcopy(active)
    try:
        from source_session_state import set_sbi_preview_source, sync_custom_session

        set_sbi_preview_source(session, "Custom progression")
        sync_custom_session(session)
    except ImportError:
        session["sbi_preview_source"] = "Custom progression"
        session["improv_song_source"] = "Custom progression"
    session["improv_song_source"] = "Custom progression"
    session["improv_entry_mode"] = str(origin.get("entry_mode") or "Song-Based Improvisation")
    tab = str(origin.get("intelligence_tab") or "Entry & Jam").strip() or "Entry & Jam"
    session["improv_intelligence_tab"] = tab
    session["creative_improv_intelligence_tab"] = tab
    practice_key = str(origin.get("practice_key") or "").strip()
    if practice_key:
        try:
            from custom_progression_lab import sync_custom_workspace_practice_key

            sync_custom_workspace_practice_key(
                session,
                practice_key=practice_key,
                active=active,
                source="custom_sbi_origin_return",
            )
        except Exception:
            pass
        try:
            from songs.music_source import custom_pick_key_for
            from songs.practice_key_state import set_practice_concert_key

            set_practice_concert_key(
                session,
                practice_key,
                pick_key=custom_pick_key_for(active),
            )
        except ImportError:
            pass
    # Preserve sealed Global Active — visiting Custom SBI / Custom page is not Set as Active.
    if ga_source:
        session["active_music_source"] = ga_source
    if ga_pick and not ga_pick.startswith("custom::"):
        session["active_catalog_pick_key"] = ga_pick
    try:
        from creative_session_state import get_creative_session, set_creative_session
        from source_session_state import resolve_sbi_preview

        sess = get_creative_session(session)
        preview = resolve_sbi_preview(session)
        sections = origin.get("sections") if isinstance(origin.get("sections"), dict) else {}
        if not sections:
            sections = preview.get("sections") if isinstance(preview, dict) else {}
        if sess is not None:
            sess.tool_type = "song_based_improvisation"
            sess.entry_mode = "Song-Based Improvisation"
            sess.song_source = "Custom progression"
            sess.intelligence_tab = tab
            if isinstance(sections, dict) and sections:
                sess.sections = {
                    str(name): [str(c) for c in chords if str(c).strip()]
                    for name, chords in sections.items()
                    if isinstance(chords, list)
                }
            if practice_key:
                sess.display_key = practice_key
                sess.concert_key = practice_key
            set_creative_session(session, sess)
    except ImportError:
        pass
    try:
        from songs.music_source import snapshot_last_custom_state

        snapshot_last_custom_state(session)
    except ImportError:
        pass
    session.pop(CUSTOM_SBI_PAGE_ORIGIN_KEY, None)
    return True


__all__ = [
    "CUSTOM_SBI_PAGE_ORIGIN_KEY",
    "apply_custom_sbi_origin_on_custom_page",
    "consume_custom_sbi_page_origin_on_creative",
    "peek_custom_sbi_page_origin",
    "stamp_custom_sbi_page_origin",
]

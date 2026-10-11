"""Per-lane Practice-Key authority for Song-Based Improvisation source switching.

SBI offers three lanes -- Active song, Custom progression, Composition -- and
each is a distinct musical context with its own Original and Practice Key:

* Active song   -> the global active source's own pick-scoped Practice Key.
* Custom        -> My Progression's own Custom store (``display_key_sbi_custom``).
* Composition   -> the Composition UUID's own store (``display_key_sbi_composition``).

The sidebar ``display_key`` is an *output* of whichever lane is selected, never
the authority for the lane clicked next. Before this module, the Custom and
Composition lanes both rendered through that shared key, and global reconcilers
read it back as the active song's Practice Key: Custom's D showed on the
Composition lane, and a lane's key was written into Perfect's own store when
the musician returned to "Active song".

Switching lanes is a preview, not a global activation: nothing here writes the
global owner's Practice Key.
"""

from __future__ import annotations

from typing import Any

LANE_ACTIVE = "Active song"
LANE_CUSTOM = "Custom progression"
LANE_COMPOSITION = "Composition"
SBI_LANES = (LANE_ACTIVE, LANE_CUSTOM, LANE_COMPOSITION)

#: Sidebar widget for the Composition lane. Separate from ``display_key`` so the
#: browser never re-commits a Composition preview key into the global widget.
COMPOSITION_LANE_WIDGET = "display_key_sbi_composition"

_LANE_OWNER = {LANE_CUSTOM: "custom", LANE_COMPOSITION: "composition"}


def selected_sbi_lane(session: dict[str, Any]) -> str:
    """The SBI lane on screen right now, or "" when no SBI lane is displayed."""
    if str(session.get("studio_page") or "").strip().lower() != "creative":
        return ""
    try:
        from source_session_state import sbi_custom_preview_surface_displayed

        if not sbi_custom_preview_surface_displayed(session):
            return ""
    except ImportError:
        return ""
    entry = str(session.get("improv_entry_mode") or "").strip()
    if entry and "Song-Based" not in entry:
        return ""
    for key in ("_pending_improv_song_source", "PENDING_IMPROV_SONG_SOURCE", "improv_song_source"):
        val = str(session.get(key) or "").strip()
        if val in SBI_LANES:
            return val
    return ""


def foreign_sbi_lane(session: dict[str, Any]) -> str:
    """A selected Custom/Composition lane that is only a preview, else "".

    When that lane's source is also the global owner it is not foreign: the
    lane and the global source are the same context and share one store.
    """
    lane = selected_sbi_lane(session)
    owner_kind = _LANE_OWNER.get(lane)
    if not owner_kind:
        return ""
    try:
        from source_session_state import global_music_source_owner

        if global_music_source_owner(session) == owner_kind:
            return ""
    except ImportError:
        pass
    return lane


def composition_lane_keys(session: dict[str, Any]) -> tuple[str, str, str]:
    """(pick, Original, Practice) of the Composition the lane previews."""
    try:
        from composition_session_state import get_active_document
        from composition_songs_bridge import (
            composition_pick_key_for,
            resolve_composition_canonical_keys,
        )
    except ImportError:
        return "", "", ""
    try:
        doc = get_active_document(session) or {}
    except Exception:
        doc = {}
    if not isinstance(doc, dict) or not doc:
        return "", "", ""
    pick = str(composition_pick_key_for(doc) or "").strip()
    original, practice = resolve_composition_canonical_keys(session, doc)
    original = str(original or "").strip()
    practice = str(practice or original).strip() or original
    return pick, original, practice


def composition_lane_preview(session: dict[str, Any]) -> dict[str, Any]:
    """Card data for the Composition lane: the document's real progression."""
    try:
        from composition_session_state import get_active_document
        from workflow_musical_authority import (
            resolve_composition_concert_sections_at_practice_key,
        )

        doc = get_active_document(session) or {}
        sections = resolve_composition_concert_sections_at_practice_key(session) or {}
    except Exception:
        doc, sections = {}, {}
    pick, original, practice = composition_lane_keys(session)
    return {
        "title": str((doc or {}).get("title") or "Composition"),
        "pick_key": pick,
        "original_key": original,
        "display_key": practice,
        "sections": sections,
    }


def composition_lane_owns_sidebar(session: dict[str, Any]) -> bool:
    return foreign_sbi_lane(session) == LANE_COMPOSITION and bool(composition_lane_keys(session)[0])


def prepare_composition_lane_sidebar(session: dict[str, Any]) -> tuple[list[str], str]:
    """Seed the Composition lane widget from Composition's own store.

    Returns (options, Original). Writes only the lane widget -- never
    ``display_key`` / ``concert_key`` / another source's store. The widget is
    re-asserted whenever it differs, so the browser is sent the value on the
    run that mounts it.
    """
    from songs.key_state import display_key_options

    _pick, original, practice = composition_lane_keys(session)
    options = list(display_key_options(original) or [original])
    if practice and practice not in options:
        options = [practice] + [k for k in options if k != practice]
    if practice and str(session.get(COMPOSITION_LANE_WIDGET) or "").strip() != practice:
        session[COMPOSITION_LANE_WIDGET] = practice
    return options, original


def commit_composition_lane_practice_key(session: dict[str, Any], token: str) -> str:
    """The musician changed the Composition lane key: store it on that Composition."""
    tok = str(token or "").strip()
    pick, _original, _practice = composition_lane_keys(session)
    if not tok or not pick:
        return ""
    from songs.practice_key_state import set_practice_concert_key

    set_practice_concert_key(
        session,
        tok,
        pick_key=pick,
        allow_restore_original=True,
        commit_catalog_practice_key=True,
    )
    return tok


def lane_original_key_for_sidebar(session: dict[str, Any]) -> str:
    """Original Key the sidebar caption must show for a foreign Composition lane."""
    if not composition_lane_owns_sidebar(session):
        return ""
    return composition_lane_keys(session)[1]


__all__ = [
    "COMPOSITION_LANE_WIDGET",
    "LANE_ACTIVE",
    "LANE_COMPOSITION",
    "LANE_CUSTOM",
    "commit_composition_lane_practice_key",
    "composition_lane_keys",
    "composition_lane_owns_sidebar",
    "composition_lane_preview",
    "foreign_sbi_lane",
    "lane_original_key_for_sidebar",
    "prepare_composition_lane_sidebar",
    "selected_sbi_lane",
]

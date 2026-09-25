"""Explicit Mission owner contract — one context while Missions / Mission Backing own.

Mission Practice Key, written transposition, progression, and Mission Backing
handoff resolve from this contract. Stale Jam / SBI preview / Original-key
residue must not reconstruct Mission identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MISSION_OWNER = "mission"
BACKING_HANDOFF_SOURCE_KEY = "_backing_explicit_handoff_source"
MISSION_RETURN_DESTINATION_KEY = "_music_mission_canonical_return_destination"


@dataclass(frozen=True)
class MissionOwnerContext:
    """Snapshot of the Mission-owned workspace."""

    underlying_pick: str
    underlying_title: str
    mission_pick: str
    section_label: str
    concert_chord: str
    practice_key: str
    written_key: str
    instrument: str
    backing_handoff: str
    return_destination: str


def missions_surface_owns(session: dict[str, Any]) -> bool:
    """True while Creative Missions tab or Mission Backing owns the visit."""
    try:
        from creative_key_sync import mission_owns_left_panel_key

        if mission_owns_left_panel_key(session):
            return True
    except ImportError:
        pass
    page = str(session.get("studio_page") or "").strip().lower()
    tab = str(
        session.get("improv_intelligence_tab")
        or session.get("creative_improv_intelligence_tab")
        or ""
    ).strip()
    if page == "creative" and tab == "Missions":
        return True
    return live_backing_owner_is_mission(session)


def live_backing_owner_is_mission(session: dict[str, Any]) -> bool:
    """Current Backing envelope owner is Mission (not leftover mission flags)."""
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and str(getattr(ctx, "source", "") or "").strip() == MISSION_OWNER:
            return True
    except ImportError:
        pass
    handoff = str(session.get(BACKING_HANDOFF_SOURCE_KEY) or "").strip()
    if handoff == MISSION_OWNER and str(session.get("studio_page") or "").strip().lower() == "backing":
        return True
    return False


def resolve_mission_underlying_practice_key(session: dict[str, Any]) -> str:
    """Practice Key from the underlying active song owner — not Original / Jam / SBI preview.

    Catalog sticky and custom:: sticky both qualify. Stale ``improv_mission_concert_key``
    equal to Original while sticky Practice differs must lose.
    """
    try:
        from creative_key_sync import _mission_user_commit_token

        user = str(_mission_user_commit_token(session) or "").strip()
        if user:
            return user
    except ImportError:
        pass

    pick = ""
    saved = ""
    try:
        from songs.practice_key_state import get_practice_concert_key, resolve_practice_source_pick
        from songs.music_source import custom_progression_is_active, custom_pick_key_for
        from custom_progression_lab import CPL_ACTIVE_KEY

        # Custom Global Active outranks a leftover catalog pick while Missions owns.
        if custom_progression_is_active(session):
            active = session.get(CPL_ACTIVE_KEY)
            custom_pick = ""
            if isinstance(active, dict):
                custom_pick = str(custom_pick_key_for(active) or "").strip()
            if not custom_pick:
                custom_pick = str(session.get("active_catalog_pick_key") or "").strip()
                if not custom_pick.startswith("custom::"):
                    custom_pick = ""
            if custom_pick:
                saved = str(get_practice_concert_key(session, custom_pick) or "").strip()
                if saved:
                    return saved
        pick = str(resolve_practice_source_pick(session) or "").strip()
        if pick:
            saved = str(get_practice_concert_key(session, pick) or "").strip()
    except ImportError:
        pick = str(session.get("active_catalog_pick_key") or "").strip()
        store = session.get("practice_key_by_source")
        if isinstance(store, dict) and pick:
            saved = str(store.get(pick) or "").strip()

    if saved:
        return saved

    # Live sidebar / session Practice (already at Practice Key, not Original).
    live = str(
        session.get("display_key") or session.get("concert_key") or session.get("practice_concert_key") or ""
    ).strip()
    if live:
        return live

    # Mission Backing sealed concert, then leftover mission token last.
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and str(getattr(ctx, "source", "") or "").strip() == MISSION_OWNER:
            ctx_key = str(getattr(ctx, "concert_key", "") or getattr(ctx, "key", "") or "").strip()
            if ctx_key:
                return ctx_key
    except ImportError:
        pass

    return str(session.get("improv_mission_concert_key") or "").strip()


def resolve_mission_written_key(session: dict[str, Any], practice_key: str = "") -> str:
    """Written Key from Mission Practice Key + instrument (charts ON)."""
    concert = str(practice_key or resolve_mission_underlying_practice_key(session) or "").strip()
    if not concert:
        return ""
    try:
        from effective_practice_context import musician_facing_chart_key

        return str(musician_facing_chart_key(session, concert) or concert).strip()
    except ImportError:
        pass
    try:
        from instrument_transposition import chart_in_instrument_key, written_key_for_type

        if not chart_in_instrument_key(session):
            return concert
        inst = str(session.get("instrument") or "").strip()
        sax = str(session.get("sax_type") or "").strip()
        ttype = sax or inst
        return str(written_key_for_type(concert, ttype) or concert).strip()
    except ImportError:
        return concert


def stamp_mission_backing_handoff(session: dict[str, Any]) -> None:
    """Explicit Mission → Backing owner. Outranks leftover entry_jam / SBI / Catalog."""
    session["improv_mission_backing_handoff"] = True
    session[BACKING_HANDOFF_SOURCE_KEY] = MISSION_OWNER
    session[MISSION_RETURN_DESTINATION_KEY] = "mission"
    session.pop("_backing_released_specialized_context", None)
    # Leftover Jam / SBI entry must not steal the open-backing classifier.
    try:
        from creative_source_ownership_contract import stamp_explicit_backing_handoff

        stamp_explicit_backing_handoff(session, MISSION_OWNER)
    except ImportError:
        session["_backing_explicit_handoff_epoch"] = int(session.get("_backing_explicit_handoff_epoch") or 0) + 1


def mission_backing_handoff_pending(session: dict[str, Any]) -> bool:
    """True when a fresh Mission Backing launch is in flight."""
    if bool(session.get("improv_mission_backing_handoff")):
        return True
    if str(session.get(BACKING_HANDOFF_SOURCE_KEY) or "").strip() == MISSION_OWNER:
        # Only while leaving Creative or already on Backing with Mission owner.
        page = str(session.get("studio_page") or "").strip().lower()
        if page in {"creative", "backing"}:
            return True
    try:
        from music_workflow_mission_backing_click import peek_mission_backing_click_intent

        if peek_mission_backing_click_intent(session):
            return True
    except ImportError:
        pass
    return False


def return_to_mission_eligible(session: dict[str, Any]) -> bool:
    """Return to Mission only while current Backing owner is Mission."""
    return live_backing_owner_is_mission(session)


def clear_mission_return_eligibility(session: dict[str, Any]) -> None:
    """Drop Mission return destination after leave / non-Mission backing."""
    session.pop(MISSION_RETURN_DESTINATION_KEY, None)
    if str(session.get(BACKING_HANDOFF_SOURCE_KEY) or "").strip() == MISSION_OWNER:
        session.pop(BACKING_HANDOFF_SOURCE_KEY, None)
    session.pop("improv_mission_backing_handoff", None)


def resolve_mission_owner_context(session: dict[str, Any]) -> MissionOwnerContext:
    """One explicit Mission context for UI / handoff / tests."""
    practice = resolve_mission_underlying_practice_key(session)
    written = resolve_mission_written_key(session, practice)
    pick = ""
    title = ""
    try:
        from songs.practice_key_state import resolve_practice_source_pick
        from songs.music_source import custom_progression_is_active, custom_pick_key_for
        from custom_progression_lab import CPL_ACTIVE_KEY

        if custom_progression_is_active(session):
            active = session.get(CPL_ACTIVE_KEY)
            if isinstance(active, dict):
                pick = str(custom_pick_key_for(active) or "").strip()
                title = str(active.get("name") or active.get("title") or "").strip()
        if not pick:
            pick = str(resolve_practice_source_pick(session) or "").strip()
    except ImportError:
        pick = str(session.get("active_catalog_pick_key") or "").strip()
    if not title:
        sel = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
        title = str(
            (sel or {}).get("title")
            or session.get("song")
            or session.get("active_song_title")
            or ""
        ).strip()
    chord = str(
        session.get("improv_selected_chord")
        or session.get("improv_mission_selected_chord")
        or ""
    ).strip()
    section = str(session.get("improv_selected_section") or "Progression").strip()
    mission = str(
        session.get("improv_mission_pick") or session.get("improv_active_mission") or ""
    ).strip()
    return MissionOwnerContext(
        underlying_pick=pick,
        underlying_title=title,
        mission_pick=mission,
        section_label=section,
        concert_chord=chord,
        practice_key=practice,
        written_key=written,
        instrument=str(session.get("instrument") or "").strip(),
        backing_handoff=str(session.get(BACKING_HANDOFF_SOURCE_KEY) or "").strip(),
        return_destination=str(session.get(MISSION_RETURN_DESTINATION_KEY) or "").strip(),
    )


__all__ = (
    "MISSION_OWNER",
    "BACKING_HANDOFF_SOURCE_KEY",
    "MISSION_RETURN_DESTINATION_KEY",
    "MissionOwnerContext",
    "missions_surface_owns",
    "live_backing_owner_is_mission",
    "resolve_mission_underlying_practice_key",
    "resolve_mission_written_key",
    "stamp_mission_backing_handoff",
    "mission_backing_handoff_pending",
    "return_to_mission_eligible",
    "clear_mission_return_eligibility",
    "resolve_mission_owner_context",
)

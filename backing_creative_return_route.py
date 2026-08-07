"""Sealed Creative return destination captured when Backing opens — consumed verbatim on Return."""

from __future__ import annotations

from typing import Any

CREATIVE_RETURN_ROUTE_BLOB_KEY = "creative_return_route"
ROUTE_VERSION = 1


def read_live_creative_surface_at_backing_launch(session: dict[str, Any]) -> tuple[str, str]:
    """Top-level Creative tab + entry submode from live session at handoff (before Backing mutates UI)."""
    try:
        from studio_page_state import CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY
    except ImportError:
        CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY = "creative_improv_intelligence_tab"

    tab = str(
        session.get("improv_intelligence_tab")
        or session.get(CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY)
        or "Entry & Jam"
    ).strip()
    try:
        from backing_source_navigation import _creative_handoff_entry_mode

        entry = _creative_handoff_entry_mode(session)
    except ImportError:
        entry = str(session.get("improv_entry_mode") or "").strip()
    return tab, entry


def capture_creative_return_route_at_backing_launch(
    session: dict[str, Any],
    *,
    backing_source: str,
    workflow_owner: str,
    launch_tab: str,
    launch_entry: str,
    ctx: Any | None = None,
) -> dict[str, Any]:
    """Persist complete Creative origin sufficient to restore exact launch surface on Return."""
    src = str(backing_source or "").strip()
    tab = str(launch_tab or "").strip()
    entry = str(launch_entry or "").strip()

    if src == "mission":
        tab = "Missions"
        if not entry:
            entry = str(getattr(ctx, "entry_mode", "") or "Song-Based Improvisation").strip()
    elif src == "song_improv":
        tab = "Entry & Jam"
        entry = "Song-Based Improvisation"
    elif src == "entry_jam":
        tab = "Entry & Jam"
        if entry not in ("Style Jam Mode", "Jam Session Generator"):
            entry = str(getattr(ctx, "entry_mode", "") or "Style Jam Mode").strip()
        if entry not in ("Style Jam Mode", "Jam Session Generator"):
            entry = "Style Jam Mode"

    owner = str(workflow_owner or "").strip()
    if src == "mission":
        owner = "mission_jam"
    elif src == "song_improv":
        owner = "song_based_improvisation"
    elif src == "entry_jam" and owner not in ("style_jam", "jam_session_generator"):
        owner = "style_jam" if entry == "Style Jam Mode" else "jam_session_generator"

    route: dict[str, Any] = {
        "version": ROUTE_VERSION,
        "studio_page": "creative",
        "intelligence_tab": tab or ("Missions" if src == "mission" else "Entry & Jam"),
        "entry_mode": entry,
        "workflow_owner": owner,
        "backing_source": src,
    }
    mission_id = str(
        getattr(ctx, "mission_id", None)
        or session.get("improv_active_mission")
        or session.get("improv_mission_pick")
        or ""
    ).strip()
    if mission_id:
        route["mission_id"] = mission_id
    chord = str(session.get("ii_selected_chord") or session.get("II_SELECTED_CHORD") or "").strip()
    if chord:
        route["mission_chord"] = chord
    section = str(
        session.get("ii_selected_section")
        or session.get("II_SELECTED_SECTION")
        or session.get("improv_selected_section")
        or ""
    ).strip()
    if section:
        route["mission_section"] = section
    pick = str(session.get("active_catalog_pick_key") or "").strip()
    if pick:
        route["song_pick_key"] = pick
    return route


def get_creative_return_route(session: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from backing_context import BACKING_CONTEXT_KEY

        raw = session.get(BACKING_CONTEXT_KEY)
    except ImportError:
        raw = session.get("backing_context")
    if not isinstance(raw, dict):
        return None
    route = raw.get(CREATIVE_RETURN_ROUTE_BLOB_KEY)
    return dict(route) if isinstance(route, dict) else None


def apply_creative_return_route(
    session: dict[str, Any],
    route: dict[str, Any],
    *,
    ctx: Any | None = None,
) -> None:
    """Apply sealed launch route — no inference from stale tabs or post-backing session drift."""
    tab = str(route.get("intelligence_tab") or "Entry & Jam").strip()
    entry = str(route.get("entry_mode") or "").strip()
    owner = str(route.get("workflow_owner") or "").strip()
    src = str(route.get("backing_source") or "").strip()
    mission_id = str(route.get("mission_id") or "").strip()
    chord = str(route.get("mission_chord") or "").strip()
    section = str(route.get("mission_section") or "").strip()

    try:
        from music_workflow_activation import activate_workflow_simple

        if owner == "song_based_improvisation" or src == "song_improv":
            activate_workflow_simple(
                session,
                "song_based_improvisation",
                activation_source="return_from_backing",
                return_route="creative",
            )
            try:
                from generated_jam_key_context import deactivate_generated_jam_key_ownership

                deactivate_generated_jam_key_ownership(session)
            except ImportError:
                pass
            try:
                from song_improv_scope_authority import (
                    apply_song_improv_entry_defaults,
                    restore_song_improv_creative_navigation,
                )

                restore_song_improv_creative_navigation(session)
                apply_song_improv_entry_defaults(session, source="return_from_backing")
            except ImportError:
                pass
        elif owner == "jam_session_generator":
            activate_workflow_simple(
                session,
                "jam_session_generator",
                activation_source="return_from_backing",
                return_route="creative",
            )
        elif owner == "style_jam":
            activate_workflow_simple(
                session,
                "style_jam",
                activation_source="return_from_backing",
                return_route="creative",
            )
        elif owner == "mission_jam" or src == "mission":
            activate_workflow_simple(
                session,
                "mission_jam",
                activation_source="return_from_backing",
                return_route="creative",
                navigation_intent="return_from_backing",
            )
    except ImportError:
        pass

    if ctx is not None:
        try:
            from backing_source_navigation import restore_session_widgets_from_backing_context

            restore_session_widgets_from_backing_context(session, ctx)
        except ImportError:
            pass

    try:
        from studio_page_state import CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY

        session["improv_intelligence_tab"] = tab
        session[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = tab
    except ImportError:
        session["improv_intelligence_tab"] = tab
        session["creative_improv_intelligence_tab"] = tab
    if entry:
        session["improv_entry_mode"] = entry
    session.pop("_improv_tab_user_touched", None)

    if mission_id:
        session["improv_active_mission"] = mission_id
        session["improv_mission_pick"] = mission_id
    if chord:
        session["ii_selected_chord"] = chord
        session["II_SELECTED_CHORD"] = chord
    if section:
        session["ii_selected_section"] = section
        session["II_SELECTED_SECTION"] = section

    if src == "mission" or owner == "mission_jam":
        try:
            from mission_practice_context import refresh_mission_practice_context

            refresh_mission_practice_context(session)
        except ImportError:
            pass
    try:
        from backing_source_navigation import project_return_destination_to_canonical_creative_selectors

        project_return_destination_to_canonical_creative_selectors(
            session,
            intelligence_tab=tab,
            entry_mode=entry,
        )
    except ImportError:
        pass


__all__ = [
    "CREATIVE_RETURN_ROUTE_BLOB_KEY",
    "apply_creative_return_route",
    "capture_creative_return_route_at_backing_launch",
    "get_creative_return_route",
    "read_live_creative_surface_at_backing_launch",
]

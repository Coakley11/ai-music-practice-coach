"""Explicit backing session route model (regular / entry jam / mission jam)."""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from typing import Any, Literal

BackingSessionType = Literal["regular_song", "entry_jam", "mission_jam"]
SongSourceType = Literal["catalog", "custom"]

BACKING_SESSION_ROUTE_KEY = "backing_session_route"
BACKING_ROUTE_DIAG_KEY = "_backing_session_route_diag"

CreativeReturn = Literal["creative", "picker", "custom_editor"]


@dataclass
class BackingSessionRoute:
    backing_session_type: BackingSessionType
    song_source_type: SongSourceType
    pick_key: str = ""
    custom_song_id: str = ""
    creative_tab: str = ""
    return_destination: str = "creative"
    parent_regular_backing: str = "regular_song"
    mission_id: str = ""
    stale_mission_context_cleared: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Any) -> BackingSessionRoute | None:
        if not isinstance(raw, dict):
            return None
        bst = str(raw.get("backing_session_type") or "").strip()
        sst = str(raw.get("song_source_type") or "").strip()
        if bst not in {"regular_song", "entry_jam", "mission_jam"}:
            return None
        if sst not in {"catalog", "custom"}:
            sst = "catalog"
        return cls(
            backing_session_type=bst,  # type: ignore[arg-type]
            song_source_type=sst,  # type: ignore[arg-type]
            pick_key=str(raw.get("pick_key") or ""),
            custom_song_id=str(raw.get("custom_song_id") or ""),
            creative_tab=str(raw.get("creative_tab") or ""),
            return_destination=str(raw.get("return_destination") or "creative"),
            parent_regular_backing=str(raw.get("parent_regular_backing") or "regular_song"),
            mission_id=str(raw.get("mission_id") or ""),
            stale_mission_context_cleared=bool(raw.get("stale_mission_context_cleared")),
        )


def _song_source_type(session: dict[str, Any]) -> SongSourceType:
    try:
        from songs.music_source import cpl_session_is_active, is_custom_progression

        if is_custom_progression(session) or cpl_session_is_active(session):
            return "custom"
    except ImportError:
        pass
    if str(session.get("active_music_source") or "").strip() == "custom_progression":
        return "custom"
    return "catalog"


def _backing_session_type_from_ctx_source(source: str) -> BackingSessionType:
    if source == "mission":
        return "mission_jam"
    if source == "entry_jam":
        return "entry_jam"
    if source in {"regular_song", "custom_progression"}:
        return "regular_song"
    if source == "song_improv":
        return "entry_jam"
    return "regular_song"


def get_backing_session_route(session: dict[str, Any]) -> BackingSessionRoute | None:
    return BackingSessionRoute.from_dict(session.get(BACKING_SESSION_ROUTE_KEY))


def sync_backing_session_route_from_context(session: dict[str, Any]) -> BackingSessionRoute | None:
    try:
        from backing_context import get_backing_context
    except ImportError:
        return None
    ctx = get_backing_context(session)
    if ctx is None:
        session.pop(BACKING_SESSION_ROUTE_KEY, None)
        return None
    source = str(ctx.source or "").strip()
    bst = _backing_session_type_from_ctx_source(source)
    sst = _song_source_type(session)
    if source == "custom_progression":
        sst = "custom"
    pick_key = str(
        ctx.bound_pick_key or ctx.active_song_id or session.get("active_catalog_pick_key") or ""
    ).strip()
    custom_id = ""
    if sst == "custom":
        active = session.get("cpl_active_progression")
        if isinstance(active, dict):
            custom_id = str(active.get("id") or active.get("name") or "").strip()
    tab = str(session.get("improv_intelligence_tab") or session.get("creative_improv_intelligence_tab") or "")
    mission_id = str(ctx.mission_id or session.get("improv_active_mission") or "").strip()
    route = BackingSessionRoute(
        backing_session_type=bst,
        song_source_type=sst,
        pick_key=pick_key,
        custom_song_id=custom_id,
        creative_tab=tab,
        return_destination="creative",
        parent_regular_backing="regular_song",
        mission_id=mission_id if bst == "mission_jam" else "",
    )
    session[BACKING_SESSION_ROUTE_KEY] = route.to_dict()
    return route


def deactivate_mission_backing_ui_state(session: dict[str, Any]) -> None:
    """Clear transient mission backing ownership (not persisted mission artifacts)."""
    from improvisation_missions import IMPROV_MISSION_PRACTICE_LICK_HANDOFF

    session.pop(IMPROV_MISSION_PRACTICE_LICK_HANDOFF, None)
    session.pop("improv_mission_backing_handoff", None)
    try:
        from mission_backing_handoff_persistence import MISSION_BACKING_HANDOFF_ACTIVE_KEY

        session.pop(MISSION_BACKING_HANDOFF_ACTIVE_KEY, None)
    except ImportError:
        session.pop("_mission_backing_handoff_active", None)
    session["_backing_mission_ui_suppressed"] = True


def clear_mission_ui_suppression(session: dict[str, Any]) -> None:
    session.pop("_backing_mission_ui_suppressed", None)


def mission_backing_ui_allowed(session: dict[str, Any]) -> bool:
    if session.get("_backing_mission_ui_suppressed"):
        return False
    if session.get("_pending_upload_suppresses_mission_backing"):
        return False
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is None:
            return False
        return str(ctx.source or "") == "mission"
    except ImportError:
        return False


def on_creative_backing_handoff(session: dict[str, Any], *, source: str) -> None:
    """Entry/mission handoff hygiene — separate backing workflows."""
    src = str(source or "").strip()
    cleared = False
    if src == "entry_jam" or src in {"song_improv", "custom_progression"}:
        deactivate_mission_backing_ui_state(session)
        cleared = True
        clear_mission_ui_suppression(session)
    elif src == "mission":
        session.pop("_backing_mission_ui_suppressed", None)
        session.pop("_pending_upload_suppresses_mission_backing", None)
        cleared = False
    route = sync_backing_session_route_from_context(session)
    if route is not None:
        route.stale_mission_context_cleared = cleared
        session[BACKING_SESSION_ROUTE_KEY] = route.to_dict()
    session[BACKING_ROUTE_DIAG_KEY] = {
        "handoff_source": src,
        "stale_mission_context_cleared": cleared,
        "route": copy.deepcopy(session.get(BACKING_SESSION_ROUTE_KEY)),
    }


def visible_navigation_actions(session: dict[str, Any]) -> list[str]:
    try:
        from backing_nav_actions import build_backing_nav_actions

        actions, _ = build_backing_nav_actions(session)
        if actions:
            return [a.label for a in actions]
    except ImportError:
        pass
    route = get_backing_session_route(session) or sync_backing_session_route_from_context(session)
    if route is None:
        return []
    actions: list[str] = []
    bst, sst = route.backing_session_type, route.song_source_type
    if bst == "entry_jam":
        actions.append("Return to Creative Page")
    elif bst == "mission_jam":
        actions.append("Return to Mission")
        actions.append("Return to Creative Page")
    elif bst == "regular_song":
        actions.append("Return to Custom Songs" if sst == "custom" else "Return to Song Catalog")
    return actions


def return_to_regular_backing_label(session: dict[str, Any]) -> str | None:
    route = get_backing_session_route(session) or sync_backing_session_route_from_context(session)
    if route is None or route.backing_session_type == "regular_song":
        return None
    if route.song_source_type == "custom":
        try:
            from backing_source_navigation import return_to_catalog_song_backing_label

            return return_to_catalog_song_backing_label(custom=True)
        except ImportError:
            return "🎧 Return to Custom Song Backing"
    try:
        from backing_source_navigation import return_to_catalog_song_backing_label

        return return_to_catalog_song_backing_label(custom=False)
    except ImportError:
        return "🎧 Return to Catalog Song Backing"


def navigate_to_regular_backing(session: dict[str, Any], *, st_like: Any | None = None) -> None:
    """Leave jam/practice backing; restore normal catalog/custom backing for same song."""
    route = get_backing_session_route(session)
    sst = route.song_source_type if route else _song_source_type(session)
    deactivate_mission_backing_ui_state(session)
    try:
        from backing_context import restore_custom_song_backing, restore_regular_song_backing

        if sst == "custom":
            restore_custom_song_backing(session, st_like=st_like)
        else:
            restore_regular_song_backing(session, st_like=st_like)
    except ImportError:
        pass
    sync_backing_session_route_from_context(session)


def render_backing_route_dev_marker(st_module: Any, session: dict[str, Any]) -> None:
    try:
        from suite_workspace import is_developer_mode_enabled

        if not is_developer_mode_enabled(st=st_module):
            return
    except ImportError:
        if not session.get("dev_mode"):
            return
    route = get_backing_session_route(session) or sync_backing_session_route_from_context(session)
    style_diag = session.get("_mission_jam_style_resolution") or {}
    deploy = str(session.get("_studio_ui_release_sha") or session.get("_deploy_sha") or "—")
    st_module.caption(
        "DEV backing route · "
        f"type `{getattr(route, 'backing_session_type', '—')}` · "
        f"song_src `{getattr(route, 'song_source_type', '—')}` · "
        f"renderer `{session.get('studio_page', '—')}` · "
        f"nav `{visible_navigation_actions(session)}` · "
        f"style `{style_diag.get('groove', '—')}` src `{style_diag.get('source', '—')}` · "
        f"mission_ui `{mission_backing_ui_allowed(session)}` · "
        f"sha `{deploy[:7] if deploy != '—' else '—'}`"
    )


__all__ = [
    "BACKING_SESSION_ROUTE_KEY",
    "BackingSessionRoute",
    "deactivate_mission_backing_ui_state",
    "get_backing_session_route",
    "mission_backing_ui_allowed",
    "navigate_to_regular_backing",
    "on_creative_backing_handoff",
    "render_backing_route_dev_marker",
    "return_to_regular_backing_label",
    "sync_backing_session_route_from_context",
    "visible_navigation_actions",
]

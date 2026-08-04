"""Backing page navigation actions — build once, dedupe by destination + purpose."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

BACKING_NAV_DIAG_KEY = "_backing_nav_actions_diag"


@dataclass(frozen=True)
class BackingNavAction:
    action_id: str
    label: str
    destination: str
    purpose: str


def _catalog_backing_destination(session: dict[str, Any]) -> str:
    try:
        from backing_session_route import get_backing_session_route, sync_backing_session_route_from_context

        route = get_backing_session_route(session) or sync_backing_session_route_from_context(session)
        if route and route.song_source_type == "custom":
            return "regular_custom_backing"
    except ImportError:
        pass
    return "regular_catalog_backing"


def build_backing_nav_actions(session: dict[str, Any]) -> tuple[list[BackingNavAction], list[str]]:
    """
    Collect intended backing nav buttons and remove duplicates.

    Rules:
    - ``Return to Catalog Song Backing`` suppresses ``Use catalog song backing``.
    - One ``Return to Mission`` when destinations match.
    - ``Return to Creative Page`` and ``Return to Mission`` may coexist when distinct.
    """
    actions: list[BackingNavAction] = []
    try:
        from backing_context import BackingContext, get_backing_context
        from backing_session_route import return_to_regular_backing_label
        from backing_source_navigation import return_to_source_button_label
        from backing_workflow_context import get_backing_workflow_envelope, workflow_is_generated
    except ImportError:
        return [], []

    ctx: BackingContext | None = get_backing_context(session)
    if ctx is None:
        return [], []

    src = str(getattr(ctx, "source", "") or "").strip()
    env = get_backing_workflow_envelope(session) or {}
    wf = str(env.get("workflow_type") or "").strip()
    jam_label = return_to_regular_backing_label(session)

    if src in {"entry_jam", "song_improv", "mission"}:
        creative_dest = "creative:missions" if src == "mission" or wf == "mission_jam" else "creative:improvisation"
        actions.append(
            BackingNavAction(
                action_id="return_creative",
                label=return_to_source_button_label(ctx),
                destination=creative_dest,
                purpose="return_creative",
            )
        )
        if src == "mission" or wf == "mission_jam":
            actions.append(
                BackingNavAction(
                    action_id="return_mission",
                    label="Return to Mission",
                    destination="creative:mission_detail",
                    purpose="return_mission",
                )
            )

    if jam_label and src in {"entry_jam", "song_improv", "mission"}:
        actions.append(
            BackingNavAction(
                action_id="return_catalog_backing",
                label=str(jam_label),
                destination=_catalog_backing_destination(session),
                purpose="catalog_backing",
            )
        )

    if src in {"entry_jam", "mission", "song_improv"}:
        deduped, removed = _dedupe_actions(actions)
        session[BACKING_NAV_DIAG_KEY] = {
            "visible": [a.label for a in deduped],
            "removed_duplicates": removed,
        }
        return deduped, removed

    if src == "regular_song" or not src:
        try:
            from backing_session_route import get_backing_session_route

            route = get_backing_session_route(session)
            if route and route.song_source_type == "custom":
                actions.append(
                    BackingNavAction(
                        action_id="return_custom_songs",
                        label="Return to Custom Songs",
                        destination="creative:custom",
                        purpose="return_creative",
                    )
                )
            else:
                actions.append(
                    BackingNavAction(
                        action_id="return_song_catalog",
                        label="🎵 Return to Song Catalog",
                        destination="picker:catalog",
                        purpose="return_catalog_picker",
                    )
                )
        except ImportError:
            pass

    deduped, removed = _dedupe_actions(actions)
    session[BACKING_NAV_DIAG_KEY] = {
        "visible": [a.label for a in deduped],
        "removed_duplicates": removed,
    }
    return deduped, removed


def _dedupe_actions(actions: list[BackingNavAction]) -> tuple[list[BackingNavAction], list[str]]:
    removed: list[str] = []
    seen_dest: set[str] = set()
    seen_purpose: set[str] = set()
    out: list[BackingNavAction] = []

    has_catalog_return = any(a.purpose == "catalog_backing" for a in actions)

    for action in actions:
        if action.purpose == "use_catalog_backing" and has_catalog_return:
            removed.append(f"DUPLICATE_BACKING_NAV_ACTION:{action.label}")
            continue
        if action.label.strip().lower().startswith("use catalog song backing") and has_catalog_return:
            removed.append(f"DUPLICATE_BACKING_NAV_ACTION:{action.label}")
            continue
        key = (action.destination, action.purpose)
        if action.purpose in {"return_mission", "catalog_backing", "return_creative"}:
            if action.purpose in seen_purpose and action.purpose != "return_creative":
                removed.append(f"DUPLICATE_BACKING_NAV_ACTION:{action.label}")
                continue
            seen_purpose.add(action.purpose)
        if action.destination in seen_dest and action.purpose not in {"return_creative", "return_mission"}:
            removed.append(f"DUPLICATE_BACKING_NAV_ACTION:{action.label}")
            continue
        seen_dest.add(action.destination)
        out.append(action)
    return out, removed


def catalog_return_action_visible(session: dict[str, Any]) -> bool:
    """True when the primary UI already offers return-to-catalog-song-backing."""
    actions, _ = build_backing_nav_actions(session)
    return any(a.purpose == "catalog_backing" for a in actions)


__all__ = [
    "BACKING_NAV_DIAG_KEY",
    "BackingNavAction",
    "build_backing_nav_actions",
    "catalog_return_action_visible",
]

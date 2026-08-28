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
    icon: str = ""
    priority: int = 50


def _catalog_backing_destination(session: dict[str, Any]) -> str:
    try:
        from backing_session_route import get_backing_session_route, sync_backing_session_route_from_context

        route = get_backing_session_route(session) or sync_backing_session_route_from_context(session)
        if route and route.song_source_type == "custom":
            return "regular_custom_backing"
    except ImportError:
        pass
    return "regular_catalog_backing"


def _workflow_identity(session: dict[str, Any], ctx: Any) -> str:
    try:
        from backing_workflow_context import get_backing_workflow_envelope

        env = get_backing_workflow_envelope(session) or {}
        wf = str(env.get("workflow_type") or "").strip()
        sid = str(env.get("session_id") or session.get("active_catalog_pick_key") or "").strip()
        return f"{wf}|{sid}|{getattr(ctx, 'source', '')}"
    except ImportError:
        return str(getattr(ctx, "source", "") or "")


def build_backing_nav_actions(session: dict[str, Any]) -> tuple[list[BackingNavAction], list[str]]:
    """
    Collect intended backing nav buttons and remove duplicates.

    Deduplicate by (destination, purpose, workflow identity). Never show two mission-return buttons.
    """
    candidates: list[BackingNavAction] = []
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
    wf_id = _workflow_identity(session, ctx)
    jam_label = return_to_regular_backing_label(session)

    if src == "custom_progression":
        candidates.append(
            BackingNavAction(
                action_id="return_custom_page",
                label=return_to_source_button_label(ctx),
                destination="custom",
                purpose="return_custom_page",
                icon="custom",
                priority=10,
            )
        )
        deduped, removed = _dedupe_actions(candidates, session=session, workflow_id=wf_id)
        _store_nav_diag(session, candidates, deduped, removed)
        return deduped, removed

    if src in {"entry_jam", "song_improv", "mission"}:
        creative_dest = "creative:missions" if src == "mission" or wf == "mission_jam" else "creative:improvisation"
        candidates.append(
            BackingNavAction(
                action_id="return_creative",
                label=return_to_source_button_label(ctx),
                destination=creative_dest,
                purpose="return_creative",
                icon="creative",
                priority=10,
            )
        )
        if src == "mission" or wf == "mission_jam":
            candidates.append(
                BackingNavAction(
                    action_id="return_mission",
                    label="Return to Mission",
                    destination=f"creative:mission_detail|{wf_id}",
                    purpose="return_mission",
                    icon="mission",
                    priority=5,
                )
            )

    if jam_label and src in {"entry_jam", "song_improv", "mission"}:
        # Mission Backing under Custom/Catalog GA: do not offer ordinary song
        # Backing fallthrough while the Mission handoff is active. That button
        # competes with "Return to Mission" and reclaims Custom/Catalog owner.
        suppress_ordinary = (
            src == "mission"
            and not session.get("_backing_released_specialized_context")
            and (
                str(session.get("_backing_explicit_handoff_source") or "").strip() == "mission"
                or bool(session.get("_music_mission_canonical_return_destination"))
            )
        )
        if not suppress_ordinary:
            candidates.append(
                BackingNavAction(
                    action_id="return_catalog_backing",
                    label=str(jam_label),
                    destination=_catalog_backing_destination(session),
                    purpose="catalog_backing",
                    icon="headphones",
                    priority=30,
                )
            )

    if src in {"entry_jam", "mission", "song_improv"}:
        deduped, removed = _dedupe_actions(candidates, session=session, workflow_id=wf_id)
        _store_nav_diag(session, candidates, deduped, removed)
        return deduped, removed

    if src == "regular_song" or not src:
        custom_dest = None
        try:
            from custom_page_return_destination import peek_custom_page_return_destination

            custom_dest = peek_custom_page_return_destination(session)
        except ImportError:
            custom_dest = None
        if isinstance(custom_dest, dict):
            candidates.append(
                BackingNavAction(
                    action_id="return_custom_page",
                    label="✏️ Return to Custom Page",
                    destination="custom",
                    purpose="return_custom_page",
                    icon="custom",
                    priority=10,
                )
            )
        else:
            try:
                from backing_session_route import get_backing_session_route

                route = get_backing_session_route(session)
                if route and route.song_source_type == "custom":
                    candidates.append(
                        BackingNavAction(
                            action_id="return_custom_songs",
                            label="Return to Custom Songs",
                            destination="creative:custom",
                            purpose="return_custom_page",
                            icon="creative",
                            priority=10,
                        )
                    )
                else:
                    candidates.append(
                        BackingNavAction(
                            action_id="return_song_catalog",
                            label="🎵 Return to Song Catalog",
                            destination="picker:catalog",
                            purpose="return_catalog_picker",
                            icon="song_catalog",
                            priority=10,
                        )
                    )
            except ImportError:
                pass

    deduped, removed = _dedupe_actions(candidates, session=session, workflow_id=wf_id)
    _store_nav_diag(session, candidates, deduped, removed)
    return deduped, removed


def _dedupe_actions(
    actions: list[BackingNavAction],
    *,
    session: dict[str, Any],
    workflow_id: str,
) -> tuple[list[BackingNavAction], list[str]]:
    removed: list[str] = []
    seen_purpose: set[str] = set()
    seen_dest_purpose: set[tuple[str, str]] = set()
    out: list[BackingNavAction] = []

    has_catalog_return = any(a.purpose == "catalog_backing" for a in actions)
    sorted_actions = sorted(actions, key=lambda a: a.priority)

    for action in sorted_actions:
        if action.purpose == "use_catalog_backing" and has_catalog_return:
            removed.append(f"DUPLICATE_BACKING_NAV_ACTION:{action.label}:catalog_backing_exists")
            continue
        low = action.label.strip().lower()
        if low.startswith("use catalog song backing") and has_catalog_return:
            removed.append(f"DUPLICATE_BACKING_NAV_ACTION:{action.label}:use_catalog_suppressed")
            continue
        if action.purpose == "return_mission" and "return_mission" in seen_purpose:
            removed.append(f"DUPLICATE_BACKING_NAV_ACTION:{action.label}:second_mission_return")
            continue
        if action.purpose == "return_creative":
            dup_edit = any(
                a.purpose == "return_creative" and a.action_id != action.action_id for a in out
            )
            if dup_edit:
                removed.append(f"DUPLICATE_BACKING_NAV_ACTION:{action.label}:return_creative")
                continue
        key = (action.destination.split("|")[0], action.purpose)
        if key in seen_dest_purpose and action.purpose not in {"return_creative", "return_mission"}:
            removed.append(f"DUPLICATE_BACKING_NAV_ACTION:{action.label}:dest_purpose")
            continue
        seen_dest_purpose.add(key)
        seen_purpose.add(action.purpose)
        out.append(action)
    return out, removed


def _store_nav_diag(
    session: dict[str, Any],
    candidates: list[BackingNavAction],
    visible: list[BackingNavAction],
    removed: list[str],
) -> None:
    deploy = str(session.get("_studio_ui_release_sha") or "")[:7]
    session[BACKING_NAV_DIAG_KEY] = {
        "candidates": [a.label for a in candidates],
        "visible": [a.label for a in visible],
        "removed_duplicates": removed,
        "destinations": {a.label: a.destination for a in visible},
        "deploy_sha": deploy,
    }


def catalog_return_action_visible(session: dict[str, Any]) -> bool:
    """True when the primary UI already offers return-to-catalog-song-backing."""
    actions, _ = build_backing_nav_actions(session)
    return any(a.purpose == "catalog_backing" for a in actions)


def backing_nav_has_return_mission(session: dict[str, Any]) -> bool:
    actions, _ = build_backing_nav_actions(session)
    return any(a.action_id == "return_mission" for a in actions)


__all__ = [
    "BACKING_NAV_DIAG_KEY",
    "BackingNavAction",
    "backing_nav_has_return_mission",
    "build_backing_nav_actions",
    "catalog_return_action_visible",
]

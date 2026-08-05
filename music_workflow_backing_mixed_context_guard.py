"""Fail closed when Backing page mixes mission workflow with untyped catalog backing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MIXED_BACKING_MISSION_CATALOG = "MIXED_BACKING_MISSION_CATALOG_CONTEXT"
MIXED_BACKING_GUARD_DIAG_KEY = "_music_backing_mixed_context_diag"


@dataclass
class MixedBackingContextResult:
    blocked: bool
    code: str = ""
    message: str = ""
    diagnostics: dict[str, Any] = field(default_factory=dict)


def _mission_example_active(session: dict[str, Any]) -> bool:
    try:
        from improvisation_missions import MISSION_EXAMPLE_KEY

        raw = session.get(MISSION_EXAMPLE_KEY)
        return isinstance(raw, dict) and bool(str(raw.get("chord") or "").strip())
    except ImportError:
        raw = session.get("improv_mission_example")
        return isinstance(raw, dict) and bool(str(raw.get("chord") or "").strip())


def _valid_typed_mission_handoff(session: dict[str, Any]) -> bool:
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and str(getattr(ctx, "source", "") or "").strip() == "mission":
            return True
    except ImportError:
        pass
    try:
        from music_workflow_pending_backing_handoff import peek_pending_backing_workflow_handoff

        pending = peek_pending_backing_workflow_handoff(session)
        if isinstance(pending, dict) and str(pending.get("backing_source") or "") == "mission":
            return True
    except ImportError:
        pass
    try:
        from mission_return_destination import peek_mission_return_destination

        if peek_mission_return_destination(session):
            return True
    except ImportError:
        pass
    return bool(session.get("improv_mission_backing_handoff"))


def evaluate_backing_mixed_mission_catalog_context(session: dict[str, Any]) -> MixedBackingContextResult:
    """Detect mission_jam authority with regular_song/catalog backing context (invalid mix)."""
    page = str(session.get("studio_page") or "").strip().lower()
    if page != "backing":
        return MixedBackingContextResult(blocked=False)

    ptr_owner = ""
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        if ptr:
            ptr_owner = str(ptr.workflow_owner or "").strip()
    except ImportError:
        pass

    mission_active = ptr_owner == "mission_jam" or _mission_example_active(session)
    if not mission_active:
        return MixedBackingContextResult(blocked=False)

    ctx_source = ""
    ctx_label = ""
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            ctx_source = str(getattr(ctx, "source", "") or "").strip()
            ctx_label = str(getattr(ctx, "source_label", "") or "").strip()
    except ImportError:
        pass

    if ctx_source not in {"regular_song", ""}:
        return MixedBackingContextResult(blocked=False)

    if ctx_source == "regular_song" and _valid_typed_mission_handoff(session):
        return MixedBackingContextResult(blocked=False)

    if ctx_source == "regular_song" or (not ctx_source and mission_active):
        diag = {
            "pointer_owner": ptr_owner,
            "backing_context_source": ctx_source,
            "backing_context_label": ctx_label,
            "mission_example_active": _mission_example_active(session),
            "typed_mission_handoff": _valid_typed_mission_handoff(session),
        }
        session[MIXED_BACKING_GUARD_DIAG_KEY] = diag
        try:
            from music_workflow_state_store import record_compat_fallback

            record_compat_fallback(session, MIXED_BACKING_MISSION_CATALOG, ctx_source or "missing")
        except ImportError:
            pass
        return MixedBackingContextResult(
            blocked=True,
            code=MIXED_BACKING_MISSION_CATALOG,
            message=(
                "Backing opened with catalog song context while a Mission workflow is active. "
                "Return to Creative → Missions and use Mission Backing when you intend to jam."
            ),
            diagnostics=diag,
        )
    return MixedBackingContextResult(blocked=False)


def remediate_mixed_backing_mission_catalog_context(session: dict[str, Any]) -> None:
    """Keep mission state; leave backing page without applying catalog authority."""
    try:
        from studio_nav_history import navigate_studio_page

        navigate_studio_page(session, "creative")
    except ImportError:
        session["studio_page"] = "creative"
    session["improv_intelligence_tab"] = "Missions"
    try:
        from creative_tab_tool_persistence import persist_improv_intelligence_tab

        persist_improv_intelligence_tab(session)
    except ImportError:
        pass


__all__ = [
    "MIXED_BACKING_GUARD_DIAG_KEY",
    "MIXED_BACKING_MISSION_CATALOG",
    "MixedBackingContextResult",
    "evaluate_backing_mixed_mission_catalog_context",
    "remediate_mixed_backing_mission_catalog_context",
]

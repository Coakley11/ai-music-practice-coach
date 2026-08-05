"""Pre-widget workflow activation for Creative → Backing handoffs (Mission / Jam)."""

from __future__ import annotations

import copy
from typing import Any, Literal

PENDING_BACKING_WORKFLOW_KEY = "_music_pending_backing_workflow_handoff"
PENDING_BACKING_WORKFLOW_CONSUMED_SEQ_KEY = "_music_pending_backing_workflow_consumed_seq"
PENDING_BACKING_WORKFLOW_CONSUMED_FP_KEY = "_music_pending_backing_workflow_consumed_fp"
PENDING_BACKING_WORKFLOW_RERUN_SEQ_KEY = "_music_pending_backing_workflow_rerun_for_seq"

ConsumePhase = Literal["applied", "skipped", "already_consumed"]


def _next_seq(session: dict[str, Any]) -> int:
    raw = session.get(PENDING_BACKING_WORKFLOW_KEY)
    prev = int(raw.get("request_seq") or 0) if isinstance(raw, dict) else 0
    return prev + 1


def should_defer_backing_workflow_activation(session: dict[str, Any]) -> bool:
    try:
        from session_widget_safe import widgets_likely_instantiated

        return widgets_likely_instantiated(session)
    except ImportError:
        return bool(session.get("_streamlit_widgets_locked_this_run"))


def peek_pending_backing_workflow_handoff(session: dict[str, Any]) -> dict[str, Any] | None:
    raw = session.get(PENDING_BACKING_WORKFLOW_KEY)
    return copy.deepcopy(raw) if isinstance(raw, dict) else None


def clear_pending_backing_workflow_handoff(session: dict[str, Any]) -> None:
    session.pop(PENDING_BACKING_WORKFLOW_KEY, None)


def queue_pending_backing_workflow_handoff(
    session: dict[str, Any],
    *,
    backing_source: str,
    workflow_owner: str,
    activation_source: str = "open_backing_from_creative",
    persist_policy: str = "durable_handoff",
    page_route: str = "backing",
    return_route: str = "creative",
    navigation_intent: str = "backing_open",
    with_practice_lick: bool = False,
    navigation_callback: str = "_improv_open_backing",
    mission_alignment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Queue typed backing activation for the next pre-widget script run."""
    seq = _next_seq(session)
    align = copy.deepcopy(mission_alignment) if isinstance(mission_alignment, dict) else None
    align_fp = str((align or {}).get("alignment_fingerprint") or "")
    req = {
        "request_seq": seq,
        "backing_source": str(backing_source or "").strip(),
        "workflow_owner": str(workflow_owner or "").strip(),
        "activation_source": activation_source,
        "persist_policy": persist_policy,
        "page_route": page_route,
        "return_route": str(return_route or "creative").strip() or "creative",
        "navigation_intent": navigation_intent,
        "with_practice_lick": bool(with_practice_lick),
        "navigation_callback": navigation_callback,
        "mission_handoff": str(backing_source or "") == "mission",
        "mission_alignment": align,
        "alignment_fingerprint": align_fp,
    }
    session[PENDING_BACKING_WORKFLOW_KEY] = req
    session.pop(PENDING_BACKING_WORKFLOW_CONSUMED_SEQ_KEY, None)
    return req


def should_request_backing_handoff_rerun(session: dict[str, Any]) -> bool:
    pending = peek_pending_backing_workflow_handoff(session)
    if not pending:
        return False
    seq = pending.get("request_seq")
    if seq is None:
        return True
    if session.get(PENDING_BACKING_WORKFLOW_RERUN_SEQ_KEY) == seq:
        return False
    session[PENDING_BACKING_WORKFLOW_RERUN_SEQ_KEY] = seq
    return True


def backing_workflow_owner_is_active(session: dict[str, Any], owner: str) -> bool:
    return _owner_already_active(session, owner)


def backing_source_from_workflow_owner(owner: str) -> str:
    o = str(owner or "").strip()
    if o == "mission_jam":
        return "mission"
    if o == "song_based_improvisation":
        return "song_improv"
    if o == "regular_custom_backing":
        return "custom_progression"
    if o in {"style_jam", "jam_session_generator", "entry_jam"}:
        return "entry_jam"
    return "entry_jam"


def resolve_backing_workflow_owner(session: dict[str, Any], *, backing_source: str) -> str:
    source = str(backing_source or "").strip()
    if source == "mission":
        return "mission_jam"
    if source == "song_improv":
        return "song_based_improvisation"
    if source == "custom_progression":
        return "regular_custom_backing"
    if source == "entry_jam":
        try:
            from workflow_musical_authority import workflow_type_from_backing_source

            entry_mode = str(session.get("improv_entry_mode") or "").strip()
            try:
                from backing_source_navigation import _creative_handoff_entry_mode

                entry_mode = _creative_handoff_entry_mode(session)
            except ImportError:
                pass
            launch_wf = workflow_type_from_backing_source("entry_jam", entry_mode=entry_mode)
            if launch_wf in {"style_jam", "jam_session_generator"}:
                return launch_wf
            return "entry_jam"
        except ImportError:
            return "style_jam"
    return "regular_catalog_backing"


def _owner_already_active(session: dict[str, Any], owner: str) -> bool:
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        return bool(ptr and str(ptr.workflow_owner or "") == owner)
    except ImportError:
        return False


def consume_pending_backing_workflow_handoff(session: dict[str, Any], *, st: Any | None = None) -> ConsumePhase:
    """Apply queued workflow activation + backing navigation once, before widgets."""
    pending = session.get(PENDING_BACKING_WORKFLOW_KEY)
    if not isinstance(pending, dict):
        return "skipped"
    seq = pending.get("request_seq")
    align_fp = str(pending.get("alignment_fingerprint") or "")
    consumed = session.get(PENDING_BACKING_WORKFLOW_CONSUMED_SEQ_KEY)
    consumed_fp = session.get(PENDING_BACKING_WORKFLOW_CONSUMED_FP_KEY)
    if seq is not None and consumed == seq and (not align_fp or consumed_fp == align_fp):
        clear_pending_backing_workflow_handoff(session)
        return "already_consumed"

    owner = str(pending.get("workflow_owner") or "").strip()
    source = str(pending.get("backing_source") or "").strip()
    if not owner or not source:
        clear_pending_backing_workflow_handoff(session)
        return "skipped"

    activation_needed = not _owner_already_active(session, owner)
    if activation_needed:
        try:
            from music_workflow_activation import activate_workflow_simple

            result = activate_workflow_simple(
                session,
                owner,
                activation_source=str(pending.get("activation_source") or "pending_backing_consume"),
                page_route=str(pending.get("page_route") or "backing"),
                return_route=str(pending.get("return_route") or "creative"),
                navigation_intent=str(pending.get("navigation_intent") or "backing_open"),
                persist_policy=str(pending.get("persist_policy") or "durable_handoff"),  # type: ignore[arg-type]
            )
            if not result.ok:
                session["_music_pending_backing_consume_error"] = dict(getattr(result, "trace", {}) or {})
                return "skipped"
        except ImportError:
            return "skipped"

    alignment = pending.get("mission_alignment")
    if isinstance(alignment, dict) and str(pending.get("backing_source") or "") == "mission":
        try:
            from mission_backing_alignment import apply_pending_mission_backing_alignment

            apply_pending_mission_backing_alignment(session, alignment)
        except ImportError:
            pass

    try:
        from backing_context import open_backing_from_creative

        open_backing_from_creative(
            session,
            source=source,  # type: ignore[arg-type]
            st_like=st,
            skip_workflow_activation=True,
        )
    except TypeError:
        from backing_context import open_backing_from_creative

        open_backing_from_creative(session, source=source, st_like=st)  # type: ignore[arg-type]
    except ImportError:
        pass

    try:
        from backing_source_navigation import BACKING_INTENT_FROM_CREATIVE, set_backing_open_intent

        set_backing_open_intent(session, BACKING_INTENT_FROM_CREATIVE)
    except ImportError:
        pass

    if pending.get("with_practice_lick"):
        try:
            from mission_backing_handoff_persistence import arm_mission_backing_handoff_page_change

            arm_mission_backing_handoff_page_change(session)
        except ImportError:
            pass

    try:
        from studio_scroll_anchors import set_pending_anchor, ANCHOR_BACKING_MAIN_CONTROLS
        from studio_nav_state import navigate_studio_page

        set_pending_anchor(session, ANCHOR_BACKING_MAIN_CONTROLS)
        navigate_studio_page(session, "backing")
    except ImportError:
        session["studio_page"] = "backing"

    try:
        from mission_backing_handoff_persistence import complete_mission_backing_handoff_after_navigation

        complete_mission_backing_handoff_after_navigation(
            session,
            navigation_callback=str(pending.get("navigation_callback") or "_improv_open_backing"),
            backing_source=source,
        )
    except ImportError:
        pass

    if seq is not None:
        session[PENDING_BACKING_WORKFLOW_CONSUMED_SEQ_KEY] = seq
    if align_fp:
        session[PENDING_BACKING_WORKFLOW_CONSUMED_FP_KEY] = align_fp
    clear_pending_backing_workflow_handoff(session)
    return "applied"


__all__ = [
    "PENDING_BACKING_WORKFLOW_CONSUMED_FP_KEY",
    "PENDING_BACKING_WORKFLOW_CONSUMED_SEQ_KEY",
    "PENDING_BACKING_WORKFLOW_KEY",
    "backing_source_from_workflow_owner",
    "backing_workflow_owner_is_active",
    "consume_pending_backing_workflow_handoff",
    "peek_pending_backing_workflow_handoff",
    "queue_pending_backing_workflow_handoff",
    "resolve_backing_workflow_owner",
    "should_defer_backing_workflow_activation",
    "should_request_backing_handoff_rerun",
]

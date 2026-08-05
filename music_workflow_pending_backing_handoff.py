"""Pre-widget workflow activation for Creative → Backing handoffs (Mission / Jam)."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Literal

PENDING_BACKING_WORKFLOW_KEY = "_music_pending_backing_workflow_handoff"
PENDING_BACKING_WORKFLOW_CONSUMED_SEQ_KEY = "_music_pending_backing_workflow_consumed_seq"
PENDING_BACKING_WORKFLOW_CONSUMED_FP_KEY = "_music_pending_backing_workflow_consumed_fp"
PENDING_BACKING_WORKFLOW_CONSUMED_TOKEN_KEY = "_music_pending_backing_workflow_consumed_token"
PENDING_BACKING_WORKFLOW_RERUN_SEQ_KEY = "_music_pending_backing_workflow_rerun_for_seq"
PENDING_BACKING_WORKFLOW_RERUN_DIAG_KEY = "_music_pending_backing_workflow_rerun_diag"
PENDING_BACKING_HANDOFF_USER_MESSAGE_KEY = "_music_pending_backing_handoff_user_message"

ConsumePhase = Literal["applied", "skipped", "already_consumed"]


def _next_seq(session: dict[str, Any]) -> int:
    raw = session.get(PENDING_BACKING_WORKFLOW_KEY)
    prev = int(raw.get("request_seq") or 0) if isinstance(raw, dict) else 0
    return prev + 1


def should_defer_backing_workflow_activation(session: dict[str, Any]) -> bool:
    try:
        from creative_mission_config_persistence import CREATIVE_MISSION_WIDGETS_INSTANTIATED_KEY

        if session.get(CREATIVE_MISSION_WIDGETS_INSTANTIATED_KEY):
            return True
    except ImportError:
        pass
    try:
        from session_widget_safe import widgets_likely_instantiated

        return widgets_likely_instantiated(session)
    except ImportError:
        return bool(session.get("_streamlit_widgets_locked_this_run"))


def mission_backing_click_must_defer(session: dict[str, Any]) -> bool:
    """Mission Backing / Practice-in-Jam clicks never mutate workflow when True."""
    return should_defer_backing_workflow_activation(session)


def peek_pending_backing_workflow_handoff(session: dict[str, Any]) -> dict[str, Any] | None:
    raw = session.get(PENDING_BACKING_WORKFLOW_KEY)
    return copy.deepcopy(raw) if isinstance(raw, dict) else None


def clear_pending_backing_workflow_handoff(session: dict[str, Any]) -> None:
    session.pop(PENDING_BACKING_WORKFLOW_KEY, None)


def _consume_token(pending: dict[str, Any]) -> str:
    seq = pending.get("request_seq")
    align_fp = str(pending.get("alignment_fingerprint") or "")
    lick = int(bool(pending.get("with_practice_lick")))
    mode = str(pending.get("handoff_mode") or ("practice_in_jam" if lick else "mission_backing"))
    return f"{seq}:{align_fp}:lick={lick}:mode={mode}"


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
    lick = bool(with_practice_lick or (align or {}).get("with_practice_lick"))
    handoff_mode = "practice_in_jam" if lick else "mission_backing"
    backing_scope = str((align or {}).get("backing_scope") or "mission_chord")
    req = {
        "request_seq": seq,
        "backing_source": str(backing_source or "").strip(),
        "workflow_owner": str(workflow_owner or "").strip(),
        "activation_source": activation_source,
        "persist_policy": persist_policy,
        "page_route": page_route,
        "return_route": str(return_route or "creative").strip() or "creative",
        "navigation_intent": navigation_intent,
        "with_practice_lick": lick,
        "handoff_mode": handoff_mode,
        "backing_scope": backing_scope,
        "navigation_callback": navigation_callback,
        "mission_handoff": str(backing_source or "") == "mission",
        "mission_alignment": align,
        "alignment_fingerprint": align_fp,
    }
    req["consume_token"] = _consume_token(req)
    session[PENDING_BACKING_WORKFLOW_KEY] = req
    session.pop(PENDING_BACKING_WORKFLOW_CONSUMED_SEQ_KEY, None)
    session.pop(PENDING_BACKING_WORKFLOW_CONSUMED_TOKEN_KEY, None)
    session.pop(PENDING_BACKING_WORKFLOW_RERUN_DIAG_KEY, None)
    session.pop(PENDING_BACKING_HANDOFF_USER_MESSAGE_KEY, None)
    try:
        from music_mission_backing_handoff_trace import log_pending_queued

        log_pending_queued(session, req)
    except ImportError:
        pass
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


def build_backing_handoff_rerun_fingerprint(session: dict[str, Any], pending: dict[str, Any]) -> str:
    """Semantic rerun identity — new request_seq / consume_token always changes fingerprint."""
    parts = {
        "kind": "pending_backing_workflow_handoff",
        "request_seq": pending.get("request_seq"),
        "consume_token": str(pending.get("consume_token") or ""),
        "alignment_fingerprint": str(pending.get("alignment_fingerprint") or ""),
        "handoff_mode": str(pending.get("handoff_mode") or ""),
        "with_practice_lick": bool(pending.get("with_practice_lick")),
        "studio_page": str(session.get("studio_page") or ""),
    }
    blob = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def request_pending_backing_handoff_rerun(st_module: Any, session: dict[str, Any]) -> bool:
    """
    Request at most one guarded rerun per pending request_seq.
    Never calls bare st.rerun(); leaves pending retryable when guard rejects.
    """
    pending = peek_pending_backing_workflow_handoff(session)
    if not pending:
        return False
    seq = pending.get("request_seq")
    token = str(pending.get("consume_token") or "")
    if not should_request_backing_handoff_rerun(session):
        session[PENDING_BACKING_WORKFLOW_RERUN_DIAG_KEY] = {
            "status": "rerun_already_requested_for_seq",
            "request_seq": seq,
            "consume_token": token,
        }
        return False

    fp = build_backing_handoff_rerun_fingerprint(session, pending)
    rerun_sent = False
    block_status = "rerun_guard_rejected"
    try:
        from music_app_rerun import request_app_rerun

        rerun_sent = bool(
            request_app_rerun(
                st_module,
                session,
                reason="pending_backing_workflow_handoff",
                stage="mission_backing_pre_widget",
                fingerprint=fp,
            )
        )
    except ImportError:
        block_status = "music_app_rerun_unavailable"

    try:
        from music_mission_backing_handoff_trace import log_rerun_request

        log_rerun_request(
            session,
            allowed=rerun_sent,
            reason="pending_backing_workflow_handoff",
            fingerprint=fp,
        )
    except ImportError:
        pass

    if not rerun_sent:
        session[PENDING_BACKING_WORKFLOW_RERUN_DIAG_KEY] = {
            "status": block_status,
            "request_seq": seq,
            "consume_token": token,
            "fingerprint": fp,
        }
        session[PENDING_BACKING_HANDOFF_USER_MESSAGE_KEY] = (
            "Backing handoff is queued but navigation was paused to prevent a rerun loop. "
            "Refresh the page to continue, or try again."
        )
    return rerun_sent


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
        try:
            from music_mission_backing_handoff_trace import log_consume

            log_consume(session, phase="skipped", detail={"reason": "no_pending"})
        except ImportError:
            pass
        return "skipped"
    token = str(pending.get("consume_token") or _consume_token(pending))
    seq = pending.get("request_seq")
    if session.get(PENDING_BACKING_WORKFLOW_CONSUMED_TOKEN_KEY) == token or (
        seq is not None and session.get(PENDING_BACKING_WORKFLOW_CONSUMED_SEQ_KEY) == seq
    ):
        clear_pending_backing_workflow_handoff(session)
        try:
            from music_mission_backing_handoff_trace import log_consume

            log_consume(session, phase="already_consumed", detail={"token": token})
        except ImportError:
            pass
        return "already_consumed"

    align_fp = str(pending.get("alignment_fingerprint") or "")

    owner = str(pending.get("workflow_owner") or "").strip()
    source = str(pending.get("backing_source") or "").strip()
    if not owner or not source:
        clear_pending_backing_workflow_handoff(session)
        return "skipped"

    with_lick = bool(pending.get("with_practice_lick"))
    if with_lick:
        try:
            from mission_backing_handoff_persistence import (
                MISSION_BACKING_HANDOFF_ACTIVE_KEY,
                MISSION_BACKING_HANDOFF_DIAG_KEY,
            )
            from improvisation_missions import IMPROV_MISSION_PRACTICE_LICK_HANDOFF

            session[IMPROV_MISSION_PRACTICE_LICK_HANDOFF] = True
            session[MISSION_BACKING_HANDOFF_ACTIVE_KEY] = True
            diag = session.get(MISSION_BACKING_HANDOFF_DIAG_KEY)
            if not isinstance(diag, dict):
                diag = {}
                session[MISSION_BACKING_HANDOFF_DIAG_KEY] = diag
            diag.setdefault("with_practice_lick", True)
            diag.setdefault(
                "navigation_callback",
                str(pending.get("navigation_callback") or "_improv_open_backing"),
            )
        except ImportError:
            pass

    activation_needed = not _owner_already_active(session, owner)
    activation_ok = True
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
            activation_ok = bool(result.ok)
            if not activation_ok:
                session["_music_pending_backing_consume_error"] = dict(getattr(result, "trace", {}) or {})
        except ImportError:
            activation_ok = False
    try:
        from music_mission_backing_handoff_trace import log_consume

        log_consume(
            session,
            phase="activation",
            detail={
                "needed": activation_needed,
                "ok": activation_ok,
                "owner": owner,
                "with_practice_lick": with_lick,
            },
        )
    except ImportError:
        pass
    if activation_needed and not activation_ok:
        return "skipped"

    alignment_ok = True
    alignment = pending.get("mission_alignment")
    if isinstance(alignment, dict) and str(pending.get("backing_source") or "") == "mission":
        try:
            from mission_backing_alignment import apply_pending_mission_backing_alignment

            alignment_ok = bool(apply_pending_mission_backing_alignment(session, alignment))
        except ImportError:
            alignment_ok = False
    try:
        from music_mission_backing_handoff_trace import log_consume

        log_consume(session, phase="alignment", detail={"ok": alignment_ok})
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

    if with_lick:
        try:
            from mission_backing_handoff_persistence import arm_mission_backing_handoff_page_change

            arm_mission_backing_handoff_page_change(session)
        except ImportError:
            pass

    try:
        from studio_scroll_anchors import ANCHOR_BACKING_MAIN_CONTROLS, set_pending_anchor
        from studio_nav_history import navigate_studio_page

        set_pending_anchor(session, ANCHOR_BACKING_MAIN_CONTROLS)
        navigate_studio_page(session, "backing")
    except ImportError:
        session["studio_page"] = "backing"

    page_after = str(session.get("studio_page") or "").strip().lower()
    if page_after != "backing":
        session["_music_pending_backing_consume_error"] = {
            "reason": "navigation_incomplete",
            "studio_page": page_after,
            "token": token,
        }
        try:
            from music_mission_backing_handoff_trace import log_consume

            log_consume(session, phase="navigation_failed", detail={"studio_page": page_after})
        except ImportError:
            pass
        return "skipped"

    try:
        from mission_backing_handoff_persistence import complete_mission_backing_handoff_after_navigation

        complete_mission_backing_handoff_after_navigation(
            session,
            navigation_callback=str(pending.get("navigation_callback") or "_improv_open_backing"),
            backing_source=source,
        )
    except ImportError:
        pass

    try:
        from mission_return_destination import seal_mission_return_destination_from_handoff

        seal_mission_return_destination_from_handoff(session, pending)
    except ImportError:
        pass

    if seq is not None:
        session[PENDING_BACKING_WORKFLOW_CONSUMED_SEQ_KEY] = seq
    if align_fp:
        session[PENDING_BACKING_WORKFLOW_CONSUMED_FP_KEY] = align_fp
    session[PENDING_BACKING_WORKFLOW_CONSUMED_TOKEN_KEY] = token
    clear_pending_backing_workflow_handoff(session)
    try:
        from music_mission_backing_handoff_trace import log_consume

        log_consume(
            session,
            phase="applied",
            detail={
                "token": token,
                "with_practice_lick": with_lick,
                "studio_page": page_after,
            },
        )
    except ImportError:
        pass
    return "applied"


__all__ = [
    "PENDING_BACKING_HANDOFF_USER_MESSAGE_KEY",
    "PENDING_BACKING_WORKFLOW_CONSUMED_TOKEN_KEY",
    "PENDING_BACKING_WORKFLOW_CONSUMED_FP_KEY",
    "PENDING_BACKING_WORKFLOW_CONSUMED_SEQ_KEY",
    "PENDING_BACKING_WORKFLOW_KEY",
    "PENDING_BACKING_WORKFLOW_RERUN_DIAG_KEY",
    "backing_source_from_workflow_owner",
    "backing_workflow_owner_is_active",
    "build_backing_handoff_rerun_fingerprint",
    "consume_pending_backing_workflow_handoff",
    "mission_backing_click_must_defer",
    "peek_pending_backing_workflow_handoff",
    "queue_pending_backing_workflow_handoff",
    "request_pending_backing_handoff_rerun",
    "resolve_backing_workflow_owner",
    "should_defer_backing_workflow_activation",
    "should_request_backing_handoff_rerun",
]

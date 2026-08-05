"""Two-phase workflow activation when Streamlit widgets may already exist."""

from __future__ import annotations

from typing import Any, Literal

PENDING_WORKFLOW_ACTIVATION_KEY = "_music_pending_workflow_activation"
PENDING_WORKFLOW_ACTIVATION_SEQ_KEY = "_music_pending_workflow_activation_seq"
PENDING_WORKFLOW_ACTIVATION_CONSUMED_KEY = "_music_pending_workflow_activation_consumed"
PENDING_WORKFLOW_BLOCKED_KEYS_KEY = "_music_workflow_pending_blocked_restore_keys"

ActivationPhase = Literal["queued", "applied", "skipped"]


def _next_seq(session: dict[str, Any]) -> int:
    seq = int(session.get(PENDING_WORKFLOW_ACTIVATION_SEQ_KEY) or 0) + 1
    session[PENDING_WORKFLOW_ACTIVATION_SEQ_KEY] = seq
    return seq


def _dev_mode(session: dict[str, Any]) -> bool:
    try:
        import streamlit as st

        return bool(st.query_params.get("dev"))
    except Exception:
        return bool(session.get("_music_dev_mode"))


def queue_pending_workflow_activation(
    session: dict[str, Any],
    *,
    target_owner: str,
    target_session_id: str = "",
    activation_source: str = "unspecified",
    active_creative_view: str = "",
    navigation_intent: str = "",
    page_route: str = "",
    return_route: str = "",
) -> dict[str, Any]:
    """Record activation to run at pre-widget stage on the next script run."""
    owner = str(target_owner or "").strip()
    if not owner:
        return {"queued": False, "reason": "missing_owner"}
    req = {
        "target_owner": owner,
        "target_session_id": str(target_session_id or "").strip(),
        "activation_source": str(activation_source or "unspecified"),
        "active_creative_view": str(active_creative_view or "").strip(),
        "navigation_intent": str(navigation_intent or "").strip(),
        "page_route": str(page_route or "").strip(),
        "return_route": str(return_route or "").strip(),
        "request_seq": _next_seq(session),
    }
    session[PENDING_WORKFLOW_ACTIVATION_KEY] = req
    session.pop(PENDING_WORKFLOW_ACTIVATION_CONSUMED_KEY, None)
    if _dev_mode(session):
        session["_music_workflow_pending_activation_diag"] = {"queued": True, **req}
    return {"queued": True, **req}


def peek_pending_workflow_activation(session: dict[str, Any]) -> dict[str, Any] | None:
    raw = session.get(PENDING_WORKFLOW_ACTIVATION_KEY)
    return raw if isinstance(raw, dict) else None


def clear_pending_workflow_activation(session: dict[str, Any]) -> None:
    session.pop(PENDING_WORKFLOW_ACTIVATION_KEY, None)


def consume_pending_workflow_activation(session: dict[str, Any]) -> ActivationPhase:
    """Apply queued activation once, before sidebar / Creative widgets."""
    pending = peek_pending_workflow_activation(session)
    if not pending:
        return "skipped"
    if session.get(PENDING_WORKFLOW_ACTIVATION_CONSUMED_KEY) == pending.get("request_seq"):
        clear_pending_workflow_activation(session)
        return "skipped"
    try:
        from music_workflow_activation import ActivateWorkflowRequest, activate_workflow
        from music_workflow_compatibility import legacy_session_id_for_owner

        owner = str(pending.get("target_owner") or "").strip()
        sid = str(pending.get("target_session_id") or "").strip() or legacy_session_id_for_owner(session, owner)
        result = activate_workflow(
            session,
            ActivateWorkflowRequest(
                target_owner=owner,
                target_session_id=sid,
                activation_source=str(pending.get("activation_source") or "pending_consume"),
                navigation_intent=str(pending.get("navigation_intent") or ""),
                active_creative_view=str(pending.get("active_creative_view") or ""),
                page_route=str(pending.get("page_route") or ""),
                return_route=str(pending.get("return_route") or ""),
            ),
        )
        if result.ok:
            session[PENDING_WORKFLOW_ACTIVATION_CONSUMED_KEY] = pending.get("request_seq")
            clear_pending_workflow_activation(session)
            if _dev_mode(session):
                session["_music_workflow_pending_activation_diag"] = {
                    "applied": True,
                    "request_seq": pending.get("request_seq"),
                    "owner": owner,
                }
            return "applied"
        if _dev_mode(session):
            session["_music_workflow_pending_activation_diag"] = {
                "failed": True,
                "error": result.error_code,
                "request_seq": pending.get("request_seq"),
            }
        return "skipped"
    except ImportError:
        return "skipped"


def request_or_activate_workflow(
    session: dict[str, Any],
    *,
    target_owner: str,
    target_session_id: str = "",
    activation_source: str = "unspecified",
    active_creative_view: str = "",
    navigation_intent: str = "",
    page_route: str = "",
    return_route: str = "",
) -> Literal["done", "queued", "failed"]:
    """Activate now when pre-widget; otherwise queue for next run."""
    try:
        from session_widget_safe import widgets_likely_instantiated
    except ImportError:

        def widgets_likely_instantiated(_session: dict[str, Any]) -> bool:  # type: ignore[misc]
            return bool(_session.get("_streamlit_widgets_locked_this_run"))

    if widgets_likely_instantiated(session):
        queue_pending_workflow_activation(
            session,
            target_owner=target_owner,
            target_session_id=target_session_id,
            activation_source=activation_source,
            active_creative_view=active_creative_view,
            navigation_intent=navigation_intent,
            page_route=page_route,
            return_route=return_route,
        )
        return "queued"
    try:
        from music_workflow_activation import ActivateWorkflowRequest, activate_workflow
        from music_workflow_compatibility import legacy_session_id_for_owner

        owner = str(target_owner or "").strip()
        sid = str(target_session_id or "").strip() or legacy_session_id_for_owner(session, owner)
        result = activate_workflow(
            session,
            ActivateWorkflowRequest(
                target_owner=owner,
                target_session_id=sid,
                activation_source=activation_source,
                navigation_intent=navigation_intent,
                active_creative_view=active_creative_view,
                page_route=page_route,
                return_route=return_route,
            ),
        )
        return "done" if result.ok else "failed"
    except ImportError:
        try:
            from workflow_musical_authority import switch_workflow_owner

            switch_workflow_owner(session, target_owner)  # type: ignore[arg-type]
            return "done"
        except ImportError:
            return "failed"


__all__ = [
    "PENDING_WORKFLOW_ACTIVATION_KEY",
    "consume_pending_workflow_activation",
    "peek_pending_workflow_activation",
    "queue_pending_workflow_activation",
    "request_or_activate_workflow",
]

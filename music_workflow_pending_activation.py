"""Two-phase workflow activation when Streamlit widgets may already exist."""

from __future__ import annotations

from typing import Any, Literal

PENDING_WORKFLOW_ACTIVATION_KEY = "_music_pending_workflow_activation"
PENDING_WORKFLOW_ACTIVATION_SEQ_KEY = "_music_pending_workflow_activation_seq"
PENDING_WORKFLOW_ACTIVATION_CONSUMED_KEY = "_music_pending_workflow_activation_consumed"
PENDING_WORKFLOW_BLOCKED_KEYS_KEY = "_music_workflow_pending_blocked_restore_keys"

ENTRY_MODE_TO_OWNER: dict[str, str] = {
    "Song-Based Improvisation": "song_based_improvisation",
    "Style Jam Mode": "style_jam",
    "Jam Session Generator": "jam_session_generator",
}

ActivationPhase = Literal["queued", "applied", "skipped"]


def owner_for_improv_entry_mode(entry: str) -> str:
    return str(ENTRY_MODE_TO_OWNER.get(str(entry or "").strip()) or "").strip()


def _pending_dedupe_token(owner: str, session_id: str, *, entry_mode: str = "") -> str:
    return f"{owner}:{session_id}:{entry_mode}"


def sync_creative_entry_selectors_from_active_blob(session: dict[str, Any]) -> None:
    """Align Entry & Jam widget keys with the active workflow blob (pre-widget safe)."""
    try:
        from music_theory import key_center_token
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob
    except ImportError:
        return
    ptr = get_active_workflow_pointer(session)
    if ptr is None:
        return
    blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
    if blob is None:
        return
    token = key_center_token(
        str(blob.keys.practice_tonic or "C"),
        str(blob.keys.practice_mode or "major"),
    )
    owner = str(ptr.workflow_owner or "")
    if owner == "style_jam":
        session["improv_style_key"] = token
    elif owner == "jam_session_generator":
        session["improv_jam_key"] = token


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
    try:
        from music_workflow_compatibility import legacy_session_id_for_owner

        resolved_sid = str(target_session_id or "").strip() or legacy_session_id_for_owner(session, owner)
    except ImportError:
        resolved_sid = str(target_session_id or "").strip()
    entry_mode = str(session.get("improv_entry_mode") or "").strip() if navigation_intent == "creative_entry" else ""
    dedupe = _pending_dedupe_token(owner, resolved_sid, entry_mode=entry_mode)
    existing = peek_pending_workflow_activation(session)
    if isinstance(existing, dict) and str(existing.get("target_owner") or "") == owner:
        if str(existing.get("dedupe_token") or "") == dedupe:
            merged = {**existing}
            merged.update(
                {
                    "activation_source": str(activation_source or existing.get("activation_source") or "unspecified"),
                    "active_creative_view": str(active_creative_view or existing.get("active_creative_view") or ""),
                    "navigation_intent": str(navigation_intent or existing.get("navigation_intent") or ""),
                    "page_route": str(page_route or existing.get("page_route") or ""),
                    "return_route": str(return_route or existing.get("return_route") or ""),
                    "target_session_id": resolved_sid,
                    "entry_mode": entry_mode or existing.get("entry_mode") or "",
                    "dedupe_token": dedupe,
                }
            )
            session[PENDING_WORKFLOW_ACTIVATION_KEY] = merged
            session.pop(PENDING_WORKFLOW_ACTIVATION_CONSUMED_KEY, None)
            if _dev_mode(session):
                session["_music_workflow_pending_activation_diag"] = {"deduped": True, **merged}
            return {"queued": True, "deduped": True, **merged}
    req = {
        "target_owner": owner,
        "target_session_id": resolved_sid,
        "activation_source": str(activation_source or "unspecified"),
        "active_creative_view": str(active_creative_view or "").strip(),
        "navigation_intent": str(navigation_intent or "").strip(),
        "page_route": str(page_route or "").strip(),
        "return_route": str(return_route or "").strip(),
        "entry_mode": entry_mode,
        "dedupe_token": dedupe,
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
            sync_creative_entry_selectors_from_active_blob(session)
            try:
                from generated_jam_key_change import clear_generated_key_hydrate_guard

                clear_generated_key_hydrate_guard(session)
            except ImportError:
                pass
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


def queue_workflow_activation_for_entry_mode(session: dict[str, Any]) -> dict[str, Any]:
    """Capture Entry-mode radio intent — consumed pre-widget on the next run."""
    try:
        from generated_jam_key_change import clear_generated_key_hydrate_guard
        from music_workflow_pending_generated_key_edit import PENDING_GENERATED_KEY_EDIT_KEY

        session.pop(PENDING_GENERATED_KEY_EDIT_KEY, None)
        clear_generated_key_hydrate_guard(session)
    except ImportError:
        pass
    entry = str(session.get("improv_entry_mode") or "").strip()
    owner = owner_for_improv_entry_mode(entry)
    if not owner:
        return {"queued": False, "reason": "unknown_entry_mode", "entry_mode": entry}
    return queue_pending_workflow_activation(
        session,
        target_owner=owner,
        activation_source="entry_mode_change",
        navigation_intent="creative_entry",
        active_creative_view="Entry & Jam",
    )


__all__ = [
    "ENTRY_MODE_TO_OWNER",
    "PENDING_WORKFLOW_ACTIVATION_KEY",
    "consume_pending_workflow_activation",
    "owner_for_improv_entry_mode",
    "peek_pending_workflow_activation",
    "queue_pending_workflow_activation",
    "queue_workflow_activation_for_entry_mode",
    "request_or_activate_workflow",
    "sync_creative_entry_selectors_from_active_blob",
]

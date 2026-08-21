"""Orchestrate Mission envelope reconciliation before deferred Mission backing handoffs."""

from __future__ import annotations

import hashlib
import json
from typing import Any

ORCHESTRATED_MISSION_BACKING_RERUN_SEQ_KEY = "_music_orchestrated_mission_backing_rerun_seq"
MISSION_EXPLICIT_HANDOFF_ENVELOPE_DIAG_KEY = "_mission_explicit_handoff_envelope_diag"


def _sync_reconcile_mission_envelope_for_explicit_handoff(
    session: dict[str, Any],
    *,
    mission_alignment: dict[str, Any] | None,
) -> dict[str, Any]:
    """Reconcile Mission envelope pre-widget so explicit Backing clicks are not stuck syncing."""
    diag: dict[str, Any] = {}
    try:
        from music_workflow_pending_mission_envelope import ensure_mission_envelope_reconciliation_before_widgets

        diag["ensure"] = ensure_mission_envelope_reconciliation_before_widgets(session)
    except ImportError:
        diag["ensure"] = "skipped"
    if isinstance(mission_alignment, dict) and mission_alignment:
        try:
            from mission_backing_alignment import apply_pending_mission_backing_alignment

            diag["alignment_applied"] = bool(
                apply_pending_mission_backing_alignment(session, mission_alignment)
            )
        except ImportError:
            diag["alignment_applied"] = False
        try:
            from active_musical_workflow_envelope import apply_mission_workflow_envelope_reconciliation

            apply_mission_workflow_envelope_reconciliation(session)
        except ImportError:
            pass
    try:
        from generated_jam_key_context import (
            deactivate_generated_jam_key_ownership,
            generated_jam_owns_practice_key,
        )

        if generated_jam_owns_practice_key(session):
            diag["released_jam_key"] = bool(
                deactivate_generated_jam_key_ownership(session, pre_widget=True)
            )
    except ImportError:
        pass
    try:
        from active_musical_workflow_envelope import validate_mission_workflow_envelope

        validation = validate_mission_workflow_envelope(session)
        diag["consistent"] = bool(validation.get("consistent"))
        diag["violations"] = list(validation.get("violations") or [])
    except ImportError:
        diag["consistent"] = None
    session[MISSION_EXPLICIT_HANDOFF_ENVELOPE_DIAG_KEY] = diag
    return diag


def mission_envelope_reconciliation_required(session: dict[str, Any]) -> bool:
    if str(session.get("studio_page") or "").strip().lower() != "creative":
        return False
    try:
        from music_workflow_pending_mission_envelope import missions_envelope_reconciliation_target

        if not missions_envelope_reconciliation_target(session):
            return False
    except ImportError:
        tab = str(session.get("improv_intelligence_tab") or "").strip()
        if tab != "Missions":
            return False
    try:
        from generated_jam_key_context import generated_jam_owns_practice_key

        if generated_jam_owns_practice_key(session):
            return True
    except ImportError:
        pass
    try:
        from active_musical_workflow_envelope import validate_mission_workflow_envelope

        return not bool(validate_mission_workflow_envelope(session).get("consistent"))
    except ImportError:
        return False


def _orchestration_fingerprint(session: dict[str, Any]) -> str:
    try:
        from music_workflow_pending_backing_handoff import peek_pending_backing_workflow_handoff
        from music_workflow_pending_mission_envelope import peek_pending_mission_envelope_reconciliation

        backing = peek_pending_backing_workflow_handoff(session) or {}
        envelope = peek_pending_mission_envelope_reconciliation(session) or {}
    except ImportError:
        backing = {}
        envelope = {}
    blob = json.dumps(
        {
            "kind": "mission_envelope_then_backing",
            "backing_seq": backing.get("request_seq"),
            "backing_token": str(backing.get("consume_token") or ""),
            "envelope_seq": envelope.get("request_seq"),
            "waiting": bool(backing.get("waiting_for_mission_envelope")),
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def request_orchestrated_mission_backing_rerun(st_module: Any, session: dict[str, Any]) -> bool:
    """One guarded rerun for envelope prerequisite + deferred backing intent."""
    try:
        from music_workflow_pending_backing_handoff import peek_pending_backing_workflow_handoff

        backing = peek_pending_backing_workflow_handoff(session)
    except ImportError:
        return False
    if not backing or not backing.get("waiting_for_mission_envelope"):
        return False
    orch_seq = backing.get("request_seq")
    if orch_seq is not None and session.get(ORCHESTRATED_MISSION_BACKING_RERUN_SEQ_KEY) == orch_seq:
        return False
    fp = _orchestration_fingerprint(session)
    try:
        from music_app_rerun import request_app_rerun

        sent = bool(
            request_app_rerun(
                st_module,
                session,
                reason="mission_envelope_then_backing_handoff",
                stage="mission_backing_orchestrated_pre_widget",
                fingerprint=fp,
            )
        )
    except ImportError:
        return False
    if sent and orch_seq is not None:
        session[ORCHESTRATED_MISSION_BACKING_RERUN_SEQ_KEY] = orch_seq
    if not sent:
        try:
            from music_workflow_pending_backing_handoff import PENDING_BACKING_HANDOFF_USER_MESSAGE_KEY

            session[PENDING_BACKING_HANDOFF_USER_MESSAGE_KEY] = (
                "Mission backing is queued but navigation paused to prevent a rerun loop. Refresh once to continue."
            )
        except ImportError:
            pass
    return sent


def prepare_deferred_mission_backing_handoff(
    st_module: Any,
    session: dict[str, Any],
    *,
    backing_source: str,
    workflow_owner: str,
    with_practice_lick: bool,
    mission_alignment: dict[str, Any] | None,
    return_route: str = "creative",
) -> bool:
    """Queue backing (and envelope prerequisite if needed); request one rerun."""
    explicit_handoff = isinstance(mission_alignment, dict) and bool(mission_alignment)
    if explicit_handoff:
        _sync_reconcile_mission_envelope_for_explicit_handoff(
            session,
            mission_alignment=mission_alignment,
        )
    env_needed = mission_envelope_reconciliation_required(session)
    # Explicit Mission Backing click must open in this pre-widget pass when possible.
    if env_needed and explicit_handoff:
        session["_mission_backing_envelope_defer_overridden"] = True
        env_needed = False
    if env_needed:
        try:
            from music_workflow_pending_mission_envelope import (
                peek_pending_mission_envelope_reconciliation,
                queue_pending_mission_envelope_reconciliation,
            )

            if not peek_pending_mission_envelope_reconciliation(session):
                queue_pending_mission_envelope_reconciliation(
                    session,
                    reason="backing_handoff_prerequisite",
                    violations=[],
                )
        except ImportError:
            env_needed = False

    try:
        from music_workflow_pending_backing_handoff import (
            PENDING_BACKING_HANDOFF_USER_MESSAGE_KEY,
            queue_pending_backing_workflow_handoff,
        )

        queue_pending_backing_workflow_handoff(
            session,
            backing_source=backing_source,
            workflow_owner=workflow_owner,
            with_practice_lick=with_practice_lick,
            mission_alignment=mission_alignment,
            return_route=return_route,
            waiting_for_mission_envelope=env_needed,
        )
        if env_needed:
            rerun_sent = request_orchestrated_mission_backing_rerun(st_module, session)
            if not rerun_sent:
                session.pop(PENDING_BACKING_HANDOFF_USER_MESSAGE_KEY, None)
            return True
        try:
            from music_workflow_pending_backing_handoff import arm_pending_backing_handoff_consume

            arm_pending_backing_handoff_consume(session)
        except ImportError:
            pass
        session.pop(PENDING_BACKING_HANDOFF_USER_MESSAGE_KEY, None)
        return True
    except ImportError:
        return False


def try_finalize_backing_after_mission_envelope(session: dict[str, Any]) -> bool:
    """After envelope reconcile, arm and allow backing consume for waiting requests."""
    try:
        from music_workflow_pending_backing_handoff import (
            PENDING_BACKING_WORKFLOW_CONSUME_ARMED_SEQ_KEY,
            PENDING_BACKING_WORKFLOW_KEY,
            arm_pending_backing_handoff_consume,
            peek_pending_backing_workflow_handoff,
        )
    except ImportError:
        return False
    pending = peek_pending_backing_workflow_handoff(session)
    if not isinstance(pending, dict) or not pending.get("waiting_for_mission_envelope"):
        return False
    try:
        from music_workflow_pending_mission_envelope import peek_pending_mission_envelope_reconciliation

        if peek_pending_mission_envelope_reconciliation(session):
            return False
    except ImportError:
        pass
    pending = dict(pending)
    pending["waiting_for_mission_envelope"] = False
    session[PENDING_BACKING_WORKFLOW_KEY] = pending
    req_seq = pending.get("request_seq")
    if req_seq is not None:
        session[PENDING_BACKING_WORKFLOW_CONSUME_ARMED_SEQ_KEY] = req_seq
    return arm_pending_backing_handoff_consume(session)


def run_pre_widget_mission_handoff_consumers(session: dict[str, Any], *, st: Any | None = None) -> dict[str, str]:
    """Mission backing click intent, envelope reconciliation, then deferred backing handoff."""
    phases: dict[str, str] = {}
    try:
        from music_workflow_mission_backing_click import apply_mission_backing_click_intent, peek_mission_backing_click_intent

        if peek_mission_backing_click_intent(session):
            applied = apply_mission_backing_click_intent(session, st_module=st)
            phases["mission_backing_click_intent"] = "applied" if applied else "failed"
    except ImportError:
        phases["mission_backing_click_intent"] = "skipped"
    try:
        from music_workflow_pending_mission_return import consume_pending_mission_return_handoff

        phases["mission_return"] = str(consume_pending_mission_return_handoff(session, st=st))
    except ImportError:
        phases["mission_return"] = "skipped"
    try:
        from music_workflow_pending_mission_envelope import consume_pending_mission_envelope_reconciliation

        phases["mission_envelope"] = str(consume_pending_mission_envelope_reconciliation(session, st=st))
    except ImportError:
        phases["mission_envelope"] = "skipped"
    if try_finalize_backing_after_mission_envelope(session):
        phases["backing_armed_after_envelope"] = "yes"
    try:
        from music_workflow_pending_backing_handoff import consume_pending_backing_workflow_handoff

        phases["backing_handoff"] = str(consume_pending_backing_workflow_handoff(session, st=st))
    except ImportError:
        phases["backing_handoff"] = "skipped"
    return phases


__all__ = [
    "ORCHESTRATED_MISSION_BACKING_RERUN_SEQ_KEY",
    "mission_envelope_reconciliation_required",
    "prepare_deferred_mission_backing_handoff",
    "request_orchestrated_mission_backing_rerun",
    "run_pre_widget_mission_handoff_consumers",
    "try_finalize_backing_after_mission_envelope",
]

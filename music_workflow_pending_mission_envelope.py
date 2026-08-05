"""Pre-widget mission workflow envelope reconciliation (generated-jam key release)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

PENDING_MISSION_ENVELOPE_KEY = "_music_pending_mission_envelope_reconciliation"
PENDING_MISSION_ENVELOPE_SEQ_KEY = "_music_pending_mission_envelope_seq"
PENDING_MISSION_ENVELOPE_CONSUMED_SEQ_KEY = "_music_pending_mission_envelope_consumed_seq"
PENDING_MISSION_ENVELOPE_RERUN_SEQ_KEY = "_music_pending_mission_envelope_rerun_for_seq"

ConsumePhase = Literal["applied", "skipped", "already_consumed"]


def _next_seq(session: dict[str, Any]) -> int:
    seq = int(session.get(PENDING_MISSION_ENVELOPE_SEQ_KEY) or 0) + 1
    session[PENDING_MISSION_ENVELOPE_SEQ_KEY] = seq
    return seq


def peek_pending_mission_envelope_reconciliation(session: dict[str, Any]) -> dict[str, Any] | None:
    raw = session.get(PENDING_MISSION_ENVELOPE_KEY)
    return dict(raw) if isinstance(raw, dict) else None


def clear_pending_mission_envelope_reconciliation(session: dict[str, Any]) -> None:
    session.pop(PENDING_MISSION_ENVELOPE_KEY, None)


def queue_pending_mission_envelope_reconciliation(
    session: dict[str, Any],
    *,
    reason: str,
    violations: list[str] | None = None,
) -> dict[str, Any]:
    seq = _next_seq(session)
    viol = list(violations or [])
    req = {
        "kind": "mission_envelope_reconciliation",
        "reason": str(reason or "unspecified"),
        "violations": viol,
        "request_seq": seq,
        "consume_token": hashlib.sha256(json.dumps({"seq": seq, "v": viol}, sort_keys=True).encode()).hexdigest()[:16],
    }
    session[PENDING_MISSION_ENVELOPE_KEY] = req
    session.pop(PENDING_MISSION_ENVELOPE_CONSUMED_SEQ_KEY, None)
    return req


def should_request_mission_envelope_rerun(session: dict[str, Any]) -> bool:
    pending = peek_pending_mission_envelope_reconciliation(session)
    if not pending:
        return False
    seq = pending.get("request_seq")
    if seq is None:
        return True
    if session.get(PENDING_MISSION_ENVELOPE_RERUN_SEQ_KEY) == seq:
        return False
    session[PENDING_MISSION_ENVELOPE_RERUN_SEQ_KEY] = seq
    return True


def request_pending_mission_envelope_rerun(st_module: Any, session: dict[str, Any]) -> bool:
    pending = peek_pending_mission_envelope_reconciliation(session)
    if not pending or not should_request_mission_envelope_rerun(session):
        return False
    fp = str(pending.get("consume_token") or "")
    try:
        from music_app_rerun import request_app_rerun

        return bool(
            request_app_rerun(
                st_module,
                session,
                reason="pending_mission_envelope_reconciliation",
                stage="mission_envelope_pre_widget",
                fingerprint=fp,
            )
        )
    except ImportError:
        return False


def missions_envelope_reconciliation_target(session: dict[str, Any]) -> bool:
    tab = str(session.get("improv_intelligence_tab") or "").strip()
    if tab == "Missions":
        return True
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        return bool(ptr and str(ptr.workflow_owner or "") == "mission_jam")
    except ImportError:
        return False


def ensure_mission_envelope_reconciliation_before_widgets(session: dict[str, Any]) -> str:
    """Apply reconciliation before Creative/Mission widgets when validation fails."""
    if str(session.get("studio_page") or "").strip().lower() != "creative":
        return "skipped"
    if not missions_envelope_reconciliation_target(session):
        return "skipped"
    try:
        from session_widget_safe import widgets_likely_instantiated

        if widgets_likely_instantiated(session):
            return "skipped"
    except ImportError:
        pass
    pending = peek_pending_mission_envelope_reconciliation(session)
    released_jam = False
    try:
        from active_musical_workflow_envelope import (
            apply_mission_workflow_envelope_reconciliation,
            validate_mission_workflow_envelope,
        )
        from generated_jam_key_context import deactivate_generated_jam_key_ownership, generated_jam_owns_practice_key

        if generated_jam_owns_practice_key(session):
            released_jam = bool(deactivate_generated_jam_key_ownership(session, pre_widget=True))

        if pending:
            apply_mission_workflow_envelope_reconciliation(session)
            seq = pending.get("request_seq")
            if seq is not None:
                session[PENDING_MISSION_ENVELOPE_CONSUMED_SEQ_KEY] = seq
            clear_pending_mission_envelope_reconciliation(session)
            return "applied_pending"
        diag = validate_mission_workflow_envelope(session)
        if diag.get("consistent"):
            return "applied" if released_jam else "skipped"
        apply_mission_workflow_envelope_reconciliation(session)
        return "applied"
    except ImportError:
        return "skipped"


def consume_pending_mission_envelope_reconciliation(session: dict[str, Any], *, st: Any | None = None) -> ConsumePhase:
    """Early bootstrap consumer — runs before studio page routing when creative."""
    pending = peek_pending_mission_envelope_reconciliation(session)
    if not pending:
        return "skipped"
    seq = pending.get("request_seq")
    if seq is not None and session.get(PENDING_MISSION_ENVELOPE_CONSUMED_SEQ_KEY) == seq:
        clear_pending_mission_envelope_reconciliation(session)
        return "already_consumed"
    page = str(session.get("studio_page") or "").strip().lower()
    if page != "creative":
        return "skipped"
    try:
        from session_widget_safe import widgets_likely_instantiated

        if widgets_likely_instantiated(session):
            return "skipped"
    except ImportError:
        pass
    status = ensure_mission_envelope_reconciliation_before_widgets(session)
    if status in {"applied", "applied_pending"}:
        return "applied"
    return "skipped"


__all__ = [
    "PENDING_MISSION_ENVELOPE_KEY",
    "clear_pending_mission_envelope_reconciliation",
    "consume_pending_mission_envelope_reconciliation",
    "ensure_mission_envelope_reconciliation_before_widgets",
    "missions_envelope_reconciliation_target",
    "peek_pending_mission_envelope_reconciliation",
    "queue_pending_mission_envelope_reconciliation",
    "request_pending_mission_envelope_rerun",
]

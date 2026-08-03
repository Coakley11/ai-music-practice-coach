"""Phase 1 Item 8 — optimistic concurrency for music workspace cloud writes."""

from __future__ import annotations

import copy
from typing import Any

ITEM8_DIAG_KEY = "_phase1_item8_stale_write_diag"
ITEM8_VIOLATIONS_KEY = "_phase1_item8_stale_write_violations"
STALE_WRITE_USER_MESSAGE = (
    "This workspace changed on another device. Refresh to load the latest version before saving."
)

VIOLATION_STALE_DEVICE_WRITE_NOT_BLOCKED = "STALE_DEVICE_WRITE_NOT_BLOCKED"
VIOLATION_REVISION_REUSED = "REVISION_REUSED_WITH_DIFFERENT_PAYLOAD"
VIOLATION_ZERO_ROWS_NOT_CONFLICT = "CONDITIONAL_WRITE_ZERO_ROWS_NOT_TREATED_AS_CONFLICT"
VIOLATION_CONFLICT_REPORTED_CONFIRMED = "CONFLICT_WRITE_REPORTED_CONFIRMED"
VIOLATION_STALE_WRITE_CLEARED_DIRTY = "STALE_WRITE_CLEARED_DIRTY_STATE"
VIOLATION_UNCONDITIONAL_UPSERT_AFTER_CONFLICT = "UNCONDITIONAL_UPSERT_AFTER_CONFLICT"


def device_applied_revision(session: dict[str, Any]) -> int:
    try:
        from workspace_revision import APPLIED_REVISION_KEY

        return int(session.get(APPLIED_REVISION_KEY) or 0)
    except (TypeError, ValueError):
        return 0


def authoritative_cloud_revision(session: dict[str, Any]) -> int:
    try:
        from workspace_revision import CLOUD_REVISION_KEY, LAST_CONFIRMED_REVISION_KEY

        for key in (CLOUD_REVISION_KEY, LAST_CONFIRMED_REVISION_KEY, "_suite_cloud_workspace_revision"):
            try:
                v = int(session.get(key) or 0)
            except (TypeError, ValueError):
                v = 0
            if v > 0:
                return v
    except ImportError:
        pass
    return 0


def candidate_revision_from_state(state: dict[str, Any]) -> int:
    try:
        from workspace_revision import workspace_revision_from_blob

        return int(workspace_revision_from_blob(state))
    except (TypeError, ValueError):
        return 0


def prepare_music_conditional_write(
    session: dict[str, Any] | None,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Pre-flight for music CAS cloud write. Does not mutate cloud."""
    ss = session if isinstance(session, dict) else {}
    applied = device_applied_revision(ss)
    candidate = candidate_revision_from_state(state)
    cloud_rev = authoritative_cloud_revision(ss)
    violations: list[str] = []

    if candidate <= applied:
        violations.append(VIOLATION_REVISION_REUSED)

    out: dict[str, Any] = {
        "device_applied_revision": applied,
        "precondition_expected_revision": applied,
        "authoritative_revision_before_write": cloud_rev,
        "candidate_revision": candidate,
        "cloud_revision_newer_than_applied": cloud_rev > applied if cloud_rev else None,
        "blocked_precheck": bool(violations),
        "violations_precheck": violations,
    }
    return out


def record_conditional_write_result(
    session: dict[str, Any],
    *,
    prep: dict[str, Any],
    cas: dict[str, Any],
    saved: bool,
) -> dict[str, Any]:
    """Record Item 8 diagnostics; set conflict flags when CAS rejects."""
    violations: list[str] = list(prep.get("violations_precheck") or [])
    rows = int(cas.get("rows_affected") or 0)
    accepted = bool(cas.get("accepted"))
    write_mode = str(cas.get("write_mode") or "")
    unconditional = bool(cas.get("unconditional_upsert_attempted"))
    stale_blocked = not accepted and write_mode in ("conflict", "conflict_precheck")

    if not accepted and rows == 0 and write_mode == "conditional_patch" and not prep.get("blocked_precheck"):
        pass  # expected conflict
    if unconditional:
        violations.append(VIOLATION_UNCONDITIONAL_UPSERT_AFTER_CONFLICT)
    if saved and stale_blocked:
        violations.append(VIOLATION_CONFLICT_REPORTED_CONFIRMED)
    if not accepted and not stale_blocked and rows == 0 and not prep.get("blocked_precheck"):
        violations.append(VIOLATION_ZERO_ROWS_NOT_CONFLICT)

    session["_suite_workspace_conflict_detected"] = stale_blocked or bool(violations)
    session["_suite_workspace_conflict_resolution"] = (
        "stale_write_blocked" if stale_blocked else ("accepted" if accepted else "rejected")
    )
    session["_music_stale_write_blocked"] = stale_blocked
    session["stale_write_blocked"] = stale_blocked

    diag: dict[str, Any] = {
        "device_applied_revision": prep.get("device_applied_revision"),
        "candidate_revision": prep.get("candidate_revision"),
        "precondition_expected_revision": prep.get("precondition_expected_revision"),
        "authoritative_revision_before_write": prep.get("authoritative_revision_before_write"),
        "cloud_revision_newer_than_applied": prep.get("cloud_revision_newer_than_applied"),
        "conditional_write_attempted": bool(cas.get("conditional_write_attempted")),
        "conditional_write_rows_affected": rows,
        "conflict_detected": stale_blocked,
        "stale_write_blocked": stale_blocked,
        "unconditional_upsert_attempted": unconditional,
        "cloud_write_succeeded": accepted,
        "write_mode": write_mode,
        "cas_reason": cas.get("reason"),
    }
    session[ITEM8_DIAG_KEY] = diag
    session[ITEM8_VIOLATIONS_KEY] = violations

    if stale_blocked or not accepted:
        try:
            from workspace_revision import (
                PENDING_CANONICAL_FP_KEY,
                RESERVED_WRITE_REVISION_KEY,
            )

            session.pop(RESERVED_WRITE_REVISION_KEY, None)
            session.pop(PENDING_CANONICAL_FP_KEY, None)
            session.pop("_music_pending_save_revision", None)
        except ImportError:
            pass

    return diag


def fetch_latest_network_revision_evidence(st: Any, app_id: str = "music") -> dict[str, Any]:
    """Network fetch for Item 8 diagnostics only — does not apply payload to session."""
    ss = st.session_state
    evidence: dict[str, Any] = {"fetch_attempted": True}
    try:
        from suite_cloud_state import load_cloud_full_session
        from workspace_revision import workspace_revision_from_blob

        payload, ts = load_cloud_full_session(app_id, force=True)
        rev = workspace_revision_from_blob(payload if isinstance(payload, dict) else {})
        evidence["latest_network_revision"] = rev
        evidence["latest_network_updated_at"] = ts
        if isinstance(payload, dict):
            ws = payload.get("music_workspace_state")
            if isinstance(ws, dict):
                evidence["latest_network_harmony_map_chord"] = ws.get("harmony_map_chord")
        ss["_phase1_item8_latest_network_revision"] = rev
        ss["_phase1_item8_latest_network_context"] = copy.deepcopy(evidence)
    except Exception as exc:
        evidence["fetch_error"] = str(exc)
    session_diag = ss.get(ITEM8_DIAG_KEY)
    if isinstance(session_diag, dict):
        session_diag = dict(session_diag)
        session_diag.update(evidence)
        ss[ITEM8_DIAG_KEY] = session_diag
    return evidence


def abandon_revision_reservation(session: dict[str, Any]) -> None:
    try:
        from workspace_revision import PENDING_CANONICAL_FP_KEY, RESERVED_WRITE_REVISION_KEY

        session.pop(RESERVED_WRITE_REVISION_KEY, None)
        session.pop(PENDING_CANONICAL_FP_KEY, None)
        session.pop("_music_pending_save_revision", None)
    except ImportError:
        pass


__all__ = [
    "ITEM8_DIAG_KEY",
    "STALE_WRITE_USER_MESSAGE",
    "abandon_revision_reservation",
    "candidate_revision_from_state",
    "device_applied_revision",
    "fetch_latest_network_revision_evidence",
    "prepare_music_conditional_write",
    "record_conditional_write_result",
]

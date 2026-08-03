"""Item 5 read-only browser/Streamlit session lifecycle markers (?dev=1 diagnostics only).

Markers live in URL query params + Streamlit session_state only — never in music workspace / Supabase.
"""

from __future__ import annotations

import uuid
from typing import Any

ITEM5_BROWSER_MARKER_QP = "item5_bsm"
ITEM5_BROWSER_MARKER_SESSION_KEY = "_phase1_item5_browser_session_marker"
ITEM5_STREAMLIT_MARKER_SESSION_KEY = "_phase1_item5_streamlit_session_marker"
ITEM5_LIFECYCLE_DIAG_KEY = "_phase1_item5_session_lifecycle_diag"


def _run_seq(session: dict[str, Any]) -> int:
    try:
        return int(session.get("_script_run_seq") or 0)
    except (TypeError, ValueError):
        return 0


def _query_param(st: Any, name: str) -> str:
    raw = st.query_params.get(name)
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    return str(raw or "").strip()


def observe_item5_session_lifecycle_start(st: Any, session: dict[str, Any]) -> dict[str, Any]:
    """Record lifecycle once per Streamlit session (first script run). Read-only after freeze."""
    frozen = session.get(ITEM5_LIFECYCLE_DIAG_KEY)
    if isinstance(frozen, dict):
        return frozen

    run_seq = _run_seq(session)
    qp_marker_before = _query_param(st, ITEM5_BROWSER_MARKER_QP)
    prior_browser = bool(qp_marker_before)
    prior_streamlit = bool(session.get(ITEM5_STREAMLIT_MARKER_SESSION_KEY))

    suite_sid_before = _query_param(st, "suite_sid") or str(session.get("_suite_browser_session_id") or "").strip()

    created_stage: str | None = None
    if not qp_marker_before:
        new_marker = uuid.uuid4().hex[:16]
        try:
            st.query_params[ITEM5_BROWSER_MARKER_QP] = new_marker
        except Exception:
            pass
        session[ITEM5_BROWSER_MARKER_SESSION_KEY] = new_marker
        created_stage = "observe_item5_session_lifecycle_start"
    else:
        session[ITEM5_BROWSER_MARKER_SESSION_KEY] = qp_marker_before

    if not prior_streamlit:
        session[ITEM5_STREAMLIT_MARKER_SESSION_KEY] = f"st-{run_seq}-{uuid.uuid4().hex[:8]}"

    apply_reason = str(session.get("_suite_persist_apply_reason") or "")
    auth_restored = bool(
        session.get("_suite_first_sync")
        or "first_sync" in apply_reason
        or "cold_start_hydrate" in apply_reason
    )

    diag: dict[str, Any] = {
        "startup_run_seq": run_seq,
        "prior_browser_session_marker_present": prior_browser,
        "prior_streamlit_session_marker_present": prior_streamlit,
        "prior_suite_sid_in_url": bool(suite_sid_before),
        "current_marker_created_stage": created_stage,
        "auth_restored_from_fresh_session": auth_restored,
        "current_run_network_hydration": None,
    }
    session[ITEM5_LIFECYCLE_DIAG_KEY] = diag
    return diag


def _lifecycle(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(ITEM5_LIFECYCLE_DIAG_KEY)
    return dict(raw) if isinstance(raw, dict) else {}


def classify_item5_session_start(
    session: dict[str, Any],
    *,
    certification_network: bool,
    fetch_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify hard_refresh vs cold_reboot vs unknown — independent of certification_passed."""
    explicit = str(session.get("_phase1_item5_session_start_kind") or "").strip()
    if explicit in ("hard_refresh", "cold_reboot", "unknown"):
        return {
            "session_start_kind": explicit,
            "classification_evidence": [f"explicit:{explicit}"],
            "classification_failures": [],
            "classification_confidence": "explicit",
        }

    life = _lifecycle(session)
    prior_browser = bool(life.get("prior_browser_session_marker_present"))
    prior_streamlit = bool(life.get("prior_streamlit_session_marker_present"))
    marker_created_this_run = bool(life.get("current_marker_created_stage"))

    evidence: list[str] = []
    failures: list[str] = []
    confidence = "low"
    kind = "unknown"

    network = certification_network
    if fetch_evidence and fetch_evidence.get("selected_certification_fetch_source") == "network":
        network = True
    life["current_run_network_hydration"] = network

    if not network:
        evidence.append("no_current_run_network_hydration")
        return {
            "session_start_kind": "unknown",
            "classification_evidence": evidence,
            "classification_failures": failures,
            "classification_confidence": "low",
            "session_lifecycle": life,
        }

    if marker_created_this_run and not prior_browser:
        kind = "cold_reboot"
        confidence = "high"
        evidence.append("no_prior_browser_marker_before_startup")
        evidence.append("browser_marker_created_this_startup")
    elif prior_browser and not prior_streamlit:
        kind = "hard_refresh"
        confidence = "high"
        evidence.append("browser_marker_survived_new_streamlit_session")
    elif prior_browser and prior_streamlit:
        kind = "unknown"
        confidence = "medium"
        evidence.append("both_markers_present_likely_streamlit_rerun_not_startup")
    elif not prior_browser and prior_streamlit:
        kind = "unknown"
        confidence = "low"
        failures.append("unexpected_streamlit_marker_without_browser_marker")
        evidence.append("inconsistent_marker_state")
    else:
        apply_reason = str(session.get("_suite_persist_apply_reason") or "")
        if "cold_start_hydrate" in apply_reason or life.get("auth_restored_from_fresh_session"):
            kind = "cold_reboot"
            confidence = "medium"
            evidence.append("suite_cold_start_hydrate_fallback")
        else:
            evidence.append("insufficient_lifecycle_evidence")

    return {
        "session_start_kind": kind,
        "classification_evidence": evidence,
        "classification_failures": failures,
        "classification_confidence": confidence,
        "session_lifecycle": life,
    }


__all__ = [
    "ITEM5_LIFECYCLE_DIAG_KEY",
    "classify_item5_session_start",
    "observe_item5_session_lifecycle_start",
]

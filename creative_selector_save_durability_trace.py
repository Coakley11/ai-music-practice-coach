"""Save-side durability trace for creative_tab_change / creative_tool_change (?dev=1)."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from creative_tab_tool_persistence import (
    SAVE_REASON_TAB,
    SAVE_REASON_TOOL,
    canonical_creative_selector_value,
)

CREATIVE_SELECTOR_SAVE_DURABILITY_KEY = "_creative_selector_save_durability_trace"
CREATIVE_SELECTOR_SAVE_ACTIVE_KEY = "_creative_selector_save_active_tx"

VIOLATION_FALSE_AUTHORITATIVE = "CREATIVE_SELECTOR_FALSE_AUTHORITATIVE_CONFIRMATION"
VIOLATION_UPSERT_NOT_ATTEMPTED = "CREATIVE_SELECTOR_UPSERT_NOT_ATTEMPTED"
VIOLATION_PAYLOAD_OMITTED = "CREATIVE_SELECTOR_PAYLOAD_OMITTED_FIELD"
VIOLATION_WRONG_CLOUD_KEY = "CREATIVE_SELECTOR_WRONG_CLOUD_KEY"
VIOLATION_REFETCH_USED_CACHE = "CREATIVE_SELECTOR_REFETCH_USED_CACHE"
VIOLATION_REVISION_NOT_ADVANCED = "CREATIVE_SELECTOR_REVISION_NOT_ADVANCED"
VIOLATION_CONFIRMED_MISSING = "CREATIVE_SELECTOR_CONFIRMED_VALUE_MISSING_FROM_CLOUD"

_SELECTOR_FIELDS = (
    "improv_intelligence_tab",
    "improv_entry_mode",
    "creative_lab_analysis_mode",
)
_MIRROR_FIELDS = ("creative_improv_intelligence_tab", "creative_lab_last_mode")


def selector_save_reasons() -> frozenset[str]:
    return frozenset({SAVE_REASON_TAB, SAVE_REASON_TOOL})


def is_selector_save_reason(reason: str) -> bool:
    return str(reason or "").strip() in selector_save_reasons()


def _trace(session: dict[str, Any]) -> dict[str, Any]:
    t = session.get(CREATIVE_SELECTOR_SAVE_DURABILITY_KEY)
    if not isinstance(t, dict):
        t = {}
        session[CREATIVE_SELECTOR_SAVE_DURABILITY_KEY] = t
    return t


def _active(session: dict[str, Any]) -> dict[str, Any] | None:
    tx = session.get(CREATIVE_SELECTOR_SAVE_ACTIVE_KEY)
    return tx if isinstance(tx, dict) else None


def _run_seq(session: dict[str, Any]) -> int:
    try:
        return int(session.get("_script_run_seq") or 0)
    except (TypeError, ValueError):
        return 0


def _cloud_identity(session: dict[str, Any]) -> dict[str, str]:
    account = ""
    workspace = ""
    key = "music"
    try:
        from suite_workspace import get_active_workspace_id

        workspace = str(get_active_workspace_id(session) or "").strip()
    except Exception:
        workspace = str(session.get("_suite_active_workspace") or session.get("suite_active_workspace") or "").strip()
    for k in ("_suite_cloud_workspace_key", "_music_cloud_workspace_key"):
        if str(session.get(k) or "").strip():
            account = str(session.get(k) or "").strip()
            break
    return {"app_id": key, "account_or_key": account, "workspace_id": workspace}


def _selector_paths_from_state(state: dict[str, Any]) -> dict[str, Any]:
    session_extra = state.get("session") if isinstance(state.get("session"), dict) else {}
    top = state.get("creative_workspace_state")
    mws = state.get("music_workspace_state")
    nested = mws.get("creative_workspace_state") if isinstance(mws, dict) else None
    return {
        "session": {f: session_extra.get(f) if isinstance(session_extra, dict) else None for f in _SELECTOR_FIELDS},
        "creative_workspace_state": (
            {f: top.get(f) for f in _SELECTOR_FIELDS} if isinstance(top, dict) else {}
        ),
        "nested_creative_workspace_state": (
            {f: nested.get(f) for f in _SELECTOR_FIELDS} if isinstance(nested, dict) else {}
        ),
        "legacy_mirrors": {
            "creative_improv_intelligence_tab": session_extra.get("creative_improv_intelligence_tab")
            if isinstance(session_extra, dict)
            else None,
            "creative_lab_last_mode": session_extra.get("creative_lab_last_mode")
            if isinstance(session_extra, dict)
            else None,
        },
    }


def _revision_from_payload(payload: dict[str, Any]) -> int | None:
    for block in (payload, payload.get("music_workspace_state") if isinstance(payload.get("music_workspace_state"), dict) else {}):
        if not isinstance(block, dict):
            continue
        try:
            if block.get("workspace_revision") is not None:
                return int(block["workspace_revision"])
        except (TypeError, ValueError):
            pass
    try:
        if payload.get("workspace_revision") is not None:
            return int(payload["workspace_revision"])
    except (TypeError, ValueError):
        return None
    return None


def _loaded_revision(session: dict[str, Any]) -> int | None:
    for key in (
        "_suite_applied_workspace_revision",
        "_music_startup_revision_loaded",
        "_suite_cloud_workspace_revision",
    ):
        try:
            if session.get(key) is not None:
                return int(session.get(key))
        except (TypeError, ValueError):
            continue
    return None


def begin_selector_save_durability(
    session: dict[str, Any],
    *,
    field: str,
    old_value: str,
    selected_value: str,
    widget_key: str,
    save_reason: str,
    transaction_id: str = "",
) -> None:
    if not is_selector_save_reason(save_reason):
        return
    tx_id = transaction_id or f"sel-save-{_run_seq(session)}-{uuid.uuid4().hex[:8]}"
    identity = _cloud_identity(session)
    tx = {
        "transaction_id": tx_id,
        "A_user_transaction": {
            "transaction_id": tx_id,
            "run_seq": _run_seq(session),
            "field": field,
            "old_value": old_value,
            "selected_value": selected_value,
            "widget_key": widget_key,
            "canonical_after_callback": canonical_creative_selector_value(session, field),
            "cloud_identity": identity,
            "save_reason": save_reason,
        },
        "revision_loaded_before_edit": _loaded_revision(session),
    }
    session[CREATIVE_SELECTOR_SAVE_ACTIVE_KEY] = tx
    _trace(session)["last_transaction"] = copy.deepcopy(tx)


def record_force_save_path(
    session: dict[str, Any],
    *,
    save_reason: str,
    force_save_entered: bool,
    allowed: bool | None = None,
    block_reason: str = "",
    early_return_stage: str = "",
    early_return_reason: str = "",
    startup_suppression_armed: Any = None,
    startup_suppression_released: Any = None,
    transaction_sequence: Any = None,
    canonical_revision_before: int | None = None,
    reserved_revision: int | None = None,
) -> None:
    if not is_selector_save_reason(save_reason):
        return
    tx = _active(session)
    if tx is None:
        return
    try:
        from music_egress_config import is_intentional_user_save_reason, normalize_music_save_reason

        normalized = normalize_music_save_reason(save_reason)
        intentional = is_intentional_user_save_reason(normalized)
    except ImportError:
        normalized = save_reason
        intentional = None
    tx["B_force_save_path"] = {
        "force_save_entered": force_save_entered,
        "reason_received": save_reason,
        "reason_normalized": normalized,
        "strict_intentional_allowed": intentional,
        "save_allowed": allowed,
        "block_reason": block_reason or None,
        "early_return_stage": early_return_stage or None,
        "early_return_reason": early_return_reason or None,
        "startup_suppression_armed": startup_suppression_armed,
        "startup_suppression_released": startup_suppression_released,
        "transaction_sequence": transaction_sequence,
        "canonical_revision_before_reservation": canonical_revision_before,
        "reserved_revision": reserved_revision,
    }


def ensure_selector_field_in_upsert_payload(
    session: dict[str, Any],
    state: dict[str, Any],
) -> None:
    """Guarantee active selector field is present in envelope paths before Supabase upsert."""
    tx = _active(session)
    if tx is None:
        return
    a = tx.get("A_user_transaction") if isinstance(tx.get("A_user_transaction"), dict) else {}
    field = str(a.get("field") or "").strip()
    value = str(a.get("selected_value") or "").strip()
    if not field or not value:
        return
    if not isinstance(state, dict):
        return
    top = state.setdefault("creative_workspace_state", {})
    if isinstance(top, dict):
        top[field] = value
        if field == "improv_intelligence_tab":
            top["creative_improv_intelligence_tab"] = value
        if field == "creative_lab_analysis_mode":
            top["creative_lab_last_mode"] = value
    sess = state.setdefault("session", {})
    if isinstance(sess, dict):
        sess[field] = value
        if field == "improv_intelligence_tab":
            sess["creative_improv_intelligence_tab"] = value
        if field == "creative_lab_analysis_mode":
            sess["creative_lab_last_mode"] = value
    mws = state.setdefault("music_workspace_state", {})
    if isinstance(mws, dict):
        nested = mws.setdefault("creative_workspace_state", {})
        if isinstance(nested, dict):
            nested[field] = value


def record_payload_before_upsert(session: dict[str, Any], state: dict[str, Any], *, write_path: str = "") -> None:
    tx = _active(session)
    if tx is None:
        return
    a = tx.get("A_user_transaction") if isinstance(tx.get("A_user_transaction"), dict) else {}
    field = str(a.get("field") or "").strip()
    selected = str(a.get("selected_value") or "").strip()
    paths = _selector_paths_from_state(state if isinstance(state, dict) else {})
    field_in_payload = False
    if field:
        for block in (paths.get("session"), paths.get("creative_workspace_state"), paths.get("nested_creative_workspace_state")):
            if isinstance(block, dict) and str(block.get(field) or "").strip() == selected:
                field_in_payload = True
                break
    tx["C_payload_before_upsert"] = {
        "write_path": write_path,
        "selector_paths": paths,
        "canonical_payload_path": "creative_workspace_state",
        "selected_field_nonempty_in_upsert": field_in_payload,
        "workspace_revision_in_payload": _revision_from_payload(state if isinstance(state, dict) else {}),
    }


def record_supabase_result(session: dict[str, Any], *, diag: dict[str, Any] | None, saved: bool) -> None:
    tx = _active(session)
    if tx is None:
        return
    d = diag if isinstance(diag, dict) else {}
    identity = _cloud_identity(session)
    tx["D_supabase_result"] = {
        "request_attempted": bool(d.get("cloud_upsert_attempted") or d.get("save_cloud_full_session_return_value") is not None),
        "http_status": d.get("supabase_response_status"),
        "storage_app_id": identity.get("app_id"),
        "storage_account_key": identity.get("account_or_key"),
        "storage_workspace_id": identity.get("workspace_id"),
        "revision_submitted": d.get("cloud_payload_revision"),
        "response_revision": d.get("cloud_payload_revision"),
        "upsert_succeeded": bool(saved and d.get("cloud_upsert_succeeded", saved)),
        "failure_stage": d.get("save_cloud_full_session_failure_stage"),
        "exception": d.get("save_cloud_full_session_exception"),
    }


def perform_authoritative_selector_refetch(session: dict[str, Any], *, app_id: str = "music") -> dict[str, Any]:
    tx = _active(session)
    if tx is None:
        return {}
    try:
        from suite_cloud_state import load_cloud_full_session

        payload, _ts = load_cloud_full_session(app_id, force=True)
    except Exception as exc:
        tx["E_authoritative_refetch"] = {"error": str(exc), "fetch_source": "error"}
        return {}
    fetch_source = str(session.get("_music_last_cloud_fetch_source") or "")
    cache_bypassed = fetch_source == "network"
    identity = _cloud_identity(session)
    paths = _selector_paths_from_state(payload if isinstance(payload, dict) else {})
    tx["E_authoritative_refetch"] = {
        "cloud_identity": identity,
        "fetched_revision": _revision_from_payload(payload if isinstance(payload, dict) else {}),
        "selector_paths": paths,
        "fetch_source": fetch_source,
        "cache_bypass_confirmed": cache_bypassed,
        "force": True,
    }
    session["_creative_selector_authoritative_refetch_payload"] = copy.deepcopy(payload)
    return payload if isinstance(payload, dict) else {}


def finalize_selector_save_confirmation(session: dict[str, Any], *, force_save_ok: bool) -> dict[str, Any]:
    """Confirm only from Supabase upsert + forced network refetch of the same row."""
    from creative_tab_tool_persistence import record_creative_tab_violation

    tx = _active(session) or {}
    a = tx.get("A_user_transaction") if isinstance(tx.get("A_user_transaction"), dict) else {}
    b = tx.get("B_force_save_path") if isinstance(tx.get("B_force_save_path"), dict) else {}
    c = tx.get("C_payload_before_upsert") if isinstance(tx.get("C_payload_before_upsert"), dict) else {}
    d = tx.get("D_supabase_result") if isinstance(tx.get("D_supabase_result"), dict) else {}
    e = tx.get("E_authoritative_refetch") if isinstance(tx.get("E_authoritative_refetch"), dict) else {}

    field = str(a.get("field") or "").strip()
    selected = str(a.get("selected_value") or "").strip()
    reserved = b.get("reserved_revision")
    try:
        reserved_int = int(reserved) if reserved is not None else None
    except (TypeError, ValueError):
        reserved_int = None
    ref_rev = e.get("fetched_revision")
    try:
        ref_rev_int = int(ref_rev) if ref_rev is not None else None
    except (TypeError, ValueError):
        ref_rev_int = None
    loaded_before = tx.get("revision_loaded_before_edit")
    try:
        loaded_int = int(loaded_before) if loaded_before is not None else None
    except (TypeError, ValueError):
        loaded_int = None

    ref_paths = e.get("selector_paths") if isinstance(e.get("selector_paths"), dict) else {}
    ref_val = ""
    if field:
        for block in (ref_paths.get("session"), ref_paths.get("creative_workspace_state"), ref_paths.get("nested_creative_workspace_state")):
            if isinstance(block, dict) and str(block.get(field) or "").strip():
                ref_val = str(block.get(field) or "").strip()
                break

    identity = a.get("cloud_identity") if isinstance(a.get("cloud_identity"), dict) else {}
    ref_identity = e.get("cloud_identity") if isinstance(e.get("cloud_identity"), dict) else {}

    checks = {
        "force_save_ok": bool(force_save_ok),
        "upsert_attempted": bool(d.get("request_attempted")),
        "upsert_succeeded": bool(d.get("upsert_succeeded")),
        "payload_field_nonempty": bool(c.get("selected_field_nonempty_in_upsert")),
        "same_cloud_key": identity.get("app_id") == ref_identity.get("app_id"),
        "cache_bypass_confirmed": bool(e.get("cache_bypass_confirmed")),
        "refetch_revision_equals_reserved": (
            reserved_int is not None and ref_rev_int is not None and reserved_int == ref_rev_int
        ),
        "refetch_revision_advanced": (
            ref_rev_int is not None and loaded_int is not None and ref_rev_int > loaded_int
        ),
        "refetched_field_equals_selected": ref_val == selected,
    }

    confirmed = all(
        (
            checks["upsert_attempted"],
            checks["upsert_succeeded"],
            checks["payload_field_nonempty"],
            checks["same_cloud_key"],
            checks["cache_bypass_confirmed"],
            checks["refetch_revision_equals_reserved"],
            checks["refetch_revision_advanced"],
            checks["refetched_field_equals_selected"],
        )
    )

    confirmation_status = "confirmed" if confirmed else "unconfirmed"
    confirmation_stage = "authoritative_network_refetch" if confirmed else "failed_checks"

    result = {
        "transaction_id": a.get("transaction_id"),
        "transaction_run_seq": a.get("run_seq"),
        "field": field,
        "old_value": a.get("old_value"),
        "new_value": selected,
        "save_reason": a.get("save_reason"),
        "reserved_revision": reserved_int,
        "confirmed_revision": ref_rev_int if checks["refetch_revision_equals_reserved"] else None,
        "authoritative_refetch_revision": ref_rev_int,
        "authoritative_refetched_value": ref_val,
        "confirmation_checks": checks,
        "confirmation_status": confirmation_status,
        "confirmation_stage": confirmation_stage,
        "revision_loaded_before_edit": loaded_int,
        "durability_trace": copy.deepcopy(tx),
    }

    if not checks["upsert_attempted"]:
        record_creative_tab_violation(session, VIOLATION_UPSERT_NOT_ATTEMPTED)
    if not checks["payload_field_nonempty"]:
        record_creative_tab_violation(session, VIOLATION_PAYLOAD_OMITTED, detail=field)
    if not checks["cache_bypass_confirmed"]:
        record_creative_tab_violation(session, VIOLATION_REFETCH_USED_CACHE)
    if reserved_int is not None and ref_rev_int is not None and ref_rev_int <= (loaded_int or 0):
        record_creative_tab_violation(session, VIOLATION_REVISION_NOT_ADVANCED, detail=f"{ref_rev_int}<={loaded_int}")
    if checks["upsert_succeeded"] and not checks["refetched_field_equals_selected"]:
        record_creative_tab_violation(session, VIOLATION_CONFIRMED_MISSING, detail=f"expected={selected} got={ref_val}")
    if not confirmed and force_save_ok:
        record_creative_tab_violation(session, VIOLATION_FALSE_AUTHORITATIVE)

    _trace(session)["last_finalized"] = copy.deepcopy(result)
    session.pop(CREATIVE_SELECTOR_SAVE_ACTIVE_KEY, None)
    return result


def collect_selector_save_durability_trace(session: dict[str, Any]) -> dict[str, Any]:
    return dict(_trace(session))


__all__ = [
    "CREATIVE_SELECTOR_SAVE_DURABILITY_KEY",
    "CREATIVE_SELECTOR_SAVE_ACTIVE_KEY",
    "VIOLATION_CONFIRMED_MISSING",
    "VIOLATION_FALSE_AUTHORITATIVE",
    "VIOLATION_PAYLOAD_OMITTED",
    "VIOLATION_REFETCH_USED_CACHE",
    "VIOLATION_REVISION_NOT_ADVANCED",
    "VIOLATION_UPSERT_NOT_ATTEMPTED",
    "VIOLATION_WRONG_CLOUD_KEY",
    "begin_selector_save_durability",
    "collect_selector_save_durability_trace",
    "ensure_selector_field_in_upsert_payload",
    "finalize_selector_save_confirmation",
    "is_selector_save_reason",
    "perform_authoritative_selector_refetch",
    "record_force_save_path",
    "record_payload_before_upsert",
    "record_supabase_result",
    "selector_save_reasons",
]

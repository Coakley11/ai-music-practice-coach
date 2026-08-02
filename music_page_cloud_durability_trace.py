"""Page_change cloud durability trace (?dev=1) — authoritative upsert vs hydration."""

from __future__ import annotations

import json
import uuid
from typing import Any

PAGE_CLOUD_DURABILITY_TRACE_KEY = "_music_page_cloud_durability_trace"
PAGE_CLOUD_DURABILITY_IMPL_MARKER = "music_page_cloud_durability_trace:v2-tx-retention"
PAGE_CLOUD_DURABILITY_UI_MARKER = "PAGE_CLOUD_DURABILITY_TRACE_IMPL: 3ff4251-v1"
_MAX_PAGE_CHANGE_TRANSACTIONS = 5

AUTHORITATIVE_CONFIRMED_KEY = "_music_page_change_authoritative_confirmed"
AUTHORITATIVE_CONFIRMATION_DETAIL_KEY = "_music_page_change_authoritative_confirmation"

_SUBSEQUENT_MAX = 80
_VIOLATIONS_KEY = "_phase1_creative_cloud_violations"


def durability_trace_enabled(session: dict[str, Any]) -> bool:
    if session.get("_phase1_write_journal_force"):
        return True
    if session.get("developer_mode"):
        return True
    try:
        from suite_workspace import is_developer_mode_enabled

        return bool(is_developer_mode_enabled())
    except ImportError:
        return False


def _fresh_bucket(session: dict[str, Any], *, reset_stage: str) -> dict[str, Any]:
    prev = session.get(PAGE_CLOUD_DURABILITY_TRACE_KEY)
    reset_count = 0
    if isinstance(prev, dict):
        try:
            reset_count = int(prev.get("journal_reset_count") or 0)
        except (TypeError, ValueError):
            reset_count = 0
    return {
        "impl_marker": PAGE_CLOUD_DURABILITY_IMPL_MARKER,
        "journal_storage": "session_state",
        "transactions": [],
        "active_transaction_id": None,
        "subsequent_writes": [],
        "fresh_hydration": None,
        "failure_class": None,
        "first_mismatch_stage": None,
        "violations": [],
        "transaction_start_hook_called": False,
        "journal_reset_count": reset_count + 1,
        "last_journal_reset_stage": reset_stage,
        "transaction_lost_across_rerun": False,
        "recovered_transaction": False,
    }


def _ensure_bucket(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(PAGE_CLOUD_DURABILITY_TRACE_KEY)
    if not isinstance(raw, dict):
        fresh = _fresh_bucket(session, reset_stage="init_non_dict" if raw is not None else "init_missing")
        session[PAGE_CLOUD_DURABILITY_TRACE_KEY] = fresh
        return fresh
    raw.setdefault("impl_marker", PAGE_CLOUD_DURABILITY_IMPL_MARKER)
    raw.setdefault("journal_storage", "session_state")
    if not isinstance(raw.get("transactions"), list):
        raw["transactions"] = list(raw.get("transactions") or [])
    raw.setdefault("active_transaction_id", None)
    raw.setdefault("subsequent_writes", [])
    raw.setdefault("violations", [])
    raw.setdefault("transaction_start_hook_called", False)
    raw.setdefault("journal_reset_count", 0)
    raw.setdefault("last_journal_reset_stage", None)
    raw.setdefault("transaction_lost_across_rerun", False)
    raw.setdefault("recovered_transaction", False)
    return raw


def _bucket(session: dict[str, Any]) -> dict[str, Any]:
    return _ensure_bucket(session)


def _trim_transactions(bucket: dict[str, Any]) -> None:
    txs = bucket.get("transactions")
    if not isinstance(txs, list) or len(txs) <= _MAX_PAGE_CHANGE_TRANSACTIONS:
        return
    del txs[: len(txs) - _MAX_PAGE_CHANGE_TRANSACTIONS]


def _phase1_genuine_user_page_write(session: dict[str, Any]) -> bool:
    try:
        from music_phase1_write_journal import PHASE1_WRITE_JOURNAL_KEY, USER_ORIGINS, phase1_journal_enabled
    except ImportError:
        return False
    if not phase1_journal_enabled(session):
        return False
    j = session.get(PHASE1_WRITE_JOURNAL_KEY)
    if not isinstance(j, dict):
        return False
    for row in j.get("page_writes") or []:
        if not isinstance(row, dict):
            continue
        origin = str(row.get("origin") or row.get("reason") or "").strip()
        if origin in USER_ORIGINS or origin == "user_navigation":
            return True
    summary = j.get("final_summary")
    if isinstance(summary, dict):
        clicked = str(summary.get("clicked_page") or "").strip()
        origin = str(summary.get("page_change_origin") or "").strip()
        if clicked and origin in USER_ORIGINS | {"user_navigation"}:
            return True
    prev = session.get("_phase1_prev_run_summary")
    if isinstance(prev, dict):
        clicked = str(prev.get("clicked_page") or "").strip()
        origin = str(prev.get("page_change_origin") or "").strip()
        if clicked and origin in USER_ORIGINS | {"user_navigation"}:
            return True
    if str(session.get("_music_user_navigated_page_this_run") or "").strip():
        return True
    return False


def evaluate_durability_transaction_integrity(session: dict[str, Any]) -> dict[str, Any]:
    bucket = _ensure_bucket(session)
    txs = bucket.get("transactions") if isinstance(bucket.get("transactions"), list) else []
    phase1_nav = _phase1_genuine_user_page_write(session)
    lost = phase1_nav and not txs
    if lost:
        bucket["transaction_lost_across_rerun"] = True
        prior = bucket.get("violations") if isinstance(bucket.get("violations"), list) else []
        if not any(isinstance(v, dict) and v.get("code") == "PAGE_CLOUD_DURABILITY_TRANSACTION_LOST" for v in prior):
            _record_violation(
            session,
            code="PAGE_CLOUD_DURABILITY_TRANSACTION_LOST",
            detail={
                "phase1_user_page_write": True,
                "transaction_count": 0,
                "run_seq": session.get("_script_run_seq"),
            },
        )
    return {
        "transaction_start_hook_called": bool(bucket.get("transaction_start_hook_called")),
        "transaction_count": len(txs),
        "journal_storage": bucket.get("journal_storage") or "session_state",
        "journal_reset_count": bucket.get("journal_reset_count"),
        "last_journal_reset_stage": bucket.get("last_journal_reset_stage"),
        "transaction_lost_across_rerun": bool(bucket.get("transaction_lost_across_rerun") or lost),
        "recovered_transaction": bool(bucket.get("recovered_transaction")),
        "active_transaction_id": bucket.get("active_transaction_id"),
    }


def _set_active_transaction_status(session: dict[str, Any], status: str) -> None:
    tx = _active_tx(session)
    if tx:
        tx["status"] = status


def _complete_active_transaction(session: dict[str, Any], status: str) -> None:
    _set_active_transaction_status(session, status)
    bucket = _ensure_bucket(session)
    bucket["active_transaction_id"] = None


def begin_navigation_page_change_transaction(
    session: dict[str, Any],
    *,
    clicked_page: str,
    prior_page: str,
    origin: str = "user_navigation",
) -> str:
    """Earliest page_change durability hook — must run before save suppression."""
    if not durability_trace_enabled(session):
        return ""
    bucket = _ensure_bucket(session)
    bucket["transaction_start_hook_called"] = True
    run_seq = session.get("_script_run_seq")
    tx_id = f"nav-{run_seq or 0}-{uuid.uuid4().hex[:8]}"
    tx: dict[str, Any] = {
        "transaction_id": tx_id,
        "status": "navigation_recorded",
        "save_reason": "page_change",
        "run_seq": run_seq,
        "clicked_page": str(clicked_page or "").strip().lower(),
        "prior_page": str(prior_page or "").strip().lower(),
        "origin": str(origin or "user_navigation").strip(),
        "transaction_start_stage": "navigate_studio_page",
        "transaction_sequence": session.get("_music_page_change_transaction_seq"),
        "cloud_context": _cloud_context(session),
        "revision": {},
        "force_save_events": [],
        "attempted_upsert": None,
        "supabase_response": None,
        "authoritative_refetch": None,
        "confirmation": None,
        "legacy_confirmed_revision": session.get("_music_last_confirmed_cloud_revision"),
    }
    bucket.setdefault("transactions", []).append(tx)
    _trim_transactions(bucket)
    bucket["active_transaction_id"] = tx_id
    return tx_id


def record_force_save_durability_entry(
    session: dict[str, Any],
    *,
    reason: str,
    stage: str = "entry",
) -> None:
    if not durability_trace_enabled(session):
        return
    r = str(reason or "").strip()
    bucket = _ensure_bucket(session)
    tx = _active_tx(session)
    if not tx and r == "page_change":
        begin_page_change_cloud_transaction(
            session,
            save_reason="page_change",
            transaction_recovered_at_force_save=True,
        )
        bucket["recovered_transaction"] = True
        tx = _active_tx(session)
    if not tx:
        return
    event: dict[str, Any] = {
        "stage": stage,
        "force_save_entered": True,
        "reason": r,
        "run_seq": session.get("_script_run_seq"),
        "pending_page": session.get("_suite_page_change_save_page"),
        "current_page": session.get("studio_page"),
        "user_nav_page_this_run": session.get("_music_user_navigated_page_this_run"),
    }
    try:
        from music_startup_save_suppression import (
            STARTUP_SUPPRESSION_ARMED_KEY,
            STARTUP_SUPPRESSION_RELEASED_KEY,
            collect_startup_save_suppression_diagnostics,
        )

        event["startup_suppression_armed"] = session.get(STARTUP_SUPPRESSION_ARMED_KEY)
        event["startup_suppression_released"] = session.get(STARTUP_SUPPRESSION_RELEASED_KEY)
        event["startup_suppression_diag"] = collect_startup_save_suppression_diagnostics(session)
    except ImportError:
        pass
    tx.setdefault("force_save_events", []).append(event)
    if tx.get("status") == "navigation_recorded" and r == "page_change":
        tx["status"] = "save_entered"


def record_force_save_early_exit(
    session: dict[str, Any],
    *,
    save_reason: str,
    exit_stage: str,
    exit_reason: str,
) -> None:
    if not durability_trace_enabled(session):
        return
    if str(save_reason or "").strip() != "page_change":
        return
    record_force_save_durability_entry(session, reason="page_change", stage=f"early_return:{exit_stage}")
    _set_active_transaction_status(session, "save_blocked_before_payload")
    tx = _active_tx(session)
    if tx:
        tx["early_exit"] = {"stage": exit_stage, "reason": exit_reason}
    if "startup_suppression" in str(exit_reason or "") or exit_reason == "startup_suppression_armed_page_change":
        bucket = _ensure_bucket(session)
        bucket["startup_release_failure_hint"] = "8_page_change_blocked_by_false_startup_page_mismatch"
    record_startup_release_revision_violation(session)


def record_startup_release_revision_violation(session: dict[str, Any]) -> None:
    if not durability_trace_enabled(session):
        return
    loaded = int(session.get("startup_revision_loaded") or 0)
    final = int(session.get("startup_revision_final") or 0)
    if final == loaded:
        return
    if session.get("_music_page_change_payload_built"):
        return
    _record_violation(
        session,
        code="STARTUP_RELEASE_ADVANCED_REVISION_WITHOUT_CLOUD_WRITE",
        detail={
            "startup_revision_loaded": loaded,
            "startup_revision_final": final,
            "current_page_change_payload_built": session.get("_music_page_change_payload_built"),
        },
    )


def record_queued_page_release_hotfix_violation(
    session: dict[str, Any],
    *,
    code: str,
    detail: dict[str, Any],
) -> None:
    if not durability_trace_enabled(session):
        return
    _record_violation(session, code=code, detail=detail)


def merge_queued_release_trace_into_payload(payload: dict[str, Any], session: dict[str, Any]) -> None:
    try:
        from music_queued_page_startup_release_trace import (
            QUEUED_PAGE_STARTUP_RELEASE_IMPL,
            build_queued_release_trace_copy,
        )

        payload["queued_page_startup_release_impl"] = QUEUED_PAGE_STARTUP_RELEASE_IMPL
        payload["queued_page_release_trace"] = build_queued_release_trace_copy(session)
    except ImportError:
        payload["queued_page_startup_release_impl"] = "import_failed"


def record_startup_release_blocked(
    session: dict[str, Any],
    *,
    differing_paths: list[str],
    suppress_reason: str = "",
) -> None:
    if not durability_trace_enabled(session):
        return
    bucket = _ensure_bucket(session)
    bucket["startup_release_failure_hint"] = (
        "startup_release_included_queued_user_page_in_fingerprint"
        if _page_diffs_only(differing_paths)
        else "8_page_change_blocked_by_false_startup_page_mismatch"
    )
    _record_violation(
        session,
        code="PAGE_CHANGE_STARTUP_RELEASE_BLOCKED",
        detail={
            "differing_canonical_paths": differing_paths,
            "suppress_reason": suppress_reason or None,
        },
    )


def _page_diffs_only(differing_paths: list[str]) -> bool:
    if not differing_paths:
        return False
    try:
        from music_startup_save_suppression import _is_page_bearing_canonical_path

        return all(_is_page_bearing_canonical_path(str(p)) for p in differing_paths)
    except ImportError:
        return False


def page_fields_from_state(state: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(state, dict):
        return {}
    core = state.get("core") if isinstance(state.get("core"), dict) else {}
    sess = state.get("session") if isinstance(state.get("session"), dict) else {}
    pws = state.get("practice_workspace_state") if isinstance(state.get("practice_workspace_state"), dict) else {}
    mws = state.get("music_workspace_state") if isinstance(state.get("music_workspace_state"), dict) else {}
    nav = state.get("studio_nav_state") if isinstance(state.get("studio_nav_state"), dict) else {}

    def _p(page: Any) -> str:
        return str(page or "").strip().lower()

    return {
        "core": _p(core.get("studio_page") or core.get("page")),
        "session": _p(sess.get("studio_page")),
        "practice_workspace": _p(pws.get("studio_page") or pws.get("page")),
        "music_workspace": _p(mws.get("studio_page") or mws.get("page")),
        "studio_nav": _p(nav.get("studio_page") or nav.get("page")),
    }


def _revision_from_state(state: dict[str, Any] | None) -> int | None:
    if not isinstance(state, dict):
        return None
    try:
        from workspace_revision import workspace_revision_from_blob

        rev = workspace_revision_from_blob(state)
        return int(rev) if rev is not None else None
    except ImportError:
        pass
    try:
        if state.get("workspace_revision") is not None:
            return int(state.get("workspace_revision"))
    except (TypeError, ValueError):
        pass
    ws = state.get("music_workspace_state")
    if isinstance(ws, dict) and ws.get("workspace_revision") is not None:
        try:
            return int(ws.get("workspace_revision"))
        except (TypeError, ValueError):
            return None
    return None


def _cloud_context(session: dict[str, Any]) -> dict[str, Any]:
    ctx: dict[str, Any] = {}
    try:
        from suite_cloud_state import _cloud_save_account_context

        ctx = dict(_cloud_save_account_context())
    except Exception:
        pass
    try:
        from suite_workspace import get_active_workspace_id

        ctx["active_workspace_id"] = str(get_active_workspace_id() or "").strip() or None
    except Exception:
        pass
    ctx["startup_revision_loaded"] = session.get("startup_revision_loaded")
    return ctx


def _active_tx(session: dict[str, Any]) -> dict[str, Any] | None:
    bucket = session.get(PAGE_CLOUD_DURABILITY_TRACE_KEY)
    if not isinstance(bucket, dict):
        return None
    tx_id = bucket.get("active_transaction_id")
    for tx in bucket.get("transactions") or []:
        if isinstance(tx, dict) and tx.get("transaction_id") == tx_id:
            return tx
    return None


def begin_page_change_cloud_transaction(
    session: dict[str, Any],
    *,
    save_reason: str,
    run_seq: Any = None,
    transaction_sequence: Any = None,
    transaction_recovered_at_force_save: bool = False,
) -> str:
    if not durability_trace_enabled(session):
        return ""
    if str(save_reason or "").strip() != "page_change":
        return ""
    bucket = _ensure_bucket(session)
    existing = _active_tx(session)
    if existing:
        existing["save_reason"] = "page_change"
        if transaction_recovered_at_force_save:
            existing["transaction_recovered_at_force_save"] = True
        return str(existing.get("transaction_id") or "")
    tx_id = (
        f"pc-{run_seq or session.get('_script_run_seq')}-"
        f"{transaction_sequence or session.get('_music_page_change_transaction_seq')}-"
        f"{uuid.uuid4().hex[:8]}"
    )
    stage = "force_music_workspace_save" if transaction_recovered_at_force_save else "page_change_save"
    tx: dict[str, Any] = {
        "transaction_id": tx_id,
        "status": "navigation_recorded" if transaction_recovered_at_force_save else "save_entered",
        "save_reason": "page_change",
        "run_seq": run_seq if run_seq is not None else session.get("_script_run_seq"),
        "transaction_sequence": transaction_sequence
        if transaction_sequence is not None
        else session.get("_music_page_change_transaction_seq"),
        "transaction_start_stage": stage,
        "transaction_recovered_at_force_save": bool(transaction_recovered_at_force_save),
        "cloud_context": _cloud_context(session),
        "revision": {},
        "force_save_events": [],
        "attempted_upsert": None,
        "supabase_response": None,
        "authoritative_refetch": None,
        "confirmation": None,
        "legacy_confirmed_revision": session.get("_music_last_confirmed_cloud_revision"),
    }
    if transaction_recovered_at_force_save:
        bucket["recovered_transaction"] = True
    bucket.setdefault("transactions", []).append(tx)
    _trim_transactions(bucket)
    bucket["active_transaction_id"] = tx_id
    return tx_id


def record_revision_stages(
    session: dict[str, Any],
    *,
    canonical_revision_before: int | None,
    reserved_revision: int | None,
    revision_in_upsert_payload: int | None,
    startup_revision_loaded: int | None = None,
) -> None:
    if not durability_trace_enabled(session):
        return
    tx = _active_tx(session)
    if not tx:
        return
    loaded = (
        startup_revision_loaded
        if startup_revision_loaded is not None
        else session.get("startup_revision_loaded")
    )
    tx["revision"] = {
        "startup_revision_loaded": loaded,
        "canonical_revision_before_reservation": canonical_revision_before,
        "reserved_revision": reserved_revision,
        "revision_in_upsert_payload": revision_in_upsert_payload,
        "reserved_equals_payload": (
            reserved_revision is not None
            and revision_in_upsert_payload is not None
            and int(reserved_revision) == int(revision_in_upsert_payload)
        ),
        "reserved_gt_startup_loaded": (
            reserved_revision is not None
            and loaded is not None
            and int(reserved_revision) > int(loaded)
        )
        if loaded is not None
        else None,
    }


def record_attempted_upsert(
    session: dict[str, Any],
    state: dict[str, Any],
    *,
    page_arg: str = "",
    write_path: str = "",
) -> None:
    if not durability_trace_enabled(session):
        return
    tx = _active_tx(session)
    if not tx:
        return
    ctx = _cloud_context(session)
    tx["attempted_upsert"] = {
        "write_path": write_path or None,
        "page_arg": page_arg or None,
        "cloud_namespace_key": ctx.get("cloud_document_path"),
        "workspace_id": ctx.get("workspace_id_resolved") or ctx.get("active_workspace_id"),
        "account_id": ctx.get("account_id"),
        "pages": page_fields_from_state(state),
        "revision": _revision_from_state(state),
    }
    _set_active_transaction_status(session, "payload_built")


def record_supabase_response(session: dict[str, Any], *, cloud_result_diag: dict[str, Any] | None) -> None:
    if not durability_trace_enabled(session):
        return
    tx = _active_tx(session)
    if not tx:
        return
    diag = dict(cloud_result_diag or {})
    tx["supabase_response"] = {
        "success": diag.get("save_cloud_full_session_return_value") or diag.get("cloud_upsert_succeeded"),
        "cloud_payload_revision": diag.get("cloud_payload_revision"),
        "supabase_response_status": diag.get("supabase_response_status"),
        "storage_app_key": diag.get("storage_app_key"),
        "cloud_document_path": diag.get("cloud_document_path"),
        "failure_stage": diag.get("save_cloud_full_session_failure_stage"),
        "exception": diag.get("save_cloud_full_session_exception"),
    }
    _set_active_transaction_status(session, "upsert_attempted")


def record_authoritative_refetch(
    session: dict[str, Any],
    readback: dict[str, Any] | None,
    *,
    force: bool,
    cache_bypassed: bool,
    fetch_source: str,
) -> None:
    if not durability_trace_enabled(session):
        return
    tx = _active_tx(session)
    if not tx:
        return
    payload = readback if isinstance(readback, dict) else {}
    tx["authoritative_refetch"] = {
        "fetch_source": fetch_source,
        "force_refetch": force,
        "cache_bypassed": cache_bypassed,
        "revision": _revision_from_state(payload),
        "pages": page_fields_from_state(payload),
        "cloud_key": _cloud_context(session).get("cloud_document_path"),
    }


def evaluate_authoritative_page_change_confirmation(
    session: dict[str, Any],
    *,
    target_page: str = "creative",
) -> dict[str, Any]:
    """Diagnostics-only confirmation — does not mutate egress or suite persist flags."""
    tx = _active_tx(session) or {}
    attempted = tx.get("attempted_upsert") if isinstance(tx.get("attempted_upsert"), dict) else {}
    refetch = tx.get("authoritative_refetch") if isinstance(tx.get("authoritative_refetch"), dict) else {}
    rev_block = tx.get("revision") if isinstance(tx.get("revision"), dict) else {}

    reserved = rev_block.get("reserved_revision")
    startup_loaded = rev_block.get("startup_revision_loaded")
    ref_rev = refetch.get("revision")
    ref_pages = refetch.get("pages") if isinstance(refetch.get("pages"), dict) else {}

    target = str(target_page or "creative").strip().lower()
    pages_ok = bool(ref_pages) and all(
        (not val) or str(val).strip().lower() == target for val in ref_pages.values()
    )

    checks: dict[str, Any] = {
        "refetch_revision_equals_reserved": (
            reserved is not None and ref_rev is not None and int(ref_rev) == int(reserved)
        ),
        "refetch_revision_gt_startup_loaded": (
            startup_loaded is not None and ref_rev is not None and int(ref_rev) > int(startup_loaded)
        ),
        "all_refetch_pages_match_target": pages_ok,
        "cache_bypassed_for_refetch": bool(refetch.get("cache_bypassed")),
        "workspace_key_match": bool(refetch.get("cloud_key")),
    }

    legacy_rev = tx.get("legacy_confirmed_revision")
    checks["not_reusing_legacy_revision_only"] = not (
        legacy_rev is not None
        and ref_rev is not None
        and reserved is not None
        and startup_loaded is not None
        and int(ref_rev) == int(legacy_rev)
        and int(reserved) <= int(legacy_rev)
        and int(ref_rev) <= int(startup_loaded)
    )

    confirmed = all(bool(v) for v in checks.values())
    detail: dict[str, Any] = {
        "confirmed": confirmed,
        "checks": checks,
        "target_page": target,
        "reserved_revision": reserved,
        "refetch_revision": ref_rev,
        "startup_revision_loaded": startup_loaded,
        "legacy_confirmed_revision": legacy_rev,
        "refetch_pages": ref_pages,
    }

    if durability_trace_enabled(session):
        tx_obj = _active_tx(session)
        if tx_obj:
            tx_obj["confirmation"] = detail
            _set_active_transaction_status(
                session, "authoritative_confirmed" if confirmed else "authoritative_not_confirmed"
            )
        session[AUTHORITATIVE_CONFIRMATION_DETAIL_KEY] = detail
        session[AUTHORITATIVE_CONFIRMED_KEY] = confirmed
        if not confirmed:
            _record_violation(
                session,
                code="PHASE1_PAGE_CHANGE_NOT_AUTHORITATIVELY_CONFIRMED",
                detail=detail,
            )
    return detail


def record_subsequent_save_attempt(
    session: dict[str, Any],
    *,
    reason: str,
    allowed: bool,
    blocked_reason: str = "",
    state: dict[str, Any] | None = None,
    cloud_result: str = "",
    transaction_sequence: Any = None,
) -> None:
    if not durability_trace_enabled(session):
        return
    auth = session.get(AUTHORITATIVE_CONFIRMATION_DETAIL_KEY)
    if not isinstance(auth, dict) or not auth.get("confirmed"):
        return
    bucket = _ensure_bucket(session)
    confirmed_rev = auth.get("refetch_revision") or auth.get("reserved_revision")
    entry: dict[str, Any] = {
        "seq": len(bucket.get("subsequent_writes") or []) + 1,
        "run_seq": session.get("_script_run_seq"),
        "transaction_sequence": transaction_sequence,
        "reason": str(reason or "").strip(),
        "revision": _revision_from_state(state) if isinstance(state, dict) else None,
        "pages": page_fields_from_state(state) if isinstance(state, dict) else {},
        "allowed": allowed,
        "blocked_reason": blocked_reason or None,
        "cloud_result": cloud_result or None,
        "cloud_key": _cloud_context(session).get("cloud_document_path"),
    }
    subs = bucket.setdefault("subsequent_writes", [])
    subs.append(entry)
    if len(subs) > _SUBSEQUENT_MAX:
        del subs[: len(subs) - _SUBSEQUENT_MAX]

    pages = entry.get("pages") if isinstance(entry.get("pages"), dict) else {}
    backing_write = any(str(v).strip().lower() == "backing" for v in pages.values() if v)
    user_nav_backing = str(session.get("_music_user_navigated_page_this_run") or "").strip().lower() == "backing"
    if backing_write and not user_nav_backing:
        _record_violation(
            session,
            code="PHASE1_CREATIVE_OVERWRITTEN_AFTER_CONFIRMATION",
            detail={"subsequent_write": entry, "confirmed_revision": confirmed_rev},
        )
    if (
        confirmed_rev is not None
        and entry.get("revision") is not None
        and int(entry["revision"]) <= int(confirmed_rev)
        and backing_write
    ):
        _record_violation(
            session,
            code="PHASE1_STALE_REVISION_BACKING_WRITE",
            detail={"subsequent_write": entry, "confirmed_revision": confirmed_rev},
        )


def record_fresh_hydration(
    session: dict[str, Any],
    payload: dict[str, Any] | None,
    *,
    fetch_source: str,
    cloud_key: str = "",
    used_cache: bool = False,
    selected_page: str = "",
    selection_reason: str = "",
) -> None:
    if not durability_trace_enabled(session):
        return
    bucket = _ensure_bucket(session)
    data = payload if isinstance(payload, dict) else {}
    bucket["fresh_hydration"] = {
        "fetch_source": fetch_source,
        "used_session_cache": used_cache,
        "cloud_key": cloud_key or _cloud_context(session).get("cloud_document_path"),
        "revision": _revision_from_state(data),
        "pages": page_fields_from_state(data),
        "selected_page": selected_page or None,
        "selection_reason": selection_reason or None,
    }
    classify_failure(session)


def record_cloud_fetch_event(
    session: dict[str, Any],
    *,
    app_id: str,
    force: bool,
    from_session_cache: bool,
    fetch_source: str,
) -> None:
    if not durability_trace_enabled(session):
        return
    bucket = _ensure_bucket(session)
    bucket["last_cloud_fetch"] = {
        "app_id": app_id,
        "force": force,
        "from_session_cache": from_session_cache,
        "fetch_source": fetch_source,
    }


def _record_violation(session: dict[str, Any], *, code: str, detail: dict[str, Any]) -> None:
    viol = {"code": code, "detail": detail}
    bucket = _ensure_bucket(session)
    bucket.setdefault("violations", []).append(viol)
    prev = session.get(_VIOLATIONS_KEY)
    if not isinstance(prev, list):
        prev = []
    prev.append(viol)
    session[_VIOLATIONS_KEY] = prev


def classify_failure(session: dict[str, Any]) -> str | None:
    bucket = session.get(PAGE_CLOUD_DURABILITY_TRACE_KEY)
    if not isinstance(bucket, dict):
        return None
    evaluate_durability_transaction_integrity(session)
    txs = bucket.get("transactions") if isinstance(bucket.get("transactions"), list) else []
    tx = _active_tx(session) or (txs[-1] if txs else {})
    attempted = tx.get("attempted_upsert") if isinstance(tx, dict) else None
    supa = tx.get("supabase_response") if isinstance(tx, dict) else None
    conf = tx.get("confirmation") or session.get(AUTHORITATIVE_CONFIRMATION_DETAIL_KEY)
    hydrate = bucket.get("fresh_hydration")
    violations = bucket.get("violations") or []

    failure: str | None = None
    first_mismatch: str | None = None

    tx = _active_tx(session)
    if tx and tx.get("early_exit"):
        exit_reason = str((tx.get("early_exit") or {}).get("reason") or "")
        if "startup_suppression" in exit_reason:
            failure = bucket.get("startup_release_failure_hint") or (
                "8_page_change_blocked_by_false_startup_page_mismatch"
            )
            first_mismatch = "startup_release_queued_page"
    if failure is None and isinstance(violations, list) and any(
        isinstance(v, dict) and v.get("code") == "PHASE1_CREATIVE_OVERWRITTEN_AFTER_CONFIRMATION"
        for v in violations
    ):
        failure = "5_authoritative_creative_then_backing_overwrite"
        first_mismatch = "subsequent_write"
    elif failure is None and not txs and _phase1_genuine_user_page_write(session):
        failure = "diagnostic_transaction_missing"
        first_mismatch = "durability_transaction_journal"
    elif failure is None and isinstance(hydrate, dict) and not txs:
        hint = bucket.get("startup_release_failure_hint")
        if hint:
            failure = str(hint)
            first_mismatch = "startup_release_queued_page"
        elif _phase1_genuine_user_page_write(session):
            failure = "diagnostic_transaction_missing"
            first_mismatch = "durability_transaction_journal"
    elif failure is None and isinstance(hydrate, dict):
        pages = hydrate.get("pages") if isinstance(hydrate.get("pages"), dict) else {}
        if any(str(v).strip().lower() == "backing" for v in pages.values() if v):
            if not txs and _phase1_genuine_user_page_write(session):
                failure = "diagnostic_transaction_missing"
                first_mismatch = "durability_transaction_journal"
            elif hydrate.get("used_session_cache"):
                failure = "6_cloud_creative_but_cache_backing"
                first_mismatch = "fresh_hydration_cache"
            elif isinstance(conf, dict) and conf.get("confirmed"):
                failure = "5_authoritative_creative_then_backing_overwrite"
                first_mismatch = "fresh_hydration_network"
            elif not attempted:
                failure = "1_creative_never_reached_supabase"
                first_mismatch = "no_attempted_upsert"
            elif isinstance(supa, dict) and not supa.get("success"):
                failure = "1_creative_never_reached_supabase"
                first_mismatch = "supabase_failed"
            elif isinstance(conf, dict) and conf.get("checks", {}).get("not_reusing_legacy_revision_only") is False:
                failure = "4_confirmation_reused_revision_191"
                first_mismatch = "confirmation"
            elif isinstance(conf, dict) and not conf.get("confirmed"):
                failure = "3_upsert_ok_but_stored_backing"
                first_mismatch = "authoritative_refetch"
            else:
                failure = "7_envelope_location_mismatch"
                first_mismatch = "hydration_page_fields"

    bucket["failure_class"] = failure
    bucket["first_mismatch_stage"] = first_mismatch
    return failure


def authoritative_page_change_cloud_confirmed(session: dict[str, Any]) -> bool:
    detail = session.get(AUTHORITATIVE_CONFIRMATION_DETAIL_KEY)
    if isinstance(detail, dict):
        return bool(detail.get("confirmed"))
    return False


def build_durability_copy_block(session: dict[str, Any]) -> str:
    classify_failure(session)
    bucket = session.get(PAGE_CLOUD_DURABILITY_TRACE_KEY)
    if not isinstance(bucket, dict):
        bucket = {}
    payload = {
        "page_cloud_durability_trace": bucket,
        "impl_marker": PAGE_CLOUD_DURABILITY_IMPL_MARKER,
        "authoritative_page_change_cloud_confirmed": authoritative_page_change_cloud_confirmed(session),
        "legacy_suite_persist_last_save_cloud": session.get("_suite_persist_last_save_cloud"),
        "legacy_confirmed_revision": session.get("_music_last_confirmed_cloud_revision"),
    }
    return json.dumps(payload, indent=2, default=str)


def finalize_page_change_cloud_durability_trace(session: dict[str, Any], *, save_reason: str) -> None:
    """Post-save authoritative refetch for diagnostics (does not alter egress confirmation)."""
    if str(save_reason or "").strip() != "page_change" or not durability_trace_enabled(session):
        return
    if not _active_tx(session):
        return
    try:
        from suite_cloud_state import load_cloud_full_session

        readback, _ts = load_cloud_full_session("music", force=True)
        record_authoritative_refetch(
            session,
            readback if isinstance(readback, dict) else {},
            force=True,
            cache_bypassed=True,
            fetch_source="post_save_force_network",
        )
    except Exception:
        record_authoritative_refetch(
            session,
            {},
            force=True,
            cache_bypassed=False,
            fetch_source="post_save_refetch_failed",
        )
    target = str(
        session.get("_music_user_navigated_page_this_run") or session.get("studio_page") or "creative"
    ).strip()
    evaluate_authoritative_page_change_confirmation(session, target_page=target or "creative")
    detail = session.get(AUTHORITATIVE_CONFIRMATION_DETAIL_KEY)
    if isinstance(detail, dict) and detail.get("confirmed"):
        _complete_active_transaction(session, "authoritative_confirmed")
    else:
        _complete_active_transaction(session, "authoritative_not_confirmed")


def durability_journal_payload(session: dict[str, Any]) -> dict[str, Any]:
    """JSON-safe payload for sidebar + copyable journal; never omits the key."""
    base: dict[str, Any] = {
        "ui_marker": PAGE_CLOUD_DURABILITY_UI_MARKER,
        "impl_marker": PAGE_CLOUD_DURABILITY_IMPL_MARKER,
        "module_import_ok": True,
    }
    integrity = evaluate_durability_transaction_integrity(session)
    base["diagnostic_integrity"] = integrity
    merge_queued_release_trace_into_payload(base, session)
    try:
        bucket = session.get(PAGE_CLOUD_DURABILITY_TRACE_KEY)
        has_tx = isinstance(bucket, dict) and bool(bucket.get("transactions"))
        if not has_tx:
            classify_failure(session)
            base["status"] = "no_page_change_transaction_recorded"
            base["page_cloud_durability_trace"] = bucket if isinstance(bucket, dict) else {}
            base["authoritative_page_change_cloud_confirmed"] = authoritative_page_change_cloud_confirmed(
                session
            )
            base["legacy_suite_persist_last_save_cloud"] = session.get("_suite_persist_last_save_cloud")
            base["legacy_confirmed_revision"] = session.get("_music_last_confirmed_cloud_revision")
            base["failure_class"] = (
                bucket.get("failure_class") if isinstance(bucket, dict) else None
            )
            return base
        parsed = json.loads(build_durability_copy_block(session))
        if isinstance(parsed, dict):
            parsed["ui_marker"] = PAGE_CLOUD_DURABILITY_UI_MARKER
            parsed["module_import_ok"] = True
            parsed["diagnostic_integrity"] = integrity
            parsed["status"] = "ok"
            merge_queued_release_trace_into_payload(parsed, session)
            return parsed
        base["status"] = "invalid_trace_payload"
        return base
    except Exception as exc:
        return {
            **base,
            "status": "durability_trace_build_error",
            "error": str(exc),
            "page_cloud_durability_trace": session.get(PAGE_CLOUD_DURABILITY_TRACE_KEY),
        }


def render_page_cloud_durability_trace_section(st: Any, session: dict[str, Any]) -> None:
    """Always visible in dev journal expander."""
    st.markdown("**Page cloud durability trace**")
    payload = durability_journal_payload(session)
    integrity = payload.get("diagnostic_integrity")
    if isinstance(integrity, dict):
        st.caption(
            f"integrity: hook_called={integrity.get('transaction_start_hook_called')} "
            f"tx_count={integrity.get('transaction_count')} "
            f"storage={integrity.get('journal_storage')} "
            f"resets={integrity.get('journal_reset_count')}"
        )
    if payload.get("status") == "no_page_change_transaction_recorded":
        st.json({"status": "no_page_change_transaction_recorded", "diagnostic_integrity": integrity})
    elif payload.get("status") == "durability_trace_build_error":
        st.error(f"Durability trace error: {payload.get('error')}")
        st.json({"status": "durability_trace_build_error", "error": payload.get("error")})
    failure = payload.get("failure_class") or (
        (session.get(PAGE_CLOUD_DURABILITY_TRACE_KEY) or {}).get("failure_class")
        if isinstance(session.get(PAGE_CLOUD_DURABILITY_TRACE_KEY), dict)
        else None
    )
    if failure:
        st.warning(f"Cloud durability failure class: {failure}")
    viols = payload.get("violations")
    if not isinstance(viols, list):
        trace = session.get(PAGE_CLOUD_DURABILITY_TRACE_KEY)
        viols = trace.get("violations") if isinstance(trace, dict) else []
    for viol in viols or []:
        if isinstance(viol, dict):
            st.error(f"{viol.get('code')}: {viol.get('detail')}")
    st.code(json.dumps(payload, indent=2, default=str), language="json")

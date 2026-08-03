"""Authoritative network confirmation for explicit sidebar display_key_change saves."""

from __future__ import annotations

import copy
import time
from typing import Any

from display_key_sidebar_persistence_trace import (
    DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY,
    DISPLAY_KEY_SIDEBAR_TRACE_KEY,
    display_key_from_cloud_session_blob,
    is_explicit_sidebar_display_key_save,
    record_display_key_sidebar_stage,
    record_display_key_user_change_violation,
)

DISPLAY_KEY_CLOUD_WRITE_NOT_ATTEMPTED = "DISPLAY_KEY_CLOUD_WRITE_NOT_ATTEMPTED"
DISPLAY_KEY_CLOUD_UPSERT_FAILED = "DISPLAY_KEY_CLOUD_UPSERT_FAILED"
DISPLAY_KEY_CLOUD_CONFIRMATION_OLD_REVISION = "DISPLAY_KEY_CLOUD_CONFIRMATION_OLD_REVISION"
DISPLAY_KEY_CLOUD_CONFIRMATION_VALUE_MISMATCH = "DISPLAY_KEY_CLOUD_CONFIRMATION_VALUE_MISMATCH"
DISPLAY_KEY_CLOUD_CONFIRMATION_WRONG_WORKSPACE = "DISPLAY_KEY_CLOUD_CONFIRMATION_WRONG_WORKSPACE"
DISPLAY_KEY_CLOUD_CONFIRMATION_NOT_NETWORK = "DISPLAY_KEY_CLOUD_CONFIRMATION_NOT_NETWORK"

_CONFIRMATION_RETRIES = 3
_CONFIRMATION_RETRY_DELAY_SEC = 0.35


def _cloud_identity(session: dict[str, Any]) -> dict[str, str]:
    try:
        from creative_selector_save_durability_trace import _cloud_identity as _sel_identity

        return _sel_identity(session)
    except ImportError:
        pass
    workspace = str(session.get("_suite_active_workspace") or session.get("suite_active_workspace") or "").strip()
    account = str(session.get("_suite_cloud_workspace_key") or session.get("_music_cloud_workspace_key") or "").strip()
    return {"app_id": "music", "account_or_key": account, "workspace_id": workspace}


def _loaded_revision(session: dict[str, Any]) -> int | None:
    active = session.get(DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY)
    if isinstance(active, dict) and active.get("revision_loaded_before_edit") is not None:
        try:
            return int(active["revision_loaded_before_edit"])
        except (TypeError, ValueError):
            pass
    for key in (
        "_suite_applied_workspace_revision",
        "_music_startup_revision_loaded",
        "_suite_cloud_workspace_revision",
        "startup_revision_loaded",
    ):
        try:
            if session.get(key) is not None:
                return int(session.get(key))
        except (TypeError, ValueError):
            continue
    return None


def _workspace_save_transaction(session: dict[str, Any]) -> dict[str, Any]:
    tx = session.get("_music_workspace_save_transaction")
    merged: dict[str, Any] = dict(tx) if isinstance(tx, dict) else {}
    for src_key in ("_music_last_cloud_save_diag", "_suite_last_cloud_save_result"):
        src = session.get(src_key)
        if isinstance(src, dict):
            for k, v in src.items():
                if v is not None and k not in merged:
                    merged[k] = v
    merged.setdefault("save_music_cloud_session_return_value", session.get("_music_last_cloud_write_ok"))
    return merged


def record_display_key_payload_before_upsert(session: dict[str, Any], state: dict[str, Any]) -> None:
    if not is_explicit_sidebar_display_key_save("display_key_change", session):
        return
    active = session.get(DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY)
    if not isinstance(active, dict):
        return
    core = state.get("core") if isinstance(state.get("core"), dict) else {}
    ass = state.get("active_song_state") if isinstance(state.get("active_song_state"), dict) else {}
    payload_dk = str((ass or {}).get("display_key") or (core or {}).get("display_key") or "").strip()
    try:
        from workspace_revision import workspace_revision_from_blob

        rev = workspace_revision_from_blob(state)
    except ImportError:
        rev = None
    active["payload_before_upsert"] = {
        "payload_core_display_key": payload_dk or None,
        "payload_revision": rev,
        "cloud_identity": _cloud_identity(session),
    }
    session[DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY] = active


def record_display_key_supabase_result(session: dict[str, Any], *, saved: bool) -> None:
    if not is_explicit_sidebar_display_key_save("display_key_change", session):
        return
    active = session.get(DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY)
    if not isinstance(active, dict):
        return
    diag = session.get("_music_last_cloud_save_diag")
    if not isinstance(diag, dict):
        diag = {}
    upsert_ok = diag.get("cloud_upsert_succeeded")
    if upsert_ok is None:
        upsert_ok = bool(saved and diag.get("cloud_upsert_attempted", True))
    active["supabase_result"] = {
        "cloud_write_attempted": bool(
            diag.get("cloud_upsert_attempted")
            or (session.get("_music_workspace_save_transaction") or {}).get("cloud_write_attempted")
            or saved
        ),
        "cloud_upsert_succeeded": bool(upsert_ok),
        "save_music_cloud_session_return_value": bool(saved),
        "supabase_response_status": diag.get("supabase_response_status"),
        "cloud_payload_revision": diag.get("cloud_payload_revision"),
        "failure_stage": diag.get("save_cloud_full_session_failure_stage"),
        "exception": diag.get("save_cloud_full_session_exception"),
        "cloud_write_error": session.get("_music_last_cloud_write_error"),
    }
    session[DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY] = active


def _store_confirmation_forensic(session: dict[str, Any], detail: dict[str, Any]) -> None:
    trace = session.get(DISPLAY_KEY_SIDEBAR_TRACE_KEY)
    if not isinstance(trace, dict):
        trace = {}
        session[DISPLAY_KEY_SIDEBAR_TRACE_KEY] = trace
    trace["confirmation_forensic"] = copy.deepcopy(detail)
    trace["save_transaction"] = enrich_display_key_save_transaction(session)


def enrich_display_key_save_transaction(
    session: dict[str, Any],
    *,
    force_save_return: Any = None,
    save_exception: str = "",
) -> dict[str, Any]:
    """Merge workspace save tx + cloud session return into sidebar trace save_transaction."""
    try:
        from display_key_sidebar_persistence_trace import sync_sidebar_trace_from_workspace_save

        sync_sidebar_trace_from_workspace_save(session)
    except ImportError:
        pass
    trace = session.get(DISPLAY_KEY_SIDEBAR_TRACE_KEY)
    tx = _workspace_save_transaction(session)
    if isinstance(trace, dict) and isinstance(trace.get("save_transaction"), dict):
        for k, v in trace["save_transaction"].items():
            if v is not None and k not in tx:
                tx[k] = v
    if force_save_return is not None:
        tx["force_save_music_state_return_value"] = force_save_return
        tx["force_save_music_state_return_type"] = type(force_save_return).__name__
    smc = session.get("_music_last_cloud_write_ok")
    if smc is not None:
        tx["save_music_cloud_session_return_value"] = smc
        tx["save_music_cloud_session_return_type"] = type(smc).__name__
    elif tx.get("cloud_write_attempted"):
        tx.setdefault("save_music_cloud_session_return_value", False)
        tx.setdefault("save_music_cloud_session_return_type", "bool")
    if save_exception:
        tx["save_exception"] = save_exception
    if isinstance(trace, dict):
        trace["save_transaction"] = copy.deepcopy(tx)
        session[DISPLAY_KEY_SIDEBAR_TRACE_KEY] = trace
    return tx


def record_display_key_confirmation_not_attempted(
    session: dict[str, Any],
    *,
    save_reason: str,
    detail: str,
    tx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    identity = _cloud_identity(session)
    tx = tx if isinstance(tx, dict) else _workspace_save_transaction(session)
    active = session.get(DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY)
    tx_id = None
    if isinstance(active, dict):
        tx_id = active.get("transaction_id")
    forensic: dict[str, Any] = {
        "attempted": False,
        "confirmed": False,
        "failure_code": DISPLAY_KEY_CLOUD_WRITE_NOT_ATTEMPTED,
        "reason": save_reason,
        "failure_detail": detail,
        "transaction_id": tx_id or tx.get("transaction_id"),
        "workspace_account_key": identity.get("account_or_key"),
        "workspace_id": identity.get("workspace_id"),
        "strict_egress_plan_action": tx.get("strict_egress_plan_action"),
        "duplicate_write_skipped": tx.get("duplicate_write_skipped"),
        "reserved_write_revision": tx.get("reserved_write_revision"),
        "payload_revision": tx.get("envelope_revision_after") or tx.get("payload_revision"),
        "payload_core_display_key": tx.get("payload_core_display_key"),
        "cloud_write_attempted": bool(tx.get("cloud_write_attempted")),
        "cloud_upsert_succeeded": tx.get("cloud_upsert_succeeded"),
        "cloud_write_error": tx.get("cloud_write_error") or session.get("_music_last_cloud_write_error"),
        "save_music_cloud_session_return_value": tx.get("save_music_cloud_session_return_value"),
        "force_save_early_return_reason": tx.get("force_save_early_return_reason"),
        "force_save_block_reason": tx.get("force_save_block_reason") or session.get("_music_force_save_blocked_reason"),
    }
    _store_confirmation_forensic(session, forensic)
    record_display_key_user_change_violation(
        session,
        detail,
        violation_code=DISPLAY_KEY_CLOUD_WRITE_NOT_ATTEMPTED,
        **forensic,
    )
    record_display_key_sidebar_stage(
        session,
        "forced_network_confirmation",
        reason=save_reason,
        cloud_save_ok=False,
        confirmation_forensic=forensic,
    )
    return forensic


def finalize_display_key_sidebar_save_outcome(
    st: Any,
    *,
    transaction_id: str = "",
    caller: str = "",
    force_save_return: Any = None,
    save_exception: str = "",
) -> bool:
    """After force_save_music_state: merge tx diagnostics, confirm or record why not."""
    session = st.session_state
    save_reason = "display_key_change"
    tx_id = str(transaction_id or "").strip()
    tx = enrich_display_key_save_transaction(
        session,
        force_save_return=force_save_return,
        save_exception=save_exception,
    )
    trace = session.get(DISPLAY_KEY_SIDEBAR_TRACE_KEY)
    existing = trace.get("confirmation_forensic") if isinstance(trace, dict) else None
    if isinstance(existing, dict) and existing.get("confirmed"):
        try:
            from display_key_sidebar_persistence_trace import disarm_explicit_sidebar_display_key_save

            disarm_explicit_sidebar_display_key_save(session)
        except ImportError:
            session.pop(DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY, None)
        return True

    if tx.get("cloud_confirmed") is True and tx.get("cloud_write_attempted"):
        if not isinstance(existing, dict) or not existing.get("confirmed"):
            identity = _cloud_identity(session)
            forensic = {
                "attempted": True,
                "confirmed": True,
                "reason": save_reason,
                "transaction_id": tx_id or tx.get("transaction_id"),
                "workspace_account_key": identity.get("account_or_key"),
                "comparison": "cloud_confirmed_in_save_transaction",
                **{k: tx.get(k) for k in (
                    "strict_egress_plan_action",
                    "duplicate_write_skipped",
                    "reserved_write_revision",
                    "payload_core_display_key",
                    "cloud_write_attempted",
                    "cloud_upsert_succeeded",
                    "save_music_cloud_session_return_value",
                )},
            }
            _store_confirmation_forensic(session, forensic)
        try:
            from display_key_sidebar_persistence_trace import disarm_explicit_sidebar_display_key_save

            disarm_explicit_sidebar_display_key_save(session)
        except ImportError:
            session.pop(DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY, None)
        return True

    upsert_attempted = bool(tx.get("cloud_write_attempted"))
    block = (
        str(session.get("_music_force_save_blocked_reason") or "").strip()
        or str(tx.get("force_save_early_return_reason") or "").strip()
        or str(tx.get("force_save_block_reason") or "").strip()
        or str(save_exception or "").strip()
        or "cloud_save_path_did_not_complete"
    )

    ok = False
    if not upsert_attempted:
        try:
            from display_key_startup_save_queue import (
                maybe_queue_display_key_save_blocked_by_startup,
            )

            maybe_queue_display_key_save_blocked_by_startup(
                session,
                block_reason=block,
                transaction_id=tx_id,
            )
        except ImportError:
            pass
        record_display_key_confirmation_not_attempted(
            session,
            save_reason=save_reason,
            detail=block,
            tx=tx,
        )
    elif isinstance(existing, dict) and existing.get("failure_code") and not existing.get("confirmed"):
        ok = False
    else:
        ok_auth, _forensic = attempt_explicit_display_key_authoritative_confirmation(
            session,
            st=st,
            save_reason=save_reason,
            expected_display_key=str(session.get("display_key") or ""),
        )
        ok = ok_auth

    if not ok:
        trace = session.get(DISPLAY_KEY_SIDEBAR_TRACE_KEY)
        violations = trace.get("violations") if isinstance(trace, dict) else None
        if not isinstance(violations, list) or not violations:
            forensic = trace.get("confirmation_forensic") if isinstance(trace, dict) else {}
            code = DISPLAY_KEY_CLOUD_WRITE_NOT_ATTEMPTED
            detail = block
            if isinstance(forensic, dict) and forensic.get("failure_code"):
                code = str(forensic.get("failure_code"))
                detail = str(forensic.get("failure_detail") or block)
            record_display_key_user_change_violation(
                session,
                detail,
                violation_code=code,
            )

    try:
        from display_key_sidebar_persistence_trace import disarm_explicit_sidebar_display_key_save
        from display_key_startup_save_queue import has_queued_display_key_change

        if not has_queued_display_key_change(session):
            disarm_explicit_sidebar_display_key_save(session)
    except ImportError:
        session.pop(DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY, None)

    try:
        from display_key_sidebar_save_pipeline import resolve_display_key_cloud_save_ok

        ok_resolved, _detail = resolve_display_key_cloud_save_ok(session)
        if ok:
            return True
        return ok_resolved
    except ImportError:
        return bool(ok)


def attempt_explicit_display_key_authoritative_confirmation(
    session: dict[str, Any],
    *,
    st: Any | None = None,
    save_reason: str,
    expected_display_key: str,
    payload_state: dict[str, Any] | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Confirm display_key from Supabase upsert + forced network refetch (bounded retry)."""
    expected = str(expected_display_key or session.get("display_key") or "").strip()
    active = session.get(DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY)
    if not isinstance(active, dict):
        active = {}
    tx = _workspace_save_transaction(session)
    reserved_raw = tx.get("reserved_write_revision") or active.get("reserved_revision")
    try:
        reserved_rev = int(reserved_raw) if reserved_raw is not None else None
    except (TypeError, ValueError):
        reserved_rev = None
    if reserved_rev is None and isinstance(payload_state, dict):
        try:
            from workspace_revision import workspace_revision_from_blob

            reserved_rev = workspace_revision_from_blob(payload_state)
        except ImportError:
            pass
    loaded_before = _loaded_revision(session)
    identity = _cloud_identity(session)

    upsert_attempted = bool(tx.get("cloud_write_attempted"))
    supabase = active.get("supabase_result") if isinstance(active.get("supabase_result"), dict) else {}
    if supabase.get("cloud_write_attempted") is not None:
        upsert_attempted = bool(supabase.get("cloud_write_attempted"))
    upsert_ok = bool(supabase.get("cloud_upsert_succeeded")) if supabase else bool(tx.get("cloud_upsert_succeeded"))

    forensic: dict[str, Any] = {
        "transaction_id": active.get("transaction_id") or tx.get("transaction_id"),
        "workspace_account_key": identity.get("account_or_key"),
        "workspace_id": identity.get("workspace_id"),
        "reason": save_reason,
        "explicit_sidebar_display_key_save": True,
        "strict_egress_plan_action": tx.get("strict_egress_plan_action"),
        "duplicate_write_skipped": tx.get("duplicate_write_skipped"),
        "payload_changed": tx.get("payload_changed_since_last_confirmed_save"),
        "strict_approved": tx.get("strict_egress_approved"),
        "reserved_write_revision": reserved_rev,
        "payload_revision": (active.get("payload_before_upsert") or {}).get("payload_revision")
        if isinstance(active.get("payload_before_upsert"), dict)
        else tx.get("envelope_revision_after"),
        "payload_core_display_key": (active.get("payload_before_upsert") or {}).get("payload_core_display_key")
        if isinstance(active.get("payload_before_upsert"), dict)
        else tx.get("payload_core_display_key"),
        "cloud_write_attempted": upsert_attempted,
        "save_music_cloud_session_return_value": supabase.get("save_music_cloud_session_return_value")
        if supabase
        else tx.get("save_music_cloud_session_return_value"),
        "cloud_upsert_succeeded": upsert_ok,
        "cloud_write_error": supabase.get("cloud_write_error") if supabase else tx.get("cloud_write_error"),
        "expected_display_key": expected,
        "expected_revision": reserved_rev,
        "revision_loaded_before_edit": loaded_before,
        "confirmation_attempts": [],
    }

    def _fail(code: str, detail: str, **extra: Any) -> tuple[bool, dict[str, Any]]:
        forensic["confirmed"] = False
        forensic["failure_code"] = code
        forensic["failure_detail"] = detail
        forensic.update({k: v for k, v in extra.items() if v is not None})
        _store_confirmation_forensic(session, forensic)
        record_display_key_user_change_violation(session, detail, violation_code=code, **forensic)
        record_display_key_sidebar_stage(
            session,
            "forced_network_confirmation",
            reason=save_reason,
            cloud_save_ok=False,
            confirmation_forensic=forensic,
        )
        return False, forensic

    if not upsert_attempted:
        forensic["attempted"] = False
        return _fail(
            DISPLAY_KEY_CLOUD_WRITE_NOT_ATTEMPTED,
            "cloud_write_not_attempted",
            comparison="no_upsert_before_confirmation",
        )
    if not upsert_ok:
        forensic["attempted"] = True
        return _fail(
            DISPLAY_KEY_CLOUD_UPSERT_FAILED,
            "cloud_upsert_not_succeeded",
            supabase_result=supabase or None,
        )
    forensic["attempted"] = True

    try:
        from suite_cloud_state import load_cloud_full_session
        from workspace_revision import workspace_revision_from_blob
    except ImportError as exc:
        return _fail(DISPLAY_KEY_CLOUD_UPSERT_FAILED, f"import_error:{exc}")

    last_fetch_source = ""
    last_fetched_key = ""
    last_fetched_rev: int | None = None

    for attempt in range(_CONFIRMATION_RETRIES):
        attempt_detail: dict[str, Any] = {"attempt": attempt + 1}
        try:
            readback, _ts = load_cloud_full_session("music", force=True)
        except Exception as exc:
            attempt_detail["error"] = str(exc)
            forensic["confirmation_attempts"].append(attempt_detail)
            continue
        fetch_source = str(session.get("_music_last_cloud_fetch_source") or "")
        attempt_detail["fetch_source"] = fetch_source
        last_fetch_source = fetch_source
        if fetch_source != "network":
            attempt_detail["network_forced"] = False
            forensic["confirmation_attempts"].append(attempt_detail)
            if attempt + 1 >= _CONFIRMATION_RETRIES:
                return _fail(
                    DISPLAY_KEY_CLOUD_CONFIRMATION_NOT_NETWORK,
                    f"refetch_source={fetch_source}",
                    fetch_source=fetch_source,
                    comparison="fetch_source_not_network",
                )
            time.sleep(_CONFIRMATION_RETRY_DELAY_SEC)
            continue

        ref_identity = _cloud_identity(session)
        if identity.get("workspace_id") and ref_identity.get("workspace_id"):
            if identity["workspace_id"] != ref_identity["workspace_id"]:
                return _fail(
                    DISPLAY_KEY_CLOUD_CONFIRMATION_WRONG_WORKSPACE,
                    "workspace_id_mismatch",
                    expected_workspace=identity.get("workspace_id"),
                    fetched_workspace=ref_identity.get("workspace_id"),
                    comparison="workspace_id_mismatch",
                )
        if identity.get("account_or_key") and ref_identity.get("account_or_key"):
            if identity["account_or_key"] != ref_identity["account_or_key"]:
                return _fail(
                    DISPLAY_KEY_CLOUD_CONFIRMATION_WRONG_WORKSPACE,
                    "account_key_mismatch",
                    expected_account=identity.get("account_or_key"),
                    fetched_account=ref_identity.get("account_or_key"),
                    comparison="account_key_mismatch",
                )

        fetched_key = display_key_from_cloud_session_blob(readback if isinstance(readback, dict) else {})
        last_fetched_key = fetched_key
        try:
            last_fetched_rev = workspace_revision_from_blob(readback if isinstance(readback, dict) else {})
        except Exception:
            last_fetched_rev = None
        attempt_detail["fetched_display_key"] = fetched_key or None
        attempt_detail["fetched_revision"] = last_fetched_rev

        rev_ok = False
        if reserved_rev is not None and last_fetched_rev is not None:
            rev_ok = last_fetched_rev >= reserved_rev
        elif last_fetched_rev is not None and loaded_before is not None:
            rev_ok = last_fetched_rev > loaded_before
        elif last_fetched_rev is not None:
            rev_ok = True

        key_ok = bool(expected and fetched_key == expected)
        attempt_detail["revision_ok"] = rev_ok
        attempt_detail["display_key_ok"] = key_ok
        forensic["confirmation_attempts"].append(attempt_detail)

        if key_ok and rev_ok:
            forensic["attempted"] = True
            forensic["confirmed"] = True
            forensic["fetch_source"] = "network"
            forensic["fetched_display_key"] = fetched_key
            forensic["fetched_revision"] = last_fetched_rev
            forensic["comparison"] = "revision_and_display_key_match"
            _store_confirmation_forensic(session, forensic)
            try:
                from music_egress_strict_save import note_confirmed_cloud_fingerprint
                from music_workspace_canonical_fingerprint import workspace_canonical_content_fingerprint

                if isinstance(readback, dict):
                    note_confirmed_cloud_fingerprint(session, workspace_canonical_content_fingerprint(readback))
            except ImportError:
                pass
            try:
                from workspace_revision import note_confirmed_workspace_revision

                if isinstance(readback, dict):
                    note_confirmed_workspace_revision(session, readback)
            except ImportError:
                pass
            record_display_key_sidebar_stage(
                session,
                "forced_network_confirmation",
                reason=save_reason,
                cloud_save_ok=True,
                network_refetch_display_key=fetched_key,
                fetched_revision=last_fetched_rev,
                confirmation_forensic=forensic,
            )
            session.pop(DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY, None)
            return True, forensic

        if not rev_ok and attempt + 1 < _CONFIRMATION_RETRIES:
            time.sleep(_CONFIRMATION_RETRY_DELAY_SEC)
            continue
        if not rev_ok:
            return _fail(
                DISPLAY_KEY_CLOUD_CONFIRMATION_OLD_REVISION,
                f"expected>={reserved_rev} got={last_fetched_rev}",
                fetched_revision=last_fetched_rev,
                fetched_display_key=fetched_key or None,
                fetch_source=last_fetch_source,
                comparison=f"revision_stale expected>={reserved_rev} fetched={last_fetched_rev}",
            )
        return _fail(
            DISPLAY_KEY_CLOUD_CONFIRMATION_VALUE_MISMATCH,
            f"expected={expected} fetched={fetched_key}",
            fetched_revision=last_fetched_rev,
            fetched_display_key=fetched_key or None,
            fetch_source=last_fetch_source,
            comparison=f"display_key expected={expected} fetched={fetched_key}",
        )

    return _fail(
        DISPLAY_KEY_CLOUD_CONFIRMATION_NOT_NETWORK,
        "exhausted_retries",
        fetch_source=last_fetch_source,
        fetched_display_key=last_fetched_key or None,
        fetched_revision=last_fetched_rev,
    )


__all__ = [
    "DISPLAY_KEY_CLOUD_CONFIRMATION_NOT_NETWORK",
    "DISPLAY_KEY_CLOUD_CONFIRMATION_OLD_REVISION",
    "DISPLAY_KEY_CLOUD_CONFIRMATION_VALUE_MISMATCH",
    "DISPLAY_KEY_CLOUD_CONFIRMATION_WRONG_WORKSPACE",
    "DISPLAY_KEY_CLOUD_UPSERT_FAILED",
    "DISPLAY_KEY_CLOUD_WRITE_NOT_ATTEMPTED",
    "attempt_explicit_display_key_authoritative_confirmation",
    "enrich_display_key_save_transaction",
    "finalize_display_key_sidebar_save_outcome",
    "record_display_key_confirmation_not_attempted",
    "record_display_key_payload_before_upsert",
    "record_display_key_supabase_result",
]

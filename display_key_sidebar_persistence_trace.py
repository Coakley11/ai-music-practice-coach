"""Trace explicit sidebar Display key changes vs Creative projection (?dev=1)."""

from __future__ import annotations

import copy
import uuid
from typing import Any

DISPLAY_KEY_SIDEBAR_TRACE_KEY = "_display_key_sidebar_user_change_trace"
DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY = "_display_key_sidebar_save_active"
DISPLAY_KEY_USER_CHANGE_NOT_COMMITTED = "DISPLAY_KEY_USER_CHANGE_NOT_COMMITTED"

_SAVE_TX_DIAG_KEYS: tuple[str, ...] = (
    "transaction_id",
    "force_save_reason",
    "raw_save_reason",
    "strict_egress_plan_action",
    "strict_egress_approved",
    "payload_changed_since_last_confirmed_save",
    "duplicate_write_skipped",
    "reserved_write_revision",
    "envelope_revision_after",
    "cloud_write_attempted",
    "cloud_write_succeeded",
    "cloud_upsert_succeeded",
    "cloud_confirmed",
    "cloud_readback_matches",
    "force_save_block_reason",
    "cloud_write_error",
    "workspace_account_key",
)

ORDERED_STAGES: tuple[str, ...] = (
    "callback_enter",
    "widget_value_read",
    "canonical_commit_start",
    "canonical_commit_end",
    "cloud_save_start",
    "cloud_save_end",
    "forced_network_confirmation",
    "next_rerun_projection",
)


def _trace(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(DISPLAY_KEY_SIDEBAR_TRACE_KEY)
    if isinstance(raw, dict):
        return raw
    d: dict[str, Any] = {"events": [], "violations": [], "stages": []}
    session[DISPLAY_KEY_SIDEBAR_TRACE_KEY] = d
    return d


def _canonical_display_key(session: dict[str, Any]) -> str:
    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY, canonical_active_song_context

        ctx = canonical_active_song_context(session)
        if isinstance(ctx, dict):
            return str(ctx.get("display_key") or "").strip()
    except ImportError:
        pass
    meta = session.get(ACTIVE_SONG_STATE_KEY)
    if isinstance(meta, dict):
        return str(meta.get("display_key") or "").strip()
    return ""


def _cloud_display_key_from_hydrated(session: dict[str, Any]) -> str:
    try:
        from music_startup_save_suppression import HYDRATED_PAYLOAD_SNAPSHOT_KEY

        snap = session.get(HYDRATED_PAYLOAD_SNAPSHOT_KEY)
        if isinstance(snap, dict):
            core = snap.get("core") if isinstance(snap.get("core"), dict) else {}
            ass = snap.get("active_song_state") if isinstance(snap.get("active_song_state"), dict) else {}
            for blob in (core, ass, snap):
                if isinstance(blob, dict):
                    dk = str(blob.get("display_key") or "").strip()
                    if dk:
                        return dk
    except ImportError:
        pass
    return ""


def _payload_core_display_key(session: dict[str, Any]) -> str:
    tx = session.get("_music_workspace_save_transaction")
    if isinstance(tx, dict):
        for key in ("payload_core_display_key", "core_display_key"):
            val = str(tx.get(key) or "").strip()
            if val:
                return val
    return ""


def active_sidebar_display_key_transaction_id(session: dict[str, Any]) -> str:
    d = session.get(DISPLAY_KEY_SIDEBAR_TRACE_KEY)
    if isinstance(d, dict):
        tx = str(d.get("active_transaction_id") or "").strip()
        if tx:
            return tx
    active = session.get(DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY)
    if isinstance(active, dict):
        return str(active.get("transaction_id") or "").strip()
    return ""


def arm_explicit_sidebar_display_key_save(
    session: dict[str, Any],
    *,
    transaction_id: str,
    selected_display_key: str,
    cloud_display_key_before: str = "",
    canonical_display_key_before: str = "",
) -> None:
    cloud_before = str(cloud_display_key_before or _cloud_display_key_from_hydrated(session) or "").strip()
    canon_before = str(canonical_display_key_before or _canonical_display_key(session) or "").strip()
    session[DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY] = {
        "transaction_id": str(transaction_id or "").strip() or None,
        "selected_display_key": str(selected_display_key or "").strip() or None,
        "cloud_display_key_before": cloud_before or None,
        "canonical_display_key_before": canon_before or None,
        "save_reason": "display_key_change",
        "source": "sidebar_on_change",
        "revision_loaded_before_edit": _revision_loaded_before_edit(session),
    }


def _revision_loaded_before_edit(session: dict[str, Any]) -> int | None:
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
    try:
        from workspace_revision import LAST_CONFIRMED_REVISION_KEY

        if session.get(LAST_CONFIRMED_REVISION_KEY) is not None:
            return int(session.get(LAST_CONFIRMED_REVISION_KEY))
    except ImportError:
        pass
    return None


def disarm_explicit_sidebar_display_key_save(session: dict[str, Any]) -> None:
    session.pop(DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY, None)


def is_explicit_sidebar_display_key_save(save_reason: str, session: dict[str, Any]) -> bool:
    reason = str(save_reason or "").strip()
    if reason not in ("display_key_change", "capo_widget"):
        try:
            from music_egress_config import normalize_music_save_reason

            if normalize_music_save_reason(reason) != "display_key_change":
                return False
        except ImportError:
            if reason != "display_key_change":
                return False
    active = session.get(DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY)
    if not isinstance(active, dict):
        return False
    src = str(session.get("display_key_change_source") or active.get("source") or "").strip()
    return src == "sidebar_on_change"


def should_force_display_key_cloud_write(
    session: dict[str, Any],
    *,
    save_reason: str,
    payload_fp: str = "",
) -> bool:
    if not is_explicit_sidebar_display_key_save(save_reason, session):
        return False
    active = session.get(DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY)
    if not isinstance(active, dict):
        return True
    before = str(active.get("cloud_display_key_before") or active.get("canonical_display_key_before") or "").strip()
    after = str(session.get("display_key") or active.get("selected_display_key") or "").strip()
    if before and after and before != after:
        return True
    if before and after and before == after:
        return False
    return bool(after)


def display_key_from_cloud_session_blob(blob: dict[str, Any]) -> str:
    if not isinstance(blob, dict):
        return ""
    for key in ("active_song_state", "core"):
        part = blob.get(key)
        if isinstance(part, dict):
            dk = str(part.get("display_key") or "").strip()
            if dk:
                return dk
    return str(blob.get("display_key") or "").strip()


def sync_sidebar_trace_from_workspace_save(session: dict[str, Any]) -> None:
    if not session.get("developer_mode"):
        return
    d = _trace(session)
    try:
        from display_key_sidebar_cloud_confirmation import _workspace_save_transaction

        summary = _workspace_save_transaction(session)
    except ImportError:
        summary = {}
    tx = session.get("_music_workspace_save_transaction")
    if isinstance(tx, dict):
        for k, v in tx.items():
            if v is not None and k not in summary:
                summary[k] = v
        core = tx.get("core") if isinstance(tx.get("core"), dict) else {}
        if isinstance(core, dict) and core.get("display_key"):
            summary.setdefault("payload_core_display_key", core.get("display_key"))
    d["save_transaction"] = summary
    sid = active_sidebar_display_key_transaction_id(session)
    if sid:
        d["active_transaction_id"] = sid
        summary.setdefault("transaction_id", sid)
    try:
        from music_workspace_cloud_save import collect_save_transaction_diagnostics

        extra = collect_save_transaction_diagnostics(session)
        if isinstance(extra, dict):
            for k in _SAVE_TX_DIAG_KEYS:
                if k not in summary and extra.get(k) is not None:
                    summary[k] = extra.get(k)
    except ImportError:
        pass


def _save_block_reason(session: dict[str, Any]) -> str:
    tx = session.get("_music_workspace_save_transaction")
    if isinstance(tx, dict):
        for key in ("force_save_block_reason", "cloud_write_error", "final_cloud_write_block_reason"):
            val = str(tx.get(key) or "").strip()
            if val:
                return val
    return str(session.get("_music_force_save_blocked_reason") or session.get("_music_last_cloud_write_error") or "").strip()


def _save_tx_fields(session: dict[str, Any]) -> dict[str, Any]:
    try:
        from music_workspace_cloud_save import collect_save_transaction_diagnostics

        tx = collect_save_transaction_diagnostics(session)
        if isinstance(tx, dict):
            out = {k: tx.get(k) for k in _SAVE_TX_DIAG_KEYS if tx.get(k) is not None}
            core = tx.get("core") if isinstance(tx.get("core"), dict) else {}
            if isinstance(core, dict) and core.get("display_key") and "payload_core_display_key" not in out:
                out["payload_core_display_key"] = core.get("display_key")
            sid = active_sidebar_display_key_transaction_id(session)
            if sid and "transaction_id" not in out:
                out["transaction_id"] = sid
            return out
    except ImportError:
        pass
    return {}


def begin_display_key_sidebar_transaction(session: dict[str, Any], *, caller: str = "") -> str:
    if not session.get("developer_mode"):
        return ""
    d = _trace(session)
    tx_id = str(uuid.uuid4())
    d["active_transaction_id"] = tx_id
    d["active_caller"] = str(caller or "").strip() or None
    return tx_id


def record_display_key_sidebar_stage(
    session: dict[str, Any],
    stage: str,
    *,
    caller: str = "",
    reason: str = "",
    **fields: Any,
) -> None:
    if not session.get("developer_mode"):
        return
    d = _trace(session)
    tx_id = str(d.get("active_transaction_id") or fields.get("transaction_id") or "").strip() or None
    entry = {
        "stage": stage,
        "transaction_id": tx_id,
        "caller": str(caller or d.get("active_caller") or "").strip() or None,
        "session_display_key": str(session.get("display_key") or "").strip() or None,
        "canonical_display_key": _canonical_display_key(session) or None,
        "display_key_change_source": str(session.get("display_key_change_source") or "").strip() or None,
        "reason": str(reason or "").strip() or None,
        **_save_tx_fields(session),
        **{k: v for k, v in fields.items() if v is not None},
    }
    stages = d.setdefault("stages", [])
    if isinstance(stages, list):
        stages.append(entry)
        if len(stages) > 60:
            del stages[:-60]


def record_display_key_sidebar_event(session: dict[str, Any], phase: str, **fields: Any) -> None:
    if not session.get("developer_mode"):
        return
    d = _trace(session)
    events = d.setdefault("events", [])
    if not isinstance(events, list):
        events = []
        d["events"] = events
    tx_id = str(d.get("active_transaction_id") or fields.get("transaction_id") or "").strip() or None
    entry = {
        "phase": phase,
        "transaction_id": tx_id,
        "session_display_key": str(session.get("display_key") or "").strip() or None,
        "canonical_display_key": _canonical_display_key(session) or None,
        "display_key_change_source": str(session.get("display_key_change_source") or "").strip() or None,
        **{k: v for k, v in fields.items() if v is not None},
    }
    events.append(entry)
    if len(events) > 40:
        del events[:-40]


def record_display_key_user_change_violation(
    session: dict[str, Any],
    detail: str,
    *,
    violation_code: str = DISPLAY_KEY_USER_CHANGE_NOT_COMMITTED,
    **fields: Any,
) -> None:
    if not session.get("developer_mode"):
        return
    d = _trace(session)
    violations = d.setdefault("violations", [])
    if not isinstance(violations, list):
        violations = []
        d["violations"] = violations
    entry = {
        "code": str(violation_code or DISPLAY_KEY_USER_CHANGE_NOT_COMMITTED).strip(),
        "detail": str(detail or "").strip() or "unknown",
        "session_display_key": str(session.get("display_key") or "").strip() or None,
        "canonical_display_key": _canonical_display_key(session) or None,
        **{k: v for k, v in fields.items() if v is not None},
    }
    violations.append(entry)


def audit_display_key_user_change_committed(
    session: dict[str, Any],
    *,
    callback_invoked: bool,
    cloud_save_requested: bool,
    cloud_save_ok: bool = False,
) -> None:
    if not session.get("developer_mode") or not callback_invoked:
        return
    if cloud_save_ok:
        return
    trace = session.get(DISPLAY_KEY_SIDEBAR_TRACE_KEY)
    if isinstance(trace, dict):
        violations = trace.get("violations")
        if isinstance(violations, list) and violations:
            return
        forensic = trace.get("confirmation_forensic")
        if isinstance(forensic, dict) and forensic.get("failure_code"):
            record_display_key_user_change_violation(
                session,
                str(forensic.get("failure_detail") or "cloud_save_failed"),
                violation_code=str(forensic.get("failure_code")),
                cloud_save_requested=cloud_save_requested,
                cloud_save_ok=False,
            )
            return
    live = str(session.get("display_key") or "").strip()
    canon = _canonical_display_key(session)
    if live and canon and live != canon:
        record_display_key_user_change_violation(
            session,
            "session_display_key_differs_from_canonical_after_callback",
            cloud_save_requested=cloud_save_requested,
            cloud_save_ok=cloud_save_ok,
        )
        return
    if not cloud_save_requested:
        record_display_key_user_change_violation(
            session,
            "display_key_change_cloud_save_not_requested",
            violation_code=DISPLAY_KEY_USER_CHANGE_NOT_COMMITTED,
            cloud_save_requested=False,
            cloud_save_ok=False,
        )
        return
    try:
        from display_key_sidebar_cloud_confirmation import DISPLAY_KEY_CLOUD_WRITE_NOT_ATTEMPTED

        fallback_code = DISPLAY_KEY_CLOUD_WRITE_NOT_ATTEMPTED
    except ImportError:
        fallback_code = DISPLAY_KEY_USER_CHANGE_NOT_COMMITTED
    record_display_key_user_change_violation(
        session,
        str(session.get("_music_force_save_blocked_reason") or "display_key_cloud_save_failed"),
        violation_code=fallback_code,
        cloud_save_requested=cloud_save_requested,
        cloud_save_ok=False,
    )


def collect_display_key_sidebar_trace(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(DISPLAY_KEY_SIDEBAR_TRACE_KEY)
    if not isinstance(raw, dict):
        return {}
    out = copy.deepcopy(raw)
    events = out.get("events")
    if isinstance(events, list) and events:
        last = events[-1]
        if isinstance(last, dict):
            out["last_event"] = last.get("phase")
            for key in (
                "widget_before",
                "widget_after",
                "callback_invoked",
                "display_key_change_source",
                "session_display_key",
                "canonical_display_key",
                "skipped_projection",
                "resolver_key",
                "backing_key",
                "save_reason",
                "cloud_save_requested",
                "cloud_save_ok",
                "transaction_id",
            ):
                if key not in out and last.get(key) is not None:
                    out[key] = last.get(key)
    stages = out.get("stages")
    if isinstance(stages, list) and stages:
        out["last_stage"] = stages[-1].get("stage") if isinstance(stages[-1], dict) else None
        last_stage = stages[-1] if isinstance(stages[-1], dict) else {}
        for key in (
            "cloud_save_requested",
            "cloud_save_ok",
            "transaction_id",
            "strict_egress_plan_action",
            "duplicate_write_skipped",
            "reserved_write_revision",
            "payload_core_display_key",
            "block_reason",
            "confirmation_forensic",
        ):
            if key not in out and last_stage.get(key) is not None:
                out[key] = last_stage.get(key)
    if isinstance(out.get("confirmation_forensic"), dict):
        out.setdefault("save_transaction", {})
        if isinstance(out["save_transaction"], dict):
            for k, v in out["confirmation_forensic"].items():
                if k not in out["save_transaction"] and v is not None:
                    out["save_transaction"][k] = v
    save_tx = out.get("save_transaction")
    if isinstance(save_tx, dict):
        out.setdefault("transaction_id", save_tx.get("transaction_id"))
        for key in ("cloud_write_succeeded", "cloud_confirmed", "payload_core_display_key"):
            if key not in out and save_tx.get(key) is not None:
                out[key] = save_tx.get(key)
    try:
        from display_key_sidebar_save_pipeline import DISPLAY_KEY_SAVE_PIPELINE_KEY

        pipe = session.get(DISPLAY_KEY_SAVE_PIPELINE_KEY)
        if isinstance(pipe, dict) and pipe.get("steps"):
            out["save_pipeline"] = copy.deepcopy(pipe)
    except ImportError:
        pass
    return out


__all__ = [
    "DISPLAY_KEY_SIDEBAR_TRACE_KEY",
    "DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY",
    "DISPLAY_KEY_USER_CHANGE_NOT_COMMITTED",
    "ORDERED_STAGES",
    "active_sidebar_display_key_transaction_id",
    "arm_explicit_sidebar_display_key_save",
    "audit_display_key_user_change_committed",
    "begin_display_key_sidebar_transaction",
    "collect_display_key_sidebar_trace",
    "disarm_explicit_sidebar_display_key_save",
    "display_key_from_cloud_session_blob",
    "is_explicit_sidebar_display_key_save",
    "record_display_key_sidebar_event",
    "record_display_key_sidebar_stage",
    "record_display_key_user_change_violation",
    "should_force_display_key_cloud_write",
    "sync_sidebar_trace_from_workspace_save",
]

"""Trace explicit sidebar Display key changes vs Creative projection (?dev=1)."""

from __future__ import annotations

import copy
import uuid
from typing import Any

DISPLAY_KEY_SIDEBAR_TRACE_KEY = "_display_key_sidebar_user_change_trace"
DISPLAY_KEY_USER_CHANGE_NOT_COMMITTED = "DISPLAY_KEY_USER_CHANGE_NOT_COMMITTED"

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


def _save_tx_fields(session: dict[str, Any]) -> dict[str, Any]:
    try:
        from music_workspace_cloud_save import collect_save_transaction_diagnostics

        tx = collect_save_transaction_diagnostics(session)
        if isinstance(tx, dict):
            return {
                k: tx.get(k)
                for k in (
                    "transaction_id",
                    "save_reason",
                    "reserved_revision",
                    "confirmed_revision",
                    "cloud_save_ok",
                    "payload_core_display_key",
                    "network_refetch_display_key",
                )
                if tx.get(k) is not None
            }
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


def record_display_key_user_change_violation(session: dict[str, Any], detail: str, **fields: Any) -> None:
    if not session.get("developer_mode"):
        return
    d = _trace(session)
    violations = d.setdefault("violations", [])
    if not isinstance(violations, list):
        violations = []
        d["violations"] = violations
    entry = {
        "code": DISPLAY_KEY_USER_CHANGE_NOT_COMMITTED,
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
) -> None:
    if not session.get("developer_mode") or not callback_invoked:
        return
    live = str(session.get("display_key") or "").strip()
    canon = _canonical_display_key(session)
    if live and canon and live != canon:
        record_display_key_user_change_violation(
            session,
            "session_display_key_differs_from_canonical_after_callback",
            cloud_save_requested=cloud_save_requested,
        )
    elif not cloud_save_requested:
        record_display_key_user_change_violation(
            session,
            "display_key_change_cloud_save_not_requested",
            cloud_save_requested=False,
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
    return out


__all__ = [
    "DISPLAY_KEY_SIDEBAR_TRACE_KEY",
    "DISPLAY_KEY_USER_CHANGE_NOT_COMMITTED",
    "ORDERED_STAGES",
    "audit_display_key_user_change_committed",
    "begin_display_key_sidebar_transaction",
    "collect_display_key_sidebar_trace",
    "record_display_key_sidebar_event",
    "record_display_key_sidebar_stage",
    "record_display_key_user_change_violation",
]

"""Strict egress: intentional user saves, debounce/coalesce, fingerprint dedupe."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

from music_egress_config import (
    is_intentional_user_save_reason,
    music_egress_strict_enabled,
    normalize_music_save_reason,
)

APP_ID = "music"
_STRICT_DEBOUNCE_SEC = 2.0

_PENDING_KEY = "_music_strict_save_pending"
_DUE_AT_KEY = "_music_strict_save_due_at"
_FIRST_QUEUED_KEY = "_music_strict_save_first_queued_at"
_LAST_EDIT_KEY = "_music_strict_save_last_edit_at"
_PENDING_FP_KEY = "_music_strict_pending_payload_fingerprint"
_PENDING_REASONS_KEY = "_music_strict_pending_save_reasons"
_DEADLINE_EXTENDED_KEY = "_music_strict_save_deadline_extended_by_new_edit"
_WAKEUP_SCHEDULED_KEY = "_music_strict_save_wakeup_scheduled"
_WAKEUP_RAN_KEY = "_music_strict_save_wakeup_ran"
_FLUSH_ATTEMPTED_KEY = "_music_strict_save_flush_attempted"
_FLUSH_RESULT_KEY = "_music_strict_save_flush_result"

_DEFER_REASON_KEY = "_music_strict_save_deferred_reason"
_COALESCE_COUNT_KEY = "_music_strict_edits_coalesced_count"
_CONFIRMED_FP_KEY = "_music_last_confirmed_cloud_fp"
_CLOUD_WRITE_TS_KEY = "_music_strict_cloud_write_ts"
_TX_WRITE_COUNT_KEY = "_music_strict_tx_cloud_write_count"
_TX_READ_COUNT_KEY = "_music_strict_tx_cloud_read_count"

# Discrete choices — cloud write on the same rerun (no debounce timer).
_DISCRETE_IMMEDIATE_SAVE_REASONS: frozenset[str] = frozenset(
    {
        "page_change",
        "song_edit",
        "section_change",
        "instrument_change",
        "level_change",
        "focus_change",
        "key_family_change",
        "fixed_key_mode_change",
        "practice_key_mode_change",
        "display_key_change",
        "practice_tool_select",
        "practice_workspace_edit",
        "time_pitch_view_change",
        "capo_change",
        "creative_edit",
        "cpl_draft_edit",
        "multitrack_upload",
        "multitrack_layer_save",
        "force_autosave",
        "insight_persist",
        "analysis_complete",
        "music_coach_send",
        "practice_edit",
    }
)

# Rapid controls — coalesce with fixed wake-up at ``strict_save_due_at``.
_DEBOUNCED_SAVE_REASONS: frozenset[str] = frozenset(
    {
        "backing_edit",
    }
)


def save_reason_uses_strict_debounce(save_reason: str) -> bool:
    reason = normalize_music_save_reason(save_reason)
    if reason in _DEBOUNCED_SAVE_REASONS:
        return True
    if reason in _DISCRETE_IMMEDIATE_SAVE_REASONS:
        return False
    return False


def workspace_payload_fingerprint(state: dict[str, Any]) -> str:
    """Canonical content fingerprint (revision/timestamps excluded)."""
    from music_workspace_canonical_fingerprint import workspace_canonical_content_fingerprint

    return workspace_canonical_content_fingerprint(state)


def last_confirmed_cloud_fingerprint(session: dict[str, Any]) -> str:
    fp = str(session.get(_CONFIRMED_FP_KEY) or "").strip()
    if fp:
        return fp
    try:
        from suite_user_persistence import _restored_fp_key

        restored = str(session.get(_restored_fp_key(APP_ID)) or "").strip()
    except ImportError:
        restored = ""
    return restored or str(session.get(f"_suite_autosave_fp::{APP_ID}") or "").strip()


def note_confirmed_cloud_fingerprint(session: dict[str, Any], fp: str) -> None:
    if fp:
        session[_CONFIRMED_FP_KEY] = fp


def reset_transaction_egress_counters(session: dict[str, Any]) -> None:
    session[_TX_WRITE_COUNT_KEY] = 0
    session[_TX_READ_COUNT_KEY] = 0


def bump_cloud_write_count(session: dict[str, Any]) -> int:
    n = int(session.get(_TX_WRITE_COUNT_KEY) or 0) + 1
    session[_TX_WRITE_COUNT_KEY] = n
    session[_CLOUD_WRITE_TS_KEY] = time.time()
    return n


def bump_cloud_read_count(session: dict[str, Any]) -> int:
    n = int(session.get(_TX_READ_COUNT_KEY) or 0) + 1
    session[_TX_READ_COUNT_KEY] = n
    return n


def strict_save_pending(session: dict[str, Any]) -> bool:
    return bool(session.get(_PENDING_KEY))


def strict_save_due_at(session: dict[str, Any]) -> float:
    try:
        return float(session.get(_DUE_AT_KEY) or 0)
    except (TypeError, ValueError):
        return 0.0


def _append_pending_reason(session: dict[str, Any], reason: str) -> None:
    reasons = session.get(_PENDING_REASONS_KEY)
    if not isinstance(reasons, list):
        reasons = []
    if reason and reason not in reasons:
        reasons.append(reason)
    session[_PENDING_REASONS_KEY] = reasons


def _record_strict_pending_diag(session: dict[str, Any], **fields: Any) -> None:
    tx = session.get("_music_workspace_save_transaction")
    if not isinstance(tx, dict):
        tx = {}
    tx.update({k: v for k, v in fields.items() if v is not None})
    session["_music_workspace_save_transaction"] = tx


def queue_strict_deferred_save(
    session: dict[str, Any],
    *,
    save_reason: str,
    payload_fp: str,
    now: float | None = None,
) -> dict[str, Any]:
    """Queue a debounced strict save; ``strict_save_due_at`` is anchored at first queue."""
    reason = normalize_music_save_reason(save_reason)
    ts = float(now if now is not None else time.time())
    pending_fp = str(session.get(_PENDING_FP_KEY) or "").strip()
    first = session.get(_FIRST_QUEUED_KEY)
    deadline_extended = False

    if not session.get(_PENDING_KEY):
        session[_PENDING_KEY] = True
        session[_FIRST_QUEUED_KEY] = ts
        session[_DUE_AT_KEY] = ts + _STRICT_DEBOUNCE_SEC
        session[_LAST_EDIT_KEY] = ts
        session[_PENDING_FP_KEY] = payload_fp
        session[_COALESCE_COUNT_KEY] = 0
        session[_DEADLINE_EXTENDED_KEY] = False
        _append_pending_reason(session, reason)
    else:
        session[_LAST_EDIT_KEY] = ts
        _append_pending_reason(session, reason)
        if payload_fp and payload_fp != pending_fp:
            session[_PENDING_FP_KEY] = payload_fp
            new_due = ts + _STRICT_DEBOUNCE_SEC
            old_due = strict_save_due_at(session)
            if new_due > old_due:
                session[_DUE_AT_KEY] = new_due
                session[_DEADLINE_EXTENDED_KEY] = True
                deadline_extended = True
        coalesce = int(session.get(_COALESCE_COUNT_KEY) or 0) + 1
        session[_COALESCE_COUNT_KEY] = coalesce

    session[_DEFER_REASON_KEY] = reason
    session[_WAKEUP_SCHEDULED_KEY] = True

    diag = collect_strict_pending_diagnostics(session)
    diag["deadline_extended_by_new_edit"] = deadline_extended
    _record_strict_pending_diag(session, **diag)
    return diag


def clear_strict_pending_save(session: dict[str, Any], *, flush_result: str = "") -> None:
    session.pop(_PENDING_KEY, None)
    session.pop(_DUE_AT_KEY, None)
    session.pop(_FIRST_QUEUED_KEY, None)
    session.pop(_LAST_EDIT_KEY, None)
    session.pop(_PENDING_FP_KEY, None)
    session.pop(_PENDING_REASONS_KEY, None)
    session.pop(_DEADLINE_EXTENDED_KEY, None)
    session.pop(_DEFER_REASON_KEY, None)
    session.pop(_COALESCE_COUNT_KEY, None)
    session.pop(_WAKEUP_SCHEDULED_KEY, None)
    if flush_result:
        session[_FLUSH_RESULT_KEY] = flush_result
    diag = collect_strict_pending_diagnostics(session)
    diag["strict_save_pending"] = False
    _record_strict_pending_diag(session, **diag)


def collect_strict_pending_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    due = strict_save_due_at(session)
    return {
        "strict_save_pending": bool(session.get(_PENDING_KEY)),
        "strict_save_due_at": due if due else None,
        "strict_save_first_queued_at": session.get(_FIRST_QUEUED_KEY),
        "strict_save_last_edit_at": session.get(_LAST_EDIT_KEY),
        "strict_save_wakeup_scheduled": bool(session.get(_WAKEUP_SCHEDULED_KEY)),
        "strict_save_wakeup_ran": bool(session.get(_WAKEUP_RAN_KEY)),
        "strict_save_flush_attempted": bool(session.get(_FLUSH_ATTEMPTED_KEY)),
        "strict_save_flush_result": session.get(_FLUSH_RESULT_KEY) or "(none)",
        "pending_payload_fingerprint": session.get(_PENDING_FP_KEY) or "(none)",
        "pending_save_reasons": list(session.get(_PENDING_REASONS_KEY) or []),
        "deadline_extended_by_new_edit": bool(session.get(_DEADLINE_EXTENDED_KEY)),
    }


@dataclass(frozen=True)
class StrictEgressWritePlan:
    allow_cloud_write: bool
    defer_cloud_write: bool
    block_reason: str
    strict_egress_user_write_allowed: bool
    strict_egress_reason: str
    payload_changed_since_last_confirmed_save: bool
    duplicate_write_skipped: bool
    save_debounce_started: bool
    save_debounce_completed: bool
    edits_coalesced_count: int

    def diag(self) -> dict[str, Any]:
        return {
            "strict_egress_user_write_allowed": self.strict_egress_user_write_allowed,
            "strict_egress_reason": self.strict_egress_reason or "(none)",
            "save_debounce_started": self.save_debounce_started,
            "save_debounce_completed": self.save_debounce_completed,
            "edits_coalesced_count": self.edits_coalesced_count,
            "payload_changed_since_last_confirmed_save": self.payload_changed_since_last_confirmed_save,
            "duplicate_write_skipped": self.duplicate_write_skipped,
        }


def plan_strict_egress_cloud_write(
    session: dict[str, Any],
    *,
    save_reason: str,
    payload_fp: str,
    bypass_defer: bool = False,
    now: float | None = None,
) -> StrictEgressWritePlan:
    """Decide whether this invocation may perform a strict-mode cloud upsert."""
    reason = normalize_music_save_reason(save_reason)
    intentional = is_intentional_user_save_reason(reason)
    strict = music_egress_strict_enabled()
    coalesce = int(session.get(_COALESCE_COUNT_KEY) or 0)
    ts = float(now if now is not None else time.time())

    if not strict:
        confirmed = last_confirmed_cloud_fingerprint(session)
        changed = bool(payload_fp) and payload_fp != confirmed
        return StrictEgressWritePlan(
            allow_cloud_write=True,
            defer_cloud_write=False,
            block_reason="",
            strict_egress_user_write_allowed=True,
            strict_egress_reason=reason,
            payload_changed_since_last_confirmed_save=changed,
            duplicate_write_skipped=bool(confirmed and payload_fp == confirmed),
            save_debounce_started=False,
            save_debounce_completed=False,
            edits_coalesced_count=0,
        )

    if not intentional:
        return StrictEgressWritePlan(
            allow_cloud_write=False,
            defer_cloud_write=False,
            block_reason="music_egress_strict",
            strict_egress_user_write_allowed=False,
            strict_egress_reason=reason,
            payload_changed_since_last_confirmed_save=False,
            duplicate_write_skipped=False,
            save_debounce_started=False,
            save_debounce_completed=False,
            edits_coalesced_count=coalesce,
        )

    confirmed = last_confirmed_cloud_fingerprint(session)
    if confirmed and payload_fp == confirmed:
        return StrictEgressWritePlan(
            allow_cloud_write=False,
            defer_cloud_write=False,
            block_reason="",
            strict_egress_user_write_allowed=True,
            strict_egress_reason=reason,
            payload_changed_since_last_confirmed_save=False,
            duplicate_write_skipped=True,
            save_debounce_started=False,
            save_debounce_completed=False,
            edits_coalesced_count=coalesce,
        )

    if bypass_defer:
        clear_strict_pending_save(session)
        return StrictEgressWritePlan(
            allow_cloud_write=True,
            defer_cloud_write=False,
            block_reason="",
            strict_egress_user_write_allowed=True,
            strict_egress_reason=reason,
            payload_changed_since_last_confirmed_save=True,
            duplicate_write_skipped=False,
            save_debounce_started=False,
            save_debounce_completed=True,
            edits_coalesced_count=coalesce,
        )

    if not save_reason_uses_strict_debounce(reason):
        return StrictEgressWritePlan(
            allow_cloud_write=True,
            defer_cloud_write=False,
            block_reason="",
            strict_egress_user_write_allowed=True,
            strict_egress_reason=reason,
            payload_changed_since_last_confirmed_save=True,
            duplicate_write_skipped=False,
            save_debounce_started=False,
            save_debounce_completed=True,
            edits_coalesced_count=0,
        )

    if strict_save_pending(session) and ts >= strict_save_due_at(session):
        return StrictEgressWritePlan(
            allow_cloud_write=True,
            defer_cloud_write=False,
            block_reason="",
            strict_egress_user_write_allowed=True,
            strict_egress_reason=reason,
            payload_changed_since_last_confirmed_save=True,
            duplicate_write_skipped=False,
            save_debounce_started=False,
            save_debounce_completed=True,
            edits_coalesced_count=coalesce,
        )

    queue_strict_deferred_save(session, save_reason=reason, payload_fp=payload_fp, now=ts)
    coalesce = int(session.get(_COALESCE_COUNT_KEY) or 0)
    started = session.get(_FIRST_QUEUED_KEY) == ts
    return StrictEgressWritePlan(
        allow_cloud_write=False,
        defer_cloud_write=True,
        block_reason="",
        strict_egress_user_write_allowed=True,
        strict_egress_reason=reason,
        payload_changed_since_last_confirmed_save=True,
        duplicate_write_skipped=False,
        save_debounce_started=bool(started),
        save_debounce_completed=False,
        edits_coalesced_count=coalesce,
    )


def strict_post_save_confirmation_uses_authoritative_upsert(*, save_reason: str) -> bool:
    if not music_egress_strict_enabled():
        return False
    return is_intentional_user_save_reason(save_reason)


def allow_single_strict_confirmation_read(session: dict[str, Any]) -> bool:
    return int(session.get(_TX_READ_COUNT_KEY) or 0) < 1


def _pending_flush_reason(session: dict[str, Any]) -> str:
    reasons = session.get(_PENDING_REASONS_KEY)
    if isinstance(reasons, list) and reasons:
        return str(reasons[-1])
    return str(session.get(_DEFER_REASON_KEY) or "backing_edit").strip() or "backing_edit"


def flush_strict_pending_save_if_due(
    st: Any,
    *,
    build_state: Any,
    now: float | None = None,
) -> bool:
    """Flush queued debounced save when ``now >= strict_save_due_at``."""
    ss = st.session_state
    if not music_egress_strict_enabled() or not strict_save_pending(ss):
        return False
    ts = float(now if now is not None else time.time())
    due = strict_save_due_at(ss)
    if due <= 0 or ts < due:
        return False

    ss[_FLUSH_ATTEMPTED_KEY] = True
    reason = _pending_flush_reason(ss)
    try:
        from music_workspace_cloud_save import force_music_workspace_save

        ok = bool(
            force_music_workspace_save(
                st,
                reason=reason,
                build_state=build_state,
                bypass_strict_defer=True,
            )
        )
        result = "confirmed" if ok else "failed"
        if ok:
            clear_strict_pending_save(ss, flush_result=result)
        else:
            ss[_FLUSH_RESULT_KEY] = result
        _record_strict_pending_diag(ss, **collect_strict_pending_diagnostics(ss))
        return ok
    except ImportError:
        ss[_FLUSH_RESULT_KEY] = "import_error"
        return False


def maybe_flush_deferred_strict_cloud_save(st: Any, *, build_state: Any) -> bool:
    """End-of-rerun flush when the debounce deadline has passed."""
    return flush_strict_pending_save_if_due(st, build_state=build_state)


def strict_save_wakeup_tick(st: Any, *, build_state: Any) -> None:
    """Fragment timer tick — flush pending save after deadline without user input."""
    ss = st.session_state
    ss[_WAKEUP_RAN_KEY] = True
    _record_strict_pending_diag(ss, **collect_strict_pending_diagnostics(ss))
    flush_strict_pending_save_if_due(st, build_state=build_state)


__all__ = [
    "allow_single_strict_confirmation_read",
    "bump_cloud_read_count",
    "bump_cloud_write_count",
    "clear_strict_pending_save",
    "collect_strict_pending_diagnostics",
    "flush_strict_pending_save_if_due",
    "last_confirmed_cloud_fingerprint",
    "maybe_flush_deferred_strict_cloud_save",
    "note_confirmed_cloud_fingerprint",
    "plan_strict_egress_cloud_write",
    "queue_strict_deferred_save",
    "reset_transaction_egress_counters",
    "save_reason_uses_strict_debounce",
    "strict_post_save_confirmation_uses_authoritative_upsert",
    "strict_save_pending",
    "strict_save_wakeup_tick",
    "workspace_payload_fingerprint",
]

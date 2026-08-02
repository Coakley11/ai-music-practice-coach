"""Strict egress: intentional user saves, debounce/coalesce, fingerprint dedupe."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

from music_egress_config import (
    get_music_egress_policy,
    is_intentional_user_save_reason,
    music_egress_strict_enabled,
    normalize_music_save_reason,
)

APP_ID = "music"
_STRICT_DEBOUNCE_SEC = 2.0

_DEFER_REASON_KEY = "_music_strict_save_deferred_reason"
_DEBOUNCE_STARTED_KEY = "_music_save_debounce_started"
_COALESCE_COUNT_KEY = "_music_strict_edits_coalesced_count"
_CONFIRMED_FP_KEY = "_music_last_confirmed_cloud_fp"
_CLOUD_WRITE_TS_KEY = "_music_strict_cloud_write_ts"
_TX_WRITE_COUNT_KEY = "_music_strict_tx_cloud_write_count"
_TX_READ_COUNT_KEY = "_music_strict_tx_cloud_read_count"


def workspace_payload_fingerprint(state: dict[str, Any]) -> str:
    blob = json.dumps(state, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]


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
) -> StrictEgressWritePlan:
    """Decide whether this invocation may perform a strict-mode cloud upsert."""
    reason = normalize_music_save_reason(save_reason)
    intentional = is_intentional_user_save_reason(reason)
    strict = music_egress_strict_enabled()
    coalesce = int(session.get(_COALESCE_COUNT_KEY) or 0)

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
        session.pop(_DEBOUNCE_STARTED_KEY, None)
        session.pop(_DEFER_REASON_KEY, None)
        session[_COALESCE_COUNT_KEY] = 0
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

    now = time.time()
    started = session.get(_DEBOUNCE_STARTED_KEY)
    if started is None:
        session[_DEBOUNCE_STARTED_KEY] = now
        session[_DEFER_REASON_KEY] = reason
        session[_COALESCE_COUNT_KEY] = 0
        return StrictEgressWritePlan(
            allow_cloud_write=False,
            defer_cloud_write=True,
            block_reason="",
            strict_egress_user_write_allowed=True,
            strict_egress_reason=reason,
            payload_changed_since_last_confirmed_save=True,
            duplicate_write_skipped=False,
            save_debounce_started=True,
            save_debounce_completed=False,
            edits_coalesced_count=0,
        )

    elapsed = now - float(started)
    if elapsed < _STRICT_DEBOUNCE_SEC:
        coalesce += 1
        session[_COALESCE_COUNT_KEY] = coalesce
        session[_DEFER_REASON_KEY] = reason
        return StrictEgressWritePlan(
            allow_cloud_write=False,
            defer_cloud_write=True,
            block_reason="",
            strict_egress_user_write_allowed=True,
            strict_egress_reason=reason,
            payload_changed_since_last_confirmed_save=True,
            duplicate_write_skipped=False,
            save_debounce_started=False,
            save_debounce_completed=False,
            edits_coalesced_count=coalesce,
        )

    session.pop(_DEBOUNCE_STARTED_KEY, None)
    session.pop(_DEFER_REASON_KEY, None)
    session[_COALESCE_COUNT_KEY] = 0
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


def strict_post_save_confirmation_uses_authoritative_upsert(*, save_reason: str) -> bool:
    """Under strict mode, trust a successful upsert for intentional saves (no extra fetch)."""
    if not music_egress_strict_enabled():
        return False
    return is_intentional_user_save_reason(save_reason)


def allow_single_strict_confirmation_read(session: dict[str, Any]) -> bool:
    """Exactly one targeted readback per save transaction when upsert is not enough."""
    return int(session.get(_TX_READ_COUNT_KEY) or 0) < 1


def maybe_flush_deferred_strict_cloud_save(st: Any, *, build_state: Any) -> bool:
    """Trailing-edge flush after coalesced intentional edits (end of rerun)."""
    ss = st.session_state
    reason = str(ss.get(_DEFER_REASON_KEY) or "").strip()
    if not reason or not music_egress_strict_enabled():
        return False
    try:
        from music_workspace_cloud_save import force_music_workspace_save

        return bool(
            force_music_workspace_save(
                st,
                reason=reason,
                build_state=build_state,
                bypass_strict_defer=True,
            )
        )
    except ImportError:
        return False


__all__ = [
    "allow_single_strict_confirmation_read",
    "bump_cloud_read_count",
    "bump_cloud_write_count",
    "last_confirmed_cloud_fingerprint",
    "maybe_flush_deferred_strict_cloud_save",
    "note_confirmed_cloud_fingerprint",
    "plan_strict_egress_cloud_write",
    "reset_transaction_egress_counters",
    "strict_post_save_confirmation_uses_authoritative_upsert",
    "workspace_payload_fingerprint",
]

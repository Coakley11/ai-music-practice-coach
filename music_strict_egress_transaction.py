"""Canonical strict-egress decision for one Music workspace save transaction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from music_egress_config import (
    is_intentional_user_save_reason,
    music_cloud_write_allowed,
    music_egress_strict_enabled,
    normalize_music_save_reason,
)
from music_egress_strict_save import (
    plan_strict_egress_cloud_write,
    save_reason_uses_strict_debounce,
)

STRICT_EGRESS_APPROVAL_KEY = "_music_strict_egress_approval"
_PASSIVE_AUTOSAVE_SKIP_KEY = "_music_passive_autosave_cloud_skip_reason"


@dataclass
class StrictEgressTransaction:
    raw_save_reason: str
    normalized_save_reason: str
    save_reason_is_intentional: bool
    save_reason_is_discrete: bool
    strict_egress_user_write_allowed: bool
    strict_egress_plan_action: str
    strict_egress_approved: bool
    cloud_write_allowed_before_transaction: bool
    cloud_write_allowed_inside_save_cloud_full_session: bool = True
    strict_egress_denied_by_function: str = ""
    strict_egress_denied_by_file_line: str = ""
    final_cloud_write_block_reason: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def approval_dict(self) -> dict[str, Any]:
        return {
            "reason": self.normalized_save_reason,
            "raw_reason": self.raw_save_reason,
            "intentional_user_write": self.save_reason_is_intentional,
            "strict_egress_approved": self.strict_egress_approved,
            "strict_egress_plan_action": self.strict_egress_plan_action,
        }

    def diag(self) -> dict[str, Any]:
        return {
            "raw_save_reason": self.raw_save_reason,
            "normalized_save_reason": self.normalized_save_reason,
            "save_reason_is_intentional": self.save_reason_is_intentional,
            "save_reason_is_discrete": self.save_reason_is_discrete,
            "strict_egress_user_write_allowed": self.strict_egress_user_write_allowed,
            "strict_egress_plan_action": self.strict_egress_plan_action,
            "strict_egress_approved": self.strict_egress_approved,
            "cloud_write_allowed_before_transaction": self.cloud_write_allowed_before_transaction,
            "cloud_write_allowed_inside_save_cloud_full_session": self.cloud_write_allowed_inside_save_cloud_full_session,
            "strict_egress_denied_by_function": self.strict_egress_denied_by_function or "(none)",
            "strict_egress_denied_by_file_line": self.strict_egress_denied_by_file_line or "(none)",
            "final_cloud_write_block_reason": self.final_cloud_write_block_reason or "(none)",
            **self.extra,
        }


def evaluate_strict_egress_transaction(
    session: dict[str, Any],
    *,
    raw_save_reason: str,
    payload_fp: str,
    bypass_defer: bool = False,
    st: Any | None = None,
) -> StrictEgressTransaction:
    """Single strict-egress gate for the full workspace save stack."""
    raw = str(raw_save_reason or "autosave").strip() or "autosave"
    normalized = normalize_music_save_reason(raw)
    intentional = is_intentional_user_save_reason(normalized)
    discrete = intentional and not save_reason_uses_strict_debounce(normalized)
    allowed_before = music_cloud_write_allowed(save_reason=raw, st=st)

    plan = plan_strict_egress_cloud_write(
        session,
        save_reason=raw,
        payload_fp=payload_fp,
        bypass_defer=bypass_defer,
    )

    action = "deny"
    approved = False
    denied_fn = ""
    denied_line = ""
    block = ""

    if plan.duplicate_write_skipped:
        action = "duplicate_skip"
        approved = True
    elif plan.defer_cloud_write:
        action = "defer"
        approved = False
        block = "strict_save_deferred"
    elif not plan.strict_egress_user_write_allowed:
        action = "deny"
        approved = False
        denied_fn = "plan_strict_egress_cloud_write"
        denied_line = "music_egress_strict_save.py:evaluate_not_intentional"
        block = "music_egress_strict"
    elif plan.allow_cloud_write:
        action = "immediate"
        approved = True
    else:
        action = "deny"
        approved = False
        denied_fn = "plan_strict_egress_cloud_write"
        denied_line = "music_egress_strict_save.py:evaluate_not_allowed"
        block = "music_egress_strict"

    if music_egress_strict_enabled() and approved:
        allowed_inside = True
    elif music_egress_strict_enabled():
        allowed_inside = False
    else:
        allowed_inside = True

    tx = StrictEgressTransaction(
        raw_save_reason=raw,
        normalized_save_reason=normalized,
        save_reason_is_intentional=intentional,
        save_reason_is_discrete=discrete,
        strict_egress_user_write_allowed=plan.strict_egress_user_write_allowed,
        strict_egress_plan_action=action,
        strict_egress_approved=approved,
        cloud_write_allowed_before_transaction=allowed_before,
        cloud_write_allowed_inside_save_cloud_full_session=allowed_inside,
        strict_egress_denied_by_function=denied_fn,
        strict_egress_denied_by_file_line=denied_line,
        final_cloud_write_block_reason=block,
        extra=plan.diag(),
    )
    session[STRICT_EGRESS_APPROVAL_KEY] = tx.approval_dict()
    return tx


def cloud_write_permitted_for_transaction(
    session: dict[str, Any],
    *,
    save_reason: str = "",
    st: Any | None = None,
) -> bool:
    """Honor an approved transaction; do not re-deny lower in the stack."""
    approval = session.get(STRICT_EGRESS_APPROVAL_KEY)
    if isinstance(approval, dict) and approval.get("strict_egress_approved"):
        return True
    return music_cloud_write_allowed(save_reason=save_reason, st=st, strict_egress_approval=approval)


def note_passive_autosave_cloud_skip(session: dict[str, Any], *, reason: str) -> None:
    """Record passive autosave skip without overwriting an intentional save transaction."""
    session[_PASSIVE_AUTOSAVE_SKIP_KEY] = reason
    if session.get("_suite_persist_last_save_cloud"):
        return
    session["_suite_autosave_cloud_blocked_reason"] = reason


__all__ = [
    "STRICT_EGRESS_APPROVAL_KEY",
    "_PASSIVE_AUTOSAVE_SKIP_KEY",
    "StrictEgressTransaction",
    "cloud_write_permitted_for_transaction",
    "evaluate_strict_egress_transaction",
    "note_passive_autosave_cloud_skip",
]

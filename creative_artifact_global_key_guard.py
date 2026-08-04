"""Prevent Creative artifact / handoff saves from mutating global practice keys."""

from __future__ import annotations

import copy
from typing import Any

from creative_mission_artifact_persistence import (
    CREATIVE_MISSION_ARTIFACT_SAVE_ACTIVE_KEY,
    is_mission_artifact_save_reason,
)
from improvisation_missions import MISSION_EXAMPLE_KEY, MISSION_PRACTICE_LICK_KEY

CREATIVE_ARTIFACT_GLOBAL_KEY_DIAG_KEY = "_creative_artifact_global_key_diag"
CREATIVE_ARTIFACT_FROZEN_GLOBAL_SNAPSHOT_KEY = "_creative_artifact_frozen_global_snapshot"
VIOLATION_CREATIVE_ARTIFACT_GLOBAL_KEY_MUTATION = "CREATIVE_ARTIFACT_GLOBAL_KEY_MUTATION"

GLOBAL_KEY_GUARD_FIELDS: tuple[str, ...] = (
    "display_key",
    "practice_concert_key",
    "concert_key",
    "chart_key",
    "written_key",
)

_EXPLICIT_DISPLAY_KEY_SOURCES: frozenset[str] = frozenset(
    {
        "sidebar",
        "widget_callback",
        "sidebar_on_change_display_key",
        "display_key_widget",
        "user",
        "user_navigation",
        "key_control",
        "display_key_change",
        "capo_widget",
    }
)


def _diag(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(CREATIVE_ARTIFACT_GLOBAL_KEY_DIAG_KEY)
    if not isinstance(raw, dict):
        raw = {"violations": [], "writes": []}
        session[CREATIVE_ARTIFACT_GLOBAL_KEY_DIAG_KEY] = raw
    return raw


def _run_seq(session: dict[str, Any]) -> int:
    try:
        return int(session.get("_script_run_seq") or 0)
    except (TypeError, ValueError):
        return 0


def is_creative_artifact_global_key_guard_reason(session: dict[str, Any], save_reason: str) -> bool:
    reason = str(save_reason or "").strip()
    if is_mission_artifact_save_reason(reason):
        return True
    if reason == "page_change":
        try:
            from mission_backing_handoff_persistence import (
                MISSION_BACKING_HANDOFF_SEALED_FOR_PAGE_CHANGE_KEY,
            )

            return bool(session.get(MISSION_BACKING_HANDOFF_SEALED_FOR_PAGE_CHANGE_KEY))
        except ImportError:
            pass
    return False


def explicit_display_key_user_event(session: dict[str, Any]) -> bool:
    pending = str(
        session.get("_suite_pending_save_reason") or session.get("_music_build_save_reason") or ""
    ).strip()
    if pending == "display_key_change":
        return True
    src = str(session.get("display_key_change_source") or "").strip()
    if src in _EXPLICIT_DISPLAY_KEY_SOURCES:
        return True
    if src and "sidebar" in src.lower():
        return True
    if src and "user" in src.lower():
        return True
    return False


def canonical_global_key_snapshot(session: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY, canonical_active_song_context

        ctx = canonical_active_song_context(session)
        if isinstance(ctx, dict):
            for field in GLOBAL_KEY_GUARD_FIELDS:
                val = str(ctx.get(field) or "").strip()
                if val:
                    out[field] = val
    except ImportError:
        pass
    meta = session.get(ACTIVE_SONG_STATE_KEY)
    if isinstance(meta, dict):
        for field in GLOBAL_KEY_GUARD_FIELDS:
            if field not in out:
                val = str(meta.get(field) or "").strip()
                if val:
                    out[field] = val
    for field in GLOBAL_KEY_GUARD_FIELDS:
        if field not in out:
            val = str(session.get(field) or "").strip()
            if val:
                out[field] = val
    return out


def _artifact_key_center(session: dict[str, Any]) -> str:
    for key in (MISSION_EXAMPLE_KEY, MISSION_PRACTICE_LICK_KEY):
        raw = session.get(key)
        if isinstance(raw, dict):
            kc = str(raw.get("key_center") or raw.get("display_key") or "").strip()
            if kc:
                return kc
    try:
        from creative_mission_artifact_persistence import canonical_mission_artifact_value

        for key in (MISSION_EXAMPLE_KEY, MISSION_PRACTICE_LICK_KEY):
            blob = canonical_mission_artifact_value(session, key)
            if isinstance(blob, dict):
                kc = str(blob.get("key_center") or blob.get("display_key") or "").strip()
                if kc:
                    return kc
    except ImportError:
        pass
    return ""


def _record_write(
    session: dict[str, Any],
    *,
    field: str,
    old_value: str,
    new_value: str,
    function: str,
    caller: str,
    save_reason: str,
    reverted: bool = False,
) -> None:
    d = _diag(session)
    writes = d.setdefault("writes", [])
    if not isinstance(writes, list):
        writes = []
        d["writes"] = writes
    tx = session.get(CREATIVE_MISSION_ARTIFACT_SAVE_ACTIVE_KEY)
    tx_id = tx.get("transaction_id") if isinstance(tx, dict) else None
    writes.append(
        {
            "field": field,
            "old_value": old_value or None,
            "new_value": new_value or None,
            "function": function,
            "caller": caller,
            "save_reason": save_reason,
            "run_seq": _run_seq(session),
            "transaction_id": tx_id,
            "reverted": reverted,
            "user_key_action": explicit_display_key_user_event(session),
            "entered_cloud_payload": None,
        }
    )


def freeze_global_keys_for_creative_artifact_save(
    session: dict[str, Any],
    *,
    save_reason: str,
    caller: str = "freeze_global_keys_for_creative_artifact_save",
) -> dict[str, Any]:
    """Build canonical global-key snapshot for save — never mutate live widget-bound session keys."""
    if not is_creative_artifact_global_key_guard_reason(session, save_reason):
        session.pop(CREATIVE_ARTIFACT_FROZEN_GLOBAL_SNAPSHOT_KEY, None)
        return {"frozen": False}
    if explicit_display_key_user_event(session):
        session.pop(CREATIVE_ARTIFACT_FROZEN_GLOBAL_SNAPSHOT_KEY, None)
        return {"frozen": False, "skipped": "explicit_user_key_event"}
    canonical = canonical_global_key_snapshot(session)
    frozen = {f: str(canonical.get(f) or "").strip() for f in GLOBAL_KEY_GUARD_FIELDS if canonical.get(f)}
    session[CREATIVE_ARTIFACT_FROZEN_GLOBAL_SNAPSHOT_KEY] = copy.deepcopy(frozen)
    d = _diag(session)
    d["prior_global_keys"] = copy.deepcopy(canonical)
    d["frozen_snapshot"] = copy.deepcopy(frozen)
    d["save_reason"] = str(save_reason or "")
    d["artifact_key_center"] = _artifact_key_center(session)
    d["caller"] = caller
    would_revert: list[str] = []
    for field in GLOBAL_KEY_GUARD_FIELDS:
        canon_val = str(canonical.get(field) or "").strip()
        if not canon_val:
            continue
        live = str(session.get(field) or "").strip()
        if live and live != canon_val:
            would_revert.append(field)
            _record_write(
                session,
                field=field,
                old_value=live,
                new_value=canon_val,
                function="freeze_global_keys_for_creative_artifact_save",
                caller=caller,
                save_reason=save_reason,
                reverted=False,
            )
    d["session_keys_after_freeze"] = {
        f: str(session.get(f) or "").strip() or None for f in GLOBAL_KEY_GUARD_FIELDS
    }
    d["snapshot_only"] = True
    d["would_revert_fields"] = would_revert
    return {
        "frozen": True,
        "reverted": False,
        "snapshot_only": True,
        "would_revert_fields": would_revert,
        "canonical": canonical,
        "frozen_snapshot": frozen,
    }


def apply_frozen_global_keys_to_payload(session: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """Overlay frozen canonical global keys onto save payload (not session)."""
    frozen = session.get(CREATIVE_ARTIFACT_FROZEN_GLOBAL_SNAPSHOT_KEY)
    if not isinstance(frozen, dict) or not frozen:
        diag = session.get(CREATIVE_ARTIFACT_GLOBAL_KEY_DIAG_KEY)
        if isinstance(diag, dict) and isinstance(diag.get("frozen_snapshot"), dict):
            frozen = diag["frozen_snapshot"]
    if not isinstance(frozen, dict) or not frozen:
        return state
    core = state.get("core")
    if isinstance(core, dict):
        for field, val in frozen.items():
            if val:
                core[field] = val
    sess = state.get("session")
    if isinstance(sess, dict):
        for field, val in frozen.items():
            if val:
                sess[field] = val
    ass = state.get("active_song_state")
    if isinstance(ass, dict):
        for field, val in frozen.items():
            if val:
                ass[field] = val
    return state


def get_frozen_global_key_snapshot(session: dict[str, Any]) -> dict[str, str]:
    raw = session.get(CREATIVE_ARTIFACT_FROZEN_GLOBAL_SNAPSHOT_KEY)
    if isinstance(raw, dict) and raw:
        return {str(k): str(v) for k, v in raw.items() if v}
    return {}


def audit_payload_global_keys(
    session: dict[str, Any],
    state: dict[str, Any],
    *,
    save_reason: str,
) -> None:
    if not is_creative_artifact_global_key_guard_reason(session, save_reason):
        return
    prior = _diag(session).get("prior_global_keys") or canonical_global_key_snapshot(session)
    if not isinstance(prior, dict):
        prior = {}
    core = state.get("core") if isinstance(state.get("core"), dict) else {}
    session_extra = state.get("session") if isinstance(state.get("session"), dict) else {}
    payload_dk = str(core.get("display_key") or session_extra.get("display_key") or "").strip()
    prior_dk = str(prior.get("display_key") or "").strip()
    if not prior_dk or payload_dk == prior_dk:
        return
    if explicit_display_key_user_event(session):
        return
    tx = session.get(CREATIVE_MISSION_ARTIFACT_SAVE_ACTIVE_KEY)
    tx_id = tx.get("transaction_id") if isinstance(tx, dict) else None
    try:
        from workspace_revision import workspace_revision_from_blob

        rev = workspace_revision_from_blob(state)
    except ImportError:
        rev = None
    detail = {
        "prior_global_key": prior_dk,
        "payload_global_key": payload_dk,
        "artifact_key_center": _artifact_key_center(session),
        "save_reason": save_reason,
        "caller": "audit_payload_global_keys",
        "transaction_id": tx_id,
        "revision": rev,
    }
    violations = _diag(session).setdefault("violations", [])
    if not isinstance(violations, list):
        violations = []
        _diag(session)["violations"] = violations
    entry = {"code": VIOLATION_CREATIVE_ARTIFACT_GLOBAL_KEY_MUTATION, "detail": detail}
    if entry not in violations:
        violations.append(entry)


def collect_creative_artifact_global_key_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(CREATIVE_ARTIFACT_GLOBAL_KEY_DIAG_KEY)
    return copy.deepcopy(raw) if isinstance(raw, dict) else {}


__all__ = [
    "CREATIVE_ARTIFACT_FROZEN_GLOBAL_SNAPSHOT_KEY",
    "CREATIVE_ARTIFACT_GLOBAL_KEY_DIAG_KEY",
    "GLOBAL_KEY_GUARD_FIELDS",
    "VIOLATION_CREATIVE_ARTIFACT_GLOBAL_KEY_MUTATION",
    "apply_frozen_global_keys_to_payload",
    "audit_payload_global_keys",
    "canonical_global_key_snapshot",
    "collect_creative_artifact_global_key_diagnostics",
    "explicit_display_key_user_event",
    "freeze_global_keys_for_creative_artifact_save",
    "get_frozen_global_key_snapshot",
    "is_creative_artifact_global_key_guard_reason",
]

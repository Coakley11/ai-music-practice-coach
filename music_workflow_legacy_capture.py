"""Legacy capture allowlist and authoritative outgoing blob rules (Commit 4)."""

from __future__ import annotations

import copy
from typing import Any

from music_workflow_state_store import (
    WorkflowStateBlob,
    get_workflow_blob,
    record_compat_fallback,
)

WORKFLOW_LEGACY_CAPTURE_STATS_KEY = "_music_workflow_legacy_capture_stats"

# Transient legacy fields permitted to supplement an existing authoritative blob.
# Each entry: owner -> {field: (reason, removal_target)}
TRANSIENT_LEGACY_CAPTURE_ALLOWLIST: dict[str, dict[str, tuple[str, str]]] = {
    "mission_jam": {
        "improv_mission_recording_seal": ("recording_seal_pending_migration", "commit_5"),
    },
    "style_jam": {},
    "jam_session_generator": {},
    "song_based_improvisation": {},
}

VIOLATION_LEGACY_REBUILD_WITH_VALID_BLOB = "LEGACY_REBUILD_ATTEMPT_WITH_VALID_BLOB"
VIOLATION_UNATTRIBUTED_LEGACY_WRITE = "UNATTRIBUTED_LEGACY_WRITE_IGNORED"
VIOLATION_LEGACY_CAPTURE_OWNER_MISMATCH = "LEGACY_CAPTURE_OWNER_MISMATCH"
VIOLATION_AUTHORITATIVE_BLOB_OVERWRITE = "AUTHORITATIVE_BLOB_OVERWRITE_ATTEMPT"


def _stats(session: dict[str, Any]) -> dict[str, int]:
    raw = session.get(WORKFLOW_LEGACY_CAPTURE_STATS_KEY)
    if not isinstance(raw, dict):
        raw = {
            "legacy_capture_allowed": 0,
            "legacy_capture_ignored": 0,
            "legacy_rebuild_blocked": 0,
            "compatibility_bootstrap_builds": 0,
        }
        session[WORKFLOW_LEGACY_CAPTURE_STATS_KEY] = raw
    return raw  # type: ignore[return-value]


def _bump(session: dict[str, Any], key: str) -> None:
    s = _stats(session)
    s[key] = int(s.get(key) or 0) + 1


def _supplement_blob_from_allowlisted_legacy(
    session: dict[str, Any],
    blob: WorkflowStateBlob,
    owner: str,
) -> list[str]:
    """Copy only allowlisted transient legacy fields onto authoritative blob."""
    applied: list[str] = []
    allow = TRANSIENT_LEGACY_CAPTURE_ALLOWLIST.get(owner) or {}
    for field, (_reason, _target) in allow.items():
        if field not in session:
            continue
        val = session.get(field)
        if field == "improv_mission_recording_seal" and isinstance(val, dict):
            blob.recording_seal_chord = str(val.get("chord_symbol") or val.get("chord") or "")
            applied.append(field)
    if applied:
        _bump(session, "legacy_capture_allowed")
    return applied


def capture_outgoing_workflow_blob(
    session: dict[str, Any],
    *,
    owner: str,
    session_id: str,
    allow_legacy_bootstrap: bool = False,
) -> WorkflowStateBlob | None:
    """
    Outgoing capture for activation — never wholesale-rebuild from legacy when a valid blob exists.
    """
    if not owner or not session_id:
        return None
    stored = get_workflow_blob(session, owner, session_id)
    if stored is not None and str(stored.keys.practice_mode or "").strip():
        out = copy.deepcopy(stored)
        if out.workflow_owner != owner:
            _bump(session, "legacy_capture_ignored")
            record_compat_fallback(session, VIOLATION_LEGACY_CAPTURE_OWNER_MISMATCH, owner)
            return out
        _supplement_blob_from_allowlisted_legacy(session, out, owner)
        _bump(session, "legacy_rebuild_blocked")
        session.setdefault("_music_workflow_capture_violations", []).append(
            VIOLATION_LEGACY_REBUILD_WITH_VALID_BLOB
        )
        return out
    if not allow_legacy_bootstrap:
        _bump(session, "legacy_capture_ignored")
        return None
    from music_workflow_compatibility import build_workflow_blob_from_legacy

    _bump(session, "compatibility_bootstrap_builds")
    record_compat_fallback(session, "compatibility_bootstrap_build", owner)
    fresh = build_workflow_blob_from_legacy(session, owner)
    fresh.workflow_owner = owner
    fresh.workflow_session_id = session_id
    return fresh


__all__ = [
    "TRANSIENT_LEGACY_CAPTURE_ALLOWLIST",
    "VIOLATION_AUTHORITATIVE_BLOB_OVERWRITE",
    "VIOLATION_LEGACY_CAPTURE_OWNER_MISMATCH",
    "VIOLATION_LEGACY_REBUILD_WITH_VALID_BLOB",
    "VIOLATION_UNATTRIBUTED_LEGACY_WRITE",
    "WORKFLOW_LEGACY_CAPTURE_STATS_KEY",
    "capture_outgoing_workflow_blob",
]

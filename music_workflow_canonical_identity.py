"""Pre-activation canonical identity agreement (Commit 7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from music_workflow_state_store import ActiveWorkflowPointer

CANONICAL_IDENTITY_CONFLICT = "CANONICAL_IDENTITY_CONFLICT"

_ACTIVATION_SOURCES_SKIP_LIVE_SONG_SESSION_BIND: frozenset[str] = frozenset(
    {
        "canonical_restore",
        "compatibility_bootstrap",
        "compatibility_bootstrap_store",
        "legacy_musical_snapshot_hydrate",
    }
)

VIOLATION_MISSION_SESSION_SONG_IDENTITY_MISMATCH = "MISSION_SESSION_SONG_IDENTITY_MISMATCH"
VIOLATION_SONG_PRACTICE_SESSION_IDENTITY_MISMATCH = "SONG_PRACTICE_SESSION_IDENTITY_MISMATCH"
VIOLATION_LEGACY_OWNER_POINTER_MISMATCH = "LEGACY_OWNER_ACTIVE_POINTER_MISMATCH"
VIOLATION_PENDING_BACKING_HANDOFF_OWNER_MISMATCH = "PENDING_BACKING_HANDOFF_OWNER_MISMATCH"
VIOLATION_POINTER_BLOB_OWNER_MISMATCH = "POINTER_BLOB_OWNER_MISMATCH"
VIOLATION_POINTER_BLOB_SESSION_MISMATCH = "POINTER_BLOB_SESSION_MISMATCH"


@dataclass
class CanonicalIdentityConflictResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def error_code(self) -> str:
        return "" if self.ok else CANONICAL_IDENTITY_CONFLICT


def validate_pre_activation_identity(
    session: dict[str, Any],
    *,
    target_owner: str,
    target_session_id: str,
    ptr_before: ActiveWorkflowPointer | None,
    activation_source: str = "",
    target_blob_owner: str = "",
    target_blob_session_id: str = "",
) -> CanonicalIdentityConflictResult:
    """Fail closed before activation mutates pointer, store, or legacy projection."""
    violations: list[str] = []
    diag: dict[str, Any] = {
        "target_owner": target_owner,
        "target_session_id": target_session_id,
        "activation_source": activation_source,
    }
    owner = str(target_owner or "").strip()
    sid = str(target_session_id or "").strip()
    blob_owner = str(target_blob_owner or owner or "").strip()
    blob_sid = str(target_blob_session_id or sid or "").strip()
    src = str(activation_source or "").strip()
    relax_live_song_bind = src in _ACTIVATION_SOURCES_SKIP_LIVE_SONG_SESSION_BIND

    if blob_owner and owner and blob_owner != owner:
        violations.append(VIOLATION_POINTER_BLOB_OWNER_MISMATCH)
        diag["blob_owner"] = blob_owner
    if blob_sid and sid and blob_sid != sid:
        violations.append(VIOLATION_POINTER_BLOB_SESSION_MISMATCH)
        diag["blob_session_id"] = blob_sid

    if owner == "mission_jam" and sid and not relax_live_song_bind:
        try:
            from music_workflow_mission_session import mission_blob_session_id, normalize_requested_mission_session_id

            expected = mission_blob_session_id(session)
            has_song_anchor = bool(
                str(session.get("active_catalog_pick_key") or session.get("song") or session.get("custom_progression_id") or "").strip()
            )
            if has_song_anchor and expected:
                normalized = normalize_requested_mission_session_id(session, sid)
                if normalized != expected and sid != expected:
                    violations.append(VIOLATION_MISSION_SESSION_SONG_IDENTITY_MISMATCH)
                    diag["expected_mission_session_id"] = expected
        except ImportError:
            pass

    if owner == "song_based_improvisation" and sid and not relax_live_song_bind:
        try:
            from music_workflow_song_practice import song_based_blob_session_id

            expected = song_based_blob_session_id(session)
            has_song_anchor = bool(
                str(session.get("active_catalog_pick_key") or session.get("song") or session.get("custom_progression_id") or "").strip()
            )
            if has_song_anchor and expected and sid != expected:
                violations.append(VIOLATION_SONG_PRACTICE_SESSION_IDENTITY_MISMATCH)
                diag["expected_song_session_id"] = expected
        except ImportError:
            pass

    if ptr_before and ptr_before.workflow_owner:
        try:
            from workflow_musical_authority import ACTIVE_WORKFLOW_OWNER_KEY

            legacy = str(session.get(ACTIVE_WORKFLOW_OWNER_KEY) or "").strip()
            if legacy and legacy != ptr_before.workflow_owner:
                violations.append(VIOLATION_LEGACY_OWNER_POINTER_MISMATCH)
                diag["legacy_owner"] = legacy
                diag["pointer_owner"] = ptr_before.workflow_owner
        except ImportError:
            pass

    try:
        from music_workflow_pending_backing_handoff import peek_pending_backing_workflow_handoff

        pending = peek_pending_backing_workflow_handoff(session)
        if isinstance(pending, dict):
            handoff_owner = str(pending.get("workflow_owner") or "").strip()
            if handoff_owner and owner and handoff_owner != owner:
                violations.append(VIOLATION_PENDING_BACKING_HANDOFF_OWNER_MISMATCH)
                diag["pending_backing_owner"] = handoff_owner
    except ImportError:
        pass

    if ptr_before and owner and ptr_before.workflow_owner == owner and sid and not relax_live_song_bind:
        if ptr_before.workflow_session_id and ptr_before.workflow_session_id != sid:
            if owner in {"mission_jam", "song_based_improvisation"}:
                violations.append(VIOLATION_POINTER_BLOB_SESSION_MISMATCH)
                diag["pointer_session_id"] = ptr_before.workflow_session_id

    if violations:
        try:
            from music_workflow_state_store import record_compat_fallback

            record_compat_fallback(session, CANONICAL_IDENTITY_CONFLICT, violations[0])
        except ImportError:
            pass
        session["_music_workflow_canonical_identity_diag"] = {"violations": list(violations), **diag}

    return CanonicalIdentityConflictResult(ok=not violations, violations=violations, diagnostics=diag)


__all__ = [
    "CANONICAL_IDENTITY_CONFLICT",
    "CanonicalIdentityConflictResult",
    "VIOLATION_LEGACY_OWNER_POINTER_MISMATCH",
    "VIOLATION_MISSION_SESSION_SONG_IDENTITY_MISMATCH",
    "VIOLATION_PENDING_BACKING_HANDOFF_OWNER_MISMATCH",
    "VIOLATION_POINTER_BLOB_OWNER_MISMATCH",
    "VIOLATION_POINTER_BLOB_SESSION_MISMATCH",
    "VIOLATION_SONG_PRACTICE_SESSION_IDENTITY_MISMATCH",
    "validate_pre_activation_identity",
]

"""Canonical Creative workspace blob — mission, tabs, motif, and creative_session."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from creative_workspace_persistence import CREATIVE_WORKSPACE_KEYS
from improvisation_mission_persistence import (
    MISSION_LOCAL_DIRTY_KEY,
    MISSION_WORKSPACE_UPDATED_AT_KEY,
    clear_mission_workspace_local_edit,
    hydrate_mission_workspace_after_restore,
    is_mission_workspace_locally_dirty,
    mark_mission_workspace_dirty,
)

# Global musician context — owned by active_song_state / session bar, not Creative workspace.
_GLOBAL_CONTEXT_SESSION_KEYS: frozenset[str] = frozenset(
    {
        "instrument",
        "level",
        "focus",
        "display_key",
        "concert_key",
        "practice_concert_key",
        "chart_key",
        "written_key",
    }
)

CREATIVE_SESSION_KEY = "creative_session"
CREATIVE_WORKSPACE_STATE_KEY = "creative_workspace_state"
CREATIVE_WORKSPACE_RESTORED_KEY = "_creative_workspace_state_restored"
CREATIVE_WORKSPACE_MIGRATED_KEY = "_creative_workspace_state_legacy_migrated"
CREATIVE_WORKSPACE_LAST_SAVE_REASON_KEY = "_creative_workspace_last_save_reason"
CREATIVE_WORKSPACE_LAST_SKIP_KEY = "_creative_workspace_last_apply_skipped"

SCHEMA_VERSION = 1


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_creative_workspace_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": _utc_now_iso(),
    }


def upgrade_creative_workspace_blob(blob: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(blob or {})
    out["schema_version"] = max(int(out.get("schema_version") or 0), SCHEMA_VERSION)
    if not str(out.get("updated_at") or "").strip():
        out["updated_at"] = _utc_now_iso()
    return out


def _field_slice(blob: dict[str, Any]) -> dict[str, Any]:
    return {k: copy.deepcopy(blob[k]) for k in CREATIVE_WORKSPACE_KEYS if k in blob}


def gather_creative_workspace_from_session(session: dict[str, Any]) -> dict[str, Any]:
    base = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    if not isinstance(base, dict):
        base = default_creative_workspace_state()
    else:
        base = upgrade_creative_workspace_blob(base)
    for key in CREATIVE_WORKSPACE_KEYS:
        if key in session:
            base[key] = copy.deepcopy(session[key])
    cs = base.get(CREATIVE_SESSION_KEY)
    if isinstance(cs, dict):
        cs = copy.deepcopy(cs)
        live_inst = str(session.get("instrument") or "").strip()
        if live_inst:
            cs["instrument"] = live_inst
        base[CREATIVE_SESSION_KEY] = cs
    base["updated_at"] = _utc_now_iso()
    return base


def _sanitize_creative_session_for_projection(blob: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(blob)
    out.pop("instrument", None)
    return out


def project_creative_workspace_to_session(session: dict[str, Any], *, overwrite: bool = False) -> None:
    meta = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    if not isinstance(meta, dict):
        return
    for key in CREATIVE_WORKSPACE_KEYS:
        if key in _GLOBAL_CONTEXT_SESSION_KEYS:
            continue
        if key not in meta:
            continue
        val = meta[key]
        if key == CREATIVE_SESSION_KEY and isinstance(val, dict):
            val = _sanitize_creative_session_for_projection(val)
        if overwrite or key not in session:
            session[key] = copy.deepcopy(val)


def write_canonical_creative_workspace(
    session: dict[str, Any],
    blob: dict[str, Any],
    *,
    reason: str = "autosave",
) -> dict[str, Any]:
    canonical = upgrade_creative_workspace_blob(blob)
    session[CREATIVE_WORKSPACE_STATE_KEY] = copy.deepcopy(canonical)
    session[CREATIVE_WORKSPACE_LAST_SAVE_REASON_KEY] = reason
    clear_mission_workspace_local_edit(session)
    return canonical


def mark_creative_workspace_state_dirty(session: dict[str, Any], *, reason: str = "user_edit") -> None:
    mark_mission_workspace_dirty(session)
    session[CREATIVE_WORKSPACE_LAST_SAVE_REASON_KEY] = reason


def creative_workspace_state_restored(session: dict[str, Any]) -> bool:
    return bool(session.get(CREATIVE_WORKSPACE_RESTORED_KEY))


def sync_creative_workspace_state_before_persist(session: dict[str, Any], *, reason: str = "autosave") -> None:
    try:
        from creative_workspace_persistence import sync_creative_workspace_before_persist

        sync_creative_workspace_before_persist(session)
    except ImportError:
        pass
    gathered = gather_creative_workspace_from_session(session)
    write_canonical_creative_workspace(session, gathered, reason=reason)


def creative_workspace_for_envelope(session: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(gather_creative_workspace_from_session(session))


def _creative_workspace_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    top = payload.get(CREATIVE_WORKSPACE_STATE_KEY)
    if isinstance(top, dict) and _field_slice(top):
        return copy.deepcopy(top)
    ws = payload.get("music_workspace_state")
    if isinstance(ws, dict) and isinstance(ws.get(CREATIVE_WORKSPACE_STATE_KEY), dict):
        block = ws[CREATIVE_WORKSPACE_STATE_KEY]
        if _field_slice(block):
            return copy.deepcopy(block)
    return None


def _legacy_fields_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        from creative_workspace_persistence import creative_session_blob_from_envelope

        blob = creative_session_blob_from_envelope(payload)
    except ImportError:
        blob = {}
    if blob:
        return blob
    session_extra = payload.get("session") if isinstance(payload.get("session"), dict) else {}
    return {
        key: copy.deepcopy(session_extra[key])
        for key in CREATIVE_WORKSPACE_KEYS
        if isinstance(session_extra, dict) and key in session_extra
    }


def migrate_legacy_creative_workspace_once(
    session: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    if session.get(CREATIVE_WORKSPACE_MIGRATED_KEY):
        return None
    if _creative_workspace_from_payload(payload):
        session[CREATIVE_WORKSPACE_MIGRATED_KEY] = True
        return None
    legacy = _legacy_fields_from_payload(payload)
    if not legacy:
        session[CREATIVE_WORKSPACE_MIGRATED_KEY] = True
        return None
    blob = default_creative_workspace_state()
    blob.update(legacy)
    session[CREATIVE_WORKSPACE_MIGRATED_KEY] = True
    session["_creative_workspace_migrated_from"] = "session_flat_keys"
    return blob


def apply_creative_workspace_to_session(
    session: dict[str, Any],
    blob: dict[str, Any],
    *,
    source: str = "cloud_restore",
) -> None:
    canonical = upgrade_creative_workspace_blob(blob)
    write_canonical_creative_workspace(session, canonical, reason=source)
    session[CREATIVE_WORKSPACE_RESTORED_KEY] = True
    session.pop(CREATIVE_WORKSPACE_LAST_SKIP_KEY, None)
    try:
        from creative_workspace_persistence import hydrate_creative_workspace_after_restore

        hydrate_creative_workspace_after_restore(session)
    except ImportError:
        pass
    hydrate_mission_workspace_after_restore(session, adopt_practice_transport=True)
    session["_creative_restore_source"] = source
    session["_mission_restore_source"] = source
    session.pop("_creative_restore_skipped_reason", None)


def apply_creative_workspace_from_payload(
    session: dict[str, Any],
    payload: dict[str, Any],
    *,
    authoritative: bool = False,
) -> bool:
    if is_mission_workspace_locally_dirty(session) and not authoritative:
        session[CREATIVE_WORKSPACE_LAST_SKIP_KEY] = "local_dirty"
        session["_creative_restore_skipped_reason"] = "local_dirty"
        return False
    blob = _creative_workspace_from_payload(payload)
    if not blob:
        migrated = migrate_legacy_creative_workspace_once(session, payload)
        if migrated:
            apply_creative_workspace_to_session(session, migrated, source="legacy_migration")
            return True
        session[CREATIVE_WORKSPACE_LAST_SKIP_KEY] = "missing_in_envelope"
        return False
    apply_creative_workspace_to_session(
        session,
        blob,
        source="cloud_restore" if authoritative else "disk_restore",
    )
    session[CREATIVE_WORKSPACE_MIGRATED_KEY] = True
    return True


def prepare_creative_workspace_for_render(session: dict[str, Any]) -> None:
    """One-shot projection after cloud restore — never clobber live global controls on reruns."""
    try:
        from music_global_control_diagnostics import record_global_control_diag

        if session.get(CREATIVE_WORKSPACE_RESTORED_KEY):
            record_global_control_diag(session, creative_projection_attempted=True)
        else:
            record_global_control_diag(
                session,
                creative_projection_blocked_as_non_authoritative=True,
            )
    except ImportError:
        pass
    if not session.pop(CREATIVE_WORKSPACE_RESTORED_KEY, None):
        return
    project_creative_workspace_to_session(session, overwrite=True)
    session["_creative_workspace_restored_applied"] = True
    try:
        from music_global_control_diagnostics import record_global_control_diag

        record_global_control_diag(
            session,
            creative_workspace_restore_applied=True,
            overwrite_source="creative_workspace_state_persistence.prepare",
        )
    except ImportError:
        pass


def _cloud_creative_workspace_blob(cloud_state: dict[str, Any]) -> dict[str, Any]:
    block = _creative_workspace_from_payload(cloud_state)
    return block if isinstance(block, dict) else {}


def music_creative_workspace_state_cloud_drift(
    st: Any,
    cloud_state: dict[str, Any],
    cloud_ts: str | None,
) -> tuple[bool, str]:
    _ = cloud_ts
    ss = getattr(st, "session_state", st)
    if not isinstance(ss, dict):
        return False, ""
    if is_mission_workspace_locally_dirty(ss):
        return False, ""
    cloud_blob = _cloud_creative_workspace_blob(cloud_state)
    if not cloud_blob:
        return False, ""
    live = ss.get(CREATIVE_WORKSPACE_STATE_KEY)
    if not isinstance(live, dict):
        return True, "creative_workspace_missing_local"
    cloud_stamp = str(cloud_blob.get(MISSION_WORKSPACE_UPDATED_AT_KEY) or "")
    local_stamp = str(live.get(MISSION_WORKSPACE_UPDATED_AT_KEY) or ss.get(MISSION_WORKSPACE_UPDATED_AT_KEY) or "")
    if cloud_stamp and cloud_stamp != local_stamp:
        return True, f"creative_workspace_stamp:{local_stamp or 'none'}->{cloud_stamp}"
    for key in (
        "improv_mission_example",
        "improv_mission_practice_lick",
        "improv_motif",
        "improv_intelligence_tab",
        "harmony_map_chord",
        "creative_session",
    ):
        if key in cloud_blob and cloud_blob.get(key) != live.get(key):
            return True, f"creative_workspace:{key}"
    return False, ""


__all__ = [
    "CREATIVE_WORKSPACE_STATE_KEY",
    "apply_creative_workspace_from_payload",
    "apply_creative_workspace_to_session",
    "creative_workspace_for_envelope",
    "creative_workspace_state_restored",
    "default_creative_workspace_state",
    "gather_creative_workspace_from_session",
    "mark_creative_workspace_state_dirty",
    "migrate_legacy_creative_workspace_once",
    "music_creative_workspace_state_cloud_drift",
    "prepare_creative_workspace_for_render",
    "project_creative_workspace_to_session",
    "sync_creative_workspace_state_before_persist",
    "upgrade_creative_workspace_blob",
    "write_canonical_creative_workspace",
]

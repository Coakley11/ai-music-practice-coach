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


def _selector_value_empty(val: Any) -> bool:
    if val is None:
        return True
    return isinstance(val, str) and not val.strip()


def gather_creative_workspace_from_session(session: dict[str, Any]) -> dict[str, Any]:
    base = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    if not isinstance(base, dict):
        base = default_creative_workspace_state()
    else:
        base = upgrade_creative_workspace_blob(base)
    preserved_selectors = {
        k: copy.deepcopy(base[k])
        for k in base
        if k
        in (
            "improv_intelligence_tab",
            "creative_improv_intelligence_tab",
            "improv_entry_mode",
            "creative_lab_analysis_mode",
            "creative_lab_last_mode",
        )
        and not _selector_value_empty(base.get(k))
    }
    try:
        from creative_selector_hydration_trace import (
            CREATIVE_SELECTOR_LAST_CONFIRMED_KEY,
            merge_selector_fields_into_blob,
        )

        last_conf = session.get(CREATIVE_SELECTOR_LAST_CONFIRMED_KEY)
        if isinstance(last_conf, dict):
            merge_selector_fields_into_blob(base, last_conf)
    except ImportError:
        pass

    persist_reason = str(
        session.get("_music_build_save_reason")
        or session.get("_suite_pending_save_reason")
        or session.get(CREATIVE_WORKSPACE_LAST_SAVE_REASON_KEY)
        or "autosave"
    )
    for key in CREATIVE_WORKSPACE_KEYS:
        if key in session:
            val = session[key]
            if key in preserved_selectors and _selector_value_empty(val):
                continue
            try:
                from creative_tab_tool_persistence import should_gather_selector_from_session

                if not should_gather_selector_from_session(
                    session, key, val, persist_reason=persist_reason
                ):
                    continue
            except ImportError:
                pass
            try:
                from creative_mission_config_persistence import should_gather_mission_config_from_session

                if not should_gather_mission_config_from_session(
                    session, key, val, persist_reason=persist_reason
                ):
                    continue
            except ImportError:
                pass
            base[key] = copy.deepcopy(val)
    for key, val in preserved_selectors.items():
        if _selector_value_empty(base.get(key)):
            base[key] = copy.deepcopy(val)
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
    prior = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    prior_dict = prior if isinstance(prior, dict) else {}
    canonical = upgrade_creative_workspace_blob(blob)
    try:
        from creative_selector_hydration_trace import (
            SELECTOR_CANONICAL_FIELDS,
            record_selector_field_write,
        )

        for field in SELECTOR_CANONICAL_FIELDS:
            old_v = prior_dict.get(field)
            new_v = canonical.get(field)
            if old_v != new_v:
                record_selector_field_write(
                    session,
                    field,
                    old_value=old_v,
                    new_value=new_v,
                    function="write_canonical_creative_workspace",
                    reason=reason,
                    authoritative_restore=bool(session.get("_cloud_workspace_restored_this_run")),
                    default_initialization=reason == "migration_local",
                )
    except ImportError:
        pass
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
    try:
        from creative_tab_tool_persistence import note_passive_creative_tab_persist

        note_passive_creative_tab_persist(session, reason=reason)
    except ImportError:
        pass
    try:
        from creative_mission_config_persistence import note_passive_mission_config_persist

        note_passive_mission_config_persist(session, reason=reason)
    except ImportError:
        pass
    gathered = gather_creative_workspace_from_session(session)
    write_canonical_creative_workspace(session, gathered, reason=reason)


def creative_workspace_for_envelope(session: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(gather_creative_workspace_from_session(session))


def _creative_workspace_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    try:
        from creative_selector_hydration_trace import extract_merged_creative_blob_from_payload

        merged = extract_merged_creative_blob_from_payload(payload)
        if _field_slice(merged):
            return merged
    except ImportError:
        pass
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
    try:
        from creative_selector_hydration_trace import SELECTOR_CANONICAL_FIELDS, record_canonical_stage

        prior = session.get(CREATIVE_WORKSPACE_STATE_KEY)
        prior_dict = prior if isinstance(prior, dict) else {}
        for field in SELECTOR_CANONICAL_FIELDS:
            record_canonical_stage(
                session,
                "apply_creative_workspace_to_session",
                field,
                canonical_before=prior_dict.get(field),
                incoming_value=blob.get(field),
                canonical_after=None,
                widget_after=session.get(field),
                function="apply_creative_workspace_to_session",
                branch=source,
                authoritative_restore=source.startswith("cloud"),
            )
    except ImportError:
        pass
    canonical = upgrade_creative_workspace_blob(blob)
    write_canonical_creative_workspace(session, canonical, reason=source)
    session[CREATIVE_WORKSPACE_RESTORED_KEY] = True
    session.pop(CREATIVE_WORKSPACE_LAST_SKIP_KEY, None)
    try:
        from creative_tab_tool_persistence import (
            project_creative_selectors_from_canonical,
            snapshot_hydrated_creative_selectors,
        )

        project_creative_selectors_from_canonical(session, overwrite=True)
        snapshot_hydrated_creative_selectors(session, source=source)
    except ImportError:
        pass
    try:
        from creative_mission_config_persistence import (
            project_mission_config_from_canonical,
            snapshot_hydrated_mission_config,
        )

        project_mission_config_from_canonical(session, overwrite=True)
        snapshot_hydrated_mission_config(session, source=source)
    except ImportError:
        pass
    project_creative_workspace_to_session(session, overwrite=True)
    try:
        from creative_selector_hydration_trace import mark_selector_hydration_complete

        mark_selector_hydration_complete(session, source=source)
    except ImportError:
        pass
    try:
        from creative_workspace_persistence import hydrate_creative_workspace_after_restore

        hydrate_creative_workspace_after_restore(session)
    except ImportError:
        pass
    hydrate_mission_workspace_after_restore(session, adopt_practice_transport=True)
    session["_creative_restore_source"] = source
    session["_mission_restore_source"] = source
    session.pop("_creative_restore_skipped_reason", None)


def merge_incoming_creative_workspace_state(
    session: dict[str, Any],
    incoming: dict[str, Any],
    *,
    source: str = "payload",
) -> None:
    """Apply payload creative_workspace_state without empty selector overwrites."""
    if not isinstance(incoming, dict):
        return
    existing = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    base = upgrade_creative_workspace_blob(existing if isinstance(existing, dict) else default_creative_workspace_state())
    upgraded_in = upgrade_creative_workspace_blob(incoming)
    for key, val in upgraded_in.items():
        if key in (
            "improv_intelligence_tab",
            "creative_improv_intelligence_tab",
            "improv_entry_mode",
            "creative_lab_analysis_mode",
            "creative_lab_last_mode",
        ) and _selector_value_empty(val):
            continue
        base[key] = copy.deepcopy(val)
    session[CREATIVE_WORKSPACE_STATE_KEY] = base
    try:
        from creative_selector_hydration_trace import record_canonical_stage, SELECTOR_CANONICAL_FIELDS

        for field in SELECTOR_CANONICAL_FIELDS:
            record_canonical_stage(
                session,
                "merge_incoming_creative_workspace_state",
                field,
                canonical_before=(existing or {}).get(field) if isinstance(existing, dict) else None,
                incoming_value=incoming.get(field),
                canonical_after=base.get(field),
                widget_after=session.get(field),
                function="merge_incoming_creative_workspace_state",
                branch=source,
            )
    except ImportError:
        pass


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
    try:
        from creative_selector_hydration_trace import (
            SELECTOR_CANONICAL_FIELDS,
            _LEGACY_SESSION_PATH,
            _TOP_CWS_PATH,
            record_envelope_extraction,
        )

        for field in SELECTOR_CANONICAL_FIELDS:
            path = ""
            val = None
            status = "absent"
            if isinstance(blob, dict) and field in blob and not _selector_value_empty(blob.get(field)):
                path = "merged_envelope"
                val = blob.get(field)
                status = "valid"
            else:
                sess = payload.get("session") if isinstance(payload.get("session"), dict) else {}
                if isinstance(sess, dict) and field in sess and not _selector_value_empty(sess.get(field)):
                    path = _LEGACY_SESSION_PATH
                    val = sess.get(field)
                    status = "valid"
                top = payload.get(CREATIVE_WORKSPACE_STATE_KEY)
                if status == "absent" and isinstance(top, dict) and field in top:
                    path = _TOP_CWS_PATH
                    val = top.get(field)
                    status = "empty" if _selector_value_empty(val) else "valid"
            record_envelope_extraction(
                session,
                field,
                source_path=path or "none",
                extracted_value=val,
                status=status,
                migration_source="apply_creative_workspace_from_payload",
                migration_result=str(blob is not None),
            )
    except ImportError:
        pass
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
    try:
        from creative_selector_hydration_trace import SELECTOR_CANONICAL_FIELDS, merge_selector_fields_into_blob

        canon = session.get(CREATIVE_WORKSPACE_STATE_KEY)
        if isinstance(canon, dict):
            flat = {f: session.get(f) for f in SELECTOR_CANONICAL_FIELDS if session.get(f)}
            merge_selector_fields_into_blob(canon, flat)
            session[CREATIVE_WORKSPACE_STATE_KEY] = canon
            for f in SELECTOR_CANONICAL_FIELDS:
                if not _selector_value_empty(canon.get(f)):
                    session[f] = canon[f]
    except ImportError:
        pass
    try:
        from creative_tab_tool_persistence import migrate_invalid_creative_selectors

        migrate_invalid_creative_selectors(session, source="cloud_apply" if authoritative else "disk_apply")
    except ImportError:
        pass
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
    try:
        from creative_tab_tool_persistence import (
            migrate_invalid_creative_selectors,
            project_creative_selectors_from_canonical,
            snapshot_hydrated_creative_selectors,
        )

        migrate_invalid_creative_selectors(session, source="prepare")
        project_creative_selectors_from_canonical(session, overwrite=True)
        snapshot_hydrated_creative_selectors(session, source="prepare")
        try:
            from creative_tab_tool_persistence import establish_selector_defaults_when_cloud_empty

            establish_selector_defaults_when_cloud_empty(session)
        except ImportError:
            pass
        try:
            from creative_mission_config_persistence import (
                project_mission_config_from_canonical,
                snapshot_hydrated_mission_config,
            )

            project_mission_config_from_canonical(session, overwrite=True)
            snapshot_hydrated_mission_config(session, source="prepare")
        except ImportError:
            pass
        try:
            from creative_selector_hydration_trace import (
                SELECTOR_CANONICAL_FIELDS,
                audit_selector_hydration_after_restore,
                mark_selector_hydration_complete,
                record_canonical_stage,
            )

            canon = session.get(CREATIVE_WORKSPACE_STATE_KEY)
            canon_dict = canon if isinstance(canon, dict) else {}
            for field in SELECTOR_CANONICAL_FIELDS:
                record_canonical_stage(
                    session,
                    "prepare_creative_workspace_for_render",
                    field,
                    canonical_before=canon_dict.get(field),
                    incoming_value=canon_dict.get(field),
                    canonical_after=canon_dict.get(field),
                    widget_after=session.get(field),
                    function="prepare_creative_workspace_for_render",
                    branch="after_projection",
                )
            mark_selector_hydration_complete(session, source="prepare")
            audit_selector_hydration_after_restore(session)
        except ImportError:
            pass
    except ImportError:
        pass
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

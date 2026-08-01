"""Cloud + page-snapshot persistence for Improvisation Intelligence Missions.

Long-term design contract (frozen): cursor-prompts/plans/2026-07-30-mission-workspace-contract.md
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from improvisation_missions import (
    MISSION_EXAMPLE_KEY,
    MISSION_NEW_NONCE_KEY,
    MISSION_PRACTICE_LICK_KEY,
    MISSION_VARIANT_KEY,
)

MISSION_WORKSPACE_UPDATED_AT_KEY = "improv_mission_workspace_updated_at"
MISSION_LOCAL_DIRTY_KEY = "_mission_workspace_local_dirty"

# Flat session keys mirrored to workspace envelope (see music_persistent_state._PERSIST_KEYS).
MISSION_WORKSPACE_KEYS: tuple[str, ...] = (
    "improv_active_mission",
    "improv_mission_pick",
    MISSION_EXAMPLE_KEY,
    MISSION_VARIANT_KEY,
    MISSION_NEW_NONCE_KEY,
    MISSION_PRACTICE_LICK_KEY,
    "improv_mission_chord_options",
    "improv_mission_progression",
    "ii_selected_chord",
    "ii_selected_section",
    "ii_selected_chord_index",
    "ii_selected_chord_label",
    MISSION_WORKSPACE_UPDATED_AT_KEY,
)
# Creative + backing page snapshots (page-local UI).
MISSION_PAGE_SNAPSHOT_KEYS: frozenset[str] = frozenset(MISSION_WORKSPACE_KEYS)


def _merge_mission_keys_into_creative_snapshot(session: dict[str, Any]) -> None:
    """Keep creative snapshot warm while user practices on Backing Jam."""
    store = session.get("_studio_page_snapshots")
    if not isinstance(store, dict):
        return
    creative = store.get("creative")
    if not isinstance(creative, dict):
        creative = {}
    else:
        creative = dict(creative)
    changed = False
    for key in MISSION_PAGE_SNAPSHOT_KEYS:
        if key not in session:
            continue
        val = copy.deepcopy(session[key])
        if creative.get(key) != val:
            creative[key] = val
            changed = True
    if changed:
        store["creative"] = creative


def _refresh_practice_lick_transport(session: dict[str, Any]) -> None:
    raw = session.get(MISSION_PRACTICE_LICK_KEY)
    if not isinstance(raw, dict) or not raw.get("motif"):
        return
    payload = dict(raw)
    bpm = session.get("backing_track_bpm")
    if bpm is not None:
        try:
            payload["bpm"] = int(bpm)
        except (TypeError, ValueError):
            pass
    groove = session.get("backing_groove_style")
    if groove:
        payload["groove"] = str(groove)
    meter = session.get("backing_time_signature")
    if meter:
        payload["meter"] = str(meter)
    scope = session.get("backing_track_scope")
    if scope:
        payload["backing_track_scope"] = str(scope)
    loops = session.get("backing_track_loops")
    if loops is not None:
        try:
            payload["backing_track_loops"] = int(loops)
        except (TypeError, ValueError):
            pass
    single = session.get("backing_track_single_section")
    if single:
        payload["backing_track_single_section"] = str(single)
    multi = session.get("backing_track_multi_sections")
    if isinstance(multi, list) and multi:
        payload["backing_track_multi_sections"] = list(multi)
    session[MISSION_PRACTICE_LICK_KEY] = payload


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def mark_mission_workspace_dirty(session: dict[str, Any]) -> None:
    """Same-run guard: block cloud overlay until the next successful persist."""
    session[MISSION_LOCAL_DIRTY_KEY] = True


def clear_mission_workspace_local_edit(session: dict[str, Any]) -> None:
    session.pop(MISSION_LOCAL_DIRTY_KEY, None)


def is_mission_workspace_locally_dirty(session: dict[str, Any]) -> bool:
    return bool(session.get(MISSION_LOCAL_DIRTY_KEY))


def mission_session_blob_from_envelope(state: dict[str, Any]) -> dict[str, Any]:
    """Extract mission keys from a music disk/cloud envelope."""
    if not isinstance(state, dict):
        return {}
    session_extra = state.get("session")
    if not isinstance(session_extra, dict):
        session_extra = state
    return {
        key: copy.deepcopy(session_extra[key])
        for key in MISSION_WORKSPACE_KEYS
        if key in session_extra
    }


def sync_mission_workspace_before_persist(session: dict[str, Any]) -> None:
    """Capture mission + full Creative workspace before disk/cloud save."""
    try:
        from creative_workspace_persistence import sync_creative_workspace_before_persist

        sync_creative_workspace_before_persist(session)
    except ImportError:
        _legacy_sync_mission_workspace_before_persist(session)


def _legacy_sync_mission_workspace_before_persist(session: dict[str, Any]) -> None:
    if not any(session.get(k) for k in MISSION_WORKSPACE_KEYS if k != MISSION_WORKSPACE_UPDATED_AT_KEY):
        return
    _refresh_practice_lick_transport(session)
    page = str(session.get("studio_page") or "").strip().lower()
    if page == "backing":
        _merge_mission_keys_into_creative_snapshot(session)
    try:
        from studio_page_persistence import save_page_snapshot

        save_page_snapshot(session, "creative")
        if page == "backing":
            save_page_snapshot(session, "backing")
    except ImportError:
        pass
    try:
        from creative_session_state import sync_creative_session_before_persist

        sync_creative_session_before_persist(session)
    except ImportError:
        pass
    session[MISSION_WORKSPACE_UPDATED_AT_KEY] = _utc_now_iso()
    clear_mission_workspace_local_edit(session)


def hydrate_mission_workspace_after_restore(
    session: dict[str, Any],
    *,
    adopt_practice_transport: bool = False,
) -> None:
    """Reconcile mission chord picks and practice lick after cloud/local restore."""
    example = session.get(MISSION_EXAMPLE_KEY)
    if isinstance(example, dict):
        chord = str(example.get("chord") or "").strip()
        section = str(example.get("section") or "").strip()
        if chord and not str(session.get("ii_selected_chord") or "").strip():
            session["ii_selected_chord"] = chord
        if section and not str(session.get("ii_selected_section") or "").strip():
            session["ii_selected_section"] = section
        mission = str(example.get("mission") or "").strip()
        if mission:
            session.setdefault("improv_active_mission", mission)
            session.setdefault("improv_mission_pick", mission)
        variant = str(example.get("variant") or "").strip()
        if variant:
            session.setdefault(MISSION_VARIANT_KEY, variant)

    payload = session.get(MISSION_PRACTICE_LICK_KEY)
    if isinstance(payload, dict):
        bpm = payload.get("bpm")
        if bpm is not None and (adopt_practice_transport or session.get("backing_track_bpm") is None):
            try:
                session["backing_track_bpm"] = int(bpm)
            except (TypeError, ValueError):
                pass
        if payload.get("groove") and (adopt_practice_transport or not session.get("backing_groove_style")):
            session["backing_groove_style"] = str(payload["groove"])
        if payload.get("meter") and (adopt_practice_transport or not session.get("backing_time_signature")):
            session["backing_time_signature"] = str(payload["meter"])
        if payload.get("backing_track_loops") is not None and (
            adopt_practice_transport or session.get("backing_track_loops") is None
        ):
            session["backing_track_loops"] = payload.get("backing_track_loops")
        if payload.get("backing_track_scope") and (
            adopt_practice_transport or not session.get("backing_track_scope")
        ):
            session["backing_track_scope"] = payload.get("backing_track_scope")
        if payload.get("backing_track_single_section") and (
            adopt_practice_transport or not session.get("backing_track_single_section")
        ):
            session["backing_track_single_section"] = payload.get("backing_track_single_section")
        multi = payload.get("backing_track_multi_sections")
        if isinstance(multi, list) and multi and (
            adopt_practice_transport or not session.get("backing_track_multi_sections")
        ):
            session["backing_track_multi_sections"] = list(multi)


def apply_cloud_mission_state_if_allowed(session: dict[str, Any], state: dict[str, Any]) -> bool:
    """Apply cloud Creative workspace when it differs (latest saved state wins)."""
    try:
        from creative_workspace_persistence import apply_cloud_creative_state_if_allowed

        return apply_cloud_creative_state_if_allowed(session, state)
    except ImportError:
        return _legacy_apply_cloud_mission_state_if_allowed(session, state)


def _legacy_apply_cloud_mission_state_if_allowed(session: dict[str, Any], state: dict[str, Any]) -> bool:
    if is_mission_workspace_locally_dirty(session):
        session["_mission_restore_skipped_reason"] = "local_dirty"
        return False
    blob = mission_session_blob_from_envelope(state)
    if not blob:
        session.pop("_mission_restore_source", None)
        return False
    cloud_stamp = str(blob.get(MISSION_WORKSPACE_UPDATED_AT_KEY) or "")
    local_stamp = str(session.get(MISSION_WORKSPACE_UPDATED_AT_KEY) or "")
    same_example = blob.get(MISSION_EXAMPLE_KEY) == session.get(MISSION_EXAMPLE_KEY)
    same_lick = blob.get(MISSION_PRACTICE_LICK_KEY) == session.get(MISSION_PRACTICE_LICK_KEY)
    if cloud_stamp and cloud_stamp == local_stamp and same_example and same_lick:
        return False
    for key, val in blob.items():
        session[key] = copy.deepcopy(val)
    hydrate_mission_workspace_after_restore(session, adopt_practice_transport=True)
    session["_mission_restore_source"] = "cloud_restore"
    session.pop("_mission_restore_skipped_reason", None)
    clear_mission_workspace_local_edit(session)
    return True


def music_mission_cloud_drift(
    st: Any,
    cloud_state: dict[str, Any],
    cloud_ts: str | None,
) -> tuple[bool, str]:
    """Detect cross-device drift in the Creative workspace."""
    try:
        from creative_workspace_persistence import music_creative_cloud_drift

        return music_creative_cloud_drift(st, cloud_state, cloud_ts)
    except ImportError:
        pass
    _ = cloud_ts
    ss = getattr(st, "session_state", st)
    if not isinstance(ss, dict):
        return False, ""
    if is_mission_workspace_locally_dirty(ss):
        return False, ""
    blob = mission_session_blob_from_envelope(cloud_state)
    if not blob:
        return False, ""
    cloud_stamp = str(blob.get(MISSION_WORKSPACE_UPDATED_AT_KEY) or "")
    local_stamp = str(ss.get(MISSION_WORKSPACE_UPDATED_AT_KEY) or "")
    if cloud_stamp and cloud_stamp != local_stamp:
        return True, f"mission_stamp:{local_stamp or 'none'}->{cloud_stamp}"
    if blob.get(MISSION_EXAMPLE_KEY) != ss.get(MISSION_EXAMPLE_KEY):
        return True, "mission_example"
    if blob.get(MISSION_PRACTICE_LICK_KEY) != ss.get(MISSION_PRACTICE_LICK_KEY):
        return True, "mission_practice_lick"
    return False, ""


__all__ = [
    "MISSION_LOCAL_DIRTY_KEY",
    "MISSION_PAGE_SNAPSHOT_KEYS",
    "MISSION_WORKSPACE_KEYS",
    "MISSION_WORKSPACE_UPDATED_AT_KEY",
    "apply_cloud_mission_state_if_allowed",
    "clear_mission_workspace_local_edit",
    "hydrate_mission_workspace_after_restore",
    "is_mission_workspace_locally_dirty",
    "mark_mission_workspace_dirty",
    "mission_session_blob_from_envelope",
    "music_mission_cloud_drift",
    "sync_mission_workspace_before_persist",
]
"""Cloud workspace for the full Creative page (tabs, generated artifacts, Mission Jam).

Design: extend the Mission workspace contract — one account workspace, latest save wins.
See cursor-prompts/plans/2026-07-30-mission-workspace-contract.md
"""

from __future__ import annotations

import copy
from typing import Any

from improvisation_mission_persistence import (
    MISSION_LOCAL_DIRTY_KEY,
    MISSION_WORKSPACE_KEYS,
    MISSION_WORKSPACE_UPDATED_AT_KEY,
    _merge_mission_keys_into_creative_snapshot,
    _refresh_practice_lick_transport,
    _utc_now_iso,
    clear_mission_workspace_local_edit,
    hydrate_mission_workspace_after_restore,
    is_mission_workspace_locally_dirty,
    mark_mission_workspace_dirty,
)

# Keys beyond Mission Jam that must sync cross-device with the Creative document.
CREATIVE_WORKSPACE_EXTRA_KEYS: tuple[str, ...] = (
    "improv_intelligence_tab",
    "creative_improv_intelligence_tab",
    "creative_lab_analysis_mode",
    "creative_lab_last_mode",
    "improv_entry_mode",
    "improv_motif",
    "improv_motif_output_mode",
    "improv_motif_abc",
    "improv_motif_tab",
    "harmony_map_section",
    "harmony_map_chord",
    "deep_harmony_lesson_step",
    "improv_deep_harmony_dha_section_idx",
    "improv_generated_sections",
    "improv_style_meta",
    "improv_jam_session",
    "creative_session",
    "improv_ai_metric_ids",
    "analysis_criteria_locked",
)

CREATIVE_WORKSPACE_KEYS: tuple[str, ...] = tuple(
    dict.fromkeys(MISSION_WORKSPACE_KEYS + CREATIVE_WORKSPACE_EXTRA_KEYS)
)

CREATIVE_PAGE_SNAPSHOT_KEYS: frozenset[str] = frozenset(CREATIVE_WORKSPACE_KEYS)


def mark_creative_workspace_dirty(session: dict[str, Any]) -> None:
    """Block cloud overlay until the next successful persist (same flag as Mission)."""
    mark_mission_workspace_dirty(session)


def _session_has_creative_workspace(session: dict[str, Any]) -> bool:
    page = str(session.get("studio_page") or "").strip().lower()
    if page in ("creative", "backing"):
        return True
    return any(
        session.get(k)
        for k in CREATIVE_WORKSPACE_KEYS
        if k != MISSION_WORKSPACE_UPDATED_AT_KEY
    )


def creative_session_blob_from_envelope(state: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    session_extra = state.get("session")
    if not isinstance(session_extra, dict):
        session_extra = state
    return {
        key: copy.deepcopy(session_extra[key])
        for key in CREATIVE_WORKSPACE_KEYS
        if key in session_extra
    }


def sync_creative_workspace_before_persist(session: dict[str, Any]) -> None:
    """Capture full Creative workspace immediately before disk/cloud save."""
    try:
        from mission_backing_handoff_persistence import should_skip_creative_sync_for_handoff_page_change

        if should_skip_creative_sync_for_handoff_page_change(session):
            return
    except ImportError:
        pass
    if not _session_has_creative_workspace(session):
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


def hydrate_creative_workspace_after_restore(session: dict[str, Any]) -> None:
    """Rebuild derived Phrase & Motif outputs from stored motif when ABC/TAB missing."""
    motif = session.get("improv_motif")
    if not isinstance(motif, dict) or not motif.get("notes"):
        return
    need_abc = session.get("improv_motif_output_mode") == "notation" and not session.get(
        "improv_motif_abc"
    )
    need_tab = session.get("improv_motif_output_mode") == "tab" and not session.get("improv_motif_tab")
    if not need_abc and not need_tab:
        return
    try:
        from improvisation_intelligence import coaching_reference_key
        from improvisation_motif import (
            build_motif_guitar_tab,
            build_motif_notation_abc,
            sync_motif_midi,
        )

        ref = coaching_reference_key(
            key_center=str(session.get("practice_concert_key") or session.get("concert_key") or "C"),
            display_key=str(session.get("chart_key") or session.get("written_key") or "C"),
        )
        motif = sync_motif_midi(dict(motif))
        session["improv_motif"] = motif
        bpm = 100
        try:
            bpm = int(session.get("backing_track_bpm") or session.get("bpm") or 100)
        except (TypeError, ValueError):
            pass
        if need_abc:
            session["improv_motif_abc"] = build_motif_notation_abc(
                motif, key_center=ref, bpm=bpm
            )
        if need_tab:
            session["improv_motif_tab"] = build_motif_guitar_tab(motif)
    except ImportError:
        pass


def apply_cloud_creative_state_if_allowed(session: dict[str, Any], state: dict[str, Any]) -> bool:
    try:
        from creative_workspace_state_persistence import apply_creative_workspace_from_payload

        if apply_creative_workspace_from_payload(session, state, authoritative=False):
            return True
    except ImportError:
        pass
    if is_mission_workspace_locally_dirty(session):
        session["_creative_restore_skipped_reason"] = "local_dirty"
        return False
    blob = creative_session_blob_from_envelope(state)
    if not blob:
        session.pop("_creative_restore_source", None)
        return False
    cloud_stamp = str(blob.get(MISSION_WORKSPACE_UPDATED_AT_KEY) or "")
    local_stamp = str(session.get(MISSION_WORKSPACE_UPDATED_AT_KEY) or "")
    if cloud_stamp and cloud_stamp == local_stamp:
        local_slice = {k: session.get(k) for k in blob if k in session}
        if local_slice == {k: blob[k] for k in local_slice}:
            return False
    for key, val in blob.items():
        session[key] = copy.deepcopy(val)
    hydrate_mission_workspace_after_restore(session, adopt_practice_transport=True)
    hydrate_creative_workspace_after_restore(session)
    session["_creative_restore_source"] = "cloud_restore"
    session["_mission_restore_source"] = "cloud_restore"
    session.pop("_creative_restore_skipped_reason", None)
    clear_mission_workspace_local_edit(session)
    return True


def music_creative_cloud_drift(
    st: Any,
    cloud_state: dict[str, Any],
    cloud_ts: str | None,
) -> tuple[bool, str]:
    try:
        from creative_workspace_state_persistence import music_creative_workspace_state_cloud_drift

        drift, detail = music_creative_workspace_state_cloud_drift(st, cloud_state, cloud_ts)
        if drift:
            return drift, detail
    except ImportError:
        pass
    _ = cloud_ts
    ss = getattr(st, "session_state", st)
    if not isinstance(ss, dict):
        return False, ""
    if is_mission_workspace_locally_dirty(ss):
        return False, ""
    blob = creative_session_blob_from_envelope(cloud_state)
    if not blob:
        return False, ""
    cloud_stamp = str(blob.get(MISSION_WORKSPACE_UPDATED_AT_KEY) or "")
    local_stamp = str(ss.get(MISSION_WORKSPACE_UPDATED_AT_KEY) or "")
    if cloud_stamp and cloud_stamp != local_stamp:
        return True, f"creative_stamp:{local_stamp or 'none'}->{cloud_stamp}"
    for key in (
        "improv_mission_example",
        "improv_mission_practice_lick",
        "improv_motif",
        "improv_intelligence_tab",
        "harmony_map_chord",
    ):
        if key in blob and blob.get(key) != ss.get(key):
            return True, key
    return False, ""


__all__ = [
    "CREATIVE_PAGE_SNAPSHOT_KEYS",
    "CREATIVE_WORKSPACE_EXTRA_KEYS",
    "CREATIVE_WORKSPACE_KEYS",
    "apply_cloud_creative_state_if_allowed",
    "creative_session_blob_from_envelope",
    "hydrate_creative_workspace_after_restore",
    "mark_creative_workspace_dirty",
    "music_creative_cloud_drift",
    "sync_creative_workspace_before_persist",
]

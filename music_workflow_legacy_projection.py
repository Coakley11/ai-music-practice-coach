"""One-way projection from authoritative workflow blob → legacy session keys (Commit 2)."""

from __future__ import annotations

import copy
from typing import Any

from music_workflow_state_store import (
    WorkflowStateBlob,
    record_compat_fallback,
    record_legacy_field_read,
)

# Legacy keys written by projection (documented for dev diagnostics / migration).
PROJECTED_LEGACY_KEYS: dict[str, tuple[str, ...]] = {
    "song_based_improvisation": (
        "display_key",
        "concert_key",
        "_pending_display_key",
        "improv_song_concert_sections",
    ),
    "mission_jam": (
        "display_key",
        "concert_key",
        "_pending_display_key",
        "improv_song_concert_sections",
        "ii_selected_chord",
        "ii_selected_section",
        "ii_selected_chord_index",
        "improv_active_mission",
        "improv_mission_pick",
        "improv_intelligence_tab",
        "creative_improv_intelligence_tab",
    ),
    "style_jam": (
        "improv_entry_mode",
        "improv_style_key",
        "improv_style",
        "improv_mood",
        "improv_groove",
        "improv_style_bpm",
        "improv_generated_sections",
        "display_key",
        "concert_key",
        "_pending_display_key",
    ),
    "jam_session_generator": (
        "improv_entry_mode",
        "improv_jam_key",
        "improv_jam_style",
        "improv_jam_mood",
        "improv_jam_bpm",
        "improv_jam_session",
        "display_key",
        "concert_key",
    ),
    "regular_catalog_backing": ("studio_page",),
    "regular_custom_backing": ("studio_page",),
    "entry_jam": ("improv_entry_mode", "display_key", "concert_key"),
}


def _practice_key_token(blob: WorkflowStateBlob) -> str:
    tonic = str(blob.keys.practice_tonic or "C").strip() or "C"
    mode = str(blob.keys.practice_mode or "major").strip().lower()
    if mode == "minor":
        return f"{tonic}m" if not tonic.endswith("m") else tonic
    return tonic


def clear_incompatible_legacy_fields(session: dict[str, Any], owner: str) -> list[str]:
    """Remove transient fields that conflict with the active workflow owner."""
    cleared: list[str] = []
    if owner == "mission_jam":
        for key in ("improv_generated_sections",):
            if session.pop(key, None) is not None:
                cleared.append(key)
        try:
            from generated_jam_key_context import deactivate_generated_jam_key_ownership

            deactivate_generated_jam_key_ownership(session)
            cleared.append("generated_jam_ownership")
        except ImportError:
            pass
    elif owner in {"style_jam", "jam_session_generator"}:
        pass
    elif owner == "song_based_improvisation":
        if str(session.get("improv_intelligence_tab") or "") == "Missions":
            pass
    record_compat_fallback(session, "clear_incompatible_legacy_fields", owner)
    return cleared


def restore_workflow_blob_to_session(session: dict[str, Any], blob: WorkflowStateBlob) -> None:
    """Apply authoritative blob fields to session (full restore, not display-only)."""
    owner = str(blob.workflow_owner or "").strip()
    key_token = _practice_key_token(blob)
    if owner in {"song_based_improvisation", "mission_jam"}:
        if blob.section_map:
            session["improv_song_concert_sections"] = copy.deepcopy(blob.section_map)
        if blob.song_id:
            record_legacy_field_read(session, "active_catalog_pick_key", adapter="restore")
        try:
            from creative_key_sync import apply_creative_concert_key

            apply_creative_concert_key(session, key_token, source=f"workflow_restore_{owner}")
        except ImportError:
            pass
        session["display_key"] = key_token
        session["concert_key"] = key_token
        session["_pending_display_key"] = key_token
    if owner == "mission_jam":
        session["improv_intelligence_tab"] = "Missions"
        session["creative_improv_intelligence_tab"] = "Missions"
        if blob.selected_chord_symbol:
            session["ii_selected_chord"] = blob.selected_chord_symbol
        if blob.selected_section:
            session["ii_selected_section"] = blob.selected_section
        session["ii_selected_chord_index"] = int(blob.selected_chord_index or 0)
        if blob.mission_type:
            session["improv_active_mission"] = blob.mission_type
            session["improv_mission_pick"] = blob.mission_type
        try:
            from generated_jam_key_context import deactivate_generated_jam_key_ownership

            deactivate_generated_jam_key_ownership(session)
        except ImportError:
            pass
        try:
            from workflow_musical_authority import ACTIVE_WORKFLOW_OWNER_KEY

            from music_workflow_mutation import set_legacy_owner_compat_hint

            set_legacy_owner_compat_hint(session, "mission_jam")
        except ImportError:
            pass
    elif owner == "style_jam":
        session["improv_entry_mode"] = "Style Jam Mode"
        session["improv_style_key"] = key_token
        session["improv_style"] = str(blob.style or blob.generated_session_id or "").strip()
        session["improv_mood"] = str(blob.mood or "").strip()
        session["improv_groove"] = str(blob.groove or "").strip()
        if blob.tempo_bpm:
            session["improv_style_bpm"] = int(blob.tempo_bpm)
        if blob.section_map:
            session["improv_generated_sections"] = copy.deepcopy(blob.section_map)
        try:
            from creative_key_sync import apply_creative_concert_key, IMPROV_STYLE_KEY_TRACKER

            apply_creative_concert_key(session, key_token, source="workflow_restore_style_jam")
            session[IMPROV_STYLE_KEY_TRACKER] = key_token
        except ImportError:
            pass
        session["display_key"] = key_token
        session["concert_key"] = key_token
        session["_pending_display_key"] = key_token
        try:
            from music_workflow_mutation import set_legacy_owner_compat_hint

            set_legacy_owner_compat_hint(session, "style_jam")
        except ImportError:
            pass
    elif owner == "jam_session_generator":
        session["improv_entry_mode"] = "Jam Session Generator"
        session["improv_jam_key"] = key_token
        session["improv_jam_style"] = str(blob.style or "").strip()
        session["improv_jam_mood"] = str(blob.mood or "").strip()
        if blob.tempo_bpm:
            session["improv_jam_bpm"] = int(blob.tempo_bpm)
        jam: dict[str, Any] = {}
        if isinstance(session.get("improv_jam_session"), dict):
            jam = copy.deepcopy(session["improv_jam_session"])
        if blob.generated_session_id:
            jam["id"] = blob.generated_session_id
        if blob.section_map:
            jam["sections"] = copy.deepcopy(blob.section_map)
        if jam:
            session["improv_jam_session"] = jam
        try:
            from creative_key_sync import apply_creative_concert_key, IMPROV_JAM_KEY_TRACKER
            from generated_jam_key_context import activate_generated_jam_key_ownership

            apply_creative_concert_key(session, key_token, source="workflow_restore_jam_gen")
            session[IMPROV_JAM_KEY_TRACKER] = key_token
            activate_generated_jam_key_ownership(session, entry_mode="Jam Session Generator")
        except ImportError:
            pass
        session["display_key"] = key_token
        session["concert_key"] = key_token
        session["_pending_display_key"] = key_token
        try:
            from music_workflow_mutation import set_legacy_owner_compat_hint

            set_legacy_owner_compat_hint(session, "jam_session_generator")
        except ImportError:
            pass
    elif owner == "song_based_improvisation":
        try:
            from music_workflow_mutation import set_legacy_owner_compat_hint

            set_legacy_owner_compat_hint(session, "song_based_improvisation")
        except ImportError:
            pass
    # Navigation routes are never applied from blob restore (Commit 3 B2).
    if blob.return_to_source_route or blob.return_route:
        session["_music_workflow_return_route"] = str(blob.return_to_source_route or blob.return_route or "")


def project_active_blob_to_legacy_session(
    session: dict[str, Any],
    blob: WorkflowStateBlob,
) -> dict[str, Any]:
    """One-way compatibility projection after activation — does not mutate store or pointer."""
    owner = str(blob.workflow_owner or "").strip()
    cleared = clear_incompatible_legacy_fields(session, owner)
    restore_workflow_blob_to_session(session, blob)
    projected = list(PROJECTED_LEGACY_KEYS.get(owner, ()))
    for k in projected:
        record_legacy_field_read(session, k, adapter="projection")
    return {"owner": owner, "projected_keys": projected, "cleared": cleared}


__all__ = [
    "PROJECTED_LEGACY_KEYS",
    "clear_incompatible_legacy_fields",
    "project_active_blob_to_legacy_session",
    "restore_workflow_blob_to_session",
]

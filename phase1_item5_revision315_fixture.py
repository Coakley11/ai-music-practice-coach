"""Authoritative Phase 1 Item 5 certification fixture @ revision 315 (Daniel acceptance profile)."""

from __future__ import annotations

import copy
from typing import Any

from creative_workspace_state_persistence import default_creative_workspace_state
from improvisation_missions import MISSION_EXAMPLE_KEY, MISSION_PRACTICE_LICK_KEY

AUTHORITATIVE_REVISION = 315

_MOTIF_NOTES = ["C4", "D4", "Eb4", "G4"]
_ARTIFACT_MOTIF_NOTES = ["C4", "D4", "Eb4", "G4"]


def creative_workspace_state_rev315() -> dict[str, Any]:
    cs = {
        "session_id": "item5-session-315",
        "tool_type": "song_based_improvisation",
        "entry_mode": "Song-Based Improvisation",
        "display_key": "Cm",
        "concert_key": "Cm",
        "instrument": "Piano",
        "updated_at": "2026-08-03T12:00:00+00:00",
        "signature": "item5rev315sig01",
        "sections": {"Melody A": ["Ab", "G7"]},
        "intelligence_tab": "Missions",
    }
    example = {
        "mission_title": "Traditional::Hevenu Shalom Aleichem",
        "variant": "normal",
        "display_key": "Cm",
        "key_center": "Cm",
        "motif": {"notes": copy.deepcopy(_ARTIFACT_MOTIF_NOTES), "rhythm": [1, 1, 1, 1]},
    }
    lick = {
        "mission_title": "Traditional::Hevenu Shalom Aleichem",
        "key_center": "Cm",
        "section_label": "Melody A",
        "chord": "Ab",
        "motif": {"notes": copy.deepcopy(_ARTIFACT_MOTIF_NOTES), "rhythm": [1, 1, 1, 1]},
    }
    return {
        **default_creative_workspace_state(),
        "improv_intelligence_tab": "Missions",
        "creative_improv_intelligence_tab": "Missions",
        "improv_entry_mode": "Song-Based Improvisation",
        "creative_lab_analysis_mode": "Improvisation Intelligence",
        "creative_lab_last_mode": "Improvisation Intelligence",
        "improv_mission_pick": "Traditional::Hevenu Shalom Aleichem",
        "improv_active_mission": "Traditional::Hevenu Shalom Aleichem",
        "improv_mission_progression": ["Ab", "G7"],
        "improv_ai_metric_ids": ["timing", "note_choice"],
        "analysis_criteria_locked": True,
        "ii_selected_section": "Melody A",
        "ii_selected_chord_index": 3,
        "ii_selected_chord": "Ab",
        "ii_selected_chord_label": "Melody A · Ab",
        "harmony_map_section": "Melody A",
        "harmony_map_chord": "G7",
        "creative_session": copy.deepcopy(cs),
        "improv_motif": {
            "notes": copy.deepcopy(_MOTIF_NOTES),
            "rhythm": [1, 1, 1, 1],
            "display": "notation",
        },
        MISSION_EXAMPLE_KEY: example,
        MISSION_PRACTICE_LICK_KEY: lick,
    }


def expected_globals_rev315() -> dict[str, str]:
    return {
        "display_key": "Cm",
        "instrument": "Piano",
        "level": "Beginner",
        "focus": "Left-Hand Patterns",
    }


def expected_studio_navigation_rev315() -> dict[str, str]:
    return {
        "studio_page": "backing",
        "backing_subview": "mission",
        "backing_context_source": "mission",
    }


def build_authoritative_music_payload(*, revision: int = AUTHORITATIVE_REVISION) -> dict[str, Any]:
    """Full disk/cloud envelope for Item 5 certification tests."""
    globals_ = expected_globals_rev315()
    nav = expected_studio_navigation_rev315()
    cws = creative_workspace_state_rev315()
    backing_context = {
        "source": "mission",
        "progression_label": "Melody A · Ab",
        "section": "Melody A",
        "progression": ["Ab"],
    }
    return {
        "core": {
            "pick_key": "Traditional::Hevenu Shalom Aleichem",
            "studio_page": nav["studio_page"],
            **globals_,
        },
        "active_song_state": {
            "pick_key": "Traditional::Hevenu Shalom Aleichem",
            "music_source": "catalog",
            **globals_,
            "last_write_reason": "cloud_restore",
        },
        "studio_nav_state": {
            "studio_page": nav["studio_page"],
            "page": nav["studio_page"],
            "last_write_reason": "cloud_restore",
        },
        "backing_track_state": {
            "backing_track_bpm": 88,
            "backing_groove_style": "swing",
            "backing_transport_status": "idle",
            "last_write_reason": "cloud_restore",
        },
        "practice_state": {
            "practice_minutes": 15,
            "last_write_reason": "cloud_restore",
        },
        "practice_workspace_state": {"updated_at": "2026-08-03T12:00:00+00:00"},
        "creative_workspace_state": copy.deepcopy(cws),
        "music_workspace_state": {
            "workspace_revision": revision,
            "studio_page": nav["studio_page"],
            "updated_at": "2026-08-03T12:00:00+00:00",
            "active_song": {
                "pick_key": "Traditional::Hevenu Shalom Aleichem",
                "source_type": "catalog",
                "music_source": "catalog",
            },
        },
        "session": {
            "backing_context": copy.deepcopy(backing_context),
            "studio_page": nav["studio_page"],
            **globals_,
        },
        "workspace_revision": revision,
    }


def expected_certification_fields() -> dict[str, Any]:
    """Canonical expected values for certification_passed checks."""
    cws = creative_workspace_state_rev315()
    cs = cws["creative_session"]
    return {
        "authoritative_revision": AUTHORITATIVE_REVISION,
        "globals": expected_globals_rev315(),
        "studio_navigation": expected_studio_navigation_rev315(),
        "item1": {
            "improv_intelligence_tab": cws["improv_intelligence_tab"],
            "improv_entry_mode": cws["improv_entry_mode"],
            "creative_lab_analysis_mode": cws["creative_lab_analysis_mode"],
        },
        "item2_target_tuple": {
            "ii_selected_section": cws["ii_selected_section"],
            "ii_selected_chord_index": cws["ii_selected_chord_index"],
            "ii_selected_chord": cws["ii_selected_chord"],
            "ii_selected_chord_label": cws["ii_selected_chord_label"],
            "improv_ai_metric_ids": cws["improv_ai_metric_ids"],
        },
        "item4_harmony_map": {
            "harmony_map_section": cws["harmony_map_section"],
            "harmony_map_chord": cws["harmony_map_chord"],
            "creative_session_tool": cs["tool_type"],
            "creative_session_display_key_snapshot": cs["display_key"],
        },
        "artifact_motif_notes": copy.deepcopy(_ARTIFACT_MOTIF_NOTES),
        "artifact_key_center": "Cm",
    }

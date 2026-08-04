"""Upload Analysis refresh: build payload → hydrate → route wins analysis."""

from __future__ import annotations

import copy
import unittest
from typing import Any
from unittest.mock import patch

from mission_pending_upload_analysis import PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY
from music_persistent_state import apply_music_disk_state, build_music_disk_state
from pending_upload_route_precedence import (
    apply_pending_upload_to_save_payload,
    pending_upload_should_restore_analysis_page,
    resolve_pending_upload_studio_page,
)
from studio_nav_state import resolve_studio_page_for_restore


def _prepared_env() -> dict[str, Any]:
    return {
        "take_id": "take-refresh-1",
        "handoff_revision": 3,
        "analysis_status": "prepared",
        "active_destination_page": "analysis",
        "navigation": {
            "studio_page": "analysis",
            "resume_upload_analysis": True,
            "route_lock": True,
            "destination_workflow": "pending_mission_upload_analysis",
        },
        "dry_audio": {
            "recording_id": "take-refresh-1",
            "fingerprint": "abc123",
            "storage_ref": "cloud://dry.wav",
        },
        "metrics": {"effective_metric_ids": ["chord_tone_targeting"]},
    }


class TestUploadAnalysisRefreshCycle(unittest.TestCase):
    def test_cloud_payload_carries_full_analysis_route(self) -> None:
        env = _prepared_env()
        session: dict[str, Any] = {
            "pending_upload_analysis_envelope": copy.deepcopy(env),
            "creative_workspace_state": {PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY: copy.deepcopy(env)},
            "_pending_upload_route_lock": True,
            "studio_page": "analysis",
        }
        st_like = type("St", (), {"session_state": session})()
        session["_music_build_save_reason"] = "mission_pending_upload_handoff"
        state = build_music_disk_state(st_like)
        state = apply_pending_upload_to_save_payload(session, state)
        mws = state.get("music_workspace_state") or {}
        self.assertEqual(mws.get("studio_page"), "analysis")
        route = mws.get("pending_upload_route") or {}
        self.assertTrue(route.get("route_lock"))
        self.assertEqual(route.get("destination_page"), "analysis")
        cws = state.get("creative_workspace_state") or {}
        self.assertEqual((cws.get(PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY) or {}).get("take_id"), "take-refresh-1")

    def test_refresh_hydrate_restores_analysis_page(self) -> None:
        env = _prepared_env()
        payload: dict[str, Any] = {
            "creative_workspace_state": {PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY: copy.deepcopy(env)},
            "music_workspace_state": {
                "studio_page": "creative",
                "pending_upload_route": {
                    "destination_page": "analysis",
                    "studio_page": "analysis",
                    "route_lock": True,
                    "resume_upload_analysis": True,
                },
            },
            "core": {"studio_page": "creative"},
            "session": {},
        }
        session: dict[str, Any] = {"studio_page": "practice"}
        with patch("music_persistent_state.apply_saved_music_context", return_value=False):
            apply_music_disk_state(
                type("St", (), {"session_state": session})(),
                payload,
                song_picker_catalog={},
                song_library={},
                authoritative_restore=True,
            )
        pending = resolve_pending_upload_studio_page(session, payload)
        self.assertEqual(pending, ("analysis", "pending_upload_analysis"))
        page, source = resolve_studio_page_for_restore(session, payload)
        self.assertEqual(page, "analysis")
        self.assertTrue(pending_upload_should_restore_analysis_page(session, payload))


if __name__ == "__main__":
    unittest.main()

"""Pending upload route lock release after successful startup apply."""

from __future__ import annotations

import copy
import unittest
from typing import Any

from mission_pending_upload_analysis import PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY
from pending_upload_route_precedence import (
    PENDING_UPLOAD_HYDRATED_TAKE_ID_KEY,
    PENDING_UPLOAD_ROUTE_APPLIED_TAKE_ID_KEY,
    PENDING_UPLOAD_ROUTE_LOCK_KEY,
    PENDING_UPLOAD_ROUTE_LOCK_RELEASED_RUN_KEY,
    apply_pending_upload_startup_page_if_needed,
    enforce_pending_upload_startup_route,
    finalize_pending_upload_session_route_lock,
)


def _env() -> dict[str, Any]:
    return {
        "take_id": "take-lock-1",
        "analysis_status": "prepared",
        "active_destination_page": "analysis",
        "navigation": {
            "studio_page": "analysis",
            "resume_upload_analysis": True,
            "route_lock": True,
        },
    }


class TestPendingUploadRouteLockLifecycle(unittest.TestCase):
    def test_finalize_releases_lock_when_hydrated_and_applied(self) -> None:
        env = _env()
        session: dict[str, Any] = {
            PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY: copy.deepcopy(env),
            "creative_workspace_state": {PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY: copy.deepcopy(env)},
            "studio_page": "analysis",
            PENDING_UPLOAD_ROUTE_LOCK_KEY: True,
            PENDING_UPLOAD_HYDRATED_TAKE_ID_KEY: "take-lock-1",
            PENDING_UPLOAD_ROUTE_APPLIED_TAKE_ID_KEY: "take-lock-1",
            "_script_run_seq": 12,
            "_suite_last_cloud_fetch_payload": {
                "creative_workspace_state": {PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY: copy.deepcopy(env)},
                "music_workspace_state": {
                    "pending_upload_route": {
                        "destination_page": "analysis",
                        "route_lock": True,
                        "resume_upload_analysis": True,
                    }
                },
            },
        }
        self.assertTrue(finalize_pending_upload_session_route_lock(session))
        self.assertNotIn(PENDING_UPLOAD_ROUTE_LOCK_KEY, session)
        self.assertEqual(session.get(PENDING_UPLOAD_ROUTE_LOCK_RELEASED_RUN_KEY), 12)

    def test_enforce_applies_once_and_releases_when_hydrated(self) -> None:
        env = _env()
        blob = {
            "creative_workspace_state": {PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY: copy.deepcopy(env)},
            "music_workspace_state": {
                "studio_page": "analysis",
                "pending_upload_route": {
                    "destination_page": "analysis",
                    "route_lock": True,
                    "resume_upload_analysis": True,
                },
            },
        }
        session: dict[str, Any] = {
            PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY: copy.deepcopy(env),
            "creative_workspace_state": {PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY: copy.deepcopy(env)},
            "studio_page": "practice",
            "_suite_last_cloud_fetch_payload": blob,
            PENDING_UPLOAD_HYDRATED_TAKE_ID_KEY: "take-lock-1",
            "_script_run_seq": 3,
        }
        apply_pending_upload_startup_page_if_needed(session)
        self.assertEqual(session.get("studio_page"), "analysis")
        self.assertEqual(session.get(PENDING_UPLOAD_ROUTE_APPLIED_TAKE_ID_KEY), "take-lock-1")
        enforce_pending_upload_startup_route(session, st=None)
        self.assertNotIn(PENDING_UPLOAD_ROUTE_LOCK_KEY, session)


if __name__ == "__main__":
    unittest.main()

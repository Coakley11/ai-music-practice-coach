"""Regression: Creative page_dispatch must not infinite-rerun on tab workflow sync."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from music_workflow_creative_nav import (
    CREATIVE_TAB_WORKFLOW_RERUN_FOR_SEQ_KEY,
    creative_tab_workflow_rerun_fingerprint,
    should_request_creative_tab_workflow_rerun,
    sync_workflow_for_creative_tab,
)
from music_workflow_pending_activation import (
    PENDING_WORKFLOW_ACTIVATION_KEY,
    queue_pending_workflow_activation,
)


class TestCreativePageDispatchWorkflowRerun(unittest.TestCase):
    def test_sync_skips_when_owner_already_active(self) -> None:
        session: dict[str, Any] = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "_pending_upload_route_lock": True,
        }

        class _Ptr:
            workflow_owner = "mission_jam"

        with patch("music_workflow_state_store.get_active_workflow_pointer", return_value=_Ptr()):
            status = sync_workflow_for_creative_tab(session, "Missions")
        self.assertEqual(status, "skipped")

    def test_sync_returns_already_queued_without_new_queue(self) -> None:
        session: dict[str, Any] = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Live Coach",
            "_streamlit_widgets_locked_this_run": True,
        }
        queue_pending_workflow_activation(
            session,
            target_owner="song_based_improvisation",
            activation_source="creative_tab_change",
            active_creative_view="Live Coach",
        )
        with patch("music_workflow_state_store.get_active_workflow_pointer", return_value=None):
            with patch(
                "music_workflow_pending_activation.request_or_activate_workflow",
            ) as req:
                status = sync_workflow_for_creative_tab(session, "Live Coach")
        self.assertEqual(status, "already_queued")
        req.assert_not_called()

    def test_rerun_once_per_pending_request_seq(self) -> None:
        session: dict[str, Any] = {"studio_page": "creative", "improv_intelligence_tab": "Missions"}
        session[PENDING_WORKFLOW_ACTIVATION_KEY] = {
            "target_owner": "mission_jam",
            "request_seq": 42,
            "active_creative_view": "Missions",
        }
        fp = creative_tab_workflow_rerun_fingerprint(session, "Missions")
        self.assertTrue(should_request_creative_tab_workflow_rerun(session, "Missions"))
        self.assertEqual(session.get(CREATIVE_TAB_WORKFLOW_RERUN_FOR_SEQ_KEY), 42)
        self.assertFalse(should_request_creative_tab_workflow_rerun(session, "Missions"))
        self.assertTrue(fp)

    def test_page_dispatch_reaches_completed_after_second_sync(self) -> None:
        from music_run_boundary import log_run_completed
        from music_run_lifecycle import begin_script_run_lifecycle, enter_run_phase, exit_run_phase

        session: dict[str, Any] = {
            "_script_run_seq": 2,
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "_pending_upload_route_lock": True,
        }
        begin_script_run_lifecycle(session, st=None)
        enter_run_phase(session, "page_dispatch")

        class _Ptr:
            workflow_owner = "mission_jam"

        with patch("music_workflow_state_store.get_active_workflow_pointer", return_value=_Ptr()):
            status = sync_workflow_for_creative_tab(session, "Missions")
        self.assertEqual(status, "skipped")

        exit_run_phase(session, "page_dispatch")
        log_run_completed(session)
        self.assertEqual((session.get("_music_run_lifecycle") or {}).get("status"), "RUN_COMPLETED")


if __name__ == "__main__":
    unittest.main()

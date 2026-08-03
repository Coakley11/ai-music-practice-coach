"""Item 5 session-start classification (read-only lifecycle markers)."""

from __future__ import annotations

import unittest
from typing import Any

from mission_backing_handoff_persistence import MISSION_BACKING_REFRESH_HYDRATION_TRACE_KEY
from phase1_item5_session_lifecycle import (
    ITEM5_LIFECYCLE_DIAG_KEY,
    classify_item5_session_start,
)
from phase1_item5_refresh_certification import collect_phase1_item5_refresh_certification


def _network_trace(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "_script_run_seq": 10,
        **{
            MISSION_BACKING_REFRESH_HYDRATION_TRACE_KEY: {
                "fetch_source": "network",
                "fetched_revision": 315,
                "startup_run_seq": 10,
                "steps": [{"function": "apply_music_disk_state:entry"}],
            }
        },
        "startup_revision_loaded": 315,
        "startup_revision_final": 315,
        "_suite_applied_workspace_revision": 315,
        "display_key": "Cm",
        "instrument": "Piano",
        "level": "Beginner",
        "focus": "Left-Hand Patterns",
        "studio_page": "creative",
        "_creative_tab_tool_diag": {"violations": []},
        "_creative_mission_config_diag": {"violations": []},
        "_creative_mission_artifact_diag": {"violations": []},
        "_creative_context_snapshot_diag": {"violations": []},
        "_creative_selector_hydration_complete": True,
    }
    base.update(extra)
    return base


def _lifecycle(
    *,
    prior_browser: bool,
    prior_streamlit: bool,
    created_stage: str | None = None,
) -> dict[str, Any]:
    return {
        "startup_run_seq": 1,
        "prior_browser_session_marker_present": prior_browser,
        "prior_streamlit_session_marker_present": prior_streamlit,
        "prior_suite_sid_in_url": False,
        "current_marker_created_stage": created_stage,
        "auth_restored_from_fresh_session": False,
        "current_run_network_hydration": None,
    }


class TestItem5SessionLifecycleClassification(unittest.TestCase):
    def test_a_hard_refresh_browser_marker_survives_new_streamlit_session(self) -> None:
        ss = _network_trace(
            **{
                ITEM5_LIFECYCLE_DIAG_KEY: _lifecycle(
                    prior_browser=True,
                    prior_streamlit=False,
                    created_stage=None,
                )
            }
        )
        out = classify_item5_session_start(ss, certification_network=True)
        self.assertEqual(out["session_start_kind"], "hard_refresh")
        self.assertEqual(out["classification_confidence"], "high")

    def test_b_cold_reboot_incognito_style_no_prior_browser_marker(self) -> None:
        ss = _network_trace(
            **{
                ITEM5_LIFECYCLE_DIAG_KEY: _lifecycle(
                    prior_browser=False,
                    prior_streamlit=False,
                    created_stage="observe_item5_session_lifecycle_start",
                )
            }
        )
        out = classify_item5_session_start(ss, certification_network=True)
        self.assertEqual(out["session_start_kind"], "cold_reboot")
        self.assertEqual(out["classification_confidence"], "high")
        diag = collect_phase1_item5_refresh_certification(ss)
        self.assertEqual(diag["session_start_kind"], "cold_reboot")
        self.assertTrue(diag["certification_passed"])

    def test_c_marker_created_this_run_must_not_classify_hard_refresh(self) -> None:
        ss = _network_trace(
            _suite_already_synced_before_restore=True,
            _music_workspace_blob_hydrated=True,
            **{
                ITEM5_LIFECYCLE_DIAG_KEY: _lifecycle(
                    prior_browser=False,
                    prior_streamlit=False,
                    created_stage="observe_item5_session_lifecycle_start",
                )
            },
        )
        out = classify_item5_session_start(ss, certification_network=True)
        self.assertEqual(out["session_start_kind"], "cold_reboot")
        self.assertNotEqual(out["session_start_kind"], "hard_refresh")

    def test_d_insufficient_evidence_unknown_certification_may_still_pass(self) -> None:
        ss = _network_trace(
            _music_last_cloud_fetch_source="session_cache",
        )
        out = classify_item5_session_start(ss, certification_network=True)
        self.assertEqual(out["session_start_kind"], "unknown")
        diag = collect_phase1_item5_refresh_certification(ss)
        self.assertEqual(diag["session_start_kind"], "unknown")
        self.assertTrue(diag["certification_passed"])

    def test_e_synced_before_restore_without_lifecycle_is_not_hard_refresh(self) -> None:
        ss = _network_trace(_suite_already_synced_before_restore=True)
        out = classify_item5_session_start(ss, certification_network=True)
        self.assertNotEqual(out["session_start_kind"], "hard_refresh")
        self.assertEqual(out["session_start_kind"], "unknown")


if __name__ == "__main__":
    unittest.main()

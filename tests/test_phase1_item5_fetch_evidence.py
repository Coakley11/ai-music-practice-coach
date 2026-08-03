"""Item 5 fetch-source precedence — authoritative hydration vs session cache."""

from __future__ import annotations

import unittest
from typing import Any

from mission_backing_handoff_persistence import MISSION_BACKING_REFRESH_HYDRATION_TRACE_KEY
from music_page_cloud_durability_trace import PAGE_CLOUD_DURABILITY_TRACE_KEY
from phase1_item5_fetch_evidence import resolve_item5_fetch_evidence
from phase1_item5_refresh_certification import collect_phase1_item5_refresh_certification
from phase1_item5_session_lifecycle import ITEM5_LIFECYCLE_DIAG_KEY


def _base_session(**extra: Any) -> dict[str, Any]:
    ss: dict[str, Any] = {
        "_script_run_seq": 10,
        "startup_revision_loaded": 315,
        "startup_revision_final": 315,
        "_suite_applied_workspace_revision": 315,
        "display_key": "Cm",
        "instrument": "Piano",
        "level": "Beginner",
        "focus": "Left-Hand Patterns",
        "studio_page": "creative",
        "harmony_map_section": "Melody A",
        "harmony_map_chord": "G7",
        "ii_selected_chord": "Ab",
        "improv_mission_example": {"key_center": "Cm", "motif": {"notes": ["C4"]}, "present": True},
        "improv_mission_practice_lick": {"key_center": "Cm", "motif": {"notes": ["C4"]}},
        "_creative_tab_tool_diag": {"violations": []},
        "_creative_mission_config_diag": {"violations": []},
        "_creative_mission_artifact_diag": {"violations": []},
        "_creative_context_snapshot_diag": {"violations": []},
        "_creative_selector_hydration_complete": True,
    }
    ss.update(extra)
    return ss


class TestItem5FetchEvidencePrecedence(unittest.TestCase):
    def test_a_network_hydrate_then_session_cache_lookup_still_network(self) -> None:
        ss = _base_session(
            **{
                MISSION_BACKING_REFRESH_HYDRATION_TRACE_KEY: {
                    "fetch_source": "network",
                    "fetched_revision": 315,
                    "startup_run_seq": 10,
                    "hydration_run_id": "live-hydrate-315",
                    "steps": [{"function": "apply_music_disk_state:entry"}],
                }
            },
            _music_last_cloud_fetch_source="session_cache",
            _suite_last_cloud_fetch_source="session_cache",
        )
        ev = resolve_item5_fetch_evidence(ss)
        self.assertEqual(ev["selected_certification_fetch_source"], "network")
        self.assertEqual(ev["initial_startup_fetch_source"], "network")
        self.assertEqual(ev["initial_startup_fetched_revision"], 315)
        self.assertIn("session_cache", str(ev["later_lookup_fetch_sources"]))
        diag = collect_phase1_item5_refresh_certification(ss)
        self.assertEqual(diag["certification_fetch_source"], "network")
        self.assertNotIn("fetch_source_not_network", diag["certification_failures"])
        self.assertTrue(diag["certification_passed"])

    def test_b_only_session_cache_fails(self) -> None:
        ss = _base_session(
            _music_last_cloud_fetch_source="session_cache",
        )
        ev = resolve_item5_fetch_evidence(ss)
        self.assertNotEqual(ev["selected_certification_fetch_source"], "network")
        diag = collect_phase1_item5_refresh_certification(ss)
        self.assertIn("fetch_source_not_network", diag["certification_failures"])
        self.assertFalse(diag["certification_passed"])

    def test_c_stale_prior_run_trace_ignored_with_current_cache(self) -> None:
        ss = _base_session(
            _script_run_seq=20,
            **{
                MISSION_BACKING_REFRESH_HYDRATION_TRACE_KEY: {
                    "fetch_source": "network",
                    "fetched_revision": 315,
                    "startup_run_seq": 5,
                    "steps": [{"function": "apply_music_disk_state:entry"}],
                }
            },
            _music_last_cloud_fetch_source="session_cache",
        )
        ev = resolve_item5_fetch_evidence(ss)
        self.assertNotEqual(ev["selected_certification_fetch_source"], "network")
        diag = collect_phase1_item5_refresh_certification(ss)
        self.assertFalse(diag["certification_passed"])

    def test_d_unknown_start_kind_still_passes_with_network_trace(self) -> None:
        ss = _base_session(
            **{
                MISSION_BACKING_REFRESH_HYDRATION_TRACE_KEY: {
                    "fetch_source": "network",
                    "fetched_revision": 315,
                    "steps": [{"function": "apply_music_disk_state:entry"}],
                }
            },
            _music_last_cloud_fetch_source="session_cache",
        )
        diag = collect_phase1_item5_refresh_certification(ss)
        self.assertTrue(diag["certification_passed"])
        self.assertEqual(diag["session_start_kind"], "unknown")

    def test_e_creative_studio_page_does_not_fail_certification(self) -> None:
        ss = _base_session(
            studio_page="creative",
            **{
                MISSION_BACKING_REFRESH_HYDRATION_TRACE_KEY: {
                    "fetch_source": "network",
                    "fetched_revision": 315,
                    "steps": [{"function": "apply_music_disk_state:entry", "page": "creative"}],
                }
            },
        )
        diag = collect_phase1_item5_refresh_certification(ss)
        self.assertEqual(diag["restored_studio_navigation"].get("studio_page"), "creative")
        self.assertTrue(diag["certification_passed"])

    def test_fresh_hydration_network_used_when_trace_missing(self) -> None:
        ss = _base_session(
            **{
                PAGE_CLOUD_DURABILITY_TRACE_KEY: {
                    "fresh_hydration": {
                        "fetch_source": "network",
                        "used_session_cache": False,
                        "revision": 315,
                    },
                }
            },
            _music_last_cloud_fetch_source="session_cache",
        )
        ev = resolve_item5_fetch_evidence(ss)
        self.assertEqual(ev["selected_certification_fetch_source"], "network")

    def test_hard_refresh_requires_lifecycle_browser_marker_not_hydration_flags(self) -> None:
        ss = _base_session(_suite_already_synced_before_restore=True)
        from phase1_item5_session_lifecycle import classify_item5_session_start

        self.assertEqual(
            classify_item5_session_start(ss, certification_network=True)["session_start_kind"],
            "unknown",
        )
        ss[ITEM5_LIFECYCLE_DIAG_KEY] = {
            "prior_browser_session_marker_present": True,
            "prior_streamlit_session_marker_present": False,
            "current_marker_created_stage": None,
        }
        self.assertEqual(
            classify_item5_session_start(ss, certification_network=True)["session_start_kind"],
            "hard_refresh",
        )


if __name__ == "__main__":
    unittest.main()

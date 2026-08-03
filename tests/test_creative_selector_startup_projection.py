"""Regression: Creative selector defaults must not dirty cloud on restore/autosave."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from creative_selector_hydration_trace import (
    CREATIVE_SELECTOR_HYDRATION_COMPLETE_KEY,
    mark_selector_hydration_complete,
)
from creative_tab_tool_persistence import (
    CREATIVE_SELECTOR_PERSISTENCE_REQUESTED_KEY,
    CREATIVE_TAB_HYDRATED_SNAPSHOT_KEY,
    CREATIVE_TAB_USER_EVENT_KEY,
    SAVE_REASON_TAB,
    VIOLATION_PASSIVE_STARTUP_WRITE,
    canonical_creative_selector_value,
    collect_creative_tab_tool_diagnostics,
    handle_user_creative_selector_change,
    note_passive_creative_tab_persist,
    project_startup_default_selector,
    should_gather_selector_from_session,
)
from creative_workspace_state_persistence import (
    CREATIVE_WORKSPACE_RESTORED_KEY,
    CREATIVE_WORKSPACE_STATE_KEY,
    apply_creative_workspace_to_session,
    default_creative_workspace_state,
    gather_creative_workspace_from_session,
    prepare_creative_workspace_for_render,
    sync_creative_workspace_state_before_persist,
)


def _cloud_cws(**selectors: str) -> dict:
    base = {**default_creative_workspace_state(), **selectors}
    return base


class TestCloudHydrateNoDefaultSave(unittest.TestCase):
    def test_autosave_does_not_overwrite_canonical_with_widget_defaults(self) -> None:
        ss: dict = {
            CREATIVE_SELECTOR_HYDRATION_COMPLETE_KEY: True,
            CREATIVE_WORKSPACE_STATE_KEY: _cloud_cws(
                improv_intelligence_tab="Missions",
                improv_entry_mode="Song-Based Improvisation",
                creative_lab_analysis_mode="Improvisation Intelligence",
            ),
            CREATIVE_TAB_HYDRATED_SNAPSHOT_KEY: {
                "improv_intelligence_tab": "Missions",
                "improv_entry_mode": "Song-Based Improvisation",
                "creative_lab_analysis_mode": "Improvisation Intelligence",
            },
            "improv_intelligence_tab": "Entry & Jam",
            "improv_entry_mode": "Song-Based Improvisation",
            "creative_lab_analysis_mode": "Deep Harmonic Analyzer",
        }
        self.assertFalse(
            should_gather_selector_from_session(ss, "improv_intelligence_tab", "Entry & Jam", persist_reason="autosave")
        )
        gathered = gather_creative_workspace_from_session(ss)
        self.assertEqual(gathered.get("improv_intelligence_tab"), "Missions")
        sync_creative_workspace_state_before_persist(ss, reason="autosave")
        note_passive_creative_tab_persist(ss, reason="autosave")
        codes = [v.get("code") for v in (ss.get("_creative_tab_tool_diag") or {}).get("violations") or []]
        self.assertNotIn(VIOLATION_PASSIVE_STARTUP_WRITE, codes)
        self.assertFalse(ss.get(CREATIVE_SELECTOR_PERSISTENCE_REQUESTED_KEY))

    def test_apply_projects_cloud_before_widget_defaults(self) -> None:
        ss: dict = {}
        apply_creative_workspace_to_session(
            ss,
            _cloud_cws(
                improv_intelligence_tab="Missions",
                improv_entry_mode="Song-Based Improvisation",
                creative_lab_analysis_mode="Improvisation Intelligence",
            ),
            source="cloud_restore",
        )
        self.assertEqual(ss.get("improv_intelligence_tab"), "Missions")
        self.assertTrue(ss.get(CREATIVE_SELECTOR_HYDRATION_COMPLETE_KEY))


class TestEmptyCloudLocalDefaults(unittest.TestCase):
    def test_local_defaults_without_canonical_autosave_promotion(self) -> None:
        ss: dict = {
            CREATIVE_SELECTOR_HYDRATION_COMPLETE_KEY: True,
            "_suite_last_cloud_fetch_payload": {"workspace_revision": 193},
            CREATIVE_WORKSPACE_STATE_KEY: default_creative_workspace_state(),
            CREATIVE_TAB_HYDRATED_SNAPSHOT_KEY: {
                "improv_intelligence_tab": "",
                "improv_entry_mode": "",
                "creative_lab_analysis_mode": "",
            },
        }
        mark_selector_hydration_complete(ss, source="cloud_restore")
        project_startup_default_selector(ss, "improv_intelligence_tab", "Entry & Jam")
        gathered = gather_creative_workspace_from_session(ss)
        self.assertNotEqual(gathered.get("improv_intelligence_tab"), "Entry & Jam")
        sync_creative_workspace_state_before_persist(ss, reason="autosave")
        self.assertFalse(ss.get(CREATIVE_SELECTOR_PERSISTENCE_REQUESTED_KEY))


class TestUserChangeStillSaves(unittest.TestCase):
    def test_user_tab_change_requests_persistence(self) -> None:
        ss: dict = {
            CREATIVE_SELECTOR_HYDRATION_COMPLETE_KEY: True,
            CREATIVE_WORKSPACE_STATE_KEY: _cloud_cws(improv_intelligence_tab="Entry & Jam"),
            "improv_intelligence_tab": "Missions",
            "_script_run_seq": 5,
        }
        with patch("creative_tab_tool_persistence.request_creative_selector_cloud_save", return_value=True) as save:
            handle_user_creative_selector_change(ss, "improv_intelligence_tab")
            save.assert_called_once()
        self.assertEqual(canonical_creative_selector_value(ss, "improv_intelligence_tab"), "Missions")


class TestRestoreRunDiagnostics(unittest.TestCase):
    def test_refresh_after_cloud_restore_no_startup_write_flag(self) -> None:
        ss: dict = {
            CREATIVE_SELECTOR_HYDRATION_COMPLETE_KEY: True,
            CREATIVE_WORKSPACE_STATE_KEY: _cloud_cws(
                improv_intelligence_tab="Missions",
                improv_entry_mode="Song-Based Improvisation",
                creative_lab_analysis_mode="Improvisation Intelligence",
            ),
            CREATIVE_TAB_HYDRATED_SNAPSHOT_KEY: {
                "improv_intelligence_tab": "Missions",
                "improv_entry_mode": "Song-Based Improvisation",
                "creative_lab_analysis_mode": "Improvisation Intelligence",
            },
            CREATIVE_WORKSPACE_RESTORED_KEY: True,
        }
        prepare_creative_workspace_for_render(ss)
        sync_creative_workspace_state_before_persist(ss, reason="autosave")
        diag = collect_creative_tab_tool_diagnostics(ss)
        self.assertFalse(diag.get("startup_write_attempted"))
        codes = [v.get("code") for v in (diag.get("violations") or [])]
        self.assertNotIn(VIOLATION_PASSIVE_STARTUP_WRITE, codes)


if __name__ == "__main__":
    unittest.main()

"""Regression: Creative selector fields survive cloud restore and unrelated saves."""

from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from creative_selector_hydration_trace import (
    CREATIVE_SELECTOR_HYDRATION_COMPLETE_KEY,
    VIOLATION_ALL_EMPTY_AFTER_RESTORE,
    extract_merged_creative_blob_from_payload,
)
from creative_workspace_state_persistence import (
    CREATIVE_WORKSPACE_STATE_KEY,
    apply_creative_workspace_from_payload,
    creative_workspace_for_envelope,
    default_creative_workspace_state,
    gather_creative_workspace_from_session,
    prepare_creative_workspace_for_render,
    sync_creative_workspace_state_before_persist,
)
from music_persistent_state import apply_music_disk_state, build_music_disk_state


class _FakeSt:
    def __init__(self, ss: dict):
        self.session_state = ss


class TestCreativeSelectorMergedExtraction(unittest.TestCase):
    def test_legacy_session_fills_empty_top_level_cws(self) -> None:
        payload = {
            "creative_workspace_state": {"schema_version": 1, "updated_at": "t"},
            "session": {
                "improv_intelligence_tab": "Missions",
                "improv_entry_mode": "Song-Based Improvisation",
                "creative_lab_analysis_mode": "Improvisation Intelligence",
            },
            "music_workspace_state": {
                "creative_workspace_state": {},
                "workspace_revision": 200,
            },
            "workspace_revision": 200,
        }
        blob = extract_merged_creative_blob_from_payload(payload)
        self.assertEqual(blob.get("improv_intelligence_tab"), "Missions")
        self.assertEqual(blob.get("improv_entry_mode"), "Song-Based Improvisation")
        self.assertEqual(blob.get("creative_lab_analysis_mode"), "Improvisation Intelligence")


class TestCreativeSelectorCloudRestorePath(unittest.TestCase):
    def _authoritative_payload(self) -> dict:
        return {
            "core": {"studio_page": "creative", "instrument": "Piano", "level": "Beginner", "focus": "Left-Hand Patterns"},
            "session": {
                "studio_page": "creative",
                "improv_intelligence_tab": "Missions",
                "creative_improv_intelligence_tab": "Missions",
                "improv_entry_mode": "Song-Based Improvisation",
                "creative_lab_analysis_mode": "Improvisation Intelligence",
                "creative_lab_last_mode": "Improvisation Intelligence",
            },
            "creative_workspace_state": {
                **default_creative_workspace_state(),
                "improv_intelligence_tab": "Missions",
                "improv_entry_mode": "Song-Based Improvisation",
                "creative_lab_analysis_mode": "Improvisation Intelligence",
            },
            "music_workspace_state": {
                "studio_page": "creative",
                "workspace_revision": 200,
                "creative_workspace_state": {
                    **default_creative_workspace_state(),
                    "improv_intelligence_tab": "Missions",
                },
            },
            "workspace_revision": 200,
            "studio_nav_state": {"studio_page": "creative", "page": "creative"},
        }

    def test_fresh_hydration_restore_render_keeps_selectors(self) -> None:
        payload = self._authoritative_payload()
        ss: dict = {"_script_run_seq": 1, "_cloud_workspace_restored_this_run": True}
        st = _FakeSt(ss)
        apply_music_disk_state(
            st,
            payload,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        prepare_creative_workspace_for_render(ss)
        self.assertEqual(ss.get("improv_intelligence_tab"), "Missions")
        self.assertEqual(ss.get("improv_entry_mode"), "Song-Based Improvisation")
        self.assertEqual(ss.get("creative_lab_analysis_mode"), "Improvisation Intelligence")
        canon = ss.get(CREATIVE_WORKSPACE_STATE_KEY)
        self.assertIsInstance(canon, dict)
        self.assertEqual(canon.get("improv_intelligence_tab"), "Missions")
        self.assertTrue(ss.get(CREATIVE_SELECTOR_HYDRATION_COMPLETE_KEY))

    def test_unrelated_rerun_does_not_clear_selectors(self) -> None:
        payload = self._authoritative_payload()
        ss: dict = {"_script_run_seq": 2, "_cloud_workspace_restored_this_run": True}
        st = _FakeSt(ss)
        apply_music_disk_state(
            st,
            payload,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        prepare_creative_workspace_for_render(ss)
        ss["_music_canonical_prepared_for_run"] = 1
        ss["_script_run_seq"] = 3
        from music_persistent_state import prepare_canonical_music_page_state

        prepare_canonical_music_page_state(ss)
        self.assertEqual(ss.get("improv_intelligence_tab"), "Missions")
        self.assertEqual(ss.get("studio_page"), "creative")

    def test_gather_preserves_selectors_when_session_widgets_missing(self) -> None:
        ss: dict = {
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_intelligence_tab": "Missions",
                "improv_entry_mode": "Song-Based Improvisation",
                "creative_lab_analysis_mode": "Improvisation Intelligence",
            },
            "studio_page": "creative",
        }
        gathered = gather_creative_workspace_from_session(ss)
        self.assertEqual(gathered.get("improv_intelligence_tab"), "Missions")
        st = _FakeSt(ss)
        sync_creative_workspace_state_before_persist(ss, reason="song_edit")
        disk = build_music_disk_state(st)
        cws = disk.get("creative_workspace_state") or {}
        self.assertEqual(cws.get("improv_intelligence_tab"), "Missions")
        self.assertEqual(cws.get("improv_entry_mode"), "Song-Based Improvisation")


class TestCreativeSelectorHydrationViolations(unittest.TestCase):
    def test_empty_after_restore_with_cloud_data_raises_violation(self) -> None:
        from creative_tab_tool_persistence import collect_creative_tab_tool_diagnostics

        ss: dict = {
            "_cloud_workspace_restored_this_run": True,
            CREATIVE_SELECTOR_HYDRATION_COMPLETE_KEY: True,
            "_suite_last_cloud_fetch_payload": {
                "session": {"improv_intelligence_tab": "Missions"},
            },
        }
        diag = collect_creative_tab_tool_diagnostics(ss)
        codes = [v.get("code") for v in (diag.get("violations") or [])]
        self.assertIn(VIOLATION_ALL_EMPTY_AFTER_RESTORE, codes)


if __name__ == "__main__":
    unittest.main()

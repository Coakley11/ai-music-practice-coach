"""Phase 1 item 1 — Creative tool/tab selector persistence."""

from __future__ import annotations

import copy
import unittest
from unittest.mock import MagicMock, patch

from creative_tab_tool_persistence import (
    CREATIVE_TAB_HYDRATED_SNAPSHOT_KEY,
    CREATIVE_TAB_MIGRATION_DONE_KEY,
    SAVE_REASON_TAB,
    VIOLATION_PASSIVE_STARTUP_WRITE,
    canonical_creative_selector_value,
    commit_creative_selector_to_canonical,
    handle_user_creative_selector_change,
    migrate_invalid_creative_selectors,
    note_passive_creative_tab_persist,
    record_creative_tab_violation,
    snapshot_hydrated_creative_selectors,
)
from creative_workspace_state_persistence import (
    CREATIVE_WORKSPACE_RESTORED_KEY,
    CREATIVE_WORKSPACE_STATE_KEY,
    apply_creative_workspace_from_payload,
    default_creative_workspace_state,
    prepare_creative_workspace_for_render,
    sync_creative_workspace_state_before_persist,
)
from music_persistent_state import apply_music_disk_state, build_music_disk_state
from studio_nav_state import STUDIO_NAV_STATE_KEY


class _FakeSt:
    def __init__(self, ss: dict):
        self.session_state = ss


class TestCreativeTabHydrationNoWrite(unittest.TestCase):
    def test_cloud_tab_a_restores_without_user_save(self) -> None:
        payload = {
            "core": {"studio_page": "creative"},
            "creative_workspace_state": {
                **default_creative_workspace_state(),
                "improv_intelligence_tab": "Missions",
            },
            "session": {},
        }
        ss: dict = {"studio_page": "creative"}
        self.assertTrue(apply_creative_workspace_from_payload(ss, payload, authoritative=True))
        prepare_creative_workspace_for_render(ss)
        self.assertEqual(ss.get("improv_intelligence_tab"), "Missions")
        self.assertTrue(ss.get("_creative_workspace_restored_applied"))
        self.assertNotIn("_improv_tab_user_touched", ss)


class TestCreativeTabUserChangeSave(unittest.TestCase):
    def test_user_tab_change_commits_canonical_and_requests_save(self) -> None:
        ss: dict = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Phrase / Motif",
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_intelligence_tab": "Entry & Jam",
            },
        }
        saves: list[str] = []

        def _fake_save(session: dict, *, save_reason: str) -> bool:
            saves.append(save_reason)
            session["_suite_persist_last_save_cloud"] = True
            session["_music_workspace_save_transaction"] = {
                "cloud_confirmed": True,
                "reserved_write_revision": 51,
                "cloud_readback_revision": 51,
            }
            return True

        with patch(
            "creative_tab_tool_persistence.request_creative_selector_cloud_save",
            side_effect=_fake_save,
        ):
            handle_user_creative_selector_change(ss, "improv_intelligence_tab")
        self.assertEqual(saves, [SAVE_REASON_TAB])
        canon = ss.get(CREATIVE_WORKSPACE_STATE_KEY)
        self.assertIsInstance(canon, dict)
        self.assertEqual(canon.get("improv_intelligence_tab"), "Phrase / Motif")
        self.assertEqual(ss.get("creative_improv_intelligence_tab"), "Phrase / Motif")

    def test_disk_round_trip_tab(self) -> None:
        ss: dict = {"studio_page": "creative", "improv_intelligence_tab": "Harmony Map"}
        sync_creative_workspace_state_before_persist(ss, reason="user_edit")
        st = _FakeSt(ss)
        disk = build_music_disk_state(st)
        fresh = _FakeSt({"studio_page": "creative"})
        apply_music_disk_state(
            fresh,
            disk,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        prepare_creative_workspace_for_render(fresh.session_state)
        self.assertEqual(fresh.session_state.get("improv_intelligence_tab"), "Harmony Map")


class TestCreativeTabIsolation(unittest.TestCase):
    def test_tab_change_does_not_alter_studio_page_or_globals(self) -> None:
        ss: dict = {
            "studio_page": "creative",
            STUDIO_NAV_STATE_KEY: {"studio_page": "creative", "page": "creative"},
            "instrument": "Piano",
            "level": "Beginner",
            "focus": "Left-Hand Patterns",
            "improv_intelligence_tab": "Metrics & AI",
        }
        with patch("creative_tab_tool_persistence.request_creative_selector_cloud_save", return_value=True):
            handle_user_creative_selector_change(ss, "improv_intelligence_tab")
        self.assertEqual(ss.get("studio_page"), "creative")
        self.assertEqual(ss.get("instrument"), "Piano")
        self.assertEqual(ss.get("level"), "Beginner")
        self.assertEqual(ss.get("focus"), "Left-Hand Patterns")


class TestCreativeTabMigration(unittest.TestCase):
    def test_invalid_legacy_tab_migrates_once_locally(self) -> None:
        ss: dict = {
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "creative_lab_analysis_mode": "deep",
            },
        }
        first = migrate_invalid_creative_selectors(ss, source="test")
        self.assertIn("creative_lab_analysis_mode", first)
        canon = ss[CREATIVE_WORKSPACE_STATE_KEY]
        self.assertEqual(canon.get("creative_lab_analysis_mode"), "Deep Harmonic Analyzer")
        second = migrate_invalid_creative_selectors(ss, source="test")
        self.assertEqual(second, [])
        self.assertTrue(ss.get(CREATIVE_TAB_MIGRATION_DONE_KEY))

    def test_passive_startup_write_violation(self) -> None:
        ss: dict = {
            CREATIVE_TAB_HYDRATED_SNAPSHOT_KEY: {"improv_intelligence_tab": "Missions"},
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_intelligence_tab": "Entry & Jam",
            },
        }
        note_passive_creative_tab_persist(ss, reason="autosave")
        diag = ss.get("_creative_tab_tool_diag") or {}
        codes = [v.get("code") for v in (diag.get("violations") or [])]
        self.assertIn(VIOLATION_PASSIVE_STARTUP_WRITE, codes)


class TestCreativeTabStaleRevision(unittest.TestCase):
    def test_commit_updates_canonical_not_stale_session_mirror(self) -> None:
        ss: dict = {
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_intelligence_tab": "Missions",
            },
            "improv_intelligence_tab": "Missions",
        }
        commit_creative_selector_to_canonical(
            ss,
            "improv_intelligence_tab",
            "Live Coach",
            reason=SAVE_REASON_TAB,
        )
        self.assertEqual(canonical_creative_selector_value(ss, "improv_intelligence_tab"), "Live Coach")
        stale = copy.deepcopy(ss)
        stale["improv_intelligence_tab"] = "Missions"
        stale[CREATIVE_WORKSPACE_STATE_KEY]["improv_intelligence_tab"] = "Missions"
        self.assertNotEqual(
            canonical_creative_selector_value(ss, "improv_intelligence_tab"),
            "Missions",
        )


class TestCreativeTabRestoreGate(unittest.TestCase):
    def test_prepare_sets_hydrated_snapshot(self) -> None:
        ss: dict = {
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_intelligence_tab": "Missions",
            },
            CREATIVE_WORKSPACE_RESTORED_KEY: True,
        }
        prepare_creative_workspace_for_render(ss)
        self.assertEqual(ss.get("improv_intelligence_tab"), "Missions")
        snap = ss.get(CREATIVE_TAB_HYDRATED_SNAPSHOT_KEY)
        self.assertIsInstance(snap, dict)
        self.assertEqual(snap.get("improv_intelligence_tab"), "Missions")


if __name__ == "__main__":
    unittest.main()

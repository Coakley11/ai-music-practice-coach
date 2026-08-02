"""Canonical creative_workspace_state save, apply, migration, and projection."""

from __future__ import annotations

import copy
import unittest

from creative_workspace_state_persistence import (
    CREATIVE_WORKSPACE_RESTORED_KEY,
    CREATIVE_WORKSPACE_STATE_KEY,
    apply_creative_workspace_from_payload,
    default_creative_workspace_state,
    prepare_creative_workspace_for_render,
    sync_creative_workspace_state_before_persist,
)
from music_persistent_state import apply_music_disk_state, build_music_disk_state


class _FakeSt:
    def __init__(self, ss: dict):
        self.session_state = ss


class TestCreativeWorkspaceStatePersistence(unittest.TestCase):
    def test_creative_tab_round_trip(self) -> None:
        ss: dict = {"studio_page": "creative", "improv_intelligence_tab": "Missions"}
        sync_creative_workspace_state_before_persist(ss)
        st = _FakeSt(ss)
        blob = build_music_disk_state(st)
        self.assertIn("creative_workspace_state", blob)
        self.assertEqual(blob["creative_workspace_state"]["improv_intelligence_tab"], "Missions")
        self.assertIn("creative_workspace_state", blob.get("music_workspace_state") or {})

        fresh = _FakeSt({"studio_page": "creative"})
        apply_music_disk_state(
            fresh,
            blob,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        prepare_creative_workspace_for_render(fresh.session_state)
        self.assertEqual(fresh.session_state.get("improv_intelligence_tab"), "Missions")
        self.assertTrue(fresh.session_state.get("_creative_workspace_restored_applied"))

    def test_legacy_session_keys_migrate_to_canonical(self) -> None:
        payload = {
            "core": {"studio_page": "creative"},
            "session": {
                "improv_intelligence_tab": "Entry & Jam",
                "creative_lab_analysis_mode": "deep",
            },
        }
        ss: dict = {"studio_page": "creative"}
        self.assertTrue(apply_creative_workspace_from_payload(ss, payload, authoritative=True))
        prepare_creative_workspace_for_render(ss)
        self.assertEqual(ss.get("improv_intelligence_tab"), "Entry & Jam")
        self.assertIsInstance(ss.get(CREATIVE_WORKSPACE_STATE_KEY), dict)

    def test_project_respects_restored_canonical(self) -> None:
        ss: dict = {
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "harmony_map_chord": "Dm7",
            },
            CREATIVE_WORKSPACE_RESTORED_KEY: True,
            "harmony_map_chord": "Cmaj7",
        }
        prepare_creative_workspace_for_render(ss)
        self.assertEqual(ss["harmony_map_chord"], "Dm7")


if __name__ == "__main__":
    unittest.main()

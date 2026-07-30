"""Cross-device CPL drift detection for workspace resync."""

from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace

from custom_progression_lab import CPL_ACTIVE_KEY, default_active_progression
from music_persistent_state import music_active_song_cloud_drift


class TestMusicCplCloudDrift(unittest.TestCase):
    def test_detects_cpl_chord_count_drift(self) -> None:
        active = default_active_progression()
        active["original_sections"] = {"Verse": [{"chord": "C", "bars": 1}]}
        st = SimpleNamespace(
            session_state={
                CPL_ACTIVE_KEY: default_active_progression(),
                "display_key": "C",
            }
        )
        cloud = {
            "core": {"display_key": "C"},
            "session": {
                CPL_ACTIVE_KEY: active,
            },
        }
        needed, detail = music_active_song_cloud_drift(st, cloud, "2026-01-01T00:00:00Z")
        self.assertTrue(needed)
        self.assertIn("cpl_chords", detail)

    def test_no_drift_when_matching(self) -> None:
        active = default_active_progression()
        active["original_sections"] = {"Verse": [{"chord": "C", "bars": 1}]}
        st = SimpleNamespace(
            session_state={
                CPL_ACTIVE_KEY: copy.deepcopy(active),
                "display_key": "C",
            }
        )
        cloud = {
            "core": {"display_key": "C"},
            "session": {CPL_ACTIVE_KEY: copy.deepcopy(active)},
        }
        needed, _ = music_active_song_cloud_drift(st, cloud, None)
        self.assertFalse(needed)


if __name__ == "__main__":
    unittest.main()

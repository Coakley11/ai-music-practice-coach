"""Phase 1 Item 4 — Creative context snapshot persistence."""

from __future__ import annotations

import copy
import os
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from creative_context_snapshot_persistence import (
    CREATIVE_CONTEXT_CANONICAL_KEYS,
    SAVE_REASON_CONTEXT_SECTION,
    VIOLATION_ENVELOPE_FIELD_DROPPED,
    VIOLATION_SNAPSHOT_MUTATED_GLOBAL_KEY,
    commit_context_snapshot_to_canonical,
    handle_user_harmony_map_context_change,
    should_gather_context_from_session,
    verify_full_creative_envelope_preserved,
)
from creative_workspace_state_persistence import CREATIVE_WORKSPACE_STATE_KEY
from music_egress_config import MUSIC_EGRESS_STRICT_KEY


class TestCreativeContextSnapshotPersistence(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop(MUSIC_EGRESS_STRICT_KEY, None)

    def test_passive_autosave_does_not_gather_harmony_map(self) -> None:
        ss: dict[str, Any] = {
            CREATIVE_WORKSPACE_STATE_KEY: {
                "harmony_map_section": "A",
                "harmony_map_chord": "Dm7",
            },
            "harmony_map_section": "B",
            "harmony_map_chord": "G7",
        }
        self.assertFalse(
            should_gather_context_from_session(
                ss,
                "harmony_map_chord",
                "G7",
                persist_reason="autosave",
            )
        )

    def test_envelope_guard_detects_dropped_mission_field(self) -> None:
        ss: dict[str, Any] = {}
        before = {
            "improv_mission_pick": "Hevenu",
            "harmony_map_chord": "C",
        }
        after = {"harmony_map_chord": "C"}
        dropped = verify_full_creative_envelope_preserved(ss, before, after)
        self.assertIn("improv_mission_pick", dropped)
        violations = ss.get("_creative_context_snapshot_diag", {}).get("violations") or []
        codes = [v.get("code") for v in violations if isinstance(v, dict)]
        self.assertIn(VIOLATION_ENVELOPE_FIELD_DROPPED, codes)

    def test_global_cm_not_mutated_by_context_save_handler(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        ss: dict[str, Any] = {
            "display_key": "Cm",
            "instrument": "Piano",
            "level": "Intermediate",
            "focus": "Melody",
            CREATIVE_WORKSPACE_STATE_KEY: {
                "improv_intelligence_tab": "Missions",
                "improv_mission_pick": "Traditional::Hevenu Shalom Aleichem",
            },
        }
        with patch(
            "creative_context_snapshot_persistence.force_save_music_state",
            create=True,
        ) as force_save:
            with patch(
                "music_persistent_state.force_save_music_state",
                return_value=True,
            ) as real_force:
                handle_user_harmony_map_context_change(ss, section="Chorus", chord="G7")
        self.assertEqual(ss.get("display_key"), "Cm")
        canon = ss.get(CREATIVE_WORKSPACE_STATE_KEY) or {}
        self.assertEqual(canon.get("harmony_map_section"), "Chorus")
        self.assertEqual(canon.get("harmony_map_chord"), "G7")
        self.assertEqual(canon.get("improv_mission_pick"), "Traditional::Hevenu Shalom Aleichem")

    def test_artifact_key_center_unchanged_when_current_context_changes(self) -> None:
        from improvisation_missions import MISSION_PRACTICE_LICK_KEY

        artifact = {
            "motif": {"notes": ["C"]},
            "key_center": "Dm",
            "section_label": "Verse",
        }
        ss: dict[str, Any] = {
            CREATIVE_WORKSPACE_STATE_KEY: {
                MISSION_PRACTICE_LICK_KEY: copy.deepcopy(artifact),
                "harmony_map_chord": "Dm7",
            },
            "harmony_map_chord": "Cmaj7",
        }
        commit_context_snapshot_to_canonical(
            ss,
            reason=SAVE_REASON_CONTEXT_SECTION,
            values={"harmony_map_chord": "Cmaj7", "harmony_map_section": "Chorus"},
        )
        stored = (ss.get(CREATIVE_WORKSPACE_STATE_KEY) or {}).get(MISSION_PRACTICE_LICK_KEY)
        self.assertIsInstance(stored, dict)
        self.assertEqual(stored.get("key_center"), "Dm")

    def test_context_keys_list_covers_harmony_and_session(self) -> None:
        self.assertIn("harmony_map_section", CREATIVE_CONTEXT_CANONICAL_KEYS)
        self.assertIn("creative_session", CREATIVE_CONTEXT_CANONICAL_KEYS)


if __name__ == "__main__":
    unittest.main()

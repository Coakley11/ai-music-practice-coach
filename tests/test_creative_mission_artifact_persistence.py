"""Phase 1 Item 3 — mission artifact persistence (motif, example, practice lick)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from creative_mission_artifact_persistence import (
    CREATIVE_MISSION_ARTIFACT_HYDRATED_SNAPSHOT_KEY,
    MISSION_EXAMPLE_KEY,
    SAVE_REASON_MISSION_EXAMPLE,
    SAVE_REASON_MOTIF,
    VIOLATION_PASSIVE_ARTIFACT_STARTUP_WRITE,
    canonical_mission_artifact_value,
    commit_mission_artifacts_to_canonical,
    handle_user_mission_example_artifact_saved,
    handle_user_motif_artifact_change,
    mission_artifact_configured_in_canonical,
    note_passive_mission_artifact_persist,
    project_mission_artifacts_from_canonical,
    should_gather_mission_artifact_from_session,
    snapshot_hydrated_mission_artifacts,
)
from creative_workspace_state_persistence import (
    CREATIVE_WORKSPACE_STATE_KEY,
    default_creative_workspace_state,
    gather_creative_workspace_from_session,
)
from improvisation_missions import MISSION_VARIANT_KEY, store_mission_example
from improvisation_missions import MissionExample


class TestMissionArtifactPersistence(unittest.TestCase):
    def test_motif_save_commits_to_canonical(self) -> None:
        motif = {"notes": ["C", "E", "G"], "rhythm": "q q q", "display": "C E G", "chord": "C"}
        ss: dict = {
            "_script_run_seq": 2,
            CREATIVE_WORKSPACE_STATE_KEY: default_creative_workspace_state(),
            "improv_motif": motif,
            "improv_motif_output_mode": "none",
        }
        with patch(
            "creative_mission_artifact_persistence.request_mission_artifact_cloud_save",
            return_value=True,
        ) as save:
            handle_user_motif_artifact_change(ss, interaction="test_motif")
            save.assert_called_once()
            self.assertEqual(save.call_args.kwargs.get("save_reason"), SAVE_REASON_MOTIF)
        self.assertEqual(canonical_mission_artifact_value(ss, "improv_motif"), motif)

    def test_gather_skips_stale_session_on_user_motif_save(self) -> None:
        ss: dict = {
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_motif": {"notes": ["C"], "display": "C"},
            },
            "improv_motif": {"notes": ["X"], "display": "X"},
        }
        self.assertFalse(
            should_gather_mission_artifact_from_session(
                ss, "improv_motif", ss["improv_motif"], persist_reason=SAVE_REASON_MOTIF
            )
        )
        ss["_music_build_save_reason"] = SAVE_REASON_MOTIF
        gathered = gather_creative_workspace_from_session(ss)
        self.assertEqual(gathered.get("improv_motif", {}).get("notes"), ["C"])

    def test_project_restores_motif_after_refresh(self) -> None:
        motif = {"notes": ["A", "C"], "rhythm": "q q", "display": "A C", "chord": "Am"}
        ss: dict = {
            CREATIVE_WORKSPACE_STATE_KEY: {**default_creative_workspace_state(), "improv_motif": motif},
            "improv_motif": {"notes": ["stale"]},
        }
        project_mission_artifacts_from_canonical(ss, overwrite=True)
        self.assertEqual(ss.get("improv_motif"), motif)

    def test_store_mission_example_persist_flag_triggers_save(self) -> None:
        example = MissionExample(
            mission="Test",
            variant="normal",
            chord="C",
            section="Verse",
            song_title="Song",
            display_key="C",
            instrument="Guitar",
            level="Intermediate",
            focus="Melody",
            motif={"notes": ["C"], "display": "C"},
            abc="",
            tab="",
            piano_html="",
            why="",
            practice_steps=[],
            insight=None,
            show_tab=False,
            show_piano=False,
        )
        ss: dict = {
            "_script_run_seq": 4,
            CREATIVE_WORKSPACE_STATE_KEY: default_creative_workspace_state(),
        }
        with patch(
            "creative_mission_artifact_persistence.handle_user_mission_example_artifact_saved",
        ) as persist:
            store_mission_example(ss, example, persist_artifact=False)
            persist.assert_not_called()
            store_mission_example(ss, example, persist_artifact=True, interaction="generate")
            persist.assert_called_once()

    def test_passive_violation_when_canonical_drift(self) -> None:
        ss: dict = {
            CREATIVE_MISSION_ARTIFACT_HYDRATED_SNAPSHOT_KEY: {
                "improv_motif": {"notes": ["C"], "display": "C"},
            },
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_motif": {"notes": ["D"], "display": "D"},
            },
        }
        note_passive_mission_artifact_persist(ss, reason="autosave")
        codes = [v.get("code") for v in (ss.get("_creative_mission_artifact_diag") or {}).get("violations") or []]
        self.assertIn(VIOLATION_PASSIVE_ARTIFACT_STARTUP_WRITE, codes)

    def test_explicit_empty_motif_list_in_canonical_is_configured(self) -> None:
        ss: dict = {
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                MISSION_EXAMPLE_KEY: {},
            },
        }
        self.assertTrue(mission_artifact_configured_in_canonical(ss, MISSION_EXAMPLE_KEY))


if __name__ == "__main__":
    unittest.main()

"""Upload Analysis metric inheritance from AI Metrics page."""

from __future__ import annotations

import unittest

from mission_upload_handoff import MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY, handoff_mission_take_to_upload_analysis
from mission_upload_metrics import (
    ANALYSIS_ADDITIONAL_TAKE_METRIC_IDS_KEY,
    ANALYSIS_INHERITED_AI_METRIC_IDS_KEY,
    active_improv_ai_metric_ids,
    apply_additional_take_metrics,
    compute_effective_upload_metric_ids,
    seed_upload_metrics_from_mission_handoff,
)


class TestMissionUploadMetrics(unittest.TestCase):
    def test_handoff_inherits_active_improv_metrics(self) -> None:
        session: dict = {
            "improv_ai_metric_ids": ["phrase_structure", "melodic_diversity_goal"],
            "improv_active_mission": "Develop one motif for the entire solo",
            "improv_mission_chord_options": ["Ab7"],
            "ii_selected_chord_index": 0,
            "ii_selected_chord": "Ab7",
        }
        audio = b"RIFF" + b"\x00" * 40 + b"data" + b"\x00" * 100
        handoff_mission_take_to_upload_analysis(
            session, audio_bytes=audio, filename="take.wav", source="upload"
        )
        self.assertTrue(session.get(MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY))
        self.assertEqual(
            session.get(ANALYSIS_INHERITED_AI_METRIC_IDS_KEY),
            ["phrase_structure", "melodic_diversity_goal"],
        )
        self.assertIn("phrase_structure", session.get("analysis_ai_metric_ids") or [])

    def test_additional_take_metrics_union_without_duplicates(self) -> None:
        session = {
            "analysis_inherited_ai_metric_ids": ["phrase_structure"],
            "analysis_additional_take_metric_ids": [],
            "analysis_sync_creative_mission": False,
        }
        apply_additional_take_metrics(
            session, ["phrase_structure", "motif_development", "space_silence"]
        )
        effective = compute_effective_upload_metric_ids(session)
        self.assertEqual(
            effective,
            ["phrase_structure", "motif_development", "space_silence"],
        )

    def test_take_only_additions_do_not_change_global_improv_metrics(self) -> None:
        session = {
            "improv_ai_metric_ids": ["phrase_structure"],
            "analysis_inherited_ai_metric_ids": ["phrase_structure"],
            "analysis_additional_take_metric_ids": [],
            "analysis_sync_creative_mission": False,
        }
        global_before = list(session["improv_ai_metric_ids"])
        apply_additional_take_metrics(session, ["motif_development"])
        self.assertEqual(session["improv_ai_metric_ids"], global_before)
        self.assertEqual(session[ANALYSIS_ADDITIONAL_TAKE_METRIC_IDS_KEY], ["motif_development"])

    def test_seed_from_handoff(self) -> None:
        session = {"improv_ai_metric_ids": ["rhythmic_diversity"]}
        seed_upload_metrics_from_mission_handoff(session)
        self.assertEqual(active_improv_ai_metric_ids(session), ["rhythmic_diversity"])
        self.assertEqual(session.get("analysis_ai_metric_ids"), ["rhythmic_diversity"])


if __name__ == "__main__":
    unittest.main()

"""Jam Generator live runtime trace (read-only diagnostics)."""

from __future__ import annotations

import unittest

from jam_generator_live_runtime_trace import (
    infer_first_divergence,
    record_jam_post_generate_trace,
    refresh_jam_generator_live_trace_table,
)
from music_workflow_activation import ActivateWorkflowRequest, activate_workflow
from music_workflow_generated_session import commit_jam_session_generation
from music_workflow_state_store import KeyAuthority, WorkflowStateBlob, save_workflow_blob


class JamGeneratorLiveRuntimeTraceTests(unittest.TestCase):
    def test_post_generate_records_eb_progression_with_c_labels(self) -> None:
        """Simulates live split: generate at Eb, UI labels forced to C."""
        bossa_eb = {
            "A": ["Fm7", "Bb7", "Ebmaj7", "Ebmaj7"],
            "B": ["Fm7", "Bb7", "Gm7", "C7"],
        }
        jam = {
            "id": "jam-trace-1",
            "key": "Eb",
            "style": "Bossa Nova",
            "ensemble": "Jazz trio",
            "prompt": "**Jazz trio** in **Eb** · Bossa Nova · ~110 BPM · daylight clarity.",
            "sections": bossa_eb,
        }
        session: dict = {
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_style": "Bossa Nova",
            "improv_jam_mood": "Bright",
            "improv_jam_key": "Eb",
            "improv_jam_session": jam,
            "display_key": "C",
            "concert_key": "C",
        }
        commit_jam_session_generation(
            session,
            jam,
            key_center="Eb",
            style="Bossa Nova",
            new_session=True,
        )
        # Simulate live split: blob/jam sealed at Eb, global practice labels still show C.
        session["display_key"] = "C"
        session["concert_key"] = "C"
        record_jam_post_generate_trace(session, key_c="Eb", owner="jam_session_generator", token="t1")
        table = refresh_jam_generator_live_trace_table(session)
        self.assertEqual(table["jam_workflow_blob"]["practice_tonic"], "Eb")
        self.assertEqual(table["ui_projections"]["display_key"], "C")
        div = table["first_divergence_hypothesis"]
        self.assertIn(
            div["first_fork_stage"],
            {"ui_projection_after_blob", "ui_projection_vs_jam_session", "none_detected_in_session"},
        )
        coh = table["coherence_resolver"]
        self.assertFalse(coh.get("untransposed_generated_artifact_fired"))

    def test_incoherent_blob_c_with_eb_progression_flags_untransposed(self) -> None:
        bossa_eb = {"A": ["Fm7", "Bb7", "Ebmaj7"]}
        blob = WorkflowStateBlob(
            workflow_owner="jam_session_generator",
            workflow_session_id="sid-c-eb",
            keys=KeyAuthority(
                practice_tonic="C",
                practice_mode="major",
                original_tonic="Eb",
                original_mode="major",
            ),
            style="Bossa Nova",
            mood="Bright",
            section_map=bossa_eb,
            source_type="generated",
        )
        session: dict = {
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_mood": "Bright",
            "improv_jam_style": "Bossa Nova",
            "display_key": "C",
            "concert_key": "C",
        }
        save_workflow_blob(session, blob, source="test")
        activate_workflow(
            session,
            ActivateWorkflowRequest(
                target_owner="jam_session_generator",
                target_session_id="sid-c-eb",
                activation_source="test",
                navigation_intent="creative_entry",
                incoming_blob=blob,
            ),
        )
        table = refresh_jam_generator_live_trace_table(session)
        self.assertTrue(table["coherence_resolver"]["untransposed_generated_artifact_fired"])


if __name__ == "__main__":
    unittest.main()

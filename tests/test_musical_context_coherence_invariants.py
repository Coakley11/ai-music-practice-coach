"""Invariant tests — one coherent musical context; no hybrid key/progression splits."""

from __future__ import annotations

import unittest

from backing_context import build_entry_jam_context
from improvisation_intelligence import generate_style_progression
from musical_context_coherence import (
    VIOLATION_UNTRANSPOSED_GENERATED_ARTIFACT,
    CoherentMusicalContext,
    infer_major_tonic_from_progression,
    resolve_coherent_musical_context,
    run_musical_context_coherence_checks,
    validate_coherent_musical_context,
    validate_untransposed_generated_artifact,
)
from music_workflow_pending_generated_progression import (
    consume_pending_generated_progression,
    queue_generated_progression_intent,
)
from music_workflow_state_store import KeyAuthority, WorkflowStateBlob, get_workflow_blob, save_workflow_blob, set_active_workflow_pointer, ActiveWorkflowPointer


def _session(**extra: object) -> dict:
    base: dict = {"_suite_active_workspace_id": "daniel"}
    base.update(extra)
    return base


class MusicalContextCoherenceInvariantTests(unittest.TestCase):
    def test_infer_major_tonic_from_ii_v_i(self) -> None:
        from music_theory import normalize_root, semitone_distance

        eb_center = infer_major_tonic_from_progression(["Fm7", "Bb7", "Ebmaj7"])
        self.assertEqual(semitone_distance(eb_center, "Eb"), 0)
        c_center = infer_major_tonic_from_progression(["Dm7", "G7", "Cmaj7"])
        self.assertEqual(normalize_root(c_center), "C")

    def test_untransposed_artifact_original_eb_practice_c(self) -> None:
        ctx = CoherentMusicalContext(
            owner="jam_session_generator",
            workflow_session_id="x",
            practice_tonic="C",
            practice_mode="major",
            key_token="C",
            original_tonic="Eb",
            original_mode="major",
            style_id="Jazz Swing",
            mood="Mellow",
            section_map={"Head": ["Fm7", "Bb7", "Ebmaj7", "Cm7"]},
            selected_section="",
            selected_chord="",
            progression_flat=("Fm7", "Bb7", "Ebmaj7", "Cm7"),
        )
        v = validate_untransposed_generated_artifact(ctx)
        self.assertTrue(any(VIOLATION_UNTRANSPOSED_GENERATED_ARTIFACT in x for x in v))

    def test_c_jazz_swing_with_secondary_dominant_not_flagged(self) -> None:
        sections = generate_style_progression(
            style="Jazz Swing", key_center="C", mood="Mellow", difficulty="Intermediate", seed=0
        )
        ctx = CoherentMusicalContext(
            owner="style_jam",
            workflow_session_id="s1",
            practice_tonic="C",
            practice_mode="major",
            key_token="C",
            original_tonic="C",
            original_mode="major",
            style_id="Jazz Swing",
            mood="Mellow",
            section_map=sections,
            selected_section="",
            selected_chord="",
            progression_flat=tuple(
                c for chs in sections.values() for c in chs
            ),
        )
        self.assertEqual(validate_coherent_musical_context(ctx), [])

    def test_coherent_blob_resolves_tonic_mode_together(self) -> None:
        session = _session()
        blob = WorkflowStateBlob(
            workflow_owner="jam_session_generator",
            workflow_session_id="jam-1",
            keys=KeyAuthority(
                practice_tonic="C",
                practice_mode="major",
                original_tonic="C",
                original_mode="major",
            ),
            section_map={"Head": ["Dm7", "G7", "Cmaj7", "A7"]},
            style="Jazz Swing",
            mood="Mellow",
        )
        save_workflow_blob(session, blob, source="test")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="jam_session_generator", workflow_session_id="jam-1"),
        )
        ctx = resolve_coherent_musical_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.key_token, "C")
        self.assertEqual(ctx.section_map["Head"][2], "Cmaj7")
        self.assertEqual(validate_coherent_musical_context(ctx), [])

    def test_build_entry_jam_uses_blob_not_hybrid_session_jam(self) -> None:
        session = _session(
            studio_page="backing",
            improv_entry_mode="Jam Session Generator",
            improv_jam_key="C",
            display_key="C",
            concert_key="C",
            improv_jam_session={
                "id": "stale",
                "key": "C",
                "sections": {"Head": ["Fm7", "Bb7", "Ebmaj7"]},
            },
        )
        blob = WorkflowStateBlob(
            workflow_owner="jam_session_generator",
            workflow_session_id="jam-1",
            keys=KeyAuthority(practice_tonic="C", practice_mode="major"),
            section_map={"Head": ["Dm7", "G7", "Cmaj7", "A7"]},
            style="Jazz Swing",
            mood="Mellow",
        )
        save_workflow_blob(session, blob, source="test")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="jam_session_generator", workflow_session_id="jam-1"),
        )
        ctx = build_entry_jam_context(session)
        self.assertEqual(str(ctx.concert_key or ""), "C")
        self.assertIn("Cmaj7", " ".join(ctx.progression or []))
        self.assertNotIn("Ebmaj7", " ".join(ctx.progression or []))

    def test_hybrid_legacy_path_transposes_to_declared_key(self) -> None:
        session = _session(
            studio_page="backing",
            improv_entry_mode="Jam Session Generator",
            improv_jam_key="C",
            display_key="C",
            concert_key="C",
            improv_jam_style="Jazz Swing",
            improv_jam_mood="Mellow",
            improv_jam_session={"sections": {"Head": ["Fm7", "Bb7", "Ebmaj7", "Cm7"]}},
        )
        ctx = build_entry_jam_context(session)
        self.assertEqual(str(ctx.concert_key or ""), "C")
        joined = " ".join(ctx.progression or [])
        self.assertIn("Cmaj7", joined)
        self.assertNotIn("Ebmaj7", joined)
        self.assertFalse(session.get("_musical_context_coherence_handoff_block"))

    def test_generate_then_coherence_clean(self) -> None:
        session = _session(
            studio_page="creative",
            improv_entry_mode="Jam Session Generator",
            improv_jam_key="C",
            improv_jam_style="Jazz Swing",
            improv_jam_mood="Mellow",
            improv_ensemble="Jazz trio",
        )
        queue_generated_progression_intent(session, owner="jam_session_generator")
        self.assertEqual(consume_pending_generated_progression(session), "done")
        diag = run_musical_context_coherence_checks(session)
        self.assertTrue(diag.get("consistent"))
        summary = diag.get("coherent_context_summary") or {}
        self.assertNotIn("section_map", summary)

    def test_bare_eb_token_is_major_not_minor(self) -> None:
        from music_theory import key_center_token, split_key_center

        tonic, mode = split_key_center("Eb")
        self.assertEqual(mode, "major")
        self.assertEqual(key_center_token(tonic, mode), "Eb")
        tonic_m, mode_m = split_key_center("Ebm")
        self.assertEqual(mode_m, "minor")


if __name__ == "__main__":
    unittest.main()

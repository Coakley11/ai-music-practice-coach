"""Tests for recording analysis-context snapshot + workflow-gated recording types."""

from __future__ import annotations

import unittest

from recording_analysis_context import (
    ANALYSIS_EVAL_INSTRUMENTS_KEY,
    ANALYSIS_SONG_SOURCE_NAME_KEY,
    ANALYSIS_SONG_SOURCE_TYPE_KEY,
    RECORDING_TYPE_BACKING,
    RECORDING_TYPE_MT_LAYER,
    RECORDING_TYPE_MT_MIX,
    RECORDING_TYPE_PRACTICE,
    RECORDING_TYPE_SOLO,
    SONG_SOURCE_CATALOG,
    WORKFLOW_MULTITRACK,
    WORKFLOW_SINGLE,
    apply_mission_recording_defaults,
    apply_snapshot_to_analysis_ctx,
    build_analysis_context_snapshot,
    coach_emphasis_notes,
    load_snapshot_from_result,
    normalize_recording_type_for_workflow,
    persist_snapshot_on_result,
    recording_types_for_workflow,
)
from recording_analysis import build_coach_summary, build_practice_plan, _apply_context_emphasis_to_categories
from upload_analysis_modes import MULTITRACK_RECORDING, SINGLE_RECORDING


class RecordingTypesByWorkflowTests(unittest.TestCase):
    def test_single_recording_types(self) -> None:
        types = recording_types_for_workflow(WORKFLOW_SINGLE)
        self.assertEqual(types, (RECORDING_TYPE_SOLO, RECORDING_TYPE_PRACTICE, RECORDING_TYPE_BACKING))
        self.assertNotIn(RECORDING_TYPE_MT_MIX, types)

    def test_multitrack_types(self) -> None:
        types = recording_types_for_workflow(WORKFLOW_MULTITRACK)
        self.assertEqual(types, (RECORDING_TYPE_MT_LAYER, RECORDING_TYPE_MT_MIX))
        self.assertNotIn(RECORDING_TYPE_SOLO, types)

    def test_normalize_swaps_invalid_type(self) -> None:
        session = {
            "analysis_mode": MULTITRACK_RECORDING,
            "analysis_recording_type": RECORDING_TYPE_SOLO,
        }
        out = normalize_recording_type_for_workflow(session)
        self.assertEqual(out, RECORDING_TYPE_MT_MIX)
        self.assertEqual(session["analysis_recording_type"], RECORDING_TYPE_MT_MIX)


class SnapshotBuildTests(unittest.TestCase):
    def test_build_snapshot_captures_core_fields(self) -> None:
        session = {
            "analysis_mode": SINGLE_RECORDING,
            "analysis_recording_type": RECORDING_TYPE_PRACTICE,
            "improv_ai_metric_ids": ["phrase_structure"],
            "analysis_effective_metric_ids": ["phrase_structure"],
            "focus": "Improvisation",
            "instrument": "Tenor Sax",
            "level": "Intermediate",
            ANALYSIS_EVAL_INSTRUMENTS_KEY: ["Tenor Sax"],
            ANALYSIS_SONG_SOURCE_TYPE_KEY: SONG_SOURCE_CATALOG,
            ANALYSIS_SONG_SOURCE_NAME_KEY: "Say",
            "analysis_song_source_id": "catalog:say",
            "song": "Say",
        }
        snap = build_analysis_context_snapshot(session, association="unit_test")
        self.assertEqual(snap["workflow"], WORKFLOW_SINGLE)
        self.assertEqual(snap["recording_type"], RECORDING_TYPE_PRACTICE)
        self.assertEqual(snap["practice_focus"], "Improvisation")
        self.assertEqual(snap["instruments"], ["Tenor Sax"])
        self.assertEqual(snap["level"], "Intermediate")
        self.assertEqual(snap["song_source_name"], "Say")
        self.assertEqual(snap["song_source_type"], SONG_SOURCE_CATALOG)
        self.assertIn("phrase_structure", snap["evaluating_criteria_ids"])

    def test_snapshot_owns_ctx_over_ambient_state(self) -> None:
        snap = {
            "recording_type": RECORDING_TYPE_BACKING,
            "instruments": ["Piano"],
            "level": "Advanced",
            "practice_focus": "Groove",
            "song_source_name": "Song A",
            "song_source_type": SONG_SOURCE_CATALOG,
            "evaluating_criteria_ids": ["tone"],
            "evaluating_criteria_labels": ["Tone"],
            "mission_type": "",
            "workflow": WORKFLOW_SINGLE,
        }
        ctx = {
            "song": "Song B",
            "instrument": "Guitar",
            "level": "Beginner",
            "focus": "Technique",
            "recording_type": "practice",
        }
        merged = apply_snapshot_to_analysis_ctx(ctx, snap)
        self.assertEqual(merged["song"], "Song A")
        self.assertEqual(merged["instrument"], "Piano")
        self.assertEqual(merged["level"], "Advanced")
        self.assertEqual(merged["focus"], "Groove")
        self.assertEqual(merged["recording_type"], RECORDING_TYPE_BACKING)

    def test_persist_and_reload_roundtrip(self) -> None:
        snap = build_analysis_context_snapshot(
            {
                "analysis_mode": SINGLE_RECORDING,
                "analysis_recording_type": RECORDING_TYPE_SOLO,
                "instrument": "Flute",
                "focus": "Tone",
                ANALYSIS_SONG_SOURCE_NAME_KEY: "Custom Piece",
            }
        )
        result = persist_snapshot_on_result({"ok": True, "scores": {"timing": 70}}, snap)
        loaded = load_snapshot_from_result(result)
        self.assertEqual(loaded["recording_type"], RECORDING_TYPE_SOLO)
        self.assertEqual(loaded["song_source_name"], "Custom Piece")
        self.assertEqual(result["analysis_context_snapshot"]["instruments"], ["Flute"])


class MissionDefaultsTests(unittest.TestCase):
    def test_mission_defaults_solo_single(self) -> None:
        session = {
            "instrument": "Guitar",
            "song": "Autumn Leaves",
            "level": "Intermediate",
            "focus": "Improvisation",
        }
        apply_mission_recording_defaults(session)
        self.assertEqual(session["analysis_mode"], SINGLE_RECORDING)
        self.assertEqual(session["analysis_recording_type"], RECORDING_TYPE_SOLO)
        self.assertEqual(session.get(ANALYSIS_EVAL_INSTRUMENTS_KEY), ["Guitar"])


class CoachEmphasisTests(unittest.TestCase):
    def test_practice_take_more_diagnostic_than_solo(self) -> None:
        practice_notes = coach_emphasis_notes({"recording_type": RECORDING_TYPE_PRACTICE})
        solo_notes = coach_emphasis_notes({"recording_type": RECORDING_TYPE_SOLO})
        self.assertTrue(any("Practice Take" in n or "diagnostic" in n.lower() for n in practice_notes))
        self.assertTrue(any("Solo Performance" in n for n in solo_notes))
        self.assertNotEqual(practice_notes[0], solo_notes[0])

    def test_criteria_changes_next_focus(self) -> None:
        scores = {"timing": 60, "pitch": 80, "technique": 70, "groove": 75, "musicality": 72, "confidence": 78, "tone": 74}
        categories = {
            "timing": {"findings": ["timing issue"], "tips": ["metronome"]},
            "pitch": {"findings": ["pitch ok"], "tips": ["drone"]},
            "technique": {"findings": ["tech"], "tips": ["slow"]},
            "groove": {"findings": ["groove"], "tips": ["pocket"]},
            "musicality": {"findings": ["mus"], "tips": ["shape"]},
            "confidence": {"findings": ["conf"], "tips": ["take2"]},
            "tone": {"findings": ["tone"], "tips": ["air"]},
        }
        _, _, _, focus_phrasing = build_coach_summary(
            scores,
            categories,
            {"evaluating_criteria_labels": ["Phrasing"], "focus": "Improvisation"},
        )
        _, _, _, focus_tone = build_coach_summary(
            scores,
            categories,
            {"evaluating_criteria_labels": ["Tone"], "focus": "Improvisation"},
        )
        self.assertIn("Phrasing", focus_phrasing)
        self.assertIn("Tone", focus_tone)
        self.assertNotEqual(focus_phrasing, focus_tone)

    def test_recording_type_changes_practice_plan(self) -> None:
        class _F:
            tempo = 90

        scores = {"timing": 55, "pitch": 70, "technique": 68, "groove": 60, "musicality": 65, "confidence": 70, "tone": 72}
        practice = build_practice_plan(scores, {"recording_type": RECORDING_TYPE_PRACTICE, "display_key": "C"}, _F())
        backing = build_practice_plan(scores, {"recording_type": RECORDING_TYPE_BACKING, "display_key": "C"}, _F())
        self.assertTrue(any("Diagnostic" in p or "weakest" in p.lower() for p in practice))
        self.assertTrue(any("backing" in p.lower() or "Lock" in p for p in backing))

    def test_criteria_augments_categories_without_changing_scores(self) -> None:
        categories = {
            "musicality": {
                "title": "Musicality",
                "findings": ["base"],
                "tips": ["base tip"],
                "score": 71,
            },
            "timing": {"title": "Timing", "findings": ["t"], "tips": ["tt"], "score": 60},
        }
        out = _apply_context_emphasis_to_categories(
            categories,
            {"evaluating_criteria_labels": ["Phrasing"], "recording_type": RECORDING_TYPE_SOLO},
        )
        self.assertEqual(out["musicality"]["score"], 71)
        self.assertTrue(any("Evaluating Criteria" in f for f in out["musicality"]["findings"]))


if __name__ == "__main__":
    unittest.main()

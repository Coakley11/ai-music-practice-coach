"""Phase 2B: Upload / AI Coach Practice Focus snapshot and evaluation."""

from __future__ import annotations

import copy
import unittest

from practice_focus_evaluation import (
    CAPABILITY_COACHING,
    CAPABILITY_DERIVED,
    CAPABILITY_MEASURED,
    analysis_focus_caption,
    analysis_focus_display_label,
    apply_focus_to_coach_outputs,
    attach_frozen_focus_to_context,
    capability_for_dimension,
    compact_analysis_focus_block,
    merge_metric_ids_with_focus,
    prepare_upload_analysis_context,
    severe_non_focus_scores,
    stamp_result_with_frozen_snapshot,
    supported_preferred_metric_ids,
    supported_score_keys,
)
from practice_setup_globals import set_active_focus
from recording_analysis_ui import render_analysis_dashboard
from upload_history import compact_analysis_for_history


def _session(instrument: str, focus: str) -> dict:
    return {"instrument": instrument, "focus": focus, "level": "Intermediate"}


def _scores(**overrides: int) -> dict[str, int]:
    base = {
        "timing": 72,
        "pitch": 70,
        "technique": 68,
        "groove": 71,
        "musicality": 66,
        "confidence": 64,
        "tone": 69,
    }
    base.update(overrides)
    return base


class TestPhase2BSnapshotImmutability(unittest.TestCase):
    def test_saved_strumming_result_does_not_follow_harmony(self) -> None:
        session = _session("Guitar", "Strumming")
        ctx = {"instrument": "Guitar", "focus": "Strumming", "mission_ids": []}
        prepare_upload_analysis_context(session, ctx)
        result = stamp_result_with_frozen_snapshot(
            {"ok": True, "coach_summary": "strum take", "scores": _scores()},
            ctx.get("practice_focus_snapshot"),
        )
        frozen = copy.deepcopy(result)
        set_active_focus(session, "Harmony", source="test")
        self.assertEqual(session["focus"], "Harmony")
        self.assertEqual(frozen["practice_focus_at_analysis"], "Strumming")
        self.assertEqual(
            frozen["practice_focus_snapshot"]["practice_focus"],
            "Strumming",
        )
        self.assertIn("Strumming", analysis_focus_caption(frozen))
        self.assertNotIn("Harmony", analysis_focus_caption(frozen))

    def test_same_rerun_uses_new_focus(self) -> None:
        session = _session("Guitar", "Strumming")
        set_active_focus(session, "Timing", source="test")
        ctx = {"instrument": "Guitar", "focus": "Strumming", "mission_ids": []}
        prepare_upload_analysis_context(session, ctx)
        self.assertEqual(ctx["practice_focus_snapshot"]["practice_focus"], "Timing")
        self.assertEqual(ctx["focus"], "Timing")

    def test_frozen_ctx_does_not_reread_live_focus(self) -> None:
        session = _session("Guitar", "Strumming")
        ctx = {"instrument": "Guitar", "focus": "Strumming"}
        prepare_upload_analysis_context(session, ctx)
        set_active_focus(session, "Harmony", source="test")
        attach_frozen_focus_to_context(ctx, session)
        self.assertEqual(ctx["practice_focus_snapshot"]["practice_focus"], "Strumming")


class TestPhase2BMetricPriority(unittest.TestCase):
    def test_guitar_strumming_prioritizes_supported_rhythm_metrics(self) -> None:
        ids = supported_preferred_metric_ids("Guitar", "Strumming")
        scores = supported_score_keys("Guitar", "Strumming")
        self.assertIn("timing_groove", ids)
        self.assertIn("timing", scores)
        self.assertIn("groove", scores)
        self.assertNotIn("resonance", ids)
        self.assertEqual(capability_for_dimension("timing"), CAPABILITY_MEASURED)
        self.assertEqual(capability_for_dimension("timing_groove"), CAPABILITY_DERIVED)

    def test_sax_tone_only_supportable_tone_evidence(self) -> None:
        ids = supported_preferred_metric_ids("Saxophone", "Tone")
        scores = supported_score_keys("Saxophone", "Tone")
        self.assertIn("instrument_tone", ids)
        self.assertIn("tone", scores)
        self.assertNotIn("resonance", ids)
        block = compact_analysis_focus_block("Saxophone", "Tone")
        self.assertIn("Tone", block)
        self.assertIn("Do not claim metrics", block)

    def test_timing_cross_instrument_shares_emphasis_not_copy(self) -> None:
        g_ids = supported_preferred_metric_ids("Guitar", "Timing")
        s_ids = supported_preferred_metric_ids("Saxophone", "Timing")
        self.assertEqual(g_ids, s_ids)
        self.assertIn("timing_groove", g_ids)
        g = apply_focus_to_coach_outputs(
            scores=_scores(),
            categories={},
            practice_plan=["generic scale"],
            instrument="Guitar",
            focus="Timing",
            baseline_summary="Baseline take.",
        )
        sax = apply_focus_to_coach_outputs(
            scores=_scores(),
            categories={},
            practice_plan=["generic scale"],
            instrument="Saxophone",
            focus="Timing",
            baseline_summary="Baseline take.",
        )
        self.assertIn("Timing", g["coach_summary"])
        self.assertIn("Timing", sax["coach_summary"])
        self.assertIn("Guitar", g["coach_summary"])
        self.assertIn("Saxophone", sax["coach_summary"])
        self.assertNotEqual(g["practice_plan"][0], "generic scale")

    def test_severe_non_focus_issue_still_surfaces(self) -> None:
        scores = _scores(timing=32, tone=78)
        severe = severe_non_focus_scores(scores, "Saxophone", "Tone")
        self.assertIn(("timing", 32), severe)
        out = apply_focus_to_coach_outputs(
            scores=scores,
            categories={
                "timing": {"findings": ["Onsets drift far from the beat."], "tips": []},
                "tone": {"findings": ["Centroid is stable."], "tips": ["Long tones."]},
            },
            practice_plan=[],
            instrument="Saxophone",
            focus="Tone",
            baseline_summary="Tone looked even.",
            biggest_issue="Centroid is stable.",
        )
        self.assertIn("timing", out["coach_summary"].lower())
        self.assertTrue(
            "32" in out["coach_summary"] or "outside this focus" in out["coach_summary"]
        )

    def test_user_metrics_are_not_removed(self) -> None:
        merged, added = merge_metric_ids_with_focus(
            ["motif_development"],
            "Guitar",
            "Strumming",
        )
        self.assertIn("motif_development", merged)
        self.assertIn("timing_groove", merged)
        self.assertIn("timing_groove", added)
        self.assertNotIn("motif_development", added)


class TestPhase2BHistoryAndUnknown(unittest.TestCase):
    def test_old_result_without_snapshot_does_not_inherit_current_focus(self) -> None:
        old = {"ok": True, "coach_summary": "legacy take", "scores": {"timing": 60}}
        self.assertEqual(analysis_focus_display_label(old), "")
        self.assertIn("Not recorded", analysis_focus_caption(old))
        html = render_analysis_dashboard(old)
        self.assertIn("Not recorded", html)
        self.assertNotIn("Harmony", html)

    def test_unknown_focus_preserves_exact_label(self) -> None:
        session = _session("Guitar", "Qwertyxyz Custom")
        ctx = {"instrument": "Guitar", "focus": "Qwertyxyz Custom", "mission_ids": []}
        prepare_upload_analysis_context(session, ctx)
        self.assertEqual(
            ctx["practice_focus_snapshot"]["practice_focus"],
            "Qwertyxyz Custom",
        )
        merged, _added = merge_metric_ids_with_focus([], "Guitar", "Qwertyxyz Custom")
        self.assertTrue(set(merged) <= {"timing_groove", "phrase_structure"})
        out = apply_focus_to_coach_outputs(
            scores=_scores(),
            categories={},
            practice_plan=[],
            instrument="Guitar",
            focus="Qwertyxyz Custom",
            baseline_summary="Useful baseline.",
        )
        self.assertIn("Qwertyxyz Custom", out["coach_summary"])
        self.assertNotIn("downstroke", out["coach_summary"].lower())

    def test_current_and_historical_can_coexist(self) -> None:
        session = _session("Guitar", "Strumming")
        ctx_a = {"instrument": "Guitar", "focus": "Strumming"}
        prepare_upload_analysis_context(session, ctx_a)
        a = stamp_result_with_frozen_snapshot(
            {"ok": True, "coach_summary": "A"},
            ctx_a.get("practice_focus_snapshot"),
        )
        set_active_focus(session, "Harmony", source="test")
        ctx_b = {"instrument": "Guitar", "focus": "Harmony"}
        prepare_upload_analysis_context(session, ctx_b)
        b = stamp_result_with_frozen_snapshot(
            {"ok": True, "coach_summary": "B"},
            ctx_b.get("practice_focus_snapshot"),
        )
        self.assertEqual(a["practice_focus_at_analysis"], "Strumming")
        self.assertEqual(b["practice_focus_at_analysis"], "Harmony")

    def test_compact_history_keeps_snapshot(self) -> None:
        session = _session("Guitar", "Strumming")
        ctx = {"instrument": "Guitar", "focus": "Strumming"}
        prepare_upload_analysis_context(session, ctx)
        result = stamp_result_with_frozen_snapshot(
            {
                "ok": True,
                "coach_summary": "Keep the groove hand moving.",
                "scores": _scores(),
                "practice_plan": ["Isolate the strumming pattern."],
            },
            ctx.get("practice_focus_snapshot"),
            evaluation_debug={"emphasized_score_keys": ["timing", "groove"]},
        )
        compact = compact_analysis_for_history(result)
        self.assertEqual(compact["practice_focus_at_analysis"], "Strumming")
        self.assertEqual(
            compact["practice_focus_snapshot"]["practice_focus"],
            "Strumming",
        )
        set_active_focus(session, "Harmony", source="test")
        self.assertEqual(compact["practice_focus_at_analysis"], "Strumming")


class TestPhase2BCoachingDifference(unittest.TestCase):
    def test_strumming_vs_timing_summary_and_plan_differ(self) -> None:
        scores = _scores(timing=60, groove=58, pitch=80)
        cats = {
            "timing": {"findings": ["Placement wobbles into changes."], "tips": ["Count the grid."]},
            "groove": {"findings": ["Attacks miss the pocket."], "tips": ["Mute and strum."]},
            "pitch": {"findings": ["Pitch is fine."], "tips": []},
        }
        strum = apply_focus_to_coach_outputs(
            scores=scores,
            categories=cats,
            practice_plan=["C major scale"],
            instrument="Guitar",
            focus="Strumming",
            baseline_summary="Baseline overlap.",
        )
        timing = apply_focus_to_coach_outputs(
            scores=scores,
            categories=cats,
            practice_plan=["C major scale"],
            instrument="Guitar",
            focus="Timing",
            baseline_summary="Baseline overlap.",
        )
        self.assertNotEqual(strum["coach_summary"], timing["coach_summary"])
        self.assertNotEqual(strum["practice_plan"], timing["practice_plan"])
        self.assertTrue(
            "strum" in " ".join(strum["practice_plan"]).lower()
            or "hand" in " ".join(strum["practice_plan"]).lower()
        )
        self.assertTrue(
            "metronome" in " ".join(timing["practice_plan"]).lower()
            or "subdivision" in " ".join(timing["practice_plan"]).lower()
        )
        html = render_analysis_dashboard(
            {
                "ok": True,
                "coach_summary": strum["coach_summary"],
                "practice_plan": strum["practice_plan"],
                "scores": scores,
                "practice_focus_at_analysis": "Strumming",
                "instrument": "Guitar",
            }
        )
        self.assertIn("Practice Focus at analysis: Strumming", html)
        self.assertNotIn("resonance score was", html.lower())

    def test_coaching_only_is_not_a_measured_metric(self) -> None:
        self.assertEqual(capability_for_dimension("long tones"), CAPABILITY_COACHING)
        sax = apply_focus_to_coach_outputs(
            scores=_scores(tone=74),
            categories={"tone": {"findings": ["Centroid 1800 Hz."], "tips": ["Keep color even."]}},
            practice_plan=[],
            instrument="Saxophone",
            focus="Tone",
            baseline_summary="Sustains were fairly even.",
        )
        blob = (sax["coach_summary"] + " " + " ".join(sax["practice_plan"])).lower()
        self.assertNotIn("resonance score was", blob)
        self.assertNotIn("82%", blob)
        self.assertTrue("long tone" in blob or "tone" in blob)


if __name__ == "__main__":
    unittest.main()

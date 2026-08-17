"""Phase 2D: Multitrack Practice Focus snapshot and coaching emphasis."""

from __future__ import annotations

import copy
import unittest

from practice_focus_evaluation import analysis_focus_caption
from practice_focus_multitrack import (
    MULTITRACK_CAPABILITY_MAP,
    apply_focus_to_multitrack_outputs,
    multitrack_capability_for,
    prepare_multitrack_analysis_context,
    stamp_multitrack_result_with_focus,
)
from practice_setup_globals import set_active_focus
from recording_analysis_ui import render_analysis_dashboard


def _baseline_findings(*, timing_severe: bool = True) -> list[str]:
    findings = []
    if timing_severe:
        findings.append("LayerB timing differs from LayerA (~120 ms average onset gap).")
    else:
        findings.append("LayerB and LayerA are rhythmically well locked.")
    findings.append("LayerB sits quietly in the mix — may sound buried.")
    return findings


def _scores() -> dict[str, int]:
    return {"ensemble": 62, "balance": 70, "sync": 68}


def _apply(focus: str, instrument: str = "Guitar", *, timing_severe: bool = True) -> dict:
    return apply_focus_to_multitrack_outputs(
        findings=_baseline_findings(timing_severe=timing_severe),
        tips=["Mix check: solo each layer, then A/B with drums or click."],
        coach_summary=(
            "Multitrack coach read: comparing onset alignment and level balance across layers."
        ),
        scores=_scores(),
        instrument=instrument,
        focus=focus,
    )


class TestPhase2DSnapshot(unittest.TestCase):
    def test_timing_snapshot_immutable_after_harmony(self) -> None:
        session = {"instrument": "Guitar", "focus": "Timing"}
        ctx = {"instrument": "Guitar", "focus": "Timing"}
        prepare_multitrack_analysis_context(session, ctx)
        result = stamp_multitrack_result_with_focus(
            {
                "ok": True,
                "multitrack": True,
                "coach_summary": "timing take",
                "scores": _scores(),
                "findings": _baseline_findings(),
            },
            ctx,
        )
        frozen = copy.deepcopy(result)
        set_active_focus(session, "Harmony", source="test")
        self.assertEqual(frozen["practice_focus_at_analysis"], "Timing")
        self.assertEqual(frozen["practice_focus_snapshot"]["practice_focus"], "Timing")
        self.assertIn("Timing", analysis_focus_caption(frozen))
        self.assertNotIn("Harmony", analysis_focus_caption(frozen))

    def test_same_rerun_uses_new_focus(self) -> None:
        session = {"instrument": "Guitar", "focus": "Timing"}
        set_active_focus(session, "Phrasing", source="test")
        ctx = {"instrument": "Guitar", "focus": "Timing"}
        prepare_multitrack_analysis_context(session, ctx)
        self.assertEqual(ctx["practice_focus_snapshot"]["practice_focus"], "Phrasing")
        self.assertEqual(ctx["focus"], "Phrasing")

    def test_freeze_once_ignores_later_live_focus(self) -> None:
        session = {"instrument": "Guitar", "focus": "Timing"}
        ctx = {"instrument": "Guitar", "focus": "Timing"}
        prepare_multitrack_analysis_context(session, ctx)
        set_active_focus(session, "Harmony", source="test")
        prepare_multitrack_analysis_context(session, ctx)
        self.assertEqual(ctx["practice_focus_snapshot"]["practice_focus"], "Timing")


class TestPhase2DEmphasis(unittest.TestCase):
    def test_raw_scores_invariant_across_focus(self) -> None:
        timing = _apply("Timing")
        tone = _apply("Tone", instrument="Saxophone")
        self.assertEqual(timing["scores"], tone["scores"])
        self.assertEqual(timing["scores"], _scores())

    def test_timing_vs_tone_coaching_differs(self) -> None:
        timing = _apply("Timing")
        tone = _apply("Tone", instrument="Saxophone")
        self.assertNotEqual(timing["coach_summary"], tone["coach_summary"])
        self.assertIn("Timing", timing["coach_summary"])
        self.assertIn("Tone", tone["coach_summary"])
        self.assertIn("onset_alignment", timing["emphasized_dimensions"])
        self.assertTrue(
            "alignment" in timing["coach_summary"].lower()
            or "onset" in timing["coach_summary"].lower()
        )
        self.assertNotIn("resonance score was", tone["coach_summary"].lower())
        self.assertNotIn("embouchure score was", tone["coach_summary"].lower())
        self.assertNotIn("82%", tone["coach_summary"])

    def test_severe_timing_under_tone_still_surfaces(self) -> None:
        tone = _apply("Tone", instrument="Saxophone", timing_severe=True)
        blob = tone["coach_summary"] + " " + " ".join(tone["findings"])
        self.assertTrue(
            "timing differs" in blob.lower() or "onset gap" in blob.lower()
        )
        self.assertTrue(tone["severe_non_focus_findings"])

    def test_guitar_strumming_no_stroke_invention(self) -> None:
        out = _apply("Strumming", instrument="Guitar")
        blob = (out["coach_summary"] + " " + " ".join(out["tips"])).lower()
        self.assertNotIn("upstroke", blob)
        self.assertNotIn("downstroke", blob)
        self.assertEqual(multitrack_capability_for("stroke_direction"), "unsupported")
        self.assertTrue(
            "strum" in blob or "hand" in blob or "onset" in blob or "rhythm" in blob
        )

    def test_sax_tone_no_resonance_invention(self) -> None:
        out = _apply("Tone", instrument="Saxophone")
        blob = (out["coach_summary"] + " " + " ".join(out["tips"])).lower()
        self.assertNotIn("resonance score was", blob)
        self.assertNotIn("82%", blob)
        self.assertEqual(multitrack_capability_for("resonance"), "unsupported")
        self.assertTrue("long tone" in blob or "tone" in blob)

    def test_harmony_no_fake_transcription(self) -> None:
        out = _apply("Harmony", instrument="Guitar")
        blob = (out["coach_summary"] + " " + " ".join(out["tips"])).lower()
        self.assertNotIn("wrong third", blob)
        self.assertNotIn("d7 chord", blob)
        self.assertEqual(multitrack_capability_for("chord_identity"), "unsupported")
        self.assertIn("does not transcribe", out["coach_summary"].lower())

    def test_finding_text_preserved(self) -> None:
        """Focus may reorder findings but must not rewrite measured sentences."""
        original = _baseline_findings()
        out = _apply("Timing")
        self.assertEqual(set(out["findings"]), set(original))


class TestPhase2DHistoryAndUnknown(unittest.TestCase):
    def test_old_result_without_focus(self) -> None:
        old = {
            "ok": True,
            "multitrack": True,
            "coach_summary": "legacy ensemble",
            "findings": ["LayerB and LayerA are rhythmically well locked."],
            "tips": [],
            "layers": ["A", "B"],
        }
        self.assertIn("Not recorded", analysis_focus_caption(old))
        html = render_analysis_dashboard(old)
        self.assertIn("Not recorded", html)
        self.assertNotIn("Harmony", html)

    def test_unknown_focus_safe(self) -> None:
        session = {"instrument": "Guitar", "focus": "Qwertyxyz Custom"}
        ctx = {"instrument": "Guitar", "focus": "Qwertyxyz Custom"}
        prepare_multitrack_analysis_context(session, ctx)
        self.assertEqual(
            ctx["practice_focus_snapshot"]["practice_focus"],
            "Qwertyxyz Custom",
        )
        out = _apply("Qwertyxyz Custom")
        self.assertIn("Qwertyxyz Custom", out["coach_summary"])
        stamped = stamp_multitrack_result_with_focus(
            {"ok": True, "multitrack": True, "coach_summary": out["coach_summary"]},
            ctx,
        )
        self.assertEqual(stamped["practice_focus_at_analysis"], "Qwertyxyz Custom")

    def test_explicit_findings_not_erased(self) -> None:
        """No Multitrack metric multiselect exists; Focus must not drop measured findings."""
        out = _apply("Tone", instrument="Saxophone")
        self.assertEqual(len(out["findings"]), len(_baseline_findings()))

    def test_capability_map_documented(self) -> None:
        self.assertEqual(MULTITRACK_CAPABILITY_MAP["onset_alignment"], "measured")
        self.assertEqual(MULTITRACK_CAPABILITY_MAP["rms_balance"], "measured")
        self.assertEqual(MULTITRACK_CAPABILITY_MAP["chord_identity"], "unsupported")

    def test_dashboard_shows_frozen_focus(self) -> None:
        session = {"instrument": "Guitar", "focus": "Timing"}
        ctx = {"instrument": "Guitar", "focus": "Timing"}
        prepare_multitrack_analysis_context(session, ctx)
        applied = _apply("Timing")
        result = stamp_multitrack_result_with_focus(
            {
                "ok": True,
                "multitrack": True,
                "coach_summary": applied["coach_summary"],
                "findings": applied["findings"],
                "tips": applied["tips"],
                "layers": ["A", "B"],
                "instrument": "Guitar",
                "scores": applied["scores"],
            },
            ctx,
        )
        html = render_analysis_dashboard(result)
        self.assertIn("Practice Focus at analysis: Timing", html)
        self.assertIn("onset", html.lower() or applied["coach_summary"].lower())


if __name__ == "__main__":
    unittest.main()

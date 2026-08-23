"""Live-report cleanup: Scale/mode contract, criteria dedupe, mixed-backing confidence."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from analysis_coach_quality import criteria_report_heading
from mission_analysis import (
    MISSION_BY_ID,
    analyze_improvisation_missions,
    score_missions,
)
from mission_analysis_ui import render_mission_analysis_html
from multitrack_upload_analysis import build_target_layer_focus_analysis
from recording_analysis import _is_mixed_backing_ctx, build_coach_summary
from recording_analysis_ui import render_analysis_dashboard


class ScaleModeEvidenceContractTests(unittest.TestCase):
    def test_weights_exclude_diversity_and_contour(self) -> None:
        goal = MISSION_BY_ID["scale_connection"]
        self.assertIn("scale_adherence", goal.weights)
        self.assertNotIn("melodic_diversity", goal.weights)
        self.assertNotIn("phrase_contour_variety", goal.weights)

    def test_low_diversity_does_not_drag_strong_scale_score(self) -> None:
        results = score_missions(
            ["scale_connection"],
            {
                "scale_adherence": 92.0,
                "chord_tone_accuracy": 90.0,
                "guide_tone_usage": 70.0,
                "melodic_diversity": 35.0,
                "phrase_contour_variety": 41.0,
            },
            {
                "song": "Perfect — Ed Sheeran",
                "display_key": "G major",
                "instrument": "Flute",
                "recording_type": "Over a Backing Track",
            },
        )
        self.assertEqual(len(results), 1)
        score = results[0]["score"]
        self.assertIsNotNone(score)
        self.assertGreaterEqual(int(score), 85)
        summary = (results[0].get("summary") or "").lower()
        self.assertTrue("strong" in summary or "solid" in summary)
        self.assertNotIn("several notes sat outside", summary)
        self.assertNotIn("melodic diversity", summary)
        self.assertNotIn("contour variety", summary)

    def test_scales_focus_and_criterion_directionally_consistent(self) -> None:
        metrics = {
            "scale_adherence": 92.0,
            "chord_tone_accuracy": 92.0,
            "guide_tone_usage": 70.0,
            "melodic_diversity": 35.0,
            "phrase_contour_variety": 41.0,
        }
        ctx = {
            "instruments": ["Flute"],
            "target_layer": "Flute",
            "practice_focuses": ["Scales"],
            "recording_type": "Over a Backing Track",
            "display_key": "G major",
            "song": "Perfect — Ed Sheeran",
            "selected_song_analysis_context": {
                "title": "Perfect",
                "artist": "Ed Sheeran",
                "key": "G major",
                "has_song_harmony": True,
                "chord_progression": ["G", "D/F#", "Em7", "D"],
            },
        }
        focus = build_target_layer_focus_analysis(
            features=SimpleNamespace(
                onset_strength_mean=1.0,
                onset_density=1.5,
                groove_tightness=0.5,
                spectral_centroid_mean=2000.0,
                dyn_flatness=0.4,
                dyn_range=0.05,
                pitch_cents_std=20.0,
                pitch_note="B3",
            ),
            scores={"technique": 70, "tone": 65, "pitch": 40},
            categories={},
            ctx=ctx,
            musical_metrics=metrics,
        )
        crit = score_missions(["scale_connection"], metrics, ctx)[0]
        focus_score = focus[0].get("score")
        self.assertIsNotNone(focus_score)
        self.assertIsNotNone(crit.get("score"))
        self.assertLessEqual(abs(int(focus_score) - int(crit["score"])), 12)

    def test_scale_criterion_drill_is_scale_owned_not_breath(self) -> None:
        results = score_missions(
            ["scale_connection"],
            {"scale_adherence": 60.0, "chord_tone_accuracy": 55.0},
            {
                "song": "Perfect — Ed Sheeran",
                "display_key": "G major",
                "instrument": "Flute",
                "recording_type": "Over a Backing Track",
            },
        )
        tips = " ".join(results[0].get("tips") or []).lower()
        drill = str(results[0].get("drill") or "").lower()
        joined = tips + " " + drill
        self.assertTrue("scale" in joined or "chord" in joined or "mode" in joined)
        self.assertNotIn("breath", joined)
        self.assertNotIn("supported air", joined)


class CriteriaWordingAndDedupeTests(unittest.TestCase):
    def test_ordinary_backing_has_no_improvisation_score_copy(self) -> None:
        y = np.zeros(2048, dtype=float)
        features = SimpleNamespace(
            duration=1.0,
            tempo=95,
            onset_times=np.array([0.1, 0.3, 0.5]),
            beat_times=np.array([0.0, 0.5, 1.0]),
            groove_tightness=0.5,
            beat_interval_cv=0.05,
            dyn_range=0.05,
        )
        with patch(
            "mission_analysis.extract_improv_metrics",
            return_value={
                "scale_adherence": 92.0,
                "chord_tone_accuracy": 90.0,
                "guide_tone_usage": 70.0,
                "melodic_diversity": 35.0,
                "phrase_contour_variety": 41.0,
                "articulation": 60.0,
                "groove_consistency": 60.0,
                "musical_expression": 55.0,
            },
        ):
            block = analyze_improvisation_missions(
                y,
                22050,
                features,
                {
                    "song": "Perfect — Ed Sheeran",
                    "display_key": "G major",
                    "instrument": "Flute",
                    "recording_type": "Over a Backing Track",
                    "mission_evaluation_active": False,
                },
                ["scale_connection"],
            )
        summary = str(block.get("mission_coach_summary") or "").lower()
        self.assertIn("selected-criteria assessment", summary)
        self.assertNotIn("improvisation score", summary)

    def test_mission_active_keeps_improvisation_score_wording(self) -> None:
        y = np.zeros(2048, dtype=float)
        features = SimpleNamespace(
            duration=1.0,
            tempo=95,
            onset_times=np.array([0.1, 0.3]),
            beat_times=np.array([0.0, 0.5]),
            groove_tightness=0.5,
            beat_interval_cv=0.05,
            dyn_range=0.05,
        )
        with patch(
            "mission_analysis.extract_improv_metrics",
            return_value={
                "scale_adherence": 80.0,
                "chord_tone_accuracy": 70.0,
                "guide_tone_usage": 60.0,
                "melodic_diversity": 50.0,
                "phrase_contour_variety": 50.0,
                "articulation": 60.0,
                "groove_consistency": 60.0,
                "musical_expression": 55.0,
            },
        ):
            block = analyze_improvisation_missions(
                y,
                22050,
                features,
                {
                    "song": "Perfect",
                    "display_key": "G major",
                    "instrument": "Flute",
                    "mission_evaluation_active": True,
                },
                ["scale_connection"],
            )
        self.assertIn(
            "improvisation score",
            str(block.get("mission_coach_summary") or "").lower(),
        )

    def test_selected_evaluating_criteria_renders_once_in_dashboard(self) -> None:
        result = {
            "ok": True,
            "coach_summary": "Solid take.",
            "biggest_issue": "timing",
            "next_focus": "Scales",
            "most_improved": "tone",
            "instrument": "Flute",
            "duration": 10.0,
            "scores": {
                "timing": 70,
                "pitch": 40,
                "technique": 65,
                "groove": 60,
                "musicality": 55,
                "confidence": 60,
                "tone": 70,
            },
            "categories": {},
            "practice_plan": ["Loop at 95 BPM."],
            "mission_evaluation_active": False,
            "overall_improv_score": 88,
            "mission_coach_summary": "Overall selected-criteria assessment: **88%**. **Scale/mode usage**: 88%.",
            "mission_strongest": "",
            "mission_weakest": "",
            "mission_next_recommendation": "Play the G major scale against Perfect's chords.",
            "mission_results": [
                {
                    "id": "scale_connection",
                    "label": "Scale/mode usage",
                    "score": 88,
                    "assessment": "88/100",
                    "summary": "Scale adherence was strong at about 92/100.",
                    "observed_evidence": ["scale adherence ≈ 92/100"],
                    "went_well": "Strong tonal fit.",
                    "improve_to": "Resolve a few outside tones.",
                    "drill": "Play the G major scale against Perfect's chords.",
                    "tips": ["Play the G major scale against Perfect's chords."],
                }
            ],
            "practice_focus_analysis": [
                {
                    "focus": "Scales",
                    "assessment": "92/100",
                    "findings": ["scale adherence ≈ 92%"],
                    "went_well": "Strong alignment.",
                    "improve_to": "Clean a few outliers.",
                    "drill": "Loop verse chords.",
                    "attribution_confidence": "Limited/moderate target attribution",
                }
            ],
            "recording_type": "Over a Backing Track",
        }
        html = render_analysis_dashboard(result)
        self.assertEqual(html.count("Selected Evaluating Criteria"), 1)
        self.assertNotIn("improvisation score", html.lower())
        # Criterion drill should appear once (card only) — not also in a footer recommendation.
        # Match without apostrophe so HTML escaping does not false-fail.
        self.assertEqual(html.lower().count("play the g major scale against perfect"), 1)


class MixedBackingConfidenceTests(unittest.TestCase):
    def test_focus_blocks_avoid_definitive_flute_only_claims(self) -> None:
        blocks = build_target_layer_focus_analysis(
            features=SimpleNamespace(
                onset_strength_mean=1.3,
                onset_density=2.0,
                groove_tightness=0.55,
                spectral_centroid_mean=2100.0,
                dyn_flatness=0.35,
                dyn_range=0.08,
                pitch_cents_std=18.0,
                pitch_note="B3",
            ),
            scores={"technique": 75, "tone": 70, "pitch": 40, "musicality": 60},
            categories={},
            ctx={
                "instruments": ["Flute"],
                "target_layer": "Flute",
                "practice_focuses": ["Articulation", "Tone", "Dynamics", "Scales"],
                "recording_type": "Over a Backing Track",
                "display_key": "G major",
                "selected_song_analysis_context": {
                    "title": "Perfect",
                    "key": "G major",
                    "has_song_harmony": True,
                    "chord_progression": ["G", "D/F#", "Em7", "D"],
                },
            },
            musical_metrics={"scale_adherence": 92.0, "chord_tone_accuracy": 90.0},
        )
        joined = " ".join(
            " ".join(
                [
                    str(b.get("went_well") or ""),
                    " ".join(str(x) for x in (b.get("findings") or [])),
                    str(b.get("attribution_confidence") or ""),
                ]
            )
            for b in blocks
        ).lower()
        self.assertIn("mixed", joined)
        self.assertTrue("limited" in joined or "moderate" in joined or "backing" in joined)
        self.assertNotIn("flute shows clear, intentional attacks", joined)

    def test_mixed_pitch_not_definitive_biggest_growth_edge(self) -> None:
        summary, *_rest = build_coach_summary(
            {
                "timing": 70,
                "pitch": 39,
                "technique": 65,
                "groove": 60,
                "musicality": 55,
                "confidence": 60,
                "tone": 70,
            },
            {
                "pitch": {"findings": ["Within-note drift."], "tips": ["Long tones."]},
                "musicality": {"findings": ["Flat dynamics."], "tips": ["Shape phrases."]},
            },
            {"recording_type": "Over a Backing Track", "instrument": "Flute"},
        )
        low = summary.lower()
        self.assertIn("backing", low)
        self.assertTrue(
            "limited" in low or "cautious" in low or "not a definitive" in low or "target-only" in low
        )
        self.assertFalse(
            low.startswith("your") and "biggest growth edge: pitch" in low
        )

    def test_score_and_confidence_remain_separate(self) -> None:
        self.assertTrue(_is_mixed_backing_ctx({"recording_type": "Over a Backing Track"}))
        blocks = build_target_layer_focus_analysis(
            features=SimpleNamespace(
                onset_strength_mean=1.0,
                onset_density=1.0,
                groove_tightness=0.5,
                spectral_centroid_mean=1800.0,
                dyn_flatness=0.4,
                dyn_range=0.05,
                pitch_cents_std=20.0,
                pitch_note="B3",
            ),
            scores={"tone": 80},
            categories={},
            ctx={
                "instruments": ["Flute"],
                "practice_focuses": ["Tone"],
                "recording_type": "Over a Backing Track",
            },
            musical_metrics={},
        )
        self.assertEqual(len(blocks), 1)
        self.assertTrue(blocks[0].get("attribution_confidence"))
        self.assertIn("attribution", blocks[0]["attribution_confidence"].lower())


class HeadingOwnershipTests(unittest.TestCase):
    def test_ordinary_heading_is_selected_evaluating_criteria(self) -> None:
        self.assertEqual(
            criteria_report_heading(mission_evaluation_active=False),
            "Selected Evaluating Criteria",
        )


if __name__ == "__main__":
    unittest.main()

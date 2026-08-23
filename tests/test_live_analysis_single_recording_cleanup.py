"""Single-recording live-report cleanup: Ear Training, Phrasing, meter, labels, criteria."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

import numpy as np

from analysis_coach_quality import (
    has_audio_form_timeline_alignment,
    has_chord_timeline_alignment,
    meter_aware_groove_click_tip,
    meter_aware_subdivision_drill,
)
from mission_analysis_ui import render_mission_analysis_html
from multitrack_upload_analysis import build_target_layer_focus_analysis
from recording_analysis import AudioFeatures, _musicality_analysis, build_practice_plan
from recording_analysis_ui import render_analysis_dashboard


def _focus_features(**overrides):
    base = dict(
        onset_strength_mean=1.1,
        onset_density=1.8,
        groove_tightness=0.48,
        spectral_centroid_mean=2100.0,
        dyn_flatness=0.35,
        dyn_range=0.08,
        pitch_cents_std=22.0,
        pitch_note="B3",
        energy_curve=[0.2, 0.25, 0.3, 0.35, 0.45, 0.5, 0.55, 0.6],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _audio_features(**overrides) -> AudioFeatures:
    vals = dict(
        duration=8.0,
        sr=22050,
        tempo=95.0,
        beat_times=np.linspace(0, 8, 16),
        beat_interval_cv=0.08,
        tempo_drift_pct=-8.0,
        onset_times=np.linspace(0, 8, 24),
        onset_strength_mean=1.0,
        onset_density=1.5,
        groove_tightness=0.25,
        pitch_median_hz=440.0,
        pitch_note="A4",
        pitch_cents_std=20.0,
        pitch_sharp_bias=0.0,
        voiced_ratio=0.8,
        rms=np.ones(20) * 0.1,
        dyn_range=0.05,
        dyn_flatness=0.4,
        spectral_centroid_mean=2000.0,
        zcr_mean=0.05,
        energy_curve=np.array([0.2, 0.25, 0.3, 0.35, 0.5, 0.55, 0.6, 0.65]),
        waveform_peaks=[0.1, 0.2],
        waveform_times=[0.0, 1.0],
    )
    vals.update(overrides)
    return AudioFeatures(**vals)


class EarTrainingEvidenceTests(unittest.TestCase):
    def test_ear_training_limited_evidence_not_selection_metadata(self) -> None:
        blocks = build_target_layer_focus_analysis(
            features=_focus_features(),
            scores={"technique": 70, "musicality": 60, "pitch": 55},
            categories={
                "technique": {
                    "tips": [
                        "Intermediate coaching: keep fundamentals solid while stretching one musical risk per take."
                    ]
                },
                "musicality": {"findings": []},
            },
            ctx={
                "instruments": ["Flute"],
                "target_layer": "Flute",
                "practice_focuses": ["Ear Training"],
                "recording_type": "Practice Take",
                "display_key": "G major",
                "level": "Intermediate",
                "selected_song_analysis_context": {
                    "title": "Perfect",
                    "artist": "Ed Sheeran",
                    "key": "G major",
                    "has_song_harmony": True,
                    "chord_progression": ["G", "D/F#", "Em7", "D"],
                },
            },
            musical_metrics={},
        )
        self.assertEqual(len(blocks), 1)
        ear = blocks[0]
        self.assertEqual(ear["focus"], "Ear Training")
        self.assertIsNone(ear.get("score"))
        assessment = str(ear.get("assessment") or "").lower()
        self.assertIn("limited", assessment)
        self.assertNotIn("/100", assessment)
        findings = " ".join(ear.get("findings") or []).lower()
        self.assertIn("limited direct", findings)
        self.assertNotIn("intermediate coaching", findings)
        self.assertNotIn("explicit coaching goal", findings)
        self.assertFalse(str(ear.get("went_well") or "").strip())
        drill = str(ear.get("drill") or "").lower()
        self.assertTrue(
            any(tok in drill for tok in ("sing", "hear", "match", "scale degree", "root")),
            drill,
        )
        self.assertNotIn("breath", drill)
        self.assertNotIn("embouchure", drill)


class PhrasingFormAlignmentTests(unittest.TestCase):
    def test_musicality_does_not_claim_after_the_intro(self) -> None:
        block = _musicality_analysis(
            _audio_features(energy_curve=np.array([0.1, 0.15, 0.2, 0.25, 0.5, 0.55, 0.6, 0.7]))
        )
        joined = " ".join(block.get("findings") or []).lower()
        self.assertNotIn("after the intro", joined)
        self.assertTrue(
            "opening portion" in joined or "later in the take" in joined or "builds" in joined,
            joined,
        )

    def test_no_form_alignment_without_timestamps(self) -> None:
        self.assertFalse(
            has_audio_form_timeline_alignment(
                {
                    "selected_song_analysis_context": {
                        "has_song_form": True,
                        "sections": {"Intro": ["G"], "Verse": ["G", "D"]},
                    }
                }
            )
        )

    def test_phrasing_sanitizes_intro_without_timeline_alignment(self) -> None:
        blocks = build_target_layer_focus_analysis(
            features=_focus_features(),
            scores={"musicality": 72},
            categories={
                "musicality": {
                    "findings": [
                        "Energy builds through the take — confidence grows after the intro."
                    ]
                }
            },
            ctx={
                "instruments": ["Flute"],
                "target_layer": "Flute",
                "practice_focuses": ["Phrasing"],
                "recording_type": "Practice Take",
                "selected_song_analysis_context": {
                    "title": "Perfect",
                    "sections": {"Intro": [], "Verse": [], "Chorus": []},
                    "has_song_form": True,
                },
            },
        )
        phr = blocks[0]
        findings = " ".join(phr.get("findings") or []).lower()
        self.assertNotIn("after the intro", findings)
        self.assertIn("opening portion", findings)


class MeterAwareGrooveTests(unittest.TestCase):
    def test_six_eight_avoids_two_and_four(self) -> None:
        tip = meter_aware_groove_click_tip("6/8").lower()
        self.assertNotIn("2 & 4", tip)
        self.assertNotIn("2 and 4", tip)
        self.assertTrue("1" in tip and "4" in tip)
        self.assertTrue("dotted" in tip or "two big" in tip or "two main" in tip)
        sub = meter_aware_subdivision_drill("6/8").lower()
        self.assertNotIn("2 & 4", sub)

    def test_four_four_may_use_two_and_four(self) -> None:
        tip = meter_aware_groove_click_tip("4/4").lower()
        self.assertIn("2 & 4", tip)

    def test_practice_plan_six_eight_avoids_two_and_four(self) -> None:
        plan = build_practice_plan(
            {
                "timing": 40,
                "pitch": 70,
                "technique": 70,
                "groove": 35,
                "musicality": 60,
                "confidence": 60,
                "tone": 65,
            },
            {
                "instrument": "Flute",
                "time_signature": "6/8",
                "display_key": "G major",
                "reference_bpm": 95,
                "song": "Perfect — Ed Sheeran",
                "target_chords": ["G", "D/F#", "Em7", "D"],
            },
            _audio_features(),
        )
        joined = " ".join(plan).lower()
        self.assertNotIn("2 & 4", joined)
        self.assertNotIn("mute on 2", joined)


class HarmonicOverlapLabelTests(unittest.TestCase):
    def test_no_chord_timeline_alignment_by_default(self) -> None:
        self.assertFalse(
            has_chord_timeline_alignment(
                {
                    "target_chords": ["G", "D/F#", "Em7", "D"],
                    "selected_song_analysis_context": {
                        "chord_progression": ["G", "D/F#", "Em7", "D"],
                        "has_song_harmony": True,
                    },
                }
            )
        )

    def test_scales_labels_describe_pool_overlap_not_hit_rate(self) -> None:
        blocks = build_target_layer_focus_analysis(
            features=_focus_features(),
            scores={"pitch": 80},
            categories={},
            ctx={
                "instruments": ["Flute"],
                "target_layer": "Flute",
                "practice_focuses": ["Scales"],
                "recording_type": "Practice Take",
                "display_key": "G major",
                "target_chords": ["G", "D/F#", "Em7", "D"],
                "selected_song_analysis_context": {
                    "title": "Perfect",
                    "key": "G major",
                    "chord_progression": ["G", "D/F#", "Em7", "D"],
                    "has_song_harmony": True,
                },
            },
            musical_metrics={
                "scale_adherence": 92.0,
                "chord_tone_accuracy": 92.0,
                "guide_tone_usage": 70.0,
            },
        )
        scales = blocks[0]
        findings = " ".join(scales.get("findings") or []).lower()
        self.assertIn("overlap", findings)
        self.assertTrue("union" in findings or "pooled" in findings)
        self.assertNotIn("chord-tone hit rate", findings)
        drill = str(scales.get("drill") or "")
        self.assertTrue("G" in drill or "→" in drill or "3rd" in drill.lower())


class EvaluatingCriteriaRenderTests(unittest.TestCase):
    def test_zero_criteria_no_section(self) -> None:
        html = render_mission_analysis_html({"mission_results": [], "ok": True})
        self.assertEqual(html.strip(), "")
        dash = render_analysis_dashboard(
            {
                "ok": True,
                "scores": {
                    "timing": 70,
                    "pitch": 70,
                    "technique": 70,
                    "groove": 70,
                    "musicality": 70,
                    "confidence": 70,
                    "tone": 70,
                },
                "categories": {},
                "coach_summary": "ok",
                "mission_results": [],
            }
        )
        self.assertNotIn("Selected Evaluating Criteria", dash)

    def test_one_criterion_renders_once(self) -> None:
        result = {
            "ok": True,
            "scores": {
                "timing": 70,
                "pitch": 70,
                "technique": 70,
                "groove": 70,
                "musicality": 70,
                "confidence": 70,
                "tone": 70,
            },
            "categories": {},
            "coach_summary": "ok",
            "practice_plan": [],
            "mission_evaluation_active": False,
            "mission_results": [
                {
                    "id": "scale_connection",
                    "label": "Scale/mode usage",
                    "score": 90,
                    "went_well": "Strong tonal fit.",
                    "improve_to": "Keep resolving.",
                    "tips": ["Loop G → D/F# → Em7 → D and land 3rds."],
                    "drill": "Loop G → D/F# → Em7 → D and land 3rds.",
                    "observed_evidence": ["scale adherence ≈ 92/100"],
                }
            ],
            "mission_coach_summary": "Overall selected-criteria assessment: **90%**.",
            "practice_focus_analysis": [],
        }
        html = render_analysis_dashboard(result)
        self.assertEqual(html.count("Selected Evaluating Criteria"), 1)
        self.assertIn("Scale/mode usage", html)

    def test_multiple_criteria_one_card_each(self) -> None:
        result = {
            "ok": True,
            "scores": {
                "timing": 70,
                "pitch": 70,
                "technique": 70,
                "groove": 70,
                "musicality": 70,
                "confidence": 70,
                "tone": 70,
            },
            "categories": {},
            "coach_summary": "ok",
            "mission_evaluation_active": False,
            "mission_results": [
                {
                    "id": "scale_connection",
                    "label": "Scale/mode usage",
                    "score": 88,
                    "tips": [],
                    "drill": "a",
                },
                {
                    "id": "articulation",
                    "label": "Articulation",
                    "score": 70,
                    "tips": [],
                    "drill": "b",
                },
            ],
            "practice_focus_analysis": [],
        }
        html = render_analysis_dashboard(result)
        self.assertEqual(html.count("Selected Evaluating Criteria"), 1)
        self.assertIn("Scale/mode usage", html)
        self.assertIn("Articulation", html)


class FocusEvidenceRuleTests(unittest.TestCase):
    def test_focus_blocks_use_real_or_limited_evidence(self) -> None:
        focuses = ["Articulation", "Scales", "Phrasing", "Ear Training"]
        blocks = build_target_layer_focus_analysis(
            features=_focus_features(),
            scores={"technique": 68, "pitch": 80, "musicality": 62},
            categories={
                "technique": {"findings": ["Clear tongued attacks"]},
                "musicality": {
                    "findings": [
                        "Energy builds through the take — confidence grows after the opening portion of the take."
                    ]
                },
            },
            ctx={
                "instruments": ["Flute"],
                "target_layer": "Flute",
                "practice_focuses": focuses,
                "recording_type": "Practice Take",
                "display_key": "G major",
                "target_chords": ["G", "D/F#", "Em7", "D"],
                "selected_song_analysis_context": {
                    "title": "Perfect",
                    "key": "G major",
                    "chord_progression": ["G", "D/F#", "Em7", "D"],
                    "has_song_harmony": True,
                    "sections": {"Intro": ["G"], "Verse": ["G", "D"]},
                    "has_song_form": True,
                },
            },
            musical_metrics={
                "scale_adherence": 92.0,
                "chord_tone_accuracy": 90.0,
                "guide_tone_usage": 70.0,
            },
        )
        by = {b["focus"]: b for b in blocks}
        self.assertEqual(set(by), set(focuses))
        art = " ".join(by["Articulation"].get("findings") or []).lower()
        self.assertTrue("attack" in art or "onset" in art)
        scales = " ".join(by["Scales"].get("findings") or []).lower()
        self.assertIn("overlap", scales)
        phr = " ".join(by["Phrasing"].get("findings") or []).lower()
        self.assertNotIn("after the intro", phr)
        ear = by["Ear Training"]
        self.assertIsNone(ear.get("score"))
        self.assertIn("limited", str(ear.get("assessment") or "").lower())
        self.assertNotIn("was analyzed with", str(ear.get("went_well") or "").lower())




class PhrasingFocusEvidenceContractTests(unittest.TestCase):
    """Phrasing Focus uses phrase metrics — never Musicality as a numeric proxy."""

    def _blocks(self, *, musicality: int = 94, metrics: dict | None = None):
        return build_target_layer_focus_analysis(
            features=_focus_features(),
            scores={"musicality": musicality, "technique": 70, "tone": 72},
            categories={
                "technique": {
                    "findings": [
                        "Flute attack profile reviewed from onset clarity and attack density."
                    ],
                    "tips": [
                        "Keep tonguing clean and consistent — not every note equally accented."
                    ],
                },
                "musicality": {
                    "findings": [
                        "Phrasing deep-dive: shape start/middle/end of each phrase; leave intentional space."
                    ],
                    "tips": [
                        "Shape start/middle/end of each phrase; leave intentional space."
                    ],
                },
            },
            ctx={
                "instruments": ["Flute"],
                "target_layer": "Flute",
                "practice_focuses": ["Phrasing", "Articulation"],
                "recording_type": "Practice Take",
                "display_key": "G major",
                "selected_song_analysis_context": {
                    "title": "Perfect",
                    "artist": "Ed Sheeran",
                    "key": "G major",
                    "has_song_harmony": True,
                },
            },
            musical_metrics=metrics
            or {
                "phrase_pacing": 87.0,
                "phrase_contour_variety": 41.0,
                "space_rests": 34.0,
            },
        )

    def test_phrasing_does_not_borrow_musicality_score(self) -> None:
        from multitrack_upload_analysis import _mapped_score_for_focus

        self.assertIsNone(
            _mapped_score_for_focus("Phrasing", {"musicality": 94, "tone": 70})
        )
        phr = next(b for b in self._blocks(musicality=94) if b["focus"] == "Phrasing")
        self.assertNotEqual(phr.get("score"), 94)
        self.assertIsNotNone(phr.get("score"))
        self.assertLess(int(phr["score"]), 75)

    def test_phrasing_uses_phrase_specific_evidence(self) -> None:
        phr = next(b for b in self._blocks() if b["focus"] == "Phrasing")
        findings = " ".join(phr.get("findings") or []).lower()
        self.assertIn("phrase pacing", findings)
        self.assertIn("87", findings)
        self.assertIn("contour", findings)
        self.assertIn("41", findings)
        self.assertIn("34", findings)
        self.assertIn("space", findings)

    def test_strong_pace_weak_contour_is_developing_not_excellent(self) -> None:
        phr = next(b for b in self._blocks() if b["focus"] == "Phrasing")
        assessment = str(phr.get("assessment") or "").lower()
        went = str(phr.get("went_well") or "").lower()
        improve = str(phr.get("improve_to") or "").lower()
        self.assertTrue(
            "developing" in assessment or "moderate" in assessment,
            assessment,
        )
        self.assertNotIn("excellent", assessment)
        self.assertIn("pacing", went)
        self.assertTrue("contour" in improve or "space" in improve, improve)

    def test_detected_evidence_excludes_coaching_commands(self) -> None:
        by = {b["focus"]: b for b in self._blocks()}
        phr_findings = " ".join(by["Phrasing"].get("findings") or []).lower()
        self.assertNotIn("shape start/middle/end", phr_findings)
        self.assertNotIn("leave intentional space", phr_findings)
        art_findings = " ".join(by["Articulation"].get("findings") or []).lower()
        self.assertNotIn("keep tonguing", art_findings)
        self.assertNotIn("not every note equally accented", art_findings)


class PhraseStructureCriterionConsistencyTests(unittest.TestCase):
    def test_went_well_uses_strong_pacing_evidence(self) -> None:
        from mission_analysis import score_missions

        rows = score_missions(
            ["phrase_structure"],
            {
                "phrase_pacing": 87.0,
                "phrase_contour_variety": 41.0,
                "space_rests": 34.0,
            },
            {
                "instrument": "Flute",
                "display_key": "G major",
                "song": "Perfect — Ed Sheeran",
            },
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertIsNotNone(row.get("score"))
        self.assertLess(int(row["score"]), 75)
        went = str(row.get("went_well") or "").lower()
        self.assertIn("pacing", went)
        self.assertIn("87", went)
        self.assertNotIn("clear starting point", went)
        improve = str(row.get("improve_to") or "").lower()
        self.assertTrue("contour" in improve or "space" in improve, improve)

    def test_directionally_consistent_with_phrasing_focus(self) -> None:
        from mission_analysis import score_missions
        from multitrack_upload_analysis import (
            _phrase_metric_bundle,
            _score_phrasing_from_metrics,
        )

        metrics = {
            "phrase_pacing": 87.0,
            "phrase_contour_variety": 41.0,
            "space_rests": 34.0,
        }
        focus_score = _score_phrasing_from_metrics(_phrase_metric_bundle(metrics))
        crit = score_missions(
            ["phrase_structure"],
            metrics,
            {"instrument": "Flute", "display_key": "G major", "song": "Perfect"},
        )[0]
        self.assertIsNotNone(focus_score)
        self.assertIsNotNone(crit.get("score"))
        self.assertLess(int(focus_score), 75)
        self.assertLess(int(crit["score"]), 75)
        self.assertGreater(int(focus_score), 40)
        self.assertGreater(int(crit["score"]), 40)


class SingleCriterionRankingTests(unittest.TestCase):
    def test_one_criterion_omits_strongest_weakest_in_html(self) -> None:
        result = {
            "ok": True,
            "overall_improv_score": 58,
            "mission_evaluation_active": False,
            "mission_results": [
                {
                    "id": "phrase_structure",
                    "label": "Phrase structure",
                    "score": 58,
                    "went_well": "Phrase pacing was strong at approximately 87/100.",
                    "improve_to": "More contour and space.",
                    "observed_evidence": [
                        "phrase pacing ≈ 87/100",
                        "phrase contour variety ≈ 41/100",
                        "space rests ≈ 34/100",
                    ],
                    "tips": [],
                    "drill": "2-bar question → rest → answer",
                }
            ],
            "mission_coach_summary": (
                "Evaluated 1 criterion against **Perfect**. "
                "Overall selected-criteria assessment: **58%**. **Phrase structure**: 58%."
            ),
            "mission_strongest": "Phrase structure — 58%",
            "mission_weakest": "Phrase structure — 58%",
            "musical_metrics": {
                "phrase_pacing": 87,
                "phrase_contour_variety": 41,
                "space_rests": 34,
            },
        }
        html = render_mission_analysis_html(result)
        self.assertIn("Phrase structure", html)
        self.assertNotIn("Strongest:", html)
        self.assertNotIn("Weakest:", html)

    def test_two_or_more_criteria_may_render_ranking(self) -> None:
        two = {
            "mission_results": [
                {"label": "Phrase structure", "score": 58, "tips": [], "drill": "a"},
                {"label": "Articulation", "score": 70, "tips": [], "drill": "b"},
            ],
            "mission_strongest": "Articulation — 70%",
            "mission_weakest": "Phrase structure — 58%",
            "overall_improv_score": 64,
            "mission_evaluation_active": False,
            "musical_metrics": {},
        }
        html = render_mission_analysis_html(two)
        self.assertIn("Strongest:", html)
        self.assertIn("Weakest:", html)

    def test_analyze_one_criterion_clears_ranking_fields(self) -> None:
        from unittest.mock import patch

        from mission_analysis import analyze_improvisation_missions

        fake_metrics = {
            "phrase_pacing": 87.0,
            "phrase_contour_variety": 41.0,
            "space_rests": 34.0,
            "timing_stability": 70.0,
            "groove_consistency": 70.0,
            "instrument_tone": 70.0,
            "articulation": 70.0,
        }
        with patch(
            "mission_analysis.extract_improv_metrics",
            return_value=dict(fake_metrics),
        ):
            out = analyze_improvisation_missions(
                np.zeros(1024),
                22050,
                _audio_features(),
                {
                    "instrument": "Flute",
                    "song": "Perfect — Ed Sheeran",
                    "display_key": "G major",
                    "mission_evaluation_active": False,
                },
                ["phrase_structure"],
            )
        self.assertEqual(out.get("mission_strongest"), "")
        self.assertEqual(out.get("mission_weakest"), "")
        summary = str(out.get("mission_coach_summary") or "").lower()
        self.assertNotIn("strongest:", summary)
        self.assertNotIn("grow next:", summary)
        self.assertIn("phrase structure", summary)

    def test_analyze_two_criteria_keeps_ranking(self) -> None:
        from unittest.mock import patch

        from mission_analysis import analyze_improvisation_missions

        fake_metrics = {
            "phrase_pacing": 87.0,
            "phrase_contour_variety": 41.0,
            "space_rests": 34.0,
            "articulation": 70.0,
            "timing_stability": 70.0,
            "groove_consistency": 70.0,
            "instrument_tone": 70.0,
        }
        with patch(
            "mission_analysis.extract_improv_metrics",
            return_value=dict(fake_metrics),
        ):
            out = analyze_improvisation_missions(
                np.zeros(1024),
                22050,
                _audio_features(),
                {
                    "instrument": "Flute",
                    "song": "Perfect",
                    "display_key": "G major",
                    "mission_evaluation_active": False,
                },
                ["phrase_structure", "articulation"],
            )
        self.assertTrue(str(out.get("mission_strongest") or "").strip())
        self.assertTrue(str(out.get("mission_weakest") or "").strip())
        summary = str(out.get("mission_coach_summary") or "").lower()
        self.assertIn("strongest:", summary)
        self.assertTrue("grow next:" in summary or "grow next" in summary)

if __name__ == "__main__":
    unittest.main()

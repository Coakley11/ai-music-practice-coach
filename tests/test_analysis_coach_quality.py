"""Regression tests for analysis status messages + coach quality fixes."""

from __future__ import annotations

import unittest

import numpy as np

from analysis_coach_quality import (
    build_analysis_status_message,
    dedupe_recommendations,
    has_song_form_context,
    instrument_family,
)
from mission_analysis import _coach_result_fields, score_missions
from recording_analysis import (
    AudioFeatures,
    _intonation_stats_from_f0,
    _pitch_analysis,
    _technique_analysis,
    build_practice_plan,
    compute_performance_scores,
)
from recording_analysis_context import (
    RECORDING_TYPE_PRACTICE,
    SONG_SOURCE_OTHER,
)


def _blank_features(**overrides) -> AudioFeatures:
    base = dict(
        duration=8.0,
        sr=22050,
        tempo=90.0,
        beat_times=np.linspace(0, 8, 16),
        beat_interval_cv=0.05,
        tempo_drift_pct=1.0,
        onset_times=np.linspace(0, 8, 24),
        onset_strength_mean=1.2,
        onset_density=1.5,
        groove_tightness=0.6,
        pitch_median_hz=440.0,
        pitch_note="A4",
        pitch_cents_std=18.0,
        pitch_sharp_bias=2.0,
        voiced_ratio=0.8,
        rms=np.ones(32) * 0.1,
        dyn_range=0.05,
        dyn_flatness=0.4,
        spectral_centroid_mean=1800.0,
        zcr_mean=0.03,
        energy_curve=np.linspace(0.08, 0.12, 16),
        waveform_peaks=[0.5] * 16,
        waveform_times=[i * 0.1 for i in range(16)],
        highlight_regions=[],
        raw={},
    )
    base.update(overrides)
    return AudioFeatures(**base)


class AnalysisStatusMessageTests(unittest.TestCase):
    def test_includes_criteria_focuses_baselines_and_missions(self) -> None:
        msg = build_analysis_status_message(
            {
                "evaluating_criteria_labels": [
                    "Phrase structure",
                    "Scale/mode usage",
                    "Timing/groove",
                    "Articulation",
                ],
                "practice_focuses": ["Articulation", "Dynamics", "Phrasing"],
            },
            mission_ids=["phrase_structure", "scale_connection"],
        )
        lower = msg.lower()
        self.assertTrue(msg.startswith("Analyzing "))
        self.assertIn("phrase structure", lower)
        self.assertTrue("phrasing" in lower or "dynamics" in lower)
        self.assertIn("improvisation missions", lower)
        # Avoid exact duplicate articulation token twice as bare repeats.
        self.assertEqual(lower.count("articulation"), 1)

    def test_dedupes_related_labels(self) -> None:
        msg = build_analysis_status_message(
            {
                "evaluating_criteria_labels": ["Timing/groove", "Articulation"],
                "practice_focuses": ["Articulation", "Timing"],
            },
            mission_ids=[],
        )
        lower = msg.lower()
        self.assertNotIn("articulation, articulation", lower)
        self.assertTrue(("timing" in lower) or ("groove" in lower))

    def test_multitrack_mentions_ensemble_concepts(self) -> None:
        msg = build_analysis_status_message(
            {
                "instrument_focuses": {
                    "Tenor Saxophone": ["Phrasing", "Improvisation"],
                    "Piano": ["Comping"],
                },
                "evaluating_criteria_labels": [],
            },
            multitrack=True,
        )
        lower = msg.lower()
        self.assertTrue("sax" in lower or "phrasing" in lower)
        self.assertTrue("balance" in lower or "ensemble" in lower)


class CoachSemanticsTests(unittest.TestCase):
    def test_mid_score_critique_not_in_went_well(self) -> None:
        summary = "Every note has the same attack — try softer starts and clearer accents on phrase peaks."
        why = "Shape the phrase: lighter on approach notes, clearer accents on destination notes."
        went, improve = _coach_result_fields(70, summary, why)
        self.assertNotIn("same attack", went.lower())
        self.assertIn("same attack", improve.lower())

    def test_high_score_praise_not_in_improve(self) -> None:
        summary = "Your time feels steady and grooves with the pulse."
        why = "Groove (76/100) and timing (82/100) are solid."
        went, improve = _coach_result_fields(78, summary, why)
        self.assertIn("steady", went.lower())
        self.assertNotIn("are solid", improve.lower())


class InstrumentCoachingLeakageTests(unittest.TestCase):
    def test_flute_pitch_and_technique_avoid_sax_guitar_wording(self) -> None:
        f = _blank_features(pitch_cents_std=60.0, pitch_sharp_bias=-15.0)
        pitch = _pitch_analysis(f, "Flute", {"display_key": "C", "song_source_type": SONG_SOURCE_OTHER})
        tech = _technique_analysis(f, "Flute")
        blob = " ".join(pitch["findings"] + pitch["tips"] + tech["findings"] + tech["tips"]).lower()
        self.assertIn("flute", blob)
        self.assertNotIn("mouthpiece", blob)
        self.assertNotIn("sax/voice", blob)
        self.assertNotIn("zero buzz", blob)
        self.assertNotIn("strum", blob)

    def test_flute_practice_plan_no_song_form_or_guitar_drills(self) -> None:
        f = _blank_features(pitch_cents_std=20.0)
        scores = compute_performance_scores(f, "Flute")
        # Force technique into weakest set
        scores["technique"] = 40
        scores["pitch"] = 42
        plan = build_practice_plan(
            scores,
            {
                "instrument": "Flute",
                "display_key": "C",
                "recording_type": RECORDING_TYPE_PRACTICE,
                "song_source_type": SONG_SOURCE_OTHER,
                "practice_focuses": ["Articulation", "Dynamics", "Phrasing"],
                "evaluating_criteria_labels": [
                    "Phrase structure",
                    "Scale/mode usage",
                    "Timing/groove",
                    "Articulation",
                ],
                "sections": {},
                "target_chords": [],
                "song": "Scale exercise",
            },
            f,
        )
        joined = " | ".join(plan).lower()
        self.assertNotIn("zero buzz", joined)
        self.assertNotIn("verse", joined)
        self.assertNotIn("chorus", joined)
        self.assertTrue("flute" in joined or "breath" in joined or "long-tone" in joined or "long tone" in joined)
        self.assertTrue(has_song_form_context({"song_source_type": SONG_SOURCE_OTHER}) is False)


class PitchIntonationArchitectureTests(unittest.TestCase):
    def test_stable_scale_not_penalized_like_drifting_sustain(self) -> None:
        # Stable ascending scale: each note flat within ~5 cents, large melodic range.
        notes_hz = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
        scale_frames: list[float] = []
        for hz in notes_hz:
            scale_frames.extend([hz] * 12)
            scale_frames.append(float("nan"))  # gap between notes
        scale_f0 = np.asarray(scale_frames, dtype=float)
        scale_stats = _intonation_stats_from_f0(scale_f0)

        # Single sustained note with strong within-note drift.
        drift = [440.0 * (2 ** (cents / 1200.0)) for cents in np.linspace(-40, 40, 96)]
        drift_f0 = np.asarray(drift, dtype=float)
        drift_stats = _intonation_stats_from_f0(drift_f0)

        self.assertIsNotNone(scale_stats["pitch_cents_std"])
        self.assertIsNotNone(drift_stats["pitch_cents_std"])
        # Melodic range of the scale is large, but local stability should stay modest.
        self.assertGreater(float(scale_stats["pitch_melody_range_cents"]), 200)
        self.assertLess(float(scale_stats["pitch_cents_std"]), 20)
        self.assertGreater(
            float(drift_stats["pitch_cents_std"]),
            float(scale_stats["pitch_cents_std"]) + 10,
        )

        scale_feat = _blank_features(
            pitch_cents_std=scale_stats["pitch_cents_std"],
            pitch_sharp_bias=scale_stats["pitch_sharp_bias"],
            voiced_ratio=0.85,
        )
        drift_feat = _blank_features(
            pitch_cents_std=drift_stats["pitch_cents_std"],
            pitch_sharp_bias=drift_stats["pitch_sharp_bias"],
            voiced_ratio=0.85,
        )
        scale_score = compute_performance_scores(scale_feat, "Flute")["pitch"]
        drift_score = compute_performance_scores(drift_feat, "Flute")["pitch"]
        self.assertGreater(scale_score, drift_score)
        self.assertGreaterEqual(scale_score, 55)


class RecommendationDedupeTests(unittest.TestCase):
    def test_near_duplicate_breath_and_backing_tips_collapsed(self) -> None:
        items = [
            "Record one pass focusing on breath — longer notes need supported air.",
            "Record one pass focusing on breath — longer notes need supported air.",
            "Slow the backing track 10–15 BPM and record two takes back-to-back.",
            "Slow the backing track 10–15 BPM and record two takes back-to-back.",
            "Criteria drill (Articulation): one 8-bar loop focusing only on that emphasis @ 70 BPM.",
        ]
        out = dedupe_recommendations(items, limit=8)
        self.assertEqual(len(out), 3)

    def test_score_missions_attaches_shared_tip_once(self) -> None:
        metrics = {
            "phrase_pacing": 40,
            "phrase_contour_variety": 40,
            "space_rests": 40,
            "scale_adherence": 40,
            "melodic_diversity": 40,
            "timing_stability": 40,
            "groove_consistency": 40,
            "articulation": 40,
            "instrument_tone": 50,
            "musical_expression": 50,
            "rhythmic_diversity": 50,
            "rhythmic_syncopation": 50,
            "motif_consistency": 50,
            "motif_transformation": 50,
            "repetition_variation": 50,
            "chord_tone_accuracy": 50,
            "guide_tone_usage": 50,
            "landing_note_quality": 50,
            "tension_release_balance": 50,
            "resolution_strength": 50,
            "voice_leading_smoothness": 50,
            "pentatonic_adherence": 50,
            "dynamic_contrast": 50,
        }
        results = score_missions(
            ["phrase_structure", "scale_connection", "timing_groove", "articulation"],
            metrics,
            {
                "instrument": "Flute",
                "song_source_type": SONG_SOURCE_OTHER,
                "song": "Scale exercise",
                "sections": {},
                "target_chords": [],
                "display_key": "C",
            },
        )
        breath_hits = 0
        backing_hits = 0
        for row in results:
            tips = " ".join(row.get("tips") or []).lower()
            if "supported air" in tips:
                breath_hits += 1
            if "backing track" in tips:
                backing_hits += 1
            self.assertNotIn("mouthpiece", tips)
            self.assertNotIn("zero buzz", tips)
        self.assertLessEqual(breath_hits, 1)
        self.assertEqual(backing_hits, 0)  # no song form → metronome, not backing
        # Semantics: articulation mid/low critique not in went_well
        art = next(r for r in results if r["id"] == "articulation")
        self.assertNotIn("same attack", str(art.get("went_well") or "").lower())


class FamilyHelpersTests(unittest.TestCase):
    def test_instrument_family_flute(self) -> None:
        self.assertEqual(instrument_family("Flute"), "flute")
        self.assertEqual(instrument_family("Tenor Saxophone"), "saxophone")


if __name__ == "__main__":
    unittest.main()

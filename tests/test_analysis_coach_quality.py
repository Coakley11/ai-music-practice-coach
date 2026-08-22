"""Regression tests for analysis status messages + coach quality fixes."""

from __future__ import annotations

import unittest

import numpy as np

from analysis_coach_quality import (
    build_analysis_status_message,
    criteria_overall_score_label,
    criteria_report_heading,
    dedupe_recommendations,
    has_song_form_context,
    has_song_harmony_context,
    instrument_family,
    is_mission_evaluation_active,
)
from mission_analysis import _coach_result_fields, score_missions
from mission_upload_handoff import MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY
from recording_analysis import (
    AudioFeatures,
    _intonation_stats_from_f0,
    _pitch_analysis,
    _technique_analysis,
    build_practice_plan,
    compute_performance_scores,
)
from recording_analysis_context import (
    RECORDING_TYPE_MISSION,
    RECORDING_TYPE_PRACTICE,
    SONG_SOURCE_OTHER,
)
from mission_analysis_ui import render_mission_analysis_html


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
    def test_practice_take_omits_improvisation_missions_wording(self) -> None:
        """Ordinary Practice Take + selected criteria/focuses is NOT a Mission."""
        ctx = {
            "recording_type": RECORDING_TYPE_PRACTICE,
            "evaluating_criteria_labels": [
                "Scale/mode usage",
                "Dynamics",
                "Articulation",
            ],
            "practice_focuses": ["Phrasing", "Articulation", "Scales"],
        }
        msg = build_analysis_status_message(
            ctx,
            mission_ids=["scale_connection", "dynamics", "articulation"],
        )
        lower = msg.lower()
        self.assertTrue(msg.startswith("Analyzing "))
        self.assertIn("scale/mode usage", lower)
        self.assertIn("dynamics", lower)
        self.assertTrue("phrasing" in lower or "scales" in lower)
        self.assertNotIn("improvisation missions", lower)
        self.assertFalse(is_mission_evaluation_active(recording_type=RECORDING_TYPE_PRACTICE, ctx=ctx))
        # Avoid exact duplicate articulation token twice as bare repeats.
        self.assertEqual(lower.count("articulation"), 1)

    def test_manual_mission_recording_includes_improvisation_missions(self) -> None:
        ctx = {
            "recording_type": RECORDING_TYPE_MISSION,
            "evaluating_criteria_labels": ["Scale/mode usage", "Articulation"],
            "practice_focuses": ["Phrasing"],
        }
        msg = build_analysis_status_message(
            ctx,
            mission_ids=["scale_connection", "articulation"],
        )
        self.assertIn("improvisation missions", msg.lower())
        self.assertTrue(
            is_mission_evaluation_active(recording_type=RECORDING_TYPE_MISSION, ctx=ctx)
        )

    def test_genuine_creative_mission_handoff_includes_improvisation_missions(self) -> None:
        # Genuine Creative → Upload handoff seals Mission Recording identity.
        session = {MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY: True}
        ctx = {
            "recording_type": RECORDING_TYPE_MISSION,
            "evaluating_criteria_labels": ["Scale/mode usage"],
            "practice_focuses": ["Phrasing"],
            "from_mission_handoff": True,
        }
        msg = build_analysis_status_message(
            ctx,
            mission_ids=["scale_connection"],
            session_state=session,
        )
        self.assertIn("improvisation missions", msg.lower())
        self.assertTrue(
            is_mission_evaluation_active(
                recording_type=RECORDING_TYPE_MISSION,
                session_state=session,
                ctx=ctx,
            )
        )

    def test_stale_handoff_marker_does_not_force_mission_wording_on_practice_take(self) -> None:
        """Leftover session handoff must not make a later ordinary Practice Take a Mission."""
        session = {
            MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY: True,
            "improv_active_mission": "Motif development",
        }
        ctx = {
            "recording_type": RECORDING_TYPE_PRACTICE,
            "evaluating_criteria_labels": [
                "Scale/mode usage",
                "Dynamics",
                "Articulation",
            ],
            "practice_focuses": ["Phrasing", "Articulation", "Scales"],
            # Stale durable flags from a prior Mission analysis must not win.
            "mission_evaluation_active": True,
            "from_mission_handoff": True,
        }
        msg = build_analysis_status_message(
            ctx,
            mission_ids=["scale_connection", "articulation"],
            session_state=session,
        )
        self.assertNotIn("improvisation missions", msg.lower())
        self.assertFalse(
            is_mission_evaluation_active(
                recording_type=RECORDING_TYPE_PRACTICE,
                session_state=session,
                ctx=ctx,
            )
        )

    def test_stale_ambient_creative_mission_does_not_trigger_mission_wording(self) -> None:
        session = {
            "improv_active_mission": "Motif development",
            "analysis_sync_creative_mission": True,
            "creative_lab_analysis_mode": "Improvisation Intelligence",
        }
        ctx = {
            "recording_type": RECORDING_TYPE_PRACTICE,
            "evaluating_criteria_labels": [
                "Scale/mode usage",
                "Dynamics",
                "Articulation",
            ],
            "practice_focuses": ["Phrasing", "Articulation", "Scales"],
        }
        msg = build_analysis_status_message(
            ctx,
            mission_ids=["scale_connection", "articulation"],
            session_state=session,
        )
        self.assertNotIn("improvisation missions", msg.lower())
        self.assertFalse(
            is_mission_evaluation_active(
                recording_type=RECORDING_TYPE_PRACTICE,
                session_state=session,
                ctx=ctx,
            )
        )

    def test_report_heading_and_score_label_are_ownership_aware(self) -> None:
        self.assertEqual(
            criteria_report_heading(mission_evaluation_active=False),
            "🎯 Focused AI evaluation",
        )
        self.assertEqual(
            criteria_report_heading(mission_evaluation_active=True),
            "🎯 AI improvisation evaluation",
        )
        self.assertEqual(
            criteria_overall_score_label(mission_evaluation_active=False),
            "Overall criteria score",
        )
        self.assertEqual(
            criteria_overall_score_label(mission_evaluation_active=True),
            "Overall Improvisation Score",
        )
        practice_html = render_mission_analysis_html(
            {
                "mission_evaluation_active": False,
                "mission_results": [
                    {
                        "label": "Scale/mode usage",
                        "score": 72,
                        "summary": "Solid scale coverage.",
                        "went_well": "Clear scale outline.",
                        "improve_to": "Add more contour.",
                    }
                ],
                "overall_improv_score": 72,
                "mission_coach_summary": "Criteria look intentional.",
                "mission_strongest": "Scale/mode usage",
                "mission_weakest": "Articulation",
                "mission_next_recommendation": "Keep drilling scales slowly.",
                "musical_metrics": {"scale_adherence": 70},
            }
        )
        self.assertIn("Focused AI evaluation", practice_html)
        self.assertIn("Overall criteria score", practice_html)
        self.assertNotIn("AI improvisation evaluation", practice_html)
        self.assertIn("Scale/mode usage", practice_html)

        mission_html = render_mission_analysis_html(
            {
                "mission_evaluation_active": True,
                "mission_results": [
                    {
                        "label": "Scale/mode usage",
                        "score": 72,
                        "summary": "Solid scale coverage.",
                        "went_well": "Clear scale outline.",
                        "improve_to": "Add more contour.",
                    }
                ],
                "overall_improv_score": 72,
                "mission_coach_summary": "Mission feedback.",
                "mission_strongest": "Scale/mode usage",
                "mission_weakest": "Articulation",
                "mission_next_recommendation": "Keep drilling scales slowly.",
                "musical_metrics": {"scale_adherence": 70},
            }
        )
        self.assertIn("AI improvisation evaluation", mission_html)
        self.assertIn("Overall Improvisation Score", mission_html)

    def test_coach_report_step_kicker_is_step_3(self) -> None:
        from pathlib import Path

        app = Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py"
        text = app.read_text(encoding="utf-8")
        self.assertIn("Step 3 · Coach report", text)
        self.assertNotIn("Step 2 · Coach report", text)
        self.assertNotIn("Step 2 · Ensemble report", text)

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
        self.assertTrue(has_song_harmony_context({"song_source_type": SONG_SOURCE_OTHER}) is False)


class SongHarmonyVsFormGateTests(unittest.TestCase):
    def test_flat_progression_has_harmony_without_form(self) -> None:
        ctx = {
            "song_source_type": "Custom Progression",
            "display_key": "Eb",
            "target_chords": ["Cm7", "Fm7", "Bb7", "Ebmaj7"],
            "sections": {},
        }
        self.assertTrue(has_song_harmony_context(ctx))
        self.assertFalse(has_song_form_context(ctx))

    def test_named_sections_enable_form(self) -> None:
        ctx = {
            "song_source_type": "Custom Progression",
            "display_key": "Eb",
            "target_chords": ["Cm7", "Fm7"],
            "sections": {"Verse": ["Cm7"], "Chorus": ["Ebmaj7"]},
        }
        self.assertTrue(has_song_harmony_context(ctx))
        self.assertTrue(has_song_form_context(ctx))

    def test_chords_alone_no_longer_count_as_form(self) -> None:
        # Legacy bug: chords alone made has_song_form_context True.
        ctx = {
            "song_source_type": "Catalog",
            "display_key": "F",
            "target_chords": ["Fmaj7", "Gm7", "C7"],
            "sections": {},
        }
        self.assertTrue(has_song_harmony_context(ctx))
        self.assertFalse(has_song_form_context(ctx))

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

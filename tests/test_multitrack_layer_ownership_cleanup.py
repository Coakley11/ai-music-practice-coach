"""Multitrack Layer ownership: spinner, Breath Support evidence, arrangement/form wording."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from analysis_coach_quality import build_analysis_status_message
from multitrack_upload_analysis import (
    build_layer_arrangement_context,
    build_target_layer_focus_analysis,
    enrich_layer_analysis_result,
)


def _layer_features(**overrides):
    base = dict(
        onset_strength_mean=1.1,
        onset_density=1.8,
        groove_tightness=0.48,
        spectral_centroid_mean=2100.0,
        dyn_flatness=0.40,
        dyn_range=0.08,
        pitch_cents_std=22.0,
        energy_curve=[0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _layer_ctx(**overrides):
    ctx = {
        "recording_type": "Multitrack Layer",
        "target_layer": "Flute",
        "instruments": ["Flute", "Piano"],
        "practice_focuses": ["Breath Support", "Dynamics", "Tone"],
        "instrument_focuses": {
            "Flute": ["Breath Support", "Dynamics", "Tone"],
            "Piano": ["Comping"],
        },
        "display_key": "G major",
        "reference_bpm": 95,
        "time_signature": "6/8",
        "song": "Perfect",
        "selected_song_analysis_context": {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "key": "G major",
            "meter": "6/8",
            "bpm": 95,
            "has_song_form": True,
            "sections": {"Intro": ["G"], "Verse 1": ["G", "D"], "Verse 2": ["Em", "D"]},
        },
    }
    ctx.update(overrides)
    return ctx


class LayerSpinnerOwnershipTests(unittest.TestCase):
    def test_layer_spinner_includes_flute_focuses_not_piano_comping(self) -> None:
        msg = build_analysis_status_message(_layer_ctx(), multitrack=True)
        lower = msg.lower()
        self.assertTrue(msg.startswith("Analyzing "))
        self.assertIn("flute", lower)
        self.assertIn("breath support", lower)
        self.assertIn("dynamics", lower)
        self.assertIn("tone", lower)
        self.assertNotIn("piano", lower)
        self.assertNotIn("comping", lower)

    def test_layer_spinner_does_not_claim_ensemble_balance_for_one_target(self) -> None:
        msg = build_analysis_status_message(_layer_ctx(), multitrack=True).lower()
        self.assertNotIn("balance", msg)
        self.assertNotIn("ensemble interaction", msg)

    def test_non_target_focuses_never_enter_layer_spinner(self) -> None:
        msg = build_analysis_status_message(
            _layer_ctx(
                instrument_focuses={
                    "Flute": ["Tone"],
                    "Piano": ["Comping"],
                    "Guitar": ["Rhythm"],
                }
            ),
            multitrack=True,
        ).lower()
        self.assertIn("flute", msg)
        self.assertNotIn("piano", msg)
        self.assertNotIn("guitar", msg)
        self.assertNotIn("comping", msg)
        self.assertNotIn("rhythm", msg)

    def test_mix_may_still_advertise_balance(self) -> None:
        msg = build_analysis_status_message(
            {
                "recording_type": "Multitrack Mix",
                "instrument_focuses": {
                    "Flute": ["Tone"],
                    "Piano": ["Comping"],
                },
                "practice_focuses": ["Tone"],
            },
            multitrack=True,
        ).lower()
        self.assertTrue("balance" in msg or "ensemble" in msg)


class LayerTargetContextOwnershipTests(unittest.TestCase):
    def test_flute_is_target_and_piano_is_context_only(self) -> None:
        arr = build_layer_arrangement_context(_layer_ctx())
        lower = arr.lower()
        self.assertIn("flute", lower)
        self.assertIn("piano", lower)
        self.assertIn("comping", lower)
        self.assertIn("arrangement context", lower)
        self.assertIn("no audio was scored", lower)
        self.assertNotIn("piano score", lower)

    def test_removing_piano_removes_piano_context(self) -> None:
        arr = build_layer_arrangement_context(
            _layer_ctx(
                instruments=["Flute"],
                instrument_focuses={"Flute": ["Breath Support", "Dynamics", "Tone"]},
            )
        )
        self.assertFalse(arr.strip())

    def test_focus_blocks_only_cover_target_focuses(self) -> None:
        blocks = build_target_layer_focus_analysis(
            features=_layer_features(),
            scores={"technique": 70, "tone": 72, "musicality": 94},
            categories={},
            ctx=_layer_ctx(),
            musical_metrics={},
        )
        labels = [b["focus"] for b in blocks]
        self.assertEqual(labels, ["Breath Support", "Dynamics", "Tone"])
        self.assertNotIn("Comping", labels)


class BreathSupportEvidenceTests(unittest.TestCase):
    def test_selection_metadata_is_not_detected_evidence(self) -> None:
        blocks = build_target_layer_focus_analysis(
            features=_layer_features(),
            scores={"technique": 70, "tone": 72, "musicality": 94},
            categories={
                "technique": {
                    "findings": [
                        "Flute attack profile reviewed from onset clarity and attack density."
                    ]
                }
            },
            ctx=_layer_ctx(practice_focuses=["Breath Support"]),
            musical_metrics={},
        )
        breath = blocks[0]
        findings = " ".join(breath.get("findings") or []).lower()
        went = str(breath.get("went_well") or "").lower()
        self.assertNotIn("attack density", findings)
        self.assertNotIn("attack profile", findings)
        self.assertNotIn("explicit coaching goal", went)
        self.assertNotIn("was analyzed with breath support", went)

    def test_breath_uses_sustain_energy_pitch_cues_when_available(self) -> None:
        breath = build_target_layer_focus_analysis(
            features=_layer_features(),
            scores={},
            categories={},
            ctx=_layer_ctx(practice_focuses=["Breath Support"]),
            musical_metrics={},
        )[0]
        findings = " ".join(breath.get("findings") or []).lower()
        self.assertTrue("sustain" in findings or "energy" in findings or "pitch" in findings)
        self.assertIn("acoustic", findings)
        self.assertNotIn("breath pressure", findings)

    def test_limited_direct_evidence_when_sustain_cues_missing(self) -> None:
        breath = build_target_layer_focus_analysis(
            features=_layer_features(
                dyn_flatness=0.0,
                dyn_range=0.0,
                pitch_cents_std=None,
                energy_curve=None,
            ),
            scores={},
            categories={},
            ctx=_layer_ctx(practice_focuses=["Breath Support"]),
            musical_metrics={},
        )[0]
        assessment = str(breath.get("assessment") or "").lower()
        findings = " ".join(breath.get("findings") or []).lower()
        self.assertIn("limited", assessment)
        self.assertIn("limited direct", findings)
        self.assertIn("not treated as breath support evidence", findings)
        # Disclaimer may mention onset/attack metrics; do not treat that as claimed evidence.
        self.assertNotIn("attack density ≈", findings)
        self.assertNotIn("onset strength mean", findings)

    def test_breath_drill_is_specific_not_generic_focus_loop(self) -> None:
        breath = build_target_layer_focus_analysis(
            features=_layer_features(),
            scores={},
            categories={},
            ctx=_layer_ctx(practice_focuses=["Breath Support"]),
            musical_metrics={},
        )[0]
        drill = str(breath.get("drill") or "").lower()
        self.assertIn("breath support", drill)
        self.assertTrue(
            "8 beat" in drill or "long tone" in drill or "crescendo" in drill,
            drill,
        )
        self.assertNotIn("one short loop focusing only on breath support", drill)


class LayerSummaryFormTests(unittest.TestCase):
    def test_song_context_appears_once_after_enrich(self) -> None:
        result = {
            "ok": True,
            "coach_summary": (
                "Song context: Perfect — G major, 6/8, reference tempo 95 BPM. "
                "You asked me to evaluate Practice Focuses: Breath Support, Dynamics, Tone."
            ),
            "scores": {"timing": 70, "pitch": 70, "technique": 70, "groove": 70, "musicality": 70, "tone": 70},
            "categories": {},
            "features": _layer_features(),
            "practice_plan": [],
        }
        out = enrich_layer_analysis_result(result, _layer_ctx(), uploaded_track_count=1)
        summary = str(out.get("coach_summary") or "")
        self.assertEqual(summary.lower().count("song context:"), 1)
        self.assertIn("analyzing flute only", summary.lower())

    def test_known_sections_are_prospective_not_observed_transitions(self) -> None:
        arr = build_layer_arrangement_context(_layer_ctx()).lower()
        self.assertIn("prospective", arr)
        self.assertNotIn("around intro, verse 1, verse 2 transitions", arr)
        self.assertIn("sections such as", arr)

    def test_no_audio_scored_for_other_instruments_copy_remains(self) -> None:
        arr = build_layer_arrangement_context(_layer_ctx()).lower()
        self.assertIn("no audio was scored", arr)


if __name__ == "__main__":
    unittest.main()

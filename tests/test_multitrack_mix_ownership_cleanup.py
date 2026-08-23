"""Multitrack Mix ownership: spinner, Focus coverage, evidence confidence, ensemble section."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from analysis_coach_quality import build_analysis_status_message
from multitrack_upload_analysis import (
    build_ensemble_mix_analysis,
    build_mix_focus_analysis,
    enrich_mix_analysis_result,
)
from recording_analysis_ui import render_analysis_dashboard


def _mix_features(**overrides):
    base = dict(
        onset_strength_mean=1.0,
        onset_density=2.1,
        groove_tightness=0.52,
        spectral_centroid_mean=4116.0,
        dyn_flatness=0.41,
        dyn_range=0.09,
        pitch_cents_std=28.0,
        energy_curve=[0.2, 0.25, 0.3, 0.4, 0.45, 0.4, 0.35, 0.3],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _mix_ctx(**overrides):
    ctx = {
        "recording_type": "Multitrack Mix",
        "instruments": ["Flute", "Guitar"],
        "practice_focuses": ["Articulation", "Tone"],
        "instrument_focuses": {
            "Flute": ["Articulation", "Tone"],
            "Guitar": ["Rhythm Guitar"],
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
        },
    }
    ctx.update(overrides)
    return ctx


class MixSpinnerOwnershipTests(unittest.TestCase):
    def test_mix_spinner_mentions_flute_and_guitar(self) -> None:
        msg = build_analysis_status_message(_mix_ctx(), multitrack=True)
        lower = msg.lower()
        self.assertTrue(msg.startswith("Analyzing "))
        self.assertIn("flute", lower)
        self.assertIn("guitar", lower)
        self.assertIn("articulation", lower)
        self.assertIn("tone", lower)
        self.assertTrue("rhythm" in lower)

    def test_mix_spinner_includes_ensemble_baselines(self) -> None:
        msg = build_analysis_status_message(_mix_ctx(), multitrack=True).lower()
        self.assertTrue(
            "timing" in msg or "timing cohesion" in msg,
            msg,
        )
        self.assertTrue("groove" in msg or "balance" in msg or "interaction" in msg, msg)

    def test_mix_spinner_does_not_collapse_to_first_instrument_only(self) -> None:
        msg = build_analysis_status_message(_mix_ctx(), multitrack=True).lower()
        self.assertIn("flute", msg)
        self.assertIn("guitar", msg)

    def test_mix_spinner_avoids_awkward_guitar_rhythm_guitar(self) -> None:
        msg = build_analysis_status_message(_mix_ctx(), multitrack=True).lower()
        self.assertNotIn("guitar rhythm guitar", msg)

    def test_layer_spinner_remains_target_only(self) -> None:
        msg = build_analysis_status_message(
            {
                "recording_type": "Multitrack Layer",
                "target_layer": "Flute",
                "instruments": ["Flute", "Guitar"],
                "instrument_focuses": {
                    "Flute": ["Articulation", "Tone"],
                    "Guitar": ["Rhythm Guitar"],
                },
            },
            multitrack=True,
        ).lower()
        self.assertIn("flute", msg)
        self.assertNotIn("guitar", msg)
        self.assertNotIn("balance", msg)


class MixOwnershipTests(unittest.TestCase):
    def _enriched(self, uploaded_track_count: int = 1):
        result = {
            "ok": True,
            "coach_summary": (
                "You asked me to evaluate Practice Focuses: Articulation, Tone. "
                "Biggest growth edge: pitch & intonation (score 39/100)."
            ),
            "scores": {
                "timing": 70,
                "pitch": 39,
                "technique": 72,
                "groove": 68,
                "musicality": 74,
                "confidence": 71,
                "tone": 75,
            },
            "categories": {
                "pitch": {
                    "title": "Pitch",
                    "findings": ["Flute intonation drifts."],
                    "tips": ["drone"],
                },
                "tone": {
                    "title": "Tone Quality",
                    "findings": ["Brightness (spectral centroid): 4116 Hz avg."],
                    "tips": ["even"],
                },
                "technique": {
                    "title": "Technique",
                    "findings": ["Flute attack profile reviewed from onset clarity."],
                    "tips": ["tongue"],
                },
            },
            "features": _mix_features(),
            "instrument": "Flute",
            "biggest_issue": "pitch & intonation (score 39/100)",
        }
        return enrich_mix_analysis_result(
            result,
            _mix_ctx(),
            uploaded_track_count=uploaded_track_count,
        )

    def test_mix_summary_lists_all_instruments_and_focus_mappings(self) -> None:
        out = self._enriched()
        summary = str(out.get("coach_summary") or "").lower()
        self.assertIn("flute", summary)
        self.assertIn("guitar", summary)
        self.assertIn("articulation", summary)
        self.assertIn("rhythm guitar", summary)
        self.assertIn("multitrack mix", summary)

    def test_top_metadata_not_flute_only(self) -> None:
        out = self._enriched()
        self.assertEqual(out.get("instrument"), "Multitrack Mix")
        self.assertIn("Guitar", str(out.get("instrument_display") or ""))

    def test_practice_focus_analysis_includes_guitar(self) -> None:
        out = self._enriched()
        labels = [
            (b.get("instrument"), b.get("focus"))
            for b in (out.get("mix_focus_analysis") or [])
        ]
        self.assertIn(("Flute", "Articulation"), labels)
        self.assertIn(("Flute", "Tone"), labels)
        self.assertIn(("Guitar", "Rhythm Guitar"), labels)

    def test_one_mix_file_does_not_claim_high_target_attribution(self) -> None:
        out = self._enriched(uploaded_track_count=1)
        for block in out.get("mix_focus_analysis") or []:
            conf = str(block.get("attribution_confidence") or "").lower()
            self.assertNotIn("high target attribution", conf)
            self.assertIn("limited", conf)


class MixEvidenceTests(unittest.TestCase):
    def test_global_spectral_centroid_labeled_mix_not_flute_tone(self) -> None:
        out = enrich_mix_analysis_result(
            {
                "ok": True,
                "coach_summary": "x",
                "scores": {"tone": 75, "timing": 70, "pitch": 39, "groove": 68},
                "categories": {
                    "tone": {
                        "title": "Tone Quality",
                        "findings": ["Brightness (spectral centroid): 4116 Hz avg."],
                        "tips": [],
                    }
                },
                "features": _mix_features(),
            },
            _mix_ctx(),
            uploaded_track_count=1,
        )
        findings = " ".join(
            str(x) for x in ((out.get("categories") or {}).get("tone") or {}).get("findings") or []
        ).lower()
        self.assertIn("mix", findings)
        self.assertIn("spectrum", findings)

    def test_ambiguous_pitch_not_definitive_growth_edge(self) -> None:
        out = enrich_mix_analysis_result(
            {
                "ok": True,
                "coach_summary": "Biggest growth edge: pitch & intonation (score 39/100).",
                "scores": {
                    "timing": 70,
                    "pitch": 39,
                    "technique": 72,
                    "groove": 55,
                    "musicality": 74,
                    "confidence": 71,
                    "tone": 75,
                },
                "categories": {},
                "features": _mix_features(),
                "biggest_issue": "pitch & intonation (score 39/100)",
            },
            _mix_ctx(),
            uploaded_track_count=1,
        )
        biggest = str(out.get("biggest_issue") or "").lower()
        summary = str(out.get("coach_summary") or "").lower()
        self.assertNotIn("pitch & intonation (score 39/100)", biggest)
        self.assertTrue(
            "groove" in biggest or "timing" in biggest or "musical" in biggest,
            biggest,
        )
        self.assertNotIn("biggest growth edge: pitch & intonation (score 39/100)", summary)

    def test_guitar_rhythm_gets_limited_attribution_block_for_one_mix(self) -> None:
        blocks = build_mix_focus_analysis(
            features=_mix_features(),
            scores={"timing": 70, "groove": 68, "technique": 72, "tone": 75},
            categories={},
            ctx=_mix_ctx(),
            uploaded_track_count=1,
        )
        guitar = [b for b in blocks if b.get("instrument") == "Guitar"]
        self.assertTrue(guitar)
        self.assertIn("Rhythm Guitar", [b.get("focus") for b in guitar])
        conf = str(guitar[0].get("attribution_confidence") or "").lower()
        self.assertIn("limited", conf)

    def test_multi_stem_path_marks_stronger_attribution_scope(self) -> None:
        blocks = build_mix_focus_analysis(
            features=_mix_features(),
            scores={"technique": 72, "tone": 75, "timing": 70},
            categories={},
            ctx=_mix_ctx(),
            uploaded_track_count=2,
        )
        scopes = {b.get("attribution_scope") for b in blocks}
        self.assertIn("stem", scopes)


class MixEnsembleTests(unittest.TestCase):
    def test_ensemble_section_present(self) -> None:
        ens = build_ensemble_mix_analysis(
            features=_mix_features(),
            scores={"timing": 70, "groove": 68, "musicality": 74},
            ctx=_mix_ctx(),
            uploaded_track_count=1,
        )
        self.assertEqual(ens.get("input_mode"), "single_mix_file")
        self.assertTrue(ens.get("timing_cohesion"))
        self.assertTrue(ens.get("groove_cohesion"))
        self.assertTrue(ens.get("balance"))
        bal = " ".join(ens.get("balance") or []).lower()
        self.assertIn("without isolated stems", bal)

    def test_ui_renders_ensemble_and_both_instruments(self) -> None:
        html = render_analysis_dashboard(
            {
                "ok": True,
                "coach_summary": "Multitrack Mix: Flute + Guitar",
                "recording_type": "Multitrack Mix",
                "multitrack_mode": "mix_single",
                "instrument": "Multitrack Mix",
                "instrument_display": "Multitrack Mix — Flute + Guitar",
                "instruments": ["Flute", "Guitar"],
                "duration": 103.5,
                "scores": {
                    "timing": 70,
                    "pitch": 39,
                    "technique": 72,
                    "groove": 68,
                    "musicality": 74,
                    "confidence": 71,
                    "tone": 75,
                },
                "categories": {},
                "practice_plan": [],
                "mix_focus_analysis": [
                    {
                        "instrument": "Flute",
                        "focus": "Articulation",
                        "assessment": "limited",
                        "findings": ["mix attacks"],
                        "attribution_confidence": "Limited instrument attribution",
                    },
                    {
                        "instrument": "Guitar",
                        "focus": "Rhythm Guitar",
                        "assessment": "limited",
                        "findings": ["pulse"],
                        "attribution_confidence": "Limited instrument attribution",
                    },
                ],
                "ensemble_mix_analysis": {
                    "title": "Ensemble Mix analysis",
                    "input_mode": "single_mix_file",
                    "balance_policy": "One mixed file",
                    "timing_cohesion": ["pulse"],
                    "groove_cohesion": ["groove"],
                    "balance": ["no per-instrument dB"],
                    "interaction_space": ["density"],
                    "musical_shape": ["arc"],
                },
                "biggest_issue": "groove",
                "next_focus": "lock",
                "most_improved": "timing",
            }
        )
        self.assertIn("Practice Focus analysis — Ensemble", html)
        self.assertIn("Rhythm Guitar", html)
        self.assertIn("Ensemble Mix analysis", html)
        self.assertIn("Multitrack Mix", html)
        self.assertNotIn("Practice Focus analysis — Flute", html)


if __name__ == "__main__":
    unittest.main()

"""Multitrack Upload — Analyze Ensemble contracts (Layer vs Mix)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from multitrack_upload_analysis import (
    run_multitrack_upload_analysis,
    validate_multitrack_analyze_request,
)
from recording_analysis_context import RECORDING_TYPE_MT_LAYER, RECORDING_TYPE_MT_MIX
from upload_analysis_modes import MULTITRACK_RECORDING


class TestMultitrackAnalyzeValidation(unittest.TestCase):
    def test_layer_missing_audio_visible_validation(self) -> None:
        msg = validate_multitrack_analyze_request(
            recording_type=RECORDING_TYPE_MT_LAYER,
            file_count=0,
            instruments=["Flute", "Piano"],
            target_layer="Flute",
        )
        self.assertIsNotNone(msg)
        self.assertIn("Upload", msg or "")
        self.assertIn("target layer", (msg or "").lower())

    def test_layer_missing_target_visible_validation(self) -> None:
        msg = validate_multitrack_analyze_request(
            recording_type=RECORDING_TYPE_MT_LAYER,
            file_count=1,
            instruments=["Flute", "Piano"],
            target_layer="",
        )
        self.assertIsNotNone(msg)
        self.assertIn("target layer", (msg or "").lower())

    def test_mix_missing_audio_visible_validation(self) -> None:
        msg = validate_multitrack_analyze_request(
            recording_type=RECORDING_TYPE_MT_MIX,
            file_count=0,
            instruments=["Flute", "Piano"],
        )
        self.assertIsNotNone(msg)
        self.assertTrue(
            "mix" in (msg or "").lower() or "stem" in (msg or "").lower(),
            msg,
        )

    def test_layer_valid_one_file(self) -> None:
        self.assertIsNone(
            validate_multitrack_analyze_request(
                recording_type=RECORDING_TYPE_MT_LAYER,
                file_count=1,
                instruments=["Flute", "Piano"],
                target_layer="Flute",
            )
        )

    def test_mix_valid_one_file(self) -> None:
        self.assertIsNone(
            validate_multitrack_analyze_request(
                recording_type=RECORDING_TYPE_MT_MIX,
                file_count=1,
                instruments=["Flute", "Piano"],
            )
        )


class TestMultitrackAnalyzeOrchestration(unittest.TestCase):
    def _layer_ctx(self) -> dict:
        return {
            "recording_type": RECORDING_TYPE_MT_LAYER,
            "workflow": MULTITRACK_RECORDING,
            "instruments": ["Flute", "Piano"],
            "target_layer": "Flute",
            "instrument_focuses": {
                "Flute": ["Phrasing", "Articulation", "Tone"],
                "Piano": ["Comping", "Voicing", "Rhythm"],
            },
            "practice_focuses": ["Phrasing", "Articulation", "Tone"],
        }

    def _mix_ctx(self) -> dict:
        return {
            "recording_type": RECORDING_TYPE_MT_MIX,
            "workflow": MULTITRACK_RECORDING,
            "instruments": ["Flute", "Piano"],
            "instrument_focuses": {
                "Flute": ["Phrasing", "Articulation", "Tone"],
                "Piano": ["Comping", "Voicing", "Rhythm"],
            },
            "practice_focuses": ["Phrasing", "Articulation", "Tone"],
        }

    def test_layer_valid_upload_invokes_analyze_recording(self) -> None:
        tracks = [{"name": "flute.wav", "filename": "flute.wav", "bytes": b"RIFF"}]
        with patch(
            "recording_analysis.analyze_recording",
            return_value={
                "ok": True,
                "coach_summary": "ok",
                "practice_focuses": ["Phrasing", "Articulation", "Tone"],
            },
        ) as mock_ar:
            with patch("recording_analysis.analyze_multitrack") as mock_mt:
                result = run_multitrack_upload_analysis(tracks, self._layer_ctx())
        mock_ar.assert_called_once()
        mock_mt.assert_not_called()
        self.assertTrue(result.get("ok"))
        self.assertTrue(result.get("multitrack"))
        self.assertEqual(result.get("target_layer"), "Flute")
        call_ctx = mock_ar.call_args[0][2]
        self.assertEqual(
            call_ctx.get("practice_focuses"),
            ["Phrasing", "Articulation", "Tone"],
        )

    def test_layer_preserves_complete_target_focus_list(self) -> None:
        tracks = [{"name": "flute.wav", "filename": "flute.wav", "bytes": b"RIFF"}]
        with patch(
            "recording_analysis.analyze_recording",
            return_value={"ok": True, "coach_summary": "ok"},
        ) as mock_ar:
            result = run_multitrack_upload_analysis(tracks, self._layer_ctx())
        call_ctx = mock_ar.call_args[0][2]
        self.assertEqual(
            call_ctx.get("practice_focuses"),
            ["Phrasing", "Articulation", "Tone"],
        )
        self.assertEqual(
            result.get("instrument_focuses"),
            {
                "Flute": ["Phrasing", "Articulation", "Tone"],
                "Piano": ["Comping", "Voicing", "Rhythm"],
            },
        )
        focus_labels = [
            str(b.get("focus"))
            for b in (result.get("target_layer_focus_analysis") or [])
            if isinstance(b, dict)
        ]
        self.assertEqual(focus_labels, ["Phrasing", "Articulation", "Tone"])

    def test_mix_valid_one_file_invokes_analyze_recording(self) -> None:
        tracks = [{"name": "mix.wav", "filename": "mix.wav", "bytes": b"RIFF"}]
        with patch(
            "recording_analysis.analyze_recording",
            return_value={"ok": True, "coach_summary": "blend"},
        ) as mock_ar:
            with patch("recording_analysis.analyze_multitrack") as mock_mt:
                result = run_multitrack_upload_analysis(tracks, self._mix_ctx())
        mock_ar.assert_called_once()
        mock_mt.assert_not_called()
        self.assertTrue(result.get("ok"))
        self.assertTrue(result.get("multitrack"))
        self.assertEqual(
            result.get("instrument_focuses"),
            {
                "Flute": ["Phrasing", "Articulation", "Tone"],
                "Piano": ["Comping", "Voicing", "Rhythm"],
            },
        )

    def test_mix_two_stems_invokes_analyze_multitrack(self) -> None:
        tracks = [
            {"name": "a.wav", "filename": "a.wav", "bytes": b"RIFF1"},
            {"name": "b.wav", "filename": "b.wav", "bytes": b"RIFF2"},
        ]
        with patch(
            "recording_analysis.analyze_multitrack",
            return_value={
                "ok": True,
                "multitrack": True,
                "findings": ["locked"],
                "instrument_focuses": {
                    "Flute": ["Phrasing", "Articulation", "Tone"],
                    "Piano": ["Comping", "Voicing", "Rhythm"],
                },
            },
        ) as mock_mt:
            with patch("recording_analysis.analyze_recording") as mock_ar:
                result = run_multitrack_upload_analysis(tracks, self._mix_ctx())
        mock_mt.assert_called_once()
        mock_ar.assert_not_called()
        self.assertTrue(result.get("ok"))
        self.assertEqual(
            result.get("instrument_focuses"),
            {
                "Flute": ["Phrasing", "Articulation", "Tone"],
                "Piano": ["Comping", "Voicing", "Rhythm"],
            },
        )

    def test_mix_preserves_complete_instrument_focus_mapping(self) -> None:
        tracks = [{"name": "mix.wav", "filename": "mix.wav", "bytes": b"RIFF"}]
        mapping = {
            "Flute": ["Phrasing", "Articulation", "Tone"],
            "Piano": ["Comping", "Voicing", "Rhythm"],
        }
        with patch(
            "recording_analysis.analyze_recording",
            return_value={"ok": True, "coach_summary": "ok"},
        ):
            result = run_multitrack_upload_analysis(tracks, self._mix_ctx())
        self.assertEqual(result.get("instrument_focuses"), mapping)

    def test_layer_missing_audio_returns_visible_error_payload(self) -> None:
        result = run_multitrack_upload_analysis([], self._layer_ctx())
        self.assertFalse(result.get("ok"))
        self.assertTrue(result.get("multitrack"))
        self.assertIn("Upload", result.get("message") or "")

    def test_exceptions_are_not_swallowed(self) -> None:
        tracks = [{"name": "flute.wav", "filename": "flute.wav", "bytes": b"RIFF"}]
        with patch(
            "recording_analysis.analyze_recording",
            side_effect=RuntimeError("boom-diag"),
        ):
            result = run_multitrack_upload_analysis(tracks, self._layer_ctx())
        self.assertFalse(result.get("ok"))
        self.assertTrue(result.get("multitrack"))
        self.assertIn("boom-diag", result.get("message") or "")


class TestMultitrackLayerFocusCoaching(unittest.TestCase):
    def _alto_guitar_ctx(self) -> dict:
        return {
            "recording_type": RECORDING_TYPE_MT_LAYER,
            "workflow": MULTITRACK_RECORDING,
            "instruments": ["Alto Saxophone", "Guitar"],
            "target_layer": "Alto Saxophone",
            "instrument": "Alto Saxophone",
            "instrument_focuses": {
                "Alto Saxophone": ["Articulation", "Tone"],
                "Guitar": ["Rhythm Guitar"],
            },
            "practice_focuses": ["Articulation", "Tone"],
        }

    def test_target_focuses_explicitly_analyzed_and_guitar_is_context_only(self) -> None:
        from multitrack_upload_analysis import (
            build_layer_arrangement_context,
            build_target_layer_focus_analysis,
            enrich_layer_analysis_result,
        )

        ctx = self._alto_guitar_ctx()
        features = {
            "onset_strength_mean": 1.4,
            "onset_density": 1.8,
            "groove_tightness": 0.52,
            "spectral_centroid_mean": 2100.0,
            "dyn_flatness": 0.35,
            "pitch_cents_std": 18.0,
        }
        scores = {"technique": 74, "tone": 68, "timing": 70, "groove": 71, "musicality": 66}
        blocks = build_target_layer_focus_analysis(
            features=features,
            scores=scores,
            categories={
                "technique": {"findings": ["Sax articulation note"], "tips": []},
                "tone": {"findings": ["Brightness note"], "tips": []},
            },
            ctx=ctx,
        )
        labels = [b["focus"] for b in blocks]
        self.assertEqual(labels, ["Articulation", "Tone"])
        art = blocks[0]
        tone = blocks[1]
        self.assertIn("attack", (art.get("went_well") or "").lower() + " " + (art.get("improve_to") or "").lower())
        self.assertTrue(art.get("drill"))
        self.assertIn("tone", (tone.get("went_well") or "").lower() + " " + (tone.get("improve_to") or "").lower())
        self.assertTrue(tone.get("drill"))
        blob = " ".join(
            [
                str(art.get("went_well")),
                str(art.get("improve_to")),
                str(tone.get("went_well")),
                str(tone.get("improve_to")),
                build_layer_arrangement_context(ctx),
            ]
        ).lower()
        self.assertIn("rhythm guitar", blob)
        self.assertIn("arrangement context", blob)
        self.assertNotIn("your rhythm guitar was steady", blob)
        self.assertNotIn("strumming needs work", blob)
        self.assertNotIn("guitar score", blob)

        enriched = enrich_layer_analysis_result(
            {
                "ok": True,
                "coach_summary": "Baseline summary.",
                "features": features,
                "scores": scores,
                "categories": {},
                "practice_plan": [
                    "Layer role drill: mute other stems and check entrances/releases against the form."
                ],
            },
            ctx,
            uploaded_track_count=1,
        )
        self.assertFalse(enriched.get("non_target_instruments_scored"))
        plan_joined = " | ".join(enriched.get("practice_plan") or []).lower()
        self.assertNotIn("mute other stems", plan_joined)
        self.assertTrue("click" in plan_joined or "reference" in plan_joined)
        self.assertIn("arrangement context", (enriched.get("layer_arrangement_context") or "").lower())
        self.assertEqual(
            [b["focus"] for b in enriched.get("target_layer_focus_analysis") or []],
            ["Articulation", "Tone"],
        )

    def test_single_instrument_layer_project_is_valid(self) -> None:
        msg = validate_multitrack_analyze_request(
            recording_type=RECORDING_TYPE_MT_LAYER,
            file_count=1,
            instruments=["Alto Saxophone"],
            target_layer="Alto Saxophone",
        )
        self.assertIsNone(msg)
        tracks = [{"name": "alto.wav", "filename": "alto.wav", "bytes": b"RIFF"}]
        ctx = {
            "recording_type": RECORDING_TYPE_MT_LAYER,
            "workflow": MULTITRACK_RECORDING,
            "instruments": ["Alto Saxophone"],
            "target_layer": "Alto Saxophone",
            "instrument_focuses": {"Alto Saxophone": ["Articulation", "Tone"]},
            "practice_focuses": ["Articulation", "Tone"],
        }
        with patch(
            "recording_analysis.analyze_recording",
            return_value={"ok": True, "coach_summary": "solo layer", "scores": {"technique": 70, "tone": 72}},
        ):
            result = run_multitrack_upload_analysis(tracks, ctx)
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("target_layer"), "Alto Saxophone")
        self.assertEqual(
            [b["focus"] for b in result.get("target_layer_focus_analysis") or []],
            ["Articulation", "Tone"],
        )

    def test_comparison_stems_keep_mute_other_stems_tip(self) -> None:
        from multitrack_upload_analysis import enrich_layer_analysis_result

        enriched = enrich_layer_analysis_result(
            {
                "ok": True,
                "coach_summary": "ok",
                "practice_plan": [
                    "Layer role drill: mute other stems and check entrances/releases against the form."
                ],
                "scores": {"technique": 70, "tone": 70},
                "features": {},
                "categories": {},
            },
            self._alto_guitar_ctx(),
            uploaded_track_count=2,
        )
        joined = " | ".join(enriched.get("practice_plan") or []).lower()
        self.assertIn("mute other stems", joined)

    def test_ui_labels_distinguish_project_and_layer(self) -> None:
        from pathlib import Path

        src = Path("upload_analysis_setup_ui.py").read_text(encoding="utf-8")
        self.assertIn('"Project instruments"', src)
        self.assertIn('"Layer being analyzed"', src)
        self.assertIn("single-instrument Layer project is valid", src)


class TestMultitrackLayerPracticePlan(unittest.TestCase):
    def test_one_file_layer_plan_has_no_mute_other_stems(self) -> None:
        from recording_analysis import build_practice_plan
        from recording_analysis_context import SONG_SOURCE_OTHER

        class _F:
            tempo = 90.0

        plan = build_practice_plan(
            {"timing": 60, "pitch": 70, "technique": 65, "groove": 68, "musicality": 70, "confidence": 72, "tone": 66},
            {
                "instrument": "Alto Saxophone",
                "display_key": "Eb",
                "recording_type": RECORDING_TYPE_MT_LAYER,
                "uploaded_track_count": 1,
                "comparison_stem_count": 1,
                "practice_focuses": ["Articulation", "Tone"],
                "song_source_type": SONG_SOURCE_OTHER,
                "sections": {},
                "target_chords": [],
            },
            _F(),
        )
        joined = " | ".join(plan).lower()
        self.assertNotIn("mute other stems", joined)
        self.assertTrue("click" in joined or "reference" in joined)

    def test_multi_stem_layer_plan_may_mention_mute(self) -> None:
        from recording_analysis import build_practice_plan
        from recording_analysis_context import SONG_SOURCE_OTHER

        class _F:
            tempo = 90.0

        plan = build_practice_plan(
            {"timing": 60, "pitch": 70, "technique": 65, "groove": 68, "musicality": 70, "confidence": 72, "tone": 66},
            {
                "instrument": "Alto Saxophone",
                "display_key": "Eb",
                "recording_type": RECORDING_TYPE_MT_LAYER,
                "uploaded_track_count": 2,
                "comparison_stem_count": 2,
                "practice_focuses": ["Articulation"],
                "song_source_type": SONG_SOURCE_OTHER,
                "sections": {},
                "target_chords": [],
            },
            _F(),
        )
        self.assertIn("mute other stems", " | ".join(plan).lower())


if __name__ == "__main__":
    unittest.main()

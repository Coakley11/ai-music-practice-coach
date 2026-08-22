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


if __name__ == "__main__":
    unittest.main()

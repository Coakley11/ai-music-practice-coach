"""Issue 62 — recording quality of a Multitrack layer.

These are *synthetic* signal tests, not microphone tests. They pin what the capture
settings can and cannot preserve, using tones that stand in for the registers the musician
reported trouble with (a sustained high flute note, a saxophone tone, a guitar attack).
Real-microphone behaviour still has to be heard in a browser; nothing here claims it.
"""

from __future__ import annotations

import unittest

import numpy as np

from multitrack_audio_polish import apply_reverb
from multitrack_capture_quality import (
    ALLOWED_CAPTURE_SAMPLE_RATES,
    MULTITRACK_CAPTURE_SAMPLE_RATE,
    SPEECH_DEFAULT_SAMPLE_RATE,
    capture_quality_findings,
    capture_sample_rate,
    is_music_grade_sample_rate,
    multitrack_capture_class_keys,
    multitrack_mic_keys,
    nyquist_hz,
    widget_key_class_candidates,
)

SR = 48000


def _flute_high_note(freq: float = 2093.0, seconds: float = 1.5, sr: int = SR) -> np.ndarray:
    """A sustained high flute-like note: strong fundamental plus bright upper partials.

    C7 (2093 Hz) is within a flute's range. Its 4th and 5th partials land above 8 kHz, which
    is where a 16 kHz capture stops, so this tone shows the band loss the musician hears as
    a high note going dull or disappearing.
    """
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    partial_gains = (1.0, 0.45, 0.28, 0.18, 0.12, 0.08)
    y = np.zeros_like(t)
    for n, gain in enumerate(partial_gains, start=1):
        y += gain * np.sin(2 * np.pi * freq * n * t)
    # A held note: steady body with soft edges, no decay to silence in the middle.
    env = np.ones_like(t)
    edge = int(0.02 * sr)
    env[:edge] = np.linspace(0, 1, edge)
    env[-edge:] = np.linspace(1, 0, edge)
    return (y * env / np.max(np.abs(y))).astype(np.float32)


def _energy_above(y: np.ndarray, hz: float, sr: int) -> float:
    """Share of spectral energy above ``hz``."""
    spec = np.abs(np.fft.rfft(y.astype(np.float64))) ** 2
    freqs = np.fft.rfftfreq(len(y), 1.0 / sr)
    total = float(spec.sum())
    if total <= 0:
        return 0.0
    return float(spec[freqs > hz].sum() / total)


def _capture_at(y: np.ndarray, rate: int, sr: int = SR) -> np.ndarray:
    """What survives a capture at ``rate``: band-limit to its Nyquist, then resample back."""
    spec = np.fft.rfft(y.astype(np.float64))
    freqs = np.fft.rfftfreq(len(y), 1.0 / sr)
    spec[freqs >= rate / 2.0] = 0.0
    return np.fft.irfft(spec, n=len(y)).astype(np.float32)


class CapturePolicy(unittest.TestCase):
    def test_multitrack_captures_at_a_music_grade_rate(self):
        self.assertEqual(capture_sample_rate(), MULTITRACK_CAPTURE_SAMPLE_RATE)
        self.assertTrue(is_music_grade_sample_rate(capture_sample_rate()))
        self.assertIn(capture_sample_rate(), ALLOWED_CAPTURE_SAMPLE_RATES)

    def test_the_streamlit_speech_default_is_not_music_grade(self):
        self.assertFalse(is_music_grade_sample_rate(SPEECH_DEFAULT_SAMPLE_RATE))
        self.assertEqual(nyquist_hz(SPEECH_DEFAULT_SAMPLE_RATE), 8000.0)
        findings = capture_quality_findings(SPEECH_DEFAULT_SAMPLE_RATE)
        self.assertTrue(any("band-limited" in f for f in findings))
        self.assertTrue(any("speech default" in f for f in findings))

    def test_music_grade_rate_reports_no_bandwidth_finding(self):
        self.assertEqual(capture_quality_findings(MULTITRACK_CAPTURE_SAMPLE_RATE), [])

    def test_unknown_rate_is_reported_not_assumed_good(self):
        findings = capture_quality_findings(None)
        self.assertTrue(any("unknown" in f for f in findings))


class SustainedHighFluteNote(unittest.TestCase):
    """The reported symptom: high flute notes cut off or disappearing."""

    def setUp(self):
        self.note = _flute_high_note()

    def test_the_test_tone_really_has_energy_above_8k(self):
        self.assertGreater(_energy_above(self.note, 8000, SR), 0.002)

    def test_a_16k_capture_destroys_the_bright_partials(self):
        captured = _capture_at(self.note, SPEECH_DEFAULT_SAMPLE_RATE)
        self.assertLess(_energy_above(captured, 8000, SR), 1e-9)

    def test_a_48k_capture_keeps_them(self):
        captured = _capture_at(self.note, MULTITRACK_CAPTURE_SAMPLE_RATE)
        kept = _energy_above(captured, 8000, SR)
        self.assertAlmostEqual(kept, _energy_above(self.note, 8000, SR), places=6)

    def test_a_16k_capture_does_not_shorten_or_silence_the_note(self):
        # Band loss changes the tone, not the length — so "note cut off" is a tone
        # complaint, not a truncation one. This separates the two symptoms.
        captured = _capture_at(self.note, SPEECH_DEFAULT_SAMPLE_RATE)
        self.assertEqual(len(captured), len(self.note))
        mid = captured[len(captured) // 3 : 2 * len(captured) // 3]
        self.assertGreater(float(np.sqrt(np.mean(mid**2))), 0.05)


class OtherRegisters(unittest.TestCase):
    def test_saxophone_tone_loses_edge_at_16k(self):
        sax = _flute_high_note(freq=880.0)  # A5, rich in partials
        before = _energy_above(sax, 8000, SR)
        after = _energy_above(_capture_at(sax, SPEECH_DEFAULT_SAMPLE_RATE), 8000, SR)
        self.assertGreater(before, after)

    def test_guitar_attack_transient_loses_high_content_at_16k(self):
        rng = np.random.default_rng(7)
        attack = np.zeros(int(0.5 * SR), dtype=np.float32)
        attack[:64] = rng.normal(0, 0.8, 64)  # a pick transient is broadband
        t = np.linspace(0, 0.5, len(attack), endpoint=False)
        attack += (0.5 * np.sin(2 * np.pi * 330 * t)).astype(np.float32)
        before = _energy_above(attack, 8000, SR)
        after = _energy_above(_capture_at(attack, SPEECH_DEFAULT_SAMPLE_RATE), 8000, SR)
        self.assertGreater(before, after)


class ReverbIsNonDestructive(unittest.TestCase):
    def test_reverb_off_returns_the_dry_signal_unchanged(self):
        note = _flute_high_note(seconds=0.3)
        np.testing.assert_array_equal(apply_reverb(note, sr=SR, amount=0.0), note)

    def test_reverb_keeps_the_note_present_and_does_not_clip(self):
        note = _flute_high_note(seconds=0.3)
        wet = apply_reverb(note, sr=SR, amount=1.0)
        self.assertEqual(len(wet), len(note))
        self.assertLessEqual(float(np.max(np.abs(wet))), 1.0 + 1e-6)
        self.assertGreater(float(np.sqrt(np.mean(wet**2))), 0.05)


class MicConstraintTargeting(unittest.TestCase):
    def test_every_layer_slot_contributes_a_mic_key(self):
        from multitrack_slots import MULTITRACK_SLOTS

        keys = multitrack_mic_keys({})
        self.assertEqual(len(keys), len(MULTITRACK_SLOTS))
        self.assertIn("mt_record_Guitar", keys)

    def test_a_retaken_slot_uses_its_new_widget_key(self):
        keys = multitrack_mic_keys({"mt_take_nonce_Guitar": 3})
        self.assertIn("mt_record_Guitar__take3", keys)
        self.assertNotIn("mt_record_Guitar", keys)

    def test_slot_names_with_spaces_and_slashes_get_class_safe_candidates(self):
        candidates = widget_key_class_candidates("mt_record_Sax / winds")
        self.assertIn("mt_record_Sax / winds", candidates)  # the key verbatim
        self.assertIn("mt_record_Sax---winds", candidates)  # space, slash, space → '-'
        self.assertIn("mt_record_Sax___winds", candidates)  # the same, rewritten to '_'
        self.assertIn("mt_record_Saxwinds", candidates)  # offending characters dropped

    def test_candidates_cover_all_slots_without_duplicates(self):
        keys = multitrack_capture_class_keys({})
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(any("Piano" in k for k in keys))

    def test_empty_key_yields_no_candidates(self):
        self.assertEqual(widget_key_class_candidates(""), [])


class MicConstraintReuse(unittest.TestCase):
    def test_multitrack_reuses_the_mission_capture_constraints(self):
        from mission_music_capture import MUSIC_CAPTURE_CONSTRAINTS, music_capture_script

        self.assertFalse(MUSIC_CAPTURE_CONSTRAINTS["noiseSuppression"])
        self.assertFalse(MUSIC_CAPTURE_CONSTRAINTS["autoGainControl"])
        self.assertFalse(MUSIC_CAPTURE_CONSTRAINTS["echoCancellation"])
        script = music_capture_script(multitrack_capture_class_keys({}))
        self.assertIn("noiseSuppression", script)
        self.assertIn("mt_record_Guitar", script)

    def test_install_is_a_no_op_without_a_script_capable_streamlit(self):
        from multitrack_capture_quality import install_multitrack_music_capture

        class _NoHtml:
            pass

        self.assertFalse(install_multitrack_music_capture(_NoHtml(), {}))

    def test_install_passes_the_script_to_streamlit(self):
        from multitrack_capture_quality import install_multitrack_music_capture

        sent: list[str] = []

        class _St:
            @staticmethod
            def html(markup, unsafe_allow_javascript=False):
                sent.append(markup)

        self.assertTrue(install_multitrack_music_capture(_St(), {}))
        self.assertIn("noiseSuppression", sent[0])


if __name__ == "__main__":
    unittest.main()

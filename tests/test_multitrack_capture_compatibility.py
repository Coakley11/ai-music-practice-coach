"""Issue 62 — raising the capture rate must not break layers already saved at 16 kHz.

The mix decodes every layer to one common rate before summing, so a project can hold a
16 kHz layer recorded last month beside a 48 kHz layer recorded today. These tests exercise
the real decode library the app uses (librosa), not a stand-in, and also pin that a round
trip through WAV does not shorten a held note.
"""

from __future__ import annotations

import io
import unittest
import wave

import numpy as np

MIX_SR = 44100  # the rate mix_multitrack decodes every layer to


def _wav_bytes(y: np.ndarray, sr: int) -> bytes:
    """16-bit mono PCM WAV, the format st.audio_input returns."""
    pcm = np.clip(np.asarray(y, dtype=np.float64), -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(sr))
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def _held_note(freq: float, seconds: float, sr: int) -> np.ndarray:
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    y = np.sin(2 * np.pi * freq * t)
    edge = max(1, int(0.01 * sr))
    env = np.ones_like(t)
    env[:edge] = np.linspace(0, 1, edge)
    env[-edge:] = np.linspace(1, 0, edge)
    return (y * env * 0.8).astype(np.float32)


def _decode_at(data: bytes, sr: int) -> np.ndarray:
    """Decode exactly as the mix does: librosa.load(path, sr=sr, mono=True)."""
    import tempfile
    from pathlib import Path

    import librosa

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        y, _ = librosa.load(path, sr=sr, mono=True)
        return y
    finally:
        Path(path).unlink(missing_ok=True)


class MixedRateProjects(unittest.TestCase):
    """A legacy 16 kHz layer and a new 48 kHz layer in one project."""

    SECONDS = 1.0

    def setUp(self):
        self.legacy = _wav_bytes(_held_note(440.0, self.SECONDS, 16000), 16000)
        self.fresh = _wav_bytes(_held_note(440.0, self.SECONDS, 48000), 48000)

    def test_both_layers_decode_to_the_mix_rate(self):
        a = _decode_at(self.legacy, MIX_SR)
        b = _decode_at(self.fresh, MIX_SR)
        self.assertAlmostEqual(len(a) / MIX_SR, self.SECONDS, places=2)
        self.assertAlmostEqual(len(b) / MIX_SR, self.SECONDS, places=2)

    def test_layers_stay_aligned_so_the_mix_does_not_smear(self):
        a = _decode_at(self.legacy, MIX_SR)
        b = _decode_at(self.fresh, MIX_SR)
        # Same musical length, so summing them cannot drift one against the other.
        self.assertLess(abs(len(a) - len(b)), int(0.01 * MIX_SR))

    def test_summing_mixed_rate_layers_keeps_both_audible(self):
        a = _decode_at(self.legacy, MIX_SR)
        b = _decode_at(self.fresh, MIX_SR)
        n = min(len(a), len(b))
        mixed = a[:n] + b[:n]
        peak = float(np.max(np.abs(mixed)))
        self.assertGreater(peak, 0.5)
        # Peak-normalising as the mix does cannot clip.
        normalised = mixed / peak * 0.95
        self.assertLessEqual(float(np.max(np.abs(normalised))), 0.95 + 1e-6)

    def test_pitch_is_unchanged_by_the_rate_conversion(self):
        """A resample bug would shift the note; 440 Hz must stay 440 Hz."""
        for data in (self.legacy, self.fresh):
            y = _decode_at(data, MIX_SR)
            spec = np.abs(np.fft.rfft(y.astype(np.float64)))
            freqs = np.fft.rfftfreq(len(y), 1.0 / MIX_SR)
            peak_hz = float(freqs[int(np.argmax(spec))])
            self.assertAlmostEqual(peak_hz, 440.0, delta=5.0)

    def test_a_48k_layer_really_carries_more_band_than_a_16k_one(self):
        """The point of the change: new captures keep content a 16 kHz one cannot."""
        rng = np.random.default_rng(3)
        bright = rng.normal(0, 0.3, int(48000 * 0.5)).astype(np.float32)

        def energy_above(y, hz, sr):
            spec = np.abs(np.fft.rfft(y.astype(np.float64))) ** 2
            freqs = np.fft.rfftfreq(len(y), 1.0 / sr)
            total = float(spec.sum())
            return float(spec[freqs > hz].sum() / total) if total > 0 else 0.0

        at48 = _decode_at(_wav_bytes(bright, 48000), MIX_SR)
        # The same signal captured at 16 kHz: decimate, which band-limits it.
        at16 = _decode_at(_wav_bytes(_decode_at(_wav_bytes(bright, 48000), 16000), 16000), MIX_SR)
        self.assertGreater(energy_above(at48, 8000, MIX_SR), energy_above(at16, 8000, MIX_SR))


class NoTruncationThroughTheRoundTrip(unittest.TestCase):
    def test_a_long_held_note_keeps_its_full_duration(self):
        seconds = 6.0
        data = _wav_bytes(_held_note(2093.0, seconds, 48000), 48000)
        y = _decode_at(data, MIX_SR)
        self.assertAlmostEqual(len(y) / MIX_SR, seconds, places=2)

    def test_the_end_of_the_note_is_not_cut_away(self):
        y = _decode_at(_wav_bytes(_held_note(2093.0, 3.0, 48000), 48000), MIX_SR)
        tail = y[int(len(y) * 0.80) : int(len(y) * 0.95)]
        self.assertGreater(float(np.sqrt(np.mean(tail**2))), 0.1)

    def test_the_attack_at_the_start_is_not_cut_away(self):
        y = _decode_at(_wav_bytes(_held_note(2093.0, 3.0, 48000), 48000), MIX_SR)
        head = y[int(len(y) * 0.05) : int(len(y) * 0.20)]
        self.assertGreater(float(np.sqrt(np.mean(head**2))), 0.1)

    def test_a_steady_note_does_not_sag_in_the_middle(self):
        """What noise suppression does to a held tone, measured as a level drop."""
        y = _decode_at(_wav_bytes(_held_note(2093.0, 4.0, 48000), 48000), MIX_SR)
        thirds = np.array_split(y[int(0.05 * len(y)) : int(0.95 * len(y))], 3)
        levels = [float(np.sqrt(np.mean(t**2))) for t in thirds]
        self.assertLess(max(levels) / max(1e-9, min(levels)), 1.3, f"levels={levels}")


class CapturePolicyDegrades(unittest.TestCase):
    def test_policy_reports_a_rate_streamlit_would_reject(self):
        from multitrack_capture_quality import ALLOWED_CAPTURE_SAMPLE_RATES

        self.assertNotIn(96000, ALLOWED_CAPTURE_SAMPLE_RATES)
        self.assertIn(48000, ALLOWED_CAPTURE_SAMPLE_RATES)

    def test_legacy_16k_layers_are_still_classified_honestly(self):
        from multitrack_capture_quality import capture_quality_findings, is_music_grade_sample_rate

        self.assertFalse(is_music_grade_sample_rate(16000))
        self.assertTrue(capture_quality_findings(16000))


if __name__ == "__main__":
    unittest.main()


class ReverbIsReportedNotHidden(unittest.TestCase):
    """The export is the only audio the coach gets, so a wet mix must say so."""

    def test_a_dry_export_is_reported_as_dry(self):
        from multitrack_recording_identity import export_stem_info

        stems = export_stem_info({"mix_settings": {"reverb_amount": 0.0, "reverb_applied": False}})
        self.assertTrue(stems["dry_audio"])
        self.assertFalse(stems["reverb_applied"])
        self.assertEqual(stems["reverb_note"], "")

    def test_a_wet_export_is_flagged_with_an_explanation(self):
        from multitrack_recording_identity import export_stem_info

        stems = export_stem_info({"mix_settings": {"reverb_amount": 0.4, "reverb_applied": True}})
        self.assertFalse(stems["dry_audio"])
        self.assertTrue(stems["reverb_applied"])
        self.assertIn("not dry", stems["reverb_note"])
        self.assertIn("layers themselves are unchanged", stems["reverb_note"])

    def test_a_legacy_export_without_reverb_metadata_is_assumed_dry(self):
        from multitrack_recording_identity import export_stem_info

        stems = export_stem_info({"export_id": "old", "mix_settings": {}})
        self.assertTrue(stems["dry_audio"])
        self.assertEqual(stems["reverb_note"], "")

    def test_the_saved_row_records_the_reverb_amount(self):
        from media_multitrack_export_catalog import build_multitrack_export_fields
        from multitrack_audio_polish import REVERB_AMOUNT_KEY, REVERB_ENABLED_KEY

        audio = _wav_bytes(_held_note(440.0, 0.2, 44100), 44100)
        session = {REVERB_ENABLED_KEY: True, REVERB_AMOUNT_KEY: 0.35, "mt_tracks": {}}
        fields = build_multitrack_export_fields(session, audio, song_title="Say", track_items=[])
        self.assertAlmostEqual(fields["mix_settings"]["reverb_amount"], 0.35, places=3)
        self.assertTrue(fields["mix_settings"]["reverb_applied"])

    def test_reverb_off_records_a_dry_mix(self):
        from media_multitrack_export_catalog import build_multitrack_export_fields

        audio = _wav_bytes(_held_note(440.0, 0.2, 44100), 44100)
        fields = build_multitrack_export_fields({"mt_tracks": {}}, audio, song_title="Say", track_items=[])
        self.assertFalse(fields["mix_settings"]["reverb_applied"])

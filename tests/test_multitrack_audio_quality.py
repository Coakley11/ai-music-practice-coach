"""Multitrack audio: the mix and the exported WAV must keep the recorded notes and their timing.

These tests run synthetic flute-register takes (fundamentals up to C7 with their harmonics) through the
real decode -> mix -> WAV path and compare the partials and the duration before and after. They cover
everything the app itself does to the audio; they cannot cover what the browser's microphone capture
does before the bytes arrive.
"""
import io
import unittest
import wave

import numpy as np

from backing_audio import wav_bytes_from_float
from multitrack_audio_polish import apply_reverb, mix_reverb_amount, reverb_tail
from streamlit_music_practice_app import _load_audio_mono_bytes, mix_multitrack

SR = 44100
# C6, E6, G6, C7 - the register the flute complaint was about.
NOTES = (1046.5, 1318.5, 1568.0, 2093.0)
NOTE_SEC = 0.5


def _note(f0, dur=NOTE_SEC, sr=SR):
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    y = np.zeros_like(t)
    for h, amp in ((1, 1.0), (2, 0.35), (3, 0.18), (4, 0.08)):
        if f0 * h < sr / 2:
            y += amp * np.sin(2 * np.pi * f0 * h * t)
    env = np.clip(np.minimum(t / 0.02, (dur - t) / 0.05), 0, 1)
    return (y / np.max(np.abs(y)) * 0.8 * env).astype(np.float32)


def _phrase():
    return np.concatenate([_note(f) for f in NOTES])


def _partials(y, f0, sr=SR):
    spec = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    freqs = np.fft.rfftfreq(len(y), 1 / sr)
    peak = spec.max() + 1e-9
    out = []
    for h in (1, 2, 3, 4):
        target = f0 * h
        if target >= sr / 2:
            continue
        out.append(float(spec[np.argmin(np.abs(freqs - target))] / peak))
    return out


def _item(wav, **over):
    base = {"audio_bytes": wav, "filename": "flute.wav", "volume": 1.0,
            "delay": 0.0, "mute": False, "solo": False}
    base.update(over)
    return base


class TestExportKeepsTheNotes(unittest.TestCase):
    def setUp(self):
        self.take = _phrase()
        self.wav = wav_bytes_from_float(self.take, SR)

    def test_the_written_wav_is_cd_quality_mono_pcm(self):
        with wave.open(io.BytesIO(self.wav)) as w:
            self.assertEqual(w.getframerate(), SR)
            self.assertEqual(w.getnchannels(), 1)
            self.assertEqual(w.getsampwidth(), 2)
            self.assertEqual(w.getnframes(), len(self.take))

    def test_decoding_a_layer_preserves_its_length(self):
        decoded = _load_audio_mono_bytes(self.wav, "flute.wav", SR)
        self.assertEqual(len(decoded), len(self.take))

    def test_every_high_note_survives_the_mix_with_its_harmonics(self):
        mixed = mix_multitrack(None, [_item(self.wav)], sr=SR)
        self.assertEqual(len(mixed), len(self.take))
        for i, f0 in enumerate(NOTES):
            with self.subTest(note=f0):
                a = self.take[int(i * NOTE_SEC * SR): int((i + 1) * NOTE_SEC * SR)]
                b = mixed[int(i * NOTE_SEC * SR): int((i + 1) * NOTE_SEC * SR)]
                before, after = _partials(a, f0), _partials(b, f0)
                self.assertEqual(len(before), len(after))
                for p_before, p_after in zip(before, after):
                    self.assertAlmostEqual(p_after, p_before, delta=0.02)

    def test_no_note_is_dropped_or_silenced(self):
        mixed = mix_multitrack(None, [_item(self.wav)], sr=SR)
        for i, f0 in enumerate(NOTES):
            seg = mixed[int(i * NOTE_SEC * SR): int((i + 1) * NOTE_SEC * SR)]
            self.assertGreater(float(np.max(np.abs(seg))), 0.1, f"note {f0} is missing from the mix")

    def test_the_mix_never_clips(self):
        loud = [_item(wav_bytes_from_float(_phrase() * 0.95, SR), volume=2.0) for _ in range(3)]
        mixed = mix_multitrack(None, loud, sr=SR)
        self.assertLessEqual(float(np.max(np.abs(mixed))), 1.0)


class TestTiming(unittest.TestCase):
    def setUp(self):
        self.take = _phrase()
        self.wav = wav_bytes_from_float(self.take, SR)

    def test_a_layer_with_no_offset_starts_where_it_was_recorded(self):
        mixed = mix_multitrack(None, [_item(self.wav)], sr=SR)
        self.assertGreater(float(np.max(np.abs(mixed[: int(0.1 * SR)]))), 0.1)

    def test_a_positive_align_moves_the_layer_later_by_exactly_that_much(self):
        mixed = mix_multitrack(None, [_item(self.wav, delay=0.5)], sr=SR)
        self.assertLess(float(np.max(np.abs(mixed[: int(0.45 * SR)]))), 0.01)   # silence first
        self.assertGreater(float(np.max(np.abs(mixed[int(0.55 * SR): int(0.9 * SR)]))), 0.1)
        self.assertEqual(len(mixed), len(self.take) + int(0.5 * SR))

    def test_a_negative_align_trims_from_the_front(self):
        mixed = mix_multitrack(None, [_item(self.wav, delay=-0.25)], sr=SR)
        self.assertEqual(len(mixed), len(self.take) - int(0.25 * SR))

    def test_mute_and_solo_are_honoured(self):
        a, b = _item(self.wav, mute=True), _item(self.wav)
        self.assertGreater(float(np.max(np.abs(mix_multitrack(None, [a, b], sr=SR)))), 0.1)
        only_muted = mix_multitrack(None, [a], sr=SR)          # a silent mix, never a crash
        self.assertTrue(only_muted.size == 0 or float(np.max(np.abs(only_muted))) <= 1e-6)
        solo = mix_multitrack(None, [_item(self.wav, solo=True), _item(self.wav, volume=5.0)], sr=SR)
        self.assertGreater(float(np.max(np.abs(solo))), 0.1)


class TestOptionalReverbIsNonDestructive(unittest.TestCase):
    def setUp(self):
        self.take = _phrase()

    def test_it_is_off_by_default(self):
        self.assertEqual(mix_reverb_amount({}), 0.0)
        self.assertEqual(mix_reverb_amount({"mt_mix_reverb_amount": 0.9}), 0.0)
        self.assertEqual(mix_reverb_amount({"mt_mix_reverb_on": True}), 0.25)

    def test_zero_amount_returns_the_dry_mix_untouched(self):
        out = apply_reverb(self.take, sr=SR, amount=0.0)
        self.assertTrue(np.array_equal(out, self.take))

    def test_it_keeps_length_level_and_the_notes(self):
        for amount in (0.25, 0.5, 1.0):
            with self.subTest(amount=amount):
                out = apply_reverb(self.take, sr=SR, amount=amount)
                self.assertEqual(len(out), len(self.take))
                self.assertAlmostEqual(float(np.max(np.abs(out))), float(np.max(np.abs(self.take))), delta=1e-3)
                for i, f0 in enumerate(NOTES):
                    seg = out[int(i * NOTE_SEC * SR): int((i + 1) * NOTE_SEC * SR)]
                    self.assertGreater(_partials(seg, f0)[0], 0.8, f"note {f0} lost its fundamental")

    def test_reverb_cannot_restore_a_note_that_was_never_recorded(self):
        """It is a finishing touch, not a repair: silence stays silent."""
        gapped = self.take.copy()
        gapped[int(0.5 * SR): int(1.0 * SR)] = 0.0
        out = apply_reverb(gapped, sr=SR, amount=1.0)
        tail = out[int(0.75 * SR): int(1.0 * SR)]
        self.assertLess(float(np.max(np.abs(tail))), 0.2)

    def test_degenerate_input_is_safe(self):
        empty = np.zeros(0, dtype=np.float32)
        self.assertEqual(len(apply_reverb(empty, sr=SR, amount=0.5)), 0)
        self.assertEqual(len(reverb_tail(empty, SR)), 0)
        self.assertTrue(np.array_equal(apply_reverb(self.take, sr=SR, amount="bad"), self.take))


if __name__ == "__main__":
    unittest.main()

"""Live mission recording mix preview."""

from __future__ import annotations

import struct
import unittest

import numpy as np

from mission_live_recording_mix import mix_dry_mic_with_backing


def _tone_wav(freq: float, ms: int, *, sr: int = 44100) -> bytes:
    n = int(sr * ms / 1000)
    t = np.linspace(0, ms / 1000, n, endpoint=False)
    samples = (0.4 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes()
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(pcm),
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sr,
        sr * 2,
        2,
        16,
        b"data",
        len(pcm),
    )
    return header + pcm


class TestMissionLiveRecordingMix(unittest.TestCase):
    def test_mix_includes_backing_energy(self) -> None:
        dry = _tone_wav(440, 200)
        back = _tone_wav(220, 400)
        mixed = mix_dry_mic_with_backing(dry, back, backing_offset_samples=0, backing_gain=0.8)
        self.assertGreater(len(mixed), len(dry))
        dry_rms = np.sqrt(np.mean(np.frombuffer(dry[44:], dtype=np.int16).astype(float) ** 2))
        mix_rms = np.sqrt(np.mean(np.frombuffer(mixed[44:], dtype=np.int16).astype(float) ** 2))
        self.assertGreater(mix_rms, dry_rms * 0.95)


if __name__ == "__main__":
    unittest.main()

"""Synthesized long tones whose pitch and loudness behaviour is known exactly.

Issue 79's whole problem was that the numbers did not describe the playing. The only way to check
that they do now is to measure audio whose truth is known in advance: a tone that holds 659.2551 Hz
to the sample, a drift of exactly 60 cents, a dropout of exactly 0.4 s. Then "the score should be
high" becomes a statement that can be wrong.

Used by ``tests/test_issue79_tone_sustain.py`` and by ``scripts/_issue79_signal_evidence.py``, so
the evidence in the report and the assertions in the suite describe the same audio.
"""

from __future__ import annotations

import io
import wave
from typing import Callable

import numpy as np

SR = 22050

# Equal-tempered A440 reference pitches.
E2_HZ = 82.4069
BB3_HZ = 233.0819  # a tenor saxophone's written C4 sounds this
E4_HZ = 329.6276
A4_HZ = 440.0
D5_HZ = 587.3295
E5_HZ = 659.2551


def wav_bytes(samples: np.ndarray, sr: int = SR) -> bytes:
    """16-bit mono WAV - the shape ``st.audio_input`` hands the analyzer."""
    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def tone(
    hz: float,
    seconds: float,
    *,
    amp: float = 0.3,
    sr: int = SR,
    cents_curve: Callable[[np.ndarray], np.ndarray] | None = None,
    amp_curve: Callable[[np.ndarray], np.ndarray] | None = None,
    harmonics: tuple[float, ...] = (1.0, 0.25, 0.1),
) -> np.ndarray:
    """A sustained tone following the given pitch and amplitude curves exactly.

    ``cents_curve(t)`` gives the detuning in cents at each instant and ``amp_curve(t)`` a
    multiplier, so a 60-cent drift or a 0.4 s dropout is specified rather than approximated. Two
    harmonics are included because a bare sine is not what a pitch tracker meets in practice.
    """
    n = int(seconds * sr)
    t = np.arange(n) / sr
    cents = np.zeros(n) if cents_curve is None else np.asarray(cents_curve(t), dtype=float)
    inst_hz = hz * (2.0 ** (cents / 1200.0))
    phase = 2 * np.pi * np.cumsum(inst_hz) / sr
    a = (
        np.full(n, amp, dtype=float)
        if amp_curve is None
        else amp * np.asarray(amp_curve(t), dtype=float)
    )
    out = np.zeros(n)
    for k, weight in enumerate(harmonics, start=1):
        out += weight * np.sin(k * phase)
    return a * out


def silence(seconds: float, sr: int = SR) -> np.ndarray:
    return np.zeros(int(seconds * sr))


def noise(seconds: float, *, amp: float = 0.02, seed: int = 7, sr: int = SR) -> np.ndarray:
    """Breath-like broadband noise: sound with no pitch in it."""
    rng = np.random.default_rng(seed)
    return amp * rng.standard_normal(int(seconds * sr))


def ramp(t: np.ndarray, start: float, end: float) -> np.ndarray:
    span = t[-1] if t.size and t[-1] > 0 else 1.0
    return start + (end - start) * (t / span)


def signal_catalog() -> dict[str, tuple[bytes, str | None, str]]:
    """``name -> (wav bytes, target note, what the signal really is)``."""
    steady = tone(E5_HZ, 3.0)
    return {
        "steady_e5_trimmed": (wav_bytes(steady), "E5", "3 s of dead-steady E5"),
        "steady_e5_with_silence": (
            wav_bytes(np.concatenate([silence(1.0), steady, silence(1.0)])),
            "E5",
            "the same E5 with 1 s of silence at each end",
        ),
        "steady_e5_target_e4": (wav_bytes(steady), "E4", "steady E5 against an E4 reference"),
        "steady_e5_target_pitch_class": (
            wav_bytes(steady),
            "E",
            "steady E5 against a pitch-class-only E target",
        ),
        "flat31_e5_target_e4": (
            wav_bytes(tone(E5_HZ * 2 ** (-31 / 1200.0), 3.0)),
            "E4",
            "E5 played 31 cents flat, against an E4 reference",
        ),
        "mild_offset_30c_sharp": (
            wav_bytes(tone(E5_HZ * 2 ** (30 / 1200.0), 3.0)),
            "E5",
            "steady, but 30 cents sharp",
        ),
        "drift_20c": (
            wav_bytes(tone(E5_HZ, 3.0, cents_curve=lambda t: ramp(t, 0.0, 20.0))),
            "E5",
            "a 20-cent upward drift",
        ),
        "drift_60c": (
            wav_bytes(tone(E5_HZ, 3.0, cents_curve=lambda t: ramp(t, 0.0, 60.0))),
            "E5",
            "a 60-cent upward drift",
        ),
        "vibrato_regular": (
            wav_bytes(tone(E5_HZ, 3.0, cents_curve=lambda t: 35.0 * np.sin(2 * np.pi * 5.0 * t))),
            "E5",
            "regular 5 Hz vibrato, +/-35 cents",
        ),
        "fluctuation_irregular": (
            wav_bytes(
                tone(
                    E5_HZ,
                    3.0,
                    cents_curve=lambda t: 45.0
                    * np.sin(2 * np.pi * 1.3 * t + 0.7 * np.sin(2 * np.pi * 0.37 * t)),
                )
            ),
            "E5",
            "irregular wandering, about +/-45 cents",
        ),
        "semitone_jump": (
            wav_bytes(np.concatenate([tone(E5_HZ, 1.5), tone(E5_HZ * 2 ** (1 / 12), 1.5)])),
            "E5",
            "E5 then a semitone higher",
        ),
        "octave_jump": (
            wav_bytes(np.concatenate([tone(E5_HZ, 1.5), tone(E5_HZ * 2, 1.5)])),
            "E5",
            "E5 then an octave higher",
        ),
        "constant_volume_with_silence": (
            wav_bytes(np.concatenate([silence(0.8), tone(A4_HZ, 3.0), silence(0.8)])),
            "A4",
            "even A4 with silence around it",
        ),
        "crescendo": (
            wav_bytes(tone(A4_HZ, 3.0, amp_curve=lambda t: ramp(t, 0.35, 1.0))),
            "A4",
            "a smooth crescendo, about 9 dB",
        ),
        "decrescendo": (
            wav_bytes(tone(A4_HZ, 3.0, amp_curve=lambda t: ramp(t, 1.0, 0.35))),
            "A4",
            "a smooth decrescendo, about 9 dB",
        ),
        "volume_dropout": (
            wav_bytes(
                tone(A4_HZ, 3.0, amp_curve=lambda t: np.where((t > 1.3) & (t < 1.7), 0.08, 1.0))
            ),
            "A4",
            "a sudden 0.4 s dropout mid-note",
        ),
        "breath_noise_only": (wav_bytes(noise(2.5)), "E5", "breath noise, no pitch"),
        "weak_input": (wav_bytes(tone(E5_HZ, 3.0, amp=0.002)), "E5", "a tone 54 dB down"),
        "too_short": (wav_bytes(tone(E5_HZ, 0.35)), "E5", "0.35 s of tone"),
        "flute_d5": (wav_bytes(tone(D5_HZ, 3.0)), "D5", "flute-range D5, steady"),
        "tenor_sax_bb3_concert": (
            wav_bytes(tone(BB3_HZ, 3.0)),
            "Bb3",
            "tenor saxophone written C4 = concert Bb3",
        ),
        "low_e2_steady": (wav_bytes(tone(E2_HZ, 3.0)), "E2", "bass-range E2, steady"),
    }


__all__ = [
    "A4_HZ",
    "BB3_HZ",
    "D5_HZ",
    "E2_HZ",
    "E4_HZ",
    "E5_HZ",
    "SR",
    "noise",
    "ramp",
    "signal_catalog",
    "silence",
    "tone",
    "wav_bytes",
]

"""A guitar amplifier and speaker for the recorded guitar (numpy and scipy only).

The chain follows a real amp: input filter, pickup resonance and tone hump, a preamp stage that clips unevenly, the tone
stack, a second stage, a power section that sags under load, then a speaker. Each tone is its own amp
setting, not one distortion turned up. The speaker is a designed response with a cone's uneven peaks,
a roll-off, off-axis mic combing and a hint of the room, made minimum phase so nothing arrives late.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from scipy import signal

import backing_eq as eq


@dataclass(frozen=True)
class AmpTone:
    input: tuple  # before the first stage
    gain1: float
    bias: float  # uneven clipping, for even harmonics
    stack: tuple  # the tone stack between the stages
    gain2: float
    sag: float
    level: float
    speaker: str


TONES: dict[str, AmpTone] = {
    # A clean combo: full lows, scooped mids, sparkle; barely breaking up on hard strokes.
    "clean": AmpTone(
        (("highpass", 65.0), ("peak", 2800.0, 1.2, 5.0)), 1.3, 0.02,
        (("low_shelf", 140.0, 1.0), ("peak", 480.0, 0.8, -3.0), ("high_shelf", 3000.0, 5.0)),
        0.9, 0.12, 1.65, "open",
    ),
    # A cranked vintage stack: forward mids, chords still ring and notes stay distinct.
    "crunch": AmpTone(
        (("highpass", 95.0), ("peak", 900.0, 0.8, 3.0), ("peak", 2800.0, 1.2, 6.0)), 4.5, 0.06,
        (("low_shelf", 130.0, 1.0), ("peak", 520.0, 0.9, -1.0), ("peak", 1500.0, 0.9, 2.0), ("high_shelf", 2000.0, 4.0)),
        1.4, 0.30, 0.86, "closed",
    ),
    # The same stack pushed by an overdrive pedal: tight lows, a mid hump, long sustain.
    "overdrive": AmpTone(
        (("highpass", 150.0), ("peak", 900.0, 0.7, 5.0), ("peak", 2800.0, 1.2, 7.0)), 10.0, 0.08,
        (("peak", 400.0, 1.0, -3.0), ("peak", 1800.0, 0.9, 2.0), ("high_shelf", 2000.0, 5.0)),
        1.8, 0.34, 0.70, "closed",
    ),
    # A high-gain channel: very tight lows, scooped low-mids, thick but still pick-sensitive.
    "distorted": AmpTone(
        (("highpass", 210.0), ("peak", 950.0, 0.7, 6.0), ("peak", 2800.0, 1.2, 8.0)), 24.0, 0.10,
        (("peak", 350.0, 0.8, -5.0), ("peak", 2200.0, 0.9, 2.5), ("high_shelf", 2000.0, 5.0)),
        2.4, 0.26, 0.62, "closed",
    ),
}

_SPEAKERS = {
    # A closed 4x12: a low thump, then the cone's bright uneven region, and nothing above about 5.5 kHz.
    "closed": dict(low=82.0, high=5400.0, order=9.0, peaks=((105.0, 2.2, 3.5), (420.0, 1.1, -5.5), (1150.0, 1.8, 1.0), (2450.0, 2.4, 7.5), (3400.0, 3.5, 6.5), (4150.0, 6.0, -6.0), (4850.0, 5.0, 3.0)), comb=0.000128),
    # An open-back 1x12: less thump, more air, an easier top.
    "open": dict(low=72.0, high=6600.0, order=7.0, peaks=((130.0, 1.6, 1.5), (500.0, 1.0, -4.0), (2100.0, 2.0, 5.0), (3600.0, 3.0, 5.0), (5000.0, 5.0, -3.0)), comb=0.000096),
}
_IR_TAPS = 2048


@lru_cache(maxsize=4)
def speaker_ir(kind: str, sr: int) -> np.ndarray:
    """The speaker as a short minimum-phase impulse response, with the room's first reflections."""
    spec = _SPEAKERS[kind]
    n = 8192
    f = np.maximum(np.fft.rfftfreq(n, 1.0 / sr), 1.0)
    mag = (f / spec["low"]) ** 2 / np.sqrt(1.0 + (f / spec["low"]) ** 4)
    mag = mag / np.sqrt(1.0 + (f / spec["high"]) ** (2.0 * spec["order"]))
    for fc, q, db in spec["peaks"]:
        mag = mag * 10.0 ** (db / 20.0 * (1.0 / (1.0 + ((f - fc) / (fc / q)) ** 2)))
    mag = mag * (1.0 + 0.12 * np.cos(2.0 * np.pi * f * spec["comb"]))
    log_mag = np.log(np.maximum(mag, 1e-5))
    ceps = np.fft.irfft(log_mag, n)
    folded = np.zeros(n)
    folded[0] = ceps[0]
    folded[1 : n // 2] = 2.0 * ceps[1 : n // 2]
    folded[n // 2] = ceps[n // 2]
    h = np.fft.irfft(np.exp(np.fft.rfft(folded)), n)[:_IR_TAPS]
    h *= np.concatenate((np.ones(_IR_TAPS - 256), np.linspace(1.0, 0.0, 256)))
    room = np.zeros(_IR_TAPS + int(0.016 * sr))
    room[: len(h)] += h
    for delay, gain in ((0.0031, 0.10), (0.0074, -0.07), (0.0129, 0.05)):
        d = int(delay * sr)
        room[d : d + len(h)] += gain * h
    k = np.argmin(np.abs(np.fft.rfftfreq(len(room), 1.0 / sr) - 1000.0))
    return (room / (abs(np.fft.rfft(room)[k]) or 1.0)).astype(np.float32)


def amplify(x: np.ndarray, tone_name: str, sr: int) -> np.ndarray:
    """One tone's span through the amp and speaker. Same length as ``x``."""
    tone = TONES[tone_name]
    x = eq.apply(np.asarray(x, dtype=np.float32), sr, tone.input)
    # Twice the sample rate keeps what the clipping folds back well below the music.
    up = signal.resample_poly(x, 2, 1, window=("kaiser", 6.0)).astype(np.float32)
    sr2 = sr * 2
    bias = tone.bias
    y = np.tanh(up * tone.gain1 + bias) - np.tanh(bias)
    y = eq.apply(y, sr2, (("highpass", 35.0),) + tone.stack)
    y = np.tanh(y * tone.gain2 * (1.0 + 0.5 * bias))
    # The power section sags under a hard chord and recovers: it breathes, it does not squash.
    a = 1.0 - np.exp(-1.0 / (0.045 * sr2))
    env = signal.lfilter([a], [1.0, a - 1.0], np.abs(y))
    y = np.tanh(1.05 * y / (1.0 + tone.sag * env))
    down = signal.resample_poly(y, 1, 2, window=("kaiser", 6.0)).astype(np.float32)[: len(x)]
    out = signal.oaconvolve(down, speaker_ir(tone.speaker, sr), mode="full")[: len(x)]
    return (out * tone.level).astype(np.float32)

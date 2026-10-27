"""Measurable checks on rendered practice-loop audio (no listening required).

Pitch content is read with FFT chroma: the bass band (35–260 Hz) gives the sounding bass
pitch class, the mid band (260–1600 Hz) the chord colour. Rhythm is read from an onset
(spectral-flux) envelope. These checks cannot judge feel or mix balance — that still needs
human listening — but they do catch wrong roots, wrong bass, wrong timing, missing or
duplicated changes, silence, clipping and broken loop boundaries.
"""

from __future__ import annotations

import numpy as np

HOP = 256
FRAME = 2048


def _spectrum(x: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=np.float64)
    if len(x) < 64:
        return np.zeros(1), np.zeros(1)
    win = np.hanning(len(x))
    mag = np.abs(np.fft.rfft(x * win))
    freqs = np.fft.rfftfreq(len(x), 1.0 / sr)
    return freqs, mag


def chroma(x: np.ndarray, sr: int, lo: float, hi: float) -> np.ndarray:
    """12-bin pitch-class energy in [lo, hi] Hz (bin 0 = C)."""
    freqs, mag = _spectrum(x, sr)
    out = np.zeros(12)
    band = (freqs >= lo) & (freqs <= hi)
    if not band.any():
        return out
    f, m = freqs[band], mag[band] ** 2
    midi = 69 + 12 * np.log2(f / 440.0)
    pcs = np.mod(np.round(midi), 12).astype(int)
    np.add.at(out, pcs, m)
    return out


def bass_pc(x: np.ndarray, sr: int) -> int:
    c = chroma(x, sr, 35.0, 260.0)
    return int(np.argmax(c)) if c.sum() > 0 else -1


def onset_envelope(x: np.ndarray, sr: int) -> np.ndarray:
    """Positive spectral flux per hop (one value every ``HOP`` samples)."""
    x = np.asarray(x, dtype=np.float64)
    n = 1 + max(0, (len(x) - FRAME) // HOP)
    win = np.hanning(FRAME)
    prev = None
    env = np.zeros(n)
    for i in range(n):
        seg = x[i * HOP: i * HOP + FRAME]
        if len(seg) < FRAME:
            seg = np.pad(seg, (0, FRAME - len(seg)))
        mag = np.abs(np.fft.rfft(seg * win))
        if prev is not None:
            env[i] = np.maximum(mag - prev, 0.0).sum()
        prev = mag
    return env


def onset_times(x: np.ndarray, sr: int, *, rel: float = 0.25) -> list[float]:
    env = onset_envelope(x, sr)
    if not len(env) or env.max() <= 0:
        return []
    thr = env.max() * rel
    peaks = [i for i in range(1, len(env) - 1) if env[i] >= thr and env[i] >= env[i - 1] and env[i] > env[i + 1]]
    # A frame's flux peaks as an attack reaches the window's centre: report that time.
    return [(p * HOP + FRAME / 2) / sr for p in peaks]


def beat_period(x: np.ndarray, sr: int, lo: float, hi: float) -> float:
    """The strongest onset periodicity (seconds) between ``lo`` and ``hi`` seconds."""
    env = onset_envelope(x, sr)
    env = env - env.mean()
    ac = np.correlate(env, env, mode="full")[len(env) - 1:]
    lags = np.arange(len(ac)) * HOP / sr
    band = (lags >= lo) & (lags <= hi)
    if not band.any():
        return 0.0
    i = int(np.argmax(np.where(band, ac, -np.inf)))
    return float(lags[i])


def rms_db(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=np.float64)
    r = float(np.sqrt(np.mean(x * x))) if len(x) else 0.0
    return 20 * np.log10(r + 1e-12)


def wrap_jump(x: np.ndarray) -> tuple[float, float]:
    """(sample jump across the loop wrap, 99.9th percentile of in-loop sample steps)."""
    x = np.asarray(x, dtype=np.float64)
    steps = np.abs(np.diff(x))
    return float(abs(x[0] - x[-1])), float(np.percentile(steps, 99.9))

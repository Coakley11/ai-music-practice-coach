"""Small studio filters for the band: biquads in cascade (RBJ cookbook), run with scipy's sosfilt."""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from scipy import signal


def _row(b0: float, b1: float, b2: float, a0: float, a1: float, a2: float) -> tuple[float, ...]:
    return (b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0)


def peak(sr: int, fc: float, q: float, db: float) -> tuple[float, ...]:
    a = 10.0 ** (db / 40.0)
    w = 2.0 * math.pi * fc / sr
    alpha = math.sin(w) / (2.0 * q)
    c = math.cos(w)
    return _row(1 + alpha * a, -2 * c, 1 - alpha * a, 1 + alpha / a, -2 * c, 1 - alpha / a)


def low_shelf(sr: int, fc: float, db: float) -> tuple[float, ...]:
    a = 10.0 ** (db / 40.0)
    w = 2.0 * math.pi * fc / sr
    c = math.cos(w)
    alpha = math.sin(w) / 2.0 * math.sqrt(2.0)
    s = 2.0 * math.sqrt(a) * alpha
    return _row(
        a * ((a + 1) - (a - 1) * c + s), 2 * a * ((a - 1) - (a + 1) * c), a * ((a + 1) - (a - 1) * c - s),
        (a + 1) + (a - 1) * c + s, -2 * ((a - 1) + (a + 1) * c), (a + 1) + (a - 1) * c - s,
    )


def high_shelf(sr: int, fc: float, db: float) -> tuple[float, ...]:
    a = 10.0 ** (db / 40.0)
    w = 2.0 * math.pi * fc / sr
    c = math.cos(w)
    alpha = math.sin(w) / 2.0 * math.sqrt(2.0)
    s = 2.0 * math.sqrt(a) * alpha
    return _row(
        a * ((a + 1) + (a - 1) * c + s), -2 * a * ((a - 1) + (a + 1) * c), a * ((a + 1) + (a - 1) * c - s),
        (a + 1) - (a - 1) * c + s, 2 * ((a - 1) - (a + 1) * c), (a + 1) - (a - 1) * c - s,
    )


def highpass(sr: int, fc: float, q: float = 0.707) -> tuple[float, ...]:
    w = 2.0 * math.pi * fc / sr
    alpha = math.sin(w) / (2.0 * q)
    c = math.cos(w)
    return _row((1 + c) / 2, -(1 + c), (1 + c) / 2, 1 + alpha, -2 * c, 1 - alpha)


def lowpass(sr: int, fc: float, q: float = 0.707) -> tuple[float, ...]:
    w = 2.0 * math.pi * fc / sr
    alpha = math.sin(w) / (2.0 * q)
    c = math.cos(w)
    return _row((1 - c) / 2, 1 - c, (1 - c) / 2, 1 + alpha, -2 * c, 1 - alpha)


@lru_cache(maxsize=64)
def _sos(sr: int, spec: tuple) -> np.ndarray:
    make = {"peak": peak, "low_shelf": low_shelf, "high_shelf": high_shelf, "highpass": highpass, "lowpass": lowpass}
    return np.array([make[name](sr, *args) for name, *args in spec], dtype=np.float64)


def apply(x: np.ndarray, sr: int, spec: tuple) -> np.ndarray:
    """Run ``x`` through ``spec``, a tuple of ``("peak", fc, q, db)``-style steps. An empty spec returns ``x``."""
    if not spec or len(x) == 0:
        return x
    return signal.sosfilt(_sos(int(sr), spec), x)


def response_db(sr: int, spec: tuple, freqs: np.ndarray) -> np.ndarray:
    """The filter's gain at ``freqs`` in dB (for tests and reports)."""
    _w, h = signal.sosfreqz(_sos(int(sr), spec), worN=np.asarray(freqs, dtype=np.float64), fs=sr)
    return 20.0 * np.log10(np.maximum(np.abs(h), 1e-9))

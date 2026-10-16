"""Preview-only polish for a live performance track (Performance + Backing).

Never applied to the dry take, pitch analysis or Mission scoring — only to the performance
track inside the combined preview, so a flute (or any solo instrument) sounds natural and
present over the accompaniment:

* high-pass at ~90 Hz (handling / room rumble),
* gentle compression (2:1 above ~-24 dBFS RMS, smooth attack / release) for an even level,
* a short, light plate-style reverb (pre-delay 18 ms, ~1.1 s tail, ~14 % wet) — space, not wash.

Headroom and clipping are handled by the mix's limiter.
"""

from __future__ import annotations

import numpy as np


def _highpass(x: np.ndarray, sr: int, hz: float = 90.0) -> np.ndarray:
    from scipy.signal import butter, sosfilt

    sos = butter(2, hz, btype="highpass", fs=sr, output="sos")
    return sosfilt(sos, x).astype(np.float32)


def _compress(x: np.ndarray, sr: int, *, threshold_db: float = -24.0, ratio: float = 2.0,
              attack_ms: float = 12.0, release_ms: float = 180.0) -> np.ndarray:
    from scipy.signal import lfilter

    if not x.size:
        return x
    power = x.astype(np.float64) ** 2
    # RMS follower (one-pole on power), then a static 2:1 curve smoothed by attack / release.
    a = np.exp(-1.0 / (sr * 0.010))
    env = np.sqrt(np.maximum(lfilter([1 - a], [1, -a], power), 1e-12))
    level_db = 20 * np.log10(env)
    over = np.maximum(0.0, level_db - threshold_db)
    target_gain_db = -over * (1.0 - 1.0 / ratio)
    att, rel = np.exp(-1.0 / (sr * attack_ms / 1000)), np.exp(-1.0 / (sr * release_ms / 1000))
    g = np.empty_like(target_gain_db)
    cur = 0.0
    for i, t in enumerate(target_gain_db[:: max(1, sr // 2000)]):  # control rate ~2 kHz
        coef = att if t < cur else rel
        cur = coef * cur + (1 - coef) * t
        g[i] = cur
    step = max(1, sr // 2000)
    g = np.repeat(g[: (len(x) + step - 1) // step], step)[: len(x)]
    makeup = (threshold_db * -(1.0 - 1.0 / ratio)) * 0.25  # modest make-up gain
    return (x * 10 ** ((g + makeup) / 20)).astype(np.float32)


def _plate(x: np.ndarray, sr: int, *, wet: float = 0.14, decay_s: float = 1.1, predelay_ms: float = 18.0) -> np.ndarray:
    """Small Schroeder-style plate: 4 parallel combs + 2 series allpasses, damped."""
    from scipy.signal import lfilter

    if not x.size:
        return x
    scale = sr / 44100.0
    pre = int(sr * predelay_ms / 1000)
    src = np.concatenate([np.zeros(pre, np.float32), x])[: len(x)]
    out = np.zeros(len(x), dtype=np.float64)
    for d in (1557, 1617, 1491, 1422):
        n = max(1, int(d * scale))
        g = 10 ** (-3.0 * n / (sr * decay_s))  # -60 dB after decay_s
        b = np.zeros(n + 1); b[n] = 1.0
        a = np.zeros(n + 1); a[0] = 1.0; a[n] = -g
        out += lfilter(b, a, src)
    out /= 4.0
    for d in (225, 556):
        n = max(1, int(d * scale)); g = 0.5
        b = np.zeros(n + 1); b[0] = -g; b[n] = 1.0
        a = np.zeros(n + 1); a[0] = 1.0; a[n] = -g
        out = lfilter(b, a, out)
    # Darker tail (one-pole low-pass ~5 kHz) so the room supports rather than hisses.
    alpha = 1.0 - np.exp(-2.0 * np.pi * 5000.0 / sr)
    out = lfilter([alpha], [1.0, alpha - 1.0], out)
    return ((1.0 - wet * 0.5) * x + wet * out).astype(np.float32)


def performance_preview_chain(x: np.ndarray, sr: int) -> np.ndarray:
    """HPF → gentle compression → light plate. Input / output: mono float32."""
    if x is None or not np.asarray(x).size:
        return x
    y = _highpass(np.asarray(x, dtype=np.float32), sr)
    y = _compress(y, sr)
    y = _plate(y, sr)
    return y


__all__ = ["performance_preview_chain"]

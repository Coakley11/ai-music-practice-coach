"""Loudness-matched master for Backing takes.

Off by default: today's master stays until ``MUSIC_BACKING_LOUDNESS=match``. Nothing here runs otherwise.

Today every take is scaled so its loudest sample sits at 0.86, so how loud a take *sounds* depends on how peaky
it is. The recorded instruments' natural attacks made the full band up to 6.6 dB quieter than today's synthesized
band in the same song. With the switch on, every full-mix take is set to one integrated loudness (ITU-R BS.1770-4,
gated), and a look-ahead peak limiter keeps every sample under the ceiling. The limiter acts only on the few peaks
above it; :data:`LAST_STATS` reports how much and how often, so its effect can be checked song by song.
"""

from __future__ import annotations

import math
import os

import numpy as np
from scipy.signal import lfilter

DEFAULT_TARGET_LUFS = -22.0
CEILING_DBFS = -1.0
LOOKAHEAD_MS = 5.0
RELEASE_MS = 80.0
_BLOCK = 32
LAST_STATS: dict[str, float] = {}


def loudness_mode() -> str:
    raw = str(os.environ.get("MUSIC_BACKING_LOUDNESS") or "").strip().lower()
    return "match" if raw in {"match", "1", "on", "true", "yes"} else ""


def target_lufs() -> float:
    try:
        return float(os.environ.get("MUSIC_BACKING_LOUDNESS_TARGET") or DEFAULT_TARGET_LUFS)
    except ValueError:
        return DEFAULT_TARGET_LUFS


def loudness_renderer_tag() -> str:
    """Part of a saved backing's identity, so a take mastered the other way is never replayed as this one."""
    if not loudness_mode():
        return ""
    return f"+lufs{target_lufs():g}c{CEILING_DBFS:g}"


def _k_weight(x: np.ndarray, sr: int) -> np.ndarray:
    """BS.1770 K-weighting: the high-shelf pre-filter, then the RLB high-pass, designed for ``sr``."""
    f0, gain_db, q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    k = math.tan(math.pi * f0 / sr)
    vh = 10 ** (gain_db / 20)
    vb = vh ** 0.4996667741545416
    a0 = 1 + k / q + k * k
    b = [(vh + vb * k / q + k * k) / a0, 2 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0]
    a = [1.0, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0]
    y = lfilter(b, a, x)
    f1, q1 = 38.13547087602444, 0.5003270373238773
    k = math.tan(math.pi * f1 / sr)
    a0 = 1 + k / q1 + k * k
    return lfilter([1.0, -2.0, 1.0], [1.0, 2 * (k * k - 1) / a0, (1 - k / q1 + k * k) / a0], y)


def integrated_lufs(x: np.ndarray, sr: int) -> float:
    """Gated integrated loudness of a mono signal (400 ms blocks, 75 % overlap, -70 LUFS and relative -10 LU gates)."""
    y = _k_weight(np.asarray(x, dtype=np.float64), sr)
    n, hop = int(0.4 * sr), int(0.1 * sr)
    if len(y) < n:
        ms = float(np.mean(y ** 2)) if len(y) else 0.0
        return -0.691 + 10 * math.log10(ms) if ms > 0 else float("-inf")
    sq = np.concatenate([[0.0], np.cumsum(y ** 2)])
    starts = np.arange(0, len(y) - n + 1, hop)
    blocks = (sq[starts + n] - sq[starts]) / n
    blocks = blocks[blocks > 0]
    if not len(blocks):
        return float("-inf")
    loud = -0.691 + 10 * np.log10(blocks)
    gated = blocks[loud > -70.0]
    if not len(gated):
        return float("-inf")
    rel = -0.691 + 10 * math.log10(float(np.mean(gated))) - 10.0
    gated = gated[(-0.691 + 10 * np.log10(gated)) > rel]
    return -0.691 + 10 * math.log10(float(np.mean(gated)))


def limit(x: np.ndarray, sr: int, ceiling: float) -> tuple[np.ndarray, dict[str, float]]:
    """Look-ahead peak limiter: every sample ends at or under ``ceiling``; signal under it is left exactly alone.

    The gain needed per 32-sample block is spread over the look-ahead on both sides (a minimum then a mean over
    it, so the gain is already down when a peak arrives and never above what any nearby sample needs), then
    recovers at the release rate.
    """
    x = np.asarray(x, dtype=np.float64)
    nb = (len(x) + _BLOCK - 1) // _BLOCK
    pad = np.zeros(nb * _BLOCK)
    pad[: len(x)] = np.abs(x)
    peak = pad.reshape(nb, _BLOCK).max(axis=1)
    need = np.minimum(1.0, ceiling / np.maximum(peak, 1e-12))
    if float(need.min()) >= 1.0:
        return x.copy(), {"max_gr_db": 0.0, "limited_pct": 0.0, "residual_samples": 0.0}
    look = max(1, int(round(LOOKAHEAD_MS * 1e-3 * sr / _BLOCK)))
    from scipy.ndimage import minimum_filter1d, uniform_filter1d

    g = minimum_filter1d(need, size=2 * (look + 1) + 1, mode="nearest")
    g = np.minimum(uniform_filter1d(g, size=2 * look + 1, mode="nearest"), need)
    rel = 1.0 - math.exp(-_BLOCK / (RELEASE_MS * 1e-3 * sr))
    out = np.empty_like(g)
    prev = 1.0
    for i, gi in enumerate(g):  # recover slowly, fall at once (the look-ahead already prepared the fall)
        prev = gi if gi < prev else min(gi, prev + (1.0 - prev) * rel)
        out[i] = prev
    centers = np.arange(nb) * _BLOCK + _BLOCK / 2.0
    gain = np.interp(np.arange(len(x)), centers, out)
    y = x * gain
    over = np.abs(y) > ceiling
    if over.any():  # interpolation edge: scale only those samples onto the ceiling
        y[over] = np.sign(y[over]) * ceiling
    return y, {
        "max_gr_db": round(float(-20 * np.log10(max(float(gain.min()), 1e-9))), 2),
        # Share of the take turned down by more than 0.5 dB (the release tail below that is inaudible).
        "limited_pct": round(float(np.mean(gain < 10 ** (-0.5 / 20)) * 100), 3),
        "residual_samples": float(np.count_nonzero(over)),
    }


def master(audio: np.ndarray, sr: int) -> tuple[np.ndarray, dict[str, float]]:
    """The full mix at the target loudness, every sample under the ceiling (two passes: the limiter takes a little)."""
    x = np.asarray(audio, dtype=np.float64)
    target, ceiling = target_lufs(), 10 ** (CEILING_DBFS / 20)
    before = integrated_lufs(x, sr)
    if not math.isfinite(before):
        LAST_STATS.clear()
        return x, {}
    gain_db = target - before
    y, st = limit(x * 10 ** (gain_db / 20), sr, ceiling)
    short = target - integrated_lufs(y, sr)
    if short > 0.2:
        gain_db += short
        y, st = limit(x * 10 ** (gain_db / 20), sr, ceiling)
    stats = {"lufs_in": round(before, 2), "gain_db": round(gain_db, 2), "lufs_out": round(integrated_lufs(y, sr), 2),
             "peak_dbfs": round(float(20 * np.log10(max(float(np.max(np.abs(y))), 1e-12))), 2), **st}
    LAST_STATS.clear()
    LAST_STATS.update(stats)
    return y, stats

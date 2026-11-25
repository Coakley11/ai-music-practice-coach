"""Backing Engine 2.0: a live band's drum balance -- drums that support the music instead of dominating it.

Off by default: ``MUSIC_BAND_BALANCE=1`` turns it on, and every take is byte-identical without it.

With it on, the recorded drum kit and the Latin percussionist play into their own drum bus. The piano, guitar,
strings and horns are levelled against exactly the same rhythm-section reference as before (bass + drums at
today's level), and only then is the drum bus shaped and placed, the way a mix engineer would:

1. A gentle high shelf (above about 5.5 kHz) calms cymbal, hi-hat and shaker sizzle, more in the softer styles.
2. A fast limiter on the drums' high band only (above 2.5 kHz) softens attacks that stick out far above that
   band's own level -- a clave click, a hi-hat or rim edge -- while everything under the threshold is untouched.
3. The drum bus is set to a per-style perceived loudness (ITU-R BS.1770, K-weighted) relative to the musical layers
   (piano, bass, guitar, horns, strings): Bossa nova softest, Samba with the most percussion energy. It is only
   ever turned DOWN to the target, never up, so a style already in balance keeps its drums.
4. Groove intensity moves the target by only a little (Light -1 LU, Heavy +0.75 LU): the density, ghost notes,
   fills and touch the performance plan already changes carry the energy, not the drums' volume.

The take is then loudness-matched as before (MUSIC_BACKING_LOUDNESS), so comparisons stay at the same loudness.
"""

from __future__ import annotations

import os

import numpy as np
from scipy import signal

_ON = {"1", "true", "yes", "on"}

# Drums + percussion against the musical layers, in LU, at Medium intensity.
TARGET_LU = {
    "Bossa nova": -12.5,
    "Ballad": -14.0,
    "Jazz swing": -10.5,
    "Latin jazz": -10.5,
    "Samba": -9.5,
    "Pop groove": -12.5,
    "Rock groove": -11.5,
    "Funk groove": -11.0,
    "Blues groove": -12.5,
}
DEFAULT_TARGET_LU = -12.0
INTENSITY_LU = {"Light": -1.0, "Medium": 0.0, "Heavy": 0.75}
MAX_CUT_DB = 9.0  # never more than this: the drums stay a band member

# High shelf on the drum bus (dB at and above SHELF_HZ).
SHELF_HZ = 5500.0
SHELF_DB = {
    "Bossa nova": -3.5, "Ballad": -3.0, "Jazz swing": -3.5, "Latin jazz": -2.5, "Samba": -5.0,
    "Pop groove": -2.0, "Rock groove": -1.5, "Funk groove": -1.5, "Blues groove": -2.5,
}
DEFAULT_SHELF_DB = -2.0

# High-band transient limiter: attacks more than this many dB above the high band's RMS are pulled in at RATIO.
SPLIT_HZ = 2500.0
SPIKE_THRESHOLD_DB = 12.0
SPIKE_RATIO = 2.5
_ATTACK_SEC = 0.0004
_LOOKAHEAD_SEC = 0.003  # the peak hold window (half of it is look-ahead)
_RELEASE_SEC = 0.045


def enabled() -> bool:
    return str(os.environ.get("MUSIC_BAND_BALANCE") or "").strip().lower() in _ON


def renderer_tag() -> str:
    """Part of the take's identity: a balanced take is never replayed as an unbalanced one, or the reverse."""
    return "+bal1" if enabled() else ""


def _lufs(x: np.ndarray, sr: int) -> float:
    import backing_loudness as _bl

    v = float(_bl.integrated_lufs(np.asarray(x, dtype=np.float64), sr))
    return v if np.isfinite(v) else -99.0


def _high_shelf(x: np.ndarray, sr: int, hz: float, db: float) -> np.ndarray:
    """RBJ high shelf (slope 1)."""
    if abs(db) < 1e-3:
        return x
    a = 10 ** (db / 40.0)
    w0 = 2 * np.pi * hz / sr
    cos, alpha = np.cos(w0), np.sin(w0) / 2 * np.sqrt(2)
    sq = 2 * np.sqrt(a) * alpha
    b = np.array([a * ((a + 1) + (a - 1) * cos + sq), -2 * a * ((a - 1) + (a + 1) * cos), a * ((a + 1) + (a - 1) * cos - sq)])
    den = np.array([(a + 1) - (a - 1) * cos + sq, 2 * ((a - 1) - (a + 1) * cos), (a + 1) - (a - 1) * cos - sq])
    return signal.lfilter(b / den[0], den / den[0], x)


def soften_spikes(x: np.ndarray, sr: int, *, threshold_db: float = SPIKE_THRESHOLD_DB, ratio: float = SPIKE_RATIO) -> np.ndarray:
    """Pull in high-band attacks that stand far above the high band's own level; leave the rest alone."""
    sos = signal.butter(2, SPLIT_HZ, "highpass", fs=sr, output="sos")
    hf = signal.sosfiltfilt(sos, x)
    low = x - hf
    rect = np.abs(hf)
    rms = float(np.sqrt(np.mean(hf ** 2)))
    if rms <= 1e-12:
        return x
    from scipy.ndimage import maximum_filter1d

    # A centred peak hold looks ahead by half its width, so the gain is already down when a click arrives.
    hold = maximum_filter1d(rect, size=max(3, int(_LOOKAHEAD_SEC * sr)), mode="nearest")
    a_rel = np.exp(-1.0 / (_RELEASE_SEC * sr))
    env = np.maximum(hold, signal.lfilter([1 - a_rel], [1, -a_rel], hold))
    thr = rms * 10 ** (threshold_db / 20.0)
    over = env > thr
    gain = np.ones_like(env)
    gain[over] = (thr / env[over]) ** (1.0 - 1.0 / ratio)
    a_s = np.exp(-1.0 / (_ATTACK_SEC * sr))
    gain = signal.filtfilt([1 - a_s], [1, -a_s], gain)  # smooth without lag: no zipper, no late attack
    return low + hf * np.minimum(gain, 1.0)


def place_drums(drum_bus: np.ndarray, music: np.ndarray, sr: int, *, style: str, intensity: str = "Medium") -> tuple[np.ndarray, dict]:
    """The shaped drum bus at its target loudness against ``music``; returns (bus, stats)."""
    x = np.asarray(drum_bus, dtype=np.float64)
    stats = {"drums_lu_before": None, "drums_lu_after": None, "drum_gain_db": 0.0}
    if not np.any(x):
        return x, stats
    x = _high_shelf(x, sr, SHELF_HZ, SHELF_DB.get(style, DEFAULT_SHELF_DB))
    x = soften_spikes(x, sr)
    l_music = _lufs(music, sr)
    if l_music <= -90:
        return x, stats
    before = _lufs(x, sr) - l_music
    target = TARGET_LU.get(style, DEFAULT_TARGET_LU) + INTENSITY_LU.get(str(intensity), 0.0)
    cut_db = float(np.clip(target - before, -MAX_CUT_DB, 0.0))
    x = x * 10 ** (cut_db / 20.0)
    stats.update(drums_lu_before=round(before, 2), drums_lu_after=round(before + cut_db, 2), drum_gain_db=round(cut_db, 2))
    return x, stats

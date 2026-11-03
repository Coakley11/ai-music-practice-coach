"""Optional, non-destructive polish applied to a Multitrack MIX.

Nothing here edits a recorded layer: the saved takes are untouched and the effect is applied only to
the audio produced at mix time, so turning it off and mixing again returns the dry sound exactly.

The reverb is a small Schroeder network (parallel combs into series all-passes) built with numpy only,
so it adds no dependency. It is a *finishing* touch - it cannot restore notes the capture never
recorded, and it is off by default.
"""

from __future__ import annotations

import numpy as np

REVERB_ENABLED_KEY = "mt_mix_reverb_on"
REVERB_AMOUNT_KEY = "mt_mix_reverb_amount"

# Classic Schroeder constants, in seconds, scaled for a small room.
_COMB_DELAYS = (0.0297, 0.0371, 0.0411, 0.0437)
_COMB_FEEDBACK = (0.805, 0.827, 0.783, 0.764)
_ALLPASS_DELAYS = (0.005, 0.0017)
_ALLPASS_GAIN = 0.7


def _comb(x: np.ndarray, delay_samples: int, feedback: float) -> np.ndarray:
    if delay_samples <= 0 or delay_samples >= len(x):
        return np.zeros_like(x)
    out = np.copy(x)
    for i in range(delay_samples, len(out)):
        out[i] += feedback * out[i - delay_samples]
    return out


def _allpass(x: np.ndarray, delay_samples: int, gain: float) -> np.ndarray:
    if delay_samples <= 0 or delay_samples >= len(x):
        return x
    out = np.copy(x)
    for i in range(delay_samples, len(out)):
        out[i] = -gain * x[i] + x[i - delay_samples] + gain * out[i - delay_samples]
    return out


def reverb_tail(y: np.ndarray, sr: int = 44100) -> np.ndarray:
    """The wet (reverberant) signal for ``y`` — same length, same sample rate."""
    x = np.asarray(y, dtype=np.float64)
    if x.size == 0:
        return x.astype(np.float32)
    wet = np.zeros_like(x)
    for delay, fb in zip(_COMB_DELAYS, _COMB_FEEDBACK):
        wet += _comb(x, int(delay * sr), fb)
    wet /= max(1, len(_COMB_DELAYS))
    for delay in _ALLPASS_DELAYS:
        wet = _allpass(wet, int(delay * sr), _ALLPASS_GAIN)
    return wet.astype(np.float32)


def apply_reverb(y: np.ndarray, *, sr: int = 44100, amount: float = 0.0) -> np.ndarray:
    """Return ``y`` with ``amount`` (0..1) of reverb blended in; ``amount <= 0`` returns it unchanged.

    The dry signal is never removed - at the maximum setting the wet share is still only a third - so
    the recorded notes stay audible and in place. The result keeps the input's peak level, so adding
    reverb cannot make the mix clip.
    """
    x = np.asarray(y, dtype=np.float32)
    try:
        amt = float(amount)
    except (TypeError, ValueError):
        return x
    if x.size == 0 or amt <= 0:
        return x
    amt = min(1.0, amt)
    wet_share = 0.33 * amt
    before = float(np.max(np.abs(x))) if x.size else 0.0
    out = (1.0 - wet_share) * x.astype(np.float64) + wet_share * reverb_tail(x, sr).astype(np.float64)
    after = float(np.max(np.abs(out))) if out.size else 0.0
    if after > 0 and before > 0:
        out = out * (before / after)
    return out.astype(np.float32)


def mix_reverb_amount(session_state: dict) -> float:
    """How much reverb this session asks for (0.0 when the switch is off)."""
    if not bool(session_state.get(REVERB_ENABLED_KEY)):
        return 0.0
    try:
        return max(0.0, min(1.0, float(session_state.get(REVERB_AMOUNT_KEY, 0.25))))
    except (TypeError, ValueError):
        return 0.0


__all__ = [
    "REVERB_AMOUNT_KEY",
    "REVERB_ENABLED_KEY",
    "apply_reverb",
    "mix_reverb_amount",
    "reverb_tail",
]

"""Upright bass voice for the generated Backing track (numpy only).

Off by default: today's Jazz bass plays unless ``MUSIC_UPRIGHT_BASS`` is set, to ``recorded``
for the 1958 Rubner double bass in ``assets/instruments/double_bass`` or to ``model`` for the
fallback below.

The fallback is a plucked-string model rather than an oscillator: the pluck point decides which
partials speak, the instrument's body colours them, the upper partials die first,
the string starts slightly sharp and settles, and each note opens with a soft
finger noise and a low knock from the body.

As with the piano, a reference tone is synthesized every few semitones and the
pitches between are resampled from it, so a song's many repeated notes cost a
copy-and-add. ``backing_audio`` decides *when* notes play; this module decides
*how* they sound.
"""

from __future__ import annotations

import os
import pathlib
from functools import lru_cache

import numpy as np

from backing_sampled_instrument import SampledInstrument

DOUBLE_BASS_PACK = pathlib.Path(__file__).resolve().parent / "assets" / "instruments" / "double_bass"
# Brings the recordings to the level the Jazz balance was set with.
RECORDED_TRIM = 0.85

_VEL_BUCKETS = 3
_FREE_SEC = 2.6
_ENV_STEP = 32
_REF_STEP = 3
_RELEASE_SEC = 0.055


def upright_mode() -> str:
    """"" (today's bass), "recorded" or "model". A missing pack falls back to the model."""
    raw = str(os.environ.get("MUSIC_UPRIGHT_BASS") or "").strip().lower()
    if raw in {"", "0", "off", "false", "no"}:
        return ""
    if raw == "model" or not (DOUBLE_BASS_PACK / "manifest.json").is_file():
        return "model"
    return "recorded"


def bass_renderer_tag() -> str:
    """Part of saved audio's signature, so takes from another bass are never replayed as this one."""
    mode = upright_mode()
    if mode == "recorded":
        return f"+upright-recorded-bus{LOW_SHELF_DB:g}_{HIGH_SHELF_DB:g}_{BUS_TRIM:g}_k{KEYS_LIFT:g}"
    return f"+upright-{mode}" if mode else ""


@lru_cache(maxsize=1)
def _double_bass() -> SampledInstrument:
    return SampledInstrument(DOUBLE_BASS_PACK)


def _freq(midi: float) -> float:
    return 440.0 * (2.0 ** ((float(midi) - 69.0) / 12.0))


def _vel_bucket(velocity: float) -> int:
    v = min(1.0, max(0.0, float(velocity)))
    return min(_VEL_BUCKETS - 1, int(v * _VEL_BUCKETS))


def _body_gain(f: float) -> float:
    """The instrument's body: air and top-plate resonances, a little nasal mid, soft highs."""

    def peak(fc: float, q: float) -> float:
        return 1.0 / (1.0 + ((f - fc) / (fc / q)) ** 2)

    shape = 0.50 + 0.55 * peak(98.0, 2.5) + 0.80 * peak(205.0, 2.6) + 0.42 * peak(420.0, 3.0) + 0.16 * peak(950.0, 3.0)
    return shape / (1.0 + (f / 1900.0) ** 2)


@lru_cache(maxsize=32)
def _upright_ref(midi: int, vel_bucket: int, sr: int) -> np.ndarray:
    """Reference plucked, undamped note, peak-normalised (float32)."""
    f0 = _freq(midi)
    v = (vel_bucket + 0.5) / _VEL_BUCKETS
    n = int(_FREE_SEC * sr)
    t = np.arange(n, dtype=np.float64) / sr
    grid = np.arange(0, n + _ENV_STEP, _ENV_STEP, dtype=np.float64)
    tg = grid / sr

    # The string is stretched by the pluck and settles a few cents flat of where it started.
    settle_tau = 0.035
    settle = (0.0025 + 0.0055 * v) * settle_tau * (1.0 - np.exp(-t / settle_tau))
    z1 = np.exp(2j * np.pi * f0 * (t + settle))

    t60 = float(np.clip(4.6 * 2.0 ** (-(midi - 28) / 22.0), 1.5, 4.6))
    tau_prompt, tau_after = t60 / 24.0, t60 / 6.9
    pluck_point = 0.19
    inharm = 0.00012
    tilt = 1.15 - 0.30 * v  # a firmer pull brings the upper partials forward

    zk = np.ones(n, dtype=np.complex128)
    acc = np.zeros(n, dtype=np.complex128)
    max_k = int(min(16, (0.36 * sr) / f0))
    for k in range(1, max(2, max_k) + 1):
        fk = k * f0 * np.sqrt(1.0 + inharm * k * k)
        if fk >= 0.36 * sr:
            break
        zk = zk * z1
        ak = abs(np.sin(np.pi * k * pluck_point)) / (k**tilt) * _body_gain(fk)
        speed = 1.0 + 0.62 * (k - 1) * (0.7 + 0.5 * v)
        env = 0.46 * np.exp(-tg * speed / tau_prompt) + 0.54 * np.exp(-tg * speed / tau_after)
        slow = np.exp(2j * np.pi * (fk - k * f0) * tg + 0.41j * k)
        x = np.arange(n, dtype=np.float64)
        shaped = ak * env * slow
        acc += zk * (np.interp(x, grid, shaped.real) + 1j * np.interp(x, grid, shaped.imag))
    sig = acc.imag / (float(np.max(np.abs(acc.imag))) or 1.0)

    # Finger on the string: a few ms of soft noise, firmer pulls louder.
    rng = np.random.default_rng(midi * 11 + vel_bucket)
    finger_n = int(0.018 * sr)
    noise = np.convolve(rng.standard_normal(finger_n), np.ones(9) / 9.0, mode="same")
    noise *= np.exp(-np.arange(finger_n) / (0.0045 * sr))
    sig[:finger_n] += (0.05 + 0.09 * v) * noise / (float(np.max(np.abs(noise))) or 1.0)

    # The low knock of the body answering the pluck.
    knock_n = int(0.07 * sr)
    sig[:knock_n] += (
        (0.07 + 0.08 * v) * np.sin(2.0 * np.pi * 92.0 * t[:knock_n]) * np.exp(-t[:knock_n] / 0.022)
    )

    # A soft finger speaks in a few ms, no click.
    attack_n = max(2, int((0.0065 - 0.0035 * v) * sr))
    sig[:attack_n] *= 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, attack_n))
    fade_n = int(0.08 * sr)
    sig[-fade_n:] *= np.linspace(1.0, 0.0, fade_n)
    return (sig / (float(np.max(np.abs(sig))) or 1.0)).astype(np.float32)


@lru_cache(maxsize=160)
def _upright_free(midi: int, vel_bucket: int, sr: int) -> np.ndarray:
    ref = int(round(midi / _REF_STEP)) * _REF_STEP
    tone = _upright_ref(ref, vel_bucket, sr)
    if ref == midi:
        return tone
    ratio = 2.0 ** ((midi - ref) / 12.0)
    pos = np.arange(int(len(tone) / ratio), dtype=np.float64) * ratio
    return np.interp(pos, np.arange(len(tone), dtype=np.float64), tone).astype(np.float32)


@lru_cache(maxsize=4)
def _release_curve(sr: int) -> np.ndarray:
    tau = _RELEASE_SEC / 3.0
    return np.exp(-np.arange(int(_RELEASE_SEC * sr), dtype=np.float64) / (tau * sr)).astype(np.float32)


# The recorded upright on its own bus, finished once before the mix is balanced: the recordings carry
# a real bass's harmonics and finger noise, and at their trimmed level the Jazz band lost most of its low
# end (low-band share 0.225 today -> 0.077). A low shelf restores the fundamental; a gentle high shelf
# keeps the finger noise from brightening the band. Tunable for listening rounds via the environment.
LOW_SHELF_HZ = float(os.environ.get("MUSIC_UPRIGHT_LOW_SHELF_HZ") or 110.0)
LOW_SHELF_DB = float(os.environ.get("MUSIC_UPRIGHT_LOW_SHELF_DB") or 8.0)
HIGH_SHELF_HZ = float(os.environ.get("MUSIC_UPRIGHT_HIGH_SHELF_HZ") or 2500.0)
HIGH_SHELF_DB = float(os.environ.get("MUSIC_UPRIGHT_HIGH_SHELF_DB") or -3.0)
BUS_TRIM = float(os.environ.get("MUSIC_UPRIGHT_BUS_TRIM") or 2.0)
# The piano's level is set relative to the rhythm section (bass + drums), so a quieter upright alone would pull
# the piano down with it. When the recorded upright plays, the Jazz piano target is lifted by this factor so
# the trio balances (bass under the piano and drums). Tunable for listening rounds.
KEYS_LIFT = float(os.environ.get("MUSIC_UPRIGHT_KEYS_LIFT") or 1.0)


def _shelf(x: np.ndarray, sr: int, f0: float, gain_db: float, high: bool) -> np.ndarray:
    """RBJ cookbook shelf (slope 1)."""
    if abs(gain_db) < 1e-6:
        return x
    from scipy.signal import lfilter

    a_ = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * f0 / sr
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / 2.0 * np.sqrt(2.0)
    k = 2.0 * np.sqrt(a_) * alpha
    if high:
        b = [a_ * ((a_ + 1) + (a_ - 1) * cw + k), -2 * a_ * ((a_ - 1) + (a_ + 1) * cw), a_ * ((a_ + 1) + (a_ - 1) * cw - k)]
        a = [(a_ + 1) - (a_ - 1) * cw + k, 2 * ((a_ - 1) - (a_ + 1) * cw), (a_ + 1) - (a_ - 1) * cw - k]
    else:
        b = [a_ * ((a_ + 1) - (a_ - 1) * cw + k), 2 * a_ * ((a_ - 1) - (a_ + 1) * cw), a_ * ((a_ + 1) - (a_ - 1) * cw - k)]
        a = [(a_ + 1) + (a_ - 1) * cw + k, -2 * ((a_ - 1) + (a_ + 1) * cw), (a_ + 1) + (a_ - 1) * cw - k]
    return lfilter(np.array(b) / a[0], np.array(a) / a[0], x)


def uses_own_bus() -> bool:
    return upright_mode() == "recorded"


def finish_upright_bus(bus: np.ndarray, sr: int) -> np.ndarray:
    """The recorded upright's bus, shaped for the band (low shelf up, finger noise down)."""
    out = _shelf(bus.astype(np.float64), sr, LOW_SHELF_HZ, LOW_SHELF_DB, high=False)
    out = _shelf(out, sr, HIGH_SHELF_HZ, HIGH_SHELF_DB, high=True)
    return out * BUS_TRIM


def add_upright_note(
    bus: np.ndarray,
    sr: int,
    start_sec: float,
    held_sec: float,
    midi: int,
    gain: float,
    velocity: float,
    *,
    seed: str = "",
    avoid: dict | None = None,
) -> None:
    """Mix one note into ``bus``, stopped by the finger at ``held_sec``."""
    if gain <= 0.0:
        return
    if upright_mode() == "recorded":
        _double_bass().add_note(
            bus, sr, start_sec, held_sec, midi, gain * RECORDED_TRIM, velocity,
            seed or f"{midi}:{start_sec:.3f}", avoid,
        )
        return
    start = int(max(0.0, start_sec) * sr)
    if start >= len(bus):
        return
    free = _upright_free(int(midi), _vel_bucket(velocity), int(sr))
    release = _release_curve(int(sr))
    held_n = max(1, int(max(0.02, held_sec) * sr))
    if held_n >= len(free):
        seg = free
    else:
        length = min(len(free), held_n + len(release))
        seg = free[:length].copy()
        seg[held_n:] *= release[: length - held_n]
    end = min(len(bus), start + len(seg))
    bus[start:end] += seg[: end - start] * gain

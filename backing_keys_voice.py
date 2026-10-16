"""Piano and strings voices for the generated Backing track (numpy only).

Both voices are synthesized here -- no samples, SoundFonts or third-party
assets. Each pitch is rendered once per render process and cached; a played
note is a slice of that cached tone shaped at use time (damper for the
piano, bow attack/release for strings), so a song's many repeated chord hits
cost a copy-and-add rather than a re-synthesis.

Arrangement helpers (voice leading, velocity shaping, per-style strings
voicing) live here too: ``backing_audio`` decides *when* notes play, this
module decides *how* they sound.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

import numpy as np

# Timbre buckets (brightness / decay speed). Loudness stays continuous.
_VEL_BUCKETS = 4
_PIANO_FREE_SEC = 1.8
_STRINGS_FREE_SEC = 6.0
_ENV_STEP = 32  # envelope samples are computed on a coarse grid then interpolated

# Comp register: above the bass line, below the vocal/lead range.
PIANO_LOW = 52   # E3
PIANO_HIGH = 81  # A5


def _freq(midi: float) -> float:
    return 440.0 * (2.0 ** ((float(midi) - 69.0) / 12.0))


def _vel_bucket(velocity: float) -> int:
    v = min(1.0, max(0.0, float(velocity)))
    return min(_VEL_BUCKETS - 1, int(v * _VEL_BUCKETS))


# ---------------------------------------------------------------------------
# Piano
# ---------------------------------------------------------------------------


def _interp_complex(grid: np.ndarray, vals: np.ndarray, n: int) -> np.ndarray:
    x = np.arange(n, dtype=np.float64)
    return np.interp(x, grid, vals.real) + 1j * np.interp(x, grid, vals.imag)


@lru_cache(maxsize=64)
def _piano_ref(midi: int, vel_bucket: int, sr: int) -> np.ndarray:
    """Reference struck, undamped piano note, peak-normalised (float32).

    A struck-string model rather than a sustained oscillator: slightly
    stretched (inharmonic) partials, a two-stage decay in which the upper
    partials die first, a detuned second string on the low partials (the slow
    beating of a real unison) and a short felt-hammer transient.

    Harmonics come from powers of one complex rotation; everything that only
    changes slowly per partial (decay, inharmonic stretch, unison beating) is
    computed on a coarse grid -- far cheaper than a sine per partial.
    """
    f0 = _freq(midi)
    v = (vel_bucket + 0.5) / _VEL_BUCKETS
    n = int(_PIANO_FREE_SEC * sr)
    t = np.arange(n, dtype=np.float64) / sr
    grid = np.arange(0, n + _ENV_STEP, _ENV_STEP, dtype=np.float64)
    tg = grid / sr
    t60 = float(np.clip(7.5 * 2.0 ** (-(midi - 48) / 15.0), 1.1, 9.0))
    tau_prompt, tau_after = t60 / 30.0, t60 / 6.9
    inharm = 0.00008 * 2.0 ** ((midi - 60) / 20.0)
    brightness = 1.85 - 0.75 * v          # harder strike -> stronger upper partials
    beat = 2.0 ** (1.1 / 1200.0) - 1.0      # second unison string, ~1 cent sharp
    z1 = np.exp(2j * np.pi * f0 * t)
    zk = np.ones(n, dtype=np.complex128)
    acc = np.zeros(n, dtype=np.complex128)
    norm = 0.0
    max_k = int(min(9, (0.36 * sr) / f0))
    for k in range(1, max(2, max_k) + 1):
        fk = k * f0 * np.sqrt(1.0 + inharm * k * k)
        if fk >= 0.36 * sr:
            break
        zk = zk * z1
        ak = 1.0 / (k ** brightness)
        speed = 1.0 + 0.5 * (k - 1) * (0.55 + 0.7 * v)
        env = 0.62 * np.exp(-tg * speed / tau_prompt) + 0.38 * np.exp(-tg * speed / tau_after)
        slow = np.exp(2j * np.pi * (fk - k * f0) * tg + 0.37j * k)
        if k <= 3:
            slow = slow * (1.0 + 0.55 * np.exp(2j * np.pi * fk * beat * tg + 0.73j * k))
            norm += 0.55 * ak
        acc += zk * _interp_complex(grid, ak * env * slow, n)
        norm += ak
    sig = acc.imag / max(norm, 1e-9)

    # Felt hammer: a few ms of soft, low-passed noise, louder when struck hard.
    hammer_n = int(0.012 * sr)
    rng = np.random.default_rng(midi * 7 + vel_bucket)
    noise = np.convolve(rng.standard_normal(hammer_n), np.ones(6) / 6.0, mode="same")
    noise *= np.exp(-np.arange(hammer_n) / (0.0025 * sr))
    sig[:hammer_n] += (0.05 + 0.08 * v) * noise / (np.max(np.abs(noise)) + 1e-9)

    # Attack: ~2-4 ms (softer strikes speak slightly slower).
    attack_n = max(2, int((0.0045 - 0.0025 * v) * sr))
    sig[:attack_n] *= 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, attack_n))
    peak = float(np.max(np.abs(sig))) or 1.0
    return (sig / peak).astype(np.float32)


@lru_cache(maxsize=96)
def _damper(midi: int, sr: int) -> np.ndarray:
    """Key-release curve: the felt damper closes the string over ~70-120 ms."""
    tau = (0.07 if midi >= 60 else 0.11) / 3.0
    n = int(tau * 3.0 * 4.0 * sr)
    return np.exp(-np.arange(n, dtype=np.float64) / (tau * sr)).astype(np.float32)


def add_piano_note(
    bus: np.ndarray,
    sr: int,
    start_sec: float,
    held_sec: float,
    midi: int,
    gain: float,
    velocity: float,
) -> None:
    """Mix one piano note into ``bus``: cached tone, damped at key release."""
    if gain <= 0.0:
        return
    start = int(max(0.0, start_sec) * sr)
    if start >= len(bus):
        return
    free = _piano_free(int(midi), _vel_bucket(velocity), int(sr))
    damper = _damper(int(midi), int(sr))
    held_n = max(1, int(max(0.02, held_sec) * sr))
    if held_n >= len(free):
        seg = free
    else:
        length = min(len(free), held_n + len(damper))
        seg = free[:length].copy()
        seg[held_n:] *= damper[: length - held_n]
    end = min(len(bus), start + len(seg))
    bus[start:end] += seg[: end - start] * gain


# Multisampling: synthesize a reference tone every _REF_STEP semitones and
# derive each pitch by resampling the nearest one (at most +-3 semitones), the
# way a sampler maps a few recorded notes across the keyboard. The expensive
# synthesis then runs a handful of times per process, not once per pitch.
_REF_STEP = 6


def _ref_midi(midi: int) -> int:
    return int(round(midi / _REF_STEP)) * _REF_STEP


def _resample(ref: np.ndarray, semitones: float) -> np.ndarray:
    if abs(semitones) < 1e-9:
        return ref
    ratio = 2.0 ** (semitones / 12.0)
    out_n = int(len(ref) / ratio)
    pos = np.arange(out_n, dtype=np.float64) * ratio
    return np.interp(pos, np.arange(len(ref), dtype=np.float64), ref).astype(np.float32)


@lru_cache(maxsize=256)
def _piano_free(midi: int, vel_bucket: int, sr: int) -> np.ndarray:
    ref = _ref_midi(midi)
    return _resample(_piano_ref(ref, vel_bucket, sr), midi - ref)


@lru_cache(maxsize=64)
def _string_free(midi: int, sr: int) -> np.ndarray:
    ref = _ref_midi(midi)
    return _resample(_string_ref(ref, sr), midi - ref)


# ---------------------------------------------------------------------------
# Voice leading and velocity
# ---------------------------------------------------------------------------


def _candidates(voicing: Sequence[int], low: int, high: int) -> list[list[int]]:
    """Inversions x octave shifts of ``voicing`` that fit ``[low, high]``."""
    base = sorted(int(n) for n in voicing)
    out: list[list[int]] = []
    for rot in range(len(base)):
        inv = base[rot:] + [n + 12 for n in base[:rot]]
        # Every octave that lands in the window: a voicing can arrive several
        # octaves out (Bossa upper structures reached C8), and a +-2 octave
        # search then fell back to the raw, unplayable register.
        for shift in range(-72, 73, 12):
            cand = [n + shift for n in inv]
            if cand[0] >= low and cand[-1] <= high:
                out.append(cand)
    return out


def lead_voicing(
    voicing: Sequence[int],
    previous: Sequence[int] | None,
    *,
    low: int = PIANO_LOW,
    high: int = PIANO_HIGH,
) -> list[int]:
    """Place ``voicing`` at the inversion/octave nearest the previous chord.

    Keeps the comp in one register (C -> Am -> F -> G moves by steps, not
    leaps) and inside ``[low, high]`` so it never muddies the bass. Wide
    (open/shell) voicings keep their spacing and only move by octaves.
    """
    notes = sorted(int(n) for n in voicing)
    if not notes:
        return []
    if notes[-1] - notes[0] > 12:
        cands = [
            [n + s for n in notes]
            for s in range(-72, 73, 12)
            if notes[0] + s >= low - 5 and notes[-1] + s <= high + 3
        ] or [notes]
    else:
        cands = _candidates(notes, low, high) or [notes]
    if not previous:
        centre = (low + high) / 2.0 - 3.0
        return min(cands, key=lambda c: abs(sum(c) / len(c) - centre))
    prev = sorted(int(n) for n in previous)

    def cost(c: list[int]) -> float:
        move = abs(c[-1] - prev[-1]) + 0.6 * abs(c[0] - prev[0])
        drift = abs(sum(c) / len(c) - sum(prev) / len(prev))
        return move + 0.5 * drift

    return min(cands, key=cost)


def _unit_noise(*keys: int) -> float:
    """Deterministic value in [-1, 1] for one hit (no RNG state, no drift)."""
    h = 0
    for k in keys:
        h = (h * 1_000_003 + (int(k) & 0xFFFFFFFF)) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0x5BD1E995) & 0xFFFFFFFF
    h ^= h >> 15
    return (h / 0xFFFFFFFF) * 2.0 - 1.0


def hit_velocity(beat: float, *, seed: int, pulses_per_bar: int = 4) -> float:
    """Musical velocity (0..1) for a comp hit at ``beat`` within the bar.

    Downbeat strongest, the mid-bar beat next, other beats a touch softer,
    off-beats lighter, plus a small deterministic variation so repeated
    chords never sound identical.
    """
    b = float(beat)
    if abs(b) < 1e-6:
        accent = 0.86
    elif abs(b - round(b)) < 1e-6:
        accent = 0.74 if int(round(b)) == pulses_per_bar // 2 else 0.70
    else:
        accent = 0.62
    return float(np.clip(accent + 0.05 * _unit_noise(seed, int(b * 8)), 0.25, 1.0))


def voice_gains(voicing: Sequence[int]) -> list[float]:
    """Balance inside a chord: the top voice sings, inner voices recede."""
    size = len(voicing)
    if size <= 1:
        return [1.0] * size
    order = sorted(range(size), key=lambda i: voicing[i])
    out = [0.86] * size
    out[order[0]] = 0.96
    out[order[-1]] = 1.12
    return out


# ---------------------------------------------------------------------------
# Strings
# ---------------------------------------------------------------------------

# Style -> (level, register low, register high, voices). Restrained where the
# groove needs space; a soft pad where the style wants one.
_STRINGS_STYLE = {
    "Ballad": (1.00, 55, 79, 4),
    "Jewish ballad": (0.95, 55, 79, 4),
    "Pop groove": (0.78, 55, 79, 4),
    "Pop": (0.78, 55, 79, 4),
    "Rock groove": (0.55, 52, 76, 3),
    "Blues groove": (0.48, 55, 76, 3),
    "Bossa nova": (0.45, 60, 81, 3),
    "Jazz swing": (0.36, 62, 84, 3),
    "Funk groove": (0.30, 60, 81, 3),
    "Jewish groove": (0.60, 55, 79, 3),
    "Jewish hora": (0.45, 57, 79, 3),
    "Klezmer groove": (0.45, 57, 79, 3),
}


def strings_style(style: str) -> tuple[float, int, int, int]:
    return _STRINGS_STYLE.get(str(style or ""), (0.70, 55, 79, 4))


@lru_cache(maxsize=16)
def _string_ref(midi: int, sr: int) -> np.ndarray:
    """Reference sustained ensemble-strings tone (no attack/release; float32).

    Three detuned players of a band-limited bowed-string tone (saw-like
    partials with softened highs) and vibrato that fades in after the bow
    attack. Detune and vibrato only change slowly, so they ride on a coarse
    grid on top of one complex rotation per harmonic.
    """
    f0 = _freq(midi)
    n = int(_STRINGS_FREE_SEC * sr)
    t = np.arange(n, dtype=np.float64) / sr
    grid = np.arange(0, n + _ENV_STEP, _ENV_STEP, dtype=np.float64)
    tg = grid / sr
    vib_depth = (2.0 ** (5.0 / 1200.0)) - 1.0           # ~5 cents
    vib_fade = np.clip((tg - 0.3) / 0.6, 0.0, 1.0)
    # Per player: slow phase offset (detune + integrated vibrato) relative to f0.
    slow_players = []
    for player, cents in enumerate((-7.0, 0.0, 6.0)):
        fp = f0 * 2.0 ** (cents / 1200.0)
        rate = 5.3 + 0.17 * player
        vib = vib_depth * vib_fade * np.sin(2.0 * np.pi * rate * tg + player)
        vib_int = np.concatenate(([0.0], np.cumsum(vib[:-1] * np.diff(tg))))
        phase = 2.0 * np.pi * ((fp - f0) * tg + fp * vib_int) + 0.9 * player
        slow_players.append(np.exp(1j * phase))
    z1 = np.exp(2j * np.pi * f0 * t)
    zk = np.ones(n, dtype=np.complex128)
    acc = np.zeros(n, dtype=np.complex128)
    norm = 0.0
    max_k = int(min(6, (0.36 * sr) / f0))
    for k in range(1, max(2, max_k) + 1):
        if k * f0 >= 0.36 * sr:
            break
        zk = zk * z1
        ak = 1.0 / (k ** (1.0 if k <= 3 else 1.7))
        slow = sum(sp ** k * np.exp(0.31j * k * i) for i, sp in enumerate(slow_players))
        acc += zk * _interp_complex(grid, ak * slow, n)
        norm += 3.0 * ak
    sig = acc.imag / max(norm, 1e-9)
    peak = float(np.max(np.abs(sig))) or 1.0
    return (sig / peak).astype(np.float32)


@lru_cache(maxsize=64)
def _string_env(held_ms: int, sr: int) -> np.ndarray:
    """Bow envelope: slow attack, gentle swell, release overlapping the next chord."""
    held = max(0.15, held_ms / 1000.0)
    attack = min(0.42, 0.35 * held + 0.08)
    release = 0.38
    n = int((held + release) * sr)
    t = np.arange(n, dtype=np.float64) / sr
    env = np.ones(n, dtype=np.float64)
    a_n = min(n, int(attack * sr))
    if a_n > 1:
        env[:a_n] = 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, a_n))
    r_start = min(n, int(held * sr))
    if r_start < n:
        env[r_start:] *= 0.5 + 0.5 * np.cos(np.linspace(0.0, np.pi, n - r_start))
    env *= 0.88 + 0.12 * np.sin(np.clip(t / held, 0.0, 1.0) * np.pi)
    return env.astype(np.float32)


def strings_voicing(chord_tones: Sequence[int], previous: Sequence[int] | None, style: str) -> list[int]:
    """Close, voice-led string voicing of the chord in the style's register."""
    _level, low, high, voices = strings_style(style)
    pcs: list[int] = []
    for n in chord_tones:
        pc = int(n) % 12
        if pc not in pcs:
            pcs.append(pc)
    if not pcs:
        return []
    chosen = pcs[: max(2, min(voices, len(pcs)))]
    if len(pcs) >= 4 and voices == 3:
        chosen = [pcs[0], pcs[1], pcs[3]]      # root, third, seventh -- drop the fifth
    base = sorted(low + ((pc - low) % 12) for pc in chosen)
    return lead_voicing(base, previous, low=low, high=high)


def add_string_note(
    bus: np.ndarray,
    sr: int,
    start_sec: float,
    held_sec: float,
    midi: int,
    gain: float,
) -> None:
    """Mix one bowed string note into ``bus`` (held, then released)."""
    if gain <= 0.0:
        return
    start = int(max(0.0, start_sec) * sr)
    if start >= len(bus):
        return
    held_ms = max(150, min(int(_STRINGS_FREE_SEC * 1000) - 400, int(round(held_sec * 20.0)) * 50))
    env = _string_env(held_ms, int(sr))
    tone = _string_free(int(midi), int(sr))
    length = min(len(env), len(tone), len(bus) - start)
    bus[start : start + length] += tone[:length] * env[:length] * gain


def clear_voice_caches() -> None:
    for fn in (_piano_ref, _piano_free, _damper, _string_ref, _string_free, _string_env):
        fn.cache_clear()

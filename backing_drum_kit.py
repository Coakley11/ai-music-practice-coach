"""The improved drum kit and the style-aware drummer built on it.

Off by default: today's drum sound stays until ``MUSIC_DRUM_KIT_V2=1``. Nothing here runs otherwise.

The kit replaces the sound of each hit and keeps its level: every voice is scaled to the energy the
current voice has at the same volume, so the drums sit where they sit today. The drummer adds a few
notes per bar, and each style has its own vocabulary:

* Funk: ghost notes that move, kick anticipations, an open hat, a tom fill into the chorus.
* Pop: stays simple. One tom pickup into a chorus, a rare open hat, no ghost notes.
* Rock: toms come from its own fill; an open hat and an extra kick lift the chorus. No ghost notes.
* Jazz: no backbeat, toms or crashes. Hi-hat foot on 2 and 4, quiet snare comping at phrase ends.
* Bossa: the clave pattern stays exactly as written. Only the sound of the kit changes.
* Other styles: the new sound, with no added notes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
from scipy import signal

# Energy of each current voice at volume 1 (sum of squares / sample rate). tests/test_drum_kit.py checks these.
_E_KICK = 0.0078
_E_SNARE = 0.0165
_E_RIDE = 0.0216
_E_RIM = 0.0073
_E_TOM = 0.0659
_NOISE_ENERGY_PER_SEC = 0.335  # a noise hit with a linear fade, per second of its length
_CRASH_TRIM = 0.8
# The volumes the engine uses for a full-strength hit, which set how bright a hit sounds.
_FULL = {"kick": 0.095, "snare": 0.040, "hat": 0.012, "crash": 0.034, "ride": 0.185, "rim": 0.028, "tom": 0.060}
_METAL = (205.3, 304.4, 369.6, 522.7, 540.0, 800.0)  # six square waves, the classic cymbal cluster

_TUNING: dict[str, dict[str, float]] = {
    "default": {"kick_hz": 48.0, "kick_sweep": 72.0, "kick_decay": 9.0, "snare_hz": 185.0, "snare_decay": 24.0, "wires": 0.75, "hat_lo": 6500.0},
    "Rock groove": {"beater": 1.8, "kick_hz": 50.0, "kick_sweep": 88.0, "kick_decay": 8.0, "snare_hz": 175.0, "snare_decay": 18.0, "wires": 0.9, "hat_lo": 6000.0},
    "Funk groove": {"kick_hz": 50.0, "kick_sweep": 80.0, "kick_decay": 12.0, "snare_hz": 215.0, "snare_decay": 30.0, "wires": 0.8, "hat_lo": 7000.0},
    "Jazz swing": {"kick_hz": 58.0, "kick_sweep": 40.0, "kick_decay": 10.0, "snare_hz": 240.0, "snare_decay": 26.0, "wires": 0.45, "hat_lo": 6000.0},
    "Bossa nova": {"kick_hz": 56.0, "kick_sweep": 36.0, "kick_decay": 11.0, "snare_hz": 240.0, "snare_decay": 30.0, "wires": 0.35, "hat_lo": 7000.0},
    "Ballad": {"kick_hz": 48.0, "kick_sweep": 54.0, "kick_decay": 8.0, "snare_hz": 190.0, "snare_decay": 20.0, "wires": 0.55, "hat_lo": 6000.0},
}


def drum_kit_enabled() -> bool:
    return str(os.environ.get("MUSIC_DRUM_KIT_V2") or "").strip().lower() in {"1", "true", "yes", "on"}


def _bp(x: np.ndarray, lo: float, hi: float, sr: int) -> np.ndarray:
    hi = min(hi, sr * 0.45)
    return signal.sosfilt(signal.butter(2, [lo, hi], btype="band", fs=sr, output="sos"), x)


def _unit(x: np.ndarray, sr: int) -> np.ndarray:
    """Scale to unit energy, so a voice's level comes only from the volume it is played at."""
    e = float(np.sum(x**2)) / sr
    return (x / np.sqrt(e) if e > 0 else x).astype(np.float32)


def _metal(n: int, sr: int) -> np.ndarray:
    t = np.arange(n) / sr
    return sum(signal.square(2 * np.pi * f * t) for f in _METAL) / len(_METAL)


def _synth(voice: str, vel: float, rr: int, sr: int, tune: dict[str, float], extra: float = 0.0) -> np.ndarray:
    rng = np.random.default_rng(sum(map(ord, voice)) * 997 + rr * 31 + int(vel * 100))
    detune = 1.0 + 0.012 * ((rr % 4) - 1.5) / 1.5  # each repeat of a hit differs a little
    if voice == "kick":
        n = int(0.42 * sr)
        t = np.arange(n) / sr
        f = tune["kick_hz"] * detune + tune["kick_sweep"] * np.exp(-t * 32)
        body = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t * tune["kick_decay"])
        sub = 0.35 * np.sin(2 * np.pi * tune["kick_hz"] * t) * np.exp(-t * 6)
        beater = _bp(rng.normal(0, 1, n), 1500, 5000, sr) * np.exp(-t * 300)
        return _unit(body + sub + tune.get("beater", 1.0) * (0.25 + 0.3 * vel) * beater, sr)
    if voice == "snare":
        n = int(0.30 * sr)
        t = np.arange(n) / sr
        hz = tune["snare_hz"] * detune
        body = np.sin(2 * np.pi * hz * t) * np.exp(-t * 28) + 0.6 * np.sin(2 * np.pi * hz * 1.78 * t) * np.exp(-t * 40)
        wires = _bp(rng.normal(0, 1, n), 1800 + 1500 * vel, 12500, sr) * np.exp(-t * tune["snare_decay"])
        # Wires keep rattling after the head stops: a quiet, slower layer behind the attack.
        rattle = _bp(rng.normal(0, 1, n), 2500, 7000, sr) * np.exp(-t * 11) * 0.16
        click = _bp(rng.normal(0, 1, n), 3000, 12000, sr) * np.exp(-t * 400)
        return _unit((0.35 + 0.45 * (1 - vel)) * body + (tune["wires"] + 0.25 * vel) * wires + rattle + 0.3 * vel * click, sr)
    if voice in {"closed", "half", "pedal"}:
        dur = {"closed": 0.08, "half": 0.20, "pedal": 0.06}[voice]
        decay = {"closed": 52.0, "half": 15.0, "pedal": 68.0}[voice]
        n = int(dur * sr)
        t = np.arange(n) / sr
        lo = tune["hat_lo"] + 1500 * vel + 250 * (rr % 3)  # harder is brighter
        x = _bp(0.65 * _metal(n, sr) + 0.35 * rng.normal(0, 1, n), lo, lo + 6500, sr)
        # A little of the stick on metal around 3-5 kHz keeps the hat audible through the band.
        stick = _bp(rng.normal(0, 1, n), 3000, 5500, sr) * np.exp(-t * 170) * 0.5
        return _unit((x + stick) * np.exp(-t * decay) * (1 - np.exp(-t * 3000)), sr)
    if voice == "crash":
        n = int(1.9 * sr)
        t = np.arange(n) / sr
        partials = sum(np.sin(2 * np.pi * f * detune * t + rng.uniform(0, 6.28)) for f in (3156, 4227, 5381, 6890, 8203, 9512)) / 6
        x = 0.22 * _metal(n, sr) + 0.35 * partials + 0.9 * _bp(rng.normal(0, 1, n), 3500, 14000, sr)
        return _unit(x * np.exp(-t * 1.9) * (1 - np.exp(-t * 800)), sr)
    if voice == "ride":
        n = int(0.9 * sr)
        t = np.arange(n) / sr
        ping = sum(a * np.sin(2 * np.pi * f * detune * t) for f, a in ((2380, 1.0), (3710, 0.6), (5230, 0.35), (7120, 0.2)))
        wash = _bp(rng.normal(0, 1, n), 4500, 13000, sr)
        tick = _bp(rng.normal(0, 1, n), 2500, 9000, sr) * np.exp(-t * 350)
        return _unit(ping * np.exp(-t * 13) * (0.5 + 0.5 * vel) + wash * np.exp(-t * 5) * 0.28 + (0.5 + 0.5 * vel) * tick, sr)
    if voice == "rim":
        n = int(0.05 * sr)
        t = np.arange(n) / sr
        # Stick on the rim: mostly the bright crack, with a little of the drum's wood beneath it.
        wood = 0.35 * np.sin(2 * np.pi * 480 * detune * t) * np.exp(-t * 130) + 0.5 * np.sin(2 * np.pi * 1250 * detune * t) * np.exp(-t * 190)
        crack = _bp(rng.normal(0, 1, n), 1800, 11000, sr) * np.exp(-t * 170)
        return _unit(wood + 1.2 * crack, sr)
    if voice == "tom":
        n = int(0.45 * sr)
        t = np.arange(n) / sr
        f = extra * detune * (1 + 0.35 * np.exp(-t * 25))
        body = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t * 9)
        return _unit(body + 0.25 * _bp(rng.normal(0, 1, n), 800, 4000, sr) * np.exp(-t * 60), sr)
    raise ValueError(voice)


@lru_cache(maxsize=512)
def _sample(voice: str, bucket: int, rr: int, sr: int, style: str, extra: float = 0.0) -> np.ndarray:
    tune = _TUNING.get(style, _TUNING["default"])
    return _synth(voice, (0.35, 0.65, 1.0)[bucket], rr, sr, tune, extra)


def _bucket(vel: float) -> int:
    return 0 if vel < 0.5 else (1 if vel < 0.85 else 2)


class DrumKit:
    """One song's kit. Plays the same hit the same way on every render."""

    def __init__(self, sr: int, style: str) -> None:
        self.sr = int(sr)
        self.style = str(style)

    def _place(self, audio: np.ndarray, start_sec: float, sample: np.ndarray, gain: float) -> None:
        start = int(start_sec * self.sr)
        if start >= len(audio) or gain <= 0:
            return
        end = min(len(audio), start + len(sample))
        audio[start:end] += sample[: end - start] * gain

    def _hit(self, audio: np.ndarray, start: float, voice: str, volume: float, energy: float, seed: int, full: str, extra: float = 0.0) -> None:
        vel = min(1.0, float(volume) / _FULL[full])
        rr = abs(int(seed)) % 4
        self._place(audio, start, _sample(voice, _bucket(vel), rr, self.sr, self.style, extra), float(volume) * float(np.sqrt(energy)))

    def kick(self, audio: np.ndarray, start: float, volume: float, seed: int = 0) -> None:
        self._hit(audio, start, "kick", volume, _E_KICK, seed, "kick")

    def snare(self, audio: np.ndarray, start: float, volume: float, seed: int = 0) -> None:
        self._hit(audio, start, "snare", volume, _E_SNARE, seed, "snare")

    def ride(self, audio: np.ndarray, start: float, volume: float, seed: int = 0) -> None:
        self._hit(audio, start, "ride", volume, _E_RIDE, seed, "ride")

    def tom(self, audio: np.ndarray, start: float, midi: float, volume: float, seed: int = 0) -> None:
        # The engine's fills name low notes; a real tom sounds about a fifth above them.
        hz = 440.0 * 2 ** ((float(midi) - 69.0) / 12.0) * 1.5
        self._hit(audio, start, "tom", volume, _E_TOM, seed, "tom", extra=round(hz, 1))

    def pedal(self, audio: np.ndarray, start: float, volume: float, seed: int = 0) -> None:
        self._hit(audio, start, "pedal", volume, 0.028 * _NOISE_ENERGY_PER_SEC, seed, "hat")

    def noise_hit(self, audio: np.ndarray, start: float, dur: float, volume: float, seed: int = 0, tone: float = 0.0) -> None:
        """The engine's general noise hit, played by the voice it stands for."""
        energy = float(dur) * _NOISE_ENERGY_PER_SEC
        if dur >= 0.3:
            self._hit(audio, start, "crash", volume * _CRASH_TRIM, energy, seed, "crash")
        elif tone >= 0.4 and dur <= 0.1:
            self._hit(audio, start, "rim", volume, _E_RIM, seed, "rim")
        elif dur >= 0.08:
            self._hit(audio, start, "half", volume, energy, seed, "hat")
        elif tone < 0.4 and volume >= 0.03:
            self._hit(audio, start, "snare", volume, _E_SNARE, seed, "snare")  # the stop-time crack
        else:
            self._hit(audio, start, "closed", volume, energy, seed, "hat")

    def swell(self, audio: np.ndarray, start: float, dur: float, intensity: float, seed: int = 0) -> None:
        """A cymbal rising into the next downbeat, with the energy of the stacked hits it replaces."""
        n = max(1, int(dur * self.sr))
        x = _sample("crash", 1, abs(int(seed)) % 4, self.sr, self.style)
        rising = np.interp(np.linspace(0, len(x) * 0.5, n), np.arange(len(x)), x)[::-1] * np.linspace(0, 1, n) ** 1.6
        rising = _unit(rising, self.sr)
        steps = max(8, int(dur * 12 / 0.5))
        total = sum((0.005 + 0.045 * ((i / max(1, steps - 1)) ** 1.6) * intensity) ** 2 for i in range(steps)) * 0.045 * _NOISE_ENERGY_PER_SEC
        self._place(audio, start, rising, float(np.sqrt(total)))


@dataclass(frozen=True)
class BarContext:
    style: str
    bar_in_section: int
    role: str  # this section's role: verse, chorus, ...
    next_role: str  # the next section's role, when this bar ends a section
    ends_section: bool
    pulses_per_bar: float
    drums: str = ""  # the section's drum texture, such as "hats" or "minimal"


@dataclass(frozen=True)
class Hit:
    beat: float
    voice: str  # kick / snare / open / pedal / tom
    velocity: float  # 0-1 of a full hit
    midi: float = 0.0


_QUIET_TEXTURES = {"hats", "minimal", "ending"}
_TOM_FILL = {"Funk groove": ((3.0, 50), (3.25, 47), (3.5, 43), (3.75, 40)), "Pop groove": ((3.5, 45), (3.75, 40))}


def replaces_section_fill(style: str, next_role: str) -> bool:
    """True when the drummer plays its own fill, so the engine's fill for this bar stays out."""
    return style in _TOM_FILL and next_role == "chorus"


def bar_extras(ctx: BarContext) -> list[Hit]:
    """The notes this style's drummer adds to the bar. Same song, same notes, every render."""
    if float(ctx.pulses_per_bar) != 4.0 or ctx.drums in _QUIET_TEXTURES:
        return []
    bar, style = int(ctx.bar_in_section), ctx.style
    out: list[Hit] = []
    if style == "Funk groove":
        if bar % 2 == 1:
            out += [Hit(2.75, "ghost", 0.28), Hit(3.5, "open", 0.55)]
        if bar % 4 == 1:
            out.append(Hit(3.75, "kick", 0.7))
    elif style == "Pop groove":
        if ctx.role == "chorus" and bar % 4 == 3 and not ctx.ends_section:
            out.append(Hit(3.5, "open", 0.5))
        if ctx.role != "chorus" and bar % 8 == 3 and not ctx.ends_section:
            out.append(Hit(3.5, "kick", 0.6))
    elif style == "Rock groove":
        if ctx.role == "chorus" and bar % 2 == 1 and not ctx.ends_section:
            out += [Hit(3.5, "open", 0.65), Hit(2.5, "kick", 0.7)]
    elif style == "Jazz swing":
        out += [Hit(1.0, "pedal", 0.5), Hit(3.0, "pedal", 0.5)]
        if bar % 4 == 3:
            out += [Hit(2.5, "ghost", 0.3), Hit(3.5, "ghost", 0.38)]
        elif bar % 8 == 5:
            out.append(Hit(1.5, "ghost", 0.26))
    if ctx.ends_section and replaces_section_fill(style, ctx.next_role):
        out += [Hit(b, "tom", 0.7 + 0.08 * i, float(m)) for i, (b, m) in enumerate(_TOM_FILL[style])]
    return out


def play_extras(kit: DrumKit, audio: np.ndarray, hits: list[Hit], place_beat: Any, intensity: float, seed: int) -> None:
    """Play the drummer's notes. ``place_beat`` turns a beat into seconds with the groove's swing and pocket."""
    for i, h in enumerate(hits):
        t = place_beat(h.beat)
        s = seed + i
        if h.voice == "kick":
            kit.kick(audio, t, _FULL["kick"] * h.velocity * intensity, s)
        elif h.voice == "ghost":
            kit.snare(audio, t, _FULL["snare"] * h.velocity * intensity, s)
        elif h.voice == "open":
            kit.noise_hit(audio, t, 0.09, _FULL["hat"] * h.velocity * intensity * 1.35, s)
        elif h.voice == "pedal":
            kit.pedal(audio, t, _FULL["hat"] * h.velocity * intensity, s)
        elif h.voice == "tom":
            kit.tom(audio, t, h.midi, _FULL["tom"] * h.velocity * intensity, s)

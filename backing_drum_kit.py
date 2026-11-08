"""The recorded drum kit and the style-aware drummer built on it.

Off by default: today's drum sound stays until ``MUSIC_DRUM_KIT_V2=1``. Nothing here runs otherwise.

Each hit is a recording from the pack in ``assets/drum_kit``, shaped for the style, at the level today's
voice has at the same volume. A voice the pack lacks falls back to the synthesized one.

The drummer varies through the whole song: most bars stay plain, small moves appear more often at phrase
ends, and a larger fill closes a section, sized by what comes next. Choices repeat for a given song and
never follow a fixed interval. Each style has its own vocabulary:

* Rock: kick pushes, snare pickups and tom fills, on a hard close-miked kick and snare.
* Funk: moving ghost notes, open hats, short snare runs, on a tight close-miked kit.
* Pop: stays simple, with few moves and a modest pickup into a chorus. No moving ghost notes.
* Jazz: no backbeat. Ride, hi-hat foot on 2 and 4, quiet swung snare and kick answers, a rare bell.
* Blues: triplet pickups at phrase ends.
* Bossa and the styles not named: the pattern stays as written. Only the sound of the kit changes.
"""

from __future__ import annotations

import os
import zlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
from scipy import signal

import backing_drum_samples as _samples

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
# Recorded hits against today's balance in the full band: real hats carry less top end per unit of energy
# than white noise.
_RECORDED_TRIM = {"closed": 2.0, "half": 2.0, "three": 1.8, "open": 1.6, "pedal": 1.0, "ride": 0.75, "bell": 0.75, "crash": 1.1, "sizzle": 1.1, "rim": 1.5}
# Rock and Funk use the close microphones for a harder, more direct kick and snare.
_CLOSE_MIKED = frozenset({"Rock groove", "Funk groove"})
# Each style's balance of the recorded kit: Rock hits harder, Jazz stays light behind the ride.
_STYLE_TRIM: dict[str, dict[str, float]] = {
    "Rock groove": {"kick": 1.15, "snare": 1.15, "tom": 1.15, "crash": 1.6, "closed": 2.1, "half": 2.1, "three": 2.0, "open": 2.0, "ride": 1.5},
    "Funk groove": {"kick": 1.55, "snare": 1.4},
    "Jazz swing": {"kick": 0.55, "snare": 0.8, "tom": 0.7, "pedal": 0.85, "ride": 0.62, "bell": 0.62},
    "Bossa nova": {"kick": 0.85},
    "Ballad": {"kick": 0.85, "snare": 0.85, "crash": 0.8},
}
_HAT_VOICES = frozenset({"closed", "half", "three", "open", "pedal"})
_RINGING_HATS = frozenset({"half", "three", "open"})
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

    def __init__(self, sr: int, style: str, *, pack: _samples.SamplePack | None = None, defer_hats: bool = False) -> None:
        self.sr = int(sr)
        self.style = str(style)
        self.pack = pack
        self.defer_hats = bool(defer_hats)  # hold hi-hat hits so a closing hat can choke an open one
        self._hat_rests: list[tuple[float, float]] = []
        self._hats: list[tuple[np.ndarray, float, np.ndarray, float, bool]] = []

    def _place(self, audio: np.ndarray, start_sec: float, sample: np.ndarray, gain: float) -> None:
        start = int(start_sec * self.sr)
        if start >= len(audio) or gain <= 0:
            return
        end = min(len(audio), start + len(sample))
        audio[start:end] += sample[: end - start] * gain

    def _hit(self, audio: np.ndarray, start: float, voice: str, volume: float, energy: float, seed: int, full: str, extra: float = 0.0) -> None:
        vel = min(1.0, float(volume) / _FULL[full])
        rr = abs(int(seed)) % 4
        recorded = self._recorded(voice, vel, seed, extra)
        sample = recorded if recorded is not None else _sample(voice, _bucket(vel), rr, self.sr, self.style, extra)
        gain = float(volume) * float(np.sqrt(energy))
        if recorded is not None:
            gain *= _RECORDED_TRIM.get(voice, 1.0) * _STYLE_TRIM.get(self.style, {}).get(voice, 1.0)
        if self.defer_hats and voice in _HAT_VOICES:
            self._hats.append((audio, float(start), sample, gain, voice in _RINGING_HATS))
        else:
            self._place(audio, start, sample, gain)

    def _recorded(self, voice: str, vel: float, seed: int, extra: float) -> np.ndarray | None:
        if self.pack is None:
            return None
        name = voice
        if voice == "tom":
            name = "tom_high" if extra >= 200.0 else "tom_low"
        elif voice == "snare":
            hard = self.style in _CLOSE_MIKED
            if vel >= 0.95 and self.style == "Rock groove":
                name = "rimshot_close"  # a hard backbeat catches the rim
            elif hard and vel >= 0.5:
                name = "snare_close"
        elif voice == "kick" and self.style in _CLOSE_MIKED:
            name = "kick_close"
        if not self.pack.has(name):
            return None
        return self.pack.hit(name, vel, abs(int(seed)), self.sr, self.style)

    def rest_hats(self, start: float, end: float) -> None:
        """The hands leave the hi-hat for a fill: hats held for this stretch don't play."""
        if self.defer_hats:
            self._hat_rests.append((float(start), float(end)))

    def flush(self) -> None:
        """Play the held hi-hat hits. A ringing hat stops, with a short choke, when the next hat hit closes it."""
        rests, self._hat_rests = self._hat_rests, []
        hats = sorted((h for h in self._hats if not any(a <= h[1] < b for a, b in rests)), key=lambda h: h[1])
        self._hats = []
        fade = max(1, int(0.012 * self.sr))
        for i, (audio, start, sample, gain, rings) in enumerate(hats):
            if rings and i + 1 < len(hats):
                keep = int((hats[i + 1][1] - start) * self.sr) + fade
                if 0 < keep < len(sample):
                    sample = sample[:keep].copy()
                    sample[-fade:] *= np.linspace(1.0, 0.0, min(fade, len(sample)), dtype=np.float32)
            self._place(audio, start, sample, gain)

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

    def bell(self, audio: np.ndarray, start: float, volume: float, seed: int = 0) -> None:
        self._hit(audio, start, "bell" if self.pack is not None else "ride", volume, _E_RIDE, seed, "ride")

    def open_hat(self, audio: np.ndarray, start: float, volume: float, seed: int = 0) -> None:
        self._hit(audio, start, "open" if self.pack is not None else "half", volume, 0.09 * _NOISE_ENERGY_PER_SEC, seed, "hat")

    def noise_hit(self, audio: np.ndarray, start: float, dur: float, volume: float, seed: int = 0, tone: float = 0.0) -> None:
        """The engine's general noise hit, played by the voice it stands for."""
        energy = float(dur) * _NOISE_ENERGY_PER_SEC
        if dur >= 0.3:
            self._hit(audio, start, "crash", volume * _CRASH_TRIM, energy, seed, "crash")
        elif tone >= 0.4 and dur <= 0.1:
            self._hit(audio, start, "rim", volume, _E_RIM, seed, "rim")
        elif dur >= 0.08:
            self._hit(audio, start, "three" if self.pack is not None else "half", volume, energy, seed, "hat")
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
    song_seed: int = 0  # the same song plays the same drumming on every render
    bar_index: int = 0  # the bar's place in the whole render, repeats included


@dataclass(frozen=True)
class Hit:
    beat: float
    voice: str  # kick / snare / ghost / open / pedal / tom / crash / bell
    velocity: float  # 0-1 of a full hit
    midi: float = 0.0


_QUIET_TEXTURES = {"hats", "minimal", "ending"}
_TOM_HIGH, _TOM_MID, _TOM_LOW = 50, 45, 40


def _roll(ctx: BarContext, salt: int) -> float:
    """A repeatable number in 0-1 for this bar: varied through the song, identical on every render."""
    return (zlib.crc32(f"{ctx.song_seed}:{ctx.bar_index}:{salt}".encode()) & 0xFFFF) / 0xFFFF


def _pick(ctx: BarContext, salt: int, options: list) -> Any:
    return options[int(_roll(ctx, salt) * len(options)) % len(options)]


def _snare_run(beats: list[float], top: float = 0.62) -> list[Hit]:
    n = max(1, len(beats))
    return [Hit(b, "ghost", 0.3 + (top - 0.3) * (i + 1) / n) for i, b in enumerate(beats)]


def _tom_run(beats: list[float], top: float = 0.8) -> list[Hit]:
    n = max(1, len(beats))
    pitches = [_TOM_HIGH, _TOM_MID, _TOM_LOW]
    return [Hit(b, "tom", 0.55 + (top - 0.55) * (i + 1) / n, float(pitches[min(len(pitches) - 1, i * len(pitches) // n)])) for i, b in enumerate(beats)]


def _section_fill(ctx: BarContext) -> list[Hit]:
    """The larger move that closes a section, sized by what comes next and never the same one every time."""
    style, into_chorus = ctx.style, ctx.next_role == "chorus"
    if style == "Pop groove":
        return _pick(ctx, 11, [_tom_run([3.5, 3.75], 0.7), _snare_run([3.5, 3.75], 0.6) + [Hit(3.75, "kick", 0.5)]]) if into_chorus else _snare_run([3.75], 0.45)
    if style == "Rock groove":
        if into_chorus:
            return _pick(ctx, 12, [_tom_run([2.0, 2.5, 3.0, 3.25, 3.5, 3.75], 0.95), _snare_run([3.0, 3.25], 0.8) + _tom_run([3.5, 3.75], 0.95), _tom_run([3.0, 3.25, 3.5, 3.75], 0.9)])
        return _pick(ctx, 13, [_snare_run([3.0, 3.5, 3.75], 0.75), _tom_run([3.5, 3.75], 0.75)])
    if style == "Funk groove":
        if into_chorus:
            return _pick(ctx, 14, [_tom_run([3.0, 3.25, 3.5, 3.75], 0.85), _snare_run([2.75, 3.0, 3.25, 3.5], 0.7) + _tom_run([3.75], 0.8)])
        return _pick(ctx, 15, [_snare_run([3.25, 3.5, 3.75], 0.6), [Hit(3.75, "kick", 0.6)] + _snare_run([3.5], 0.5)])
    if style == "Jazz swing":
        # A quiet swung setup: snare and a low kick answer, never a rock fill.
        return _pick(ctx, 16, [_snare_run([2.5, 3.5], 0.42) + [Hit(3.5, "kick", 0.3)], _snare_run([3.0, 3.5], 0.46)])
    if style == "Blues groove":
        return _pick(ctx, 17, [_snare_run([3.0, 3.33, 3.67], 0.6), _tom_run([3.33, 3.67], 0.65)])
    return []


def _phrase_move(ctx: BarContext) -> list[Hit]:
    """A small change inside a section. Most bars stay plain, so the groove stays easy to play over."""
    style, bar = ctx.style, int(ctx.bar_in_section)
    phrase_end = bar % 4 == 3
    chorus = ctx.role == "chorus"
    # Chance of a move: higher where a real drummer would play one, and low straight after a bar with one.
    chance = {"Pop groove": 0.16, "Rock groove": 0.24, "Funk groove": 0.34, "Jazz swing": 0.3, "Blues groove": 0.22}.get(style, 0.0)
    if phrase_end:
        chance *= 2.4
    if chorus:
        chance *= 1.25
    if bar == 0:
        return []
    if _roll(ctx, 1) >= chance:
        return []
    if style == "Pop groove":
        return _pick(ctx, 2, [[Hit(3.5, "kick", 0.6)], _snare_run([3.75], 0.45), [Hit(3.5, "open", 0.5)], [Hit(1.5, "kick", 0.55)]])
    if style == "Rock groove":
        options = [[Hit(2.5, "kick", 0.7)], [Hit(3.5, "open", 0.65)], _snare_run([3.5, 3.75], 0.65), [Hit(1.5, "kick", 0.65), Hit(3.5, "kick", 0.6)]]
        if phrase_end:
            options += [_tom_run([3.5, 3.75], 0.75), _snare_run([3.0, 3.25, 3.5, 3.75], 0.7)]
        return _pick(ctx, 3, options)
    if style == "Funk groove":
        options = [_snare_run([2.75], 0.3), [Hit(3.75, "kick", 0.7)], [Hit(1.5, "open", 0.5)], _snare_run([1.75, 2.25], 0.3), [Hit(3.5, "open", 0.55)]]
        if phrase_end:
            options += [_snare_run([3.25, 3.5, 3.75], 0.55), _tom_run([3.5, 3.75], 0.7)]
        return _pick(ctx, 4, options)
    if style == "Jazz swing":
        options = [_snare_run([2.5], 0.3), _snare_run([1.5, 3.5], 0.34), [Hit(2.5, "kick", 0.28)], [Hit(0.0, "bell", 0.35)]]
        if phrase_end:
            options += [_snare_run([2.5, 3.5], 0.4), _snare_run([3.5], 0.38) + [Hit(3.5, "kick", 0.3)]]
        return _pick(ctx, 5, options)
    if style == "Blues groove":
        return _pick(ctx, 6, [[Hit(3.67, "kick", 0.55)], _snare_run([3.67], 0.4), _snare_run([3.33, 3.67], 0.5)])
    return []


def _style_bed(ctx: BarContext) -> list[Hit]:
    """What this style always adds under the moves."""
    style, bar = ctx.style, int(ctx.bar_in_section)
    if style == "Jazz swing":
        return [Hit(1.0, "pedal", 0.5), Hit(3.0, "pedal", 0.5)]
    if style == "Funk groove":
        return [Hit(2.75, "ghost", 0.26)] if bar % 2 == 1 and _roll(ctx, 7) < 0.7 else []
    if style == "Rock groove" and ctx.role == "chorus" and bar % 2 == 1 and not ctx.ends_section:
        return [Hit(3.5, "open", 0.6)]
    return []


def replaces_section_fill(style: str, next_role: str = "") -> bool:
    """True where the drummer plays its own fills, so the engine's fixed fill for the bar stays out."""
    return style in {"Pop groove", "Rock groove", "Funk groove", "Jazz swing", "Blues groove"}


def bar_extras(ctx: BarContext) -> list[Hit]:
    """The notes this style's drummer adds to the bar. Same song, same notes, every render.

    Bossa and the styles not named here stay as written: they get the kit's sound and no added notes.
    """
    if float(ctx.pulses_per_bar) != 4.0 or ctx.drums in _QUIET_TEXTURES:
        return []
    out = _style_bed(ctx)
    if ctx.ends_section:
        out += _section_fill(ctx)
    else:
        out += _phrase_move(ctx)
    return out


def fill_window(hits: list[Hit]) -> tuple[float, float] | None:
    """The beats a fill occupies, where the hands are off the hi-hat. A lone pickup keeps the hat going."""
    beats = [h.beat for h in hits if h.voice == "tom" or (h.voice == "ghost" and h.velocity >= 0.38)]
    if len(beats) < 2:
        return None
    return (min(beats) - 0.01, max(beats) + 0.24)


def play_extras(kit: DrumKit, audio: np.ndarray, hits: list[Hit], place_beat: Any, intensity: float, seed: int) -> None:
    """Play the drummer's notes. ``place_beat`` turns a beat into seconds with the groove's swing and pocket."""
    window = fill_window(hits)
    if window is not None:
        kit.rest_hats(place_beat(window[0]), place_beat(window[1]))
    for i, h in enumerate(hits):
        t = place_beat(h.beat)
        s = seed + i
        if h.voice == "kick":
            kit.kick(audio, t, _FULL["kick"] * h.velocity * intensity, s)
        elif h.voice == "ghost":
            kit.snare(audio, t, _FULL["snare"] * h.velocity * intensity, s)
        elif h.voice == "open":
            kit.open_hat(audio, t, _FULL["hat"] * h.velocity * intensity * 1.35, s)
        elif h.voice == "pedal":
            kit.pedal(audio, t, _FULL["hat"] * h.velocity * intensity, s)
        elif h.voice == "tom":
            kit.tom(audio, t, h.midi, _FULL["tom"] * h.velocity * intensity, s)
        elif h.voice == "bell":
            kit.bell(audio, t, _FULL["ride"] * h.velocity * intensity, s)

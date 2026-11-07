"""Rock rhythm guitar played from a guitar recorded direct, through a small amp and cabinet (numpy only).

Off by default: today's Rock sound plays unless ``MUSIC_ROCK_GUITAR=recorded``. The part follows the
chart's chords and the song's sections: palm-muted power chords in a verse, ringing doubled chords in a
chorus, clean single strokes in a quiet section, short riffs and pickups at phrase ends. It stays in the
low register, leaving the melody's range clear. ``backing_audio`` calls ``play_bar`` once a bar and
``finish`` once a song.
"""

from __future__ import annotations

import os
import pathlib
import zlib
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from backing_sampled_instrument import SampledInstrument

GUITAR_PACK = pathlib.Path(__file__).resolve().parent / "assets" / "instruments" / "electric_guitar"
ROOT_LOW = 40  # E2: the lowest root of a power chord, on the sixth string
ROOT_HIGH = 51  # Eb3
# How hard the amp is driven, section by section.
DRIVE = {"clean": 1.15, "crunch": 3.6, "overdrive": 8.5}
_MUTE_CUTOFF_HZ = 1500.0
_BLOCK = 1 << 16


def enabled() -> bool:
    raw = str(os.environ.get("MUSIC_ROCK_GUITAR") or "").strip().lower()
    return raw not in {"", "0", "off", "false", "no"} and (GUITAR_PACK / "manifest.json").is_file()


def guitar_renderer_tag() -> str:
    """Part of saved audio's signature, so takes from another guitar part are never replayed as this one."""
    return "+rockgtr1" if enabled() else ""


@lru_cache(maxsize=1)
def _guitar() -> SampledInstrument:
    return SampledInstrument(GUITAR_PACK)


@dataclass(frozen=True)
class Stroke:
    beat: float
    beats: float  # how long it is held
    pitches: tuple[int, ...]  # lowest first
    velocity: float
    kind: str = "open"  # "open", "mute" (palm), "dead" (no pitch)
    up: bool = False


def _roll(*parts) -> float:
    return (zlib.crc32(":".join(str(p) for p in parts).encode("utf-8")) % 100000) / 100000.0


def power_root(pc: int) -> int:
    """``pc`` as the root of a power chord: E2 .. Eb3."""
    return ROOT_LOW + ((int(pc) - ROOT_LOW) % 12)


def power_chord(root_pc: int, fifth: int = 7, *, wide: bool = False) -> tuple[int, ...]:
    """Root, the chord's own fifth (a flat five stays flat), and the octave when the part opens up."""
    root = power_root(root_pc)
    return (root, root + fifth, root + 12) if wide else (root, root + fifth)


def section_tone(role: str, quiet: bool) -> str:
    if quiet:
        return "clean"
    return "overdrive" if role in {"chorus", "refrain", "interlude", "solo", "outro"} else "crunch"


def _verse_pattern(pulses: int, end: float, start: float, roll: float) -> list[tuple[float, float, str, float]]:
    """(beat, beats held, kind, accent) over one chord in a verse: driving eighths with a varied accent."""
    out = []
    b = start
    accent_at = start + (2.0 if roll < 0.34 else 2.5 if roll < 0.67 else 3.0)
    while b < end - 1e-6:
        on_beat = abs(b - round(b)) < 1e-6
        if abs(b - start) < 1e-6:
            out.append((b, 0.48, "mute", 1.0))
        elif abs(b - accent_at) < 1e-6 and accent_at + 0.5 <= end:
            out.append((b, min(end - b, 1.0), "open", 0.92))
            b += 1.0
            continue
        else:
            out.append((b, 0.42, "mute", 0.84 if on_beat else 0.72))
        b += 0.5
    return out


def _chorus_pattern(end: float, start: float, roll: float) -> list[tuple[float, float, str, float]]:
    """Ringing chords: a held downbeat and pushes that change from bar to bar."""
    span = end - start
    if span >= 4.0 and roll < 0.40:
        return [(start, 1.5, "open", 1.0), (start + 1.5, 1.0, "open", 0.86), (start + 2.5, 1.5, "open", 0.92)]
    if span >= 4.0 and roll < 0.75:
        return [(start, 2.0, "open", 1.0), (start + 2.0, 0.5, "mute", 0.76), (start + 2.5, 1.5, "open", 0.92)]
    if span >= 4.0:
        return [(start, 1.0, "open", 1.0), (start + 1.0, 0.5, "open", 0.80), (start + 1.5, 1.0, "open", 0.88), (start + 2.5, 0.5, "mute", 0.74), (start + 3.0, 1.0, "open", 0.92)]
    return [(start, span, "open", 1.0)]


def _riff_tail(root_pc: int, next_pc: int | None, start: float, end: float, roll: float) -> list[Stroke]:
    """Single notes leading out of a phrase: the minor pentatonic toward the next chord, never the same way twice."""
    root = power_root(root_pc)
    if next_pc is None or end - start < 1.5:
        return []
    target = root + ((int(next_pc) - root) % 12)
    if target - root > 7:
        target -= 12
    if roll < 0.34:
        line = (root + 3, root + 5, root + 6)
    elif roll < 0.67:
        line = (root + 7, root + 5, root + 3)
    else:
        line = (target - 3, target - 2, target - 1) if target - 3 >= ROOT_LOW else (root + 3, root + 5, root + 7)
    line = tuple(max(ROOT_LOW, m) for m in line)
    step = (end - start) / len(line)
    return [Stroke(start + i * step, step * 0.92, (m,), 0.84 + 0.05 * i, "open") for i, m in enumerate(line)]


def rock_guitar_bar(
    segments: list[tuple[float, float, str | None]],
    pulses_per_bar: int,
    *,
    tone: str,
    fifth_of,
    root_of,
    next_chord: str | None,
    phrase_end: bool,
    section_end: bool,
    seed: str,
    bar_index: int,
) -> list[Stroke]:
    """One bar's strokes. Rests in the chart stay silent."""
    strokes: list[Stroke] = []
    last = len(segments) - 1
    for i, (start, end, chord) in enumerate(segments):
        if chord is None:
            continue
        root_pc, fifth = int(root_of(chord)) % 12, int(fifth_of(chord))
        roll = _roll(seed, bar_index, i)
        if tone == "clean":
            strokes.append(Stroke(start, end - start, power_chord(root_pc, fifth, wide=True), 0.46, "open"))
            continue
        wide = tone == "overdrive"
        shape = power_chord(root_pc, fifth, wide=wide)
        riff_from = None
        if i == last and pulses_per_bar == 4 and end - start >= 4.0 and (phrase_end or section_end):
            # A pickup at the end of about half the phrases, so it never arrives on a schedule.
            if section_end or _roll(seed, "riff", bar_index) < 0.5:
                riff_from = end - 1.5
        stop = riff_from if riff_from is not None else end
        pattern = _chorus_pattern(stop, start, roll) if tone == "overdrive" else _verse_pattern(pulses_per_bar, stop, start, roll)
        for beat, held, kind, accent in pattern:
            up = abs(beat - round(beat)) > 1e-6
            # A palm-muted chug is the root and fifth at most; quite often the root alone.
            pitches = shape if kind == "open" else (shape[:1] if _roll(seed, bar_index, beat) < 0.55 else shape[:2])
            strokes.append(Stroke(beat, min(held, stop - beat), pitches, accent * (0.97 + 0.06 * _roll(seed, "v", bar_index, beat)), kind, up))
        if riff_from is not None:
            nxt = None if next_chord is None else int(root_of(next_chord)) % 12
            strokes += _riff_tail(root_pc, nxt, riff_from, end, _roll(seed, "line", bar_index))
        elif tone == "crunch" and end - start >= 4.0 and _roll(seed, "dead", bar_index) < 0.22:
            # A dead stroke on the "and" of 4 now and then, as a hand keeps moving through a rest.
            strokes = [s for s in strokes if not (s.beat == end - 0.5)]
            strokes.append(Stroke(end - 0.5, 0.2, shape[:1], 0.7, "dead", True))
    return strokes


class GuitarPart:
    """Collects a song's strokes into two buses and runs them through the amp at the end."""

    def __init__(self, length: int, sr: int, seed: str) -> None:
        self.sr = int(sr)
        self.seed = seed
        self.open = np.zeros(length, dtype=np.float32)
        self.mute = np.zeros(length, dtype=np.float32)
        self.drive = np.full(length, DRIVE["crunch"], dtype=np.float32)
        self._takes: dict = {}
        self._dead_n = 0

    def _play(self, stroke: Stroke, t: float, pulse: float, level: float, tag: str) -> None:
        inst = _guitar()
        if stroke.kind == "dead":
            take = inst.dead[self._dead_n % len(inst.dead)]
            self._dead_n += 1
            x = inst._audio(take["file"])
            start = int(max(0.0, t) * self.sr)
            n = min(len(x), len(self.open) - start)
            if n > 0:
                self.mute[start : start + n] += x[:n].astype(np.float32) / 32768.0 * float(take["gain"]) * level * stroke.velocity
            return
        bus = self.mute if stroke.kind == "mute" else self.open
        # A pick crosses the strings: low to high going down, the reverse coming up.
        order = stroke.pitches[::-1] if stroke.up else stroke.pitches
        gap = 0.0035 if stroke.kind == "mute" else 0.0065
        for k, midi in enumerate(order):
            inst.add_note(
                bus, self.sr, t + k * gap, max(0.03, stroke.beats * pulse), int(midi),
                level * stroke.velocity, 0.2 + 0.75 * stroke.velocity,
                f"{self.seed}:{tag}:{t:.3f}:{midi}", self._takes,
                release_sec=0.025 if stroke.kind == "mute" else 0.05,
            )

    def play_bar(self, strokes: list[Stroke], bar_start: float, pulse: float, tone: str, bar_seconds: float, *, double: bool, level: float = 1.0) -> None:
        a = int(bar_start * self.sr)
        b = min(len(self.drive), int((bar_start + bar_seconds) * self.sr))
        if b > a:
            self.drive[a:b] = DRIVE[tone]
        for s in strokes:
            jitter = (_roll(self.seed, "t", bar_start, s.beat) - 0.5) * 0.008
            self._play(s, bar_start + s.beat * pulse + jitter, pulse, level, "a")
            if double and s.kind != "dead":
                # The same part played again: a second take, never quite together.
                late = 0.008 + 0.012 * _roll(self.seed, "d", bar_start, s.beat)
                self._play(s, bar_start + s.beat * pulse + late, pulse, level * 0.82, "b")

    def finish(self) -> np.ndarray:
        """The amp's output. Silence stays silence, and nothing is rendered for a song with no guitar."""
        if not self.open.any() and not self.mute.any():
            return np.zeros_like(self.open)
        mute = _block_eq(self.mute, self.sr, _mute_curve)
        x = self.open + mute
        self.open, self.mute = np.zeros(0, dtype=np.float32), np.zeros(0, dtype=np.float32)
        out = _amp(_block_eq(x, self.sr, _pre_curve), self.drive)
        return _block_eq(out, self.sr, _cabinet_curve)


def _peak(f: np.ndarray, fc: float, q: float, db: float) -> np.ndarray:
    return 10.0 ** (db / 20.0 * (1.0 / (1.0 + ((f - fc) / (fc / q)) ** 2)))


def _mute_curve(f: np.ndarray) -> np.ndarray:
    """A palm on the strings takes the top off the note."""
    return 1.15 / np.sqrt(1.0 + (f / _MUTE_CUTOFF_HZ) ** 4)


def _pre_curve(f: np.ndarray) -> np.ndarray:
    """Before the amp's first stage: tighten the lows so the chords stay clear, push the mids."""
    hp = (f / 120.0) ** 2 / np.sqrt(1.0 + (f / 120.0) ** 4)
    return hp * _peak(f, 800.0, 1.0, 5.0)


def _cabinet_curve(f: np.ndarray) -> np.ndarray:
    """A closed 12-inch speaker: nothing below about 80 Hz or above about 5 kHz, a scooped low-mid, a presence peak."""
    hp = (f / 80.0) ** 2 / np.sqrt(1.0 + (f / 80.0) ** 4)
    lp = 1.0 / np.sqrt(1.0 + (f / 5200.0) ** 8)
    return hp * lp * _peak(f, 115.0, 2.0, 2.0) * _peak(f, 420.0, 1.6, -3.5) * _peak(f, 1300.0, 2.0, 1.5) * _peak(f, 3000.0, 2.2, 5.0)


@lru_cache(maxsize=8)
def _block_response(name: str, n: int, sr: int, curve) -> np.ndarray:
    return curve(np.maximum(np.fft.rfftfreq(n, 1.0 / sr), 1.0)).astype(np.float32)


def _block_eq(x: np.ndarray, sr: int, curve) -> np.ndarray:
    """Filter by overlap-add, so a long song's memory stays at a few blocks."""
    if len(x) == 0:
        return x
    hop = _BLOCK // 2
    window = np.hanning(_BLOCK + 1)[:-1].astype(np.float32)
    h = _block_response(curve.__name__, _BLOCK, sr, curve)
    out = np.zeros(len(x), dtype=np.float32)
    for start in range(-hop, len(x), hop):
        a, b = max(0, start), min(len(x), start + _BLOCK)
        if b <= a or not x[a:b].any():
            continue
        block = np.zeros(_BLOCK, dtype=np.float32)
        block[a - start : b - start] = x[a:b]
        filtered = np.fft.irfft(np.fft.rfft(block * window) * h, _BLOCK).astype(np.float32)
        out[a:b] += filtered[a - start : b - start]
    return out


def _amp(x: np.ndarray, drive: np.ndarray) -> np.ndarray:
    """Two soft-clipping stages at twice the sample rate, to keep the fold-back quiet. Harder drive stays about level."""
    d = drive[: len(x)]
    mid = np.empty(2 * len(x), dtype=np.float32)
    mid[0::2] = x
    mid[1:-1:2] = 0.5 * (x[:-1] + x[1:])
    mid[-1] = x[-1]
    g = np.repeat(d * 4.0, 2)
    y = np.tanh(mid * g + 0.08 * np.minimum(g / 8.0, 1.0)) - np.tanh(0.08 * np.minimum(g / 8.0, 1.0))
    y = np.tanh(1.4 * y)
    out = 0.5 * (y[0::2] + y[1::2])
    return (out * (1.0 / np.sqrt(np.minimum(d, 2.5)))).astype(np.float32)

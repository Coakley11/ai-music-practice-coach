"""Rock guitar played from a guitar recorded direct, through ``backing_guitar_amp``.

Off by default: today's Rock sound plays unless ``MUSIC_ROCK_GUITAR=recorded``. A song gets one guitarist
with one part, chosen from its title, tempo and chords: driving palm mutes, a boogie, an open strum,
clean picking that opens into big chords, syncopated stabs, or a single-note riff. The part stays out of
the melody's range. ``backing_audio`` calls ``start_part``, then ``add_bar`` once a bar and ``finish`` once.
"""

from __future__ import annotations

import os
import pathlib
import zlib
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

import backing_eq as eq
from backing_guitar_amp import TONES, amplify
from backing_sampled_instrument import SampledInstrument

GUITAR_PACK = pathlib.Path(__file__).resolve().parent / "assets" / "instruments" / "electric_guitar"
ROOT_LOW = 40  # E2: the lowest root, on the sixth string
ROOT_HIGH = 51  # Eb3
TOP_NOTE = 69  # A4: above this is the melody's space
OPEN_STRINGS = (40, 45, 50, 55, 59, 64)
PARTS = ("chug", "boogie", "strum", "arena", "stabs", "riff")
CHORUS_ROLES = frozenset({"chorus", "refrain", "interlude", "solo", "outro"})
# (verse, chorus) amp tones; the heavier pair is for faster songs.
PART_TONES = {
    "chug": (("crunch", "overdrive"), ("overdrive", "distorted")),
    "boogie": (("crunch", "crunch"), ("crunch", "overdrive")),
    "strum": (("clean", "crunch"), ("crunch", "overdrive")),
    "arena": (("clean", "overdrive"), ("clean", "distorted")),
    "stabs": (("clean", "crunch"), ("crunch", "crunch")),
    "riff": (("overdrive", "overdrive"), ("overdrive", "distorted")),
}
_TAIL_SEC = 0.8


def enabled() -> bool:
    raw = str(os.environ.get("MUSIC_ROCK_GUITAR") or "").strip().lower()
    return raw not in {"", "0", "off", "false", "no"} and (GUITAR_PACK / "manifest.json").is_file()


def guitar_renderer_tag() -> str:
    """Part of saved audio's signature, so takes from another guitar part are never replayed as this one."""
    if not enabled():
        return ""
    import backing_audio as _ba  # the band slot and the piano's level are part of the take

    return f"+rockgtr3-slot{_ba._GTR_SLOT_PRESENCE_DB:g}_{_ba._GTR_SLOT_PIANO_DIP_DB:g}_{_ba._ROCK_KEYS_BEHIND_GUITAR:g}_{_ba._ROCK_GUITAR_BALANCE:g}"


def _palm_mute(x: np.ndarray, sr: int) -> np.ndarray:
    """A palm resting on the strings: the pick's click, then a dark, quickly choked note."""
    n = int(0.42 * sr)
    y = x[:n].astype(np.float32) / 32768.0
    t = np.arange(len(y), dtype=np.float32) / sr
    body = eq.apply(y, sr, (("lowpass", 620.0, 0.8), ("lowpass", 980.0, 0.7), ("peak", 170.0, 1.2, 3.0)))
    click = np.exp(-t / 0.0045)
    out = (y * click * 0.9 + body * (1.0 - click) * 1.35) * np.exp(-t / 0.085)
    out[-64:] *= np.linspace(1.0, 0.0, 64, dtype=np.float32)
    return np.clip(out * 32768.0, -32768, 32767).astype(np.int16)


@lru_cache(maxsize=1)
def _guitar() -> SampledInstrument:
    inst = SampledInstrument(GUITAR_PACK)
    inst.variants["palm"] = _palm_mute
    return inst


@dataclass(frozen=True)
class Stroke:
    beat: float
    beats: float  # how long it is held
    pitches: tuple[int, ...]  # lowest first
    velocity: float
    kind: str = "open"  # "open" rings, "mute" is palm muted, "dead" has no pitch
    up: bool = False


@dataclass(frozen=True)
class Plan:
    part: str
    tones: tuple[str, str]
    seed: str


@dataclass(frozen=True)
class Shape:
    """One chord under the hand."""

    root: int
    power: tuple[int, ...]
    wide: tuple[int, ...]
    full: tuple[int, ...]
    high: tuple[int, ...]
    tones: frozenset = frozenset()  # the chord's own notes, as intervals above the root


def _colour(shape: Shape, step: int) -> int:
    """A riff or boogie note (semitones above the root), bent to the chord only where the stock blues note
    would rub against one of the chord's own notes. The blues vocabulary over major, power and dominant
    chords (blue third, flat seventh, fourth, sixth) is kept: it is the idiom, not a wrong note.

    * major seventh chord: the flat seventh becomes the major seventh, the blue third the major third;
    * an altered fifth (diminished, half-diminished, augmented): the plain fifth becomes the chord's fifth;
    * diminished seventh: the flat seventh becomes its double-flat seventh;
    * a flat thirteenth (or raised fifth): the sixth becomes that note.
    """
    t = shape.tones
    if not t:
        return step
    octave, pc = step - step % 12, step % 12
    if pc in t:
        return step
    if pc == 7:
        pc = 6 if 6 in t else 8 if 8 in t else 7
    elif pc == 10:
        pc = 11 if 11 in t else 9 if (9 in t and 6 in t) else 10
    elif pc == 9:
        pc = 8 if 8 in t else 9
    elif pc == 3 and 4 in t and (11 in t or 8 in t):
        pc = 4
    return octave + pc


def _roll(*parts) -> float:
    return (zlib.crc32(":".join(str(p) for p in parts).encode("utf-8")) % 100000) / 100000.0


def power_root(pc: int) -> int:
    return ROOT_LOW + ((int(pc) - ROOT_LOW) % 12)


def _intervals(notes: list[int]) -> tuple[int | None, int, int | None]:
    """(third, fifth, seventh) above the root; a power chord has no third."""
    pcs = {(n - notes[0]) % 12 for n in notes[1:]}
    third = 3 if 3 in pcs else 4 if 4 in pcs else 5 if 5 in pcs else 2 if 2 in pcs else None
    fifth = 7 if 7 in pcs else 6 if 6 in pcs else 8 if 8 in pcs else 7
    seventh = 10 if 10 in pcs else 11 if 11 in pcs else 9 if 9 in pcs else None
    return third, fifth, seventh


def chord_shape(notes: list[int]) -> Shape:
    """Barre fingerings with the root on the sixth or fifth string, stopping below the melody's range."""
    third, fifth, seventh = _intervals(notes)
    root = power_root(notes[0] % 12)
    power = (root, root + fifth)
    wide = (root, root + fifth, root + 12)
    upper = 12 if seventh is None else seventh
    full = wide if third is None else (root, root + fifth, root + upper, root + 12 + third, root + 12 + fifth)
    # The three notes on the thin strings, for a second guitar above the first.
    high = tuple(sorted((root + 12 + (third if third is not None else fifth), root + 12 + fifth, root + 24)))
    while max(high) > TOP_NOTE:
        high = tuple(m - 12 for m in high)
    tones = frozenset((n - notes[0]) % 12 for n in notes)
    return Shape(root, power, wide, tuple(m for m in full if m <= TOP_NOTE), high, tones)


def choose_plan(chords: list[str], chord_notes, bpm: float, seed: str) -> Plan:
    """One guitarist's part for the whole song. Songs full of seventh chords avoid bare power-chord parts."""
    plain = [c for c in chords if c]
    colourful = 0
    for c in plain:
        try:
            colourful += int(_intervals(chord_notes(c))[2] is not None)
        except Exception:
            continue
    if colourful / max(1, len(plain)) > 0.45:
        pool = ("strum", "strum", "arena", "stabs")
    elif bpm >= 138:
        pool = ("chug", "chug", "boogie", "riff")
    elif bpm <= 92:
        pool = ("arena", "arena", "strum", "riff")
    else:
        pool = PARTS
    part = pool[int(_roll(seed, "part") * len(pool)) % len(pool)]
    heavy = bpm >= 122 and _roll(seed, "heavy") < 0.5
    return Plan(part, PART_TONES[part][1 if heavy else 0], seed)


def section_tone(plan: Plan, role: str, quiet: bool) -> str:
    if quiet:
        return "clean"
    return plan.tones[1] if role in CHORUS_ROLES else plan.tones[0]


# --- The parts. Each writes one chord's strokes between ``start`` and ``end``. -----------------------------


def _fit(items: list[Stroke], end: float) -> list[Stroke]:
    return [Stroke(s.beat, min(s.beats, end - s.beat), s.pitches, s.velocity, s.kind, s.up) for s in items if s.beat < end - 1e-6]


def _is_up(beat: float) -> bool:
    return abs(beat - round(beat)) > 1e-6


def _chug(start, end, shape: Shape, chorus: bool, seed, bar) -> list[Stroke]:
    roll = _roll(seed, "chug", bar, start)
    if chorus:
        if roll < 0.40:
            grid = [(0.0, 1.5, 1.0), (1.5, 1.0, 0.86), (2.5, 1.5, 0.92)]
        elif roll < 0.75:
            grid = [(0.0, 2.0, 1.0), (2.5, 1.5, 0.92)]
        else:
            grid = [(0.0, 1.0, 1.0), (1.0, 0.5, 0.80), (1.5, 1.0, 0.88), (3.0, 1.0, 0.92)]
        return _fit([Stroke(start + b, h, shape.wide, a, "open", _is_up(start + b)) for b, h, a in grid], end)
    accent = 2.0 if roll < 0.34 else 2.5 if roll < 0.67 else 3.0
    out, b = [], start
    while b < end - 1e-6:
        rel = b - start
        if abs(rel - accent) < 1e-6 and b + 1.0 <= end:
            out.append(Stroke(b, 1.0, shape.power, 0.92, "open", _is_up(b)))
            b += 1.0
            continue
        one = _roll(seed, "n", bar, b) < 0.55
        out.append(Stroke(b, 0.42, shape.power[:1] if one else shape.power, 1.0 if rel == 0 else 0.84 if not _is_up(b) else 0.72, "mute"))
        b += 0.5
    return out


def _boogie(start, end, shape: Shape, chorus: bool, seed, bar) -> list[Stroke]:
    """Root and fifth rocking to the sixth, as on countless blues-rock records."""
    r, fifth = shape.root, shape.power[1]
    if fifth - r != 7:
        # Diminished, half-diminished, augmented: the fifth-to-sixth rock does not fit the chord.
        return _chug(start, end, shape, chorus, seed, bar)
    six, flat7 = r + _colour(shape, 9), r + _colour(shape, 10)
    line = [fifth, fifth, six, six, flat7 if _roll(seed, "boog", bar) < 0.3 else six, six, fifth, fifth]
    out = []
    for i, top in enumerate(line):
        accent = 1.0 if i == 0 else 0.86 if i % 2 == 0 else 0.74
        out.append(Stroke(start + i * 0.5, 0.46, (r, top), accent * (1.0 if chorus else 0.92), "open" if chorus or i % 4 == 0 else "mute"))
    return _fit(out, end)


_STRUMS = (
    # (beat, held, velocity, up, muted chop)
    ((0.0, 1.0, 1.0, False, False), (1.0, 0.25, 0.70, False, True), (1.5, 0.5, 0.74, True, False), (2.0, 1.0, 0.92, False, False), (3.0, 0.25, 0.70, False, True), (3.5, 0.5, 0.74, True, False)),
    ((0.0, 1.5, 1.0, False, False), (1.5, 0.5, 0.78, True, False), (2.0, 0.5, 0.86, False, False), (2.5, 0.5, 0.72, True, False), (3.0, 0.5, 0.88, False, False), (3.5, 0.5, 0.74, True, False)),
    ((0.0, 1.0, 1.0, False, False), (1.0, 0.5, 0.82, False, False), (1.5, 1.0, 0.76, True, False), (2.5, 0.5, 0.74, True, False), (3.0, 1.0, 0.90, False, False)),
)


def _strum(start, end, shape: Shape, chorus: bool, seed, bar) -> list[Stroke]:
    chosen = int(_roll(seed, "strumpat") * len(_STRUMS))
    if _roll(seed, "strumbar", bar) < 0.2:
        chosen += 1
    out = []
    for b, held, vel, up, chop in _STRUMS[chosen % len(_STRUMS)]:
        at = start + b
        if chop:
            out.append(Stroke(at, 0.12, shape.full[:3], vel * 0.8, "dead", up))
        else:
            # An upstroke catches only the thin strings.
            out.append(Stroke(at, held, shape.full[-3:] if up else shape.full, vel * (1.0 if chorus else 0.9), "open", up))
    return _fit(out, end)


def _arena(start, end, shape: Shape, chorus: bool, seed, bar) -> list[Stroke]:
    if chorus:
        return _chug(start, end, shape, True, seed, bar)
    # Clean picking: each note rings on under the next.
    tones = shape.full
    pick = lambda i: tones[min(i, len(tones) - 1)]
    order = [pick(0), pick(2), pick(3), pick(1)] if _roll(seed, "arp") >= 0.5 else [pick(0), pick(1), pick(2), pick(4)]
    out, b, i = [], start, 0
    while b < end - 1e-6:
        out.append(Stroke(b, min(2.0, end - b), (order[i % 4],), 0.62 + 0.14 * (i % 4 == 0) + 0.06 * _roll(seed, "av", bar, b), "open", _is_up(b)))
        b += 0.5
        i += 1
    return out


def _stabs(start, end, shape: Shape, chorus: bool, seed, bar) -> list[Stroke]:
    """Short syncopated chords, with the hand still moving through the gaps."""
    patterns = ((0.0, 1.5, 2.5, 3.5), (0.0, 0.75, 2.0, 2.75), (0.5, 1.5, 2.0, 3.5))
    hits = patterns[int(_roll(seed, "stab", bar // 2) * len(patterns)) % len(patterns)]
    notes = shape.high if chorus else shape.full[-3:]
    out, grid = [], 0.0
    while grid < 4.0:
        at = start + grid
        if any(abs(grid - h) < 1e-6 for h in hits):
            out.append(Stroke(at, 0.3, notes, 0.92, "open", _is_up(at)))
        elif abs(grid * 2 - round(grid * 2)) < 1e-6 and _roll(seed, "gap", bar, grid) < 0.45:
            out.append(Stroke(at, 0.1, notes[:2], 0.5, "dead", _is_up(at)))
        grid += 0.25
    return _fit(out, end)


# One-bar riffs as (beat, semitones above the root, held).
_RIFFS = (
    ((0.0, 0, 0.5), (0.5, 0, 0.5), (1.0, 3, 0.5), (1.5, 5, 0.5), (2.0, 0, 0.5), (3.0, 10, 0.5), (3.5, 7, 0.5)),
    ((0.0, 0, 0.75), (0.75, 7, 0.25), (1.0, 10, 0.5), (1.5, 0, 0.5), (2.5, 3, 0.5), (3.0, 5, 0.5), (3.5, 6, 0.5)),
    ((0.0, 0, 0.5), (0.5, 12, 0.25), (0.75, 0, 0.25), (1.5, 10, 0.5), (2.0, 7, 0.5), (2.5, 5, 0.5), (3.0, 3, 0.5), (3.5, 0, 0.5)),
)


def _riff(start, end, shape: Shape, chorus: bool, seed, bar) -> list[Stroke]:
    if chorus or end - start < 3.0:
        return _chug(start, end, shape, True, seed, bar)
    out = []
    for b, step, held in _RIFFS[int(_roll(seed, "riffpick") * len(_RIFFS)) % len(_RIFFS)]:
        pitches = shape.power if step == 0 and b == 0.0 else (shape.root + _colour(shape, step),)
        out.append(Stroke(start + b, held, pitches, 0.95 if b == 0.0 else 0.82, "open" if _roll(seed, "rm", bar, b) < 0.75 else "mute"))
    return _fit(out, end)


_WRITERS = {"chug": _chug, "boogie": _boogie, "strum": _strum, "arena": _arena, "stabs": _stabs, "riff": _riff}


def _pickup(shape: Shape, next_pc: int | None, start: float, end: float, roll: float) -> list[Stroke]:
    """A short line out of the phrase, from the blues scale toward the next chord."""
    if next_pc is None or end - start < 1.5:
        return []
    root = shape.root
    target = root + ((int(next_pc) - root) % 12)
    if target - root > 7:
        target -= 12
    line = (root + 3, root + 5, root + 6) if roll < 0.34 else (root + 7, root + 5, root + 3) if roll < 0.67 else (target - 3, target - 2, target - 1)
    line = tuple(max(ROOT_LOW, root + _colour(shape, m - root)) for m in line)
    step = (end - start) / len(line)
    return [Stroke(start + i * step, step * 0.92, (m,), 0.84 + 0.05 * i) for i, m in enumerate(line)]


def guitar_bar(segments, plan: Plan, *, tone: str, chord_notes, next_chord, phrase_end: bool, section_end: bool, bar_index: int, chorus: bool) -> list[Stroke]:
    """One bar's strokes. Rests in the chart stay silent."""
    strokes: list[Stroke] = []
    last = len(segments) - 1
    writer = _WRITERS[plan.part]
    for i, (start, end, chord) in enumerate(segments):
        if chord is None:
            continue
        shape = chord_shape(chord_notes(chord))
        if tone == "clean" and plan.part not in {"arena", "strum", "stabs"}:
            # A quiet section: one clean held chord, whatever the part.
            strokes.append(Stroke(start, end - start, shape.full, 0.5))
            continue
        lead = None
        if i == last and end - start >= 4.0 and plan.part != "arena" and (section_end or (phrase_end and _roll(plan.seed, "lead", bar_index) < 0.5)):
            lead = end - 1.5
        strokes += writer(start, lead if lead is not None else end, shape, chorus, plan.seed, bar_index)
        if lead is not None:
            nxt = None if next_chord is None else chord_notes(next_chord)[0] % 12
            strokes += _pickup(shape, nxt, lead, end, _roll(plan.seed, "line", bar_index))
    return strokes


# --- The guitarist's hands and the amp. -------------------------------------------------------------------


@dataclass
class GuitarPart:
    length: int
    sr: int
    plan: Plan
    buses: dict = field(default_factory=dict)
    spans: dict = field(default_factory=dict)
    _takes: dict = field(default_factory=dict)
    _noise_n: int = 0

    def _bus(self, tone: str) -> np.ndarray:
        if tone not in self.buses:
            self.buses[tone] = np.zeros(self.length, dtype=np.float32)
        return self.buses[tone]

    def _add_noise(self, bus, takes, t, gain) -> None:
        if not takes:
            return
        take = takes[self._noise_n % len(takes)]
        self._noise_n += 1
        x = _guitar()._audio(take["file"])
        start = int(max(0.0, t) * self.sr)
        n = min(len(x), len(bus) - start)
        if n > 0:
            bus[start : start + n] += x[:n].astype(np.float32) / 32768.0 * float(take["gain"]) * gain

    def _play(self, bus, s: Stroke, t: float, pulse: float, level: float, tag: str) -> None:
        inst = _guitar()
        seed = self.plan.seed
        if s.kind == "dead":
            self._add_noise(bus, inst.dead, t, level * s.velocity)
            return
        # A hand crosses the strings: quicker on a hard stroke, low to high going down, high to low coming up.
        order = s.pitches[::-1] if s.up else s.pitches
        speed = _roll(seed, "speed", tag, t)
        gap = 0.0025 + 0.002 * speed if s.kind == "mute" else (0.012 - 0.006 * s.velocity) + 0.0035 * speed
        at = t
        for k, midi in enumerate(order):
            r = _roll(seed, tag, t, k, midi)
            string_vel = s.velocity * (1.0 - (0.03 if s.up else 0.05) * k)
            # Where the pick meets the string changes: the attack softens by a moment, the pitch leans a few cents.
            inst.add_note(
                bus, self.sr, at, max(0.03, s.beats * pulse), int(midi), level * string_vel, 0.18 + 0.78 * string_vel + (r - 0.5) * 0.06,
                f"{seed}:{tag}:{t:.3f}:{midi}", self._takes,
                release_sec=0.02 if s.kind == "mute" else 0.045 + 0.05 * r,
                variant="palm" if s.kind == "mute" else None,
                offset_sec=0.0 if s.kind == "mute" else 0.0035 * r * (1.4 if s.up else 1.0),
                detune_cents=(r - 0.5) * 7.0 + (2.0 if s.velocity > 0.9 else 0.0),
            )
            at += gap * (0.7 + 0.6 * _roll(seed, "g", tag, t, k))
        if s.kind == "open":
            if s.velocity > 0.86:
                self._add_noise(bus, inst.dead, t - 0.002, level * 0.10 * s.velocity)  # the pick's scrape
            if s.beats * pulse > 0.5:
                # The fretting hand lets go, and an open string that shares the root rings quietly under the chord.
                self._add_noise(bus, inst.manifest.get("release", []), t + s.beats * pulse - 0.01, level * 0.9)
                ring = next((o for o in OPEN_STRINGS if o % 12 == s.pitches[0] % 12 and o not in s.pitches), None)
                if ring is not None and len(s.pitches) > 1:
                    inst.add_note(bus, self.sr, t + 0.01, s.beats * pulse, ring, level * 0.07, 0.3, f"{seed}:ring:{t:.3f}", None, release_sec=0.09)

    def play_bar(self, strokes: list[Stroke], bar_start: float, pulse: float, tone: str, bar_seconds: float, *, double: bool, level: float = 1.0) -> None:
        bus = self._bus(tone)
        self.spans.setdefault(tone, []).append((int(bar_start * self.sr), int((bar_start + bar_seconds) * self.sr)))
        seed = self.plan.seed
        for s in strokes:
            # A player sits slightly behind or ahead, a little differently on each stroke.
            t = bar_start + s.beat * pulse + (_roll(seed, "t", bar_start, s.beat) - 0.5) * 0.01
            self._play(bus, s, t, pulse, level, "a")
            if double and s.kind != "dead":
                # The same part again: a second performance, never quite together.
                self._play(bus, s, t + 0.007 + 0.014 * _roll(seed, "d", bar_start, s.beat), pulse, level * 0.8, "b")

    def finish(self) -> np.ndarray:
        """Each tone's spans through its own amp setting. A long song's memory stays near one span's length."""
        out = np.zeros(self.length, dtype=np.float32)
        tail = int(_TAIL_SEC * self.sr)
        for tone, spans in self.spans.items():
            bus = self.buses[tone]
            merged: list[list[int]] = []
            for a, b in sorted(spans):
                if merged and a <= merged[-1][1] + tail:
                    merged[-1][1] = max(merged[-1][1], b)
                else:
                    merged.append([a, b])
            for a, b in merged:
                a, b = max(0, a), min(self.length, b + tail)
                if b > a and bus[a:b].any():
                    out[a:b] += amplify(bus[a:b], tone, self.sr)
        self.buses.clear()
        return out


def start_part(length: int, sr: int, chords, chord_notes, bpm: float, seed: str) -> GuitarPart:
    return GuitarPart(int(length), int(sr), choose_plan(list(chords), chord_notes, float(bpm), str(seed)))


def add_bar(part: GuitarPart, chord, next_chord, role, texture, bar_in_section, is_hit, section_edge, bar_start, pulse, bar_seconds, intensity, bar_index, *, segments, chord_notes) -> None:
    """One bar, in the tone its section calls for."""
    quiet = texture is not None and (texture.drums in ("hats", "minimal") or texture.comp == "sustain")
    tone = section_tone(part.plan, role, quiet)
    chorus = role in CHORUS_ROLES or (texture is not None and texture.comp == "full")
    if chorus and not quiet:
        tone = part.plan.tones[1]
    if is_hit:
        strokes = [Stroke(0.0, 1.0, chord_shape(chord_notes(chord)).wide, 1.0)]
    else:
        strokes = guitar_bar(segments, part.plan, tone=tone, chord_notes=chord_notes, next_chord=next_chord,
                             phrase_end=int(bar_in_section) % 4 == 3, section_end=bool(section_edge), bar_index=bar_index, chorus=chorus)
    part.play_bar(strokes, bar_start, pulse, tone, bar_seconds, double=chorus and tone in {"overdrive", "distorted"}, level=float(np.clip(intensity, 0.5, 1.2)))


assert all(t in TONES for pair in PART_TONES.values() for tones in pair for t in tones)

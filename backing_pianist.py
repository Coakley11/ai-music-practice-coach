"""A pianist for the Backing track: decides what to play, bar by bar, like a person accompanying a band.

Off by default: today's comping plays unless ``MUSIC_PIANO_V2`` is set, to ``varied`` for this playing on
the existing piano voice, or to ``recorded`` for this playing on a recorded Steinway.

The pianist plays in phrases of uneven length. Each phrase has an idea, a rhythmic cell from the style's
own vocabulary, which is repeated with small changes: a hit dropped for space, a chord pushed ahead of the
bar, a different voicing or register, a broken chord, a passing figure into the next phrase. Sections set
how much is played, and nothing happens on a fixed schedule. Every note is a chord tone, an extension that
suits the chord, or a passing note in a short figure that resolves onto a chord tone.
"""

from __future__ import annotations

import os
import pathlib
import zlib
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

import backing_keys_voice as _kv
from backing_sampled_instrument import SampledInstrument

PIANO_PACK = pathlib.Path(__file__).resolve().parent / "assets" / "instruments" / "grand_piano"
RECORDED_LEVEL = 4.0
FULL_ROLES = frozenset({"chorus", "refrain", "interlude", "solo", "outro"})
# Where each style's hands live: (right hand's floor, ceiling under a melody, ceiling when no melody plays).
REGISTERS = {
    "Jazz swing": (52, 74, 79),  # above the walking bass, under the soloist
    "Blues groove": (50, 76, 84),  # figures can sing up high between phrases
    "Pop groove": (48, 76, 81),
    "Pop": (48, 76, 81),
    "Rock groove": (52, 77, 84),
    "Funk groove": (55, 77, 82),
    "Soul": (52, 76, 81),
    "Soul groove": (52, 76, 81),
    "Ballad": (48, 77, 84),  # a wide, open instrument
    "Jewish ballad": (48, 77, 84),
    "Bossa nova": (52, 72, 76),  # close and understated
}
_DEFAULT_REGISTER = (48, 76, 81)
# Where the left hand's bass notes may go. The ballad pianist carries the low end himself.
LEFT_HAND = {"Ballad": (36, 50), "Jewish ballad": (36, 50), "Pop groove": (43, 55), "Pop": (43, 55), "Blues groove": (45, 55)}
_DEFAULT_LEFT_HAND = (48, 55)
# Below these notes, an interval this small turns to mud (the arranger's low-interval limits).
LOW_INTERVAL_LIMITS = {1: 58, 2: 55, 3: 50, 4: 47, 5: 45, 6: 45, 7: 36}
GUITAR_FLOOR = 60  # the guitar has the middle: the piano answers above it
NO_MELODY_ROLES = frozenset({"intro", "interlude", "solo", "outro"})


def mode() -> str:
    raw = str(os.environ.get("MUSIC_PIANO_V2") or "").strip().lower()
    if raw in {"", "0", "off", "false", "no"}:
        return ""
    if raw == "recorded" and (PIANO_PACK / "manifest.json").is_file():
        return "recorded"
    return "varied"


def piano_renderer_tag() -> str:
    """Part of saved audio's signature, so takes from another pianist are never replayed as this one."""
    m = mode()
    return f"+pianist1-{m}" if m else ""


@lru_cache(maxsize=1)
def _grand() -> SampledInstrument:
    return SampledInstrument(PIANO_PACK)


def _roll(*parts) -> float:
    return (zlib.crc32(":".join(str(p) for p in parts).encode("utf-8")) % 100000) / 100000.0


# --- Harmony. -------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Harmony:
    root: int
    bass: int  # the written bass note of a slash chord, or the root
    third: int | None
    fifth: int | None
    seventh: int | None
    written: tuple[int, ...]  # every pitch class the chart's symbol names
    extensions: tuple[int, ...]  # pitch classes that suit it and are not in the symbol

    @property
    def allowed(self) -> frozenset:
        return frozenset(self.written) | frozenset(self.extensions)

    @property
    def guides(self) -> tuple[int, ...]:
        return tuple(p for p in (self.third, self.seventh) if p is not None)


def harmony_of(chord: str, chord_notes, bass_note, *, colour: bool = True) -> Harmony:
    notes = list(chord_notes(chord))
    root = notes[0] % 12
    steps = [(n - notes[0]) % 12 for n in notes]
    if str(chord).split("/")[0].endswith("5") and "b5" not in str(chord) and "#5" not in str(chord):
        steps = [0, 7]  # a power chord has no third, whatever else the chart's note list holds
    pcs = set(steps)
    third = 3 if 3 in pcs and 4 not in pcs else 4 if 4 in pcs else 5 if 5 in pcs else 2 if 2 in pcs else None
    fifth = 7 if 7 in pcs else 6 if 6 in pcs else 8 if 8 in pcs else None
    seventh = 10 if 10 in pcs else 11 if 11 in pcs else 9 if 9 in pcs and len(notes) >= 4 else None
    extra: list[int] = []
    if colour and third in (3, 4) and fifth in (6, 7):
        altered = bool(pcs & {1, 3 if third == 4 else 99, 6 if fifth == 7 else 99, 8})
        if fifth == 6 and third == 3:
            extra = [5] if seventh == 10 else []  # half diminished: the 11th; a diminished chord has none
        elif third == 3:
            extra = [2, 5] if seventh == 10 else [2]
        elif seventh == 10:
            extra = ([] if altered else [2, 9])  # dominant: the 9th and 13th, unless the chart alters it
        elif not altered:
            extra = [2, 9] if seventh == 11 else [2]
    to_pc = lambda s: None if s is None else (root + s) % 12
    return Harmony(
        root, bass_note(chord) % 12, to_pc(third), to_pc(fifth), to_pc(seventh),
        tuple(dict.fromkeys((root + s) % 12 for s in steps)),
        tuple((root + s) % 12 for s in extra if s not in pcs),
    )


def stack(pcs: list[int], bottom: int) -> list[int]:
    """The pitch classes in the order given, each the next one above the last, starting at or above ``bottom``."""
    out: list[int] = []
    at = bottom - 1
    for pc in pcs:
        at += 1 + ((pc - at - 1) % 12)
        out.append(at)
    return out


def muddy(notes: list[int]) -> int:
    """How many neighbouring notes sit closer than the low-interval limits allow."""
    bad = 0
    for a, b in zip(notes, notes[1:]):
        limit = LOW_INTERVAL_LIMITS.get(b - a)
        if limit is not None and a < limit:
            bad += 1
    return bad


def voicing_choices(h: Harmony, kind: str) -> list[list[int]]:
    """Orderings of pitch classes to voice this chord, low to high."""
    rootless = [p for p in (h.third, h.fifth, h.seventh) if p is not None]
    ext = list(h.extensions)
    if kind == "rootless" and h.third is not None:
        a = [h.third, h.seventh if h.seventh is not None else h.fifth or h.root]
        if ext:
            a = [h.third, ext[-1], a[1], ext[0]] if len(ext) >= 2 else [h.third, ext[0], a[1]]
        else:
            a = rootless
        return [a, a[1:] + a[:1], [p for p in a[2:]] + a[:2]]
    if kind == "shell":
        guides = list(h.guides) or [h.root, h.fifth if h.fifth is not None else h.root]
        return [guides, guides[::-1]]
    if kind == "open":
        third = h.third if h.third is not None else h.root
        five = h.fifth if h.fifth is not None else h.root
        return [[h.root, five, third], [h.root, third, five], [five, h.root, third], [third, five, h.root]]
    notes = [p for p in h.written]
    return [notes[i:] + notes[:i] for i in range(len(notes))]


# --- The vocabulary. A cell is (beat, beats held, voice, accent). ----------------------------------------
# Voices: C whole chord, S guide tones, T upper notes only, R rolled chord, L left-hand bass note,
# N the next chord pushed ahead of the bar, A<n> one note of a broken chord.

_JAZZ = (
    ((0.0, 0.62, "C", 1.0), (1.5, 0.40, "C", 0.84)),  # Charleston
    ((1.5, 0.36, "C", 0.86), (3.5, 0.40, "N", 0.90)),
    ((1.0, 0.34, "S", 0.74), (3.0, 0.34, "S", 0.80)),
    ((0.5, 0.34, "C", 0.80), (2.0, 0.66, "C", 0.92)),
    ((2.5, 0.42, "C", 0.86),),
    ((0.0, 0.95, "C", 0.96), (2.5, 0.34, "S", 0.78), (3.5, 0.40, "N", 0.84)),
    ((1.5, 0.34, "S", 0.78), (2.5, 0.34, "C", 0.84)),
)
_BLUES = (
    ((0.0, 0.8, "C", 1.0), (1.5, 0.45, "C", 0.84), (3.0, 0.45, "T", 0.78)),
    ((1.0, 0.40, "C", 0.94), (3.0, 0.40, "C", 0.94)),
    ((0.0, 1.4, "C", 0.96), (2.5, 0.6, "T", 0.80)),
    ((0.5, 0.40, "T", 0.74), (1.0, 0.45, "C", 0.90), (2.5, 0.45, "T", 0.76), (3.0, 0.5, "C", 0.88)),
    ((0.0, 0.42, "C", 1.0), (0.5, 0.3, "T", 0.68), (1.0, 0.42, "C", 0.88), (1.5, 0.3, "T", 0.68), (2.0, 0.42, "C", 0.92), (2.5, 0.3, "T", 0.68), (3.0, 0.42, "C", 0.88), (3.5, 0.3, "T", 0.68)),
)
_POP = (
    ((0.0, 1.0, "L", 0.92), (0.5, 0.6, "A1", 0.62), (1.0, 0.6, "A2", 0.70), (1.5, 0.6, "A3", 0.62), (2.0, 1.0, "L", 0.84), (2.5, 0.6, "A2", 0.62), (3.0, 0.6, "A3", 0.70), (3.5, 0.6, "A1", 0.60)),
    ((0.0, 3.9, "R", 0.92),),
    ((0.0, 1.4, "C", 1.0), (1.5, 1.0, "C", 0.80), (3.0, 0.9, "C", 0.82)),
    ((0.0, 0.9, "C", 0.96), (1.0, 0.9, "C", 0.72), (2.0, 0.9, "C", 0.84), (3.0, 0.9, "C", 0.72)),
    ((0.0, 1.9, "C", 0.96), (2.5, 1.4, "C", 0.82)),
    ((0.0, 1.5, "L", 0.90), (1.0, 0.5, "A2", 0.66), (1.5, 0.5, "A3", 0.66), (2.0, 1.9, "T", 0.80), (3.5, 0.4, "A1", 0.60)),
    ((0.0, 1.0, "C", 0.94), (1.5, 0.45, "T", 0.70), (2.0, 1.0, "C", 0.86), (3.5, 0.45, "T", 0.68)),
    ((0.0, 0.9, "L", 0.86), (0.5, 0.5, "A1", 0.60), (1.0, 0.5, "A3", 0.66), (1.5, 0.5, "A2", 0.60), (2.0, 0.9, "T", 0.78), (3.0, 0.9, "T", 0.70)),
)
_BALLAD = (
    ((0.0, 3.9, "L", 0.90), (0.5, 1.5, "A1", 0.58), (1.0, 1.5, "A2", 0.66), (1.5, 1.5, "A3", 0.60), (2.0, 1.5, "A4", 0.70), (3.0, 0.9, "A2", 0.62)),
    ((0.0, 3.9, "R", 0.90),),
    ((0.0, 1.9, "R", 0.92), (2.0, 1.9, "R", 0.76)),
    ((0.0, 3.9, "L", 0.86), (1.0, 2.9, "C", 0.68), (3.0, 0.9, "T", 0.60)),
    ((0.0, 2.9, "L", 0.88), (0.5, 1.0, "A2", 0.60), (1.0, 1.0, "A3", 0.66), (1.5, 1.4, "A4", 0.70), (3.0, 0.9, "T", 0.62)),
)
_ROCK = (
    ((0.0, 0.42, "C", 1.0), (1.5, 0.3, "T", 0.74), (2.5, 0.3, "T", 0.78)),
    ((1.5, 0.3, "T", 0.74), (3.5, 0.4, "N", 0.84)),
    ((0.0, 0.40, "C", 0.96), (1.0, 0.36, "C", 0.82), (2.0, 0.40, "C", 0.92), (3.0, 0.36, "C", 0.82)),
    ((0.5, 0.26, "T", 0.70), (1.0, 0.26, "T", 0.74), (2.5, 0.26, "T", 0.70), (3.0, 0.26, "T", 0.76)),
    ((0.0, 1.4, "C", 0.92), (3.0, 0.8, "T", 0.74)),
)
_FUNK = (
    ((0.0, 0.2, "C", 1.0), (0.75, 0.14, "S", 0.70), (1.75, 0.14, "S", 0.70), (2.5, 0.2, "C", 0.90)),
    ((0.5, 0.18, "C", 0.84), (1.5, 0.18, "S", 0.72), (3.25, 0.18, "C", 0.84)),
    ((0.0, 0.22, "C", 0.96), (2.0, 0.14, "S", 0.66), (2.75, 0.18, "C", 0.84), (3.5, 0.14, "S", 0.68)),
    ((1.0, 0.18, "C", 0.90), (2.5, 0.18, "C", 0.84)),
)
_SOUL = (
    ((0.0, 1.0, "C", 0.96), (1.5, 0.5, "S", 0.70), (2.5, 0.5, "C", 0.84), (3.5, 0.5, "N", 0.76)),
    ((0.5, 0.4, "S", 0.68), (1.5, 0.6, "C", 0.86), (3.0, 0.9, "C", 0.84)),
    ((0.0, 1.9, "C", 0.92), (2.5, 0.5, "S", 0.70), (3.25, 0.4, "S", 0.66)),
    ((0.0, 0.5, "C", 0.94), (0.75, 0.25, "S", 0.64), (2.0, 1.4, "C", 0.84)),
)
_BOSSA = (
    ((0.0, 0.6, "C", 0.90), (1.5, 0.5, "C", 0.74), (3.0, 0.5, "C", 0.76)),
    ((0.0, 0.6, "S", 0.84), (2.5, 0.6, "C", 0.78)),
    ((1.0, 0.5, "S", 0.72), (2.5, 0.6, "C", 0.78)),
    ((0.0, 1.4, "S", 0.80), (3.5, 0.4, "N", 0.70)),
)


@dataclass(frozen=True)
class StyleHands:
    ideas: tuple
    voicing: str  # how the right hand builds chords
    centre: int  # where the hands sit
    colour: bool  # extensions beyond the chart
    bars: tuple[int, ...]  # phrase lengths to choose from
    space: float  # chance of leaving a hit out, for air
    rest_bar: float  # chance of a bar of almost nothing
    fill: float  # chance of a figure at a phrase's end
    push: float  # chance of pushing the next chord ahead of the bar
    velocity: float  # how hard this style plays
    sparse_ideas: tuple[int, ...]  # the quieter ideas, for verses
    pedal: bool = False
    pickup: float = 0.0  # chance of one lone note leading into the next bar


HANDS: dict[str, StyleHands] = {
    "Jazz swing": StyleHands(_JAZZ, "rootless", 62, True, (2, 3, 4, 2), 0.14, 0.07, 0.22, 0.20, 0.56, (0, 1, 2, 4, 6)),
    "Blues groove": StyleHands(_BLUES, "chord", 63, False, (2, 4, 3, 2), 0.10, 0.03, 0.42, 0.12, 0.66, (0, 1, 2, 3)),
    "Pop groove": StyleHands(_POP, "chord", 62, True, (4, 2, 3, 4), 0.06, 0.0, 0.20, 0.10, 0.60, (1, 2, 3, 4, 5), True, 0.22),
    "Rock groove": StyleHands(_ROCK, "chord", 64, False, (2, 4, 3), 0.12, 0.05, 0.14, 0.12, 0.70, (0, 1, 3)),
    "Funk groove": StyleHands(_FUNK, "rootless", 65, True, (2, 2, 3, 4), 0.14, 0.05, 0.08, 0.04, 0.66, (0, 1, 3)),
    "Ballad": StyleHands(_BALLAD, "open", 60, True, (4, 2, 3), 0.03, 0.0, 0.26, 0.04, 0.54, (1, 2, 3, 4), True, 0.15),
    "Bossa nova": StyleHands(_BOSSA, "rootless", 62, True, (2, 4, 3), 0.14, 0.05, 0.08, 0.08, 0.50, (0, 1, 2, 3)),
}
# How a phrase stays alive: (chance of a contrasting bar, of moving one hit by an eighth, of an answering hit).
_LIFE = {
    "Jazz swing": (0.20, 0.42, 0.22),
    "Blues groove": (0.18, 0.28, 0.32),
    "Pop groove": (0.26, 0.22, 0.22),
    "Pop": (0.26, 0.22, 0.22),
    "Rock groove": (0.20, 0.26, 0.18),
    "Funk groove": (0.20, 0.30, 0.16),
    "Soul": (0.22, 0.34, 0.24),
    "Soul groove": (0.22, 0.34, 0.24),
    "Ballad": (0.24, 0.10, 0.20),
    "Jewish ballad": (0.24, 0.10, 0.20),
    "Bossa nova": (0.14, 0.18, 0.10),
}
_SPARSE_STYLES = frozenset({"Jazz swing", "Funk groove", "Soul", "Soul groove", "Bossa nova"})
# Broken-chord contours: rising, rocking, falling, wide.
_CONTOURS = ((0, 1, 2, 3), (0, 2, 1, 3), (0, 3, 2, 1), (0, 2, 3, 1))
HANDS["Pop"] = HANDS["Pop groove"]
HANDS["Soul groove"] = HANDS["Soul"] = StyleHands(_SOUL, "rootless", 62, True, (2, 3, 4), 0.12, 0.04, 0.2, 0.15, 0.60, (0, 1, 2))
HANDS["Jewish ballad"] = HANDS["Ballad"]
_FALLBACK = HANDS["Pop groove"]


@dataclass(frozen=True)
class Hit:
    beat: float
    beats: float
    notes: tuple[int, ...]  # low to high
    velocity: float
    kind: str = "chord"  # "chord", "bass", "broken", "figure"
    roll: float = 0.0  # seconds between notes of a rolled chord
    passing: bool = False  # a figure's note outside the chord


class Pianist:
    """One player for one song. Call ``bar`` in order; the same song always plays the same way."""

    def __init__(self, style: str, seed, *, has_guitar: bool = False, level: str = "Intermediate", chord_notes=None, bass_note=None) -> None:
        self.style = style
        self.seed = str(seed)
        self.hands = HANDS.get(style, _FALLBACK)
        self.has_guitar = has_guitar
        self.chord_notes = chord_notes
        self.bass_note = bass_note
        self.simple = str(level).lower().startswith("beg")
        self.prev: list[int] = []
        self.phrase_left = 0
        self.phrase_no = 0
        self.idea = 0
        self.recent: list[int] = []
        self.arc = 0.0
        self.register = 0
        self.filled_last = False
        self.pool: list[int] = []
        self.floor, self.with_melody, self.without_melody = REGISTERS.get(style, _DEFAULT_REGISTER)
        if has_guitar:
            self.floor = max(self.floor, GUITAR_FLOOR)
        self.ceiling = self.with_melody
        self.full = False
        # A song's own centre: one pianist likes to sit a little higher or lower than another.
        self.song_centre = int(round((_roll(self.seed, "centre") - 0.5) * 4.0))
        self.contour = _CONTOURS[0]

    def _h(self, chord: str) -> Harmony:
        return harmony_of(chord, self.chord_notes, self.bass_note, colour=self.hands.colour and not self.simple)

    def _new_phrase(self, role_full: bool, bar: int) -> None:
        self.phrase_no += 1
        r = _roll(self.seed, "phrase", self.phrase_no, bar)
        lengths = self.hands.bars
        self.phrase_left = lengths[int(r * len(lengths)) % len(lengths)]
        pool = list(range(len(self.hands.ideas))) if role_full else list(self.hands.sparse_ideas)
        pool = [p for p in pool if p < len(self.hands.ideas)]
        self.pool = pool
        self.contour = _CONTOURS[int(_roll(self.seed, "contour", self.phrase_no) * len(_CONTOURS)) % len(_CONTOURS)]
        fresh = [p for p in pool if p not in self.recent[-2:]] or pool
        self.idea = fresh[int(_roll(self.seed, "idea", self.phrase_no) * len(fresh)) % len(fresh)]
        self.recent.append(self.idea)
        self.arc = 0.92 + 0.16 * _roll(self.seed, "arc", self.phrase_no)
        # The hands move around the keyboard from phrase to phrase, a little higher in full sections.
        step = _roll(self.seed, "reg", self.phrase_no)
        self.register = (-2 if step < 0.28 else 2 if step > 0.72 else 0) + (2 if role_full else 0)

    def _vary(self, cells: list, tag) -> list:
        """A person does not play one bar twice: sometimes a contrasting bar, a hit moved by an eighth, an answer."""
        change, displace, answer = _LIFE.get(self.style, (0.2, 0.25, 0.2))
        if self.pool and _roll(self.seed, "bbar", tag) < change:
            others = [p for p in self.pool if p != self.idea] or self.pool
            cells = list(self.hands.ideas[others[int(_roll(self.seed, "bpick", tag) * len(others)) % len(others)]])
        if _roll(self.seed, "move", tag) < displace:
            movable = [i for i, c in enumerate(cells) if c[2] in {"C", "S", "T"} and c[0] > 0.0]
            if movable:
                i = movable[int(_roll(self.seed, "movei", tag) * len(movable)) % len(movable)]
                beat, held, voice, accent = cells[i]
                to = beat + (0.5 if _roll(self.seed, "moved", tag) < 0.5 else -0.5)
                if 0.5 <= to <= 3.5 and not any(abs(c[0] - to) < 0.3 for j, c in enumerate(cells) if j != i):
                    cells = list(cells)
                    cells[i] = (to, min(held, 4.0 - to), voice, accent * 0.96)
        if _roll(self.seed, "answer", tag) < answer:
            free = [b for b in (1.5, 2.0, 2.5, 3.0, 3.5) if not any(abs(c[0] - b) < 0.45 for c in cells)]
            if free:
                at = free[int(_roll(self.seed, "answerat", tag) * len(free)) % len(free)]
                cells = list(cells) + [(at, 0.34, "T" if _roll(self.seed, "answerv", tag) < 0.6 else "S", 0.64)]
        return sorted(cells, key=lambda c: c[0])

    def _place(self, pcs: list[int], centre: int, *, tag) -> list[int]:
        """A voicing near the last one, with the top under the melody's space; not always the same answer."""
        options = []
        floor = self.floor
        span = range(max(floor, centre - 10), centre + 8)
        for bottom in span:
            placed = stack(pcs, bottom)
            if placed[-1] > self.ceiling or placed[0] < floor:
                continue
            if placed[0] != bottom:
                continue
            if self.prev:
                move = sum(min(abs(n - p) for p in self.prev) for n in placed) / len(placed)
            else:
                move = abs(sum(placed) / len(placed) - centre)
            cost = move + 0.25 * abs(sum(placed) / len(placed) - centre) + 12.0 * muddy(placed)
            options.append((cost, placed))
        if not options:
            placed = stack(pcs, floor)
            return [n - 12 if n > self.ceiling and n - 12 >= floor else n for n in placed]
        options.sort(key=lambda o: o[0])
        return options[0][1]

    def _chord_voicing(self, h: Harmony, voice: str, tag) -> list[int]:
        hands = self.hands
        centre = hands.centre + self.register + self.song_centre
        kind = "shell" if voice == "S" else hands.voicing
        if self.simple and kind == "rootless":
            kind = "chord"
        choices = voicing_choices(h, kind)
        best: tuple[float, list[int]] | None = None
        pick = _roll(self.seed, "voice", tag)
        # Try each ordering; usually the smoothest wins, sometimes the next best, so repeats change colour.
        ranked = []
        for pcs in choices:
            placed = self._place(list(pcs), centre, tag=tag)
            move = sum(min(abs(n - p) for p in self.prev) for n in placed) / len(placed) if self.prev else 0.0
            ranked.append((move, placed))
        ranked.sort(key=lambda r: r[0])
        slot = 2 if pick < 0.16 else 1 if pick < 0.44 else 0
        notes = list(ranked[min(slot, len(ranked) - 1)][1])
        if muddy(notes):
            notes = list(min(ranked, key=lambda r: (muddy(r[1]), r[0]))[1])
        floor = self.floor
        r = _roll(self.seed, "shape", tag)
        if voice in {"C", "R"} and h.extensions and hands.colour and r < 0.30 and kind != "rootless" and h.third in {n % 12 for n in notes}:
            # A colour on top, when the chord welcomes one.
            extra = stack([notes[-1] % 12, h.extensions[0]], notes[-1])[-1]
            if extra <= self.ceiling:
                notes = notes + [extra]
        elif voice in {"C", "R"} and 0.30 <= r < 0.50 and notes[0] + 12 <= self.ceiling and notes[0] + 12 not in notes and len(notes) <= 4:
            # A firmer chord with its bottom note doubled above.
            notes = sorted(notes + [notes[0] + 12])
        elif voice in {"C", "R"} and 0.50 <= r < 0.62 and len(notes) >= 3 and notes[-2] - 12 >= floor:
            # Spread: the second note from the top drops an octave, where it stays clear.
            spread = sorted(notes[:-2] + [notes[-2] - 12] + notes[-1:])
            if not muddy(spread):
                notes = spread
        if voice == "T":
            notes = notes[-2:]
            if _roll(self.seed, "tup", tag) < 0.22 and notes[-1] + 12 <= self.ceiling:
                notes = [n + 12 for n in notes]
        self.prev = notes
        return notes

    def _lh(self, h: Harmony) -> tuple[int, ...]:
        lowest, highest = LEFT_HAND.get(self.style, _DEFAULT_LEFT_HAND)
        low = lowest + ((h.bass - lowest) % 12)
        # Always the chord's own bass note: past the top of the range, the octave below or this one,
        # whichever sits nearer the range (a range narrower than an octave cannot hold every note).
        if low > highest and lowest - (low - 12) <= low - highest:
            low -= 12
        # In a full section a big left hand doubles the note at the octave, while it stays clear.
        return (low, low + 12) if self.full and low + 12 <= highest + 10 else (low,)

    def _broken(self, h: Harmony, tag) -> list[int]:
        """The notes a broken chord climbs through, under the melody's space."""
        tones = [h.root, h.fifth if h.fifth is not None else h.root, h.third if h.third is not None else h.root]
        if h.seventh is not None and _roll(self.seed, "b7", tag) < 0.5:
            tones.append(h.seventh)
        elif h.extensions and _roll(self.seed, "b9", tag) < 0.25:
            tones.append(h.extensions[0])
        else:
            tones.append(h.root)
        placed = stack(tones, max(self.floor, self.hands.centre - 9) + self.register)
        while placed[-1] > self.ceiling:
            placed = [n - 12 for n in placed]
        return placed

    def _figure(self, h: Harmony, target: Harmony | None, start: float, end: float, tag) -> list[Hit]:
        """A short line into what comes next: chord tones on strong places, passing notes between, landing on a chord tone."""
        goal_pcs = list((target or h).written)
        top = min(self.prev) + 6 if self.prev else self.hands.centre + 4
        top = int(np.clip(top, max(56, self.floor + 4), self.ceiling - 2))
        goal = min((top - 6 + i for i in range(13) if (top - 6 + i) % 12 in goal_pcs), key=lambda m: abs(m - top))
        n = 3 if _roll(self.seed, "fign", tag) < 0.6 else 4
        step = (end - start) / n
        direction = -1 if _roll(self.seed, "figd", tag) < 0.55 else 1
        line = [goal]
        for i in range(n - 1):
            m = line[-1] - direction * (1 if i == 0 and _roll(self.seed, "figc", tag) < 0.4 else 2)
            line.append(m)
        line = line[::-1]
        while max(line) > self.ceiling:
            line = [m - 12 for m in line]
        chord_tones = set(h.written)
        out = []
        for i, m in enumerate(line):
            if i < len(line) - 1 and i % 2 == 0 and m % 12 not in chord_tones:
                m = min((m + d for d in (-2, -1, 1, 2) if (m + d) % 12 in chord_tones), key=lambda x: abs(x - m), default=m)
            out.append(Hit(start + i * step, step * 0.95, (m,), 0.58 + 0.05 * i, "figure", passing=m % 12 not in (h.allowed | set(goal_pcs))))
        return out

    def _turnaround(self, h: Harmony) -> list[Hit]:
        """The classic blues turnaround on the home chord: the root held on top, a line falling under it to the fifth."""
        top = 60 + ((h.root - 60) % 12)
        out = []
        for i, step in enumerate((10, 9, 8, 7)):
            low = top - 12 + step
            passing = (low % 12) not in h.allowed
            out.append(Hit(i * 0.5, 0.46, (low, top), 0.72 + 0.03 * i, "figure", passing=passing))
        out.append(Hit(2.0, 0.9, (top - 12 + 7, top), 0.82, "figure"))
        return out

    def bar(self, segments, next_chord, *, role: str, quiet: bool, bar_in_section: int, section_end: bool, bar_index: int, pulses_per_bar: int, intensity: float = 1.0, section_bars: int = 0) -> list[Hit]:
        full = role in FULL_ROLES and not quiet
        self.full = full
        # With no melody playing, the hands have more of the keyboard.
        self.ceiling = self.without_melody if role in NO_MELODY_ROLES else self.with_melody
        if self.phrase_left <= 0:
            self._new_phrase(full, bar_index)
        self.phrase_left -= 1
        ending_phrase = self.phrase_left == 0 or section_end
        hits: list[Hit] = []
        chords = [s for s in segments if s[2] is not None]
        if not chords:
            self.phrase_left = 0
            return hits
        hands = self.hands
        if pulses_per_bar != 4:
            return self._other_meter(segments, full, bar_index)
        tag0 = (self.phrase_no, bar_index)
        if (
            self.style == "Blues groove" and section_bars and section_bars % 12 == 0 and bar_in_section % 12 == 10
            and len(chords) == 1 and not quiet and not self.simple and _roll(self.seed, "turn", bar_index) < 0.6
        ):
            self.filled_last = True
            return self._turnaround(self._h(chords[0][2]))
        cells = list(hands.ideas[self.idea])
        if not quiet and not self.simple:
            cells = self._vary(cells, tag0)
        if quiet:
            # A quiet texture holds its chord.
            cells = [(0.0, 3.9, "R", 0.72)]
        rest = not ending_phrase and _roll(self.seed, "rest", tag0) < hands.rest_bar * (0.5 if full else 1.0)
        if rest:
            cells = [c for c in cells if c[0] >= 2.5][:1]
        figure_at = None
        if ending_phrase and next_chord and not self.filled_last and not quiet and _roll(self.seed, "fig", tag0) < hands.fill * (1.5 if section_end else 1.0):
            figure_at = 2.5
        self.filled_last = figure_at is not None
        for k, (beat, held, voice, accent) in enumerate(cells):
            if figure_at is not None and beat >= figure_at:
                continue
            # A hit left out for air, never the first of a bar that opens the phrase.
            # Styles that flow keep their downbeat; only the sparse ones may leave it out.
            keeps_downbeat = beat == 0.0 and self.style not in _SPARSE_STYLES
            if (k > 0 or self.phrase_left > 0) and not keeps_downbeat and voice not in {"L", "R"} and not voice.startswith("A"):
                keep = 1.0 - hands.space * (0.6 if full else 1.0)
                if _roll(self.seed, "space", tag0, k) > keep:
                    continue
            if self.simple and accent < 0.82 and k > 0:
                continue
            seg = next((s for s in segments if s[0] <= beat < s[1]), None)
            if seg is None or seg[2] is None:
                continue
            end = seg[1]
            chord = seg[2]
            push = False
            at = beat
            if voice == "N":
                if next_chord is None or beat + held < 4.0 and seg is not segments[-1]:
                    voice = "C"
                else:
                    chord, push, voice = next_chord, True, "C"
            elif voice == "C" and beat >= 3.5 and next_chord and _roll(self.seed, "push", tag0, k) < hands.push:
                chord, push = next_chord, True
            limit = (4.0 if push else end) - at
            held = min(held, limit) if not push else min(held, 1.0)
            # Note lengths breathe: a touch longer or shorter each time.
            held = max(0.08, held * (0.86 + 0.28 * _roll(self.seed, "len", tag0, k)))
            if not push:
                held = min(held, end - at)
            h = self._h(chord)
            vel = accent * (0.97 + 0.08 * _roll(self.seed, "vel", tag0, k)) * self.arc * (1.08 if full else 0.94)
            if voice == "L":
                hits.append(Hit(at, held, self._lh(h), vel * 0.96, "bass"))
            elif voice.startswith("A"):
                notes = self._broken(h, tag0)
                hits.append(Hit(at, held, (notes[self.contour[int(voice[1:]) % 4] % len(notes)],), vel, "broken"))
            elif voice == "R":
                notes = self._chord_voicing(h, "C", (tag0, k))
                hits.append(Hit(at, held, tuple(notes), vel, "chord", roll=0.018 + 0.016 * _roll(self.seed, "roll", tag0)))
            else:
                notes = self._chord_voicing(h, voice, (tag0, k))
                hits.append(Hit(at, held, tuple(notes), vel, "chord"))
        last_seg = segments[-1]
        if figure_at is None and not quiet and last_seg[2] is not None and hands.pickup > 0.0 and last_seg[1] - 3.5 > 0.25 and not self.simple:
            r = _roll(self.seed, "pickup", tag0)
            if r < hands.pickup and not any(x.beat >= 3.25 for x in hits):
                # One chord tone leading to the next bar, on its own, as a hand moves to the next chord.
                notes = self._broken(self._h(last_seg[2]), (tag0, "pu"))
                hits.append(Hit(3.5, 0.45, (notes[int(r * 97) % len(notes)],), 0.56 + 0.1 * r, "broken"))
        if figure_at is not None:
            seg = next((s for s in segments if s[0] <= figure_at < s[1]), None)
            if seg is not None and seg[2] is not None:
                hits += self._figure(self._h(seg[2]), self._h(next_chord), figure_at, 4.0, tag0)
        hits.sort(key=lambda x: x.beat)
        return self._state_quality(hits, segments)

    def _state_quality(self, hits: list[Hit], segments) -> list[Hit]:
        """Variety must never blur the harmony: wherever a chord plays, its third is heard, so major stays major."""
        out = list(hits)
        for start, end, chord in segments:
            if chord is None:
                continue
            h = self._h(chord)
            if h.third is None:
                continue
            inside = [i for i, x in enumerate(out) if start <= x.beat < end and x.kind != "figure"]
            # The third has to arrive early, not only in a quiet pickup on the way out.
            early = [i for i in inside if out[i].beat < start + 0.75 * (end - start)] or inside
            if not inside or any(h.third in {n % 12 for n in out[i].notes} for i in early):
                continue
            inside = early
            i = next((i for i in inside if out[i].kind == "chord"), inside[0])
            x = out[i]
            if x.kind == "bass":
                near = max(self.floor, x.notes[-1] + 3)
                third = near + ((h.third - near) % 12)
                out.insert(i + 1, Hit(x.beat + min(0.5, x.beats * 0.5), max(0.25, x.beats * 0.5), (third,), x.velocity * 0.72, "broken"))
                continue
            # The top note of the hit gives way to the third, as near to it as the hand allows.
            top = x.notes[-1]
            third = max((top - d for d in range(0, 12) if (top - d) % 12 == h.third), default=top)
            notes = tuple(sorted({*x.notes[:-1], third})) if len(x.notes) > 1 else (third,)
            out[i] = Hit(x.beat, x.beats, notes, x.velocity, x.kind, x.roll, x.passing)
        return out

    def _other_meter(self, segments, full: bool, bar_index: int) -> list[Hit]:
        """Other meters: a chord on each change, an answer later in the longer ones."""
        hits = []
        for i, (start, end, chord) in enumerate(segments):
            if chord is None:
                continue
            h = self._h(chord)
            span = end - start
            first = max(0.5, span * 0.9 if _roll(self.seed, "m", bar_index, i) < 0.4 else span * 0.45)
            notes = self._chord_voicing(h, "C", (bar_index, i))
            hits.append(Hit(start, min(first, span), tuple(notes), 0.86 * (1.06 if full else 0.94), "chord"))
            if first < span and span - first >= 0.5:
                notes = self._chord_voicing(h, "T", (bar_index, i, "b"))
                hits.append(Hit(start + first, span - first, tuple(notes), 0.68, "chord"))
        return self._state_quality(hits, segments)

    def perform(self, bus: np.ndarray, sr: int, hits: list[Hit], time_of, pulse: float, *, gain: float) -> None:
        """Play the hits. Each note is placed by a hand, so chords are never struck by a machine."""
        velocity = self.hands.velocity
        recorded = mode() == "recorded"
        if recorded:
            # The recording is quieter than the modelled voice; this keeps the keys balance inside its limits.
            gain *= RECORDED_LEVEL
        for hit in hits:
            t = time_of(hit.beat)
            vel = float(np.clip(velocity * hit.velocity, 0.08, 1.0))
            loud = gain * vel ** 1.5
            shape = _kv.voice_gains(list(hit.notes)) if len(hit.notes) > 1 else [1.0]
            # Sustained styles hold a pedal through a held chord, and arpeggio notes ring on.
            pedalled = self.hands.pedal or hit.kind == "broken"
            held = hit.beats * pulse * (1.25 if pedalled else 1.0)
            for i, midi in enumerate(hit.notes):
                r = _roll(self.seed, "hand", round(t, 4), midi)
                at = t + i * hit.roll + (r - 0.5) * 0.006
                note_vel = float(np.clip(vel * (0.95 + 0.10 * r), 0.05, 1.0))
                if recorded:
                    _grand().add_note(
                        bus, sr, at, max(0.04, held), int(midi), loud * shape[i], note_vel, f"{self.seed}:{at:.4f}:{midi}",
                        release_sec=0.09 if pedalled else 0.05, offset_sec=0.0012 * r, detune_cents=(r - 0.5) * 2.0,
                    )
                else:
                    _kv.add_piano_note(bus, sr, at, max(0.04, held), int(midi), loud * shape[i], note_vel)


def start(style: str, seed, *, has_guitar: bool, level: str, chord_notes, bass_note) -> Pianist:
    return Pianist(style, seed, has_guitar=has_guitar, level=level, chord_notes=chord_notes, bass_note=bass_note)

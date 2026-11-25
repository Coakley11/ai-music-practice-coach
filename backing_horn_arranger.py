"""Two horns playing as a front line behind a soloist: the Jazz quintet's trumpet and tenor sax.

Only runs when ``MUSIC_HORNS`` is on and both horns' packs are present (``backing_horns.available``); the
Jazz quartet's single tenor keeps its own guide-tone pad (``backing_audio._horn_background``).

A small-group horn section behind a soloist does not hold a chord for the whole tune. It plays a
background for a phrase, lays out for the next one, answers itself and sets up the next section. This
module writes that, phrase by phrase (four bars, or the song's own sections):

* ``rest``      - both horns lay out: room for the soloist.
* ``solo_pad``  - one horn holds the guide tones; the other rests.
* ``staggered`` - the tenor holds the guide tones, the trumpet enters above it two bars later.
* ``pad``       - both hold the chord in harmony (a third, sixth or tenth apart), with a swell.
* ``call``      - one horn plays a short figure, the other answers it two bars later (the same rhythm,
                  the contour turned over), and sometimes both close the phrase together.
* ``riff``      - a short figure harmonised for both horns, played, left, then played again on the new
                  chord: the classic background riff.
* ``hits``      - short harmonised shots, ending on a held chord.

The phrase's texture comes from the intensity (Light rests and pads, Heavy riffs and shots), the mood
(a mellow band holds and answers, a driving one riffs) and the level (a beginner gets more room). No
texture plays twice in a row, the horns lay out after a run of playing phrases, and the last phrase of a
section that leads into another ends on two shots that set the new section up. Every note sits in the
horn's background register (clear of the soloist's melody and the bass), the pair is voiced by
``backing_horns.section_voicing`` (neither horn on the root or the bass note), and the two horns are
humanised separately (the trumpet a hair ahead, the tenor a hair behind, a few ms of jitter each).
"""

from __future__ import annotations

import math
import random
import zlib
from dataclasses import dataclass, field, replace
from typing import Sequence

import backing_horns as bh

ARRANGER_VERSION = 1
TEXTURES = ("rest", "solo_pad", "staggered", "pad", "call", "riff", "hits")
PHRASE_BARS = 4

# Relative weights of each texture per intensity: Light leaves the most room, Heavy riffs and shoots.
_PALETTE: dict[str, dict[str, float]] = {
    "Light": {"rest": 4.0, "solo_pad": 3.0, "staggered": 2.0, "pad": 1.0, "call": 1.5},
    "Medium": {"rest": 2.0, "solo_pad": 1.0, "staggered": 2.0, "pad": 1.0, "call": 3.0, "riff": 2.0},
    "Heavy": {"rest": 1.0, "staggered": 1.0, "pad": 2.0, "call": 2.0, "riff": 3.0, "hits": 2.0},
}
# The longest run of phrases the horns play before they lay out for one.
_MAX_RUN = {"Light": 1, "Medium": 2, "Heavy": 3}
_RELAXED_MOODS = frozenset({"Mellow", "Relaxed", "Dreamy", "Dark"})
_DRIVING_MOODS = frozenset({"Energetic", "Gritty", "Bright"})
_BASE_VELOCITY = {"Light": 0.45, "Medium": 0.6, "Heavy": 0.75}
# Dynamics by texture (added to the base velocity): one horn alone is softer, shots are harder.
_TEXTURE_DYNAMIC = {"solo_pad": -0.06, "staggered": -0.02, "pad": 0.0, "call": 0.03, "riff": 0.05, "hits": 0.1}

# Figure rhythms within one bar: (onset beat, length in beats), 0-based beats of a 4/4 bar.
FIGURE_CELLS: tuple[tuple[tuple[float, float], ...], ...] = (
    ((0.5, 0.5), (1.0, 1.5)),
    ((1.5, 0.5), (2.0, 0.5), (2.5, 1.5)),
    ((0.0, 0.75), (1.0, 0.5), (1.5, 0.5), (2.0, 1.25)),
    ((2.0, 0.5), (2.5, 0.5), (3.0, 0.5), (3.5, 0.5)),
    ((0.5, 0.5), (1.5, 0.5), (2.0, 1.75)),
    ((0.0, 1.5), (1.5, 0.5), (2.5, 1.0)),
)
# Shots within one bar (onset beats); the phrase's last bar holds its final shot.
HIT_PATTERNS: tuple[tuple[float, ...], ...] = ((1.5, 3.0), (0.5, 2.0), (1.5, 2.5), (0.0, 1.5), (2.5, 3.5))
SETUP_BEATS = (2.5, 3.5)  # the "and" of 3 and of 4: two shots that push into the next section
HIT_SEC = 0.22  # how long a shot is held: short enough for the staccato recordings

# Humanising: where each horn sits against the beat and how much it wanders (seconds).
_SEAT_SEC = {"top": -0.004, "bottom": 0.006}
_JITTER_SEC = 0.006


@dataclass(frozen=True)
class ArrBar:
    """One bar of the take as the arranger sees it."""

    index: int
    start_sec: float
    beat_sec: float
    chords: tuple[tuple[str, float, float], ...]  # (chord, start beat, end beat) in the bar
    beats: float = 4.0
    bar_in_section: int = -1  # -1: the take has no section labels
    section_bars: int = 0

    def chord_at(self, beat: float) -> str:
        for chord, a, b in self.chords:
            if a - 1e-9 <= beat < b:
                return chord
        return self.chords[-1][0] if self.chords else ""


@dataclass
class Phrase:
    bars: list[ArrBar]
    texture: str = "rest"
    first_of_section: bool = False
    leads_into_section: bool = False  # the last phrase of a section another one follows
    last_of_take: bool = False
    caller: str = "top"  # which horn plays first in a call / solo pad
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Arrangement:
    top: str
    bottom: str
    notes: dict[str, list[bh.HornNote]]
    phrases: tuple[tuple[int, str], ...]  # (first bar index, texture) per phrase

    def describe(self) -> list[str]:
        return [f"bar {b + 1}: {t}" for b, t in self.phrases]


# --- Form ---------------------------------------------------------------------------------------------


def phrases_of(bars: Sequence[ArrBar], phrase_bars: int = PHRASE_BARS) -> list[Phrase]:
    """The take cut into phrases: every ``phrase_bars`` bars, restarting at each new section."""
    out: list[Phrase] = []
    cur: list[ArrBar] = []
    for bar in bars:
        labelled = bar.bar_in_section >= 0
        pos = bar.bar_in_section if labelled else bar.index
        if cur and (pos % phrase_bars == 0 or (labelled and bar.bar_in_section == 0)):
            out.append(Phrase(cur))
            cur = []
        cur.append(bar)
    if cur:
        out.append(Phrase(cur))
    for i, ph in enumerate(out):
        first, last = ph.bars[0], ph.bars[-1]
        ph.first_of_section = first.bar_in_section == 0 if first.bar_in_section >= 0 else i == 0
        ph.last_of_take = i == len(out) - 1
        ends_section = last.bar_in_section >= 0 and last.section_bars > 0 and last.bar_in_section == last.section_bars - 1
        ph.leads_into_section = ends_section and not ph.last_of_take
    return out


def choose_textures(
    phrases: Sequence[Phrase], *, intensity: str = "Medium", mood: str = "", level: str = "", seed: int = 0
) -> list[str]:
    """One texture per phrase (see the module doc): weighted by intensity / mood / level, never the same
    twice in a row, a rest after the longest run of playing phrases the intensity allows."""
    inten = intensity if intensity in _PALETTE else "Medium"
    weights = dict(_PALETTE[inten])
    if mood in _RELAXED_MOODS:
        for k, f in (("riff", 0.5), ("hits", 0.3), ("pad", 1.5), ("staggered", 1.5), ("solo_pad", 1.3)):
            if k in weights:
                weights[k] *= f
    elif mood in _DRIVING_MOODS:
        for k, f in (("riff", 1.5), ("hits", 1.5), ("solo_pad", 0.6)):
            if k in weights:
                weights[k] *= f
    if level == "Beginner":
        for k, f in (("call", 0.5), ("riff", 0.5), ("hits", 0.5), ("rest", 1.5)):
            if k in weights:
                weights[k] *= f
    elif level == "Advanced":
        for k, f in (("call", 1.3), ("riff", 1.3)):
            if k in weights:
                weights[k] *= f
    rng = random.Random(zlib.crc32(f"horn-textures:{seed}:{inten}:{mood}:{level}".encode()))
    out: list[str] = []
    run = 0
    for i, ph in enumerate(phrases):
        if i == 0:
            # The rhythm section sets the tune up; a heavy band brings the horns in at once, softly staggered.
            # A take of one or two phrases (a short vamp the player loops) cannot spend half of it resting.
            if len(phrases) <= 2:
                tex = "solo_pad" if inten == "Light" else "staggered"
            else:
                tex = "staggered" if inten == "Heavy" else "rest"
        elif run >= _MAX_RUN[inten] and out[-1] != "rest":
            tex = "rest"
        else:
            options = [(k, w) for k, w in weights.items() if k != out[-1] and w > 0]
            if out[-1] == "rest":
                options = [(k, w) for k, w in options if k != "rest"]
            total = sum(w for _, w in options)
            r = rng.random() * total
            tex = options[-1][0]
            for k, w in options:
                r -= w
                if r <= 0:
                    tex = k
                    break
        run = 0 if tex == "rest" else run + 1
        out.append(tex)
    return out


# --- Notes ----------------------------------------------------------------------------------------------


def _swung(beat: float, swing: float) -> float:
    """A written beat position with the off-beat 8th moved to ``swing`` of the beat (0.5 = straight)."""
    whole = math.floor(beat + 1e-9)
    frac = beat - whole
    if abs(frac - 0.5) < 1e-6:
        return whole + swing
    return beat


def _span_sec(bar: ArrBar, onset: float, length: float, swing: float) -> tuple[float, float]:
    a = _swung(onset, swing)
    b = _swung(onset + length, swing)
    return bar.start_sec + a * bar.beat_sec, max(0.05, (b - a) * bar.beat_sec)


def _ladder(chord: str, low: int, high: int) -> list[int]:
    """Every chord tone the horns may play on ``chord`` (no root, no bass note) between ``low`` and ``high``."""
    guides, tones = bh.section_tones(chord)
    pcs = set(tones) | set(guides)
    return [m for m in range(low, high + 1) if m % 12 in pcs]


def _figure_range(h: bh.Horn) -> tuple[int, int]:
    lo, hi, _ = h.background
    return lo, min(h.high - 2, hi + 3)


def figure_pitches(
    bar: ArrBar, cell, h: bh.Horn, *, start_near: int, contour: str, rng: random.Random, next_chord: str = ""
) -> list[int]:
    """Pitches for a figure: chord tones of the chord under each note, moving by ladder steps in ``contour``
    (up / down / arch / valley), starting near ``start_near``; the last (longest) note lands on a guide tone,
    of the next chord when the figure ends the bar, and a short note before it may approach it by a half step."""
    lo, hi = _figure_range(h)
    n = len(cell)
    pitches: list[int] = []
    cur = start_near
    for i, (onset, _length) in enumerate(cell):
        ladder = _ladder(bar.chord_at(onset), lo, hi) or list(range(lo, hi + 1))
        if not pitches:
            cur = min(ladder, key=lambda m: (abs(m - cur), -m))
        else:
            if contour == "up":
                step = 1
            elif contour == "down":
                step = -1
            elif contour == "arch":
                step = 1 if i < (n + 1) // 2 else -1
            else:  # valley
                step = -1 if i < (n + 1) // 2 else 1
            if rng.random() < 0.25:
                step *= 2  # a small leap now and then
            above = [m for m in ladder if m > cur]
            below = [m for m in ladder if m < cur]
            if step > 0:
                cur = above[min(step, len(above)) - 1] if above else (below[-1] if below else cur)
            else:
                cur = below[-min(-step, len(below))] if below else (above[0] if above else cur)
        pitches.append(cur)
    # The last note: a guide tone of the chord under it - the one nearest the next chord's guide tones, so
    # the line resolves by step into the new bar.
    last_onset, _last_len = cell[-1]
    guides, _ = bh.section_tones(bar.chord_at(last_onset))
    goal = [m for m in range(lo, hi + 1) if m % 12 in set(guides)]
    if goal:
        near = [m for m in goal if abs(m - pitches[-1]) <= 4] or goal
        if next_chord:
            nxt_guides, _ = bh.section_tones(next_chord)
            nxt = [m for m in range(lo - 2, hi + 3) if m % 12 in set(nxt_guides)]
            pitches[-1] = min(near, key=lambda m: (min((abs(m - x) for x in nxt), default=0), abs(m - pitches[-1]), -m))
        else:
            pitches[-1] = min(near, key=lambda m: (abs(m - pitches[-1]), -m))
    if n >= 3 and rng.random() < 0.35 and cell[-2][1] <= 0.5:
        approach = pitches[-1] - 1 if rng.random() < 0.6 else pitches[-1] + 1  # chromatic approach
        if lo <= approach <= hi:
            pitches[-2] = approach
    return pitches


def harmonise_below(top_pitch: int, chord: str, h: bh.Horn) -> int:
    """The lower horn's note under ``top_pitch``: a chord tone a third, sixth or tenth below in its
    register (a fourth, fifth, seventh or eleventh if none), never the root or bass, never a unison."""
    lo, hi, _ = h.background
    hi = min(hi, top_pitch - 3)
    ladder = _ladder(chord, lo, hi)
    for intervals in (bh.SECTION_INTERVALS, bh._FALLBACK_INTERVALS):
        cands = [m for m in ladder if top_pitch - m in intervals]
        if cands:
            return max(cands)  # the closest harmony under the lead
    return bh.clamp_to_range(top_pitch - 12, lo, max(lo, hi))


@dataclass
class _Writer:
    top: bh.Horn
    bottom: bh.Horn
    swing: float
    base_velocity: float
    rng: random.Random
    voicing: dict[tuple[int, int], tuple[int, int]]  # (bar index, chord number in bar) -> (top, bottom)
    notes: dict[str, list[bh.HornNote]] = field(default_factory=lambda: {"top": [], "bottom": []})
    last: dict[str, int] = field(default_factory=dict)

    def horn(self, who: str) -> bh.Horn:
        return self.top if who == "top" else self.bottom

    def add(self, who: str, start: float, dur: float, midi: int, velocity: float, *, art: str | None = None, swell: float = 0.0) -> None:
        h = self.horn(who)
        lo, hi = _figure_range(h)
        midi = bh.clamp_to_range(midi, max(h.low, lo - 2), min(h.high, hi))
        jitter = self.rng.uniform(-_JITTER_SEC, _JITTER_SEC)
        start = max(0.0, start + _SEAT_SEC[who] + jitter)
        v = min(1.0, max(0.2, velocity + self.rng.uniform(-0.03, 0.03)))
        if art is None:
            art = bh.choose_articulation(dur)
        self.notes[who].append(bh.HornNote(start, dur, int(midi), v, art, 0, swell=swell))
        self.last[who] = int(midi)

    # Held lines --------------------------------------------------------------------------------------
    def held(self, who: str, bars: Sequence[ArrBar], velocity: float, *, from_beat: float = 0.0, swell_first: float = 0.0,
             fade_last: bool = True) -> None:
        """``who`` holds its voicing pitch for each chord of ``bars`` (tied where it repeats), breathing at the end."""
        k = 0 if who == "top" else 1
        segments: list[list] = []  # [start, end, midi]
        for bar in bars:
            for ci, (chord, a, b) in enumerate(bar.chords):
                if bar is bars[0] and b <= from_beat:
                    continue
                a = max(a, from_beat) if bar is bars[0] else a
                midi = self.voicing.get((bar.index, ci), (None, None))[k]
                if midi is None:
                    continue
                s, e = bar.start_sec + a * bar.beat_sec, bar.start_sec + b * bar.beat_sec
                if segments and segments[-1][2] == midi and abs(segments[-1][1] - s) < 1e-6:
                    segments[-1][1] = e
                else:
                    segments.append([s, e, midi])
        if not segments:
            return
        beat = bars[-1].beat_sec
        for i, (s, e, midi) in enumerate(segments):
            last = i == len(segments) - 1
            dur = (e - s) - (max(bh.BREATH_SEC, beat) if last else bh.TONGUE_GAP_SEC)
            if dur < 0.12:
                continue
            p = i / max(1, len(segments) - 1)
            v = velocity * (0.92 + 0.16 * math.sin(math.pi * p))  # a phrase arc
            swell = swell_first if i == 0 else (-3.0 if (last and fade_last) else 0.0)
            self.add(who, s, dur, midi, v, art="sustain", swell=swell)

    # Figures -----------------------------------------------------------------------------------------
    def figure(self, who: str, bar: ArrBar, cell, velocity: float, contour: str, next_chord: str) -> list[int]:
        h = self.horn(who)
        near = self.last.get(who, h.background[2])
        pitches = figure_pitches(bar, cell, h, start_near=near, contour=contour, rng=self.rng, next_chord=next_chord)
        self._play_cell(who, bar, cell, pitches, velocity)
        return pitches

    def _play_cell(self, who: str, bar: ArrBar, cell, pitches, velocity: float) -> None:
        for i, ((onset, length), midi) in enumerate(zip(cell, pitches)):
            start, dur = _span_sec(bar, onset, length, self.swing)
            last = i == len(cell) - 1
            accent = 0.06 if abs(onset % 1 - 0.5) < 1e-6 else 0.0  # off-beats lean in, as horn players phrase
            dur = dur - bh.TONGUE_GAP_SEC if not last else dur * 0.9
            self.add(who, start, max(0.06, dur), midi, velocity + accent + (0.03 if last else 0.0),
                     swell=-2.0 if (last and dur > 0.5) else 0.0)

    def harmonised_cell(self, bar: ArrBar, cell, velocity: float, contour: str, next_chord: str) -> list[int]:
        tops = self.figure("top", bar, cell, velocity, contour, next_chord)
        lows = [harmonise_below(t, bar.chord_at(onset), self.bottom) for t, (onset, _ln) in zip(tops, cell)]
        self._play_cell("bottom", bar, cell, lows, velocity - 0.04)
        return tops

    def shots(self, bar: ArrBar, beats: Sequence[float], velocity: float, *, hold_last: bool = False) -> None:
        for j, b in enumerate(beats):
            if b >= bar.beats:
                continue
            chord_i = next((ci for ci, (_c, a, e) in enumerate(bar.chords) if a - 1e-9 <= b < e), len(bar.chords) - 1)
            t, lo = self.voicing.get((bar.index, chord_i), (None, None))
            if t is None:
                continue
            start, _ = _span_sec(bar, b, 0.5, self.swing)
            last = j == len(beats) - 1
            if hold_last and last:
                dur = max(0.4, (bar.beats - _swung(b, self.swing)) * bar.beat_sec - bh.BREATH_SEC)
                self.add("top", start, dur, t, velocity, art="sustain", swell=-3.0)
                self.add("bottom", start, dur, lo, velocity - 0.04, art="sustain", swell=-3.0)
            else:
                self.add("top", start, HIT_SEC, t, velocity + 0.05, art="staccato")
                self.add("bottom", start, HIT_SEC, lo, velocity + 0.01, art="staccato")


def _next_chord(bars: Sequence[ArrBar], i: int, all_bars: Sequence[ArrBar]) -> str:
    bar = bars[i]
    nxt = next((b for b in all_bars if b.index == bar.index + 1), None)
    return nxt.chords[0][0] if nxt is not None and nxt.chords else ""


def arrange(
    bars: Sequence[ArrBar],
    *,
    top: str = "trumpet",
    bottom: str = "tenor",
    intensity: str = "Medium",
    mood: str = "",
    level: str = "",
    swing: float = 0.5,
    seed: int = 0,
) -> Arrangement:
    """The two horns' notes for the take, phrase by phrase (see the module doc)."""
    hi_h, lo_h = bh.horn(top), bh.horn(bottom)
    bars = [b for b in bars if b.chords]
    if not bars:
        return Arrangement(top, bottom, {top: [], bottom: []}, ())
    keys = [(b.index, ci) for b in bars for ci in range(len(b.chords))]
    pairs = bh.section_voicing([c for b in bars for c, _a, _e in b.chords], top=top, bottom=bottom)
    voicing = dict(zip(keys, pairs))
    inten = intensity if intensity in _BASE_VELOCITY else "Medium"
    rng = random.Random(zlib.crc32(f"horn-arranger:{seed}:{top}:{bottom}".encode()))
    w = _Writer(hi_h, lo_h, swing, _BASE_VELOCITY[inten], rng, voicing)
    w.last = {"top": hi_h.background[2], "bottom": lo_h.background[2]}
    phrases = phrases_of(bars)
    textures = choose_textures(phrases, intensity=inten, mood=mood, level=level, seed=seed)
    callers = ("top", "bottom")
    n_call = n_solo = 0
    for ph, tex in zip(phrases, textures):
        ph.texture = tex
        v = w.base_velocity + _TEXTURE_DYNAMIC.get(tex, 0.0) + (0.03 if ph.first_of_section and tex != "rest" else 0.0)
        pb = ph.bars
        if tex == "solo_pad":
            who = "bottom" if n_solo % 2 == 0 else "top"  # the tenor first, then the trumpet
            n_solo += 1
            w.held(who, pb, v, swell_first=2.0)
        elif tex == "staggered":
            w.held("bottom", pb, v, swell_first=2.0)
            enter = pb[min(2, len(pb) - 1)] if len(pb) > 2 else pb[-1]
            w.held("top", [b for b in pb if b.index >= enter.index], v - 0.03, from_beat=0.0 if len(pb) > 2 else 2.0,
                   swell_first=3.0)
        elif tex == "pad":
            w.held("bottom", pb, v - 0.04, swell_first=3.0)
            w.held("top", pb, v, swell_first=3.0)
        elif tex == "call":
            caller = callers[n_call % 2]
            answerer = "bottom" if caller == "top" else "top"
            n_call += 1
            cell = FIGURE_CELLS[rng.randrange(len(FIGURE_CELLS))]
            contour = rng.choice(("up", "down", "arch", "valley"))
            flipped = {"up": "down", "down": "up", "arch": "valley", "valley": "arch"}[contour]
            w.figure(caller, pb[0], cell, v, contour, _next_chord(pb, 0, bars))
            if len(pb) >= 3:
                w.figure(answerer, pb[2], cell, v - 0.03, flipped, _next_chord(pb, 2, bars))
            elif len(pb) == 2:
                w.figure(answerer, pb[1], cell, v - 0.03, flipped, _next_chord(pb, 1, bars))
            if len(pb) >= 4 and not ph.leads_into_section and rng.random() < 0.5:
                w.shots(pb[3], (1.5, 2.0), v, hold_last=True)  # both close the phrase together
            ph.detail.update(caller=caller, cell=cell)
        elif tex == "riff":
            cell = FIGURE_CELLS[rng.randrange(len(FIGURE_CELLS))]
            contour = rng.choice(("up", "down", "arch", "valley"))
            w.harmonised_cell(pb[0], cell, v, contour, _next_chord(pb, 0, bars))
            if len(pb) >= 3:
                w.last["top"] = w.top.background[2] if rng.random() < 0.3 else w.last["top"]
                w.harmonised_cell(pb[2], cell, v + 0.03, contour, _next_chord(pb, 2, bars))  # the riff again, on its new chord
            ph.detail.update(cell=cell)
        elif tex == "hits":
            pattern = HIT_PATTERNS[rng.randrange(len(HIT_PATTERNS))]
            for i, bar in enumerate(pb):
                if i == len(pb) - 1:
                    w.shots(bar, (pattern[0],), v, hold_last=True)
                elif i % 2 == 0 or rng.random() < 0.5:
                    w.shots(bar, pattern, v)
        if ph.leads_into_section and tex not in ("hits",):
            # Set the next section up: two shots on the "and" of 3 and of 4 of the phrase's last bar.
            last_bar = pb[-1]
            cut = last_bar.start_sec + 2.25 * last_bar.beat_sec
            for who in ("top", "bottom"):
                w.notes[who] = _clip_before(w.notes[who], cut)
            w.shots(last_bar, SETUP_BEATS, v + 0.08)
    notes = {top: bh.breathe(w.notes["top"]), bottom: bh.breathe(w.notes["bottom"])}
    return Arrangement(top, bottom, notes, tuple((ph.bars[0].index, ph.texture) for ph in phrases))


def _clip_before(notes: list[bh.HornNote], t: float) -> list[bh.HornNote]:
    """Notes that would still sound at ``t`` end a tongue's gap before it (or go, if that leaves nothing)."""
    out = []
    for n in notes:
        if n.start_sec >= t - 0.05:
            continue
        if n.start_sec + n.dur_sec > t - bh.TONGUE_GAP_SEC:
            d = t - bh.TONGUE_GAP_SEC - n.start_sec
            if d < 0.1:
                continue
            n = replace(n, dur_sec=d)
        out.append(n)
    return out


def arranger_tag(top: str, bottom: str) -> str:
    return f"+hornarr{ARRANGER_VERSION}-{top[:2]}{bottom[:2]}"

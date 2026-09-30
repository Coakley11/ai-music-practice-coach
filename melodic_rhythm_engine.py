"""Reusable melodic rhythm engine — musical timing for an existing pitch sequence.

Layering (beside ``melodic_pattern_engine``)::

    melodic_pattern_engine  → notes + per-note roles (target, chord tone, approach …)
    melodic_rhythm_engine   → THIS MODULE: onsets / durations / rests / tuplets per bar
    improvisation_motif     → motif dict (``rhythm_events``), ABC renderer, Change Rhythm
    motif_engine            → public facade

The engine never sees or changes pitches. It answers one question: given ``n``
notes, a meter, a student level, and (optionally) what each note does musically,
which bar-aligned rhythms are good practice rhythms — ranked best first.

Representation
--------------
Time is exact: :class:`fractions.Fraction` in quarter-note units (a 4/4 bar is 4,
a 6/8 bar is 3). A :class:`RhythmEvent` is a note (``note`` = index into the pitch
list) or a rest, with its onset, sounding ``duration``, ``written`` value, and an
optional tuplet ``(p, q)`` — *p* notes in the time of *q* (eighth triplet: written
1/2, duration 1/3, tuplet (3, 2)).

Vocabulary
----------
Rhythms are built from small beat-level :class:`Figure`\\ s (quarter, two eighths,
dotted-quarter + eighth, eighth triplet, off-beat entry, 6/8 long-short, …), each
with a family, a level, and alignment rules. Figures tile a bar exactly and never
cross a barline, so every candidate fills its bars. Compound meters (6/8, 9/8,
12/8) use their own dotted-quarter-beat figures — never simple-meter templates.

Ranking
-------
Candidates are scored by: structurally important notes (targets, guide tones,
chord tones) on strong beats and chromatic ornaments off them; level fit (at the
student's level, simpler ones still eligible); and penalties for fragmentation,
rests, and monotony. Ties break deterministically by ``seed``.

Consumers
---------
Phrase / Motif patterns use this now. Missions, AMI (``music_coach_ami``), and
Composition examples can call :func:`rhythm_candidates` the same way later: pass
the pitch count, meter, level, and per-note roles; read ``events``.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from fractions import Fraction
from functools import cached_property, lru_cache
from typing import Any, Sequence

LEVELS: tuple[str, ...] = ("Beginner", "Intermediate", "Advanced")
_LEVEL_RANK = {lvl: i for i, lvl in enumerate(LEVELS)}

F = Fraction
_ZERO = F(0)


def normalize_level(level: str) -> str:
    low = str(level or "").lower()
    if "begin" in low:
        return "Beginner"
    if "adv" in low:
        return "Advanced"
    return "Intermediate"


# --------------------------------------------------------------------------- meter


@dataclass(frozen=True)
class Meter:
    token: str
    numerator: int
    denominator: int
    bar: Fraction  # bar length in quarter notes
    beat: Fraction  # main pulse (quarter, half, or dotted quarter for compound)
    compound: bool

    def strength(self, pos: Fraction) -> float:
        """Metric strength of a position within the bar (1.0 = downbeat)."""
        return _strength(self, F(pos) % self.bar)

    def _strength_uncached(self, pos: Fraction) -> float:
        if pos == 0:
            return 1.0
        n_beats = int(self.bar / self.beat)
        if pos % self.beat == 0:
            k = int(pos / self.beat)
            # Mid-bar pulse in even-beat meters (4/4 beat 3, 12/8 beat 3) is secondary-strong.
            if n_beats % 2 == 0 and n_beats >= 4 and k == n_beats // 2:
                return 0.8
            if self.compound and n_beats == 2:
                return 0.8  # 6/8: the second dotted-quarter pulse
            return 0.55
        sub = self.beat / (3 if self.compound else 2)  # compound: eighths inside the beat
        if pos % sub == 0:
            return 0.3 if not self.compound else 0.35
        return 0.15


@lru_cache(maxsize=8192)
def _strength(meter: Meter, pos: Fraction) -> float:
    return meter._strength_uncached(pos)


@lru_cache(maxsize=64)
def parse_meter(token: str) -> Meter:
    text = str(token or "4/4").strip() or "4/4"
    try:
        num_s, den_s = text.split("/", 1)
        num, den = int(num_s), int(den_s)
    except (ValueError, TypeError):
        num, den = 4, 4
    if num <= 0 or den not in (2, 4, 8, 16):
        num, den = 4, 4
    bar = F(num * 4, den)
    compound = den == 8 and num % 3 == 0 and num >= 6
    if compound:
        beat = F(3, 2)
    elif den == 2:
        beat = F(2)
    else:
        beat = F(4, den)
    return Meter(token=f"{num}/{den}", numerator=num, denominator=den, bar=bar, beat=beat, compound=compound)


# --------------------------------------------------------------------------- figures


@dataclass(frozen=True)
class Figure:
    """A beat-level rhythm cell: written parts (duration, is_rest), optional tuplet."""

    id: str
    family: str  # straight | dotted | syncopated | triplet | rest | compound
    level: str
    parts: tuple[tuple[Fraction, bool], ...]
    tuplet: tuple[int, int] | None = None
    compound: bool = False  # True: for compound meters only; False: simple meters only

    @cached_property
    def span(self) -> Fraction:
        written = sum((d for d, _ in self.parts), _ZERO)
        if self.tuplet:
            p, q = self.tuplet
            return written * q / p
        return written

    @cached_property
    def notes(self) -> int:
        return sum(1 for _, rest in self.parts if not rest)

    @cached_property
    def rests(self) -> int:
        return sum(1 for _, rest in self.parts if rest)


def _fig(id_: str, family: str, level: str, parts: Sequence[tuple[Any, bool] | Any], *,
         tuplet: tuple[int, int] | None = None, compound: bool = False) -> Figure:
    norm: list[tuple[Fraction, bool]] = []
    for part in parts:
        if isinstance(part, tuple):
            norm.append((F(part[0]), bool(part[1])))
        else:
            norm.append((F(part), False))
    return Figure(id_, family, level, tuple(norm), tuplet, compound)


R = True  # marks a rest part

FIGURES: tuple[Figure, ...] = (
    # ---- simple meters (beat = quarter note)
    _fig("q", "straight", "Beginner", [1]),
    _fig("ee", "straight", "Beginner", ["1/2", "1/2"]),
    _fig("h", "straight", "Beginner", [2]),
    _fig("dh", "straight", "Beginner", [3]),
    _fig("w", "straight", "Beginner", [4]),
    _fig("qd_e", "dotted", "Intermediate", ["3/2", "1/2"]),
    _fig("e_qd", "syncopated", "Intermediate", ["1/2", "3/2"]),
    _fig("e_q_e", "syncopated", "Intermediate", ["1/2", 1, "1/2"]),
    _fig("r_e", "syncopated", "Intermediate", [("1/2", R), "1/2"]),
    _fig("e_r", "rest", "Intermediate", ["1/2", ("1/2", R)]),
    _fig("r_q", "rest", "Intermediate", [(1, R)]),
    _fig("ssss", "straight", "Intermediate", ["1/4"] * 4),
    _fig("e_ss", "straight", "Intermediate", ["1/2", "1/4", "1/4"]),
    _fig("ss_e", "straight", "Intermediate", ["1/4", "1/4", "1/2"]),
    _fig("trip_e", "triplet", "Intermediate", ["1/2"] * 3, tuplet=(3, 2)),
    _fig("de_s", "dotted", "Advanced", ["3/4", "1/4"]),
    _fig("s_de", "syncopated", "Advanced", ["1/4", "3/4"]),
    _fig("s_e_s", "syncopated", "Advanced", ["1/4", "1/2", "1/4"]),
    _fig("trip_q", "triplet", "Advanced", [1] * 3, tuplet=(3, 2)),
    # ---- compound meters (beat = dotted quarter)
    _fig("c_dq", "compound", "Beginner", ["3/2"], compound=True),
    _fig("c_eee", "compound", "Beginner", ["1/2"] * 3, compound=True),
    _fig("c_qe", "compound", "Beginner", [1, "1/2"], compound=True),
    _fig("c_dh", "compound", "Beginner", [3], compound=True),
    _fig("c_eq", "syncopated", "Intermediate", ["1/2", 1], compound=True),
    _fig("c_des_e", "dotted", "Intermediate", ["3/4", "1/4", "1/2"], compound=True),
    _fig("c_ssee", "compound", "Intermediate", ["1/4", "1/4", "1/2", "1/2"], compound=True),
    _fig("c_eess", "compound", "Intermediate", ["1/2", "1/2", "1/4", "1/4"], compound=True),
    _fig("c_r_ee", "rest", "Intermediate", [("1/2", R), "1/2", "1/2"], compound=True),
    _fig("c_duplet", "triplet", "Advanced", ["1/2", "1/2"], tuplet=(2, 3), compound=True),
    _fig("c_esse", "syncopated", "Advanced", ["1/2", "1/4", "1/4", "1/2"], compound=True),
)
FIGURES_BY_ID: dict[str, Figure] = {f.id: f for f in FIGURES}


def _placement_ok(fig: Figure, pos: Fraction, meter: Meter) -> tuple[bool, bool]:
    """(allowed, displaced): may ``fig`` start at bar position ``pos``?"""
    return _placement_cached(fig.id, pos, meter)


@lru_cache(maxsize=16384)
def _placement_cached(fid: str, pos: Fraction, meter: Meter) -> tuple[bool, bool]:
    fig = FIGURES_BY_ID[fid]
    if pos + fig.span > meter.bar:
        return False, False
    if meter.compound:
        return pos % meter.beat == 0 and (fig.span < meter.bar or pos == 0), False
    beat = meter.beat
    if pos % beat != 0:
        return False, False
    span_beats = fig.span / beat
    beats_in_bar = int(meter.bar / beat)
    if span_beats <= 1:
        return True, False
    if span_beats == beats_in_bar:
        return pos == 0, False
    if span_beats == 2:
        if beats_in_bar == 4:
            # Half-bar figures sit on beat 1 or 3; on beat 2 they displace the bar.
            return True, int(pos / beat) % 2 == 1
        return True, False  # 3/4: beat 1 or 2 are both natural
    if span_beats == 3:
        return int(pos / beat) <= beats_in_bar - 3, False
    return pos == 0, False


# --------------------------------------------------------------------------- realization


@dataclass(frozen=True)
class RhythmEvent:
    onset: Fraction
    duration: Fraction
    written: Fraction
    rest: bool = False
    tuplet: tuple[int, int] | None = None
    tuplet_start: bool = False
    note: int | None = None  # index into the pitch list (None for rests)

    def to_json(self) -> dict[str, Any]:
        return {
            "on": str(self.onset),
            "dur": str(self.duration),
            "w": str(self.written),
            "rest": self.rest,
            "tup": list(self.tuplet) if self.tuplet else None,
            "ts": self.tuplet_start,
            "n": self.note,
        }

    @staticmethod
    def from_json(data: dict[str, Any]) -> "RhythmEvent":
        tup = data.get("tup")
        return RhythmEvent(
            onset=F(str(data["on"])),
            duration=F(str(data["dur"])),
            written=F(str(data.get("w") or data["dur"])),
            rest=bool(data.get("rest")),
            tuplet=(int(tup[0]), int(tup[1])) if tup else None,
            tuplet_start=bool(data.get("ts")),
            note=None if data.get("n") is None else int(data["n"]),
        )


@dataclass(frozen=True)
class BarRhythm:
    """One bar as a sequence of figures (the reusable unit of variety)."""

    figures: tuple[str, ...]
    level: str
    families: tuple[str, ...]
    displaced: bool = False

    @property
    def id(self) -> str:
        return "+".join(self.figures) + ("~" if self.displaced else "")

    @property
    def notes(self) -> int:
        return sum(FIGURES_BY_ID[f].notes for f in self.figures)


@dataclass(frozen=True)
class RhythmRealization:
    id: str
    meter: str
    level: str  # hardest figure used
    families: tuple[str, ...]
    bars: int
    unit_bars: int  # bars per repeating unit (patterns) — equals ``bars`` for free phrases
    events: tuple[RhythmEvent, ...]
    score: float = 0.0
    signature: tuple = field(default=(), compare=False)

    @property
    def note_events(self) -> list[RhythmEvent]:
        return [e for e in self.events if not e.rest]

    @property
    def total(self) -> Fraction:
        return sum((e.duration for e in self.events), _ZERO)

    def events_json(self) -> list[dict[str, Any]]:
        return [e.to_json() for e in self.events]


def _bar_events(bar: BarRhythm, start: Fraction, first_note: int) -> tuple[list[RhythmEvent], int]:
    events: list[RhythmEvent] = []
    pos = start
    note = first_note
    for fid in bar.figures:
        fig = FIGURES_BY_ID[fid]
        ratio = F(fig.tuplet[1], fig.tuplet[0]) if fig.tuplet else F(1)
        for k, (written, rest) in enumerate(fig.parts):
            dur = written * ratio
            events.append(
                RhythmEvent(
                    onset=pos,
                    duration=dur,
                    written=written,
                    rest=rest,
                    tuplet=fig.tuplet,
                    tuplet_start=bool(fig.tuplet) and k == 0,
                    note=None if rest else note,
                )
            )
            if not rest:
                note += 1
            pos += dur
    return events, note


# --------------------------------------------------------------------------- enumeration


@lru_cache(maxsize=512)
def bar_rhythms(meter_token: str, n_notes: int, level: str, *, final: bool = False) -> tuple[BarRhythm, ...]:
    """Every figure sequence that fills one bar with exactly ``n_notes`` notes.

    At most one rest per bar; a rest is never the bar's last event when ``final``
    (phrases end on a note). Figures above ``level`` are excluded.
    """
    meter = parse_meter(meter_token)
    rank = _LEVEL_RANK[normalize_level(level)]
    usable = [
        f for f in FIGURES
        if f.compound == meter.compound and _LEVEL_RANK[f.level] <= rank and f.span <= meter.bar
    ]
    out: list[BarRhythm] = []
    densest = max((f.notes / f.span for f in usable), default=F(1))

    def walk(pos: Fraction, remaining: int, rests: int, chosen: list[str], displaced: bool) -> None:
        if len(out) >= 2500:
            return
        if remaining > densest * (meter.bar - pos):
            return  # the rest of the bar cannot hold the remaining notes
        if pos == meter.bar:
            if remaining == 0:
                figs = [FIGURES_BY_ID[c] for c in chosen]
                if final and figs[-1].parts[-1][1]:
                    return
                lvl = max((f.level for f in figs), key=lambda x: _LEVEL_RANK[x])
                if displaced and _LEVEL_RANK[lvl] < _LEVEL_RANK["Advanced"]:
                    lvl = "Advanced"
                if _LEVEL_RANK[lvl] > rank:
                    return
                fams = tuple(sorted({f.family for f in figs} | ({"syncopated"} if displaced else set())))
                out.append(BarRhythm(tuple(chosen), lvl, fams, displaced))
            return
        for fig in usable:
            if fig.notes > remaining or rests + fig.rests > 1:
                continue
            ok, disp = _placement_ok(fig, pos, meter)
            if not ok:
                continue
            chosen.append(fig.id)
            walk(pos + fig.span, remaining - fig.notes, rests + fig.rests, chosen, displaced or disp)
            chosen.pop()

    walk(_ZERO, int(n_notes), 0, [], False)
    return tuple(out)


def max_notes_per_bar(meter_token: str, level: str) -> int:
    meter = parse_meter(meter_token)
    rank = _LEVEL_RANK[normalize_level(level)]
    dens = max(
        (f.notes / f.span for f in FIGURES if f.compound == meter.compound and _LEVEL_RANK[f.level] <= rank),
        default=F(1),
    )
    return int(meter.bar * dens)


# --------------------------------------------------------------------------- scoring

ROLE_WEIGHTS: dict[str, float] = {
    "target": 1.5,  # resolution targets matter most
    "guide_tone": 0.8,
    "chord_tone": 0.6,
    "scale": 0.2,
    "neighbor": -0.3,
    "approach": -0.5,
    "passing": -0.5,
}
_DEFAULT_ROLE_WEIGHT = 0.3


def _role_fit(events: Sequence[RhythmEvent], roles: Sequence[str | None] | None, meter: Meter) -> float:
    notes = [e for e in events if not e.rest]
    if not notes:
        return 0.0
    total = 0.0
    for e in notes:
        role = roles[e.note] if roles and e.note is not None and e.note < len(roles) else None
        w = ROLE_WEIGHTS.get(str(role), _DEFAULT_ROLE_WEIGHT) if role else _DEFAULT_ROLE_WEIGHT
        total += w * meter.strength(e.onset % meter.bar)
    return total / len(notes)


def _style_score(
    bars: Sequence[BarRhythm], events: Sequence[RhythmEvent], level: str, *, final: bool = True
) -> float:
    """Level fit and practice-rhythm hygiene (small next to role fit).

    The at-level bonus is deliberately modest so simpler rhythms stay competitive:
    an Advanced student should not get a maximally busy rhythm every time.
    """
    rank = _LEVEL_RANK[level]
    lvl = max((b.level for b in bars), key=lambda x: _LEVEL_RANK[x])
    gap = rank - _LEVEL_RANK[lvl]
    score = {0: 0.08, 1: 0.06}.get(gap, 0.0)
    notes = [e for e in events if not e.rest]
    sixteenths = sum(1 for e in notes if e.duration < F(1, 2) and not e.tuplet)
    score -= (0.04 if rank < 2 else 0.02) * sixteenths
    score -= 0.08 * sum(1 for e in events if e.rest)
    if rank >= 1 and len({e.duration for e in notes}) == 1 and len(notes) > 2:
        score -= 0.08  # monotony
    if rank == 0 and all(set(b.families) <= {"straight", "compound"} for b in bars):
        score += 0.1
    if final and notes and notes[-1].duration >= 1:
        score += 0.02  # a settled ending (never outweighs placing a target)
    return score


def _tiebreak(rid: str, seed: int) -> int:
    return zlib.crc32(f"{rid}|{seed}".encode("utf-8"))


def _signature(events: Sequence[RhythmEvent]) -> tuple:
    return tuple((e.duration, e.rest, e.tuplet) for e in events)


# --------------------------------------------------------------------------- candidates


def _unit_bar_counts(n: int, bars: int, cap: int) -> list[tuple[int, ...]]:
    """Ways to split ``n`` notes over ``bars`` bars (each 1..cap), front-loaded first."""
    out: list[tuple[int, ...]] = []

    def walk(i: int, remaining: int, acc: list[int]) -> None:
        if i == bars:
            if remaining == 0:
                out.append(tuple(acc))
            return
        left = bars - i - 1
        for c in range(min(cap, remaining - left), 0, -1):
            if remaining - c > left * cap:
                break
            acc.append(c)
            walk(i + 1, remaining - c, acc)
            acc.pop()

    walk(0, n, [])
    out.sort(key=lambda t: (max(t) - min(t), [-x for x in t]))  # even splits, longer ending
    return out


def _preferred_per_bar(meter: Meter, level: str) -> int:
    """Comfortable notes per bar for a free phrase: ~1/beat Beginner, 1.5 Intermediate, 2 Advanced."""
    per_beat = {"Beginner": 1, "Intermediate": F(3, 2), "Advanced": 2}[level]
    if meter.compound:
        return max(2, int(meter.bar / meter.beat * (2 if level == "Beginner" else 3)))
    return max(2, int(meter.bar * per_beat))


def _assemble(
    bar_seq: Sequence[BarRhythm], meter: Meter, level: str, roles: Sequence[str | None] | None,
    seed: int, *, repeat: int = 1, unit_bars: int | None = None, prefix: str = "phrase",
) -> RhythmRealization:
    events: list[RhythmEvent] = []
    note = 0
    pos = _ZERO
    for _ in range(repeat):
        for bar in bar_seq:
            evs, note = _bar_events(bar, pos, note)
            events.extend(evs)
            pos += meter.bar
    lvl = max((b.level for b in bar_seq), key=lambda x: _LEVEL_RANK[x])
    fams = tuple(sorted({f for b in bar_seq for f in b.families}))
    rid = f"{prefix}:{meter.token}:" + "/".join(b.id for b in bar_seq)
    score = _role_fit(events, roles, meter) + _style_score(bar_seq, events, level)
    return RhythmRealization(
        id=rid,
        meter=meter.token,
        level=lvl,
        families=fams,
        bars=len(bar_seq) * repeat,
        unit_bars=unit_bars or len(bar_seq),
        events=tuple(events),
        score=round(score, 6),
        signature=_signature(events),
    )


def rhythm_candidates(
    n_notes: int,
    *,
    meter: str = "4/4",
    level: str = "Intermediate",
    roles: Sequence[str | None] | None = None,
    group_size: int | None = None,
    seed: int = 0,
    limit: int = 24,
) -> list[RhythmRealization]:
    """Ranked, de-duplicated rhythm candidates for ``n_notes`` (best first).

    ``group_size``: the pitch list is ``n_notes // group_size`` repeated cells (a
    pattern); one unit rhythm (1–2 bars) is found for a cell and repeated, so every
    cell keeps the same rhythm, as practice patterns do. Without it, the notes form
    one free phrase spread over as many bars as the level's density suggests.

    Deterministic: identical arguments always return the same list in the same order.
    """
    n = int(n_notes)
    if n <= 0:
        return []
    m = parse_meter(meter)
    lvl = normalize_level(level)
    roles_t = tuple(roles) if roles else None
    if group_size and group_size > 0 and n % group_size == 0 and n > group_size:
        return _pattern_candidates(n, m, lvl, roles_t, int(group_size), seed, limit)
    return _phrase_candidates(n, m, lvl, roles_t, seed, limit)


def _unit_bars_for(size: int, meter: Meter, level: str) -> int:
    cap = max_notes_per_bar(meter.token, level)
    for bars in (1, 2, 3, 4):
        if size <= cap * bars and any(
            all(_top_bars(meter.token, c, level, None, 0, False, 1) for c in split)
            for split in _unit_bar_counts(size, bars, cap)[:6]
        ):
            return bars
    return 4


_BEAM_WIDTH = 160


@lru_cache(maxsize=4096)
def _figure_offsets(fid: str) -> tuple[tuple[Fraction, Fraction, bool], ...]:
    """(relative onset, duration, rest) for each part of a figure."""
    fig = FIGURES_BY_ID[fid]
    ratio = F(fig.tuplet[1], fig.tuplet[0]) if fig.tuplet else F(1)
    out = []
    pos = _ZERO
    for written, rest in fig.parts:
        dur = written * ratio
        out.append((pos, dur, rest))
        pos += dur
    return tuple(out)


@lru_cache(maxsize=2048)
def _top_bars(
    meter_token: str, count: int, level: str, roles: tuple | None, offset: int, final: bool, k: int
) -> tuple[BarRhythm, ...]:
    """The ``k`` best single-bar rhythms for ``count`` notes starting at pitch ``offset``.

    Beam search over the bar, one figure at a time. Role fit and the fragmentation/
    rest costs are additive per placed note, so partial bars are ranked while they
    are built; only the best ``_BEAM_WIDTH`` survive each step. Deterministic.
    """
    meter = parse_meter(meter_token)
    rank = _LEVEL_RANK[normalize_level(level)]
    usable = [
        f for f in FIGURES
        if f.compound == meter.compound and _LEVEL_RANK[f.level] <= rank and f.span <= meter.bar
    ]
    densest = max((f.notes / f.span for f in usable), default=F(1))
    six_cost = 0.04 if rank < 2 else 0.02

    def fig_gain(fig: Figure, pos: Fraction, first_note: int) -> float:
        gain = 0.0
        note = first_note
        for rel, dur, rest in _figure_offsets(fig.id):
            if rest:
                gain -= 0.08 * count  # scaled: the final role fit is divided by count
                continue
            role = roles[offset + note] if roles and offset + note < len(roles) else None
            w = ROLE_WEIGHTS.get(str(role), _DEFAULT_ROLE_WEIGHT) if role else _DEFAULT_ROLE_WEIGHT
            gain += w * meter.strength(pos + rel)
            if dur < F(1, 2) and not fig.tuplet:
                gain -= six_cost * count
            note += 1
        return gain

    # state: (partial_gain, pos, notes, rests, chosen, displaced)
    beam: list[tuple[float, Fraction, int, int, tuple[str, ...], bool]] = [(0.0, _ZERO, 0, 0, (), False)]
    complete: list[tuple[float, tuple[str, ...], bool]] = []
    while beam:
        grown: list[tuple[float, Fraction, int, int, tuple[str, ...], bool]] = []
        for gain, pos, notes, rests, chosen, displaced in beam:
            for fig in usable:
                n2 = notes + fig.notes
                if n2 > count or rests + fig.rests > 1:
                    continue
                ok, disp = _placement_ok(fig, pos, meter)
                if not ok:
                    continue
                end = pos + fig.span
                if count - n2 > densest * (meter.bar - end):
                    continue
                g2 = gain + fig_gain(fig, pos, notes)
                state = (g2, end, n2, rests + fig.rests, chosen + (fig.id,), displaced or disp)
                if end == meter.bar:
                    if n2 == count:
                        complete.append((g2, state[4], state[5]))
                else:
                    grown.append(state)
        grown.sort(key=lambda s: (-s[0], s[4]))
        beam = grown[:_BEAM_WIDTH]

    scored: list[tuple[float, str, BarRhythm]] = []
    for _g, chosen, displaced in complete:
        figs = [FIGURES_BY_ID[c] for c in chosen]
        if final and figs[-1].parts[-1][1]:
            continue  # a phrase ends on a note, not a rest
        lvl = max((f.level for f in figs), key=lambda x: _LEVEL_RANK[x])
        if displaced and _LEVEL_RANK[lvl] < _LEVEL_RANK["Advanced"]:
            lvl = "Advanced"
        if _LEVEL_RANK[lvl] > rank:
            continue
        fams = tuple(sorted({f.family for f in figs} | ({"syncopated"} if displaced else set())))
        bar = BarRhythm(tuple(chosen), lvl, fams, displaced)
        evs, _ = _bar_events(bar, _ZERO, offset)
        s = _role_fit(evs, roles, meter) + _style_score([bar], evs, level, final=final)
        scored.append((s, bar.id, bar))
    scored.sort(key=lambda t: (-t[0], t[1]))
    out: list[BarRhythm] = []
    seen: set = set()
    for _s, _id, bar in scored:
        sig = tuple((dur, rest) for fid in bar.figures for _rel, dur, rest in _figure_offsets(fid))
        if sig in seen:
            continue
        seen.add(sig)
        out.append(bar)
        if len(out) >= k:
            break
    return tuple(out)


def _pattern_candidates(
    n: int, meter: Meter, level: str, roles: tuple | None, size: int, seed: int, limit: int
) -> list[RhythmRealization]:
    n_cells = n // size
    unit_bars = _unit_bars_for(size, meter, level)
    cap = max_notes_per_bar(meter.token, level)
    # One rhythm serves every cell: rank it against each position's dominant role.
    cell_roles: tuple | None = None
    if roles and len(roles) >= size:
        cell_roles = tuple(
            _dominant_role([roles[c * size + i] for c in range(n_cells) if c * size + i < len(roles)])
            for i in range(size)
        )
    units: list[RhythmRealization] = []
    for split in _unit_bar_counts(size, unit_bars, cap)[:3]:
        per_bar: list[tuple[BarRhythm, ...]] = []
        offset = 0
        for c in split:
            per_bar.append(_top_bars(meter.token, c, level, cell_roles, offset, False, 40 if unit_bars == 1 else 16))
            offset += c
        if not all(per_bar):
            continue
        for combo in _bar_combos(per_bar):
            units.append(_assemble(combo, meter, level, cell_roles, seed, unit_bars=unit_bars, prefix="cell"))
    out: list[RhythmRealization] = []
    for u in _rank(units, seed, limit):
        bar_seq = [_bar_from_id(bid) for bid in u.id.split(":", 2)[2].split("/")]
        full = _assemble(bar_seq, meter, level, roles, seed, repeat=n_cells, unit_bars=unit_bars, prefix="cell")
        out.append(RhythmRealization(
            id=u.id, meter=full.meter, level=full.level, families=full.families, bars=full.bars,
            unit_bars=unit_bars, events=full.events, score=u.score, signature=u.signature,
        ))
    return out


def _phrase_candidates(
    n: int, meter: Meter, level: str, roles: tuple | None, seed: int, limit: int
) -> list[RhythmRealization]:
    cap = max_notes_per_bar(meter.token, level)
    pref = min(cap, _preferred_per_bar(meter, level))
    bars = max(1, -(-n // pref))
    while bars * cap < n:
        bars += 1
    cands: list[RhythmRealization] = []
    for split in _unit_bar_counts(n, bars, cap)[:2]:
        per_bar: list[tuple[BarRhythm, ...]] = []
        offset = 0
        for i, c in enumerate(split):
            final = i == len(split) - 1
            per_bar.append(_top_bars(meter.token, c, level, roles, offset, final, 40 if bars == 1 else 12))
            offset += c
        if not all(per_bar):
            continue
        for combo in _bar_combos(per_bar):
            cands.append(_assemble(combo, meter, level, roles, seed))
    return _rank(cands, seed, limit)


def _bar_combos(per_bar: Sequence[Sequence[BarRhythm]]):
    """Bar combinations from per-bar rankings: parallel ranks first, then all pairs (2 bars)."""
    width = max(len(b) for b in per_bar)
    for r in range(width):
        yield tuple(b[min(r, len(b) - 1)] for b in per_bar)
    if len(per_bar) == 2:
        for a in per_bar[0]:
            for b in per_bar[1]:
                yield (a, b)


def _bar_from_id(bid: str) -> BarRhythm:
    displaced = bid.endswith("~")
    figs = tuple(bid.rstrip("~").split("+"))
    fobjs = [FIGURES_BY_ID[f] for f in figs]
    lvl = max((f.level for f in fobjs), key=lambda x: _LEVEL_RANK[x])
    if displaced and _LEVEL_RANK[lvl] < 2:
        lvl = "Advanced"
    fams = tuple(sorted({f.family for f in fobjs} | ({"syncopated"} if displaced else set())))
    return BarRhythm(figs, lvl, fams, displaced)


def _dominant_role(roles: Sequence[str | None]) -> str | None:
    vals = [r for r in roles if r]
    if not vals:
        return None
    return max(set(vals), key=lambda r: (vals.count(r), ROLE_WEIGHTS.get(r, 0.0)))


_VARIETY_PENALTY = 0.05


def _rank(cands: Sequence[RhythmRealization], seed: int, limit: int) -> list[RhythmRealization]:
    """Best first, de-duplicated, with a small penalty for repeating a rhythm family mix.

    The penalty spreads straight / dotted / syncopated / triplet / rest ideas through
    the list, so successive Change Rhythm steps sound genuinely different.
    """
    ordered = sorted(cands, key=lambda c: (-c.score, _tiebreak(c.id, seed)))
    unique: list[RhythmRealization] = []
    seen: set = set()
    for c in ordered:
        if c.signature not in seen:
            seen.add(c.signature)
            unique.append(c)
    pool = unique[: max(limit * 8, 64)]
    used: dict[tuple, int] = {}
    out: list[RhythmRealization] = []
    while pool and len(out) < limit:
        best_i = max(
            range(len(pool)),
            key=lambda i: (pool[i].score - _VARIETY_PENALTY * used.get(pool[i].families, 0), -i),
        )
        pick = pool.pop(best_i)
        used[pick.families] = used.get(pick.families, 0) + 1
        out.append(pick)
    return out


# --------------------------------------------------------------------------- public helpers


def realize_rhythm(n_notes: int, *, index: int = 0, **kw: Any) -> RhythmRealization | None:
    cands = rhythm_candidates(n_notes, **kw)
    if not cands:
        return None
    return cands[int(index) % len(cands)]


def next_rhythm(current_id: str, n_notes: int, **kw: Any) -> tuple[int, RhythmRealization] | None:
    """The candidate after ``current_id`` (deterministic wraparound)."""
    cands = rhythm_candidates(n_notes, **kw)
    if not cands:
        return None
    ids = [c.id for c in cands]
    idx = (ids.index(current_id) + 1) % len(cands) if current_id in ids else 0
    if len(cands) > 1 and cands[idx].id == current_id:
        idx = (idx + 1) % len(cands)
    return idx, cands[idx]


def validate_realization(r: RhythmRealization, n_notes: int) -> list[str]:
    """Problems with a realization (empty = valid)."""
    probs: list[str] = []
    meter = parse_meter(r.meter)
    notes = [e for e in r.events if not e.rest]
    if len(notes) != n_notes:
        probs.append(f"{len(notes)} note events for {n_notes} pitches")
    if [e.note for e in notes] != list(range(len(notes))):
        probs.append("note events are not in pitch order")
    pos = _ZERO
    for i, e in enumerate(r.events):
        if e.onset != pos:
            probs.append(f"event {i} onset {e.onset} != {pos}")
        if e.duration <= 0:
            probs.append(f"event {i} has no duration")
        bar_start = (e.onset // meter.bar) * meter.bar
        if e.onset + e.duration > bar_start + meter.bar:
            probs.append(f"event {i} crosses a barline")
        pos = e.onset + e.duration
    if r.total != meter.bar * r.bars:
        probs.append(f"total {r.total} != {r.bars} bars of {meter.bar}")
    for i, e in enumerate(r.events):
        if e.tuplet_start:
            p = e.tuplet[0]
            group = r.events[i:i + p]
            if len(group) != p or any(g.tuplet != e.tuplet for g in group):
                probs.append(f"incomplete tuplet at event {i}")
    return probs


def events_from_json(data: Sequence[dict[str, Any]]) -> list[RhythmEvent]:
    return [RhythmEvent.from_json(d) for d in data]


_DISPLAY = {
    F(4): "𝅝", F(3): "𝅗𝅥.", F(2): "𝅗𝅥", F(3, 2): "♩.", F(1): "♩",
    F(3, 4): "♪.", F(1, 2): "♪", F(1, 4): "♬",
}
_REST_DISPLAY = {F(1): "𝄽", F(1, 2): "𝄾", F(2): "𝄼", F(1, 4): "𝄿"}


def display_rhythm(events: Sequence[RhythmEvent], meter_token: str, *, bars: int | None = None) -> str:
    """Readable rhythm text: note values, rests, tuplet marks, and bar lines."""
    meter = parse_meter(meter_token)
    parts: list[str] = []
    current_bar = 0
    for e in events:
        b = int(e.onset // meter.bar)
        if bars is not None and b >= bars:
            break
        if b != current_bar:
            parts.append("|")
            current_bar = b
        if e.rest:
            parts.append(_REST_DISPLAY.get(e.written, "𝄽"))
            continue
        sym = _DISPLAY.get(e.written, "♩")
        if e.tuplet_start:
            sym = f"{e.tuplet[0]}:" + sym
        parts.append(sym)
    return " ".join(parts)


def legacy_symbol(e: RhythmEvent) -> str:
    """Closest legacy per-note symbol (``improvisation_motif._RHYTHM_BEATS``) for old readers."""
    table = {F(2): "\U0001d15e", F(3, 2): "♩.", F(1): "♩", F(3, 4): "♪", F(1, 2): "♪", F(1, 4): "♬"}
    return table.get(e.duration, table.get(e.written, "♩"))


__all__ = [
    "FIGURES",
    "LEVELS",
    "Meter",
    "RhythmEvent",
    "RhythmRealization",
    "ROLE_WEIGHTS",
    "bar_rhythms",
    "display_rhythm",
    "events_from_json",
    "legacy_symbol",
    "max_notes_per_bar",
    "next_rhythm",
    "normalize_level",
    "parse_meter",
    "realize_rhythm",
    "rhythm_candidates",
    "validate_realization",
]
